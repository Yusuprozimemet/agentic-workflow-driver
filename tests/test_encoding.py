"""The driver's output is UTF-8 whatever the locale says: run-steps.py writes its stdout and stderr
as UTF-8 when they are not a console, and the checks read the kit's output with bad bytes replaced.
Each test builds a project whose spec-drift.py writes a byte that is not UTF-8 to its stdout, or
runs the driver with a Windows-1252 PYTHONIOENCODING and a pipe for its stdout."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import SCRIPT, drift_of, make_project
from tests.test_preflight import fake_cli

# The fixture's spec-drift.py: it writes the drift it was given to --out, then a line whose dash is
# the Windows-1252 byte 0x96. The escape stays in the script, so the child writes that byte itself.
NOT_UTF8_SCRIPT = r"""import argparse
import json
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--out")
parser.add_argument("--cache")
args = parser.parse_args()
with open(args.out, "w", encoding="utf-8") as f:
    json.dump(json.loads({drift!r}), f)
sys.stdout.buffer.write(b"next: Day 02 Track B: C02.4\x96C02.6\n")
"""


class EncodingTest(unittest.TestCase):
    def temp_dir(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def not_utf8_project(self):
        drift = drift_of("Day 02 Track B: C02.4–C02.6")
        script = NOT_UTF8_SCRIPT.format(drift=json.dumps(drift))
        return make_project(self.temp_dir(), script=script)

    def test_drift_output_not_utf8(self):
        project = self.not_utf8_project()
        cmd = [sys.executable, str(SCRIPT), "--dry-run", "--project", str(project)]
        done = subprocess.run(cmd, check=False, capture_output=True)
        self.assertEqual(done.stderr, b"")
        self.assertEqual(done.returncode, 0)
        out = done.stdout.decode("utf-8").replace("\r\n", "\n")
        self.assertEqual(out, "start: Day 02 Track B: C02.4–C02.6\n")

    def test_preflight_output_not_utf8(self):
        project = self.not_utf8_project()
        program = fake_cli(self.temp_dir())
        cmd = [
            sys.executable,
            str(SCRIPT),
            "preflight",
            "--project",
            str(project),
            "--claude",
            program,
        ]
        done = subprocess.run(cmd, check=False, capture_output=True)
        self.assertEqual(done.stderr, b"")
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout.decode("utf-8").replace("\r\n", "\n"), "preflight: ok\n")

    def test_stdout_is_utf8_in_a_pipe(self):
        project = make_project(self.temp_dir(), drift_of("Day 01 Track A: C01.1–C01.3"))
        # The parent's locale says Windows-1252 and the child is told so; a pipe still gets UTF-8.
        env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
        env.pop("PYTHONUTF8", None)
        cmd = [sys.executable, str(SCRIPT), "--dry-run", "--project", str(project)]
        done = subprocess.run(cmd, check=False, capture_output=True, env=env)
        self.assertEqual(done.returncode, 0)
        expected = "start: Day 01 Track A: C01.1–C01.3".encode() + os.linesep.encode()
        self.assertEqual(done.stdout, expected)
        self.assertEqual(done.stderr, b"")


if __name__ == "__main__":
    unittest.main()
