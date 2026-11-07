"""start() and end() append one JSON line each, in UTF-8 with no carriage return, and a second
process reads them back. open_session() finds the session started and not ended for a prefix, and
refuses a log with a line it cannot read, torn or not an object, rather than guessing past it."""

import datetime
import importlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Read in a process of its own, so the bytes are checked by something that did not write them.
# The reader prints ASCII, so the pipe's encoding does not matter on Windows.
READER = (
    "import json, sys; "
    "print(json.dumps(json.loads(open(sys.argv[1], 'rb').read().decode('utf-8'))))"
)


class RunLogTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone, and
        # scripts/track-red.py counts a module that does not load as not run, not as red.
        self.runlog = importlib.import_module("driver.runlog")
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)

    def read_bytes(self):
        return Path(self.runlog.path(self.state)).read_bytes()

    def test_start_line_is_on_disk(self):
        session = str(uuid.uuid4())
        self.runlog.start(
            self.state,
            "Day 04 Track B: C04.4–C04.5",
            "day-04/track-b",
            session,
            "2.1.312 (Claude Code)",
        )
        result = subprocess.run(
            [sys.executable, "-c", READER, self.runlog.path(self.state)],
            capture_output=True,
            check=True,
        )
        line = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(list(line), ["event", "at", "step", "prefix", "session", "claude"])
        self.assertEqual(line["event"], "start")
        self.assertEqual(line["step"], "Day 04 Track B: C04.4–C04.5")
        self.assertEqual(line["prefix"], "day-04/track-b")
        self.assertEqual(line["session"], session)
        self.assertEqual(line["claude"], "2.1.312 (Claude Code)")
        datetime.datetime.strptime(line["at"], "%Y-%m-%dT%H:%M:%SZ")

    def test_end_line(self):
        session = str(uuid.uuid4())
        self.runlog.start(self.state, "Day 04 Track B", "day-04/track-b", session, "2.1.312")
        self.runlog.end(self.state, session, "opened: #23 from day-04/track-b-x", 1.25, 2)
        data = self.read_bytes()
        self.assertEqual(data.count(b"\n"), 2)
        self.assertTrue(data.endswith(b"\n"))
        self.assertNotIn(b"\r", data)
        line = json.loads(data.split(b"\n")[1].decode("utf-8"))
        self.assertEqual(list(line), ["event", "at", "session", "outcome", "cost_usd", "denials"])
        self.assertEqual(line["event"], "end")
        self.assertEqual(line["session"], session)
        self.assertEqual(line["outcome"], "opened: #23 from day-04/track-b-x")
        self.assertEqual(line["cost_usd"], 1.25)
        self.assertEqual(line["denials"], 2)
        with self.subTest("cost_usd None is null"):
            self.runlog.end(self.state, session, "parked", None, 0)
            line = json.loads(self.read_bytes().split(b"\n")[2].decode("utf-8"))
            self.assertIsNone(line["cost_usd"])

    def test_open_session(self):
        prefix = "day-04/track-b"
        self.assertEqual(self.runlog.open_session(self.state, prefix), (None, None))
        session = str(uuid.uuid4())
        self.runlog.start(self.state, "Day 04 Track B", prefix, session, "2.1.312")
        self.assertEqual(self.runlog.open_session(self.state, prefix), (session, None))
        self.assertEqual(self.runlog.open_session(self.state, "day-04/track-c"), (None, None))
        self.runlog.end(self.state, session, "parked", None, 0)
        self.assertEqual(self.runlog.open_session(self.state, prefix), (None, None))
        with self.subTest("the last start that has no end"):
            first = str(uuid.uuid4())
            second = str(uuid.uuid4())
            self.runlog.start(self.state, "Day 04 Track B", prefix, first, "2.1.312")
            self.runlog.end(self.state, first, "opened", 0.5, 0)
            self.runlog.start(self.state, "Day 04 Track B", prefix, second, "2.1.312")
            self.assertEqual(self.runlog.open_session(self.state, prefix), (second, None))

    def test_torn_log(self):
        prefix = "day-04/track-b"
        self.runlog.start(self.state, "Day 04 Track B", prefix, str(uuid.uuid4()), "2.1.312")
        with open(self.runlog.path(self.state), "ab") as f:
            f.write(b'{"event": "sta')
        self.assertEqual(
            self.runlog.open_session(self.state, prefix),
            (None, "the run log cannot be read at line 2"),
        )
        with self.subTest("a line that is JSON but not an object"):
            Path(self.runlog.path(self.state)).write_bytes(b"[1, 2]\n")
            self.assertEqual(
                self.runlog.open_session(self.state, prefix),
                (None, "the run log cannot be read at line 1"),
            )
