"""scripts/break-lines.py prints a branch's break lines from its record and checks a spec's against it.

Each test builds a scratch git repository with a main commit and a day-12/ branch, writes a break
manifest as break.py --record writes it, and runs the script there.

    python scripts/test_break_lines.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "break-lines.py")
MANIFEST = "specs/breaks/day-12.json"


def entry(what="the guard off", report="AssertionError: the guard is off", **more):
    return {"what": what, "file": "guard.py", "find": "ok = True", "replace": "ok = False",
            "command": ["python", "-m", "unittest", "tests.test_guard"], "report": report,
            "blob": "0" * 40, **more}


def spec(*lines):
    criteria = "".join(f"- [x] C12.{n} **hold** — the guard holds.\n      {line}\n" for n, line in enumerate(lines, 1))
    return f"# Day 12\n\n## Acceptance criteria\n{criteria}\n## Notes\n\nbroken: outside → ignored\n"


class Scratch(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        git = lambda *a: subprocess.run(["git", *a], cwd=self.dir, check=True, capture_output=True)
        self.git = git
        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@localhost")
        git("config", "user.name", "t")
        self.manifest([entry(what="an earlier track's break")])
        git("add", "-A")
        git("commit", "-q", "-m", "main")
        git("checkout", "-q", "-b", "day-12/track-a-guard")

    def manifest(self, entries):
        os.makedirs(os.path.join(self.dir, "specs", "breaks"), exist_ok=True)
        with open(os.path.join(self.dir, MANIFEST), "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entries))

    def run_it(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], cwd=self.dir, capture_output=True, text=True,
                              encoding="utf-8")


class PrLinesTest(Scratch):
    def test_the_branch_s_recorded_breaks_print_as_break_py_printed_them(self):
        self.manifest([entry(what="an earlier track's break"), entry()])
        run = self.run_it()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertEqual(run.stdout.count("manifest:"), 1, "an entry main already holds printed too")
        manifest = {k: v for k, v in entry().items() if k not in ("report", "blob")}
        self.assertEqual(run.stdout.splitlines(), ["manifest: " + json.dumps(manifest, ensure_ascii=False),
                                                   "broken: the guard off → AssertionError: the guard is off"])

    def test_a_re_recorded_break_prints_again(self):
        self.manifest([entry(what="an earlier track's break", report="AssertionError: again")])
        run = self.run_it()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("broken: an earlier track's break → AssertionError: again", run.stdout)

    def test_nothing_recorded_on_the_branch_fails(self):
        run = self.run_it()
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("no break recorded in specs/breaks/day-12.json on this branch", run.stdout)

    def test_an_entry_with_no_report_is_named_not_printed(self):
        self.manifest([entry(what="an earlier track's break"), {k: v for k, v in entry().items() if k != "report"}])
        run = self.run_it()
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("no report for 'the guard off'", run.stderr)


class SpecCheckTest(Scratch):
    def check(self, text, entries):
        self.manifest(entries)
        with open(os.path.join(self.dir, "specs", "day-12-guard.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return self.run_it("--spec", "specs/day-12-guard.md")

    def test_a_line_that_matches_its_record_passes_its_pr_number_aside(self):
        run = self.check(spec("broken: the guard off → AssertionError: the guard is off (#12)"), [entry()])
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("matches: the guard off (C12.1)", run.stdout)
        self.assertIn("break-lines: 1 of 1 broken: lines in specs/day-12-guard.md agree", run.stdout)

    def test_a_line_with_no_entry_fails(self):
        # bearing D10.20: two lines had no entry.
        run = self.check(spec("broken: the guard gone → AssertionError: the guard is off"), [entry()])
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("no entry: the guard gone (C12.1)", run.stdout)
        self.assertIn("not in the spec: broken: the guard off → AssertionError: the guard is off", run.stdout)

    def test_a_report_other_than_the_recorded_one_fails(self):
        # bearing D10.20: one line ended in "(close, D10.19)".
        run = self.check(spec("broken: the guard off → AssertionError: the guard is off (close, D10.19)"), [entry()])
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("differs: the guard off (C12.1): the spec says 'AssertionError: the guard is off "
                      "(close, D10.19)', recorded 'AssertionError: the guard is off'", run.stdout)

    def test_a_name_recorded_twice_fails(self):
        # bearing D10.20: two breaks shared a name.
        run = self.check(spec("broken: the guard off → AssertionError: the guard is off"), [entry(), entry()])
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("recorded 2 times: the guard off (C12.1)", run.stdout)

    def test_an_entry_copied_by_hand_is_unchecked_and_none_is_skipped(self):
        hand = {k: v for k, v in entry().items() if k not in ("report", "blob")}
        run = self.check(spec("broken: the guard off → anything", "broken: none → a reader judged it"), [hand])
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("unchecked: the guard off (C12.1)", run.stdout)
        self.assertIn("break-lines: 1 of 1 broken: lines", run.stdout)


if __name__ == "__main__":
    unittest.main()
