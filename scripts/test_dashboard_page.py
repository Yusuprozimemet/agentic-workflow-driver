"""The dashboard page: what each of its graphs draws and says, and what the page file must hold.

docs/dashboard/dashboard.js keeps its reading of the data in model(), which touches no document, so
these tests run it in node on small made-up data and compare what comes out. The page itself is
booted on a document that accepts anything, to see that drawing does not throw. Needs node.

    python scripts/test_dashboard_page.py
"""
import datetime
import importlib.util
import json
import os
import re
import shutil
import subprocess
import unittest
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "..", "docs", "dashboard")
SCRIPT = os.path.join(PAGE, "dashboard.js")
spec = importlib.util.spec_from_file_location("spec_drift", os.path.join(HERE, "spec-drift.py"))
sd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sd)
import spec_drift_views as views  # noqa: E402  (spec-drift.py put scripts/ on the path)

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
  banner: shown(els["demo-banner"]), missing: shown(els["data-banner"]), quality: shown(els.quality),
  now: shown(els.now), whr: shown(els.whr), attention: shown(els.attention), attentionAll: shown(els["attention-all"]), sticks: shown(els.sticks),
  chips: { prt: shown(els["prt-chips"]), g12: shown(els["g12-chips"]) } }));
"""

# BOOT, then the first Day's button pressed: its document records each element's listeners and every line written
# under the big score (`qof`, in order), and `pressed` is the error the press threw, if any.
BOOT_PRESS = r"""
const fs = require("fs"), vm = require("vm"), els = {}, logged = [], qof = [];
const stub = () => new Proxy(function () {}, {
  get: (t, k) => k === Symbol.toPrimitive ? () => "" : k === Symbol.iterator ? [][Symbol.iterator] : k in t ? t[k]
    : k === "addEventListener" ? (t[k] = (type, fn) => { (t.on = t.on || {})[type] = fn; }) : (t[k] = stub()),
  apply: () => stub(), construct: () => stub() });
els["q-of"] = stub(); els["q-of"].replaceChildren = (...k) => { qof.push(k.map(String).join("")); };
els.days = stub(); els.days.replaceChildren = (...k) => { els.days.kids = k; };
const document = new Proxy({}, { get: (t, k) => k === "getElementById" ? id => els[id] || (els[id] = stub()) : stub() });
const ctx = vm.createContext({ document, window: {}, location: { hash: "" }, matchMedia: () => ({ matches: false, addEventListener() {} }),
  console: { error: e => logged.push(String(e)) }, DATA: JSON.parse(fs.readFileSync(0, "utf8")) });
let error = null, pressed = null;
try { vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\nboot(DATA);", ctx); } catch (e) { error = e.message; }
try { const chip = (els.days.kids || [])[2]; if (chip && chip.on && chip.on.click) chip.on.click(); } catch (e) { pressed = e.message; }
console.log(JSON.stringify({ error, pressed, qof }));
"""

# flipTheme() on each [saved, systemDark] pair of the list from stdin.
FLIP = r"""
const fs = require("fs"), vm = require("vm");
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")) });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\nDATA.map(c => flipTheme(c[0], c[1]))", ctx)));
"""

# howBlob() on the data from stdin: where the page's links to the repository's files point.
HOW_BLOB = r"""
const fs = require("fs"), vm = require("vm");
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")) });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\nhowBlob(DATA)", ctx)));
"""

# underLine() on each list of a fold's items from stdin; null when the page has no underLine, so the test fails by its assertion.
UNDER_LINE = r"""
const fs = require("fs"), vm = require("vm");
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")) });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\ntypeof underLine !== 'function' ? null : DATA.map(items => underLine(items))", ctx)));
"""

# foldItems() on a fold built from the tree on stdin: each node is its tag, classes, children and the text after them
# (`post`), with only what foldItems asks of an element. A selector is tags, comma-separated, each a descendant chain
# ("table tr"). Null when the page has no foldItems.
FOLD_ITEMS = r"""
const fs = require("fs"), vm = require("vm");
const below = n => n.kids.flatMap(k => [k, ...below(k)]);
const match = (n, chain) => { const tags = chain.trim().split(/\s+/), last = tags.pop();
  return n.tag === last && (!tags.length || below(n.root).some(a => a.tag === tags[tags.length - 1] && below(a).includes(n))); };
const build = (s, root) => { const n = { tag: s.tag, kids: [], root: null, post: s.post || "", text: s.text || "" };
  n.root = root || n; n.kids = (s.kids || []).map(k => build(k, n.root));
  n.tagName = s.tag.toUpperCase(); n.classList = { contains: c => (s.cls || []).includes(c) }; n.children = n.kids;
  n.querySelectorAll = sel => below(n).filter(d => sel.split(",").some(c => match(d, c)));
  n.querySelector = sel => n.querySelectorAll(sel)[0] || null;
  Object.defineProperty(n, "textContent", { get: () => n.text + n.kids.map(k => k.textContent).join("") + n.post });
  return n; };
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")), build });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\ntypeof foldItems !== 'function' ? null : foldItems(build(DATA))", ctx)));
"""

# viewFor() on each [hash, ids of the back page] pair from stdin; null when the page has no viewFor.
VIEW_FOR = r"""
const fs = require("fs"), vm = require("vm");
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")) });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\ntypeof viewFor !== 'function' ? null : DATA.map(c => viewFor(c[0], new Set(c[1])))", ctx)));
"""


# planBar() on the graph 12 model from stdin: the nodes it puts in its box, as the page would hold them (a
# node is its tag, attributes, text and children; a string child is text).
PLAN_BAR = r"""
const fs = require("fs"), vm = require("vm");
const node = tag => { const n = { tag, attrs: {}, kids: [], textContent: "", hidden: false,
  setAttribute(k, v) { this.attrs[k] = String(v); }, appendChild(c) { this.kids.push(c); return c; }, append(...c) { c.forEach(x => this.kids.push(x)); },
  replaceChildren(...c) { if (c.some(Array.isArray)) throw new Error("replaceChildren() given an array: a browser writes it as text"); this.kids = c.flat(); }, addEventListener() {}, getBoundingClientRect: () => ({ left: 0, top: 0, width: 0, height: 0 }) };
  n.style = { set cssText(v) { n.attrs.style = v; } }; Object.defineProperty(n, "className", { set(v) { this.attrs.class = v; }, get() { return this.attrs.class || ""; } });
  return n; };
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")), document: { createElementNS: (ns, tag) => node(tag), createElement: tag => node(tag) },
  window: {}, console, box: node("div"), tip: node("div"), panel: node("div"), forDays: el => el, resets: [] });
vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\nplanBar(model(DATA).g12, box, tip, panel, forDays, resets);", ctx);
const dump = n => typeof n === "string" ? n : { tag: n.tag, attrs: n.attrs, text: n.textContent, kids: n.kids.map(dump) };
console.log(JSON.stringify(dump(ctx.box)));
"""


def node(harness, data):
    return json.loads(subprocess.run(["node", "-e", harness, SCRIPT], input=json.dumps(data), capture_output=True,
                                     encoding="utf-8", check=True).stdout)


def model(data):
    """What the page would draw and say for this data, each criterion given its state as spec-drift.py gives it."""
    if isinstance(data.get("criteria_index"), list):
        views.criterion_states(data["criteria_index"], data.get("days") or [], data.get("replay"))
    # Graph 7's gates, phases and cost per catch, as spec-drift.py writes them (spec_drift_views.proofreading).
    if isinstance(data.get("days"), list) and "proofreading" not in data:
        data = dict(data, proofreading=views.proofreading(data))
    # Graph 8's beads and graph 9's rings, as spec-drift.py writes them (spec_drift_views.budget, rings).
    if "budget" not in data:
        data = dict(data, budget=views.budget(data))
    if isinstance(data.get("days"), list) and "rings" not in data:
        data = dict(data, rings=views.rings(data))
    # Graph 10's figures per date and the actogram, as spec-drift.py writes them (spec_drift_views.actogram).
    if "actogram" not in data:
        data = dict(data, actogram=views.actogram(data))
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


# "Needs attention" as spec_drift_views.needs_attention() gives it: one broken on Day 1, one hand-off on Day 2 that no
# graph draws, eight never proved that share a sentence, nothing to repair and nothing expected.
NEEDS = dict(
    head="abcdef1", last_pr=9, count=2,
    groups=[dict(key="broken", name="broken", sub="a check that fails today", n=1), dict(key="repair", name="to repair", sub="a missing test", n=0),
            dict(key="waiting", name="waiting for you", sub="hand-offs nobody has picked up", n=1)],
    folded=[dict(key="never", name="hold, never proved", n=8), dict(key="expected", name="expected, not counted", n=0)],
    lines=[dict(group="broken", mark="bad", why="replay_failed", text="The replay fails: `x`.", graphs=["prt", "mrg"], ids=[dict(id="C1.1", day=1)]),
           dict(group="waiting", mark="hnd", why="handoff_unpicked", text="Hand-off H2.1.", graphs=[], ids=[dict(id="H2.1", day=2)]),
           dict(group="never", mark="unp", why="unproven", text="Holds.", graphs=["prt"], ids=[dict(id=f"C1.{n}", day=1) for n in range(2, 10)])],
    chips=dict(prt=[dict(mark="bad", name="broken", n=1), dict(mark="unp", name="never proved", n=8)], mrg=[dict(mark="bad", name="broken", n=1)]),
    days=[dict(day=1, n=1, marks=[dict(mark="bad", id="C1.1")] + [dict(mark="unp", id=f"C1.{n}") for n in range(2, 10)]),
          dict(day=2, n=1, marks=[dict(mark="hnd", id="H2.1")]), dict(day=3, n=0, marks=[]), dict(day=None, n=0, marks=[])],
    unread=[dict(text="Replay report: absent", n=3)])


@unittest.skipUnless(shutil.which("node"), "needs node to run the page's model")
class ModelTest(unittest.TestCase):
    def test_the_header_says_when_the_data_was_read_and_what_is_next(self):
        head = model(data())["head"]
        self.assertEqual((head["project"], head["when"], head["commit"], head["demo"]), ("toy", "3 Jan 2026 at 09:30", "abcdef1", False))
        self.assertEqual(head["now"], "Days 1 to 2 are closed and Day 3 is in progress.")
        self.assertEqual(head["next"], "Day 03 Track A: `run`")
        self.assertEqual(head["took"], "")

    def test_the_graphs_that_left_the_page_are_not_in_the_model(self):
        self.assertEqual([k for k in GONE_KEYS if k in model(demo_data())], [])
        self.assertEqual([k for k in GONE_KEYS if k in model({})], [])

    def test_the_header_says_how_many_dates_the_days_took(self):
        # A Day is a step of the plan, not a calendar day: two Days share a date here. The Day in progress is not
        # counted, and neither is a pull request outside any Day that merged later, whatever Day its row carries.
        days = [a_day(1, worked=["2026-01-02", "2026-01-02"]), a_day(2, worked=["2026-01-02", "2026-01-03"]), a_day(3, "active", worked=["2026-01-06", "2026-01-06"])]
        rows = [dict(pr=4, date="2026-01-05", day=2)]
        self.assertEqual(model(data(days=days, rows=rows))["head"]["took"], "Days 1 to 2 took 2 dates")

    def test_what_needs_attention_is_the_counted_rule_put_into_words(self):
        got = model(data(needs_attention=NEEDS))["attention"]
        self.assertEqual((got["count"], got["head"], got["at"]), (2, "2 need a decision or a fix", ", at pull request #9"))
        self.assertEqual([(g["key"], g["mark"], g["n"], g["title"], len(g["lines"])) for g in got["groups"]],
                         [("broken", "bad", 1, "Broken · 1", 1), ("repair", "rep", 0, "To repair · 0", 0),
                          ("waiting", "hnd", 1, "Waiting for you · 1", 1)])
        # what is folded is said under the headline and left out of it; a fold with nothing in it is not drawn
        self.assertEqual(got["below"], [dict(mark="unp", text="8 hold, never proved")])
        self.assertEqual([(f["key"], f["title"]) for f in got["folded"]], [("never", "Hold, never proved · 8")])
        self.assertEqual(got["unread"], ["Replay report: absent (3)"])

    def test_a_line_names_its_ids_its_day_and_the_graphs_that_draw_it(self):
        got = model(data(needs_attention=NEEDS))["attention"]
        broken, waiting, never = got["groups"][0]["lines"][0], got["groups"][2]["lines"][0], got["folded"][0]["lines"][0]
        self.assertEqual(broken, dict(mark="bad", ids="C1.1 · Day 1", more=[], text="The replay fails: `x`.", at=[
            dict(id="prt", title="What can the driver do, and can I rely on it?"), dict(id="mrg", title="Does the code still pass the spec?")]))
        self.assertEqual((waiting["ids"], waiting["at"]), ("H2.1 · Day 2", []))
        # eight ids: the first six, and the rest folded; seven would fold one id alone, so they are all printed
        self.assertEqual((never["ids"], never["more"]), ("C1.2 C1.3 C1.4 C1.5 C1.6 C1.7", ["C1.8", "C1.9"]))
        seven = dict(NEEDS, lines=[dict(NEEDS["lines"][2], ids=NEEDS["lines"][2]["ids"][:7])])
        line = model(data(needs_attention=seven))["attention"]["folded"][0]["lines"][0]
        self.assertEqual((line["ids"], line["more"]), ("C1.2 C1.3 C1.4 C1.5 C1.6 C1.7 C1.8", []))

    def test_the_marks_hang_under_the_day_each_belongs_to(self):
        rows = [dict(phase=0, days=[1, 2], stop=None), dict(phase=1, days=[3], stop=None)]
        got = model(data(needs_attention=NEEDS, meta=dict(project="toy", where=dict(rows=rows, names={}))))["attention"]
        self.assertEqual([(d["label"], d["n"], d["end"], len(d["marks"])) for d in got["days"]],
                         [("1", 1, False, 9), ("2", 1, True, 1), ("3", 0, True, 0), ("no Day", 0, False, 0)])
        self.assertEqual([m["tip"] for m in got["days"][0]["marks"][:2]], ["C1.1: broken", "C1.2: holds, never proved"])
        self.assertEqual(got["daysSay"], "The marks under the Day each belongs to. Of the 2 that need a decision or a fix: "
                         "1 on Day 1 and 1 on Day 2. 8 marks are of what is folded below.")

    def test_a_chip_is_the_figure_the_rule_counted_for_its_graph(self):
        got = model(data(needs_attention=NEEDS))["attention"]["chips"]
        self.assertEqual(got, dict(prt=[dict(mark="bad", n=1, name="broken", text="1 broken"),
                                        dict(mark="unp", n=8, name="never proved", text="8 never proved")],
                                   mrg=[dict(mark="bad", n=1, name="broken", text="1 broken")]))

    def test_the_headline_says_one_and_none_in_words(self):
        head = lambda n: model(data(needs_attention=dict(NEEDS, count=n, last_pr=None)))["attention"]  # noqa: E731
        self.assertEqual((head(1)["head"], head(1)["at"]), ("1 needs a decision or a fix", ""))
        self.assertEqual(head(0)["head"], "Nothing needs a decision or a fix")

    def test_data_without_the_rule_draws_no_panel(self):
        # the old list alone (a page built before the rule) is not grouped by the page any more
        self.assertIsNone(model(data())["attention"])
        self.assertIsNone(model(data(attention=[dict(id="C1.1", reason="replay_failed", detail="x")]))["attention"])

    def test_the_promises_are_counted_in_the_state_each_criterion_has(self):
        # C1.1 broken, C1.2 proven, C1.3 replaced, C1.4 open, C1.5 unchecked, C2.1 unproven, C2.2 repair, C2.3 skipped,
        # C3.1 building: one in each state. The merge graph's reconcile line reads this count.
        p = model(data(**PROMISES))["promises"]
        self.assertEqual(sorted(p["states"].values()), [1] * 9)
        self.assertEqual(p["states"], dict.fromkeys(("proven", "unproven", "repair", "broken", "skipped", "replaced", "building", "open", "unchecked"), 1))
        self.assertEqual((p["counts"], p["total"]), ([["proven", 1], ["unproven", 1], ["repair", 1], ["broken", 1], ["skipped", 1]], 5))

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
                                          "1 of 5 pull requests had a check of any workflow fail before they merged."])
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
        self.assertEqual([[len(c) for c in r["cells"]] for r in g["rows"]], [[1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0], [0, 0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0], [0] * 14])
        self.assertEqual([r["note"] for r in g["rows"]], ["3 of 12 · 25%", "not read yet", "read at its close"])
        dots = {o["id"]: o for r in g["rows"] for o in r["dots"]}
        self.assertEqual([(o["id"], o["cause"], o["escaped"], o["back"]) for o in dots.values()], [
            ("D1.1", "spec", False, False), ("D1.2", "implementation", False, False), ("D2.1", "process", True, True),
            ("D2.2", "other", False, False)])
        self.assertEqual((dots["D2.1"]["t"], dots["D2.1"]["b"]), (
            "D2.1 · process · caught by: the close",
            ["Made on Day 1 and caught on Day 2: it escaped for 1 Day. The same problem as D1.1, back again."]))
        self.assertEqual(dots["D1.2"]["b"], ["Made outside any Day: in the plan, a tool or a machine. Noticed by: Track A."])
        self.assertEqual(dots["D2.2"]["b"], ["Caught on Day 2; its line does not say which Day made it."])
        self.assertEqual([x["sub"] for x in g["gates"]], ["1 caught · 2 runs · $1.00", "0 caught", "0 caught", "1 caught", "0 caught", "0 caught",
                                                         "0 caught", "0 caught", "1 caught · tracks, the session", "1 caught", "0 caught",
                                                         "0 caught", "0 caught", "0 caught"])
        self.assertEqual(g["read"]["t"], "4 defects; the auditors caught 1 of them before any code was written")
        self.assertEqual(g["read"]["b"], ["1 was in a spec. 1 escaped from an earlier Day and 1 came back. A second reader gave 3 of 12 "
                                          "tags differently. Each catch cost about $1.00 at the auditors."])

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

    def test_graph_2_draws_each_yardstick_as_a_bullet_on_its_own_scale_over_the_columns_days(self):
        value = lambda day, v: dict(day=day, value=v, text="")
        yard = dict(days=[1, 2], problems=[], rows=[
            dict(key="cost", name="Cost", unit="$", decimals=2, baseline=1.5, average=[2.0, 1.5, None],
                 values=[value(1, 2.0), value(2, 1.0), value(14, 9.0)]),
            dict(key="refusals", name="Refused", unit="", decimals=0, baseline=None, average=[4.0, 5.0],
                 values=[value(1, 4), value(2, 6)])])
        # Which way is better is read from the gel's panels (spec_drift_views.LOWER_BETTER), as spec-drift.py writes them.
        g = model(data(yardsticks=yard, gel=views.gel(dict(yardsticks=yard))))["g2"]
        cost, ref = (r["bullet"] for r in g["rows"])
        # Scale: the largest of the Days, the kit and the average, and a little more; Day 14 has no column, so it is left out.
        top = 2.0 * 1.08
        self.assertEqual([round(cost[k], 3) for k in ("lo", "hi", "last", "avg", "base")],
                         [round(v / top, 3) for v in (1.0, 2.0, 1.0, 1.5, 1.5)])
        self.assertEqual((cost["now"], cost["day"], cost["avgText"], cost["cmp"]), ("$1.00", 2, "$1.50", "better"))
        self.assertEqual([p["day"] for p in cost["spark"]], [1, 2])
        self.assertEqual(cost["b"], ["Every Day between $1.00 and $2.00, average so far $1.50; the kit with a person driving every step: $1.50. "
                                     "The last Day was better than the average."])
        # Refusals have no better direction: no colour, though the last Day is over the average.
        self.assertEqual((ref["cmp"], ref["base"], ref["now"]), ("", None, "6"))

    def test_graph_7_pipeline_puts_the_same_dots_at_their_gates_and_counts_the_stops(self):
        defect = lambda i, found, cause: dict(id=i, found=found, cause=cause, made="Day 01", same_as=None, problem=None)
        days = [a_day(1, defects=[defect("D1.1", "auditor", "spec"), defect("D1.2", "Track A", "implementation"),
                                  defect("D1.3", "review", "process"), defect("D1.4", "close", "process")]), a_day(2, "active")]
        g = model(data(days=days, refusals=[dict(date="2026-01-01", guard="read-guard", refused=3), dict(date="2026-01-02", guard="read-guard", refused=2),
                                            dict(date="2026-01-02", guard="step-guard", refused=1)],
                       verification=[dict(number=1, failed_in=["PR checks", "Tests"]), dict(number=2, failed_in=["PR checks"]), dict(number=3, failed_in=[])],
                       rows=[dict(pr=None), dict(pr=1, day=1), dict(pr=2, day=1)]))["g7"]
        P = g["pipe"]
        self.assertEqual([s["name"] for s in P["stages"]], ["Before any code", "Writing a track, on this machine", "The close",
                                                          "CI on every pull request", "You", "After the merge"])
        gates = {n: x for s in [*P["stages"], P["hooks"]] for x in s["gates"] for n in x["names"]}
        self.assertEqual([o["id"] for o in gates["spec-auditor"]["dots"]], ["D1.1"])
        self.assertEqual([o["id"] for o in gates["Noticed in the work"]["dots"]], ["D1.2"])
        self.assertEqual([o["id"] for o in gates["Diff review"]["dots"]], ["D1.3"])
        self.assertEqual(gates["Noticed in the work"]["by"], "by: tracks 1 · self 0 · other 0")
        # Both views hold the same dots: the pipeline cannot disagree with the rows by Day.
        self.assertEqual(sorted(o["id"] for s in P["stages"] for x in s["gates"] if x["dots"] for o in x["dots"]), sorted(o["id"] for r in g["rows"] for o in r["dots"]))
        self.assertEqual([gates[n]["stop"] for n in ("read-guard", "step-guard", "auditor-guard", "Tests", "Track breaks", "Your merge")],
                         ["5 refused", "1 refused", "0 refused", "failed on 1 pull request", "failed on 0 pull requests", "2 pull requests merged"])
        notes = {s["name"]: s["note"] for s in P["stages"]}
        self.assertEqual((P["hooks"]["note"], notes["CI on every pull request"]), ("6 refusals", "the PR checks workflow failed on 2 pull requests; graph 6 counts any workflow"))
        self.assertEqual((gates["ruff"]["plain"], gates["Style check"]["plain"], gates["Compose and Prometheus"]["kind"]),
                         ("not counted yet", "in the PR checks' count", "kit"))
        self.assertEqual([(p["name"], p["n"], p["pct"]) for p in P["phases"]],
                         [("Before any code", 1, 25), ("While writing", 2, 50), ("At the close", 1, 25), ("After the merge", 0, 0)])
        self.assertEqual(P["gates"], 43)

    def test_graph_7_sends_every_pull_request_through_ci_and_the_merge_with_the_hooks_beside_the_pipe(self):
        defect = lambda i, found: dict(id=i, found=found, cause="process", made="Day 12", same_as=None, problem=None)
        g = model(data(days=[a_day(12, defects=[defect("D12.1", "review"), defect("D12.2", "self"), defect("D12.3", "rehearsal")])],
                       refusals=[dict(date="2026-01-01", guard="read-guard", refused=3)]))["g7"]
        P = g["pipe"]
        # The track loop wraps the writing alone; the spec change, each track and the close then pass CI and the merge,
        # the closing PR's rehearsal among CI's checks, and the replay after the merge.
        self.assertEqual([(s["name"], s.get("loop", False)) for s in P["stages"]],
                         [("Before any code", False), ("Writing a track, on this machine", True), ("The close", False),
                          ("CI on every pull request", False), ("You", False), ("After the merge", False)])
        where = {n: s["name"] for s in P["stages"] for x in s["gates"] for n in x["names"]}
        self.assertEqual([where.get(n) for n in ("close-evidence --rehearse", "Diff review", "Your merge")],
                         ["CI on every pull request", "Writing a track, on this machine", "You"])
        # The hooks run in every stage: a band beside the pipe, not a stage of it, with the same refusal counts.
        self.assertEqual([x["names"][0] for x in P["hooks"]["gates"]], ["step-guard", "read-guard", "auditor-guard", "cap-output"])
        self.assertEqual((P["hooks"]["note"], P["hooks"]["gates"][1]["stop"]), ("3 refusals", "3 refused"))
        # The main session's diff review is a gate of its own; the work no longer counts reviews.
        gates = {n: x for s in P["stages"] for x in s["gates"] for n in x["names"]}
        self.assertEqual([[o["id"] for o in gates[n]["dots"]] for n in ("Diff review", "Noticed in the work")], [["D12.1"], ["D12.2"]])
        self.assertEqual(gates["Noticed in the work"]["by"], "by: tracks 0 · self 1 · other 0")
        self.assertEqual([len(c) for c in g["rows"][0]["cells"]], [0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 0])
        # A phase's end sits after the Day's pipe: nothing counts its auditors apart yet.
        self.assertEqual((P["phase_end"]["name"], [x["names"] for x in P["phase_end"]["gates"]], P["phase_end"]["gates"][0]["plain"]),
                         ("End of a phase", [["plan-auditor"], ["security-ops-auditor", "agentic-engineering-auditor", "architecture-auditor"]],
                          "not counted yet"))
        self.assertNotIn("seven", g["say"])

    def test_the_pages_source_links_go_to_the_repository_the_data_names(self):
        blob = lambda meta: node(HOW_BLOB, dict(meta=meta))
        self.assertEqual(blob(dict(repo_url="https://github.com/someone/fork")), "https://github.com/someone/fork/blob/main/")
        self.assertEqual(blob(dict(project="toy")), None)

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

    def test_graph_1_names_a_promise_a_closed_day_wrote_and_never_built(self):
        col = lambda pr, built, got: dict(pr=pr, built=built, got=got, written=2, open=0, open_numbered=0, opened=[], closed=[])
        look = dict(columns=[col(None, 0, []), col(1, 1, ["C1.1"])], pending=None, hand_offs=[])
        g = model(data(rows=[dict(pr=None, kind="origin", day=0, title="The first commit"), dict(pr=1, kind="spec", day=1, own_day=1, title="`spec`")],
                       days=[dict(day=1, status="closed", title="One")], criteria_index=[dict(id="C1.1", day=1), dict(id="C1.2", day=1)],
                       look_ahead=look, now=dict(current_day=3, stop_after=None)))["g1"]
        self.assertEqual(g["read"]["t"].split(" · ")[-1], "1 never built")
        self.assertIn("(C1.2)", " ".join(g["read"]["b"]))

    def test_graph_1_without_look_ahead_data_says_nothing_is_merged(self):
        g = model(data())["g1"]
        self.assertNotIn("error", g)
        self.assertEqual((g["merges"], g["read"]["t"]), ([], "Nothing is merged yet"))

    def test_graph_1_ladder_puts_the_project_at_level_1_and_draws_the_level_2_count(self):
        steps = [run_step(n, 1, "merged") for n in "ABCD"]
        g = model(data(driver_runs=dict(source="run log", counted=None, steps=steps, parks=[], level_2=dict(run=3, of=15))))["g1"]
        ladder = g.get("ladder", [])
        self.assertEqual(len(ladder), 4)
        self.assertEqual([r.get("cls") for r in ladder], ["", "now", "", "wait"])
        self.assertEqual(ladder[1].get("state"), "Where the trial's project is: 4 steps run")
        self.assertEqual((ladder[2].get("state"), ladder[2].get("run"), ladder[2].get("of")), ("3 of 15 in a row", 3, 15))
        self.assertEqual(ladder[3].get("state"), "Waits on level 2")
        # Each level card says who starts and who merges at it.
        self.assertEqual([r.get("lv") for r in ladder], ["Level 0", "Level 1", "Level 2", "Level 3"])
        self.assertEqual([r.get("who") for r in ladder[:3]], [[["maintainer", "starts"], ["maintainer", "merges"]],
                                                              [["driver", "starts"], ["maintainer", "merges"]],
                                                              [["driver", "starts"], ["driver", "merges"]]])

    def test_graph_1_ladder_without_a_driver_count_stays_at_level_0(self):
        g = model(data())["g1"]
        ladder = g.get("ladder", [])
        self.assertEqual(len(ladder), 4)
        self.assertEqual([r.get("cls") for r in ladder], ["now", "", "wait", "wait"])
        self.assertEqual(ladder[2].get("state"), "Not counted yet")
        self.assertNotIn("run", ladder[2])

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

    def test_graph_2_cost_row_says_its_count_changed_at_day_7(self):
        value = lambda day, v, text: dict(day=day, value=v, text=text)
        got = model(data(yardsticks=dict(days=[1, 2], problems=[], rows=[
            dict(key="cost", name="Cost of each merged pull request", unit="$", decimals=2, baseline=1.5,
                 values=[value(1, 1.2, "$6 over 5"), value(2, 1.8, "$9 over 5")]),
            dict(key="parks", name="Times it stopped", unit="", decimals=0, baseline=None,
                 values=[value(1, 1, "one park"), value(2, 2, "two parks")])])))["g2"]
        self.assertEqual(len(got.get("rows", [])), 2)
        self.assertEqual(got["rows"][0].get("foot"), "Days 1 to 6 count every pull request merged since the last count, outside work included; "
                                                     "from Day 7 on, each Day counts its own only. The two halves of the row do not compare; "
                                                     "graph 8, with a column for each Day, has the split.")
        self.assertIsNone(got["rows"][1].get("foot"))

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
        # The 23:50 to 00:10 stretch is the 1st's: a date runs from 05:00 to 05:00, so only the 2nd's work is on the 2nd.
        self.assertEqual((jan2["label"], jan2["days"]), ("2 Jan", [2]))
        lanes = {lane["name"]: lane for lane in jan2["lanes"]}
        self.assertEqual(list(lanes), ["Main session", "Implementer", "Auditors", "Pull request open", "Checks running", "Maintainer merges"])
        pr7 = next(b for b in lanes["Pull request open"]["bars"] if "#7" in b["t"])
        self.assertEqual((round(pr7["x"], 3), round(pr7["w"], 3), pr7["cls"], pr7["days"]), (round(330 / 14.4, 3), round(30 / 14.4, 3), "code", [2]))
        self.assertEqual(pr7["t"], "Pull request #7 · day-02/track-a · open 10:30 to 11:00")
        self.assertEqual(pr7["b"], ["Open for 30 minutes before it merged.", "Its checks were running for 9 minutes: 4 workflow runs, 1 of them failed."])
        # PR 6 opened at 23:00 on the 1st and merged at 02:00 on the 2nd: all of it is the 1st's work, so it is drawn there only.
        pr6 = next((b for b in lane(g["dates"][0], "Pull request open").get("bars", []) if "#6" in b["t"]), {})
        self.assertEqual((pr6.get("from"), pr6.get("to"), pr6.get("cls")), ("23:00", "02:00", "spec"))
        self.assertEqual(pr6.get("b", [""])[0], "Open for 3 h 0 min before it merged.")
        self.assertEqual([(b["from"], b["to"]) for b in lane(g["dates"][0], "Auditors").get("bars", [])], [("23:50", "00:10")])
        self.assertEqual([lane["sub"] for lane in jan2["lanes"]], ["busy 2 h 0 min", "busy 30 minutes", "nothing recorded", "1 pull request, 30 minutes in all",
                                                             "on 1 pull request, running for 9 minutes, 1 with a failure", "1 merge"])
        self.assertEqual([b["cls"] for b in lanes["Checks running"]["bars"]], ["failed"])
        self.assertEqual(jan2["read"]["t"], "2 Jan: 1 pull request merged, half of them open for 30 minutes or less")
        self.assertEqual(jan2["read"]["b"], ["Work of Day 2.", "The main session was busy for 2 h 0 min and the implementer for 30 minutes.",
                                             "The longest wait for a merge: #7 (30 minutes).",
                                             "Times are on the clock of the machine that recorded the sessions (UTC+01:00)."])
        self.assertEqual(jan2["table"]["head"], ["Lane", "What", "From", "To", "Minutes"])
        self.assertIn(["Pull request open", "Pull request #7", "10:30", "11:00", 30], jan2["table"]["rows"])
        self.assertEqual((g["read"], g["table"]), (jan2["read"], jan2["table"]))
        self.assertEqual([x["t"] for x in g["hours"]][:3], ["06:00", "09:00", "12:00"])
        self.assertNotIn("Where a date's time goes, and who waits for whom", [n for n, _ in got["notMeasured"]])

    def test_graph_10_runs_a_date_from_05_00_to_05_00_so_work_after_midnight_stays_on_its_date(self):
        # Local time is +01:00. 23:30 to 01:30 and a merge at 02:00 belong to the first date; 06:00 the next morning to the second.
        s = lambda start, end: {"date": start[:10], "day": 1, "agent": "main", "from": start, "to": end, "replies": 3}
        clock = dict(sessions=[s("2026-01-01T23:30:00+01:00", "2026-01-02T01:30:00+01:00"), s("2026-01-02T06:00:00+01:00", "2026-01-02T06:30:00+01:00")],
                     prs=[dict(number=4, day=1, kind="code", branch="day-01/x", opened="2026-01-01T20:00:00Z", merged="2026-01-02T01:00:00Z", checks=None)])
        g = model(data(clock=clock))["g10"]
        first, second = (g.get("dates", []) + [{}, {}])[:2]
        self.assertEqual(([first.get("date"), second.get("date")], [a["t"] for a in g.get("hours", [])][:2]), (["2026-01-01", "2026-01-02"], ["06:00", "09:00"]))
        main = lambda d: [(b["from"], b["to"]) for x in d.get("lanes", []) if x["name"] == "Main session" for b in x["bars"]]
        self.assertEqual((main(first), main(second)), ([("23:30", "01:30")], [("06:00", "06:30")]))
        merged = [b["t"] for x in first.get("lanes", []) if x["name"] == "Maintainer merges" for b in x["bars"]]
        self.assertEqual(merged, ["Merged pull request #4 · at 02:00"])
        # Each tick sits at its minutes after 05:00 on the axis, which runs from 05:00 to 05:00.
        self.assertEqual([(x["t"], round(x["x"], 2)) for x in g.get("hours", [])],
                         [(t, round(m / 14.4, 2)) for t, m in [("06:00", 60), ("09:00", 240), ("12:00", 420), ("15:00", 600),
                                                              ("18:00", 780), ("21:00", 960), ("00:00", 1140), ("03:00", 1320)]])

    def test_graph_10_draws_a_pull_request_still_open_or_closed_without_merging_and_says_which(self):
        prs = [dict(number=8, day=2, kind="code", branch="day-02/a", opened="2026-01-02T08:00:00Z", merged=None, checks=None),
               dict(number=9, day=2, kind="code", branch="day-02/b", opened="2026-01-02T09:00:00Z", closed="2026-01-02T12:00:00Z", merged=None, checks=None)]
        date = (model(data(clock=dict(sessions=[], prs=prs)))["g10"].get("dates") or [{}])[0]
        pulls = lane(date, "Pull request open")
        self.assertEqual(sorted((b["t"], b["from"], b["to"]) for b in pulls.get("bars", [])),
                         [("Pull request #8 · day-02/a · still open from 08:00", "08:00", "05:00"),
                          ("Pull request #9 · day-02/b · closed without merging 09:00 to 12:00", "09:00", "12:00")])
        self.assertEqual(pulls.get("sub"), "2 pull requests, 24 h 0 min in all, 1 still open, 1 closed without merging")

    def test_graph_10_puts_overlapping_pull_requests_of_one_lane_on_separate_rows(self):
        pr = lambda n, opened, merged: dict(number=n, day=2, kind="code", branch=f"day-02/{n}", opened=opened, merged=merged, checks=None)
        prs = [pr(20, "2026-01-02T08:00:00Z", "2026-01-02T11:00:00Z"), pr(21, "2026-01-02T08:30:00Z", "2026-01-02T09:30:00Z"),
               pr(22, "2026-01-02T12:00:00Z", "2026-01-02T12:30:00Z")]
        date = (model(data(clock=dict(sessions=[], prs=prs)))["g10"].get("dates") or [{}])[0]
        self.assertEqual({b["t"].split(" · ")[0]: b.get("row") for b in lane(date, "Pull request open").get("bars", [])},
                         {"Pull request #20": 0, "Pull request #21": 1, "Pull request #22": 0})

    def test_graph_10_says_which_pull_requests_had_no_check_run_on_the_date(self):
        prs = [dict(number=30, day=2, kind="code", branch="day-02/a", opened="2026-01-02T09:00:00Z", merged="2026-01-02T11:00:00Z",
                    checks=dict(start="2026-01-02T09:31:00Z", end="2026-01-02T09:40:00Z", runs=1, failed=0)),
               dict(number=31, day=2, kind="code", branch="day-02/b", opened="2026-01-02T09:10:00Z", merged="2026-01-02T11:00:00Z", checks=None)]
        date = (model(data(clock=dict(sessions=[], prs=prs)))["g10"].get("dates") or [{}])[0]
        self.assertEqual(lane(date, "Checks running").get("sub"), "on 1 pull request, running for 9 minutes, 0 with a failure; none on #31")

    def test_graph_10_draws_no_driver_or_parked_row_on_a_date_with_nothing_in_them_and_says_so(self):
        clock = dict(sessions=[dict(date="2026-01-02", day=2, agent="main", **{"from": "2026-01-02T10:00:00Z", "to": "2026-01-02T10:30:00Z"}, replies=2)], prs=[])
        g = model(data(clock=clock, driver_runs=dict(steps=[], parks=[an_issue(3, "2026-01-01T10:00:00Z", "2026-01-01T12:00:00Z")])))["g10"]
        busy, quiet = (g.get("dates", []) + [{}, {}])[:2]  # the 1st of January has the park, the 2nd only a session
        self.assertEqual([x.get("name") for x in quiet.get("lanes", [])], ["Main session", "Implementer", "Auditors", "Pull request open", "Checks running", "Maintainer merges"])
        self.assertIn("The driver started no step and nothing was parked on this date.", quiet.get("read", {}).get("b", []))
        self.assertEqual([x.get("name") for x in busy.get("lanes", [])][:2], ["Driver", "Parked for the maintainer"])
        self.assertNotIn("The driver started no step and nothing was parked on this date.", busy.get("read", {}).get("b", []))

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
        # A stretch from 04:00 to 06:00 crosses 05:00, where a date ends. Its half hour of waiting on tests, from 04:10 to 04:40,
        # is the first date's, and the hour after 05:00 is the second's, which gets only half of the two minutes of shorter waits.
        # Two main sessions busy from 08:00 to 10:00 and from 09:00 to 11:00 are three hours of the clock, not four: four with the hour after 05:00, not five.
        s = lambda start, end, **more: {"date": start[:10], "day": 2, "agent": "main", "from": start, "to": end, "replies": 5, **more}
        clock = dict(prs=[], sessions=[
            s("2026-01-02T04:00:00+01:00", "2026-01-02T06:00:00+01:00", ran=dict(tests=1800, other=120),
              runs=[["2026-01-02T04:10:00+01:00", "2026-01-02T04:40:00+01:00", "tests"]]),
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

    def test_graph_10_does_not_call_cancelled_or_unfinished_runs_passed(self):
        at = lambda hm: f"2026-01-02T{hm}Z"
        checks = dict(start=at("09:01:00"), end=at("09:50:00"), runs=19, failed=0, pushes=3, cancelled=5, unfinished=7,
                      spans=[[at("09:01:00"), at("09:50:00"), 0]])
        clock = dict(sessions=[], prs=[dict(number=7, day=None, kind="other", branch="plan/x", opened=at("09:00:00"), merged=at("09:50:00"), checks=checks)])
        lanes = {lane["name"]: lane for lane in model(data(clock=clock))["g10"]["dates"][0]["lanes"]}
        self.assertEqual(lanes["Checks running"]["bars"][0]["b"],
                         ["On this pull request in all: 19 workflow runs over 3 pushes: 7 passed, 5 cancelled and 7 never finished."])

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
        # Graph 7's reading of a found: value moved from the page (tagOf) to spec_drift_views.proofreading.
        self.assertEqual([views._tag(v) for v in values], [sd.found_tag(v) for v in values])
        # Day 2 had a pull request merge after the count, so the auditors' dollar is not shared with its catch.
        defect = lambda i, found, cause, made: dict(id=i, found=found, cause=cause, made=made, same_as=None, problem=None)
        pr = lambda n, day, merged: dict(number=n, day=day, kind="code", branch=f"day-0{day}/track-a", opened="2026-01-01T09:00:00Z", merged=merged, checks=None)
        g = model(data(days=[a_day(1, defects=[defect("D1.1", "The auditor (spec-auditor)", "Spec", "Day 01")]),
                             a_day(2, "active", defects=[defect("D2.1", "auditor", "spec", "Day 02")])],
                       gate_report=dict(gates=[dict(gate="auditors", found="auditor", defects=2, runs=2, cost=1.0)]),
                       clock=dict(sessions=[], prs=[pr(1, 1, "2026-01-01T10:00:00Z"), pr(2, 2, "2026-01-03T10:00:00Z")]),
                       counted=dict(at="2026-01-02T12:00:00+01:00")))["g7"]
        self.assertEqual([[len(c) for c in r["cells"]] for r in g["rows"]], [[1] + [0] * 13, [1] + [0] * 13])
        self.assertEqual(g["rows"][0]["dots"][0]["cause"], "spec")
        self.assertEqual(g["read"]["b"], ["2 were in a spec. 0 escaped from an earlier Day and 0 came back. Each catch cost about $1.00 at the auditors, "
                                          "over the catches of the Days in the count: Day 2 had a pull request merge after it. "
                                          "The gates' runs and dollars are counted up to 12:00 on 2 Jan."])

    def test_graph_7_puts_a_rehearsal_at_the_close_not_after_the_merge(self):
        defect = dict(id="D12.1", found="rehearsal", cause="process", made="Day 12", same_as=None, problem=None)
        g = model(data(days=[a_day(12, defects=[defect])]))["g7"]
        self.assertEqual([len(c) for c in g["rows"][0]["cells"]], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0])
        gates = {n: x for s in g["pipe"]["stages"] for x in s["gates"] for n in x["names"]}
        self.assertEqual([o["id"] for o in gates["close-evidence --rehearse"]["dots"]], ["D12.1"])
        self.assertEqual(gates["Evidence replay"]["dots"], [])
        self.assertEqual([(p["name"], p["n"]) for p in g["pipe"]["phases"]],
                         [("Before any code", 0), ("While writing", 0), ("At the close", 1), ("After the merge", 0)])

    def test_graph_7_gives_a_spec_change_pr_the_dashboard_and_a_day_review_their_own_trays(self):
        defect = lambda i, found: dict(id=i, found=found, cause="process", made="Day 02", same_as=None, problem=None)
        g = model(data(days=[a_day(2, defects=[defect("D2.1", "spec-change PR"), defect("D2.2", "dashboard"), defect("D2.3", "Day 02 review"),
                                               defect("D2.4", "review"), defect("D2.5", "evidence replay")])]))["g7"]
        gates = {n: x for s in g["pipe"]["stages"] for x in s["gates"] for n in x["names"]}
        self.assertEqual([[o["id"] for o in gates[n]["dots"]] for n in ("Spec-change PR", "Diff review", "Evidence replay", "Dashboard", "Day NN review")],
                         [["D2.1"], ["D2.4"], ["D2.5"], ["D2.2"], ["D2.3"]])
        self.assertEqual((gates["Noticed in the work"]["dots"], gates["Noticed in the work"]["by"]), ([], ""))
        self.assertEqual([(p["name"], p["n"]) for p in g["pipe"]["phases"]],
                         [("Before any code", 1), ("While writing", 1), ("At the close", 0), ("After the merge", 3)])

    def test_graph_10_without_any_time_recorded_says_so_under_not_measured(self):
        got = model(data())
        self.assertIn("sessions.json", got["g10"]["empty"])
        self.assertEqual(got["g10"]["dates"], [])
        self.assertEqual(got["notMeasured"][-1][0], "Where a date's time goes, and who waits for whom")
        self.assertEqual(got["notMeasured"][-1][1], got["g10"]["empty"])

    def test_one_graph_that_cannot_read_its_data_leaves_the_others_drawn(self):
        got = model(data(criteria_index=[None]))
        self.assertEqual(got["promises"], {"counts": []})  # the promises could not be read, and count nothing
        self.assertEqual([g for g in ("g1", "g6", "g7", "g2", "g10", "quality") if "error" in (got[g] or {})], [])

    def test_data_with_nothing_in_it_still_gives_every_graph_something_to_say(self):
        got = model({})
        self.assertEqual({g: got[g].get("error") for g in ("g6", "g7", "g2", "g10")}, dict.fromkeys(("g6", "g7", "g2", "g10")))
        self.assertEqual([got[g]["read"]["t"] for g in ("g6", "g7", "g2")], [
            "No gap is measured yet", "No defect is recorded yet", "No yardstick is counted yet"])

    def test_a_run_log_not_counted_is_said_under_not_measured(self):
        why = dict(model(data()).get("notMeasured", [])).get("Whether it runs without a person", "")
        self.assertIn("`driver-runs.json` on the dashboard-data branch", why)

    def test_a_driver_that_started_no_step_is_counted_and_not_under_not_measured(self):
        got = model(data(driver_runs=dict(source="run log", counted=None, steps=[], parks=[])))
        self.assertNotIn("Whether it runs without a person", [n for n, _ in got.get("notMeasured", [])])

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

    # The quality score, as scripts/pipeline/counts/spec_drift_score.py writes it: the page rounds it and links each part.
    PART = lambda key, pct, counts: dict(key=key, name=key.title(), graph="g4", pct=pct, counts=counts)  # noqa: E731
    SCORE = dict(all=dict(score=89.8, low="proof", parts=[
        PART("plan", 92.5, [dict(name="Named", n=9, m=10, pct=90.0, note="")]),
        PART("proof", 74.0, [dict(name="Seen", n=74, m=100, pct=74.0, note=""), dict(name="Cost", n=None, m=None, pct=74.0, note="2 against 1")])]),
        days={"1": dict(score=91.6, low="plan", parts=[PART("plan", 91.6, [])])},
        abilities={"a": dict(score=81.4, low="proof", parts=[PART("plan", 90.0, []), PART("proof", 72.3, [])]), "b": None})

    def test_the_quality_score_is_rounded_and_counted_for_the_whole_each_day_and_each_ability(self):
        q = model(data(score=self.SCORE)).get("quality") or {}
        whole = q.get("all") or {}
        self.assertEqual((whole.get("label"), whole.get("n")), ("the finished Days", 90))
        self.assertEqual([(p["key"], p["n"], p["low"], p["graph"]) for p in whole.get("parts", [])],
                         [("plan", 93, False, "g4"), ("proof", 74, True, "g4")])
        self.assertEqual(whole.get("rows"), [["Plan", "Named", "9 of 10", 90], ["Proof", "Seen", "74 of 100", 74], ["Proof", "Cost", "2 against 1", 74]])
        self.assertEqual(((q.get("days") or {}).get("1") or {}).get("label"), "Day 1")
        self.assertEqual(q.get("abilities"), {"a": dict(n=81, parts="plan 90 · proof 72")})
        self.assertIsNone(model(data()).get("quality"))

    # Graph 12: Days 1 and 2 closed, Day 3 in progress; the plan rewritten after Day 1.
    PLAN = dict(reference="x", quotes=5, unlined=["C3.2"], rewrites=[dict(pr=4, after_day=1)], commitments=[
        dict(id="P01", short="One", section="A", owner_day=1, rule=False, change=None, text="One thing."),
        dict(id="P02", short="Two", section="A", owner_day=2, rule=False, change="changed", text="Two things."),
        dict(id="P03", short="People", section="B", owner_day=None, rule=True, change=None, text="A rule."),
        dict(id="P04", short="Later", section="B", owner_day=3, rule=False, change=None, text="Not yet."),
        dict(id="N01", short="Added", section="B", owner_day=2, rule=False, change=None, text="Added.")],
        links={"C1.1": ["P01"], "C1.2": ["P01", "N01"], "C2.1": ["N01"], "C2.2": [], "C2.3": [], "C3.1": ["P01"]})
    CRIT = [promise("C1.1"), promise("C1.2"), promise("C2.1"), promise("C2.2"), promise("C2.3", tag="hold"), promise("C3.1"), promise("C3.2")]

    def test_graph_12_puts_each_commitment_and_each_day_where_its_plan_lines_say(self):
        g = model(data(plan=self.PLAN, criteria_index=self.CRIT)).get("g12", {})
        stripes = {c["key"]: (c["arm"], c["n"], c["shade"], c["due"], c["rule"]) for c in g.get("all", []) if c["arm"] != "o"}
        self.assertEqual(stripes, {"P01": ("p", 3, 2, False, False), "P02": ("p", 0, 0, True, False), "P03": ("p", 0, 0, False, True),
                                   "P04": ("p", 0, 0, False, False), "N01": ("n", 2, 2, False, False)})
        # A criterion naming nothing has its own column: new work (amber) or a safety check (grey), by its tag.
        self.assertEqual([(c["key"], c["kind"]) for c in g.get("all", []) if c["arm"] == "o"], [("C2.2", "unplanned"), ("C2.3", "guard")])
        self.assertEqual([(r["day"], r["n"], r["counts"], r["rewrite"]) for r in g.get("rows", [])],
                         [(1, 2, dict(first=2, added=0, unplanned=0, guard=0), True),
                          (2, 3, dict(first=0, added=1, unplanned=1, guard=1), False),
                          (3, 1, dict(first=1, added=0, unplanned=0, guard=0), False)])
        self.assertEqual({f["key"]: f["n"] for f in g.get("filters", [])}, dict(due=1, none=2, single=0, changed=1))
        self.assertEqual([s["label"] for s in g.get("sections", [])], ["A", "B"])
        self.assertEqual(g.get("read", {}).get("t"), "1 of 4 commitments of the approved plan and 1 of 1 added later are named by a criterion")
        self.assertIn("1 criterion has no Plan: line yet and is not drawn: C3.2.", g["read"]["b"])
        self.assertEqual(g["ladder"]["rows"][0]["cells"], [2, 0, 1])

    def test_graph_12_hands_its_drawings_each_quote_note_rewrite_and_why_unnamed(self):
        plan = dict(self.PLAN, said={"C1.2": ["one quote", "an added quote"]},
                    commitments=[dict(c, note="Now two.") if c["id"] == "P02" else c for c in self.PLAN["commitments"]])
        ch = model(data(plan=plan, criteria_index=self.CRIT)).get("g12", {}).get("chart", {})
        c12 = next((c for c in ch.get("C", []) if c["id"] == "C1.2"), {})
        self.assertEqual((c12.get("kind"), c12.get("links")), ("ref", [dict(p="P01", quote="one quote"), dict(p="N01", quote="an added quote")]))
        self.assertEqual([(c["id"], c["kind"]) for c in ch.get("C", []) if not c["links"]], [("C2.2", "unplanned"), ("C2.3", "guard")])
        self.assertEqual([(p["id"], p["status"], p["note"]) for p in ch.get("ref", [])][:2], [("P01", "kept", ""), ("P02", "changed", "Now two.")])
        self.assertEqual([p["id"] for p in ch.get("added", [])], ["N01"])
        # The rewrite after Day 1 sits above the row of Day 2, the second row.
        self.assertEqual(ch.get("rw"), [1])
        self.assertEqual(ch.get("un"), {"P02": dict(kind="due", when="Day 2"), "P03": dict(kind="standing", when=""), "P04": dict(kind="later", when="Day 3")})

    def test_graph_12_gives_the_added_commitments_their_section_labels(self):
        g = model(data(plan=self.PLAN, criteria_index=self.CRIT))["g12"]
        self.assertEqual([(s.get("label"), s.get("from"), s.get("to")) for s in g.get("added_sections", [])], [("B", 4, 4)])

    def test_graph_12_marks_a_commitment_owned_by_a_later_day_as_later_and_one_no_day_owns_as_neither(self):
        # P04 is owned by Day 3, after the last closed Day (2), and no criterion names it; P05 has no owner Day.
        plan = dict(self.PLAN, commitments=self.PLAN["commitments"] + [dict(id="P05", short="Owned", section="B", owner_day=None, rule=False, change=None, text="Unowned.")])
        un = model(data(plan=plan, criteria_index=self.CRIT))["g12"]["chart"]["un"]
        self.assertEqual((un.get("P04"), "P05" in un), (dict(kind="later", when="Day 3"), False))

    def test_graph_12_without_a_promise_file_says_so_under_not_measured(self):
        got = model(data(criteria_index=self.CRIT))
        self.assertIn(["Whether the specs follow the plan", got["g12"].get("empty")], got.get("notMeasured", []))
        self.assertIsNotNone(got["g12"].get("empty"))

    # Five yardsticks as the gel holds them: four judged (lower is better), two of them worse than their own average.
    GEL = dict(days=[14, 15, 16], judged=4, panels=[
        dict(key="cost", name="Cost of each merged pull request, main sessions", unit="$", decimals=2, lower_better=True, kit=1.86,
             average=2.67, last=dict(day=16, value=10.77), verdict="worse"),
        dict(key="replies", name="Replies for each merged pull request, main sessions", unit="", decimals=1, lower_better=True, kit=None,
             average=36.8, last=dict(day=16, value=45.5), verdict="worse"),
        dict(key="parks", name="Times the driver stopped for a person", unit="", decimals=0, lower_better=True, kit=None,
             average=4, last=dict(day=16, value=2), verdict="better"),
        dict(key="refusals", name="Calls the hooks refused", unit="", decimals=0, lower_better=False, kit=None,
             average=14.6, last=dict(day=16, value=18), verdict="flat"),
        dict(key="escapes", name="Defects that escaped from an earlier Day", unit="", decimals=0, lower_better=True, kit=None,
             average=1.2, last=None, verdict="flat")])

    def test_the_yardstick_row_names_each_one_worse_than_its_own_average(self):
        G = self.GEL
        got = model(data(gel=G))
        # the key first, so that its absence fails short
        self.assertEqual(sorted(set(got) & {"yardsticks"}), ["yardsticks"])
        Y = got["yardsticks"] or {}
        self.assertEqual((Y.get("day"), Y.get("judged"), G["judged"]), (16, 4, 4))
        self.assertEqual(Y.get("worse"), ["Cost of each merged pull request", "Replies for each merged pull request"])
        self.assertEqual(Y.get("lead"), "on Day 16, the last Day counted: 2 of 4 judged are worse than their own average so far")
        # each chip's judgement first, so that a wrong one fails short; then every field
        self.assertEqual([c.get("cls") for c in Y.get("chips") or []], ["bad", "bad", "", "none", ""])
        self.assertEqual(Y.get("chips"), [
            dict(key="cost", name="Cost of each merged pull request", value="$10.77", word="worse than its average $2.67", cls="bad",
                 title="Cost of each merged pull request, main sessions. The kit's figure: $1.86"),
            dict(key="replies", name="Replies for each merged pull request", value="45.5", word="worse than its average 36.8", cls="bad",
                 title="Replies for each merged pull request, main sessions"),
            dict(key="parks", name="Times the driver stopped for a person", value="2", word="better than its average 4", cls="",
                 title="Times the driver stopped for a person"),
            dict(key="refusals", name="Calls the hooks refused", value="18", word="not judged", cls="none", title="Calls the hooks refused"),
            dict(key="escapes", name="Defects that escaped from an earlier Day", value="–", word="level with its average", cls="",
                 title="Defects that escaped from an earlier Day")])
        # one worse, then none
        better = lambda keys: dict(G, panels=[dict(p, verdict="better") if p["key"] in keys else p for p in G["panels"]])  # noqa: E731
        leads = [(model(data(gel=better(keys)))["yardsticks"] or {}).get("lead") for keys in (("replies",), ("cost", "replies"))]
        self.assertEqual(leads, ["on Day 16, the last Day counted: 1 of 4 judged is worse than its own average so far",
                                 "on Day 16, the last Day counted: none of the 4 judged is worse than its own average so far"])
        # and no row without the gel
        none = model(data())
        self.assertEqual(sorted(set(none) & {"yardsticks"}), ["yardsticks"])
        self.assertIsNone(none["yardsticks"])

    def test_a_closed_line_carries_the_counts_of_what_it_holds(self):
        cases = [
            [dict(kind="list", heads=["  What   the picture\n shows ", "x" * 90]), dict(kind="notes", heads=["Broken since Day 3"]),
             dict(kind="table", title="Exact numbers · 12 rows: by Day", rows=12), dict(kind="table", title="How to read it", rows=0),
             dict(kind="old"), dict(kind="svg", heads=["not read"])],
            [dict(kind="table", title=f"T{n}", rows=0) for n in range(1, 10)],
        ]
        out = node(UNDER_LINE, cases)
        self.assertIsNotNone(out, "dashboard.js has no underLine")
        want = [["What the picture shows", "x" * 71 + "…", "Broken since Day 3", "Exact numbers (12 rows)", "How to read it", "As it was"],
                [f"T{n}" for n in range(1, 7)] + ["and 3 more"]]
        self.assertEqual([sum(s not in got for s in w) for got, w in zip(out, want)], [0] * len(want))
        self.assertEqual(out, want)

    def test_a_closed_line_keeps_each_lists_count_and_the_old_graph_last(self):
        long = "A name for a list that runs on and on, well past the cut of the line, and further"
        cases = [
            [dict(kind="list", heads=["Stops grouped by suspect window · 13 groups, first seen at 11 merges", f"{long} · 2", "Doubtful citations · 5 groups"]),
             dict(kind="table", title="Where it stopped: by Day", rows=0), dict(kind="table", title="  ", rows=3)],
            [dict(kind="list", heads=[f"h{n}" for n in range(1, 11)]), dict(kind="old")],
            # graph 6's two headings that differ only at their end stay apart
            [dict(kind="list", heads=[f"{h} · {n}" for h, n in zip(("Not holding when last run, since replaced by one not shown to hold", "Not holding when last run, since replaced by one that holds"), (0, 5))])],
        ]
        out = node(UNDER_LINE, cases)
        self.assertIsNotNone(out, "dashboard.js has no underLine")
        want = [["Stops grouped by suspect window · 13 groups", f"{long[:71]}… · 2", "Doubtful citations · 5 groups", "Where it stopped"],
                [f"h{n}" for n in range(1, 7)] + ["and 4 more", "As it was"],
                [f"{h} · {n}" for h, n in zip(("Not holding when last run, since replaced by one not shown to hold", "Not holding when last run, since replaced by one that holds"), (0, 5))]]
        # how many strings of each line are missing first, so that a failure stays short; then all of them, in order
        self.assertEqual([sum(s not in got for s in w) for got, w in zip(out, want)], [0] * len(want))
        self.assertEqual(out, want)

    def test_a_fold_is_read_as_its_lists_notes_tables_and_old_graph(self):
        el = lambda tag, *kids, cls=(), text="", post="": dict(tag=tag, cls=list(cls), kids=list(kids), text=text, post=post)  # noqa: E731
        fold = el("details",
                  el("summary", el("b", text="Under the picture")),
                  el("div", el("h3", text="Broken · 2"), el("p", text="not a head"), el("h4", text="Older"), cls=["find"]),
                  el("div", el("p", el("b", text="Doubtful citations"), post=" 5 groups, first seen at Day 3"), el("p", text="no lead"), cls=["notes"]),
                  el("details", el("summary", text="Exact numbers"),
                     el("table", el("tr", el("th", text="Day")), el("tr", el("td", text="1")), el("tr", el("td", text="2"))), cls=["exact"]),
                  el("div", el("details", el("summary", text="Graph 1 as it was")), cls=["mock-fold"]),
                  cls=["under"])
        out = node(FOLD_ITEMS, fold)
        self.assertIsNotNone(out, "dashboard.js has no foldItems")
        # the kinds and row counts first, so that a wrong count fails short
        self.assertEqual([(it.get("kind"), it.get("rows")) for it in out], [("list", None), ("notes", None), ("table", 2), ("old", None)])
        self.assertEqual(out, [dict(kind="list", heads=["Broken · 2", "Older"]), dict(kind="notes", heads=["Doubtful citations 5 groups"]),
                               dict(kind="table", title="Exact numbers", rows=2), dict(kind="old")])

    def test_a_link_opens_the_page_that_holds_its_target(self):
        back = ["a-b", "gel"]
        hashes = ["back", "front", "gel", "rdg", "", "a%2Db", "#gel", "a%"]
        self.assertEqual(node(VIEW_FOR, [[x, back] for x in hashes]), ["back", "front", "back", "front", None, "back", "back", "front"])


def texts(t):
    """Every string a drawn node holds, its own text and its children's, in order."""
    if isinstance(t, str):
        return [t]
    return ([t["text"]] if t.get("text") else []) + [s for k in t["kids"] for s in texts(k)]


