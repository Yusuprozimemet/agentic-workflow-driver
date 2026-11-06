"""take() writes the lock once and refuses a second run with one line: while the process the lock
names lives, when it is gone or was reused, and when the lock cannot be read. release() leaves a
lock that names another pid, and asking whether a process lives does not end it."""

import datetime
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

UTC = datetime.UTC


def utc_now():
    return datetime.datetime.now(UTC)


def fmt(when):
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class LockTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone, and
        # scripts/track-red.py counts a module that does not load as not run, not as red.
        self.lock = importlib.import_module("driver.lock")
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)
        self.lock_file = os.path.join(self.state, "lock")

    def write_lock(self, body):
        Path(self.lock_file).write_bytes(body)

    def start_child(self, code):
        child = subprocess.Popen([sys.executable, "-c", code])
        self.addCleanup(self.end_child, child)
        return child

    def end_child(self, child):
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)

    def test_take_writes_pid_and_start(self):
        self.assertIsNone(self.lock.take(self.state))
        lock = json.loads(Path(self.lock_file).read_bytes())
        self.assertEqual(set(lock), {"pid", "started"})
        self.assertEqual(lock["pid"], os.getpid())
        self.assertRegex(lock["started"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        started = datetime.datetime.strptime(lock["started"], "%Y-%m-%dT%H:%M:%SZ")
        started = started.replace(tzinfo=UTC)
        self.assertLess(abs(utc_now() - started), datetime.timedelta(seconds=60))
        self.assertEqual(self.lock.read(self.state), (os.getpid(), lock["started"]))

    def test_live_lock_refuses(self):
        self.assertIsNone(self.lock.take(self.state))
        before = Path(self.lock_file).read_bytes()
        started = json.loads(before)["started"]
        line = self.lock.take(self.state)
        self.assertEqual(
            line,
            f"cannot start: the driver is already running (pid {os.getpid()}, since {started})",
        )
        self.assertEqual(Path(self.lock_file).read_bytes(), before)

    def test_stale_lock_refuses(self):
        # Catches a Windows liveness check written the POSIX way: signal 0 there reports an
        # exited process as alive, so this lock would be taken as the driver's.
        before = utc_now() - datetime.timedelta(seconds=60)
        child = self.start_child("pass")
        child.wait()
        body = json.dumps({"pid": child.pid, "started": fmt(before)}).encode()
        self.write_lock(body)
        line = self.lock.take(self.state)
        self.assertEqual(
            line,
            f"cannot start: a lock names pid {child.pid}, which is gone; "
            "run-steps.py clear removes it",
        )
        self.assertEqual(Path(self.lock_file).read_bytes(), body)

    def test_reused_pid_is_gone(self):
        child = self.start_child("import time; time.sleep(60)")
        body = json.dumps(
            {"pid": child.pid, "started": fmt(utc_now() - datetime.timedelta(hours=1))}
        )
        self.write_lock(body.encode())
        line = self.lock.take(self.state)
        self.assertEqual(
            line,
            f"cannot start: a lock names pid {child.pid}, which is gone; "
            "run-steps.py clear removes it",
        )
        self.assertIsNone(child.poll())

    def test_unreadable_lock_refuses(self):
        cases = [b"", b"not json", b"[1, 2]", b'{"pid": 1}', b'{"started": "2026-11-07T21:00:00Z"}']
        for body in cases:
            with self.subTest(body=body):
                self.write_lock(body)
                line = self.lock.take(self.state)
                self.assertEqual(
                    line,
                    f"cannot start: {self.lock_file} cannot be read; run-steps.py clear removes it",
                )
                self.assertEqual(Path(self.lock_file).read_bytes(), body)
                self.assertIsNone(self.lock.read(self.state))

    def test_release_keeps_anothers_lock(self):
        child = self.start_child("pass")
        child.wait()
        body = json.dumps({"pid": child.pid, "started": fmt(utc_now())}).encode()
        self.write_lock(body)
        self.lock.release(self.state)
        self.assertTrue(os.path.exists(self.lock_file), "release removed another pid's lock")
        self.assertEqual(Path(self.lock_file).read_bytes(), body)
        os.remove(self.lock_file)
        self.assertIsNone(self.lock.take(self.state))
        self.lock.release(self.state)
        self.assertFalse(os.path.exists(self.lock_file))

    def test_asking_does_not_kill(self):
        child = self.start_child("import time; time.sleep(60)")
        # Stamped after the child began, as a driver writes its own lock: a stamp before its
        # start would make it a reused pid, and gone.
        started = fmt(utc_now())
        self.write_lock(json.dumps({"pid": child.pid, "started": started}).encode())
        line = self.lock.take(self.state)
        self.assertEqual(
            line,
            f"cannot start: the driver is already running (pid {child.pid}, since {started})",
        )
        time.sleep(0.5)
        self.assertIsNone(child.poll())
        child.kill()
        child.wait(timeout=10)
        self.assertNotEqual(child.returncode, 0)
