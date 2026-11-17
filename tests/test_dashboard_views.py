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
     dated: drawn.length, names: is("t-row"), box: made[0].attrs.viewBox.split(" ").length,
     free: is("free"), free_say: made.filter(e => / no criterion cites$/.test(e.textContent || "")).map(e => e.textContent) })`, ctx)));
"""


# mergeDraw() from dashboard.js on the data from stdin, on the same kind of document, in each of its views: the
# criteria's stripes, the red marks of the stops, the uncited merges' marks and the numbered badges it drew.
MRG = r"""
const fs = require("fs"), vm = require("vm"), els = {};
const node = tag => ({ tag, attrs: {}, kids: [], style: {}, dataset: {}, classList: { add() {}, remove() {} }, hidden: false,
  setAttribute(k, v) { this.attrs[k] = String(v); }, appendChild(c) { this.kids.push(c); return c; },
  append(...c) { this.kids.push(...c); }, replaceChildren(...c) { this.kids = c; }, addEventListener() {} });
const document = { createElementNS(ns, tag) { return node(tag); }, createElement: node, addEventListener() {} };
const $ = id => els[id] || (els[id] = node(id));
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")), document, $, els });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const all = n => [n, ...n.kids.filter(k => typeof k === "object").flatMap(all)];
  const count = () => {
    const made = all($("mrg-g")), clip = p => made.filter(e => e.tag === "g" && (e.attrs["clip-path"] || "").startsWith("url(#" + p));
    return { stripes: clip("mrg-cp-d").reduce((s, g) => s + g.kids.length, 0) - clip("mrg-cp-d").length,
      loose: clip("mrg-cp-loose").reduce((s, g) => s + g.kids.length - 1, 0),
      stops: made.filter(e => e.tag === "rect" && e.attrs.stroke === "var(--c-bad)" && e.attrs.rx === "1").length,
      badges: made.filter(e => e.tag === "circle" && e.attrs.r !== "2.4" && e.attrs.r !== "3.2").length,
      tiles: $("mrg-verdict").kids.length, events: $("mrg-ev").kids.length,
      nocite: made.filter(e => (e.attrs.class || "").split(" ").includes("nocite")).length,
      nc: made.filter(e => e.attrs.class === "nc").map(e => e.textContent) };
  };
  const days = [];
  mergeDraw(model(DATA).mrg, $, days);
  const out = { all: count() };
  days.forEach(f => f(DATA.merge_graph.days[0].day));
  out.day = count();
  out`, ctx)));
"""


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

    def test_the_replay_groups_of_the_recount_are_the_views(self):
        import spec_drift_views as views

        reconcile = load("dashboard_reconcile", "dashboard-reconcile.py")
        self.assertEqual(reconcile.REPLAY_GROUP, views.REPLAY_GROUP)

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
def merge_row(i, pr, kind, prod=0, branch="", day=1):
    return {
        "i": i,
        "pr": pr,
        "kind": kind,
        "branch": branch,
        "day": day,
        "title": f"PR {pr}",
        "date": "2026-11-01",
        "work": {"spec": 0, "context": 0, "prod": prod, "test": 1, "tooling": 0},
    }


def merge_crit(cid, day, prs, replaced_by=(), ticked=True):
    return {
        "id": cid,
        "day": day,
        "tag": "new",
        "prs": list(prs),
        "tests": ["T.test_a"],
        "replaced_by": list(replaced_by),
        "claim": cid,
        "ticked": ticked,
    }


def merge_cell(cid, n, state, checks=None):
    return {
        "criterion": cid,
        "day": "01",
        "n": n,
        "state": state,
        "checks": checks or [{"check": "tests", "state": state, "platform": "linux"}],
    }


class MergeGraphTest(unittest.TestCase):
    """merge_graph(): the merges against the criteria they give evidence to, as the merge graph draws them."""

    def views(self):
        return load("spec_drift_views", "spec_drift_views.py")

    def test_the_merges_no_criterion_cites_are_one_list_the_graph_and_the_gene_read(self):
        g = self.views().merge_graph(demo_data.demo())
        self.assertEqual(
            [u["pr"] for u in g["uncited"]], [m["pr"] for m in g["merges"] if m["loose"]]
        )
        self.assertEqual([(u["pr"], u["prod"]) for u in g["uncited"]], [(119, 6)])
        self.assertEqual(g["all"]["loose"], [119])

    def test_a_merge_no_criterion_cites_is_loose_only_when_it_is_code_or_other_and_changed_product_code(
        self,
    ):
        rows = [
            dict(merge_row(0, None, "origin"), day=0),
            merge_row(
                1, 1, "spec", prod=2, branch="day-02/spec-preflight"
            ),  # a root config file counted as prod
            merge_row(2, 2, "close", prod=5, branch="day-01/close-the-day"),
            merge_row(
                3, 3, "code", prod=10, branch="change/switch-log"
            ),  # a short spec's criteria cite it
            merge_row(4, 4, "code", prod=20, branch="day-01/track-a"),  # cited
            merge_row(5, 5, "code", prod=7, branch="tooling/x"),
            merge_row(6, 6, "other", prod=3, branch="dashboard/y"),
            merge_row(7, 7, "other", prod=0, branch="docs/z"),
        ]
        d = {
            "rows": rows,
            "criteria_index": [merge_crit("C1.1", 1, [4])],
            "days": [{"day": 1, "title": "One", "status": "done"}],
            "replay": {},
            "order": [1],
            "now": {},
        }
        self.views().criterion_states(d["criteria_index"], d["days"], d["replay"])
        g = self.views().merge_graph(d)
        self.assertEqual([m["pr"] for m in g["merges"] if m["loose"]], [5, 6])
        self.assertEqual([m["pr"] for m in g["merges"]], [4, 5, 6])
        self.assertEqual(g["skipped"], {"spec": 1, "close": 1, "code": 1, "other": 1})
        self.assertEqual(g["skipped_total"], 4)
        self.assertEqual(
            [(f["n"], f["kind"], f.get("pr")) for f in g["finds"]],
            [(1, "loose", 5), (2, "loose", 6)],
        )

    def fixture(self):
        # Row i and the replay's n differ on purpose: a cell's n is the replay's, an event's n is the row's.
        rows = [
            merge_row(i, 10 + i, "code", prod=p, branch=f"day-01/track-{i}")
            for i, p in ((1, 5), (2, 4), (3, 0), (4, 0), (5, 0), (6, 0))
        ]
        index = [merge_crit("C1.1", 1, [11]), merge_crit("C1.2", 1, [12])]
        replay = {
            "merges": [
                {"n": 100 + i, "pr": 10 + i, "sample": "all" if i in (1, 4) else "day"}
                for i in range(1, 7)
            ],
            "cells": [
                merge_cell("C1.1", 101, "holds"),
                merge_cell(
                    "C1.1",
                    104,
                    "code broken",
                    [
                        {"check": "a", "state": "holds", "platform": "linux"},
                        {
                            "check": "b",
                            "state": "code broken",
                            "detail": "FAILED",
                            "platform": "linux",
                        },
                    ],
                ),
                merge_cell("C1.1", 105, "not runnable"),
                merge_cell("C1.1", 106, "holds"),
                merge_cell("C1.2", 102, "break no longer applies"),
            ],
        }
        d = {
            "rows": rows,
            "criteria_index": index,
            "days": [{"day": 1, "title": "One", "status": "done"}],
            "replay": replay,
            "order": [1],
            "now": {"head": "abc1234", "last_pr": 16, "generated": "2026-11-01T10:00+00:00"},
        }
        self.views().criterion_states(index, d["days"], replay)
        return self.views().merge_graph(d)

    def test_a_merge_drawn_only_for_a_stop_is_marked_apart_from_the_cited_and_the_loose(self):
        g = self.fixture()
        # #14: the replay first saw C1.1 stop there; #16: it saw it hold again there; neither is cited nor loose
        self.assertEqual(
            [(m["pr"], m["nocite"]) for m in g["merges"]],
            [(11, []), (12, []), (14, ["stop"]), (16, ["held"])],
        )
        self.assertEqual((g["nocite"], g["all"]["nocite"]), ([14, 16], [14, 16]))
        self.assertEqual(g["by_day"]["1"]["nocite"], [14, 16])
        self.assertEqual([r["nocite"] for r in g["all"]["rows"]], [2])

    def test_a_stop_keeps_its_suspect_window_its_check_and_where_it_held_again(self):
        g = self.fixture()
        # #14 and #16 are cited by none and changed no product code: drawn because a stop starts and ends there
        self.assertEqual(
            [(m["pr"], m["loose"]) for m in g["merges"]],
            [(11, False), (12, False), (14, False), (16, False)],
        )
        keep = ("c", "pr", "n", "state", "check", "detail", "end", "lon", "lo", "wn", "sus")
        self.assertEqual(
            [{k: e[k] for k in keep} for e in g["events"]],
            [
                {
                    "c": 0,
                    "pr": 14,
                    "n": 4,
                    "state": "code broken",
                    "check": "b",
                    "detail": "FAILED",
                    "end": 16,
                    "lon": 1,
                    "lo": 11,
                    "wn": 3,
                    "sus": [12],
                },
                {
                    "c": 1,
                    "pr": 12,
                    "n": 2,
                    "state": "break no longer applies",
                    "check": "tests",
                    "detail": None,
                    "end": None,
                    "lon": None,
                    "lo": None,
                    "wn": 0,
                    "sus": [],
                },
            ],
        )
        self.assertEqual(
            [(c["id"], c["st"], c["why"], c["lp"], c["nc"]) for c in g["crit"]],
            [("C1.1", "ok", "holds", 16, 4), ("C1.2", "stale", "break no longer applies", 12, 1)],
        )
        self.assertEqual(
            [(f["n"], f["kind"], f.get("c")) for f in g["finds"]], [(1, "back", 0), (2, "fix", 1)]
        )
        self.assertEqual((g["all_at"], g["at_all"], g["win"]), ([11, 14], 1, {"min": 3, "max": 3}))
        self.assertEqual(g["flap"], {"series": 4, "stopped": 2, "twice": 0, "crit_twice": 0})

    def test_the_days_plan_md_lists_with_no_spec_are_future_with_their_hand_offs_and_commitments(
        self,
    ):
        d = {
            "rows": [],
            "criteria_index": [],
            "days": [{"day": 1, "title": "One", "status": "done"}, {"day": 2, "title": "Two"}],
            "replay": {},
            "order": [1, 2, 3, 4],
            "now": {},
            "meta": {"where": {"names": {"3": "the third", "4": "the fourth"}}},
            "hand_offs": [{"to": 3}, {"to": 3}, {"to": 4}, {"to": 2}],
            "plan": {
                "commitments": [
                    {"owner_day": 4},
                    {"owner_day": 3},
                    {"owner_day": 4},
                    {"owner_day": None},
                ]
            },
        }
        g = self.views().merge_graph(d)
        self.assertEqual(
            g["future"],
            [
                {"day": 3, "title": "the third", "ho": 2, "pc": 1},
                {"day": 4, "title": "the fourth", "ho": 1, "pc": 2},
            ],
        )

    def test_the_verdict_counts_what_the_promise_tiles_count_on_demo_data(self):
        data = demo_data.demo()
        g = data["merge_graph"]
        states = [c["state"] for c in data["criteria_index"]]
        n = lambda *s: sum(1 for x in states if x in s)
        self.assertEqual(
            [t["n"] for t in g["all"]["verdict"]],
            [
                n("proven"),
                n("unproven"),
                n("broken", "repair"),
                n("skipped", "unchecked"),
                n("open", "building"),
                n("replaced"),
            ],
        )
        self.assertEqual(sum(t["n"] for t in g["all"]["verdict"]), len(states))


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
                    "graph 12: 13 commitments, 2 should be covered by now; "
                    "1 uncited merges | merge graph: 1: agree"
                ),
            ),
        )
        # the gene's beads and the merge graph's uncited rows held to each other
        m["gene"]["uncited"] = m["gene"]["uncited"] + m["gene"]["uncited"]
        agree, line = reconcile.gene_line(m)
        self.assertEqual(
            (agree, line[-40:]), (False, "2 uncited merges | merge graph: 1: DISAGREE"[-40:])
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

    def test_the_gene_draws_a_bead_for_each_merge_no_criterion_cites_and_none_without_one(self):
        data = demo_data.demo()
        none = dict(data, merge_graph=dict(data["merge_graph"], uncited=[]))
        got = []
        for d in (data, none):
            out = subprocess.run(
                ["node", "-e", DRAWN, reconcile.SCRIPT],
                input=json.dumps(d),
                capture_output=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(out.returncode, 0, out.stderr[:600])
            drawn = json.loads(out.stdout)
            got.append((drawn["free"], drawn["free_say"]))
        self.assertEqual(got, [(1, ["1 merge no criterion cites"]), (0, [])])

    def test_the_merge_graph_draws_a_mark_for_every_criterion_stop_loose_merge_and_finding_on_demo_data(
        self,
    ):
        data = demo_data.demo()
        out = subprocess.run(
            ["node", "-e", MRG, reconcile.SCRIPT],
            input=json.dumps(data),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(out.returncode, 0, out.stderr[:600])
        g, drawn = data["merge_graph"], json.loads(out.stdout)
        loose = [m for m in g["merges"] if m["loose"]]
        self.assertGreater(len(g["events"]), 0, "the demo data has a stop to draw")
        self.assertEqual(
            drawn["all"],
            {
                "stripes": len(g["crit"]),
                "stops": len(g["events"]),
                "loose": len(loose),
                "badges": len(g["finds"]),
                "tiles": 6,
                "events": len(g["events"]),
                "nocite": 0,
                "nc": [f"{r['nocite']} uncited" for r in g["all"]["rows"] if r["nocite"]],
            },
        )
        day = g["days"][0]["day"]
        v = g["by_day"][str(day)]
        self.assertEqual(
            drawn["day"],
            {
                "stripes": sum(1 for c in g["crit"] if c["day"] == day),
                "stops": v["events"],
                "loose": len(v["loose"]),
                "badges": sum(len(x) for x in v["finds"].values()),
                "tiles": 6,
                "events": len(g["events"]),
                "nocite": len(v["nocite"]),
                "nc": [],
            },
        )

    def test_the_merge_graph_marks_every_row_no_criterion_cites_as_the_data_counts_them(self):
        g = MergeGraphTest().fixture()
        out = subprocess.run(
            ["node", "-e", MRG, reconcile.SCRIPT],
            input=json.dumps({"merge_graph": g}),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(out.returncode, 0, out.stderr[:600])
        drawn = json.loads(out.stdout)
        # one Day row, its count beside "ran of drawn"; zoomed to the Day, one dashed row per merge
        self.assertEqual(drawn["all"]["nc"], [f"{len(g['all']['nocite'])} uncited"])
        self.assertEqual(drawn["day"]["nocite"], len(g["by_day"]["1"]["nocite"]))

    def test_the_merge_graphs_verdict_reconciles_with_the_promise_tiles_on_demo_data(self):
        agree, line = reconcile.merge_line(reconcile.model(demo_data.demo()))
        self.assertTrue(agree, line)
        self.assertRegex(
            line, r"^merge graph: \d+ criteria \(.*\) \| promise tiles: \d+ \(.*\): agree$"
        )

    def test_graph_12_counts_only_criteria_in_force(self):
        m = reconcile.model(demo_data.demo())
        due = [c["key"] for c in m["g12"]["all"] if c["is"].get("due")]
        self.assertIn("P02", due, "C1.2 named P02 and was replaced by C5.2, which names none")


# ringDraw() and readingDraw() from dashboard.js on the data from stdin, on a document that keeps what is made: the
# marks each drew, counted by class, and what the reading's pointer box says of the first hand-off.
RING = r"""
const fs = require("fs"), vm = require("vm"), els = {};
const node = tag => { const n = { tag, attrs: {}, kids: [], style: {}, dataset: {}, hidden: false, textContent: "",
  classList: { add(c) { n.attrs.class = ((n.attrs.class || "") + " " + c).trim(); }, remove() {}, toggle() {}, contains() { return false; } },
  setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k]; }, appendChild(c) { this.kids.push(c); return c; },
  append(...c) { this.kids.push(...c); }, replaceChildren(...c) { this.kids = c; }, addEventListener() {}, querySelectorAll() { return []; } };
  return n; };