def lane(date, name):
    """The lane of graph 10's date named `name`, or an empty one, so a missing lane fails the test by its assertion."""
    return next((x for x in date.get("lanes", []) if x.get("name") == name), {})


def nodes(t):
    """Every drawn node under t, t first."""
    if isinstance(t, dict):
        yield t
        for k in t["kids"]:
            yield from nodes(k)


@unittest.skipUnless(shutil.which("node"), "needs node to draw the page's plan bar")
class DrawTest(unittest.TestCase):
    """What graph 12's bar draws, read from the nodes planBar() puts in its box."""

    # Eight commitments under one long section (40 px wide), one under a short one (5 px), and six added later (30 px).
    PLAN = dict(reference="x", quotes=0, unlined=[], rewrites=[], said={}, links={}, commitments=[
        *[dict(id=f"P0{i}", short=f"P{i}", section="A long section name that cannot fit", owner_day=None, rule=False, change=None, text="t.")
          for i in range(1, 9)],
        dict(id="P09", short="Late", section="Narrow", owner_day=3, rule=False, change=None, text="t."),
        *[dict(id=f"N0{i}", short=f"N{i}", section="Later", owner_day=None, rule=False, change=None, text="t.") for i in range(1, 7)]])

    def box(self):
        return node(PLAN_BAR, data(plan=self.PLAN))

    def labels(self, box):
        """The section labels: the text nodes at the font size they are drawn at."""
        return [n for n in nodes(box) if n["tag"] == "text" and n["attrs"].get("style") == "font-size:10.5px"]

    def test_graph_12_folds_its_key_under_a_summary_after_the_show_only_chips(self):
        kids = self.box()["kids"]
        self.assertEqual([(k["tag"], k["attrs"].get("class")) for k in kids], [("div", "pc-chiprow"), ("details", "pc-key"), ("div", "scroll-x")])
        key = next((k for k in kids if k["tag"] == "details"), {"kids": []})
        self.assertIn("Key: what each colour and sign means", texts(key))
        self.assertEqual(len([k for k in key["kids"] if isinstance(k, dict) and k["attrs"].get("class") == "pc-legend"]), 4)

    def test_graph_12_draws_the_added_commitments_section_label_under_the_added_arm(self):
        # each section's label in the plan's order, and the added arm's own one stands on that arm's bracket
        box = self.box()
        labels = self.labels(box)
        self.assertEqual([n["text"] for n in labels], ["A long section name that cannot fit", "Narrow", "Later"])
        brackets = [n["attrs"] for n in nodes(box) if n["tag"] == "line" and n["attrs"].get("stroke-width") == "1.5"]
        self.assertEqual(len(brackets), 3)
        foot = float(re.match(r"translate\(([-\d.]+) ", labels[-1]["attrs"]["transform"]).group(1))
        self.assertEqual(float(brackets[-1]["x1"]) <= foot <= float(brackets[-1]["x2"]), True)

    def test_graph_12_draws_every_section_label_slanted_and_whole_with_its_name_in_a_title(self):
        box = self.box()
        labels = self.labels(box)
        # slanted as the gene slants its own, so a narrow section keeps its name too; none is near the gene's cut at 38
        self.assertEqual([n["text"] for n in labels], ["A long section name that cannot fit", "Narrow", "Later"])
        self.assertEqual([[k["text"] for k in n["kids"] if isinstance(k, dict) and k["tag"] == "title"] for n in labels],
                         [["A long section name that cannot fit"], ["Narrow"], ["Later"]])
        self.assertEqual([(n["attrs"].get("transform") or "").endswith("rotate(-52)") for n in labels], [True, True, True])
        # Each group still has its tick: the two plan sections and the added one.
        self.assertEqual(len([n for n in nodes(box) if n["tag"] == "line" and n["attrs"].get("stroke-width") == "0.75"]), 3)

    def test_graph_12_draws_a_later_commitment_as_a_dotted_outline(self):
        outlines = [n["attrs"]["stroke-dasharray"] for n in nodes(self.box()) if n["tag"] == "rect" and "stroke-dasharray" in n["attrs"]]
        self.assertEqual(outlines, ["1 1.2"])

    def test_graph_12_legend_names_the_later_stripe_and_keeps_the_safety_check_apart_from_no_criterion(self):
        drawn = texts(self.box())
        for words in ["no criterion yet, owned by a later Day", "safety check (Plan: none, a row mark)", "no criterion names it (a stripe of the bar)"]:
            self.assertIn(words, drawn)


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

    def test_the_yardstick_row_shows_on_a_day_nothing_needs_attention(self):
        # no needs_attention: the section shows for the row alone, its folded list stays hidden
        out = boot(data(gel=ModelTest.GEL))
        self.assertEqual((out["error"], out["attention"]["hidden"], out["attentionAll"] and out["attentionAll"]["hidden"], out["sticks"] and out["sticks"]["hidden"]),
                         (None, False, True, False))

    def test_the_page_names_no_repository_of_its_own(self):
        # a link to the repository is made from the data's meta.repo_url, so the page built from demo data names none
        found = sorted({m for name in ("index.html", "dashboard.js", "dashboard.css")
                        for m in re.findall(r"github\.com/[\w.-]+/[\w.-]+", read(name))})
        self.assertEqual(found, [])

    def test_the_quality_score_shows_under_the_now_line_only_when_the_data_has_one(self):
        self.assertEqual(boot(data())["quality"]["hidden"], True)
        out = boot(data(score=ModelTest.SCORE))
        self.assertEqual((out["error"], out["logged"], out["quality"]["hidden"]), (None, [], False))

    def test_the_line_under_the_whole_score_says_the_days_own_scores_average_apart(self):
        # the whole is counted over all the finished Days at once; the Days' own scores have their own mean
        out = node(BOOT_PRESS, data(score=dict(ModelTest.SCORE, days_mean=88)))
        self.assertEqual((out["error"], out["pressed"], len(out["qof"])), (None, None, 2))
        whole = "quality of the finished Days, out of 100, counted over all of them at once; the Days' own scores average 88"
        self.assertEqual((out["qof"][0][-30:], out["qof"][0] == whole), (whole[-30:], True))
        # a chosen Day's line, and the whole's when the data has no mean, read as they did
        self.assertEqual(out["qof"][1], "quality of Day 1, out of 100")
        bare = node(BOOT_PRESS, data(score=ModelTest.SCORE))
        self.assertEqual(bare["qof"][:1], ["quality of the finished Days, out of 100"])

    def test_the_now_line_gives_way_to_the_ring_only_when_the_ring_is_drawn(self):
        # The ring's middle says the next step, so the plain Now line hides under it. With no ring (no phase rows in the
        # data, or the plan's rows with no ring counted from them) the Now line is all the page says of where the work is.
        rows = [dict(phase=0, days=[1, 2, 3], stop=None, lifted=False, from_day=None, cut=False)]
        hidden = lambda out: (out["error"], out["now"]["hidden"], out["whr"]["hidden"])  # noqa: E731
        self.assertEqual(hidden(boot(demo_data())), (None, True, False))
        self.assertEqual(hidden(boot(data())), (None, False, True))
        self.assertEqual(hidden(boot(data(meta=dict(where=dict(rows=rows, names={}))))), (None, False, True))

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
                         "re-checks of finished promises. The error-correction stream is not drawn. The energy budget is not drawn.")
        one = boot(data(data=source("abc", ["replay-history.json"])))
        self.assertEqual(one["missing"]["text"], "The dashboard-data branch has no replay-history.json, so this page leaves out "
                         "the re-checks of finished promises.")
        self.assertTrue(boot(data())["missing"]["hidden"])  # example data, or a page built before the branch: no claim

    def test_needs_attention_is_drawn_with_the_rule_and_hidden_without_it(self):
        self.assertEqual(boot(data())["attention"]["hidden"], True)
        out = boot(data(needs_attention=NEEDS))
        self.assertEqual((out["error"], out["logged"], out["attention"]["hidden"]), (None, [], False))
        # a graph with something open shows its chips beside its title; one with nothing open shows none
        self.assertEqual((out["chips"]["prt"]["hidden"], out["chips"]["g12"]["hidden"]), (False, True))
        whole = boot(demo_data())
        self.assertEqual((whole["error"], whole["logged"], whole["attention"]["hidden"]), (None, [], False))

    def test_the_page_draws_without_an_error_on_data_with_nothing_in_it(self):
        out = boot({})
        self.assertEqual((out["error"], out["logged"]), (None, []))

    def test_a_graph_that_cannot_be_drawn_is_logged_and_does_not_stop_the_page(self):
        out = boot(data(plan=dict(commitments=[None])))
        self.assertIsNone(out["error"])
        # Graph 12 reads the plan's commitments, so it says it could not be drawn; every other graph drew.
        self.assertEqual([line.split(":")[0] for line in out["logged"]], ["g12"])

    def test_the_page_draws_the_driver_runs_without_an_error(self):
        clock = dict(prs=[], sessions=[{"date": "2026-01-02", "day": 2, "agent": "main", "from": "2026-01-02T08:00:00+01:00",
                                        "to": "2026-01-02T11:00:00+01:00", "replies": 3}])
        steps = [run_step("C", 2, "parked", crashes=1, parks=[park(21, "maintainer")]), run_step("D", 2, "fixed", fixes=1)]
        out = boot(data(clock=clock, driver_runs=dict(source="run log", counted="2026-01-02T13:00:00Z", steps=steps,
                                                       parks=[an_issue(21, "2026-01-02T09:00:00Z")])))
        self.assertEqual((out["error"], out["logged"]), (None, []))


