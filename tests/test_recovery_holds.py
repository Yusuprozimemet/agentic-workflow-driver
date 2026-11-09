"""Day 07's holds (C07.1, C07.14, C07.21): what the table of "Recovery" does on today's code and must
keep doing. RecoveryRulesTest reads the driver's files with ast: no command that can lose work, no
pull request opened or closed, no shell. RecoveryHoldTest runs a driver copy with the fake gh and
claude of tests/test_once.py and tests/test_github.py, and a run log the test writes."""

import ast
import importlib
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

from tests.test_dry_run import START, drift_of, git
from tests.test_github import read_calls
from tests.test_once import DASHED, OPENED, SESSION, STEP_PR, driver_copy, once
from tests.test_once_park_issues import build, dirty_tree, gh_calls

OTHER_SESSION = "11111111-1111-4111-8111-111111111111"
LOSE = {"reset", "stash", "clean", "restore", "checkout", "rebase", "push", "rm"}
LOSE |= {"-D", "-d", "--delete"}
PR_WRITES = {"create", "close", "merge", "edit", "review"}
PR7 = {"number": 7, "headRefName": "day-01/other", "url": "u", "author": "me"}
WITH_7 = drift_of(START, open_prs=(7,))
NEXT = "Day 02: read the spec against the code, then the spec-change PR"
PHASE_END = {
    **drift_of(NEXT),
    "order": [1, 2],
    "days": [{"day": d, "phase": d - 1, "status": "active"} for d in (1, 2)],
}
AT = "2026-11-07T00:00:00Z"
CLAUDE = "2.1.170 (Claude Code)"
RUN_START = {"event": "start", "at": AT, "step": START, "prefix": "day-01/spec", "claude": CLAUDE}
RUN_END = {"event": "end", "at": AT, "outcome": "success", "cost_usd": 0, "denials": 0}


def lose_work(node):
    if isinstance(node, ast.Constant) and node.value in LOSE:
        return f"{node.value!r} can lose work"
    return None


def pr_write(node):
    # A "pr" with a verb anywhere after it in the same list or tuple: gh pr create, close and so on.
    if isinstance(node, (ast.List, ast.Tuple)):
        values = [elt.value if isinstance(elt, ast.Constant) else None for elt in node.elts]
        for i, value in enumerate(values):
            if value == "pr" and any(later in PR_WRITES for later in values[i + 1 :]):
                return "a pull request is opened or closed"
    return None


def shell_true(node):
    if isinstance(node, ast.Call):
        for keyword in node.keywords:
            if keyword.arg == "shell" and getattr(keyword.value, "value", None) is True:
                return "shell=True"
    return None


def issue(number, title, labels=(), state="open"):
    return {"number": number, "title": title, "labels": [*labels], "state": state, "author": "me"}


def set_issues(folder, issues):
    # Rewrites the fake gh's issues, as bytes, as the fake writes them.
    path = folder / "gh" / "fake.json"
    spec = json.loads(path.read_bytes())
    spec["issues"] = issues
    path.write_bytes(json.dumps(spec).encode("utf-8"))


def write_log(state, records, tail=""):
    # One JSON line per record; tail is written as it is, so a torn line has no newline.
    state.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(record) + "\n" for record in records) + tail
    (state / "run.jsonl").write_bytes(body.encode("utf-8"))


def start_events(folder):
    # The start lines of the run log; none when the driver wrote no log.
    path = folder / "state" / "run.jsonl"
    if not path.exists():
        return []
    records = [json.loads(line) for line in path.read_bytes().decode("utf-8").splitlines()]
    return [record for record in records if record.get("event") == "start"]


def start_line(session=SESSION):
    return {**RUN_START, "session": session}


def pid_line(pid, session=SESSION):
    # The stamp is read after the process started, as once.run_session reads it after Popen.
    lock = importlib.import_module("driver.lock")
    stamp = lock.now().strftime(lock.STAMP)
    return {"event": "pid", "at": stamp, "session": session, "pid": pid, "started": stamp}


def end_line(session=SESSION):
    return {**RUN_END, "session": session}


def gone_pid():
    # A process that has exited: its pid is no driver's.
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    return child.pid


def crash_line(session):
    return f"park: the run log names session `{session}` for this step, with no end"


