"""The phone's heartbeat comment (Day 11, Track E1): a --once run that is in a session at a poll edits one
comment on the run's issue in place, and a comment that fails is tried again at the next poll. Each case runs
a fake claude that prints its init line and sleeps for four seconds, with the driver's --poll at 0.3 seconds
or at 30, and reads the bodies the fake gh recorded. No report here names a pid, uuid or path."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import test_once_outcome as outcome
from tests.test_dry_run import drift_of
from tests.test_github import read_bodies
from tests.test_once import DASHED, driver_copy
from tests.test_once_halt import kill_left_over
from tests.test_once_park_issues import build, gh_issues

SYSTEM = {"type": "system", "subtype": "init"}
PREFIXES = ("running: ", "last event: ", "tokens so far:")
PATCH = ["api", "--method", "PATCH", "repos/{owner}/{repo}/issues/comments/99", "--input", "-"]


def parsed(text):
    # A patch's body as an object, or None when it is not JSON.
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def line_at(lines, prefix):
    # The index of the first line that starts with the prefix, or -1.
    return next((i for i, line in enumerate(lines) if line.startswith(prefix)), -1)


class PhoneTest(unittest.TestCase):
    setUp = outcome.OutcomeTest.setUp

    def live_run(self, poll, comment_id=None, comment_code=None):
        # One --once run whose session prints its init line and sleeps for four seconds: it ends before a
        # poll of 30 seconds, and is in progress at each poll of 0.3 seconds. The fake gh's comment id and
        # its comment failure code are set in its fake.json, as build leaves them.
        do = f"print({json.dumps(SYSTEM)!r}, flush=True)\nimport time; time.sleep(4)\n"
        folder = Path(tempfile.mkdtemp(dir=self.root))
        flags = build(folder, drift=drift_of(DASHED), do=do)
        gh_file = folder / "gh" / "fake.json"
        spec = json.loads(gh_file.read_bytes())
        if comment_id is not None:
            spec["comment_id"] = comment_id
        if comment_code is not None:
            spec["comment_code"] = comment_code
        gh_file.write_bytes(json.dumps(spec).encode("utf-8"))
        copy = driver_copy(tempfile.mkdtemp(dir=self.root))
        self.addCleanup(kill_left_over, folder / "claude")
        try:
            completed = subprocess.run(
                [sys.executable, str(copy / "run-steps.py"), "--once", *flags]
                + ["--poll", str(poll), "--session-minutes", "1"],
                capture_output=True,
                check=False,
                timeout=120,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        except subprocess.TimeoutExpired:
            self.fail("the driver did not end")
        runs = []
        if (folder / "state" / "run.jsonl").exists():
            text = (folder / "state" / "run.jsonl").read_bytes().decode("utf-8")
            runs = [json.loads(line) for line in text.splitlines() if line.strip()]
        starts = [record for record in runs if record.get("event") == "start"]
        start = starts[0] if starts else {}
        numbers = [
            issue["number"]
            for issue in gh_issues(folder)
            if issue["title"].startswith("Driver run")
        ]
        number = numbers[0] if numbers else None
        bodies = read_bodies(folder / "gh") if (folder / "gh" / "bodies.jsonl").exists() else []
        return folder, completed, start, number, bodies

    def test_heartbeat_comment_edited_in_place(self):
        # C11.16: the first beat posts a comment, the later beats edit it through the API, and the run's
        # closing comment comes last. The run that polls at 30 seconds has no heartbeat, so it is the
        # reference for the return code and the output.
        _, first, start, number, bodies = self.live_run(0.3, comment_id=99)
        _, second, _, _, _ = self.live_run(30)
        comments = [
            record
            for record in bodies
            if record["args"] == ["issue", "comment", str(number), "--body-file", "-"]
        ]
        beats = comments[:-1]
        patches = [record for record in bodies if record["args"] == PATCH]
        lines = beats[0]["body"].split("\n") if beats else []
        patch_objects = [parsed(record["body"]) for record in patches]
        last = patch_objects[-1] if patch_objects and isinstance(patch_objects[-1], dict) else {}
        order = [line_at(lines, prefix) for prefix in PREFIXES]
        checks = (
            len(beats) == 1,
            lines[:2] == [f"step: {start.get('step')}", f"session: {start.get('session')}"],
            all(index > 1 for index in order) and order == sorted(order) and len(set(order)) == 3,
            len(patches) >= 1,
            all(isinstance(obj, dict) and sorted(obj) == ["body"] for obj in patch_objects),
            "last event: system init" in str(last.get("body", "")),
            first.returncode == second.returncode,
            first.stdout == second.stdout,
        )
        self.assertEqual(checks, (True,) * len(checks), "no heartbeat comment edited in place")

    def test_failed_comment_skipped(self):
        # C11.18: a heartbeat comment that fails is tried again at the next poll, and the run goes on as
        # the run whose comments work does.
        _, failed, _, number, bodies = self.live_run(0.3, comment_code=1)
        _, working, _, _, _ = self.live_run(0.3)
        beats = [
            record
            for record in bodies
            if record["args"] == ["issue", "comment", str(number), "--body-file", "-"]
            and record["body"].startswith("step: ")
        ]
        checks = (
            failed.returncode == working.returncode,
            failed.stdout == working.stdout,
            len(beats) >= 2,
        )
        self.assertEqual(
            checks,
            (True,) * len(checks),
            "a failed heartbeat comment was not skipped and tried again",
        )
