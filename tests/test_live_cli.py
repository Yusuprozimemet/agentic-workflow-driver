"""The live check on the installed Claude Code: the driver's --settings hooks run beside a project's
own hooks, the halt hook refuses a tool call, and a rules file and a resumed session keep both.
Skipped unless DRIVER_LIVE_CLI names the program; DRIVER_LIVE_MODEL picks the model (default
haiku). Costs a few cents per run."""

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROMPT = "Run this exact command with the Bash tool: echo driver > out.txt"
RESUME_PROMPT = "Run this exact command with the Bash tool: echo resumed > out2.txt"
PARK = "PARK: live check"
TIMEOUT = 300
# The project's own hook: it appends one line to the marker file each time a Bash call reaches it.
MARKER_HOOK = """import sys
sys.stdin.read()
with open(sys.argv[1], "ab") as f:
    f.write(b"bash\\n")
"""


def detail(completed):
    return (
        f"exit {completed.returncode}: stdout={completed.stdout[-2000:]!r} "
        f"stderr={completed.stderr[-2000:]!r}"
    )


class LiveCliTest(unittest.TestCase):
    def setUp(self):
        # Imported before the skip: on main's code, where driver/settings.py is missing, each test
        # errors.
        self.settings = importlib.import_module("driver.settings")
        program = os.environ.get("DRIVER_LIVE_CLI")
        if not program:
            self.skipTest("DRIVER_LIVE_CLI is not set")
        # On Windows `claude` may be a .cmd shim, which only its full path finds.
        self.program = shutil.which(program) or program
        self.model = os.environ.get("DRIVER_LIVE_MODEL", "haiku")
        # realpath expands a Windows 8.3 short name (C:\Users\HACKYO~1\...): Claude Code 2.1.170
        # asks before writing in a cwd given that way, and -p turns the ask into a denial.
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.project = os.path.join(self.root, "project")
        self.state = os.path.join(self.root, "state")
        # Outside the project, so the agent cannot see or change the marker it is checked by.
        self.marker = os.path.join(self.root, "marker.txt")
        marker_py = os.path.join(self.root, "marker.py")
        Path(marker_py).write_bytes(MARKER_HOOK.encode("utf-8"))
        os.makedirs(self.project)
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        claude_dir = os.path.join(self.project, ".claude")
        os.makedirs(claude_dir)
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": f'"{sys.executable}" "{marker_py}" "{self.marker}"',
                            }
                        ],
                    }
                ]
            }
        }
        Path(claude_dir, "settings.json").write_bytes(json.dumps(settings).encode("utf-8"))
        self.settings_file = self.settings.write(self.state, str(ROOT))

    def marker_lines(self):
        if not os.path.exists(self.marker):
            return 0
        return len(Path(self.marker).read_bytes().splitlines())

    def run_cli(self, prompt, *extra):
        command = [
            self.program,
            "-p",
            prompt,
            "--model",
            self.model,
            "--output-format",
            "json",
            "--max-budget-usd",
            "0.50",
            "--strict-mcp-config",
            "--permission-mode",
            "auto",
            "--settings",
            self.settings_file,
            "--allowedTools",
            "Bash",
            *extra,
        ]
        env = dict(os.environ)
        # A check run from inside a Claude Code session must not look like a nested one.
        env.pop("CLAUDECODE", None)
        env.pop("CLAUDE_PROJECT_DIR", None)
        completed = subprocess.run(
            command,
            cwd=self.project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
            check=False,
            env=env,
        )
        try:
            data = json.loads(completed.stdout)
        except ValueError:
            self.fail(f"not JSON ({detail(completed)})")
        return completed, data

    def test_settings_hooks_are_added(self):
        completed, _ = self.run_cli(PROMPT)
        self.assertEqual(completed.returncode, 0, detail(completed))
        self.assertTrue(os.path.exists(os.path.join(self.project, "out.txt")), detail(completed))
        # The project's own hook ran beside the driver's.
        self.assertGreaterEqual(self.marker_lines(), 1, detail(completed))

    def test_halt_refuses_a_tool_call(self):
        os.makedirs(self.state, exist_ok=True)
        Path(self.state, "halt").write_bytes(b"halted at live check\n")
        completed, data = self.run_cli(PROMPT)
        self.assertFalse(os.path.exists(os.path.join(self.project, "out.txt")), detail(completed))
        # The Bash call was attempted: the project's hook ran beside the halt hook that refused it.
        self.assertGreaterEqual(self.marker_lines(), 1, detail(completed))
        self.assertIs(data.get("is_error"), False, detail(completed))

    def test_rules_file_and_resume(self):
        rules = os.path.join(self.root, "rules.md")
        Path(rules).write_bytes(b"End every reply with the line PARK: live check\n")
        session = str(uuid.uuid4())
        completed, data = self.run_cli(
            "Say hello.", "--append-system-prompt-file", rules, "--session-id", session
        )
        self.assertEqual(completed.returncode, 0, detail(completed))
        self.assertTrue(data["result"].strip().endswith(PARK), detail(completed))
        self.assertEqual(data["session_id"], session, detail(completed))
        before = self.marker_lines()
        completed, data = self.run_cli(RESUME_PROMPT, "--resume", session)
        self.assertEqual(completed.returncode, 0, detail(completed))
        self.assertEqual(data["session_id"], session, detail(completed))
        self.assertTrue(os.path.exists(os.path.join(self.project, "out2.txt")), detail(completed))
        self.assertGreater(self.marker_lines(), before, detail(completed))
