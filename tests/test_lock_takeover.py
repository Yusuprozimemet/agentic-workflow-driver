"""A stale lock, one whose process is gone, is taken over by one start of many: the others refuse
with a line that names the guard, the replace or the lock. clear removes a guard left behind, and
--once says which pid it took over from. A stale lock with no run log parks instead of going on, and
the next start, with that park closed, goes on through the table. The fixtures write bytes."""

import datetime
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from tests.test_dry_run import drift_of
from tests.test_github import read_calls
from tests.test_once import DASHED, driver_copy, once
from tests.test_once_park_issues import build, dirty_tree, parked_issues

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROBES = (["--version"], ["--help"])

# The eight starts: each waits for the go file, takes the lock, reports what it got in one whole
# file, and waits for the done file, so that every start holds what it got until all have reported.
CHILD = """
import json, os, sys, time
sys.path.insert(0, sys.argv[1])
from driver import lock
state, go_file, done_file, report_file = sys.argv[2:6]
while not os.path.exists(go_file):
    pass
result = lock.take(state)
temp = report_file + ".tmp"
with open(temp, "wb") as f:
    f.write(json.dumps(result).encode("utf-8"))
os.replace(temp, report_file)
while not os.path.exists(done_file):
    time.sleep(0.01)
"""


def stale_body():
    # The lock a driver left behind: its process has exited, and its stamp is a minute old.
    lock = importlib.import_module("driver.lock")
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=10)
    started = lock.now() - datetime.timedelta(seconds=60)
    body = json.dumps({"pid": child.pid, "started": started.strftime(lock.STAMP)})
    return child.pid, body.encode("utf-8")


def kill_alive(children):
    for child in children:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)


def stale_setup(body, log=False):
    # What build() runs: the stale lock; log adds a run log and a dirty tree, so the table parks.
    def setup(project, state):
        state.mkdir(parents=True, exist_ok=True)
        (state / "lock").write_bytes(body)
        if log:
            (state / "run.jsonl").write_bytes(b"")
            dirty_tree(project, state)

    return setup


class CopiedDriver(unittest.TestCase):
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


class LockTakeoverTest(CopiedDriver):
    def setUp(self):
        # Imported here, as in tests/test_lock.py, so each test fails alone where driver/ is missing.
        self.lock = importlib.import_module("driver.lock")
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)
        self.lock_file = os.path.join(self.state, "lock")

    def stale_lock(self):
        old, body = stale_body()
        Path(self.lock_file).write_bytes(body)
        return old, body

    def test_stale_lock_taken_over(self):
        old, _ = self.stale_lock()
        self.assertIsNone(self.lock.take(self.state))
        self.assertEqual(self.lock.read(self.state)[0], os.getpid())
        self.assertEqual(self.lock.took_over(self.state), old)
        self.assertFalse(os.path.exists(self.lock.guard(self.state)))
        # A start that finds no stale lock takes it with no took_over in it.
        fresh = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, fresh)
        self.assertIsNone(self.lock.take(fresh))
        self.assertIsNone(self.lock.took_over(fresh))
        self.assertNotIn("took_over", json.loads(Path(fresh, "lock").read_bytes()))

    def test_guard_refuses(self):
        _, body = self.stale_lock()
        guardpath = os.path.join(self.state, "lock.takeover")
        Path(guardpath).write_bytes(b"")
        line = self.lock.take(self.state)
        self.assertEqual(
            line,
            f"cannot start: {guardpath} exists: another start is taking the lock over; "
            "run-steps.py clear removes it",
        )
        self.assertEqual(Path(self.lock_file).read_bytes(), body)
        self.assertTrue(os.path.exists(guardpath))

    def test_read_again_finds_it_taken(self):
        _, body = self.stale_lock()
        stamp = self.lock.now().strftime(self.lock.STAMP)
        reads = [self.lock.read(self.state), (os.getpid(), stamp)]
        with mock.patch.object(self.lock, "read", side_effect=reads):
            line = self.lock.take(self.state)
        self.assertIn(f"already running (pid {os.getpid()}, since {stamp})", str(line))
        self.assertEqual(Path(self.lock_file).read_bytes(), body)
        self.assertFalse(os.path.exists(self.lock.guard(self.state)))

    def test_replace_refused_retries_then_refuses(self):
        _, body = self.stale_lock()
        with (
            mock.patch.object(self.lock.os, "replace", side_effect=PermissionError) as replace,
            mock.patch.object(self.lock.time, "sleep"),
        ):
            line = self.lock.take(self.state)
        self.assertEqual(
            line,
            f"cannot start: {self.lock.path(self.state)} cannot be replaced; "
            "run-steps.py clear removes it",
        )
        self.assertFalse(os.path.exists(self.lock.guard(self.state)))
        self.assertEqual(Path(self.lock_file).read_bytes(), body)
        self.assertEqual(replace.call_count, self.lock.REPLACE_TRIES)

    def test_eight_starts_one_winner(self):
        old, _ = self.stale_lock()
        files = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, files)
        go_file, done_file = (os.path.join(files, name) for name in ("go", "done"))
        reports = [os.path.join(files, f"report-{i}.json") for i in range(8)]
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        children = []
        self.addCleanup(kill_alive, children)
        for report in reports:
            args = [sys.executable, "-c", CHILD, str(ROOT), self.state, go_file, done_file, report]
            children.append(subprocess.Popen(args, env=env))
        Path(go_file).write_bytes(b"go")
        deadline = time.monotonic() + 60
        while not all(os.path.exists(report) for report in reports):
            self.assertLess(time.monotonic(), deadline, "a start never reported")
            time.sleep(0.01)
        results = [json.loads(Path(report).read_bytes()) for report in reports]
        Path(done_file).write_bytes(b"done")
        for child in children:
            self.assertEqual(child.wait(timeout=30), 0)
        winners = [i for i, result in enumerate(results) if result is None]
        self.assertEqual(len(winners), 1)
        losers = [str(result)[:13] for i, result in enumerate(results) if i != winners[0]]
        self.assertEqual(losers, ["cannot start:"] * 7)
        self.assertEqual(self.lock.read(self.state)[0], children[winners[0]].pid)
        self.assertEqual(self.lock.took_over(self.state), old)
        self.assertFalse(os.path.exists(self.lock.guard(self.state)))

    def test_clear_removes_guard(self):
        self.stale_lock()
        guardpath = self.lock.guard(self.state)
        Path(guardpath).write_bytes(b"")
        command = [sys.executable, str(ROOT / "run-steps.py"), "clear", "--state", self.state]
        done = subprocess.run(command, capture_output=True, check=False)
        self.assertEqual(done.returncode, 0)
        self.assertFalse(os.path.exists(self.lock_file))
        self.assertFalse(os.path.exists(guardpath))

    def test_once_prints_the_takeover(self):
        old, body = stale_body()
        flags = build(
            self.folder_of("takeover"), drift=drift_of(DASHED), setup=stale_setup(body, log=True)
        )
        code, out, _ = once(self.copy, *flags)
        self.assertEqual(code, 1)
        self.assertEqual(out.splitlines()[0], f"lock: taken over from pid {old}, which is gone")
        self.assertGreaterEqual(len(out.splitlines()), 2)


