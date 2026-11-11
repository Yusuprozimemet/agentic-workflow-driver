"""The dashboard page: what each of its eleven graphs draws and says, and what the page file must hold.

docs/dashboard/dashboard.js keeps its reading of the data in model(), which touches no document, so
these tests run it in node on small made-up data and compare what comes out. The page itself is
booted on a document that accepts anything, to see that drawing does not throw. Needs node.

    python scripts/test_dashboard_page.py
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "..", "docs", "dashboard")
SCRIPT = os.path.join(PAGE, "dashboard.js")
spec = importlib.util.spec_from_file_location("spec_drift", os.path.join(HERE, "spec-drift.py"))
sd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sd)

# model() on the data from stdin, printed as JSON.
MODEL = r"""
const fs = require("fs"), vm = require("vm");
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")) });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\nmodel(DATA)", ctx)));
"""

# boot() on the data from stdin, with a document that accepts anything: the error that stopped it, what
# went to console.error (a graph that could not be drawn says so there), and the banner and eyebrow it wrote.
BOOT = r"""
const fs = require("fs"), vm = require("vm"), els = {}, logged = [];
const stub = () => new Proxy(function () {}, {
  get: (t, k) => k === Symbol.toPrimitive ? () => "" : k === Symbol.iterator ? [][Symbol.iterator] : k in t ? t[k] : (t[k] = stub()),
  apply: () => stub(), construct: () => stub() });
const document = new Proxy({}, { get: (t, k) => k === "getElementById" ? id => els[id] || (els[id] = stub()) : stub() });
const ctx = vm.createContext({ document, window: {}, location: { hash: "" }, matchMedia: () => ({ matches: false, addEventListener() {} }),
  console: { error: e => logged.push(String(e)) }, DATA: JSON.parse(fs.readFileSync(0, "utf8")) });
