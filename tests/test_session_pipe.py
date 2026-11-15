"""A session's stdout pipe is closed by run_session when the session ends, not left to the garbage
collector: its ResourceWarning reached the driver's stderr in some runs and not others, and the
Day 10 breaks' reports changed with it."""

import gc
import importlib
import os
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

once = importlib.import_module("driver.once")


class SessionPipeTest(unittest.TestCase):
    def test_session_end_leaves_no_open_pipe(self):
        state = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(state, ignore_errors=True))
        args = SimpleNamespace(state=state, session_minutes=1, poll=5, docker="docker", gh="gh")
        record = {"session": "s1", "step": None}
        command = [sys.executable, "-c", "import sys; sys.stdin.read(); print('done')"]
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always")
            out, code = once.run_session(command, "go", args, os.getcwd(), 1, record)
            gc.collect()
        leaks = [str(w.message) for w in seen if issubclass(w.category, ResourceWarning)]
        self.assertEqual((out.strip(), code, leaks), (b"done", 0, []))


if __name__ == "__main__":
    unittest.main()
