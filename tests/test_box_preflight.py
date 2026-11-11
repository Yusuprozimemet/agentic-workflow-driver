"""The container's checks before a session, run in-process with the fake docker of tests/fake_docker.py
and the fake claude of tests/test_once.py. A Docker that is down, an image not built or a secrets file
missing stops --once with one line and no issue read (C10.8). The image's Claude Code is the one
checked, its version and its --settings, and `on` reads the image's version against the live check
(C10.9). In none of them is the PC's claude run."""

import contextlib
import importlib.util
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.fake_docker import docker_calls, fake_docker
from tests.test_github import read_calls
from tests.test_on import OnCase
from tests.test_preflight import HELP

# The same help without its --settings line: the one flag the image's claude then lacks.
HELP_NO_SETTINGS = "".join(
    line for line in HELP.splitlines(keepends=True) if "--settings <file-or-json>" not in line
)
VERSION_LINE = (
    "cannot run a session: Claude Code 2.1.100 is older than 2.1.170, "
    "the oldest the driver was checked on"
)


class BoxPreflightTest(OnCase, unittest.TestCase):
    def box(self, name, secrets=True, **answers):
        # One case: OnCase's project, fake claude and state, with the container keys in driver.json,
        # and a fake docker that answers as given. The secrets file exists unless the case says not.
        self.build(name)
        self.secrets = self.folder / ("secrets.env" if secrets else "missing.env")
        if secrets:
            self.secrets.write_bytes(b"GH_TOKEN=x\n")
        path = self.folder / "driver.json"
        config = json.loads(path.read_bytes())
        config["container_image"] = "img:1"
        config["container_secrets"] = str(self.secrets)
        path.write_bytes(json.dumps(config).encode("utf-8"))
        (self.folder / "docker").mkdir()
        docker = fake_docker(self.folder / "docker", **answers)
        self.flags = [*self.flags, "--docker", docker]

    def run_steps(self, command):
        # The driver run in-process, from the copy's run-steps.py; returns (code, stdout, stderr).
        spec = importlib.util.spec_from_file_location("run_steps", self.copy / "run-steps.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        out, err = io.StringIO(), io.StringIO()
        # os.setpgid would move this test process into a group of its own on Linux.
        setpgid = mock.patch.object(os, "setpgid", create=True)
        with setpgid, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = module.main([command, *self.flags])
        return code, self.hidden(out.getvalue()), self.hidden(err.getvalue())

    def hidden(self, text):
        # The secrets path as the config has it, and as realpath spells it, reads <secrets>.
        for path in (str(self.secrets), os.path.realpath(self.secrets)):
            text = text.replace(path, "<secrets>")
        return text

    def claude_ran(self):
        # The PC's fake claude records every call, its --version and --help probes too.
        return (self.folder / "claude" / "calls.jsonl").exists()

    def issue_read(self):
        # The fake gh records each call's arguments; an issue read is a call with "issue" among them.
        if not (self.folder / "gh" / "calls.jsonl").exists():
            return False
        return any("issue" in call for call in read_calls(self.folder / "gh"))

    def test_docker_down(self):
        self.box("down", version={"stderr": "Cannot connect to the Docker daemon\n", "code": 1})
        code, out, err = self.run_steps("--once")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(
            err.splitlines(),
            ["cannot start: Docker does not run: Cannot connect to the Docker daemon"],
        )
        self.assertFalse(self.claude_ran())
        self.assertFalse(self.issue_read())
        self.assertEqual(
            docker_calls(self.folder / "docker"),
            [["version", "--format", "{{.Server.Version}}"]],
        )

    def test_no_image(self):
        self.box("no-image", image={"stderr": "Error: No such image: img:1\n", "code": 1})
        code, out, err = self.run_steps("--once")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(
            err.splitlines(),
            ["cannot start: the image `img:1` is not built; docs/container.md says how"],
        )
        self.assertFalse(self.claude_ran())
        self.assertFalse(self.issue_read())

    def test_no_secrets(self):
        self.box("no-secrets", secrets=False)
        code, out, err = self.run_steps("--once")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(
            err.splitlines(), ["cannot start: the secrets file `<secrets>` does not exist"]
        )
        self.assertFalse(self.claude_ran())
        self.assertFalse(self.issue_read())

    def test_image_cli_checked(self):
        cases = [
            ("old", "2.1.100\n", HELP, VERSION_LINE),
            (
                "no-settings",
                "2.1.170 (Claude Code)\n",
                HELP_NO_SETTINGS,
                "cannot run a session: the image's claude --help lists no --settings",
            ),
        ]
        for name, version, help_text, line in cases:
            with self.subTest(name):
                answers = [
                    {"tail": ["claude", "--version"], "stdout": version},
                    {"tail": ["claude", "--help"], "stdout": help_text},
                ]
                self.box(name, run=answers)
                code, out, err = self.run_steps("--once")
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertEqual(err.splitlines(), [line])
                self.assertFalse(self.claude_ran())
                calls = docker_calls(self.folder / "docker")
                self.assertIn(["run", "--rm", "img:1", "claude", "--version"], calls)
                self.assertIn(["run", "--rm", "img:1", "claude", "--help"], calls)

    def test_on_live_check_reads_the_image(self):
        answers = [
            {"tail": ["claude", "--version"], "stdout": "2.1.400 (Claude Code)\n"},
            {"tail": ["claude", "--help"], "stdout": HELP},
        ]
        self.box("on-live", run=answers)
        live = (
            "cannot start: Claude Code `2.1.400 (Claude Code)` has not passed the live check; "
            "run run-steps.py live-check"
        )
        code, _, err = self.run_steps("on")
        self.assertEqual(code, 2)
        self.assertEqual(err.splitlines(), [live])
        self.assertFalse(self.claude_ran())
