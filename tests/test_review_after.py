"""The reviewer's git check after its session (driver/loop.py, review_pass): C13.16. A git that works before
the review and fails after it stops the run with code 2 and says so, with the step's session and the
reviewer's both run."""

import importlib
import unittest
from unittest import mock

from tests import test_box_preflight as preflight
from tests.test_review_loop import REVIEW_ONLY, ReviewCase, same


class ReviewAfterTest(ReviewCase, unittest.TestCase):
    run_steps = preflight.BoxPreflightTest.run_steps
    hidden = preflight.BoxPreflightTest.hidden

    def test_git_fails_after_the_review(self):
        # C13.16: the snapshot before the reviewer works and the one after it fails: the run stops with
        # code 2, and the line names "after the review" (loop.py's check of after).
        self.review("git_fails_after", [{"text": REVIEW_ONLY}])
        self.secrets = self.folder / "secrets.env"
        review = importlib.import_module("driver.review")
        original = review.snapshot
        calls = []

        def git_works_then_fails(project, git=("git",)):
            calls.append(project)
            if len(calls) == 1:
                return original(project, git=git)
            return {key: None for key in original(project, git=git)}

        with mock.patch.object(review, "snapshot", side_effect=git_works_then_fails):
            code, _, err = self.run_steps("on")
        step, reviewer = self.uuids()
        message = "cannot read the project: git failed after the review of #12"
        same(
            self,
            (
                code,
                message in self.hold(err, step, reviewer),
                len(self.sessions()),
                len(self.reviewer_ids()),
            ),
            (2, True, 2, 1),
        )


if __name__ == "__main__":
    unittest.main()
