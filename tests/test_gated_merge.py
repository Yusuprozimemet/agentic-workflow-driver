"""The gated merge (Day 8, C08.7 and C08.9): at a start that takes the lock, a pull request that a wait
or park line named, and that no merged or closed line settles, is asked once, and its merged or
closed line is written before the run's first step. Each case writes the earlier run's log as bytes,
then runs --once or `on` against a fake gh whose views answer the start-time read. An open pull
request writes nothing."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import drift_of
from tests.test_merge_wait import view
from tests.test_on import OnCase
from tests.test_once import DASHED, once
from tests.test_once_park_issues import build
from tests.test_runlog_report import RunLogLines

AT = "2026-11-10T00:00:00Z"


def park(head):
    # The park a gated wait writes for #7, with the head it had.
    return {
        "event": "park",
        "at": AT,
        "step": DASHED,
        "line": "park: #7 touches plan.md",
        "pr": 7,
        "head": head,
    }


def wait():
    return {"event": "wait", "at": AT, "pr": 7}


def settled(lines):
    # The merged and closed lines, compared by these keys only: never `at`.
    return [
        (line.get("event"), line.get("pr"), line.get("head"), line.get("changed"))
        for line in lines
        if line.get("event") in ("merged", "closed")
    ]


def events_of(lines, names):
    return [line.get("event") for line in lines if line.get("event") in names]


class GatedMergeTest(RunLogLines, OnCase, unittest.TestCase):
    def write_log(self, state, lines):
        # The earlier run's log, one JSON object per line; written as bytes, as the driver does.
        state.mkdir(parents=True, exist_ok=True)
        (state / "run.jsonl").write_bytes(
            b"".join(json.dumps(line).encode("utf-8") + b"\n" for line in lines)
        )

    def set_gh(self, folder, views):
        # build() takes no views and opens no pull request in the fake gh: the pull request #7 is
        # not open, so only the start-time reads and the session can ask it.
        path = folder / "gh" / "fake.json"
        spec = json.loads(path.read_bytes())
        spec["views"] = views
        spec["prs"] = []
        path.write_bytes(json.dumps(spec).encode("utf-8"))

    def once_case(self, name, lines, views):
        # One --once run on a fresh project, with the log written before it; returns the flags,
        # the exit code, stderr and the run log's lines.
        folder = Path(self.root) / name
        folder.mkdir()
        flags = build(folder, drift=drift_of(DASHED))
        self.set_gh(folder, views)
        self.write_log(folder / "state", lines)
        code, _, err = once(self.copy, *flags)
        return flags, code, err, self.log_of(folder / "state")

    def test_merged_after_park(self):
        flags, _, _, lines = self.once_case(
            "merged-once", [park("aaa")], [view("MERGED", head="aaa")]
        )
        # The merged line comes before the start of the run's first session.
        events = events_of(lines, ("merged", "start"))
        self.assertEqual(events[:2], ["merged", "start"])
        self.assertEqual(settled(lines), [("merged", 7, "aaa", False)])
        once(self.copy, *flags)
        state = Path(self.root) / "merged-once" / "state"
        self.assertEqual(settled(self.log_of(state)), [("merged", 7, "aaa", False)])

    def test_on_writes_merged_at_start(self):
        self.build("on-merged", steps=1, views=[view("MERGED", head="aaa")])
        self.set_gh(self.folder, [view("MERGED", head="aaa")])
        self.write_log(self.state, [park("aaa")])
        self.on()
        events = events_of(self.log_of(self.state), ("merged", "start"))
        self.assertEqual(events[:2], ["merged", "start"])
        self.assertEqual(settled(self.log_of(self.state)), [("merged", 7, "aaa", False)])

    def test_two_parks_one_line(self):
        _, _, _, lines = self.once_case(
            "two-parks", [park("aaa"), park("bbb")], [view("MERGED", head="bbb")]
        )
        self.assertEqual(settled(lines), [("merged", 7, "bbb", False)])

    def test_changed(self):
        _, _, _, lines = self.once_case("changed", [park("aaa")], [view("MERGED", head="bbb")])
        self.assertEqual(settled(lines), [("merged", 7, "bbb", True)])

    def test_wait_only_null(self):
        _, _, _, lines = self.once_case("wait-only", [wait()], [view("MERGED", head="aaa")])
        self.assertEqual(settled(lines), [("merged", 7, "aaa", None)])

    def test_closed(self):
        _, _, _, lines = self.once_case("closed", [park("aaa")], [view("CLOSED", head="aaa")])
        self.assertEqual(settled(lines), [("closed", 7, None, None)])

    def test_gh_fails(self):
        _, code, err, lines = self.once_case("gh-fails", [park("aaa")], [{"code": 1, "out": ""}])
        self.assertEqual(
            (code, err.splitlines()[-1:]),
            (2, ["cannot read the project: gh pr view exited 1"]),
        )
        self.assertEqual(events_of(lines, ("start", "merged", "closed")), [])

    def test_open_adds_nothing(self):
        _, _, _, lines = self.once_case("open", [wait(), park("aaa")], [view("OPEN", head="aaa")])
        self.assertEqual(events_of(lines, ("start", "merged", "closed")), ["start"])


if __name__ == "__main__":
    unittest.main()
