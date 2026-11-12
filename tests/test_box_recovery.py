"""Recovery on a session in its container (Day 10, C10.22): a run log whose newest pid line names
driver-s1, with a pid that is gone, waits while docker says the container runs, and parks as the
crash park of Day 7 when docker says it does not. No session starts in either case. The fake
docker of tests/fake_docker.py answers the inspect; the case builder is that of
tests/test_box_session.py."""

import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import test_box_preflight as preflight
from tests import test_box_session as box_session
from tests.fake_docker import docker_calls, fake_docker
from tests.test_box_halt import gone_pid
from tests.test_on import OnCase
from tests.test_once import DASHED

WAIT = "wait: session `s1` is still running (container `driver-s1`)"
PARK = "park: the run log names session `s1` for this step, with no end"


class BoxRecoveryTest(OnCase, unittest.TestCase):
    # The runner and the case builder are borrowed, not inherited: a subclass would run every
    # test of BoxSessionTest again.
    run_steps = preflight.BoxPreflightTest.run_steps
    box = box_session.BoxSessionTest.box
    hidden = box_session.BoxSessionTest.hidden

    def crashed(self, name, inspect):
        # A case with no session started: its run log holds session s1 for the step the case
        # reaches, in driver-s1, with a gone pid, and docker answers the inspect as given. Returns
        # (exit code, stdout lines, docker calls).
        self.box(name, run=[])
        answers = [box_session.VERSION, box_session.HELP_ANSWER, box_session.PROBE_ANSWER]
        fake_docker(self.folder / "docker", run=answers, inspect=inspect)
        runlog = importlib.import_module("driver.runlog")
        lock = importlib.import_module("driver.lock")
        prefix = importlib.import_module("driver.steps").classify(DASHED).prefix
        runlog.start(self.state, DASHED, prefix, "s1", "2.1.170", container="driver-s1")
        started = lock.now().strftime(lock.STAMP)
        runlog.pid(self.state, "s1", gone_pid(), started, container="driver-s1")
        code, out, _ = self.run_steps("--once")
        return code, out.splitlines(), docker_calls(self.folder / "docker")

    def test_running_container_waits(self):
        # C10.22, first half: docker says the container runs, so --once waits and starts nothing.
        code, lines, calls = self.crashed("running", {"stdout": "true\n"})
        runs = [call for call in calls if call[:1] == ["run"]]
        self.assertEqual(
            (
                code,
                WAIT in lines,
                ["inspect", "--format", "{{.State.Running}}", "driver-s1"] in calls,
                any("--session-id" in call for call in runs),
            ),
            (0, True, True, False),
        )

    def test_stopped_container_parks(self):
        # C10.22, second half: docker says the container is stopped, or that there is none; the
        # row is the crash park as today, and no wait is printed.
        cases = [
            ("stopped", {"stdout": "false\n"}),
            ("missing", {"stderr": "error: no such object: driver-s1\n", "code": 1}),
        ]
        for name, inspect in cases:
            with self.subTest(name):
                code, lines, _ = self.crashed(name, inspect)
                waits = [line for line in lines if line.startswith("wait: session")]
                self.assertEqual((code, PARK in lines, waits), (1, True, []))
