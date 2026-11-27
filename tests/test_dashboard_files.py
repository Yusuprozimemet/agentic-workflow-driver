"""The dashboard's file map, "Where does each file belong?" (scripts/pipeline/sources/spec_drift_files.py, filDraw in dashboard.js):
every tracked file is one dot under the station it serves, a folder places itself, a script is placed by the table
in docs/dashboard/file-stations.json, and a file the table does not place is drawn in the ring, never dropped.
The page tests need node."""

import importlib.util
import itertools
import json
import math
import os
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SCRIPTS = os.path.join(ROOT, "scripts")
PAGE = os.path.join(ROOT, "docs", "dashboard")
sys.path.insert(0, SCRIPTS)
import pipeline  # importing it puts the pipeline's three folders on the path


def load(name, file):
    spec = importlib.util.spec_from_file_location(
        name, pipeline.path(file) if file.startswith("spec_drift_") else os.path.join(SCRIPTS, file)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def real(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


files = load("spec_drift_files", "spec_drift_files.py")

# A small repository: a file or two for every kind of place the table knows.
FILES = {
    "plan.md": 900, "CLAUDE.md": 400, "specs/README.md": 300, "specs/_template.md": 25,
    "specs/day-01-first.md": 500, "specs/day-02-second.md": 250, "specs/plan/promises.json": 100,
    "specs/breaks/day-01.json": 12, ".claude/agents/spec-auditor.md": 208, ".claude/agents/implementer.md": 79,
    ".claude/agents/track-reviewer.md": 150,
    "tests/test_a.py": 120, "tests/test_b.py": 60, "tests/__init__.py": 0,
    "driver/decide.py": 200, "run-steps.py": 40, "hooks/readonly.py": 30, ".github/workflows/tests.yml": 50,
    "scripts/seen-red.py": 150, "scripts/tests/test_seen_red.py": 90, "scripts/spec-drift.py": 316,
    "scripts/spec_drift_views.py": 1980, "scripts/test_spec_drift_views.py": 10, "scripts/tests/test_diff_limit.py": 40,
    "docs/lab-notebook.md": 300, "docs/kit.md": 100, "README.md": 80, "docs/dashboard/index.html": 800,
    ".gitignore": 10, "pyproject.toml": 20,
}  # fmt: skip

# The improve loop's own files, two case sets (one keeps a case's text in a folder of its own) and the driver's
# reviewer; then which brief each case set names, as the build reads it from the case sets.
LOOP = {
    ".claude/agents/brief-improver.md": 60, "scripts/improve-loop.py": 300, "scripts/test_improve_loop.py": 200,
    "specs/agent-cases/spec-auditor.json": 90, "specs/agent-cases/reviewer.json": 70,
    "specs/agent-cases/track-reviewer.json": 80, "specs/agent-cases/track-reviewer/day-13-a.md": 40,
    "rules/reviewer.md": 50,
}  # fmt: skip
BRIEFS = {
    "spec-auditor": ".claude/agents/spec-auditor.md", "reviewer": "rules/reviewer.md",
    "track-reviewer": ".claude/agents/track-reviewer.md",
}  # fmt: skip
# What the table did not place when the loop was built (#288 to #297): each has a station now.
ONCE_UNPLACED = (
    ".claude/agents/brief-improver.md", "scripts/improve-loop.py", "scripts/test_improve_loop.py",
    "scripts/case-count.py", "scripts/test_case_count.py", "scripts/close-views.py",
    "scripts/test_close_views.py", "specs/fixes.json",
)  # fmt: skip


def table():
    groups, why = files.load_table()
    assert groups, why
    return groups


def drawn(counts):
    return files.file_map(counts, table(), "abc1234")


def home(model, path):
    """The group a file hangs in, and the file's own row."""
    row = next(f for f in model["files"] if f[0] == path)
    return model["groups"][row[3]], row


class FileMapTest(unittest.TestCase):
    def test_every_file_is_drawn_once(self):
        m = drawn(FILES)
        self.assertEqual([f[0] for f in m["files"]], sorted(FILES))
        dots = sorted(d[0] for g in m["groups"] for d in g["dots"])
        self.assertEqual(dots, list(range(len(FILES))))
        self.assertEqual(sum(z["files"] for z in m["zones"]), len(FILES))
        self.assertEqual(sum(k["n"] for k in m["kinds"]), len(FILES))
        self.assertEqual(sum(z["lines"] for z in m["zones"]), sum(FILES.values()))
        self.assertEqual(m["lines"], sum(FILES.values()))
        self.assertEqual(m["unplaced"], [])

    def test_the_scripts_index_and_the_layout_test_have_a_station_and_are_not_counted_as_scripts(
        self,
    ):
        more = {"scripts/README.md": 30, "scripts/tests/test_scripts_layout.py": 60}
        m = drawn(dict(FILES, **more))
        self.assertEqual(m["unplaced"], [])
        self.assertEqual(home(m, "scripts/README.md")[0]["label"], "guides")
        self.assertEqual(
            home(m, "scripts/tests/test_scripts_layout.py")[0]["at"], "CI's checks, after station 5"
        )
        # seen-red.py, spec-drift.py and spec_drift_views.py: the scripts, not their tests or their index
        self.assertEqual(m["scripts"], 3)

    def test_a_folder_places_itself(self):
        m = drawn(
            dict(
                FILES,
                **{
                    "tests/test_brand_new.py": 33,
                    "driver/brand_new.py": 44,
                    "specs/day-03-third.md": 55,
                },
            )
        )
        for path, label, at in (
            ("tests/test_brand_new.py", "tests/", "station 4, a test that fails first"),
            ("driver/brand_new.py", "the driver", "station 5, the code, then a planted bug"),
            ("specs/day-03-third.md", "day specs", "station 2, a Day's spec"),
        ):
            group, row = home(m, path)
            self.assertEqual((group["label"], group["at"], row[4]), (label, at, 0), path)

    def test_a_script_is_placed_by_the_table_and_its_test_follows_it(self):
        m = drawn(FILES)
        kinds = [k["key"] for k in m["kinds"]]
        script, row = home(m, "scripts/seen-red.py")
        self.assertEqual(
            (script["label"], script["at"], kinds[row[2]]),
            ("scripts/", "station 4, a test that fails first", "tool"),
        )
        test, row = home(m, "scripts/tests/test_seen_red.py")
        self.assertEqual((test["label"], test["at"]), (script["label"], script["at"]))
        self.assertEqual(kinds[row[2]], "tooltest")
        # a test named in the table hangs where the table says, whatever script its name starts like
        self.assertEqual(
            home(m, "scripts/tests/test_diff_limit.py")[0]["at"], "CI's checks, after station 5"
        )
        # a pattern in the table takes a module, and that module's test follows it
        self.assertEqual(home(m, "scripts/spec_drift_views.py")[0]["label"], "dashboard")
        self.assertEqual(home(m, "scripts/test_spec_drift_views.py")[0]["label"], "dashboard")

    def test_a_module_in_the_pipeline_folder_hangs_with_the_dashboards_scripts(self):
        # scripts/pipeline/ holds the page's data builder in a folder per concern: the table takes the folder
        more = {
            "scripts/pipeline/__init__.py": 30,
            "scripts/pipeline/sources/spec_drift_git.py": 260,
            "scripts/pipeline/counts/spec_drift_views.py": 1980,
        }
        m = drawn(dict(FILES, **more))
        # the first one the table does not place, by its name alone, so that the failure stays short
        self.assertEqual([p.rsplit("/", 1)[1] for p in more if p in m["unplaced"]][:1], [])
        self.assertEqual({home(m, p)[0]["label"] for p in more}, {"dashboard"})
        # they are still scripts in the map's count: the small repository's three, and these three
        self.assertEqual(m["scripts"], 6)

    def test_a_script_missing_from_the_table_is_drawn_in_the_ring(self):
        more = {
            "scripts/brand-new.py": 77,
            "scripts/test_brand_new.py": 21,
            "elsewhere/notes.txt": 5,
        }
        m = drawn(dict(FILES, **more))
        self.assertEqual(m["unplaced"], sorted(more))
        for path in more:
            group, row = home(m, path)
            self.assertEqual((group["ring"], group["at"], row[4]), (True, "on no station", 1), path)
            self.assertEqual(
                sum(d[0] == m["files"].index(row) for g in m["groups"] for d in g["dots"]), 1, path
            )
        # a settings file is in the ring by the table's word, not for want of one
        group, row = home(m, ".gitignore")
        self.assertEqual((group["ring"], row[4]), (True, 0))
        self.assertEqual(sum(len(g["dots"]) for g in m["groups"]), len(FILES) + len(more))

    def test_a_table_with_no_ring_still_draws_what_it_does_not_place(self):
        groups = [g for g in table() if not g.get("ring")]
        m = files.file_map(FILES, groups, "abc1234")
        self.assertEqual(m["unplaced"], [".gitignore", "pyproject.toml"])
        self.assertEqual(sum(len(g["dots"]) for g in m["groups"]), len(FILES))

    def test_a_dot_is_as_big_as_its_file_and_the_longest_comes_first(self):
        self.assertEqual(round(files.radius(400), 2), 7.2)
        self.assertEqual(files.radius(0), 1.8)
        m = drawn(FILES)
        for g in m["groups"]:
            sizes = [d[3] for d in g["dots"]]
            self.assertEqual(sizes, sorted(sizes, reverse=True), g["label"])
            for i, _, _, r in g["dots"]:
                self.assertEqual(r, round(max(1.8, 0.36 * math.sqrt(m["files"][i][1])), 1))

    def test_dots_keep_clear_of_each_other_in_rows_centred_under_the_station(self):
        many = dict(FILES, **{f"tests/test_n{n:03d}.py": 15 + (n * 37) % 700 for n in range(120)})
        m = drawn(many)
        tests = next(g for g in m["groups"] if g["label"] == "tests/")
        self.assertEqual(tests["files"], 123)
        dots = [d[1:] for d in tests["dots"]]
        for a in range(len(dots)):
            for b in range(a + 1, len(dots)):
                (x1, y1, r1), (x2, y2, r2) = dots[a], dots[b]
                self.assertGreaterEqual(
                    math.hypot(x1 - x2, y1 - y2) + 0.25, r1 + r2, (dots[a], dots[b])
                )
        rows = {}
        for x, y, r in dots:
            rows.setdefault(y, []).append((x - r, x + r))
        self.assertGreater(len(rows), 3)
        for y, spans in rows.items():
            left, right = min(s[0] for s in spans), max(s[1] for s in spans)
            self.assertLessEqual(right - left, files.WIDTH + 0.2, y)
            self.assertAlmostEqual((left + right) / 2, tests["x"], delta=0.2)

    def test_the_cell_grows_with_its_tallest_column(self):
        small = drawn(FILES)
        tall = drawn(dict(FILES, **{f"tests/test_n{n:03d}.py": 400 for n in range(150)}))
        self.assertGreater(tall["geo"]["cell_h"], small["geo"]["cell_h"])
        self.assertEqual(tall["geo"]["nuc_h"], small["geo"]["nuc_h"])
        for m in (small, tall):
            geo = m["geo"]
            floor = {
                "doc": files.NUC_TOP + geo["nuc_h"],
                "try": files.CELL_TOP + geo["cell_h"],
                "after": geo["top"] + geo["height"],
            }
            for g in m["groups"]:
                for _, _, cy, r in g["dots"]:
                    self.assertLess(cy + r, floor[g["zone"]], g["label"])
            self.assertLessEqual(floor["doc"], floor["try"])
            self.assertLessEqual(floor["try"], floor["after"])

    def test_a_table_that_cannot_be_read_draws_nothing_and_says_why(self):
        groups, why = files.load_table(os.path.join(ROOT, "no-such-table.json"))
        self.assertIsNone(groups)
        m = files.file_map(FILES, groups, "abc1234", why)
        self.assertEqual(list(m), ["empty"])
        self.assertIn("docs/dashboard/file-stations.json", m["empty"])
        self.assertIn("empty", files.file_map({}, table(), "abc1234"))

    def test_the_counts_are_gits_one_per_tracked_file(self):
        def git(*args):
            if args[1] == "ls-tree":
                return (
                    "plan.md\ntests/test_a.py\ntests/__init__.py\ndocs/logo.png\ndocs/odd:name.md\n"
                )
            return "abc1234:plan.md:900\nabc1234:tests/test_a.py:120\nabc1234:docs/odd:name.md:7\n"

        self.assertEqual(
            files.tracked("abc1234", git),
            {
                "plan.md": 900,
                "tests/test_a.py": 120,
                "tests/__init__.py": 0,
                "docs/logo.png": 0,
                "docs/odd:name.md": 7,
            },
        )

    def test_the_improve_loops_files_have_a_station(self):
        for path in ONCE_UNPLACED:
            self.assertIsNotNone(files.place(path, table()), path)
        m = files.file_map(dict(FILES, **LOOP), table(), "abc1234", briefs=BRIEFS)
        self.assertEqual(m["unplaced"], [])
        for path in list(LOOP)[:3]:
            group = home(m, path)[0]
            self.assertEqual(
                (group["label"], group["at"]),
                ("improve loop", "the defect-rater's check, after station 6"),
                path,
            )

    def test_the_track_reviewers_brief_hangs_at_a_column_of_its_own(self):
        # the track-reviewer is a check after station 5, not the writer: its brief hangs at its own column, and
        # the implementer's brief alone at the implementer's
        self.assertIn("track-reviewer", sorted(files.COLUMNS))
        col = files.COLUMNS["track-reviewer"]
        self.assertEqual(
            (col["zone"], col["at"]), ("try", "the track-reviewer's check, after station 5")
        )
        order = list(files.COLUMNS)
        self.assertEqual(order[order.index("s5") + 1 : order.index("ci")], ["track-reviewer"])
        m = drawn(FILES)
        reviewer = home(m, ".claude/agents/track-reviewer.md")[0]
        writer = home(m, ".claude/agents/implementer.md")[0]
        self.assertEqual(
            (reviewer["at"], reviewer["label"], reviewer["files"]), (col["at"], "agent", 1)
        )
        self.assertEqual(
            (writer["at"], writer["label"], writer["files"]),
            (files.COLUMNS["implementer"]["at"], "agent", 1),
        )

    def test_the_loop_lands_where_each_brief_with_cases_hangs(self):
        counts = dict(FILES, **LOOP)
        m = files.file_map(counts, table(), "abc1234", briefs=BRIEFS)
        loop, col = m["loop"], files.COLUMNS
        self.assertEqual(
            (loop["x"], loop["y"]),
            (col["defect-rater"]["x"], files.LOOP_Y),
            "it leaves where its files hang",
        )
        self.assertIn("track-reviewer", sorted(col))
        self.assertEqual(
            [(t["col"], t["x"], t["at"], t["agents"]) for t in loop["to"]],
            [
                (
                    "spec-auditor",
                    col["spec-auditor"]["x"],
                    col["spec-auditor"]["at"],
                    ["spec-auditor"],
                ),
                ("s5", col["s5"]["x"], col["s5"]["at"], ["reviewer"]),
                (
                    "track-reviewer",
                    col["track-reviewer"]["x"],
                    col["track-reviewer"]["at"],
                    ["track-reviewer"],
                ),
            ],
        )
        # the picture opens higher to hold the line, and ends where it ended
        plain = files.file_map(counts, table(), "abc1234")
        self.assertIsNone(
            plain["loop"], "no case set names a brief, so there is nothing to land on"
        )
        self.assertEqual((plain["geo"]["top"], m["geo"]["top"]), (files.VIEW_TOP, files.LOOP_TOP))
        self.assertLess(files.LOOP_TOP, files.LOOP_Y - 12)
        self.assertEqual(
            m["geo"]["top"] + m["geo"]["height"], plain["geo"]["top"] + plain["geo"]["height"]
        )
        # two briefs in one column share an arrow; a brief git does not track gets none. The table hangs each
        # brief at a column of its own, so this one puts two briefs in one group at the implementer's column.
        both = [".claude/agents/implementer.md", ".claude/agents/track-reviewer.md"]
        own = [g for g in table() if not set(g.get("paths", ())) & set(both)]
        own.append(
            {
                "at": "implementer",
                "label": "agents",
                "kind": "tool",
                "what": "Two briefs.",
                "paths": both,
            }
        )
        more = {"implementer": ".claude/agents/implementer.md", "gone": ".claude/agents/gone.md"}
        shared = files.file_map(counts, own, "abc1234", briefs=dict(BRIEFS, **more))
        self.assertEqual(
            [(t["col"], t["agents"]) for t in shared["loop"]["to"]],
            [
                ("spec-auditor", ["spec-auditor"]),
                ("implementer", ["implementer", "track-reviewer"]),
                ("s5", ["reviewer"]),
            ],
        )
        # without the loop's own files there is no loop to draw, whatever has cases
        self.assertIsNone(files.file_map(FILES, table(), "abc1234", briefs=BRIEFS)["loop"])

    def test_the_build_reads_which_brief_each_case_set_names(self):
        shown = {
            "abc1234:specs/agent-cases/reviewer.json": '{"agent": "reviewer", "brief": "rules/reviewer.md"}',
            "abc1234:specs/agent-cases/spec-auditor.json": '{"agent": "spec-auditor", "cases": []}',
            "abc1234:specs/agent-cases/track-reviewer.json": '{"agent": "track-reviewer"}',
            "abc1234:specs/agent-cases/torn.json": '{"agent": ',
        }
        counts = dict(FILES, **LOOP, **{"specs/agent-cases/torn.json": 1})

        def run(*cmd):
            if cmd[1] == "ls-tree":
                return "\n".join(counts)
            if cmd[1] == "grep":
                return "\n".join(f"abc1234:{p}:{n}" for p, n in counts.items() if n)
            return shown[cmd[2]]

        # the brief a case set names, .claude/agents/<agent>.md when it names none; a set that cannot be read
        # names no brief, and a case's text in a folder is not a case set
        got = files.case_briefs(counts, "abc1234", run)
        self.assertEqual(sorted(got), sorted(BRIEFS))
        for agent, brief in BRIEFS.items():
            self.assertEqual(got[agent], brief, agent)
        m = files.build_file_map("abc1234", run)
        self.assertEqual(
            [t["agents"] for t in m["loop"]["to"]],
            [["spec-auditor"], ["reviewer"], ["track-reviewer"]],
        )

    def test_the_build_puts_it_in_the_data(self):
        wired = real("scripts", "spec-drift.py").count('real["file_map"] = build_file_map(')
        self.assertEqual(wired, 1, "spec-drift.py puts the file map in the data once")


# filDraw() from dashboard.js on the model from stdin, on a document that keeps what is made: the dots it drew,
# the marks of the cell by class, and every word it put on the page.
FIL = r"""
const fs = require("fs"), vm = require("vm"), els = {};
const node = tag => { const n = { tag, attrs: {}, kids: [], style: {}, dataset: {}, hidden: false, textContent: "",
  classList: { add(c) { n.attrs.class = ((n.attrs.class || "") + " " + c).trim(); }, remove() {}, toggle() {}, contains() { return false; } },
  setAttribute(k, v) { this.attrs[k] = String(v); }, getAttribute(k) { return this.attrs[k]; }, appendChild(c) { this.kids.push(c); return c; },
  append(...c) { this.kids.push(...c); }, replaceChildren(...c) { this.kids = c; }, addEventListener() {}, querySelectorAll() { return []; } };
  Object.defineProperty(n, "className", { set(v) { n.attrs.class = v; }, get() { return n.attrs.class || ""; } });
  return n; };
const document = { createElementNS(ns, tag) { return node(tag); }, createElement: node, addEventListener() {} };
const $ = id => els[id] || (els[id] = node(id));
const ctx = vm.createContext({ F: JSON.parse(fs.readFileSync(0, "utf8")), document, $, addEventListener() {} });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + `
  const all = n => [n, ...(n.kids || []).filter(k => k && typeof k === "object").flatMap(all)];
  const is = (root, sel) => all(root).filter(e => sel.every(c => ((e.attrs && e.attrs.class) || "").split(" ").includes(c))).length;
  const words = n => typeof n === "string" ? n : [n.textContent, ...(n.kids || []).map(words)].join(" ");
  filDraw(F, $);
  const f = $("fil-fig"), key = $("fil-key");
  ({ dots: is(f, ["f"]), kinds: ["spec", "code", "test", "tool", "tooltest"].map(k => is(f, ["f", k])), groups: is(f, ["grp"]),
     pills: is(f, ["pill"]), plasmid: is(f, ["plasmid"]), ribo: is(f, ["ribo"]), checks: is(f, ["chk"]),
     loop: [is(f, ["loop-line"]), is(f, ["loop-head"]), is(key, ["loop-line"])],
     keyMarks: [is(key, ["chk"]), is(key, ["ribo"]), is(key, ["f"])], view: f.attrs.viewBox || "", label: f.attrs["aria-label"] || "",
     key: words(key).replace(/\\s+/g, " "), rows: all($("fil-table")).filter(e => e.tag === "tr").length,
     words: ["fil-figs", "fil-key", "fil-hint", "fil-table", "fil-stamp", "fil-how", "fil-scroll"].map(id => words($(id))).join(" ").replace(/\\s+/g, " "),
     figure: words(f).replace(/\\s+/g, " "),
     chk: all(f).filter(e => ((e.attrs && e.attrs.class) || "").split(" ").includes("chk"))
       .map(e => [e.tag, e.tag === "path" ? +(/^M([\\d.]+),/.exec(e.attrs.d) || [0, 0])[1] : +e.attrs.x + +e.attrs.width / 2]),
     at: all(f).filter(e => e.tag === "text").map(e => [e.attrs.class || "", words(e), +e.attrs.x, +e.attrs.y, e.attrs["text-anchor"] || "start"]),
     pillsAt: all(f).filter(e => e.tag === "rect" && e.attrs.class === "pill").map(e => +e.attrs.x + +e.attrs.width / 2),
     riboAt: all(f).filter(e => e.attrs && e.attrs.class === "ribo").map(e => +e.attrs.cx) })`, ctx)));
"""

# A text's width on the map, as a rough share of its size: the names (10.5 px, bold) and the small words (9.5 px,
# monospaced) a little over their average letter.
PER = {"t-g": 6.0, "t-bio": 5.8}


def words_box(t):
    cls, words, x, y, anchor = t
    w = len(words) * PER[cls]
    x0 = x - w if anchor == "end" else x - w / 2 if anchor == "middle" else x
    return (x0, x0 + w, y - 9, y + 3)


def page(model):
    out = subprocess.run(
        ["node", "-e", FIL, os.path.join(PAGE, "dashboard.js")],
        input=json.dumps(model),
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if out.returncode:
        raise AssertionError(out.stderr[:800])
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which("node"), "needs node to run the page's script")
class FilePageTest(unittest.TestCase):
    def test_the_page_draws_a_dot_per_file_under_seven_stations(self):
        m = drawn(FILES)
        got = page(m)
        self.assertEqual(got["dots"], len(FILES))
        self.assertEqual(got["kinds"], [k["n"] for k in m["kinds"]])
        self.assertEqual(got["groups"], len(m["groups"]))
        self.assertEqual((got["pills"], got["plasmid"], got["ribo"]), (7, 1, 2))
        self.assertEqual(got["view"], f"0 {m['geo']['top']:g} 1236 {m['geo']['height']:g}")
        self.assertEqual(got["rows"], 1 + len(m["groups"]))
        for words in (
            f"{len(FILES)} files in the repository, each drawn once",
            f"{sum(FILES.values()):,} lines in all",
            "written down first",
            "tried on the code",
            "checked afterwards",
            "Drawn from the file list at abc1234",
        ):
            self.assertIn(words, got["words"])
        for words in (
            "The goal",
            "A Day's spec",
            "A promise",
            "The re-check",
            "on no station",
            "tests/ 3",
        ):
            self.assertIn(words, got["figure"])
        # the folders named as placing themselves are folders the table places whole, never scripts/
        self.assertIn("tests/ at station 4", got["words"])
        self.assertIn("hooks/ at station 5", got["words"])
        self.assertNotIn("scripts/ at station", got["words"])

    def test_the_graph_has_its_own_key_and_points_at_no_other_graph(self):
        got = page(drawn(FILES))
        for words in (
            "check by an AI reviewer",
            "check by a script",
            "check by a person",
            "the writer",
            "written text",
            "a test of the tooling",
            "25, 100 and 400 lines",
        ):
            self.assertIn(words, got["key"])
        marks, writer, dots = got["keyMarks"]
        self.assertGreaterEqual(marks, 4)  # a diamond, a square and the person's two halves
        self.assertEqual(writer, 2)
        self.assertGreaterEqual(dots, 5)
        html = real("docs", "dashboard", "index.html")
        section = html[html.index('<section class="graph" id="fil">') :]
        section = section[: section.index("</section>")]
        self.assertIn("fil-key", section)
        text = (got["words"] + got["label"] + section).lower()
        for gone in ("graph above", "folded below", "the panel it was"):
            self.assertNotIn(gone, text)

    def test_the_page_draws_the_improve_loop_back_to_each_brief_with_cases(self):
        m = files.file_map(dict(FILES, **LOOP), table(), "abc1234", briefs=BRIEFS)
        got = page(m)
        self.assertEqual(
            got["loop"], [1, 3, 1], "one line, an arrow for each column it lands on, and its key"
        )
        self.assertEqual(got["view"], f"0 {files.LOOP_TOP:g} 1236 {m['geo']['height']:g}")
        self.assertIn("the improve loop", got["figure"])
        self.assertIn("the improve loop, only when the maintainer asks", got["key"])
        self.assertIn(
            "spec-auditor at the spec-auditor's check, reviewer at station 5 and track-reviewer at "
            "the track-reviewer's check",
            got["words"],
        )
        # a repository with no case set has no loop: no line, no key for it, no word about it
        plain = page(drawn(FILES))
        self.assertEqual(plain["loop"], [0, 0, 0])
        self.assertNotIn("improve loop", plain["words"] + plain["figure"])

    def test_the_maps_words_and_marks_stand_at_their_columns_in_two_rows(self):
        # every station's pill, the ribosome and every check's name at its column's x; what each station is in the
        # cell on row A, under the pills; who checks on row B, below it; on each row no two texts' boxes overlap;
        # the first group's label below row B's small words; in the cytoplasm each column's dots clear of the next's
        col, got = files.COLUMNS, page(drawn(FILES))
        stations = [col[f"s{n}"]["x"] for n in range(1, 8)]
        self.assertEqual(
            (got["pillsAt"], sorted(set(got["riboAt"]))), (stations, [col["implementer"]["x"]])
        )
        names = {"plan-auditor": "plan-auditor", "spec-auditor": "spec-auditor", "implementer": "implementer",
                 "track-reviewer": "track-reviewer", "CI's checks": "ci", "defect-rater": "defect-rater"}  # fmt: skip
        at = {t[1]: t[2] for t in got["at"] if t[0] == "t-g" and t[1] in names}
        off = sorted(w for w, k in names.items() if at.get(w) != col[k]["x"])
        self.assertEqual(off, [])
        rows = [t for t in got["at"] if t[0] in PER and 190 < t[3] < 262]
        row_a = [
            t[3]
            for t in rows
            if t[0] == "t-bio" and t[1] in ("the gene", "negative control", "the protein,")
        ]
        row_b = [t[3] for t in rows if t[0] == "t-g"]
        self.assertEqual(
            (len(row_a), len(row_b) >= 7, min(row_b) > max(row_a) + 12), (3, True, True)
        )
        clash = sorted(
            sorted([a[1], b[1]])
            for i, a in enumerate(rows)
            for b in rows[i + 1 :]
            if abs(a[3] - b[3]) < 1
            and words_box(a)[0] < words_box(b)[1]
            and words_box(b)[0] < words_box(a)[1]
        )
        self.assertEqual(clash, [])
        below = max(t[3] for t in rows)
        first = min(g["y"] for g in drawn(FILES)["groups"])
        self.assertEqual((first - below >= 14, first == files.FIRST_Y), (True, True))
        tried = sorted(
            (c["x"], c.get("w", files.WIDTH), k) for k, c in col.items() if c["zone"] == "try"
        )
        touching = [
            [a[2], b[2]] for a, b in itertools.pairwise(tried) if a[0] + a[1] / 2 >= b[0] - b[1] / 2
        ]
        self.assertEqual(touching, [])

    def test_every_check_is_drawn_at_its_columns_x(self):
        # a diamond at the track-reviewer's column, and each check's mark centred where its files hang
        checks = ("plan-auditor", "spec-auditor", "track-reviewer", "ci", "defect-rater")
        self.assertEqual([c for c in checks if c not in files.COLUMNS], [])
        got = page(drawn(FILES))
        diamonds = sorted(x for tag, x in got["chk"] if tag == "path")
        marks = [x for _, x in got["chk"]]
        off = [c for c in checks if not any(abs(x - files.COLUMNS[c]["x"]) < 0.6 for x in marks)]
        self.assertEqual(off, [])
        self.assertEqual(
            len(diamonds), 4, "plan-auditor, spec-auditor, track-reviewer, defect-rater"
        )
        self.assertIn("track-reviewer", got["figure"])

    def test_no_columns_row_can_reach_its_neighbours(self):
        # the widest row of two neighbouring columns keeps 6 px between them; unittest shortens a long list, so the
        # count and the first pair
        cols = sorted(files.COLUMNS.items(), key=lambda kv: kv[1]["x"])
        pairs = [
            [ka, kb]
            for (ka, a), (kb, b) in itertools.pairwise(cols)
            if a["x"] + a.get("w", files.WIDTH) / 2 + 6 > b["x"] - b.get("w", files.WIDTH) / 2
        ]
        self.assertEqual((len(pairs), pairs[:1]), (0, []))

    def test_a_file_the_table_does_not_place_is_named_on_the_page(self):
        got = page(drawn(dict(FILES, **{"scripts/brand-new.py": 77})))
        self.assertEqual(got["dots"], len(FILES) + 1)
        self.assertIn("1 file is in the ring because the table does not place it", got["words"])
        self.assertIn("scripts/brand-new.py", got["words"])
        self.assertNotIn("because the table does not place", page(drawn(FILES))["words"])

    def test_with_no_table_the_page_says_so_and_draws_no_dot(self):
        got = page({"empty": "`docs/dashboard/file-stations.json` could not be read."})
        self.assertEqual(got["dots"], 0)
        self.assertIn("Not measured yet", got["words"])
        self.assertIn("could not be read", got["words"])

    def test_the_map_stands_where_the_three_old_views_stood(self):
        html, script, style = (
            real("docs", "dashboard", name)
            for name in ("index.html", "dashboard.js", "dashboard.css")
        )
        self.assertEqual(html.count('<section class="graph" id="fil"'), 1)
        self.assertIn("<h2>Where does each file belong?</h2>", html)
        for gone in (
            'id="cel"',
            'id="g11-fold"',
            'id="g11"',
            'id="how-fold"',
            'id="how-this-works"',
            "#how-step-",
        ):
            self.assertNotIn(gone, html)
        for gone in ("function celDraw", "function drawHow", "function howSteps", "g11-plot"):
            self.assertNotIn(gone, script)
        for gone in ("#cel ", ".how-step", ".run-plot"):
            self.assertNotIn(gone, style)
        self.assertIn("filDraw(DATA.file_map", script)


if __name__ == "__main__":
    unittest.main()
