"""scripts/README.md indexes every script under one concern, the page's data builder sits in
scripts/pipeline/ in a folder per concern, and only the held tests stay beside the commands.

    python scripts/tests/test_scripts_layout.py
"""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(HERE, "README.md")
PIPELINE = os.path.join(HERE, "pipeline")

CONCERNS = [
    "The dashboard's data: sources",
    "The dashboard's data: counts",
    "The dashboard's data: build",
    "Counts from outside git",
    "Gates on a pull request",
    "Seen red and breaks on purpose",
    "The close",
    "Guards on a session",
    "Agents with cases",
]

# The folder of scripts/pipeline/ that holds each concern's modules, and the folders a module there may
# import from: a source reads, a count counts what the sources read, the build draws both.
FOLDERS = {
    "The dashboard's data: sources": "sources",
    "The dashboard's data: counts": "counts",
    "The dashboard's data: build": "build",
}
MAY_IMPORT = {"sources": {"sources"}, "counts": {"sources", "counts"}, "build": {"sources", "counts", "build"}}

HELD = [
    "test_dashboard_page.py",  # Day 14's break record runs it by this module name (C14.9)
    "test_setup_check.py",  # Day 10's break record runs it by this path (C10.29)
    "test_token_usage.py",  # frozen by C16.19, a hold in force
]


def readme_rows():
    """(heading, name) for each table row of scripts/README.md, and the ## headings in order."""
    rows, headings, heading = [], [], None
    with open(README, encoding="utf-8") as f:
        for line in f:
            if line.startswith("## "):
                heading = line[3:].strip()
                headings.append(heading)
                continue
            cell = re.match(r"\|\s*`([^`]+\.py)`\s*\|", line)
            if cell:
                rows.append((heading, cell.group(1)))
    return rows, headings


def pipeline_modules():
    """{module's file name: its folder} for every module under scripts/pipeline/<folder>/."""
    found = {}
    for folder in sorted(os.listdir(PIPELINE)) if os.path.isdir(PIPELINE) else ():
        if os.path.isdir(os.path.join(PIPELINE, folder)) and not folder.startswith("__"):
            found.update({n: folder for n in os.listdir(os.path.join(PIPELINE, folder)) if n.endswith(".py")})
    return found


class ScriptsLayoutTest(unittest.TestCase):
    def scripts(self):
        """The commands beside this folder, and the pipeline's modules as the index names them."""
        beside = [n for n in os.listdir(HERE) if n.endswith(".py") and not n.startswith("test_")]
        return sorted(beside + [f"pipeline/{folder}/{name}" for name, folder in pipeline_modules().items()])

    def test_the_index_names_every_script_once(self):
        self.assertTrue(os.path.isfile(README), "scripts/README.md is missing")
        names = [name for _, name in readme_rows()[0]]
        twice = sorted({n for n in names if names.count(n) > 1})
        self.assertEqual(twice, [], "named more than once")
        self.assertEqual(sorted(set(self.scripts()) - set(names)), [], "scripts the index lacks")
        self.assertEqual(sorted(set(names) - set(self.scripts())), [], "named but not in scripts/")

    def test_every_script_sits_under_a_concern(self):
        self.assertTrue(os.path.isfile(README), "scripts/README.md is missing")
        rows, headings = readme_rows()
        # The differences, not the two lists: unittest shortens a long list, and break.py refuses such a report.
        self.assertEqual([h for h in headings if h not in CONCERNS], [], "headings that are no concern")
        self.assertEqual([c for c in CONCERNS if c not in headings], [], "concerns with no heading")
        self.assertEqual([CONCERNS.index(h) for h in headings], list(range(len(CONCERNS))), "the concerns' order")
        self.assertEqual(sorted(name for heading, name in rows if heading not in CONCERNS), [])

    def test_only_the_held_tests_stay_in_scripts(self):
        here = sorted(n for n in os.listdir(HERE) if n.startswith("test_") and n.endswith(".py"))
        self.assertEqual(here, HELD)
        folder = os.path.join(HERE, "tests")
        self.assertTrue(any(n.startswith("test_") and n.endswith(".py") for n in os.listdir(folder)))
        # A package would shadow the driver's tests/, and a script here would have no station and no index row.
        self.assertEqual(sorted(n for n in os.listdir(folder) if n.endswith(".py") and not n.startswith("test_")), [])

    def test_the_pages_data_builder_sits_in_the_pipeline_by_concern(self):
        beside = sorted(n for n in os.listdir(HERE) if re.fullmatch(r"spec_drift_\w+\.py", n))
        # the first one, so that the failure stays short
        self.assertEqual(beside[:1], [], "modules of spec-drift.py still beside the commands")
        modules = pipeline_modules()
        self.assertEqual(sorted(set(modules.values()) - set(FOLDERS.values())), [], "folders that are no concern")
        # each module is indexed under the concern its folder is named for
        indexed = {name: heading for heading, name in readme_rows()[0] if name.startswith("pipeline/")}
        wrong = sorted(n for n, h in indexed.items() if FOLDERS.get(h) != n.split("/")[1])
        self.assertEqual(wrong, [], "indexed under another concern than their folder's")
        self.assertEqual(len(indexed), len(modules))
        self.assertGreater(len(modules), 0, "scripts/pipeline/ holds no module")
        # the folders hold modules only: importing the package puts them on the path, they are no packages
        inits = [f for f in FOLDERS.values() if os.path.exists(os.path.join(PIPELINE, f, "__init__.py"))]
        self.assertEqual(inits, [])

    def test_a_pipeline_module_imports_only_from_the_folders_before_its_own(self):
        modules, edges, wrong = pipeline_modules(), 0, []
        for name, folder in sorted(modules.items()):
            with open(os.path.join(PIPELINE, folder, name), encoding="utf-8") as f:
                imports = set(re.findall(r"^\s*(?:from|import)\s+(spec_drift_\w+)", f.read(), re.M))
            for other in sorted(imports):
                edges += 1
                if modules.get(other + ".py") not in MAY_IMPORT[folder]:
                    wrong.append(f"{folder}/{name} imports {other} ({modules.get(other + '.py')})")
        self.assertEqual(wrong, [])
        self.assertGreater(edges, 10, "too few imports read for this to have checked anything")

    def test_a_moved_module_still_finds_what_it_read_from_beside_the_commands(self):
        # Each module finds the project's files from its own place, and a config or a cache looked for in the
        # wrong folder is no error, only an empty one: the places are held here.
        sys.path.insert(0, HERE)
        self.addCleanup(sys.path.remove, HERE)
        import pipeline  # noqa: F401
        import spec_drift_common as common
        import spec_drift_files as files
        import spec_drift_plan as plan

        root = os.path.dirname(HERE)
        found = dict(config=common.CONFIG_FILE, page=common.PAGE, cache=common.CACHE_FILE, table=files.TABLE,
                     commands=plan.HERE)
        want = dict(config=os.path.join(root, "spec-drift.config.json"), page=os.path.join(root, "docs", "dashboard"),
                    cache=os.path.join(root, ".spec-drift-cache.json"),
                    table=os.path.join(root, "docs", "dashboard", "file-stations.json"), commands=HERE)
        place = lambda p: os.path.normcase(os.path.normpath(p))  # noqa: E731
        self.assertEqual([name for name in want if place(found[name]) != place(want[name])], [])
        self.assertTrue(os.path.isfile(want["config"]) and os.path.isfile(want["table"]))


if __name__ == "__main__":
    unittest.main()