class ThemeTest(unittest.TestCase):
    def test_the_switch_flips_what_shows_the_saved_choice_first_then_the_systems(self):
        cases = [[None, False], [None, True], ["dark", False], ["light", True], ["junk", True]]
        self.assertEqual(node(FLIP, cases), ["dark", "light", "light", "dark", "light"])

    def test_the_header_has_the_switch_and_the_page_wires_it_before_it_draws(self):
        self.assertIn('<button type="button" class="theme" id="theme" aria-pressed="false">Dark mode</button>', read("index.html"))
        start = re.search(r"function start\(\) \{(.*?)\n\}", read("dashboard.js"), re.S).group(1)
        self.assertEqual(start.strip().splitlines()[0], "themeToggle();")


# The cards with a plot of their own, each folded under the drawing that took its place: graph 6 under the merge graph,
# graph 1 under the plan being read, graph 2 under its gel, graph 7 under its error-correction stream and graph 10 under
# its actogram. Graphs 3 to 5, 8, 9 and 11 and the "Where we are" tiles have left the page: the proteins, the energy
# budget, the growth rings, the reflex arcs and the ring stand alone (GONE_IDS, GONE_KEYS, which list everything that left).
CARDS = (1, 2, 6, 7, 10)
FOLDED = (6, 1, 2, 7, 10)
FOLDS = ["g1-fold", "g7-fold", "g6-fold", "g2-fold", "g10-fold"]  # in the page's order, front page first
GONE_IDS = ("where-fold", "where", "g3-fold", "g8-fold", "g9-fold", "g3-hist", "g11-fold", "g11", "g11-plot", "g11-table", "cel",
            "cel-fig", "how-fold", "how-this-works")
GONE_KEYS = ("where", "g3", "g4", "g5", "map", "g8", "g9", "g11", "cel", "how")
# Links to the graphs that left still land on the drawing in their place: an empty anchor in its section.
ANCHORS = (("prt", ("g3", "g4", "g5")), ("atp", ("g8",)), ("rng", ("g9",)))
EYEBROWS = {"whr": "Where we are · the plan as one turn of the cell cycle, a checkpoint at each stop", "prt": "Graphs 3–5 · drawn as proteins",
            "atp": "Graph 8 · drawn as an energy budget", "rng": "Graph 9 · drawn as growth rings",
            "rfx": "Graph 11 · drawn as reflex arcs"}

# gelDraw() and protDraw() on the model of the data from stdin, on a document that keeps every node it is given: how
# many marks of each kind they drew, and the words of the proteins' figures.
GEL_PRT = r"""
const fs = require("fs"), vm = require("vm"), els = {};
const node = tag => { const n = { tag, attrs: {}, kids: [], style: {}, hidden: false, textContent: "",
  classList: { add(c) { n.attrs.class = ((n.attrs.class || "") + " " + c).trim(); }, remove() {}, toggle() {} },
  setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k]; }, appendChild(c) { this.kids.push(c); return c; },
  append(...c) { this.kids.push(...c); }, replaceChildren(...c) { if (c.some(Array.isArray)) throw new Error("replaceChildren() given an array: a browser writes it as text"); this.kids = c; }, addEventListener() {} };
  Object.defineProperty(n, "className", { set(v) { n.attrs.class = v; }, get() { return n.attrs.class || ""; } });
  return n; };
const document = { createElementNS: (ns, tag) => node(tag), createElement: node };
const $ = id => els[id] || (els[id] = node(id));
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")), document, $ });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const all = n => [n, ...(n.kids || []).filter(k => k && typeof k === "object").flatMap(all)];
  const is = (root, sel) => all(root).filter(e => sel.every(c => ((e.attrs && e.attrs.class) || "").split(" ").includes(c))).length;
  const words = n => typeof n === "string" ? n : [n.textContent, ...(n.kids || []).map(words)].join(" ");
  const M = model(DATA), days = [];
  gelDraw(M.gel, $, days); protDraw(M.prt, $, days);
  // what the proteins say with no Day chosen, then with Day 2
  const said = [$("prt-say").textContent]; days[1](2); said.push($("prt-say").textContent); days[1](null);
  const g = $("gel-fig"), p = $("prt-fig");
  ({ gel: { pans: is(g, ["pan"]), lanes: is(g, ["b", "ln"]), ladder: is(g, ["b", "rb"]), figs: $("gel-figs").kids.length },
     prt: { prot: is(p, ["prot"]), cells: all(p).filter(e => e.attrs && e.attrs.tabindex != null && is(e, ["rs"])).length, rings: is(p, ["b", "arc"]),
            runs: is(p, ["b", "run"]), figs: words($("prt-figs")).replace(/\\s+/g, " "), all: $("prt-k-all").textContent, said }, onDay: days.length })`, ctx)));
"""


# protDraw() on the same document: where its group headings, cards, names and figures sit, and the figure's height.
PRT_GEO = GEL_PRT[:GEL_PRT.index("console.log(")] + r"""console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const all = n => [n, ...(n.kids || []).filter(k => k && typeof k === "object").flatMap(all)];
  protDraw(model(DATA).prt, $, []);
  const made = all($("prt-fig")), of = c => made.filter(e => e.attrs && e.attrs.class === c);
  ({ titles: of("t-grp").map(e => +e.attrs.y), boxes: of("tl").map(e => ({ y: +e.attrs.y, h: +e.attrs.height })),
     names: of("t-name").map(e => ({ x: +e.attrs.x, y: +e.attrs.y, lines: e.kids.length })), subs: of("t-sub").map(e => ({ x: +e.attrs.x, y: +e.attrs.y })),
     height: +$("prt-fig").attrs.viewBox.split(" ")[3] })`, ctx)));
"""


class GelAndProteinPageTest(unittest.TestCase):
    """The gel and the proteins, drawn by the page on the example data."""

    def test_the_gel_and_the_proteins_draw_a_mark_for_every_panel_lane_chain_and_cell(self):
        spec = importlib.util.spec_from_file_location("demo_data", os.path.join(HERE, "demo-data.py"))
        demo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo)
        data = demo.demo()
        G, P, out = data["gel"], data["protein"], node(GEL_PRT, data)
        ladder = sum((p["average"] is not None) + (p["kit"] is not None) for p in G["panels"])
        self.assertEqual(out["gel"], dict(pans=len(G["panels"]), lanes=len(G["panels"]) * len(G["days"]), ladder=ladder, figs=2 + len(G["kit"])))
        self.assertEqual(out["prt"]["prot"], len(P["chains"]))
        self.assertEqual(out["prt"]["cells"], P["written"])
        self.assertEqual(out["prt"]["rings"], len(P["chains"]))
        self.assertEqual(out["prt"]["runs"], sum(1 for c in P["chains"] if c["run"]))
        self.assertIn(f"{P['proven']} of {P['rechecked']} promises proven, of those re-checked", out["prt"]["figs"])
        outside = [x["id"] for c in P["chains"] for x in c["cells"] if x["state"] == "open"]
        self.assertTrue(outside)
        self.assertIn(f"{len(outside)} was written and not built ({', '.join(outside)})", out["prt"]["all"])
        self.assertEqual(out["onDay"], 2)  # each hooks into the page's Day buttons

    def test_the_proteins_say_how_many_promises_every_day_or_the_chosen_day_made(self):
        data = demo_data()
        P, said = data["protein"], node(GEL_PRT, data)["prt"]["said"]
        days = sorted({x["day"] for c in P["chains"] for x in c["cells"]})
        self.assertEqual(said[0], f"Every Day: {P['written']} promises, Days {days[0]} to {days[-1]}.")
        two = [(c["name"], sum(1 for x in c["cells"] if x["day"] == 2)) for c in P["chains"]]
        two = [(name, k) for name, k in two if k]
        self.assertEqual(said[1], f"Day 2: {sum(k for _, k in two)} promises, " + ", ".join(f"{k} in “{name}”" for name, k in two) + ".")

    def test_a_proteins_figures_sit_right_under_its_own_name(self):
        # the first chain's name wraps onto two lines and the second's, in the same row, does not: no empty line
        # between the second's name and its figures, as in the mockup
        data = demo_data()
        data["protein"]["chains"][0]["name"] = "A name long enough to wrap onto a second line"
        g = node(PRT_GEO, data)
        under = [(t["y"], t["x"], round(s["y"] - t["y"], 1), t["lines"]) for t in g["names"] for s in g["subs"] if s["x"] == t["x"] and 0 < s["y"] - t["y"] < 40]
        self.assertEqual([u[2:] for u in sorted(under)][:2], [(29.0, 2), (14.0, 1)])

    def test_a_group_heading_of_the_proteins_sits_clear_of_the_cards_above_it(self):
        g = node(PRT_GEO, demo_data())
        rows = sorted({(r["y"], r["y"] + r["h"]) for r in g["boxes"]})
        gaps = [round(title - max(b for t, b in rows if t < title), 1) for title in g["titles"][1:]]
        self.assertTrue(gaps)
        self.assertEqual([x for x in gaps if x < 28.5], [])  # the mockup's: 28.5 under the cards, 8.5 over the next

    def test_the_proteins_leave_no_blank_under_their_last_row(self):
        g = node(PRT_GEO, demo_data())
        self.assertLessEqual(g["height"] - max(r["y"] + r["h"] for r in g["boxes"]), 3)

    def test_the_gel_and_the_proteins_build_no_html_from_text(self):
        script = read("dashboard.js")
        for name in ("function pointerBox", "function gelDraw", "function protDraw", "function prfDraw", "function atpDraw",
                     "function rngDraw", "function actDraw", "function openFolds", "function foldLinks"):
            body = script[script.index(name):]
            body = body[:body.index("\n}\n") if "\n}\n" in body else body.index("\r\n}\r\n")]
            self.assertNotIn("innerHTML", body, name)


# atpDraw() and rngDraw() on the model of the data from stdin, on a document that keeps every node it is given: how
# many marks of each kind they drew, their words, the banner, and openFolds() on a link into a fold.
ATP_RNG = r"""
const fs = require("fs"), vm = require("vm"), els = {};
const node = tag => { const n = { tag, attrs: {}, kids: [], style: {}, hidden: false, textContent: "", open: false, parentNode: null,
  classList: { add(c) { n.attrs.class = ((n.attrs.class || "") + " " + c).trim(); }, remove() {}, toggle() {}, contains() { return false; } },
  setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k]; }, appendChild(c) { this.kids.push(c); return c; },
  append(...c) { this.kids.push(...c); }, replaceChildren(...c) { if (c.some(Array.isArray)) throw new Error("replaceChildren() given an array: a browser writes it as text"); this.kids = c; }, addEventListener() {}, scrollIntoView() { n.scrolled = true; } };
  Object.defineProperty(n, "className", { set(v) { n.attrs.class = v; }, get() { return n.attrs.class || ""; } });
  return n; };
const document = { createElementNS: (ns, tag) => node(tag), createElement: node, addEventListener() {}, getElementById: id => els[id] || null };
const $ = id => els[id] || (els[id] = node(id));
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")), document, $ });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const all = n => [n, ...(n.kids || []).filter(k => k && typeof k === "object").flatMap(all)];
  const is = (root, sel) => all(root).filter(e => sel.every(c => ((e.attrs && e.attrs.class) || "").split(" ").includes(c))).length;
  const words = n => typeof n === "string" ? n : [n.textContent, ...(n.kids || []).map(words)].join(" ");
  const keyed = (root, re) => all(root).filter(e => e.attrs && re.test(e.attrs["data-k"] || "")).length;
  const M = model(DATA), days = [];
  const drew = k => !M[k].error && !M[k].empty;
  if (drew("atp")) atpDraw(M.atp, $, days);
  if (drew("rng")) rngDraw(M.rng, $, days);
  const a = $("atp-fig"), r = $("rng-fig");
  // a link into a fold: the details around it open, and it is scrolled to
  const fold = document.createElement("details"), inner = document.createElement("div"), target = document.createElement("div");
  fold.tagName = "DETAILS"; inner.tagName = "DIV"; target.tagName = "DIV"; inner.parentNode = fold; target.parentNode = inner;
  openFolds(target);
  ({ atp: { drew: drew("atp"), error: M.atp.error || null, cols: is(a, ["b", "col"]), beads: is(a, ["q"]), rails: is(a, ["rail"]), pills: is(a, ["pill"]),
            parts: [0, 1, 2, 3, 4, 5].map(i => is(a, ["q", "p" + i])), avg: is(a, ["avgl"]), share: $("atp-share").kids.map(k => k.attrs.class),
            words: [a, $("atp-figs"), $("atp-bought"), $("atp-key"), $("atp-finds"), $("atp-round"), $("atp-split")].map(words).join(" ").replace(/\\s+/g, " ") },
     rng: { drew: drew("rng"), error: M.rng.error || null, days: keyed(r, /^d\\d+$/), outside: keyed(r, /^o\\d+$/), sides: keyed(r, /^(all|out)$/),
            hatched: is(r, ["b", "out"]), leads: is(r, ["lead"]), words: [r, $("rng-figs"), $("rng-finds")].map(words).join(" ").replace(/\\s+/g, " ") },
     missing: M.head.missing, onDay: days.length, fold: [fold.open, !!target.scrolled] })`, ctx)));
"""


# rngDraw() on the same document: every word it set in the figure, with its x, y and anchor, and the path of every lead.
RNG_TEXTS = ATP_RNG[:ATP_RNG.index("console.log(")] + r"""console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const all = n => [n, ...(n.kids || []).filter(k => k && typeof k === "object").flatMap(all)];
  rngDraw(model(DATA).rng, $, []);
  ({ texts: all($("rng-fig")).filter(e => e.tag === "text").map(e => ({ w: [e.textContent, ...e.kids.map(k => k.textContent)].join(""),
       x: +e.attrs.x, y: +e.attrs.y, a: e.attrs["text-anchor"] || "start" })),
     leads: all($("rng-fig")).filter(e => e.attrs && e.attrs.class === "lead").map(e => e.attrs.d) })`, ctx)));
"""


