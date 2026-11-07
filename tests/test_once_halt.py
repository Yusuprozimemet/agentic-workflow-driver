"""--once halted during a step (C04.12): a halt kills the driver and the session's tree, leaves the run log
with its start line and no end line, and keeps the lock. The next --once refuses with the halt's line
and starts no session, until clear removes the halt file and the lock. The session is the fake claude
of tests/test_once.py: it starts a child, writes both pids, and sleeps. No report here names a pid or a
path: a failure must not print one (D03.17)."""

import importlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import drift_of, make_project
from tests.test_github import fake_gh
from tests.test_halt import stop
from tests.test_once import DASHED, driver_copy, fake_claude, halt_line, once, write_config

PREFIX = "halt: set; killed pid "
PROBES = (["--version"], ["--help"])
# Run by the fake claude inside a session: it starts a child, writes its pid and the child's to pids
# beside the fake, then sleeps like the child does.
SESSION = """import subprocess, time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
with open(folder / "pids", "a") as f:
    f.write(f"{os.getpid()}\\n{child.pid}\\n")
    f.flush()
time.sleep(60)
"""


def kill_left_over(claude_dir):
    # Ends the fake and its child when a failing test leaves them running; a gone pid is no error.
    pids = Path(claude_dir, "pids")
    if not pids.exists():
        return
    for text in pids.read_text(encoding="utf-8").split():
        try:
            os.kill(int(text), getattr(signal, "SIGKILL", signal.SIGTERM))
        except (OSError, ValueError):
            pass


def close_pipes(process):
    # The driver's output pipes are not read; closing them keeps a finished test from leaving them open.
    for pipe in (process.stdout, process.stderr):
        pipe.close()


def session_calls(claude_dir):
    # The fake records every call it gets; the driver's --version and --help probes are not sessions.
    calls = Path(claude_dir, "calls.jsonl")
    if not calls.exists():
        return 0
    records = [json.loads(line) for line in calls.read_text(encoding="utf-8").splitlines()]
    return len([record for record in records if record["args"] not in PROBES])


class OnceHaltTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone.
        importlib.import_module("driver.once")
        self.lock = importlib.import_module("driver.lock")
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def halt_mid_step(self):
        folder = Path(tempfile.mkdtemp(dir=self.root))
        project = make_project(folder, drift_of(DASHED))
        state = folder / "state"
        claude_dir, gh_dir = folder / "claude", folder / "gh"
        claude_dir.mkdir()
        gh_dir.mkdir()
        claude = fake_claude(claude_dir, do=SESSION)
        gh_runs = [{"status": "completed", "conclusion": "success"}]
        gh = fake_gh(gh_dir, runs=gh_runs, prs=[])
        config = write_config(folder, project)
        copy = driver_copy(tempfile.mkdtemp(dir=self.root))
        flags = ["--config", str(config), "--state", str(state), "--claude", claude, "--gh", gh]
        driver = subprocess.Popen(
            [sys.executable, str(copy / "run-steps.py"), "--once", *flags],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        # Registered first, so the pipes close after the driver is stopped.
        self.addCleanup(close_pipes, driver)
        self.addCleanup(stop, driver)
        self.addCleanup(kill_left_over, claude_dir)
        pids = []
        deadline = time.monotonic() + 30
        while len(pids) < 2 and time.monotonic() < deadline:
            time.sleep(0.1)
            if Path(claude_dir, "pids").exists():
                pids = Path(claude_dir, "pids").read_text(encoding="utf-8").split()
        self.assertEqual(len(pids), 2, "the session did not start its child")
        fake_pid, child_pid = (int(text) for text in pids)
        halted = subprocess.run(
            [sys.executable, str(ROOT / "run-steps.py"), "halt", "--state", str(state)],
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            "driver": driver,
            "halted": halted,
            "fake": fake_pid,
            "child": child_pid,
            "state": state,
            "claude": claude_dir,
            "copy": copy,
            "flags": flags,
        }

    def alive(self, pid, deadline):
        while self.lock.process(pid)[0] and time.monotonic() < deadline:
            time.sleep(0.05)
        return self.lock.process(pid)[0]

    def test_halt_during_once(self):
        run = self.halt_mid_step()
        out = run["halted"].stdout.strip()
        # Only the prefix is compared: the rest of the line names a pid, and a failure must not print it.
        self.assertEqual(out[: len(PREFIX)], PREFIX)
        self.assertEqual(run["halted"].returncode, 0)
        deadline = time.monotonic() + 5
        try:
            run["driver"].wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.fail("the driver still runs")
        self.assertFalse(self.alive(run["fake"], deadline), "the fake still runs")
        self.assertFalse(self.alive(run["child"], deadline), "the fake's child still runs")
        records = Path(run["state"], "run.jsonl").read_text(encoding="utf-8").splitlines()
        events = [json.loads(line)["event"] for line in records]
        self.assertEqual(events, ["start"])
        self.assertTrue(os.path.exists(self.lock.path(str(run["state"]))), "the lock is gone")

    def test_once_refuses_after_halt(self):
        run = self.halt_mid_step()
        run["driver"].wait(timeout=10)
        state = str(run["state"])
        calls_before = session_calls(run["claude"])
        code, out, err = once(run["copy"], *run["flags"])
        self.assertEqual(code, 2)
        self.assertFalse(out.strip(), "--once printed on stdout")
        self.assertTrue(
            err.strip() == halt_line(state), "--once did not refuse with the halt's line"
        )
        self.assertEqual(session_calls(run["claude"]), calls_before)
        done = subprocess.run(
            [sys.executable, str(ROOT / "run-steps.py"), "clear", "--state", state],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, 0)
        self.assertFalse(
            os.path.exists(os.path.join(state, "halt")), "the halt file is still there"
        )
        self.assertFalse(os.path.exists(self.lock.path(state)), "the lock is still there")
