"""scripts/test-parallel.py keeps what a failure printed, and --repeat counts a flaky file's failures.

Two flaky failures (D07.27, D08.81) were seen once, their output not kept, and their cause is still
unknown. Each test builds a scratch tests/ and points the runner's paths at it.

    python scripts/test_test_parallel.py
"""
import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))

FAILS = "import unittest\n\nclass T(unittest.TestCase):\n    def test_it(self):\n        self.assertEqual(1, 2)\n"
PASSES = "import unittest\n\nclass T(unittest.TestCase):\n    def test_it(self):\n        pass\n"
# Fails on its second run only: a counter file beside it.
FLAKY = ("import pathlib, unittest\n\nN = pathlib.Path(__file__).with_name('runs')\n\n"
         "class T(unittest.TestCase):\n    def test_it(self):\n"
         "        n = int(N.read_text()) + 1 if N.exists() else 1\n        N.write_text(str(n))\n"
         "        self.assertNotEqual(n, 2, 'the second run')\n")


def load():
    spec = importlib.util.spec_from_file_location("test_parallel", os.path.join(HERE, "test-parallel.py"))
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    return script


class TestParallelTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "tests").mkdir()
        self.script = load()
        state = self.root / ".claude" / "state"
        for name, value in (("ROOT", self.root), ("TESTS", self.root / "tests"),
                            ("TIMES", state / "test-times.json"), ("FAILURES", state / "test-failures")):
            patch = mock.patch.object(self.script, name, value, create=True)
            patch.start()
            self.addCleanup(patch.stop)

    def write(self, name, text):
        (self.root / "tests" / name).write_text(text, encoding="utf-8")

    def main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.script.main(list(argv))
        return code, out.getvalue()

    def test_a_failing_file_s_output_is_kept_and_its_path_printed(self):
        self.write("test_fails.py", FAILS)
        self.write("test_passes.py", PASSES)
        code, out = self.main()
        self.assertEqual(code, 1)
        failures = self.root / ".claude" / "state" / "test-failures"
        kept = list(failures.iterdir()) if failures.exists() else []
        self.assertEqual(len(kept), 1, kept)
        self.assertIn("test_fails", kept[0].name)
        self.assertIn("AssertionError: 1 != 2", kept[0].read_text(encoding="utf-8"))
        self.assertIn(f"kept: {kept[0]}", out)

    def test_repeat_counts_how_often_each_file_failed(self):
        self.write("test_flaky.py", FLAKY)
        self.write("test_passes.py", PASSES)
        code, out = self.main("--repeat", "3", "-j", "1")
        self.assertEqual(code, 1)
        self.assertIn("test_flaky.py failed 1 of 3", out)
        self.assertNotIn("test_passes.py failed", out)
        self.assertIn("Ran 6 tests", out)


if __name__ == "__main__":
    unittest.main()
