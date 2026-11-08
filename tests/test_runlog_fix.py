"""fix() appends one fix line, fsynced, and fixes() counts the fix lines of one session. A torn
log, a line that is not an object, or a log that cannot be read counts as both used, never as
none."""

import datetime
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class RunlogFixTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone, and
        # scripts/track-red.py counts a module that does not load as not run, not as red.
        self.runlog = importlib.import_module("driver.runlog")
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)

    def test_fixes_counted(self):
        state = self.state
        self.assertEqual(self.runlog.fixes(state, "s1"), 0)
        with mock.patch.object(self.runlog.os, "fsync", wraps=os.fsync) as fsync:
            self.runlog.fix(state, "s1", 12, 1)
        self.assertEqual(fsync.call_count, 1)
        data = Path(self.runlog.path(state)).read_bytes()
        self.assertTrue(data.endswith(b"\n"))
        self.assertNotIn(b"\r", data)
        self.assertEqual(data.count(b"\n"), 1)
        record = json.loads(data.decode("utf-8"))
        self.assertEqual(set(record), {"event", "at", "session", "pr", "n"})
        self.assertEqual(record["event"], "fix")
        self.assertEqual(record["session"], "s1")
        self.assertEqual(record["pr"], 12)
        self.assertEqual(record["n"], 1)
        datetime.datetime.strptime(record["at"], self.runlog.STAMP)
        self.assertEqual(self.runlog.fixes(state, "s1"), 1)

        # Start, end and fix lines of other sessions must not count for s1, s2 or s3.
        self.runlog.start(state, "step", "day-06/track-c", "s1", "2.1.400 (Claude Code)")
        self.runlog.end(state, "s1", "opened: #12", 0.5, 0)
        self.runlog.fix(state, "s2", 13, 1)
        self.assertEqual(self.runlog.fixes(state, "s1"), 1)
        self.assertEqual(self.runlog.fixes(state, "s2"), 1)
        self.assertEqual(self.runlog.fixes(state, "s3"), 0)

        self.runlog.fix(state, "s1", 12, 2)
        self.assertEqual(self.runlog.fixes(state, "s1"), 2)

    def test_torn_log_counts_both(self):
        complete = (
            json.dumps(
                {
                    "event": "fix",
                    "at": "2026-11-08T00:00:00Z",
                    "session": "s1",
                    "pr": 12,
                    "n": 1,
                }
            ).encode("utf-8")
            + b"\n"
        )
        torn = complete + b'{"event": "fi'
        cases = [
            ("torn last line, one fix before it", torn, "s1"),
            ("torn, the session has no fix lines", torn, "other"),
            ("a line that is not an object", b"[1]\n", "s1"),
        ]
        for name, data, session in cases:
            with self.subTest(name):
                # Each case starts from its own file, written as bytes.
                Path(self.runlog.path(self.state)).write_bytes(data)
                self.assertEqual(self.runlog.fixes(self.state, session), 2)

        other_state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other_state)
        # A directory at the log's path cannot be opened as a file, on Windows and on POSIX.
        os.makedirs(self.runlog.path(other_state))
        with self.subTest("the log is not readable"):
            self.assertEqual(self.runlog.fixes(other_state, "s1"), 2)
