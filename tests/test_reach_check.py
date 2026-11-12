"""The reach check before each session (C10.11 to C10.13): with the container keys, the probe runs in
the session's container with the session's mounts before the start, and a folder it can write where
it must not, or cannot where it must, stops the start with one line on stderr. No issue is opened or
commented, no run log line is made and no session runs. The fake docker of tests/fake_docker.py
answers the probe; the image's Claude Code is answered as tests/test_box_preflight.py answers it."""

import json
import os
import shutil
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver import runlog
from tests import test_box_preflight as preflight
from tests.fake_docker import docker_calls
from tests.test_github import read_bodies
from tests.test_on import OnCase
from tests.test_preflight import HELP

VERSION = {"tail": ["claude", "--version"], "stdout": "2.1.170 (Claude Code)\n"}
HELP_ANSWER = {"tail": ["claude", "--help"], "stdout": HELP}
PREFIX = "driver-probe-"
# The two sessions' uuids, fixed for the case; the session's container answers with RESULT.
FIRST = "11111111-1111-4111-8111-111111111111"
SECOND = "22222222-2222-4222-8222-222222222222"
RESULT = json.dumps({"type": "result", "is_error": False, "result": "done", "session_id": FIRST})
# The probe's six lines on a container that can write where it should and cannot where it should
# not: the first three refused, the last three written.
EXPECTED = [
    "refused /driver/hooks",
    "refused /driver/rules",
    "refused /state",
    "written /work",
    "written /state/refusals",
    "written /claude",
]
# The probe's command in the container, as the spec's In scope gives it.
PROBE = ["python", "/driver/hooks/probe.py", *(line.split(" ")[1] for line in EXPECTED)]


def probe_stdout(lines):
    # The probe's stdout, one line per folder, as the container prints it.
    return "".join(f"{line}\n" for line in lines)