const document = { createElementNS(ns, tag) { return node(tag); }, createElement: node, addEventListener() {} };
const $ = id => els[id] || (els[id] = node(id));
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")), document, $, els });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const all = n => [n, ...(n.kids || []).filter(k => k && typeof k === "object").flatMap(all)];
  const is = (root, sel) => all(root).filter(e => sel.every(c => ((e.attrs && e.attrs.class) || "").split(" ").includes(c))).length;
  const M = model(DATA);
  ringDraw(M.whr, $, [], () => {});
  readingDraw(M.rdg, $, []);
  const w = $("whr-fig"), r = $("rdg-fig");
  ({ whr: { segs: is(w, ["seg"]), gates: is(w, ["gate"]), arcs: is(w, ["parc"]), pins: is(w, ["pin"]), boxes: is(w, ["box"]) },
     rdg: { cells: is(r, ["cell"]), ivs: is(r, ["iv"]), arcs: is(r, ["ho"]), open: is(r, ["ho", "open"]), num: is(r, ["ho", "open", "num"]),
            q: is(r, ["q"]), gap: is(r, ["gap"]), ahead: is(r, ["todo-day"]), opens: $("rdg-opens").kids.length },
     tip: rdgTip(M.rdg, "h", 0) })`, ctx)));
"""

# ringDraw() on the same document, then Day 2 chosen on the page's buttons and let go: the segments that say they are
# the chosen Day (aria-current) before, with Day 2 chosen and after, and how many segments say whether they are.
RING_DAY = (
    RING[: RING.index("console.log(")]
    + r"""console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const all = n => [n, ...(n.kids || []).filter(k => k && typeof k === "object").flatMap(all)];
  const onDay = [], marks = () => all($("whr-fig")).filter(e => e.attrs && "aria-current" in e.attrs);
  const chosen = () => marks().filter(e => e.attrs["aria-current"] === "true").map(e => e.attrs["data-k"]);
  ringDraw(model(DATA).whr, $, onDay, () => {});
  const out = [chosen()];
  onDay.forEach(f => f(2)); out.push(chosen(), marks().length);
  onDay.forEach(f => f(null)); out.push(chosen());
  out`, ctx)));
"""
)


def ring_data():
    """Four Days in three phases: Days 1 and 2 closed (2 with a promise not built), Day 3 next with no spec, Day 4
    the stop; between them, merges no Day owns, a stray of Day 1 inside Day 2, and four hand-offs."""

    def row(i, pr, kind, own):
        return {
            "i": i,
            "pr": pr,
            "kind": kind,
            "own_day": own,
            "day": 0,
            "title": f"PR {pr}",
            "branch": "",
            "date": "2026-01-01",
        }

    rows = [row(0, None, "origin", None), row(1, 1, "spec", 1), row(2, 2, "code", None)]
    rows += [
        row(3, 3, "code", 1),
        row(4, 4, "close", 1),
        row(5, 5, "other", None),
        row(6, 6, "spec", None),
    ]
    rows += [
        row(7, 7, "other", None),
        row(8, 8, "spec", 2),
        row(9, 9, "code", 1),
        row(10, 10, "code", 2),
    ]
    rows += [row(11, 11, "close", 2), row(12, 12, "other", None)]
    got = {3: ["C1.1"], 9: ["C1.2"], 10: ["C2.1"]}
    built, cols = 0, []
    for r in rows:
        built += len(got.get(r["i"], []))
        cols.append(
            {
                "pr": r["pr"],
                "built": built,
                "written": 4,
                "got": got.get(r["i"], []),
                "open": 0,
                "open_numbered": 0,
            }
        )
    cols[-1].update(open=2, open_numbered=1)

    def ho(hid, to, o, c, how):
        closed = rows[c]["pr"] if c is not None else None
        return {
            "id": hid,
            "source": "Day 01 Notes",
            "to": to,
            "opened": o,
            "closed": c,
            "how": how,
            "text": "a hand-off",
            "opened_pr": rows[o]["pr"],
            "closed_pr": closed,
        }

    hand_offs = [
        ho("H1.1", [2], 4, 8, "picked"),
        ho(None, [3], 4, None, None),
        ho("H2.1", [4], 11, None, None),
    ]
    hand_offs.append(ho(None, [1], 0, 4, "lapsed"))

    def crit(cid, day, tag, ticked=True):
        return {
            "id": cid,
            "day": day,
            "tag": tag,
            "ticked": ticked,
            "claim": f"{cid} never built",
            "replaced_by": [],
        }

    index = [
        crit("C1.1", 1, "new"),
        crit("C1.2", 1, "hold"),
        crit("C2.1", 2, "new"),
        crit("C2.2", 2, "new", False),
    ]

    def prs(*kinds):
        return [{"number": n, "kind": k, "title": "t"} for n, k in enumerate(kinds)]

    days = [
        {
            "day": 1,
            "status": "done",
            "phase": 0,
            "title": "One",
            "criteria": {"total": 2, "ticked": 2},
            "prs": prs("spec", "code", "close"),
        },
        {
            "day": 2,
            "status": "closed",
            "phase": 0,
            "title": "Two",
            "criteria": {"total": 2, "ticked": 1},
            "prs": prs("spec", "code", "close"),
        },
    ]
    where = {
        "rows": [
            {"phase": 0, "days": [1, 2], "stop": 2, "lifted": True, "from_day": None, "cut": False},
            {
                "phase": 1,
                "days": [3, 4],
                "stop": 4,
                "lifted": False,
                "from_day": None,
                "cut": False,
            },
            {"phase": 2, "days": [], "stop": None, "lifted": False, "from_day": 5, "cut": False},
        ],
        "names": {"3": "the third", "4": "the fourth"},
    }
    score_days = {
        "1": {"score": 91.5, "low": "proof", "parts": [{"key": "proof", "name": "Proven"}]},
        "2": {"score": 80.0, "low": "plan", "parts": [{"key": "plan", "name": "On the plan"}]},
    }
    return {
        "rows": rows,
        "days": days,
        "order": [1, 2, 3, 4],
        "criteria_index": index,
        "look_ahead": {
            "columns": cols,
            "hand_offs": hand_offs,
            "built": 3,
            "written": 4,
            "pending": None,
        },
        "now": {
            "generated": "2026-01-02T10:00+00:00",
            "head": "abcdef1",
            "last_pr": 12,
            "current_day": None,
            "next_step": "Day 3: write its day spec",
            "stop_after": 4,
            "open_prs": [],
        },
        "score": {"all": {"score": 90.4, "low": "proof", "parts": []}, "days": score_days},
        "meta": {
            "phases": ["Ground", "Build", "Chain"],
            "stops": [2, 4],
            "where": where,
            "repo_url": None,
        },
    }


class WhereRingTest(unittest.TestCase):
    """where_ring(): the plan as a ring, one segment per Day, as the ring draws it."""

    def ring(self, data=None):
        return load("spec_drift_views", "spec_drift_views.py").where_ring(data or ring_data())

    def test_the_ring_counts_the_days_closed_and_left_to_the_stop(self):
        w = self.ring()
        self.assertEqual((w["closed"], w["numbered"], w["left"], w["stop"]), (2, 4, [3, 4], 4))
        self.assertEqual((w["built"], w["written"]), (3, 4))
        slots = [(s["k"], s["state"]) for s in w["slots"]]
        expected = [
            ("d1", "done"),
            ("d2", "open"),
            ("d3", "next"),
            ("d4", "planned"),
            ("stub2", "stub"),
        ]
        self.assertEqual(slots, expected)
        self.assertEqual([(g["k"], g["passed"]) for g in w["gates"]], [("s2", True), ("s4", False)])
        self.assertEqual(w["now"], {"between": [2, 3], "day": None, "slot": 1})
        self.assertEqual(w["boxes"], [{"day": 2, "ticked": 1, "total": 2, "ids": ["C2.2"]}])

    def test_a_day_with_a_spec_that_has_not_closed_is_not_counted_closed(self):
        data = ring_data()
        data["days"][1]["status"] = "in progress"
        self.assertEqual(self.ring(data)["closed"], 1)

    def test_a_day_says_its_promises_its_pull_requests_and_its_score(self):
        w = self.ring()
        d1 = w["slots"][0]
        self.assertEqual((d1["ticked"], d1["total"], d1["score"], d1["low"]), (2, 2, 92, "proven"))
        self.assertEqual(d1["prs"], {"n": 3, "code": 1, "spec": 1, "close": 1})
        self.assertEqual(
            (w["score"], w["lo"], w["hi"]), (90, {"day": 2, "n": 80}, {"day": 1, "n": 92})
        )
        phases = [(p["k"], p["closed"], p["total"]) for p in w["phases"]]
        self.assertEqual(phases, [("p0", 2, 2), ("p1", 0, 2), ("p2", 0, 0)])

    def test_no_phase_rows_draw_no_ring(self):
        data = ring_data()
        data["meta"]["where"] = {"rows": [], "names": {}}
        self.assertIn("empty", self.ring(data))


class ReadingTest(unittest.TestCase):
    """reading(): every merge in order as a strand, the Days as blocks, the merges between them as stretches, and the
    hand-offs as arcs, as graph 1's reading draws it."""

    def reading(self):
        return load("spec_drift_views", "spec_drift_views.py").reading(ring_data())

    def test_the_merges_no_day_owns_are_stretches_between_the_days(self):
        r = self.reading()
        strand = [x.get("iv", x.get("m")) for x in r["strand"]]
        self.assertEqual(strand, [[0], 1, [2], 3, 4, [5, 6, 7], 8, 9, 10, 11, [12]])
        self.assertEqual((r["stretches"], r["between"], r["merges"]), (4, 6, 13))
        self.assertEqual(r["between_kinds"], {"origin": 1, "other": 4, "spec": 1})
        self.assertEqual([m["k"] for m in r["m"][:3]], ["origin", "spec", "other"])
        whose = [r["m"][i]["w"] for i in (0, 1, 2, 5)]
        self.assertEqual(
            whose,
            [
                "before Day 1",
                "Day 1",
                "outside any Day, merged while Day 1 was open",
                "outside any Day, merged after Day 1 closed",
            ],
        )
        self.assertEqual(r["m"][9]["g"], [["C1.2", "hold", 1]])

    def test_a_days_main_span_and_its_strays(self):
        days = {d["day"]: d for d in self.reading()["days"]}
        self.assertEqual(
            (days[1]["main"], days[1]["strays"], days[1]["frags"]), ([1, 4], [[9, 9]], 3)
        )
        self.assertEqual(
            (days[2]["main"], days[2]["strays"], days[2]["frags"]), ([10, 11], [[8, 8]], 2)
        )
        self.assertEqual((days[2]["ticked"], days[2]["total"]), (1, 2))

    def test_hand_offs_open_and_closed_the_numbered_open_ones_and_the_days_ahead(self):
        r = self.reading()
        arcs = [(h["o"], h["c"], h["how"], h["w"]) for h in r["h"]]
        self.assertEqual(
            arcs,
            [
                (4, 8, "picked", None),
                (4, None, None, 3),
                (11, None, None, 4),
                (0, 4, "lapsed", None),
            ],
        )
        self.assertEqual((r["open"], r["numbered"]), (2, 1))
        self.assertEqual(r["opens"], [{"h": 2, "id": "H2.1", "to": 4, "pr": 11, "x": "a hand-off"}])
        ahead = [(a["day"], a["n"], a["w"]) for a in r["ahead"]]
        self.assertEqual(ahead, [(3, "the third", ["unnumbered"]), (4, "the fourth", ["H2.1"])])
        self.assertEqual(r["gap"], [{"id": "C2.2", "d": 2, "at": 11, "x": "C2.2 never built"}])
        self.assertEqual(r["lifted"], [{"day": 2, "at": 11, "between": 1}])
        self.assertEqual(r["stop"], {"day": 4, "name": "the fourth"})


@unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
class RingAndReadingPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global reconcile
        reconcile = load("dashboard_reconcile", "dashboard-reconcile.py")

    def drawn(self, data, script=RING):
        out = subprocess.run(
            ["node", "-e", script, reconcile.SCRIPT],
            input=json.dumps(data),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(out.returncode, 0, out.stderr[:600])
        return json.loads(out.stdout)

    def test_the_ring_says_which_day_is_chosen_on_that_days_segment(self):
        # a Day chosen on the page's buttons is dimmed around on the ring, which a screen reader cannot see: its
        # segment says it is the current one, and no other does
        data = demo_data.demo()
        days = sum(1 for s in data["where_ring"]["slots"] if s.get("day") is not None)
        self.assertEqual(self.drawn(data, RING_DAY), [[], ["d2"], days, []])

    def test_the_ring_and_the_reading_draw_a_mark_for_each_day_gate_merge_stretch_and_hand_off(
        self,
    ):
        data = demo_data.demo()
        w, r, drawn = data["where_ring"], data["reading"], self.drawn(data)
        ring = {
            "segs": len(w["slots"]),
            # a stop passed is a gate standing open, in two halves
            "gates": sum(2 if g["passed"] else 1 for g in w["gates"]),
            "arcs": len(w["phases"]),
            "pins": 1,
            "boxes": len(w["boxes"]),
        }
        # one mark at a time, so a failure names the mark in a short line
        for k, want in ring.items():
            self.assertEqual((k, drawn["whr"][k]), (k, want))
        self.assertEqual(sorted(drawn["whr"]), sorted(ring))
        self.assertGreater(drawn["whr"]["gates"], 0)
        cells = sum(1 for x in r["strand"] if "m" in x)
        q = sum(len(m["g"]) for m in r["m"]) + len(r["gap"])
        marks = {
            "cells": cells,
            "ivs": r["stretches"],
            "arcs": len(r["h"]),
            "open": r["open"],
            "num": r["numbered"],
            "q": q,
            "gap": len(r["gap"]),
            "ahead": len(r["ahead"]),
            "opens": len(r["opens"]),
        }
        for k, want in marks.items():
            self.assertEqual((k, drawn["rdg"][k]), (k, want))
        self.assertEqual(sorted(drawn["rdg"]), sorted(marks))
        self.assertGreater(drawn["rdg"]["arcs"], 0)

    def test_every_closed_hand_off_is_drawn_always_and_a_pointer_or_a_day_only_lights_some(self):
        # the mockup's form: no rule hides a closed arc until it is lit; pointing dims the others, a Day dims those
        # not of it, and the hint under the picture says nothing of drawing them only then
        page = os.path.join(ROOT, "docs", "dashboard")
        with open(os.path.join(page, "dashboard.css"), encoding="utf-8") as f:
            css = f.read()
        with open(os.path.join(page, "index.html"), encoding="utf-8") as f:
            html = f.read()
        hides = re.findall(r"#rdg[^{}]*\.ho[^{}]*\{[^}]*display:\s*none", css)
        self.assertEqual(hides, [])
        self.assertIn("#rdg .fig.foc .ho:not(.lit){opacity:.12}", css)
        self.assertNotIn("drawn only then", html)

    def test_the_ring_and_the_reading_reconcile_with_the_days_counted_and_the_hand_off_ledger(self):
        data = demo_data.demo()
        m = reconcile.model(data)
        agree, line = reconcile.ring_line(m, data)
        self.assertTrue(agree, line)
        self.assertRegex(
            line,
            r"^where we are: ring \d+ of \d+ Days closed, \d+ of \d+ promises built \| "
            r"counted from the data: \d+ of \d+ Days, look-ahead \d+ of \d+: agree$",
        )
        agree, line = reconcile.reading_line(m)
        self.assertTrue(agree, line)
        self.assertRegex(
            line,
            r"^reading: \d+ arcs, \d+ open, \d+ numbered \| "
            r"look-ahead \d+ hand-offs, \d+ open, \d+ numbered: agree$",
        )

    def test_a_hand_off_quoting_a_script_tag_stays_text_in_the_page_and_in_the_pointer_box(self):
        data = ring_data()
        text = "<!-- PROJECT: x --> a second `<script>` </script>"
        data["look_ahead"]["hand_offs"][0]["text"] = text
        views = load("spec_drift_views", "spec_drift_views.py")
        data["where_ring"], data["reading"] = views.where_ring(data), views.reading(data)
        page = load("spec_drift", "spec-drift.py").build(json.dumps(data))
        lines = re.findall(r"^window\.SPEC_DRIFT = (.*);$", page, re.MULTILINE)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].count("<"), 0)
        self.assertEqual(json.loads(lines[0])["reading"]["h"][0]["x"], text)
        self.assertEqual(page.count("window.SPEC_DRIFT = "), 1)
        self.assertEqual(self.drawn(data)["tip"]["q"], text)


def gel_data():
    """Three Days of three yardsticks: cost with the kit's figure, parks with only Day 2 in the notebook and a driver
    step on Day 3 (and one on Day 14, a Day of the driven project with no lane), refusals, which are not judged."""

    def row(key, unit, decimals, baseline, values, average, over="days"):
        vals = [{"day": i + 1, "value": v, "text": f"{key} {i + 1}"} for i, v in enumerate(values)]
        return {
            "key": key,
            "name": f"The {key}",
            "unit": unit,
            "decimals": decimals,
            "baseline": baseline,
            "source": "notebook",
            "values": vals,
            "average": average,
            "average_over": over,
        }

    rows = [
        row("cost", "$", 2, 1.5, [1.2, 1.8, 1.4], [1.2, 1.5, 1.47], "pull requests"),
        row("parks", "", 0, None, [None, 2, None], [None, 2.0, 2.0]),
        row("refusals", "", 0, None, [3, 5, 6], [3.0, 4.0, 4.67]),
    ]

    def step(day, parks):
        return {"step": f"Day {day}", "day": day, "parks": [{"by": "fault", "line": "x"}] * parks}

    return {
        "yardsticks": {"days": [1, 2, 3], "problems": [], "rows": rows},
        "driver_runs": {"steps": [step(3, 1), step(14, 2)]},
        "now": {"head": "abcdef1", "last_pr": 9},
    }


class GelTest(unittest.TestCase):
    """gel(): graph 2 as one small gel per yardstick, a lane per Day and a ladder lane."""

    def gel(self, data=None):
        return load("spec_drift_views", "spec_drift_views.py").gel(data or gel_data())

    def test_one_panel_per_yardstick_with_a_lane_per_day_and_the_ladder(self):
        g = self.gel()
        self.assertEqual([p["key"] for p in g["panels"]], ["cost", "parks", "refusals"])
        self.assertEqual(g["days"], [1, 2, 3])
        for p in g["panels"]:
            self.assertEqual([x["day"] for x in p["lanes"]], [1, 2, 3], p["key"])
        cost, parks, _ = g["panels"]
        self.assertEqual((cost["kit"], cost["average"]), (1.5, 1.47))
        self.assertEqual((parks["kit"], parks["average"]), (None, 2.0))
        self.assertEqual([x["value"] for x in cost["lanes"]], [1.2, 1.8, 1.4])
        self.assertEqual(
            (cost["last"], cost["above_kit"], cost["counted"]), ({"day": 3, "value": 1.4}, 1, 3)
        )

    def test_which_way_is_better_is_the_maintainers_judgement_the_old_list_unchanged(self):
        views = load("spec_drift_views", "spec_drift_views.py")
        # dashboard.js's LOWER_BETTER up to #236
        old = ["cost", "replies", "escapes", "parks", "gates", "reread"]
        self.assertEqual(list(views.LOWER_BETTER), old)
        self.assertEqual([p["lower_better"] for p in self.gel()["panels"]], [True, True, False])
        demo = demo_data.demo()
        self.assertEqual(
            [(p["key"], p["lower_better"]) for p in views.gel(demo)["panels"]],
            [(r["key"], r["key"] in old) for r in demo["yardsticks"]["rows"]],
        )

    def test_the_parks_lane_is_filled_from_the_run_log_where_the_notebook_has_no_figure(self):
        parks = self.gel()["panels"][1]
        self.assertEqual([x["value"] for x in parks["lanes"]], [None, 2, 1])
        self.assertIn("run log", parks["lanes"][2]["text"])
        self.assertEqual(parks["lanes"][1]["text"], "parks 2")
        self.assertEqual((parks["last"], parks["empty"]), ({"day": 3, "value": 1}, 1))

    def test_the_headline_judges_the_lower_better_yardsticks_against_their_average(self):
        g = self.gel()
        self.assertEqual([p["verdict"] for p in g["panels"]], ["better", "better", "flat"])
        self.assertEqual((g["named"], g["judged"], g["below"]), (3, 2, ["cost", "parks"]))
        kit = {"key": "cost", "above": 1, "of": 3, "kit": 1.5, "last": {"day": 3, "value": 1.4}}
        self.assertEqual(g["kit"], [kit])

    def test_no_yardsticks_draw_no_gel(self):
        self.assertIn("empty", self.gel({"yardsticks": {"days": [], "rows": []}}))


def prt_data():
    """Six abilities and nine criteria: one replaced, one written and not built, one naming no ability, one that
    grows two; and the driver's five steps: two merged, a crash that parked on a fault, the park when every Day was
    done, and one still open."""
    names = {
        "rehearse": "Shows",
        "stop": "Stops",
        "loop": "Loops",
        "park": "Parks",
        "recover": "Recovers",
        "see": "Sees",
    }
    abilities = [
        {"key": k, "name": v, "role": "rail" if k == "see" else "rung"} for k, v in names.items()
    ]

    def crit(cid, abilities, state, **more):
        c = {
            "id": cid,
            "day": int(cid[1]),
            "tag": "new",
            "plain": f"{cid} holds.",
            "abilities": abilities,
            "state": state,
            "back": False,
            "replaced_by": [],
            "prs": [],
            "seen": {"last": None, "stops": []},
            "ticked": True,
        }
        return {**c, **more}

    index = [
        crit("C1.10", ["loop"], "proven"),
        crit("C1.1", ["loop"], "proven", back=True),
        crit("C1.2", ["see", "loop"], "unproven"),
        crit("C1.3", ["park"], "proven"),
        crit("C2.1", ["loop"], "replaced", replaced_by=["C2.3"]),
        crit("C2.2", ["park"], "open", ticked=False),
        crit("C2.3", ["loop"], "skipped"),
        crit("C2.4", [], "repair"),
        crit("C2.5", ["see"], "proven"),
    ]
    stories = [
        {"number": n, "day": day, "ability": a}
        for n, day, a in ((1, 1, "loop"), (2, 2, "loop"), (3, None, "loop"), (4, 1, "park"))
    ]

    def step(pr, ended, crashes=0, parks=()):
        return {
            "step": f"Step {pr}",
            "day": 13 if pr else None,
            "pr": pr,
            "ended": ended,
            "crashes": crashes,
            "sessions": [{}] * (1 + crashes),
            "parks": [{"by": b, "line": f"park: {b}"} for b in parks],
        }

    steps = [
        step(90, "merged"),
        step(91, "merged"),
        step(96, "parked", 1, ["fault"]),
        step(None, "parked", 0, ["maintainer"]),
        step(101, "open"),
    ]
    return {
        "criteria_index": index,
        "user_stories": {"abilities": abilities, "stories": stories},
        "driver_runs": {"steps": steps},
        "score": {"abilities": {"loop": {"score": 81.6}}},
        "now": {"head": "abc", "last_pr": 9},
    }


