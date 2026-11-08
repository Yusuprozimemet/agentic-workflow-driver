"""`on` (run-steps.py on, driver/loop.py): --once's refusals with no lock left behind (C06.8), one lock
for the whole run, the night's count of steps and off between steps (C06.9), and the ends a park or a
pull request found open at a start gives. Each case is a copy of the driver with the fake claude of
tests/test_once.py and the fake gh of tests/test_github.py, as tests/test_once_run.py runs them."""

import contextlib
import importlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import drift_of, make_project
from tests.test_github import JOB, fake_gh, read_bodies, read_calls
from tests.test_merge_wait import run as run_answer
from tests.test_merge_wait import view
from tests.test_once import (
    DASHED,
    STEP_PR,
    claude_program,
    driver_copy,
    fake_claude,
    halt_line,
    without_session_id,
)
from tests.test_preflight import HELP

# The checks answers, as tests/test_wait.py gives them; a red check's log is LOGS.
GREEN = {"code": 0, "out": [{"name": "tests", "bucket": "pass", "link": JOB}]}
RED = {"code": 0, "out": [{"name": "tests", "bucket": "fail", "link": JOB}]}
LOGS = [{"code": 0, "out": "one\nboom\n"}]
# The next step after the merge: the same track, so the step's pull request is still the one found.
SECOND = "Day 01 Track A: C01.4"
# The drift is read from drift.json beside the case's folder, so a test can change it between sessions.
DRIFT_FILE_SCRIPT = """import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--out")
parser.add_argument("--cache")
args = parser.parse_args()
Path(args.out).write_bytes((Path(__file__).resolve().parents[2] / "drift.json").read_bytes())
"""


