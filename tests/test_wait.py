"""The wait on a pull request's required checks (driver/loop.py, C06.4 and C06.5): checks red, red,
green resume the session twice; red after two fixes parks; red with no session parks; no checks
parks after --wait-minutes; two open pull requests park before any check is read; and a halt file,
a STOP issue or the run's issue closed ends the wait while the checks are pending. A failed read of
the issues is skipped, and bounded by --wait-minutes. Each case runs the functions with the fake
claude of tests/test_once.py and the fake gh of tests/test_github.py."""

import importlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_github import JOB, fake_gh, read_bodies, read_calls
from tests.test_once import fake_claude

SESSION = "00000000-0000-4000-8000-000000000000"
STEP = "Day 01 Track A: the first track"
RUN_ISSUE = {"number": 7, "title": "Driver run x", "labels": [], "state": "open", "author": "me"}
STOP_ISSUE = {"number": 9, "title": "STOP", "labels": [], "state": "open", "author": "me"}
PR = {"number": 12, "headRefName": "day-01/track-a-x", "url": "u", "author": "me"}
OPENED = "opened: #12 from `day-01/track-a-x`"
# Exit 0: with --json, gh 2.93.0 writes the rows and returns before its failed-check exit code.
RED = {"code": 0, "out": [{"name": "tests", "bucket": "fail", "link": JOB}]}
GREEN = {"code": 0, "out": [{"name": "tests", "bucket": "pass", "link": JOB}]}
PENDING = {"code": 8, "out": [{"name": "tests", "bucket": "pending", "link": JOB}]}
NONE = {"code": 0, "out": []}
LOGS = [{"code": 0, "out": "one\nboom\n"}]
# Run by the fake claude in each session: counts the fix lines in the run log, one line per session.
COUNT_FIXES = """lines = (state / "run.jsonl").read_bytes().splitlines()
count = sum(b'"event": "fix"' in line for line in lines)
with (folder / "fixes.txt").open("ab") as counted:
    counted.write(str(count).encode("utf-8") + b"\\n")
"""


class WaitTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top, as in test_github: where driver/loop.py is missing, each
        # test fails alone with ModuleNotFoundError.
        self.loop = importlib.import_module("driver.loop")

    def build(self, checks, issues=None, prs=(PR,), issue_code=0, wait_minutes=30):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        for name in ("gh", "claude", "state", "project"):
            (folder / name).mkdir()
        gh = fake_gh(
            folder / "gh",
            prs=list(prs),
            issues=[RUN_ISSUE] if issues is None else issues,
            checks=checks,
            logs=LOGS,
            issue_code=issue_code,
        )
        claude = fake_claude(folder / "claude", do=COUNT_FIXES)
        self.folder = folder
        self.project = str(folder / "project")
        self.args = SimpleNamespace(
            state=str(folder / "state"), gh=gh, poll=0.01, wait_minutes=wait_minutes
        )
        self.record = {"issue": 7, "step": STEP, "session": SESSION}
        self.command = [
            claude,
            "-p",
            "--settings",
            str(folder / "state" / "settings.json"),
            "--session-id",
            SESSION,
        ]

    def gh_of(self, *prefix):
        # The recorded gh calls that begin with prefix; each call is its argument list.
        if not (self.folder / "gh" / "calls.jsonl").exists():
            return []
        calls = read_calls(self.folder / "gh")
        return [call for call in calls if call[: len(prefix)] == list(prefix)]

    def sessions(self):
        # The session calls, not the --version and --help probes, which carry no session.
        if not (self.folder / "claude" / "calls.jsonl").exists():
            return []
        calls = read_calls(self.folder / "claude")
        return [call for call in calls if call["args"] not in (["--version"], ["--help"])]

    def on_sleep(self, change):
        # change runs during the first sleep only, so that the next poll reads what it wrote. A wait
        # that does not end on it fails here, instead of polling for ever.
        ran = []

        def once_only(poll):
            ran.append(poll)
            if len(ran) == 1:
                change()
            elif len(ran) > 5:
                raise AssertionError("the wait did not end on what the first sleep changed")

        return mock.patch.object(self.loop, "sleep", side_effect=once_only)

    def test_red_resumed_twice_then_green(self):
        self.build([RED, RED, GREEN])
        result = self.loop.wait_pr(self.args, self.project, 12, self.record, self.command)
        self.assertEqual(result, (None, 0))
        sessions = self.sessions()
        self.assertEqual(len(sessions), 2)
        for session in sessions:
            args = session["args"]
            self.assertIn("--resume", args)
            self.assertEqual(args[args.index("--resume") + 1], SESSION)
            self.assertNotIn("--session-id", args)
            prompt = bytes.fromhex(session["stdin"]).decode("utf-8")
            self.assertTrue(prompt.startswith("The required checks failed on #12: tests."))
            self.assertIn("boom", prompt)
            self.assertTrue(prompt.endswith("Fix this step's pull request, push, and stop.\n"))
        self.assertEqual(self.gh_of("pr", "view"), [])
        fixes = (self.folder / "claude" / "fixes.txt").read_bytes().split()
        self.assertEqual(fixes, [b"1", b"2"])
        lines = (self.folder / "state" / "run.jsonl").read_bytes().decode("utf-8").splitlines()
        records = [json.loads(line) for line in lines]
        ends = [record for record in records if record["event"] == "end"]
        self.assertEqual([record["outcome"] for record in ends], [OPENED, OPENED])
        fix_lines = [record for record in records if record["event"] == "fix"]
        self.assertEqual([(record["n"], record["pr"]) for record in fix_lines], [(1, 12), (2, 12)])

    def test_red_after_two_fixes_parks(self):
        self.build([RED])
        result = self.loop.wait_pr(self.args, self.project, 12, self.record, self.command)
        self.assertEqual(
            result, ("park: the checks on #12 are still red after two fixes: tests", 1)
        )
        self.assertEqual(len(self.sessions()), 2)

    def test_red_without_session_parks(self):
        self.build([RED])
        result = self.loop.wait_found(self.args, self.project, "wait: #12", self.record)
        self.assertEqual(result, ("park: the checks on #12 are red: tests", 1))
        self.assertEqual(self.sessions(), [])
        self.assertEqual(self.gh_of("run", "view"), [])

    def test_no_checks_parks(self):
        self.build([NONE], wait_minutes=0.01)
        result = self.loop.wait_pr(self.args, self.project, 12, self.record, self.command)
        self.assertEqual(result, ("park: no required checks on #12 after 0.01 minutes", 1))

    def test_two_open_prs_park(self):
        self.build([GREEN])
        result = self.loop.wait_found(self.args, self.project, "wait: #3, #5", self.record)
        self.assertEqual(result, ("park: more than one open pull request: #3, #5", 1))
        self.assertEqual(self.gh_of("pr", "checks"), [])

    def test_halt_during_wait(self):
        self.build([PENDING])

        def halt():
            (self.folder / "state" / "halt").write_bytes(b"halted")

        with self.on_sleep(halt):
            line, code = self.loop.wait_pr(self.args, self.project, 12, self.record, self.command)
        self.assertEqual(code, 1)
        self.assertTrue(line.startswith("halt:"))
        # The second poll read the halt file before it read the checks.
        self.assertEqual(len(self.gh_of("pr", "checks")), 1)
        self.assertEqual(self.sessions(), [])

    def test_stop_during_wait(self):
        self.build([PENDING])

        def add_stop():
            path = self.folder / "gh" / "fake.json"
            spec = json.loads(path.read_bytes())
            spec["issues"].append(STOP_ISSUE)
            path.write_bytes(json.dumps(spec).encode("utf-8"))

        with self.on_sleep(add_stop):
            result = self.loop.wait_pr(self.args, self.project, 12, self.record, self.command)
        self.assertEqual(result, ("halt: the STOP issue #9 is open; nothing more starts", 1))
        halt = (self.folder / "state" / "halt").read_bytes().decode("utf-8")
        self.assertIn("STOP issue #9", halt)
        bodies = [
            body
            for body in read_bodies(self.folder / "gh")
            if body["args"][:3] == ["issue", "comment", "7"]
        ]
        self.assertEqual(len(bodies), 1)
        self.assertIn("halted at ", bodies[0]["body"])
        self.assertIn("step: " + STEP, bodies[0]["body"])
        self.assertIn("session: " + SESSION, bodies[0]["body"])
        self.assertEqual(len(self.gh_of("issue", "close", "7")), 1)
        self.assertEqual(len(self.gh_of("pr", "checks")), 1)
        self.assertEqual(self.sessions(), [])

    def test_off_during_wait(self):
        self.build([PENDING])

        def close_run():
            path = self.folder / "gh" / "fake.json"
            spec = json.loads(path.read_bytes())
            for issue in spec["issues"]:
                if issue["number"] == 7:
                    issue["state"] = "closed"
            path.write_bytes(json.dumps(spec).encode("utf-8"))

        with self.on_sleep(close_run):
            result = self.loop.wait_pr(self.args, self.project, 12, self.record, self.command)
        self.assertEqual(result, ("off: the run's issue #7 is closed; nothing new starts", 0))
        self.assertEqual(self.gh_of("pr", "close"), [])
        self.assertEqual(self.gh_of("issue", "comment"), [])
        self.assertEqual(self.sessions(), [])

    def test_failed_read_skipped(self):
        self.build([GREEN], issue_code=1)

        def heal():
            path = self.folder / "gh" / "fake.json"
            spec = json.loads(path.read_bytes())
            spec["issue_code"] = 0
            path.write_bytes(json.dumps(spec).encode("utf-8"))

        with self.on_sleep(heal):
            result = self.loop.wait_pr(self.args, self.project, 12, self.record, self.command)
        self.assertEqual(result, (None, 0))
        # Nothing was read from the checks while the issues could not be read.
        self.assertEqual(len(self.gh_of("pr", "checks")), 1)

    def test_failed_read_bounded(self):
        self.build([GREEN], issue_code=1, wait_minutes=0.01)
        result = self.loop.wait_pr(self.args, self.project, 12, self.record, self.command)
        self.assertEqual(result, ("cannot read the project: gh issue list exited 1", 2))
        self.assertEqual(self.gh_of("pr", "checks"), [])
