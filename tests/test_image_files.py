"""The session image's Dockerfile and the container page that tells the maintainer how to build it.
Reads two files and checks the words each one must hold; the built image is checked by
tests/test_image_live.py."""

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DOCKERFILE = "docker/Dockerfile"
DOC = "docs/container.md"
DOCKERFILE_NEEDLES = [
    "FROM node:22-trixie-slim",
    "ARG CLAUDE_VERSION",
    "ARG GIT_NAME",
    "ARG GIT_EMAIL",
    "@anthropic-ai/claude-code@${CLAUDE_VERSION}",
    "/opt/venv",
    "USER node",
    "safe.directory",
    "/work",
    "autocrlf",
    "filemode",
    "gh auth git-credential",
]
DOC_NEEDLES = [
    "docker build",
    "CLAUDE_VERSION",
    "GIT_NAME",
    "claude setup-token",
    "GH_TOKEN",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "container_image",
    "container_secrets",
    "pip install",
    "Do not allow bypassing the above settings",
]
# The six folders the box mounts, named as the page names them: the project, the driver's hooks and
# rules, and the state folder with its refusals and the session's own Claude settings.
MOUNT_SOURCES = {
    "<project>",
    "<home>/hooks",
    "<home>/rules",
    "<state>",
    "<state>/refusals",
    "<state>/claude",
}


class ImageFilesTest(unittest.TestCase):
    def test_dockerfile_and_doc(self):
        # C10.5: the Dockerfile holds the pinned base, the build arguments and the git settings,
        # and the page holds the steps a maintainer follows to build and secure the image.
        # Each file is checked to exist first, so a missing one fails by name.
        self.assertTrue((ROOT / DOCKERFILE).exists(), f"{DOCKERFILE} does not exist")
        self.assertTrue((ROOT / DOC).exists(), f"{DOC} does not exist")
        dockerfile = (ROOT / DOCKERFILE).read_bytes().decode("utf-8")
        doc = (ROOT / DOC).read_bytes().decode("utf-8")
        for needle in DOCKERFILE_NEEDLES:
            with self.subTest(file=DOCKERFILE, needle=needle):
                self.assertIn(needle, dockerfile, f"{DOCKERFILE} does not hold {needle!r}")
        for needle in DOC_NEEDLES:
            with self.subTest(file=DOC, needle=needle):
                self.assertIn(needle, doc, f"{DOC} does not hold {needle!r}")
        completed = subprocess.run(
            [sys.executable, "scripts/check-links.py", DOC],
            check=False,
            cwd=ROOT,
            capture_output=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout.decode("utf-8", "replace"))

    def test_doc_mounts_the_six(self):
        # C10.6: every mount the page shows is one of the six the box makes, and none is a -v flag.
        self.assertTrue((ROOT / DOC).exists(), f"{DOC} does not exist")
        text = (ROOT / DOC).read_bytes().decode("utf-8")
        sources = re.findall(r"source=([^,\s`|]+)", text)
        self.assertTrue(sources, f"{DOC} shows no mount source")
        for source in sources:
            self.assertIn(source, MOUNT_SOURCES, f"{DOC} shows the unknown mount source {source!r}")
        self.assertNotIn("-v ", text, f"{DOC} shows a -v flag")
        self.assertNotIn("--volume", text, f"{DOC} shows a --volume flag")
