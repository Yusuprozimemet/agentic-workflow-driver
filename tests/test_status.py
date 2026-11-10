"""status prints where the driver is, from the state folder and the project's open issues, and
changes nothing. Each test runs the CLI as a person runs it, on a state folder and a scratch project
of its own, with a fake gh beside it, and compares the lines it prints."""

import json
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

from driver import lock
from tests.test_github import fake_gh, read_calls

T1 = "2026-11-08T10:00:00Z"
T2 = "2026-11-08T11:00:00Z"
T3 = "2026-11-08T12:00:00Z"
LEVEL_2_NONE = "level 2: 0 of 15 pull requests in a row merged without a change asked"

ISSUES = [
    {
        "number": 12,
        "title": "Driver run 2026-11-08T09:00:00Z",
        "labels": [],
        "state": "open",
        "author": "me",
    },
    {"number": 14, "title": "park: x", "labels": ["parked"], "state": "open", "author": "me"},
    {"number": 15, "title": "park: y", "labels": ["parked"], "state": "open", "author": "me"},
    {"number": 16, "title": "a note", "labels": [], "state": "open", "author": "me"},
    {
        "number": 30,
        "title": "Driver run 2026-11-08T10:00:00Z",
        "labels": [],
        "state": "open",
        "author": "me",
    },
]


