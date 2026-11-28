"""The cell's own key of spec-drift.json (scripts/pipeline/counts/spec_drift_view_cell.py): each checking agent's
challenge test from its case set, and the check each fix is drawn beside from docs/dashboard/fix-stations.json."""

import importlib
import json
import os
import sys
import unittest

SCRIPTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)
import pipeline  # noqa: E402,F401  (importing it puts the pipeline's folders on the path)

MODULE = os.path.join(SCRIPTS, "pipeline", "counts", "spec_drift_view_cell.py")
TABLE = os.path.join(ROOT, "docs", "dashboard", "fix-stations.json")


def view():
    """The module, loaded inside a test: missing, it fails that test's assertion and no other."""
    return importlib.import_module("spec_drift_view_cell")


def cases(cases, recorded=None):
    return json.dumps(dict(agent="x", cases=cases, **({"recorded": recorded} if recorded else {})))


class CellCardsTest(unittest.TestCase):
    def test_a_card_is_the_recorded_count_over_the_known_cases(self):
        self.assertTrue(os.path.isfile(MODULE), "scripts/pipeline/counts/spec_drift_view_cell.py")
        texts = {
            # 2 cases naming 3 known faults between them; 2 named on the worst run
            "spec-auditor": cases([dict(known=["a", "b"]), dict(known=["c"])], dict(named=2, runs=3)),
            # 3 cases, 2 known faults (a case with none, and one with no list)
            "track-reviewer": cases([dict(known=["x", "y"]), dict(known=[]), dict()], dict(named=1, runs=3)),
            # 3 cases, 2 of them a blocker
            "reviewer": cases([dict(expect="blocker"), dict(expect="none"), dict(expect="blocker")], dict(verdict=2, named=1, runs=3)),
            "defect-rater": cases([dict(), dict()], dict(cause=5, stage=6, made=7, runs=3)),
        }
        # five defects: two the auditor found, one the track-reviewer, one CI and one the driver's reviewer
        found = ["auditor", "auditor", "track-reviewer", "CI", "driver reviewer"]
        d = dict(one_day=dict(days=[dict(defects=[dict(found=f) for f in found[:3]]), dict(defects=[dict(found=f) for f in found[3:]])]),
                 defect_counts=dict(rater=dict(cause=[4, 5])))
        cards = view().cell_cards(d, texts)
        self.assertEqual(list(cards), ["sa", "chap", "ci", "rater"])
        self.assertEqual(cards["sa"], dict(agent="spec-auditor", cases=2, runs=3, n=2, of=3, found=2))
        self.assertEqual(cards["chap"], dict(agent="track-reviewer", cases=3, runs=3, n=1, of=2, found=1))
        self.assertEqual(cards["ci"], dict(agent="reviewer", cases=3, runs=3, n=2, of=3, named=1, named_of=2, found=2))
        self.assertEqual(cards["rater"], dict(agent="defect-rater", cases=2, runs=3, cause=5, stage=6, made=7, real=dict(cause=[4, 5])))
        # a set that is missing, one that is not JSON and one with no recorded count are left out
        left = dict(texts, **{"spec-auditor": None, "track-reviewer": "{not json", "reviewer": cases([dict(expect="none")])})
        self.assertEqual(list(view().cell_cards(d, left)), ["rater"])
        # with no rater's count in the data, its real agreement is empty
        self.assertEqual(view().cell_cards(dict(d, defect_counts={}), texts)["rater"]["real"], {})


class FixStationsTest(unittest.TestCase):
    def test_a_fix_stands_where_the_table_puts_it(self):
        self.assertTrue(os.path.isfile(MODULE), "scripts/pipeline/counts/spec_drift_view_cell.py")
        table = json.dumps(dict(what="made up", stations={"1": "sa", "3": "chap", "4": "bogus"}))
        stations, problems = view().fix_stations(table, [1, 2, 4])
        self.assertEqual(stations, {"1": "sa"})
        self.assertEqual(problems, [
            "fix #2 has no station in docs/dashboard/fix-stations.json, so the cell draws it at no check",
            "docs/dashboard/fix-stations.json puts fix #4 at 'bogus', which is none of sa, test, chap, ko, spec, ci",
            "docs/dashboard/fix-stations.json places #3, which is no fix in specs/fixes.json",
        ])
        self.assertEqual(view().fix_stations("{not json", [1]),
                         ({}, ["docs/dashboard/fix-stations.json cannot be read, so the cell draws no fix at a check"]))

    def test_every_fix_on_record_has_a_station(self):
        self.assertTrue(os.path.isfile(MODULE), "scripts/pipeline/counts/spec_drift_view_cell.py")
        self.assertTrue(os.path.isfile(TABLE), "docs/dashboard/fix-stations.json")
        with open(os.path.join(ROOT, "specs", "fixes.json"), encoding="utf-8") as f:
            prs = [x["pr"] for x in json.load(f)]
        with open(TABLE, encoding="utf-8") as f:
            stations, problems = view().fix_stations(f.read(), prs)
        self.assertEqual(len(problems), 0, "; ".join(problems))
        self.assertEqual(len(stations), len(prs), "every fix in specs/fixes.json needs a station in docs/dashboard/fix-stations.json")

class CellKeyTest(unittest.TestCase):
    def test_the_key_holds_the_cards_the_stations_and_the_total(self):
        self.assertTrue(os.path.isfile(MODULE), "scripts/pipeline/counts/spec_drift_view_cell.py")
        d = dict(learning=dict(fixes=[dict(pr=5), dict(pr=6)]), defect_recurrence=dict(defects=7),
                 one_day=dict(days=[dict(defects=[dict(found="auditor")])]), defect_counts={})
        texts = {"spec-auditor": cases([dict(known=["a"])], dict(named=1, runs=3))}
        table = json.dumps(dict(what="made up", stations={"5": "sa", "6": "ci"}))
        key = view().cell(d, texts, table)
        self.assertEqual((sorted(key["fix_station"]), key["total"]), (["5", "6"], 7))
        self.assertEqual(key, dict(
            cards=dict(sa=dict(agent="spec-auditor", cases=1, runs=3, n=1, of=1, found=1)), fix_station={"5": "sa", "6": "ci"},
            problems=[], total=7))
        # a table missing #6 says so
        short = json.dumps(dict(what="made up", stations={"5": "sa"}))
        self.assertEqual(view().cell(d, texts, short)["problems"],
                         ["fix #6 has no station in docs/dashboard/fix-stations.json, so the cell draws it at no check"])
        # with no learning view there is no fix: nothing is placed, and each of the table's entries names no fix
        bare = view().cell(dict(d, learning=None), {}, table)
        self.assertEqual((bare["fix_station"], bare["problems"], bare["cards"], bare["total"]), ({}, [
            "docs/dashboard/fix-stations.json places #5, which is no fix in specs/fixes.json",
            "docs/dashboard/fix-stations.json places #6, which is no fix in specs/fixes.json"], {}, 7))


if __name__ == "__main__":
    unittest.main()
