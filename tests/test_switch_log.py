"""The driver's switch log (<state>/switches.jsonl): a STOP during a session names the session in a halt
line, `run-steps.py halt` and `clear` write their lines, and `on` then `off` write theirs. The run log
keeps its own lines (start, pid) and gets none of these."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import test_once_stop
from tests.test_halt import SwitchTest, new_group, stop
from tests.test_merge_wait import run as run_answer
from tests.test_on import OnCase


def switches(state):
    # Read as bytes and decoded here: the file is written as bytes, one JSON object per line.
    text = Path(state, "switches.jsonl").read_bytes().decode("utf-8")
    return [json.loads(line) for line in text.splitlines()]


def without_at(record):
    return {key: value for key, value in record.items() if key != "at"}


# The helpers are borrowed from the module, not imported by name: an imported TestCase would run its own tests here.
class SwitchLogTest(unittest.TestCase):
    setUp = test_once_stop.OnceStopTest.setUp
    start = test_once_stop.OnceStopTest.start
    wait_pids = test_once_stop.OnceStopTest.wait_pids
    alive = test_once_stop.OnceStopTest.alive
    stopped = test_once_stop.OnceStopTest.stopped

    def test_stop_during_session_names_the_session(self):
        run = self.stopped()
        log = [
            json.loads(line)
            for line in Path(run["state"], "run.jsonl").read_bytes().decode("utf-8").splitlines()
        ]
        self.assertEqual([record.get("event") for record in log], ["start", "pid"])
        session = next(
            (record.get("session") for record in log if record.get("event") == "start"), None
        )
        lines = switches(run["state"])
        self.assertEqual(len(lines), 1)
        # The run's session is shown as a fixed word, so that a failure's report holds no uuid.
        seen = without_at(lines[0])
        if "session" in seen:
            seen["session"] = "<uuid>" if seen["session"] == session else "<another>"
        self.assertEqual(seen, {"event": "halt", "why": "STOP issue #9", "session": "<uuid>"})
        self.assertIsNotNone(re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", lines[0].get("at", "")))

    def test_halt_and_clear_commands(self):
        # A fresh folder for each run: the repository's own state/ folder is never written here.
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, True)
        for command in ("halt", "clear", "clear"):
            subprocess.run(
                [sys.executable, str(ROOT / "run-steps.py"), command, "--state", state],
                capture_output=True,
                check=False,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        self.assertEqual(
            [without_at(line) for line in switches(state)],
            [{"event": "halt", "why": "run-steps.py halt"}, {"event": "clear"}],
        )


class SwitchLogOnTest(OnCase, unittest.TestCase):
    def test_on_then_off(self):
        # The set-up of OnTest.test_off_between_steps: the run's issue (#1) is closed after the first merge.
        self.build("switch-off", run_steps=[{**run_answer("completed", "success"), "closes": [1]}])
        code, _, _ = self.on()
        self.assertEqual(code, 0)
        self.assertEqual(
            [without_at(line) for line in switches(self.state)],
            [{"event": "on"}, {"event": "off", "issue": 1}],
        )


class SwitchLogHaltTreeTest(SwitchTest):
    # SwitchTest holds only helpers, so subclassing it runs no test of test_halt.py here.
    def test_halt_names_the_session_the_lock_kill_ended(self):
        # The lock names a live driver whose tree holds the session: the lock's kill ends the session
        # before the halt looks at it again, and the halt line still names it.
        runlog = __import__("driver.runlog", fromlist=["runlog"])
        sleeper = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"], **new_group()
        )
        self.addCleanup(stop, sleeper)
        self.write_lock(sleeper.pid)
        started = self.lock.now().strftime(self.lock.STAMP)
        runlog.start(self.state, "Day 13 Track A: x", "day-13/track-a", "s-tree", "1")
        runlog.pid(self.state, "s-tree", sleeper.pid, started)
        done = self.cli("halt")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = [without_at(record) for record in switches(self.state)]
        self.assertEqual(
            lines, [{"event": "halt", "why": "run-steps.py halt", "session": "s-tree"}]
        )
