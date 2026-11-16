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
DAY11 = "## Acceptance criteria\n\n- [ ] C11.1 **new** — the reviewer\n      Plan: none\n"


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
        self.assertRegex(out.getvalue(),
                         r"^plan links: 106 commitments, 146 criteria, \d+ Plan: lines, \d+ links, every quote found\n$")

    def test_a_quote_wrapped_over_lines_in_plan_md_is_found(self):
        problems, summary = self.run_check()
        self.assertEqual(problems, [])
        self.assertEqual(summary, "plan links: 2 commitments, 2 criteria, 0 Plan: lines, 1 links, every quote found")

    def day11(self, *plan_lines):
        crit = "".join(f"      {line}\n" for line in plan_lines)
        self.files["specs/day-11-reviewer.md"] = (
            "## Acceptance criteria\n\n- [ ] C11.1 **new** — the reviewer. Red today: none.\n"
            f"      Test: `ReviewTest.test_it`.\n{crit}      Evidence: x\n- [ ] C11.2 **hold** — guard.\n"
            "      Plan: none\n\n## Verify\n")
        return self.run_check()

    def test_from_day_11_a_plan_line_links_its_criterion_and_its_quotes_are_checked(self):
        problems, summary = self.day11('Plan: P01 "parks when the next step"; P02 "Nothing merges"')
        self.assertEqual(problems, [])
        self.assertEqual(summary, "plan links: 2 commitments, 2 criteria, 2 Plan: lines, 3 links, every quote found")

    def test_a_plan_line_may_wrap_and_may_be_none_with_a_reason(self):
        self.assertEqual(self.day11('Plan: P01 "parks when the next',
                                    'step is a stopping point"')[0], [])
        self.assertEqual(self.day11("Plan: none — tooling the plan does not name")[0], [])

    def test_from_day_11_a_criterion_with_no_plan_line_fails_and_day_10_needs_none(self):
        problems, _ = self.day11()
        self.assertEqual(problems, ["C11.1: no Plan: line (the commitments it serves, or Plan: none)"])

    def test_a_plan_line_with_a_wrong_quote_or_id_fails(self):
        problems, _ = self.day11('Plan: P01 "parks at once", P09 "x"')
        self.assertEqual(problems, ['C11.1: quote not in P01: "parks at once"', "C11.1: no such commitment P09"])

    def test_two_plan_lines_or_one_in_neither_form_fail(self):
        self.assertEqual(self.day11("Plan: none", "Plan: none")[0], ["C11.1: more than one Plan: line"])
        self.assertEqual(self.day11('Plan: P01 parks')[0],
                         ['C11.1: a Plan: line is none, or ids each with a quote: "P01 parks"'])
        self.assertEqual(self.day11('Plan: P01 "parks when" and more')[0],
                         ['C11.1: a Plan: line is none, or ids each with a quote: "P01 "parks when" and more"'])

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

    def test_a_commitment_due_by_the_current_day_that_no_criterion_names_fails(self):
        self.links["C01.1"] = []
        self.assertTrue(self.run_check()[0], "P01 is overdue and nothing said so")
        self.assertEqual(self.run_check()[0], [
            "P01: overdue, due on Day 1, the current Day is 1, and no criterion in force names it: name it in a Plan: "
            "line, or record it in specs/plan/overdue.json with the Day that settles it"])
        self.promises[0]["owner_day"] = 2
        self.assertEqual(self.run_check()[0], [], "due on a later Day: not overdue yet")

    def test_a_commitment_named_only_by_a_replaced_criterion_is_overdue(self):
        self.files["specs/day-02-preflight.md"] = ("## Acceptance criteria\n\n- [x] C02.1 **new** — x\n"
                                                   "      Replaces: C01.1 — was: parks at a stopping point.\n")
        self.links["C02.1"] = []
        self.assertEqual(self.run_check()[0], [
            "P01: overdue, due on Day 1, the current Day is 2, and no criterion in force names it: name it in a Plan: "
            "line, or record it in specs/plan/overdue.json with the Day that settles it"])
        self.files["specs/plan/overdue.json"] = json.dumps([{"id": "P01", "settled_by": 3, "why": "spliced out"}])
        self.assertEqual(self.run_check()[0], [], "an exception for it is not 'named by a criterion now'")

    def test_a_plan_line_of_a_replaced_criterion_names_nothing(self):
        self.links["C01.1"] = []
        self.files["specs/day-12-close.md"] = ("## Acceptance criteria\n\n- [x] C12.1 **new** — x\n"
                                               "      Replaces: C11.1 — was: the reviewer.\n      Plan: none\n")
        problems = self.day11('Plan: P01 "parks when the next step"')[0]
        self.assertEqual([p.split(", the current")[0] for p in problems], ["P01: overdue, due on Day 1"])
        self.assertIn("no criterion in force names it", problems[0])

    def test_an_exception_holds_only_before_the_day_that_settles_it(self):
        self.links["C01.1"] = []
        self.files["specs/plan/overdue.json"] = json.dumps([{"id": "P01", "settled_by": 2, "why": "PR B"}])
        self.assertEqual(self.run_check()[0], [])
        self.files["specs/day-02-preflight.md"] = "## Acceptance criteria\n\n- [x] C02.1 **new** — x\n"
        self.links["C02.1"] = []
        self.assertEqual(self.run_check()[0], [
            "P01: overdue, due on Day 1, the current Day is 2, and no criterion in force names it: name it in a Plan: "
            "line (its exception ran out at Day 2)"])

    def test_an_exception_for_a_named_unknown_or_not_yet_due_commitment_fails(self):
        self.promises.append(promise("P03", "Nothing merges", "Nothing merges by itself.", owner=5))
        self.files["specs/plan/overdue.json"] = json.dumps(
            [{"id": i, "settled_by": 9, "why": "x"} for i in ("P01", "P03", "P09")])
        self.assertEqual(self.run_check()[0], [
            "P01: named by a criterion now: take it out of specs/plan/overdue.json",
            "P03: in specs/plan/overdue.json, but not due yet",
            "P09: in specs/plan/overdue.json, but no such commitment"])

    def test_a_day_with_more_than_a_third_plan_none_is_a_warning_not_a_problem(self):
        problems, _ = self.day11("Plan: none")
        self.assertEqual(problems, [])
        self.assertEqual(pl.none_shares(self.root), [
            "warning: Day 11: 2 of 2 criteria say Plan: none, more than a third: the plan may need a change "
            "(#212, S18)"])
        self.day11('Plan: P01 "parks when the next step"')
        self.assertEqual(pl.none_shares(self.root), [
            "warning: Day 11: 1 of 2 criteria say Plan: none, more than a third: the plan may need a change "
            "(#212, S18)"])


if __name__ == "__main__":
    unittest.main()
