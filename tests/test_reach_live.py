"""The reach check on the built session image (C10.14): the probe, run as a session's container runs it
with this repository's folders, a scratch state folder and a scratch clone as the project, finds the
folders as the session will see them. Skipped unless DRIVER_CONTAINER_IMAGE names a built image;
DRIVER_DOCKER picks the docker program (default docker), and the image is built by hand (docs/container.md)."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver import box

TIMEOUT = 120


class ReachLiveTest(unittest.TestCase):
    def test_reach_in_the_container(self):
        # C10.14: the probe prints refused for the first three folders and written for the last three,
        # so reach() returns None. Fails on main: hooks/probe.py is missing, before the skip.
        self.assertTrue((ROOT / "hooks" / "probe.py").exists(), "hooks/probe.py does not exist")
        image = os.environ.get("DRIVER_CONTAINER_IMAGE")
        if not image:
            self.skipTest("DRIVER_CONTAINER_IMAGE is not set")
        docker = os.environ.get("DRIVER_DOCKER", "docker")
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        state = os.path.join(tmp, "state")
        for folder in ("refusals", "claude"):
            os.makedirs(os.path.join(state, folder))
        secrets = os.path.join(tmp, "secrets.env")
        with open(secrets, "wb") as f:
            f.write(b"")
        project = os.path.join(tmp, "project")
        clone = ["git", "clone", "-q", str(ROOT), project]
        subprocess.run(clone, capture_output=True, check=True, timeout=TIMEOUT)
        self.assertIsNone(box.reach(docker, image, secrets, str(ROOT), state, project, "live"))
