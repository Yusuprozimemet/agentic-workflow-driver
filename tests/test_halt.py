"""halt and clear, and the settings file the driver writes for a session. Each test runs the CLI as a
person runs it, on a state folder of its own; the stand-in driver is a real process, in its own
process group, with a child."""

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SLEEP = "import time; time.sleep(60)"
# The stand-in writes its own pid and its child's, one per line, then sleeps like the child.
STAND_IN = """import os, subprocess, sys
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
with open(sys.argv[1], "a") as f:
    f.write(f"{os.getpid()}\\n{child.pid}\\n")
    f.flush()
import time
time.sleep(60)
"""
NO_DRIVER = "halt: set; no driver is running"


def new_group():
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def stop(process):
    # Ends a process a failed test left running; one that has already gone is no error.
    try:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        pass


class SwitchTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone.
        self.settings = importlib.import_module("driver.settings")
        self.lock = importlib.import_module("driver.lock")
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.state = os.path.join(self.root, "state")
        self.halt_file = os.path.join(self.state, "halt")

    def cli(self, command, state=None):
        return subprocess.run(
            [sys.executable, str(ROOT / "run-steps.py"), command, "--state", state or self.state],
            check=False,
            capture_output=True,
            text=True,
        )

    def write_lock(self, pid, state=None):
        state = state or self.state
        os.makedirs(state, exist_ok=True)
        started = self.lock.now().strftime(self.lock.STAMP)
        body = json.dumps({"pid": pid, "started": started})
        Path(self.lock.path(state)).write_bytes(body.encode("utf-8"))

    def gone_pid(self):
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait(timeout=10)
        return child.pid


class SettingsTest(SwitchTest):
    def test_settings_name_both_hooks(self):
        path = self.settings.write(self.state, ROOT)
        self.assertEqual(path, os.path.join(os.path.abspath(self.state), "settings.json"))
        data = json.loads(Path(path).read_bytes())
        self.assertEqual(list(data), ["hooks"])
        entries = data["hooks"]["PreToolUse"]
        self.assertEqual(
            [entry["matcher"] for entry in entries],
            ["*", "Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit"],
        )
        halt_command, guard_command = (entry["hooks"][0]["command"] for entry in entries)
        self.assertIn(os.path.abspath(self.halt_file), halt_command)
        self.assertIn(os.path.abspath(ROOT), guard_command)

    def test_commands_run_from_anywhere(self):
        state = os.path.join(self.root, "state with space")
        path = self.settings.write(state, ROOT)
        entries = json.loads(Path(path).read_bytes())["hooks"]["PreToolUse"]
        halt_command, guard_command = (entry["hooks"][0]["command"] for entry in entries)
        elsewhere = os.path.join(self.root, "elsewhere")
        os.makedirs(elsewhere)
        env = {**os.environ, "CLAUDE_PROJECT_DIR": elsewhere}

        def run(command, stdin):
            return subprocess.run(
                command,
                check=False,
                shell=True,
                cwd=elsewhere,
                env=env,
                input=stdin,
                capture_output=True,
                text=True,
            )

        self.assertEqual(run(halt_command, "").returncode, 0)
        Path(state, "halt").write_bytes(b"halted")
        self.assertEqual(run(halt_command, "").returncode, 2)
        call = {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}}
        self.assertEqual(run(guard_command, json.dumps(call)).returncode, 2)


class HaltTest(SwitchTest):
    def test_halt_kills_the_tree(self):
        pidfile = os.path.join(self.root, "pids")
        standin = subprocess.Popen([sys.executable, "-c", STAND_IN, pidfile], **new_group())
        self.addCleanup(stop, standin)
        pids = []
        deadline = time.monotonic() + 10
        while len(pids) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
            if os.path.exists(pidfile):
                pids = Path(pidfile).read_text().split()
        self.assertEqual(len(pids), 2)
        pid, child = (int(text) for text in pids)
        self.assertEqual(pid, standin.pid)
        self.write_lock(standin.pid)

        done = self.cli("halt")
        line = f"halt: set; killed pid {standin.pid} and the processes it started"
        self.assertEqual(done.stdout.strip(), line)
        self.assertEqual(done.returncode, 0)
        standin.wait(timeout=5)
        deadline = time.monotonic() + 5
        while self.lock.process(child)[0] and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(self.lock.process(child)[0])
        self.assertTrue(os.path.exists(self.halt_file))

        path = self.settings.write(self.state, ROOT)
        entries = json.loads(Path(path).read_bytes())["hooks"]["PreToolUse"]
        halt_command = entries[0]["hooks"][0]["command"]
        check = subprocess.run(halt_command, check=False, shell=True)
        self.assertEqual(check.returncode, 2)

    def test_halt_with_no_driver(self):
        done = self.cli("halt")
        self.assertEqual(done.stdout.strip(), NO_DRIVER)
        self.assertEqual(done.returncode, 0)
        self.assertTrue(os.path.exists(self.halt_file))

        stale = os.path.join(self.root, "stale")
        self.write_lock(self.gone_pid(), stale)
        done = self.cli("halt", stale)
        self.assertEqual(done.stdout.strip(), NO_DRIVER)
        self.assertEqual(done.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(stale, "halt")))

    def test_halt_twice(self):
        for _ in range(2):
            done = self.cli("halt")
            self.assertEqual(done.stdout.strip(), NO_DRIVER)
            self.assertEqual(done.returncode, 0)
        self.assertTrue(os.path.exists(self.halt_file))

    def test_halt_creates_state(self):
        state = os.path.join(self.root, "new", "state")
        done = self.cli("halt", state)
        self.assertEqual(done.stdout.strip(), NO_DRIVER)
        self.assertEqual(done.returncode, 0)
        self.assertTrue(os.path.exists(os.path.join(state, "halt")))

    def test_halt_unreadable_lock(self):
        os.makedirs(self.state)
        Path(self.lock.path(self.state)).write_bytes(b"")
        done = self.cli("halt")
        lock_file = os.path.join(self.state, "lock")
        line = f"halt: set; {lock_file} cannot be read, so nothing was killed"
        self.assertEqual(done.stdout.strip(), line)
        self.assertEqual(done.returncode, 1)
        self.assertTrue(os.path.exists(self.halt_file))


class ClearTest(SwitchTest):
    def test_clear_removes_halt_and_stale_lock(self):
        self.write_lock(self.gone_pid())
        Path(self.halt_file).write_bytes(b"halted")
        done = self.cli("clear")
        self.assertEqual(done.stdout.strip(), "clear: the halt is removed; the driver is off")
        self.assertEqual(done.returncode, 0)
        self.assertFalse(os.path.exists(self.halt_file))
        self.assertFalse(os.path.exists(self.lock.path(self.state)))

    def test_clear_no_halt(self):
        os.makedirs(self.state)
        done = self.cli("clear")
        self.assertEqual(done.stdout.strip(), "clear: no halt is set")
        self.assertEqual(done.returncode, 0)

    def test_clear_refuses_while_driver_lives(self):
        child = subprocess.Popen([sys.executable, "-c", SLEEP])
        self.addCleanup(stop, child)
        self.write_lock(child.pid)
        Path(self.halt_file).write_bytes(b"halted")
        done = self.cli("clear")
        line = f"clear: pid {child.pid} still runs; halt again, or stop it by hand"
        self.assertEqual(done.stdout.strip(), line)
        self.assertEqual(done.returncode, 1)
        self.assertTrue(os.path.exists(self.halt_file))
        self.assertTrue(os.path.exists(self.lock.path(self.state)))
