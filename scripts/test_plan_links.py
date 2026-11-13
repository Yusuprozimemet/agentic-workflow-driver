"""Tests for the check of the plan's commitments and the criteria's links to them."""
import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("plan_links", os.path.join(HERE, "plan-links.py"))
pl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pl)

PLAN = "# Plan\n\nThe driver parks when the next step\nis a stopping point.\n\nNothing merges by itself.\n"
DAY1 = "## Acceptance criteria\n\n- [x] C01.1 **new** — parks at a stop\n- [x] C01.2 **hold** — guard\n"
DAY11 = "## Acceptance criteria\n\n- [ ] C11.1 **new** — the reviewer\n"


def promise(pid, quote, text, owner=1, rule=False, **more):
    return dict(id=pid, short="s", section="x", owner_day=owner, rule_about_people=rule,
                quote=quote, text=text, **more)


class PlanLinksTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = self.temp.name
        self.promises = [
            promise("P01", "parks when the next step is a stopping point",
                    "The driver parks when the next step is a stopping point."),
            promise("P02", "Nothing merges by itself.", "Nothing merges by itself.", owner=None, rule=True),
        ]
        self.links = {"C01.1": [{"p": "P01", "quote": "parks when the next step"}], "C01.2": []}
        self.files = {"plan.md": PLAN, "specs/day-01-dry-run.md": DAY1}

    def run_check(self):
        for name, body in self.files.items():
            self.write(name, body)
        self.write("specs/plan/promises.json", json.dumps(self.promises))
        self.write("specs/plan/links-days-01-10.json", json.dumps(self.links))
        return pl.check(self.root)

    def write(self, name, body):
        path = os.path.join(self.root, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(body)

    def test_the_repository_passes(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = pl.main([])
        self.assertEqual(code, 0, out.getvalue())
        self.assertRegex(out.getvalue(), r"^plan links: 97 commitments, 146 criteria, \d+ links, every quote found\n$")

    def test_a_quote_wrapped_over_lines_in_plan_md_is_found(self):
        problems, summary = self.run_check()
        self.assertEqual(problems, [])
        self.assertEqual(summary, "plan links: 2 commitments, 2 criteria, 1 links, every quote found")

    def test_a_commitment_quote_missing_from_plan_md_fails(self):
        self.promises[0]["quote"] = "parks when the next step is a phase's end"
        problems, _ = self.run_check()
        self.assertEqual(problems, ["P01: quote not in plan.md: \"parks when the next step is a phase's end\""])

    def test_a_link_quote_missing_from_its_commitment_fails(self):
        self.links["C01.1"][0]["quote"] = "parks at once"
        problems, _ = self.run_check()
        self.assertEqual(problems, ['C01.1: quote not in P01: "parks at once"'])

    def test_a_link_may_quote_a_changed_commitment_s_change(self):
        self.promises[0]["change"] = "It now also parks on a halt."
        self.links["C01.1"][0]["quote"] = "also parks on a halt"
        problems, _ = self.run_check()
        self.assertEqual(problems, [])

    def test_unknown_ids_fail(self):
        self.links["C01.1"].append({"p": "P09", "quote": "x"})
        self.links["C01.7"] = []
        problems, _ = self.run_check()
        self.assertEqual(problems, ["C01.1: no such commitment P09", "C01.7: no such criterion in specs/"])

    def test_a_criterion_linked_twice_to_one_commitment_fails(self):
        self.links["C01.1"].append({"p": "P01", "quote": "is a stopping point"})
        problems, _ = self.run_check()
        self.assertEqual(problems, ["C01.1: P01 linked twice"])

    def test_every_criterion_of_days_1_to_10_is_in_the_backfill_and_day_11_need_not_be(self):
        del self.links["C01.2"]
        self.files["specs/day-11-reviewer.md"] = DAY11
        problems, _ = self.run_check()
        self.assertEqual(problems, ["C01.2: Day 1 criterion missing from the backfill"])

    def test_owner_day_and_rule_about_people_exclude_each_other(self):
        self.promises[0]["owner_day"] = None
        self.promises[1]["owner_day"] = 3
        problems, _ = self.run_check()
        self.assertEqual(problems, ["P01: owner_day must be a Day number", "P02: a rule about people has no owner Day"])

    def test_bad_and_duplicate_ids_and_missing_fields_fail(self):
        self.promises.append(promise("P1", "Nothing merges by itself.", "t"))
        self.promises.append(promise("P02", "Nothing merges by itself.", "t", owner=None, rule=True))
        self.promises.append({"id": "P03", "text": "t"})
        problems, _ = self.run_check()
        self.assertEqual(problems, ["P1: an id is P or N and two digits", "P02: listed twice",
                                    "P03: missing owner_day, quote, rule_about_people, section, short"])

    def test_problems_exit_1_with_a_count(self):
        self.promises[0]["quote"] = "absent words"
        self.run_check()
        out = io.StringIO()
        with redirect_stdout(out):
            code = pl.main(["--root", self.root])
        self.assertEqual(code, 1)
        self.assertEqual(out.getvalue().splitlines()[-1], "plan links: 1 problem(s)")


if __name__ == "__main__":
    unittest.main()
