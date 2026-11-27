"""Day 16 Track C, C16.12 to C16.14: level 3's entry. At level 2 or 3 a step's start line carries the level in
force and its Day's phase; status counts the phases in a row at level 2 from the run log's phase-end parks and
the switch log; `on` at level 3 starts only when that count is 2, and then runs as level 2 does."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The modules, not the classes: a class imported by name would have its tests collected here again.
from tests import test_escape as escape
from tests import test_level_in_force as level_in_force
from tests import test_status_level as status_level
from tests.test_github import fake_gh
from tests.test_review_loop import ReviewCase, same

LEVEL_3_LINE = "level 3: {} of 2 phases in a row at level 2 with no escape, no merge by hand and no step at level 1"
REFUSAL = (
    "cannot start: level 3 needs 2 of 2 phases in a row at level 2 with no escape, no merge by hand and "
    "no step at level 1; status counts 1"
)
# A step's start line at level 1, and a review's, as Track B left them.
STEP_KEYS = ["event", "at", "step", "prefix", "session", "claude", "issue", "container"]
REVIEW_KEYS = ["event", "at", "step", "prefix", "session", "claude", "pr", "issue", "container"]


def lines_of(records):
    return b"".join(json.dumps(record).encode("utf-8") + b"\n" for record in records)


class StartLevelTest(ReviewCase, unittest.TestCase):
    # EscapeTest's helpers by assignment, as it borrows LevelInForceTest's.
    box = escape.EscapeTest.box
    hidden = escape.EscapeTest.hidden
    run_steps = escape.EscapeTest.run_steps
    holds = escape.EscapeTest.holds
    seed = escape.EscapeTest.seed
    starts = escape.EscapeTest.starts
    build = escape.EscapeTest.build
    case = escape.EscapeTest.case
    on = escape.EscapeTest.on
    steps = escape.EscapeTest.steps

    def test_start_records_level_and_phase(self):
        # C16.12: at level 2 the close's start line carries the level and Day 23's phase (3 in the JSON);
        # after the escape's lowering, Day 24's start line has neither, and no review's start line has.
        self.case("start_level", later=escape.after())
        before = len(self.starts())
        self.on()
        added = self.starts()[before:]
        found = {
            "level": [r.get("level", "none") for r in added],
            "phase": [r.get("phase", "none") for r in added],
        }
        # At level 1 each start line's keys are as today.
        self.case("start_level_one", later=escape.after(), level=None)
        before = len(self.starts())
        self.on()
        found["keys at level 1"] = [list(r) for r in self.starts()[before:]]
        expected = {
            "level": [2, "none", "none", "none"],
            "phase": [3, "none", "none", "none"],
            "keys at level 1": [STEP_KEYS, REVIEW_KEYS, STEP_KEYS, REVIEW_KEYS],
        }
        same(self, found, expected)


class StatusLevel3Test(unittest.TestCase):
    setUp = status_level.StatusLevelTest.setUp
    status_with = status_level.StatusLevelTest.status_with

    def write(self, records, switches=()):
        # The run log and the switch log, as bytes.
        os.makedirs(self.state, exist_ok=True)
        Path(self.state, "run.jsonl").write_bytes(lines_of(records))
        Path(self.state, "switches.jsonl").write_bytes(lines_of(switches))

    def after_level_2(self, out):
        # The line after status's level 2: line, or "none" when it is the last.
        lines = out.splitlines()
        k = next((i for i, line in enumerate(lines) if line.startswith("level 2: ")), None)
        if k is None:
            return "no level 2 line"
        return lines[k + 1] if k + 1 < len(lines) else "none"

    def test_counts(self):
        # C16.13: k counts back from the newest phase-end park, and stops at the first span that fails.
        base = {"project": self.project, "human_only": [], "budget_usd": 5, "steps_per_night": 1}
        all_hold = escape.phase_spans()
        no_level = escape.phase_spans()
        del no_level[0]["level"]
        no_by = escape.phase_spans()
        del no_by[6]["by"]
        reviews = []
        for i, record in enumerate(escape.phase_spans()):
            reviews.append(record)
            if record["event"] == "merged":
                session = f"00000000-0000-4000-8000-{400 + i:012d}"
                reviews += [
                    {
                        "event": "start",
                        "at": record["at"],
                        "step": "Day 01: read the spec against the code, then the spec-change PR",
                        "prefix": "review",
                        "session": session,
                        "claude": "2.1.170",
                        "pr": record["pr"],
                    },
                    {
                        "event": "end",
                        "at": record["at"],
                        "session": session,
                        "outcome": "REVIEW: none",
                        "cost_usd": 0,
                        "denials": 0,
                    },
                ]
        twice = escape.phase_spans()
        twice.append({**twice[-1], "at": "2026-11-20T03:00:00Z"})
        lowering = {
            "event": "level",
            "level": 1,
            "from": 2,
            "escapes": ["D23.4"],
            "at": "2026-11-20T02:01:00Z",
        }
        fixtures = [
            ("all_hold", all_hold, (), 2),
            ("older_start_no_level", no_level, (), 1),
            ("newer_merge_no_by", no_by, (), 0),
            ("lowering_in_newer", all_hold, (lowering,), 0),
            ("review_starts", reviews, (), 2),
            ("park_twice", twice, (), 2),
        ]
        for name, records, switches, k in fixtures:
            with self.subTest(name):
                self.write(records, switches)
                done = self.status_with({**base, "level": 2})
                found = {"level 3 line": self.after_level_2(done.stdout)}
                same(self, found, {"level 3 line": LEVEL_3_LINE.format(k)})
        self.write(all_hold)
        with self.subTest("level_1"):
            done = self.status_with({**base, "level": 1})
            found = {
                "level 3 line": any(x.startswith("level 3:") for x in done.stdout.splitlines())
            }
            same(self, found, {"level 3 line": False})
        with self.subTest("project"):
            gh = fake_gh(self.folder, issues=[])
            done = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "run-steps.py"),
                    "status",
                    "--project",
                    self.project,
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
            lines = done.stdout.splitlines()
            found = {
                "level 2 line": any(x.startswith("level 2:") for x in lines),
                "level 3 line": any(x.startswith("level 3:") for x in lines),
            }
            same(self, found, {"level 2 line": True, "level 3 line": False})


class Level3StartTest(ReviewCase, unittest.TestCase):
    # LevelInForceTest's set-up by assignment, at driver.json's level 3, the run log seeded with the phase
    # spans first.
    box = level_in_force.LevelInForceTest.box
    hidden = level_in_force.LevelInForceTest.hidden
    run_steps = level_in_force.LevelInForceTest.run_steps
    holds = level_in_force.LevelInForceTest.holds
    seed = level_in_force.LevelInForceTest.seed
    starts = level_in_force.LevelInForceTest.starts
    case = level_in_force.LevelInForceTest.case
    on = level_in_force.LevelInForceTest.on

    def start(self, name, spans):
        self.case(name, b"", level=3)
        escape.seed_phases(self.state, spans)
        before = len(self.starts())
        code, _, err = self.on()
        added = [r for r in self.starts()[before:] if r.get("prefix") != "review"]
        return code, err, added

    def test_needs_two_phases(self):
        # C16.14: with the older span's step start at no level, status counts 1, and level 3 refuses.
        spans = escape.phase_spans()
        del spans[0]["level"]
        code, err, added = self.start("three_counts_1", spans)
        found = {
            "code": code,
            "refused": err.splitlines()[-1:],
            "sessions": len(added),
            "merges": len(self.gh_of("pr", "merge")),
        }
        same(self, found, {"code": 2, "refused": [REFUSAL], "sessions": 0, "merges": 0})

    def test_runs_as_level_2(self):
        # C16.14: counting 2, level 3 starts, its start line carries level 3, and the driver merges.
        _, _, added = self.start("three_counts_2", escape.phase_spans())
        found = {
            "sessions": len(added),
            "level": [r.get("level", "none") for r in added],
            "merges": len(self.gh_of("pr", "merge")),
        }
        same(self, found, {"sessions": 1, "level": [3], "merges": 1})
