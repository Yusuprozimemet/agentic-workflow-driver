"""A review's start line names its pull request (C15.11): the run log's start line of a review carries
`pr`, the number of the pull request the reviewer was given. The case is the reviewer's own run, from
tests/test_review_loop.py, with the same fake claude and the same project."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import test_box_preflight as preflight
from tests.test_review_loop import REVIEW_ONLY, ReviewCase


class ReviewStartTest(ReviewCase, unittest.TestCase):
    # The same in-process driver run as ReviewLoopTest, in case on needs them.
    run_steps = preflight.BoxPreflightTest.run_steps
    hidden = preflight.BoxPreflightTest.hidden

    def test_start_names_the_pr(self):
        self.review("start-pr", [{"text": REVIEW_ONLY, "cost": 0.25}])
        self.on()
        log = self.run_log()
        prs = [
            r.get("pr", "no pr key")
            for r in log
            if r.get("event") == "start" and r.get("prefix") == "review"
        ]
        self.assertEqual(prs, [12])
