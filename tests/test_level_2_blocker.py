"""Day 13, C13.19 (and Track C's C13.6): the level 2 count, status.level_2_run in driver/status.py, passes
over the reviewer's first blocker park; of the reviewer's parks, only "still has a blocker ... after two
fixes" is to end it (C13.6). The records are the run log's lines, oldest first, as the driver writes them."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver import status


def container_merges(first, k):
    # The run log's lines for k pull requests, first to first + k - 1: each opened by a container
    # session and merged without a change, as tests/test_level_2_container.py writes them.
    records = []
    for n in range(first, first + k):
        session = f"00000000-0000-4000-8000-{n:012d}"
        records.append(
            {
                "event": "start",
                "session": session,
                "step": "Day 01 Track A: x",
                "container": f"driver-{session}",
            }
        )
        records.append(
            {
                "event": "end",
                "session": session,
                "outcome": f"opened: #{n} from `x`",
                "cost_usd": 0,
                "denials": 0,
            }
        )
        records.append({"event": "merged", "pr": n, "changed": False})
    return records


class LevelTwoBlockerTest(unittest.TestCase):
    def test_other_blocker_park_passes(self):
        # A blocker park is a line the count passes over: the five merges before it and the two after
        # it are seven in a row, so the count does not stop at the park.
        records = (
            container_merges(1, 5)
            + [
                {
                    "event": "park",
                    "step": "Day 01 Track A: x",
                    "line": "park: the reviewer has a blocker on #9: x",
                    "pr": 9,
                }
            ]
            + container_merges(6, 2)
        )
        self.assertEqual(status.level_2_run(records), 7)

    def test_blocker_park_ends_the_count(self):
        # The reviewer's park after two fixes ends the count, so only the two merges after it count.
        records = (
            container_merges(1, 5)
            + [
                {
                    "event": "park",
                    "step": "Day 01 Track A: x",
                    "line": "park: the reviewer still has a blocker on #9 after two fixes",
                    "pr": 9,
                }
            ]
            + container_merges(6, 2)
        )
        self.assertEqual(status.level_2_run(records), 2)
