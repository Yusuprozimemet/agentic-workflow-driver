"""The dashboard's newer views (scripts/pipeline/counts/spec_drift_views.py) and the citations they read: what a criterion cites, each
criterion's state, and the gene, which every commitment of the plan sits in once. Needs node for the page's model."""

import importlib.util
import itertools
import json
import math
import os
import re
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
import pipeline  # importing it puts the pipeline's three folders on the path


def load(name, file):
    spec = importlib.util.spec_from_file_location(
        name, pipeline.path(file) if file.startswith("spec_drift_") else os.path.join(SCRIPTS, file)
    )
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
     dated: drawn.length, names: is("t-row"), box: made[0].attrs.viewBox.split(" ").length, secdiv: is("secdiv"),
     sizes: [...new Set(made.filter(e => (e.attrs.class || "").split(" ").includes("b")).map(e => e.attrs.width + "x" + e.attrs.height))],
     free: is("free"), free_say: made.filter(e => / no criterion cites$/.test(e.textContent || "")).map(e => e.textContent),
     secs: made.filter(e => e.attrs.class === "t-sec").map(e => [e.textContent, e.attrs.transform || ""]) })`, ctx)));
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
  // where the by-Day view put its counts of merges drawn for a stop and its Days' names: [class, words, x, y, anchor]
  out.at = all($("mrg-g")).filter(e => e.tag === "text" && ["nc", "day"].includes(e.attrs.class))
    .map(e => [e.attrs.class, e.textContent, +e.attrs.x, +e.attrs.y, e.attrs["text-anchor"] || "start"]);
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


# The least distance, in px along the plan, between the feet of two slanted section names (the gene's and graph
# 12's): at 52 degrees a 10.5 px line of text needs about 15 px across its slant, so 19 px along the plan.
SEC_GAP = 19


def cut(name):
    """A section name as the gene cuts it: at 38 characters."""
    return name if len(name) <= 38 else name[:37] + "…"


def closer_than(secs, gap):
    """The pairs of neighbouring slanted names whose feet are closer than `gap`, as their words: `secs` is
    [[words, "translate(x y) rotate(a)"]] as drawn."""
    feet = []
    for words, transform in secs:
        m = re.match(r"translate\(([-\d.]+)[ ,]", transform)
        feet.append((float(m.group(1)) if m else 0.0, words))
    feet.sort()
    return [[a[1], b[1]] for a, b in itertools.pairwise(feet) if b[0] - a[0] < gap - 0.05]


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

    def fixture(self, index=None):
        # Row i and the replay's n differ on purpose: a cell's n is the replay's, an event's n is the row's.
        rows = [
            merge_row(i, 10 + i, "code", prod=p, branch=f"day-01/track-{i}")
            for i, p in ((1, 5), (2, 4), (3, 0), (4, 0), (5, 0), (6, 0))
        ]
        index = index or [merge_crit("C1.1", 1, [11]), merge_crit("C1.2", 1, [12])]
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

    def test_a_stop_replaced_by_a_criterion_that_holds_is_replaced_and_one_whose_successor_does_not_is_retired(
        self,
    ):
        # C1.2 stopped holding and is replaced: by C1.1, which holds at the end, it is settled ("replaced");
        # by C1.3, which the replay never ran, it is still a finding to read ("retired").
        held = self.fixture(
            [merge_crit("C1.1", 1, [11]), merge_crit("C1.2", 1, [12], replaced_by=["C1.1"])]
        )
        self.assertEqual(
            [(f["n"], f["kind"], f.get("c")) for f in held["finds"]],
            [(1, "back", 0), (2, "replaced", 1)],
        )
        self.assertEqual(held["all"]["finds"]["replaced"], [2])
        self.assertEqual(held["all"]["finds"]["retired"], [])
        self.assertEqual((held["open_events"], held["replaced_events"]), (0, 1))
        unrun = self.fixture(
            [
                merge_crit("C1.1", 1, [11]),
                merge_crit("C1.2", 1, [12], replaced_by=["C1.3"]),
                merge_crit("C1.3", 1, [13]),
            ]
        )
        self.assertEqual(
            [(f["n"], f["kind"], f.get("c")) for f in unrun["finds"]],
            [(1, "back", 0), (2, "retired", 1)],
        )
        self.assertEqual((unrun["open_events"], unrun["replaced_events"]), (1, 0))

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

    def test_the_gene_splits_what_was_never_transcribed_and_draws_every_band_the_same_size(self):
        data = demo_data.demo()
        m = reconcile.model(data)["gene"]
        self.assertEqual(" ".join(f["cls"] for f in m["figs"][-3:]), "regulatory switched overdue")
        self.assertEqual(
            [(f["cls"], f["n"], f["what"]) for f in m["figs"][-3:]],
            [
                ("regulatory", 1, "is regulatory"),
                ("switched", 1, "is switched off for now"),
                ("overdue", 1, "should be on by now"),
            ],
        )
        tip = {c["id"]: dict(c["tip"])["st"] for c in m["cols"]}
        self.assertEqual(
            (tip["P10"], tip["N03"]),
            (
                (
                    "Regulatory: a rule for how people work. It steers the work and never becomes code, "
                    "so no criterion is expected."
                ),
                (
                    "Switched off until Day 7: a real gene with no criterion yet. "
                    "It turns on when that Day writes its checks."
                ),
            ),
        )
        self.assertEqual(
            [b for b, _ in m["expected"][:2]], ["1 regulatory region", "1 switched-off gene"]
        )
        out = subprocess.run(
            ["node", "-e", DRAWN, reconcile.SCRIPT],
            input=json.dumps(data),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(out.returncode, 0, out.stderr[:600])
        drawn = json.loads(out.stdout)
        # one size for every band; a line in each of the five section gaps inside an arm, none at the arm break
        self.assertEqual((drawn["sizes"], drawn["secdiv"]), (["6.4x24"], 5))

    def test_the_genes_section_names_keep_apart_where_sections_are_narrow(self):
        # the demo plan's added arm holds three sections one commitment wide, side by side: Payment, The cart,
        # Delivery. A slanted name is clear of the next when their feet are SEC_GAP px apart or more. One section
        # gets a name of 46 characters, which the gene cuts at 38.
        data = demo_data.demo()
        for c in data["gene"]["commitments"]:
            if c["section"] == "Who does what":
                c["section"] = "Who does what, and who decides when it is done"
        self.assertEqual(len("Who does what, and who decides when it is done"), 46)
        out = subprocess.run(
            ["node", "-e", DRAWN, reconcile.SCRIPT],
            input=json.dumps(data),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(out.returncode, 0, out.stderr[:600])
        secs = json.loads(out.stdout)["secs"]
        runs = []
        for c in data["gene"]["commitments"]:
            if not runs or runs[-1] != (c["arm"], c["section"]):
                runs.append((c["arm"], c["section"]))
        got, want = [s[0] for s in secs], [cut(name) for _, name in runs]
        self.assertEqual((len(got), got == want), (len(want), True))
        self.assertEqual(closer_than(secs, SEC_GAP), [])

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
        self.assertEqual(got, [(1, ["1 merge of product code no criterion cites"]), (0, [])])

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
                "nc": [f"{r['nocite']} drawn for a stop" for r in g["all"]["rows"] if r["nocite"]],
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
        self.assertEqual(drawn["all"]["nc"], [f"{len(g['all']['nocite'])} drawn for a stop"])
        self.assertEqual(drawn["day"]["nocite"], len(g["by_day"]["1"]["nocite"]))

    def test_a_days_count_of_merges_drawn_for_a_stop_ends_before_its_name(self):
        # by Day: the count at the row's left edge, 8 px italic, about 4.6 px a letter; the Day's name ends 54 px
        # before the row's marks, 11.5 px, about 6.6 px a letter. The count ends before the name begins.
        g = MergeGraphTest().fixture()
        out = subprocess.run(
            ["node", "-e", MRG, reconcile.SCRIPT],
            input=json.dumps({"merge_graph": g}),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(out.returncode, 0, out.stderr[:600])
        at = json.loads(out.stdout)["at"]
        counts = [t for t in at if t[0] == "nc"]
        self.assertEqual(len(counts), 1)
        _, words, x, y, _ = counts[0]
        name = [t for t in at if t[0] == "day" and abs(t[3] - y) < 1 and t[4] == "end"]
        self.assertEqual(len(name), 1)
        _, day, end, _, _ = name[0]
        self.assertEqual((words, x + len(words) * 4.6 < end - len(day) * 6.6), (words, True))

    def test_the_merge_graphs_verdict_reconciles_with_the_promise_tiles_on_demo_data(self):
        agree, line = reconcile.merge_line(reconcile.model(demo_data.demo()))
        self.assertTrue(agree, line)
        self.assertRegex(
            line, r"^merge graph: \d+ criteria \(.*\) \| promise tiles: \d+ \(.*\): agree$"
        )

    def plan_bar(self, data):
        out = subprocess.run(
            ["node", "-e", PLANBAR, reconcile.SCRIPT],
            input=json.dumps(data),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(out.returncode, 0, out.stderr[:600])
        return json.loads(out.stdout)

    def test_graph_12_draws_every_section_name_slanted_whole_and_apart(self):
        # each name is drawn, cut only where the gene cuts; the last of the original plan and the first added
        # later share a name and stay two; none sits on its neighbour
        secs = self.plan_bar(plan_bar_data())["secs"]
        names = [PLAN_LONG, "Narrow", "Tiny", "Thin", "Recovery", "Recovery", "Added later on"]
        got, want = [s[0] for s in secs], [cut(n) for n in names]
        self.assertEqual((len(got), got == want), (len(want), True))
        self.assertEqual(closer_than(secs, SEC_GAP), [])

    def test_graph_12_draws_each_chapter_once_under_added_later(self):
        # commitments added later in an order that comes back to chapter B: the bar draws them chapter by chapter,
        # each chapter in the order it first comes up, as the gene does
        def p(pid, section):
            return {"id": pid, "short": pid, "section": section, "owner_day": None, "rule": False,
                    "change": None, "text": "t."}  # fmt: skip

        data = plan_bar_data()
        order = [("P01", "A"), ("P02", "B"), ("N01", "B"), ("N02", "A"), ("N03", "C"), ("N04", "B")]
        data["plan"]["commitments"] = [p(pid, s) for pid, s in order]
        got = self.plan_bar(data)
        self.assertEqual([s[0] for s in got["secs"]], ["A", "B", "B", "A", "C"])
        # and inside a chapter in the order added: the stripes left to right
        added = [i for i, _ in sorted(got["bands"], key=lambda b: b[1]) if i.startswith("N")]
        self.assertEqual(added, ["N01", "N04", "N02", "N03"])

    def test_graph_12_holds_its_names_title_and_bends_inside_its_picture(self):
        # every slanted name's box and the right column's title lie inside the viewBox; a name moved off its
        # bracket's middle has a bent tick from that middle to its foot
        got = self.plan_bar(plan_bar_data())
        vx, vy, vw, vh = (float(v) for v in got["view"].split())
        out = [
            w
            for w, t in got["secs"]
            for x, y in slanted_corners(w, t)
            if not (vx <= x <= vx + vw and vy <= y <= vy + vh)
        ]
        title = [t for t in got["texts"] if t[0] == "Criteria in force per Day"]
        self.assertEqual(len(title), 1)
        self.assertEqual((len(set(out)), title[0][1] + 25 * 6.8 <= vx + vw), (0, True))
        self.assertEqual(len(got["brackets"]), len(got["secs"]))
        bends = [path_points(d) for d in got["bends"] if "L" in d]
        unbent = []
        for (w, t), (x1, x2) in zip(got["secs"], got["brackets"]):
            c, foot = (x1 + x2) / 2, float(re.match(r"translate\(([-\d.]+)", t).group(1))
            if abs(foot - c) > 0.5 and not any(
                abs(b[0][0] - c) < 0.2 and abs(b[-1][0] - foot) < 0.2 for b in bends
            ):
                unbent.append(w)
        moved = sum(
            abs(float(re.match(r"translate\(([-\d.]+)", t).group(1)) - (x1 + x2) / 2) > 0.5
            for (_, t), (x1, x2) in zip(got["secs"], got["brackets"])
        )
        self.assertEqual((moved > 0, len(unbent)), (True, 0))

    def test_graph_12_keeps_its_names_clear_of_the_quotes_lines(self):
        # twelve more sections added later, one commitment wide each, push names out under the quotes' three lines
        # at the right; each name's slanted box, sampled along its two long sides, stays out of their boxes
        got = self.plan_bar(plan_bar_data(12))
        quotes = [
            t
            for t in got["texts"]
            if t[0].startswith(("Quotes checked", "each one found", "checked again"))
        ]
        self.assertEqual(len(quotes), 3)
        boxes = [(x - len(w) * 6.2, x, y - 10, y + 4) for w, x, y, _ in quotes]
        hit = set()
        for w, t in got["secs"]:
            foot, start, foot_up, start_up = slanted_corners(w, t)
            for a, b in ((foot, start), (foot_up, start_up)):
                for k in range(41):
                    px, py = a[0] + (b[0] - a[0]) * k / 40, a[1] + (b[1] - a[1]) * k / 40
                    if any(x0 < px < x1 and y0 < py < y1 for x0, x1, y0, y1 in boxes):
                        hit.add(w)
        self.assertEqual(len(hit), 0)

    def test_graph_12_counts_only_criteria_in_force(self):
        m = reconcile.model(demo_data.demo())
        due = [c["key"] for c in m["g12"]["all"] if c["is"].get("due")]
        self.assertIn("P02", due, "C1.2 named P02 and was replaced by C5.2, which names none")


# planBar() from dashboard.js on graph 12's model of the data from stdin, as scripts/test_dashboard_page.py's
# PLAN_BAR runs it: the section names under the plan, as [words, transform], in the order drawn; the svg's viewBox;
# every other text, as [words, x, y, anchor]; each section's bracket, as [x1, x2]; and each bent tick, as its d.
PLANBAR = r"""
const fs = require("fs"), vm = require("vm");
const node = tag => { const n = { tag, attrs: {}, kids: [], textContent: "", hidden: false,
  setAttribute(k, v) { this.attrs[k] = String(v); }, appendChild(c) { this.kids.push(c); return c; }, append(...c) { c.forEach(x => this.kids.push(x)); },
  replaceChildren(...c) { this.kids = c.flat(); }, addEventListener() {}, getBoundingClientRect: () => ({ left: 0, top: 0, width: 0, height: 0 }) };
  n.style = { set cssText(v) { n.attrs.style = v; } }; Object.defineProperty(n, "className", { set(v) { this.attrs.class = v; }, get() { return this.attrs.class || ""; } });
  return n; };
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")), document: { createElementNS: (ns, tag) => node(tag), createElement: tag => node(tag) },
  window: {}, console, box: node("div"), tip: node("div"), panel: node("div"), forDays: el => el, resets: [] });
vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\nplanBar(model(DATA).g12, box, tip, panel, forDays, resets);", ctx);
const all = n => typeof n === "object" && n ? [n, ...n.kids.flatMap(all)] : [];
const made = all(ctx.box), named = n => n.tag === "text" && n.attrs.style === "font-size:10.5px";
console.log(JSON.stringify({ secs: made.filter(named).map(n => [n.textContent, n.attrs.transform || ""]),
  view: (made.find(n => n.tag === "svg" && n.attrs.class === "pc-svg") || { attrs: {} }).attrs.viewBox || "",
  texts: made.filter(n => n.tag === "text" && !named(n) && n.attrs.x != null).map(n => [String(n.textContent), +n.attrs.x, +n.attrs.y, n.attrs["text-anchor"] || "start"]),
  brackets: made.filter(n => n.tag === "line" && n.attrs["stroke-width"] === "1.5").map(n => [+n.attrs.x1, +n.attrs.x2]),
  bends: made.filter(n => n.tag === "path" && n.attrs["stroke-width"] === "0.75").map(n => n.attrs.d),
  bands: made.filter(n => n.tag === "rect" && n.attrs.class === "band").map(n => [n.attrs["data-slot"], +n.attrs.x]) }));
"""


def plan_bar_data(added_singles=0):
    """Graph 12's plan: a name over 38 characters, three sections one commitment wide side by side, a wide one, and
    after it an added section of the same name (the arms keep apart), then one more; `added_singles` more added
    sections one commitment wide each, after those."""

    def p(pid, section):
        return {"id": pid, "short": pid, "section": section, "owner_day": None, "rule": False,
                "change": None, "text": "t."}  # fmt: skip

    sections = [PLAN_LONG] * 4 + ["Narrow", "Tiny", "Thin"] + ["Recovery"] * 6
    commitments = [p(f"P{i + 1:02d}", s) for i, s in enumerate(sections)]
    commitments += [p("N01", "Recovery"), p("N02", "Added later on"), p("N03", "Added later on")]
    commitments += [p(f"N{k + 4:02d}", f"Single {k}") for k in range(added_singles)]
    plan = {"reference": "x", "quotes": 0, "unlined": [], "rewrites": [], "said": {}, "links": {},
            "commitments": commitments}  # fmt: skip
    return {
        "now": {"generated": "2026-01-03T09:30+00:00", "head": "abcdef1234", "last_pr": 9,
                "current_day": 3, "next_step": "x", "stop_after": 3, "open_prs": []},
        "days": [{"day": n, "title": f"Day {n}", "status": "done" if n < 3 else "active",
                  "defects": [], "relabel": None, "worked": None} for n in (1, 2, 3)],
        "meta": {"project": "toy", "caveats": []},
        "plan": plan,
    }  # fmt: skip


PLAN_LONG = "What the driver needs from the kit, and what it reads"
SLANT = math.radians(52)


def slanted_corners(words, transform):
    """The four corners of a slanted section name's box: it ends at its foot and runs down to the left, 5.8 px a
    letter, 8 px tall across its slant, as the page estimates it."""
    m = re.match(r"translate\(([-\d.]+) ([-\d.]+)\)", transform)
    fx, fy = float(m.group(1)), float(m.group(2))
    n = len(words) * 5.8
    sx, sy = fx - n * math.cos(SLANT), fy + n * math.sin(SLANT)
    ux, uy = -8 * math.sin(SLANT), -8 * math.cos(SLANT)
    return [(fx, fy), (sx, sy), (fx + ux, fy + uy), (sx + ux, sy + uy)]


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

# ringDraw() or readingDraw() alone on the same document, for working out where each text's box falls: every text
# it drew, as [class, x, y, anchor, words with a tspan's own, whether it holds a tspan]; every lead, as [class, d];
# each stop's gate on the ring, as [its key, the angle it is turned to]; the words of the ring's facts; and the d of
# each stop sign's cap on the reading.
TEXTS = (
    RING[: RING.index("console.log(")]
    + r"""console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const all = n => [n, ...(n.kids || []).filter(k => k && typeof k === "object").flatMap(all)];
  const words = n => typeof n === "string" ? n : [n.textContent, ...(n.kids || []).map(words)].join("");
  const M = model(DATA), which = DATA.draw, fig = $(which + "-fig"), has = (e, c) => ((e.attrs && e.attrs.class) || "").split(" ").includes(c);
  if (which === "whr") ringDraw(M.whr, $, [], () => {}); else readingDraw(M.rdg, $, []);
  ({ texts: all(fig).filter(e => e.tag === "text").map(e => [e.attrs.class || "", +e.attrs.x, +e.attrs.y,
       e.attrs["text-anchor"] || "start", words(e), e.kids.some(k => k && k.tag === "tspan")]),
     leads: all(fig).filter(e => e.tag === "path" && has(e, "lead")).map(e => [e.attrs.class, e.attrs.d]),
     gates: all(fig).filter(e => /^s\\d+$/.test(e.attrs["data-k"] || "")).map(e => [e.attrs["data-k"], parseFloat(/rotate\\(([-\\d.]+)/.exec(e.attrs.transform)[1])]),
     facts: words($("whr-facts")).replace(/\\s+/g, " "),
     caps: all(fig).filter(e => e.tag === "path" && has(e, "termcap")).map(e => e.attrs.d) })`, ctx)));
