"""The run log's pid lines and live_session (C07.3 to C07.5). A pid line follows each session's start
and holds the process's pid and the time it started, so that after a crash live_session can find the
session whose process still lives. A line the readers cannot read parks the driver, as a torn line
does: open_session, failures, live_session and last_session all name the same line. The --once cases
are copies of the driver with the fake claude and the fake gh of tests/test_once.py."""

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import drift_of
from tests.test_once import DASHED, driver_copy, once
from tests.test_once_park_issues import build

PREFIX = "day-07/track-a"
OTHER_PREFIX = "day-02/track-b"
AT = "2026-11-08T10:00:00Z"
REASON = "the run log cannot be read at line 2"


def lines_of(state):
    # The run log's lines, read back as objects.
    with open(os.path.join(state, "run.jsonl"), "rb") as f:
        return [json.loads(line) for line in f.read().decode("utf-8").splitlines()]


def events(state):
    return [record["event"] for record in lines_of(state)]


def write(state, *records):
    # Written as bytes, one JSON object per line: on Windows, text mode would add a carriage return.
    os.makedirs(state, exist_ok=True)
    data = b"".join(json.dumps(record).encode("utf-8") + b"\n" for record in records)
    with open(os.path.join(state, "run.jsonl"), "wb") as f:
        f.write(data)


def start(session, prefix=PREFIX):
    return {
        "event": "start",
        "at": AT,
        "step": "x",
        "prefix": prefix,
        "session": session,
        "claude": "1",
    }


def pid(session, number, started):
    return {"event": "pid", "at": AT, "session": session, "pid": number, "started": started}


def end(session):
    return {
        "event": "end",
        "at": AT,
        "session": session,
        "outcome": "opened: #7",
        "cost_usd": 0,
        "denials": 0,
    }


def fix(session):
    return {"event": "fix", "at": AT, "session": session, "pr": 7, "n": 1}


def without(record, key):
    return {k: v for k, v in record.items() if k != key}


def stop(proc):
    proc.kill()
    proc.wait()


class RunLogTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone.
        self.runlog = importlib.import_module("driver.runlog")
        self.lock = importlib.import_module("driver.lock")

    def state_of(self, records=None):
        # A state folder under a fresh temp folder; None means there is no log at all.
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        state = os.path.join(root, "state")
        if records is not None:
            write(state, *records)
        return state


