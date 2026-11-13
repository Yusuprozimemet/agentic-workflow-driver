"""The live check on the session image's Claude Code: it takes --output-format stream-json only with
--verbose, and driver.stream reads what it prints. Skipped unless DRIVER_CONTAINER_IMAGE and
DRIVER_CONTAINER_SECRETS are both set; DRIVER_DOCKER picks the docker program (default docker). Runs
two tiny paid sessions (under $0.05 each), and needs the image built by hand (docs/container.md)."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver import stream

TIMEOUT = 120


def detail(completed):
    return (
        f"exit {completed.returncode}: stdout={completed.stdout[-2000:]!r} "
        f"stderr={completed.stderr[-2000:]!r}"
    )


class StreamLiveTest(unittest.TestCase):
    def test_image_takes_stream_json(self):
        # C11.21: the session image's Claude Code prints stream-json with --verbose, and driver.stream
        # reads it: one result with a cost and a session id, and every line a JSON object of a known kind.
        image = os.environ.get("DRIVER_CONTAINER_IMAGE")
        secrets = os.environ.get("DRIVER_CONTAINER_SECRETS")
        if not image or not secrets:
            self.skipTest("DRIVER_CONTAINER_IMAGE and DRIVER_CONTAINER_SECRETS are not both set")
        docker = os.environ.get("DRIVER_DOCKER", "docker")

        def run(flags):
            command = [
                docker,
                "run",
                "--rm",
                "-i",
                "--env-file",
                secrets,
                image,
                "claude",
                "-p",
                "--model",
                "haiku",
                "--output-format",
                "stream-json",
                *flags,
                "--max-budget-usd",
                "0.05",
                "--strict-mcp-config",
            ]
            try:
                return subprocess.run(
                    command,
                    input="Reply with the word ok.\n",
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=TIMEOUT,
                )
            except subprocess.TimeoutExpired:
                self.fail(f"the session did not finish in {TIMEOUT} seconds")

        completed = run(["--verbose"])
        self.assertEqual(completed.returncode, 0, detail(completed))
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        self.assertTrue(lines, detail(completed))
        for line in lines:
            try:
                data = json.loads(line)
            except ValueError:
                self.fail(f"a line of stdout is not JSON: {line!r}")
            self.assertIsInstance(data, dict, detail(completed))
        self.assertEqual(json.loads(lines[0]).get("type"), "system", detail(completed))
        found = stream.result(completed.stdout)
        self.assertIsNotNone(found, detail(completed))
        self.assertIs(found.get("is_error"), False, detail(completed))
        cost = found.get("total_cost_usd")
        self.assertTrue(
            isinstance(cost, (int, float)) and not isinstance(cost, bool), detail(completed)
        )
        self.assertIsInstance(found.get("session_id"), str, detail(completed))
        unparsed = [line for line in lines if stream.kind(line) == "unparsed"]
        self.assertEqual(unparsed, [], detail(completed))

        refused = run([])
        self.assertNotEqual(refused.returncode, 0, detail(refused))
