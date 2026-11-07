"""off closes the project's open "Driver run" issues, and reports what it could not read. Each test
runs the CLI as a person runs it, on a scratch project with a fake gh beside it, and reads back the
issues the fake holds and the calls it got. The config is a missing file, so the real driver.json
never matters."""

import json
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

from tests.test_github import fake_gh, read_bodies, read_calls

ONE = "off: closed the run's issue #{}; the current step finishes, nothing new starts"
ISSUES = [
    {
        "number": 2,
        "title": "Driver run 2026-11-06T09:00:00Z",
        "labels": [],
        "state": "open",
        "author": "me",
    },
    {"number": 3, "title": "park: x", "labels": ["parked"], "state": "open", "author": "me"},
    {
        "number": 4,
        "title": "Driver run 2026-11-07T09:00:00Z",
        "labels": [],
        "state": "open",
        "author": "me",
    },
    {
        "number": 5,
        "title": "Driver run 2026-11-07T10:00:00Z",
        "labels": [],
        "state": "open",
        "author": "someone",
    },
]


class OffTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.project = os.path.join(self.root, "project")
        os.makedirs(self.project)
        self.config = os.path.join(self.root, "missing.json")
        self.folder = Path(self.root, "gh")
        self.folder.mkdir()

    def off(self, issues, issue_code=0):
        gh = fake_gh(self.folder, issues=issues, issue_code=issue_code)
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "run-steps.py"),
                "off",
                "--config",
                self.config,
                "--project",
                self.project,
                "--gh",
                gh,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def states(self):
        issues = json.loads(Path(self.folder, "fake.json").read_bytes())["issues"]
        return {issue["number"]: issue["state"] for issue in issues}

    def test_off_closes_runs(self):
        done = self.off(ISSUES)
        self.assertEqual(done.stdout.splitlines(), [ONE.format(2), ONE.format(4)])
        self.assertEqual(done.returncode, 0)
        self.assertEqual(self.states(), {2: "closed", 3: "open", 4: "closed", 5: "open"})
        bodies = read_bodies(self.folder)
        self.assertEqual([body["args"][2] for body in bodies], ["2", "4"])
        for body in bodies:
            self.assertTrue(body["body"].startswith("off from the PC at "))

    def test_off_no_run(self):
        done = self.off([ISSUES[1]])
        self.assertEqual(done.stdout.splitlines(), ["off: no run is going"])
        self.assertEqual(done.returncode, 0)
        self.assertFalse(any(call[:2] == ["issue", "comment"] for call in read_calls(self.folder)))

    def test_off_gh_fails(self):
        done = self.off(ISSUES, issue_code=1)
        self.assertEqual(done.stderr.strip(), "cannot read the project: gh issue list exited 1")
        self.assertEqual(done.returncode, 2)

    def test_off_no_config(self):
        done = subprocess.run(
            [
                sys.executable,
                str(ROOT / "run-steps.py"),
                "off",
                "--config",
                self.config,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(
            done.stderr.strip(),
            f"cannot start: no --project, and no config at {self.config}",
        )
        self.assertEqual(done.returncode, 2)