let error = null;
try { vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\nboot(DATA);", ctx); } catch (e) { error = e.message; }
const shown = el => el ? { hidden: el.hidden, text: el.textContent } : null;
console.log(JSON.stringify({ error, logged, eyebrow: els.eyebrow ? els.eyebrow.textContent : null,
  banner: shown(els["demo-banner"]), missing: shown(els["data-banner"]) }));
"""

# tagOf() on each value of the list from stdin.
TAGS = r"""
const fs = require("fs"), vm = require("vm");
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")) });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\nDATA.map(tagOf)", ctx)));
"""


def node(harness, data):
    return json.loads(subprocess.run(["node", "-e", harness, SCRIPT], input=json.dumps(data), capture_output=True,
                                     encoding="utf-8", check=True).stdout)


def model(data):
    """What the page would draw and say for this data."""
    return node(MODEL, data)


def boot(data):
    """What booting the page on this data reported."""
    return node(BOOT, data)


def read(name):
    with open(os.path.join(PAGE, name), encoding="utf-8") as f:
        return f.read()


def a_day(n, status="done", **more):
    return dict(dict(day=n, title=f"Day {n}: `thing`", status=status, defects=[], relabel=None, worked=None), **more)


def data(**more):
    """Three Days, the third in progress, and nothing else; `more` adds or replaces fields."""
    return dict(dict(now=dict(generated="2026-01-03T09:30+00:00", head="abcdef1234", last_pr=9, current_day=3,
                              next_step="Day 03 Track A: `run`", stop_after=3, open_prs=[]),
                     days=[a_day(1), a_day(2), a_day(3, "active")], meta=dict(project="toy", caveats=["Names, not meaning."])), **more)


def promise(cid, ticked=True, **more):
    return dict(dict(id=cid, day=int(cid[1]), tag="new", claim=f"`{cid}` holds.", ticked=ticked, cited=True, test_found=True,
                     seen_red=dict(state=True, lines=[], none=[]), replaced_by=[], abilities=[]), **more)


def cell(cid, n, state):
    return dict(criterion=cid, day=f"0{cid[1]}", n=n, state=state, mixed=False, checks=[])


def run_step(n, day, ended, fixes=0, crashes=0, parks=()):
    """One step the driver started, as driver_runs.json holds it: `ended` is how it ended, `parks` its parks."""
    return dict(step=f"Step {n}.", day=day, prefix=n, sessions=[], fixes=fixes, crashes=crashes, pr=None, merged=None,
                parks=list(parks), ended=ended)


def park(issue, by, line="Waiting for a decision."):
    return dict(at="2026-01-02T09:00:00Z", line=line, by=by, issue=issue)


def an_issue(number, opened, closed=None):
    return dict(number=number, title=f"Park {number}", url=f"https://example.com/issues/{number}", opened=opened, closed=closed)


ABILITIES = dict(abilities=[dict(key="a", name="Runs", role="rung"), dict(key="b", name="Stops", role="rung")])
# One promise in each state a tile can be in: C1.1's newest re-check found the code broken, and C1.3 was
# re-checked before C2.1 replaced it.
PROMISES = dict(
    criteria_index=[promise("C1.1", abilities=["a"]), promise("C1.2", abilities=["b", "a"]), promise("C1.3", replaced_by=["C2.1"]),
                    promise("C1.4", ticked=False), promise("C1.5"), promise("C2.1", abilities=["a"]), promise("C2.2", tag="hold"),
                    promise("C2.3"), promise("C3.1", ticked=False)],
    replay=dict(state="loaded", merges=[dict(n=1, pr=5), dict(n=2, pr=8)], cells=[
        cell("C1.1", 1, "holds"), cell("C1.3", 1, "holds"), cell("C1.1", 2, "code broken"), cell("C1.2", 2, "holds"), cell("C2.1", 2, "holds, never broken"),
        cell("C2.2", 2, "break no longer applies"), cell("C2.3", 2, "live only")]))


@unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
class ModelTest(unittest.TestCase):
    def test_the_header_says_when_the_data_was_read_and_what_is_next(self):
        head = model(data())["head"]
        self.assertEqual((head["project"], head["when"], head["commit"], head["demo"]), ("toy", "3 Jan 2026 at 09:30", "abcdef1", False))
        self.assertEqual(head["now"], "Days 1 to 2 are closed and Day 3 is in progress.")
        self.assertEqual(head["next"], "Day 03 Track A: `run`")
        self.assertEqual(head["took"], "")

    def test_the_header_says_how_many_dates_the_days_took(self):
        # A Day is a step of the plan, not a calendar day: two Days share a date here. The Day in progress is not
        # counted, and neither is a pull request outside any Day that merged later, whatever Day its row carries.
        days = [a_day(1, worked=["2026-01-02", "2026-01-02"]), a_day(2, worked=["2026-01-02", "2026-01-03"]), a_day(3, "active", worked=["2026-01-06", "2026-01-06"])]
        rows = [dict(pr=4, date="2026-01-05", day=2)]
        self.assertEqual(model(data(days=days, rows=rows))["head"]["took"], "Days 1 to 2 took 2 dates")

    def test_what_needs_attention_is_grouped_by_reason_and_detail(self):
        got = model(data(attention=[dict(id="C1.1", reason="evidence_missing", detail="Replay report: absent"),
                                    dict(id="C1.2", reason="evidence_missing", detail="Replay report: absent"),
                                    dict(id="Day 2", reason="a_new_reason", detail="x")]))["attention"]
        self.assertEqual(got, dict(total=3, groups=[
            dict(label="Evidence missing", detail="Replay report: absent", ids=["C1.1", "C1.2"]),
            dict(label="a_new_reason", detail="x", ids=["Day 2"])]))

    def test_graph_3_counts_each_abilitys_pull_requests_by_day_and_outside_any_day(self):
        story = lambda n, day, ability: dict(number=n, day=day, ability=ability, title="t")
        g = model(data(user_stories=dict(ABILITIES, stories=[story(2, 1, "a"), story(1, 1, "a"), story(3, 2, "b"), story(4, None, "a"),
                                                             story(5, 1, "gone")]),
                       hand_offs=[dict(to=3, picked=True), dict(to=3, picked=False), dict(to=4, picked=False, id="H02.1"),
                                  dict(to=4, picked=False)]))["g3"]
        self.assertEqual([(c["label"], c["mark"]) for c in g["cols"]], [("1", "✓"), ("2", "✓"), ("3", "now"), ("No Day", "")])
        self.assertEqual([(r["name"], [c["n"] for c in r["cells"]]) for r in g["rows"]],
                         [("Runs", [2, 0, 0, 1]), ("Stops", [0, 1, 0, 0]), ("No ability named", [1, 0, 0, 0])])
        first = g["rows"][0]["cells"][0]
        self.assertEqual((first["t"], first["b"], first["level"]),
                         ("Runs · Day 1", ["2 merged pull requests grew this ability on Day 1: #1, #2."], 1))
        self.assertEqual(g["rows"][1]["cells"][0]["b"], ["No pull request grew this ability on Day 1."])
        self.assertEqual(g["read"]["t"], "5 merged pull requests, each tagged with the ability it grew")
        self.assertEqual(g["read"]["b"], ["Days 1 to 2 are closed and Day 3 is in progress. 1 of the 2 notes earlier Days left for Day 3 "
                                          "were picked up; 2 more wait for Day 4, 1 of them numbered. The plan stops for the maintainer after Day 3."])
        self.assertEqual(g["table"]["rows"][0], ["Runs", 2, 0, 0, 1, 3])

    def test_graph_4_gives_each_promise_the_state_of_its_newest_recheck(self):
        g = model(data(**PROMISES))["g4"]
        self.assertEqual({t["id"]: t["status"] for r in g["rows"] for t in r["tiles"]}, {
            "C1.1": "broken", "C1.2": "proven", "C1.3": "replaced", "C1.4": "open", "C1.5": "unchecked",
            "C2.1": "unproven", "C2.2": "repair", "C2.3": "skipped", "C3.1": "building"})
        self.assertEqual([r["count"] for r in g["rows"]], ["1 of 2 proven", "0 of 3 proven", "not yet in force"])
        self.assertEqual([k["text"] for k in g["key"]], [
            "Proven 1", "Passes, not yet proven 1", "Needs repair 1", "Broken 1", "Not checked here 1", "Replaced 1",
            "Not yet in force 1", "Left unticked 1", "Not re-checked yet 1"])
        self.assertEqual(g["read"]["t"], "1 of the 5 promises re-checked are proven; 1 is broken")
        self.assertIn("1 passes but is not yet proven, 1 needs repair and 1 cannot be checked on this computer.", g["read"]["b"][0])
        self.assertIn("Last re-check: pull request #8, 1 change ago.", g["read"]["b"][0])

    def test_a_tile_says_its_promise_its_evidence_and_its_last_recheck(self):
        tiles = {t["id"]: t for r in model(data(**PROMISES, user_stories=ABILITIES))["g4"]["rows"] for t in r["tiles"]}
        self.assertEqual(tiles["C2.2"]["t"], "C2.2 · must keep holding · Needs repair: the code moved, so the planted bug could not be put back")
        self.assertEqual(tiles["C1.3"]["t"], "C1.3 · new behaviour · Replaced: by C2.1")
        self.assertEqual(tiles["C1.2"]["b"], [
            "`C1.2` holds.",
            "✓ ticked at the close · ✓ cites its pull request · ✓ names a test that exists · ✓ a failure was recorded when it was built",
            "Last re-checked after pull request #8, 1 change ago. It grew “Stops”, and also “Runs”."])
        self.assertEqual(tiles["C3.1"]["b"], ["`C3.1` holds.", "No evidence yet: the Day is not closed."])

    def test_the_trust_strip_counts_the_promises_at_every_recheck(self):
        # C1.3 held at the first re-check, and is in neither count: a replaced promise is no longer one.
        g = model(data(**PROMISES))["g4"]
        self.assertEqual([(h["pr"], h["total"], h["counts"]) for h in g["hist"]], [
            (5, 1, dict(proven=1, unproven=0, repair=0, broken=0, skipped=0)),
            (8, 5, dict(proven=1, unproven=1, repair=1, broken=1, skipped=1))])
        self.assertEqual(g["hist"][1]["t"], "Re-check after pull request #8: 1 of 5 proven")
        self.assertIn("1 proven of 1 at first, 1 of 5 now.", g["histSay"])

    def test_with_no_recheck_on_record_graph_4_says_so(self):
        g = model(data(criteria_index=PROMISES["criteria_index"]))["g4"]
        self.assertEqual(g["read"]["t"], "No re-check of the promises is on record")
        self.assertEqual(g["hist"], [])

    def test_graph_5_draws_a_promise_under_its_first_ability_and_the_untied_ones_last(self):
        story = lambda n, day, ability: dict(number=n, day=day, ability=ability, title="t")
        g = model(data(**PROMISES, user_stories=dict(ABILITIES, stories=[story(1, 1, "a"), story(2, 1, "b"), story(3, 2, "a")])))["g5"]
        self.assertEqual([(r["name"], [(x["day"], [t["id"] for t in x["tiles"]]) for x in r["groups"]], r["count"]) for r in g["rows"]], [
            ("Runs", [(1, ["C1.1"]), (2, ["C2.1"])], "0 of 2 proven · 2 pull requests"),
            ("Stops", [(1, ["C1.2"])], "1 of 1 proven · 1 pull request"),
            ("Not tied to an ability yet", [(1, ["C1.3", "C1.4", "C1.5"]), (2, ["C2.2", "C2.3"]), (3, ["C3.1"])],
             "6 promises, not yet tied to a pull request")])
        self.assertEqual(g["read"]["t"], "“Stops” is the best proven: 1 of its 1 re-checked promise")
        self.assertEqual(g["read"]["b"], ["“Runs” has none proven yet. 1 promise touches more than one ability and is drawn under the one "
                                          "most of its pull requests grew, the first named when they tie."])

    def test_graph_5_ties_an_open_days_built_promise_to_the_pull_request_that_built_it(self):
        story = dict(number=7, day=3, ability="b", title="t")
        model_out = model(data(criteria_index=[promise("C3.1", ticked=False), promise("C3.2", ticked=False)],
                               user_stories=dict(ABILITIES, stories=[story]),
                               look_ahead=dict(columns=[dict(pr=None, got=[]), dict(pr=7, got=["C3.1"])], pending=None, hand_offs=[]),
                               rows=[dict(pr=None, kind="origin", day=0), dict(pr=7, kind="code", day=3, own_day=3)]))
        rows = model_out["g5"]["rows"]
        self.assertEqual([(r["name"], [(x["day"], [t["id"] for t in x["tiles"]]) for x in r["groups"]]) for r in rows],
                         [("Runs", []), ("Stops", [(3, ["C3.1"])]), ("Day 3, still being built", [(3, ["C3.2"])])])
        self.assertEqual(rows[1]["count"], "1 promise · 1 pull request")
        self.assertEqual(rows[2]["count"], "1 promise, not yet tied to a pull request")
        tiles = {t["id"]: t for r in model_out["g4"]["rows"] for t in r["tiles"]}
        self.assertIn("Built by pull request #7. No evidence yet: the Day is not closed.", tiles["C3.1"]["b"])

    def test_an_ability_with_no_promise_says_whether_its_work_was_outside_the_days(self):
        story = lambda n, day, ability: dict(number=n, day=day, ability=ability, title="t")
        rows = model(data(criteria_index=[], user_stories=dict(ABILITIES, stories=[story(1, None, "a"), story(2, 1, "b")])))["g5"]["rows"]
        self.assertEqual([r["note"] for r in rows], ["No promise covers this ability. Its pull requests are work outside the Day specs.",
                                                     "No promise covers this ability yet."])

    def test_graph_6_keeps_each_merges_gap_its_time_open_and_its_failed_check(self):
        row = lambda pr, kind, day, gap, **more: dict(dict(pr=pr, kind=kind, day=day, gap_full=gap, title=f"`{kind}`", date="2026-01-01"), **more)
        check = lambda n, hours, failed=0: dict(number=n, hours=hours, failed=failed, failed_in=["PR checks"] * bool(failed))
        g = model(data(rows=[row(None, "origin", 0, 50.0), row(1, "spec", 1, 54.0, own_day=1), row(2, "code", 1, 48.0, own_day=1),
                             row(3, "close", 1, 48.0, own_day=1), row(4, "other", 1, 47.0),
                             row(5, "code", 1, 47.0, gap_chance=52.0, gap_chance_band=[50.0, 54.0])],
                       verification=[check(1, 0.05), check(2, 2.0, 2), check(3, 0.1), check(4, 0.1), check(5, 0.1)]))["g6"]
        self.assertEqual([k[1] for k in g["key"]], ["Spec merge 1", "Code merge 1", "A Day's close 1", "Other (tooling, dashboard) 2",
                                                   "A check failed before the merge 1"])
        self.assertEqual(g["bands"], [dict(day=0, n=1), dict(day=1, n=5)])
        self.assertEqual([m["y"] for m in g["merges"]], [0.5, 0.1, 0.7, 0.7, 0.8, 0.8])  # the scale runs from 55° down to 45°
        self.assertEqual(g["merges"][0]["t"], "The first commit · the first commit · before Day 1")
        code = g["merges"][2]
        self.assertEqual((code["t"], code["b"]), ("Pull request #2 · code · Day 1", [
            "`code`", "Spec and code 48.0° apart, down 6.0° from the merge before. Open for 2.0 h before it merged. "
                      "A check failed on it first (PR checks)."]))
        self.assertEqual(g["merges"][3]["b"][1], "Spec and code 48.0° apart, unchanged. Open for 6 minutes before it merged. No check failed on it.")
        self.assertGreater(code["h"], g["merges"][1]["h"])  # two hours open draws a taller bar than three minutes
        self.assertEqual(g["read"]["t"], "Now 47.0° apart, where chance alone would give 52.0°")
        self.assertEqual(g["read"]["b"], ["The specs and the code share more names than chance would: nineteen times in twenty, chance gives "
                                          "50.0° to 54.0°. On average a spec merge moved the dot up by 4.0° and a code merge down by 6.0°. "
                                          "1 of 5 pull requests had a check fail before they merged."])
        self.assertEqual(g["table"]["rows"][2], ["#2", "code", 1, "2026-01-01", "48.0", 120, "yes"])
        self.assertEqual(g["table"]["rows"][4][:3], ["#4", "other", ""])
        self.assertEqual(g["merges"][4]["t"], "Pull request #4 · other · outside any Day, merged after Day 1 closed")
        self.assertEqual(g["merges"][5]["t"], "Pull request #5 · other · outside any Day, merged after Day 1 closed")
        self.assertTrue(g["say"].endswith("The first column is the first commit, before any pull request."))

    def test_a_days_spec_change_merged_before_the_day_before_closed_still_belongs_to_its_own_day(self):
        row = lambda pr, kind, day, gap, **more: dict(dict(pr=pr, kind=kind, day=day, gap_full=gap, title=f"`{kind}`", date="2026-01-01"), **more)
        g = model(data(rows=[row(None, "origin", 0, 50.0), row(1, "code", 1, 48.0, own_day=1), row(2, "spec", 1, 54.0, own_day=2),
                             row(3, "other", 1, 47.0), row(4, "close", 1, 48.0, own_day=1), row(5, "other", 1, 47.0)]))["g6"]
        self.assertEqual([m["day"] for m in g["merges"]], [0, 1, 2, 0, 1, 0])
        self.assertTrue(g["merges"][2]["t"].endswith("· spec · Day 2"))
        self.assertTrue(g["merges"][3]["t"].endswith("outside any Day, merged while Day 2 was open"))
        self.assertEqual(g["bands"], [dict(day=0, n=1), dict(day=1, n=1), dict(day=2, n=2), dict(day=1, n=1), dict(day=2, n=1)])
        self.assertTrue(g["merges"][5]["t"].endswith("outside any Day, merged while Day 2 was open"))

    def test_graph_7_puts_each_defect_at_the_gate_that_caught_it(self):
        defect = lambda i, found, cause, made, same=None: dict(id=i, found=found, cause=cause, made=made, same_as=same, problem=None)
        days = [a_day(1, defects=[defect("D1.1", "auditor", "spec", "Day 01"), defect("D1.2", "Track A", "implementation", "none")],
                      relabel=dict(stage=[3, 4], cause=[4, 4], made=[2, 4])),
                a_day(2, defects=[defect("D2.1", "close", "process", "Day 01", "D1.1"), defect("D2.2", "seen red", "a typo", None)]),
                a_day(3, "active")]
        g = model(data(days=days, defect_recurrence=dict(recurrences=[dict(id="D2.1", same_as="D1.1")]),
                       gate_report=dict(gates=[dict(gate="auditors", found="auditor", defects=1, runs=2, cost=1.0),
                                               dict(gate="hooks", found=None, defects=0, runs=1, cost=0.1)])))["g7"]
        self.assertEqual([[len(c) for c in r["cells"]] for r in g["rows"]], [[1, 0, 0, 1, 0, 0], [0, 1, 0, 0, 1, 0], [0] * 6])
        self.assertEqual([r["note"] for r in g["rows"]], ["3 of 12", "not read yet", "read at its close"])
        dots = {o["id"]: o for r in g["rows"] for o in r["dots"]}
        self.assertEqual([(o["id"], o["cause"], o["escaped"], o["back"]) for o in dots.values()], [
            ("D1.1", "spec", False, False), ("D1.2", "implementation", False, False), ("D2.1", "process", True, True),
            ("D2.2", "other", False, False)])
        self.assertEqual((dots["D2.1"]["t"], dots["D2.1"]["b"]), (
            "D2.1 · process · caught by: the close",
            ["Made on Day 1 and caught on Day 2: it escaped for 1 Day. The same problem as D1.1, back again."]))
        self.assertEqual(dots["D1.2"]["b"], ["Made outside any Day: in the plan, a tool or a machine. Noticed by: Track A."])
        self.assertEqual(dots["D2.2"]["b"], ["Caught on Day 2; its line does not say which Day made it."])
        self.assertEqual([x["sub"] for x in g["gates"]], ["1 caught · 2 runs · $1.00", "1 caught", "0 caught",
                                                         "1 caught · tracks, reviews, the session", "1 caught", "0 caught"])
        self.assertEqual(g["read"]["t"], "4 defects; the auditors caught 1 of them before any code was written")
        self.assertEqual(g["read"]["b"], ["1 was in a spec. 1 escaped from an earlier Day and 1 came back. A second reader gave 3 of 12 "
                                          "tags differently. Each catch cost about $1.00 at the auditors."])

    def test_graph_8_adds_up_each_dates_sessions_and_what_the_hooks_stopped(self):
        token = lambda date, agent, cost, cut=0: dict(date=date, agent=agent, cost=cost, replies=10, cut=cut)
        g = model(data(days=[a_day(1, worked=["2026-01-02", "2026-01-02"]), a_day(2, "active")],
                       tokens=[token("2026-01-01", "main", 2.0, 1), token("2026-01-01", "spec-auditor", 0.5),
                               token("2026-01-02", "main", 3.0, 2), token("2026-01-02", "implementer", 0.5)],
                       refusals=[dict(date="2026-01-02", guard="read-guard", refused=3)],
                       rows=[dict(pr=1, date="2026-01-02", day=1), dict(pr=2, date="2026-01-02", day=1), dict(pr=3, date="2026-01-04", day=1)]))["g8"]
        self.assertEqual([(b["t"], b["setup"], b["days"]) for b in g["bars"]], [
            ("1 Jan · before Day 1 · $2.50", True, []), ("2 Jan · Day 1 · $3.50", False, [1])])
        self.assertEqual(g["bars"][1]["b"], ["Main session $3.00, auditors $0.00, implementer and others $0.50. 20 replies. The hooks refused "
                                             "3 calls (3 by the read-guard) and cut 2 long outputs. 2 pull requests merged that date: $1.75 "
                                             "each, all sessions."])
        self.assertEqual([k[1] for k in g["key"]], ["Main session $5.00", "Auditors and the implementer $1.00"])
        # The dollars are list prices and not a bill, and the last date is counted only up to its close: the page says both.
        self.assertEqual(g["read"]["t"], "$6.00 of tokens at list prices; 83% of it in the main session")
        self.assertEqual(g["read"]["b"], ["1 date of set-up cost $2.50 before Day 1. The Days cost $3.50 over 1 date, on which 2 pull requests merged. "
                                          "The hooks refused 3 calls and cut 3 long outputs. Counted on the maintainer's computer, "
                                          "so 2 Jan is counted only up to the last count run on it, and nothing after it is in yet."])
        self.assertEqual(g["say"], "What each date's tokens would cost on the pay-per-token API, at list prices. This repository's sessions only, "
                                   "counted on the maintainer's computer. The maintainer pays a flat subscription, so this measures usage and is not a bill.")

    def test_graph_9_adds_each_days_changed_lines_by_what_the_file_is(self):
        g = model(data(rows=[dict(pr=None, day=0, work=dict(spec=7)),
                             dict(pr=1, day=0, own_day=1, work=dict(spec=10, context=5, prod=20, test=40, tooling=0)),
                             dict(pr=2, day=1, own_day=1, work=dict(prod=10, test=20)),
                             dict(pr=3, day=1, work=dict(prod=5, test=100, tooling=50)),
                             dict(pr=4, day=1, own_day=2, kind="spec", work=dict(spec=30))]))["g9"]
        first = g["bars"][0]
        self.assertEqual((first["w"], first["total"], first["prs"], first["ratio"]), (dict(spec=15, prod=30, test=60, tooling=0), 105, 2, "2.0"))
        self.assertEqual(first["b"], ["Spec and agent context 15, production code 30, tests 60, tooling 0. 2 pull requests merged. "
                                      "2.0 test lines for each production line."])
        self.assertEqual((first["aside"]["total"], first["aside"]["prs"]), (155, 1))
        self.assertEqual(first["aside"]["t"], "Outside any Day · merged while Day 1 was open or after it closed · 155 lines changed")
        self.assertEqual((g["bars"][1]["total"], g["bars"][1]["prs"], g["bars"][1]["aside"]), (30, 1, None))
        self.assertEqual(g["bars"][2]["t"], "Day 3 (in progress) · 0 lines changed")
        self.assertEqual(g["read"]["t"], "135 lines changed in Days 1 to 3; the largest share is tests")
        self.assertIn("Another 7 lines came before Day 1.", g["read"]["b"][0])
        self.assertIn("Another 155 lines, in 1 pull request, are outside any Day (dashboard and tooling work)", g["read"]["b"][0])
        self.assertEqual(g["max"], 155)
        self.assertEqual(g["table"]["rows"][0][-4:], [2, "2.0", 155, 1])

    def test_graph_2_marks_a_day_over_the_baseline_and_keeps_a_yardstick_never_counted_apart(self):
        value = lambda day, v, text: dict(day=day, value=v, text=text)
        got = model(data(yardsticks=dict(days=[1, 2], problems=[], rows=[
            dict(key="cost", name="Cost of each merged pull request", unit="$", decimals=2, baseline=1.5,
                 values=[value(1, 1.2, "`$6` over 5"), value(2, 1.8, "$9 over 5")]),
            dict(key="parks", name="Times it stopped", unit="", decimals=0, baseline=None,
                 values=[value(1, None, "none yet"), value(2, None, "none yet: only fake projects")])])))
        g, cost = got["g2"], got["g2"]["rows"][0]
        self.assertEqual(g["cols"], [1, 2, 3])
        self.assertEqual([(c["text"], c["over"]) for c in cost["cells"]], [("$1.20", False), ("$1.80", True), ("·", False)])
        self.assertEqual((cost["cells"][1]["t"], cost["cells"][1]["b"]),
                         ("Cost of each merged pull request · Day 2: $1.80, above the baseline of $1.50", ["$9 over 5"]))
        self.assertEqual(cost["cells"][2]["b"], ["Day 3 is in progress: it is counted at its close."])
        self.assertEqual((cost["note"], round(cost["line"], 3)), ("kit's baseline: $1.50", 0.833))
        # The row already says "Not measured yet": the cell's own "none yet:" is not said after it.
        self.assertEqual(g["waiting"], [dict(name="Times it stopped", why="only fake projects")])
        self.assertEqual(g["read"]["t"], "Above the kit's baseline on 1 of 2 Days for cost")
        self.assertIn(["Times it stopped", "only fake projects."], got["notMeasured"])
        self.assertEqual(got["notMeasured"][-1][0], "Where a date's time goes, and who waits for whom")

    def test_graph_1_counts_the_promises_built_and_written_at_each_merge_and_what_is_left_before_the_stop(self):
        # The unnumbered hand-off counts in `open` but not in the numbered count the graph draws.
        col = lambda pr, built, got, written, open_numbered: dict(pr=pr, built=built, got=got, written=written,
                                                                   open=open_numbered + 1, open_numbered=open_numbered, opened=[], closed=[])
        look = dict(columns=[col(None, 0, [], 10, 0), col(1, 0, [], 14, 1), col(2, 2, ["C2.1", "C2.2"], 14, 1), col(3, 3, ["C2.3"], 14, 1)],
                    pending=dict(day=3, tracks=[dict(track="F", ids=["C3.1", "C3.2"]), dict(track="G", ids=["C3.3"])], at_close=["C3.4"]),
                    hand_offs=[dict(id="H03.1", to=[4], closed=None), dict(id=None, to=[4], closed=None), dict(id="H02.1", to=[4], closed="Day 3")])
        rows = [dict(pr=None, kind="origin", day=0, title="The first commit"), dict(pr=1, kind="spec", day=2, own_day=2, title="`spec`"),
                dict(pr=2, kind="code", day=2, own_day=2, title="`code`"), dict(pr=3, kind="close", day=2, own_day=2, title="`close`")]
        g = model(data(rows=rows, look_ahead=look, order=[1, 2, 3, 4], now=dict(current_day=3, stop_after=4)))["g1"]
        self.assertEqual([(m["built"], m["written"], m["open"]) for m in g["merges"]], [(0, 10, 0), (0, 14, 1), (2, 14, 1), (3, 14, 1)])
        self.assertEqual((g["merges"][1]["t"], g["merges"][1]["b"]), ("Pull request #1 · spec · Day 2", [
            "`spec`", "Its spec wrote 4 promises. Built no promise. 0 of 14 built after it. 1 hand-off open after it."]))
        self.assertEqual(g["merges"][2]["b"][1], "Built C2.1, C2.2. 2 of 14 built after it. 1 hand-off open after it.")
        self.assertEqual([(a["label"], a["day"], a["built"]) for a in g["ahead"]], [("F", 3, 5), ("G", 3, 6), ("close", 3, 7)])
        self.assertEqual((g["ahead"][0]["t"], g["ahead"][0]["b"]), ("Day 3 track F · specified, not merged",
                                                                     ["Would build C3.1, C3.2.", "5 of 14 built after it."]))
        self.assertEqual(g["ahead"][2]["b"][0], "The close ticks each promise with its evidence and leaves the hand-offs for the Days after.")
        self.assertEqual([(u["day"], u["waits"], u["ids"]) for u in g["unknown"]], [(4, 1, ["H03.1"])])
        self.assertEqual((g["pMax"], g["hMax"], g["stop"]), (20, 6, 4))
        self.assertEqual(g["bands"], [dict(day=0, n=1), dict(day=2, n=3), dict(day=3, n=3)])
        self.assertEqual(g["read"]["t"], "3 of 14 promises built · 4 promises and Day 4 before the stop")
        self.assertEqual(g["read"]["b"], ["Day 3 has 2 tracks left (F: 2, G: 1) and its close.",
                                          "Day 4 has no spec, so its size cannot be drawn. 1 numbered hand-off waits for it (H03.1).",
                                          "After Day 4 the plan stops for the maintainer. What comes after is not specified, so the graph "
                                          "ends there and gives no percentage of the whole plan."])
        self.assertEqual([k[1] for k in g["key"]], ["Spec merge 1", "Code merge 1", "A Day's close 1", "Other (tooling, dashboard) 0",
                                                   "Promises built", "Promises written", "Hand-offs open", "Specified, not merged", "Not specified yet"])
        self.assertEqual(g["table"]["head"], ["Merge", "Kind", "Day", "Built", "Written", "Hand-offs open"])
        self.assertEqual(g["table"]["rows"][0], ["start", "the first commit", "", 0, 10, 0])
        self.assertEqual(g["table"]["rows"][-1], ["close", "not merged", 3, 7, 14, ""])

    def test_graph_1_with_nothing_ahead_and_no_stop_ends_at_today(self):
        col = lambda pr, built, got: dict(pr=pr, built=built, got=got, written=2, open=0, open_numbered=0, opened=[], closed=[])
        look = dict(columns=[col(None, 0, []), col(1, 1, ["C1.1"])], pending=None, hand_offs=[])
        g = model(data(rows=[dict(pr=None, kind="origin", day=0, title="The first commit"), dict(pr=1, kind="spec", day=1, own_day=1, title="`spec`")],
                       look_ahead=look, now=dict(current_day=3, stop_after=None)))["g1"]
        self.assertEqual((g["ahead"], g["unknown"], g["stop"]), ([], [], None))
        self.assertEqual(g["read"]["t"], "1 of 2 promises built")

    def test_graph_1_without_look_ahead_data_says_nothing_is_merged(self):
        g = model(data())["g1"]
        self.assertNotIn("error", g)
        self.assertEqual((g["merges"], g["read"]["t"]), ([], "Nothing is merged yet"))

    def test_graph_2_draws_each_rows_average_so_far_inside_its_scale(self):
        value = lambda day, v, text: dict(day=day, value=v, text=text)
        g = model(data(yardsticks=dict(days=[1, 2], problems=[], rows=[
            dict(key="cost", name="Cost of each merged pull request", unit="$", decimals=2, baseline=1.5,
                 values=[value(1, 1.2, "$1.20 over 5"), value(2, 1.8, "$9 over 5")], average=[1.2, 2.4], average_over="pull requests"),
            dict(key="replies", name="Replies", unit="", decimals=0, baseline=None, values=[value(1, 40, "40"), value(2, 50, "50")]),
            # A count's average keeps one decimal, and a noun the page has no singular for is left out.
            dict(key="reread", name="Read again", unit="", decimals=0, baseline=None, values=[value(1, 1, "1"), value(2, 0, "0")],
                 average=[1.0, 0.83], average_over="tokens written")])))["g2"]
        cost, replies, reread = g["rows"]
        self.assertEqual(([a["text"] for a in reread["avg"]], reread["avgNote"]), (["1.0", "0.8"], "average so far: 0.8"))
        self.assertEqual([(a["day"], a["text"], round(a["y"], 3)) for a in cost["avg"]], [(1, "$1.20", 0.5), (2, "$2.40", 1.0)])
        self.assertEqual((cost["avgNote"], round(cost["line"], 3)), ("average so far: $2.40 over every pull request", 0.625))
        self.assertEqual((replies["avg"], replies["avgNote"]), ([], ""))

    def test_graph_10_puts_one_date_on_the_clock_of_the_machine_that_recorded_the_sessions(self):
        # The sessions are stamped +01:00, GitHub's times are UTC: a pull request opened at 09:30Z sits at 10:30 on
        # the clock. A stretch across midnight is clipped to each date, and the last date is the one shown first.
        s = lambda day, agent, start, end, n: {"date": start[:10], "day": day, "agent": agent, "from": start, "to": end, "replies": n}
        clock = dict(sessions=[s(2, "main", "2026-01-02T08:00:00+01:00", "2026-01-02T10:00:00+01:00", 12),
                               s(2, "implementer", "2026-01-02T09:00:00+01:00", "2026-01-02T09:30:00+01:00", 4),
                               s(1, "spec-auditor", "2026-01-01T23:50:00+01:00", "2026-01-02T00:10:00+01:00", 2)],
                     prs=[dict(number=7, day=2, kind="code", branch="day-02/track-a", opened="2026-01-02T09:30:00Z", merged="2026-01-02T10:00:00Z",
                               checks=dict(start="2026-01-02T09:31:00Z", end="2026-01-02T09:40:00Z", runs=4, failed=1)),
                          dict(number=6, day=1, kind="spec", branch="day-01/spec-x", opened="2026-01-01T22:00:00Z", merged="2026-01-02T01:00:00Z", checks=None)])
        got = model(data(clock=clock))
        g = got["g10"]
        self.assertEqual(([d["date"] for d in g["dates"]], g["at"], g["zone"]), (["2026-01-01", "2026-01-02"], 1, "UTC+01:00"))
        jan2 = g["dates"][1]
        self.assertEqual((jan2["label"], jan2["days"]), ("2 Jan", [1, 2]))
        lanes = {lane["name"]: lane for lane in jan2["lanes"]}
        self.assertEqual(list(lanes), ["Main session", "Implementer", "Auditors", "Pull request open", "Checks running", "Maintainer merges"])
        pr7 = next(b for b in lanes["Pull request open"]["bars"] if "#7" in b["t"])
        self.assertEqual((round(pr7["x"], 3), round(pr7["w"], 3), pr7["cls"], pr7["days"]), (round(630 / 14.4, 3), round(30 / 14.4, 3), "code", [2]))
        self.assertEqual(pr7["t"], "Pull request #7 · day-02/track-a · open 10:30 to 11:00")
        self.assertEqual(pr7["b"], ["Open for 30 minutes before it merged.", "Its checks were running for 9 minutes: 4 workflow runs, 1 of them failed."])
        pr6 = next(b for b in lanes["Pull request open"]["bars"] if "#6" in b["t"])
        self.assertEqual((pr6["from"], pr6["to"], pr6["cls"]), ("00:00", "02:00", "spec"))
        self.assertIn("opened on an earlier date", pr6["b"][0])
        self.assertEqual([(b["from"], b["to"]) for b in lanes["Auditors"]["bars"]], [("00:00", "00:10")])
        self.assertEqual([lane["sub"] for lane in jan2["lanes"]], ["busy 2 h 0 min", "busy 30 minutes", "busy 10 minutes", "2 pull requests, 2 h 30 min in all",
                                                             "on 1 pull request, running for 9 minutes, 1 with a failure", "2 merges"])
        self.assertEqual([b["cls"] for b in lanes["Checks running"]["bars"]], ["failed"])
        self.assertEqual(jan2["read"]["t"], "2 Jan: 2 pull requests merged, half of them open for 30 minutes or less")
        self.assertEqual(jan2["read"]["b"], ["Work of Days 1 to 2.", "The main session was busy for 2 h 0 min, the implementer for 30 minutes and the auditors for 10 minutes.",
                                             "Nothing ran from 00:10 to 08:00.", "The longest waits for a merge: #6 (3 h 0 min) and #7 (30 minutes).",
                                             "Times are on the clock of the machine that recorded the sessions (UTC+01:00)."])
        self.assertEqual(jan2["table"]["head"], ["Lane", "What", "From", "To", "Minutes"])
        self.assertIn(["Pull request open", "Pull request #7", "10:30", "11:00", 30], jan2["table"]["rows"])
        self.assertEqual((g["read"], g["table"]), (jan2["read"], jan2["table"]))
        self.assertEqual([x["t"] for x in g["hours"]][:3], ["00:00", "03:00", "06:00"])
        self.assertNotIn("Where a date's time goes, and who waits for whom", [n for n, _ in got["notMeasured"]])

    def test_graph_10_draws_what_a_session_waited_on_inside_its_busy_bar(self):
        s = lambda agent, start, end, **more: {"date": start[:10], "day": 2, "agent": agent, "from": start, "to": end, "replies": 5, **more}
        clock = dict(prs=[], sessions=[
            s("main", "2026-01-02T08:00:00+01:00", "2026-01-02T10:00:00+01:00", ran=dict(tests=1800, checks=600, other=60),
              runs=[["2026-01-02T08:10:00+01:00", "2026-01-02T08:40:00+01:00", "tests"], ["2026-01-02T09:00:00+01:00", "2026-01-02T09:10:00+01:00", "checks"]]),
            s("implementer", "2026-01-02T09:00:00+01:00", "2026-01-02T09:30:00+01:00", ran=dict(tests=300),
              runs=[["2026-01-02T09:05:00+01:00", "2026-01-02T09:10:00+01:00", "tests"]])])
        g = model(data(clock=clock))["g10"]
        self.assertEqual(g["runs"], [["tests", "waiting on tests"], ["checks", "waiting on GitHub's checks"], ["other", "waiting on another command"]])
        date = g["dates"][0]
        main = date["lanes"][0]
        # The waits are drawn over the busy bar, which keeps its whole length: busy includes them.
        self.assertEqual([(b["cls"], b["from"], b["to"]) for b in main["bars"]],
                         [("busy", "08:00", "10:00"), ("run tests", "08:10", "08:40"), ("run checks", "09:00", "09:10")])
        self.assertEqual([lane["sub"] for lane in date["lanes"]][:2], ["busy 2 h 0 min, 41 minutes of it waiting on commands", "busy 30 minutes, 5 minutes of it waiting on commands"])
        self.assertEqual(main["bars"][0]["b"], ["5 replies, with no gap longer than 5 minutes. 41 minutes of it waiting on commands it ran: "
                                                "30 minutes on tests, 10 minutes on GitHub's checks and 1 minute on other commands."])
        self.assertEqual(main["bars"][1]["t"], "Main session · waiting on tests 08:10 to 08:40")
        self.assertEqual(date["read"]["b"][1:3], [
            "The main session was busy for 2 h 0 min and the implementer for 30 minutes.",
            "Of that, the sessions waited 46 minutes on commands they had run: 35 minutes on tests, 10 minutes on GitHub's checks and "
            "1 minute on other commands. The wait on GitHub's checks is drawn again under Checks running."])
        self.assertIn(["Main session", "Main session, waiting on tests", "08:10", "08:40", 30], date["table"]["rows"])
        self.assertIn(["Main session", "Main session", "08:00", "10:00", 120], date["table"]["rows"])

    def test_graph_10_keeps_a_wait_on_its_own_date_and_counts_a_minute_two_sessions_share_once(self):
        # A stretch from 23:00 to 01:00 waited half an hour on tests before midnight: none of that wait is the next
        # date's, which gets only half of the two minutes of shorter waits. Two main sessions busy from 08:00 to 10:00
        # and from 09:00 to 11:00 are three hours of the clock, not four: four with the hour after midnight, not five.
        s = lambda start, end, **more: {"date": start[:10], "day": 2, "agent": "main", "from": start, "to": end, "replies": 5, **more}
        clock = dict(prs=[], sessions=[
            s("2026-01-01T23:00:00+01:00", "2026-01-02T01:00:00+01:00", ran=dict(tests=1800, other=120),
              runs=[["2026-01-01T23:10:00+01:00", "2026-01-01T23:40:00+01:00", "tests"]]),
            s("2026-01-02T08:00:00+01:00", "2026-01-02T10:00:00+01:00"), s("2026-01-02T09:00:00+01:00", "2026-01-02T11:00:00+01:00")])
        jan1, jan2 = model(data(clock=clock))["g10"]["dates"]
        self.assertEqual(jan1["lanes"][0]["sub"], "busy 1 h 0 min, 31 minutes of it waiting on commands")
        self.assertEqual(jan1["read"]["b"][2], "Of that, the sessions waited 31 minutes on commands they had run: 30 minutes on tests and 1 minute on other commands.")
        self.assertEqual(jan2["lanes"][0]["sub"], "busy 4 h 0 min, 1 minute of it waiting on commands")
        self.assertEqual(jan2["read"]["b"][1:3], ["The main session was busy for 4 h 0 min.",
                                                  "Of that, the sessions waited 1 minute on commands they had run: 1 minute on other commands."])
        self.assertEqual(jan2["lanes"][0]["bars"][0]["b"], ["5 replies, with no gap longer than 5 minutes. 1 minute of it waiting on commands it ran: 1 minute on other commands."])

    def test_graph_10_draws_the_checks_while_they_ran_and_not_the_time_between_two_pushes(self):
        # Nine workflow runs over two pushes half an hour apart: seven minutes of running, in two bars, the first with the failure.
        at = lambda hm: f"2026-01-02T{hm}Z"
        checks = dict(start=at("09:01:00"), end=at("09:38:00"), runs=9, failed=1, pushes=2,
                      spans=[[at("09:01:00"), at("09:05:00"), 1], [at("09:35:00"), at("09:38:00"), 0]])
        clock = dict(sessions=[], prs=[dict(number=7, day=2, kind="code", branch="day-02/track-a", opened=at("09:00:00"), merged=at("10:59:40"), checks=checks)])
        lanes = {lane["name"]: lane for lane in model(data(clock=clock))["g10"]["dates"][0]["lanes"]}
        # 119 minutes and 40 seconds are two hours, never "1 h 60 min".
        self.assertEqual(lanes["Pull request open"]["bars"][0]["b"], ["Open for 2 h 0 min before it merged.",
                                                                    "Its checks were running for 7 minutes: 9 workflow runs over 2 pushes, 1 of them failed."])
        self.assertEqual([(b["cls"], b["from"], b["to"]) for b in lanes["Checks running"]["bars"]], [("failed", "09:01", "09:05"), ("ok", "09:35", "09:38")])
        self.assertEqual(lanes["Checks running"]["bars"][1]["b"], ["On this pull request in all: 9 workflow runs over 2 pushes, 1 of them failed."])
        self.assertEqual(lanes["Checks running"]["sub"], "on 1 pull request, running for 7 minutes, 1 with a failure")

    def test_graph_10_says_what_the_sessions_are_counted_up_to_and_claims_nothing_after_it(self):
        # The sessions were counted at 12:00 on 2 Jan; GitHub's pull requests go on. A lane empty after the count is not
        # counted yet, and the hours from the last session to a later check are not "nothing ran".
        at = lambda day, hm: f"2026-01-0{day}T{hm}:00Z"
        clock = dict(sessions=[{"date": "2026-01-02", "day": 2, "agent": "main", "from": "2026-01-02T08:00:00+01:00", "to": "2026-01-02T11:00:00+01:00", "replies": 9}],
                     prs=[dict(number=7, day=2, kind="code", branch="day-02/track-a", opened=at(2, "13:00"), merged=at(2, "13:10"),
                               checks=dict(start=at(2, "13:01"), end=at(2, "13:05"), runs=4, failed=0, pushes=1, spans=[[at(2, "13:01"), at(2, "13:05"), 0]])),
                          dict(number=8, day=2, kind="code", branch="day-02/track-b", opened=at(3, "09:00"), merged=at(3, "09:10"), checks=None)])
        jan2, jan3 = model(data(clock=clock, counted=dict(at="2026-01-02T12:00:00+01:00")))["g10"]["dates"]
        self.assertEqual([lane["sub"] for lane in jan2["lanes"]][:3], ["busy 3 h 0 min", "nothing recorded up to 12:00", "nothing recorded up to 12:00"])
        self.assertEqual(jan2["read"]["b"], ["Work of Day 2.", "The main session was busy for 3 h 0 min.",
                                             "The sessions are counted up to 12:00: after that, only GitHub's pull requests and checks are in.",
                                             "The longest wait for a merge: #7 (10 minutes).", "Times are on the clock of the machine that recorded the sessions (UTC+01:00)."])
        self.assertEqual([lane["sub"] for lane in jan3["lanes"]][:3], ["not counted yet"] * 3)
        self.assertEqual(jan3["read"]["b"][1], "The sessions of this date are not counted yet: the count ends at 12:00 on 2 Jan.")
        # With no count on record the page claims no horizon: it says what it has.
        jan2, jan3 = model(data(clock=clock))["g10"]["dates"]
        self.assertEqual(([lane["sub"] for lane in jan3["lanes"]][:3], jan3["read"]["b"][1]), (["nothing recorded"] * 3, "No session was recorded on this date."))
        self.assertIn("Nothing ran from 11:00 to 14:01.", jan2["read"]["b"])

    def test_graphs_6_and_10_give_a_pull_request_the_same_minutes_open(self):
        # Open for 3 minutes 20 seconds. The hours beside it are rounded to 0.06, which is 3.6 minutes: graph 6 said 4.
        clock = dict(sessions=[], prs=[dict(number=1, day=1, kind="code", branch="day-01/track-a", opened="2026-01-01T09:00:00Z", merged="2026-01-01T09:03:20Z", checks=None)])
        got = model(data(rows=[dict(pr=1, kind="code", day=1, own_day=1, gap_full=48.0, title="`code`", date="2026-01-01")],
                         verification=[dict(number=1, hours=0.06, failed=0, failed_in=[])], clock=clock))
        self.assertIn("Open for 3 minutes before it merged.", got["g6"]["merges"][0]["b"][1])
        self.assertEqual(got["g6"]["table"]["rows"][0][5], 3)
        self.assertEqual(got["g10"]["dates"][0]["lanes"][3]["bars"][0]["b"][0], "Open for 3 minutes before it merged.")

    def test_graph_7_reads_a_found_value_as_the_gate_report_does_and_shares_a_gates_dollars_over_the_days_counted(self):
        values = ["The auditor (spec-auditor)", " Seen red ", "break on purpose (D03.2)", "the close", "Track A", "Spec", None, ""]
        self.assertEqual(node(TAGS, values), [sd.found_tag(v) for v in values])
        # Day 2 had a pull request merge after the count, so the auditors' dollar is not shared with its catch.
        defect = lambda i, found, cause, made: dict(id=i, found=found, cause=cause, made=made, same_as=None, problem=None)
        pr = lambda n, day, merged: dict(number=n, day=day, kind="code", branch=f"day-0{day}/track-a", opened="2026-01-01T09:00:00Z", merged=merged, checks=None)
        g = model(data(days=[a_day(1, defects=[defect("D1.1", "The auditor (spec-auditor)", "Spec", "Day 01")]),
                             a_day(2, "active", defects=[defect("D2.1", "auditor", "spec", "Day 02")])],
                       gate_report=dict(gates=[dict(gate="auditors", found="auditor", defects=2, runs=2, cost=1.0)]),
                       clock=dict(sessions=[], prs=[pr(1, 1, "2026-01-01T10:00:00Z"), pr(2, 2, "2026-01-03T10:00:00Z")]),
                       counted=dict(at="2026-01-02T12:00:00+01:00")))["g7"]
        self.assertEqual([[len(c) for c in r["cells"]] for r in g["rows"]], [[1, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0]])
        self.assertEqual(g["rows"][0]["dots"][0]["cause"], "spec")
        self.assertEqual(g["read"]["b"], ["2 were in a spec. 0 escaped from an earlier Day and 0 came back. Each catch cost about $1.00 at the auditors, "
                                          "over the catches of the Days in the count: Day 2 had a pull request merge after it. "
                                          "The gates' runs and dollars are counted up to 12:00 on 2 Jan."])

    def test_graph_8_shares_a_dates_dollars_over_the_pull_requests_merged_before_the_count(self):
        # Counted at 12:00 on 2 Jan (11:00 UTC): #1 had merged, #2 merged an hour later that date and #3 two dates on.
        token = lambda agent, cost: dict(date="2026-01-02", agent=agent, cost=cost, replies=10, cut=0)
        pr = lambda n, merged: dict(number=n, day=1, kind="code", branch="day-01/track-a", opened="2026-01-02T08:00:00Z", merged=merged, checks=None)
        g = model(data(days=[a_day(1, worked=["2026-01-02", "2026-01-02"]), a_day(2, "active")], tokens=[token("main", 3.0), token("implementer", 0.5)],
                       rows=[dict(pr=1, date="2026-01-02", day=1), dict(pr=2, date="2026-01-02", day=1), dict(pr=3, date="2026-01-04", day=1)],
                       clock=dict(sessions=[], prs=[pr(1, "2026-01-02T10:00:00Z"), pr(2, "2026-01-02T12:00:00Z"), pr(3, "2026-01-04T10:00:00Z")]),
                       counted=dict(at="2026-01-02T12:00:00+01:00")))["g8"]
        self.assertTrue(g["bars"][0]["b"][0].endswith("2 pull requests merged that date, 1 of them before the count at 12:00 on 2 Jan: $3.50 each, all sessions."))
        self.assertEqual(g["read"]["b"], ["The Days cost $3.50 over 1 date, on which 1 pull request merged before the count. The hooks refused 0 calls and "
                                          "cut 0 long outputs. Counted on the maintainer's computer up to 12:00 on 2 Jan: 2 pull requests have merged since, "
                                          "and what they cost is not in yet."])
        self.assertEqual((g["table"]["head"][-2:], g["table"]["rows"][0][-2:]), (["Pull requests merged", "Merged before the count"], [2, 1]))

    def test_graph_10_without_any_time_recorded_says_so_under_not_measured(self):
        got = model(data())
        self.assertIn("sessions.json", got["g10"]["empty"])
        self.assertEqual(got["g10"]["dates"], [])
        self.assertEqual(got["notMeasured"][-1][0], "Where a date's time goes, and who waits for whom")
        self.assertEqual(got["notMeasured"][-1][1], got["g10"]["empty"])

    def test_one_graph_that_cannot_read_its_data_leaves_the_others_drawn(self):
        got = model(data(criteria_index=[None]))
        self.assertIn("error", got["g4"])
        self.assertIn("error", got["g5"])
        self.assertEqual([g for g in ("g3", "g6", "g7", "g8", "g9", "g2", "g10") if "error" in got[g]], [])

    def test_data_with_nothing_in_it_still_gives_every_graph_something_to_say(self):
        got = model({})
        self.assertEqual({g: got[g].get("error") for g in ("g3", "g4", "g5", "g6", "g7", "g8", "g9", "g2", "g10")}, dict.fromkeys(
            ("g3", "g4", "g5", "g6", "g7", "g8", "g9", "g2", "g10")))
        self.assertEqual([got[g]["read"]["t"] for g in ("g3", "g4", "g6", "g7", "g8", "g2")], [
            "No merged pull request yet", "No promise yet", "No gap is measured yet", "No defect is recorded yet",
            "No token counts yet", "No yardstick is counted yet"])

    def test_graph_11_places_each_step_by_how_it_ended(self):
        # Steps of every kind: a merge, a merge after two fix rounds, a park the maintainer closed after 70 minutes, a park
        # by a fault whose issue is still open, a parked step whose session crashed, a step still open, and a step with no Day.
        steps = [run_step("A", 1, "merged"), run_step("B", 1, "fixed", fixes=2),
                 run_step("C", 2, "parked", parks=[park(21, "maintainer")]), run_step("D", 2, "parked", parks=[park(22, "fault")]),
                 run_step("E", 2, "parked", crashes=1, parks=[park(23, "maintainer")]), run_step("F", 3, "open"), run_step("G", None, "merged")]
        driver = dict(source="run log", counted=None, steps=steps, parks=[an_issue(21, "2026-01-02T09:00:00Z", "2026-01-02T10:10:00Z"),
                      an_issue(22, "2026-01-02T09:00:00Z"), an_issue(23, "2026-01-02T11:00:00Z", "2026-01-02T11:30:00Z")])
        g = model(data(driver_runs=driver)).get("g11", {})
        rows = g.get("rows", [])
        self.assertEqual([r.get("label") for r in rows], ["Day 1", "Day 2", "Day 3", "No Day"])
        self.assertEqual([[len(c) for c in r.get("cells", [])] for r in rows], [[1, 1, 0, 0], [0, 0, 2, 1], [0, 0, 0, 0], [1, 0, 0, 0]])
        self.assertEqual([(r.get("alone"), r.get("n"), r.get("open")) for r in rows], [(2, 2, 0), (0, 3, 0), (0, 0, 1), (1, 1, 0)])
        dots = [[[(o.get("col"), o.get("fixes"), o.get("crashed"), o.get("wait")) for o in c] for c in r.get("cells", [])] for r in rows]
        self.assertEqual(dots[0], [[("merged", 0, False, None)], [("fixed", 2, False, None)], [], []])
        self.assertEqual(dots[1], [[], [], [("maintainer", 0, False, 70), ("maintainer", 0, True, 30)], [("fault", 0, False, None)]])
        self.assertEqual([c.get("sub") for c in g.get("cols", [])],
                         ["2 steps", "1 step · 2 fix rounds", "2 steps · waited 1 h 40 min", "1 step · the waits are not known"])
        self.assertEqual(g.get("read", {}).get("t"), "6 steps, 3 of them with no person")
        self.assertEqual(g.get("read", {}).get("b", [""])[0], "2 parks for the maintainer and 1 park by a fault. 1 crashed session in 1 step. "
                         "1 step still open. A park is an issue the driver opens with the label \"parked\", so its reason and its wait come from GitHub; "
                         "the fix rounds, the crashes and how a step ended come from the driver's run log.")

    def test_graph_11_without_a_count_says_so_under_not_measured(self):
        g = model(data()).get("g11", {})
        self.assertIn("`driver-runs.json` on the dashboard-data branch", g.get("empty", ""))
        self.assertEqual((g.get("rows"), g.get("read", {}).get("t")), ([], "No step of the driver is counted yet"))
        self.assertIn(["Whether it runs without a person", g.get("empty")], model(data()).get("notMeasured", []))

    def test_graph_11_with_no_step_started_says_so_and_is_not_an_empty_count(self):
        got = model(data(driver_runs=dict(source="run log", counted=None, steps=[], parks=[])))
        g = got.get("g11", {})
        self.assertEqual((g.get("empty"), g.get("rows"), g.get("read", {}).get("t")), (None, [], "The driver has started no step yet"))
        self.assertNotIn("Whether it runs without a person", [n for n, _ in got.get("notMeasured", [])])

    def test_graph_11_says_the_waits_could_not_be_read_when_the_parks_are_unknown(self):
        steps = [run_step("C", 2, "parked", parks=[park(21, "maintainer")])]
        g = model(data(driver_runs=dict(source="run log", counted=None, steps=steps, parks=None))).get("g11", {})
        self.assertEqual([c.get("sub") for c in g.get("cols", [])],
                         ["0 steps", "0 steps · 0 fix rounds", "1 step · the waits could not be read", "0 steps · the waits could not be read"])

    def test_graph_10_draws_the_driver_and_its_parks_on_the_sessions_clock(self):
        # The session is stamped +01:00 and the driver's times are UTC: 09:30Z is 10:30 on the clock. The open park runs to
        # the driver's count, and the driver's lanes are not busy time.
        clock = dict(prs=[], sessions=[{"date": "2026-01-02", "day": 2, "agent": "main", "from": "2026-01-02T08:00:00+01:00",
                                        "to": "2026-01-02T11:00:00+01:00", "replies": 3}])
        step_c = run_step("C", 2, "parked", parks=[park(21, "maintainer")])
        step_c["sessions"] = [dict(session="s1", start="2026-01-02T09:30:00Z", end="2026-01-02T09:45:00Z", cost=0.5, denials=0, fixes=0, crashed=False),
                              dict(session="s2", start="2026-01-02T10:00:00Z", end=None, cost=0.1, denials=0, fixes=0, crashed=True)]
        step_m = run_step("M", 2, "merged")
        step_m.update(pr=7, merged="2026-01-02T10:20:00Z")
        driver = dict(source="run log", counted="2026-01-02T13:00:00Z", steps=[step_c, step_m],
                      parks=[an_issue(21, "2026-01-02T09:00:00Z", "2026-01-02T10:10:00Z"), an_issue(22, "2026-01-02T12:00:00Z")])
        got = model(data(clock=clock, driver_runs=driver)).get("g10", {})
        dates = got.get("dates", [])
        self.assertEqual(len(dates), 1)
        self.assertEqual([lane.get("name") for lane in dates[0].get("lanes", [])][:2], ["Driver", "Parked for the maintainer"])
        driver_lane, parked = dates[0]["lanes"][0], dates[0]["lanes"][1]
        self.assertEqual(sorted((b.get("cls"), b.get("from")) for b in driver_lane.get("bars", [])),
                         [("act", "10:30"), ("act", "11:00"), ("act", "11:20"), ("crash", "11:00")])
        self.assertEqual(sorted(b.get("t") for b in driver_lane.get("bars", [])), sorted([
            "The driver started a session · 10:30", "The driver started a session · 11:00", "The driver saw pull request #7 merged · 11:20",
            "A session crashed · started 11:00"]))
        self.assertEqual(driver_lane.get("sub"), "3 acts, 1 crashed session")
        self.assertEqual([(b.get("cls"), b.get("t"), b.get("from"), b.get("to"), b.get("days")) for b in parked.get("bars", [])],
                         [("park", "Parked · 10:00 to 11:10", "10:00", "11:10", [2]), ("park", "Parked · 13:00 to 14:00", "13:00", "14:00", [])])
        self.assertEqual([b.get("b") for b in parked.get("bars", [])], [["Waited 1 h 10 min: Park 21"], ["Still waiting at the count: Park 22"]])
        self.assertEqual(parked.get("sub"), "2 parks, 2 h 10 min in all")
        self.assertIn("The driver started 2 sessions and waited 2 h 10 min on 2 parks.", dates[0].get("read", {}).get("b", []))
        self.assertEqual(got.get("driver"), True)
        # Without steps the lanes are the session lanes, as they were before the driver's data was drawn.
        plain = model(data(clock=clock, driver_runs=dict(source="run log", counted=None, steps=None, parks=None))).get("g10", {})
        plain_dates = plain.get("dates", [])
        self.assertEqual(len(plain_dates), 1)
        self.assertEqual([lane.get("name") for lane in plain_dates[0].get("lanes", [])],
                         ["Main session", "Implementer", "Auditors", "Pull request open", "Checks running", "Maintainer merges"])
        self.assertEqual(plain.get("driver"), False)

    def test_graph_8_hatches_the_main_session_dollars_after_150k_and_sums_only_the_rows_that_say_so(self):
        # 2 Jan: two main rows, one with the dollars past 150k and one without the key, and an implementer row that is not the main session.
        # 3 Jan: no row says it, so it is not known.
        tokens = [dict(date="2026-01-02", agent="main", cost=3.0, replies=1, cut=0, cost_past_150k=1.0),
                  dict(date="2026-01-02", agent="main", cost=1.0, replies=1, cut=0),
                  dict(date="2026-01-02", agent="implementer", cost=0.5, replies=1, cut=0, cost_past_150k=9.0),
                  dict(date="2026-01-03", agent="main", cost=2.0, replies=1, cut=0)]
        g = model(data(tokens=tokens)).get("g8", {})
        self.assertEqual([x.get("past") for x in g.get("bars", [])], [1.0, None])
        self.assertIn("$1.00 of the main session's $4.00 came after a session passed 150k tokens.", g.get("bars", [{}])[0].get("b", [""])[0])
        self.assertIn("Over 1 date where it is known, $1.00 of the main session's $4.00 came after a session passed 150k tokens.",
                      g.get("read", {}).get("b", [""])[0])
        self.assertIn(["past", "Of the main session, after a session passed 150k tokens $1.00"], g.get("key", []))
        self.assertEqual((g.get("table", {}).get("head", [])[2:4], [r[2:4] for r in g.get("table", {}).get("rows", [])]),
                         (["Main session, $", "Main session after 150k, $"], [["4.00", "1.00"], ["2.00", ""]]))
        plain = model(data(tokens=[dict(date="2026-01-02", agent="main", cost=3.0, replies=1, cut=0)])).get("g8", {})
        self.assertNotIn("past", [k for k, _ in plain.get("key", [])])

    def test_graph_2_counts_the_parks_row_from_the_driver_steps_where_the_notebook_has_no_figure(self):
        steps = [run_step("A", 1, "merged"), run_step("B", 2, "parked", parks=[park(21, "maintainer"), park(22, "fault")]),
                 run_step("C", 2, "merged")]
        yardsticks = dict(days=[1, 2], problems=[], rows=[dict(key="parks", name="Times it stopped", unit="", decimals=0, baseline=None,
                          values=[dict(day=1, value=None, text="none yet"), dict(day=2, value=5, text="5 in the notebook")])])
        g = model(data(yardsticks=yardsticks, driver_runs=dict(source="run log", counted=None, steps=steps, parks=[]))).get("g2", {})
        row = next((r for r in g.get("rows", []) if r.get("key") == "parks"), {})
        self.assertEqual([(c.get("text"), c.get("b")) for c in row.get("cells", [])[:2]],
                         [("0", ["0 parks, counted from the driver's run log; the lab notebook has no figure for this Day yet."]),
                          ("5", ["5 in the notebook"])])
        self.assertEqual((row.get("avg"), [w.get("name") for w in g.get("waiting", [])]), ([], []))


@unittest.skipUnless(shutil.which("node"), "needs node to boot the page")
class BootTest(unittest.TestCase):
    def test_the_page_draws_without_an_error_on_data_with_every_graph_in_it(self):
        out = boot(data(**PROMISES, user_stories=dict(ABILITIES, stories=[dict(number=1, day=1, ability="a", title="t")]),
                        rows=[dict(pr=1, kind="code", day=1, own_day=1, gap_full=40.0, title="t", date="2026-01-01", work=dict(prod=3))],
                        tokens=[dict(date="2026-01-01", agent="main", cost=1.0, replies=1, cut=0)],
                        yardsticks=dict(days=[1], problems=[], rows=[dict(key="cost", name="Cost", unit="$", decimals=2, baseline=1.0,
                                                                         values=[dict(day=1, value=2.0, text="t")])])))
        self.assertEqual((out["error"], out["logged"]), (None, []))
        self.assertEqual(out["eyebrow"], "toy · read from git and GitHub on 3 Jan 2026 at 09:30 · commit abcdef1")
        self.assertTrue(out["banner"]["hidden"])

    def test_the_data_branch_or_a_file_on_it_missing_is_said_on_the_page(self):
        names = ["token-usage.json", "refusals.json", "gates.json", "sessions.json", "counted.json", "driver-runs.json",
                 "replay-history.json"]
        source = lambda commit, absent: dict(branch="dashboard-data", commit=commit, at=None, absent=absent)  # noqa: E731
        whole = boot(data(data=source("abc", [])))
        self.assertEqual((whole["error"], whole["missing"]["hidden"]), (None, True))
        gone = boot(data(data=source(None, names)))
        self.assertFalse(gone["missing"]["hidden"])
        self.assertEqual(gone["missing"]["text"], "The dashboard-data branch is missing, so this page leaves out the dollars, the hooks' refusals, the gates' "
                         "runs and cost, the sessions' times, when the sessions were last counted, the driver's steps and the "
                         "re-checks of finished promises.")
        one = boot(data(data=source("abc", ["replay-history.json"])))
        self.assertEqual(one["missing"]["text"], "The dashboard-data branch has no replay-history.json, so this page leaves out "
                         "the re-checks of finished promises.")
        self.assertTrue(boot(data())["missing"]["hidden"])  # example data, or a page built before the branch: no claim

    def test_the_page_draws_without_an_error_on_data_with_nothing_in_it(self):
        out = boot({})
        self.assertEqual((out["error"], out["logged"]), (None, []))

    def test_a_graph_that_cannot_be_drawn_is_logged_and_does_not_stop_the_page(self):
        out = boot(data(criteria_index=[None]))
        self.assertIsNone(out["error"])
        # The walk-through reads the same list of promises, so it says so too; the other six graphs drew.
        self.assertEqual([line.split(":")[0] for line in out["logged"]], ["g4", "g5", "how this works"])

    def test_the_page_draws_the_driver_runs_without_an_error(self):
        clock = dict(prs=[], sessions=[{"date": "2026-01-02", "day": 2, "agent": "main", "from": "2026-01-02T08:00:00+01:00",
                                        "to": "2026-01-02T11:00:00+01:00", "replies": 3}])
        steps = [run_step("C", 2, "parked", crashes=1, parks=[park(21, "maintainer")]), run_step("D", 2, "fixed", fixes=1)]
        out = boot(data(clock=clock, driver_runs=dict(source="run log", counted="2026-01-02T13:00:00Z", steps=steps,
                                                       parks=[an_issue(21, "2026-01-02T09:00:00Z")])))
        self.assertEqual((out["error"], out["logged"]), (None, []))


class PageFilesTest(unittest.TestCase):
    """What index.html, dashboard.css and dashboard.js must hold, read as text."""

    def test_every_graph_has_its_plot_its_readout_and_its_exact_numbers_folded_under_it(self):
        html = read("index.html")
        for n in range(1, 12):
            section = re.search(rf'<section class="graph" id="g{n}">.*?</section>', html, re.S)
            self.assertIsNotNone(section, f"graph {n}")
            order = [section.group(0).index(f'id="g{n}-{part}"') for part in ("plot", "read", "table")]
            self.assertEqual(order, sorted(order), f"graph {n}")
            self.assertRegex(section.group(0), rf'<details class="exact"><summary>Exact numbers</summary><div class="scroll-x"><table id="g{n}-table">')
            self.assertIn(f'id="g{n}-read" aria-live="polite"', section.group(0))
        self.assertNotIn("<details open", html)

    def test_no_graph_sits_inside_anything_collapsed(self):
        html = read("index.html")
        for n in range(1, 12):
            self.assertIn(f'id="g{n}-plot"', html, f"graph {n}")
            before = html[:html.index(f'id="g{n}-plot"')]
            self.assertEqual(before.count("<details"), before.count("</details>"), f"graph {n}")

    def test_what_graph_6_would_mislead_without_stays_visible_beside_it(self):
        section = re.search(r'<section class="graph" id="g6">.*?</section>', read("index.html"), re.S).group(0)
        visible = re.sub(r"<details.*?</details>", "", section, flags=re.S)
        self.assertIn("The angle matches names, not meaning", visible)
        self.assertIn('href="#cannot-see"', visible)
        self.assertIn('id="cannot-see"', read("index.html"))

    def test_the_page_says_what_a_day_and_a_date_are_and_keeps_the_two_words_apart(self):
        page = read("index.html")
        self.assertIn("<dt>Day</dt><dd>A numbered step of the plan", page)
        self.assertIn("<dt>Date</dt><dd>A calendar date", page)
        self.assertIn('id="words-took"', page)
        self.assertIn("<h2>Where does a date's time go, and who waits for whom?</h2>", page)
        self.assertIn("Dollars are API list prices, as in graph 8, and not what was paid.", page)
        # The plan's step is written "Day": a lower-case "a day" or "each day" would read as a calendar day.
        text = re.sub(r"<[^>]+>", " ", page)
        self.assertEqual(re.findall(r"\b(?:a|an|each|one|the|any|every|later|next|earlier) days?\b", text), [])

    def test_the_eleven_graphs_sit_in_order_under_five_group_headings(self):
        html = read("index.html")
        self.assertEqual(re.findall(r'<section class="graph" id="(g\d+)">', html), [f"g{n}" for n in range(1, 12)])
        heads = ["Where is it going?", "What can it do, and can it be trusted?", "Is the way of working sound?", "What does it take?",
                 "Can it be left alone?"]
        self.assertEqual(re.findall(r'<h2 class="chapter">([^<]*)<small>', html), heads)
        starts = [html.index(f'<h2 class="chapter">{h}<small>') for h in heads]
        group = {1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 3, 9: 3, 10: 3, 11: 4}
        for n, g in group.items():
            at = html.index(f'<section class="graph" id="g{n}">')
            self.assertEqual(max(i for i, s in enumerate(starts) if s < at), g, f"graph {n}")
        for part in ("say", "ladder", "key", "plot", "read", "table"):
            self.assertIn(f'id="g1-{part}"', html)

    def test_the_build_inlines_one_stylesheet_and_one_script_and_fills_one_data_line(self):
        page = sd.build(json.dumps(dict(now=dict(next_step="x"))))
        self.assertNotIn('href="dashboard.css"', page)
        self.assertNotIn('src="dashboard.js"', page)
        self.assertIn("function boot(DATA)", page)
        self.assertIn("--proven:", page)
        self.assertEqual(re.findall(r"^window\.SPEC_DRIFT = (.*);$", page, re.M), ['{"now": {"next_step": "x"}}'])

    def test_no_text_in_the_data_can_keep_its_script_open(self):
        # Day 12's spec quoted "<!--" and "<script>": in a browser the data script then ran to the end
        # of the page, and the live dashboard showed nothing. With no "<" on the line, no tag or comment
        # can start there, whatever the text.
        text = "<!-- PROJECT: x --> <!-- a second `<script>` </script> <SCRIPT src=x>"
        payload = dict(now=dict(next_step=text), specs=[dict(title=text)])
        line = re.search(r"^window\.SPEC_DRIFT = (.*);$", sd.build(json.dumps(payload)), re.M).group(1)
        self.assertNotIn("<", line)
        self.assertEqual(json.loads(line), payload)

    def test_the_graphs_put_data_on_the_page_as_text_never_as_html(self):
        script = read("dashboard.js")
        how, page = script.index("/* ---------- how this works"), script.index("/* ---------- the page")
        self.assertLess(how, page)
        # Only the walk-through builds HTML, from excerpts it passes through esc(). (The failure names the
        # lines, not the script: a break's report goes in a pull request whole.)
        outside = script[:how] + script[page:]
        self.assertEqual([line.strip()[:60] for line in outside.splitlines() if "innerHTML" in line], [])
        self.assertIn("innerHTML", script[how:page])

    def test_every_colour_has_a_dark_value_and_both_dark_scopes_agree(self):
        css = read("dashboard.css")
        light = re.search(r":root \{(.*?)\n\}", css, re.S).group(1)
        by_os = re.search(r':root:not\(\[data-theme="light"\]\) \{(.*?)\n  \}', css, re.S).group(1)
        by_choice = re.search(r':root\[data-theme="dark"\] \{(.*?)\n\}', css, re.S).group(1)
        colours = lambda block: dict(re.findall(r"(--[\w-]+): (#[0-9a-f]{6})", block))
        self.assertGreaterEqual(len(colours(light)), 30)
        self.assertEqual(sorted(colours(by_os)), sorted(colours(light)))
        self.assertEqual(colours(by_os), colours(by_choice))

    def test_the_page_needs_no_script_or_style_from_anywhere_but_its_own_two_files(self):
        html = read("index.html")
        self.assertEqual(re.findall(r'<script src="([^"]+)"', html), ["dashboard.js"])
        self.assertEqual([h for h in re.findall(r'<link rel="stylesheet" href="([^"]+)"', html) if not h.startswith("https://fonts.googleapis.com/")],
                         ["dashboard.css"])


if __name__ == "__main__":
    unittest.main()
