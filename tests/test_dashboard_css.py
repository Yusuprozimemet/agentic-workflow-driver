"""The dashboard's stylesheet: one top-level rule per class, so a graph's bar style cannot
silently restyle another graph's bars (graph 9's `.bar` once collapsed graphs 6 and 7)."""

import re
import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "docs" / "dashboard"
CLASS = re.compile(r"^\.[A-Za-z0-9_-]+$")


def top_level_rules(css):
    """The selector list of every rule at the sheet's top level, in order, each split on commas.

    Rules inside an at-rule block (`@media`, `@supports`) are left out: redeclaring a class
    there is how a sheet adapts, not a collision."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    rules, depth, start = [], 0, 0
    for i, ch in enumerate(css):
        if ch == "{":
            if depth == 0:
                head = css[start:i].strip()
                if not head.startswith("@"):
                    rules.append([s.strip() for s in head.split(",") if s.strip()])
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                start = i + 1
        elif ch == ";" and depth == 0:
            start = i + 1
    return rules


def declared_twice(css):
    """The classes that head more than one top-level rule on their own (`.name { ... }` twice).

    A class named in a comma group and then in a rule of its own shares the group's style and
    adds to it; two rules of its own are two declarations, and the later one wins unseen."""
    seen, twice = set(), []
    for rule in top_level_rules(css):
        if len(rule) == 1 and CLASS.match(rule[0]):
            if rule[0] in seen and rule[0] not in twice:
                twice.append(rule[0])
            seen.add(rule[0])
    return twice


class StylesheetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.css = (PAGE / "dashboard.css").read_text(encoding="utf-8")
        cls.script = (PAGE / "dashboard.js").read_text(encoding="utf-8")

    def test_the_parser_sees_only_top_level_rules(self):
        css = ".a { x: 1 } .b, .a span { x: 2 } @media (max-width: 1px) { .a { x: 3 } } .c { } .b { } .a { }"
        self.assertEqual(top_level_rules(css), [[".a"], [".b", ".a span"], [".c"], [".b"], [".a"]])
        self.assertEqual(declared_twice(css), [".a"])

    def test_no_top_level_class_is_declared_twice(self):
        self.assertEqual(declared_twice(self.css), [])

    def test_graph_9_bars_have_their_own_class(self):
        self.assertIn("\n.lane-bar {", self.css)
        self.assertIn("class: `lane-bar ${b.cls}`", self.script)
        self.assertNotIn("class: `bar ${b.cls}`", self.script)


if __name__ == "__main__":
    unittest.main()