class RunLogPidTest(RunLogTest):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp()
        cls.copy = driver_copy(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def setUp(self):
        super().setUp()
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.state = str(self.folder / "state")

    def test_pid_line_between_start_and_end(self):
        flags = build(self.folder, drift=drift_of(DASHED))
        code, _, _ = once(self.copy, *flags)
        self.assertEqual(code, 0)
        self.assertEqual(events(self.state), ["start", "pid", "end"])
        start_line, pid_line = lines_of(self.state)[:2]
        self.assertIs(type(pid_line["pid"]), int)
        self.lock.stamp_time(pid_line["started"])
        self.assertEqual(pid_line["session"], start_line["session"])
        uuid.UUID(pid_line["session"])

    def test_resume_writes_a_pid_line(self):
        loop = importlib.import_module("driver.loop")
        once_module = importlib.import_module("driver.once")
        github = importlib.import_module("driver.github")
        self.runlog.start(self.state, "x", PREFIX, "abc", "1")
        self.runlog.pid(self.state, "abc", os.getpid(), self.lock.now().strftime(self.lock.STAMP))
        self.runlog.end(self.state, "abc", "park: x", 0, 0)
        args = SimpleNamespace(state=self.state, gh="gh", poll=30, session_minutes=1)
        record = {"issue": 7, "session": "abc", "step": "x"}
        command = [sys.executable, "-c", "import sys; sys.stdin.read()", "--session-id", "abc"]
        real_popen = subprocess.Popen
        spawned = []

        def spy(*call, **options):
            proc = real_popen(*call, **options)
            spawned.append(proc.pid)
            return proc

        with (
            mock.patch.object(github, "failed_lines", return_value=""),
            mock.patch.object(once_module, "outcome", return_value=("opened: #7", 0)),
            mock.patch.object(once_module.subprocess, "Popen", side_effect=spy),
        ):
            loop.resume(args, str(self.folder), 7, record, command, [{"name": "tests"}], 0)
        self.assertEqual(events(self.state), ["start", "pid", "end", "fix", "pid", "end"])
        last_pid = lines_of(self.state)[4]
        self.assertEqual(last_pid["session"], "abc")
        self.assertEqual(spawned, [last_pid["pid"]])

    def test_pid_is_fsynced(self):
        with mock.patch.object(self.runlog.os, "fsync", wraps=os.fsync) as fsync:
            self.runlog.pid(self.state, "s1", 123, AT)
        self.assertEqual(fsync.call_count, 1)
        data = Path(self.runlog.path(self.state)).read_bytes()
        self.assertTrue(data.endswith(b"\n"))
        self.assertNotIn(b"\r", data)
        self.assertEqual(data.count(b"\n"), 1)
        line = json.loads(data.decode("utf-8"))
        self.assertEqual(set(line), {"event", "at", "session", "pid", "started"})
        self.assertEqual(line["event"], "pid")
        self.assertEqual(line["session"], "s1")
        self.assertEqual(line["pid"], 123)
        self.assertEqual(line["started"], AT)


class LiveSessionTest(RunLogTest):
    def child(self):
        # A process that lives until the test ends.
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(stop, proc)
        return proc

    def gone(self):
        # The pid of a process that has exited and been reaped.
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        return proc.pid

    def stamp(self):
        return self.lock.now().strftime(self.lock.STAMP)

    def test_truth_table(self):
        # The child starts before the stamp is read, as a driver's process does before its pid line.
        live = self.child()
        dead = self.gone()
        now = self.stamp()
        hour_ago = (self.lock.now() - timedelta(hours=1)).strftime(self.lock.STAMP)
        cases = [
            (
                "a start and a live pid",
                [start("s1"), pid("s1", live.pid, now)],
                ("s1", live.pid, None),
            ),
            (
                "an end after the pid",
                [start("s1"), pid("s1", live.pid, now), end("s1")],
                (None, None, None),
            ),
            (
                "a resume",
                [
                    start("s1"),
                    pid("s1", live.pid, now),
                    end("s1"),
                    fix("s1"),
                    pid("s1", live.pid, now),
                ],
                ("s1", live.pid, None),
            ),
            ("a pid that has exited", [start("s1"), pid("s1", dead, now)], (None, None, None)),
            ("a reused pid", [start("s1"), pid("s1", live.pid, hour_ago)], (None, None, None)),
            (
                "a session of another prefix",
                [start("s9", prefix=OTHER_PREFIX), pid("s9", live.pid, now)],
                ("s9", live.pid, None),
            ),
            (
                "an older session that exited, a newer one live",
                [start("s1"), pid("s1", dead, now), start("s2"), pid("s2", live.pid, now)],
                ("s2", live.pid, None),
            ),
            (
                "an older session still alive",
                [start("s1"), pid("s1", live.pid, now), start("s2"), pid("s2", dead, now)],
                ("s1", live.pid, None),
            ),
            (
                "the last pid line decides",
                [start("s1"), pid("s1", live.pid, now), fix("s1"), pid("s1", dead, now)],
                (None, None, None),
            ),
            ("no log at all", None, (None, None, None)),
        ]
        for name, records, want in cases:
            with self.subTest(name):
                state = self.state_of(records)
                self.assertEqual(self.runlog.live_session(state), want)

    def test_torn_log(self):
        state = self.state_of([start("s1")])
        with open(self.runlog.path(state), "ab") as f:
            f.write(b'{"event": "pi')
        self.assertEqual(self.runlog.live_session(state), (None, None, REASON))
        with self.subTest("the log is not readable"):
            state = self.state_of()
            # A directory at the log's path cannot be opened as a file, on Windows and on POSIX.
            os.makedirs(self.runlog.path(state))
            result = self.runlog.live_session(state)
            self.assertEqual(result[:2], (None, None))
            self.assertTrue(result[2].startswith("the run log cannot be read"))


class RunLogLinesTest(RunLogTest):
    def test_bad_lines_are_unreadable(self):
        bad = [
            ("a start with no session", without(start("s1"), "session")),
            ("a start with session 7", dict(start("s1"), session=7)),
            ("a pid with pid x", dict(pid("s1", 123, AT), pid="x")),
            ("a pid with pid true", dict(pid("s1", 123, AT), pid=True)),
            ("a pid with pid 2147483648", pid("s1", 2147483648, AT)),
            ("a pid with no started", without(pid("s1", 123, AT), "started")),
            ("a pid with started x", dict(pid("s1", 123, AT), started="x")),
            ("a pid with no session", without(pid("s1", 123, AT), "session")),
            ("a pid with session []", dict(pid("s1", 123, AT), session=[])),
        ]
        for name, line in bad:
            with self.subTest(name):
                state = self.state_of([start("s1"), line])
                self.assertEqual(self.runlog.open_session(state, PREFIX), (None, REASON))
                self.assertEqual(self.runlog.failures(state, PREFIX), (None, REASON))
                self.assertEqual(self.runlog.live_session(state), (None, None, REASON))
        with self.subTest("a pid with the largest pid is read"):
            state = self.state_of([start("s1"), pid("s1", 2147483647, AT)])
            self.assertEqual(self.runlog.open_session(state, PREFIX), ("s1", None))

    def test_last_session(self):
        state = self.state_of([start("s1"), start("q1", OTHER_PREFIX), start("s2")])
        self.assertEqual(self.runlog.last_session(state, PREFIX), "s2")
        self.assertIsNone(self.runlog.last_session(state, "day-99/none"))
        with self.subTest("no log"):
            self.assertIsNone(self.runlog.last_session(self.state_of(), PREFIX))
        with self.subTest("a torn log"):
            state = self.state_of([start("s1")])
            with open(self.runlog.path(state), "ab") as f:
                f.write(b'{"event": "pi')
            self.assertIsNone(self.runlog.last_session(state, PREFIX))
        with self.subTest("the log is not readable"):
            state = self.state_of()
            os.makedirs(self.runlog.path(state))
            self.assertIsNone(self.runlog.last_session(state, PREFIX))


if __name__ == "__main__":
    unittest.main()
