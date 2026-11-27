"""Day 16's escape in `on` (driver/loop.py, read_escapes): C16.7 to C16.11 and C16.20. At driver.json's level 2,
before each step the loop reads the finished Days of the --out JSON it has not read yet, writes an escapes line
for each, and goes back one level when one of them holds a Defect line found at the close, by the dashboard, in
a Day NN review or by the evidence replay; a failed evidence run after a driver merge lowers too. Each case is
LevelInForceTest's container set-up, two steps: Day 23's close, whose session writes the JSON after the close,
then Day 24's spec."""

import json
import subprocess
import sys
import types
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver import loop

# The module, not the class: a class imported by name would have its tests collected here again.
from tests import test_box_session as box_session
from tests import test_level_in_force as level_in_force
from tests.test_level_2_blocker import container_merges
from tests.test_level_in_force import LOWERING, UNREADABLE, UNREADABLE_LINE, lines_of
from tests.test_merge_wait import run, view
from tests.test_on import DRIFT_FILE_SCRIPT, OnCase
from tests.test_review_loop import HEAD, R, ReviewCase, rewrite, same, without_at

U = box_session.U
# The second step's session and its review's, after U and R.
U2 = "00000000-0000-4000-8000-000000000011"
R2 = "00000000-0000-4000-8000-000000000021"
CLOSE = "Day 23: the closing PR"
SPEC = "Day 24: read the spec against the code, then the spec-change PR"
TRACK = "Day 25 Track A: x"
PRS = [
    {"number": n, "headRefName": branch, "url": "u", "author": "me"}
    for n, branch in [(12, "day-23/close-the-day"), (13, "day-24/spec-x"), (14, "day-25/track-a-x")]
]
# Each pull request is read three times at level 2: by the review, then open when the merge is asked,
# then merged. After a lowering, #13 is merged by hand at the sixth read.
ONE = [view("OPEN", head=HEAD), view("OPEN", head=HEAD), view("MERGED", head=HEAD)]
SIX = ONE + ONE
ESCAPED = ["D23.4", "D23.5", "D23.6", "D23.7"]
LOWERED = "level: lowered to 1 from 2 on an escape: D23.4, D23.5, D23.6, D23.7"
ON = {"event": "on"}
ESCAPES_23 = {"event": "escapes", "day": 23, "found": ESCAPED}
LEVEL_1 = {"event": "level", "level": 1, "from": 2, "escapes": ESCAPED}
FOUND_LINE = "cannot read the project: spec-drift.py's JSON has no days[0].defects[1].found"
START_LINE = (
    "cannot start: level 2 needs each Defect line's found in spec-drift.py's JSON: "
    "days[0].defects[0] has none"
)
AT = "2026-11-27T00:00:00Z"


def defects(*pairs):
    # A Defect line per (id, found); a found of ... leaves the key out.
    return [{"id": i} if f is ... else {"id": i, "found": f} for i, f in pairs]


# Day 23's Defect lines after the close: D23.1 is no escape, the four after it are (D23.4 is defects[1]).
CLOSED = defects(
    ("D23.1", "track-reviewer"),
    ("D23.4", "close"),
    ("D23.5", "Day 22 review"),
    ("D23.6", "dashboard"),
    ("D23.7", "Evidence replay "),
)


def day(n, status, lines=None):
    record = {"day": n, "phase": 3, "status": status}
    if lines is not None:
        record["defects"] = lines
    return record


def drift(next_step, days, order=(23, 24)):
    return {
        "now": {"next_step": next_step, "open_prs": []},
        "order": list(order),
        "days": days,
        "meta": {"caveats": []},
    }


BEFORE = drift(CLOSE, [day(23, "active"), day(24, "ready")])


def after(lines=CLOSED, status="done"):
    # The JSON the close's session writes: Day 23 finished with its Defect lines, the next step Day 24's spec.
    return drift(SPEC, [day(23, status, lines), day(24, "ready")])


