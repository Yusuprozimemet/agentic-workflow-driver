"""The halt file set while a session ran (Day 9, C09.13): --once, a resume after red checks and a
resume after the usage limit end in the halt line, with no park issue and no end line. The --once
cases run the driver as tests/test_usage_limit.py does; the resume case calls driver.loop in process."""

import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import test_usage_limit
from tests.test_github import read_calls
from tests.test_usage_limit import (
    DONE,
    LIMITED,
    PLAIN,
    WAITING,
    events,
    limit_records,
    starts_of,
)

HALTED = "halt: the halt file was set while the session ran (session `<uuid>`)"
PREFIX = "day-09/track-c"


def parks_of(folder):
    # The create calls of the park issues: the run's own issue is titled "Driver run".
    calls = read_calls(folder / "gh") if (folder / "gh" / "calls.jsonl").exists() else []
    creates = [call for call in calls if call[:2] == ["issue", "create"]]
    return [call for call in creates if not any("Driver run" in arg for arg in call)]


class HaltRaceTest(unittest.TestCase):
    # The case runner of tests/test_usage_limit.py, without its tests.
    setUpClass = test_usage_limit.UsageLimitTest.__dict__["setUpClass"]
    tearDownClass = test_usage_limit.UsageLimitTest.__dict__["tearDownClass"]
    start = test_usage_limit.UsageLimitTest.start
    finish = test_usage_limit.UsageLimitTest.finish

    def test_halt_file_after_session(self):
        # C09.13: the session wrote the halt file and opened its pull request: the step ends in the
        # halt line, and no pull request is read as its outcome.
        folder, proc = self.start([{"result": DONE, "halt": True}])
        code, lines = self.finish(folder, proc)
        self.assertEqual((code, lines), (1, [HALTED]))
        self.assertEqual(events(folder), ["start", "pid"])
        self.assertEqual(parks_of(folder), [])

    def test_halt_file_after_limit_resume(self):
        # C09.13: the resumed session wrote the halt file: the wait and the resume are as before, and
        # the resumed session's result is not read.
        runs = [
            {"records": limit_records(2), "result": LIMITED},
            {"records": [PLAIN], "result": DONE, "halt": True},
        ]
        folder, proc = self.start(runs)
        code, lines = self.finish(folder, proc)
        first = [text.startswith(WAITING) for text in lines[:1]]
        self.assertEqual(
            (code, len(starts_of(folder)), len(lines), lines[1:], first),
            (1, 2, 2, [HALTED], [True]),
        )
        self.assertEqual(events(folder), ["start", "pid", "end", "pid"])
        self.assertEqual(parks_of(folder), [])

    def test_halt_file_after_resume(self):
        # C09.13: a resume after red checks: the halt file the resumed session wrote ends the step
        # with the halt line, and writes no end line after the fix line.
        loop = importlib.import_module("driver.loop")
        once_module = importlib.import_module("driver.once")
        github = importlib.import_module("driver.github")
        runlog = importlib.import_module("driver.runlog")
        lock = importlib.import_module("driver.lock")
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        state = os.path.join(root, "state")
        runlog.start(state, "x", PREFIX, "abc", "1")
        runlog.pid(state, "abc", os.getpid(), lock.now().strftime(lock.STAMP))
        runlog.end(state, "abc", "park: x", 0, 0)
        args = SimpleNamespace(state=state, gh="gh", poll=30, session_minutes=1)
        record = {"issue": 7, "session": "abc", "step": "x"}
        halt = os.path.join(state, "halt")
        command = [
            sys.executable,
            "-c",
            "import sys; sys.stdin.read(); open(sys.argv[1], 'wb').close()",
            halt,
            "--session-id",
            "abc",
        ]
        with (
            mock.patch.object(github, "failed_lines", return_value=""),
            mock.patch.object(once_module, "outcome", return_value=("opened: #7", 0)),
        ):
            line, code = loop.resume(args, root, 7, record, command, [{"name": "tests"}], 0)
        # Read as bytes, one JSON object per line, as the run log is written.
        with open(runlog.path(state), "rb") as f:
            names = [
                json.loads(text).get("event") for text in f.read().decode("utf-8").splitlines()
            ]
        after = names[names.index("fix") + 1 :] if "fix" in names else None
        expected = HALTED.replace("<uuid>", "abc")
        self.assertEqual((line, code, after), (expected, 1, ["pid"]))
