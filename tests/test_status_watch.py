"""status --watch prints the status again at each poll while a session is live, and once when none
is. Each test runs the CLI as a person runs it, on a state folder and a scratch project of its own,
with a fake gh beside it. A child process stands for the live session; the test ends it."""

import datetime
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver import lock
from tests.test_github import fake_gh

T1 = "2026-11-08T10:00:00Z"
WAIT = 30


def encode(record):
    # Bytes, as the driver writes them: text mode would add a carriage return on Windows.
    return (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")


def pump(stream, lines):
    # Each line goes to the queue as it is read; None marks the end of the stream.
    for line in stream:
        lines.put(line.rstrip("\r\n"))
    lines.put(None)


class StatusWatchTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.project = os.path.join(self.root, "project")
        os.makedirs(self.project)
        self.state = os.path.join(self.root, "state")
        self.folder = Path(self.root, "gh")
        self.folder.mkdir()
        self.gh = fake_gh(self.folder)
        self.child = None

    def command(self, *extra):
        return [
            sys.executable,
            str(ROOT / "run-steps.py"),
            "status",
            "--project",
            self.project,
            "--state",
            self.state,
            "--gh",
            self.gh,
            *extra,
        ]

    def write_log(self, records):
        os.makedirs(self.state, exist_ok=True)
        Path(self.state, "run.jsonl").write_bytes(b"".join(encode(record) for record in records))

    def start_live(self):
        # A child process that lives, a run log that starts session s1 and names the child, and an
        # events file for s1 with one line.
        self.child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        self.addCleanup(self.child.wait)
        self.addCleanup(self.child.kill)
        now = lock.now()
        started = now.strftime(lock.STAMP)
        self.write_log(
            [
                {
                    "event": "start",
                    "at": (now - datetime.timedelta(seconds=5)).strftime(lock.STAMP),
                    "step": "Day 11 Track A: x",
                    "prefix": "day-11/track-a",
                    "session": "s1",
                    "claude": "claude",
                },
                {
                    "event": "pid",
                    "at": T1,
                    "session": "s1",
                    "pid": self.child.pid,
                    "started": started,
                },
            ]
        )
        os.makedirs(os.path.join(self.state, "sessions"), exist_ok=True)
        event = {"at": started, "kind": "system init"}
        Path(self.state, "sessions", "s1.events.jsonl").write_bytes(encode(event))

    def snapshot(self):
        # The state folder's files and folders by their path under it, sorted; empty when it is absent.
        names = []
        for folder, subfolders, files in os.walk(self.state):
            for name in subfolders + files:
                names.append(os.path.relpath(os.path.join(folder, name), self.state))
        return sorted(names)

    def watch_live(self):
        # Runs status --watch while the child lives: reads the first block, ends the child, then reads
        # what the watch prints after it. Returns (first block's lines, the rest, return code, stderr).
        proc = subprocess.Popen(
            self.command("--watch", "--poll", "0.5"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        self.addCleanup(proc.kill)
        lines = queue.Queue()
        threading.Thread(target=pump, args=(proc.stdout, lines), daemon=True).start()
        first = []
        while True:
            line = self.next_line(lines)
            self.assertIsNotNone(line, "status ended before the first block's last line")
            first.append(line)
            if line.startswith("level 2: "):
                break
        # The first block showed the session live, so status prints at least one more; the child
        # ends now, so a later block finds no session.
        self.child.kill()
        self.child.wait(timeout=WAIT)
        rest = []
        while True:
            line = self.next_line(lines)
            if line is None:
                break
            rest.append(line)
        try:
            code = proc.wait(timeout=WAIT)
        except subprocess.TimeoutExpired:
            self.fail("status --watch did not end within 30 s")
        stderr = proc.stderr.read()
        proc.stdout.close()
        proc.stderr.close()
        return first, rest, code, stderr

    def next_line(self, lines):
        try:
            return lines.get(timeout=WAIT)
        except queue.Empty:
            self.fail("status --watch printed no line for 30 s")

    def test_status_shows_progress(self):
        self.start_live()
        done = subprocess.run(
            self.command(), check=False, capture_output=True, text=True, encoding="utf-8"
        )
        lines = done.stdout.splitlines()
        found = [index for index, line in enumerate(lines) if line.startswith("in progress: ")]
        self.assertEqual(len(found), 1)
        index = found[0]
        self.assertTrue(lines[index].endswith("cost so far $0.00"), lines[index])
        following = lines[index + 1 : index + 4]
        self.assertEqual(len(following), 3)
        self.assertTrue(following[0].startswith("running: "), following[0])
        self.assertTrue(following[1].startswith("last event: system init, "), following[1])
        self.assertEqual(following[2], "tokens so far: 0 in, 0 out")
        self.assertEqual(done.returncode, 0)

    def test_watch_until_the_session_ends(self):
        self.start_live()
        first, rest, code, _ = self.watch_live()
        in_progress = [line for line in first if line.startswith("in progress: ")]
        self.assertEqual(len(in_progress), 1)
        self.assertIn("(session `s1`)", in_progress[0])
        self.assertTrue(rest, "status --watch printed nothing after its first block")
        self.assertEqual(rest[0], "")
        blocks = [[]]
        for line in first + rest:
            if line == "":
                blocks.append([])
            else:
                blocks[-1].append(line)
        self.assertGreaterEqual(len(blocks), 2)
        self.assertIn("in progress: none", blocks[-1])
        self.assertEqual(code, 0)

    def test_watch_with_nothing_running(self):
        self.write_log(
            [
                {
                    "event": "start",
                    "at": T1,
                    "step": "Day 11 Track A: x",
                    "prefix": "day-11/track-a",
                    "session": "s1",
                    "claude": "claude",
                },
                {
                    "event": "end",
                    "at": T1,
                    "session": "s1",
                    "outcome": "opened: #20",
                    "cost_usd": 0.4,
                    "denials": 0,
                },
            ]
        )
        done = subprocess.run(
            self.command("--watch", "--poll", "0.5"),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=WAIT,
        )
        lines = done.stdout.splitlines()
        self.assertNotIn("", lines)
        self.assertEqual(sum(1 for line in lines if line.startswith("level 2: ")), 1)
        self.assertIn("in progress: none", lines)
        self.assertEqual(done.returncode, 0)

    def test_watch_creates_nothing(self):
        self.start_live()
        before = self.snapshot()
        first, rest, code, _ = self.watch_live()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(code, 0)
        self.assertTrue(first)
        self.assertTrue(rest)
        self.write_log(
            [
                {
                    "event": "start",
                    "at": T1,
                    "step": "Day 11 Track A: x",
                    "prefix": "day-11/track-a",
                    "session": "s2",
                    "claude": "claude",
                },
            ]
        )
        before = self.snapshot()
        done = subprocess.run(
            self.command("--watch", "--poll", "0.5"),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=WAIT,
        )
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(done.returncode, 0)


if __name__ == "__main__":
    unittest.main()