def thin_rings():
    """Rings with Day 1 just wide enough for its head label and Day 2 too thin for one: Day 2's name goes under the
    strip, where the pith's and the bark's labels already are. Outside the Days, one thin ring and one wide."""
    def row(pr, own, kind, **work):
        w = dict.fromkeys(("spec", "context", "prod", "test", "tooling"), 0)
        w.update(work)
        return dict(pr=pr, own_day=own, kind=kind, work=w, date=f"2026-01-0{pr}", branch="")
    data = dict(rows=[row(1, 1, "code", prod=600), row(2, 2, "code", test=200), row(3, 3, "code", test=10000),
                      row(4, 4, "code", prod=10000), row(5, None, "other", tooling=30), row(6, None, "other", tooling=9000)],
                days=[dict(day=d, status="done", title=str(d)) for d in (1, 2, 3, 4)],
                now=dict(head="abc", last_pr=6, generated="2026-01-07T00:00+00:00"))
    return dict(data, rings=views.rings(data))


def word_box(t):
    """A word's box as the page estimates it: about 5.6 px a character, from 9 px above its baseline to 2 below."""
    width = 5.6 * len(t["w"])
    x0 = t["x"] - width if t["a"] == "end" else t["x"] - width / 2 if t["a"] == "middle" else t["x"]
    return (t["w"], x0, x0 + width, t["y"] - 9, t["y"] + 2)


def demo_data():
    spec = importlib.util.spec_from_file_location("demo_data", os.path.join(HERE, "demo-data.py"))
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    return demo.demo()


class CostAndRingsPageTest(unittest.TestCase):
    """Graph 8 as an energy budget and graph 9 as growth rings, drawn by the page."""

    def test_the_budget_draws_a_column_for_each_day_a_block_for_each_part_between_them_and_a_column_for_each_date(self):
        data = demo_data()
        B, out = data["budget"], node(ATP_RNG, data)
        cols, atp = B["cols"], out["atp"]
        blocks = [c for c in cols["between"] if c["b"]]
        self.assertEqual((atp["drew"], atp["error"]), (True, None))
        self.assertEqual([c["label"] for c in blocks], ["dashboard", "tooling", "stayed on main"])
        self.assertEqual(atp["cols"], len(cols["date"]) + len(cols["day"]) + len(blocks))
        self.assertEqual(atp["beads"], 2 * B["beads"])
        # each part's beads: a Day's column and a block by Day, and its share of each date's column
        by_day = [sum(c["b"] for c in cols["day"])] + [sum(c["b"] for c in blocks if c["part"] == i) for i in range(1, 6)]
        self.assertEqual(atp["parts"], [by_day[i] + sum(c["pb"][i] for c in cols["date"]) for i in range(6)])
        self.assertEqual((atp["rails"], atp["avg"]), (0, 1))  # no rail past 150k any more; one line at the average Day
        self.assertEqual(atp["share"], ["p0", "p1", "p2", "p4"])  # the bar of shares: a piece for each part with dollars
        self.assertEqual(atp["pills"], len(B["pills"]))
        self.assertIn("one bead is $2 , rounded", atp["words"])
        self.assertIn("of tokens at list prices Not a bill", atp["words"])
        self.assertIn(f"${B['mean']:.2f} for a Day, on average Over {B['mean_over']} closed Days.", atp["words"])
        self.assertIn(f"${B['on_days']:.2f} {B['on_days_pct']}% on the Days", atp["words"])
        self.assertIn(f"${B['between']:.2f} {B['between_pct']}% between the Days Dashboard $", atp["words"])
        self.assertIn(f"Shared over the {B['closed']} closed Days, it is ${B['per_closed']:.2f} each.", atp["words"])
        self.assertEqual(out["onDay"], 2)  # each hooks into the page's Day buttons

    def test_with_no_day_closed_the_budget_has_no_average_and_draws_no_line(self):
        data = demo_data()
        for day in data["days"]:
            day["status"] = "active"
        data["budget"] = views.budget(data)
        atp = node(ATP_RNG, data)["atp"]
        self.assertEqual((atp["drew"], atp["error"], atp["avg"]), (True, None, 0))
        self.assertIn("– for a Day, on average No Day with a token row is closed yet.", atp["words"])
        self.assertNotIn("the average closed Day", atp["words"])

    def test_the_rings_draw_a_ring_for_each_day_and_for_the_work_beside_it(self):
        data = demo_data()
        R, out = data["rings"], node(ATP_RNG, data)
        self.assertEqual((out["rng"]["drew"], out["rng"]["error"]), (True, None))
        self.assertEqual((out["rng"]["days"], out["rng"]["outside"]), (len(R["days"]), len(R["outside"])))
        # work on no Day's branch: one thin ring and one wide one, both hatched, the thin one named under a lead
        def row(pr, own, kind, **work):
            w = dict.fromkeys(("spec", "context", "prod", "test", "tooling"), 0)
            w.update(work)
            return dict(pr=pr, own_day=own, kind=kind, work=w, date=f"2026-01-0{pr}", branch="")
        data = dict(rows=[row(1, 1, "code", prod=300, test=500), row(2, None, "other", tooling=900), row(3, 2, "code", test=40, spec=10),
                          row(4, None, "other", tooling=5)],
                    days=[dict(day=1, status="done", title="One"), dict(day=2, status="active", title="Two")],
                    now=dict(head="abc", last_pr=4, generated="2026-01-05T00:00+00:00"))
        out = node(ATP_RNG, dict(data, rings=views.rings(data)))["rng"]
        self.assertEqual((out["days"], out["outside"], out["sides"], out["hatched"]), (2, 2, 2, 3))
        self.assertGreaterEqual(out["leads"], 1)
        self.assertIn("at Day 2: 5", out["words"])
        self.assertIn("850 inside the 2 Days, 905 outside any Day", out["words"])

    def test_no_label_under_a_strip_of_rings_overlaps_another(self):
        texts = node(RNG_TEXTS, thin_rings())["texts"]
        low = next(t for t in texts if t["w"].startswith("Outside any Day"))["y"]
        for top, bottom in ((47 + 120, low - 9), (low + 120 + 37, 10000)):  # under the upper strip, under the lower
            boxes = [word_box(t) for t in texts if top < t["y"] < bottom]
            over = [(a[0], b[0]) for i, a in enumerate(boxes) for b in boxes[i + 1:] if a[1] < b[2] and b[1] < a[2] and a[3] < b[4] and b[3] < a[4]]
            self.assertEqual(over, [])
        # and the upper strip's labels stay clear of the lower strip's heading
        self.assertEqual([t["w"] for t in texts if 47 + 120 < t["y"] < low and t["y"] + 2 > low - 9], [])

    def test_a_lead_to_a_label_a_line_lower_is_not_drawn_through_the_words_above_it(self):
        # Day 2's label sits a line under the pith's: its lead runs down to it, and stops where the pith's words are
        drawn = node(RNG_TEXTS, thin_rings())
        boxes = [word_box(t) for t in drawn["texts"]]
        day2 = next(b for b in boxes if b[0] == "Day 2: 200")
        pith = next(b for b in boxes if b[0].startswith("pith"))
        self.assertGreaterEqual(day2[3], pith[4])  # a line lower: its words start under the pith's
        # the lead's strokes down from the bracket under the ring (the bracket itself is 3 px high)
        down = [(float(x), float(a), float(b)) for d in drawn["leads"] for x, a, b in re.findall(r"M([\d.]+) ([\d.]+) V([\d.]+)", d) if float(b) - float(a) > 3]
        self.assertEqual(len(down), 1)
        self.assertEqual(round(day2[3] - down[0][2], 1), 1.0)  # it ends 1 px above its own words
        self.assertEqual([w for w, x0, x1, y0, y1 in boxes for x, a, b in down if x0 <= x <= x1 and a < y1 and y0 < b], [])

    def test_without_token_usage_json_the_budget_is_not_drawn_and_the_banner_says_so(self):
        for source in (dict(branch="dashboard-data", commit="abc", at=None, absent=["token-usage.json"]),
                       dict(branch="dashboard-data", commit=None, at=None, absent=[])):
            data = demo_data()
            data["data"] = source
            data["budget"] = views.budget(data)
            out = node(ATP_RNG, data)
            self.assertEqual((out["atp"]["drew"], out["atp"]["cols"], out["atp"]["beads"]), (False, 0, 0))
            self.assertIn("The energy budget is not drawn.", out["missing"])
            self.assertTrue(out["rng"]["drew"])  # the rings need nothing from the data branch

    def test_a_link_to_a_folded_graph_opens_its_fold(self):
        self.assertEqual(node(ATP_RNG, demo_data())["fold"], [True, True])
        script = read("dashboard.js")
        self.assertIn('addEventListener("hashchange", go)', script)
        # given the switch between the two pages, so that a link first turns to the page that holds its target
        self.assertRegex(script[script.index("function draw(M, DATA)"):], r"foldLinks\(\w+\);")


# actDraw() on the model of the data from stdin, on a document that keeps every node it is given and the listeners
# put on it: its rows, merge ticks, wait marks and hatching, its words, the rows the Day buttons dim, and what a click
# on the first row does (graph 10 turned to its date, its fold opened). A lane's waits are one path: `waits` counts
# the stretches in it. `n` counts the marks by class, `said` is each row's date and Days as written, `lanes` the first
# row's lane names, `head` the table's headings, and `tips` what the pointer box says on row `tip_row` for the row,
# its first pull request, its first check with a failed run and its first merge.
ACT_DRAW = r"""
const fs = require("fs"), vm = require("vm"), els = {};
const node = tag => { const n = { tag, attrs: {}, kids: [], style: {}, hidden: false, textContent: "", open: false, parentNode: null, on: {}, dim: false,
  classList: { add(c) { n.attrs.class = ((n.attrs.class || "") + " " + c).trim(); }, remove() {}, toggle(c, on) { if (c === "mk-dim") n.dim = !!on; }, contains() { return false; } },
  setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k]; }, appendChild(c) { this.kids.push(c); return c; },
  append(...c) { this.kids.push(...c); }, replaceChildren(...c) { if (c.some(Array.isArray)) throw new Error("replaceChildren() given an array: a browser writes it as text");
    if (c.some(k => k == null)) throw new Error("replaceChildren() given null: a browser writes it as text"); this.kids = c; },
  addEventListener(t, fn) { n.on[t] = fn; }, scrollIntoView() { n.scrolled = true; }, getBoundingClientRect: () => ({ left: 0, bottom: 0 }) };
  Object.defineProperty(n, "className", { set(v) { n.attrs.class = v; }, get() { return n.attrs.class || ""; } });
  return n; };
const document = { createElementNS: (ns, tag) => node(tag), createElement: node, addEventListener() {}, getElementById: id => els[id] || null };
const $ = id => els[id] || (els[id] = node(id));
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")), document, $, innerWidth: 1200, innerHeight: 800 });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const all = n => [n, ...(n.kids || []).filter(k => k && typeof k === "object").flatMap(all)];
  const is = (root, sel) => all(root).filter(e => sel.every(c => ((e.attrs && e.attrs.class) || "").split(" ").includes(c)));
  const words = n => typeof n === "string" ? n : [n.textContent, ...(n.kids || []).map(words)].join(" ");
  const tidy = t => t.replace(/\\s+/g, " ").trim();
  const M = model(DATA), days = [], dates = [], A = M.act;
  const drew = !A.error && !A.empty ? (actDraw(A, $, days, [d => dates.push(d)]), true) : false;
  const f = $("act-fig"), rows = is(f, ["act-row", "b"]);
  let dimmed = null, opened = null, tips = null;
  if (drew) {
    days.forEach(fn => fn(DATA.dim_day)); dimmed = rows.filter(r => r.dim).length;
    const r = rows[0]; r.closest = () => r; f.on.click({ target: r }); opened = [dates, !!$("g10").scrolled];
    const at = rows[DATA.tip_row || 0];
    tips = [at, ...["act-p", "act-failed", "act-m"].map(c => is(at, [c])[0])].map(e => { if (!e) return null;
      e.closest = () => e; f.on.focusin({ target: e }); return $("act-tip").kids.map(words).map(tidy); });
  }
  const CLS = ["act-s", "act-w", "act-two", "act-p", "act-p2", "act-ok", "act-failed", "act-m", "act-t-ln", "act-mini", "act-mini-w", "act-sep", "act-trk", "act-cnt", "act-t-cnt", "act-ml"];
  ({ drew, empty: A.empty || null, error: A.error || null, rows: rows.length, merges: is(f, ["act-m"]).length,
     waits: is(f, ["act-w"]).reduce((s, e) => s + (e.attrs.d.match(/M/g) || []).length, 0),
     hatched: is(f, ["act-unc"]).length, words: [$("act-figs"), $("act-finds"), $("act-bends")].map(words).join(" ").replace(/\\s+/g, " "),
     table: is($("act-table"), []).filter(e => e.tag === "tr").length, onDay: days.length, dimmed, opened,
     n: Object.fromEntries(CLS.map(c => [c, is(f, [c]).length])), box: f.attrs.viewBox || null,
     said: rows.map(r => [is(r, ["act-t-date"]), is(r, ["act-t-day"])].map(t => t.map(words).map(tidy).join(" | "))),
     lanes: rows.length ? is(rows[0], ["act-t-ln"]).map(e => e.textContent) : [],
     head: is($("act-table"), []).filter(e => e.tag === "th").map(words).map(tidy), tips })`, ctx)));
"""


def act_data(**source):
    """The example data, one of its sessions waiting on tests from 09:00 to 09:20, the actogram counted from it."""
    data = demo_data()
    s = data["clock"]["sessions"][0]
    s["runs"] = [[s["from"][:11] + "07:00:00Z", s["from"][:11] + "07:20:00Z", "tests"]]
    s["ran"] = {"tests": 1200}
    if source:
        data["data"] = dict(data["data"], **source)
    data["actogram"] = views.actogram(data)
    return data


def act_lanes_data():
    """act_data() and what the example data lacks. On its first date: a second main session busy for 20 minutes while
    the first is, a sub-agent waiting on GitHub's checks, and two pull requests in the evening, the second opened while the
    first is open, the first's checks running twice with a failed run the first time. Two dates before it, a date
    whose only session and pull request are of no Day."""
    data = demo_data()
    c = data["clock"]
    first = c["sessions"][0]
    at = first["from"][:11]
    first["runs"] = [[at + "07:00:00Z", at + "07:20:00Z", "tests"]]
    first["ran"] = {"tests": 1200}
    sub = next(s for s in c["sessions"] if s["agent"] == "implementer")
    sub["runs"] = [[at + "08:22:00Z", at + "08:30:00Z", "checks"]]
    sub["ran"] = {"checks": 480}
    c["sessions"].append({"date": at[:10], "day": first["day"], "agent": "main", "from": at + "09:00:00+02:00", "to": at + "09:20:00+02:00", "replies": 4})
    before = (datetime.date.fromisoformat(at[:10]) - datetime.timedelta(days=2)).isoformat() + "T"
    c["sessions"].append({"date": before[:10], "day": None, "agent": "main", "from": before + "10:00:00+02:00", "to": before + "11:00:00+02:00", "replies": 4})

    def pr(number, day, kind, on, opened, merged, spans, failed=0):
        return dict(number=number, day=day, kind=kind, branch=f"b{number}", opened=f"{on}{opened}:00Z", merged=f"{on}{merged}:00Z",
                    checks=dict(start=f"{on}{spans[0][0]}:00Z", end=f"{on}{spans[-1][1]}:00Z", runs=4 * len(spans), failed=failed, pushes=len(spans),
                                spans=[[f"{on}{a}:00Z", f"{on}{b}:00Z", bad] for a, b, bad in spans]))
    c["prs"] += [pr(901, first["day"], "code", at, "18:00", "19:00", [("18:01", "18:05", 1), ("18:30", "18:35", 0)], failed=1),
                 pr(902, first["day"], "spec", at, "18:10", "18:20", [("18:11", "18:15", 0)]),
                 pr(903, None, "other", before, "09:00", "09:30", [("09:01", "09:04", 0)])]
    data["actogram"] = views.actogram(data)
    return data


class ActogramPageTest(unittest.TestCase):
    """actDraw(): a row for each date, its marks, its figures, the Day buttons, and graph 10 opened at a row's date."""

    def test_a_row_has_five_lanes_and_a_mark_for_each_stretch_the_actogram_counted(self):
        data = act_lanes_data()
        A, out = data["actogram"], node(ACT_DRAW, data)
        D, n = A["dates"], out["n"]
        self.assertEqual((out["drew"], out["error"], out["rows"]), (True, None, len(D)))
        self.assertEqual(out["box"], f"0 0 1232 {30 + 58 * len(D) + 6}")
        self.assertEqual(out["lanes"], ["main session", "sub-agents", "pull request", "checks", "merge"])
        self.assertEqual((n["act-t-ln"], n["act-trk"], n["act-mini"], n["act-mini-w"], n["act-sep"]), (5 * len(D), len(D), len(D), len(D), len(D) - 1))
        # lanes 0 and 1: a bar for each stretch the main session was busy and each the sub-agents were, a strip on a
        # date with two main sessions at once, and the waits of a lane as one path
        self.assertEqual(n["act-s"], sum(sum(1 for s in d["segs"] if s[2] == "main") + len(d["subs"]) for d in D))
        self.assertEqual(n["act-two"], sum(1 for d in D if d["two"]))
        self.assertEqual(n["act-w"], sum(len({w[3] for w in d["wait_segs"]}) for d in D))
        self.assertEqual(out["waits"], sum(len(d["wait_segs"]) for d in D))
        # lanes 2 to 4: every pull request open, the ones opened while another is open at half height; its checks,
        # passed or with a failed run; the merges
        self.assertEqual((n["act-p"], n["act-p2"]), (sum(len(d["prs"]) for d in D), sum(1 for d in D for p in d["prs"] if p["half"])))
        self.assertEqual((n["act-ok"], n["act-failed"]), (sum(1 for d in D for c in d["checks"] if not c[2]), sum(1 for d in D for c in d["checks"] if c[2])))
        self.assertEqual(n["act-m"], sum(len(d["merges"]) for d in D))
        # and the data has each of them
        self.assertEqual((n["act-two"], n["act-w"], out["waits"]), (1, 2, 2))
        for cls in ("act-p2", "act-failed", "act-ok", "act-m"):
            self.assertGreaterEqual(n[cls], 1, cls)
        # the last date is counted to 18:00: hatched from there, with the dashed mark and its words
        self.assertEqual((out["hatched"], n["act-cnt"], n["act-t-cnt"]), (1, 1, 1))
        # nothing of the old strip is drawn
        self.assertEqual(n["act-ml"], 0)
        self.assertEqual(out["head"], ["Date", "Days", "A session busy", "Main session", "Sub-agents", "Two main at once", "Waiting on commands", "Share",
                                       "Pull requests open", "Checks running", "Merged", "Median wait"])
        self.assertEqual(out["table"], len(D) + 1)
        for w in ("Two main sessions were busy at once for 20 min", "One wait is drawn twice."):
            self.assertIn(w, out["words"])

    def test_a_row_says_its_date_with_its_weekday_and_its_days_or_that_it_is_outside_any_day(self):
        data = act_lanes_data()
        A, out = data["actogram"], node(ACT_DRAW, data)
        self.assertEqual(out["said"][:2], [["Tue 29 Sep", "outside any Day"], ["Thu 1 Oct", "Day 1"]])
        self.assertEqual([s[0] for s in out["said"]], [f"{d['weekday']} {d['label']}" for d in A["dates"]])
        self.assertNotIn("no Day", " ".join(s[1] for s in out["said"]))

    def test_the_pointer_box_says_a_rows_date_and_a_marks_own(self):
        data = act_lanes_data()
        data["tip_row"] = 1
        row, pr, check, merge = node(ACT_DRAW, data)["tips"]
        self.assertEqual(row[0], "Thu 1 Oct · Day 1")
        self.assertIn("Sub-agents busy 1 h 25 min; two main sessions at once 20 min.", row)
        self.assertIn("3 pull requests open; checks running 17 min.", row)
        self.assertEqual(pr[0], "Pull request #101 · spec")
        self.assertEqual(pr, ["Pull request #101 · spec", "Open 11:47 to 12:42, 55 min before it merged."])
        self.assertEqual(check, ["Checks on pull request #901", "20:01 to 20:05: a run failed."])
        self.assertEqual(merge, ["Merged #101 at 12:42", "55 min after it opened."])

    def test_the_example_page_draws_a_mark_in_each_of_the_five_lanes(self):
        data = demo_data()
        data["actogram"] = A = views.actogram(data)
        n = node(ACT_DRAW, data)["n"]
        main, subs = sum(1 for d in A["dates"] for s in d["segs"] if s[2] == "main"), sum(len(d["subs"]) for d in A["dates"])
        self.assertGreaterEqual(main, 1)
        self.assertGreaterEqual(subs, 1)
        self.assertEqual(n["act-s"], main + subs)
        for cls in ("act-p", "act-ok", "act-failed", "act-m"):
            self.assertGreaterEqual(n[cls], 1, cls)

    def test_the_key_names_what_each_lane_draws_and_nothing_is_left_of_the_old_strip(self):
        html = read("index.html")
        section = html[html.index('<section class="graph" id="act">'):html.index('<div class="mock-fold" id="g10-fold">')]
        key = section[section.index('<div class="act-key">'):section.index('<div class="act-scroll"')]
        self.assertIn('<span class="act-lead">In each row, top to bottom:</span>', key)
        for cls in ("act-s", "act-w", "act-two", "act-k-spec", "act-k-code", "act-k-close", "act-k-other", "act-ok", "act-failed", "act-m", "act-unc", "act-cnt"):
            self.assertRegex(key, rf'class="{cls}"')
        self.assertEqual(key.count('<i class="act-sep" aria-hidden="true"></i>'), 3)
        self.assertIn("a half-height bar", section)
        for name in ("index.html", "dashboard.css", "dashboard.js"):
            self.assertNotIn("act-ml", read(name), name)

    def test_a_row_for_each_date_and_a_mark_for_each_merge_and_wait(self):
        data = act_data()
        data["dim_day"] = 3
        A, out = data["actogram"], node(ACT_DRAW, data)
        self.assertEqual((out["drew"], out["error"]), (True, None))
        self.assertEqual(out["rows"], len(A["dates"]))
        self.assertEqual(out["merges"], sum(len(d["merges"]) for d in A["dates"]))
        self.assertEqual(out["waits"], sum(len(d["wait_segs"]) for d in A["dates"]))
        self.assertEqual(out["waits"], 1)
        # the last date is counted up to 18:00 on the clock: hatched from there to its end
        self.assertEqual(out["hatched"], sum(1 for d in A["dates"] if d["up_to"] < 1440))
        self.assertEqual(out["hatched"], 1)
        self.assertEqual(out["table"], len(A["dates"]) + 1)
        for w in ("dates with a session", "with a session busy", "of it waiting on commands", "median wait, opened to merged",
                  "A gap is not a rest.", "A date runs 05:00 to 05:00.", "Two waits at once count twice."):
            self.assertIn(w, out["words"])
        # every date counted whole ran past midnight, or not: "all N" only when the two counts are equal
        T = A["totals"]
        said = f"on all {T['whole']} dates counted whole" if T["after_midnight"] == T["whole"] else f"on {T['after_midnight']} of the {T['whole']} dates counted whole"
        self.assertIn(said, out["words"])
        self.assertNotRegex(out["words"], r"on (\d+) of the \1 ")

    def test_the_day_buttons_dim_the_other_dates_and_a_row_opens_graph_10_at_its_date(self):
        data = act_data()
        data["dim_day"] = 3
        A, out = data["actogram"], node(ACT_DRAW, data)
        self.assertEqual(out["onDay"], 1)
        self.assertEqual(out["dimmed"], sum(1 for d in A["dates"] if 3 not in d["days"]))
        self.assertGreater(out["dimmed"], 0)
        self.assertEqual(out["opened"], [[A["dates"][0]["date"]], True])

    def test_without_sessions_json_nothing_is_drawn_and_the_page_says_not_measured_yet(self):
        for source in (dict(absent=["sessions.json"]), dict(commit=None)):
            out = node(ACT_DRAW, act_data(**source))
            self.assertEqual((out["drew"], out["rows"]), (False, 0))
            self.assertEqual((sum(out["n"].values()), out["box"]), (0, None))
            self.assertRegex(out["empty"], r"^the dashboard-data branch (has no sessions\.json|is missing), so no session is drawn\.$")
        loop = read("dashboard.js")
        loop = loop[loop.index('["rng", rngDraw], ["act", actDraw]]'):]
        self.assertIn('"Not measured yet: ", rich(g.empty)', loop[:loop.index("});")])


