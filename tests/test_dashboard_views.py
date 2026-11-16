"""The dashboard's newer views (scripts/spec_drift_views.py) and the citations they read: what a criterion cites, each
criterion's state, and the gene, which every commitment of the plan sits in once. Needs node for the page's model."""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


specs = load("spec_drift_specs", "spec_drift_specs.py")
demo_data = load("demo_data", "demo-data.py")

# C10.12's lines as Day 10's spec has them, cut down: its `seen red:` quote holds "#5", a test's output.
C10_12 = """- [x] C10.12 **new** — As C10.11, the probe printing `refused /state/refusals`.
      Test: `ReachCheckTest.test_unwritable_log_refuses`.
      Evidence: `ReachCheckTest.test_unwritable_log_refuses` (#152; two breaks recorded again in #153).
      seen red: python -m unittest tests.test_reach_check on main → AssertionError: (0, 'opened: #5 from `x`\\n') (#152)
      broken: a refused folder that must write not read (C10.12) → AssertionError: (1, 'park') (#154)
"""

# The state promises() in docs/dashboard/dashboard.js gave each criterion up to e12b504 (#232), kept here word for
# word so the state spec_drift_views.py gives now can be held to it.
OLD_STATUS = r"""
const fs = require("fs"), DATA = JSON.parse(fs.readFileSync(0, "utf8"));
const REPLAY_LOOK = %s;
const finished = d => d.status === "done" || d.status === "closed" || d.status === "cut";
const rp = DATA.replay || {}, index = DATA.criteria_index || [], byDay = new Map(DATA.days.map(d => [d.day, d]));
const cells = [...(rp.cells || [])].sort((a, b) => a.n - b.n), latest = new Map(cells.map(c => [c.criterion, c]));
console.log(JSON.stringify(index.map(c => {
  const day = byDay.get(c.day), cell = latest.get(c.id), look = (cell && REPLAY_LOOK[cell.state]) || {};
  return [c.id, !day || !finished(day) ? "building" : (c.replaced_by || []).length ? "replaced" : c.ticked === false ? "open" : look.group || "unchecked"];
})));
"""


# geneDraw() from dashboard.js on the data from stdin, on a document that only keeps what is made: the marks it
# drew, counted by class, and how many of them it handed to the Day filter.
DRAWN = r"""
const fs = require("fs"), vm = require("vm"), made = [];
const node = tag => ({ tag, attrs: {}, kids: [], style: {}, dataset: {}, classList: { add() {}, remove() {} },
  setAttribute(k, v) { this.attrs[k] = String(v); }, appendChild(c) { this.kids.push(c); return c; },
  replaceChildren(...c) { this.kids = c; }, addEventListener() {}, querySelectorAll() { return []; } });
const document = { createElementNS(ns, tag) { const n = node(tag); made.push(n); return n; },
  createElement: node, addEventListener() {} };
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")), document, made, node });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const drawn = [], is = cls => made.filter(e => (e.attrs.class || "").split(" ").includes(cls)).length;
  geneDraw(model(DATA).gene, node("div"), node("div"), (n, days) => { drawn.push(days); return n; });
  ({ bands: is("b"), quotes: is("rd") - is("rg"), cells: is("tc"), beads: is("bead"), ring: is("rg"), inner: is("rk"),
     dated: drawn.length, names: is("t-row"), box: made[0].attrs.viewBox.split(" ").length })`, ctx)));
"""


def page_replay_look():
    """REPLAY_LOOK as dashboard.js declares it, as JSON."""
    with open(os.path.join(ROOT, "docs", "dashboard", "dashboard.js"), encoding="utf-8") as f:
        text = f.read()
    body = re.search(r"^const REPLAY_LOOK = (\{.*?^\});", text, re.DOTALL | re.MULTILINE).group(1)
    return subprocess.run(
        ["node", "-e", f"console.log(JSON.stringify({body}))"],
        capture_output=True,
        encoding="utf-8",
        check=True,
    ).stdout


class CitationTest(unittest.TestCase):
    def test_a_criterion_cites_only_its_evidence_line_and_its_breaks_trailing_pull_request(self):
        crit = specs.criteria(C10_12)[0]
        self.assertEqual(crit["prs"], [152, 153, 154])
        self.assertNotIn(5, crit["prs"], "#5 is in a seen red: quote, not a citation")


@unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
class StateTest(unittest.TestCase):
    def test_each_criterion_has_the_state_the_page_used_to_work_out_on_demo_data(self):
        import spec_drift_views as views

        data = demo_data.demo()
        old = subprocess.run(
            [
                "node",
                "-e",
                OLD_STATUS % json.dumps({k: {"group": v} for k, v in views.REPLAY_GROUP.items()}),
            ],
            input=json.dumps(data),
            capture_output=True,
            encoding="utf-8",
            check=True,
        ).stdout
        self.assertEqual([[c["id"], c["state"]] for c in data["criteria_index"]], json.loads(old))
        self.assertEqual(
            len({c["state"] for c in data["criteria_index"]}), 8, "the demo shows most states"
        )

    def test_the_replay_groups_are_the_pages(self):
        import spec_drift_views as views

        self.assertEqual(
            {k: v.get("group") for k, v in json.loads(page_replay_look()).items()},
            views.REPLAY_GROUP,
        )

    def test_a_criterion_that_stopped_and_holds_again_came_back(self):
        import spec_drift_views as views

        index = [
            {"id": "C1.1", "day": 1, "ticked": True, "replaced_by": []},
            {"id": "C1.2", "day": 1, "ticked": True, "replaced_by": []},
        ]
        cells = [
            {"criterion": "C1.1", "n": 1, "state": "code broken"},
            {"criterion": "C1.1", "n": 2, "state": "holds"},
            {"criterion": "C1.2", "n": 1, "state": "holds"},
            {"criterion": "C1.2", "n": 2, "state": "code broken"},
        ]
        views.criterion_states(index, [{"day": 1, "status": "closed"}], {"cells": cells})
        self.assertEqual(
            [(c["state"], c["back"]) for c in index], [("proven", True), ("broken", False)]
        )


class SeenTest(unittest.TestCase):
    def test_what_the_replay_saw_of_a_criterion_is_kept_with_each_stop(self):
        import spec_drift_views as views

        index = [{"id": "C1.1", "day": 1, "ticked": True, "replaced_by": []}]
        states = ["holds", "code broken", "code broken", "holds", "break no longer applies"]
        replay = {
            "cells": [{"criterion": "C1.1", "n": n, "state": s} for n, s in enumerate(states, 1)],
            "merges": [{"n": n, "pr": 100 + n} for n in range(1, 6)],
        }
        views.criterion_states(index, [{"day": 1, "status": "closed"}], replay)
        seen = index[0].get("seen") or {}
        stops = seen.get("stops", [])
        self.assertEqual([(s["pr"], s["held"]) for s in stops], [(102, 104), (105, None)])
        self.assertEqual([s["state"] for s in stops], ["code broken", "break no longer applies"])
        self.assertEqual((seen["merges"], seen["last"]), (5, 105))


def commitment(pid, owner=1, rule=False):
    return {"id": pid, "short": pid, "section": "s", "owner_day": owner, "rule": rule}


def crit(cid, state, replaced_by=()):
    return {
        "id": cid,
        "day": int(cid[1]),
        "state": state,
        "replaced_by": list(replaced_by),
        "tag": "new",
    }


