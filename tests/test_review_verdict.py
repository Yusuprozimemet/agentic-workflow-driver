"""The reviewer's verdict and its comment (Day 12, Track D): driver.review.verdict reads the
reviewer's result, driver.review.body writes the comment, and driver.issues.pr_comment posts it on
the pull request. Checks C12.8 to C12.10."""

import importlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_github import fake_gh, read_bodies, read_calls


class ReviewVerdictTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top, as in test_github: where driver/review.py has no verdict
        # yet, each test fails alone with AttributeError.
        self.review = importlib.import_module("driver.review")

    def test_verdicts(self):
        # C12.8: the found lines and the blockers, when the REVIEW line agrees with them; else None.
        cases = [
            (
                "found: blocker — a\nfound: advice — b\nREVIEW: blocker",
                (["found: blocker — a", "found: advice — b"], ["found: blocker — a"]),
            ),
            ("found: advice — b\n\nREVIEW: none\n", (["found: advice — b"], [])),
            ("REVIEW: none", ([], [])),
            ("found: blocker — a\nREVIEW: none", None),
            ("REVIEW: blocker", None),
            ("found: advice — b", None),
            ("", None),
            ("REVIEW: none\nmore", None),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(self.review.verdict(text), expected)

    def test_body(self):
        # C12.9: the comment names the head and the session, lists the found lines, and ends with
        # the REVIEW line that the blockers decide.
        self.assertEqual(
            self.review.body("abc1234", "s1", ["found: advice — b"]),
            "review of `abc1234` (session `s1`):\nfound: advice — b\nREVIEW: none",
        )
        blocked = self.review.body("abc1234", "s1", ["found: blocker — a", "found: advice — b"])
        self.assertEqual(blocked.split("\n")[-1], "REVIEW: blocker")
        self.assertEqual(
            blocked,
            "review of `abc1234` (session `s1`):\nfound: blocker — a\nfound: advice — b\nREVIEW: blocker",
        )
        empty = self.review.body("abc1234", "s1", [])
        # The lines after the header first, so that a failure here does not print the head.
        self.assertEqual(empty.split("\n")[1:], ["nothing found", "REVIEW: none"])
        self.assertEqual(empty, "review of `abc1234` (session `s1`):\nnothing found\nREVIEW: none")


class ReviewCommentTest(unittest.TestCase):
    def setUp(self):
        # Imported here, as in IssueWritesTest: where driver/issues.py has no pr_comment yet, each
        # test fails alone with AttributeError.
        self.issues = importlib.import_module("driver.issues")
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_pr_comment(self):
        # C12.10: one comment on the pull request, its body read from stdin; a failed gh says why.
        project = Path(self.root, "project")
        project.mkdir()
        folder = Path(self.root, "gh")
        folder.mkdir()
        gh = fake_gh(folder)
        self.assertIsNone(self.issues.pr_comment(str(project), gh, 12, "x\ny"))
        self.assertEqual(read_calls(folder), [["pr", "comment", "12", "--body-file", "-"]])
        self.assertEqual(
            read_bodies(folder),
            [{"args": ["pr", "comment", "12", "--body-file", "-"], "body": "x\ny"}],
        )

        folder2 = Path(self.root, "gh2")
        folder2.mkdir()
        gh = fake_gh(folder2, comment_code=1)
        self.assertIsNotNone(self.issues.pr_comment(str(project), gh, 12, "x\ny"))