# lrnDraw() on the model of the data from stdin, on a document that keeps every node: how many marks of each kind it
# drew, the words of its figures, and which marks a Day's button dims.
LRN = r"""
const fs = require("fs"), vm = require("vm"), els = {};
const node = tag => { const n = { tag, attrs: {}, kids: [], style: {}, hidden: false, textContent: "",
  classList: { toggle(c, on) { const k = new Set((n.attrs.class || "").split(" ").filter(Boolean)); if (on) k.add(c); else k.delete(c); n.attrs.class = [...k].join(" "); } },
  setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k]; }, appendChild(c) { this.kids.push(c); return c; },
  append(...c) { this.kids.push(...c); }, replaceChildren(...c) { if (c.some(Array.isArray)) throw new Error("replaceChildren() given an array: a browser writes it as text"); this.kids = c; }, addEventListener() {} };
  Object.defineProperty(n, "className", { set(v) { n.attrs.class = v; }, get() { return n.attrs.class || ""; } });
  return n; };
const document = { createElementNS: (ns, tag) => node(tag), createElement: node };
const $ = id => els[id] || (els[id] = node(id));
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")), document, $ });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const all = n => [n, ...(n.kids || []).filter(k => k && typeof k === "object").flatMap(all)];
  const has = (e, c) => ((e.attrs && e.attrs.class) || "").split(" ").includes(c);
  const is = (root, c) => all(root).filter(e => has(e, c)).length;
  const keys = (root, re) => all(root).filter(e => e.attrs && re.test(e.attrs["data-k"] || "")).map(e => e.attrs["data-k"]);
  const words = n => typeof n === "string" ? n : [n.textContent, ...(n.kids || []).map(words)].join(" ");
  const days = [], e = $("lrn-epi"), d = $("lrn-dmb");
  lrnDraw(model(DATA).lrn, $, days);
  days.forEach(f => f(8));
  ({ bars: keys(e, /^d/), lines: keys(e, /^f/), rows: keys(d, /^p/), before: is(e, "l-before"), past: is(e, "l-past"), hatch: is(e, "l-pasth"),
     held: is(d, "l-dot-held"), less: is(d, "l-dot-less"), back: is(d, "l-dot-back"), early: is(d, "l-dot-early"), dim: [...all(e), ...all(d)].filter(x => has(x, "mk-dim")).map(x => x.attrs["data-k"]),
     figs: words($("lrn-figs")).replace(/\\s+/g, " ").trim(), table: $("lrn-fixes").kids[1].kids.length })`, ctx)));
"""


class LearnPageTest(unittest.TestCase):
    def setUp(self):
        if not shutil.which("node"):
            self.skipTest("needs node")

    def test_does_it_learn_draws_a_bar_per_day_a_line_per_fix_day_and_a_row_per_fix_red_never_alone(self):
        def fix(pr, day, before, after, verdict=None):
            return dict(pr=pr, title=f"fix {pr}", merged="2026-11-10T08:00:00Z", from_day=day, stops=["D07.1"], before=before,
                        after=after, after_ids=[f"D08.{i}" for i in range(after)], days_since=2, first_day=7,
                        days_before=1 if day else 0, rate_before=before if day else None,
                        rate_after=round(after / 2, 2) if day else None, gated=[], leaked=[f"D08.{i}" for i in range(after)],
                        verdict=verdict)
        learning = dict(head="abc1234", last_pr=9, generated="2026-11-24", repeats=5, past_fix=2, held=1, problems=[],
                        days=[dict(day=7, n=2, before=["D07.2", "D07.3"], past_fix=[], fixes=[]),
                              dict(day=8, n=3, before=["D08.1"], past_fix=["D08.2", "D08.3"], fixes=[112]),
                              dict(day=9, n=0, before=[], past_fix=[], fixes=[133])],
                        fixes=[fix(112, 8, 4, 2, "reduced"), fix(133, 9, 1, 0, "gone"), fix(150, None, 1, 0)])
        out = node(LRN, data(learning=learning))
        self.assertEqual(out["bars"], ["d7", "d8", "d9"])
        self.assertEqual(out["lines"], ["f8", "f9"])
        self.assertEqual(out["rows"], ["p112", "p133", "p150"])
        # a grey segment for each Day with a repeat before a fix; each red segment carries its hatch
        self.assertEqual((out["before"], out["past"], out["hatch"]), (2, 1, 1))
        # a fix in force gets a dot after it, ticked when gone (133), arrowed when reduced (112), crossed when not; one
        # that counts from no Day yet gets none: three fixes, two after dots
        self.assertEqual((out["held"], out["less"], out["back"], out["early"]), (1, 1, 0, 0))
        # Day 8's button dims every mark of another Day: the bars, the fix lines and the fixes' rows
        self.assertEqual(sorted(out["dim"]), ["d7", "d9", "f9", "p133", "p150"])
        self.assertIn("5 times an old problem came back", out["figs"])
        self.assertIn("2 of them although a fix was in place", out["figs"])
        self.assertIn("2 fixes old enough to judge", out["figs"])
        self.assertIn("1 gone, 1 reduced, 0 not reduced", out["figs"])
        self.assertEqual(out["table"], 3)

    def test_does_it_learn_without_a_merged_day_says_so_under_not_measured(self):
        self.assertIn("empty", model(data(learning=dict(days=[], fixes=[])))["lrn"])
        self.assertIn("empty", model(data())["lrn"])


def one_day_key():
    """Graph 7's One Day as spec_drift_views.one_day() writes it: Day 6 with one spec change and nothing else, and Day 7
    still open, its close not started, with a defect at each kind of place and a promise no step names."""
    def step(key, name, kind, prs=(), date=None, title="", subs=()):
        return dict(key=key, name=name, kind=kind, prs=list(prs), date=date, title=title, subs=list(subs))

    def defect(n, at, sub=None, by="at", found="auditor", cause="spec", same=None):
        return dict(id=f"D07.{n}", found=found, cause=cause, same=same, text=f"problem `{n}`", step=at, sub=sub, by=by)

    def criterion(n, at, state, tag):
        return dict(id=f"C07.{n}", day=7, tag=tag, state=state, back=False, gone=False, quote=f"claim {n}", step=at)

    def agent(key, name, does, covers, replies, cost):
        return dict(agent=key, name=name, does=does, replies=replies, cost=cost, covers=covers)

    def totals(**t):
        return dict(dict(prs=0, new=0, hold=0, ticked=0, cost=0, replies=0, defects=0, placed=0, no_step=0, after=0), **t)

    six = dict(day=6, title="Day 6: `thing`", status="done", steps=[step("spec", "Spec change", "spec", [3], "2026-11-01", "Day 06 spec change")],
               defects=[], criteria=[], agents=[], totals=totals(prs=1))
    seven = dict(
        day=7, title="Day 7: `thing`", status="active",
        steps=[step("audit", "Audit", "audit", subs=["audit", "recheck"]),
               step("spec", "Spec change", "spec", [5], "2026-11-02", "Day 07 spec change: `x`", ["pr"]),
               step("A", "Track A", "code", [6], "2026-11-03", "Day 07 track A: it runs", ["brief", "build", "diff", "pr"]),
               step("close", "Close", "close", subs=["rehearsal", "pr", "replay"])],
        defects=[defect(1, "audit", "audit"), defect(2, "audit", "audit", same="D03.4"), defect(3, "audit", by="found"),
                 defect(4, "A", "diff", found="track-reviewer", cause="implementation"),
                 defect(5, None, by="found", found="self", cause="process"), defect(6, "after", by="found", found="dashboard")],
        criteria=[criterion(1, "A", "proven", "new"), criterion(2, "A", "unproven", "hold"), criterion(3, None, "building", "new")],
        agents=[agent("main", "main session", "writes the specs and the briefs", [["*", "*"]], 40, 2.5),
                agent("track-reviewer", "track-reviewer", "reads each track's brief and diff", [["code", "brief"], ["code", "diff"]], 10, 0.5),
                agent("Explore", "Explore", "searches the code", [], 3, 0.1)],
        totals=totals(prs=2, new=2, hold=1, ticked=1, cost=3.1, replies=53, defects=6, placed=4, no_step=1, after=1))
    return dict(head="abc1234", last_pr=9, generated="2026-11-26", from_day=7, problems=[], no_step=dict(lines=0, of=0, ids=[]),
                days=[six, seven])


# prfViews() and oneDraw() on the model of the data from stdin, on a document that keeps every node and each node's
# listeners: what Day 7's rings and strand drew, then Day 6's after its page button, then what the two switches show.
ONE = r"""
const fs = require("fs"), vm = require("vm"), els = {};
const node = tag => { const n = { tag, attrs: {}, kids: [], style: {}, hidden: false, textContent: "", on: {},
  classList: { toggle(c, on) { const k = new Set((n.attrs.class || "").split(" ").filter(Boolean)); if (on) k.add(c); else k.delete(c); n.attrs.class = [...k].join(" "); } },
  setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k]; }, appendChild(c) { this.kids.push(c); return c; },
  append(...c) { this.kids.push(...c); }, replaceChildren(...c) { if (c.some(Array.isArray)) throw new Error("replaceChildren() given an array: a browser writes it as text"); this.kids = c; },
  addEventListener(type, fn) { this.on[type] = fn; }, focus() {} };
  Object.defineProperty(n, "className", { set(v) { n.attrs.class = v; }, get() { return n.attrs.class || ""; } });
  return n; };
const document = { createElementNS: (ns, tag) => node(tag), createElement: node };
const $ = id => els[id] || (els[id] = node(id));
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")), document, $ });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `;(() => {
  const all = n => [n, ...(n.kids || []).filter(k => k && typeof k === "object").flatMap(all)];
  const has = (e, c) => ((e.attrs && e.attrs.class) || "").split(" ").includes(c);
  const is = (root, c) => all(root).filter(e => has(e, c)).length;
  const words = n => typeof n === "string" ? n : [n.textContent, ...(n.kids || []).map(words)].join(" ").replace(/\\s+/g, " ").trim();
  const marks = (id, band) => ({ st: is($(id), "st"), df: is($(id), "df"), pip: is($(id), "pip"), ct: is($(id), "ct"), band: is($(id), band) });
  const days = [];
  oneDraw(model(DATA).one, $, days);
  prfViews($);
  const seven = { ring: marks("one-rfig", "arcband"), strand: marks("one-fig", "band"), who: $("one-who").kids.filter(k => k.tag === "tr").length,
    figs: words($("one-figs")), out: words($("one-out")), pick: $("one-pick").value };
  days.forEach(f => f(6));
  const six = { ring: marks("one-rfig", "arcband"), pick: $("one-pick").value };
  $("prf-v-one").on.click();
  const views = { all: $("prf-all").hidden, one: $("one").hidden };
  $("one-v-strand").on.click();
  return { seven, six, views, ring: $("one-ring").hidden, strand: $("one-strand").hidden }; })()`, ctx)));
"""

# oneLayout(), oneCovers() and onePack() on Day 7 of the model of the data from stdin.
ONE_LAYOUT = r"""
const fs = require("fs"), vm = require("vm");
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")) });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `;(() => {
  const day = model(DATA).one.days.find(d => d.day === 7), sum = a => a.reduce((x, y) => x + y, 0);
  const at = k => day.steps.find(s => s.key === k), agent = k => day.agents.find(a => a.agent === k);
  const more = Object.assign({}, day, { defects: day.defects.concat(Array.from({ length: 60 }, (_, i) => ({ id: "X" + i, step: "audit", sub: "audit" }))) });
  const lay = oneLayout(day), wide = oneLayout(more);
  return { total: sum(lay.map(x => x.share)).toFixed(6), subs: lay.map(x => sum(x.subs).toFixed(6)), wider: wide[0].share > lay[0].share,
     track: oneCovers(agent("track-reviewer"), at("A")), audit: oneCovers(agent("track-reviewer"), at("audit")),
     build: oneCovers(agent("track-reviewer"), { kind: "code", subs: [{ key: "build" }] }), none: oneCovers(agent("main"), at("none")),
     rows: onePack(5, 30, 12).map(p => p.row) }; })()`, ctx)));
"""


class OneDayPageTest(unittest.TestCase):
    def setUp(self):
        if not shutil.which("node"):
            self.skipTest("needs node")

    def drawn(self, harness, data):
        """node on the harness; a script that throws fails the test with its error's line, not a path or the harness."""
        run = subprocess.run(["node", "-e", harness, SCRIPT], input=json.dumps(data), capture_output=True, encoding="utf-8")
        self.assertEqual((run.returncode, re.findall(r"(?m)^\w*Error: .*$", run.stderr)[:1]), (0, []))
        return json.loads(run.stdout)

    def test_one_day_reads_each_step_defect_and_promise_out_in_words(self):
        one = model(data(one_day=one_day_key(), criteria_index=[promise("C07.1", replaces=["C03.2"])]))["one"]
        # the data's current Day, 3, is not a Day of the key, so the newest is picked
        self.assertEqual(one["pick"], 7)
        self.assertEqual([d["day"] for d in one["days"]], [6, 7])
        day = one["days"][1]
        steps = {s["key"]: s for s in day["steps"]}
        self.assertEqual([s["key"] for s in day["steps"]], ["audit", "spec", "A", "close", "none", "after"])
        self.assertEqual(steps["A"]["head"], "Track A · #6 · 3 Nov")
        self.assertEqual(steps["A"]["lines"], ["Day 07 track A: it runs", "1 defect caught here: 1 at the diff.",
                                               "2 promises of the spec built here, 1 proved: C07.1, C07.2."])
        self.assertEqual(steps["audit"]["lines"][1:], ["3 defects caught here: 2 at the audit.", "1 of them repeats an earlier defect."])
        self.assertEqual(steps["close"]["note"], "not started")
        defects = {f["id"]: f for f in day["defects"]}
        self.assertEqual([defects[i]["head"] for i in ("D07.4", "D07.1", "D07.5", "D07.6")],
                         ["D07.4 · caught at the diff of Track A · found by track-reviewer", "D07.1 · caught at the audit · found by auditor",
                          "D07.5 · step not recorded · found by self", "D07.6 · caught after the Day · found by dashboard"])
        self.assertEqual(defects["D07.3"]["lines"], ["Cause: spec", "Placed by who found it: its line names no step.", "problem 3"])
        criteria = {c["id"]: c for c in day["criteria"]}
        self.assertEqual(criteria["C07.1"]["head"], "C07.1 · new · holds, and a break on purpose proved its test")
        self.assertEqual(criteria["C07.1"]["lines"], ["It rewrites C03.2.", "claim 1"])
        self.assertEqual([(f["num"], f["what"], f["sub"]) for f in day["figs"]],
                         [("2", "pull requests merged", "1 spec change, 1 track; the close still to come"),
                          ("6", "defects caught", "3 by the audit, before any code; 1 at no recorded step; 1 after the Day"),
                          ("1", "promise proved", "of 3 in the spec: 2 new, 1 that already held"),
                          ("$3.10", "across 3 kinds of session", "API list prices, not a bill")])
        self.assertEqual(day["start"]["head"], "Day 7 · 2 Nov to 3 Nov · still open")

    def test_one_day_opens_on_the_current_day_and_a_closed_day_is_neither_open_nor_to_come(self):
        shut = one_day_key()
        shut["days"][1]["status"] = "closed"
        one = model(data(one_day=shut, now=dict(data()["now"], current_day=6)))["one"]
        self.assertEqual(one["pick"], 6)
        day = one["days"][1]
        self.assertEqual(day["start"]["head"], "Day 7 · 2 Nov to 3 Nov")
        self.assertEqual(day["figs"][0]["sub"], "1 spec change, 1 track; the close with no pull request")
        close = next(s for s in day["steps"] if s["key"] == "close")
        self.assertEqual((close["note"], close["lines"][0]), ("no pull request", "No pull request: the Day closed without one."))
        # an open Day's step with no pull request has its promises still to build; the arc of no step says what it holds
        key = one_day_key()
        key["days"][1]["criteria"][0]["step"] = "close"
        key["days"][1]["defects"] = [f for f in key["days"][1]["defects"] if f["step"] is not None]
        steps = {s["key"]: s for s in model(data(one_day=key))["one"]["days"][1]["steps"]}
        self.assertEqual(steps["close"]["lines"][-1], "1 promise of the spec to build here, 1 proved: C07.1.")
        self.assertEqual(steps["none"]["lines"][0], "No track and no pull request names these promises.")

    def test_one_day_draws_the_same_marks_as_rings_and_as_a_strand_and_turns_to_a_pressed_day(self):
        out = self.drawn(ONE, data(one_day=one_day_key()))
        # six steps (the four of the Day, an arc for no step and one for after the Day), six defects, one a repeat, and
        # three promises; main's band is one run over the four real steps, the track-reviewer's two (brief, diff), and
        # Explore, whose role belongs to no step, gets no lane
        self.assertEqual(out["seven"]["ring"], dict(st=6, df=6, pip=1, ct=3, band=3))
        self.assertEqual(out["seven"]["strand"], dict(st=6, df=6, pip=1, ct=3, band=3))
        self.assertEqual(out["seven"]["who"], 4)
        self.assertIn("6 defects caught 3 by the audit, before any code", out["seven"]["figs"])
        self.assertIn("Day 7 · 2 Nov to 3 Nov · still open", out["seven"]["out"])
        self.assertEqual(out["seven"]["pick"], "7")
        self.assertEqual(out["six"], dict(ring=dict(st=1, df=0, pip=0, ct=0, band=0), pick="6"))
        self.assertEqual((out["views"], out["ring"], out["strand"]), (dict(all=True, one=False), True, False))

    def test_one_day_shares_the_ring_by_what_each_step_holds_and_bands_an_agent_by_its_role(self):
        out = self.drawn(ONE_LAYOUT, data(one_day=one_day_key()))
        self.assertEqual(out["total"], "1.000000")
        self.assertEqual(out["subs"], ["1.000000"] * 6)
        self.assertTrue(out["wider"], "sixty more defects on the audit widen its arc")
        self.assertEqual((out["track"], out["audit"]), ([True, False, True, False], [False, False]))
        # the Day records neither the brief nor the diff of this track, so the track-reviewer's band takes all of it
        self.assertEqual((out["build"], out["none"]), ([True], [False]))
        self.assertEqual(out["rows"], [0, 0, 1, 1, 2])

    def test_one_day_without_the_key_says_so_under_not_measured(self):
        self.assertIn("empty", model(data())["one"])
        out = boot(data())
        self.assertIsNone(out["error"])
        self.assertEqual([e for e in out["logged"] if e.startswith("one:")], [])


