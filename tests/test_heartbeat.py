"""The heartbeat file (Day 11, Track C): --once writes <state>/heartbeat.json at its start and at each poll, so
a session that is quiet for a while, as a tool that runs for seconds is, still shows its last event and the
time of the last poll. The case runs a fake claude that prints its init line and sleeps, with the driver's
--poll at 0.3 seconds, and reads the file twice while the session is quiet. No report here names a pid, uuid
or path."""

import datetime
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import test_once_outcome as outcome
from tests.test_dry_run import drift_of
from tests.test_halt import stop
from tests.test_once import DASHED, driver_copy
from tests.test_once_halt import kill_left_over
from tests.test_once_park_issues import build

SYSTEM = {"type": "system", "subtype": "init"}
KEYS = ["last_event", "poll", "session", "started", "step"]


def parsed_stamp(value):
    # The poll's time read with lock.STAMP, or None when it is not one.
    from driver import lock

    try:
        return datetime.datetime.strptime(value, lock.STAMP)
    except (TypeError, ValueError):
        return None


class HeartbeatTest(unittest.TestCase):
    setUp = outcome.OutcomeTest.setUp

    def heartbeat(self, state):
        # The heartbeat file as an object, read again for up to a second while a write holds it or
        # leaves it half written.
        path = Path(state) / "heartbeat.json"
        deadline = time.monotonic() + 1
        while True:
            try:
                return json.loads(path.read_bytes().decode("utf-8"))
            except (OSError, ValueError):
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.05)
        if path.exists():
            self.fail("the heartbeat file does not hold a JSON object")
        self.fail("the session wrote no heartbeat")

    def test_heartbeat_beats_through_a_quiet_tool(self):
        # The fake prints its init line, then sleeps for four seconds: a quiet tool that the bound of one
        # minute does not end. Its own result line comes after the sleep, when the session ends.
        do = f"print({json.dumps(SYSTEM)!r}, flush=True)\nimport time; time.sleep(4)\n"
        folder = Path(tempfile.mkdtemp(dir=self.root))
        flags = build(folder, drift=drift_of(DASHED), do=do)
        copy = driver_copy(tempfile.mkdtemp(dir=self.root))
        self.addCleanup(kill_left_over, folder / "claude")
        state = folder / "state"
        with open(folder / "stdout.txt", "wb") as out, open(folder / "stderr.txt", "wb") as err:
            driver = subprocess.Popen(
                [sys.executable, str(copy / "run-steps.py"), "--once", *flags]
                + ["--poll", "0.3", "--session-minutes", "1"],
                stdout=out,
                stderr=err,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        self.addCleanup(stop, driver)
        # The first line of the session's events file is the moment the session is known to be running.
        deadline = time.monotonic() + 30
        while True:
            files = list((state / "sessions").glob("*.events.jsonl"))
            if files and files[0].read_bytes().strip():
                break
            if time.monotonic() >= deadline:
                self.fail("the session wrote no events line")
            time.sleep(0.05)
        t0 = time.monotonic()
        time.sleep(max(0, t0 + 0.5 - time.monotonic()))
        first = self.heartbeat(state)
        time.sleep(max(0, t0 + 2.5 - time.monotonic()))
        second = self.heartbeat(state)
        if not (isinstance(first, dict) and isinstance(second, dict)):
            self.fail("the heartbeat file does not hold a JSON object")
        runs = [
            json.loads(line)
            for line in (state / "run.jsonl").read_bytes().decode("utf-8").splitlines()
        ]
        starts = [record for record in runs if record.get("event") == "start"]
        self.assertEqual(len(starts), 1, "the run did not start one session")
        start = starts[0]
        files = list((state / "sessions").glob("*.events.jsonl"))
        self.assertEqual(len(files), 1, "the run did not write one events file")
        events = [
            json.loads(line)
            for line in files[0].read_bytes().decode("utf-8").splitlines()
            if line.strip()
        ]
        self.assertTrue(events, "the session's events file has no line")
        first_poll, second_poll = parsed_stamp(first.get("poll")), parsed_stamp(second.get("poll"))
        self.assertEqual(
            (
                sorted(first) == KEYS,
                sorted(second) == KEYS,
                first.get("session") == start.get("session"),
                second.get("session") == start.get("session"),
                first.get("started") == start.get("at"),
                second.get("started") == start.get("at"),
                first_poll is not None and second_poll is not None and second_poll > first_poll,
                first.get("last_event") == second.get("last_event") == events[0].get("at"),
                events[0].get("kind") == "system init",
            ),
            (True,) * 9,
        )
        try:
            driver.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self.fail("the driver did not end")
        self.assertTrue(
            (state / "heartbeat.json").exists(), "the heartbeat file is gone after the run"
        )
