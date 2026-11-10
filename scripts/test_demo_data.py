"""The demo data draws every graph of the dashboard and has every key the real data has.

The page tests run docs/dashboard/dashboard.js on demo() with test_dashboard_page.py's harnesses; the
key test reads the keys spec-drift.py's main() writes. Needs node for the page tests.

    python scripts/test_demo_data.py
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_dashboard_page  # noqa: E402  (its harnesses run the page's model and boot on the data they are given)

spec = importlib.util.spec_from_file_location("demo_data", os.path.join(HERE, "demo-data.py"))
demo_data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo_data)
GRAPHS = ("g1", "g3", "g4", "g5", "g6", "g7", "g8", "g9", "g2", "g10", "g11")
REAL = dict(now=dict(current_day=None), rows=[], days=[])


def keys_at_top(text):
    """The names given as name= in an argument list, up to its closing parenthesis, not inside a nested call."""
    keys, depth = [], 0
    for m in re.finditer(r"[()]|\b(\w+)=(?!=)", text):
        if m.group(0) == "(":
            depth += 1
        elif m.group(0) == ")":
            depth -= 1
            if depth < 0:
                break
        elif depth == 0:
            keys.append(m.group(1))
    return keys


def written_keys():
    """The keys spec-drift.py's main() puts in the real dict it writes, and those of its now and meta."""
    with open(os.path.join(HERE, "spec-drift.py"), encoding="utf-8") as f:
        source = f.read()
    block = source[source.index("real = dict(") + len("real = dict("):]
    # now is built as its own dict, "now = dict(", and meta inside the main call
    nested = {name: keys_at_top(source[m.end():]) for name, m in
              ((n, re.search(rf"\b{n} ?= ?dict\(", source)) for n in ("now", "meta"))}
    return keys_at_top(block), nested


