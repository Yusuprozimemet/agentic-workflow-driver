"""scripts/brief-check.py finds a name a brief puts in the wrong file, before the implementer does.

Each test builds a scratch git repository and runs the script there as a subprocess.

    python scripts/tests/test_brief_check.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "brief-check.py")


class BriefCheckTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.write("tests/test_dry_run.py", "def commit_file(repo, name):\n    pass\n")
        self.write("tests/test_tree.py", "import unittest\n\nclass TreeTest(unittest.TestCase):\n    pass\n")
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)
        subprocess.run(["git", "add", "."], cwd=self.dir, check=True)

    def write(self, path, text):
        full = os.path.join(self.dir, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def brief(self, text):
        self.write("brief.md", text)
        subprocess.run(["git", "add", "."], cwd=self.dir, check=True)
        return subprocess.run([sys.executable, SCRIPT, "brief.md"], cwd=self.dir, capture_output=True,
                              text=True, encoding="utf-8")

    def test_a_name_in_the_wrong_file_is_refused(self):
        # D07.24: the brief said `commit_file` is in tests/test_tree.py.
        run = self.brief("- Import `commit_file` from `tests/test_tree.py` for the fixture.\n")
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("line 1: `commit_file` is defined in tests/test_dry_run.py, not in tests/test_tree.py",
                      run.stdout)

    def test_a_name_in_its_file_and_a_new_file_pass(self):
        run = self.brief("- Import `commit_file()` from `tests/test_dry_run.py`.\n"
                         "- Create `tests/test_new.py` with `NewTest`, beside `TreeTest` in `tests/test_tree.py`.\n")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("not in the tree (a file the brief creates?): line 2: `tests/test_new.py`", run.stdout)
        self.assertIn("brief-check: 2 names found where the brief says", run.stdout)

    def test_a_name_imported_from_another_file_is_refused(self):
        # D07.24 as it stood: tests/test_tree.py imports `commit_file`; it is defined elsewhere.
        self.write("tests/test_tree.py", "from tests.test_dry_run import commit_file\n\ncommit_file(1, 2)\n")
        run = self.brief("- Import `commit_file` from `tests/test_tree.py` for the fixture.\n")
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("line 1: `commit_file` is defined in tests/test_dry_run.py, not in tests/test_tree.py",
                      run.stdout)

    def test_a_module_or_an_event_the_file_uses_passes(self):
        # D09.32: `once` is a module driver/loop.py imports, `park` an event it writes; both are
        # defined, under the same names, in other files.
        self.write("driver/loop.py", 'from driver import once\n\n\ndef run(log):\n    once.go()\n    log("park")\n')
        self.write("tests/test_once.py", "def once():\n    pass\n")
        self.write("driver/runlog.py", 'park = "park"\n')
        run = self.brief("- In `driver/loop.py`, `once` writes a `park` line.\n")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("brief-check: 2 names found where the brief says", run.stdout)

    def test_a_signature_change_names_the_callers_the_brief_misses(self):
        # D09.28: a new argument of `_steps` broke tests/test_trial_record.py, which the brief did not name.
        self.write("driver/status.py", "def _steps(rows):\n    return rows\n")
        self.write("tests/test_trial_record.py", "from driver import status\n\nstatus._steps([])\n")
        run = self.brief("- Give `_steps` in `driver/status.py` a new argument `late`.\n")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("callers the brief does not name: line 1: `_steps` is called in tests/test_trial_record.py",
                      run.stdout)
        named = self.brief("- Give `_steps` in `driver/status.py` a new argument `late`; "
                           "update `tests/test_trial_record.py`.\n")
        self.assertNotIn("callers the brief does not name", named.stdout)


if __name__ == "__main__":
    unittest.main()
