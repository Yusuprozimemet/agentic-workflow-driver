"""status's progress lines for a live review (C15.12) name its pull request: from the review's start line
when it has one, else from the newest review line of the session, else "an unknown pull request". A
track's estimate counts only the sessions of its own kind (C15.13). The status tests run the CLI on a
state folder with a live session's pid line; the track test calls progress with a fixed now."""

import datetime
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

from driver import lock, status
from tests.test_github import fake_gh
from tests.test_status import T1, encode

TRACK_STEP = "Day 15 Track C"
TRACK = "day-15/track-c"
T1_TIME = lock.stamp_time(T1)


def start_line(session, prefix, at, pr=None):
    # A track's step is named as review.run passes it, so the step's sentence never reads "review of #12".
    record = {
        "event": "start",
        "at": at,
        "step": TRACK_STEP,
        "prefix": prefix,
        "session": session,
        "claude": "claude",
    }
    if pr is not None:
        record["pr"] = pr
    return record


def end_line(session, at):
    return {
        "event": "end",
        "at": at,
        "session": session,
        "outcome": "review: #12, 0 blockers",
        "cost_usd": 0,
        "denials": 0,
    }


def earlier_reviews():
    # Three ended review sessions, e0, e1 and e2, of 600, 1200 and 2400 seconds, an hour apart.
    records = []
    for i, length in enumerate([600, 1200, 2400]):
        begun = T1_TIME + datetime.timedelta(hours=i)
        ended = begun + datetime.timedelta(seconds=length)
        records.append(start_line(f"e{i}", "review", begun.strftime(lock.STAMP)))
        records.append(end_line(f"e{i}", ended.strftime(lock.STAMP)))
    return records


def verdict_line(session, pr):
    return {
        "event": "review",
        "at": T1,
        "pr": pr,
        "session": session,
        "head": "abc1234",
        "blockers": 0,
    }


class ReviewProgressTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.project = os.path.join(self.root, "project")
        os.makedirs(self.project)
        self.state = os.path.join(self.root, "state")
        self.folder = Path(self.root, "gh")
        self.folder.mkdir()

    def live_pid(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        return child.pid

    def live_log(self, records):
        # The records, then a pid line that keeps session r1 live: its process is this test's child.
        now = lock.now().strftime(lock.STAMP)
        records = [
            *records,
            {"event": "pid", "at": now, "session": "r1", "pid": self.live_pid(), "started": now},
        ]
        os.makedirs(self.state, exist_ok=True)
        Path(self.state, "run.jsonl").write_bytes(b"".join(encode(record) for record in records))

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

    def line(self, done, prefix):
        # The first line of the output that starts with the prefix, or a line that says none does.
        for text in done.stdout.splitlines():
            if text.startswith(prefix):
                return text
        return "no line " + prefix

    def test_live_review_line(self):
        self.live_log([start_line("r1", "review", lock.now().strftime(lock.STAMP), pr=12)])
        done = self.status()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(
            self.line(done, "in progress:"),
            "in progress: review of #12 (session `r1`), cost so far $0.00",
        )
        running = self.line(done, "running:")
        self.assertIn(" (", running)
        self.assertEqual(running.split(" (", 1)[1], "no estimate: 0 earlier review sessions)")

    def test_review_estimate(self):
        self.live_log(
            [*earlier_reviews(), start_line("r1", "review", lock.now().strftime(lock.STAMP), pr=12)]
        )
        done = self.status()
        self.assertEqual(done.returncode, 0, done.stderr)
        running = self.line(done, "running:")
        self.assertIn(" (", running)
        self.assertEqual(
            running.split(" (", 1)[1],
            "estimate 20m00s, the median of 3 earlier review sessions)",
        )
        self.assertEqual(
            self.line(done, "in progress:"),
            "in progress: review of #12 (session `r1`), cost so far $0.00",
        )

    def test_no_pr_on_the_start(self):
        self.live_log([start_line("r1", "review", lock.now().strftime(lock.STAMP))])
        done = self.status()
        self.assertEqual(done.returncode, 0, done.stderr)
        progress_line = self.line(done, "in progress:")
        self.assertIn(" (session", progress_line)
        self.assertEqual(
            progress_line.split(" (session")[0], "in progress: review of an unknown pull request"
        )
        self.assertEqual(progress_line.split(" (session")[1], " `r1`), cost so far $0.00")
        running = self.line(done, "running:")
        self.assertIn(" (", running)
        self.assertEqual(running.split(" (", 1)[1], "no estimate: 0 earlier review sessions)")

    def test_pr_from_review_line(self):
        self.live_log(
            [start_line("r1", "review", lock.now().strftime(lock.STAMP)), verdict_line("r1", 12)]
        )
        done = self.status()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(
            self.line(done, "in progress:"),
            "in progress: review of #12 (session `r1`), cost so far $0.00",
        )
        running = self.line(done, "running:")
        self.assertIn(" (", running)
        self.assertEqual(running.split(" (", 1)[1], "no estimate: 0 earlier review sessions)")

    def test_track_counts_no_review(self):
        # Review sessions are not earlier track sessions: the track's estimate counts none of them.
        now = lock.now()
        at = (now - datetime.timedelta(seconds=725)).strftime(lock.STAMP)
        records = [*earlier_reviews(), start_line("run", TRACK, at)]
        running = status.progress(records, "run", [], now)[0]
        self.assertIn(" (", running)
        self.assertEqual(running.split(" (", 1)[1], "no estimate: 0 earlier track sessions)")
