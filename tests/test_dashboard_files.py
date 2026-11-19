"""The dashboard's file map, "Where does each file belong?" (scripts/spec_drift_files.py, filDraw in dashboard.js):
every tracked file is one dot under the station it serves, a folder places itself, a script is placed by the table
in docs/dashboard/file-stations.json, and a file the table does not place is drawn in the ring, never dropped.
The page tests need node."""

import importlib.util
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


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, file))
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
    "tests/test_a.py": 120, "tests/test_b.py": 60, "tests/__init__.py": 0,
    "driver/decide.py": 200, "run-steps.py": 40, "hooks/readonly.py": 30, ".github/workflows/tests.yml": 50,
    "scripts/seen-red.py": 150, "scripts/test_seen_red.py": 90, "scripts/spec-drift.py": 316,
    "scripts/spec_drift_views.py": 1980, "scripts/test_spec_drift_views.py": 10, "scripts/test_diff_limit.py": 40,
    "docs/lab-notebook.md": 300, "docs/kit.md": 100, "README.md": 80, "docs/dashboard/index.html": 800,
    ".gitignore": 10, "pyproject.toml": 20,
}  # fmt: skip


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
        test, row = home(m, "scripts/test_seen_red.py")
        self.assertIs(test, script)
        self.assertEqual(kinds[row[2]], "tooltest")
        # a test named in the table hangs where the table says, whatever script its name starts like
        self.assertEqual(
            home(m, "scripts/test_diff_limit.py")[0]["at"], "CI's checks, after station 5"
        )
        # a pattern in the table takes a module, and that module's test follows it
        self.assertEqual(home(m, "scripts/spec_drift_views.py")[0]["label"], "dashboard")
        self.assertEqual(home(m, "scripts/test_spec_drift_views.py")[0]["label"], "dashboard")

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

    def test_the_build_puts_it_in_the_data(self):
        self.assertIn('real["file_map"] = build_file_map(', real("scripts", "spec-drift.py"))


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
     keyMarks: [is(key, ["chk"]), is(key, ["ribo"]), is(key, ["f"])], view: f.attrs.viewBox || "", label: f.attrs["aria-label"] || "",
     key: words(key).replace(/\\s+/g, " "), rows: all($("fil-table")).filter(e => e.tag === "tr").length,
     words: ["fil-figs", "fil-key", "fil-hint", "fil-table", "fil-stamp", "fil-how", "fil-scroll"].map(id => words($(id))).join(" ").replace(/\\s+/g, " "),
     figure: words(f).replace(/\\s+/g, " ") })`, ctx)));
"""


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