"""
)


def path_points(d):
    """The corners of a path of M, L, H and V steps, absolute, as [(x, y)]."""
    out, x, y = [], 0.0, 0.0
    for cmd, args in re.findall(r"([MLHV])\s*([-\d.\s,]*)", d):
        nums = [float(v) for v in re.findall(r"-?[\d.]+", args)]
        if cmd in "ML":
            x, y = nums[0], nums[1]
        elif cmd == "H":
            x = nums[0]
        else:
            y = nums[0]
        out.append((x, y))
    return out


def through(points, box):
    """Whether the polyline runs inside the box (its edges shrunk by half a pixel), sampled every half pixel."""
    x0, x1, y0, y1 = box[0] + 0.5, box[1] - 0.5, box[2] + 0.5, box[3] - 0.5
    for (ax, ay), (bx, by) in itertools.pairwise(points):
        n = max(1, int(max(abs(bx - ax), abs(by - ay)) * 2))
        for k in range(n + 1):
            px, py = ax + (bx - ax) * k / n, ay + (by - ay) * k / n
            if x0 < px < x1 and y0 < py < y1:
                return True
    return False


def crossing(a, b):
    """Whether two polylines cross."""

    def turn(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    for p1, p2 in itertools.pairwise(a):
        for q1, q2 in itertools.pairwise(b):
            d1, d2 = turn(q1, q2, p1), turn(q1, q2, p2)
            d3, d4 = turn(p1, p2, q1), turn(p1, p2, q2)
            if d1 * d2 < 0 and d3 * d4 < 0:
                return True
    return False


def ring_nothing_closed():
    """ring_data_left with no Day closed: the work stands before Day 1, at the top of the ring, beside the first
    phase's name."""
    data = ring_data_left()
    for d in data["days"]:
        d["status"] = "ready"
    data["score"]["days"] = {}
    data["where_ring"] = load("spec_drift_views", "spec_drift_views.py").where_ring(data)
    return data


def text_box(t, per):
    """A text's box, by a rough width of `per` px a character, as the page estimates it: (x0, x1, y0, y1)."""
    _, x, y, anchor, words, _ = t
    w = len(words) * per
    x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
    return (x0, x0 + w, y - 10, y + 4)


def overlapping(boxes):
    """The pairs of boxes that overlap, as their words, sorted."""
    out = []
    for i, (a, wa) in enumerate(boxes):
        for b, wb in boxes[i + 1 :]:
            if a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]:
                out.append(sorted([wa, wb]))
    return sorted(out)