class ProteinTest(unittest.TestCase):
    """protein(): graphs 3 to 5 as one folded chain per ability, one cell per criterion in the order built."""

    def prt(self, data=None):
        return load("spec_drift_views", "spec_drift_views.py").protein(data or prt_data())

    def test_one_chain_per_ability_and_one_for_the_criteria_naming_none(self):
        p = self.prt()
        keys = ["rehearse", "stop", "loop", "park", "recover", "see", None]
        self.assertEqual([c["key"] for c in p["chains"]], keys)
        chains = {c["key"]: c for c in p["chains"]}
        loop = chains["loop"]
        self.assertEqual([x["id"] for x in loop["cells"]], ["C1.1", "C1.10", "C2.1", "C2.3"])
        self.assertEqual([x["id"] for x in chains[None]["cells"]], ["C2.4"])
        # drawn once, under the first ability it names, though "loop" is listed before "see",
        # and says it grows the other
        self.assertEqual([x["id"] for x in chains["see"]["cells"]], ["C1.2", "C2.5"])
        self.assertEqual(chains["see"]["cells"][0]["also"], ["loop"])
        self.assertEqual(loop["cells"][0]["back"], True)
        self.assertEqual((loop["proven"], loop["rechecked"], loop["score"]), (2, 3, 82))
        self.assertEqual((loop["prs"], loop["between"]), ([[1, [1]], [2, [2]]], [3]))

    def test_the_headline_counts_only_the_criteria_the_replay_rechecks(self):
        p = self.prt()
        counts = {"proven": 4, "unproven": 1, "skipped": 1, "repair": 1, "open": 1, "replaced": 1}
        self.assertEqual(p["counts"], counts)
        self.assertEqual((p["proven"], p["rechecked"], p["in_force"], p["written"]), (4, 7, 8, 9))
        self.assertEqual(p["outside"], ["C2.2"])
        self.assertEqual((p["weakest"]["key"], p["strongest"]["key"]), ("see", "park"))

    def test_in_real_runs_is_the_maintainers_mapping_of_the_run_log(self):
        p = self.prt()
        runs = {c["key"]: c["run"] for c in p["chains"]}
        want = {
            "rehearse": ("uncounted", None, 5),
            "stop": ("stop", 0, 5),
            "loop": ("loop", 2, 5),
            "park": ("park", 2, 5),
            "recover": ("recover", 1, 5),
            "see": ("rail", None, 5),
        }
        self.assertEqual(sorted(k for k, r in runs.items() if r), sorted(want))
        for k, w in want.items():  # one ability at a time, so a failure names a short pair
            self.assertEqual((runs[k]["how"], runs[k]["n"], runs[k]["of"]), w, k)
        self.assertEqual(runs[None], None)
        # the open step (#101) is in neither; the crash that parked (#96) is in both recover and park
        self.assertEqual(runs["loop"]["prs"], [90, 91])
        parks = [(x["pr"], x["by"]) for x in runs["park"]["parks"]]
        self.assertEqual(parks, [(96, "fault"), (None, "maintainer")])
        self.assertEqual(runs["recover"]["prs"], [96])
        self.assertEqual(runs["loop"]["open"], [101])
        self.assertEqual(p["used"], {"n": 3, "of": 5, "steps": 5})

    def test_each_days_promises_are_counted_in_all_and_in_each_chain(self):
        p = self.prt()
        self.assertEqual(p["per_day"], [[1, 4], [2, 5]])
        per_chain = {c["key"]: c["per_day"] for c in p["chains"] if c["per_day"]}
        self.assertEqual(
            per_chain,
            {
                "loop": [[1, 2], [2, 2]],
                "park": [[1, 1], [2, 1]],
                "see": [[1, 1], [2, 1]],
                None: [[2, 1]],
            },
        )

    def test_no_criteria_draw_no_chains(self):
        data = {"criteria_index": [], "user_stories": {"abilities": [], "stories": []}}
        self.assertIn("empty", self.prt(data))


def prf_data(absent=(), commit="abc"):
    """Two closed Days of defects at most of the gates: two Days' auditors (one Notes line in the older form), a track
    and the session in the work, a later Day's review, the evidence replay; Day 2 had a pull request merge after the
    count, so its catches are left out of the cost per catch (graph 7's rule). D2.1 and D2.4 came back; D2.1 escaped."""

    def defect(i, found, cause, made, same=None):
        return {
            "id": i,
            "found": found,
            "cause": cause,
            "made": made,
            "same_as": same,
            "problem": None,
        }

    def gate(name, found, runs, cost):
        return {"gate": name, "found": found, "runs": runs, "cost": cost}

    def pr(n, day, merged):
        return {"number": n, "day": day, "opened": f"{merged[:10]}T08:00:00Z", "merged": merged}

    return {
        "days": [
            {
                "day": 1,
                "status": "done",
                "defects": [
                    defect("D1.1", "auditor", "spec", "Day 01"),
                    defect("D1.2", "The auditor (plan-auditor)", "process", "Day 01"),
                    defect("D1.3", "Track A", "implementation", "Day 01"),
                    defect("D1.4", "self", "spec", "none"),
                ],
            },
            {
                "day": 2,
                "status": "done",
                "relabel": {"stage": [3, 4], "cause": [4, 4], "made": [2, 4]},
                "defects": [
                    defect("D2.1", "auditor", "spec", "Day 01", "D1.1"),
                    defect("D2.2", "seen red", "implementation", "Day 02"),
                    defect("D2.3", "Day 1 review", "process", None),
                    defect("D2.4", "evidence replay", "environment", "Day 02", "D1.3"),
                ],
            },
            {"day": 3, "status": "active", "defects": []},
        ],
        "gate_report": {
            "gates": [
                gate("auditors", "auditor", 4, 3.0),
                gate("seen red", "seen red", 2, 1.0),
                gate("break on purpose", "break on purpose", 0, 0.0),
                gate("evidence replay", "evidence replay", 1, 0.5),
                gate("hooks", None, 3, 0.3),
            ]
        },
        "counted": {"at": "2026-01-02T12:00:00+00:00"},
        "clock": {
            "sessions": [],
            "prs": [pr(1, 1, "2026-01-01T10:00:00Z"), pr(2, 2, "2026-01-03T10:00:00Z")],
        },
        "rows": [{"pr": None}, {"pr": 1, "day": 1}, {"pr": 2, "day": 2}],
        "refusals": [
            {"date": "2026-01-01", "guard": "read-guard", "refused": 3},
            {"date": "2026-01-01", "guard": "step-guard", "refused": 1},
            {"date": "2026-01-02", "guard": "read-guard", "refused": 2},
        ],
        "verification": [
            {"number": 1, "failed_in": ["PR checks", "Tests"]},
            {"number": 2, "failed_in": ["PR checks", "PR checks"]},
            {"number": 3, "failed_in": []},
        ],
        "defect_recurrence": {
            "recurrences": [{"id": "D2.1", "same_as": "D1.1"}, {"id": "D2.4", "same_as": "D1.3"}]
        },
        "data": {"branch": "dashboard-data", "commit": commit, "at": None, "absent": list(absent)},
        "now": {"head": "abcdef1234", "last_pr": 2, "generated": "2026-01-04T09:00+00:00"},
    }


# model() and prfDraw() from dashboard.js on the data from stdin, on a document that keeps what is made: graph 7's
# counts as its model has them, the marks prfDraw drew by class, its words, and the banner.
PRF = r"""
const fs = require("fs"), vm = require("vm"), els = {};
const node = tag => { const n = { tag, attrs: {}, kids: [], style: {}, dataset: {}, hidden: false, textContent: "",
  classList: { add(c) { n.attrs.class = ((n.attrs.class || "") + " " + c).trim(); }, remove() {}, toggle() {}, contains() { return false; } },
  setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k]; }, appendChild(c) { this.kids.push(c); return c; },
  append(...c) { this.kids.push(...c); }, replaceChildren(...c) { this.kids = c; }, addEventListener() {}, querySelectorAll() { return []; } };
  Object.defineProperty(n, "className", { set(v) { n.attrs.class = v; }, get() { return n.attrs.class || ""; } });
  return n; };
const document = { createElementNS(ns, tag) { return node(tag); }, createElement: node, addEventListener() {} };
const $ = id => els[id] || (els[id] = node(id));
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")), document, $ });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const all = n => [n, ...(n.kids || []).filter(k => k && typeof k === "object").flatMap(all)];
  const is = (root, sel) => all(root).filter(e => sel.every(c => ((e.attrs && e.attrs.class) || "").split(" ").includes(c))).length;
  const words = n => typeof n === "string" ? n : [n.textContent, ...(n.kids || []).map(words)].join(" ");
  const M = model(DATA), days = [], g7 = M.g7;
  const drew = typeof prfDraw === "function" && M.prf && !M.prf.error ? (prfDraw(M.prf, $, days), true) : false;
  const f = $("prf-fig");
  ({ g7: { subs: g7.gates.map(x => x.sub), gates: g7.gates.map(x => [x.key, x.n, x.per == null ? null : x.per]),
           phases: g7.pipe.phases.map(p => p.n),
           caught: g7.pipe.stages.flatMap(s => s.gates.filter(x => x.caught).map(x => x.caught)) },
     prf: { drew, dots: is(f, ["b", "d"]), grps: is(f, ["b", "grp"]), lays: is(f, ["b", "lay"]), hooks: is(f, ["b", "hk"]),
            marks: is(f, ["b", "mk"]), drops: is(f, ["t-drop"]),
            words: [f, $("prf-figs"), $("prf-finds"), $("prf-bends"), $("prf-ci"), $("prf-key")].map(words).join(" ").replace(/\\s+/g, " ") },
     missing: M.head.missing, onDay: days.length })`, ctx)));
"""


