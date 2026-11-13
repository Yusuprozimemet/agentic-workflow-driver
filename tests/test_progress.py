"""progress gives the three lines a live session adds to status: how long it has run and its estimate,
its last event and how long ago, and the tokens so far. Each test calls it with a run log and an
events list built by hand, and a fixed now, so no clock is read."""

import datetime
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver import lock, status

NOW = "2026-11-13T12:00:00Z"
NOW_TIME = lock.stamp_time(NOW)
TRACK = "day-11/track-a"


def ago(seconds):
    # The stamp that many seconds before NOW, as the run log and the events file write them.
    return (NOW_TIME - datetime.timedelta(seconds=seconds)).strftime(lock.STAMP)


def start(session, prefix, at):
    return {"event": "start", "at": at, "session": session, "step": "Day 11", "prefix": prefix}


def end(session, at):
    return {"event": "end", "at": at, "session": session}


def finished(session, prefix, begin, length):
    # A session that started begin seconds before NOW and ended length seconds later.
    return [start(session, prefix, ago(begin)), end(session, ago(begin - length))]


def earlier(*lengths):
    # Ended track sessions of the given lengths in seconds, begun long before the running one.
    records = []
    for index, length in enumerate(lengths):
        records += finished(f"t{index}", TRACK, 100000 + index * 10000, length)
    return records


def running(prefix=TRACK, begin=725):
    # The session under test: started begin seconds before NOW (725s is 12m05s).
    return [start("run", prefix, ago(begin))]


class ProgressTest(unittest.TestCase):
    def test_progress_lines(self):
        records = earlier(600, 1200, 2400) + running()
        events = [
            {"at": ago(700), "kind": "system init"},
            {"at": ago(600), "kind": "reply", "message": "m1", "in": 115, "out": 7},
            {"at": ago(500), "kind": "reply", "message": "m1", "in": 115, "out": 9},
            {"at": ago(400), "kind": "reply", "message": "m2", "in": 3, "out": 20},
            {"at": ago(40), "kind": "tool Bash"},
        ]
        lines = status.progress(records, "run", events, NOW_TIME)
        self.assertEqual(
            lines,
            [
                "running: 12m05s (estimate 20m00s, the median of 3 earlier track sessions)",
                "last event: tool Bash, 0m40s ago",
                "tokens so far: 118 in, 29 out",
            ],
        )

    def test_estimate_edges(self):
        cases = [
            (
                "two earlier track sessions",
                earlier(600, 1200) + running(),
                "running: 12m05s (no estimate: 2 earlier track sessions)",
            ),
            (
                "four of 10, 20, 30 and 41 minutes",
                earlier(600, 1200, 1800, 2460) + running(),
                "running: 12m05s (estimate 25m00s, the median of 4 earlier track sessions)",
            ),
            (
                "four of 10m00s, 20m00s, 20m01s and 41m00s",
                earlier(600, 1200, 1201, 2460) + running(),
                "running: 12m05s (estimate 20m00s, the median of 4 earlier track sessions)",
            ),
            (
                "no start line for the session",
                earlier(600, 1200, 2400),
                "running: unknown (no start line)",
            ),
            (
                "an earlier track session with no end line, and a spec session, not counted",
                earlier(600, 1200, 2400)
                + [start("t9", TRACK, ago(90000))]
                + finished("sp", "day-11/spec", 95000, 600)
                + running(),
                "running: 12m05s (estimate 20m00s, the median of 3 earlier track sessions)",
            ),
            (
                "a prefix that is none of the three kinds",
                earlier(600, 1200, 2400) + running(prefix="day-11/other"),
                "running: 12m05s (no estimate: the step has no kind)",
            ),
        ]
        for name, records, first in cases:
            with self.subTest(name):
                lines = status.progress(records, "run", [], NOW_TIME)
                self.assertEqual(lines[0], first)

    def test_no_events(self):
        records = earlier(600, 1200, 2400) + running()
        lines = status.progress(records, "run", [], NOW_TIME)
        self.assertEqual(
            lines[1:],
            ["last event: none yet", "tokens so far: 0 in, 0 out"],
        )


if __name__ == "__main__":
    unittest.main()
