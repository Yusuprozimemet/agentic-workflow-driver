"""Day 10, C10.24: the level 2 count (driver/status.py, level_2_run) counts a merge without a change
only when a container session opened that pull request. The records are the run log's lines, oldest
first, as the driver writes them; the count reads the lines and nothing else."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver import status


class Level2ContainerTest(unittest.TestCase):
    def test_only_container_sessions_count(self):
        sessions = [
            {"event": "start", "session": "c1", "step": "Step A", "container": "driver-c1"},
            {
                "event": "end",
                "session": "c1",
                "outcome": "opened: #5 from `x`",
                "cost_usd": 0.1,
                "denials": 0,
            },
            {"event": "start", "session": "p1", "step": "Step B"},
            {
                "event": "end",
                "session": "p1",
                "outcome": "opened: #6 from `y`",
                "cost_usd": 0.1,
                "denials": 0,
            },
        ]
        # #5 was opened in a container and #6 on the PC. The newest merge, #5, counts; #6 ends it.
        self.assertEqual(
            status.level_2_run(
                sessions
                + [
                    {"event": "merged", "pr": 6, "changed": False},
                    {"event": "merged", "pr": 5, "changed": False},
                ]
            ),
            1,
        )
        # Swapped, the newest merge is #6, which the PC opened, so the count stops at once.
        self.assertEqual(
            status.level_2_run(
                sessions
                + [
                    {"event": "merged", "pr": 5, "changed": False},
                    {"event": "merged", "pr": 6, "changed": False},
                ]
            ),
            0,
        )
        # No session opened #9, so its merge ends the count.
        self.assertEqual(status.level_2_run([{"event": "merged", "pr": 9, "changed": False}]), 0)
