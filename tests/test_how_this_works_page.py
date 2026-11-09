"""The dashboard's "How this works" panel on the page: where it sits, and that an excerpt the
build could not read shows as missing."""

import re
import shutil
import subprocess
import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "docs" / "dashboard"


class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (PAGE / "index.html").read_text(encoding="utf-8")
        cls.script = (PAGE / "dashboard.js").read_text(encoding="utf-8")

    def panel(self):
        return re.search(
            r'<section class="panel" id="how-this-works">.*?</section>', self.html, re.DOTALL
        ).group(0)

    def test_the_panel_sits_folded_under_the_graphs(self):
        order = [
            self.html.index(f'id="{name}"') for name in ("g2", "g8", "how-fold", "how-this-works")
        ]
        self.assertEqual(order, sorted(order))
        self.assertRegex(self.html, r'<details class="fold" id="how-fold">\s*<summary>')

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's function")
    def test_step_seven_says_when_there_is_no_recheck(self):
        def part(pattern):
            return re.search(pattern, self.script, re.MULTILINE | re.DOTALL).group(0)

        code = "\n".join(
            [
                part(r"^const esc = .*?$"),
                part(r"^const howHas = .*?$"),
                part(r"^function howMissing\(.*?^}$"),
                part(r"^function howExcerpt\(.*?^}$"),
                part(r"^function howRecheck\(.*?^}$"),
            ]
        )
        code += """
console.log(howRecheck({source: "r", text: {pr: null, checks: []}}, "C1.1"));
console.log("---");
console.log(howRecheck({source: "r", text: {pr: 7, checks: [{check: "T.a", state: "pass"}]}}, "C1.1"));
console.log("---");
console.log(howRecheck({source: "r", missing: "the file is missing or empty"}, "C1.1"));
"""
        out = subprocess.run(
            ["node", "-e", code], capture_output=True, text=True, encoding="utf-8", check=True
        ).stdout
        none, some, gone = out.split("---")
        self.assertIn("not re-checked yet", none)
        self.assertNotIn("at its latest re-check", none)
        self.assertIn("C1.1 at its latest re-check, the merge of PR #7", some)
        self.assertIn("T.a", some)
        self.assertNotIn("not re-checked yet", some)
        self.assertIn("Missing from this build: r (the file is missing or empty)", gone)
        self.assertNotIn("not re-checked yet", gone)

    def test_the_panel_needs_no_diagram_library(self):
        self.assertNotIn("mermaid", (self.html + self.script).lower())

    def test_who_does_what_is_collapsed(self):
        self.assertRegex(
            self.panel(), r"<details class=\"technical\">\s*<summary>Who does what</summary>"
        )

    def test_the_promise_board_links_to_the_steps_that_prove_a_promise(self):
        board = re.search(
            r'<section class="graph" id="g2">.*?</section>', self.html, re.DOTALL
        ).group(0)
        self.assertEqual(
            re.findall(r'<a href="#how-step-(\w+)" data-how="(\w+)">', board),
            [("red", "red"), ("bug", "bug"), ("close", "close"), ("recheck", "recheck")],
        )
        # Each link names a step the walk-through draws.
        for step in ("red", "bug", "close", "recheck"):
            self.assertIn(f'{{ id: "{step}", kind:', self.script)

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's function")
    def test_a_missing_excerpt_shows_as_missing_on_the_page(self):
        def part(pattern):
            return re.search(pattern, self.script, re.MULTILINE | re.DOTALL).group(0)

        code = "\n".join(
            [
                part(r"^const esc = .*?$"),
                part(r"^const howHas = .*?$"),
                part(r"^function howMissing\(.*?^}$"),
                part(r"^function howExcerpt\(.*?^}$"),
            ]
        )
        code += """
console.log(howExcerpt({source: "plan.md", missing: "the file is missing or empty"}, "A caption"));
console.log("---");
console.log(howExcerpt(undefined, "Another caption"));
console.log("---");
console.log(howExcerpt({source: "plan.md", text: "<kept>"}, "Found"));
"""
        out = subprocess.run(
            ["node", "-e", code], capture_output=True, text=True, check=True
        ).stdout
        gone, absent, found = out.split("---")
        self.assertIn("Missing from this build: plan.md (the file is missing or empty)", gone)
        self.assertNotIn("<pre>", gone)
        self.assertIn("Missing from this build", absent)
        self.assertIn("<pre>&lt;kept&gt;</pre>", found)
        self.assertNotIn("Missing", found)


if __name__ == "__main__":
    unittest.main()
