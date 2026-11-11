"""The hooks log their refusals to <refusals folder>/hooks.jsonl: the guard and the halt hook, run as
subprocesses with a refusals folder, and the settings commands run through the shell as Claude Code
runs them. A refusal writes one JSON line; a pass writes nothing; a log that cannot be written
changes nothing else. Failure messages name no temp path, so a break's report replays."""

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PUSH = "refused by the driver: a session never pushes to main"
HALTED = "halted: <halt> exists; run-steps.py clear removes it"
KEYS = ["at", "session", "hook", "tool", "input", "line"]
PUSH_CALL = {
    "session_id": "s1",
    "tool_name": "Bash",
    "tool_input": {"command": "git push origin main"},
}
PASS_CALL = {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "gh pr view 12"}}
WRITE_CALL = {
    "session_id": "s2",
    "tool_name": "Write",
    "tool_input": {"file_path": "a.txt", "content": "x"},
}


def run_hook(name, args, stdin=None):
    return subprocess.run(
        [sys.executable, str(ROOT / "hooks" / name), *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


class HookLogTest(unittest.TestCase):
    def setUp(self):
        self.driver = self.temp()
        self.state = self.temp()
        self.refusals = os.path.join(self.temp(), "refusals")
        self.halt = os.path.join(self.state, "halt")

    def temp(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        return folder

    def log_records(self, refusals):
        path = os.path.join(refusals, "hooks.jsonl")
        self.assertTrue(os.path.exists(path), "hooks.jsonl was not written")
        return [json.loads(text) for text in Path(path).read_bytes().decode("utf-8").splitlines()]

    def halt_stderr(self, result):
        return result.stderr.replace(self.halt, "<halt>")

    def test_guard_logs_refusal(self):
        result = run_hook("guard.py", [self.driver, self.refusals], json.dumps(PUSH_CALL))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, PUSH + "\n")
        records = self.log_records(self.refusals)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(list(record), KEYS)
        self.assertEqual(record.get("session"), "s1")
        self.assertEqual(record.get("hook"), "guard")
        self.assertEqual(record.get("tool"), "Bash")
        self.assertEqual(record.get("input"), json.dumps({"command": "git push origin main"}))
        self.assertEqual(record.get("line"), PUSH)
        self.assertTrue(
            re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", str(record.get("at"))),
            "at is not a UTC time",
        )

    def test_guard_pass_writes_nothing(self):
        result = run_hook("guard.py", [self.driver, self.refusals], json.dumps(PASS_CALL))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertFalse(os.path.exists(self.refusals), "the refusals folder was created")

    def test_halt_logs_refusal(self):
        Path(self.halt).write_bytes(b"halted")
        result = run_hook("halt.py", [self.halt, self.refusals], json.dumps(WRITE_CALL))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.halt_stderr(result), HALTED + "\n")
        records = self.log_records(self.refusals)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(list(record), KEYS)
        self.assertEqual(record.get("session"), "s2")
        self.assertEqual(record.get("hook"), "halt")
        self.assertEqual(record.get("tool"), "Write")
        self.assertEqual(record.get("input"), json.dumps(WRITE_CALL["tool_input"]))
        self.assertEqual(str(record.get("line")).replace(self.halt, "<halt>"), HALTED)

        os.remove(self.halt)
        fresh = os.path.join(self.temp(), "refusals")
        result = run_hook("halt.py", [self.halt, fresh], json.dumps(WRITE_CALL))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertFalse(os.path.exists(fresh), "the refusals folder was created")

    def test_halt_unreadable_stdin_logs_nulls(self):
        Path(self.halt).write_bytes(b"halted")
        result = run_hook("halt.py", [self.halt, self.refusals], "not json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.halt_stderr(result), HALTED + "\n")
        records = self.log_records(self.refusals)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record.get("hook"), "halt")
        self.assertIsNone(record.get("session"))
        self.assertIsNone(record.get("tool"))
        self.assertIsNone(record.get("input"))

    def test_unwritable_log_still_refuses(self):
        Path(self.refusals).write_bytes(b"x")
        result = run_hook("guard.py", [self.driver, self.refusals], json.dumps(PUSH_CALL))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, PUSH + "\n")

        Path(self.halt).write_bytes(b"halted")
        result = run_hook("halt.py", [self.halt, self.refusals], json.dumps(WRITE_CALL))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.halt_stderr(result), HALTED + "\n")

    def test_settings_commands_log(self):
        settings = importlib.import_module("driver.settings")
        state = os.path.join(self.temp(), "state")
        path = settings.write(state, ROOT)
        entries = json.loads(Path(path).read_bytes()).get("hooks", {}).get("PreToolUse", [])
        self.assertEqual(len(entries), 2, "the settings do not hold two PreToolUse hooks")
        halt_command, guard_command = (entry["hooks"][0]["command"] for entry in entries)
        log = os.path.join(state, "refusals", "hooks.jsonl")

        result = subprocess.run(
            guard_command,
            shell=True,
            input=json.dumps(PUSH_CALL),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertTrue(os.path.exists(log), "hooks.jsonl was not written")
        records = self.log_records(os.path.join(state, "refusals"))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].get("session"), "s1")

        Path(state, "halt").write_bytes(b"halted")
        halt_call = {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "ls"}}
        result = subprocess.run(
            halt_command,
            shell=True,
            input=json.dumps(halt_call),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        records = self.log_records(os.path.join(state, "refusals"))
        self.assertEqual(len(records), 2)
        self.assertEqual(records[1].get("hook"), "halt")