class DemoData(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_the_page_draws_every_graph_on_the_demo_data(self):
        out = test_dashboard_page.boot(demo_data.demo())
        self.assertEqual((out["error"], out["logged"]), (None, []), "a graph could not be drawn on the demo data")
        self.assertIn("sample-shop", out["eyebrow"])

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_every_graph_has_marks_to_show_on_the_demo_data(self):
        m = test_dashboard_page.model(demo_data.demo())
        self.assertEqual([g for g in GRAPHS if "error" in m[g]], [])
        marks = dict(g1=len(m["g1"]["merges"]), g3=sum(c["n"] > 0 for r in m["g3"]["rows"] for c in r["cells"]), g4=sum(len(r["tiles"]) for r in m["g4"]["rows"]),
                     g5=sum(len(r["tiles"]) for r in m["g5"]["rows"]), g6=len(m["g6"]["merges"]), g7=sum(len(r["dots"]) for r in m["g7"]["rows"]),
                     g8=len(m["g8"]["bars"]), g9=sum(b["total"] > 0 for b in m["g9"]["bars"]), g2=len(m["g2"]["rows"]),
                     g10=sum(len(lane["bars"]) for d in m["g10"]["dates"] for lane in d["lanes"]),
                     g11=sum(len(c) for r in m["g11"]["rows"] for c in r["cells"]))
        self.assertEqual([g for g in GRAPHS if not marks[g]], [], marks)
        # Every lane of the clock has a bar on the date shown first but the parks, which were answered on
        # earlier dates; every lane has one on some date, and the day buttons can reach every demo day.
        shown = m["g10"]["dates"][m["g10"]["at"]]
        self.assertEqual([lane["name"] for lane in shown["lanes"] if not lane["bars"]], ["Parked for the maintainer"])
        self.assertEqual(sorted({lane["name"] for d in m["g10"]["dates"] for lane in d["lanes"] if lane["bars"]}),
                         sorted(lane["name"] for lane in shown["lanes"]))
        self.assertEqual(sorted({day for d in m["g10"]["dates"] for day in d["days"]}), [1, 2, 3, 4, 5, 6])
        # The board shows every state a re-check can find, and the trust strip a bar for each re-check.
        self.assertEqual(sorted({t["status"] for r in m["g4"]["rows"] for t in r["tiles"]}),
                         ["broken", "building", "open", "proven", "repair", "skipped", "unproven"])
        self.assertEqual(len(m["g4"]["hist"]), 3)
        # A defect at every gate, and the parks, which the notebook has not counted, read from the driver's steps.
        self.assertEqual([sum(len(r["cells"][i]) for r in m["g7"]["rows"]) for i in range(6)], [1] * 6)
        self.assertEqual(m["g2"]["waiting"], [])
        parks = next(r for r in m["g2"]["rows"] if r["key"] == "parks")
        self.assertEqual([c["day"] for c in parks["cells"] if c.get("value") is not None], [4, 5, 6])
        # A step in every column of graph 11, one still open and one with a crashed session.
        self.assertEqual([min(1, sum(len(r["cells"][i]) for r in m["g11"]["rows"])) for i in range(4)], [1] * 4)
        self.assertTrue(any(r["open"] for r in m["g11"]["rows"]) and any(o["crashed"] for r in m["g11"]["rows"] for c in r["cells"] for o in c))
        self.assertTrue(any(r["avg"] for r in m["g2"]["rows"]), "no yardstick on the demo has an average so far")

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_no_graph_on_the_demo_data_says_a_bad_number(self):
        said = json.dumps(test_dashboard_page.model(demo_data.demo()))
        self.assertEqual(re.findall(r"NaN|Infinity|undefined|\$-|null (?:of|pull|days)", said), [])

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_the_banner_shows_on_the_demo_data(self):
        out = test_dashboard_page.boot(dict(demo_data.demo(), demo=True))
        self.assertIsNone(out["error"], "the page threw on the demo data")
        self.assertFalse(out["banner"]["hidden"])
        self.assertIn("Example data", out["banner"]["text"])

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_no_banner_without_the_demo_key(self):
        out = test_dashboard_page.boot(demo_data.demo())
        self.assertIsNone(out["error"], "the page threw on the data without demo")
        self.assertTrue(out["banner"]["hidden"])

    def test_no_day_specs_puts_the_demo_in_the_page(self):
        page = test_dashboard_page.sd.page_data(REAL, [])
        self.assertIs(page.get("demo"), True)
        self.assertEqual({k: v for k, v in page.items() if k != "demo"}, demo_data.demo())

    def test_day_specs_put_the_real_data_in_unchanged(self):
        page = test_dashboard_page.sd.page_data(REAL, ["01"])
        self.assertEqual(page, REAL)
        self.assertNotIn("demo", page)

    def test_every_token_row_has_the_hook_counts_with_reads_over_whole_and_bash_over_cut(self):
        for row in demo_data.demo()["tokens"]:
            for k in ("bash", "cut", "reads", "whole"):
                self.assertIn(k, row)
            self.assertGreaterEqual(row["reads"], row["whole"])
            self.assertGreaterEqual(row["bash"], row["cut"])

    def test_every_demo_row_says_which_day_its_pull_request_belongs_to(self):
        rows = demo_data.demo()["rows"]
        self.assertEqual([r["own_day"] for r in rows if "own_day" not in r], [])
        for r in rows:
            if not r["branch"].startswith("day-"):
                self.assertIsNone(r["own_day"], r["branch"])
            else:
                self.assertEqual(r["own_day"], r["day"])

    def test_the_main_sessions_token_rows_say_what_was_spent_past_150k_and_never_more_than_the_cost(self):
        rows = demo_data.demo()["tokens"]
        self.assertEqual([r for r in rows if not 0 <= r["cost_past_150k"] <= r["cost"]], [])
        self.assertTrue(all(r["cost_past_150k"] > 0 for r in rows if r["agent"] == "main"))

    def test_the_drivers_steps_are_in_the_counters_format_and_end_every_way_a_step_can(self):
        runs = demo_data.demo()["driver_runs"]
        self.assertEqual(sorted({s["ended"] for s in runs["steps"]}), ["fixed", "merged", "open", "parked"])
        self.assertEqual(sorted({p["by"] for s in runs["steps"] for p in s["parks"]}), ["fault", "maintainer"])
        self.assertEqual(sum(s["crashes"] for s in runs["steps"]), 1)
        # Each park's issue is one of the parked issues, titled with its line, and was answered.
        issues = {i["number"]: i for i in runs["parks"]}
        for park in (p for s in runs["steps"] for p in s["parks"]):
            self.assertEqual(issues[park["issue"]]["title"], park["line"])
            self.assertLess(issues[park["issue"]]["opened"], issues[park["issue"]]["closed"])
        # The keys are those scripts/driver-runs.py writes, with the issue spec-drift.py gives a park.
        spec = importlib.util.spec_from_file_location("driver_runs", os.path.join(HERE, "driver-runs.py"))
        counter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(counter)
        sentence = "Day 04 Track A: the day's work"
        (counted,) = counter.count([
            dict(event="start", at="2026-10-11T09:00:00Z", step=sentence, prefix="day-04/track-a", session="s"),
            dict(event="park", at="2026-10-11T09:30:00Z", step=sentence, line="park: #1 carries Oversized:")])
        for step in runs["steps"]:
            self.assertEqual(list(step), list(counted))
            self.assertEqual(counter.count([dict(event="park", step=step["step"], line="")])[0]["prefix"], step["prefix"])
            for session in step["sessions"]:
                self.assertEqual(list(session), list(counted["sessions"][0]))
            for park in step["parks"]:
                self.assertEqual(list(park), list(counted["parks"][0]) + ["issue"])
                self.assertEqual(counter.by(park["line"]), park["by"])

    def test_the_same_dict_comes_out_on_every_call(self):
        self.assertEqual(demo_data.demo(), demo_data.demo())

    def test_it_has_every_key_the_real_data_has(self):
        top, nested = written_keys()
        self.assertGreaterEqual(len(top), 20, "the keys were not found in spec-drift.py")
        data = demo_data.demo()
        self.assertEqual([k for k in top if k not in data], [])
        for name, keys in nested.items():
            self.assertEqual([k for k in keys if k not in data[name]], [], name)

    def test_the_script_prints_the_dict_it_returns(self):
        out = subprocess.run([sys.executable, os.path.join(HERE, "demo-data.py")], capture_output=True,
                             encoding="utf-8", check=True).stdout
        self.assertEqual(json.loads(out), demo_data.demo())


if __name__ == "__main__":
    unittest.main()
