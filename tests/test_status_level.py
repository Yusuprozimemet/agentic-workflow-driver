"""status prints the level its config names (C15.10): with "level": 2 in driver.json the second line is
`level: 2`, and with no level key it is `level: 1`, as before the key existed. Each test runs the CLI with
--config, as a person runs it, on a scratch project and a fake gh beside it."""

import json
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

from tests.test_github import fake_gh


class StatusLevelTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.project = os.path.join(self.root, "project")
        os.makedirs(self.project)
        self.state = os.path.join(self.root, "state")
        self.folder = Path(self.root, "gh")
        self.folder.mkdir()

    def status_with(self, config):
        # The config is written as bytes, as the driver reads it: text mode would add a carriage return.
        path = Path(self.root, "driver.json")
        path.write_bytes(json.dumps(config).encode("utf-8"))
        gh = fake_gh(self.folder, issues=[])
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "run-steps.py"),
                "status",
                "--config",
                str(path),
                "--state",
                self.state,
                "--gh",
                gh,
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

    def test_config_level(self):
        # The second line is the level line: the first is the mode.
        base = {"project": self.project, "human_only": [], "budget_usd": 5, "steps_per_night": 1}
        done = self.status_with({**base, "level": 2})
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.splitlines()
        self.assertGreater(len(lines), 1)
        self.assertEqual(lines[1], "level: 2")
        done = self.status_with(base)
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = done.stdout.splitlines()
        self.assertGreater(len(lines), 1)
        self.assertEqual(lines[1], "level: 1")
