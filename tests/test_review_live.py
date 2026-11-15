"""The live check that the PC's Claude Code takes --agents from a file and --agent, and that the
reviewer's settings refuse a commit. Skipped unless DRIVER_LIVE_REVIEW names the Claude Code
program; DRIVER_LIVE_MODEL picks the model (default haiku); with DRIVER_CONTAINER_IMAGE and
DRIVER_CONTAINER_SECRETS the first case runs in the image too (DRIVER_DOCKER picks docker, default
docker). A few paid sessions, under $0.50 in all."""

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

TIMEOUT = 180
AGENTS = {
    "probe": {
        "description": "Replies with one word.",
        "prompt": "Reply with the word ORCHID and nothing else.",
    },
    "runner": {
        "description": "Runs the command it is given.",
        "prompt": "Run the command the user gives you with the Bash tool, then reply DONE.",
        "tools": ["Bash"],
    },
}


def detail(completed):
    return (
        f"exit {completed.returncode}: stdout={completed.stdout[-2000:]!r} "
        f"stderr={completed.stderr[-2000:]!r}"
    )


class ReviewLiveTest(unittest.TestCase):
    def setUp(self):
        # Imported before the skip: on main's code, where driver/settings.py or driver/box.py is
        # missing, each test errors.
        self.settings = importlib.import_module("driver.settings")
        self.box = importlib.import_module("driver.box")
        program = os.environ.get("DRIVER_LIVE_REVIEW")
        if not program:
            self.skipTest("DRIVER_LIVE_REVIEW is not set")
        # On Windows `claude` may be a .cmd shim, which only its full path finds.
        self.program = shutil.which(program) or program
        self.model = os.environ.get("DRIVER_LIVE_MODEL", "haiku")
        # realpath expands a Windows 8.3 short name (C:\Users\HACKYO~1\...), as in test_live_cli.py.
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.project = os.path.join(self.root, "project")
        self.state = os.path.join(self.root, "state")
        for folder in ("refusals", "claude"):
            os.makedirs(os.path.join(self.state, folder))
        os.makedirs(self.project)
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        # One commit, so HEAD exists for head() to read before and after the refused commit.
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=driver",
                "-c",
                "user.email=driver@example.invalid",
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                "start",
            ],
            cwd=self.project,
            check=True,
        )
        self.agents = os.path.join(self.state, "agents.json")
        Path(self.agents).write_bytes(json.dumps(AGENTS).encode("utf-8"))

    def head(self):
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.project,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.strip()

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
            "0.20",
            "--strict-mcp-config",
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

    def test_agent_from_file(self):
        # C12.21: Claude Code started with --agents <file> --agent probe replies ORCHID, on the PC
        # and, when the image is named, in the image too.
        completed, data = self.run_cli("Hello.", "--agents", self.agents, "--agent", "probe")
        self.assertEqual(completed.returncode, 0, detail(completed))
        self.assertEqual(data.get("result", "").strip(), "ORCHID", detail(completed))
        image = os.environ.get("DRIVER_CONTAINER_IMAGE")
        secrets = os.environ.get("DRIVER_CONTAINER_SECRETS")
        if not (image and secrets):
            return
        docker = os.environ.get("DRIVER_DOCKER", "docker")
        with self.subTest(where="image"):
            inner = [
                "claude",
                "-p",
                "--model",
                self.model,
                "--output-format",
                "json",
                "--max-budget-usd",
                "0.20",
                "--strict-mcp-config",
                "--agents",
                "/state/agents.json",
                "--agent",
                "probe",
            ]
            name = "driver-review-live-" + uuid.uuid4().hex[:8]
            command = self.box.command(
                docker, image, secrets, str(ROOT), self.state, self.project, name, inner
            )
            completed = subprocess.run(
                command,
                input="Hello.\n",
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TIMEOUT,
                check=False,
            )
            try:
                data = json.loads(completed.stdout)
            except ValueError:
                self.fail(f"in the image: not JSON ({detail(completed)})")
            self.assertEqual(completed.returncode, 0, "in the image: " + detail(completed))
            self.assertEqual(
                data.get("result", "").strip(), "ORCHID", "in the image: " + detail(completed)
            )
            # Reported, not asserted: the spec's Assumed asks the PR to say what the image run left.
            status = subprocess.run(
                ["git", "status", "--porcelain", "--ignored"],
                cwd=self.project,
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            sys.stderr.write(
                f"image run git status: {' | '.join(status.splitlines()) or 'clean'}\n"
            )

    def test_commit_refused(self):
        # C12.21: a session under the reviewer's settings file is asked to commit: the read-only
        # hook refuses the commit, so the scratch HEAD stays as it was, and the refusal is logged.
        settings = self.settings.review(self.state, str(ROOT))
        before = self.head()
        completed, _ = self.run_cli(
            "Run `git commit --allow-empty -m x` with Bash, then reply DONE",
            "--permission-mode",
            "auto",
            "--settings",
            settings,
            "--allowedTools",
            "Bash",
            "--agents",
            self.agents,
            "--agent",
            "runner",
        )
        # No exit code is asserted: a refused call may still end the session with 0 or not.
        self.assertEqual(self.head(), before, detail(completed))
        log = os.path.join(self.state, "refusals", "hooks.jsonl")
        lines = []
        if os.path.exists(log):
            lines = Path(log).read_text(encoding="utf-8", errors="replace").splitlines()
        records = []
        for line in lines:
            try:
                records.append(json.loads(line))
            except ValueError:
                self.fail(
                    f"hooks.jsonl line is not JSON: lines read {lines!r}, {detail(completed)}"
                )
        found = any(
            isinstance(record, dict) and "the reviewer only reads" in str(record.get("line", ""))
            for record in records
        )
        self.assertTrue(found, f"lines read {lines!r}, {detail(completed)}")