def ring_data_left():
    """The live plan's shape: twenty Days in five phases, stops after Days 2, 8 and 14 lifted and after Day 18 ahead,
    Days 1 to 15 closed and the work between Days 15 and 16. The stop after Day 14 then falls on the ring's left
    side, just under where the work stands."""
    data = ring_data()
    phases = [([1, 2], 2, True), (list(range(3, 9)), 8, True), (list(range(9, 15)), 14, True)]
    phases += [([15, 16, 17, 18], 18, False)]
    rows = [
        {"phase": p, "days": ds, "stop": s, "lifted": up, "from_day": None, "cut": False}
        for p, (ds, s, up) in enumerate(phases)
    ]
    rows.append(
        {"phase": 4, "days": [], "stop": None, "lifted": False, "from_day": 19, "cut": False}
    )
    kinds = [
        {"number": n, "kind": k, "title": "t"} for n, k in enumerate(("spec", "code", "close"))
    ]
    data["days"] = [
        {
            "day": n,
            "status": "done",
            "phase": next(p for p, (ds, _, _) in enumerate(phases) if n in ds),
            "title": f"Day {n}",
            "criteria": {"total": 2, "ticked": 2},
            "prs": kinds,
        }
        for n in range(1, 16)
    ]
    data["order"] = list(range(1, 19))
    data["criteria_index"] = []
    data["now"]["stop_after"] = 18
    data["now"]["next_step"] = "Day 16: write its day spec (plan.md lists it, specs/ has none)"
    names = ["The dry run", "Level 1: the driver starts steps, the maintainer merges"]
    names += ["Level 2: the driver merges", "Level 3: phases chain", "The Telegram remote"]
    data["meta"]["phases"] = names
    data["meta"]["where"] = {"rows": rows, "names": {}}
    data["score"]["days"] = {
        str(n): {"score": 90.0, "low": "proof", "parts": [{"key": "proof", "name": "Proven"}]}
        for n in range(1, 16)
    }
    data["where_ring"] = load("spec_drift_views", "spec_drift_views.py").where_ring(data)
    return data


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

    def test_no_label_beside_the_ring_overlaps_another_or_the_ring(self):
        # the ring's labels at its sides (each line of them) clear of the disc, of each other and of the phase names
        # along its top (the texts with a tspan); the disc runs out to the outer edge of the phase arcs: radius 146,
        # half of a 3.5 px stroke more. With nothing closed the work stands at the top, beside the first phase's name.
        for name, data in (("left", ring_data_left()), ("top", ring_nothing_closed())):
            texts = self.drawn(dict(data, draw="whr"), TEXTS)["texts"]
            classes = ("t-gate", "t-now", "t-ph", "t-sub")
            side = [t for t in texts if t[0] in classes and t[3] in ("start", "end") and not t[5]]
            self.assertGreater(len(side), 6)
            boxes = [(text_box(t, 6.3), t[4]) for t in side]
            inside = []
            for (x0, x1, y0, y1), words in boxes:
                dx, dy = max(x0 - 280, 0, 280 - x1), max(y0 - 168, 0, 168 - y1)
                if dx * dx + dy * dy < 148 * 148:
                    inside.append(words)
            tops = [(text_box(t, 6.3), t[4]) for t in texts if t[5]]
            self.assertEqual(len(tops), 2)
            near = [
                p
                for p in overlapping(boxes + tops)
                if not all(w in [t[4] for t in texts if t[5]] for w in p)
            ]
            self.assertEqual((name, sorted(inside), near), (name, [], []))

    def test_a_stops_label_keeps_a_lead_to_its_gate_wherever_it_went(self):
        # a gate stands turned to its angle, its label's lead ends 155 px out from the ring's middle along it
        got = self.drawn(dict(ring_data_left(), draw="whr"), TEXTS)
        self.assertEqual(sorted(k for k, _ in got["gates"]), ["s14", "s18", "s2", "s8"])
        ends = [path_points(d)[-1] for _, d in got["leads"]]
        missing = []
        for k, a in got["gates"]:
            px, py = 280 + 155 * math.sin(math.radians(a)), 168 - 155 * math.cos(math.radians(a))
            if not any(abs(x - px) < 0.2 and abs(y - py) < 0.2 for x, y in ends):
                missing.append(k)
        self.assertEqual((len(got["leads"]), sorted(missing)), (4, []))

    def test_the_rings_score_says_the_days_own_scores_average_apart(self):
        data = dict(ring_data_left(), draw="whr")
        data["score"] = dict(data["score"], days_mean=87)
        facts = self.drawn(data, TEXTS)["facts"]
        said = "Score so far90 of 100, the finished Days together; their own scores average 87"
        self.assertEqual((facts.count("average"), said in facts), (1, True))
        del data["score"]["days_mean"]
        facts = self.drawn(data, TEXTS)["facts"]
        said = "Score so far90 of 100, the finished Days together"
        self.assertEqual((facts.count("average"), said in facts), (0, True))

    def test_the_labels_over_the_readings_right_end_do_not_overlap(self):
        # ring_data's stop after Day 2 was lifted at the merge just before today's
        data = ring_data()
        views = load("spec_drift_views", "spec_drift_views.py")
        data["where_ring"], data["reading"] = views.where_ring(data), views.reading(data)
        self.assertEqual(data["reading"]["lifted"][0]["at"], len(data["rows"]) - 2)
        self.assertEqual(overlapping(self.top_labels(data)[0]), [])

    def top_labels(self, data):
        """The reading's top labels as [(box, words)], and its leads as [(words of the label it starts at, its
        corners)]: a lead belongs to the label whose box its first corner touches."""
        got = self.drawn(dict(data, draw="rdg"), TEXTS)
        top = [t for t in got["texts"] if "t-top" in t[0].split()]
        boxes = [(text_box(t, 6.4 if "strong" in t[0] else 6.0), t[4]) for t in top]
        leads = []
        for _, d in got["leads"]:
            pts = path_points(d)
            (x, y), whose = pts[0], None
            for (x0, x1, y0, y1), words in boxes:
                if x0 - 3 <= x <= x1 + 3 and y0 - 1 <= y <= y1 + 6:
                    whose = words
            leads.append((whose, pts))
        return boxes, leads

    def reading_data(self, lifted=()):
        """ring_data's reading, with more stops lifted at the merges given (a Day each, counted down from 9)."""
        data = ring_data()
        views = load("spec_drift_views", "spec_drift_views.py")
        data["where_ring"], data["reading"] = views.where_ring(data), views.reading(data)
        data["reading"]["lifted"] += [
            {"day": 9 - k, "at": at, "between": 0} for k, at in enumerate(lifted)
        ]
        return data

    def test_every_label_over_the_reading_keeps_a_lead_and_none_runs_through_another(self):
        # ring_data's stop after Day 2 lifted at the merge before today's, and a crowded one: one more lifted two
        # merges before that. Each label has one lead from its own box; no lead runs through another label or
        # crosses another lead; the next stop's label stands on the upper row, at the right edge, over today's.
        for name, data in (("plain", self.reading_data()), ("crowded", self.reading_data([9]))):
            boxes, leads = self.top_labels(data)
            mine = sorted(w for w, _ in leads)
            self.assertEqual(
                (name, len(mine), mine == sorted(w for _, w in boxes)), (name, len(boxes), True)
            )
            through_other = sorted(
                [w, words]
                for w, pts in leads
                for box, words in boxes
                if words != w and through(pts, box)
            )
            crossed = sorted(
                sorted([a[0], b[0]])
                for i, a in enumerate(leads)
                for b in leads[i + 1 :]
                if crossing(a[1], b[1])
            )
            self.assertEqual((name, through_other, crossed), (name, [], []))
            stop = next(b for b, w in boxes if w.startswith("the next stop"))
            today = next(b for b, w in boxes if w.startswith("today"))
            self.assertEqual((name, stop[3] <= today[2], round(stop[1])), (name, True, 1238))

    def test_crowded_labels_over_the_reading_stay_near_their_marks(self):
        # two lifted stops and today within three merges: one goes up a row rather than far along one; each label's
        # lead runs at most 170 px along, but the next stop's, whose label ends at the right edge
        boxes, leads = self.top_labels(self.reading_data([9]))
        near = [(w, p) for w, p in leads if not w.startswith("the next stop")]
        far = sorted(w for w, pts in near if abs(pts[0][0] - pts[-1][0]) > 170)
        rows = sorted({round(b[2]) for b, w in boxes if not w.startswith("the next stop")})
        self.assertEqual((far, len(rows)), ([], 2))

    def full_strand(self, later_phase):
        # ring_data with 40 more merges of Day 2, so the strand fills the picture; [the cap's right end, the next
        # stop's label]. Without the phase that has no number yet the cap ends 4 px short of the picture's right
        # edge, as on the real page; with it, that phase's 56 px stand between the cap and the edge.
        data = ring_data()
        if not later_phase:
            data["meta"]["where"]["rows"] = data["meta"]["where"]["rows"][:2]
        last = data["look_ahead"]["columns"][-1]
        for i in range(len(data["rows"]), len(data["rows"]) + 40):
            data["rows"].append(
                dict(data["rows"][-1], i=i, pr=i, title=f"PR {i}", kind="code", own_day=2)
            )
            data["look_ahead"]["columns"].append(dict(last, pr=i, got=[]))
        views = load("spec_drift_views", "spec_drift_views.py")
        data["where_ring"], data["reading"] = views.where_ring(data), views.reading(data)
        got = self.drawn(dict(data, draw="rdg"), TEXTS)
        self.assertEqual(len(got["caps"]), 1)
        stop = [t for t in got["texts"] if t[4].startswith("the next stop")]
        self.assertEqual(len(stop), 1)
        return float(re.match(r"M([-\d.]+)", got["caps"][0]).group(1)) + 18, stop[0]

    def test_the_next_stops_label_ends_with_its_sign_at_the_pictures_right_end(self):
        cap_end, stop = self.full_strand(later_phase=False)
        self.assertEqual(cap_end, 1234.0)
        self.assertEqual((stop[3], float(stop[1])), ("end", cap_end))

    def test_the_next_stops_label_stays_at_the_edge_when_a_later_phase_stands_past_its_sign(self):
        # the sign is 60 px from the edge, the later phase between them: the label keeps the edge, over that phase
        cap_end, stop = self.full_strand(later_phase=True)
        self.assertEqual(cap_end, 1178.0)
        self.assertEqual((stop[3], float(stop[1])), ("end", 1238.0))

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
    "track-reviewer",
    "seen red",
    "break on purpose",
    "review",
    "CI",
    "driver reviewer",
    "work",
    "close",
    "rehearsal",
    "evidence replay",
    "dashboard",
    "Day review",
]
OLD_DEMO = {
    # the demo's Days end before Day 16, so CI and the driver's reviewer catch none of its defects
    "caught": [1] * 6 + [0, 0] + [1] * 6,
    "layers": [2, 5, 2, 3],
    "per": {
        "auditor": "$2.40",
        "seen red": "$3.60",
        "break on purpose": "$5.60",
        "evidence replay": "$2.00",
    },
}
OLD_FIXTURE = {
    "caught": [3, 0, 0, 1, 0, 0, 0, 0, 2, 0, 0, 1, 0, 1],
    "layers": [3, 3, 0, 2],
    "per": {"auditor": "$1.50"},
}
# never_found's figures for the metrics test's Days, written by hand with the keys the page reads
PRF_NEVER = {
    "left": 12,
    "low": 4,
    "high": 32,
    "estimated": 2,
    "exact": 2,
    "catchable_from": 16,
    "reviewer_from": 13,
    "agents": [
        {
            "agent": "spec-auditor",
            "estimated": True,
            "caught": 31,
            "named": 30,
            "of": 44,
            "hit_pct": 68,
            "missed": 14,
            "later": 4,
            "left": 10,
            "why": None,
        },
        {
            "agent": "track-reviewer",
            "estimated": True,
            "caught": 4,
            "named": 9,
            "of": 21,
            "hit_pct": 43,
            "missed": 5,
            "later": 3,
            "left": 2,
            "why": None,
        },
    ],
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
        keys = [g["key"] for g in p["gates"]]
        # the missing keys first: a list short enough for a report to hold whole
        self.assertEqual([k for k in GATE_KEYS if k not in keys], [])
        self.assertEqual(keys, GATE_KEYS)
        f = self.prf(prf_data())
        # field by field, gate by gate: a short report break.py can record (unittest shortens long dicts)
        for got, old in ((self.counts(p), OLD_DEMO), (self.counts(f), OLD_FIXTURE)):
            self.assertEqual(got["caught"], old["caught"])
            self.assertEqual(got["layers"], old["layers"])
            for k in sorted(set(got["per"]) | set(old["per"])):
                self.assertEqual(got["per"].get(k), old["per"].get(k), f"cost per catch at {k}")
        self.assertEqual(f["late"], [2])
        self.assertEqual((f["total"], [x["reached"] for x in f["layers"]]), (8, [8, 5, 2, 2]))

    def test_a_layers_rate_counts_its_gates_and_not_what_was_only_noticed(self):
        p = self.prf(prf_data())
        self.assertEqual(keys_in(p["layers"], ("leak", "gated", "gated_pct")), [True] * 4)
        self.assertEqual([x["leak"] for x in p["layers"]], [0, 2, 0, 0])
        self.assertEqual([x["gated"] == x["caught"] - x["leak"] for x in p["layers"]], [True] * 4)
        layer = p["layers"][1]
        self.assertEqual(
            (layer["caught"], layer["leak"], layer["gated"], layer["gated_pct"]), (3, 2, 1, 20)
        )

    def test_a_gate_with_no_run_on_record_has_no_cost(self):
        data = prf_data()
        row = next(g for g in data["gate_report"]["gates"] if g["found"])
        row.update(runs=0, cost=0)
        gates = {g["key"]: g for g in self.prf(data)["gates"]}
        self.assertIn(row["found"], sorted(gates))
        g = gates[row["found"]]
        self.assertEqual((g["runs"], g["cost"], g["per"]), (None, None, None))

    def test_the_gate_a_found_value_names_is_graph_7s_rule(self):
        gate_of = load("spec_drift_views", "spec_drift_views.py").gate_of
        cases = {
            "day 3 review": "Day review",
            "Day 12 review": "Day review",
            "the auditor (plan)": "auditor",
            "The spec-change PR": "spec-change PR",
            "Track B": "work",
            "track-reviewer": "track-reviewer",
            "Track-reviewer (the brief)": "track-reviewer",
            "self": "work",
            "work": "work",
            "a reviewer nobody named": "work",
            None: "work",
        }
        for k, want in cases.items():
            self.assertEqual(gate_of(k), want, f"found: {k}")

    def test_ci_and_the_drivers_reviewer_are_gates_from_day_16_and_the_work_before(self):
        gate_of = load("spec_drift_views", "spec_drift_views.py").gate_of
        self.assertEqual(gate_of("CI"), "CI")
        self.assertEqual(gate_of("driver reviewer"), "driver reviewer")
        self.assertEqual(gate_of("ci", 16), "CI")
        self.assertEqual(gate_of("Driver reviewer", 16), "driver reviewer")
        self.assertEqual(gate_of("CI", 15), "work")
        self.assertEqual(gate_of("driver reviewer", 15), "work")
        self.assertEqual(gate_of("reviewer", 16), "work")

    def test_the_stream_counts_ci_and_the_drivers_reviewer_as_gates_of_the_second_layer(self):
        def defect(i, found):
            return {
                "id": i,
                "found": found,
                "cause": "process",
                "made": None,
                "same_as": None,
                "problem": None,
            }

        data = prf_data()
        data["days"] = [
            {"day": 15, "status": "done", "defects": [defect("D15.1", "CI")]},
            {
                "day": 16,
                "status": "done",
                "defects": [
                    defect("D16.1", "CI"),
                    defect("D16.2", "driver reviewer"),
                    defect("D16.3", "self"),
                ],
            },
        ]
        p = self.prf(data)
        keys = [g["key"] for g in p["gates"]]
        self.assertIn("CI", keys)
        at = keys.index("CI")
        self.assertEqual(keys[at - 1 : at + 3], ["review", "CI", "driver reviewer", "work"])
        gates = {g["key"]: g for g in p["gates"]}
        self.assertEqual(
            [(gates[k]["layer"], gates[k]["caught"]) for k in ("CI", "driver reviewer")],
            [(1, 1), (1, 1)],
        )
        self.assertEqual(gates["work"]["caught"], 2)
        layer = next(x for x in p["layers"] if x["name"] == "While writing")
        self.assertEqual((layer["caught"], layer["leak"], layer["gated"]), (4, 2, 2))
        self.assertEqual((p["ci"]["from_day"], p["ci"]["caught"]), (16, 1))
        self.assertEqual(gates["driver reviewer"]["none"], "none yet: on driver runs only")

    def test_a_repeat_caught_by_ci_or_the_drivers_reviewer_is_caught_by_a_gate_before_the_close(
        self,
    ):
        views = load("spec_drift_views", "spec_drift_views.py")
        new = ["CI", "driver reviewer"]
        self.assertEqual([k for k in new if k in views.LRN_GATED], new)

    def test_the_stream_carries_the_estimate_of_defects_never_found(self):
        never = {"left": 12, "low": 4, "high": 32}
        self.assertEqual(self.prf(dict(prf_data(), never_found=never)).get("never"), never)
        self.assertIsNone(self.prf(prf_data()).get("never"))

    def test_came_back_and_after_the_merge_are_two_sets_and_what_they_share_is_counted(self):
        m = self.prf(prf_data())["marks"]
        self.assertEqual((m["back"]["n"], m["after_merge"], m["shared"]), (2, 2, 1))
        self.assertEqual((m["escaped"]["n"], m["both"]), (1, 1))
        self.assertEqual(m["back"]["layers"], [1, 0, 0, 1])

    def test_with_the_data_branch_or_its_gates_json_missing_there_is_no_stream(self):
        for data in (prf_data(commit=None), prf_data(absent=["gates.json"])):
            p = self.prf(data)
            self.assertTrue("empty" in p, "the stream would be drawn")
            self.assertEqual([g["cost"] for g in p["gates"]], [None] * 14)
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
        want = {"dots": p["total"], "grps": 14, "lays": 4, "hooks": len(guards), "marks": 2}
        self.assertEqual({k: out["prf"][k] for k in want}, want)
        self.assertEqual(p["total"], 12)
        self.assertEqual(out["onDay"], 1)  # it hooks into the page's Day buttons

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_past_every_layer_the_stream_says_the_estimate_and_its_range(self):
        out = {
            "agent": "plan-auditor",
            "estimated": False,
            "why": "no recorded count on known cases",
        }
        never = dict(PRF_NEVER, agents=[*PRF_NEVER["agents"], out])
        words = prf_node(with_prf(dict(prf_data(), never_found=never)))["prf"]["words"]
        for s in (
            "about 12 never found",
            "an estimate: 4 to 32",
            "agents miss on faults known",
            "About 12 were never found.",
            "between 4 and 32",
            "names 30 of 44 known faults at worst (68%)",
            "missed about 14",
            "later checks found 4 of them, which leaves about 10",
            "names 9 of 21",
            "The plan-auditor is not in it: no recorded count on known cases.",
            "It leans high",
            "is counted under each",
            "(every line from Day 16), 2 so far",
            "from Day 13 is the track-reviewer's",
        ):
            self.assertTrue(
                s in words, s
            )  # the words are 6,000 characters: the message names the one missing
        self.assertNotIn("left in the count", words)
        words = prf_node(
            with_prf(dict(prf_data(), never_found=dict(PRF_NEVER, left=None, agents=[out])))
        )["prf"]["words"]
        for s in (
            "never found: not estimated",
            "What nobody found is not estimated.",
            "The plan-auditor: no recorded count on known cases.",
        ):
            self.assertTrue(s in words, s)
        self.assertNotIn("were never found.", words)
        words = prf_node(with_prf(prf_data()))["prf"]["words"]
        self.assertIn("never found: not estimated", words)
        self.assertNotIn("What nobody found is not estimated.", words)

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_the_stream_says_ci_is_a_gate_from_day_16(self):
        words = prf_node(with_prf(prf_data()))["prf"]["words"]
        said = "From Day 16 CI is a gate in the stream (found: CI in the Notes), with 0 so far"
        self.assertTrue(said in words, said)
        self.assertNotIn("CI is not in the stream", words)

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_an_empty_tray_of_the_drivers_reviewer_says_why(self):
        words = prf_node(with_prf(prf_data()))["prf"]["words"]
        for s in ("none yet: on driver runs only", "none in the Notes yet"):
            self.assertTrue(s in words, s)

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_the_stream_labels_came_back_and_after_the_merge_apart_and_says_what_they_share(self):
        words = prf_node(with_prf(prf_data()))["prf"]["words"]
        self.assertIn("2 came back.", words)
        self.assertIn("They are not the 2 caught after the merge: the two sets share 1.", words)
        self.assertIn("Days merged by the count", words)

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_a_layers_label_says_gates_and_the_last_layer_gives_no_rate(self):
        data = with_prf(prf_data())
        layers = data["proofreading"]["layers"]
        self.assertEqual(len(layers), 4)
        # the second layer: 5 reached it, the gates caught 1 and 2 more were only noticed in the work
        self.assertEqual((layers[1]["reached"], layers[1]["gated"]), (5, 1))
        last = layers[-1]
        self.assertEqual(last["caught"], last["reached"])
        words = prf_node(data)["prf"]["words"]
        self.assertIn("gates catch 1 of 5 · 20%", words)
        self.assertIn(f"finds the last {last['caught']}: no rate", words)
        self.assertNotIn(f"catches {last['caught']} of {last['reached']} · 100%", words)

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_without_the_data_branch_the_stream_draws_nothing_and_the_banner_says_so(self):
        for data in (prf_data(commit=None), prf_data(absent=["gates.json"])):
            out = prf_node(with_prf(data))
            self.assertEqual(
                (out["prf"]["dots"], out["prf"]["grps"], out["prf"]["drops"]), (0, 0, 0)
            )
            self.assertIn("The error-correction stream is not drawn.", out["missing"])
            # graph 7 still puts each defect at its gate, with no gate's cost
            self.assertEqual(out["g7"]["phases"], OLD_FIXTURE["layers"])
            self.assertEqual([g[2] for g in out["g7"]["gates"]], [None] * 14)
            self.assertFalse(any("run" in s for s in out["g7"]["subs"]), out["g7"]["subs"])

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_the_stream_reconciles_with_graph_7_on_demo_data(self):
        reconcile = load("dashboard_reconcile", "dashboard-reconcile.py")
        agree, line = reconcile.prf_line(reconcile.model(demo_data.demo()))
        self.assertTrue(agree, line)
        self.assertRegex(
            line, r"^proofreading: 12 defects, layers 2/5/2/3, .* \| graph 7: .*: agree$"
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


def parts_data():
    """budget_data()'s five rows as token-usage.py places them, and four more on 3 Jan. The
    auditor's row on main is Day 1's (its session worked on Day 1's branch), the main session's
    with no price is the dashboard's; the new ones stayed on main, or were on a plan branch, a
    tooling branch and Day 3's. Days 1 and 2 are closed, Day 3 is open."""
    data = budget_data()
    rows = data["tokens"]
    placed = (("day", 1), ("day", 1), ("day", 2), ("dashboard", None), ("day", 2))
    for row, (part, day) in zip(rows, placed):
        row.update(part=part, part_day=day)
    more = (("main", None, 1.5), ("plan", None, 0.5), ("tooling", None, 0.25), ("day", 3, 1.0))
    rows += [
        {
            "date": "2026-01-03",
            "day": day,
            "agent": "main",
            "model": "claude-opus-5-5",
            "cost": cost,
            "replies": 1,
            "part": part,
            "part_day": day,
        }
        for part, day, cost in more
    ]
    data["days"][1]["status"] = "done"
    data["days"].append({"day": 3, "status": "active", "worked": ["2026-01-03", "2026-01-03"]})
    return data


class BudgetTest(unittest.TestCase):
    """budget(): graph 8's dollars as beads of $2, placed on the Days and on the parts between
    them, by Day and by date."""

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
        for data, beads in ((budget_data(), 6), (parts_data(), 7)):
            b = self.budget(data)
            self.assertEqual(b["beads"], beads)
            by_date = b["cols"]["date"]
            by_day = b["cols"]["day"] + b["cols"]["between"]
            for view, cols in (("date", by_date), ("day", by_day)):
                self.assertEqual(sum(c["b"] for c in cols), beads, view)
                self.assertEqual([c["label"] for c in cols if abs(c["b"] - c["u"] / 2) >= 1], [])
            self.assertEqual([c["label"] for c in by_date if sum(c["pb"]) != c["b"]], [])
        self.assertEqual([c["b"] for c in self.budget(budget_data())["cols"]["date"]], [1, 4, 1])

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

    def test_a_row_counted_before_the_parts_is_its_days_or_is_not_placed(self):
        cols = self.budget(budget_data())["cols"]
        self.assertEqual([(c["day"], c["b"]) for c in cols["day"]], [(1, 1), (2, 3)])
        rest = [(c["label"], c["b"], round(c["u"], 2)) for c in cols["between"]]
        self.assertEqual(rest, [("not placed", 2, 4.02)])

    def test_a_reply_on_main_counts_to_the_day_its_session_worked_on(self):
        b = self.budget(parts_data())
        got = [
            (c["day"], round(c["u"], 2), round(c["own"], 2), round(c["home"], 2))
            for c in b["cols"]["day"]
        ]
        self.assertEqual(got, [(1, 2.23, 1.21, 1.02), (2, 6.0, 6.0, 0.0), (3, 1.0, 1.0, 0.0)])
        self.assertEqual([round(b[k], 2) for k in ("on_days", "own", "home")], [9.23, 8.21, 1.02])
        self.assertEqual((b["on_days_pct"], b["between_pct"]), (64, 36))

    def test_the_work_between_days_is_a_block_for_each_part(self):
        b = self.budget(parts_data())
        rest = b["cols"]["between"]
        # short lists, one figure each: a failure prints whole, with nothing unittest shortens
        self.assertEqual([c["b"] for c in rest], [1, 0, 0, 1])
        self.assertEqual([round(c["u"], 2) for c in rest], [3.0, 0.25, 0.5, 1.5])
        self.assertEqual([c["part"] for c in rest], [1, 2, 3, 4])
        self.assertEqual([c["label"] for c in rest[:2]], ["dashboard", "tooling"])
        self.assertEqual([c["label"] for c in rest[2:]], ["other branches", "stayed on main"])
        self.assertEqual([round(x, 2) for x in b["parts"]], [9.23, 3.0, 0.25, 0.5, 1.5, 0])
        self.assertEqual(b["part_pct"], [64, 21, 2, 3, 10, 0])
        self.assertEqual(round(b["between"], 2), 5.25)

    def test_the_average_day_is_the_mean_of_the_closed_days(self):
        b = self.budget(parts_data())
        self.assertEqual(
            (round(b["mean"], 3), round(b["median"], 3), b["mean_over"]), (4.115, 4.115, 2)
        )
        self.assertEqual((b["cheap_day"], b["dear_day"]), (0, 1))
        over = [c["over"] if c["over"] is None else round(c["over"], 3) for c in b["cols"]["day"]]
        self.assertEqual(over, [-1.885, 1.885, None])
        self.assertEqual(round(b["per_closed"], 2), 7.24)  # every dollar over the 2 closed Days
        # with no Day closed there is no average, and no Day is over or under it
        data = parts_data()
        for day in data["days"]:
            day["status"] = "active"
        b = self.budget(data)
        self.assertEqual(
            (b["mean"], b["median"], b["mean_over"], b["dear_day"]), (None, None, 0, None)
        )
        self.assertEqual([c["over"] for c in b["cols"]["day"]], [None, None, None])

    def test_a_dates_beads_are_shared_out_over_its_parts(self):
        cols = self.budget(parts_data())["cols"]["date"]
        self.assertEqual([c["b"] for c in cols], [1, 3, 3])
        beads = [c["pb"] for c in cols]
        self.assertEqual(beads, [[1, 0, 0, 0, 0, 0], [2, 1, 0, 0, 0, 0], [2, 0, 0, 0, 1, 0]])
        self.assertEqual([round(x, 2) for x in cols[2]["pt"]], [3.0, 0, 0.25, 0.5, 1.5, 0])

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
        # the replay says these lines at its Park beat: a park is where the step parked and went on, not a climb
        self.assertEqual(
            [r["tips"]["s2p0"]["l"][0].split(". ")[1], r["tips"]["s2p0"]["l"][1][:24]],
            ["It parked after session 1 of 2, which crashed.", "It went on at session 2:"],
        )
        self.assertEqual(
            r["tips"]["s2p0"]["l"],
            [
                "The driver or the kit was at fault. It parked after session 1 of 2, which crashed.",
                "It went on at session 2: the next session started 5 minutes later.",
                "How long a person was needed is not known: the park names no issue.",
            ],
        )
        self.assertEqual(
            r["tips"]["s3p0"]["l"][:2],
            [
                "A decision that is the maintainer's. It parked before any session ran.",
                "It did not go on: no session started after it in this step.",
            ],
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

    def test_each_step_has_its_kind_from_its_branch_prefix(self):
        prefixes = [
            "day-20/spec",
            "day-21/spec-the-premise",
            "day-13/track-a",
            "day-13/close-the-day",
            "review",
            None,
            "hotfix/x",
            "day-13/close-other",
            "day-13/spec-x",
            "day-13/track-a/b",
        ]
        data = runs_data()
        data["driver_runs"]["steps"] = [
            {
                "step": f"Step {i}.",
                "day": 13,
                "prefix": p,
                "sessions": [],
                "parks": [],
                "pr": None,
                "ended": "open",
            }
            for i, p in enumerate(prefixes)
        ]
        rows = self.views().reflex(data)["rows"]
        self.assertEqual(len(rows), 10)
        # only the close's own branch is a close, and a track's branch has one part after the Day
        self.assertEqual(
            [r.get("kind") for r in rows],
            ["spec", "spec", "track", "close", "review", "none", "none", "none", "spec", "none"],
        )


# rfxDraw() from dashboard.js on the data from stdin, on a document that keeps every node it makes: the figures,
# the trial for level 2's boxes and its label, and the folded lists.
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
  if (!R.empty && !R.error) rfxDraw(R, $);
  ({ empty: R.empty || null, error: R.error || null, figs: $("rfx-figs").kids.length, finds: $("rfx-finds").kids.length,
     bends: $("rfx-bends").kids.length, aria: $("rfx-cell-host").attrs["aria-label"] || null,
     trial: { boxes: is("box").length, run: is("box").filter(e => e.attrs.class.split(" ").includes("run")).length,
       label: $("rfx-l2").attrs["aria-label"] || null, hidden: $("rfx-l2").hidden,
       key: [$("rfx-l2-k").hidden, $("rfx-l2-of").textContent || null] } })`, ctx)));
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

    def test_the_figures_and_the_folded_lists_are_drawn_for_every_step(self):
        v = load("spec_drift_views", "spec_drift_views.py")
        for data in (demo_data.demo(), runs_data()):
            data["reflex"] = r = v.reflex(data)
            got = self.draw(data)
            self.assertEqual(
                [got["figs"], got["finds"], got["bends"]],
                [len(r["figs"]), len(r["finds"]), len(r["bends"])],
            )
            # the cell's host is named by the sentence reflex() made for it
            self.assertEqual(got["aria"] == r["aria"], True)
        self.assertEqual(got["figs"], 4)

    def test_the_trial_for_level_2_is_a_box_for_each_pull_request_it_asks_for(self):
        v = load("spec_drift_views", "spec_drift_views.py")
        got = []
        for l2 in ({"run": 17, "of": 15}, {"run": 3, "of": 5}, None, {"run": 2, "of": 0}):
            data = runs_data()
            data["driver_runs"]["level_2"] = l2
            data["reflex"] = v.reflex(data)
            got.append(self.draw(data)["trial"])
        # more pull requests in a row than the plan asks for fill every box; no trial, or one that asks for
        # none, draws no bar
        self.assertEqual(
            [[t["boxes"], t["run"], t["hidden"]] for t in got],
            [[15, 15, False], [5, 3, False], [0, 0, True], [0, 0, True]],
        )
        self.assertEqual(
            [t["label"] for t in got],
            [
                "Trial for level 2: 17 of 15 in a row",
                "Trial for level 2: 3 of 5 in a row",
                None,
                None,
            ],
        )
        # the fold's key says how many the trial asks for, and with no trial it names none
        self.assertEqual(
            [t["key"] for t in got],
            [[False, "15"], [False, "5"], [True, None], [True, None]],
        )

    def test_with_the_run_log_missing_nothing_is_drawn(self):
        data = runs_data(absent=["driver-runs.json"])
        data["reflex"] = load("spec_drift_views", "spec_drift_views.py").reflex(data)
        got = self.draw(data)
        self.assertEqual(
            [got["empty"], got["figs"], got["trial"]["boxes"]],
            [
                "the dashboard-data branch has no driver-runs.json, so no step of the driver is drawn.",
                0,
                0,
            ],
        )

    def test_the_reflex_reconciles_with_the_proteins(self):
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
                    "5, 2, 1, 1: agree"
                ),
            ),
        )
        line = reconcile.rfx_line(reconcile.model(demo_data.demo()))
        self.assertTrue(line[0], line[1])
        # with no arc drawn, a count of steps by the proteins disagrees
        gone = {**m, "rfx": {"empty": "no step is drawn."}}
        self.assertEqual(
            reconcile.rfx_line(gone),
            (
                False,
                "reflex: not drawn (no step is drawn.) | proteins' real runs: 5 steps: DISAGREE",
            ),
        )


def needs_data():
    """One of each thing the rule reads: today's list (a failing replay, a ticked box with no evidence, a flag on a
    replaced criterion, two criteria whose replay report this build could not read, two expected flags, a hand-off),
    and what each graph already draws (an unticked box, a replaced criterion not holding, criteria and commitments
    never proved, a commitment due, a yardstick above its average, a pull request naming no ability)."""

    def crit(cid, day, state, by=()):
        return {"id": cid, "day": day, "state": state, "replaced_by": list(by)}

    def cell(cid, st, rep=()):
        return {"id": cid, "st": st, "rep": list(rep), "why": "code broken", "lp": 30}

    def gene(pid, cls, uncovered=False):
        return {"id": pid, "cls": cls, "owner_day": 1, "uncovered": uncovered, "settled_by": None}

    def flag(cid, reason, detail, **more):
        return dict(id=cid, reason=reason, detail=detail, **more)

    return {
        "now": {"head": "abc1234def", "last_pr": 30},
        "days": [{"day": 1, "status": "done"}, {"day": 2, "status": "done"}],
        "criteria_index": [
            crit("C1.1", 1, "repair"),
            crit("C1.2", 1, "replaced", ["C2.1"]),
            crit("C1.3", 1, "replaced", ["C2.2"]),
            crit("C1.4", 1, "open"),
            crit("C1.5", 1, "unproven"),
            crit("C1.6", 1, "skipped"),
            crit("C2.1", 2, "proven"),
            crit("C2.2", 2, "proven"),
            crit("C2.3", 2, "proven"),
        ],
        "attention": [
            flag("C1.1", "replay_failed", "break no longer applies at #30: t: 0 times."),
            flag("C2.3", "evidence_missing", "No evidence and PR cited together"),
            flag("C1.3", "test_not_found", "OldTest.test_gone"),
            flag("C2.1", "evidence_missing", "Replay report: absent"),
            flag("C2.2", "evidence_missing", "Replay report: absent"),
            flag("C1.6", "not_breakable", "live", expected=True),
            flag("C1.6", "test_skippable", "LiveTest", expected=True),
            flag("C2.2", "test_skippable", "LiveTest", expected=True),
            flag("H2.1", "handoff_unpicked", "Hand-off H2.1: decide"),
        ],
        "merge_graph": {
            "crit": [
                cell("C1.1", "stale"),
                cell("C1.2", "bad", ["C2.1"]),
                cell("C1.3", "ok", ["C2.2"]),
                cell("C1.4", "due"),
                cell("C1.5", "un"),
                cell("C1.6", "none"),
            ]
        },
        "protein": {
            "chains": [
                {"cells": [{"id": "C1.1", "state": "repair"}, {"id": "C1.4", "state": "open"}]},
                {
                    "cells": [
                        {"id": "C1.5", "state": "unproven"},
                        {"id": "C1.6", "state": "skipped"},
                    ]
                },
            ]
        },
        "gene": {
            "commitments": [
                gene("P01", "unproved"),
                gene("P02", "unreplayable"),
                gene("P03", "untranscribed", uncovered=True),
                gene("P04", "proved"),
            ]
        },
        "gel": {
            "panels": [
                {
                    "name": "Cost",
                    "unit": "$",
                    "decimals": 2,
                    "verdict": "better",
                    "last": {"day": 2, "value": 1.5},
                    "average": 2.0,
                },
                {
                    "name": "Replies",
                    "unit": "",
                    "decimals": 0,
                    "verdict": "worse",
                    "last": {"day": 2, "value": 37},
                    "average": 36.52,
                },
            ]
        },
        "reading": {"opens": [{"id": "H2.1", "to": None}], "gap": [{"id": "C1.4", "d": 1}]},
        "user_stories": {"problems": ["#7 names no ability: add an Ability: line"]},
    }


class NeedsAttentionTest(unittest.TestCase):
    """needs_attention(): the one rule for what is open on the page, counted from the list and the graphs."""

    def needs(self, data=None):
        return load("spec_drift_views", "spec_drift_views.py").needs_attention(data or needs_data())

    def ids(self, got, group):
        return [[x["id"] for x in ln["ids"]] for ln in got["lines"] if ln["group"] == group]

    def test_the_headline_counts_what_is_broken_to_repair_and_waiting(self):
        got = self.needs()
        self.assertEqual(
            [(g["key"], g["n"]) for g in got["groups"]],
            [("broken", 1), ("repair", 5), ("waiting", 1)],
        )
        self.assertEqual((got["count"], got["last_pr"]), (7, 30))
        self.assertEqual(self.ids(got, "broken"), [["C1.1"]])
        self.assertEqual(
            self.ids(got, "repair"), [["C2.3"], ["C1.4"], ["#7"], ["Replies"], ["P03"]]
        )
        self.assertEqual(self.ids(got, "waiting"), [["H2.1"]])
        said = {ln["ids"][0]["id"]: (ln["mark"], ln["text"]) for ln in got["lines"]}
        self.assertEqual(
            said["C1.1"], ("bad", "The replay fails: break no longer applies at #30: t: 0 times.")
        )
        self.assertEqual(said["Replies"], ("rep", "37 on Day 2, above its average so far of 36.5."))
        self.assertEqual(said["P03"], ("due", "Due by Day 1, and no criterion in force names it."))
        self.assertEqual(said["#7"], ("rep", "Names no ability: add an Ability: line."))

    def test_a_replaced_criterion_is_expected_whatever_is_flagged_on_it(self):
        got = self.needs()
        self.assertEqual(self.ids(got, "expected"), [["C1.3"], ["C2.2"], ["C1.2"]])
        said = {
            ln["ids"][0]["id"]: (ln["mark"], ln["text"])
            for ln in got["lines"]
            if ln["group"] == "expected"
        }
        self.assertEqual(
            said["C1.3"],
            ("exp", "Replaced by C2.2. The test it names is not found: OldTest.test_gone."),
        )
        self.assertEqual(
            said["C1.2"],
            (
                "stl",
                "Replaced by C2.1. Its old check stopped holding: code broken when last run, at #30.",
            ),
        )
        self.assertEqual(
            [(f["key"], f["n"]) for f in got["folded"]], [("never", 4), ("expected", 3)]
        )

    def test_never_proved_is_what_the_graphs_count_and_an_id_sits_under_its_worst_mark(self):
        got = self.needs()
        # C1.6 is flagged twice as expected and the abilities graph cannot replay it: once, under never proved
        self.assertEqual(self.ids(got, "never"), [["C1.5"], ["C1.6"], ["P01"], ["P02"]])
        self.assertEqual(sum(x["id"] == "C1.6" for ln in got["lines"] for x in ln["ids"]), 1)
        data = needs_data()
        data["protein"]["chains"][1]["cells"].append({"id": "C2.1", "state": "unproven"})
        data["merge_graph"]["crit"].append({"id": "C2.1", "st": "un", "rep": []})
        self.assertEqual(
            self.ids(self.needs(data), "never")[0], ["C1.5", "C2.1"]
        )  # the same sentence: one line

    def test_a_report_this_build_could_not_read_is_no_problem(self):
        got = self.needs()
        self.assertEqual(got["unread"], [{"text": "Replay report: absent", "n": 2}])
        self.assertNotIn("C2.1", [x["id"] for ln in got["lines"] for x in ln["ids"]])

    def test_a_chip_counts_the_lines_that_name_its_graph_and_a_day_holds_its_marks(self):
        got = self.needs()
        chips = {g: {c["mark"]: c["n"] for c in cs} for g, cs in got["chips"].items()}
        self.assertEqual(
            chips,
            {
                "rdg": {"rep": 1, "hnd": 1},
                "gel": {"rep": 1},
                "prt": {"bad": 1, "rep": 1, "unp": 2},
                "gene": {"due": 1, "unp": 2},
                "g12": {"due": 1},
                "mrg": {"bad": 1, "rep": 1, "unp": 2},
            },
        )
        self.assertEqual(
            [ln["graphs"] for ln in got["lines"] if ln["ids"][0]["id"] in ("C1.4", "C2.3")],
            [[], ["rdg", "prt", "mrg"]],
        )
        self.assertEqual(
            [(x["day"], x["n"], [m["mark"] for m in x["marks"]]) for x in got["days"]],
            [
                (1, 3, ["bad", "rep", "due", "unp", "unp", "exp", "stl"]),
                (2, 2, ["rep", "hnd", "exp"]),
                (None, 2, ["rep", "rep", "unp", "unp"]),
            ],
        )

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_the_chips_are_held_to_each_graphs_own_figure(self):
        reconcile, data = load("dashboard_reconcile", "dashboard-reconcile.py"), demo_data.demo()
        m = reconcile.model(data)
        agree, said = reconcile.attention_line(m, data)
        self.assertEqual((agree, said.endswith(": agree")), (True, True), said)
        # the chips are read where the page draws them, in its model, not in the data beside it
        m["attention"]["chips"].setdefault("mrg", []).append(
            {"mark": "bad", "name": "broken", "n": 99, "text": "99 broken"}
        )
        agree, said = reconcile.attention_line(m, data)
        self.assertEqual((agree, "DISAGREE (mrg bad)" in said), (False, True), said)


def keys_in(rows, keys):
    # one bool per row: a row without one of the keys fails as an assertion, not as a KeyError
    return [all(k in r for k in keys) for r in rows]


def learn_data():
    """Four Days whose specs merged at noon on 1 to 4 January and a fifth not begun. One problem is a chain of three
    links (D1.1 <- D2.1 <- D3.1, and D4.1 back to D1.1), another one link (D1.2 <- D3.2); D2.2 and D4.2 repeat
    nothing. Four fixes: #10 between Day 2's spec and Day 3's, naming the chain's middle; #11 before Day 4's, naming
    D2.2; #12 before Day 2's, naming D1.2 and an ID no Day has; #14 after the last spec."""

    def defect(i, same=None, found=None):
        return {"id": i, "same_as": same, "problem": None, "found": found}

    def spec(day):
        return {"number": day, "kind": "spec", "day": day, "merged": f"2026-01-0{day}T12:00:00Z"}

    def fix(pr, when, stops):
        return {"pr": pr, "title": f"fix {pr}", "merged": when, "stops": stops}

    reps = [("D2.1", "D1.1"), ("D3.1", "D2.1"), ("D3.2", "D1.2"), ("D4.1", "D1.1")]
    return {
        "now": {"head": "abc1234def", "last_pr": 14},
        "days": [
            {"day": 1, "status": "done", "defects": [defect("D1.1"), defect("D1.2")]},
            {"day": 2, "status": "done", "defects": [defect("D2.1", "D1.1"), defect("D2.2")]},
            {
                "day": 3,
                "status": "done",
                "defects": [
                    defect("D3.1", "D2.1", "track-reviewer"),
                    defect("D3.2", "D1.2", "evidence replay"),
                ],
            },
            {
                "day": 4,
                "status": "done",
                "defects": [defect("D4.1", "D1.1", "Track A"), defect("D4.2")],
            },
            {"day": 5, "defects": []},
        ],
        "defect_recurrence": {"recurrences": [{"id": i, "same_as": s} for i, s in reps]},
        "clock": {
            "prs": [
                spec(1),
                spec(2),
                spec(3),
                spec(4),
                {"number": 9, "kind": "code", "day": 4, "merged": "2026-01-04T20:00:00Z"},
            ]
        },
        "fixes": {
            "problems": ["specs/fixes.json: #99 is not a merged pull request"],
            "fixes": [
                fix(10, "2026-01-02T18:00:00Z", ["D2.1"]),
                fix(11, "2026-01-03T18:00:00Z", ["D2.2"]),
                fix(12, "2026-01-01T18:00:00Z", ["D1.2", "D9.9"]),
                fix(14, "2026-01-04T18:00:00Z", ["D4.2"]),
            ],
        },
    }


class LearningTest(unittest.TestCase):
    """learning(): "Does it learn?", the repeats per Day and the times before and after each fix (specs/fixes.json)."""

    def learn(self, data=None):
        return load("spec_drift_views", "spec_drift_views.py").learning(data or learn_data())

    def test_each_fix_counts_its_chains_before_and_after_the_first_day_after_it(self):
        got = self.learn()
        self.assertEqual(
            [
                (f["pr"], f["from_day"], f["before"], f["after"], f["after_ids"], f["days_since"])
                for f in got["fixes"]
            ],
            [
                (12, 2, 1, 1, ["D3.2"], 3),
                (10, 3, 2, 2, ["D3.1", "D4.1"], 2),
                (11, 4, 1, 0, [], 1),
                (14, None, 1, 0, [], 0),
            ],
        )
        self.assertEqual(got["held"], 1)

    def test_a_repeat_past_a_fix_of_its_chain_is_counted_apart(self):
        got = self.learn()
        # one short line per Day, "day:before/past fix", so a failure prints it whole
        said = " ".join(
            f"{r['day']}:{','.join(r['before'])}/{','.join(r['past_fix'])}" for r in got["days"]
        )
        self.assertEqual(said, "1:/ 2:D2.1/ 3:/D3.1,D3.2 4:/D4.1")
        self.assertEqual(
            [(r["day"], r["n"], r["fixes"]) for r in got["days"]],
            [(1, 0, []), (2, 1, [12]), (3, 2, [10]), (4, 1, [11])],
        )
        self.assertEqual((got["repeats"], got["past_fix"]), (4, 3))

    def test_a_day_says_what_share_of_its_defects_came_back(self):
        got = self.learn()
        self.assertEqual(keys_in(got["days"], ("defects", "share")), [True] * 4)
        self.assertEqual(
            [(r["day"], r["defects"], r["share"]) for r in got["days"]],
            [(1, 2, 0), (2, 2, 50), (3, 2, 100), (4, 2, 50)],
        )

    def test_a_repeat_past_a_fix_is_split_by_whether_a_gate_caught_it(self):
        got = self.learn()
        self.assertEqual(keys_in(got["days"], ("gated", "leaked")), [True] * 4)
        self.assertIn("past_gated", sorted(got))
        self.assertIn("past_leaked", sorted(got))
        # one short line per Day, "day:gated/leaked", so a failure prints it whole
        said = " ".join(
            f"{r['day']}:{','.join(r['gated'])}/{','.join(r['leaked'])}" for r in got["days"]
        )
        # D3.2 was found by the evidence replay, after the close: past the gates, as D4.1 noticed in the work
        self.assertEqual(said, "1:/ 2:/ 3:D3.1/D3.2 4:/D4.1")
        self.assertEqual((got["past_gated"], got["past_leaked"]), (1, 2))
        fixes = {f["pr"]: f for f in got["fixes"]}
        self.assertEqual(sorted(fixes), [10, 11, 12, 14])
        self.assertEqual(keys_in(list(fixes.values()), ("gated", "leaked")), [True] * 4)
        self.assertEqual((fixes[10]["gated"], fixes[10]["leaked"]), (["D3.1"], ["D4.1"]))
        self.assertEqual((fixes[12]["gated"], fixes[12]["leaked"]), ([], ["D3.2"]))

    def test_a_day_still_open_is_no_day_since(self):
        data = learn_data()
        data["clock"]["prs"].append(
            {"number": 5, "kind": "spec", "day": 5, "merged": "2026-01-05T12:00:00Z"}
        )
        got = self.learn(data)
        self.assertEqual(keys_in(got["fixes"], ("days_since", "rate_after")), [True] * 4)
        # fix 14 now counts from Day 5, whose spec merged but which has not finished
        self.assertEqual(
            [(f["pr"], f["days_since"], f["rate_after"]) for f in got["fixes"]],
            [(12, 3, 0.33), (10, 2, 1.0), (11, 1, 0.0), (14, 0, None)],
        )

    def test_a_fix_is_rated_by_the_day_before_and_after(self):
        got = self.learn()
        self.assertEqual(
            keys_in(got["fixes"], ("first_day", "days_before", "rate_before", "rate_after")),
            [True] * 4,
        )
        self.assertEqual(
            [
                (f["pr"], f["first_day"], f["days_before"], f["rate_before"], f["rate_after"])
                for f in got["fixes"]
            ],
            [
                (12, 1, 1, 1.0, 0.33),
                (10, 1, 2, 1.0, 1.0),
                (11, 2, 2, 0.5, 0.0),
                (14, 4, 1, 1.0, None),
            ],
        )

    def test_a_verdict_waits_for_enough_days(self):
        got = self.learn()
        self.assertIn("wait", sorted(got))
        self.assertEqual(got["wait"], 5)
        self.assertEqual(keys_in(got["fixes"], ("verdict",)), [True] * 4)
        self.assertEqual([f["verdict"] for f in got["fixes"]], [None] * 4)
        # the module's own LRN_WAIT, read when learning() is called: one Day is enough here
        # (the learning view's module, which spec_drift_views.py only imports it from)
        module = load("spec_drift_view_learning", "spec_drift_view_learning.py")
        module.LRN_WAIT = 1
        got = module.learning(learn_data())
        self.assertEqual(
            [f["verdict"] for f in got["fixes"]], ["reduced", "not reduced", "gone", None]
        )

    def test_a_repeat_under_two_fixes_is_named(self):
        got = self.learn()
        self.assertIn("shared", sorted(got))
        self.assertEqual(got["shared"], [])
        data = learn_data()
        data["fixes"]["fixes"].append(
            {"pr": 13, "title": "fix 13", "merged": "2026-01-02T19:00:00Z", "stops": ["D1.1"]}
        )
        self.assertEqual(self.learn(data)["shared"], ["D3.1", "D4.1"])

    def test_a_stop_no_day_has_is_a_problem_beside_the_records(self):
        got = self.learn()
        self.assertEqual(
            got["problems"],
            [
                "specs/fixes.json: #99 is not a merged pull request",
                "#12: stops D9.9 names no Defect line",
            ],
        )
        self.assertEqual(self.learn({"now": {}})["fixes"], [])

    def test_the_record_keeps_good_rows_and_names_each_bad_one(self):
        record = load("spec_drift_metrics", "spec_drift_metrics.py").fixes_record
        prs = {
            1: {"title": "one", "mergedAt": "2026-01-01T00:00:00Z"},
            2: {"title": "two", "mergedAt": None},
        }
        rows = [
            {"pr": 1, "stops": ["D1.1", "D1.1", "D2.3"]},
            {"pr": 1, "stops": ["D1.2"]},
            {"pr": 2, "stops": ["D1.2"]},
            {"pr": "3", "stops": ["D1.2"]},
            {"pr": 4, "stops": []},
            {"pr": 5, "stops": ["D1"]},
        ]
        got = record(json.dumps(rows), prs)
        self.assertEqual(
            got["fixes"],
            [
                {
                    "pr": 1,
                    "title": "one",
                    "merged": "2026-01-01T00:00:00Z",
                    "stops": ["D1.1", "D2.3"],
                }
            ],
        )
        bad = "row {} is not {{pr: a number, stops: [IDs like D21.2]}}"
        self.assertEqual(
            [p.removeprefix("specs/fixes.json").lstrip(": ") for p in got["problems"]],
            ["#1 is named twice", "#2 is not a merged pull request"]
            + [bad.format(i) for i in (4, 5, 6)],
        )
        self.assertEqual(record("", prs)["problems"], ["specs/fixes.json is missing"])
        self.assertEqual(record("{}", prs)["problems"], ["specs/fixes.json is not a list"])

    def test_the_committed_record_names_only_defect_lines_the_days_have(self):
        with open(os.path.join(ROOT, "specs", "fixes.json"), encoding="utf-8") as f:
            rows = json.load(f)
        ids = set()
        for name in os.listdir(os.path.join(ROOT, "specs")):
            m = re.fullmatch(r"day-(\d+)-.*\.md", name)
            if m:
                with open(os.path.join(ROOT, "specs", name), encoding="utf-8") as f:
                    ids |= {x["id"] for x in specs.defect_lines(f.read(), int(m.group(1)))}
        self.assertEqual(len({r["pr"] for r in rows}), len(rows))
        self.assertEqual([s for r in rows for s in r["stops"] if s not in ids], [])


def one_day_data():
    """Four Days. Day 11, before the split, has only a close. Day 15 has a spec, Track A, a close and a
    late spec, ten lines found as older Notes write them and one at: before Day 16. Day 16 has a spec,
    Track A in two parts, Track B with no PR and no close yet, and lines placed by at:. Day 17 has no
    PR, one at: naming a step it lacks, and a plan-auditor's row."""

    def row(pr, day, branch, kind):
        return {"pr": pr, "own_day": day, "branch": branch, "kind": kind, "date": f"d{pr}"}

    def defect(i, found, at=None, text=""):
        return {"id": i, "found": found, "at": at, "cause": "spec", "same_as": None, "text": text}

    def crit(i, day, tag, ticked, track=None, prs=()):
        return {"id": i, "day": day, "tag": tag, "ticked": ticked, "track": track, "prs": list(prs),
                "plain": f"plain {i}"}  # fmt: skip

    def tokens(agent, day, replies, cost, part="day"):
        return {"agent": agent, "part": part, "part_day": day, "replies": replies, "cost": cost}

    found15 = ["auditor", "The auditor (spec-auditor)", "spec-change PR", "Track A1", "track-reviewer",
               "evidence replay", "Day 16 review", "dashboard", "Track B"]  # fmt: skip
    day16 = [("auditor", None), ("auditor", "recheck"), ("track-reviewer", "Track A1 brief"),
             ("CI", "Track A PR"), ("review", "Track B diff"), ("self", None), ("review", "lunch"),
             ("seen red", "Track C build"), ("rehearsal", "rehearsal"), ("close", "replay"),
             ("dashboard", None)]  # fmt: skip
    defects16 = [defect(f"D16.{n}", f, a) for n, (f, a) in enumerate(day16, 1)]
    defects16[5]["text"] = "x" * 300
    return {
        "now": {"head": "ghijklmnop", "last_pr": 62},
        "days": [
            {"day": "x", "defects": [defect("DX.1", "auditor")]},
            {
                "day": 11,
                "title": "eleven",
                "status": "done",
                "tracks": [],
                "defects": [defect("D11.1", "evidence replay"), defect("D11.2", "close")],
            },
            {
                "day": 15,
                "title": "fifteen",
                "status": "done",
                "tracks": ["A"],
                "defects": [defect(f"D15.{n}", f) for n, f in enumerate(found15, 1)]
                + [defect("D15.10", "auditor", "recheck")],
            },
            {
                "day": 16,
                "title": "sixteen",
                "status": "active",
                "tracks": ["A", "B"],
                "defects": defects16,
            },
            {
                "day": 17,
                "title": "seventeen",
                "status": "pending",
                "tracks": ["A"],
                "defects": [defect("D17.1", "self", "spec-change PR")],
            },
        ],
        "rows": [
            row(40, 11, "day-11/close-the-day", "close"),
            row(50, 15, "day-15/spec-x", "spec"),
            row(51, 15, "day-15/track-a-x", "code"),
            row(52, 15, "day-15/close-the-day", "close"),
            row(53, 15, "day-15/spec-late", "spec"),
            row(60, 16, "day-16/spec-y", "spec"),
            row(61, 16, "day-16/track-a1-y", "code"),
            row(62, 16, "day-16/track-a2-y", "code"),
            row(70, None, "dashboard/x", "other"),
        ],
        "criteria_index": [
            crit("C15.1", 15, "new", True, "A", [50]),
            crit("C15.2", 15, "hold", True, None, [50]),
            crit("C15.3", 15, "hold", True, None, [53]),
            crit("C15.4", 15, "new", False),
            crit("C16.1", 16, "new", False, "A"),
            crit("C16.2", 16, "hold", False, "B"),
        ],
        "tokens": [
            tokens("main", 15, 10, 1.0),
            tokens("main", 15, 5, 0.5),
            tokens("spec-auditor", 15, 4, 0.25),
            tokens("general-purpose", 15, 2, 0.25),
            tokens("main", None, 99, 9.0, "dashboard"),
            tokens("plan-auditor", 17, 3, 0.5),
        ],
    }


class OneDayTest(unittest.TestCase):
    """one_day(): each Day's steps, its Defect lines placed on them, its criteria, agents and totals."""

    def view(self, data=None):
        return load("spec_drift_views", "spec_drift_views.py").one_day(data or one_day_data())

    def days(self, data=None):
        return {x["day"]: x for x in self.view(data)["days"]}

    def placed(self, day):
        # one short line per Defect line, "id:step/sub/by", so a failure prints it whole
        return " ".join(f"{x['id']}:{x['step']}/{x['sub']}/{x['by']}" for x in day["defects"])

    def test_a_days_steps_are_its_audit_pr_groups_tracks_with_no_pr_and_close(self):
        got = self.days()
        self.assertEqual(sorted(got), [11, 15, 16, 17])
        said = " ".join(f"{d}:{','.join(s['key'] for s in got[d]['steps'])}" for d in sorted(got))
        self.assertEqual(
            said, "11:close 15:audit,spec,A,close,spec2 16:audit,spec,A,B,close 17:audit,A,close"
        )
        data = one_day_data()
        data["tokens"] = [t for t in data["tokens"] if t["agent"] != "plan-auditor"]
        self.assertEqual([s["key"] for s in self.days(data)[17]["steps"]], ["A", "close"])

    def test_a_step_holds_its_prs_and_the_subs_of_its_days_era(self):
        got = self.days()

        def prs(d):
            return " ".join(f"{s['key']}:{','.join(map(str, s['prs']))}" for s in got[d]["steps"])

        def subs(d):
            return " ".join(f"{s['key']}:{','.join(s['subs'])}" for s in got[d]["steps"])

        self.assertEqual(prs(15), "audit: spec:50 A:51 close:52 spec2:53")
        self.assertEqual(prs(16), "audit: spec:60 A:61,62 B: close:")
        self.assertEqual(subs(11), "close:")
        self.assertEqual(subs(15), "audit: spec:pr A:build close:rehearsal,pr,replay spec2:pr")
        self.assertEqual(
            subs(16),
            "audit:audit,recheck spec:pr A:brief,build,diff,pr B:brief,build,diff,pr close:rehearsal,pr,replay",
        )
        names = " ".join(f"{s['name']}/{s['kind']}/{s['date']}" for s in got[15]["steps"])
        self.assertEqual(names, "Audit/audit/None Spec change/spec/d50 Track A/code/d51 Close/close/d52 "
                                "Spec change 2/spec/d53")  # fmt: skip

    def test_a_line_before_day_16_is_placed_from_found(self):
        got = self.days()
        self.assertEqual(self.placed(got[11]), "D11.1:close/None/found D11.2:close/None/found")
        self.assertEqual(
            self.placed(got[15]),
            "D15.1:audit/None/found D15.2:audit/None/found D15.3:spec/pr/found D15.4:A/build/found "
            "D15.5:None/None/None D15.6:close/replay/found D15.7:after/None/found D15.8:after/None/found "
            "D15.9:None/None/None D15.10:audit/None/found",
        )

    def test_a_line_from_day_16_is_placed_from_at(self):
        got = self.days()
        self.assertEqual(
            self.placed(got[16]),
            "D16.1:audit/None/found D16.2:audit/recheck/at D16.3:A/brief/at D16.4:A/pr/at D16.5:B/diff/at "
            "D16.6:None/None/None D16.7:None/None/None D16.8:None/None/None D16.9:close/rehearsal/at "
            "D16.10:close/replay/at D16.11:after/None/found",
        )
        self.assertEqual(self.placed(got[17]), "D17.1:None/None/None")

    def test_an_at_off_the_steps_or_before_day_16_is_a_problem(self):
        got = self.view()
        self.assertEqual(
            got["problems"],
            [
                "Day 15: D15.10 has at: before Day 16",
                'Day 16: D16.7 at: "lunch" is not a step of the Day',
                'Day 16: D16.8 at: "Track C build" is not a step of the Day',
                'Day 17: D17.1 at: "spec-change PR" is not a step of the Day',
            ],
        )

    def test_the_lines_from_day_16_with_no_step_are_counted(self):
        module = load("spec_drift_views", "spec_drift_views.py")
        got = module.one_day(one_day_data())
        self.assertEqual(got["from_day"], 16)
        self.assertEqual(
            got["no_step"], {"lines": 4, "of": 12, "ids": ["D16.6", "D16.7", "D16.8", "D17.1"]}
        )
        self.assertEqual(
            module.one_day_line(got), "defect steps: 4 of 12 Defect lines from Day 16 take no step"
        )

    def test_a_long_text_is_cut(self):
        six = [x for x in self.days()[16]["defects"] if x["id"] == "D16.6"]
        self.assertEqual(len(six), 1)
        self.assertEqual((len(six[0]["text"]), six[0]["text"][-1]), (260, "…"))

    def test_a_criterion_takes_its_tracks_step_or_its_first_prs(self):
        got = self.days()
        said = " ".join(f"{c['id']}:{c['step']}" for d in (15, 16) for c in got[d]["criteria"])
        self.assertEqual(said, "C15.1:A C15.2:spec C15.3:spec2 C15.4:None C16.1:A C16.2:B")
        self.assertEqual(got[15]["criteria"][0]["quote"], "plain C15.1")

    def test_agents_are_summed_in_the_role_maps_order(self):
        got = self.days()
        self.assertEqual(
            [(a["agent"], a["replies"], a["cost"], a["covers"]) for a in got[15]["agents"]],
            [
                ("main", 15, 1.5, [["*", "*"]]),
                ("spec-auditor", 4, 0.25, [["audit", "*"]]),
                ("general-purpose", 2, 0.25, []),
            ],
        )
        self.assertEqual(
            [(a["name"], a["does"]) for a in got[15]["agents"]][2], ("general-purpose", "")
        )
        self.assertEqual(got[16]["agents"], [])

    def test_totals_add_up(self):
        got = self.days()
        keys = ["prs", "new", "hold", "ticked", "cost", "replies"]
        keys += ["defects", "placed", "no_step", "after"]
        self.assertEqual(keys_in([got[d]["totals"] for d in sorted(got)], keys), [True] * 4)
        t = {d: got[d]["totals"] for d in got}
        self.assertEqual(
            [t[11][k] for k in ("prs", "defects", "placed", "no_step", "after")], [1, 2, 2, 0, 0]
        )
        self.assertEqual([t[15][k] for k in keys], [4, 2, 2, 3, 2.0, 21, 10, 6, 2, 2])
        self.assertEqual([t[16][k] for k in keys], [3, 1, 1, 0, 0, 0, 11, 7, 3, 1])
        self.assertEqual(
            [t[17][k] for k in ("defects", "placed", "no_step", "after")], [1, 0, 1, 0]
        )
        self.assertEqual(
            [
                t[d]["placed"] + t[d]["no_step"] + t[d]["after"] == t[d]["defects"]
                for d in sorted(t)
            ],
            [True] * 4,
        )
        subs = {(d, s["key"]): s["subs"] for d in got for s in got[d]["steps"]}
        stray = [x["id"] for d in got for x in got[d]["defects"]
                 if x["step"] not in (None, "after") and x["sub"] is not None
                 and x["sub"] not in subs.get((d, x["step"]), [])]  # fmt: skip
        self.assertEqual(stray, [])

    def test_the_split_is_the_metrics_one(self):
        views = load("spec_drift_views", "spec_drift_views.py")
        metrics = load("spec_drift_metrics", "spec_drift_metrics.py")
        self.assertEqual(views.ONE_DAY_SPLIT, metrics.SPLIT_FROM)

    def test_the_view_is_plain_json_and_reads_no_data(self):
        got = self.view()
        self.assertEqual(json.loads(json.dumps(got)), got)
        self.assertEqual(self.view({"now": {}})["days"], [])


def rewrites_data():
    """Six Days and eight criteria: one line of four wordings (C03.1 folded in), one from a short spec's two, one of
    two, and C06.2, replacing nothing."""

    def crit(cid, day, state, replaces=(), replaced_by=()):
        return {"id": cid, "day": day, "state": state, "plain": f"{cid} in plain words.", "claim": "",
                "replaces": list(replaces), "replaced_by": list(replaced_by)}  # fmt: skip

    return {
        "now": {"head": "abcdef1234", "last_pr": 9, "generated": "2026-11-26T00:00:00Z"},
        "days": [{"day": n, "phase": p} for n, p in zip(range(1, 7), [0, 0, 1, 1, 1, 2])],
        "criteria_index": [
            crit("C01.1", 1, "replaced", replaced_by=["C02.1"]),
            crit("C02.1", 2, "replaced", ["C01.1"], ["C04.1"]),
            crit("C03.1", 3, "replaced", replaced_by=["C04.1"]),
            # the shallow one first: the main chain takes the deeper C02.1, not the first named
            crit("C04.1", 4, "proven", ["C03.1", "C02.1"]),
            crit("C03.2", 3, "replaced", replaced_by=["C05.1"]),
            crit("C05.1", 5, "unproven", ["C03.2"]),
            crit("C06.1", 6, "building", ["S-pick-a-day.1", "S-pick-a-day.2"]),
            crit("C06.2", 6, "proven"),
        ],
    }


class RewritesTest(unittest.TestCase):
    """rewrites(): each promise in force that replaced others, as a line of its wordings joined to their successors."""

    def module(self):
        views = load("spec_drift_views", "spec_drift_views.py")
        self.assertTrue(hasattr(views, "rewrites"), "spec_drift_views has no rewrites view yet")
        return views

    def view(self, data=None):
        return self.module().rewrites(rewrites_data() if data is None else data)

    def line(self, got, sink):
        sinks = [x["sink"] for x in got["lines"]]
        self.assertIn(sink, sinks)
        return got["lines"][sinks.index(sink)]

    def test_lines_are_ordered_by_rewrites_and_walk_their_longest_chain(self):
        got = self.view()
        # one short line per line, "sink rewrites n first main", so a failure prints it whole
        said = [
            f"{x['sink']} {x['rewrites']} {x['n']} {x['first']} {'>'.join(x['main'])}"
            for x in got["lines"]
        ]
        self.assertEqual(len(said), 3)
        self.assertEqual(said[0], "C04.1 2 4 1 C01.1>C02.1>C04.1")
        self.assertEqual(said[1], "C06.1 1 3 5.5 S-pick-a-day.1>C06.1")
        self.assertEqual(said[2], "C05.1 1 2 3 C03.2>C05.1")
        self.assertEqual(
            got["stats"],
            {
                "replaced": 6,
                "lines": 3,
                "multi": 1,
                "longest": 2,
                "states": {"proven": 1, "unproven": 1, "building": 1},
            },
        )
        self.assertEqual(got["problems"], [])
        self.assertEqual([x["day"] for x in got["days"]], [1, 2, 3, 4, 5, 6])
        on = {n["id"] for x in got["lines"] for n in x["nodes"]}
        self.assertNotIn("C06.2", on)

    def test_a_lines_nodes_and_edges_in_full(self):
        line = self.line(self.view(), "C04.1")

        def node(cid, day, state, by, main):
            return {"id": cid, "label": cid, "day": day, "state": state, "short": False,
                    "text": f"{cid} in plain words.", "by": by, "main": main}  # fmt: skip

        self.assertEqual(
            line["nodes"],
            [
                node("C01.1", 1, "replaced", ["C02.1"], True),
                node("C02.1", 2, "replaced", ["C04.1"], True),
                node("C03.1", 3, "replaced", ["C04.1"], False),
                node("C04.1", 4, "proven", [], True),
            ],
        )
        self.assertEqual(
            line["edges"],
            [["C01.1", "C02.1"], ["C03.1", "C04.1"], ["C02.1", "C04.1"]],
        )
        self.assertEqual(
            (line["text"], line["state"], line["day"]),
            ("C04.1 in plain words.", "proven", 4),
        )

    def test_a_short_specs_promises_are_nodes_between_the_days(self):
        line = self.line(self.view(), "C06.1")
        short = [n for n in line["nodes"] if n["short"]]
        self.assertEqual(
            [(n["id"], n["label"], n["day"], n["state"]) for n in short],
            [
                ("S-pick-a-day.1", "S.1", 5.5, "replaced"),
                ("S-pick-a-day.2", "S.2", 5.5, "replaced"),
            ],
        )
        self.assertEqual(
            short[0]["text"],
            'A promise of the short spec "pick-a-day". Its words are in '
            "specs/changes/pick-a-day.md, not in the page's data.",
        )

    def test_an_absent_id_and_a_replaced_promise_on_no_line_are_problems(self):
        data = rewrites_data()
        index = data["criteria_index"]
        # C03.2 named twice: one edge
        index[5]["replaces"] = ["C03.2", "C00.7", "C03.2"]
        index.append(
            {"id": "C02.9", "day": 2, "state": "replaced", "plain": "C02.9 in plain words.",
             "claim": "", "replaces": [], "replaced_by": ["C09.9"]}
        )  # fmt: skip
        got = self.view(data)
        self.assertEqual(len(got["problems"]), 2)
        self.assertEqual(
            got["problems"][0], "C00.7, named by C05.1's Replaces: line, is not in the index"
        )
        self.assertEqual(got["problems"][1], "C02.9 is replaced by C09.9 and stands on no line")
        line = self.line(got, "C05.1")
        self.assertEqual((line["n"], line["edges"]), (2, [["C03.2", "C05.1"]]))
        on = {n["id"] for x in got["lines"] for n in x["nodes"]}
        self.assertNotIn("C02.9", on)

    def test_a_cycle_returns_and_no_data_draws_no_line(self):
        data = rewrites_data()
        data["criteria_index"][0]["replaces"] = ["C04.1"]
        line = self.line(self.view(data), "C04.1")
        self.assertEqual((line["n"], len(line["edges"])), (4, 4))
        self.assertEqual(len(line["main"]), len(set(line["main"])))
        got = self.view({})
        self.assertEqual((got["lines"], got["stats"]["longest"]), ([], 0))

    def test_a_sink_naming_only_absent_ids_makes_no_line_only_problems(self):
        data = rewrites_data()
        index = data["criteria_index"]
        index[5]["replaces"] = ["C03.2", "C00.7"]
        index.append(
            {"id": "C07.1", "day": 6, "state": "proven", "plain": "C07.1 in plain words.",
             "claim": "", "replaces": ["C00.8", "C00.9"], "replaced_by": []}
        )  # fmt: skip
        got = self.view(data)
        self.assertEqual([x["sink"] for x in got["lines"]], ["C04.1", "C06.1", "C05.1"])
        # an absent id's problem in line order, then the sink's that made no line
        self.assertEqual(len(got["problems"]), 3)
        self.assertEqual(
            got["problems"][0], "C00.7, named by C05.1's Replaces: line, is not in the index"
        )
        self.assertEqual(
            got["problems"][1], "C00.8, named by C07.1's Replaces: line, is not in the index"
        )
        self.assertEqual(
            got["problems"][2], "C00.9, named by C07.1's Replaces: line, is not in the index"
        )

    def test_lines_alike_in_rewrites_and_wordings_go_by_their_sinks_number(self):
        data = rewrites_data()
        index = data["criteria_index"]
        # C05.1's twin, listed first and later in number: C05.1's line comes first all the same
        index.insert(
            0,
            {"id": "C05.9", "day": 5, "state": "proven", "plain": "C05.9 in plain words.",
             "claim": "", "replaces": ["C03.9"], "replaced_by": []},
        )  # fmt: skip
        index.append(
            {"id": "C03.9", "day": 3, "state": "replaced", "plain": "C03.9 in plain words.",
             "claim": "", "replaces": [], "replaced_by": ["C05.9"]}
        )  # fmt: skip
        got = self.view(data)
        self.assertEqual([x["sink"] for x in got["lines"]], ["C04.1", "C06.1", "C05.1", "C05.9"])

    def test_the_build_line_counts_the_rewrites(self):
        views = self.module()
        self.assertEqual(
            views.rewrites_line(views.rewrites(rewrites_data())),
            "rewrites: 6 promises replaced, on 3 lines; the longest was rewritten 2 times",
        )


# a document that keeps each node's listeners, a click that fires them, and a querySelectorAll("button") over a node's
# own children: enough for readingDraw(), and for draw() to make the page's Day buttons and press them
LINK_DOC = r"""
const fs = require("fs"), vm = require("vm"), els = {};
const node = tag => { const n = { tag, attrs: {}, kids: [], style: {}, dataset: {}, hidden: false, textContent: "", on: {}, value: "",
  classList: { toggle(c, on) { const k = new Set((n.attrs.class || "").split(" ").filter(Boolean)); if (on === undefined ? !k.has(c) : on) k.add(c); else k.delete(c); n.attrs.class = [...k].join(" "); },
    add(c) { this.toggle(c, true); }, remove(c) { this.toggle(c, false); }, contains(c) { return (n.attrs.class || "").split(" ").includes(c); } },
  setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }, removeAttribute(k) { delete this.attrs[k]; },
  appendChild(c) { this.kids.push(c); return c; }, append(...c) { this.kids.push(...c); }, prepend(...c) { this.kids.unshift(...c); }, replaceChildren(...c) { this.kids = c; },
  addEventListener(type, fn) { (n.on[type] = n.on[type] || []).push(fn); }, click() { (n.on.click || []).forEach(f => f({ key: "", target: n, preventDefault() {} })); },
  querySelectorAll(s) { return s === "button" ? n.kids.filter(k => k && k.tag === "button") : []; }, querySelector() { return null; }, closest() { return null; } };
  Object.defineProperty(n, "className", { set(v) { n.attrs.class = v; }, get() { return n.attrs.class || ""; } });
  return n; };
const $ = id => els[id] || (els[id] = node(id));
const document = { createElementNS(ns, tag) { return node(tag); }, createElement: node, createTextNode: t => String(t), addEventListener() {}, getElementById: $,
  querySelectorAll: () => [], querySelector: () => null, documentElement: node("html"), body: node("body") };
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")), document, $, els, window: {}, location: { hash: "" },
  matchMedia: () => ({ matches: false, addEventListener() {} }), console: { error() {}, log() {} } });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const all = n => [n, ...(n.kids || []).filter(k => k && typeof k === "object").flatMap(all)];
  const has = (e, c) => ((e.attrs && e.attrs.class) || "").split(" ").includes(c);
  const fire = (e, type, ev) => (e.on[type] || []).forEach(f => f(Object.assign({ key: "", target: e, preventDefault() {} }, ev || {})));
  BODY`, ctx)));
