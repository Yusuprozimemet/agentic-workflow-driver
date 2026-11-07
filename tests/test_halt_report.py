"""halt's report on the run's issue: after halt kills a live driver, the issue named in
<state>/run.json gets the project's branch, last commit and uncommitted changes, and is closed.
Each test runs the CLI as a person runs it, beside a stand-in driver and a fake gh, and reads back
what the fake recorded."""

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

from tests.test_github import fake_gh, read_bodies
from tests.test_halt import STAND_IN, new_group, stop

KILL = "halt: set; killed pid {} and the processes it started"
SESSION = "6f1c2a4e-0b7d-4c1e-9a53-2d8e7f0b1c44"
ISSUES = [
    {
        "number": 4,
        "title": "Driver run 2026-11-07T09:00:00Z",
        "labels": [],
        "state": "open",
        "author": "me",
    }
]


class HaltReportTest(unittest.TestCase):
    def setUp(self):
        # Imported here, as test_halt does: where driver/ is missing, each test fails alone.
        self.lock = importlib.import_module("driver.lock")
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.state = os.path.join(self.root, "state")
        self.project = os.path.join(self.root, "project")
        self.folder = Path(self.root, "gh")
        self.folder.mkdir()
        # A repository with one commit on main; a test that needs another branch or a detached HEAD
        # moves it.
        os.makedirs(self.project)
        self.git("init", "-q", "-b", "main")
        Path(self.project, "README.md").write_bytes(b"project\n")
        self.git("add", "README.md")
        self.git(
            "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "first"
        )

    def git(self, *args):
        done = subprocess.run(
            ["git", "-C", self.project, *args],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return done.stdout

    def halt(self, raw=None, issue_code=0):
        # A stand-in driver holds the lock; run.json names the project, the fake gh, issue 4 and its
        # step and session. Returns halt's result, the stand-in's pid and the fake's folder.
        pidfile = os.path.join(self.root, "pids")
        standin = subprocess.Popen([sys.executable, "-c", STAND_IN, pidfile], **new_group())
        self.addCleanup(stop, standin)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not (
            os.path.exists(pidfile) and len(Path(pidfile).read_text().split()) == 2
        ):
            time.sleep(0.05)
        os.makedirs(self.state, exist_ok=True)
        started = self.lock.now().strftime(self.lock.STAMP)
        body = json.dumps({"pid": standin.pid, "started": started})
        Path(self.lock.path(self.state)).write_bytes(body.encode("utf-8"))
        gh = fake_gh(self.folder, issues=ISSUES, issue_code=issue_code)
        record = {
            "project": self.project,
            "gh": gh,
            "issue": 4,
            "step": "Start Day 5",
            "session": SESSION,
        }
        data = json.dumps(record).encode("utf-8") if raw is None else raw
        Path(self.state, "run.json").write_bytes(data)
        done = subprocess.run(
            [sys.executable, str(ROOT / "run-steps.py"), "halt", "--state", self.state],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return done, standin.pid

    def test_report(self):
        self.git("checkout", "-q", "-b", "day-05/track-a-x")
        Path(self.project, "notes.txt").write_bytes(b"untracked\n")
        head = self.git("rev-parse", "HEAD").strip()[:7]

        done, pid = self.halt()
        self.assertEqual(done.stdout.splitlines(), [KILL.format(pid), "halt: reported on #4"])
        self.assertEqual(done.returncode, 0)
        issues = json.loads(Path(self.folder, "fake.json").read_bytes())["issues"]
        self.assertEqual(issues[0]["state"], "closed")
        [comment] = read_bodies(self.folder)
        body = comment["body"]
        self.assertIn("step: Start Day 5", body)
        self.assertIn(f"session: {SESSION}", body)
        self.assertIn("branch: day-05/track-a-x", body)
        self.assertIn(f"last commit: {head}", body)
        self.assertIn("uncommitted changes: 1 paths", body)

    def test_unreadable_run_json(self):
        done, pid = self.halt(raw=b"not json")
        path = os.path.join(self.state, "run.json")
        self.assertEqual(
            done.stdout.splitlines(),
            [KILL.format(pid), f"halt: no report: {path} cannot be read"],
        )
        self.assertEqual(done.returncode, 0)

    def test_report_fails(self):
        done, pid = self.halt(issue_code=1)
        self.assertEqual(
            done.stdout.splitlines(),
            [KILL.format(pid), "halt: no report on #4: gh issue comment exited 1"],
        )
        self.assertEqual(done.returncode, 0)

    def test_detached_clean(self):
        self.git("checkout", "-q", "--detach")

        done, pid = self.halt()
        self.assertEqual(done.stdout.splitlines(), [KILL.format(pid), "halt: reported on #4"])
        self.assertEqual(done.returncode, 0)
        [comment] = read_bodies(self.folder)
        self.assertIn("branch: detached HEAD", comment["body"])
        self.assertIn("uncommitted changes: none", comment["body"])
