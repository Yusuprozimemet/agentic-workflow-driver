"""Day 9, C09.14: the level 2 count (driver/status.py, level_2_run) stops at the park line that
driver/loop.py's wait_pr returns after two fixes, once driver/once.py's park_issue has written it to
the run log. No code changes: the test ties the two sentences, with the fakes of test_wait.py."""

import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import test_wait


class Level2SentenceTest(unittest.TestCase):
    def test_loop_park_stops_the_count(self):
        loop = importlib.import_module("driver.loop")
        once = importlib.import_module("driver.once")
        status = importlib.import_module("driver.status")
        runlog = importlib.import_module("driver.runlog")
        # build is a plain function from WaitTest: it sets the folder, project, args, record and
        # command on self and registers its cleanup, so it is called with this test as self.
        test_wait.WaitTest.build(self, [test_wait.RED])
        line, code = loop.wait_pr(self.args, self.project, 12, self.record, self.command)
        self.assertEqual(
            (line, code), ("park: the checks on #12 are still red after two fixes: tests", 1)
        )
        # Passed on as once.finish passes it: the park is written to the run log as a park line.
        once.park_issue(
            self.project,
            self.args.gh,
            self.args.state,
            line,
            test_wait.STEP,
            test_wait.SESSION,
            [],
        )
        records, reason = runlog.read(self.args.state)
        self.assertIsNone(reason)
        parks = [r for r in records if r["event"] == "park"]
        self.assertEqual(len(parks), 1)
        self.assertEqual(parks[0]["line"], line)
        park = parks[0]
        merged = [{"event": "merged", "pr": n, "changed": False} for n in (13, 14)]
        # Both merges were opened in a container, so the count only stops on the park.
        sessions = [
            {"event": "start", "session": "s13", "step": "Step A", "container": "driver-s13"},
            {"event": "end", "session": "s13", "outcome": "opened: #13 from `b13`"},
            {"event": "start", "session": "s14", "step": "Step A", "container": "driver-s14"},
            {"event": "end", "session": "s14", "outcome": "opened: #14 from `b14`"},
        ]
        # The park line is the newest, so the count stops on it before any merge.
        self.assertEqual(status.level_2_run(sessions + merged + [park]), 0)
        # The park line is the oldest, so both merges count before the count reaches it.
        self.assertEqual(status.level_2_run(sessions + [park] + merged), 2)