def run(copy, *args):
    done = subprocess.run(
        [sys.executable, str(copy / "run-steps.py"), *args],
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return done.returncode, done.stdout.decode("utf-8"), done.stderr.decode("utf-8")


def gh_of(flags):
    return flags[flags.index("--gh") + 1]


def gh_all(folder):
    # Every call the fake gh took, in order; none when it took none.
    if not (folder / "gh" / "calls.jsonl").exists():
        return []
    return read_calls(folder / "gh")


class RecoveryRulesTest(unittest.TestCase):
    def found(self, match):
        # Every node of the driver's files that match names, as file:line and what it is.
        hits = []
        for path in [ROOT / "run-steps.py", *sorted((ROOT / "driver").glob("*.py"))]:
            tree = ast.parse(path.read_bytes())
            for node in ast.walk(tree):
                what = match(node)
                if what:
                    hits.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno} {what}")
        return hits

    def test_no_command_that_can_lose_work(self):
        self.assertEqual(self.found(lose_work), [])

    def test_no_pull_request_opened_or_closed(self):
        self.assertEqual(self.found(pr_write), [])

    def test_no_shell(self):
        self.assertEqual(self.found(shell_true), [])


class RecoveryHoldTest(unittest.TestCase):
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

    def case(self, name, drift=None, **kwargs):
        # One folder per case: the project, the fake gh and claude, and the flags of the run.
        folder = self.folder_of(name)
        return folder, build(folder, drift=drift or drift_of(START), **kwargs)

    def live_pid(self):
        # A child that outlives the test: killed at cleanup, then waited for.
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        return child.pid

    def crashed(self, name, park):
        # A session whose process is gone and whose log has no end; park is the issues it left.
        folder, flags = self.case(name)
        write_log(folder / "state", [start_line(), pid_line(gone_pid())])
        set_issues(folder, park)
        return folder, flags

    def test_rows_three_to_eight(self):
        # Each pair is set together; the outcome is the higher row's alone.
        with self.subTest("row 3 over 4"):
            folder, flags = self.case("row-3-over-4", drift=WITH_7, prs=(PR7,))
            set_issues(folder, [issue(1, "park: needs a decision", ["parked"])])
            code, out, _ = once(self.copy, *flags)
            self.assertEqual((code, out.strip()), (0, "wait: parked #1"))

        with self.subTest("row 4 over 5"):
            folder, flags = self.case("row-4-over-5", drift=WITH_7, prs=(PR7,), setup=dirty_tree)
            code, out, _ = once(self.copy, *flags)
            self.assertEqual((code, out.strip()), (0, "wait: #7"))
            self.assertEqual(gh_calls(folder, ["issue", "create"]), [])

        with self.subTest("row 5 over 6"):
            folder, flags = self.case("row-5-over-6", setup=dirty_tree)
            git(folder / "project", "branch", "day-01/spec-x")
            code, out, _ = once(self.copy, *flags)
            line = "park: the project's tree is not clean (1 paths)"
            self.assertEqual((code, out.strip()), (1, line))

        with self.subTest("row 6 over 7"):
            folder, flags = self.case("row-6-over-7")
            project = folder / "project"
            git(project, "branch", "day-01/spec-x")
            git(project, "checkout", "-b", "other")
            code, out, _ = once(self.copy, *flags)
            self.assertEqual((code, out.strip()), (1, "park: the project is on other, not on main"))
            self.assertEqual(git(project, "branch", "--show-current").stdout.strip(), "other")

        with self.subTest("row 7 over 8"):
            folder, flags = self.case("row-7-over-8", drift=drift_of(DASHED), prs=(STEP_PR,))
            project = folder / "project"
            git(project, "checkout", "-b", "other")
            code, out, _ = once(self.copy, *flags)
            self.assertEqual(code, 0)
            self.assertIn(OPENED, out)
            self.assertEqual(git(project, "branch", "--show-current").stdout.strip(), "main")
            self.assertEqual(len(start_events(folder)), 1)

    def test_stop_beats_a_live_session(self):
        folder, flags = self.case("stop")
        write_log(folder / "state", [start_line(), pid_line(self.live_pid())])
        set_issues(folder, [issue(3, "STOP")])
        code, out, err = once(self.copy, *flags)
        line = "cannot start: halted: the STOP issue #3 is open; close it, then run-steps.py clear"
        self.assertEqual((code, out.strip(), err.strip()), (2, "", line))
        halt = (folder / "state" / "halt").read_bytes().decode("utf-8")
        self.assertIn("STOP issue #3", halt)
        self.assertEqual(len(start_events(folder)), 1)

    def test_torn_log_with_its_park_open_waits(self):
        folder, flags = self.case("torn")
        write_log(folder / "state", [start_line()], tail='{"event": "st')
        set_issues(folder, [issue(1, "park: the run log cannot be read at line 2", ["parked"])])
        code, out, _ = once(self.copy, *flags)
        self.assertEqual((code, out.strip()), (0, "wait: parked #1"))
        self.assertEqual(gh_calls(folder, ["issue", "comment"]), [])
        self.assertEqual(gh_calls(folder, ["issue", "create"]), [])

    def test_crash_with_a_branch_parks(self):
        park = [issue(1, crash_line(SESSION), ["parked"], "closed")]
        folder, flags = self.crashed("crash-branch", park)
        git(folder / "project", "branch", "day-01/spec-x")
        code, out, _ = once(self.copy, *flags)
        line = "park: a branch of this step exists: day-01/spec-x"
        self.assertEqual((code, out.strip()), (1, line))
        self.assertEqual(len(start_events(folder)), 1)

    def test_crash_park_open_waits(self):
        folder, flags = self.crashed("crash-open", [issue(1, crash_line(SESSION), ["parked"])])
        code, out, _ = once(self.copy, *flags)
        self.assertEqual((code, out.strip()), (0, "wait: parked #1"))
        self.assertEqual(len(start_events(folder)), 1)

    def test_other_session_does_not_answer(self):
        park = [issue(1, crash_line(OTHER_SESSION), ["parked"], "closed")]
        folder, flags = self.crashed("other-session", park)
        code, out, _ = once(self.copy, *flags)
        self.assertEqual((code, out.strip()), (1, crash_line(SESSION)))
        self.assertEqual(len(start_events(folder)), 1)

    def test_nothing_to_kill(self):
        # No lock, so halt kills nothing, whatever the log says about a session.
        cases = {
            "no log": None,
            "gone process": lambda: [start_line(), pid_line(gone_pid())],
            "live process, ended": lambda: [start_line(), pid_line(self.live_pid()), end_line()],
        }
        for name, lines in cases.items():
            with self.subTest(name):
                folder = self.folder_of(name.replace(" ", "-").replace(",", ""))
                if lines is not None:
                    write_log(folder / "state", lines())
                code, out, _ = run(self.copy, "halt", "--state", str(folder / "state"))
                self.assertEqual((code, out.strip()), (0, "halt: set; no driver is running"))
                self.assertTrue((folder / "state" / "halt").exists())

    def test_mine_waits(self):
        folder, flags = self.case("mine", drift=WITH_7, prs=(PR7,))
        code, out, _ = once(self.copy, *flags)
        self.assertEqual((code, out.strip()), (0, "wait: #7"))
        self.assertEqual(start_events(folder), [])
        self.assertFalse((folder / "state" / "run.jsonl").exists())

    def test_no_pr_read_with_none_open(self):
        folder, flags = self.case("no-pr", drift=drift_of(DASHED), prs=(), setup=dirty_tree)
        code, _, _ = once(self.copy, *flags)
        self.assertEqual(code, 1)
        calls = gh_all(folder)
        self.assertTrue(calls, "the fake gh took no call, so the check below proves nothing")
        pr_reads = [call for call in calls if call[:2] == ["pr", "list"] and "--state" in call]
        self.assertEqual(pr_reads, [])

    def test_unanswered_phase_end_parks(self):
        folder = self.folder_of("phase-end")
        flags = build(folder, drift=PHASE_END)
        args = ["--dry-run", "--project", str(folder / "project"), "--gh", gh_of(flags)]
        code, out, _ = run(self.copy, *args)
        self.assertEqual(
            (code, out.strip()), (1, "park: the end of Phase 0: Day 02 starts Phase 1")
        )

    def test_no_issue_read_elsewhere(self):
        folder = self.folder_of("dry-run")
        flags = build(folder, drift=drift_of(START))
        args = ["--dry-run", "--project", str(folder / "project"), "--gh", gh_of(flags)]
        code, out, _ = run(self.copy, *args)
        self.assertEqual(code, 0)
        self.assertTrue(out.strip().startswith("start: "))
        self.assertEqual([call for call in gh_all(folder) if call[:1] == ["issue"]], [])