# Shared with tests/test_live_check.py; not a TestCase, so that importing it collects no tests.
class OnCase:
    @classmethod
    def setUpClass(cls):
        # Imported here, as in test_once: where driver/ is missing, each test fails alone.
        cls.lock = importlib.import_module("driver.lock")
        cls.root = tempfile.mkdtemp()
        cls.copy = driver_copy(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def build(
        self,
        name,
        drift=None,
        steps=2,
        checks=(GREEN,),
        views=None,
        run_steps=None,
        do="",
        help=None,
        drop=(),
        script=None,
    ):
        # One case's scratch folder: a project, a fake claude and a fake gh, and the config as bytes.
        folder = Path(self.root) / name
        folder.mkdir()
        project = make_project(folder, drift or drift_of(DASHED), script)
        (folder / "claude").mkdir()
        (folder / "gh").mkdir()
        claude = fake_claude(folder / "claude", help=help or HELP, do=do)
        gh = fake_gh(
            folder / "gh",
            runs=[{"status": "completed", "conclusion": "success"}],
            prs=[STEP_PR],
            checks=list(checks),
            views=list(views or [view("MERGED")]),
            logs=LOGS,
            run_steps=run_steps,
        )
        config = {
            "project": str(project),
            "human_only": [],
            "budget_usd": 5,
            "steps_per_night": steps,
        }
        path = folder / "driver.json"
        path.write_bytes(
            json.dumps({k: v for k, v in config.items() if k not in drop}).encode("utf-8")
        )
        self.folder = folder
        self.state = folder / "state"
        # The version the fake claude prints is recorded as live-checked, so `on` goes on.
        self.state.mkdir()
        (self.state / "live-checked.txt").write_bytes(b"2.1.170 (Claude Code)\n")
        flags = ["--config", str(path), "--state", str(self.state), "--claude", claude, "--gh", gh]
        self.flags = [*flags, "--poll", "0.01", "--wait-minutes", "0.5"]

    def on(self, *extra):
        # The command line as the maintainer types it, in a process of its own; returns (code, out, err).
        done = subprocess.run(
            [sys.executable, str(self.copy / "run-steps.py"), "on", *self.flags, *extra],
            capture_output=True,
            check=False,
            timeout=120,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        return done.returncode, done.stdout.decode("utf-8"), done.stderr.decode("utf-8")

    def sessions(self):
        # The session calls, not the --version and --help probes, which carry no session.
        if not (self.folder / "claude" / "calls.jsonl").exists():
            return []
        calls = read_calls(self.folder / "claude")
        return [call for call in calls if call["args"] not in (["--version"], ["--help"])]

    def gh_of(self, *prefix):
        # The recorded gh calls that begin with prefix; each call is its argument list.
        if not (self.folder / "gh" / "calls.jsonl").exists():
            return []
        calls = read_calls(self.folder / "gh")
        return [call for call in calls if call[: len(prefix)] == list(prefix)]

    def comments(self):
        # The bodies of the fake gh's `issue comment` calls, in the order they were made.
        bodies = read_bodies(self.folder / "gh")
        return [record["body"] for record in bodies if record["args"][:2] == ["issue", "comment"]]


class OnTest(OnCase, unittest.TestCase):
    def test_refusals(self):
        # Each refusal is one line on stderr with exit 2, starts no session, and leaves no lock.
        for name, kwargs in (
            ("halted", {}),
            ("no_session_id", {"help": without_session_id()}),
            ("no_budget", {"drop": ("budget_usd",)}),
        ):
            with self.subTest(case=name):
                self.build(name, **kwargs)
                if name == "halted":
                    (self.state / "halt").write_bytes(b"halted")
                claude = claude_program(self.folder / "claude")
                want = {
                    "halted": halt_line(self.state),
                    "no_session_id": f"cannot run a session: {claude} --help lists no --session-id",
                    "no_budget": f"cannot start: {self.folder / 'driver.json'} has no budget_usd",
                }[name]
                code, out, err = self.on()
                lock_left = os.path.exists(self.lock.path(str(self.state)))
                self.assertEqual(
                    (code, out, err.splitlines(), self.sessions(), lock_left),
                    (2, "", [want], [], False),
                )

    def test_one_lock_for_the_run(self):
        # In-process, so that the lock's calls can be counted: one take and one release for two steps.
        self.build("one_lock")
        spec = importlib.util.spec_from_file_location("run_steps", self.copy / "run-steps.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        take = mock.patch.object(self.lock, "take", wraps=self.lock.take)
        release = mock.patch.object(self.lock, "release", wraps=self.lock.release)
        # os.setpgid is POSIX's; the run calls it so that halt kills the session with it.
        with (
            take as taken,
            release as released,
            mock.patch("os.setpgid", create=True),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            code = module.main(["on", *self.flags])
        self.assertEqual(
            (
                code,
                taken.call_count,
                released.call_count,
                [call["lock"] for call in self.sessions()],
                os.path.exists(self.lock.path(str(self.state))),
            ),
            (0, 1, 1, [True, True], False),
        )

    def test_steps_per_night(self):
        # C06.9: the first step's red check is fixed by a resume, which is no step. The run's issue is
        # opened for the first step and commented on for the second; the night's count closes it.
        self.build("nightly", checks=[RED, GREEN, GREEN])
        code, out, _ = self.on()
        issues = json.loads((self.folder / "gh" / "fake.json").read_bytes())["issues"]
        creates = self.gh_of("issue", "create")
        closes = self.gh_of("issue", "close")
        comments = self.comments()
        sessions = self.sessions()
        night = "on: 2 steps, the night's count"
        self.assertEqual(
            (
                code,
                out.splitlines()[-1],
                sum("--session-id" in call["args"] for call in sessions),
                sum("--resume" in call["args"] for call in sessions),
                len(creates),
                [call[2] for call in closes],
                [issue["number"] for issue in issues],
                "step: " in comments[0],
                comments[-1],
                os.path.exists(self.state / "run.json"),
            ),
            (0, night, 2, 1, 1, ["1"], [1], True, night, False),
        )

    def test_off_between_steps(self):
        # The run's issue (#1) is closed by the evidence read after the first merge: nothing new starts.
        self.build("off", run_steps=[{**run_answer("completed", "success"), "closes": [1]}])
        code, out, _ = self.on()
        self.assertEqual(
            (
                code,
                out.splitlines()[-1],
                len(self.sessions()),
                len(self.gh_of("issue", "create")),
                self.gh_of("pr", "close"),
                self.gh_of("issue", "close"),
            ),
            (0, "off: the run's issue #1 is closed; nothing new starts", 1, 1, [], []),
        )

    def test_park_ends_the_run(self):
        # A pull request closed without a merge parks: its issue is opened, and the run's issue is
        # closed with the park's line and the park's number.
        self.build("park", views=[view("CLOSED")])
        code, out, _ = self.on()
        creates = self.gh_of("issue", "create")
        self.assertEqual(
            (
                code,
                out.splitlines()[-1],
                len(self.sessions()),
                len(creates),
                creates[1][creates[1].index("--label") + 1],
                self.comments()[-1].splitlines(),
            ),
            (
                1,
                "park: #5 was closed without a merge",
                1,
                2,
                "parked",
                ["park: #5 was closed without a merge", "parked: #2"],
            ),
        )

    def test_found_pr_waited(self):
        # A pull request open at the start is waited on, with no session of the run's own; the run's
        # issue is closed after it merges, and off ends the run.
        self.build(
            "found",
            drift=drift_of(DASHED, open_prs=(5,)),
            run_steps=[{**run_answer("completed", "success"), "closes": [1]}],
        )
        code, out, _ = self.on()
        lines = out.splitlines()
        self.assertEqual(
            (
                code,
                "wait: #5" in lines,
                lines[-1],
                self.sessions(),
                [call[2] for call in self.gh_of("pr", "view")],
            ),
            (0, True, "off: the run's issue #1 is closed; nothing new starts", [], ["5"]),
        )

    def test_merge_waits_on_the_fixed_pr(self):
        # The red check resumes the session, which opens its fix as #13: the merge is waited on as #13.
        do = (
            'if "--resume" in args:\n'
            '    gh_file = folder.parent / "gh" / "fake.json"\n'
            "    gh_spec = json.loads(gh_file.read_bytes())\n"
            '    gh_spec["prs"] = [{**pr, "number": 13} for pr in gh_spec["prs"]]\n'
            '    gh_file.write_bytes(json.dumps(gh_spec).encode("utf-8"))\n'
        )
        self.build("fixed", steps=1, checks=[RED, GREEN], do=do)
        code, out, _ = self.on()
        self.assertEqual(
            (code, [call[2] for call in self.gh_of("pr", "view")], out.splitlines()[-1]),
            (0, ["13"], "on: 1 steps, the night's count"),
        )

    def test_on_refuses_a_dry_run(self):
        self.build("dry")
        code, out, err = self.on("--dry-run")
        self.assertEqual(
            (code, out, err.splitlines(), self.sessions()),
            (2, "", ["run-steps.py: on goes alone"], []),
        )

    def test_next_step_read_after_merge(self):
        # The first session stands in for the merge moving main: the drift says a new next step from
        # then on. The second session must be told that step, not the first again.
        do = (
            f"text = {json.dumps(drift_of(SECOND))!r}\n"
            '(folder.parent / "drift.json").write_bytes(text.encode("utf-8"))\n'
        )
        self.build("reread", script=DRIFT_FILE_SCRIPT, do=do)
        (self.folder / "drift.json").write_bytes(json.dumps(drift_of(DASHED)).encode("utf-8"))
        code, _, _ = self.on()
        prompts = [bytes.fromhex(call["stdin"]).decode("utf-8") for call in self.sessions()]
        self.assertEqual(
            (code, [prompt.splitlines()[0] for prompt in prompts]),
            (0, [f"Next step: {DASHED}", f"Next step: {SECOND}"]),
        )
