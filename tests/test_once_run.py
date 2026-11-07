"""--once's run issue (C05.8): each step opens one issue, "Driver run <stamp>", and its session's outcome
is the comment that closes it. An open run issue from before is commented on, not doubled. While the
session runs, run.json beside the state holds the run's record, and it is gone after the step. Each
case is a copy of the driver with the fake claude and the fake gh of tests/test_once.py and
tests/test_github.py."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import drift_of
from tests.test_github import read_bodies, read_calls
from tests.test_once import DASHED, OPENED, driver_copy, once
from tests.test_once_outcome import GH_DOWN
from tests.test_once_park_issues import PARK_STEM, PARKED, build, gh_calls, gh_issues

RUN_KEYS = {"project", "gh", "issue", "step", "session"}
# Run by the fake claude inside the session: keeps the run.json the session finds in the state.
SEEN_RUN = '(folder / "seen-run.json").write_bytes((state / "run.json").read_bytes())'


def comments(folder):
    # The bodies of the fake gh's `issue comment` calls, in the order they were made.
    bodies = read_bodies(folder / "gh")
    return [record["body"] for record in bodies if record["args"][:2] == ["issue", "comment"]]


def start_session(state):
    # The session of the run log's start line: the uuid the run's issue and run.json name.
    lines = (state / "run.jsonl").read_text(encoding="utf-8").splitlines()
    records = (json.loads(line) for line in lines)
    return next(record for record in records if record["event"] == "start")["session"]


class OnceRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp()
        cls.copy = driver_copy(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def folder_of(self, name):
        folder = Path(self.root) / name
        folder.mkdir()
        return folder

    def test_run_json_during_session(self):
        folder = self.folder_of("run_json")
        flags = build(folder, drift=drift_of(DASHED), do=SEEN_RUN)
        code, _, _ = once(self.copy, *flags)
        state = folder / "state"
        seen = json.loads((folder / "claude" / "seen-run.json").read_bytes())
        self.assertEqual(
            (
                sorted(seen),
                seen["issue"],
                seen["session"] == start_session(state),
                seen["step"] == DASHED,
                (state / "run.json").exists(),
                code,
            ),
            (sorted(RUN_KEYS), 1, True, True, False, 0),
        )

    def test_run_issue_closed(self):
        folder = self.folder_of("closed")
        flags = build(folder, drift=drift_of(DASHED))
        code, out, _ = once(self.copy, *flags)
        issues = gh_issues(folder)
        self.assertEqual(
            (
                len(issues),
                issues[0]["title"].startswith("Driver run "),
                issues[0]["labels"],
                issues[0]["state"],
                [comment.splitlines()[0] for comment in comments(folder)],
                out.strip(),
                code,
            ),
            (1, True, [], "closed", [OPENED], OPENED, 0),
        )

    def test_run_issue_reused(self):
        folder = self.folder_of("reused")
        flags = build(folder, drift=drift_of(DASHED))
        # An open run issue from an earlier run: build has no issues parameter, so it goes in here.
        spec_file = folder / "gh" / "fake.json"
        spec = json.loads(spec_file.read_bytes())
        spec["issues"] = [
            {
                "number": 3,
                "title": "Driver run 2026-11-07T00:00:00Z",
                "labels": [],
                "state": "open",
                "author": "me",
            }
        ]
        spec_file.write_bytes(json.dumps(spec).encode("utf-8"))
        code, _, _ = once(self.copy, *flags)
        self.assertEqual(
            (
                len(gh_calls(folder, ["issue", "create"])),
                [(i["number"], i["state"]) for i in gh_issues(folder)],
                [call[2] for call in gh_calls(folder, ["issue", "comment"])],
                code,
            ),
            (0, [(3, "closed")], ["3", "3"], 0),
        )

    def test_park_on_run_issue(self):
        folder = self.folder_of("park_on_run")
        flags = build(folder, drift=drift_of(DASHED), result=PARKED)
        code, out, _ = once(self.copy, *flags)
        run_issue = gh_issues(folder)[0]
        closing = (comments(folder) or [""])[-1].splitlines()
        self.assertEqual(
            (
                len(out.splitlines()),
                out.startswith(PARK_STEM),
                run_issue["title"].startswith("Driver run "),
                run_issue["state"],
                out.strip() in closing,
                "parked: #2" in closing,
                code,
            ),
            (1, True, True, "closed", True, True, 1),
        )

    def test_halt_during_step_reported(self):
        # Its own copy: the session commits in it, and the copy is the driver's, not the shared one.
        copy = driver_copy(tempfile.mkdtemp(dir=self.root))
        folder = self.folder_of("halt_run")
        # The identity is given on the command line, as in test_once_outcome's driver_moved case.
        do = (
            "import subprocess; subprocess.run(['git', '-c', 'user.name=t', '-c', "
            "'user.email=t@t', '-C', "
            f"{str(copy)!r}, 'commit', '--allow-empty', '-m', 'x'], check=True, "
            "capture_output=True)"
        )
        flags = build(folder, drift=drift_of(DASHED), do=do)
        code, _, _ = once(copy, *flags)
        run_issue = gh_issues(folder)[0]
        closing = (comments(folder) or [""])[-1]
        self.assertEqual(
            (
                code,
                run_issue["state"],
                [
                    text in closing
                    for text in (
                        "halt: set during the step",
                        "halted at ",
                        "branch: ",
                        "last commit: ",
                    )
                ],
            ),
            (1, "closed", [True, True, True, True]),
        )

    def test_no_call_after_gh_fails(self):
        folder = self.folder_of("gh_down")
        flags = build(folder, drift=drift_of(DASHED), do=GH_DOWN)
        code, _, _ = once(self.copy, *flags)
        calls = [call[:2] for call in read_calls(folder / "gh")]
        after = calls[calls.index(["pr", "list"]) + 1 :]
        self.assertEqual(
            (
                after,
                gh_issues(folder)[0]["state"],
                code,
                (folder / "state" / "run.json").exists(),
            ),
            ([], "open", 2, False),
        )