def rewrites_key():
    """Graph 6's promises rewritten as spec_drift_views.rewrites() writes it, on the index of RewritesTest: C04.1's line
    of four wordings (C03.1 folded in), C06.1's from a short spec's two, C05.1's of two, and C06.2 on no line."""
    def crit(cid, day, state, replaces=(), replaced_by=()):
        return dict(id=cid, day=day, state=state, plain=f"{cid} in plain words.", claim="", replaces=list(replaces),
                    replaced_by=list(replaced_by))

    index = [crit("C01.1", 1, "replaced", replaced_by=["C02.1"]), crit("C02.1", 2, "replaced", ["C01.1"], ["C04.1"]),
             crit("C03.1", 3, "replaced", replaced_by=["C04.1"]), crit("C04.1", 4, "proven", ["C03.1", "C02.1"]),
             crit("C03.2", 3, "replaced", replaced_by=["C05.1"]), crit("C05.1", 5, "unproven", ["C03.2"]),
             crit("C06.1", 6, "building", ["S-pick-a-day.1", "S-pick-a-day.2"]), crit("C06.2", 6, "proven")]
    return views.rewrites(dict(now=dict(head="abcdef1234", last_pr=9, generated="2026-11-26"), criteria_index=index,
                               days=[dict(day=n, phase=p) for n, p in zip(range(1, 7), [0, 0, 1, 1, 1, 2])]))


def flat(s):
    """A page's words with its two non-ASCII marks spelt in ASCII, so that a failure reads the same on every machine."""
    return s.replace("·", "|").replace("→", "->")


# The document of ONE, each node keeping one listener per event; then, after `body`, what the body returns.
REW_DOC = r"""
const fs = require("fs"), vm = require("vm"), els = {};
const node = tag => { const n = { tag, attrs: {}, kids: [], style: {}, hidden: false, textContent: "", on: {},
  classList: { toggle(c, on) { const k = new Set((n.attrs.class || "").split(" ").filter(Boolean)); if (on) k.add(c); else k.delete(c); n.attrs.class = [...k].join(" "); } },
  setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k]; }, appendChild(c) { this.kids.push(c); return c; },
  append(...c) { this.kids.push(...c); }, replaceChildren(...c) { if (c.some(Array.isArray)) throw new Error("replaceChildren() given an array: a browser writes it as text"); this.kids = c; },
  addEventListener(type, fn) { this.on[type] = fn; }, focus() { if (this.on.focus) this.on.focus(); }, getBoundingClientRect() { return { width: 0, height: 0 }; } };
  Object.defineProperty(n, "className", { set(v) { n.attrs.class = v; }, get() { return n.attrs.class || ""; } });
  return n; };
const document = { createElementNS: (ns, tag) => node(tag), createElement: node, addEventListener() {} };
const $ = id => els[id] || (els[id] = node(id));
// a page address and a window, handed to the script only where a harness puts MORE in their place
const winOn = {}, location = { hash: "" }, window = { addEventListener(t, fn) { winOn[t] = fn; } };
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")), document, $ /*MORE*/ });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `;(() => {
  const all = n => [n, ...(n.kids || []).filter(k => k && typeof k === "object").flatMap(all)];
  const has = (e, c) => ((e.attrs && e.attrs.class) || "").split(" ").includes(c);
  const words = n => typeof n === "string" ? n : [n.textContent, ...(n.kids || []).map(words)].join(" ").replace(/\\s+/g, " ").trim();
  const said = () => ($("rew-out").kids[0] || {}).textContent || "";
  const label = e => (e.attrs["aria-label"] || "").split(" ")[0];
  const buttons = () => ["mrg-v-day", "mrg-v-merge", "mrg-v-rew"].map(id => id.slice(6) + ":" + $(id).attrs["aria-pressed"] + (($(id).disabled) ? ":off" : ""));
  const shown = () => ["mrg-all", "rew", "mrg-zoom-wrap", "mrg-frame-h", "rew-frame-h", "mrg-say"].filter(id => !$(id).hidden);
  BODY })()`, ctx)));
"""

# rewDraw() on the model's rewrites: the ring's arcs, marks and chords, what pointing reads out, and a pressed Day.
REW = REW_DOC.replace("BODY", r"""
  const R = model(DATA).rew, days = [];
  mrgViews($);
  rewDraw(R, $, days);
  const made = all($("rew-rfig")), marks = made.filter(e => has(e, "nd")), arcs = made.filter(e => has(e, "dayarc"));
  const chords = made.filter(e => has(e, "chord"));
  const out = { arcs: arcs.length, marks: marks.length, squares: marks.filter(e => e.tag === "rect").length, chords: chords.length,
    most: made.filter(e => e.tag === "g" && has(e, "lin") && has(e, "most")).length, start: said(),
    figs: words($("rew-figs")), note: $("rew-note").textContent, stamp: $("rew-stamp").textContent.startsWith("Drawn from the page's data at abcdef1") };
  out.stops = made.filter(e => e.attrs.tabindex === "0").map(label).sort();
  out.nan = made.filter(e => Object.values(e.attrs).some(v => /NaN|undefined/.test(v))).length;
  const cls = e => label(e) + "=" + e.attrs.class;
  out.sinks = marks.filter(e => !has(e, "old")).map(cls).sort();
  out.old = marks.filter(e => e.attrs.class === "nd old").map(label).sort();
  const top = made.filter(e => e.tag === "g" && has(e, "lin"));
  out.first_most = top.length ? has(top[0], "most") : null;
  out.most_marks = top.filter(g => has(g, "most")).flatMap(g => all(g).filter(e => has(e, "nd")).map(label)).sort();
  out.short_label = made.filter(e => e.tag === "text" && e.textContent === "short spec").length;
  const by = id => marks.find(e => label(e) === id), fire = (e, t, ev) => { if (e && e.on[t]) e.on[t](ev); };
  fire(by("C01.1"), "mouseenter");
  fire(by("C01.1"), "keydown", { key: "ArrowRight", preventDefault() {} });
  out.step = said();
  fire(by("C01.1"), "mouseenter");
  fire(by("C02.1"), "focus");
  out.focus = said();
  fire(by("C01.1"), "mouseenter");
  fire(by("C02.1"), "click");
  out.click = said();
  marks.find(e => label(e) === "C02.1").on.mouseenter();
  out.mark = said();
  made.find(e => has(e, "hit") && label(e) === "C04.1").on.mouseenter();
  out.chord = said();
  days.forEach(f => f(3));
  out.clear = marks.filter(e => !has(e, "mk-dim")).map(label).sort();
  out.clear_arcs = arcs.filter(e => !has(e, "mk-dim")).length;
  out.clear_chords = chords.filter(e => !has(e, "mk-dim")).length;
  days.forEach(f => f(null));
  out.dimmed = made.filter(e => has(e, "mk-dim")).length;
  return out;""")

# mrgViews() alone, as where the merge graph cannot be drawn: the rewrites pressed, then the merges.
REW_SWITCH = REW_DOC.replace("BODY", r"""
  mrgViews($);
  $("mrg-v-rew").on.click();
  const rew = { shown: shown(), buttons: buttons() };
  $("mrg-v-merge").on.click();
  return { rew, merge: { shown: shown(), buttons: buttons() } };""")

# mrgViews() then mergeDraw() on the example data: the rewrites pressed, a Day pressed under them, the rows pressed back
# while that Day is zoomed, then the page's "All Days".
REW_MERGE = REW_DOC.replace("BODY", r"""
  const days = [], M = model(DATA);
  mrgViews($);
  mergeDraw(M.mrg, $, days);
  $("mrg-v-rew").on.click();
  days.forEach(f => f(M.mrg.days[0].day));
  const zoomed = { shown: shown(), buttons: buttons() };
  $("mrg-v-day").on.click();
  const back = { shown: shown(), buttons: buttons() };
  days.forEach(f => f(null));
  return { zoomed, back, out: { shown: shown(), buttons: buttons() } };""")

# The other order: a Day zoomed on the rows first, then the rewrites pressed.
REW_ZOOM_FIRST = REW_DOC.replace("BODY", r"""
  const days = [], M = model(DATA);
  mrgViews($);
  mergeDraw(M.mrg, $, days);
  days.forEach(f => f(M.mrg.days[0].day));
  const zoomed = buttons();
  $("mrg-v-rew").on.click();
  return { zoomed, rew: buttons() };""")

# Under the rewrites with a Day zoomed, "One row per merge" pressed, then the page's "All Days": the rows that were
# pressed before the zoom come back.
REW_MERGE_BACK = REW_DOC.replace("BODY", r"""
  const days = [], M = model(DATA);
  mrgViews($);
  mergeDraw(M.mrg, $, days);
  $("mrg-v-rew").on.click();
  days.forEach(f => f(M.mrg.days[0].day));
  $("mrg-v-merge").on.click();
  days.forEach(f => f(null));
  return buttons();""")

# A link to the merges (#mrg-merges) followed while the rewrites show: the page's hashchange brings the rows back.
REW_HASH = REW_DOC.replace("/*MORE*/", ", location, window, winOn").replace("BODY", r"""
  const days = [], M = model(DATA);
  mrgViews($);
  mergeDraw(M.mrg, $, days);
  $("mrg-v-rew").on.click();
  const before = shown();
  location.hash = "#mrg-merges";
  if (winOn.hashchange) winOn.hashchange();
  return { before, shown: shown(), buttons: buttons() };""")


class RewritesPageTest(unittest.TestCase):
    def setUp(self):
        if not shutil.which("node"):
            self.skipTest("needs node")

    def drawn(self, harness, data):
        """node on the harness; a script that throws fails the test with its error's line, not a path or the harness."""
        run = subprocess.run(["node", "-e", harness, SCRIPT], input=json.dumps(data), capture_output=True, encoding="utf-8")
        self.assertEqual((run.returncode, re.findall(r"(?m)^\w*Error: .*$", run.stderr)[:1]), (0, []))
        return json.loads(run.stdout)

    def test_promises_rewritten_word_each_line_and_wording(self):
        m = model(data(rewrites=rewrites_key()))
        self.assertTrue("rew" in m, "the model has no rew key")
        rew = m["rew"]
        self.assertNotIn("error", rew)
        self.assertEqual([(f["num"], f["what"], f["sub"]) for f in rew.get("figs", [])],
                         [("6", "promises replaced", "each by a later Day's wording"),
                          ("3", "promises in force that replaced them", "1 proved, 1 never seen to fail, 1 not built yet"),
                          ("1", "rewritten more than once", "the other 2 changed once"),
                          ("2", "rewrites on the longest line", "it ends at C04.1")])
        self.assertEqual((rew["start"]["head"], rew["start"]["say"]),
                         ("6 promises replaced, on 3 lines", ["The longest line ends at C04.1: 4 wordings, rewritten 2 times.",
                                                              "Point at a line for its history, or at a mark for that wording."]))
        lines = {x["sink"]: x for x in rew["lines"]}
        self.assertEqual(sorted(lines), ["C04.1", "C05.1", "C06.1"])
        top = lines["C04.1"]
        self.assertEqual(flat(top["head"]), "C04.1 | in force since Day 4 | rewritten 2 times")
        self.assertEqual([flat(s) for s in top["say"]],
                         ["Its line: C01.1 (Day 1) -> C02.1 (Day 2) -> C04.1 (Day 4). Folded in on the way: C03.1.",
                          "Today: holds, and a break on purpose proved its test.", "C04.1 in plain words."])
        self.assertEqual(flat(lines["C05.1"]["head"]), "C05.1 | in force since Day 5 | rewritten 1 time")
        nodes = {n["id"]: n for x in rew["lines"] for n in x["nodes"]}
        self.assertEqual((flat(nodes["C02.1"]["head"]), nodes["C02.1"]["say"]),
                         ("C02.1 | written on Day 2", ["Replaced by C04.1 on Day 4.", "C02.1 in plain words."]))
        self.assertEqual(nodes["C04.1"]["say"][0], "In force today: holds, and a break on purpose proved its test.")
        short = nodes["S-pick-a-day.1"]
        self.assertEqual((flat(short["head"]), short["say"][0]),
                         ("S.1 | written between Days 5 and 6, in a short spec", "Replaced by C06.1 on Day 6."))
        self.assertEqual(rew["note"], "A Day's arc is as long as the wordings it holds. Day 3 holds the most: 2.")

    def test_promises_rewritten_draw_an_arc_per_day_held_a_mark_per_wording_and_a_chord_per_edge(self):
        out = self.drawn(REW, data(rewrites=rewrites_key()))
        # Days 1 to 6 each hold a wording, and the short spec's two stand on an arc of their own between Days 5 and 6
        self.assertEqual((out["arcs"], out["marks"], out["squares"], out["chords"], out["most"]), (7, 9, 2, 6, 1))
        self.assertEqual(out["start"], "6 promises replaced, on 3 lines")
        self.assertIn("6 promises replaced each by a later Day's wording", out["figs"])
        self.assertEqual(out["note"], "A Day's arc is as long as the wordings it holds. Day 3 holds the most: 2.")
        self.assertTrue(out["stamp"], "the stamp names the data's head")
        self.assertEqual(out["nan"], 0)
        self.assertEqual(len(out["sinks"]), 3)
        self.assertEqual(out["sinks"], ["C04.1=nd proven", "C05.1=nd unproven", "C06.1=nd building"])
        self.assertEqual(out["old"], ["C01.1", "C02.1", "C03.1", "C03.2", "S.1", "S.2"])
        # the dark line is the first line's, C04.1's, the most rewritten
        self.assertEqual(out["first_most"], True)
        self.assertEqual(out["most_marks"], ["C01.1", "C02.1", "C03.1", "C04.1"])
        self.assertEqual(out["short_label"], 1)

    def test_promises_rewritten_read_out_a_mark_and_a_line(self):
        out = self.drawn(REW, data(rewrites=rewrites_key()))
        self.assertEqual(flat(out["mark"]), "C02.1 | written on Day 2")
        self.assertEqual(flat(out["chord"]), "C04.1 | in force since Day 4 | rewritten 2 times")
        self.assertEqual((flat(out["focus"]), flat(out["click"])), ("C02.1 | written on Day 2", "C02.1 | written on Day 2"))

    def test_promises_rewritten_take_one_tab_stop_a_line_and_walk_its_marks_with_the_arrows(self):
        out = self.drawn(REW, data(rewrites=rewrites_key()))
        self.assertEqual(out["stops"], ["C04.1", "C05.1", "C06.1"])
        # from C01.1 the right arrow goes to C02.1, the next wording of C04.1's line
        self.assertEqual(flat(out["step"]), "C02.1 | written on Day 2")

    def test_promises_rewritten_word_one_of_each_in_the_singular(self):
        one = [dict(id="C01.1", day=1, state="replaced", plain="C01.1 in plain words.", claim="", replaces=[], replaced_by=["C02.1"]),
               dict(id="C02.1", day=2, state="proven", plain="C02.1 in plain words.", claim="", replaces=["C01.1"], replaced_by=[])]
        key = views.rewrites(dict(now=dict(head="abcdef1234", last_pr=9, generated="2026-11-26"), criteria_index=one,
                                  days=[dict(day=1, phase=0), dict(day=2, phase=0)]))
        m = model(data(rewrites=key))
        self.assertTrue("rew" in m, "the model has no rew key")
        rew = m["rew"]
        self.assertNotIn("error", rew)
        self.assertEqual(rew["start"]["head"], "1 promise replaced, on 1 line")
        self.assertEqual(rew["start"]["say"][0], "The longest line ends at C02.1: 2 wordings, rewritten 1 time.")
        self.assertEqual(len(rew["figs"]), 4)
        self.assertEqual(rew["figs"][0]["what"], "promise replaced")
        self.assertEqual(rew["figs"][2]["sub"], "it changed once")

    def test_promises_rewritten_dim_every_other_day_when_a_day_is_pressed(self):
        out = self.drawn(REW, data(rewrites=rewrites_key()))
        # Day 3: its two wordings clear, its one arc, and the two chords with an end on it
        self.assertEqual((out["clear"], out["clear_arcs"], out["clear_chords"]), (["C03.1", "C03.2"], 1, 2))
        self.assertEqual(out["dimmed"], 0)

    def test_the_switch_turns_graph_6_to_the_rewrites_and_back_without_the_merge_graph(self):
        out = self.drawn(REW_SWITCH, data())
        self.assertEqual(out["rew"]["shown"], ["rew", "rew-frame-h"])
        self.assertEqual(out["rew"]["buttons"], ["day:false", "merge:false", "rew:true"])
        self.assertEqual(out["merge"]["shown"], ["mrg-all", "mrg-zoom-wrap", "mrg-frame-h", "mrg-say"])
        self.assertEqual(out["merge"]["buttons"], ["day:false", "merge:true", "rew:false"])

    def test_under_the_rewrites_a_pressed_day_leaves_the_row_buttons_free_and_the_rows_come_back_as_they_were(self):
        out = self.drawn(REW_MERGE, demo_data())
        self.assertEqual(out["zoomed"]["shown"], ["rew", "rew-frame-h"])
        self.assertEqual(out["zoomed"]["buttons"], ["day:false", "merge:false", "rew:true"])
        # back to the rows while the Day is still zoomed: both row buttons off, as the zoom has them
        self.assertEqual(out["back"]["shown"], ["mrg-all", "mrg-zoom-wrap", "mrg-frame-h", "mrg-say"])
        self.assertEqual(out["back"]["buttons"], ["day:false:off", "merge:true:off", "rew:false"])
        self.assertEqual(out["out"]["buttons"], ["day:true", "merge:false", "rew:false"])

    def test_the_rewrites_pressed_while_a_day_is_zoomed_free_both_row_buttons(self):
        out = self.drawn(REW_ZOOM_FIRST, demo_data())
        self.assertEqual(out["zoomed"], ["day:false:off", "merge:true:off", "rew:undefined"])
        self.assertEqual(out["rew"], ["day:false", "merge:false", "rew:true"])

    def test_a_row_button_pressed_under_the_rewrites_and_a_zoom_keeps_the_rows_chosen_before_it(self):
        out = self.drawn(REW_MERGE_BACK, demo_data())
        self.assertEqual(out, ["day:true", "merge:false", "rew:false"])

    def test_a_link_to_the_merges_leaves_the_rewrites(self):
        out = self.drawn(REW_HASH, demo_data())
        self.assertEqual(out["before"], ["rew", "rew-frame-h"])
        self.assertEqual(out["shown"], ["mrg-all", "mrg-zoom-wrap", "mrg-frame-h", "mrg-say"])
        self.assertEqual(out["buttons"], ["day:false", "merge:true", "rew:false"])

    def test_promises_rewritten_without_the_key_say_so_under_not_measured(self):
        m = model(data())
        self.assertTrue("rew" in m, "the model has no rew key")
        self.assertIn("empty", m["rew"])
        out = boot(data())
        # one assertion, worded as the boot tests': a page that cannot boot fails here last, and reads the same
        self.assertEqual((out["error"], [e for e in out["logged"] if e.startswith("rew:")]), (None, []))


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


def page_tree():
    """index.html's elements by id: each a dict of its tag, attributes, children (elements and text) and parent."""
    ids, at = {}, [dict(tag=None, attrs={}, kids=[], up=None)]

    class Tree(HTMLParser):
        def handle_starttag(self, tag, attrs):
            e = dict(tag=tag, attrs=dict(attrs), kids=[], up=at[-1])
            at[-1]["kids"].append(e)
            if e["attrs"].get("id"):
                ids[e["attrs"]["id"]] = e
            if tag not in VOID:
                at.append(e)

        def handle_endtag(self, tag):
            while len(at) > 1 and at.pop()["tag"] != tag:
                pass

        def handle_data(self, data):
            at[-1].setdefault("text", []).append(data)

    Tree().feed(read("index.html"))
    return ids


def text_of(e):
    """The text inside an element, whitespace collapsed."""
    return " ".join(" ".join((e.get("text") or []) + [text_of(k) for k in e.get("kids", [])]).split())