def prf_node(data):
    reconcile = load("dashboard_reconcile", "dashboard-reconcile.py")
    out = subprocess.run(
        ["node", "-e", PRF, reconcile.SCRIPT],
        input=json.dumps(data),
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if out.returncode:
        raise AssertionError(out.stderr[:800])
    return json.loads(out.stdout)


def with_prf(data):
    data = dict(data)
    data["proofreading"] = load("spec_drift_views", "spec_drift_views.py").proofreading(data)
    return data


# What graph 7's own rules gave in dashboard.js up to #237 (GATES, gateOf, PHASES and the cost per catch over the Days
# in the count), run in node on each data set before they moved to spec_drift_views.proofreading: the gates in GATES'
# order, the four phases, and the cost per catch of the gates that had one.
GATE_KEYS = [
    "auditor",
    "spec-change PR",
    "seen red",
    "break on purpose",
    "review",
    "work",
    "close",
    "rehearsal",
    "evidence replay",
    "dashboard",
    "Day review",
]
OLD_DEMO = {
    "caught": [1] * 11,
    "layers": [2, 4, 2, 3],
    "per": {
        "auditor": "$2.40",
        "seen red": "$3.60",
        "break on purpose": "$5.60",
        "evidence replay": "$2.00",
    },
}
OLD_FIXTURE = {
    "caught": [3, 0, 1, 0, 0, 2, 0, 0, 1, 0, 1],
    "layers": [3, 3, 0, 2],
    "per": {"auditor": "$1.50"},
}


class ProofreadingTest(unittest.TestCase):
    """proofreading(): every defect in one stream through four layers of checking, counted by graph 7's rules."""

    def prf(self, data):
        return load("spec_drift_views", "spec_drift_views.py").proofreading(data)

    def counts(self, p):
        caught = [g["caught"] for g in p["gates"]]
        per = {g["key"]: f"${g['per']:.2f}" for g in p["gates"] if g["per"] is not None}
        return {"caught": caught, "layers": [x["caught"] for x in p["layers"]], "per": per}

    def test_the_counts_are_graph_7s_on_the_demo_data_and_on_a_day_merged_after_the_count(self):
        p = self.prf(demo_data.demo())
        self.assertEqual([g["key"] for g in p["gates"]], GATE_KEYS)
        f = self.prf(prf_data())
        # field by field, gate by gate: a short report break.py can record (unittest shortens long dicts)
        for got, old in ((self.counts(p), OLD_DEMO), (self.counts(f), OLD_FIXTURE)):
            self.assertEqual(got["caught"], old["caught"])
            self.assertEqual(got["layers"], old["layers"])
            for k in sorted(set(got["per"]) | set(old["per"])):
                self.assertEqual(got["per"].get(k), old["per"].get(k), f"cost per catch at {k}")
        self.assertEqual(f["late"], [2])
        self.assertEqual((f["total"], [x["reached"] for x in f["layers"]]), (8, [8, 5, 2, 2]))

    def test_the_gate_a_found_value_names_is_graph_7s_rule(self):
        gate_of = load("spec_drift_views", "spec_drift_views.py").gate_of
        cases = {
            "day 3 review": "Day review",
            "Day 12 review": "Day review",
            "the auditor (plan)": "auditor",
            "The spec-change PR": "spec-change PR",
            "Track B": "work",
            "self": "work",
            "work": "work",
            "a reviewer nobody named": "work",
            None: "work",
        }
        for k, want in cases.items():
            self.assertEqual(gate_of(k), want, f"found: {k}")

    def test_came_back_and_after_the_merge_are_two_sets_and_what_they_share_is_counted(self):
        m = self.prf(prf_data())["marks"]
        self.assertEqual((m["back"]["n"], m["after_merge"], m["shared"]), (2, 2, 1))
        self.assertEqual((m["escaped"]["n"], m["both"]), (1, 1))
        self.assertEqual(m["back"]["layers"], [1, 0, 0, 1])

    def test_with_the_data_branch_or_its_gates_json_missing_there_is_no_stream(self):
        for data in (prf_data(commit=None), prf_data(absent=["gates.json"])):
            p = self.prf(data)
            self.assertTrue("empty" in p, "the stream would be drawn")
            self.assertEqual([g["cost"] for g in p["gates"]], [None] * 11)
            self.assertIsNone(p["hooks"])
        self.assertNotIn("empty", self.prf(prf_data(absent=["sessions.json"])))

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_graph_7_reads_the_same_counts_as_the_stream(self):
        for data, old in ((demo_data.demo(), OLD_DEMO), (with_prf(prf_data()), OLD_FIXTURE)):
            got = prf_node(data)["g7"]
            self.assertEqual([int(s.split(" ")[0]) for s in got["subs"]], old["caught"])
            self.assertEqual(got["phases"], old["layers"])
            per = [re.search(r"about (\$[\d.]+) a catch", c) for c in got["caught"]]
            self.assertEqual(sorted(x.group(1) for x in per if x), sorted(old["per"].values()))
            p = data["proofreading"]
            self.assertEqual(got["gates"], [[g["key"], g["caught"], g["per"]] for g in p["gates"]])
        with open(os.path.join(ROOT, "docs", "dashboard", "dashboard.js"), encoding="utf-8") as f:
            script = f.read()
        self.assertEqual(re.findall(r"^const (GATES|gateOf|PHASES)\b", script, re.MULTILINE), [])

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_the_stream_draws_a_dot_per_defect_a_group_per_gate_and_a_row_per_guard(self):
        data = demo_data.demo()
        out, p = prf_node(data), data["proofreading"]
        guards = {r["guard"] for r in data["refusals"] if r["refused"]}
        want = {"dots": p["total"], "grps": 11, "lays": 4, "hooks": len(guards), "marks": 2}
        self.assertEqual({k: out["prf"][k] for k in want}, want)
        self.assertEqual(p["total"], 11)
        self.assertEqual(out["onDay"], 1)  # it hooks into the page's Day buttons

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_the_stream_labels_came_back_and_after_the_merge_apart_and_says_what_they_share(self):
        words = prf_node(with_prf(prf_data()))["prf"]["words"]
        self.assertIn("2 came back.", words)
        self.assertIn("They are not the 2 caught after the merge: the two sets share 1.", words)
        self.assertIn("Days merged by the count", words)

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_without_the_data_branch_the_stream_draws_nothing_and_the_banner_says_so(self):
        for data in (prf_data(commit=None), prf_data(absent=["gates.json"])):
            out = prf_node(with_prf(data))
            self.assertEqual(
                (out["prf"]["dots"], out["prf"]["grps"], out["prf"]["drops"]), (0, 0, 0)
            )
            self.assertIn("The proofreading stream is not drawn.", out["missing"])
            # graph 7 still puts each defect at its gate, with no gate's cost
            self.assertEqual(out["g7"]["phases"], OLD_FIXTURE["layers"])
            self.assertEqual([g[2] for g in out["g7"]["gates"]], [None] * 11)
            self.assertFalse(any("run" in s for s in out["g7"]["subs"]), out["g7"]["subs"])

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_the_stream_reconciles_with_graph_7_on_demo_data(self):
        reconcile = load("dashboard_reconcile", "dashboard-reconcile.py")
        agree, line = reconcile.prf_line(reconcile.model(demo_data.demo()))
        self.assertTrue(agree, line)
        self.assertRegex(
            line, r"^proofreading: 11 defects, layers 2/4/2/3, .* \| graph 7: .*: agree$"
        )


def budget_data(absent=(), commit="abc"):
    """Five token rows over three dates. Priced again with token-usage.py's list prices
    (claude-opus-5-5: 4, 5, 8, 0.20, 20 a million): A is 0.41% off its cost and is split; B, an
    auditor's cache write at the five-minute price, is 2% off and is not; C, the implementer's, is
    exact; D's model has no price; E has no cost_past_150k, so its date's rail is unknown."""

    def tok(date, day, agent, model, cost, past=None, **n):
        row = {"date": date, "day": day, "agent": agent, "model": model, "cost": cost, "replies": 3}
        row.update({k: n.get(k, 0) for k in ("input", "cache_write", "cache_read", "output")})
        if past is not None:
            row["cost_past_150k"] = past
        return row

    opus = "claude-opus-5-5"
    return {
        "tokens": [
            tok(
                "2026-01-01",
                1,
                "main",
                opus,
                1.21,
                0.5,
                input=1000,
                cache_write=100000,
                cache_read=1000000,
                output=10000,
            ),
            tok("2026-01-01", None, "spec-auditor", opus, 1.02, 0.0, cache_write=200000),
            tok(
                "2026-01-02",
                2,
                "implementer",
                opus,
                4.0,
                0.0,
                cache_write=400000,
                cache_read=5000000,
                output=50000,
            ),
            tok("2026-01-02", None, "main", "a-model-with-no-price", 3.0, 1.0, output=10),
            tok("2026-01-03", 2, "defect-rater", opus, 2.0, output=100000),
        ],
        "refusals": [{"date": "2026-01-01", "guard": "read-guard", "refused": 2}],
        "days": [
            {"day": 1, "status": "done", "worked": ["2026-01-01", "2026-01-01"]},
            {"day": 2, "status": "active", "worked": ["2026-01-02", "2026-01-03"]},
        ],
        "data": {"branch": "dashboard-data", "commit": commit, "at": None, "absent": list(absent)},
        "now": {"head": "abcdef1234", "last_pr": 2, "generated": "2026-01-04T09:00+00:00"},
    }


class BudgetTest(unittest.TestCase):
    """budget(): graph 8's dollars as beads of $2, split by kind and by who, by date and by Day."""

    def budget(self, data):
        return load("spec_drift_views", "spec_drift_views.py").budget(data)

    def test_a_row_more_than_1pct_off_is_not_split_and_a_split_rows_parts_sum_to_its_cost(self):
        b = self.budget(budget_data())
        self.assertEqual([round(x, 2) for x in b["kinds"]], [1.2, 2.81, 3.2, 4.02])
        self.assertEqual((b["split"]["rows"], b["unsplit"]["rows"]), (3, 2))
        self.assertEqual(round(sum(b["kinds"]), 2), round(b["total"], 2))
        self.assertEqual(round(b["total"], 2), 11.23)
        self.assertEqual([round(x, 2) for x in b["who"]], [4.21, 1.02, 2.0, 4.0, 0.0])

    def test_largest_remainder_keeps_the_whole_beads_and_each_column_within_one(self):
        b = self.budget(budget_data())
        self.assertEqual(b["beads"], 6)
        for view in ("date", "day"):
            cols = b["cols"][view]
            self.assertEqual(sum(c["b"] for c in cols), 6, view)
            self.assertEqual([c["label"] for c in cols if abs(c["b"] - c["u"] / 2) >= 1], [])
            self.assertEqual([c["label"] for c in cols if sum(c["kb"]) != c["b"]], [])
            self.assertEqual([c["label"] for c in cols if sum(c["wb"]) != c["b"]], [])
        self.assertEqual([c["b"] for c in b["cols"]["date"]], [1, 4, 1])

    def test_each_date_counts_the_calls_the_hooks_refused_and_the_outputs_cut(self):
        data = budget_data()
        data["refusals"] = [
            {"date": "2026-01-02", "guard": "read-guard", "refused": 3},
            {"date": "2026-01-02", "guard": "a-new-guard", "refused": 1},
            {"date": "2026-01-01", "guard": "read-guard", "refused": 0},
        ]
        data["tokens"][0]["cut"] = 2
        cols = {c["date"]: c for c in self.budget(data)["cols"]["date"]}
        short = [(cols[x]["refused"], cols[x]["cut"]) for x in sorted(cols)][:2]
        self.assertEqual(short, [(0, 2), (4, 0)])
        self.assertEqual(
            [(x, cols[x]["refused"], cols[x]["rf"], cols[x]["cut"]) for x in sorted(cols)][:2],
            [
                ("2026-01-01", 0, [], 2),
                ("2026-01-02", 4, [["read-guard", 3], ["a-new-guard", 1]], 0),
            ],
        )

    def test_the_day_view_has_a_column_for_work_on_no_day(self):
        cols = self.budget(budget_data())["cols"]["day"]
        self.assertEqual([(c["day"], c["b"]) for c in cols], [(1, 1), (2, 3), (None, 2)])
        self.assertEqual(round(cols[-1]["u"], 2), 4.02)

    def test_the_rail_is_unknown_on_a_date_with_no_past_150k_figure(self):
        cols = self.budget(budget_data())["cols"]["date"]
        self.assertEqual([c["p"] for c in cols], [0.5, 1.0, None])

    def test_the_days_worked_on_each_date_and_their_pills(self):
        b = self.budget(budget_data())
        self.assertEqual([c["days"] for c in b["cols"]["date"]], [[1], [2], [2]])
        self.assertEqual(
            [(p["day"], p["from"], p["to"], p["lane"]) for p in b["pills"]],
            [(1, 0, 0, 0), (2, 1, 2, 0)],
        )

    def test_with_the_data_branch_or_its_token_usage_json_missing_there_is_no_budget(self):
        for data in (budget_data(commit=None), budget_data(absent=["token-usage.json"])):
            self.assertTrue("empty" in self.budget(data), "the beads would be drawn")
        self.assertNotIn("empty", self.budget(budget_data(absent=["sessions.json"])))

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_the_budget_reconciles_with_the_dollars_counted_on_demo_data(self):
        reconcile = load("dashboard_reconcile", "dashboard-reconcile.py")
        data = demo_data.demo()
        agree, line = reconcile.atp_line(reconcile.model(data), data)
        self.assertTrue(agree, line)
        self.assertRegex(
            line, r"^budget: split \$[\d.]+ \+ not split \$[\d.]+ = \$[\d.]+ .*: agree"
        )


def rings_data():
    """A start with lines before Day 1, two Days and two pull requests on no Day's branch: #3
    merged while Day 1 was open, #6 while Day 2 was."""

    def row(pr, own, kind, **work):
        w = dict.fromkeys(("spec", "context", "prod", "test", "tooling"), 0)
        w.update(work)
        branch = f"day-0{own}/x" if own else "tooling/x" if pr else ""
        return {
            "pr": pr,
            "own_day": own,
            "kind": kind,
            "branch": branch,
            "work": w,
            "date": "2026-01-0" + str(pr or 1),
            "title": f"#{pr}",
        }

    return {
        "rows": [
            row(None, None, "origin", spec=5),
            row(1, 1, "spec", spec=30, context=10),
            row(2, 1, "code", prod=40, test=60),
            row(3, None, "other", tooling=100, test=20),
            row(4, 1, "close", spec=2),
            row(5, 2, "code", prod=10, test=30, context=5),
            row(6, None, "other", tooling=7),
        ],
        "days": [
            {"day": 1, "status": "done", "title": "One"},
            {"day": 2, "status": "active", "title": "Two"},
        ],
        "now": {"head": "abcdef1234", "last_pr": 6, "generated": "2026-01-07T09:00+00:00"},
    }


class RingsTest(unittest.TestCase):
    """rings(): graph 9's lines as growth rings, a Day's own work above, work on no Day below."""

    def rings(self, data):
        return load("spec_drift_views", "spec_drift_views.py").rings(data)

    def test_a_pull_request_belongs_to_the_day_graph_9_gives_it(self):
        r = self.rings(rings_data())
        self.assertEqual(
            [(x["day"], x["lines"], x["prs"]) for x in r["days"]], [(1, 142, 3), (2, 45, 1)]
        )
        self.assertEqual(
            [(x["at"], x["lines"], x["prs"]) for x in r["outside"]], [(1, 120, 1), (2, 7, 1)]
        )
        self.assertEqual((r["before"]["lines"], r["unplaced"]["lines"]), (5, 0))

    def test_specs_and_agent_context_are_two_bands(self):
        day1 = self.rings(rings_data())["days"][0]
        self.assertEqual(
            [(k[0], k[1]) for k in day1["k"]],
            [("prod", 40), ("test", 60), ("spec", 32), ("context", 10), ("tooling", 0)],
        )
        self.assertEqual([k[2] for k in day1["k"]], ["28%", "42%", "23%", "7.0%", "0%"])

    def test_a_share_is_rounded_as_the_picture_shows_it(self):
        share = load("spec_drift_views", "spec_drift_views.py")._share
        cases = [
            (0.2239, "22%"),
            (0.0328, "3.3%"),
            (0.0028, "0.28%"),
            (0.000465, "0.05%"),
            (0, "0%"),
            (1, "100%"),
            (0.00001, "<0.01%"),
        ]
        self.assertEqual([share(x) for x, _ in cases], [w for _, w in cases])

    def test_the_totals_are_graph_9s(self):
        r = self.rings(rings_data())
        self.assertEqual((r["inside"]["lines"], r["out"]["lines"], r["total"]), (187, 127, 319))
        self.assertEqual(r["all_lines"], 319)

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_the_rings_reconcile_with_the_lines_counted(self):
        reconcile = load("dashboard_reconcile", "dashboard-reconcile.py")
        data = rings_data()
        data["rings"] = self.rings(data)
        for d in (data, demo_data.demo()):
            agree, line = reconcile.rng_line(reconcile.model(d), d)
            self.assertTrue(agree, line)
            self.assertRegex(line, r"^rings: Days [\d,]+ \+ outside [\d,]+ .*: agree")


def recheck_data():
    """Two merges the replay ran on, #10 and #12; C1 proven at #12, C2 unproven, C3 broken at #10 and holding after the
    last merge (a cell the last re-check has not reached), C4 replaced, C5 not yet in force."""

    def cell(n, criterion, state):
        return {"n": n, "criterion": criterion, "state": state}

    return {
        "replay": {
            "merges": [{"n": 2, "pr": 12}, {"n": 1, "pr": 10}],
            "cells": [
                cell(1, "C1", "holds, never broken"),
                cell(2, "C1", "holds"),
                cell(1, "C2", "holds, never broken"),
                cell(1, "C3", "code broken"),
                cell(3, "C3", "holds"),
                cell(2, "C4", "holds"),
                cell(2, "C5", "not yet in force"),
            ],
        },
        "criteria_index": [{"id": "C4", "replaced_by": "C9"}, {"id": "C1"}],
    }


class RecountTest(unittest.TestCase):
    """The figures dashboard-reconcile.py counts from the data itself, for the sections whose original graph has left
    the page: each counted by none of spec_drift_views.py's functions."""

    @classmethod
    def setUpClass(cls):
        cls.reconcile = load("dashboard_reconcile", "dashboard-reconcile.py")

    def test_the_days_finished_are_those_numbered_in_a_phase_not_cut(self):
        rows = [
            {"phase": 0, "days": [1, 2, 3], "cut": False},
            {"phase": 1, "days": [4, 5], "cut": True},
            {"phase": 2, "days": [6], "cut": False},
        ]
        status = ["done", "closed", "active", "done", "done", "cut"]
        data = {
            "meta": {"where": {"rows": rows}},
            "days": [{"day": n + 1, "status": s} for n, s in enumerate(status)],
        }
        self.assertEqual(self.reconcile.days_finished(data), (3, 4))
        self.assertIsNone(self.reconcile.days_finished({"meta": {"where": {"rows": []}}}))

    def test_the_last_recheck_counts_each_criterion_in_force_at_the_newest_merge(self):
        got = self.reconcile.last_recheck(recheck_data())
        self.assertEqual(got, {"pr": 12, "proven": 1, "total": 3})
        self.assertIsNone(self.reconcile.last_recheck({"replay": {"merges": []}}))

    def test_the_dollars_are_every_token_row_to_the_cent(self):
        self.assertEqual(self.reconcile.dollars(budget_data()), 11.23)  # 1.21 + 1.02 + 4 + 3 + 2
        rows = [{"cost": 0.004}, {"cost": 0.003}, {"cost": None}]
        self.assertEqual(self.reconcile.dollars({"tokens": rows}), 0.01)

    def test_the_lines_are_placed_by_the_branch_and_the_day_begun(self):
        got = self.reconcile.lines_placed(rings_data())
        self.assertEqual(
            (got["days"], got["beside"], got["before"]),
            ({1: (142, 42), 2: (45, 5)}, {1: 120, 2: 7}, 5),
        )

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_a_section_whose_figure_differs_from_the_recount_says_disagree(self):
        data = demo_data.demo()
        m = self.reconcile.model(data)
        # the figure each line holds to its recount, one higher in the view than in the data
        lines = (
            ("whr", ["closed"], self.reconcile.ring_line),
            ("prt", ["rechecked"], self.reconcile.prt_line),
            ("atp", ["kinds", 3], self.reconcile.atp_line),
            ("rng", ["inside", "lines"], self.reconcile.rng_line),
        )
        for key, path, line in lines:
            self.assertEqual(line(m, data)[0], True, key)
            changed = json.loads(json.dumps(m))
            at = changed[key]
            for step in path[:-1]:
                at = at[step]
            at[path[-1]] += 1
            agree, said = line(changed, data)
            self.assertEqual((key, agree, "DISAGREE" in said), (key, False, True))


def clock_data(absent=(), commit="abc"):
    """Graph 10's times: a session past midnight, a wait across 05:00, two implementer sessions at once, the main
    session and an auditor at once, pull requests merged on two dates, one opened on the date before."""

    def s(agent, day, a, b, replies=5, **kw):
        return {
            "date": a[:10],
            "day": day,
            "agent": agent,
            "replies": replies,
            **kw,
            "from": a,
            "to": b,
        }

    def pr(number, day, kind, opened, merged=None):
        p = {
            "number": number,
            "day": day,
            "kind": kind,
            "branch": f"b{number}",
            "opened": opened,
            "checks": {"start": opened, "end": opened, "runs": 1, "failed": 0},
        }
        if merged:
            p["merged"] = merged
        return p

    return {
        "clock": {
            "sessions": [
                s(
                    "main",
                    1,
                    "2026-03-02T09:00:00+01:00",
                    "2026-03-02T12:00:00+01:00",
                    30,
                    ran={"tests": 120, "checks": 900, "other": 30},
                    runs=[["2026-03-02T08:30:00Z", "2026-03-02T08:45:00Z", "checks"]],
                ),
                s("spec-auditor", 1, "2026-03-02T09:30:00+01:00", "2026-03-02T09:50:00+01:00", 4),
                s("implementer", 1, "2026-03-02T10:00:00+01:00", "2026-03-02T11:00:00+01:00"),
                s(
                    "implementer",
                    1,
                    "2026-03-02T10:30:00+01:00",
                    "2026-03-02T11:30:00+01:00",
                    ran={"tests": 600},
                ),
                s(
                    "main",
                    1,
                    "2026-03-02T23:30:00+01:00",
                    "2026-03-03T01:30:00+01:00",
                    12,
                    ran={"other": 1200},
                ),
                s(
                    "main",
                    2,
                    "2026-03-03T04:30:00+01:00",
                    "2026-03-03T05:40:00+01:00",
                    8,
                    ran={"tests": 2400, "other": 300},
                    runs=[["2026-03-03T03:50:00Z", "2026-03-03T04:20:00Z", "tests"]],
                ),
                s("main", 2, "2026-03-03T09:00:00+01:00", "2026-03-03T11:00:00+01:00", 20),
                s(
                    "general-purpose",
                    2,
                    "2026-03-03T10:30:00+01:00",
                    "2026-03-03T11:45:00+01:00",
                    3,
                ),
            ],
            "prs": [
                pr(10, 1, "code", "2026-03-02T09:00:00Z", "2026-03-02T09:40:00Z"),
                pr(11, 1, "close", "2026-03-02T20:00:00Z", "2026-03-03T10:00:00Z"),
                pr(12, 2, "spec", "2026-03-03T08:00:00Z", "2026-03-03T08:05:00Z"),
                pr(13, 2, "code", "2026-03-03T09:00:00Z"),
                pr(14, None, "other", "2026-03-02T21:00:00Z", "2026-03-02T23:10:00Z"),
            ],
        },
        "counted": {"at": "2026-03-03T18:00:00+01:00"},
        "data": {"branch": "dashboard-data", "commit": commit, "absent": list(absent)},
        "days": [
            {"day": 1, "status": "done", "title": "One"},
            {"day": 2, "status": "active", "title": "Two"},
        ],
        "now": {"head": "abcdef1234", "last_pr": 14, "generated": "2026-03-03T19:00+00:00"},
    }


# What graph 10 counted itself in dashboard.js up to #239 (clockGraph's lanes, waits, `ran`, merges and lower median),
# run in node on each data set before the counting moved to spec_drift_views.actogram: per date, the lanes' busy
# minutes, their waits on commands, the waits on tests, GitHub's checks and other commands, the pull requests merged
# and their median wait, in minutes rounded to 0.1.
# fmt: off
OLD_CLOCK_DEMO = {
    "2026-10-01": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 55],
    "2026-10-02": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 25],
    "2026-10-03": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 195],
    "2026-10-04": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 55],
    "2026-10-05": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 25],
    "2026-10-06": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 195],
    "2026-10-07": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 55],
    "2026-10-08": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 25],
    "2026-10-09": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 195],
    "2026-10-10": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 55],
    "2026-10-11": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 25],
    "2026-10-12": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 195],
    "2026-10-13": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 55],
    "2026-10-14": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 25],
    "2026-10-15": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 195],
    "2026-10-16": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 1, 55],
    # the demo's tooling pull request #119 merged on 17 Oct too, open 22 minutes: two merges, their lower median 22
    "2026-10-17": [{"main": 430, "implementer": 60, "auditors": 25}, {"main": 0, "implementer": 0, "auditors": 0}, [0, 0, 0], 2, 22],
}
OLD_CLOCK_FIXTURE = {
    "2026-03-02": [{"main": 330, "implementer": 90, "auditors": 20}, {"main": 53.9, "implementer": 10, "auditors": 0}, [26.3, 15, 22.6], 2, 40],
    "2026-03-03": [{"main": 160, "other": 75}, {"main": 28.6, "other": 0}, [25.7, 0, 2.9], 2, 5],
}
# fmt: on


