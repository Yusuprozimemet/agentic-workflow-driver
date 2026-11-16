"""driver-runs.py reads the switch log beside the run log: a session a halt names is not counted as
crashed, and the document it writes carries the switch lines as `switches`."""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location("driver_runs", ROOT / "scripts" / "driver-runs.py")
dr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dr)

STEP = "Day 13 Track A: x"
PREFIX = "day-13/track-a"
# A pid of a process that is not running, so the count does not take the session for a live one.
DEAD_PID = 999991


def start(session):
    return {
        "event": "start",
        "at": "2026-11-10T23:40:00Z",
        "step": STEP,
        "prefix": PREFIX,
        "session": session,
        "claude": "2.1.312",
        "issue": 7,
    }


def pid(session):
    return {
        "event": "pid",
        "at": "2026-11-10T23:40:01Z",
        "session": session,
        "pid": DEAD_PID,
        "started": "2026-11-10T23:40:01Z",
    }


def halt(session):
    return {
        "event": "halt",
        "at": "2026-11-10T23:49:58Z",
        "why": "STOP issue #92",
        "session": session,
    }


def crashed_of(doc):
    # The sessions' crashed flags, in the order the document gives them: a missing key gives None.
    return [run.get("crashed") for step in doc.get("steps", []) for run in step.get("sessions", [])]


class SwitchCountTest(unittest.TestCase):
    def test_a_halted_session_did_not_crash(self):
        records = [start("s1"), pid("s1")]
        steps = dr.count(records, None, (), [halt("s1")])
        self.assertEqual(len(steps), 1)
        self.assertEqual((steps[0]["sessions"][0]["crashed"], steps[0]["crashes"]), (False, 0))
        steps = dr.count(records, None, ())
        self.assertEqual(len(steps), 1)
        self.assertEqual((steps[0]["sessions"][0]["crashed"], steps[0]["crashes"]), (True, 1))

    def test_the_document_carries_the_switches(self):
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, True)
        out = os.path.join(tempfile.mkdtemp(), "driver-runs.json")
        self.addCleanup(shutil.rmtree, os.path.dirname(out), True)
        # Written as bytes: one JSON object per line, with \n between them on every platform.
        run = "".join(json.dumps(record) + "\n" for record in [start("s1"), pid("s1")])
        Path(state, "run.jsonl").write_bytes(run.encode("utf-8"))
        Path(state, "switches.jsonl").write_bytes((json.dumps(halt("s1")) + "\n").encode("utf-8"))
        with contextlib.redirect_stdout(io.StringIO()):
            dr.main(["--state", state, "--out", out])
        doc = json.loads(Path(out).read_bytes().decode("utf-8"))
        self.assertEqual(doc.get("switches"), [halt("s1")])
        self.assertEqual(crashed_of(doc), [False])

        os.remove(os.path.join(state, "switches.jsonl"))
        with contextlib.redirect_stdout(io.StringIO()):
            dr.main(["--state", state, "--out", out])
        doc = json.loads(Path(out).read_bytes().decode("utf-8"))
        self.assertEqual(doc.get("switches"), [])
        self.assertEqual(crashed_of(doc), [True])
