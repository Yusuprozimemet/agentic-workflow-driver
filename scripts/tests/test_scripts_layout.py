"""scripts/README.md indexes every script under one concern, and only the held tests stay beside them.

    python scripts/tests/test_scripts_layout.py
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(HERE, "README.md")

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


class ScriptsLayoutTest(unittest.TestCase):
    def scripts(self):
        return sorted(n for n in os.listdir(HERE) if n.endswith(".py") and not n.startswith("test_"))

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
        self.assertEqual(headings, CONCERNS)
        self.assertEqual(sorted(name for heading, name in rows if heading not in CONCERNS), [])

    def test_only_the_held_tests_stay_in_scripts(self):
        here = sorted(n for n in os.listdir(HERE) if n.startswith("test_") and n.endswith(".py"))
        self.assertEqual(here, HELD)
        folder = os.path.join(HERE, "tests")
        self.assertTrue(any(n.startswith("test_") and n.endswith(".py") for n in os.listdir(folder)))
        self.assertFalse(os.path.exists(os.path.join(folder, "__init__.py")))


if __name__ == "__main__":
    unittest.main()
