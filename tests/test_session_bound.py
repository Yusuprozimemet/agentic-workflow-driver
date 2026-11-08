"""--session-minutes (C06.11): a session that runs past its bound has its tree killed, and the step parks.
With --session-minutes 0.01 and a fake claude that sleeps, --once kills the session's tree, prints the
park line, writes the run log's end line with it, opens the park's issue and exits 1. The driver's
output goes to files, not pipes: the fake's child inherits the driver's stderr, so a pipe would wait
for the child's sleep. A resumed session past its bound parks the same way (a unit test). No report
here names a pid or a path (D03.17)."""

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import drift_of
from tests.test_halt import stop
from tests.test_once import DASHED, driver_copy
from tests.test_once_halt import SESSION, kill_left_over
from tests.test_once_park_issues import build, gh_issues

PARK = re.compile(r"^park: the session ran past 0\.01 minutes \(session `([^`]+)`\)$")


class SessionBoundTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone.
        importlib.import_module("driver.once")
        self.lock = importlib.import_module("driver.lock")
        self.runlog = importlib.import_module("driver.runlog")
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def run_driver(self, minutes):
        # A --once run with the fake claude of SESSION; its output goes to files in its folder.
        folder = Path(tempfile.mkdtemp(dir=self.root))
        flags = build(folder, drift=drift_of(DASHED), do=SESSION)
        copy = driver_copy(tempfile.mkdtemp(dir=self.root))
        self.addCleanup(kill_left_over, folder / "claude")
        with open(folder / "stdout.txt", "wb") as out, open(folder / "stderr.txt", "wb") as err:
            driver = subprocess.Popen(
                [sys.executable, str(copy / "run-steps.py"), "--once", *flags]
                + ["--poll", "0.05", "--session-minutes", minutes],
                stdout=out,
                stderr=err,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        self.addCleanup(stop, driver)
        return folder, driver

    def events(self, state):
        # The run log's lines, read as bytes and decoded as UTF-8.
        text = Path(self.runlog.path(state)).read_bytes().decode("utf-8")
        return [json.loads(line) for line in text.splitlines()]

    def alive(self, pid, deadline):
        while self.lock.process(pid)[0] and time.monotonic() < deadline:
            time.sleep(0.05)
        return self.lock.process(pid)[0]

    def test_session_past_its_bound_parks(self):
        folder, driver = self.run_driver("0.01")
        self.assertEqual(driver.wait(timeout=45), 1)
        stdout = (folder / "stdout.txt").read_bytes().decode("utf-8").splitlines()
        parks = [line for line in stdout if PARK.match(line)]
        self.assertEqual(len(parks), 1, "stdout does not hold exactly one park line for the bound")
        line = parks[0]
        session = PARK.match(line).group(1)
        ends = [e for e in self.events(str(folder / "state")) if e["event"] == "end"]
        self.assertEqual([(e["session"], e["outcome"]) for e in ends], [(session, line)])
        parked = [issue["title"] for issue in gh_issues(folder) if "parked" in issue["labels"]]
        self.assertEqual(parked, [line])

        folder, driver = self.run_driver("0.1")
        self.assertEqual(driver.wait(timeout=45), 1)
        pids = Path(folder, "claude", "pids")
        found = pids.read_bytes().decode("utf-8").split() if pids.exists() else []
        self.assertEqual(len(found), 2, "the session did not start its child in time")
        deadline = time.monotonic() + 10
        for text in found:
            self.assertFalse(self.alive(int(text), deadline), "a process of the session still runs")

    def test_resumed_session_past_its_bound_parks(self):
        loop = importlib.import_module("driver.loop")
        once = importlib.import_module("driver.once")
        github = importlib.import_module("driver.github")
        state = str(Path(tempfile.mkdtemp(dir=self.root)) / "state")
        args = SimpleNamespace(state=state, gh="gh", session_minutes=0.5)
        record = {"issue": 7, "session": "abc", "step": "x"}
        with (
            mock.patch.object(once, "run_session", return_value=once.PAST),
            mock.patch.object(github, "failed_lines", return_value=""),
        ):
            line, code = loop.resume(
                args,
                "project",
                7,
                record,
                ["claude", "--session-id", "abc"],
                [{"name": "tests"}],
                0,
            )
        self.assertEqual(
            (line, code), ("park: the session ran past 0.5 minutes (session `abc`)", 1)
        )
        last = self.events(state)[-1]
        self.assertEqual((last["event"], last["outcome"]), ("end", line))
