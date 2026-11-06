"""run-steps.py --dry-run checks the kit before it reads the remote: each missing piece is one line on
stderr, and an origin that cannot be read is not the same as a main that is missing. Each test
builds a project and a bare remote in a temporary folder, as DryRunTest does.

The CliPreflightTest tests run `run-steps.py preflight` against a fake Claude Code: a program that
answers `--version` and `--help` from a file beside it, and exits 99 on anything else, so a test
fails if the preflight starts a session. Its CLI lines follow the kit's, in the order of the table."""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import SCRIPT, drift_of, dry_run, git, is_read, make_project, without


class PreflightTest(unittest.TestCase):
    def project(self, drift=None):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        return make_project(tmp.name, drift)

    def test_every_missing_piece_is_a_line(self):
        drift = without(drift_of(), "order")
        del drift["days"][0]["status"]
        project = self.project(drift)
        git(project, "rm", "scripts/pr-names.py")
        git(project, "rm", ".github/workflows/evidence.yml")
        git(project, "commit", "-m", "remove the kit's pieces")
        git(project, "push", "origin", "main")
        self.assertEqual(
            dry_run(project),
            (
                2,
                "",
                (
                    "cannot read the project: scripts/pr-names.py is missing\n"
                    "cannot read the project: .github/workflows/evidence.yml is missing\n"
                    "cannot read the project: spec-drift.py's JSON has no order\n"
                    "cannot read the project: spec-drift.py's JSON has no days[0].status\n"
                ),
            ),
        )

    def test_one_missing_file_refuses(self):
        project = self.project()
        git(project, "rm", "scripts/pr-names.py")
        git(project, "commit", "-m", "remove pr-names")
        # Pushed, so main is origin/main: without the check, the dry run would start the step.
        git(project, "push", "origin", "main")
        self.assertEqual(
            dry_run(project),
            (2, "", "cannot read the project: scripts/pr-names.py is missing\n"),
        )

    def test_unreachable_origin_is_not_a_missing_main(self):
        with self.subTest("origin does not exist"):
            project = self.project()
            missing = project.parent / "no-such-remote"
            git(project, "remote", "set-url", "origin", str(missing))
            # The code is the one git itself exits with for this remote, not a constant.
            code = subprocess.run(
                ["git", "ls-remote", str(missing)], check=False, cwd=project, capture_output=True
            ).returncode
            self.assertNotEqual(code, 0)
            self.assertEqual(
                dry_run(project),
                (
                    2,
                    "",
                    f"cannot read the project: origin could not be read (git ls-remote exited {code})\n",
                ),
            )
        with self.subTest("origin is empty"):
            project = self.project()
            git(project.parent, "init", "--bare", "-b", "main", "empty.git")
            git(project, "remote", "set-url", "origin", str(project.parent / "empty.git"))
            code, out, _ = dry_run(project)
            self.assertEqual((code, out), (1, "park: the project has no origin/main\n"))
        with self.subTest("no remote named origin"):
            project = self.project()
            git(project, "remote", "remove", "origin")
            code, out, _ = dry_run(project)
            self.assertEqual((code, out), (1, "park: the project has no origin/main\n"))

    def test_null_phase_still_parks(self):
        drift = {
            "now": {
                "next_step": "Day 02: read the spec against the code, then the spec-change PR",
                "open_prs": [],
            },
            "order": [1, 2],
            "days": [
                {"day": 1, "phase": 0, "status": "done"},
                {"day": 2, "phase": None, "status": "active"},
            ],
            "meta": {"caveats": []},
        }
        code, out, _ = dry_run(self.project(drift))
        self.assertEqual((code, out), (1, "park: Day 02 or the day before it names no phase\n"))


