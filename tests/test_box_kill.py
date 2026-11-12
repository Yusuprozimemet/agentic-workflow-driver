"""The sessions killed in their container (Day 10, C10.20): past --session-minutes, and on an open
STOP issue, the driver asks docker to kill driver-<session> before the tree kill, and the fake's run
records that it ended by itself. The case builder and the in-process runner are those of
tests/test_box_session.py and tests/test_box_preflight.py; the fake docker of tests/fake_docker.py
waits for the kill."""

import json
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import test_box_preflight as preflight
from tests import test_box_session as box_session
from tests.fake_docker import docker_calls, docker_ended, fake_docker
from tests.test_on import OnCase

# The STOP issue of tests/test_once_stop.py, as the fake gh holds it.
STOP_ISSUE = {"number": 9, "title": "STOP", "labels": [], "state": "open", "author": "me"}


class BoxKillTest(OnCase, unittest.TestCase):
    # The runner and the case builder are borrowed, not inherited: a subclass would run every
    # test of BoxSessionTest again.
    run_steps = preflight.BoxPreflightTest.run_steps
    box = box_session.BoxSessionTest.box
    hidden = box_session.BoxSessionTest.hidden

    def answer(self, run):
        # The case's fake docker again, with the run answers given: box() gives no kill to wait for.
        answers = [box_session.VERSION, box_session.HELP_ANSWER, box_session.PROBE_ANSWER, *run]
        fake_docker(self.folder / "docker", run=answers)

    def test_bound_kills_the_container(self):
        # C10.20, first half: past --session-minutes the container is killed by name, its docker
        # run ends by itself, and the park line is as without a container.
        self.box(
            "bound",
            run=[
                {
                    "tail": ["--session-id", box_session.U],
                    "until_kill": f"driver-{box_session.U}",
                    "code": 137,
                }
            ],
        )
        self.flags = [*self.flags, "--session-minutes", "0.01", "--poll", "0.05"]
        with mock.patch("uuid.uuid4", return_value=uuid.UUID(box_session.U)):
            code, out, _ = self.run_steps("--once")
        park = f"park: the session ran past 0.01 minutes (session `{box_session.U}`)"
        self.assertEqual(
            (
                code,
                park in out.splitlines(),
                ["kill", f"driver-{box_session.U}"] in docker_calls(self.folder / "docker"),
                docker_ended(self.folder / "docker"),
            ),
            (1, True, True, [{"ended": "itself"}]),
        )

    def test_stop_kills_the_container(self):
        # C10.20, second half: an open STOP issue that appears once the session runs stops it, and
        # the container is killed by name first. The run's issue is not in the spec written here,
        # so no report is asserted; the stop and the kill are.
        self.box("stop", run=[])
        gh = self.folder / "gh" / "fake.json"
        spec = json.loads(gh.read_bytes())
        spec["issues"].append(STOP_ISSUE)
        run = {
            "tail": ["--session-id", box_session.U],
            "until_kill": f"driver-{box_session.U}",
            "files": {str(gh): json.dumps(spec)},
            "code": 137,
        }
        self.answer([run])
        self.flags = [*self.flags, "--session-minutes", "5", "--poll", "0.05"]
        # On POSIX the stop kills --once's own group, which here is the test runner: not killed.
        with (
            mock.patch("uuid.uuid4", return_value=uuid.UUID(box_session.U)),
            mock.patch.object(os, "killpg", create=True),
        ):
            code, _, _ = self.run_steps("--once")
        halt = Path(self.state, "halt").read_bytes().decode("utf-8")
        self.assertEqual(
            (
                code,
                ["kill", f"driver-{box_session.U}"] in docker_calls(self.folder / "docker"),
                docker_ended(self.folder / "docker"),
                "STOP issue #9" in halt,
            ),
            (1, True, [{"ended": "itself"}], True),
        )
