"""The halt hook exits 2 with its line while the halt file exists, and 0 with nothing printed when it
does not, whatever CLAUDE_PROJECT_DIR and the working folder are. The guard hook refuses a merge, a
push to main, a call that names the driver's folder, an edit inside it and a call it cannot read,
and passes the calls a session makes. Both run as subprocesses, as Claude Code runs them."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MERGE = "refused by the driver: a session never merges"
PUSH = "refused by the driver: a session never pushes to main"
FOLDER = "refused by the driver: the driver's folder is not a session's"
UNREAD = "refused by the driver: the guard could not read the tool call"


def run_hook(name, args, cwd, env=None, stdin=None):
    return subprocess.run(
        [sys.executable, str(ROOT / "hooks" / name), *args],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
        env=env,
    )


def bash(command):
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


class HookTest(unittest.TestCase):
    def setUp(self):
        self.state = self.temp()
        self.project = self.temp()
        self.cwd = self.temp()

    def temp(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        return folder

    def environments(self, folder):
        # The hook must give the same answer with CLAUDE_PROJECT_DIR unset and set to a folder.
        base = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}
        return [("unset", base), ("set", {**base, "CLAUDE_PROJECT_DIR": folder})]


class HaltHookTest(HookTest):
    def test_refuses_while_halt_file_exists(self):
        halt = os.path.join(self.state, "halt")
        Path(halt).write_bytes(b"halted at 2026-11-06T00:00:00Z")
        for label, env in self.environments(self.project):
            for cwd in (self.cwd, str(ROOT)):
                with self.subTest(env=label, cwd=cwd):
                    result = run_hook("halt.py", [halt], cwd=cwd, env=env)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(
                        result.stderr.strip(),
                        f"halted: {halt} exists; run-steps.py clear removes it",
                    )
                    self.assertEqual(result.stdout, "")

    def test_passes_without_halt_file(self):
        halt = os.path.join(self.state, "halt")
        for label, env in self.environments(self.state):
            for cwd in (self.cwd, str(ROOT)):
                with self.subTest(env=label, cwd=cwd):
                    result = run_hook("halt.py", [halt], cwd=cwd, env=env)
                    self.assertEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "")

    def test_no_argument_refuses(self):
        result = run_hook("halt.py", [], cwd=self.cwd)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr.strip(), "halted: the halt hook was given no halt file")


class GuardHookTest(HookTest):
    def guard(self, payload):
        return run_hook("guard.py", [str(ROOT)], cwd=self.cwd, stdin=payload)

    def test_refuses(self):
        root = str(ROOT)
        drive, rest = os.path.splitdrive(root)
        cases = [
            (bash("gh pr merge 12 --squash"), MERGE),
            (bash("git push origin main"), PUSH),
            (bash("git push origin HEAD:main"), PUSH),
            (bash("git push origin HEAD:refs/heads/main"), PUSH),
            (bash("git switch x && git push origin main"), PUSH),
            (bash("cat " + root + "/state/halt"), FOLDER),
            (bash("cat " + root.replace("\\", "/") + "/state/halt"), FOLDER),
            (bash("ls " + root.replace("/", "\\")), FOLDER),
            (
                json.dumps(
                    {
                        "tool_name": "PowerShell",
                        "tool_input": {"command": "Get-Content " + root + "/state/halt"},
                    }
                ),
                FOLDER,
            ),
            (
                json.dumps(
                    {
                        "tool_name": "Write",
                        "tool_input": {"file_path": str(ROOT / "state" / "halt")},
                    }
                ),
                FOLDER,
            ),
            ("not json", UNREAD),
            ("[]", UNREAD),
        ]
        if drive:
            cases.append((bash("ls /" + drive[0].lower() + rest.replace("\\", "/")), FOLDER))
        if os.name == "nt":
            cases.append((bash("ls " + root.swapcase()), FOLDER))
        for payload, line in cases:
            with self.subTest(payload=payload):
                result = self.guard(payload)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stderr.strip(), line)
                self.assertEqual(result.stdout, "")

    def test_passes(self):
        cases = [
            bash("git push -u origin day-03/track-a-config"),
            bash("git push origin maintenance"),
            bash("git push -u origin day-03/x && gh pr create --base main"),
            bash("git push origin x; git switch main"),
            bash("gh pr view 12"),
            bash("gh pr checks 12 --watch"),
            json.dumps(
                {
                    "tool_name": "Write",
                    "tool_input": {"file_path": os.path.join(self.project, "src", "a.py")},
                }
            ),
            bash("ls " + str(ROOT) + "-old"),
            bash("ls " + str(ROOT) + "-old/state"),
            json.dumps({"tool_name": "Read", "tool_input": {"file_path": str(ROOT / "state")}}),
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                result = self.guard(payload)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
