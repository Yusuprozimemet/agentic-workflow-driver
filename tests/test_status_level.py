"""status prints the level its config names (C15.10): with "level": 2 in driver.json the second line is
`level: 2`, and with no level key it is `level: 1`, as before the key existed. A lowering in the switch log
shows instead, as the level in force (C16.4). Each test runs the CLI with --config, as a person runs it,
on a scratch project and a fake gh beside it."""

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
from tests.test_review_loop import same

LOWERING = {
    "event": "level",
    "level": 1,
    "from": 2,
    "escapes": ["D23.4"],
    "at": "2026-11-27T00:00:00Z",
}
RAISE = {"event": "level", "level": 2, "by": "maintainer", "at": "2026-11-27T01:00:00Z"}
LOWERED = "level: 1, lowered from 2 on an escape: D23.4; run-steps.py raise lifts it"
BY_EVIDENCE = (
    "level: 1, lowered from 2 on a failed evidence run of 0123456; run-steps.py raise lifts it"
)


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

    def switches(self, *records):
        # The switch log as bytes, one JSON line each; the state folder is made here, as setUp does not.
        os.makedirs(self.state, exist_ok=True)
        Path(self.state, "switches.jsonl").write_bytes(
            b"".join(json.dumps(record).encode("utf-8") + b"\n" for record in records)
        )

    def test_lowered_level(self):
        # C16.4: the second line is the level in force and why it is lowered; "from" is the switch log
        # line's, so driver.json's level 3 still reads "lowered from 2". A raise line to 2 under driver.json's
        # 3 is no lowering: the line is level 3's, as before.
        base = {"project": self.project, "human_only": [], "budget_usd": 5, "steps_per_night": 1}
        evidence = {
            "event": "level",
            "level": 1,
            "from": 2,
            "evidence": "0123456789abcdef0123456789abcdef01234567",
        }
        runs = [
            (2, [LOWERING]),
            (2, [LOWERING, RAISE]),
            (2, [evidence]),
            (3, [LOWERING]),
            (3, [RAISE]),
        ]
        found = []
        for level, records in runs:
            self.switches(*records)
            done = self.status_with({**base, "level": level})
            lines = done.stdout.splitlines()
            found.append((done.returncode, lines[1] if len(lines) > 1 else None))
        expected = [
            (0, LOWERED),
            (0, "level: 2"),
            (0, BY_EVIDENCE),
            (0, LOWERED),
            (0, "level: 3"),
        ]
        same(self, tuple(found), tuple(expected))
