"""scripts/seen-red.py runs the branch's tests on the base's code, and reports red only when they fail.

Each test builds a scratch repository with a one-line module and a test of it on main, then
changes the test or the module in the working tree and runs seen-red.py there as a subprocess.

    python scripts/test_seen_red.py
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen-red.py")
CHECK = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."]
TEST = """import unittest
from app import double

class T(unittest.TestCase):
    def test_double(self):
        self.assertEqual(double(2), 4)
"""
NEW_TEST = TEST + """
    def test_double_a_string(self):
        self.assertEqual(double("ab"), "abab")
"""


class SeenRedTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.write("app.py", "def double(x):\n    return x * 2 if isinstance(x, int) else x\n")
        self.write("tests/__init__.py", "")
        self.write("tests/test_app.py", TEST)
        self.git("add", ".")
        self.git("commit", "-q", "-m", "base")

    def tearDown(self):
        subprocess.run(["git", "worktree", "prune"], cwd=self.dir)
        shutil.rmtree(self.dir, ignore_errors=True)

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.dir, check=True, capture_output=True)

    def write(self, path, text):
        os.makedirs(os.path.dirname(os.path.join(self.dir, path)), exist_ok=True)
        with open(os.path.join(self.dir, path), "w", newline="\n") as f:
            f.write(text)

    def seen_red(self, *extra, check=CHECK):
        return subprocess.run([sys.executable, SCRIPT, *extra, "--", *check], cwd=self.dir,
                              capture_output=True, text=True, encoding="utf-8")

    def test_a_new_test_that_fails_on_the_base_is_seen_red_though_it_passes_here(self):
        self.write("app.py", "def double(x):\n    return x * 2\n")
        self.write("tests/test_app.py", NEW_TEST)
        here = subprocess.run(CHECK, cwd=self.dir, capture_output=True, text=True)
        self.assertEqual(here.returncode, 0, here.stderr)
        run = self.seen_red()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(run.stdout.startswith("seen red: "), run.stdout)
        self.assertIn(" on main → AssertionError: 'ab' != 'abab'", run.stdout)

    def test_an_untracked_test_file_is_copied_in(self):
        self.write("tests/test_more.py", "import unittest\nfrom app import triple\n\n"
                                         "class M(unittest.TestCase):\n    def test_it(self):\n        triple(1)\n")
        run = self.seen_red()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("seen red: ", run.stdout)

    def test_a_root_tests_py_is_copied_in(self):
        # python-json-pointer keeps its tests in one tests.py at the root, not under tests/
        self.git("rm", "-q", "-r", "tests")
        self.write("tests.py", TEST)
        self.git("add", ".")
        self.git("commit", "-q", "-m", "tests at the root")
        self.write("app.py", "def double(x):\n    return x * 2\n")
        self.write("tests.py", NEW_TEST)
        run = self.seen_red(check=[sys.executable, "-m", "unittest", "tests"])
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn(" on main → AssertionError: 'ab' != 'abab'", run.stdout)

    def test_code_under_tests_named_in_the_project_file_is_not_copied_in(self):
        # A fixture builder under tests/ is the code under test: copied in, the base has it too.
        self.write("tests/fixtures/build.py", "")
        self.write("tests/test_build.py", "import subprocess, sys, unittest\n\n"
                                          "class B(unittest.TestCase):\n    def test_it(self):\n"
                                          "        run = subprocess.run([sys.executable, 'tests/fixtures/build.py'])\n"
                                          "        self.assertEqual(run.returncode, 0)\n")
        self.assertEqual(self.seen_red().returncode, 1)
        self.write("spec-drift.config.json", '{"code_under_tests": ["^tests/fixtures/"]}\n')
        run = self.seen_red()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn(" on main → AssertionError: 2 != 0", run.stdout)

    def test_a_new_test_that_passes_on_the_base_is_refused(self):
        self.write("tests/test_app.py", TEST + "\n    def test_zero(self):\n        self.assertEqual(double(0), 0)\n")
        run = self.seen_red()
        self.assertEqual(run.returncode, 1)
        self.assertIn("does not see the change", run.stdout)
        self.assertNotIn("seen red:", run.stdout)

    def test_no_changed_test_is_refused_and_the_worktree_is_left_alone(self):
        self.write("app.py", "def double(x):\n    raise SystemExit(1)\n")
        run = self.seen_red()
        self.assertEqual(run.returncode, 2)
        self.assertIn("no new test to see red", run.stderr)
        with open(os.path.join(self.dir, "app.py")) as f:
            self.assertIn("SystemExit", f.read())

    def test_a_module_the_change_adds_is_not_served_by_an_editable_install(self):
        # pip install -e serves the package from the working tree through a finder on sys.meta_path;
        # the base must not import the module the change adds from there (bearing, Day 8 track A).
        self.write("pyproject.toml", '[build-system]\nrequires = ["setuptools>=64"]\n'
                                     'build-backend = "setuptools.build_meta"\n\n'
                                     '[project]\nname = "pkg"\nversion = "0"\n\n'
                                     '[tool.setuptools.packages.find]\ninclude = ["pkg*"]\n')
        self.write("pkg/__init__.py", "")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "a package")
        venv = os.path.realpath(tempfile.mkdtemp())  # venv warns on a Windows short (8.3) path
        self.addCleanup(shutil.rmtree, venv, True)
        subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", venv], check=True)
        python = os.path.join(venv, "Scripts" if os.name == "nt" else "bin", "python")
        # Offline when setuptools is at hand; a runner's bare Python has none, and pip fetches it.
        isolation = ["--no-build-isolation"] if importlib.util.find_spec("setuptools") else []
        installed = subprocess.run([python, "-m", "pip", "install", "-q", "--no-deps", *isolation, "-e", self.dir],
                                   capture_output=True, text=True)
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        self.write("pkg/extra/__init__.py", "def triple(x):\n    return x * 3\n")
        self.write("tests/test_extra.py", "import unittest\n\nclass E(unittest.TestCase):\n"
                                          "    def test_it(self):\n        from pkg.extra import triple\n"
                                          "        self.assertEqual(triple(2), 6)\n")
        served = subprocess.run([python, "-c", "import pkg.extra"], cwd=venv, capture_output=True, text=True)
        self.assertEqual(served.returncode, 0, served.stderr)  # the finder serves pkg.extra from anywhere
        run = self.seen_red(check=[python, "-m", "unittest", "tests.test_extra"])
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn(" on main → FAILED (errors=1)", run.stdout)  # the ImportError of pkg.extra

    def test_the_scratch_worktree_is_removed(self):
        self.write("tests/test_app.py", NEW_TEST)
        self.seen_red()
        listed = subprocess.run(["git", "worktree", "list"], cwd=self.dir, capture_output=True, text=True).stdout
        self.assertEqual(len(listed.strip().splitlines()), 1, listed)


if __name__ == "__main__":
    unittest.main()