class PageFilesTest(unittest.TestCase):
    """What index.html, dashboard.css and dashboard.js must hold, read as text."""

    def test_every_graph_has_its_plot_its_readout_and_its_exact_numbers_folded_under_it(self):
        html = read("index.html")
        for n in CARDS:
            section = re.search(rf'<(?:section class="graph"|div) id="g{n}">.*?</section>', html, re.S)
            self.assertIsNotNone(section, f"graph {n}")
            order = [section.group(0).index(f'id="g{n}-{part}"') for part in ("plot", "read", "table")]
            self.assertEqual(order, sorted(order), f"graph {n}")
            self.assertRegex(section.group(0), rf'<details class="exact"><summary>Exact numbers</summary>\s*(<p [^>]*>[^<]*</p>\s*)?<div class="scroll-x"><table id="g{n}-table">')
            self.assertIn(f'id="g{n}-read" aria-live="polite"', section.group(0))
        self.assertNotIn("<details open", html)

    def test_what_left_the_page_has_no_element_on_it(self):
        html = read("index.html")
        self.assertEqual([i for i in GONE_IDS if f'id="{i}"' in html], [])
        self.assertEqual(re.findall(r'id="([\w-]+-fold)"', html), FOLDS)

    def test_a_link_to_a_graph_that_left_lands_on_the_drawing_in_its_place(self):
        html = read("index.html")
        for section, ids in ANCHORS:
            body = re.search(rf'<section class="graph" id="{section}"[ >].*?</section>', html, re.S).group(0)
            self.assertEqual((section, [i for i in ids if f'<span class="anchor" id="{i}"></span>' in body]), (section, list(ids)))
        self.assertEqual(sorted(re.findall(r'id="(g[34589])"', html)), ["g3", "g4", "g5", "g8", "g9"])
        # out of the card's flex column, so an anchor adds no gap above the eyebrow
        css = read("dashboard.css")
        rules = (r"(?m)^\.graph \{[^}]*position: relative", r"(?m)^\.graph > \.anchor \{[^}]*position: absolute")
        self.assertEqual([bool(re.search(rule, css)) for rule in rules], [True, True])

    def test_an_eyebrow_names_a_fold_only_where_one_is_under_it(self):
        html = read("index.html")
        eyebrow = lambda i: re.search(rf'<section class="graph" id="{i}"[ >].*?<p class="graph-n">([^<]*)</p>', html, re.S).group(1)  # noqa: E731
        self.assertEqual({i: eyebrow(i) for i in EYEBROWS}, EYEBROWS)
        self.assertEqual([i for i in ("rdg", "gel", "mrg", "prf", "act") if "folded below" not in eyebrow(i)], [])

    def test_the_sections_that_stand_alone_point_at_no_graph_folded_under_them(self):
        # what the ring, the proteins, the budget, the rings and the reflex arcs print: their markup and the function that draws each
        html, script, gone = read("index.html"), read("dashboard.js"), r"folded (?:graph|below)|old (?:graphs?|tiles)|trust strip|graph \d+['’]s"
        said = []
        for section, draw in (("whr", "ringDraw"), ("prt", "protDraw"), ("atp", "atpDraw"), ("rng", "rngDraw"), ("rfx", "rfxDraw")):
            body = script[script.index(f"function {draw}("):]
            body = body[:body.index("\n}\n") if "\n}\n" in body else body.index("\r\n}\r\n")]
            markup = re.search(rf'<section class="graph" id="{section}"[ >].*?</section>', html, re.S).group(0)
            said += [(section, hit) for hit in re.findall(gone, markup)] + [(draw, hit) for hit in re.findall(gone, body)]
        self.assertEqual(said, [])
        # and nothing anywhere in the script credits a count to graph 3, 4 or 5, which are the proteins now
        self.assertEqual(re.findall(r"graph [345]['’]s \w+", script), [])
        self.assertEqual(re.findall(r"\w+ graph [345]\b", html), [])

    def test_no_graph_sits_inside_anything_collapsed(self):
        html = read("index.html")
        for plot in [f"g{n}-plot" for n in CARDS if n not in FOLDED] + ["mrg-scroll", "whr-scroll", "rdg-scroll", "gel-scroll", "prt-scroll",
                                                                             "prf-scroll", "atp-scroll", "rng-scroll", "act-scroll", "rfx-scroll"]:
            self.assertIn(f'id="{plot}"', html, plot)
            before = html[:html.index(f'id="{plot}"')]
            self.assertEqual(before.count("<details"), before.count("</details>"), plot)
        for n in FOLDED:
            # each old card is a plain block, last in its graph's closed line: its own fold closes it
            fold = re.search(rf'<div class="mock-fold" id="g{n}-fold">\s*<details class="exact">.*?\n    </details>\n  </div>', html, re.S)
            self.assertIsNotNone(fold, f"graph {n}'s card")
            for part in ("plot", "read", "table"):
                self.assertIn(f'id="g{n}-{part}"', fold.group(0), f"graph {n}'s {part} is in its fold")
        # and drawn there, on the example data, as before it was folded
        spec = importlib.util.spec_from_file_location("demo_data", os.path.join(HERE, "demo-data.py"))
        demo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo)
        data = demo.demo()
        for n in FOLDED:
            g = model(data)[f"g{n}"]
            self.assertNotIn("error", g)
            self.assertGreater(len(g.get("merges") or g.get("rows") or g.get("bars") or g.get("dates") or []), 0, f"graph {n}")
        out = boot(data)
        self.assertEqual((out["error"], out["logged"]), (None, []))

    def test_what_graph_6_would_mislead_without_stays_visible_beside_it(self):
        # folded under the merge graph: what shows when its fold is opened
        section = re.search(r'<div id="g6">.*?\n  </div>', read("index.html"), re.S).group(0)
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

    # The front page, chapter by chapter: each graph's section and where its old card is folded (g1, g7, g6).
    FRONT = {"rdg": 0, "g1": 0, "lrn": 0, "prf": 1, "g7": 1, "fil": 1, "prt": 2, "g3": 2, "gene": 2, "mrg": 2, "g6": 2, "rfx": 3, "atp": 4, "g8": 4}
    FRONT_HEADS = ["Where is it going?", "What happens inside a Day?", "What can it do, and can it be trusted?", "Can it be left alone?",
                   "What does it take?"]
    BACK = {"gel": 0, "g2": 0, "g12": 1, "rng": 2, "g9": 2, "act": 2, "g10": 2}
    BACK_HEADS = ["Is it on the plan's yardsticks?", "Do the specs follow the plan?", "Where did the work and the time go?"]

    def chapters(self, part, heads, ids):
        """{id: the index of the chapter it sits under} in `part`, -1 for an id not in it."""
        starts = [part.find(f'<h2 class="chapter">{h}<small>') for h in heads]
        at = {n: (m.start() if (m := re.search(f'id="{n}"[ >]', part)) else -1) for n in ids}
        return {n: max((i for i, s in enumerate(starts) if -1 < s < a), default=-1) for n, a in at.items()}

    def test_the_front_page_holds_its_graphs_in_order_under_five_chapters(self):
        html = read("index.html")
        self.assertEqual(re.findall(r'<div class="view" id="(v-front|v-back)"', html), ["v-front", "v-back"])
        front = html[html.index('<div class="view" id="v-front"'):html.index('<div class="view" id="v-back"')]
        self.assertEqual(re.findall(r'<section class="graph(?: foot)?" id="([\w-]+)"[ >]', front),
                         ["rdg", "lrn", "prf", "fil", "prt", "gene", "mrg", "rfx", "atp", "cannot-see"])
        self.assertEqual(re.findall(r'<h2 class="chapter">([^<]*)<small>', front), self.FRONT_HEADS)
        self.assertEqual(self.chapters(front, self.FRONT_HEADS, self.FRONT), self.FRONT)
        self.assertLess(front.index('id="atp"'), front.find('<div class="to-back">'))
        self.assertLess(front.find('<div class="to-back">'), front.index('id="cannot-see"'))
        for part in ("say", "ladder", "key", "plot", "read", "table"):
            self.assertIn(f'id="g1-{part}"', front)

    def test_the_back_page_holds_graphs_2_12_9_and_10_and_opens_on_a_button(self):
        html = read("index.html")
        self.assertEqual(re.findall(r'<div class="view" id="v-back" hidden>', html), ['<div class="view" id="v-back" hidden>'])
        back = html[html.index('<div class="view" id="v-back" hidden>'):html.index("<footer>")]
        self.assertEqual(re.findall(r'<section class="graph[^"]*" id="([\w-]+)"', back), ["gel", "g12", "rng", "act"])
        self.assertEqual(re.findall(r'<h2 class="chapter">([^<]*)<small>', back), self.BACK_HEADS)
        self.assertEqual(self.chapters(back, self.BACK_HEADS, self.BACK), self.BACK)
        # the switch in the header, and the way to the back page from the foot of the front one
        header = html[html.index("<header"):html.index("</header>")]
        self.assertEqual(re.findall(r'<button type="button" data-view="(\w+)" aria-pressed="(\w+)">', header), [("front", "true"), ("back", "false")])
        self.assertIn('<small id="back-n"></small>', header)
        to_back = re.findall(r'<div class="to-back">\s*<p>(\w+) more graphs[^<]*</p>\s*<button type="button" data-view="back">', html)
        self.assertEqual((to_back, len(re.findall(r'<section class="graph"', back))), (["Four"], 4))

    # Each picture's container, and the lead of its closed line where it is not "Under the picture".
    UNDER = ("rdg", "lrn", "prf-all", "one", "fil", "prt", "gene", "mrg-all", "rew", "rfx", "atp", "gel", "g12", "rng", "act")
    UNDER_LEAD = {"one": "Under this Day's picture", "rew": "Under the rewrites"}
    OLD_CARDS = {"g1-fold": "rdg-under", "g2-fold": "gel-under", "g6-fold": "mrg-all-under", "g7-fold": "prf-all-under", "g10-fold": "act-under"}

    def test_every_picture_has_one_closed_line_after_it(self):
        ids = page_tree()
        self.assertEqual([c for c in self.UNDER if c not in ids], [])
        cls = lambda e: e["attrs"].get("class", "").split()  # noqa: E731
        picture = lambda e: re.search(r"-(scroll|plot)$|^one-strand$", e["attrs"].get("id", "")) or {"pc-fig", "readout", "duo"} & set(cls(e))  # noqa: E731
        moves = lambda e: (e["tag"] == "details" and "under" not in cls(e)) or (e["tag"] == "p" and {"hint", "rng-hint", "act-hint", "ci"} & set(cls(e))) \
            or (e["tag"] == "div" and {"find", "notes"} & set(cls(e)))  # noqa: E731
        for c in self.UNDER:
            kids = ids[c]["kids"]
            unders = [i for i, e in enumerate(kids) if e["tag"] == "details" and "under" in cls(e)]
            self.assertEqual((c, len(unders)), (c, 1))
            fold = kids[unders[0]]
            self.assertEqual((fold["attrs"].get("id"), "open" in fold["attrs"]), (f"{c}-under", False))
            summary = fold["kids"][0] if fold["kids"] else {}
            self.assertEqual((summary.get("tag"), [e["attrs"].get("id") for e in summary.get("kids", []) if "under-n" in cls(e)]), ("summary", [f"{c}-under-n"]), c)
            self.assertEqual(text_of(summary.get("kids", [{}])[0]), self.UNDER_LEAD.get(c, "Under the picture"), c)
            pictures = [i for i, e in enumerate(kids) if picture(e)]
            self.assertEqual((c, bool(pictures) and max(pictures) < unders[0]), (c, True))
            self.assertEqual([(c, e["tag"], e["attrs"].get("class", "")) for e in kids if moves(e)][:1], [])
        # the five old cards, each last in its graph's fold
        for card, fold in self.OLD_CARDS.items():
            e = ids.get(card, dict(tag=None, attrs={}, up=None))
            self.assertEqual((card, e["tag"], cls(e), e["up"] is not None and e["up"]["attrs"].get("id"), e["up"] is not None and e["up"]["kids"][-1] is e),
                             (card, "div", ["mock-fold"], fold, True))
        self.assertNotIn('<section class="graph mock-fold"', read("index.html"))

    def test_the_build_inlines_one_stylesheet_and_one_script_and_fills_one_data_line(self):
        page = sd.build(json.dumps(dict(now=dict(next_step="x"))))
        self.assertNotIn('href="dashboard.css"', page)
        self.assertNotIn('src="dashboard.js"', page)
        self.assertIn("function boot(DATA)", page)
        self.assertIn("--proven:", page)
        self.assertEqual(re.findall(r"^window\.SPEC_DRIFT = (.*);$", page, re.M), ['{"now": {"next_step": "x"}}'])

    def test_no_text_in_the_data_can_keep_its_script_open(self):
        # Bearing's twelfth Day's spec quoted "<!--" and "<script>": in a browser the data script then ran to the end
        # of the page, and the live dashboard showed nothing. With no "<" on the line, no tag or comment
        # can start there, whatever the text.
        text = "<!-- PROJECT: x --> <!-- a second `<script>` </script> <SCRIPT src=x>"
        payload = dict(now=dict(next_step=text), specs=[dict(title=text)])
        line = re.search(r"^window\.SPEC_DRIFT = (.*);$", sd.build(json.dumps(payload)), re.M).group(1)
        self.assertNotIn("<", line)
        self.assertEqual(json.loads(line), payload)

    def test_the_graphs_put_data_on_the_page_as_text_never_as_html(self):
        script = read("dashboard.js")
        # Nothing builds HTML from text: an excerpt of a spec is a text node too. (The failure names the lines, not
        # the script: a break's report goes in a pull request whole.)
        self.assertEqual([line.strip()[:60] for line in script.splitlines() if "innerHTML" in line], [])

    def test_every_colour_has_a_dark_value_and_both_dark_scopes_agree(self):
        css = read("dashboard.css")
        light = re.search(r":root \{(.*?)\n\}", css, re.S).group(1)
        by_os = re.search(r':root:not\(\[data-theme="light"\]\) \{(.*?)\n  \}', css, re.S).group(1)
        by_choice = re.search(r':root\[data-theme="dark"\] \{(.*?)\n\}', css, re.S).group(1)
        colours = lambda block: dict(re.findall(r"(--[\w-]+): (#[0-9a-f]{6})", block))
        self.assertGreaterEqual(len(colours(light)), 30)
        self.assertEqual(sorted(colours(by_os)), sorted(colours(light)))
        self.assertEqual(colours(by_os), colours(by_choice))

    def test_graph_10_says_in_one_sentence_that_a_date_runs_from_05_00_to_05_00(self):
        section = re.search(r'<div class="mock-fold" id="g10-fold">.*?</section>', read("index.html"), re.S).group(0)
        self.assertIn("A date runs from 05:00 to 05:00, so work after midnight stays on the evening it belongs to.", section)

    def test_needs_attention_is_a_section_in_the_header_folded_until_it_is_opened(self):
        html, js = read("index.html"), read("dashboard.js")
        header = html[html.index("<header"):html.index("</header>")]
        self.assertIn('<section class="attention" id="attention" aria-labelledby="attention-h" hidden>', header)
        panel = header[header.index('id="attention"'):]
        # one fold, closed (no `open`), around everything but the title and the count beside it
        fold = re.findall(r'<details class="at-all" id="attention-all"( open)?>\s*<summary><h2 id="attention-h">([^<]+)</h2>'
                          r'<span class="at-peek" id="attention-peek"></span></summary>', panel)
        self.assertEqual(fold, [("", "What needs attention today?")])
        self.assertLess(panel.index('id="attention-all"'), panel.index('id="attention-n"'))
        self.assertEqual(panel.count("</details>"), 3)
        # the count beside the title is the rule's headline, and a chip's link is the fold, which openFolds() opens
        self.assertIn('put("attention-peek", A.head);', js)
        self.assertEqual(re.findall(r'class: "chip", href: "#([\w-]+)"', js), ["attention-all"])
        # inside it, what is not counted is folded again: never proved, and expected
        self.assertEqual(re.findall(r'<details class="at-fold" id="([\w-]+)" hidden>', panel), ["attention-never", "attention-known"])

    def test_each_graph_a_line_can_name_has_a_chip_slot_beside_its_title(self):
        html, js = read("index.html"), read("dashboard.js")
        titles = dict(re.findall(r'(\w+): "([^"]+)"', re.search(r"const NEEDS_TITLES = \{(.*?)\};", js, re.S).group(1)))
        self.assertEqual(tuple(titles), views.NEEDS_GRAPHS)
        for g, title in titles.items():
            section = html[html.index(f'<section class="graph" id="{g}"'):]
            first = section[:section.index("</h2>") + 200]
            self.assertRegex(first, rf'<h2>{re.escape(title)}</h2>\s*<p class="chips" id="{g}-chips" hidden></p>', g)
        self.assertEqual(len(re.findall(r'class="chips"', html)), len(titles))

    def test_every_mark_the_rule_can_give_is_drawn_and_named(self):
        css, js = read("dashboard.css"), read("dashboard.js")
        marks = sorted({why[1] for why in views.NEEDS_WHY.values()})
        self.assertEqual(marks, ["bad", "due", "exp", "hnd", "rep", "stl", "unp"])
        self.assertEqual([m for m in marks if not re.search(rf"\.o\.{m} \{{", css)], [])
        named = re.search(r"const NEEDS_MARKS = \{(.*?)\};", js, re.S).group(1)
        self.assertEqual(sorted(re.findall(r"(\w+): \"", named)), marks)
        of_group = dict(re.findall(r'(\w+): "(\w+)"', re.search(r"const NEEDS_GROUP_MARK = \{(.*?)\};", js, re.S).group(1)))
        self.assertEqual(sorted(of_group), sorted(g[0] for g in views.NEEDS_GROUPS))

    def test_graph_12_has_a_swatch_for_a_commitment_owned_by_a_later_day(self):
        self.assertRegex(read("dashboard.css"), r"\.pc-sw\.later \{[^}]*border")

    def test_every_swatch_a_key_names_has_a_rule_in_the_stylesheet(self):
        # A key's swatch is drawn by its class alone ("sw spec"): one whose rule left with a graph that shared it shows
        # nothing. Graph 10's key shares spec, prod and tooling with the bars of graphs 8 and 9, which left the page.
        used = sorted(set(re.findall(r'(?<![\w-])sw ([a-z][\w-]*)["`]', read("dashboard.js"))))
        css = read("dashboard.css")
        self.assertEqual([k for k in used if not re.search(rf"\.sw\.{re.escape(k)}[ ,{{]", css)], [])
        self.assertGreaterEqual(len(used), 14)
        # and no rule is kept for a fold that left
        self.assertEqual(re.findall(r"\.mock-top\b|--unproven-2\b|\.s(?:w|eg)\.past\b", css), [])

    def test_the_page_needs_no_script_or_style_from_anywhere_but_its_own_two_files(self):
        html = read("index.html")
        self.assertEqual(re.findall(r'<script src="([^"]+)"', html), ["dashboard.js"])
        self.assertEqual([h for h in re.findall(r'<link rel="stylesheet" href="([^"]+)"', html) if not h.startswith("https://fonts.googleapis.com/")],
                         ["dashboard.css"])

    def test_graph_7_opens_one_day_beside_its_stream_from_a_key_the_page_data_holds(self):
        html = read("index.html")
        want = ['id="prf-v-all"', 'id="prf-v-one"', 'id="prf-all"', 'id="one" hidden', 'id="one-pick"', 'id="one-rfig"', 'id="one-fig"',
                'id="one-out" aria-live="polite"', 'id="one-who"']
        # the first one missing, so that the failure stays short
        self.assertEqual([w for w in want if w not in html][:1], [])
        # the page wires the switch and draws the view when it boots: the drawing tests call both by hand
        wired = ["prfViews($);", '[["one", oneDraw]]']
        self.assertEqual([w for w in wired if w not in read("dashboard.js")][:1], [])
        section = re.search(r'<section class="graph" id="prf"[ >].*?</section>', html, re.S)
        self.assertIsNotNone(section)
        self.assertTrue('<div id="one" hidden>' in section.group(0), "#one stands inside graph 7's section")
        # the key is written into the page's data, by the real build and by the demo's
        written = []
        for name in ("spec-drift.py", "demo-data.py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as f:
                written.append('["one_day"] = one_day(' in f.read())
        self.assertEqual(written, [True, True])

    def test_graph_6_turns_to_the_promises_rewritten_from_a_key_the_page_data_holds(self):
        html = read("index.html")
        section = re.search(r'<section class="graph" id="mrg"[ >].*?</section>', html, re.S)
        self.assertIsNotNone(section)
        want = ['id="mrg-v-rew"', 'id="mrg-all"', 'id="rew" hidden', 'id="rew-rfig"', 'id="rew-out" aria-live="polite"', 'id="rew-figs"',
                'id="rew-frame-h"']
        # the first one missing from graph 6's section, so that the failure stays short
        self.assertEqual([w for w in want if w not in section.group(0)][:1], [])
        # the switch is wired before the merge graph's own listeners, and the view is drawn when the page boots
        script = read("dashboard.js")
        wired = ["mrgViews($);", '[["rew", rewDraw]]']
        self.assertEqual([w for w in wired if w not in script][:1], [])
        self.assertTrue(script.find("mrgViews($);") < script.find("mergeDraw(m, $, onDay)"), "mrgViews($); stands before mergeDraw")
        written = []
        for name in ("spec-drift.py", "demo-data.py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as f:
                written.append('["rewrites"] = rewrites(' in f.read())
        self.assertEqual(written, [True, True])
        # and the real build prints its line for the console
        with open(os.path.join(HERE, "spec-drift.py"), encoding="utf-8") as f:
            self.assertTrue("print(rewrites_line(" in f.read(), "spec-drift.py prints no rewrites line")


if __name__ == "__main__":
    unittest.main()