# The help text of Claude Code 2.1.170: every flag the preflight checks, in the forms it lists them.
HELP = (
    "Usage: claude [options] [command] [prompt]\n"
    "\n"
    "Options:\n"
    "  -p, --print  Print response and exit\n"
    "  --model <model>  Model for the current session\n"
    "  --output-format <format>  Output format: text, json or stream-json\n"
    "  --max-budget-usd <amount>  Maximum dollar amount to spend on API calls\n"
    "  --strict-mcp-config  Only use MCP servers from --mcp-config\n"
    "  --settings <file-or-json>  Path to a settings JSON file or a JSON string\n"
    "  --bare  Minimal mode; a system prompt file is set by --append-system-prompt[-file]\n"
    "  --append-system-prompt <prompt>  System prompt to append to the default one\n"
    "  --session-id <uuid>  Use a specific session ID for the conversation\n"
    "  --resume"
)
# The fake program: it answers --version and --help from fake.json beside it, and exits 99 on any
# other argument, so a preflight that starts a session fails the test.
FAKE = """import json
import sys
from pathlib import Path

spec = json.loads((Path(__file__).resolve().parent / "fake.json").read_text(encoding="utf-8"))
if sys.argv[1:] == ["--version"]:
    print(spec["version"])
    sys.exit(spec["version_code"])
if sys.argv[1:] == ["--help"]:
    print(spec["help"], end="")
    sys.exit(0)
sys.exit(99)
"""


def fake_cli(folder, version="2.1.170 (Claude Code)", help=HELP, version_code=0):
    # Files are written as bytes: on Windows, text mode would add a carriage return to each line.
    spec = {"version": version, "help": help, "version_code": version_code}
    (folder / "fake.json").write_bytes(json.dumps(spec).encode("utf-8"))
    (folder / "fake.py").write_bytes(FAKE.encode("utf-8"))
    if os.name == "nt":
        program = folder / "claude.cmd"
        program.write_bytes(f'@"{sys.executable}" "%~dp0fake.py" %*\r\n'.encode())
    else:
        program = folder / "claude"
        program.write_bytes(f"#!{sys.executable}\n{FAKE}".encode())
        program.chmod(0o755)
    return str(program)


def preflight(project, program):
    cmd = [sys.executable, str(SCRIPT), "preflight", "--project", str(project), "--claude", program]
    done = subprocess.run(cmd, check=False, capture_output=True, text=True, encoding="utf-8")
    return done.returncode, done.stdout, done.stderr