def answer(session, text="done", files=None):
    # A docker run's answer for the session: its result line, and the files written before it prints.
    out = {"type": "result", "is_error": False, "result": text, "session_id": session}
    entry = {"tail": ["--session-id", session], "stdout": json.dumps(out)}
    if files:
        entry["files"] = files
    return entry


class EscapeTest(ReviewCase, unittest.TestCase):
    # LevelInForceTest's helpers by assignment, as it borrows LevelStartTest's.
    box = level_in_force.LevelInForceTest.box
    hidden = level_in_force.LevelInForceTest.hidden
    run_steps = level_in_force.LevelInForceTest.run_steps
    holds = level_in_force.LevelInForceTest.holds
    seed = level_in_force.LevelInForceTest.seed
    starts = level_in_force.LevelInForceTest.starts
    switch_lines = level_in_force.LevelInForceTest.switch_lines
    held = level_in_force.LevelInForceTest.held

    def build(self, name, **kw):
        # The project's spec-drift.py copies <folder>/drift.json, so a session can change the JSON.
        return OnCase.build(self, name, script=DRIFT_FILE_SCRIPT, **kw)

    def case(self, name, start=BEFORE, later=None, level=2, steps=2, views=SIX, switches=None):
        # Two sessions and their reviews; U's session writes `later` as the JSON when it is given.
        target = Path(self.root) / name / "drift.json"
        files = {str(target): json.dumps(later)} if later is not None else None
        self.box(
            name,
            run=[
                answer(U, files=files),
                answer(R, "REVIEW: none"),
                answer(U2),
                answer(R2, "REVIEW: none"),
            ],
            steps=steps,
        )
        self.reviewed(views=list(views))
        rewrite(self.folder / "gh" / "fake.json", prs=PRS)
        if level is not None:
            rewrite(self.folder / "driver.json", level=level)
        self.holds()
        self.seed(15)
        target.write_bytes(json.dumps(start).encode("utf-8"))
        if switches is not None:
            (self.state / "switches.jsonl").write_bytes(switches)

    def on(self, ids=(U, R, U2, R2)):
        # One run of `on`, the sessions given these uuids in turn, the last repeated; returns (code, out,
        # err, the step starts it added: a review's start is not a step's).
        def uuids():
            yield from (uuid.UUID(i) for i in ids)
            while True:
                yield uuid.UUID(ids[-1])

        before = self.steps()
        with mock.patch("uuid.uuid4", side_effect=uuids().__next__):
            code, out, err = self.run_steps("on")
        return code, out, err, self.steps() - before

    def steps(self):
        return len([r for r in self.starts() if r.get("prefix") != "review"])

    def switches(self):
        # The switch log's records, `at` left out; none when it was never written.
        if not (self.state / "switches.jsonl").exists():
            return []
        return [without_at(r) for r in self.switch_lines()]

    def merges(self):
        return len(self.gh_of("pr", "merge"))

    def sha(self, text):
        # The project's main head read <sha>, its first seven characters <sha7>.
        done = subprocess.run(
            ["git", "-C", str(self.folder / "project"), "rev-parse", "origin/main"],
            capture_output=True,
            check=True,
        )
        sha = done.stdout.decode("utf-8").strip()
        return text.replace(sha, "<sha>").replace(sha[:7], "<sha7>")

    def test_close_escape_lowers(self):
        # C16.7: the close's escapes, found at the close, in a Day 22 review, by the dashboard and by the
        # evidence replay, lower the run to level 1: Day 24's pull request waits for a merge by hand.
        for status in ("done", "closed"):
            with self.subTest(status):
                self.case(f"close_{status}", later=after(status=status))
                _, out, _, started = self.on()
                found = (LOWERED in out.splitlines(), self.switches(), started, self.merges())
                same(self, found, (True, [ON, ESCAPES_23, LEVEL_1], 2, 1))

    def test_no_escape_no_change(self):
        # C16.8: no found value of specs/README.md's but the four escapes lowers: both pull requests merge.
        found_values = ["track-reviewer", "auditor", "seen red", "break on purpose", "review"]
        found_values += ["Day 22 review of D23", "spec-change PR", "Track A", "self", "rehearsal"]
        found_values += ["CI", "driver reviewer"]
        lines = defects(*[(f"D23.{n}", f) for n, f in enumerate(found_values, start=1)])
        self.case("no_escape", later=after(lines))
        _, out, _, _ = self.on()
        found = (
            [r for r in self.switches() if r.get("event") == "level"],
            any(line.startswith("level: lowered") for line in out.splitlines()),
            self.merges(),
        )
        same(self, found, ([], False, 2))

    def test_failed_evidence_lowers(self):
        # C16.9: a driver merge whose evidence run ends failure lowers to 1 before the park line, and the
        # next on says so first. The first run list is ready()'s, the second the merge's evidence.
        evidence = [run("completed", "success"), run("completed", "failure")]
        park = "park: the evidence run on `<sha7>` ended `failure`"
        said = "level: 1, lowered from 2 on a failed evidence run of <sha7>; run-steps.py raise lifts it"
        self.case("evidence", steps=1, views=ONE)
        rewrite(self.folder / "gh" / "fake.json", run_steps=evidence)
        _, out, _, _ = self.on()
        lines = self.sha(out).splitlines()
        line = "level: lowered to 1 from 2 on a failed evidence run of <sha7>"
        k = lines.index(line) if line in lines else len(lines)
        switches = json.loads(self.sha(json.dumps(self.switches())))
        level = {"event": "level", "level": 1, "from": 2, "evidence": "<sha>"}
        same(self, (lines[k : k + 2], switches), ([line, park], [ON, level]))
        _, out, _, _ = self.on()
        lines = self.sha(out).splitlines()
        same(self, lines[:1], [said])
        # At a level in force of 1 there is no level 0: a merge by hand whose evidence fails only parks.
        self.case("evidence_at_one", steps=1, views=ONE, switches=lines_of(LOWERING))
        rewrite(self.folder / "gh" / "fake.json", run_steps=evidence)
        _, out, _, _ = self.on()
        lines = self.sha(out).splitlines()
        found = (
            any(x.startswith("level: lowered to") for x in lines),
            [r for r in self.switches() if r.get("event") == "level"],
            park in lines,
        )
        same(self, found, (False, [without_at(LOWERING)], True))

    def test_defect_without_found(self):
        # C16.10: a Defect line of the Day read with no found, absent or null, ends the run after the close;
        # a level 2 start with one in any Day refuses before any session.
        for name, lines in [
            ("found_absent", CLOSED[:1] + defects(("D23.4", ...)) + CLOSED[2:]),
            ("found_null", CLOSED[:1] + defects(("D23.4", None)) + CLOSED[2:]),
        ]:
            with self.subTest(name):
                self.case(name, later=after(lines))
                code, _, err, started = self.on()
                read = [r for r in self.switches() if r.get("event") in ("escapes", "level")]
                same(self, (code, err.splitlines()[-1:], started, read), (2, [FOUND_LINE], 1, []))
        with self.subTest("escape_without_id"):
            # Not a criterion's: an escape with no id is named as the missing found is, not a traceback.
            self.case("id_absent", later=after(CLOSED[:1] + [{"found": "close"}] + CLOSED[2:]))
            code, _, err, started = self.on()
            same(self, (code, err.splitlines()[-1:], started), (2, [FOUND_LINE[:-5] + "id"], 1))
        with self.subTest("at_the_start"):
            start = drift(CLOSE, [day(23, "active", defects(("D23.1", ...))), day(24, "ready")])
            self.case("found_at_start", start=start, later=after())
            code, _, err, started = self.on()
            same(self, (code, err.splitlines(), started), (2, [START_LINE], 0))

    def test_level_one_escape_changes_nothing(self):
        # C16.11: at driver.json's level 1 the JSON is not read for escapes: the escapes and a Defect line
        # without found (bearing's JSON) change nothing, and both steps start; the pull requests merge by hand.
        unfound = [{"id": d["id"]} for d in CLOSED]
        for name, lines in [("one_escapes", CLOSED), ("one_unfound", unfound)]:
            with self.subTest(name):
                self.case(name, later=after(lines), level=None)
                _, out, _, started = self.on()
                found = (
                    self.switches(),
                    any(line.startswith("level:") for line in out.splitlines()),
                    started,
                )
                same(self, found, ([ON], False, 2))

    def test_close_read_at_next_on(self):
        # C16.20: a close the run did not read, as the night's last step or merged by hand, is read by the
        # next on, once; Days are read after the latest one an escapes line names, by place in order.
        with self.subTest("last_step"):
            self.case("last_step", later=after(), steps=1)
            _, out, _, _ = self.on()
            first = ("on: 1 steps, the night's count" in out.splitlines(), self.switches())
            same(self, first, (True, [ON]))
            _, out, _, _ = self.on((U2, R2))
            lines = out.splitlines()
            opened = "opened: #13 from `day-24/spec-x`"
            k = lines.index(LOWERED) if LOWERED in lines else len(lines)
            found = (opened in lines[k + 1 :], self.switches(), self.merges())
            same(self, found, (True, [ON, ON, ESCAPES_23, LEVEL_1], 1))
        with self.subTest("read_once"):
            self.on((U2, R2))
            read = [r for r in self.switches() if r.get("event") == "escapes"]
            same(self, read, [ESCAPES_23])
        with self.subTest("by_hand"):
            # The close's merge by hand, written before the on: a container session opened #12, merged
            # with no change and no by, so the count is 16 and level 2 starts.
            self.case("by_hand", start=after(), steps=1)
            hand = b"".join(json.dumps(r).encode("utf-8") + b"\n" for r in container_merges(12, 1))
            with (self.state / "run.jsonl").open("ab") as log:
                log.write(hand)
            _, out, _, _ = self.on((U2, R2))
            found = (LOWERED in out.splitlines(), self.switches(), self.merges())
            same(self, found, (True, [ON, ESCAPES_23, LEVEL_1], 0))
        both = {"event": "level", "level": 1, "from": 2, "escapes": ["D23.4", "D24.2"]}
        cases = [
            (
                "two_days",
                (22, 23, 24, 25),
                22,
                {23: [("D23.4", "close")], 24: [("D24.2", "close")]},
                [
                    {"event": "escapes", "day": 23, "found": ["D23.4"]},
                    {"event": "escapes", "day": 24, "found": ["D24.2"]},
                    both,
                ],
            ),
            (
                "out_of_order",
                (22, 24, 23, 25),
                24,
                {23: [("D23.4", "close")], 24: []},
                [
                    {"event": "escapes", "day": 23, "found": ["D23.4"]},
                    {"event": "level", "level": 1, "from": 2, "escapes": ["D23.4"]},
                ],
            ),
        ]
        for name, order, named, found_at, expected in cases:
            with self.subTest(name):
                days = [day(22, "done")]
                days += [day(n, "done", defects(*found_at[n])) for n in (23, 24)]
                days.append(day(25, "active"))
                earlier = {"event": "escapes", "day": named, "found": [], "at": AT}
                self.case(
                    name,
                    start=drift(TRACK, days, order=order),
                    steps=1,
                    views=ONE,
                    switches=lines_of(earlier),
                )
                self.on()
                found = (self.switches(), self.merges())
                same(self, found, ([without_at(earlier), ON, *expected], 0))

    def test_unreadable_switch_log_at_read(self):
        # The read's own branch: a switch log that turns unreadable during a run ends it, not "cannot start".
        self.state = Path(self.root) / "unreadable_at_read" / "state"
        self.state.mkdir(parents=True)
        (self.state / "switches.jsonl").write_bytes(UNREADABLE)
        args = types.SimpleNamespace(state=str(self.state))
        in_force, line = loop.read_escapes(args, {"level": 2}, after(), 2)
        same(
            self,
            (in_force, self.held(line or "")),
            (2, [f"cannot read the project: {UNREADABLE_LINE}"]),
        )
