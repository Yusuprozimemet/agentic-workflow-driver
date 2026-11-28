"""The quality score's recipe (scripts/pipeline/counts/spec_drift_score.py) on small made-up data."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pipeline  # noqa: E402,F401  (importing it puts the pipeline's folders on the path)
from spec_drift_score import combine, count, quality_score  # noqa: E402


def crit(cid, day, tag="new", red=True, abilities=()):
    return dict(id=cid, day=day, tag=tag, seen_red=dict(state=red), abilities=list(abilities))


# Days 1 and 2 finished, Day 3 in progress.
DATA = dict(
    days=[dict(day=1, status="done", relabel=None, defects=[dict(id="D1.1", found="Track A"), dict(id="D1.2", found="close")]),
          dict(day=2, status="closed", relabel=dict(cause=[3, 4]), defects=[dict(id="D2.1", found="Day 01 review")]),
          dict(day=3, status="active", relabel=None, defects=[dict(id="D3.1", found="close")])],
    criteria_index=[crit("C1.1", 1, abilities=["a"]), crit("C1.2", 1, tag="hold", red=None), crit("C2.1", 2), crit("C3.1", 3)],
    replay=dict(cells=[dict(criterion="C1.1", n=1, state="holds"), dict(criterion="C1.2", n=1, state="holds, never broken"),
                       dict(criterion="C2.1", n=1, state="holds"), dict(criterion="C2.1", n=2, state="broken"),
                       dict(criterion="C3.1", n=1, state="broken")]),
    plan=dict(commitments=[dict(id="P01", owner_day=1, rule=False), dict(id="P02", owner_day=2, rule=False),
                           dict(id="P03", owner_day=3, rule=False), dict(id="P04", owner_day=None, rule=True)],
              links={"C1.1": ["P01"], "C1.2": [], "C2.1": [], "C3.1": ["P02"]}),
    defect_recurrence=dict(recurrences=[dict(id="D2.1")]),
    verification=[dict(number=1, day=1, failed=False), dict(number=2, day=2, failed=True), dict(number=3, day=3, failed=True)],
    rows=[dict(day=1, kind="close", spec_names=10, names_in_code=9), dict(day=2, kind="code", spec_names=99, names_in_code=0),
          dict(day=2, kind="close", spec_names=10, names_in_code=10)],
    look_ahead=dict(hand_offs=[dict(how="picked", source="Day 01 Notes"), dict(how="lapsed", source="Day 02 Notes"),
                               dict(how="open", source="Day 01 Notes")]),
    yardsticks=dict(rows=[dict(key="cost", baseline=2.0, values=[dict(day=1, value=1.0), dict(day=2, value=4.0)])]),
    user_stories=dict(abilities=[dict(key="a", name="A"), dict(key="b", name="B")], stories=[dict(number=1, ability="a")]),
)


def counts(scope):
    return {p["key"]: [(c["name"], c["n"], c["m"]) for c in p["counts"]] for p in scope["parts"]}


class QualityScoreTest(unittest.TestCase):
    def test_the_finished_days_are_counted_part_by_part(self):
        got = counts(quality_score(DATA)["all"])
        self.assertEqual(got, {
            # P02 is named only by the Day in progress: named, as graph 12 counts it
            "plan": [("Commitments due by a closed Day that a criterion names", 2, 2),
                     ("Criteria that name a commitment, or guard what exists", 2, 3)],
            "agree": [("Names the specs give that are in the code", 10, 10)],
            "proof": [("Still holds at the last re-check", 2, 3), ("Test seen to fail when the code is broken on purpose", 1, 3),
                      ("Test seen red before the code was written", 2, 3)],
            "check": [("Defects found before the close", 1, 3), ("Defects that do not repeat an earlier one", 2, 3),
                      ("Pull requests whose checks passed on every push", 1, 2),
                      ("Hand-offs to a later Day that were picked up", 1, 2), ("Defect tags a blind reader gave the same", 3, 4)],
            "cost": [("Cost of a merged pull request", None, None)]})

    def test_a_day_has_its_own_score_and_a_day_in_progress_none(self):
        score = quality_score(DATA)
        self.assertEqual(sorted(score["days"]), ["1", "2"])
        day1 = counts(score["days"]["1"])
        self.assertEqual(day1["agree"], [("Names the specs give that are in the code", 9, 10)])
        self.assertEqual(len(day1["plan"]), 1)  # the commitments due are counted for the whole project only

    def test_cost_scores_the_yardstick_over_what_each_day_spent_capped_at_100(self):
        cost = next(p for p in quality_score(DATA)["all"]["parts"] if p["key"] == "cost")
        self.assertEqual(cost["pct"], 75.0)  # Day 1 spent under the yardstick (100), Day 2 twice it (50)
        self.assertEqual(cost["counts"][0]["note"].split(":")[0], "$2.50 spent against a yardstick of $2.00")

    def test_an_ability_scores_its_criteria_and_its_pull_requests(self):
        abilities = quality_score(DATA)["abilities"]
        self.assertEqual((abilities["a"]["score"], [p["key"] for p in abilities["a"]["parts"]]), (100.0, ["plan", "proof", "check"]))
        self.assertIsNone(abilities["b"])

    def test_the_parts_combine_by_geometric_mean_and_name_the_lowest(self):
        got = combine([("x", "X", "g1", [count("a", 1, 1)]), ("y", "Y", "g2", [count("b", 1, 4), None]), ("z", "Z", "g3", [None])])
        self.assertEqual((got["score"], got["low"], [p["key"] for p in got["parts"]]), (50.0, "y", ["x", "y"]))

    def test_the_days_own_scores_have_a_mean_apart_from_the_whole(self):
        # each Day's score rounded half up as the page shows it, then their mean rounded half up; a Day with
        # nothing to count has no score and is left out
        score = quality_score(DATA)
        self.assertIn("days_mean", sorted(score))
        shown = [int(d["score"] + 0.5) for d in score["days"].values() if d]
        self.assertEqual(score["days_mean"], int(sum(shown) / len(shown) + 0.5))
        bare = dict(DATA, days=DATA["days"] + [dict(day=4, status="done", relabel=None, defects=[])])
        bare_score = quality_score(bare)
        self.assertEqual((bare_score["days"]["4"], bare_score["days_mean"]), (None, score["days_mean"]))

    def test_a_day_with_many_more_checks_weighs_more_in_the_whole_than_in_the_mean(self):
        # Day 1 gets twenty proven criteria more; Day 2 keeps its one broken one: the whole leans to Day 1
        many = [crit(f"C1.{n}", 1) for n in range(3, 23)]
        cells = [dict(criterion=c["id"], n=1, state="holds") for c in many]
        heavy = dict(DATA, criteria_index=DATA["criteria_index"] + many,
                     replay=dict(cells=DATA["replay"]["cells"] + cells))
        score = quality_score(heavy)
        self.assertIn("days_mean", sorted(score))
        whole = int(score["all"]["score"] + 0.5)
        self.assertNotEqual(whole, score["days_mean"])

    def test_the_mean_of_the_days_rounds_half_up_twice(self):
        # Day 1 scores 100; Day 2 found 1 of its 4 defects before the close, so 62.5, shown as 63; the mean of
        # 100 and 63 is 81.5, shown as 82 (Python's round would give 62, then 81)
        def defect(i, found):
            return dict(id=i, found=found)
        days = [dict(day=1, status="done", relabel=None, defects=[defect("D1.1", "Track A")]),
                dict(day=2, status="done", relabel=None,
                     defects=[defect("D2.1", "close"), defect("D2.2", "close"), defect("D2.3", "close"),
                              defect("D2.4", "Track A")])]
        score = quality_score(dict(days=days))
        self.assertIn("days_mean", sorted(score))
        self.assertEqual(([score["days"][d]["score"] for d in ("1", "2")], score["days_mean"]), ([100.0, 62.5], 82))

    def test_a_mean_half_way_over_an_even_number_rounds_up(self):
        # Day 1 scores 100; Day 2 found 11 of its 50 defects before the close, so (22 + 100) / 2 = 61; the mean of
        # 100 and 61 is 80.5, shown as 81 (Python's round would give the even 80)
        early = [dict(id=f"D2.{n}", found="Track A") for n in range(11)]
        late = [dict(id=f"D2.{n}", found="close") for n in range(11, 50)]
        days = [dict(day=1, status="done", relabel=None, defects=[dict(id="D1.1", found="Track A")]),
                dict(day=2, status="done", relabel=None, defects=early + late)]
        score = quality_score(dict(days=days))
        self.assertIn("days_mean", sorted(score))
        self.assertEqual(([score["days"][d]["score"] for d in ("1", "2")], score["days_mean"]), ([100.0, 61.0], 81))

    def test_no_day_with_a_score_means_no_mean(self):
        # a finished Day with nothing to count has no score of its own, so there is nothing to average
        score = quality_score(dict(days=[dict(day=1, status="done", relabel=None, defects=[])]))
        self.assertIn("days_mean", sorted(score))
        self.assertEqual((score["days"], score["days_mean"]), ({"1": None}, None))

    def test_no_finished_day_means_no_score(self):
        self.assertIsNone(quality_score(dict(DATA, days=[dict(day=1, status="active")])))
        self.assertIsNone(quality_score({}))


if __name__ == "__main__":
    unittest.main()
