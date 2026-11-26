"""scripts/close-views.py prints a closing PR's defect views from the Notes' Defect lines alone.

One small day spec, written the way specs/README.md ("Record every defect") asks, with an escape,
a `made: none`, a found: value off the list, and two lines an earlier layer could have caught.

    python scripts/test_close_views.py
"""

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("close_views", os.path.join(HERE, "close-views.py"))
close_views = importlib.util.module_from_spec(spec)
spec.loader.exec_module(close_views)

SPEC = """# Day 44 — a fixture

## Notes

- Not a defect · cause: spec.
- **Defect** D44.1 — found: auditor · cause: spec · made: Day 44 · catchable: auditor · C44.2
  counted 9 files; there are 11.
- **Defect** D44.2 — found: close · cause: spec · made: Day 44 · catchable: auditor · the grep
  counted comments.
- **Defect** D44.3 — found: Track A · cause: implementation · made: Day 42 · catchable: seen red ·
  Day 42's parser dropped the last line.
- **Defect** D44.4 — found: self · cause: process · made: none · catchable: self · a branch
  named after the wrong Day.
- **Defect** D44.5 — found: live run · cause: environment · made: Day 44 · the runner ran out
  of disk.
"""

NOTEBOOK = """- **Defects:** 5. auditor 1, Track A 1, self 1, close 1; off the found: list: live run 1 (D44.5).
  Causes: spec 2, implementation 1, process 1, environment 1. Escapes: 1, from Day 42 (D44.3).
  Catchable earlier: 2 of 5 (D44.2 found by close, catchable by auditor; D44.3 found by Track A, catchable by seen red); 1 with no `catchable:` (D44.5)."""

ESCAPES = "1: 1 from Day 42 (D44.3); D44.4 is `made: none`; 3 of the 5 are `made: Day 44`"

PR = """## Defects

From the Notes' 5 Defect lines, by `scripts/close-views.py`.

- Found: auditor 1, Track A 1, self 1, close 1; off the found: list: live run 1 (D44.5)
- Cause: spec 2, implementation 1, process 1, environment 1
- Escapes: D44.3 (made: Day 42): Day 42's parser dropped the last line.
- An earlier layer could have caught: D44.2 (found: close, catchable: auditor): the grep counted comments.
- An earlier layer could have caught: D44.3 (found: Track A, catchable: seen red): Day 42's parser dropped the last line.
- No catchable: D44.5"""


class CloseViewsTest(unittest.TestCase):
    def run_on(self, text, name="day-44-a-fixture.md"):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, name)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = close_views.main([path])
        return code, out.getvalue()

    def test_three_views_from_the_notes(self):
        code, out = self.run_on(SPEC)
        self.assertEqual(code, 0)
        want = (
            "Notebook, the Day's entry:\n"
            + NOTEBOOK
            + "\n\nNotebook, Escapes per day:\n"
            + ESCAPES
            + "\n\nClosing PR body:\n"
            + PR
            + "\n"
        )
        # The first line that differs, whole: unittest would shorten a long one to "[N chars]".
        for i, (got, line) in enumerate(zip(out.split("\n"), want.split("\n")), 1):
            if got != line:
                self.fail(f"line {i}: printed {got!r}, want {line!r}")
        self.assertEqual(out.count("\n"), want.count("\n"))

    def test_no_escape_and_no_catchable(self):
        text = """## Notes

- **Defect** D45.1 — found: auditor · cause: spec · made: Day 45 · one.
- **Defect** D45.2 — found: auditor · cause: spec · made: Day 45 · two.
"""
        code, out = self.run_on(text, "day-45-b.md")
        self.assertEqual(code, 0)
        self.assertIn(
            "- **Defects:** 2. auditor 2.\n  Causes: spec 2. Escapes: 0.\n"
            "  Catchable earlier: 0 of 2; no line has a `catchable:`.",
            out,
        )
        self.assertIn("\n0: all 2 are `made: Day 45`\n", out)
        self.assertIn("- Escapes: none\n", out)

    def test_an_at_field_keeps_the_cause_after_it(self):
        text = """## Notes

- **Defect** D46.1 — found: track-reviewer · at: Track A brief · cause: process · made: Day 46 ·
  catchable: auditor · the brief named the wrong file (#1).
"""
        rows = close_views.read(text)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].get("cause"), rows[0].get("catchable")), ("process", "auditor"))
        self.assertEqual(rows[0]["text"], "the brief named the wrong file (#1).")
        code, out = self.run_on(text, "day-46-c.md")
        self.assertEqual(code, 0)
        self.assertIn("  Causes: process 1.", out)

    def test_no_defect_line(self):
        code, out = self.run_on("## Notes\n\n- nothing found.\n", "day-46-c.md")
        self.assertEqual(code, 1)
        self.assertEqual(out, "no Defect line in day-46-c.md\n")


if __name__ == "__main__":
    unittest.main()
