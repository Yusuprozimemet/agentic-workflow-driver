"""spec-drift.py's plan graph data: the `Plan:` lines it reads, and where a rewrite of `plan.md` sits.

    python scripts/test_spec_drift_plan.py
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spec_drift_plan as sp  # noqa: E402

DAY_11 = """# Day 11

- [ ] C11.1 **new** — one thing.
  Plan: P27 "a quote"; N03 "another quote"
  Evidence:
- [ ] C11.2 **hold** — a guard.
  Plan: none — it only holds
- [ ] C11.3 **new** — no line yet.
  Evidence:
"""


class Blobs:
    def __init__(self, files):
        self.files = files

    def read(self, sha, path):
        return self.files.get(path, "")


class PlanDataTest(unittest.TestCase):
    def setUp(self):
        self.real = sp.run

    def tearDown(self):
        sp.run = self.real

    def fake_git(self, listing, plan_commits=()):
        def run(*args):
            if args[:2] == ("git", "ls-tree"):
                return "\n".join(listing)
            if args[:2] == ("git", "log"):
                return "\n".join(plan_commits)
            raise AssertionError(args)
        sp.run = run

    def test_a_plan_line_names_its_commitments_none_or_nothing(self):
        self.assertEqual(sp.plan_line_links('  Plan: P27 "a"; N03 "b"\n'), ["P27", "N03"])
        self.assertEqual(sp.plan_line_links("  Plan: none — a guard\n"), [])
        self.assertIsNone(sp.plan_line_links("  Evidence: x\n"))
        self.assertIsNone(sp.plan_line_links("  Plan: P27 with no quote\n"))

    def test_the_backfill_answers_for_days_1_to_10_and_the_plan_lines_after(self):
        self.fake_git(["specs/day-01-start.md", "specs/day-11-next.md", "specs/README.md"])
        blobs = Blobs({"specs/day-01-start.md": "- [x] C01.1 **new** — x.\n- [x] C01.2 **new** — y.\n",
                       "specs/day-11-next.md": DAY_11})
        links, quotes, unlined = sp.criterion_links("head", blobs, {"C01.1": [dict(p="P01", quote="q")]})
        self.assertEqual(links, {"C01.1": ["P01"], "C11.1": ["P27", "N03"], "C11.2": []})
        self.assertEqual((quotes, unlined), (3, ["C01.2", "C11.3"]))

    def test_a_rewrite_sits_after_the_last_day_begun_before_it(self):
        self.fake_git([], ["bbbbbbb000", "ddddddd000", "0rigin000"])
        rows = [dict(sha="0rigin0", pr=None, own_day=None), dict(sha="aaaaaaa", pr=1, own_day=1),
                dict(sha="bbbbbbb", pr=2, own_day=None), dict(sha="ccccccc", pr=3, own_day=2),
                dict(sha="eeeeeee", pr=4, own_day=1), dict(sha="ddddddd", pr=5, own_day=None)]
        self.assertEqual(sp.plan_rewrites("head", rows), [dict(pr=2, after_day=1), dict(pr=5, after_day=2)])

    def test_a_project_with_no_promise_file_has_no_plan_graph(self):
        self.fake_git([])
        self.assertIsNone(sp.plan_graph("head", Blobs({}), []))

    def test_the_commitments_keep_their_order_owner_and_change(self):
        self.fake_git([])
        promises = [dict(id="P01", short="a", section="S", owner_day=None, rule_about_people=True, first_plan="kept", text="t"),
                    dict(id="P02", short="b", section="S", owner_day=3, rule_about_people=False, first_plan="changed", text="u"),
                    dict(id="N01", short="c", section="T", owner_day=4, rule_about_people=False, text="v")]
        got = sp.plan_graph("head", Blobs({sp.PROMISES: json.dumps(promises)}), [])
        self.assertEqual([(c["id"], c["owner_day"], c["rule"], c["change"]) for c in got["commitments"]],
                         [("P01", None, True, None), ("P02", 3, False, "changed"), ("N01", 4, False, None)])


if __name__ == "__main__":
    unittest.main()
