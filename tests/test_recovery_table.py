"""Day 07's table of "Recovery" with a live session, a torn log or a crashed one, and halt on them
(C07.8 to C07.13). Each case is a copy of the driver with the fake claude and gh of test_once.py."""

import contextlib
import importlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tests.test_halt as halt_tests
import tests.test_recovery_holds as holds
from tests.test_dry_run import START, clone, commit_file, drift_of, git, make_project
from tests.test_github import fake_gh
from tests.test_halt import STAND_IN, new_group, stop
from tests.test_on import OnCase
from tests.test_once import DASHED, OPENED, SESSION, STEP_PR, driver_copy, halt_line, once
from tests.test_once_park_issues import build, dirty_tree, gh_calls
from tests.test_recovery_holds import crash_line, issue, pid_line, set_issues, start_line, write_log

# The live child runs until the test creates its gate, then exits: it is the session `on` waits on.
WAIT_FOR_GATE = "import os,sys,time\nwhile not os.path.exists(sys.argv[1]): time.sleep(0.02)"
TORN = "halt: the run log cannot be read at line 2; no session was looked for"
STOP_LINE = "cannot start: halted: the STOP issue #3 is open; close it, then run-steps.py clear"
KILLED = "halt: set; killed session `{}` (pid {}) and the processes it started"
WAITING_ON_7 = drift_of("Waiting on #7 Day 01 Track A: x", open_prs=(7,))


def waiting(pid):
    return f"wait: session `{SESSION}` is still running (pid {pid})"


def write_fake(folder, spec):
    # Replaced whole, so that a gh call reading the spec sees the old one or the new one.
    path, temp = folder / "gh" / "fake.json", folder / "gh" / "fake.tmp"
    temp.write_bytes(json.dumps(spec).encode("utf-8"))
    for _ in range(100):
        with contextlib.suppress(PermissionError):  # Windows, while a gh call has the file open
            return os.replace(temp, path)
        time.sleep(0.02)
    os.replace(temp, path)


