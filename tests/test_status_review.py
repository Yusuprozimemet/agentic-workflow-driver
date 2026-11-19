"""status with no reviewer session in the run log prints the block as before: the line after
`cost:` is the `level 2:` line. Track B of Day 14 adds the reviewer's line there, and only when the
log holds a review `start` line. This test holds that today, so the reviewer line cannot leak into
runs that never had a reviewer."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_github import fake_gh
from tests.test_status import T1, encode, end, start
from tests.test_status_trial import LEVEL_2, after_cost


class StatusReviewTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.project = os.path.join(self.root, "project")
        os.makedirs(self.project)
        self.state = os.path.join(self.root, "state")
        self.folder = Path(self.root, "gh")
        self.folder.mkdir()

    def status(self):
        gh = fake_gh(self.folder, issues=[])
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "run-steps.py"),
                "status",
                "--project",
                self.project,
                "--state",
                self.state,
                "--gh",
                gh,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

    def write_log(self, records):
        os.makedirs(self.state, exist_ok=True)
        Path(self.state, "run.jsonl").write_bytes(b"".join(encode(record) for record in records))

    def test_no_reviewer_line_without_review(self):
        # start gives the prefix "day-07": a step session, not a review session.
        self.write_log([start("s1", "Step A", T1), end("s1", "opened: #20", 0.25, 0)])
        done = self.status()
        self.assertEqual(done.returncode, 0, done.stderr)
        following = after_cost(done.stdout.splitlines())
        self.assertIsNotNone(following, "no cost line")
        # The short comparison comes first: the break must reach it, and a long string would be
        # shortened by unittest's report.
        self.assertEqual(following[0].split(":")[0], "level 2")
        self.assertEqual(following[0], LEVEL_2.format(0))
        self.assertEqual(
            [line for line in done.stdout.splitlines() if line.startswith("reviewer")], []
        )
