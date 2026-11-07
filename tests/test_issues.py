"""open_issues() and closed_parks() read gh's answers: the maintainer's open issues with their labels,
the closed parks, and a gh that fails. Each test runs a fake gh beside a scratch project, as
GitHubTest does, and reads back the arguments it was called with."""

import importlib
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_github import fake_gh, read_bodies, read_calls

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


class IssueWritesTest(unittest.TestCase):
    def setUp(self):
        # Imported here, as in IssuesTest: where driver/issues.py has no writes yet, each test fails
        # alone.
        self.issues = importlib.import_module("driver.issues")

    def scratch(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        return folder

    def test_park_opens(self):
        folder = self.scratch()
        gh = fake_gh(folder)
        body = "park: the end of Phase 1\n\nstep: x\n"
        self.assertEqual(
            self.issues.park(str(folder), gh, "park: the end of Phase 1", body, []),
            (1, None),
        )
        self.assertEqual(
            read_calls(folder),
            [
                [
                    "label",
                    "create",
                    "parked",
                    "--color",
                    "D93F0B",
                    "--description",
                    "The driver parked; close to let it go on",
                    "--force",
                ],
                [
                    "issue",
                    "create",
                    "--title",
                    "park: the end of Phase 1",
                    "--label",
                    "parked",
                    "--body-file",
                    "-",
                ],
            ],
        )
        bodies = read_bodies(folder)
        self.assertEqual(len(bodies), 1)
        self.assertEqual(bodies[0]["body"], body)
        self.assertNotIn("\r", bodies[0]["body"])
        self.assertNotIn(b"\r", (folder / "bodies.jsonl").read_bytes())

    def test_park_comments(self):
        folder = self.scratch()
        gh = fake_gh(
            folder,
            issues=[
                {
                    "number": 7,
                    "title": "park: x",
                    "labels": ["parked"],
                    "state": "open",
                    "author": "me",
                }
            ],
        )
        issues = [{"number": 7, "title": "park: x", "labels": ["parked"]}]
        self.assertEqual(
            self.issues.park(str(folder), gh, "park: x", "park: x\n", issues),
            (7, None),
        )
        self.assertEqual(read_calls(folder), [["issue", "comment", "7", "--body-file", "-"]])
        self.assertTrue(read_bodies(folder)[0]["body"].startswith("parked again at "))

    def test_park_title_cut(self):
        folder = self.scratch()
        gh = fake_gh(folder)
        line = "park: " + "x" * 244
        self.assertEqual(len(line), 250)
        self.assertEqual(
            self.issues.park(str(folder), gh, line, "body\n", []),
            (1, None),
        )
        create = read_calls(folder)[-1]
        self.assertEqual(create[create.index("--title") + 1], line[:200])

    def test_park_fails(self):
        folder = self.scratch()
        gh = fake_gh(folder, issue_code=1)
        self.assertEqual(
            self.issues.park(str(folder), gh, "park: x", "body\n", []),
            (None, "gh label create exited 1"),
        )

    def test_open_run_creates(self):
        folder = self.scratch()
        gh = fake_gh(folder)
        self.assertEqual(
            self.issues.open_run(str(folder), gh, "Start Day 05", "uuid-1", []),
            (1, None),
        )
        (call,) = read_calls(folder)
        self.assertEqual(call[:3], ["issue", "create", "--title"])
        self.assertRegex(call[3], r"^Driver run \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertNotIn("--label", call)
        self.assertEqual(call[-2:], ["--body-file", "-"])
        body = read_bodies(folder)[0]["body"]
        for part in ("step: ", "Start Day 05", "session: ", "uuid-1"):
            self.assertIn(part, body)

    def test_open_run_reuses(self):
        folder = self.scratch()
        gh = fake_gh(
            folder,
            issues=[
                {
                    "number": 1,
                    "title": "Driver run 2026-11-07T09:00:00Z",
                    "labels": [],
                    "state": "open",
                    "author": "me",
                },
                {
                    "number": 9,
                    "title": "Driver run 2026-11-06T09:00:00Z",
                    "labels": [],
                    "state": "open",
                    "author": "me",
                },
            ],
        )
        issues = [
            {"number": 1, "title": "Driver run 2026-11-07T09:00:00Z", "labels": []},
            {"number": 9, "title": "Driver run 2026-11-06T09:00:00Z", "labels": []},
        ]
        self.assertEqual(
            self.issues.open_run(str(folder), gh, "Start Day 05", "uuid-1", issues),
            (1, None),
        )
        self.assertEqual(read_calls(folder), [["issue", "comment", "1", "--body-file", "-"]])

    def test_close(self):
        folder = self.scratch()
        gh = fake_gh(
            folder,
            issues=[
                {
                    "number": 4,
                    "title": "park: x",
                    "labels": ["parked"],
                    "state": "closed",
                    "author": "me",
                },
                {
                    "number": 5,
                    "title": "Driver run 2026-11-07T09:00:00Z",
                    "labels": [],
                    "state": "open",
                    "author": "me",
                },
            ],
        )
        self.assertIsNone(self.issues.close(str(folder), gh, 4, "done"))
        self.assertEqual(
            read_calls(folder),
            [["issue", "comment", "4", "--body-file", "-"], ["issue", "close", "4"]],
        )
        self.assertEqual(
            self.issues.close(str(folder), gh, 99, "x"),
            "gh issue comment exited 1",
        )
        self.assertIsNone(self.issues.close(str(folder), gh, 5, "off"))
        spec = json.loads((folder / "fake.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [issue["state"] for issue in spec["issues"] if issue["number"] == 5], ["closed"]
        )

    def test_close_times_out(self):
        folder = self.scratch()
        gh = fake_gh(
            folder,
            issues=[
                {
                    "number": 4,
                    "title": "park: x",
                    "labels": ["parked"],
                    "state": "open",
                    "author": "me",
                },
            ],
        )
        spec = json.loads((folder / "fake.json").read_text(encoding="utf-8"))
        spec.update({"sleep_on": "comment", "sleep": 5})
        (folder / "fake.json").write_bytes(json.dumps(spec).encode("utf-8"))
        started = time.monotonic()
        result = self.issues.close(str(folder), gh, 4, "x", timeout=1)
        self.assertEqual(result, "gh issue comment timed out")
        self.assertLess(time.monotonic() - started, 3)
