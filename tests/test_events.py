"""The session's events file (Day 11, Track B): --once reads the session's stdout line by line on a reader
thread, names each line's kind in stream.kind, and appends it with its time to the session's events file.
The file keeps the lines read before a session ends, a partial last line included, and a session killed
at its bound keeps the lines it had. The outcome case runs from test_once_outcome's harness and the bound
case from the driver copy and the fake claude of test_once; test_once_outcome is imported as a module, so
its own tests do not run again here. No report here names a pid, uuid or path."""

import datetime
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
from tests.test_halt import stop
from tests.test_once import DASHED, driver_copy
from tests.test_once_halt import kill_left_over
from tests.test_once_park_issues import build

SYSTEM = {"type": "system", "subtype": "init"}
TOOL = {
    "type": "assistant",
    "message": {
        "id": "m1",
        "content": [{"type": "tool_use", "name": "Bash"}],
        "usage": {
            "input_tokens": 10,
            "cache_creation_input_tokens": 5,
            "cache_read_input_tokens": 100,
            "output_tokens": 7,
        },
    },
}
USER = {"type": "user"}
TEXT = {
    "type": "assistant",
    "message": {
        "id": "m2",
        "content": [{"type": "text", "text": "done"}],
        "usage": {"input_tokens": 3, "output_tokens": 20},
    },
}
# The start of a line the session wrote and did not finish: the bound kills it before the newline.
PARTIAL = '{"type": "assi'
PARK = "park: the session ran past 0.05 minutes (session `<uuid>`)"


class StreamKindTest(unittest.TestCase):
    def test_kinds(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone.
        from driver import stream

        lines = [
            json.dumps({"type": "system", "subtype": "init"}),
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "text", "text": "a"},
                            {"type": "tool_use", "name": "Read"},
                        ]
                    },
                }
            ),
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "thinking", "thinking": "x"}]},
                }
            ),
            json.dumps({"type": "user"}),
            json.dumps({"type": "result"}),
            json.dumps({"type": "rate_limit_event"}),
            "[1, 2]",
            json.dumps({"no": "type"}),
            PARTIAL,
        ]
        self.assertEqual(
            [stream.kind(line) for line in lines],
            [
                "system init",
                "tool Read",
                "assistant",
                "tool result",
                "result",
                "rate_limit_event",
                "unparsed",
                "unparsed",
                "unparsed",
            ],
        )


class EventsTest(unittest.TestCase):
    setUp = outcome.OutcomeTest.setUp
    copy_of = outcome.OutcomeTest.copy_of
    run_case = outcome.OutcomeTest.run_case

    def events(self, state, session):
        # The events file's lines, read as bytes and decoded as UTF-8.
        path = Path(state) / "sessions" / f"{session}.events.jsonl"
        self.assertTrue(path.exists(), "the session has no events file")
        return [json.loads(line) for line in path.read_bytes().decode("utf-8").splitlines()]

    def run_driver(self, do):
        # A --once run with the fake claude of do and a bound of 0.05 minutes; its output goes to files
        # in its folder, since the fake's sleep would otherwise keep a pipe open.
        folder = Path(tempfile.mkdtemp(dir=self.root))
        flags = build(folder, drift=drift_of(DASHED), do=do)
        copy = driver_copy(tempfile.mkdtemp(dir=self.root))
        self.addCleanup(kill_left_over, folder / "claude")
        with open(folder / "stdout.txt", "wb") as out, open(folder / "stderr.txt", "wb") as err:
            driver = subprocess.Popen(
                [sys.executable, str(copy / "run-steps.py"), "--once", *flags]
                + ["--poll", "0.2", "--session-minutes", "0.05"],
                stdout=out,
                stderr=err,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        self.addCleanup(stop, driver)
        return folder, driver

    def test_events_file(self):
        # Imported here, as in StreamKindTest: where driver/ is missing, each test fails alone.
        from driver import lock

        lines = [
            json.dumps(SYSTEM),
            json.dumps(TOOL),
            json.dumps(USER),
            json.dumps(TEXT),
            "not json",
            "",
        ]
        do = f"for line in {lines!r}: print(line)"
        result = self.run_case(copy=self.copy_of(), do=do)
        self.assertEqual((result["code"], result["out"].strip()), (0, outcome.OPENED))
        self.assertEqual(len(result["starts"]), 1, "the run did not start one session")
        events = self.events(result["state"], result["starts"][0]["session"])
        kinds = [event.get("kind") for event in events]
        self.assertEqual(
            kinds, ["system init", "tool Bash", "tool result", "reply", "unparsed", "result"]
        )
        stamps = []
        for event in events:
            try:
                datetime.datetime.strptime(event.get("at"), lock.STAMP)
                stamps.append(True)
            except (TypeError, ValueError):
                stamps.append(False)
        self.assertEqual(stamps, [True] * len(events))
        tool = events[1]
        self.assertEqual((tool.get("message"), tool.get("in"), tool.get("out")), ("m1", 115, 7))

    def test_bound_keeps_events_read(self):
        do = (
            f"print({json.dumps(SYSTEM)!r}, flush=True)\n"
            f"sys.stdout.write({PARTIAL!r})\n"
            "sys.stdout.flush()\n"
            "import time; time.sleep(60)\n"
        )
        folder, driver = self.run_driver(do)
        self.assertEqual(driver.wait(timeout=60), 1)
        sessions = list((folder / "state" / "sessions").glob("*.events.jsonl"))
        self.assertEqual(len(sessions), 1, "the run did not write one events file")
        session = sessions[0].name[: -len(".events.jsonl")]
        stdout = (folder / "stdout.txt").read_bytes().decode("utf-8")
        stdout = stdout.replace(session, "<uuid>")
        self.assertTrue(PARK in stdout.splitlines(), "the park line for the bound is not printed")
        kinds = [event.get("kind") for event in self.events(folder / "state", session)]
        self.assertEqual(kinds, ["system init", "unparsed"])
