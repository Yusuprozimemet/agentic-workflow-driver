"""halt on a session in its container (Day 10, C10.21): with no lock, and the run log's newest pid
line naming a container whose process is gone, halt kills the container by name and says so; a
container that is gone is not said, and one that cannot be killed is said with docker's last stderr
line. The fake docker of tests/fake_docker.py answers the kill."""

import importlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.fake_docker import docker_calls, fake_docker

KILLED = "halt: set; killed container `driver-s1` of session `s1`"
GONE = {
    "stderr": (
        "Error response from daemon: cannot kill container: driver-s1: "
        "No such container: driver-s1\n"
    ),
    "code": 1,
}
DENIED = {"stderr": "permission denied\n", "code": 1}


def gone_pid():
    # A process that has ended: its pid is no longer a live process.
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=10)
    return child.pid


class BoxHaltTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone.
        self.runlog = importlib.import_module("driver.runlog")
        self.lock = importlib.import_module("driver.lock")
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def halt(self, kill):
        # A fresh state and fake docker: a run log whose session s1 names driver-s1 and has a gone
        # pid, no lock, and a kill answered as given. Returns (exit code, stdout lines, calls).
        folder = Path(tempfile.mkdtemp(dir=self.root))
        state = folder / "state"
        started = self.lock.now().strftime(self.lock.STAMP)
        self.runlog.start(state, "x", "day-10/track-d2", "s1", "1", container="driver-s1")
        self.runlog.pid(state, "s1", gone_pid(), started, container="driver-s1")
        (folder / "docker").mkdir()
        docker = fake_docker(folder / "docker", kill=kill)
        command = [sys.executable, str(ROOT / "run-steps.py"), "halt", "--state", str(state)]
        command += ["--docker", docker]
        done = subprocess.run(command, check=False, capture_output=True, text=True)
        return done.returncode, done.stdout.splitlines(), docker_calls(folder / "docker")

    def test_halt_kills_the_container(self):
        # C10.21, first half: the kill exits 0, halt says so, and asks no inspect.
        code, lines, calls = self.halt({})
        self.assertEqual((code, lines, calls), (0, [KILLED], [["kill", "driver-s1"]]))

    def test_halt_container_gone(self):
        # C10.21, second half: a container already gone is not said; one docker cannot kill is said
        # with its last stderr line, and the "no driver" line follows.
        code, lines, _ = self.halt(GONE)
        self.assertEqual((code, lines), (0, ["halt: set; no driver is running"]))
        code, lines, _ = self.halt(DENIED)
        denied = "halt: set; could not kill container `driver-s1`: permission denied"
        self.assertEqual((code, lines), (0, [denied, "halt: set; no driver is running"]))
