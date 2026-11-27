"""Day 16, C16.2: run-steps.py raise lifts the level in force back to driver.json's. It writes the raise line
to the switch log when a lowering holds the level below the config's, says "already" and writes nothing when
it does not, and refuses --project, which carries no level. Each test runs the CLI as a person runs it, on a
scratch state folder; raise calls no gh."""

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

from tests.test_review_loop import same, without_at

LOWERING = {
    "event": "level",
    "level": 1,
    "from": 2,
    "escapes": ["D23.4"],
    "at": "2026-11-27T00:00:00Z",
}
RAISED = "level: raised to 2, driver.json's"
ALREADY = "raise: the level is already 2, driver.json's"
UNREADABLE_LINE = (
    "cannot raise: the level cannot be read: <state>/switches.jsonl: line 2 cannot be read"
)
NEEDS_CONFIG = "cannot raise: raise reads the level from driver.json; give --config, not --project"


class RaiseTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.project = os.path.join(self.root, "project")
        os.makedirs(self.project)
        self.state = os.path.join(self.root, "state")
        os.makedirs(self.state)
        # Written as bytes, as the driver reads them: text mode would add a carriage return.
        self.config = Path(self.root, "driver.json")
        config = {
            "project": self.project,
            "human_only": [],
            "budget_usd": 5,
            "steps_per_night": 1,
            "level": 2,
        }
        self.config.write_bytes(json.dumps(config).encode("utf-8"))
        self.log = Path(self.state, "switches.jsonl")
        lines = [{"event": "on", "at": "2026-11-26T00:00:00Z"}, LOWERING]
        self.log.write_bytes(b"".join(json.dumps(r).encode("utf-8") + b"\n" for r in lines))

    def raise_with(self, *flags):
        return subprocess.run(
            [sys.executable, str(ROOT / "run-steps.py"), "raise", *flags],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )

    def switches(self, state):
        path = Path(state, "switches.jsonl")
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_bytes().splitlines()]

    def unreadable(self):
        # raise on a switch log whose second line is not JSON: its code and its stderr lines, the state
        # folder held as <state> in each spelling, the longer first, and the separator as /.
        state = os.path.join(self.root, "unreadable")
        os.makedirs(state)
        Path(state, "switches.jsonl").write_bytes(b'{"event": "on", "at": "x"}\n{\n')
        done = self.raise_with("--config", str(self.config), "--state", state)
        lines = []
        for line in done.stderr.splitlines():
            for form in sorted({state, os.path.realpath(state)}, key=len, reverse=True):
                line = line.replace(form, "<state>")
            lines.append(line.replace("\\", "/"))
        return done.returncode, lines

    def test_raise_then_already(self):
        # C16.2: the first raise lifts the lowering; the second finds the level already driver.json's and
        # appends nothing, and so does a raise on a state folder with no switch log.
        first = self.raise_with("--config", str(self.config), "--state", self.state)
        after_first = self.switches(self.state)
        second = self.raise_with("--config", str(self.config), "--state", self.state)
        added = len(self.switches(self.state)) - len(after_first)
        fresh = os.path.join(self.root, "fresh")
        third = self.raise_with("--config", str(self.config), "--state", fresh)
        found = (
            first.returncode,
            first.stdout.splitlines(),
            without_at(after_first[-1]) if after_first else None,
            second.returncode,
            second.stdout.splitlines(),
            added,
            third.returncode,
            third.stdout.splitlines(),
            Path(fresh, "switches.jsonl").exists(),
            *self.unreadable(),
        )
        expected = (
            0,
            [RAISED],
            {"event": "level", "level": 2, "by": "maintainer"},
            1,
            [ALREADY],
            0,
            1,
            [ALREADY],
            False,
            2,
            [UNREADABLE_LINE],
        )
        same(self, found, expected)

    def test_raise_needs_the_config(self):
        # C16.2: --project names no driver.json, so there is no level to raise to; the switch log is untouched.
        before = self.log.read_bytes()
        done = self.raise_with("--project", self.project, "--state", self.state)
        found = (done.returncode, done.stderr.splitlines(), self.log.read_bytes() == before)
        same(self, found, (2, [NEEDS_CONFIG], True))
