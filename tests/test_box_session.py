"""The session in its container (Day 10, C10.15, C10.16 and C10.19): with the container keys, --once and
`on` start the session as one docker run named driver-<session>, the usage limit is read from the
state folder the container writes, and a resumed session runs in the container too; without the keys
no docker is run. The fake docker of tests/fake_docker.py answers the probe, the image's Claude Code
and the session's runs, and the fake gh gives PR #5 as tests/test_once.py does."""

import json
import os
import sys
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import test_box_preflight as preflight
from tests.fake_docker import docker_calls, fake_docker
from tests.test_on import GREEN, RED, OnCase
from tests.test_once import OPENED
from tests.test_preflight import HELP
from tests.test_reach_check import EXPECTED, PROBE, probe_stdout
from tests.test_usage_limit import PLAIN, WAITING, limit_record

# The session's uuid, fixed by mock.patch on uuid.uuid4 so that the fake docker answers its runs.
U = "00000000-0000-4000-8000-000000000010"
# The image's Claude Code is a version distinct from the PC's fake claude's, and is live-checked.
IMAGE_VERSION = "2.1.322 (Claude Code)"
VERSION = {"tail": ["claude", "--version"], "stdout": f"{IMAGE_VERSION}\n"}
HELP_ANSWER = {"tail": ["claude", "--help"], "stdout": HELP}
PROBE_ANSWER = {"tail": PROBE, "stdout": probe_stdout(EXPECTED)}
# run-steps.py's --model default, as its parser gives it.
MODEL = "opus"


def result(session):
    # The session's stdout under --output-format stream-json: one result line that names the session.
    return json.dumps(
        {"type": "result", "is_error": False, "result": "done", "session_id": session}
    )


def resumed(args):
    # The list a resumed session runs: the first one's, with --resume in place of --session-id.
    return ["--resume" if arg == "--session-id" else arg for arg in args]


