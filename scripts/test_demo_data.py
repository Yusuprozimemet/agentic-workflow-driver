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
GRAPHS = ("g1", "g2", "g3", "g4", "g5", "g6", "g7", "g8")
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
        marks = dict(g1=sum(c["n"] > 0 for r in m["g1"]["rows"] for c in r["cells"]), g2=sum(len(r["tiles"]) for r in m["g2"]["rows"]),
                     g3=sum(len(r["tiles"]) for r in m["g3"]["rows"]), g4=len(m["g4"]["merges"]), g5=sum(len(r["dots"]) for r in m["g5"]["rows"]),
                     g6=len(m["g6"]["bars"]), g7=sum(b["total"] > 0 for b in m["g7"]["bars"]), g8=len(m["g8"]["rows"]))
        self.assertEqual([g for g in GRAPHS if not marks[g]], [], marks)
        # The board shows every state a re-check can find, and the trust strip a bar for each re-check.
        self.assertEqual(sorted({t["status"] for r in m["g2"]["rows"] for t in r["tiles"]}),
                         ["broken", "building", "open", "proven", "repair", "skipped", "unproven"])
        self.assertEqual(len(m["g2"]["hist"]), 3)
        # A defect at every gate, and a yardstick still waiting to be counted.
        self.assertEqual([sum(len(r["cells"][i]) for r in m["g5"]["rows"]) for i in range(6)], [1] * 6)
        self.assertEqual([w["name"] for w in m["g8"]["waiting"]], ["Times the driver stopped for a person"])

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
