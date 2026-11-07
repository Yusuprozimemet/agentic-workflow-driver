"""open_issues() and closed_parks() read gh's answers: the maintainer's open issues with their labels,
the closed parks, and a gh that fails. Each test runs a fake gh beside a scratch project, as
GitHubTest does, and reads back the arguments it was called with."""

import importlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_github import fake_gh, read_calls

# Deliberately not in number order, and with issues from someone else, so that the author filter
# and the sort both have something to do.
ISSUES = [
    {
        "number": 3,
        "title": "park: no evidence run on `1dc0f03` yet",
        "labels": ["parked", "bug"],
        "state": "open",
        "author": "me",
    },
    {
        "number": 1,
        "title": "Driver run 2026-11-07T09:00:00Z",
        "labels": [],
        "state": "open",
        "author": "me",
    },
    {"number": 2, "title": "STOP", "labels": [], "state": "open", "author": "someone"},
    {
        "number": 4,
        "title": "park: the end of Phase 1",
        "labels": ["parked"],
        "state": "closed",
        "author": "me",
    },
    {
        "number": 5,
        "title": "park: the end of Phase 2",
        "labels": ["parked"],
        "state": "closed",
        "author": "someone",
    },
    {"number": 6, "title": "an old note", "labels": [], "state": "closed", "author": "me"},
]


class IssuesTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top, as in test_github: where driver/issues.py is missing, each
        # test fails alone with ImportError.
        self.issues = importlib.import_module("driver.issues")

    def scratch(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        return folder

    def test_open_issues(self):
        folder = self.scratch()
        gh = fake_gh(folder, issues=ISSUES)
        self.assertEqual(
            self.issues.open_issues(str(folder), gh),
            (
                [
                    {"number": 1, "title": "Driver run 2026-11-07T09:00:00Z", "labels": []},
                    {
                        "number": 3,
                        "title": "park: no evidence run on `1dc0f03` yet",
                        "labels": ["parked", "bug"],
                    },
                ],
                None,
            ),
        )
        self.assertEqual(
            read_calls(folder),
            [
                [
                    "issue",
                    "list",
                    "--state",
                    "open",
                    "--author",
                    "@me",
                    "--limit",
                    "100",
                    "--json",
                    "number,title,labels",
                ]
            ],
        )

    def test_closed_parks(self):
        folder = self.scratch()
        gh = fake_gh(folder, issues=ISSUES)
        self.assertEqual(
            self.issues.closed_parks(str(folder), gh),
            ({"park: the end of Phase 1"}, None),
        )
        self.assertEqual(
            read_calls(folder),
            [
                [
                    "issue",
                    "list",
                    "--state",
                    "closed",
                    "--author",
                    "@me",
                    "--label",
                    "parked",
                    "--limit",
                    "100",
                    "--json",
                    "number,title",
                ]
            ],
        )

    def test_reads_fail(self):
        folder = self.scratch()
        gh = fake_gh(folder, issues=ISSUES, issue_code=1)
        self.assertEqual(
            self.issues.open_issues(str(folder), gh),
            ([], "gh issue list exited 1"),
        )
        self.assertEqual(
            self.issues.closed_parks(str(folder), gh),
            (set(), "gh issue list exited 1"),
        )
