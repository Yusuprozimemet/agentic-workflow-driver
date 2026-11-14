"""Which Days a merge on main re-checks (scripts/replay-history.py)."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "replay_history", ROOT / "scripts" / "replay-history.py"
)
rh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rh)

CLOSED = {"03": 30, "06": 60, "11": 179}
TOOLING = "Merge pull request #184 from me/tooling/stale-breaks-reapply"


class SampledDaysTest(unittest.TestCase):
    def test_a_merge_that_changes_a_closed_days_breaks_re_checks_that_day(self):
        # #184 re-recorded Day 03's and Day 06's breaks; only Day 11 was re-checked at it, so the
        # board kept the #179 sample's "break no longer applies" for both.
        self.assertEqual(
            rh.sampled_days(184, TOOLING, CLOSED, {"03", "06"}), (["03", "06", "11"], "day")
        )

    def test_a_changed_manifest_of_a_day_not_closed_yet_waits(self):
        self.assertEqual(rh.sampled_days(184, TOOLING, CLOSED, {"12"}), (["11"], "day"))

    def test_with_no_manifest_changed_the_rules_are_as_before(self):
        self.assertEqual(rh.sampled_days(184, TOOLING, CLOSED, set()), (["11"], "day"))
        self.assertEqual(
            rh.sampled_days(
                179, "Merge pull request #179 from me/day-11/close-the-day", CLOSED, set()
            ),
            (["03", "06", "11"], "all"),
        )
        self.assertIsNone(
            rh.sampled_days(170, "Merge pull request #170 from me/day-12/track-a", CLOSED, set())
        )


class StillToSampleTest(unittest.TestCase):
    def test_a_merge_measured_before_gets_only_the_days_it_lacks(self):
        self.assertEqual(rh.still_to_sample(["03", "06", "11"], "day", {"11"}), ["03", "06"])

    def test_a_closing_merge_measured_before_is_not_measured_again(self):
        self.assertEqual(rh.still_to_sample(["03", "06", "11"], "all", {"03", "11"}), [])

    def test_a_merge_not_measured_gets_every_day(self):
        self.assertEqual(rh.still_to_sample(["03", "11"], "all", set()), ["03", "11"])


class PageWordsTest(unittest.TestCase):
    def test_the_page_says_the_re_check_runs_after_every_merge_as_recheck_yml_does(self):
        workflow = (ROOT / ".github" / "workflows" / "recheck.yml").read_text(encoding="utf-8")
        self.assertRegex(workflow, r"on:\s*\n\s*push:\s*\n\s*branches: \[main\]")
        page = (ROOT / "docs" / "dashboard" / "dashboard.js").read_text(encoding="utf-8")
        self.assertEqual(page.count("run by hand"), 0)
        self.assertEqual(page.count("It runs after every merge to main"), 2)


if __name__ == "__main__":
    unittest.main()