"""

# readingDraw() on the data from stdin: graph 1's row of old problems back (a group per Day, each part's top and height
# over the bars' base, its count), its words and the marks that are links, and the Days its links opened in the cell.
REP = LINK_DOC.replace(
    "BODY",
    r"""
  const M = model(DATA), days = [], opened = [];
  readingDraw(M.rdg, $, days, d => opened.push(d));
  const r = $("rdg-fig"), reps = all(r).filter(e => has(e, "rep")), base = +r.attrs.viewBox.split(" ")[3] - 2;
  const PARTS = ["bk-before", "bk-gate", "bk-gateh", "bk-past", "bk-pasth"];
  const out = { reps: reps.map(g => g.attrs["data-v"]), height: +r.attrs.viewBox.split(" ")[3],
    n: reps.map(g => all(g).filter(e => has(e, "bk-n") || has(e, "bk-n0")).map(e => (has(e, "bk-n0") ? "faint " : "") + e.textContent).join(" ")),
    parts: reps.map(g => all(g).filter(e => PARTS.some(c => has(e, c))).map(e => [e.attrs.class, +(base - e.attrs.y).toFixed(2), +e.attrs.height])),
    ticks: reps.filter(g => all(g).some(e => has(e, "bk-fix"))).map(g => g.attrs["data-v"]),
    label: all(r).filter(e => e.tag === "text" && e.textContent === "Old problems back").length,
    none: all(r).filter(e => has(e, "bk-none")).map(e => e.textContent),
    total: $("rdg-k-back").textContent, tips: reps.map(g => rdgTip(M.rdg, "rep", g.attrs["data-v"])),
    links: all(r).filter(e => e.attrs && e.attrs["data-day"] != null).map(e => [e.attrs.class.split(" ")[0], e.attrs.tabindex, e.attrs.role, e.attrs["aria-label"]]) };
  days.forEach(f => f(2)); out.dim = reps.filter(g => has(g, "mk-dim")).map(g => g.attrs["data-v"]);
  // a Day's label and its strays clicked, then Enter, Space and another key on each group of the row
  all(r).filter(e => (has(e, "t-dayn") || has(e, "t-stray")) && e.attrs["data-day"] != null).forEach(e => fire(e, "click"));
  reps.forEach(g => { fire(g, "keydown", { key: "Enter" }); fire(g, "keydown", { key: " " }); fire(g, "keydown", { key: "x" }); });
  out.opened = opened;
  // drawn with no way to the cell: nothing is a button
  readingDraw(M.rdg, $, []);
  out.plain = all($("rdg-fig")).filter(e => e.attrs && (e.attrs.role === "button" || e.attrs["data-day"] != null)).length;
  out
