"""The live check on the built session image: the tools a step needs are in it, and the git settings
and the user are the ones docker/Dockerfile sets. Skipped unless DRIVER_CONTAINER_IMAGE names a built
image; DRIVER_DOCKER picks the docker program (default docker). Starts a container per check, and
needs the image built by hand (docs/container.md)."""

import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver import box

TIMEOUT = 120


def detail(completed):
    return (
        f"exit {completed.returncode}: stdout={completed.stdout[-2000:]!r} "
        f"stderr={completed.stderr[-2000:]!r}"
    )


class ImageLiveTest(unittest.TestCase):
    def test_image_has_its_tools(self):
        # C10.7: the image runs the session's tools as the node user, with the git settings the
        # Dockerfile wrote, and Claude Code at the version the image was built with.
        self.assertTrue(
            (ROOT / "docker" / "Dockerfile").exists(), "docker/Dockerfile does not exist"
        )
        image = os.environ.get("DRIVER_CONTAINER_IMAGE")
        if not image:
            self.skipTest("DRIVER_CONTAINER_IMAGE is not set")
        self.assertIn(":", image, "DRIVER_CONTAINER_IMAGE has no tag after a colon")
        tag = image.rsplit(":", 1)[1]
        docker = os.environ.get("DRIVER_DOCKER", "docker")
        with tempfile.TemporaryDirectory() as tmp:
            home = os.path.join(tmp, "home")
            state = os.path.join(tmp, "state")
            project = os.path.join(tmp, "project")
            for folder in ["home/hooks", "home/rules", "state/refusals", "state/claude", "project"]:
                os.makedirs(os.path.join(tmp, folder))
            secrets = os.path.join(tmp, "secrets.env")
            with open(secrets, "wb") as f:
                f.write(b"")

            def run(inner):
                name = f"driver-image-test-{uuid.uuid4().hex[:12]}"
                command = box.command(
                    docker, image, secrets, home, state, project, name, inner, stdin=False
                )
                try:
                    return subprocess.run(
                        command,
                        check=False,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        timeout=TIMEOUT,
                    )
                except subprocess.TimeoutExpired:
                    self.fail(f"{' '.join(inner)} did not finish in {TIMEOUT} seconds")

            def check(inner, ok):
                with self.subTest(command=" ".join(inner)):
                    completed = run(inner)
                    self.assertEqual(completed.returncode, 0, detail(completed))
                    if ok is not None:
                        self.assertTrue(ok(completed.stdout), detail(completed))

            check(["python", "--version"], lambda out: out.startswith("Python 3"))
            check(["pip", "--version"], None)
            check(
                ["git", "config", "--system", "--get", "safe.directory"],
                lambda out: out.strip() == "/work",
            )
            check(
                ["git", "config", "--system", "--get", "core.autocrlf"],
                lambda out: out.strip() == "true",
            )
            check(["id", "-un"], lambda out: out.strip() == "node")
            check(
                ["claude", "--version"],
                lambda out: (out.splitlines() or [""])[0].startswith(tag),
            )
