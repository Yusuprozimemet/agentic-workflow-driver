"""A pull request with no required checks: the real gh exits 1 and writes a line to stderr, not an
empty list on exit 0. checks() gives "none" for that line only, and the wait parks on it (C06.4 and
C08.5). Any other exit 1 is still "gh pr checks exited 1" (C08.6). Each case runs the functions with
the fake gh of tests/test_github.py, which writes the answer's `err` to stderr."""

import importlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_github import fake_gh

SESSION = "00000000-0000-4000-8000-000000000000"
STEP = "Day 01 Track A: the first track"
BRANCH = "day-01/track-a-x"
RUN_ISSUE = {"number": 7, "title": "Driver run x", "labels": [], "state": "open", "author": "me"}
PR = {"number": 7, "headRefName": BRANCH, "url": "u", "author": "me"}
NO_REQUIRED = f"no required checks reported on the '{BRANCH}' branch\n"
NO_CHECKS = f"no checks reported on the '{BRANCH}' branch\n"


class ChecksNoneTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top, as in test_github: where driver/github.py or
        # driver/loop.py is missing, each test fails alone with an ImportError.
        self.github = importlib.import_module("driver.github")
        self.loop = importlib.import_module("driver.loop")

    def scratch(self, checks):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        for name in ("gh", "state", "project"):
            (folder / name).mkdir()
        gh = fake_gh(folder / "gh", prs=[PR], issues=[RUN_ISSUE], checks=checks)
        self.project = str(folder / "project")
        self.args = SimpleNamespace(
            state=str(folder / "state"),
            gh=gh,
            poll=0.01,
            wait_minutes=0.01,
            session_minutes=120,
        )
        self.record = {"issue": 7, "step": STEP, "session": SESSION}
        return gh

    def test_no_required_checks(self):
        gh = self.scratch([{"code": 1, "out": "", "err": NO_REQUIRED}])
        self.assertEqual(self.github.checks(self.project, gh, 7), ("none", [], None))

    def test_no_checks(self):
        gh = self.scratch([{"code": 1, "out": "", "err": NO_CHECKS}])
        self.assertEqual(self.github.checks(self.project, gh, 7), ("none", [], None))

    def test_wait_parks(self):
        self.scratch([{"code": 1, "out": "", "err": NO_REQUIRED}])
        result = self.loop.wait_pr(self.args, self.project, 7, self.record)
        self.assertEqual(result, ("park: no required checks on #7 after 0.01 minutes", 1))

    def test_other_exit_1(self):
        # Each stderr is not the whole of a "no checks" line, so each stays a failed call.
        cases = [
            {"code": 1, "out": ""},
            {"code": 1, "out": "", "err": "HTTP 502: Bad Gateway\n"},
            {"code": 1, "out": "", "err": "error: " + NO_CHECKS},
            {"code": 1, "out": "", "err": "no checks reported\n"},
        ]
        for answer in cases:
            with self.subTest(err=answer.get("err")):
                gh = self.scratch([answer])
                result = self.github.checks(self.project, gh, 7)
                self.assertEqual(result, (None, [], "gh pr checks exited 1"))
