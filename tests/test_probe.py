"""The write probe, hooks/probe.py, run as the reach check runs it in the session's container (C10.10)."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIMEOUT = 60


class ProbeTest(unittest.TestCase):
    def test_written_and_refused(self):
        # C10.10: a folder it can write to is written, a missing one is refused, in that order,
        # exit 0, and the writable folder is left empty. Fails on main: hooks/probe.py is missing.
        self.assertTrue((ROOT / "hooks" / "probe.py").exists(), "hooks/probe.py does not exist")
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "missing")
            try:
                done = subprocess.run(
                    [sys.executable, str(ROOT / "hooks" / "probe.py"), tmp, missing],
                    capture_output=True,
                    check=False,
                    timeout=TIMEOUT,
                )
            except subprocess.TimeoutExpired:
                self.fail(f"hooks/probe.py did not finish in {TIMEOUT} seconds")
            # The folders are replaced by placeholders before the lines are compared.
            text = done.stdout.decode("utf-8")
            lines = [
                line.replace(missing, "<tmp>/missing").replace(tmp, "<tmp>")
                for line in text.splitlines()
            ]
            self.assertEqual(
                (done.returncode, lines, os.listdir(tmp)),
                (0, ["written <tmp>", "refused <tmp>/missing"], []),
            )
