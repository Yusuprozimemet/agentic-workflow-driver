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

    def test_the_ring_counts_the_days_closed_and_left_to_the_stop_as_the_tiles_do(self):
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

    def drawn(self, data):
        out = subprocess.run(
            ["node", "-e", RING, reconcile.SCRIPT],
            input=json.dumps(data),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(out.returncode, 0, out.stderr[:600])
        return json.loads(out.stdout)

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

    def test_the_ring_and_the_reading_reconcile_with_the_tiles_and_the_hand_off_ledger(self):
        m = reconcile.model(demo_data.demo())
        agree, line = reconcile.ring_line(m)
        self.assertTrue(agree, line)
        self.assertRegex(
            line,
            r"^where we are: ring \d+ of \d+ Days closed, \d+ of \d+ promises built \| "
            r"tiles \d+ of \d+, look-ahead \d+ of \d+: agree$",
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


if __name__ == "__main__":
    unittest.main()
