"""C09.11 and C09.12: the hook log's refusals of a session that was killed before its end line count
in the status report (C09.11) and in the dashboard's driver-runs count (C09.12). The end line counts
the refusals up to it; a hook line later than the session's last end line is counted here, and one
in the same second as it is not. Each test runs the CLI as a person runs it, on a state folder of
its own, with a fake gh beside it."""

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
from tests.test_github import fake_gh

GUARD_INPUT = json.dumps({"command": "git push origin main"})


def encode(record):
    # Bytes, as the driver writes them: text mode would add a carriage return on Windows.
    return (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")


def start(session, step, prefix, at):
    return {
        "event": "start",
        "at": at,
        "step": step,
        "prefix": prefix,
        "session": session,
        "claude": "claude",
    }


def end(session, outcome, denials, at):
    return {
        "event": "end",
        "at": at,
        "session": session,
        "outcome": outcome,
        "cost_usd": 0.5,
        "denials": denials,
    }


def pid(session, pid_number, started, at):
    return {
        "event": "pid",
        "at": at,
        "session": session,
        "pid": pid_number,
        "started": started,
    }


def guard(session, at):
    # A hook line as the guard writes it: the same tool call, refused, in the hook log.
    return {
        "at": at,
        "session": session,
        "hook": "guard",
        "tool": "Bash",
        "input": GUARD_INPUT,
        "line": "git push to main is refused",
    }


class HookRefusalCountTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.project = os.path.join(self.root, "project")
        os.makedirs(self.project)
        self.state = os.path.join(self.root, "S")
        self.folder = Path(self.root, "gh")
        self.folder.mkdir()
        self.write_fixture()

    def gone_pid(self):
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait(timeout=10)
        return child.pid

    def write_fixture(self):
        # Sessions a and c end; b is killed before its end line, and its process has exited, so
        # neither a session is live. a's hook line sits before its end, c's one line before and
        # one after, and b's two lines have no end line to be counted by.
        gone = self.gone_pid()
        started = lock.now().strftime(lock.STAMP)
        log = [
            start("a", "Day 09 Track A: a", "day-09/track-a", "2026-11-08T10:00:00Z"),
            end("a", "opened: #12", 1, "2026-11-08T10:05:00Z"),
            start("b", "Day 09 Track B: b", "day-09/track-b", "2026-11-08T10:10:00Z"),
            pid("b", gone, started, "2026-11-08T10:10:01Z"),
            start("c", "Day 09 Track C: c", "day-09/track-c", "2026-11-08T10:20:00Z"),
            end("c", "opened: #13", 0, "2026-11-08T10:25:00Z"),
            {"event": "fix", "at": "2026-11-08T10:26:00Z", "session": "c", "pr": 13, "n": 1},
            pid("c", gone, started, "2026-11-08T10:26:01Z"),
        ]
        hooks = [
            guard("b", "2026-11-08T10:12:00Z"),
            guard("b", "2026-11-08T10:13:00Z"),
            guard("a", "2026-11-08T10:03:00Z"),
            guard("c", "2026-11-08T10:24:00Z"),
            guard("c", "2026-11-08T10:30:00Z"),
        ]
        os.makedirs(os.path.join(self.state, "refusals"))
        Path(self.state, "run.jsonl").write_bytes(b"".join(encode(record) for record in log))
        Path(self.state, "refusals", "hooks.jsonl").write_bytes(
            b"".join(encode(record) for record in hooks)
        )

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
            timeout=120,
        )

    def test_status_counts_killed_session(self):
        done = self.status()
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.splitlines()
        refusals = next(
            (i for i, line in enumerate(lines) if line.startswith("refusals:")), len(lines)
        )
        cost = next((i for i, line in enumerate(lines) if line.startswith("cost")), len(lines))
        self.assertEqual(
            lines[refusals:cost],
            ["refusals: 4", '  3 Bash: {"command": "git push origin main"}'],
            done.stdout,
        )
        # Each step line's "refusals n, session `s`", by session, so a failure names the counts.
        steps = [line.rsplit(", ", 2)[-2:] for line in lines if ", session `" in line]
        self.assertEqual(
            [", ".join(parts) for parts in steps],
            ["refusals 1, session `a`", "refusals 2, session `b`", "refusals 1, session `c`"],
        )

    def test_driver_runs_counts_killed_session(self):
        out = os.path.join(self.root, "runs.json")
        done = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "driver-runs.py"),
                "--state",
                self.state,
                "--out",
                out,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        with open(out, encoding="utf-8") as f:
            data = json.load(f)
        denials = {}
        for step in data.get("steps", []):
            for run in step.get("sessions", []):
                denials[run.get("session")] = run.get("denials")
        self.assertEqual(denials, {"a": 1, "b": 2, "c": 1})
