"""What the page's script keeps for the promise the build follows: the words for its re-check,
and that an excerpt the build could not read shows as missing."""

import re
import shutil
import subprocess
import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "docs" / "dashboard"


# The walk-through builds nodes, not HTML: a document whose nodes print as tags around their escaped text.
DOCUMENT = """
const document = { createElement: tag => ({ tag, kids: [], style: {}, setAttribute() {}, append(...c) { this.kids.push(...c); }, set className(v) {} }) };
const html = n => typeof n === "string" ? n.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") : `<${n.tag}>${n.kids.map(html).join("")}</${n.tag}>`;
"""


class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (PAGE / "index.html").read_text(encoding="utf-8")
        cls.script = (PAGE / "dashboard.js").read_text(encoding="utf-8")

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's function")
    def test_step_seven_says_when_there_is_no_recheck(self):
        def part(pattern):
            return re.search(pattern, self.script, re.MULTILINE | re.DOTALL).group(0)

        code = "\n".join(
            [
                part(r"^const esc = .*?$"),
                DOCUMENT,
                part(r"^function h\(.*?^}$"),
                part(r"^const howHas = .*?$"),
                part(r"^const howMissing = .*?$"),
                part(r"^const howExcerpt = .*?$"),
                part(r"^function howRecheck\(.*?^}$"),
            ]
        )
        code += """
console.log(html(howRecheck({source: "r", text: {pr: null, checks: []}}, "C1.1")));
console.log("---");
console.log(html(howRecheck({source: "r", text: {pr: 7, checks: [{check: "T.a", state: "pass"}]}}, "C1.1")));
console.log("---");
console.log(html(howRecheck({source: "r", missing: "the file is missing or empty"}, "C1.1")));
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

    @unittest.skipUnless(shutil.which("node"), "needs node to run the page's function")
    def test_a_missing_excerpt_shows_as_missing_on_the_page(self):
        def part(pattern):
            return re.search(pattern, self.script, re.MULTILINE | re.DOTALL).group(0)

        code = "\n".join(
            [
                part(r"^const esc = .*?$"),
                DOCUMENT,
                part(r"^function h\(.*?^}$"),
                part(r"^const howHas = .*?$"),
                part(r"^const howMissing = .*?$"),
                part(r"^const howExcerpt = .*?$"),
            ]
        )
        code += """
console.log(html(howExcerpt({source: "plan.md", missing: "the file is missing or empty"}, "A caption")));
console.log("---");
console.log(html(howExcerpt(undefined, "Another caption")));
console.log("---");
console.log(html(howExcerpt({source: "plan.md", text: "<kept>"}, "Found")));
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