""",
)

# draw() itself, the whole page on the same document: Day 2's label in graph 1 clicked, then Day 1's number on a chain
# of graph 3, each time the page's Day buttons' aria-pressed (All Days first); graph 3's tab stops as drawn on the page
# and as protDraw() alone draws them with no link to the cell, and the tabindex of its Day numbers.
DRAW_LINK = LINK_DOC.replace(
    "BODY",
    r"""
  const M = model(DATA);
  draw(M, DATA);
  const pressed = () => $("days").kids.filter(k => k && k.tag === "button").map(b => b.attrs["aria-pressed"]).join(" ");
  const out = { before: pressed() };
  const lab = all($("rdg-fig")).find(e => has(e, "t-dayn") && e.attrs["data-day"] === "2");
  if (lab) fire(lab, "click");
  out.rdg = pressed();
  const num = all($("prt-fig")).find(e => has(e, "t-day") && e.attrs["data-d"] === "1");
  if (num) fire(num, "click");
  out.prt = pressed();
  const stops = () => all($("prt-fig")).filter(e => e.attrs && e.attrs.tabindex === "0").length;
  out.days = [...new Set(all($("prt-fig")).filter(e => has(e, "t-day") && e.attrs["data-d"] != null).map(e => e.attrs.tabindex))];
  out.stops = stops();
  protDraw(M.prt, $, []);
  out.stopsPlain = stops();
  out
