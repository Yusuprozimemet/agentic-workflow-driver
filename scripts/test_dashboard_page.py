"""The dashboard page: what each of its ten graphs draws and says, and what the page file must hold.

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
const banner = els["demo-banner"];
console.log(JSON.stringify({ error, logged, eyebrow: els.eyebrow ? els.eyebrow.textContent : null,
  banner: banner ? { hidden: banner.hidden, text: banner.textContent } : null }));
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
                       hand_offs=[dict(to=3, picked=True), dict(to=3, picked=False), dict(to=4, picked=False)]))["g3"]
        self.assertEqual([(c["label"], c["mark"]) for c in g["cols"]], [("1", "✓"), ("2", "✓"), ("3", "now"), ("No Day", "")])
        self.assertEqual([(r["name"], [c["n"] for c in r["cells"]]) for r in g["rows"]],
                         [("Runs", [2, 0, 0, 1]), ("Stops", [0, 1, 0, 0]), ("No ability named", [1, 0, 0, 0])])
        first = g["rows"][0]["cells"][0]
        self.assertEqual((first["t"], first["b"], first["level"]),
                         ("Runs · Day 1", ["2 merged pull requests grew this ability on Day 1: #1, #2."], 1))
        self.assertEqual(g["rows"][1]["cells"][0]["b"], ["No pull request grew this ability on Day 1."])
        self.assertEqual(g["read"]["t"], "5 merged pull requests, each tagged with the ability it grew")
        self.assertEqual(g["read"]["b"], ["Days 1 to 2 are closed and Day 3 is in progress. 1 of the 2 notes earlier Days left for Day 3 "
                                          "were picked up; 1 more wait for Day 4. The plan stops for the maintainer after Day 3."])
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
                                          "most of its pull requests grew."])

    def test_an_ability_with_no_promise_says_whether_its_work_was_outside_the_days(self):
        story = lambda n, day, ability: dict(number=n, day=day, ability=ability, title="t")
        rows = model(data(criteria_index=[], user_stories=dict(ABILITIES, stories=[story(1, None, "a"), story(2, 1, "b")])))["g5"]["rows"]
        self.assertEqual([r["note"] for r in rows], ["No promise covers this ability. Its pull requests are work outside the Day specs.",
                                                     "No promise covers this ability yet."])

    def test_graph_6_keeps_each_merges_gap_its_time_open_and_its_failed_check(self):
        row = lambda pr, kind, day, gap, **more: dict(dict(pr=pr, kind=kind, day=day, gap_full=gap, title=f"`{kind}`", date="2026-01-01"), **more)
        check = lambda n, hours, failed=0: dict(number=n, hours=hours, failed=failed, failed_in=["PR checks"] * bool(failed))
        g = model(data(rows=[row(None, "origin", 0, 50.0), row(1, "spec", 1, 54.0), row(2, "code", 1, 48.0), row(3, "close", 1, 48.0),
                             row(4, "other", 2, 47.0, gap_chance=52.0, gap_chance_band=[50.0, 54.0])],
                       verification=[check(1, 0.05), check(2, 2.0, 2), check(3, 0.1), check(4, 0.1)]))["g6"]
        self.assertEqual([k[1] for k in g["key"]], ["Spec merge 1", "Code merge 1", "A Day's close 1", "Other (tooling, dashboard) 2",
                                                   "A check failed before the merge 1"])
        self.assertEqual(g["bands"], [dict(day=0, n=1), dict(day=1, n=3), dict(day=2, n=1)])
        self.assertEqual([m["y"] for m in g["merges"]], [0.5, 0.1, 0.7, 0.7, 0.8])  # the scale runs from 55° down to 45°
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
                                          "1 of 4 pull requests had a check fail before they merged."])
        self.assertEqual(g["table"]["rows"][2], ["#2", "code", 1, "2026-01-01", "48.0", 120, "yes"])

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
                                          "The hooks refused 3 calls and cut 3 long outputs. Counted at each Day's close on the maintainer's computer, "
                                          "so 2 Jan is counted only up to the close run on it, and nothing after it is in yet."])
        self.assertEqual(g["say"], "What each date's tokens would cost on the pay-per-token API, at list prices. This repository's sessions only, "
                                   "counted on the maintainer's computer. The maintainer pays a flat subscription, so this measures usage and is not a bill.")

    def test_graph_9_adds_each_days_changed_lines_by_what_the_file_is(self):
        g = model(data(rows=[dict(pr=None, day=0, work=dict(spec=7)), dict(pr=1, day=1, work=dict(spec=10, context=5, prod=20, test=40, tooling=0)),
                             dict(pr=2, day=1, work=dict(prod=10, test=20))]))["g9"]
        first = g["bars"][0]
        self.assertEqual((first["w"], first["total"], first["prs"], first["ratio"]), (dict(spec=15, prod=30, test=60, tooling=0), 105, 2, "2.0"))
        self.assertEqual(first["b"], ["Spec and agent context 15, production code 30, tests 60, tooling 0. 2 pull requests merged. "
                                      "2.0 test lines for each production line."])
        self.assertEqual(g["bars"][2]["t"], "Day 3 (in progress) · 0 lines changed")
        self.assertEqual(g["read"]["t"], "105 lines changed in Days 1 to 3; the largest share is tests")
        self.assertIn("Another 7 lines came before Day 1.", g["read"]["b"][0])

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
        rows = [dict(pr=None, kind="origin", day=0, title="The first commit"), dict(pr=1, kind="spec", day=2, title="`spec`"),
                dict(pr=2, kind="code", day=2, title="`code`"), dict(pr=3, kind="close", day=2, title="`close`")]
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
                                          "Day 4 has no spec, so its size cannot be drawn. 1 hand-off waits for it (H03.1).",
                                          "After Day 4 the plan stops for the maintainer. What comes after is not specified, so the graph "
                                          "ends there and gives no percentage of the whole plan."])
        self.assertEqual([k[1] for k in g["key"]], ["Spec merge 1", "Code merge 1", "A Day's close 1", "Other (tooling, dashboard) 1",
                                                   "Promises built", "Promises written", "Hand-offs open", "Specified, not merged", "Not specified yet"])
        self.assertEqual(g["table"]["head"], ["Merge", "Kind", "Day", "Built", "Written", "Hand-offs open"])
        self.assertEqual(g["table"]["rows"][0], ["start", "the first commit", "", 0, 10, 0])
        self.assertEqual(g["table"]["rows"][-1], ["close", "not merged", 3, 7, 14, ""])

    def test_graph_1_with_nothing_ahead_and_no_stop_ends_at_today(self):
        col = lambda pr, built, got: dict(pr=pr, built=built, got=got, written=2, open=0, open_numbered=0, opened=[], closed=[])
        look = dict(columns=[col(None, 0, []), col(1, 1, ["C1.1"])], pending=None, hand_offs=[])
        g = model(data(rows=[dict(pr=None, kind="origin", day=0, title="The first commit"), dict(pr=1, kind="spec", day=1, title="`spec`")],
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
        self.assertEqual(pr7["b"], ["Open for 30 minutes before it merged.", "Its checks ran 4 times and took 9 minutes, 1 of them failed."])
        pr6 = next(b for b in lanes["Pull request open"]["bars"] if "#6" in b["t"])
        self.assertEqual((pr6["from"], pr6["to"], pr6["cls"]), ("00:00", "02:00", "spec"))
        self.assertIn("opened on an earlier date", pr6["b"][0])
        self.assertEqual([(b["from"], b["to"]) for b in lanes["Auditors"]["bars"]], [("00:00", "00:10")])
        self.assertEqual([lane["sub"] for lane in jan2["lanes"]], ["busy 2 h 0 min", "busy 30 minutes", "busy 10 minutes", "2 pull requests, 2 h 30 min in all", "1 set, 1 with a failure", "2 merges"])
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


@unittest.skipUnless(shutil.which("node"), "needs node to boot the page")
class BootTest(unittest.TestCase):
    def test_the_page_draws_without_an_error_on_data_with_every_graph_in_it(self):
        out = boot(data(**PROMISES, user_stories=dict(ABILITIES, stories=[dict(number=1, day=1, ability="a", title="t")]),
                        rows=[dict(pr=1, kind="code", day=1, gap_full=40.0, title="t", date="2026-01-01", work=dict(prod=3))],
                        tokens=[dict(date="2026-01-01", agent="main", cost=1.0, replies=1, cut=0)],
                        yardsticks=dict(days=[1], problems=[], rows=[dict(key="cost", name="Cost", unit="$", decimals=2, baseline=1.0,
                                                                         values=[dict(day=1, value=2.0, text="t")])])))
        self.assertEqual((out["error"], out["logged"]), (None, []))
        self.assertEqual(out["eyebrow"], "toy · read from git and GitHub on 3 Jan 2026 at 09:30 · commit abcdef1")
        self.assertTrue(out["banner"]["hidden"])

    def test_the_page_draws_without_an_error_on_data_with_nothing_in_it(self):
        out = boot({})
        self.assertEqual((out["error"], out["logged"]), (None, []))

    def test_a_graph_that_cannot_be_drawn_is_logged_and_does_not_stop_the_page(self):
        out = boot(data(criteria_index=[None]))
        self.assertIsNone(out["error"])
        # The walk-through reads the same list of promises, so it says so too; the other six graphs drew.
        self.assertEqual([line.split(":")[0] for line in out["logged"]], ["g4", "g5", "how this works"])


class PageFilesTest(unittest.TestCase):
    """What index.html, dashboard.css and dashboard.js must hold, read as text."""

    def test_every_graph_has_its_plot_its_readout_and_its_exact_numbers_folded_under_it(self):
        html = read("index.html")
        for n in range(1, 10):
            section = re.search(rf'<section class="graph" id="g{n}">.*?</section>', html, re.S)
            self.assertIsNotNone(section, f"graph {n}")
            order = [section.group(0).index(f'id="g{n}-{part}"') for part in ("plot", "read", "table")]
            self.assertEqual(order, sorted(order), f"graph {n}")
            self.assertRegex(section.group(0), rf'<details class="exact"><summary>Exact numbers</summary><div class="scroll-x"><table id="g{n}-table">')
            self.assertIn(f'id="g{n}-read" aria-live="polite"', section.group(0))
        self.assertNotIn("<details open", html)

    def test_no_graph_sits_inside_anything_collapsed(self):
        html = read("index.html")
        for n in range(1, 10):
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

    def test_the_ten_graphs_sit_in_order_under_four_group_headings(self):
        html = read("index.html")
        self.assertEqual(re.findall(r'<section class="graph" id="(g\d+)">', html), [f"g{n}" for n in range(1, 11)])
        heads = ["Where is it going?", "What can it do, and can it be trusted?", "Is the way of working sound?", "What does it take?"]
        self.assertEqual(re.findall(r'<h2 class="chapter">([^<]*)<small>', html), heads)
        starts = [html.index(f'<h2 class="chapter">{h}<small>') for h in heads]
        group = {1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 3, 9: 3, 10: 3}
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
