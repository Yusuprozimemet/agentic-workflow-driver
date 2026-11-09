"""A park's issue body (Day 7, C07.15, H05.4): each park --once opens holds the step, the session, the
branch, the last commit and the uncommitted paths, in that order; a park before a session falls back
to the log's newest session for the step. Each case is a copy of the driver with the fake gh and the
fake claude of tests/test_once.py and tests/test_github.py."""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver import once as once_module
from tests.test_dry_run import drift_of, make_project
from tests.test_github import fake_gh, read_bodies
from tests.test_once import DASHED, driver_copy, once
from tests.test_once_park_issues import CLOSE, build, created_bodies


def write_log(state, session):
    # One session for DASHED's step, started and ended: no crash row, and the newest session for
    # the step's prefix is this one.
    state.mkdir(exist_ok=True)
    records = [
        {
            "event": "start",
            "at": "2026-11-07T00:00:00Z",
            "step": DASHED,
            "prefix": "day-01/track-a",
            "session": session,
            "claude": "2.1.170 (Claude Code)",
        },
        {
            "event": "end",
            "at": "2026-11-07T00:01:00Z",
            "session": session,
            "outcome": "opened: #5 from `day-01/track-a-x`",
            "cost_usd": 0.5,
            "denials": 0,
        },
    ]
    text = "".join(json.dumps(record) + "\n" for record in records)
    (state / "run.jsonl").write_bytes(text.encode("utf-8"))


def untracked_with_log(project, state):
    (project / "stray.txt").write_bytes(b"x\n")
    (project / "b.txt").write_bytes(b"y\n")
    write_log(state, "sess-1")


def untracked(project, state):
    (project / "stray.txt").write_bytes(b"x\n")


def fifty_three(project, state):
    for number in range(53):
        (project / f"f{number:02d}.txt").write_bytes(b"x\n")


def switched(project, state):
    subprocess.run(
        ["git", "switch", "-c", "day-01/track-a-x"], cwd=project, check=True, capture_output=True
    )


def detached(project, state):
    subprocess.run(["git", "checkout", "--detach"], cwd=project, check=True, capture_output=True)


def head_of(folder):
    project = folder / "project"
    done = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, check=True
    )
    return done.stdout.decode("utf-8").strip()[:7]


def expected(line, session, branch, head, paths):
    # The whole body with the stamp fixed; paths are the porcelain lines, already capped.
    listed = ["uncommitted paths: none"] if not paths else ["uncommitted paths:", *paths]
    lines = [
        line,
        "",
        f"step: {DASHED}",
        f"session: {session}",
        f"branch: {branch}",
        f"last commit: {head}",
        *listed,
        "at: STAMP",
        "",
        CLOSE,
    ]
    return "\n".join(lines) + "\n"


class ParkBodyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp()
        cls.copy = driver_copy(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def park_of(self, name, setup):
        # Runs --once in a folder of its own; returns (exit code, the printed line, the park's body).
        folder = Path(self.root) / name
        folder.mkdir()
        code, out, _ = once(self.copy, *build(folder, drift=drift_of(DASHED), setup=setup))
        bodies = [body for body in created_bodies(folder) if CLOSE in body]
        self.assertEqual(len(bodies), 1)
        body, stamps = re.subn(
            r"^at: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
            "at: STAMP",
            bodies[0],
            flags=re.MULTILINE,
        )
        self.assertEqual(stamps, 1)
        return code, out.strip(), body

    def test_dirty_tree(self):
        folder = Path(self.root) / "dirty_tree"
        code, line, body = self.park_of("dirty_tree", untracked_with_log)
        line_of_park = "park: the project's tree is not clean (2 paths)"
        self.assertEqual(
            (code, line, body),
            (
                1,
                line_of_park,
                expected(
                    line_of_park,
                    "sess-1",
                    "main",
                    head_of(folder),
                    ["?? b.txt", "?? stray.txt"],
                ),
            ),
        )

    def test_branch_of_the_step(self):
        folder = Path(self.root) / "branch_of_the_step"
        code, line, body = self.park_of("branch_of_the_step", switched)
        self.assertEqual(
            (code, line, body, "uncommitted paths: none" in body),
            (
                1,
                "park: the project is on day-01/track-a-x, not on main",
                expected(
                    "park: the project is on day-01/track-a-x, not on main",
                    "none",
                    "day-01/track-a-x",
                    head_of(folder),
                    [],
                ),
                True,
            ),
        )

    def test_no_session(self):
        folder = Path(self.root) / "no_session"
        code, line, body = self.park_of("no_session", untracked)
        self.assertEqual(
            (code, line, body),
            (
                1,
                "park: the project's tree is not clean (1 paths)",
                expected(
                    "park: the project's tree is not clean (1 paths)",
                    "none",
                    "main",
                    head_of(folder),
                    ["?? stray.txt"],
                ),
            ),
        )

    def test_none_string_falls_back(self):
        folder = Path(self.root) / "none_string"
        folder.mkdir()
        project = make_project(folder, drift_of(DASHED))
        state = folder / "state"
        write_log(state, "sess-1")
        gh_dir = folder / "gh"
        gh_dir.mkdir()
        gh = fake_gh(gh_dir, runs=[], prs=[])
        once_module.park_issue(str(project), gh, str(state), "park: x", DASHED, "none", [])
        bodies = [
            record["body"]
            for record in read_bodies(gh_dir)
            if record["args"][:2] == ["issue", "create"]
        ]
        self.assertEqual(
            (len(bodies), "session: sess-1" in bodies[0].splitlines()),
            (1, True),
        )

    def test_capped(self):
        folder = Path(self.root) / "capped"
        code, line, body = self.park_of("capped", fifty_three)
        listed = [f"?? f{number:02d}.txt" for number in range(50)] + ["and 3 more"]
        self.assertEqual(
            (code, line, body),
            (
                1,
                "park: the project's tree is not clean (53 paths)",
                expected(
                    "park: the project's tree is not clean (53 paths)",
                    "none",
                    "main",
                    head_of(folder),
                    listed,
                ),
            ),
        )

    def test_detached_head(self):
        folder = Path(self.root) / "detached_head"
        code, line, body = self.park_of("detached_head", detached)
        self.assertEqual(
            (code, line, body),
            (
                1,
                "park: the project is on a detached HEAD, not on main",
                expected(
                    "park: the project is on a detached HEAD, not on main",
                    "none",
                    "detached HEAD",
                    head_of(folder),
                    [],
                ),
            ),
        )