class GeneTest(unittest.TestCase):
    def gene(self):
        import spec_drift_views as views

        plan = {
            "commitments": [
                commitment("P01"),
                commitment("P02"),
                commitment("P03"),
                commitment("P04"),
                commitment("P05", owner=None, rule=True),
                commitment("P06", owner=9),
                commitment("P07"),
                commitment("P08"),
            ],
            "links": {
                "C1.1": ["P01", "P02"],
                "C1.2": ["P02"],
                "C2.1": ["P03"],
                "C2.2": ["P04"],
                "C2.3": ["P08"],
                "C2.4": ["P08"],
                "C2.5": [],
                "C2.6": [],
            },
        }
        index = [
            crit("C1.1", "proven"),
            crit("C1.2", "unproven"),
            crit("C2.1", "replaced", ["C2.5"]),
            crit("C2.2", "skipped"),
            crit("C2.3", "broken"),
            crit("C2.4", "proven"),
            crit("C2.5", "proven"),
            crit("C2.6", "replaced", ["C2.5"]),
        ]
        return views.gene(
            plan, index, [{"day": 1, "status": "closed"}, {"day": 2, "status": "closed"}]
        )

    def test_every_commitment_is_in_exactly_one_class(self):
        g = self.gene()
        self.assertEqual(
            {c["id"]: (c["cls"], c["sub"]) for c in g["commitments"]},
            {
                "P01": ("proved", "full"),
                "P02": ("proved", "part"),
                "P03": ("spliced", None),
                "P04": ("unreplayable", None),
                "P05": ("untranscribed", "rule"),
                "P06": ("untranscribed", "later"),
                "P07": ("untranscribed", "due"),
                "P08": ("fails", None),
            },
        )
        self.assertEqual(sum(g["counts"].values()), len(g["commitments"]))
        self.assertEqual(
            (g["proved_full"], g["untranscribed"]), (1, {"rule": 1, "later": 1, "due": 1})
        )

    def test_uncovered_is_what_is_due_and_named_by_no_criterion_in_force(self):
        g = self.gene()
        self.assertEqual(g["uncovered"], ["P03", "P07"])
        self.assertEqual([c["id"] for c in g["off"]], ["C2.5"])

    def test_the_ring_holds_every_criterion_that_names_none_and_the_strands_are_counted(self):
        g = self.gene()
        self.assertEqual(
            [(q["id"], q["gone"]) for q in g.get("ring", [])], [("C2.5", False), ("C2.6", True)]
        )
        self.assertEqual(
            (g["quoting"], g["named"], g["live"]),
            ({"criteria": 6, "in_force": 5, "not_proved": 3, "came_back": 0}, 5, 4),
        )
        self.assertEqual(
            {c["id"]: c["tally"] for c in g["commitments"] if c["id"] in ("P02", "P08")},
            {"P02": {"proven": 1, "unproven": 1}, "P08": {"broken": 1, "proven": 1}},
        )

    def test_a_commitment_added_later_sits_with_its_section_and_a_quote_keeps_its_words(self):
        import spec_drift_views as views

        plan = {
            "commitments": [
                dict(commitment("N01"), section="a"),
                dict(commitment("N02"), section="b"),
                dict(commitment("N03"), section="a"),
                dict(commitment("P01"), section="b"),
            ],
            "links": {"C1.1": ["N03", "P01"]},
            "said": {"C1.1": ["third", "first"]},
            "overdue": {"N01": 3},
        }
        g = views.gene(plan, [crit("C1.1", "proven")], [{"day": 1, "status": "closed"}])
        self.assertEqual([c["id"] for c in g["commitments"]], ["P01", "N01", "N03", "N02"])
        by = {c["id"]: c for c in g["commitments"]}
        self.assertEqual([q["quote"] for q in by["N03"]["written"]], ["third"])
        self.assertEqual((by["N01"]["settled_by"], by["N02"]["settled_by"]), (3, None))


@unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global reconcile
        reconcile = load("dashboard_reconcile", "dashboard-reconcile.py")

    def test_the_gene_draws_on_demo_data_and_reconciles_with_graph_12(self):
        m = reconcile.model(demo_data.demo())
        self.assertNotIn("error", m["gene"])
        self.assertEqual(len(m["gene"]["cols"]), m["gene"]["total"])
        self.assertEqual(
            reconcile.gene_line(m),
            (
                True,
                (
                    "gene: 13 commitments (13 in its classes), 2 uncovered | "
                    "graph 12: 13 commitments, 2 should be covered by now: agree"
                ),
            ),
        )

    def test_the_gene_words_its_strands_its_gaps_and_what_the_pointer_says(self):
        m = reconcile.model(demo_data.demo())["gene"]
        self.assertEqual(
            m.get("rows", {}).get("written"),
            [
                "Criteria, as written",
                "the first transcript",
                ["16 quotes of the plan", "in 14 criteria"],
            ],
        )
        self.assertEqual(
            m["crit"]["C1.2"]["code"], "Code: replaced by C5.2; the replay no longer runs it"
        )
        self.assertEqual([f["ids"] for f in m["finds"] if "Spliced out" in f["text"]], [["P02"]])
        self.assertIn(
            ["st", "Overdue: due by Day 3, and no criterion names it."],
            next(c["tip"] for c in m["cols"] if c["id"] == "P09"),
        )

    def test_the_gene_draws_a_mark_for_every_quote_cell_and_bead_on_demo_data(self):
        data = demo_data.demo()
        out = subprocess.run(
            ["node", "-e", DRAWN, reconcile.SCRIPT],
            input=json.dumps(data),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(out.returncode, 0, out.stderr[:600])
        g, drawn = data["gene"], json.loads(out.stdout)
        marks = [drawn[k] for k in ("bands", "quotes", "cells", "beads", "ring", "inner")]
        self.assertEqual(marks, [13, 16, 15, 9, 4, 4])
        self.assertEqual(
            marks,
            [
                len(g["commitments"]),
                g["quotes"],
                g["live_quotes"],
                g["live"],
                len(g["ring"]),
                len(g["off"]),
            ],
        )
        self.assertEqual((drawn["dated"], drawn["names"], drawn["box"]), (16 + 15 + 4 + 4, 7, 4))

    def test_graph_12_counts_only_criteria_in_force(self):
        m = reconcile.model(demo_data.demo())
        due = [c["key"] for c in m["g12"]["all"] if c["is"].get("due")]
        self.assertIn("P02", due, "C1.2 named P02 and was replaced by C5.2, which names none")


if __name__ == "__main__":
    unittest.main()
