"""--once halted during a real step (C04.13): the live check on the installed Claude Code. The session runs
a Bash command that sleeps; once started.txt exists, halt kills the driver, and the session's tree dies
with it, so late.txt never appears. A session resumed from the run log must have its next Bash call
refused by the driver's settings, while the project's own marker hook still runs. Skipped unless
DRIVER_LIVE_CLI names the program; DRIVER_LIVE_MODEL picks the model (default haiku). Costs a few cents
per run."""

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

from tests.test_dry_run import drift_of, git, make_project
from tests.test_github import fake_gh
from tests.test_halt import stop
from tests.test_live_cli import MARKER_HOOK, detail
from tests.test_once import DASHED, driver_copy, write_config

CLAUDE_MD = (
    "# Working here\n\n"
    "Before anything else, run this exact command with the Bash tool, and wait for it: "
    "echo started > started.txt && sleep 20 && echo late > late.txt\n"
)
RESUME_PROMPT = "Run this exact command with the Bash tool: echo resumed > out2.txt"
PREFIX = "halt: set; killed pid "
TIMEOUT = 300


def close_pipes(process):
    # The driver's output pipes are read only on a failure; close them so no test leaves them open.
    for pipe in (process.stdout, process.stderr):
        pipe.close()


def marker_lines(marker):
    if not marker.exists():
        return 0
    return len(marker.read_bytes().splitlines())


class LiveOnceTest(unittest.TestCase):
    def setUp(self):
        # Imported before the skip, as in test_once: where driver/ is missing, each test fails alone.
        importlib.import_module("driver.once")
        program = os.environ.get("DRIVER_LIVE_CLI")
        if not program:
            self.skipTest("DRIVER_LIVE_CLI is not set")
        # On Windows `claude` may be a .cmd shim, which only its full path finds.
        self.program = shutil.which(program) or program
        self.model = os.environ.get("DRIVER_LIVE_MODEL", "haiku")
        # realpath expands a Windows 8.3 short name (C:\Users\HACKYO~1\...), as in test_live_cli.
        self.root = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def test_halt_during_a_real_step(self):
        root = Path(self.root)
        project = make_project(root, drift_of(DASHED))
        (project / "CLAUDE.md").write_bytes(CLAUDE_MD.encode("utf-8"))
        # Outside the project, so the agent cannot see or change the marker it is checked by.
        marker = root / "marker.txt"
        marker_py = root / "marker.py"
        marker_py.write_bytes(MARKER_HOOK.encode("utf-8"))
        settings = {
            "permissions": {"allow": ["Bash"]},
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": f'"{sys.executable}" "{marker_py}" "{marker}"',
                            }
                        ],
                    }
                ]
            },
        }
        (project / ".claude").mkdir()
        body = json.dumps(settings).encode("utf-8")
        (project / ".claude" / "settings.json").write_bytes(body)
        git(project, "add", "-A")
        git(project, "commit", "-m", "live check")
        git(project, "push")

        gh_dir = root / "gh"
        gh_dir.mkdir()
        gh_runs = [{"status": "completed", "conclusion": "success"}]
        gh = fake_gh(gh_dir, runs=gh_runs, prs=[])
        config = write_config(root, project)
        state = root / "state"
        copy = driver_copy(tempfile.mkdtemp(dir=self.root))
        env = dict(os.environ)
        # A check run from inside a Claude Code session must not look like a nested one.
        env.pop("CLAUDECODE", None)
        env.pop("CLAUDE_PROJECT_DIR", None)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        driver = subprocess.Popen(
            [
                sys.executable,
                str(copy / "run-steps.py"),
                "--once",
                "--config",
                str(config),
                "--state",
                str(state),
                "--claude",
                self.program,
                "--gh",
                gh,
                "--model",
                self.model,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        # Registered first, so the pipes close after the driver is stopped.
        self.addCleanup(close_pipes, driver)
        self.addCleanup(stop, driver)
        started = project / "started.txt"
        deadline = time.monotonic() + 240
        while not started.exists() and driver.poll() is None and time.monotonic() < deadline:
            time.sleep(0.5)
        if not started.exists():
            stop(driver)
            out, err = driver.communicate()
            self.fail(f"no started.txt: stdout={out[-2000:]!r} stderr={err[-2000:]!r}")

        halted = subprocess.run(
            [sys.executable, str(ROOT / "run-steps.py"), "halt", "--state", str(state)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertTrue(halted.stdout.strip().startswith(PREFIX), detail(halted))
        self.assertEqual(halted.returncode, 0, detail(halted))
        driver.wait(timeout=10)
        time.sleep(30)
        self.assertFalse((project / "late.txt").exists(), "the session's tree lived on")

        records = (state / "run.jsonl").read_text(encoding="utf-8").splitlines()
        starts = [record for record in map(json.loads, records) if record["event"] == "start"]
        self.assertEqual(len(starts), 1, "the run log has no start line")
        session = starts[0]["session"]
        before = marker_lines(marker)
        completed = subprocess.run(
            [
                self.program,
                "-p",
                RESUME_PROMPT,
                "--resume",
                session,
                "--model",
                self.model,
                "--output-format",
                "json",
                "--permission-mode",
                "auto",
                "--strict-mcp-config",
                "--settings",
                os.path.join(str(state), "settings.json"),
            ],
            cwd=os.path.realpath(project),
            env=env,
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
            self.fail(f"not JSON ({detail(completed)})")
        self.assertFalse((project / "out2.txt").exists(), detail(completed))
        self.assertGreater(marker_lines(marker), before, detail(completed))
        self.assertIs(data.get("is_error"), False, detail(completed))
