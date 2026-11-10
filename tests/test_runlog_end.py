"""An end line may name the tools a session was refused, and the readers refuse a line whose fields
they cannot use: such a log is unreadable at that line, for read, failures, open_session and status
alike, and the same line well-formed is read."""

import importlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_github import fake_gh
from tests.test_status import T1, encode, start

REASON = "the run log cannot be read at line 2"


def rec(**fields):
    return {"at": T1, **fields}


class RunlogEndTest(unittest.TestCase):
    def setUp(self):
        # Imported here, as in test_runlog_fix: where driver/ is missing, each test fails alone.
        self.runlog = importlib.import_module("driver.runlog")
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.project = os.path.join(self.root, "project")
        os.makedirs(self.project)
        self.folder = Path(self.root, "gh")
        self.folder.mkdir()

    def status(self, state):
        gh = fake_gh(self.folder, issues=[], issue_code=0)
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "run-steps.py"),
                "status",
                "--project",
                self.project,
                "--state",
                state,
                "--gh",
                gh,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def log_of(self, record):
        # A fresh state folder whose log is a start line and the record, written as bytes.
        state = tempfile.mkdtemp(dir=self.root)
        Path(state, "run.jsonl").write_bytes(encode(start("s1", "Step A", T1)) + encode(record))
        return state

    def refused_line(self, bad, good):
        state = self.log_of(bad)
        self.assertEqual(self.runlog.read(state), (None, REASON))
        self.assertEqual(self.runlog.failures(state, "day-07"), (None, REASON))
        self.assertEqual(self.runlog.open_session(state, "day-07"), (None, REASON))
        self.assertIsNone(self.runlog.last_session(state, "day-07"))
        done = self.status(state)
        self.assertEqual(
            (done.stdout.splitlines()[-1:], done.returncode), (["run log: " + REASON], 2)
        )
        # The same line well-formed is read, so the refusal is not a refusal of everything.
        self.assertIsNone(self.runlog.read(self.log_of(good))[1])

    def test_end_session_not_string(self):
        bad = rec(event="end", session=["s1"], outcome="x", cost_usd=0, denials=0)
        good = rec(event="end", session="s1", outcome="x", cost_usd=0, denials=0)
        self.refused_line(bad, good)

    def test_refused_not_list(self):
        bads = [
            rec(event="end", session="s1", outcome="x", cost_usd=0, denials=0, refused="x"),
            rec(
                event="end",
                session="s1",
                outcome="x",
                cost_usd=0,
                denials=0,
                refused=[{"tool": 5, "input": "{}"}],
            ),
        ]
        good = rec(
            event="end",
            session="s1",
            outcome="x",
            cost_usd=0,
            denials=0,
            refused=[{"tool": "Bash", "input": "{}"}],
        )
        for bad in bads:
            with self.subTest(refused=bad["refused"]):
                self.refused_line(bad, good)

    def test_merged_pr_not_int(self):
        for pr in (True, "3"):
            with self.subTest(pr=pr):
                self.refused_line(rec(event="merged", pr=pr), rec(event="merged", pr=3))

    def test_wait_pr_not_int(self):
        self.refused_line(rec(event="wait", pr="3"), rec(event="wait", pr=3))

    def test_closed_pr_not_int(self):
        self.refused_line(rec(event="closed", pr="3"), rec(event="closed", pr=3))

    def test_park_pr_not_int(self):
        bad = rec(event="park", step="Step A", line="park: x", pr=True)
        good = rec(event="park", step="Step A", line="park: x", pr=3)
        self.refused_line(bad, good)
        # A park line with no pr key is fine, as the driver writes it when no pull request is named.
        no_pr = rec(event="park", step="Step A", line="park: x")
        self.assertIsNone(self.runlog.read(self.log_of(no_pr))[1])

    def test_head_not_string(self):
        bads = [
            rec(event="park", step="Step A", line="park: x", pr=3, head=5),
            rec(event="merged", pr=3, head=5),
        ]
        goods = [
            rec(event="park", step="Step A", line="park: x", pr=3, head="aaa"),
            rec(event="merged", pr=3, head="aaa"),
        ]
        for bad, good in zip(bads, goods):
            with self.subTest(event=bad["event"]):
                self.refused_line(bad, good)