""",
)


def short(stderr):
    """The last line of a node error, its paths taken out, so a failure prints the same on any machine."""
    lines = [x for x in (stderr or "").splitlines() if x.strip()]
    return re.sub(r"\S*[\\/]\S*", "<path>", lines[-1] if lines else "")[:200]


def back_learning():
    """A learning of three Days: Day 1 with two back before any fix and a fix counted from it; Day 2 with one back
    before any fix, two caught at a gate and one that got past although a fix was in place; Day 3, which graph 1 does
    not draw, with six back and a fix of its own."""

    def day(n, before, gated, leaked, defects, fixes):
        return {
            "day": n,
            "n": len(before) + len(gated) + len(leaked),
            "before": before,
            "past_fix": gated + leaked,
            "gated": gated,
            "leaked": leaked,
            "defects": defects,
            "share": None,
            "fixes": fixes,
        }

    days = [
        day(1, ["D1.1", "D1.2"], [], [], 3, [5]),
        day(2, ["D2.1"], ["D2.2", "D2.4"], ["D2.3"], 5, []),
        day(3, ["D3.1", "D3.2"], [], ["D3.3", "D3.4", "D3.5", "D3.6"], 6, [9]),
    ]
    return {
        "head": "abc1234",
        "last_pr": 12,
        "generated": "2026-01-02",
        "repeats": 12,
        "past_fix": 7,
        "past_gated": 2,
        "past_leaked": 5,
        "held": 0,
        "wait": 5,
        "shared": [],
        "problems": [],
        "days": days,
        "fixes": [],
    }


class ImmunityRowTest(unittest.TestCase):
    """Graph 1's row of old problems back: a bar per Day it draws, what it says with nothing counted, and its links."""

    def run_page(self, script, learning="keep", protein=False):
        data = ring_data()
        views = load("spec_drift_views", "spec_drift_views.py")
        data["reading"] = views.reading(data)
        if learning == "keep":
            data["learning"] = back_learning()
        elif learning is not None:
            data["learning"] = learning
        if protein:
            data["protein"] = views.protein(prt_data())
        reconcile = load("dashboard_reconcile", "dashboard-reconcile.py")
        out = subprocess.run(
            ["node", "-e", script, reconcile.SCRIPT],
            input=json.dumps(data),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual((out.returncode, short(out.stderr)), (0, ""))
        return json.loads(out.stdout)

    def drawn(self, learning="keep"):
        return self.run_page(REP, learning)

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_the_row_draws_a_bar_per_day_graph_1_draws_its_parts_stacked_and_scaled(self):
        out = self.drawn()
        # Days 1 and 2 have a span on the strand; Day 3 has no merge, so no bar
        self.assertEqual(out["reps"], ["1", "2"])
        self.assertEqual(out["n"], ["2", "4"])
        # [part, its top over the bars' base, its height]: Day 2, the tallest drawn, is the full 22 px, 5.5 a repeat
        # (Day 3's 6 is not drawn and sets no scale); Day 1's 2 is half of it. Stacked from the base: 1 before, 2
        # caught at a gate, 1 got past, both parts past a fix with their hatch over them
        self.assertEqual(len(out["parts"]), 2)
        self.assertEqual(out["parts"][0], [["bk-before", 11, 11]])
        self.assertEqual(out["parts"][1][:2], [["bk-before", 5.5, 5.5], ["bk-gate", 16.5, 11]])
        self.assertEqual(out["parts"][1][2:3], [["bk-gateh", 16.5, 11]])
        self.assertEqual(out["parts"][1][3:], [["bk-past", 22, 5.5], ["bk-pasth", 22, 5.5]])
        # the part that got past is red, the one a gate caught amber
        with open(os.path.join(ROOT, "docs", "dashboard", "dashboard.css"), encoding="utf-8") as f:
            css = f.read()
        colours = [
            "#rdg .bk-past{fill:var(--broken)}" in css,
            "#rdg .bk-gate{fill:var(--repair)}" in css,
        ]
        self.assertEqual(colours, [True, True])
        # ring_data's picture ends 299 high (two open hand-offs, the last at 272.6): the row adds 8 and 34
        self.assertEqual(out["height"], 341)
        self.assertEqual(out["ticks"], ["1"])
        self.assertEqual((out["label"], out["none"]), (1, []))
        # Day 2 chosen on the page's buttons dims Day 1's bar
        self.assertEqual(out["dim"], ["1"])

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_a_day_with_nothing_back_draws_a_faint_0(self):
        learning = back_learning()
        learning["days"][0] = dict(learning["days"][0], n=0, before=[])
        out = self.drawn(learning)
        self.assertEqual(len(out["parts"]), 2)
        self.assertEqual((out["n"], out["parts"][0]), (["faint 0", "4"], []))

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_a_bars_tip_says_its_parts_its_fixes_and_where_a_click_goes(self):
        tips = self.drawn()["tips"]
        self.assertEqual(len(tips), 2)
        self.assertEqual([("t" in t, "l" in t) for t in tips], [(True, True), (True, True)])
        self.assertEqual(tips[1]["t"], "Day 2 · old problems back: 4 of its 5 defects")
        want = {
            0: ["2 with no fix yet", "0 although a fix was in place, caught at a gate", "0 got past",
                "Fixes counted from this Day: #5", "Click to open Day 1 in the cell."],
            1: ["1 with no fix yet", "2 although a fix was in place, caught at a gate", "1 got past",
                "Click to open Day 2 in the cell."],
        }  # fmt: skip
        # line by line, so a failure prints one short line whole
        for k, lines in want.items():
            self.assertEqual((k, len(tips[k]["l"])), (k, len(lines)))
            for i, line in enumerate(lines):
                self.assertEqual((k, i, tips[k]["l"][i]), (k, i, line))

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_with_nothing_counted_the_row_and_the_key_say_so(self):
        for name, learning, said in (
            ("missing", None, "Old problems back: not counted yet."),
            ("error", {"error": "x"}, "Old problems back: not counted yet. x"),
            (
                "error and days",
                dict(back_learning(), error="x"),
                "Old problems back: not counted yet. x",
            ),
            ("no days", dict(back_learning(), days=[]), "Old problems back: not counted yet."),
        ):
            out = self.drawn(learning)
            self.assertEqual((name, out["reps"], out["none"]), (name, [], [said]))
            self.assertEqual((name, out["total"]), (name, said))

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_the_key_says_the_totals_from_the_counts(self):
        # 12 repeats of 3 + 5 + 6 = 14 defects; 7 past a fix: 2 gated, 5 leaked
        total = self.drawn()["total"].split("; ")
        self.assertEqual(len(total), 2)
        self.assertEqual(total[0], "12 of 14 defects repeat an earlier one")
        self.assertEqual(
            total[1], "7 came back although a fix was in place: 2 caught at a gate, 5 got past."
        )

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_a_days_label_its_stray_and_its_bar_open_it_in_the_cell(self):
        out = self.drawn()
        # clicks on Day 1's label, its stray (#9, inside Day 2), Day 2's label and its stray (#8, cut off by #9); then
        # Enter and Space on each bar, and another key that opens nothing
        self.assertEqual(out["opened"], [1, 1, 2, 2, 1, 1, 2, 2])
        self.assertEqual(out["plain"], 0)
        # each link a tab stop and a button; a label named by its link, a bar by its counts, in three short parts
        links = out["links"]
        self.assertEqual(len(links), 6)
        self.assertEqual(
            [x[0] for x in links], ["t-dayn", "t-stray", "t-dayn", "t-stray", "b", "b"]
        )
        self.assertEqual([x[1:3] for x in links], [["0", "button"]] * 6)
        named = [x[3] for x in links[:4]]
        self.assertEqual(named[:2], ["Open Day 1 in the cell", "Open Day 1 in the cell"])
        self.assertEqual(named[2:], ["Open Day 2 in the cell", "Open Day 2 in the cell"])
        bar = links[5][3].split(", ")
        self.assertEqual(bar[0], "Day 2: 4 old problems back")
        self.assertEqual(bar[1:], ["2 although a fix was in place caught at a gate", "1 got past"])

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
    def test_the_page_presses_the_days_button_from_graph_1s_label_and_graph_3s_number(self):
        out = self.run_page(DRAW_LINK, protein=True)
        # the page's buttons: All Days, Day 1, Day 2
        self.assertEqual(out["before"], "true false false")
        self.assertEqual(out["rdg"], "false false true")
        self.assertEqual(out["prt"], "false true false")
        # graph 3's Day numbers are links out of the Tab order: its tab stops are what protDraw makes without them
        self.assertEqual(out["days"], ["-1"])
        self.assertEqual(out["stops"], out["stopsPlain"])


if __name__ == "__main__":
    unittest.main()