class LostLogTest(CopiedDriver):
    def test_stale_lock_and_no_log_parks(self):
        old, body = stale_body()
        folder = self.folder_of("no_log")
        code, out, _ = once(self.copy, *build(folder, setup=stale_setup(body)))
        takeover = f"lock: taken over from pid {old}, which is gone"
        park = f"park: the run log is missing, and a lock shows a driver ran (pid {old})"
        claude_args = [call["args"] for call in read_calls(folder / "claude")]
        self.assertEqual(
            (code, out.splitlines(), [a for a in claude_args if a not in PROBES]),
            (1, [takeover, park], []),
        )
        self.assertEqual(
            [(i["title"], i["state"]) for i in parked_issues(folder)], [(park, "open")]
        )

    def test_next_start_goes_on(self):
        _, body = stale_body()
        folder = self.folder_of("next_start")
        flags = build(folder, setup=stale_setup(body))
        once(self.copy, *flags)
        # The maintainer closes the park's issue; the fake gh keeps it, with its state changed.
        spec_file = folder / "gh" / "fake.json"
        spec = json.loads(spec_file.read_bytes())
        for issue in spec["issues"]:
            issue["state"] = "closed"
        spec_file.write_bytes(json.dumps(spec).encode("utf-8"))
        _, out, _ = once(self.copy, *flags)
        sessions = [c["args"] for c in read_calls(folder / "claude") if c["args"] not in PROBES]
        self.assertEqual(
            ("taken over" in out, "run log is missing" in out, len(sessions)), (False, False, 1)
        )

    def test_stale_lock_with_a_log_goes_on(self):
        old, body = stale_body()
        flags = build(
            self.folder_of("with_log"), drift=drift_of(DASHED), setup=stale_setup(body, log=True)
        )
        _, out, _ = once(self.copy, *flags)
        # The same dirty tree with no lock at all: the park line it gives is the line this run gives.
        plain = self.folder_of("plain")
        plain_flags = build(plain, drift=drift_of(DASHED), setup=dirty_tree)
        _, plain_out, _ = once(self.copy, *plain_flags)
        lines = out.splitlines()
        self.assertEqual(lines[0], f"lock: taken over from pid {old}, which is gone")
        self.assertEqual(lines[1], plain_out.splitlines()[0])
        self.assertNotIn("run log is missing", out)