def encode(record):
    # Bytes, as the driver writes them: text mode would add a carriage return on Windows.
    return (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")


def start(session, step, at):
    return {
        "event": "start",
        "at": at,
        "step": step,
        "prefix": "day-07",
        "session": session,
        "claude": "claude",
    }


def end(session, outcome, cost, denials, at=T1):
    return {
        "event": "end",
        "at": at,
        "session": session,
        "outcome": outcome,
        "cost_usd": cost,
        "denials": denials,
    }


def park(line):
    return {"event": "park", "at": T1, "step": "Day 07 Track A: the run log", "line": line}


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.project = os.path.join(self.root, "project")
        os.makedirs(self.project)
        self.state = os.path.join(self.root, "state")
        self.folder = Path(self.root, "gh")
        self.folder.mkdir()

    def status(self, state=None, issues=ISSUES, issue_code=0):
        gh = fake_gh(self.folder, issues=issues, issue_code=issue_code)
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "run-steps.py"),
                "status",
                "--project",
                self.project,
                "--state",
                state or self.state,
                "--gh",
                gh,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def write_log(self, records, state=None):
        state = state or self.state
        os.makedirs(state, exist_ok=True)
        Path(state, "run.jsonl").write_bytes(b"".join(encode(record) for record in records))

    def write_lock(self, pid, started=None, state=None):
        state = state or self.state
        os.makedirs(state, exist_ok=True)
        started = started or lock.now().strftime(lock.STAMP)
        body = json.dumps({"pid": pid, "started": started})
        Path(lock.path(state)).write_bytes(body.encode("utf-8"))

    def live_pid(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        return child.pid

    def gone_pid(self):
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait(timeout=10)
        return child.pid

    def snapshot(self):
        # The state folder's files by their path under it, as bytes; empty when it does not exist.
        found = {}
        for folder, _, names in os.walk(self.state):
            for name in names:
                path = os.path.join(folder, name)
                found[os.path.relpath(path, self.state)] = Path(path).read_bytes()
        return found

    def test_full_report(self):
        self.write_log(
            [
                start("s1", "Day 07 Track A: the run log", T1),
                end("s1", "park: tried", 0.5, 1),
                {"event": "fix", "at": T1, "session": "s1", "pr": 20, "n": 1},
                end("s1", "opened: #20 from `day-07/track-a-x`", 0.7, 0),
                start("s2", "Day 07 Track B: the lock", T2),
                start("s3", "Day 07 Track C: x", T3),
                end("s3", "park: y", None, 2, at=T3),
                park(
                    "park: the session ended with no pull request and no PARK line (session `s2`)"
                ),
                park(
                    "park: the session ended with no pull request and no PARK line (session `s3`)"
                ),
                park("park: pull request #14 is stuck"),
                park("park: pull request #15 is stuck"),
                park("park: the project's tree is not clean (2 paths)"),
                park("park: the project's tree is not clean (3 paths)"),
                park("park: a one-off"),
                {"event": "merged", "at": T3, "pr": 21},
                {"event": "merged", "at": T3, "pr": 22},
            ]
        )
        done = self.status()
        self.assertEqual(
            done.stdout.splitlines(),
            [
                "mode: off",
                "level: 1",
                "halt: none",
                "run's issue: #12",
                "open parks: #14, #15",
                "in progress: none",
                "steps:",
                (
                    f"  {T1} Day 07 Track A: the run log: opened: #20 from `day-07/track-a-x`, "
                    "$1.20, refusals 1, session `s1`"
                ),
                f"  {T2} Day 07 Track B: the lock: no end, $0.00, refusals 0, session `s2`",
                f"  {T3} Day 07 Track C: x: park: y, $0.00, refusals 2, session `s3`",
                "parks by reason:",
                "  2 park: pull request #n is stuck",
                "  2 park: the project's tree is not clean (n paths)",
                "  2 park: the session ended with no pull request and no PARK line (session `…`)",
                "  1 park: a one-off",
                "refusals: 3",
                "cost: $1.20, merged pull requests 2, $0.60 each (baseline $1.86)",
                LEVEL_2_NONE,
            ],
        )
        self.assertEqual(done.returncode, 0)

    def test_mode_forms(self):
        dead = self.gone_pid()
        live = self.live_pid()
        started = lock.now().strftime(lock.STAMP)
        cases = [
            (None, None, "mode: off", "halt: none"),
            (b"not json", None, "mode: off (the lock cannot be read)", "halt: none"),
            (
                json.dumps({"pid": dead, "started": started}).encode("utf-8"),
                None,
                f"mode: off (a lock names pid {dead}, which is gone)",
                "halt: none",
            ),
            (
                json.dumps({"pid": live, "started": started}).encode("utf-8"),
                b"halted at " + started.encode("utf-8"),
                f"mode: on (pid {live}, since {started})",
                f"halt: set: halted at {started}",
            ),
        ]
        for number, (lock_bytes, halt_bytes, mode, halt) in enumerate(cases):
            with self.subTest(mode=mode):
                state = os.path.join(self.root, f"state-{number}")
                os.makedirs(state)
                if lock_bytes is not None:
                    Path(lock.path(state)).write_bytes(lock_bytes)
                if halt_bytes is not None:
                    Path(state, "halt").write_bytes(halt_bytes)
                done = self.status(state=state)
                lines = done.stdout.splitlines()
                self.assertEqual((lines[0], lines[2]), (mode, halt))
                self.assertEqual(done.returncode, 0)

    def test_no_merged(self):
        self.write_log(
            [start("s1", "Day 07 Track A: the run log", T1), end("s1", "opened: #20", 0.7, 0)]
        )
        done = self.status()
        self.assertEqual(
            done.stdout.splitlines()[-2],
            "cost: $0.70, merged pull requests 0 (baseline $1.86)",
        )

    def test_no_parks(self):
        expected = [
            "mode: off",
            "level: 1",
            "halt: none",
            "run's issue: none",
            "open parks: none",
            "in progress: none",
            "steps: none",
            "parks by reason: none",
            "refusals: 0",
            "cost: $0.00, merged pull requests 0 (baseline $1.86)",
            LEVEL_2_NONE,
        ]
        done = self.status(issues=[])
        self.assertEqual(done.stdout.splitlines(), expected)
        self.assertEqual(done.returncode, 0)
        os.makedirs(self.state)
        Path(self.state, "run.jsonl").write_bytes(b"")
        done = self.status(issues=[])
        self.assertEqual(done.stdout.splitlines(), expected)
        self.assertEqual(done.returncode, 0)

    def test_in_progress(self):
        live = self.live_pid()
        started = lock.now().strftime(lock.STAMP)
        pid_line = {"event": "pid", "at": T1, "session": "s1", "pid": live, "started": started}
        # A live child of a session with an earlier end line: the session is in progress.
        live_state = os.path.join(self.root, "live")
        self.write_log(
            [start("s1", "Step A", T1), end("s1", "opened: #20", 0.4, 0), pid_line],
            state=live_state,
        )
        done = self.status(state=live_state)
        self.assertIn(
            "in progress: Step A (session `s1`), cost so far $0.40", done.stdout.splitlines()
        )
        # No live session: run.json names the step while the lock's process lives.
        lock_state = os.path.join(self.root, "lock")
        self.write_lock(live, started, state=lock_state)
        Path(lock_state, "run.json").write_bytes(
            json.dumps({"step": "Step R", "session": "s9", "issue": 12}).encode("utf-8")
        )
        done = self.status(state=lock_state)
        self.assertIn(
            "in progress: Step R (session `s9`), cost so far $0.00", done.stdout.splitlines()
        )
        # Neither: none.
        done = self.status(state=os.path.join(self.root, "none"))
        self.assertIn("in progress: none", done.stdout.splitlines())

    def test_writes_nothing(self):
        live = self.live_pid()
        self.write_log(
            [
                start("s1", "Step A", T1),
                {
                    "event": "pid",
                    "at": T1,
                    "session": "s1",
                    "pid": live,
                    "started": lock.now().strftime(lock.STAMP),
                },
            ]
        )
        self.write_lock(live)
        before = self.snapshot()
        done = self.status()
        self.assertEqual(done.returncode, 0)
        self.assertEqual(self.snapshot(), before)
        os.remove(lock.path(self.state))
        before = self.snapshot()
        self.status()
        self.assertEqual(self.snapshot(), before)
        absent = os.path.join(self.root, "absent")
        self.status(state=absent)
        self.assertFalse(os.path.exists(absent))
        calls = read_calls(self.folder)
        self.assertEqual(len(calls), 3)
        for call in calls:
            self.assertEqual(call[:2], ["issue", "list"])

    def test_torn_log(self):
        os.makedirs(self.state)
        Path(self.state, "run.jsonl").write_bytes(
            encode(start("s1", "Step A", T1)) + b'{"event": "end"'
        )
        done = self.status()
        self.assertEqual(
            done.stdout.splitlines()[5:],
            ["in progress: unknown", "run log: the run log cannot be read at line 2"],
        )
        self.assertEqual(done.returncode, 2)

    def test_gh_down(self):
        self.write_log(
            [start("s1", "Day 07 Track A: the run log", T1), end("s1", "opened: #20", 1.2, 0)]
        )
        done = self.status(issue_code=1)
        self.assertEqual(
            done.stdout.splitlines(),
            [
                "mode: off",
                "level: 1",
                "halt: none",
                "run's issue: unknown",
                "open parks: unknown",
                "in progress: none",
                "steps:",
                f"  {T1} Day 07 Track A: the run log: opened: #20, $1.20, refusals 0, session `s1`",
                "parks by reason: none",
                "refusals: 0",
                "cost: $1.20, merged pull requests 0 (baseline $1.86)",
                LEVEL_2_NONE,
            ],
        )
        self.assertEqual(done.stderr.strip(), "cannot read the project: gh issue list exited 1")
        self.assertEqual(done.returncode, 2)

    def test_bad_config(self):
        config = Path(self.root, "driver.json")
        config.write_bytes(json.dumps({"project": self.project}).encode("utf-8"))
        done = subprocess.run(
            [sys.executable, str(ROOT / "run-steps.py"), "status", "--config", str(config)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(done.stdout, "")
        self.assertEqual(
            done.stderr.splitlines(),
            [
                f"cannot start: {config} has no human_only",
                f"cannot start: {config} has no budget_usd",
                f"cannot start: {config} has no steps_per_night",
            ],
        )
        self.assertEqual(done.returncode, 2)
