"""The kit's .flake8 leaves scripts/ out of a copy's lint: they are in the kit's style, not the project's.

    python scripts/test_lint_config.py
"""
import configparser
import importlib.util
import os
import subprocess
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


class Flake8Test(unittest.TestCase):
    def test_the_shipped_config_leaves_scripts_out(self):
        # the comparison's run A: S1A had to exclude scripts/ before its whole-tree flake8 passed.
        config = configparser.ConfigParser()
        config.read(os.path.join(ROOT, ".flake8"))
        excluded = config.get("flake8", "extend-exclude", fallback="").split(",")
        self.assertIn("scripts", [e.strip() for e in excluded])

    @unittest.skipUnless(importlib.util.find_spec("flake8"), "flake8 is not installed")
    def test_flake8_from_the_root_reports_nothing_in_scripts(self):
        run = subprocess.run([sys.executable, "-m", "flake8", "--count", "scripts"], cwd=ROOT,
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout[-500:])


if __name__ == "__main__":
    unittest.main()