def preflight_recorded(project, program):
    # Loads run-steps.py in this process, so the patched subprocess.run sees each command it runs.
    real_run = subprocess.run
    commands = []

    def record(*args, **kwargs):
        commands.append(list(args[0]))
        return real_run(*args, **kwargs)

    spec = importlib.util.spec_from_file_location("run_steps", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out, err = io.StringIO(), io.StringIO()
    with (
        mock.patch("subprocess.run", side_effect=record),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ):
        code = module.main(["preflight", "--project", str(project), "--claude", program])
    return code, out.getvalue(), err.getvalue(), commands


class CliPreflightTest(unittest.TestCase):
    def project(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        return make_project(tmp.name)

    def cli(self, **kwargs):
        # The fake CLI goes in its own folder, not in the project.
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        return fake_cli(Path(tmp.name), **kwargs)

    def test_ok(self):
        project = self.project()
        self.assertEqual(preflight(project, self.cli()), (0, "preflight: ok\n", ""))

    def test_versions(self):
        project = self.project()
        for version in ("2.1.170 (Claude Code)", "2.10.0 (Claude Code)"):
            with self.subTest(version=version):
                program = self.cli(version=version)
                self.assertEqual(preflight(project, program), (0, "preflight: ok\n", ""))
        with self.subTest("older"):
            program = self.cli(version="2.1.99 (Claude Code)")
            self.assertEqual(
                preflight(project, program),
                (
                    2,
                    "",
                    (
                        "cannot run a session: Claude Code 2.1.99 is older than 2.1.170, the "
                        "oldest the driver was checked on\n"
                    ),
                ),
            )
        with self.subTest("no number"):
            program = self.cli(version="Claude Code")
            self.assertEqual(
                preflight(project, program),
                (2, "", f"cannot run a session: {program} --version printed no version\n"),
            )
        with self.subTest("exits 1"):
            program = self.cli(version_code=1)
            self.assertEqual(
                preflight(project, program),
                (2, "", f"cannot run a session: {program} --version printed no version\n"),
            )

    def test_not_found(self):
        project = self.project()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            program = str(Path(tmp) / "no-such-claude")
            self.assertEqual(
                preflight(project, program),
                (2, "", f"cannot run a session: {program} is not found\n"),
            )

    def test_kit_lines_come_first(self):
        project = self.project()
        git(project, "rm", "scripts/pr-names.py")
        git(project, "commit", "-m", "remove pr-names")
        # Pushed, so the remote is read as in DryRunTest: only the CLI's line is in question.
        git(project, "push", "origin", "main")
        program = self.cli(version="2.1.99 (Claude Code)")
        self.assertEqual(
            preflight(project, program),
            (
                2,
                "",
                (
                    "cannot read the project: scripts/pr-names.py is missing\n"
                    "cannot run a session: Claude Code 2.1.99 is older than 2.1.170, the oldest "
                    "the driver was checked on\n"
                ),
            ),
        )

    def test_every_flag_is_listed(self):
        project = self.project()
        with self.subTest("every flag"):
            self.assertEqual(preflight(project, self.cli()), (0, "preflight: ok\n", ""))
        with self.subTest("no flag"):
            program = self.cli(help="Usage: claude [options]\n")
            flags = (
                "--print",
                "--model",
                "--output-format",
                "--max-budget-usd",
                "--strict-mcp-config",
                "--settings",
                "--append-system-prompt-file",
                "--session-id",
                "--resume",
            )
            self.assertEqual(
                preflight(project, program),
                (
                    2,
                    "",
                    "".join(
                        f"cannot run a session: {program} --help lists no {flag}\n"
                        for flag in flags
                    ),
                ),
            )
        with self.subTest("the flag written out"):
            text = HELP.replace("--append-system-prompt[-file]", "--append-system-prompt-file")
            self.assertEqual(preflight(project, self.cli(help=text)), (0, "preflight: ok\n", ""))

    def test_near_miss_flags(self):
        project = self.project()
        near = (
            (HELP.replace("--settings <file-or-json>", "--settings-file <file>"), "--settings"),
            (
                HELP.replace("--append-system-prompt[-file]", "--append-system-prompt"),
                "--append-system-prompt-file",
            ),
            (HELP.replace("-p, --print", "--printer"), "--print"),
        )
        for text, flag in near:
            with self.subTest(flag=flag):
                program = self.cli(help=text)
                self.assertEqual(
                    preflight(project, program),
                    (2, "", f"cannot run a session: {program} --help lists no {flag}\n"),
                )

    def test_runs_only_reads(self):
        project = self.project()
        program = self.cli()
        code, out, _, commands = preflight_recorded(project, program)
        self.assertEqual((code, out), (0, "preflight: ok\n"))
        self.assertTrue(
            any(cmd[1:2] == [str(project / "scripts" / "spec-drift.py")] for cmd in commands),
            commands,
        )
        self.assertTrue(any(cmd[1:] == ["--version"] for cmd in commands), commands)
        self.assertTrue(any(cmd[1:] == ["--help"] for cmd in commands), commands)
        claude = Path(shutil.which(program)).resolve()
        for cmd in commands:
            is_cli = (
                len(cmd) == 2
                and cmd[1] in ("--version", "--help")
                and Path(cmd[0]).resolve() == claude
            )
            self.assertTrue(is_cli or is_read(cmd, project), f"not a read: {cmd}")
        self.assertEqual(git(project, "status", "--porcelain").stdout, "")


if __name__ == "__main__":
    unittest.main()
