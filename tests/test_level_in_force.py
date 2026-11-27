"""Day 16's level in force in `on` and `status` (driver/switchlog.py, in_force): C16.3, C16.5 and C16.6. A
lowering line in the switch log runs a level 2 config as level 1 until a raise line lifts it; a switch log
that cannot be read refuses the start at level 2; at driver.json's level 1 the switch log is not read. Each
case is LevelStartTest's container set-up with every level 2 condition holding."""

import json
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The module, not the class: a class imported by name would have its tests collected here again.
from tests import test_box_session as box_session
from tests import test_level_2_start as level_start
from tests.test_level_2_start import CLASSIC
from tests.test_merge_wait import view
from tests.test_review_loop import HEAD, R, ReviewCase, rewrite, same, without_at

LOWERING = {
    "event": "level",
    "level": 1,
    "from": 2,
    "escapes": ["D23.4"],
    "at": "2026-11-27T00:00:00Z",
}
RAISE = {"event": "level", "level": 2, "by": "maintainer", "at": "2026-11-27T01:00:00Z"}
LOWERED = "level: 1, lowered from 2 on an escape: D23.4; run-steps.py raise lifts it"
OPENED = "opened: #12 from `day-01/track-a-x`"
# An on line, then a line that is not JSON: the switch log's second line cannot be read.
UNREADABLE = b'{"event": "on", "at": "x"}\n{\n'
UNREADABLE_LINE = "<state>/switches.jsonl: line 2 cannot be read"


def lines_of(*records):
    # The switch log's bytes, one JSON line each: text mode would add a carriage return on Windows.
    return b"".join(json.dumps(record).encode("utf-8") + b"\n" for record in records)


class LevelInForceTest(ReviewCase, unittest.TestCase):
    # LevelStartTest's helpers by assignment, as it borrows BoxSessionTest's.
    box = level_start.LevelStartTest.box
    hidden = level_start.LevelStartTest.hidden
    run_steps = level_start.LevelStartTest.run_steps
    holds = level_start.LevelStartTest.holds
    seed = level_start.LevelStartTest.seed
    starts = level_start.LevelStartTest.starts

    def case(self, name, switches, level=2):
        # test_starts_when_all_hold's set-up: a session, then the reviewer's clean answer, and #12 read
        # open twice before it is merged. The switch log is written last, as bytes.
        reviewer_answer = json.dumps(
            {"type": "result", "is_error": False, "result": "REVIEW: none", "session_id": R}
        )
        self.box(
            name,
            run=[
                {
                    "tail": ["--session-id", box_session.U],
                    "stdout": box_session.result(box_session.U),
                },
                {"tail": ["--session-id", R], "stdout": reviewer_answer},
            ],
            steps=1,
        )
        self.reviewed(
            views=[view("OPEN", head=HEAD), view("OPEN", head=HEAD), view("MERGED", head=HEAD)]
        )
        if level is not None:
            rewrite(self.folder / "driver.json", level=level)
        self.holds()
        self.seed(15)
        (self.state / "switches.jsonl").write_bytes(switches)

    def on(self):
        # One run of `on` with the step's uuid first and the reviewer's after; returns (code, out, err).
        def uuids():
            yield uuid.UUID(box_session.U)
            while True:
                yield uuid.UUID(R)

        with mock.patch("uuid.uuid4", side_effect=uuids().__next__):
            return self.run_steps("on")

    def switch_lines(self):
        # The switch log's records, in the order they were written.
        return [
            json.loads(line) for line in (self.state / "switches.jsonl").read_bytes().splitlines()
        ]

    def held(self, text):
        # The state folder, in each spelling it may take, read <state>; the path's separator read /.
        lines = []
        for line in text.splitlines():
            for form in sorted(
                {str(self.state), os.path.realpath(self.state)}, key=len, reverse=True
            ):
                line = line.replace(form, "<state>")
            lines.append(line.replace("\\", "/"))
        return lines

    def test_lowered_runs_at_one(self):
        # C16.3: the lowering line runs the level 2 config as level 1: the line first, no protection read,
        # the session started, and no merge asked. The waived checks are level 2's, so none is named and
        # the on line carries none.
        self.case("lowered_at_one", lines_of(LOWERING))
        rewrite(self.folder / "driver.json", waived_checks=level_start.WAIVED)
        before = len(self.starts())
        _, out, _ = self.on()
        ons = [without_at(r) for r in self.switch_lines() if r.get("event") == "on"]
        found = (
            out.splitlines()[:2],
            [call for call in self.gh_of() if call[:2] == ["api", CLASSIC]],
            len(self.starts()) - before > 0,
            self.gh_of("pr", "merge"),
            not any(line.startswith("level 2: waived") for line in out.splitlines()),
            ons[-1] if ons else None,
        )
        same(self, found, ([LOWERED, OPENED], [], True, [], True, {"event": "on"}))
        # After a raise line, level 2 again: no level line, main's protection read, and the merge asked.
        self.case("raised_at_two", lines_of(LOWERING, RAISE))
        _, out, _ = self.on()
        found = (
            not any(line.startswith("level: ") for line in out.splitlines()),
            any(call[:2] == ["api", CLASSIC] for call in self.gh_of()),
            len(self.gh_of("pr", "merge")) > 0,
        )
        same(self, found, (True, True, True))

    def test_unreadable_switch_log(self):
        # C16.5: at level 2 a switch log that cannot be read refuses the start, and status cannot say the level.
        self.case("unreadable", UNREADABLE)
        before = len(self.starts())
        code, _, err = self.on()
        found = (
            code,
            self.held(err),
            len(self.starts()) - before,
            [call for call in self.gh_of() if call[:2] == ["issue", "create"]],
        )
        same(
            self,
            found,
            (2, [f"cannot start: the level cannot be read: {UNREADABLE_LINE}"], 0, []),
        )
        code, out, _ = self.run_steps("status")
        lines = self.held(out)
        found = (code, lines[1] if len(lines) > 1 else None)
        same(self, found, (2, f"level: unknown: {UNREADABLE_LINE}"))

    def test_level_one_reads_no_switches(self):
        # C16.6: with no level in driver.json, neither a lowering line nor an unreadable switch log changes
        # the start or status's level line.
        for name, switches in [("one_lowered", lines_of(LOWERING)), ("one_unreadable", UNREADABLE)]:
            self.case(name, switches, level=None)
            before = len(self.starts())
            _, out, _ = self.on()
            started = len(self.starts()) - before > 0
            code, status_out, _ = self.run_steps("status")
            lines = status_out.splitlines()
            found = (
                not any(line.startswith("level: ") for line in out.splitlines()),
                started,
                lines[1] if len(lines) > 1 else None,
                code,
            )
            with self.subTest(name):
                same(self, found, (True, True, "level: 1", 0))
