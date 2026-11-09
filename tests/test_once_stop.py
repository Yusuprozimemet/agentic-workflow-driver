"""--once's phone STOP (C05.11): with --poll, --once reads the project's issues every poll seconds while a
session runs, and an open STOP issue stops the session: the halt file is written, the stop and the
report are printed, the run's issue is closed with the report, and the session's tree is killed. A
failed read is skipped. Each case is a copy of the driver with the fake claude of tests/test_once.py
and the fake gh of tests/test_github.py. No report here names a pid or a path (D03.17)."""

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

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import drift_of
from tests.test_halt import stop
from tests.test_once import DASHED, OPENED, driver_copy, halt_line, once
from tests.test_once_halt import SESSION, close_pipes, kill_left_over, session_calls
from tests.test_once_park_issues import build, gh_calls
from tests.test_once_run import comments

STOPPED = "halt: the STOP issue #9 is open; the session is stopped"
STOP_ISSUE = {"number": 9, "title": "STOP", "labels": [], "state": "open", "author": "me"}
# Run by the fake claude inside a session: the fake gh's issue reads fail for 2 s, then work again.
POLL_FAILS = """import time
gh_file = folder.parent / "gh" / "fake.json"
gh_spec = json.loads(gh_file.read_bytes())
gh_spec["issue_code"] = 1
gh_file.write_bytes(json.dumps(gh_spec).encode("utf-8"))
time.sleep(2)
gh_spec["issue_code"] = 0
gh_file.write_bytes(json.dumps(gh_spec).encode("utf-8"))
time.sleep(1)
"""


def read_spec(folder):
    return json.loads((folder / "gh" / "fake.json").read_bytes())


def write_spec(folder, spec):
    # Written as bytes: on Windows, text mode would add a carriage return to each line.
    (folder / "gh" / "fake.json").write_bytes(json.dumps(spec).encode("utf-8"))


def run_issue(folder):
    # The run's issue, opened by the driver before the session starts; the fake holds it by its title.
    issues = read_spec(folder)["issues"]
    return next(issue["number"] for issue in issues if issue["title"].startswith("Driver run"))


class OnceStopTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone.
        importlib.import_module("driver.once")
        self.lock = importlib.import_module("driver.lock")
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def start(self, do=SESSION):
        folder = Path(tempfile.mkdtemp(dir=self.root))
        flags = build(folder, drift=drift_of(DASHED), do=do) + ["--poll", "0.5"]
        copy = driver_copy(tempfile.mkdtemp(dir=self.root))
        driver = subprocess.Popen(
            [sys.executable, str(copy / "run-steps.py"), "--once", *flags],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        # Registered first, so the pipes close after the driver is stopped.
        self.addCleanup(close_pipes, driver)
        self.addCleanup(stop, driver)
        self.addCleanup(kill_left_over, folder / "claude")
        return {
            "driver": driver,
            "folder": folder,
            "state": folder / "state",
            "claude": folder / "claude",
            "copy": copy,
            "flags": flags,
        }

    def wait_pids(self, claude_dir):
        pids = []
        deadline = time.monotonic() + 30
        while len(pids) < 2 and time.monotonic() < deadline:
            time.sleep(0.1)
            if Path(claude_dir, "pids").exists():
                pids = Path(claude_dir, "pids").read_text(encoding="utf-8").split()
        self.assertEqual(len(pids), 2, "the session did not start its child")
        return (int(text) for text in pids)

    def alive(self, pid, deadline):
        while self.lock.process(pid)[0] and time.monotonic() < deadline:
            time.sleep(0.05)
        return self.lock.process(pid)[0]

    def stopped(self, remove_run=False):
        # A session that the phone's STOP stops: the STOP issue is added once the pids are written, and
        # with remove_run the run's issue goes in the same write, so that its report fails.
        run = self.start()
        run["fake"], run["child"] = self.wait_pids(run["claude"])
        run["number"] = run_issue(run["folder"])
        spec = read_spec(run["folder"])
        if remove_run:
            spec["issues"] = [issue for issue in spec["issues"] if issue["number"] != run["number"]]
        spec["issues"].append(STOP_ISSUE)
        write_spec(run["folder"], spec)
        try:
            out, _ = run["driver"].communicate(timeout=10)
        except subprocess.TimeoutExpired:
            self.fail("the driver did not end within 10 s")
        run["lines"] = out.decode("utf-8").splitlines()
        return run

    def test_stop_during_session(self):
        run = self.stopped()
        halt = Path(run["state"], "halt").read_bytes().decode("utf-8")
        self.assertIn("STOP issue #9", halt)
        deadline = time.monotonic() + 10
        self.assertFalse(self.alive(run["fake"], deadline), "the fake still runs")
        self.assertFalse(self.alive(run["child"], deadline), "the fake's child still runs")
        self.assertEqual(run["lines"][:2], [STOPPED, f"halt: reported on #{run['number']}"])
        issue = next(i for i in read_spec(run["folder"])["issues"] if i["number"] == run["number"])
        self.assertEqual(issue["state"], "closed")
        report = comments(run["folder"])[-1]
        self.assertIn("halted at ", report)
        self.assertIn("step: ", report)
        records = Path(run["state"], "run.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(line)["event"] for line in records], ["start", "pid"])
        self.assertEqual(run["driver"].returncode, 1 if os.name == "nt" else -9)

    def test_refuses_after_stop(self):
        run = self.stopped()
        calls_before = session_calls(run["claude"])
        code, out, err = once(run["copy"], *run["flags"])
        self.assertEqual(code, 2)
        self.assertFalse(out.strip(), "--once printed on stdout")
        self.assertEqual(err.strip(), halt_line(run["state"]))
        self.assertEqual(session_calls(run["claude"]), calls_before)

    def test_stop_when_report_fails(self):
        run = self.stopped(remove_run=True)
        deadline = time.monotonic() + 10
        self.assertFalse(self.alive(run["fake"], deadline), "the fake still runs")
        self.assertFalse(self.alive(run["child"], deadline), "the fake's child still runs")
        self.assertEqual(
            run["lines"][:2],
            [STOPPED, f"halt: no report on #{run['number']}: gh issue comment exited 1"],
        )

    def test_failed_poll_skipped(self):
        folder = Path(tempfile.mkdtemp(dir=self.root))
        flags = build(folder, drift=drift_of(DASHED), do=POLL_FAILS)
        copy = driver_copy(tempfile.mkdtemp(dir=self.root))
        code, out, _ = once(copy, *flags, "--poll", "0.5")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), OPENED)
        self.assertFalse(Path(folder, "state", "halt").exists(), "a failed poll halted the driver")
        self.assertGreaterEqual(len(gh_calls(folder, ["issue", "list"])), 3)
