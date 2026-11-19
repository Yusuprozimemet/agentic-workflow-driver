"""status with no reviewer session in the run log prints the block as before: the line after
`cost:` is the `level 2:` line. Track B of Day 14 adds the reviewer's line there, and only when the
log holds a review `start` line. This test holds that today, so the reviewer line cannot leak into
runs that never had a reviewer. The file also holds Track B's row and reviewer line, tested below."""

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

from driver import status
from tests.test_github import fake_gh
from tests.test_status import T1, T2, T3, encode, end, start
from tests.test_status_trial import LEVEL_2, after_cost


def review_start(session, at):
    # A start line of a review session: the prefix is the only change from a step's start line.
    record = dict(start(session, "Step A", at))
    record["prefix"] = "review"
    return record


def verdict(session, pr):
    return {
        "event": "review",
        "at": T1,
        "pr": pr,
        "session": session,
        "head": "abc1234",
        "blockers": 1,
    }


def row_of(stdout, number):
    # The line number rows after the steps: line.
    lines = stdout.splitlines()
    return lines[lines.index("steps:") + number]


def label(row, at):
    # The text between the row's time and its first colon: the step's label.
    return row[len(f"  {at} ") :].split(":")[0]


LOG = [
    start("s1", "Step A", T1),
    end("s1", "opened: #20", 0.25, 0),
    review_start("r1", T2),
    verdict("r1", 7),
    end("r1", "review: #7, 1 blockers", 0.4, 0),
]


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

    def test_review_row(self):
        self.write_log(LOG)
        done = self.status()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("steps:", done.stdout.splitlines())
        row = row_of(done.stdout, 2)
        # The short comparison comes first, so the red report stays short.
        self.assertEqual(label(row, T2), "review of #7")
        self.assertEqual(
            row, f"  {T2} review of #7: review: #7, 1 blockers, $0.40, refusals 0, session `r1`"
        )

    def test_review_row_without_review_line(self):
        self.write_log(
            [
                start("s1", "Step A", T1),
                end("s1", "opened: #20", 0.25, 0),
                review_start("r1", T2),
                end("r1", "crashed", 0.1, 0),
            ]
        )
        done = self.status()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("steps:", done.stdout.splitlines())
        row = row_of(done.stdout, 2)
        self.assertEqual(label(row, T2), "review of an unknown pull request")
        self.assertEqual(
            row,
            f"  {T2} review of an unknown pull request: crashed, $0.10, refusals 0, session `r1`",
        )

    def test_reviewer_cost_line(self):
        records = LOG + [
            review_start("r2", T3),
            verdict("r2", 8),
            end("r2", "review: #8, 0 blockers", 0.3, 0),
        ]
        self.assertEqual(
            status._reviewer(records), "reviewer: 2 sessions, $0.70, in the cost above"
        )
        self.assertIsNone(
            status._reviewer([start("s1", "Step A", T1), end("s1", "opened: #20", 0.25, 0)])
        )
        self.write_log(records)
        done = self.status()
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.splitlines()
        costs = [line for line in lines if line.startswith("cost: ")]
        self.assertEqual(len(costs), 1, "no cost line")
        # The total still counts both reviews: 0.25 + 0.40 + 0.30.
        self.assertTrue(costs[0].startswith("cost: $0.95,"), costs[0])
        following = after_cost(lines)
        self.assertIsNotNone(following, "no cost line")
        self.assertEqual(following[0], "reviewer: 2 sessions, $0.70, in the cost above")
        self.assertEqual(following[1].split(":")[0], "level 2")
