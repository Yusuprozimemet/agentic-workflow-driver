"""--once's start checks (C05.6): a STOP issue of the maintainer's halts the run before any step, the
parked issues make it wait, a phase's end and a step that failed twice park until the maintainer
closes the park issue of that exact title, an unreadable project refuses, and a stale run.json is
removed. Each case is a copy of the driver with the fake gh and the fake claude of tests/test_once.py;
a case that starts a session has one session call recorded."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import START, drift_of, make_project
from tests.test_github import fake_gh, read_calls
from tests.test_once import (
    DASHED,
    OPENED,
    STEP_PR,
    driver_copy,
    fake_claude,
    once,
    write_config,
)

STOP_LINE = "cannot start: halted: the STOP issue #4 is open; close it, then run-steps.py clear"
PHASE_STEP = "Day 03: read the spec against the code, then the spec-change PR"
PHASE_PARK = "park: the end of Phase 0: Day 03 starts Phase 1"
FIRST = "11111111-0000-4000-8000-000000000000"
SECOND = "22222222-0000-4000-8000-000000000000"
FAILED_PARK = f"park: the step failed twice: sessions `{FIRST}` and `{SECOND}`"
GH_LINE = "cannot read the project: gh issue list exited 1"


def issue(number, title, author="me", labels=(), state="open"):
    return {
        "number": number,
        "title": title,
        "labels": list(labels),
        "state": state,
        "author": author,
    }


def phase_drift():
    # Day 03 is the first day of Phase 1; Days 01 and 02 end Phase 0.
    return {
        "now": {"next_step": PHASE_STEP, "open_prs": []},
        "order": [1, 2, 3],
        "days": [
            {"day": 1, "phase": 0, "status": "planned"},
            {"day": 2, "phase": 0, "status": "planned"},
            {"day": 3, "phase": 1, "status": "planned"},
        ],
        "meta": {"caveats": []},
    }


def stale(state):
    # A run.json an earlier run left behind: --once must remove it once it holds the lock.
    state.mkdir(parents=True, exist_ok=True)
    (state / "run.json").write_bytes(b"{}")


def failed_twice(state):
    # Two sessions of the step's prefix, each ended as a park, and none left open.
    state.mkdir(parents=True, exist_ok=True)
    records = []
    for session in (FIRST, SECOND):
        records.append(
            {
                "event": "start",
                "at": "2026-11-07T00:00:00Z",
                "step": START,
                "prefix": "day-01/spec",
                "session": session,
                "claude": "2.1.170 (Claude Code)",
            }
        )
        records.append(
            {
                "event": "end",
                "at": "2026-11-07T00:01:00Z",
                "session": session,
                "outcome": f"park: the session parked: stuck (session `{session}`)",
                "cost_usd": 0.5,
                "denials": 0,
            }
        )
    body = "".join(json.dumps(record) + "\n" for record in records)
    (state / "run.jsonl").write_bytes(body.encode("utf-8"))


class OnceParksTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp()
        cls.copy = driver_copy(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    @classmethod
    def run_case(cls, name, drift=None, issues=None, issue_code=0, setup=None):
        folder = Path(cls.root) / name
        folder.mkdir()
        project = make_project(folder, drift)
        state = folder / "state"
        claude_dir, gh_dir = folder / "claude", folder / "gh"
        claude_dir.mkdir()
        gh_dir.mkdir()
        claude = fake_claude(claude_dir)
        runs = [{"status": "completed", "conclusion": "success"}]
        gh = fake_gh(gh_dir, runs=runs, prs=[STEP_PR], issues=issues, issue_code=issue_code)
        config = write_config(folder, project)
        if setup is not None:
            setup(state)
        flags = ["--config", str(config), "--state", str(state), "--claude", claude, "--gh", gh]
        code, out, err = once(cls.copy, *flags)
        calls = read_calls(claude_dir) if (claude_dir / "calls.jsonl").exists() else []
        # The probes are --version and --help; any other call is a session.
        sessions = [call for call in calls if call["args"] not in (["--version"], ["--help"])]
        return {"code": code, "out": out, "err": err, "sessions": sessions, "state": state}

    def test_stop_at_start(self):
        result = self.run_case("stop", issues=[issue(4, "STOP now")])
        halt = (result["state"] / "halt").read_bytes().decode("utf-8")
        self.assertEqual(
            (
                result["err"].strip(),
                result["out"],
                result["code"],
                halt.endswith("STOP issue #4"),
                len(result["sessions"]),
            ),
            (STOP_LINE, "", 2, True, 0),
        )

    def test_stop_from_another_author(self):
        result = self.run_case(
            "stop_other",
            drift=drift_of(DASHED),
            issues=[issue(5, "STOP now", author="someone")],
        )
        self.assertEqual(
            (result["code"], result["out"].rstrip("\r\n"), len(result["sessions"])),
            (0, OPENED, 1),
        )

    def test_wait_on_parked(self):
        result = self.run_case(
            "wait",
            issues=[
                issue(5, "Day 03 park", labels=["parked"]),
                issue(3, "Day 02 park", labels=["parked"]),
            ],
        )
        self.assertEqual(
            (
                result["out"].rstrip("\r\n"),
                result["err"],
                result["code"],
                len(result["sessions"]),
            ),
            ("wait: parked #3, #5", "", 0, 0),
        )

    def test_phase_end_answered(self):
        parked = self.run_case("phase_open", drift=phase_drift())
        answered = self.run_case(
            "phase_answered",
            drift=phase_drift(),
            issues=[issue(6, PHASE_PARK, labels=["parked"], state="closed")],
        )
        self.assertEqual(
            (
                parked["out"].rstrip("\r\n"),
                parked["code"],
                len(parked["sessions"]),
                len(answered["sessions"]),
            ),
            (PHASE_PARK, 1, 0, 1),
        )

    def test_failed_twice(self):
        parked = self.run_case("failed_open", setup=failed_twice)
        answered = self.run_case(
            "failed_answered",
            setup=failed_twice,
            issues=[issue(7, FAILED_PARK, labels=["parked"], state="closed")],
        )
        self.assertEqual(
            (
                parked["out"].rstrip("\r\n"),
                parked["code"],
                len(parked["sessions"]),
                len(answered["sessions"]),
            ),
            (FAILED_PARK, 1, 0, 1),
        )

    def test_issues_unreadable(self):
        result = self.run_case("unreadable", issue_code=1)
        self.assertEqual(
            (result["err"].strip(), result["code"], len(result["sessions"])),
            (GH_LINE, 2, 0),
        )

    def test_stale_run_json_removed(self):
        waited = self.run_case(
            "stale_wait",
            setup=stale,
            issues=[issue(3, "Day 02 park", labels=["parked"])],
        )
        passed = self.run_case("stale_passes", setup=stale, drift=drift_of(DASHED))
        self.assertEqual(
            ((waited["state"] / "run.json").exists(), (passed["state"] / "run.json").exists()),
            (False, False),
        )