class BoxSessionTest(OnCase, unittest.TestCase):
    # The driver run in-process, as ReachCheckTest runs it; the module is imported, not its test class.
    run_steps = preflight.BoxPreflightTest.run_steps

    def box(self, name, run, checks=(GREEN,), steps=2):
        # One case: OnCase's project, fake claude and state, with the container keys in driver.json and
        # a fake docker that answers the image's Claude Code, the probe and the runs given.
        self.build(name, checks=checks, steps=steps)
        self.secrets = self.folder / "secrets.env"
        self.secrets.write_bytes(b"GH_TOKEN=x\n")
        path = self.folder / "driver.json"
        config = json.loads(path.read_bytes())
        config["container_image"] = "img:1"
        config["container_secrets"] = str(self.secrets)
        path.write_bytes(json.dumps(config).encode("utf-8"))
        (self.folder / "docker").mkdir()
        docker = fake_docker(self.folder / "docker", run=[VERSION, HELP_ANSWER, PROBE_ANSWER, *run])
        self.flags = [*self.flags, "--docker", docker]
        # Both versions are listed, so on goes on with the image's Claude Code as with the PC's.
        record = b"2.1.170 (Claude Code)\n" + IMAGE_VERSION.encode("utf-8") + b"\n"
        (self.state / "live-checked.txt").write_bytes(record)

    def no_docker(self, name, steps=2):
        # A case without the container keys, and a fake docker that answers 1 to every call it is asked
        # for; a call the driver makes fails the case, and docker_calls records it.
        self.build(name, steps=steps)
        # No secrets file is read without the keys; hidden() still names one, so it is set to a path.
        self.secrets = self.folder / "secrets.env"
        (self.folder / "docker").mkdir()
        docker = fake_docker(
            self.folder / "docker",
            version={"code": 1},
            image={"code": 1},
            inspect={"code": 1},
            kill={"code": 1},
            run=[{"tail": ["--session-id", U], "code": 1}],
        )
        self.flags = [*self.flags, "--docker", docker]

    def hidden(self, text):
        # The case's folders, raw and as realpath spells them, read <home>, <state>, <project> and
        # <secrets>; the longer spelling first, so that a shorter one inside it is not cut first.
        pairs = [
            (self.secrets, "<secrets>"),
            (self.copy, "<home>"),
            (self.state, "<state>"),
            (self.folder / "project", "<project>"),
        ]
        for path, name in pairs:
            for form in sorted({str(path), os.path.realpath(path)}, key=len, reverse=True):
                text = text.replace(form, name)
        return text

    def plain(self, text):
        # The case's folders and the session's uuid in placeholders, so that a report holds neither.
        return self.hidden(text).replace(U, "<uuid>")

    def names(self):
        # The --name of each docker run the fake was asked for, in order, with the placeholders.
        calls = docker_calls(self.folder / "docker")
        return [
            self.plain(call[call.index("--name") + 1])
            for call in calls
            if call[:1] == ["run"] and "--name" in call
        ]

    def named(self, name):
        # The argument lists of the docker runs with this --name, the run word first.
        calls = docker_calls(self.folder / "docker")
        return [
            [self.plain(arg) for arg in call]
            for call in calls
            if call[:1] == ["run"] and "--name" in call and call[call.index("--name") + 1] == name
        ]

    def run_log(self):
        # The run log's records, none when the driver wrote none.
        path = Path(self.state) / "run.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_bytes().decode("utf-8").splitlines()]

    def test_session_runs_in_the_container(self):
        # C10.15: the session is one docker run named driver-<session>, with claude -p's flags and the
        # container's settings and rules; the run log's start and pid lines end with its name.
        self.box("session", run=[{"tail": ["--session-id", U], "stdout": result(U)}])
        with mock.patch("uuid.uuid4", return_value=uuid.UUID(U)):
            code, out, _ = self.run_steps("--once")
        inner = [
            "claude",
            "-p",
            "--model",
            MODEL,
            "--output-format",
            "stream-json",
            "--verbose",
            "--max-budget-usd",
            "5",
            "--permission-mode",
            "auto",
            "--strict-mcp-config",
            "--settings",
            "/state/container-settings.json",
            "--append-system-prompt-file",
            "/driver/rules/session.md",
            "--session-id",
            U,
        ]
        # Imported here, not at the top: on the code before Track A there is no driver.box, and
        # C10.19's case must still load there to fail as its spec says.
        from driver import box

        command = box.command(
            "docker",
            "img:1",
            str(self.secrets),
            str(self.copy),
            str(self.state),
            str(self.folder / "project"),
            f"driver-{U}",
            inner,
        )
        log = [record for record in self.run_log() if record.get("event") in ("start", "pid")]
        self.assertEqual(
            (code, OPENED in out.splitlines(), self.sessions(), self.names()),
            (0, True, [], ["driver-probe-<uuid>", "driver-<uuid>"]),
        )
        self.assertEqual(self.named(f"driver-{U}"), [[self.plain(arg) for arg in command[1:]]])
        self.assertEqual(
            [
                (
                    record.get("event"),
                    list(record)[-1:],
                    self.plain(record.get("container") or ""),
                    record.get("claude"),
                )
                for record in log
            ],
            [
                ("start", ["container"], "driver-<uuid>", IMAGE_VERSION),
                ("pid", ["container"], "driver-<uuid>", None),
            ],
        )

    def test_limit_read_from_the_state(self):
        # C10.16, first half: the limit's transcript is read where the container writes it, under
        # <state>/claude, so the driver waits and resumes; a limit under CLAUDE_CONFIG_DIR starts none.
        reset = time.time() + 2
        limit = json.dumps(limit_record(reset)) + "\n"
        # The case's folder is the first case's name below, so its state folder is known before the box.
        base = Path(self.root) / "limit" / "state" / "claude" / "projects" / "-work"
        transcript = str(base / f"{U}.jsonl")
        self.box(
            "limit",
            run=[
                {"tail": ["--session-id", U], "files": {transcript: limit}, "stdout": result(U)},
                {
                    "tail": ["--resume", U],
                    "files": {transcript: limit + json.dumps(PLAIN) + "\n"},
                    "stdout": result(U),
                },
            ],
        )
        with mock.patch("uuid.uuid4", return_value=uuid.UUID(U)):
            code, out, _ = self.run_steps("--once")
        lines = out.splitlines()
        session = self.named(f"driver-{U}")
        first = session[0] if session else []
        self.assertEqual(
            (code, any(line.startswith(WAITING) for line in lines), OPENED in lines),
            (0, True, True),
        )
        self.assertEqual(session, [first, resumed(first)])

        # The second case: the limit is under CLAUDE_CONFIG_DIR only, so no wait starts and the step opens.
        self.box("limit-config", run=[{"tail": ["--session-id", U], "stdout": result(U)}])
        config = self.folder / "config" / "projects" / "-work"
        config.mkdir(parents=True)
        (config / f"{U}.jsonl").write_bytes(limit.encode("utf-8"))
        env = {"CLAUDE_CONFIG_DIR": str(self.folder / "config")}
        with (
            mock.patch("uuid.uuid4", return_value=uuid.UUID(U)),
            mock.patch.dict(os.environ, env),
        ):
            code, out, _ = self.run_steps("--once")
        lines = out.splitlines()
        self.assertEqual(
            (code, any(line.startswith(WAITING) for line in lines), OPENED in lines),
            (0, False, True),
        )

    def test_resumes_in_the_container(self):
        # C10.16, second half: a fix's resume through driver.loop.resume is a docker run with --resume
        # and the session's name, as the first run is.
        self.box(
            "resume",
            run=[
                {"tail": ["--session-id", U], "stdout": result(U)},
                {"tail": ["--resume", U], "stdout": result(U)},
            ],
            checks=[RED, GREEN],
            steps=1,
        )
        with mock.patch("uuid.uuid4", return_value=uuid.UUID(U)):
            code, _, _ = self.run_steps("on")
        session = self.named(f"driver-{U}")
        first = session[0] if session else []
        self.assertEqual((code, session), (0, [first, resumed(first)]))

    def test_no_keys_no_docker(self):
        # C10.19: without the container keys no docker runs: --once and on reach their outcomes, and the
        # fake docker records no call.
        self.no_docker("no-keys-once")
        once_folder = self.folder / "docker"
        with mock.patch("uuid.uuid4", return_value=uuid.UUID(U)):
            code_once, out_once, _ = self.run_steps("--once")
        self.assertEqual(
            (code_once, OPENED in out_once.splitlines(), docker_calls(once_folder)),
            (0, True, []),
        )
        self.no_docker("no-keys-on", steps=1)
        on_folder = self.folder / "docker"
        code_on, _, _ = self.on()
        self.assertEqual((code_on, docker_calls(on_folder)), (0, []))