class ReachCheckTest(OnCase, unittest.TestCase):
    # One case's folders, config and fake docker, and the in-process run, as C10.8's tests make them;
    # the module is imported, not its test class, so that its tests are not loaded here again.
    run_steps = preflight.BoxPreflightTest.run_steps

    def box(self, name, run):
        # The image's Claude Code passes C10.9's checks, so the probe's answer is the one that counts.
        preflight.BoxPreflightTest.box(self, name, run=[VERSION, HELP_ANSWER, *run])

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

    def run_names(self):
        # The --name of each docker run the fake was asked for, in order, with its arguments.
        calls = docker_calls(self.folder / "docker")
        return [(c[c.index("--name") + 1], c) for c in calls if c[:1] == ["run"] and "--name" in c]

    def probe_runs(self):
        # The probe's runs, with its session's uuid and the case's folders in placeholders.
        return [
            [self.hidden(arg).replace(name[len(PREFIX) :], "<uuid>") for arg in call]
            for name, call in self.run_names()
            if name.startswith(PREFIX)
        ]

    def run_log(self):
        # The run log's records, none when the driver wrote none.
        path = runlog.path(str(self.state))
        if not os.path.exists(path):
            return []
        return [json.loads(line) for line in Path(path).read_bytes().decode("utf-8").splitlines()]

    def bodies(self):
        # The bodies the fake gh was given for issue creates and comments, none when gh was not asked.
        if not (self.folder / "gh" / "bodies.jsonl").exists():
            return []
        bodies = read_bodies(self.folder / "gh")
        return [record["body"] for record in bodies if record["args"][:1] == ["issue"]]

    def expected_probe(self, inner):
        # The command box.command builds for the probe, with the same placeholders as probe_runs.
        from driver import box

        command = box.command(
            "docker",
            "img:1",
            str(self.secrets),
            str(self.copy),
            str(self.state),
            str(self.folder / "project"),
            "driver-probe-<uuid>",
            inner,
            stdin=False,
        )
        return [self.hidden(arg) for arg in command[1:]]

    def test_writable_hooks_refuse(self):
        # C10.11: a probe that writes /driver/hooks stops the start with its line; no issue, run log
        # line or session follows, and the probe ran with the arguments of the session's container.
        lines = ["written /driver/hooks", *EXPECTED[1:]]
        self.box("writable-hooks", run=[{"tail": PROBE, "stdout": probe_stdout(lines)}])
        code, out, err = self.run_steps("--once")
        # The exit and stdout first: a report that names a folder would read as an absolute path.
        self.assertEqual((code, out), (2, ""))
        line = "cannot start: the session's container can write `/driver/hooks`"
        self.assertEqual(err.splitlines(), [line])
        self.assertEqual(
            (
                self.gh_of("issue", "create"),
                self.gh_of("issue", "comment"),
                self.run_log(),
                [name for name, _ in self.run_names() if not name.startswith(PREFIX)],
                self.sessions(),
            ),
            ([], [], [], [], []),
        )
        self.assertEqual(self.probe_runs(), [self.expected_probe(PROBE)])
        self.assertNotIn("-i", self.probe_runs()[0])

    def test_unwritable_log_refuses(self):
        # C10.12: a probe that refuses /state/refusals stops the start with its line. The folders the
        # driver mounts are made before the probe runs, though the probe made nothing.
        lines = [*EXPECTED[:4], "refused /state/refusals", EXPECTED[5]]
        self.box("unwritable-log", run=[{"tail": PROBE, "stdout": probe_stdout(lines)}])
        for folder in ("refusals", "claude"):
            shutil.rmtree(self.state / folder, ignore_errors=True)
        code, out, err = self.run_steps("--once")
        line = "cannot start: the session's container cannot write `/state/refusals`"
        made = [os.path.isdir(self.state / folder) for folder in ("refusals", "claude")]
        self.assertEqual((code, out, err.splitlines()), (2, "", [line]))
        self.assertEqual((self.gh_of("issue", "create"), made), ([], [True, True]))

    def test_probe_failure_refuses(self):
        # C10.12: a probe that cannot run, or prints too few lines, stops the start with the line that
        # gives its last stderr line, or "exit <n>" when stderr has none.
        cases = [
            ("no-python", {"stderr": "python: not found\n", "code": 1}, "python: not found"),
            ("five-lines", {"stdout": probe_stdout(EXPECTED[:5])}, "exit 0"),
        ]
        for name, answer, why in cases:
            with self.subTest(name):
                self.box(name, run=[{"tail": PROBE, **answer}])
                code, out, err = self.run_steps("--once")
                line = f"cannot start: the session's container cannot run the probe: {why}"
                self.assertEqual((code, out, err.splitlines()), (2, "", [line]))
                self.assertEqual(self.gh_of("issue", "create"), [])

    def test_on_checks_before_each_step(self):
        # C10.13: on checks before each step. The probe passes before the first session; before the
        # second, it prints written /state, so the second step is refused and no second session runs.
        good = probe_stdout(EXPECTED)
        bad = probe_stdout([*EXPECTED[:2], "written /state", *EXPECTED[3:]])
        self.box(
            "on-two",
            run=[
                {"tail": PROBE, "answers": [{"stdout": good}, {"stdout": bad}]},
                {"tail": ["--session-id", FIRST], "stdout": RESULT},
            ],
        )
        # The session runs in its container (C10.15), so its uuid is the first of the two given.
        with mock.patch("uuid.uuid4", side_effect=[uuid.UUID(FIRST), uuid.UUID(SECOND)]):
            code, _, err = self.run_steps("on")
        starts = [record for record in self.run_log() if record.get("event") == "start"]
        probes = [name for name, _ in self.run_names()]
        # The first probe's uuid is the first session's: the run log's start line names it. Every
        # issue body names that session only, so none was opened or commented for a second one.
        first_uuid = probes[0][len(PREFIX) :] if probes else None
        # The counts first, so that a report holds no uuid and no folder.
        sessions = sum(
            name.startswith("driver-") and not name.startswith(PREFIX) for name in probes
        )
        self.assertEqual((code, sessions, len(starts), len(self.probe_runs())), (2, 1, 1, 2))
        line = "cannot start: the session's container can write `/state`"
        self.assertEqual(err.splitlines()[-1:], [line])
        self.assertEqual(starts[0].get("session"), first_uuid)
        self.assertEqual(
            [name for name in probes if not name.startswith(PREFIX)], [f"driver-{FIRST}"]
        )
        self.assertEqual([b for b in self.bodies() if f"session: {first_uuid}" not in b], [])