def fig_of(x):
    """A date's figures in OLD_CLOCK_*'s form, from actogram()'s date or graph 10's `fig`."""
    return [x["lanes"], x["waits"], x["ran"], x["merged"], x["median"]]


ACT = r"""
const fs = require("fs"), vm = require("vm");
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")) });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const g = model(DATA).g10; g.error ? g : g.dates.map(x => [x.date, x.fig])`, ctx)));
"""


class ActogramTest(unittest.TestCase):
    """actogram(): every date on one clock, 05:00 to 05:00, counted by graph 10's rules."""

    def act(self, data):
        return load("spec_drift_views", "spec_drift_views.py").actogram(data)

    def test_the_figures_per_date_are_graph_10s(self):
        for data, old in ((demo_data.demo(), OLD_CLOCK_DEMO), (clock_data(), OLD_CLOCK_FIXTURE)):
            a = self.act(data)
            self.assertEqual([x["date"] for x in a["dates"]], sorted(old))
            for x in a["dates"]:
                self.assertEqual(fig_of(x), old[x["date"]], x["date"])

    def test_a_date_runs_from_05_00_to_05_00_on_the_sessions_clock(self):
        a = self.act(clock_data())
        self.assertEqual(a["zone"], "UTC+01:00")
        evening, next_day = a["dates"]
        # 23:30 to 01:30 stays on the evening's row, past midnight (minute 1140)
        self.assertIn([1110, 1230, "main"], evening["segs"])
        # a wait from 04:50 to 05:20 is split at 05:00
        self.assertEqual(evening["wait_segs"][-1], [1430, 1440, "tests", 0])
        self.assertEqual(next_day["wait_segs"], [[0, 20, "tests", 0]])
        self.assertEqual(
            (evening["label"], evening["days"], evening["up_to"]), ("2 Mar", [1, 2], 1440)
        )
        self.assertEqual(next_day["up_to"], 780)
        # a pull request merged at 02:00 is the evening's merge, not the next date's
        d = clock_data()
        d["clock"]["prs"].append(
            {
                "number": 15,
                "day": 1,
                "kind": "code",
                "branch": "b15",
                "opened": "2026-03-02T23:00:00+01:00",
                "merged": "2026-03-03T02:00:00+01:00",
                "checks": {"start": None, "end": None, "runs": 0, "failed": 0},
            }
        )
        evening, next_day = self.act(d)["dates"]
        self.assertEqual(
            [(m["pr"], m["from"], m["at"]) for m in evening["merges"] if m["pr"] == 15],
            [(15, 1080, 1260)],
        )
        self.assertNotIn(15, [m["pr"] for m in next_day["merges"]])

    def test_two_sessions_busy_at_once_count_once(self):
        evening, next_day = self.act(clock_data())["dates"]
        self.assertEqual((evening["busy"], evening["main"]), (330, 330))
        self.assertEqual((next_day["busy"], next_day["main"]), (205, 160))
        self.assertEqual(next_day["segs"], [[0, 40, "main"], [240, 360, "main"], [360, 405, "sub"]])

    def test_a_merge_opened_before_the_rows_05_00_is_cut_and_keeps_its_wait(self):
        evening, next_day = self.act(clock_data())["dates"]
        marks = lambda d: [(m["pr"], m["at"], m["from"], m["wait"], m["cut"]) for m in d["merges"]]
        self.assertEqual(marks(evening), [(10, 340, 300, 40, False), (14, 1150, 1020, 130, False)])
        self.assertEqual(marks(next_day), [(11, 360, 0, 840, True), (12, 245, 240, 5, False)])

    def test_the_totals(self):
        t = self.act(clock_data())["totals"]
        self.assertEqual((t["dates"], t["first"], t["last"]), (2, "2026-03-02", "2026-03-03"))
        self.assertEqual((t["busy"], t["main"], t["merged"], t["median"]), (535, 490, 4, 40))
        self.assertEqual((t["over_hour"], t["longest"]), (2, {"pr": 11, "wait": 840}))
        self.assertEqual((t["after_midnight"], t["whole"]), (1, 1))

    def test_the_banner_when_the_sessions_are_not_on_the_data_branch(self):
        self.assertIsNone(self.act(clock_data())["missing"])
        absent = self.act(clock_data(absent=["sessions.json"]))["missing"]
        self.assertRegex(
            absent, r"^the dashboard-data branch has no sessions.json, so no session is drawn"
        )
        gone = self.act(clock_data(commit=None))["missing"]
        self.assertRegex(gone, r"^the dashboard-data branch is missing, so no session is drawn")

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_graph_10_reads_its_figures_from_the_actogram(self):
        reconcile = load("dashboard_reconcile", "dashboard-reconcile.py")
        for data, old in ((demo_data.demo(), OLD_CLOCK_DEMO), (clock_data(), OLD_CLOCK_FIXTURE)):
            data = {**data, "actogram": self.act(data)}
            out = subprocess.run(
                ["node", "-e", ACT, reconcile.SCRIPT],
                input=json.dumps(data),
                capture_output=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(out.returncode, 0, out.stderr[:800])
            for date, fig in json.loads(out.stdout):
                self.assertEqual(fig_of(fig), old[date], date)

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_the_actogram_reconciles_with_graph_10(self):
        reconcile = load("dashboard_reconcile", "dashboard-reconcile.py")
        for data in (clock_data(), demo_data.demo()):
            data = {**data, "actogram": self.act(data)}
            agree, line = reconcile.act_line(reconcile.model(data))
            self.assertTrue(agree, line)
            self.assertRegex(line, r"^actogram: \d+ dates, busy [\d.]+ h .*: agree$")

    def test_a_date_has_its_weekday(self):
        evening, next_day = self.act(clock_data())["dates"]
        self.assertEqual((evening["weekday"], evening["label"]), ("Mon", "2 Mar"))
        self.assertEqual((next_day["weekday"], next_day["label"]), ("Tue", "3 Mar"))

    def test_the_sub_agents_are_one_lane_two_of_them_at_once_counted_once(self):
        evening, next_day = self.act(clock_data())["dates"]
        # the auditor is busy from 09:30 to 09:50 while the main session is too, and stays in the lane;
        # the two implementers are both busy from 10:30 to 11:00, counted once
        self.assertEqual((evening["subs"], evening["sub"]), ([[270, 290], [300, 390]], 110))
        self.assertEqual((next_day["subs"], next_day["sub"]), ([[330, 405]], 75))
        # the figures graph 10 reads are as they were
        self.assertEqual(fig_of(evening), OLD_CLOCK_FIXTURE["2026-03-02"])

    def test_two_main_sessions_busy_at_once(self):
        # two implementers at once are not two main sessions
        evening, next_day = self.act(clock_data())["dates"]
        self.assertEqual((evening["two"], evening["two_min"]), ([], 0))
        self.assertEqual((next_day["two"], next_day["two_min"]), ([], 0))
        # two more main sessions inside the one busy from 09:00 to 12:00: 10:00 to 10:30 and 10:15 to 10:45
        d = clock_data()
        d["clock"]["sessions"] += [
            main_session("2026-03-02T10:00:00+01:00", "2026-03-02T10:30:00+01:00"),
            main_session("2026-03-02T10:15:00+01:00", "2026-03-02T10:45:00+01:00"),
        ]
        evening, next_day = self.act(d)["dates"]
        self.assertEqual((evening["two"], evening["two_min"]), ([[300, 345]], 45))
        self.assertEqual((evening["busy"], evening["main"]), (330, 330))
        self.assertEqual(next_day["two"], [])

    def test_a_wait_names_the_lane_it_is_drawn_in(self):
        d = clock_data()
        # the implementer busy from 10:00 to 11:00 waits on tests from 10:10 to 10:20
        d["clock"]["sessions"][2]["runs"] = [
            ["2026-03-02T09:10:00Z", "2026-03-02T09:20:00Z", "tests"]
        ]
        evening, next_day = self.act(d)["dates"]
        self.assertEqual([s[3] for s in evening["wait_segs"]], [0, 1, 0])
        self.assertEqual(
            evening["wait_segs"],
            [[270, 285, "checks", 0], [310, 320, "tests", 1], [1430, 1440, "tests", 0]],
        )
        self.assertEqual(next_day["wait_segs"], [[0, 20, "tests", 0]])

    def test_the_pull_requests_open_on_a_date(self):
        d = clock_data()
        d["clock"]["prs"] += [
            open_pr(20, "code", "2026-03-02T05:00:00Z", merged="2026-03-02T06:00:00Z"),
            # opened while #20 is open: half height
            open_pr(21, "spec", "2026-03-02T05:30:00Z", merged="2026-03-02T05:45:00Z"),
            # opened after both closed: full height; its kind is none the page draws
            open_pr(22, "dashboard", "2026-03-02T06:30:00Z", merged="2026-03-02T06:40:00Z"),
            open_pr(23, "code", "2026-03-02T07:00:00Z", closed="2026-03-02T07:20:00Z"),
        ]
        evening, next_day = self.act(d)["dates"]
        keys = ("pr", "from", "to", "kind", "half", "state", "wait", "cut", "day")
        bars = lambda x: [tuple(p[k] for k in keys) for p in x["prs"]]
        self.assertEqual([p["pr"] for p in evening["prs"] if p["half"]], [21, 14])
        self.assertEqual(
            bars(evening),
            [
                (20, 60, 120, "code", False, "merged", 60, False, 1),
                (21, 90, 105, "spec", True, "merged", 15, False, 1),
                (22, 150, 160, "other", False, "merged", 10, False, 1),
                (23, 180, 200, "code", False, "closed", 20, False, 1),
                (10, 300, 340, "code", False, "merged", 40, False, 1),
                # merged on the next date: open to this date's end
                (11, 960, 1440, "close", False, "merged", 840, False, 1),
                (14, 1020, 1150, "other", True, "merged", 130, False, None),
            ],
        )
        self.assertEqual(
            bars(next_day),
            [
                # opened before the row's 05:00: cut at its start, its whole wait kept
                (11, 0, 360, "close", False, "merged", 840, True, 1),
                (12, 240, 245, "spec", True, "merged", 5, False, 2),
                # still open: to the date's end, with no wait
                (13, 300, 1440, "code", True, "open", None, False, 2),
            ],
        )
        self.assertEqual((evening["open"], next_day["open"]), (7, 3))
        self.assertEqual(sorted(evening["prs"][0]), sorted(keys))
        # the closed one is no merge
        self.assertNotIn(23, [m["pr"] for m in evening["merges"]])

    def test_the_checks_running_on_a_date(self):
        d = clock_data()
        z = lambda t, date="02": f"2026-03-{date}T{t}:00Z"
        d["clock"]["prs"] += [
            # two stretches, a run failed in the first
            open_pr(
                30,
                "code",
                z("06:00"),
                merged=z("06:50"),
                checks=the_checks(
                    z("06:01"),
                    z("06:40"),
                    failed=1,
                    spans=[[z("06:01"), z("06:05"), 1], [z("06:30"), z("06:40"), 0]],
                ),
            ),
            # written before the stretches were kept: the first start to the last end, two runs failed
            open_pr(
                31,
                "code",
                z("07:00"),
                merged=z("07:30"),
                checks=the_checks(z("07:02"), z("07:12"), failed=2),
            ),
            # running across the row's 05:00, which is 04:00 UTC: clipped to each date
            open_pr(
                32,
                "code",
                z("03:50", "03"),
                merged=z("04:30", "03"),
                checks=the_checks(
                    z("03:55", "03"),
                    z("04:10", "03"),
                    spans=[[z("03:55", "03"), z("04:10", "03"), 0]],
                ),
            ),
            # running while #30's first stretch is: the minutes they share count once
            open_pr(
                33,
                "spec",
                z("06:00"),
                merged=z("06:20"),
                checks=the_checks(z("06:03"), z("06:08"), spans=[[z("06:03"), z("06:08"), 0]]),
            ),
        ]
        evening, next_day = self.act(d)["dates"]
        self.assertEqual([c[3] for c in evening["checks"] if c[2]], [30, 31])
        self.assertEqual(
            evening["checks"],
            [
                [121, 125, 1, 30],
                [123, 128, 0, 33],
                [150, 160, 0, 30],
                [182, 192, 1, 31],
                [300, 300, 0, 10],
                [960, 960, 0, 11],
                [1020, 1020, 0, 14],
                [1435, 1440, 0, 32],
            ],
        )
        self.assertEqual(next_day["checks"], [[0, 10, 0, 32], [240, 240, 0, 12], [300, 300, 0, 13]])
        self.assertEqual((evening["checks_min"], next_day["checks_min"]), (32, 10))
        # a pull request with no check recorded has no stretch
        d["clock"]["prs"].append(open_pr(34, "code", z("08:00"), merged=z("08:10")))
        d["clock"]["prs"].append(
            {**open_pr(35, "code", z("08:00"), merged=z("08:10")), "checks": None}
        )
        self.assertEqual(self.act(d)["dates"][0]["checks"], evening["checks"])

    def test_the_totals_of_two_main_sessions_at_once_and_of_the_sub_agents(self):
        t = self.act(clock_data())["totals"]
        self.assertEqual((t["two"], t["sub"]), (0, 185))
        d = clock_data()
        d["clock"]["sessions"] += [
            main_session("2026-03-02T10:00:00+01:00", "2026-03-02T10:30:00+01:00"),
            main_session("2026-03-03T09:30:00+01:00", "2026-03-03T09:45:00+01:00"),
        ]
        t = self.act(d)["totals"]
        self.assertEqual((t["two"], t["sub"]), (45, 185))

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_the_actograms_pull_requests_and_checks_are_graph_10s_on_each_date(self):
        reconcile = load("dashboard_reconcile", "dashboard-reconcile.py")
        for data in (clock_data(), demo_data.demo()):
            data = {**data, "actogram": self.act(data)}
            agree, line = reconcile.act_line(reconcile.model(data))
            self.assertTrue(agree, line)
            self.assertRegex(
                line,
                r", (\d+) pull requests open, (\d+) checks \| graph 10: .*"
                r", \1 pull request bars, \2 check bars: agree$",
            )
            # one pull request bar, then one check, taken out of the actogram on one date
            for key, word in (("prs", "pull requests"), ("checks", "checks")):
                less = json.loads(json.dumps(data))
                date = next(x for x in less["actogram"]["dates"] if x[key])
                date[key].pop()
                agree, line = reconcile.act_line(reconcile.model(less))
                self.assertFalse(agree, line)
                self.assertRegex(line, rf": DISAGREE \(.*{word} differ on {date['date']}\b")


def main_session(a, b):
    """A main session of clock_data()'s Day 1, busy from `a` to `b`."""
    return {"date": a[:10], "day": 1, "agent": "main", "replies": 3, "from": a, "to": b}


def the_checks(start, end, failed=0, spans=None):
    """A pull request's checks as GitHub's times give them; `spans` only when the stretches were kept."""
    checks = {"start": start, "end": end, "runs": 4, "failed": failed, "pushes": 1}
    if spans:
        checks["spans"] = spans
    return checks


def open_pr(number, kind, opened, merged=None, closed=None, checks=None):
    """A pull request of clock_data()'s Day 1: merged, closed without a merge, or still open."""
    p = {
        "number": number,
        "day": 1,
        "kind": kind,
        "branch": f"b{number}",
        "opened": opened,
        "checks": checks or {"start": None, "end": None, "runs": 0, "failed": 0},
    }
    if merged:
        p["merged"] = merged
    if closed:
        p["closed"] = closed
    return p


def runs_data(absent=(), commit="abc"):
    """The example data with the driver's run log as the trial's first five steps had it: two merged untouched, one
    parked by a fault after its first session crashed and merged after the next, one parked for the maintainer
    with no session, one still open."""
    data = demo_data.demo()

    def ses(a, b, cost, denials=0):
        return {
            "session": f"s-{a}",
            "start": a,
            "end": b,
            "cost": cost,
            "denials": denials,
            "fixes": 0,
            "crashed": b is None,
        }

    steps = [
        {
            "step": "Day 13 Track A: C13.1–C13.3, C13.8–C13.9: `bearing/cli.py`, `tests/test_stderr.py`",
            "day": 13,
            "prefix": "day-13/track-a",
            "sessions": [ses("2026-11-10T23:16:41Z", "2026-11-10T23:31:48Z", 0.896, 1)],
            "fixes": 0,
            "crashes": 0,
            "pr": 90,
            "merged": "2026-11-10T23:32:54Z",
            "parks": [],
            "ended": "merged",
        },
        {
            "step": "Day 13 Track B: C13.4–C13.6: `bearing/cli.py`, `tests/test_ingest_limit.py`",
            "day": 13,
            "prefix": "day-13/track-b",
            "sessions": [ses("2026-11-10T23:35:00Z", "2026-11-10T23:44:40Z", 0.7278)],
            "fixes": 0,
            "crashes": 0,
            "pr": 91,
            "merged": "2026-11-10T23:46:18Z",
            "parks": [],
            "ended": "merged",
        },
        {
            "step": "Day 13: the closing PR",
            "day": 13,
            "prefix": "day-13/close-the-day",
            "sessions": [
                ses("2026-11-10T23:47:55Z", None, 0.0),
                ses("2026-11-11T00:00:59Z", "2026-11-11T00:20:40Z", 1.1593),
            ],
            "fixes": 0,
            "crashes": 1,
            "pr": 96,
            "merged": "2026-11-11T00:31:46Z",
            "ended": "parked",
            "parks": [
                {
                    "at": "2026-11-10T23:56:17Z",
                    "by": "fault",
                    "line": "park: the run log names session `s-1` for this step, with no end",
                }
            ],
        },
        {
            "step": "Every day is done.",
            "day": None,
            "prefix": None,
            "sessions": [],
            "fixes": 0,
            "crashes": 0,
            "pr": None,
            "merged": None,
            "parks": [
                {
                    "at": "2026-11-11T00:33:55Z",
                    "line": "park: every day is done",
                    "by": "maintainer",
                }
            ],
            "ended": "parked",
        },
        {
            "step": "Day 14 Track A: C14.1–C14.3: `bearing/ingest/text.py`, `tests/test_sentences.py`",
            "day": 14,
            "prefix": "day-14/track-a",
            "sessions": [ses("2026-11-12T23:14:39Z", "2026-11-12T23:21:05Z", 0.5558, 1)],
            "fixes": 0,
            "crashes": 0,
            "pr": 101,
            "merged": None,
            "parks": [],
            "ended": "open",
        },
    ]
    data["driver_runs"] = {
        "source": "docs/dashboard/driver-runs.json",
        "counted": "2026-11-16T15:06:00+01:00",
        "level_2": {"run": 0, "of": 15},
        "steps": steps,
        "parks": None,
    }
    data["data"] = dict(
        data.get("data") or {}, branch="dashboard-data", commit=commit, absent=list(absent)
    )
    views = load("spec_drift_views", "spec_drift_views.py")
    data["protein"], data["reflex"] = views.protein(data), views.reflex(data)
    return data


class ReflexTest(unittest.TestCase):
    """reflex(): graph 11 as reflex arcs, one row per step the driver started, counted from its run log."""

    def views(self):
        return load("spec_drift_views", "spec_drift_views.py")

    def test_its_counts_are_the_proteins_in_real_runs(self):
        v = self.views()
        for data in (demo_data.demo(), runs_data()):
            r = v.reflex(data)
            run = next(c["run"] for c in v.protein(data)["chains"] if c["run"])
            c = r["counts"]
            self.assertEqual(
                [c["steps"], c["parks"], c["crashed"], c["open"], c["merged"]],
                [
                    run["of"],
                    len(run["parks"]),
                    len(run["crashes"]),
                    len(run["open"]),
                    len(run["merged"]),
                ],
            )
        self.assertEqual(
            [c["steps"], c["parks"], c["crashed"], c["open"], c["merged"]], [5, 2, 1, 1, 2]
        )

    def test_one_row_per_step_in_run_log_order_with_its_sessions_parks_and_pull_request(self):
        r = self.views().reflex(runs_data())
        self.assertEqual(r["zone"], "UTC+1")
        self.assertEqual(
            [[x["label"], x["sub"]] for x in r["rows"]],
            [
                ["Day 13 Track A", "project's Day 13 · C13.1–C13.3, C13.8–C13.9"],
                ["Day 13 Track B", "project's Day 13 · C13.4–C13.6"],
                ["Day 13: the closing PR", "project's Day 13"],
                ["Every day is done.", "no project Day"],
                ["Day 14 Track A", "project's Day 14 · C14.1–C14.3"],
            ],
        )
        self.assertEqual(
            [[s["crashed"] for s in x["sessions"]] for x in r["rows"]],
            [[False], [False], [True, False], [], [False]],
        )
        self.assertEqual(
            [[[p["by"], p["up"], p["back"]] for p in x["parks"]] for x in r["rows"]],
            [[], [], [["fault", 0, 1]], [["maintainer", None, None]], []],
        )
        self.assertEqual(
            [[x["pr"]["number"], x["pr"]["state"]] if x["pr"] else None for x in r["rows"]],
            [[90, "merged"], [91, "merged"], [96, "merged"], None, [101, "open"]],
        )
        self.assertEqual(
            [x["fin"] for x in r["rows"]], ["merged", "merged", "fault", "maint", "still"]
        )
        self.assertEqual(
            [x["end"] for x in r["rows"]],
            [
                "Merged, with no park",
                "Merged, with no park",
                "Parked by a fault, then merged",
                "Parked for the maintainer",
                "Still open, no park so far",
            ],
        )
        self.assertEqual(r["rows"][2]["end_sub"], "2 sessions, 1 crashed · 20 min · $1.16")

    def test_a_park_says_when_the_next_session_started_and_never_a_wait(self):
        r = self.views().reflex(runs_data())
        self.assertEqual(
            [re.findall(r"\d+ minutes? later", p["later"]) for x in r["rows"] for p in x["parks"]],
            [["5 minutes later"], []],
        )
        self.assertEqual(
            [p["later"] for x in r["rows"] for p in x["parks"]],
            [
                "the next session started 5 minutes later",
                "no session started after it in this step",
            ],
        )
        self.assertEqual(r["tips"]["s2p0"]["t"], "Parked by a fault · 11 Nov 00:56 (UTC+1)")
        self.assertEqual(
            r["tips"]["s2p0"]["l"][1:],
            [
                "It came back down at session 2: the next session started 5 minutes later.",
                "How long a person was needed is not known: the park names no issue.",
            ],
        )
        self.assertEqual(
            r["tips"]["s3p0"]["l"][1],
            "It did not come back: no session started after it in this step.",
        )
        words = json.dumps(r, ensure_ascii=False).lower()
        self.assertEqual(re.findall(r"\bwait(?:ed|ing)?\b|\banswer\w*", words), [])

    def test_the_figures_line_counts_steps_parks_sessions_and_merges(self):
        r = self.views().reflex(runs_data())
        self.assertEqual(
            [[f["num"], f["small"], f["what"]] for f in r["figs"]],
            [
                ["5", None, "steps the driver started"],
                ["2", "of 4 ended", "finished without a park"],
                ["1", None, "session a step, at the median"],
                ["3", "of 4 opened", "pull requests merged"],
            ],
        )
        self.assertEqual(
            r["figs"][0]["sub"],
            "3 on the project's Day 13, 1 on Day 14 and 1 with no Day. All on 2 dates: too few to judge by.",
        )
        self.assertEqual(r["level_2"], {"run": 0, "of": 15})

    def test_with_the_run_log_or_the_data_branch_missing_it_says_so_and_draws_nothing(self):
        v = self.views()
        self.assertEqual(
            [
                bool(v.reflex(runs_data(**k))["missing"])
                for k in ({}, {"commit": None}, {"absent": ["driver-runs.json"]})
            ],
            [False, True, True],
        )
        self.assertEqual(
            v.reflex(runs_data(commit=None))["missing"],
            "the dashboard-data branch is missing, so no step of the driver is drawn.",
        )
        self.assertEqual(
            v.reflex(runs_data(absent=["driver-runs.json"]))["missing"],
            "the dashboard-data branch has no driver-runs.json, so no step of the driver is drawn.",
        )
        data = runs_data()
        data["driver_runs"] = {
            "source": "docs/dashboard/driver-runs.json",
            "counted": None,
            "level_2": None,
            "steps": None,
            "parks": None,
        }
        self.assertEqual(
            v.reflex(data)["missing"],
            "the driver's run log is not counted for this project yet, so no step is drawn.",
        )
        self.assertEqual(v.reflex(data)["rows"], [])
        self.assertIsNone(v.reflex(runs_data())["missing"])


# rfxDraw() from dashboard.js on the data from stdin, on a document that keeps every node it makes: the marks drawn by
# kind, the rows' labels and what the pointer box says for a park.
RFX = r"""
const fs = require("fs"), vm = require("vm"), els = {}, made = [];
const node = tag => { const n = { tag, attrs: {}, kids: [], style: {}, dataset: {}, hidden: false, on: {}, classList: { add() {}, remove() {} },
  setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k]; }, appendChild(c) { this.kids.push(c); return c; },
  append(...c) { this.kids.push(...c); }, replaceChildren(...c) { if (c.some(Array.isArray)) throw new Error("array"); this.kids = c; },
  addEventListener(t, fn) { this.on[t] = fn; }, getBoundingClientRect: () => ({ left: 0, bottom: 0 }) };
  Object.defineProperty(n, "className", { set(v) { n.attrs.class = v; }, get() { return n.attrs.class || ""; } });
  made.push(n); return n; };
const document = { createElementNS: (ns, tag) => node(tag), createElement: node, addEventListener() {} };
const $ = id => els[id] || (els[id] = node(id));
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")), document, $, made, innerWidth: 1200, innerHeight: 800 });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const M = model(DATA), R = M.rfx, is = c => made.filter(e => (e.attrs.class || "").split(" ").includes(c));
  const words = n => typeof n === "string" ? n : [n.textContent, ...(n.kids || []).map(words)].join(" ");
  if (!R.empty && !R.error) rfxDraw(R, $);
  const fig = $("rfx-fig"), park = is("b").find(g => /p0$/.test(g.attrs["data-k"] || ""));
  if (park) { park.closest = () => park; fig.on.focusin({ target: park }); }
  ({ empty: R.empty || null, error: R.error || null, rows: is("t-lab").map(t => t.textContent), sessions: is("x-ses").length + is("x-crash").length + is("x-fix").length,
     crashed: is("x-crash").length, branches: is("x-br").length, pills: is("x-pill").length, awaited: is("x-go").filter(e => /await/.test(e.attrs.class)).length,
     l2: is("x-l2").length, l2run: is("x-l2").filter(e => /run/.test(e.attrs.class)).length, box: fig.attrs.viewBox,
     tip: park ? $("rfx-tip").kids.map(words) : null, figs: $("rfx-figs").kids.length })`, ctx)));
"""


class ReflexPageTest(unittest.TestCase):
    """Graph 11's reflex arcs drawn by the page: a mark for every step, session, park and pull request reflex() counted."""

    def draw(self, data):
        reconcile = load("dashboard_reconcile", "dashboard-reconcile.py")
        out = subprocess.run(
            ["node", "-e", RFX, reconcile.SCRIPT],
            input=json.dumps(data),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(out.returncode, 0, out.stderr[-600:])
        return json.loads(out.stdout)

    def test_a_mark_for_every_step_session_park_and_pull_request(self):
        v = load("spec_drift_views", "spec_drift_views.py")
        for data in (demo_data.demo(), runs_data()):
            data["reflex"] = r = v.reflex(data)
            got = self.draw(data)
            self.assertEqual(len(got["rows"]), len(r["rows"]))
            self.assertEqual(
                [got["sessions"], got["crashed"], got["branches"], got["pills"]],
                [
                    sum(len(x["sessions"]) for x in r["rows"]),
                    r["counts"]["crashed_sessions"],
                    r["counts"]["parks"],
                    sum(1 for x in r["rows"] if x["pr"]),
                ],
            )
            self.assertEqual(got["rows"], [x["label"] for x in r["rows"]])
        self.assertEqual(
            [got["awaited"], got["l2"], got["l2run"], got["box"], got["figs"]],
            [1, 15, 0, "0 0 1198 211", 4],
        )
        self.assertEqual(
            got["tip"][1:3],
            [
                "The driver or the kit was at fault. It went up at session 1 of 2, which crashed.",
                "It came back down at session 2: the next session started 5 minutes later.",
            ],
        )

    def test_with_the_run_log_missing_nothing_is_drawn(self):
        data = runs_data(absent=["driver-runs.json"])
        data["reflex"] = load("spec_drift_views", "spec_drift_views.py").reflex(data)
        got = self.draw(data)
        self.assertEqual(
            [got["empty"], got["rows"], got["branches"]],
            [
                "the dashboard-data branch has no driver-runs.json, so no step of the driver is drawn.",
                [],
                0,
            ],
        )

    def test_the_reflex_and_the_cell_reconcile_with_graph_11_the_proteins_and_the_panel(self):
        reconcile = load("dashboard_reconcile", "dashboard-reconcile.py")
        v = load("spec_drift_views", "spec_drift_views.py")
        data = runs_data()
        data["reflex"] = v.reflex(data)
        m = reconcile.model(data)
        self.assertEqual(
            reconcile.rfx_line(m),
            (
                True,
                (
                    "reflex: 5 steps, 2 parks, 1 crashed (1 session), 1 open | proteins' real runs: "
                    "5, 2, 1, 1 | graph 11: 5 steps, 2 parks, 1 crashed sessions, 1 open: agree"
                ),
            ),
        )
        self.assertEqual(
            reconcile.cel_line(m),
            (True, "cell: 7 stations, 4 loops | panel: 7 steps, 4 ways back: agree"),
        )
        for line in (
            reconcile.rfx_line(reconcile.model(demo_data.demo())),
            reconcile.cel_line(reconcile.model(demo_data.demo())),
        ):
            self.assertTrue(line[0], line[1])


if __name__ == "__main__":
    unittest.main()
