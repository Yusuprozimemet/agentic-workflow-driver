"""The heartbeat file (Day 11, Track C): --once writes <state>/heartbeat.json at its start and at each poll, so
a session that is quiet for a while, as a tool that runs for seconds is, still shows its last event and the
time of the last poll. The case runs a fake claude that prints its init line as a poll's issue read
begins, then stays quiet until the test releases it. The driver's --poll is 0.3 seconds and each issue
read sleeps two seconds; the test reads the file once its last_event is that init line and again at a
later poll, then releases the fake. No report here names a pid, uuid or path."""

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
from tests.test_phone import wait_for_reads

SYSTEM = {"type": "system", "subtype": "init"}
KEYS = ["last_event", "poll", "session", "started", "step"]


def parsed_stamp(value):
    # The poll's time read with lock.STAMP, or None when it is not one.
    from driver import lock

    try:
        return datetime.datetime.strptime(value, lock.STAMP)
    except (TypeError, ValueError):
        return None


def later(beat, earlier):
    # True when both beats' polls read with lock.STAMP, and the beat's is later than the earlier beat's.
    if not (isinstance(beat, dict) and isinstance(earlier, dict)):
        return False
    now, before = parsed_stamp(beat.get("poll")), parsed_stamp(earlier.get("poll"))
    return now is not None and before is not None and now > before


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

    def beat_where(self, state, wanted, bound=30):
        # The heartbeat file read every 0.05 seconds until wanted(beat) is true, or the bound passes. It returns
        # the beat wanted, or else the last beat read, so that the test's check reports what it saw.
        deadline = time.monotonic() + bound
        beat = self.heartbeat(state)
        while not wanted(beat) and time.monotonic() < deadline:
            time.sleep(0.05)
            beat = self.heartbeat(state)
        return beat

    def test_heartbeat_beats_through_a_quiet_tool(self):
        # The fake prints its init line as a poll's issue read begins, then stays quiet until the test writes
        # its release file: a quiet tool that the bound of one minute does not end. Its own result line comes
        # after the release, when the session ends.
        folder = Path(tempfile.mkdtemp(dir=self.root))
        release = folder / "release"
        # The init line comes as a poll's issue read begins, and each read sleeps two seconds, as on a
        # busy machine. The fake then waits for the release file, or for 30 seconds.
        do = (
            wait_for_reads(folder / "gh" / "calls.jsonl", 1, 30)
            + f"print({json.dumps(SYSTEM)!r}, flush=True)\n"
            + "import os, time\n"
            + "deadline = time.monotonic() + 30\n"
            + f"while not os.path.exists({str(release)!r}) and time.monotonic() < deadline:\n"
            + "    time.sleep(0.02)\n"
        )
        flags = build(folder, drift=drift_of(DASHED), do=do)
        gh_file = folder / "gh" / "fake.json"
        spec = json.loads(gh_file.read_bytes())
        spec["sleep_on"] = "list"
        spec["sleep"] = 2
        gh_file.write_bytes(json.dumps(spec).encode("utf-8"))
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
            # A line still being written does not end in a newline: the wait goes on until one does.
            if files and b"\n" in files[0].read_bytes().lstrip():
                break
            if time.monotonic() >= deadline:
                self.fail("the session wrote no events line")
            time.sleep(0.05)
        # The init line's time, as the heartbeat's last_event names it: the events file's first non-blank line.
        init = next(
            (line for line in files[0].read_bytes().decode("utf-8").splitlines() if line.strip()),
            "",
        )
        try:
            init_at = json.loads(init).get("at")
        except ValueError:
            init_at = None
        # The first beat that names the init line, then a beat from a later poll, both read while the fake is quiet.
        first = self.beat_where(
            state, lambda beat: isinstance(beat, dict) and beat.get("last_event") == init_at
        )
        second = self.beat_where(state, lambda beat: later(beat, first))
        release.write_bytes(b"go\n")
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