class CaseMixin:
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp()
        cls.copy = driver_copy(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def case(self, name, drift=None, **kwargs):
        folder = Path(self.root) / name
        folder.mkdir()
        return folder, build(folder, drift=drift or drift_of(START), **kwargs)

    def live_pid(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        return child.pid


class TableTest(CaseMixin, unittest.TestCase):
    def assertWaits(self, folder, flags):
        # The log names a live child: --once waits on it, and does nothing else.
        pid = self.live_pid()
        write_log(folder / "state", [start_line(), pid_line(pid)])
        code, out, _ = once(self.copy, *flags)
        self.assertEqual((code, out.splitlines()), (0, [waiting(pid)]))
        self.assertEqual(gh_calls(folder, ["issue", "create"]), [])
        self.assertEqual(len(holds.start_events(folder)), 1)
        branch = git(folder / "project", "branch", "--show-current").stdout.strip()
        self.assertEqual(branch, "main")

    def assertParksTorn(self, folder, flags):
        write_log(folder / "state", [start_line()], tail='{"event": "st')
        code, out, _ = once(self.copy, *flags)
        self.assertEqual((code, out.strip()), (1, "park: the run log cannot be read at line 2"))
        self.assertEqual(len(gh_calls(folder, ["issue", "create"])), 1)

    def test_live_session_waits(self):
        self.assertWaits(*self.case("live"))

    def test_live_session_beats_the_rows_below(self):
        with self.subTest("open parked issue"):
            folder, flags = self.case("parked")
            set_issues(folder, [issue(1, "park: x", ["parked"])])
            self.assertWaits(folder, flags)
        with self.subTest("open pull request"):
            self.assertWaits(*self.case("pr", drift=holds.WITH_7, prs=(holds.PR7,)))
        with self.subTest("dirty tree"):
            self.assertWaits(*self.case("dirty", setup=dirty_tree))
        with self.subTest("branch of the step"):
            folder, flags = self.case("branch")
            git(folder / "project", "branch", "day-01/spec-x")
            self.assertWaits(folder, flags)

    def test_torn_log_parks_first(self):
        with self.subTest("open pull request"):
            self.assertParksTorn(*self.case("torn-pr", drift=holds.WITH_7, prs=(holds.PR7,)))
        with self.subTest("open parked issue of another title"):
            folder, flags = self.case("torn-park")
            set_issues(folder, [issue(1, "park: x", ["parked"])])
            self.assertParksTorn(folder, flags)

    def test_open_pr_leaves_the_tree(self):
        folder, flags = self.case("leaves", drift=holds.WITH_7, prs=(holds.PR7,))
        project = folder / "project"
        git(project, "checkout", "-b", "day-07/other")
        other = clone(project, "other")
        commit_file(other, "next.txt")
        git(other, "push", "origin", "main")
        git(project, "fetch", "origin")
        before = git(project, "rev-parse", "main").stdout.strip()
        self.assertNotEqual(before, git(project, "rev-parse", "origin/main").stdout.strip())
        code, out, _ = once(self.copy, *flags)
        self.assertEqual((code, out.strip()), (0, "wait: #7"))
        self.assertEqual(git(project, "branch", "--show-current").stdout.strip(), "day-07/other")
        self.assertEqual(git(project, "rev-parse", "main").stdout.strip(), before)


class AuthorTest(CaseMixin, unittest.TestCase):
    def test_someone_elses_on_a_waiting_sentence_parks(self):
        prs = ({**holds.PR7, "author": "someone"},)
        folder, flags = self.case("someone", drift=WAITING_ON_7, prs=prs)
        code, out, _ = once(self.copy, *flags)
        self.assertEqual(
            (code, out.strip()), (1, "park: the next step waits on no open pull request")
        )
        self.assertEqual(holds.start_events(folder), [])
        listed = ["pr", "list", "--state", "open", "--author", "@me", "--limit", "100"]
        self.assertEqual(gh_calls(folder, ["pr", "list"]), [[*listed, "--json", "number"]])

    def test_gh_fails(self):
        folder, flags = self.case("gh-fails", drift=WAITING_ON_7, prs=(holds.PR7,))
        spec = json.loads((folder / "gh" / "fake.json").read_bytes())
        spec["pr_code"] = 1
        write_fake(folder, spec)
        code, _, err = once(self.copy, *flags)
        self.assertEqual((code, err.strip()), (2, "cannot read the project: gh pr list exited 1"))
        self.assertEqual(holds.start_events(folder), [])


class OnWaitsTest(OnCase, unittest.TestCase):
    def start(self, name):
        # `on` on a log naming a live child: returns the run, the child and its gate.
        self.build(name, drift=drift_of(START))
        gate = self.folder / "gate"
        child = subprocess.Popen([sys.executable, "-c", WAIT_FOR_GATE, str(gate)])
        self.addCleanup(child.wait)
        self.addCleanup(child.kill)
        write_log(self.state, [start_line(), pid_line(child.pid)])
        proc = subprocess.Popen(
            [sys.executable, str(self.copy / "run-steps.py"), "on", *self.flags, "--poll", "0.2"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.addCleanup(stop, proc)
        guard = threading.Timer(60, proc.kill)
        guard.start()
        self.addCleanup(guard.cancel)
        first = proc.stdout.readline().decode("utf-8").strip()
        self.assertEqual(first, waiting(child.pid))
        return proc, child, gate

    def test_waits_then_reads_the_table_again(self):
        proc, child, gate = self.start("waits")
        time.sleep(0.6)  # several polls, each reading the table again
        gate.write_bytes(b"")
        child.wait(timeout=10)  # reaped, or on would still see a live child
        out, _ = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(out.decode("utf-8").splitlines(), [crash_line(SESSION)])  # no second wait
        self.assertEqual(self.sessions(), [])

    def test_halt_file_ends_the_wait(self):
        proc, _, _ = self.start("halt-file")
        (self.state / "halt").write_bytes(b"halted")
        _, err = proc.communicate(timeout=60)
        self.assertEqual((proc.returncode, err.decode("utf-8").strip()), (2, halt_line(self.state)))
        self.assertEqual(self.sessions(), [])

    def test_stop_ends_the_wait(self):
        proc, _, _ = self.start("stop")
        spec = json.loads((self.folder / "gh" / "fake.json").read_bytes())
        write_fake(self.folder, {**spec, "issues": [*spec["issues"], issue(3, "STOP")]})
        _, err = proc.communicate(timeout=60)
        self.assertEqual((proc.returncode, err.decode("utf-8").strip()), (2, STOP_LINE))
        self.assertIn("STOP issue #3", (self.state / "halt").read_bytes().decode("utf-8"))
        self.assertEqual(self.sessions(), [])


class CrashAnsweredTest(CaseMixin, unittest.TestCase):
    def test_closed_park_starts_a_new_session(self):
        prefix = importlib.import_module("driver.steps").classify(DASHED).prefix
        folder, flags = self.case("answered", drift=drift_of(DASHED), prs=(STEP_PR,))
        crashed = {**start_line(), "step": DASHED, "prefix": prefix}
        write_log(folder / "state", [crashed, pid_line(holds.gone_pid())])
        set_issues(folder, [issue(1, crash_line(SESSION), ["parked"], "closed")])
        code, out, _ = once(self.copy, *flags)
        self.assertEqual((code, OPENED in out), (0, True))
        starts = holds.start_events(folder)
        self.assertEqual((len(starts), starts[1]["session"] != SESSION), (2, True))


class HaltSessionTest(halt_tests.SwitchTest):
    def stand_in(self, name):
        pidfile = os.path.join(self.root, name)
        standin = subprocess.Popen([sys.executable, "-c", STAND_IN, pidfile], **new_group())
        self.addCleanup(stop, standin)
        pids = []
        deadline = time.monotonic() + 10
        while len(pids) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)
            if os.path.exists(pidfile):
                pids = Path(pidfile).read_text().split()
        self.assertEqual(len(pids), 2)
        return standin, int(pids[1])

    def assertGone(self, standin, child):
        standin.wait(timeout=10)
        deadline = time.monotonic() + 10
        while self.lock.process(child)[0] and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(self.lock.process(child)[0])

    def write_run(self):
        project, gh = make_project(Path(self.root)), Path(self.root, "gh")
        gh.mkdir()
        run_issue = issue(4, "Driver run 2026-11-07T09:00:00Z")
        record = {"project": str(project), "gh": fake_gh(gh, issues=[run_issue])}
        record.update({"issue": 4, "step": START, "session": SESSION})
        Path(self.state, "run.json").write_bytes(json.dumps(record).encode("utf-8"))

    def test_kills_a_session_with_no_driver(self):
        standin, child = self.stand_in("pids")
        write_log(Path(self.state), [start_line(), pid_line(standin.pid)])
        self.write_run()
        done = self.cli("halt")
        killed = KILLED.format(SESSION, standin.pid)
        self.assertEqual(done.stdout.splitlines(), [killed, "halt: reported on #4"])
        self.assertEqual(done.returncode, 0)
        self.assertTrue(os.path.exists(self.halt_file))
        self.assertGone(standin, child)

    def test_lock_and_session(self):
        driver, driver_child = self.stand_in("driver")
        session, session_child = self.stand_in("session")
        self.write_lock(driver.pid)
        write_log(Path(self.state), [start_line(), pid_line(session.pid)])
        self.write_run()
        done = self.cli("halt")
        lines = done.stdout.splitlines()
        self.assertEqual((done.returncode, lines.count("halt: reported on #4")), (0, 1))
        self.assertIn(f"halt: set; killed pid {driver.pid} and the processes it started", lines)
        self.assertIn(KILLED.format(SESSION, session.pid), lines)
        self.assertGone(driver, driver_child)
        self.assertGone(session, session_child)

    def test_torn_log(self):
        with self.subTest("no lock"):
            write_log(Path(self.state), [start_line()], tail='{"event": "st')
            done = self.cli("halt")
            self.assertEqual(done.stdout.splitlines(), [TORN, halt_tests.NO_DRIVER])
            self.assertEqual(done.returncode, 0)
            self.assertTrue(os.path.exists(self.halt_file))
        with self.subTest("unreadable lock"):
            state = os.path.join(self.root, "unreadable")
            write_log(Path(state), [start_line()], tail='{"event": "st')
            Path(self.lock.path(state)).write_bytes(b"x")
            done = self.cli("halt", state)
            self.assertIn(TORN, done.stdout.splitlines())
            self.assertEqual(done.returncode, 1)
            self.assertTrue(os.path.exists(os.path.join(state, "halt")))

    def test_failed_kill_keeps_the_exit_code(self):
        switches = importlib.import_module("driver.switches")
        denied = mock.patch("driver.switches._kill_tree", return_value="denied")
        logged = mock.patch("driver.runlog.live_session", return_value=(SESSION, 42, None))
        with denied, logged, contextlib.redirect_stdout(io.StringIO()) as out:
            code = switches.halt(self.state)
        self.assertEqual(code, 0)
        line = f"halt: set; could not kill session `{SESSION}` (pid 42): denied"
        self.assertEqual(out.getvalue().splitlines(), [line])
        self.assertTrue(os.path.exists(self.halt_file))
