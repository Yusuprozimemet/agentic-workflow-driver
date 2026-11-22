"""Day 13's level 2 start in `on` (driver/loop.py, steps): C13.7. At level 2 a run starts only when review is
on, the sessions run in the container, the run log counts 15 pull requests merged in a row without a change,
and main requires a pull request and its checks with no bypass. Each one that does not hold refuses the start
with one line, before any session starts or any issue is created."""

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

from tests import test_box_preflight as preflight
from tests import test_box_session as box_session
from tests.test_level_2_blocker import container_merges
from tests.test_merge_gh import KIT
from tests.test_merge_wait import view
from tests.test_review_loop import HEAD, R, ReviewCase, rewrite, same, without_at

CLASSIC = "repos/{owner}/{repo}/branches/main/protection"
RULES = "repos/{owner}/{repo}/rules/branches/main"
LINE_REVIEW = 'cannot start: level 2 needs "review": true in <path>'
LINE_CONTAINER = (
    "cannot start: level 2 needs the sessions in the container: <path> has no container_image"
)
LINE_COUNT = (
    "cannot start: level 2 needs 15 of 15 pull requests in a row merged without a change asked; "
    "status counts 14"
)
LINE_PROTECTION = (
    "cannot start: level 2 needs main to require a pull request and its checks with no bypass: "
    "main allows a bypass"
)
LINE_KIT_CHECKS = (
    "cannot start: level 2 needs main to require a pull request and its checks with no bypass: "
    "main does not require " + ", ".join(f'"{name}"' for name in KIT)
)


def protected(admins, names=(*KIT, "tests")):
    # Classic protection that requires the pull request and the checks named in names: the kit's nine
    # and the project's tests by default. Admins bypass it when admins is false.
    return {
        "code": 0,
        "out": {
            "required_pull_request_reviews": {"required_approving_review_count": 0},
            "required_status_checks": {
                "contexts": list(names),
                "checks": [{"context": name, "app_id": 1} for name in names],
            },
            "enforce_admins": {"enabled": admins},
        },
    }


NO_RULES = {"code": 0, "out": []}
WAIVED = ["A track's breaks replay", "A closed day's evidence replays"]


class LevelStartTest(ReviewCase, unittest.TestCase):
    # BoxSessionTest's container helpers and BoxPreflightTest's in-process runner, by assignment.
    box = box_session.BoxSessionTest.box
    hidden = box_session.BoxSessionTest.hidden
    plain = box_session.BoxSessionTest.plain
    named = box_session.BoxSessionTest.named
    names = box_session.BoxSessionTest.names
    run_steps = preflight.BoxPreflightTest.run_steps

    def holds(self):
        # main's protection holds, so that a break of the case's own condition reaches a session's start.
        rewrite(self.folder / "gh" / "fake.json", api={CLASSIC: protected(True), RULES: NO_RULES})

    def seed(self, k):
        # The run log of k container merges, written as bytes: one JSON line each, as test_level_2_merge.py.
        seeded = container_merges(101, k)
        (self.state / "run.jsonl").write_bytes(
            b"".join(json.dumps(record).encode("utf-8") + b"\n" for record in seeded)
        )

    def starts(self):
        # The start records of the run log: a session begins with one.
        return [record for record in self.run_log() if record.get("event") == "start"]

    def held(self, err):
        # The stderr lines with the config's path held as <path>, in each spelling it may take.
        path = self.folder / "driver.json"
        lines = []
        for line in err.splitlines():
            for form in sorted({str(path), os.path.realpath(path)}, key=len, reverse=True):
                line = line.replace(form, "<path>")
            lines.append(line)
        return lines

    def refused(self):
        # One run of `on`: its exit code, its stderr lines with the config held as <path>, the start records
        # it added, and its issue creations and api calls.
        before = len(self.starts())
        code, _, err = self.run_steps("on")
        lines = self.held(err)
        calls = self.gh_of()
        return (
            code,
            lines,
            len(self.starts()) - before,
            [call for call in calls if call[:2] == ["issue", "create"]],
            [call for call in calls if call[:1] == ["api"]],
        )

    def test_needs_review(self):
        # C13.7: level 2 needs "review": true. With it absent the start refuses with the one line, and no
        # session starts. The key is taken out after reviewed() has set it, so the rest of the case holds.
        self.box("needs_review", run=[])
        self.reviewed()
        path = self.folder / "driver.json"
        spec = json.loads(path.read_bytes())
        spec.pop("review")
        path.write_bytes(json.dumps(spec).encode("utf-8"))
        rewrite(path, level=2)
        self.holds()
        self.seed(15)
        same(self, self.refused(), (2, [LINE_REVIEW], 0, [], []))

    def test_needs_container(self):
        # C13.7: level 2 needs the sessions in the container. Without the container keys the start refuses
        # with the one line; the secrets path is set so that hidden() can name it.
        self.build("needs_container", steps=1)
        self.secrets = self.folder / "secrets.env"
        self.reviewed()
        rewrite(self.folder / "driver.json", level=2)
        self.holds()
        self.seed(15)
        same(self, self.refused(), (2, [LINE_CONTAINER], 0, [], []))

    def test_needs_the_count(self):
        # C13.7: the run log must count 15 merges in a row without a change; 14 refuses with the count shown.
        self.box("needs_count", run=[])
        self.reviewed()
        rewrite(self.folder / "driver.json", level=2)
        self.holds()
        self.seed(14)
        same(self, self.refused(), (2, [LINE_COUNT], 0, [], []))

    def test_no_run_log_counts_0(self):
        # C13.7's In scope: a run log that is missing counts 0, so the start refuses with the count line.
        self.box("no_run_log", run=[])
        self.reviewed()
        rewrite(self.folder / "driver.json", level=2)
        self.holds()
        same(self, self.refused(), (2, [LINE_COUNT.replace("counts 14", "counts 0")], 0, [], []))

    def test_needs_protection(self):
        # C13.7: main must require a pull request and its checks with no bypass. Admins may bypass the classic
        # protection here, so the check reads two api calls and refuses with the reason.
        self.box("needs_protection", run=[])
        self.reviewed()
        rewrite(self.folder / "driver.json", level=2)
        rewrite(
            self.folder / "gh" / "fake.json",
            api={CLASSIC: protected(False), RULES: NO_RULES},
        )
        self.seed(15)
        same(
            self,
            self.refused(),
            (2, [LINE_PROTECTION], 0, [], [["api", CLASSIC], ["api", RULES]]),
        )

    def test_starts_when_all_hold(self):
        # C13.7: with all four conditions true the start goes on: a session starts, and the protection reads
        # come before the first issue is created. Only the api calls before that issue are compared: once the
        # session runs, its heartbeat makes api PATCH calls of its own.
        reviewer_answer = json.dumps(
            {"type": "result", "is_error": False, "result": "REVIEW: none", "session_id": R}
        )
        self.box(
            "all_hold",
            run=[
                {
                    "tail": ["--session-id", box_session.U],
                    "stdout": box_session.result(box_session.U),
                },
                {"tail": ["--session-id", R], "stdout": reviewer_answer},
            ],
            steps=1,
        )
        # Three views, as test_level_1_never_merges reads them: the wait must not reach MERGED too early.
        self.reviewed(
            views=[view("OPEN", head=HEAD), view("OPEN", head=HEAD), view("MERGED", head=HEAD)]
        )
        rewrite(self.folder / "driver.json", level=2)
        rewrite(
            self.folder / "gh" / "fake.json",
            api={CLASSIC: protected(True), RULES: NO_RULES},
        )
        self.seed(15)
        before = len(self.starts())

        def uuids():
            # The step's uuid first, then the reviewer's for every later call.
            yield uuid.UUID(box_session.U)
            while True:
                yield uuid.UUID(R)

        with mock.patch("uuid.uuid4", side_effect=uuids().__next__):
            self.run_steps("on")
        calls = self.gh_of()
        first = next(
            (n for n, call in enumerate(calls) if call[:2] == ["issue", "create"]), len(calls)
        )
        found = (
            [call for call in calls[:first] if call[0] == "api"],
            len(self.starts()) - before > 0,
        )
        same(self, found, ([["api", CLASSIC], ["api", RULES]], True))

    def test_needs_the_kits_checks(self):
        # C15.7: main must require the kit's nine checks by name, as well as the project's tests. Protection
        # that names only the tests refuses with the one line, before any session starts or issue is created.
        reviewer_answer = json.dumps(
            {"type": "result", "is_error": False, "result": "REVIEW: none", "session_id": R}
        )
        self.box(
            "needs_kit_checks",
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
        rewrite(self.folder / "driver.json", level=2)
        rewrite(
            self.folder / "gh" / "fake.json",
            api={CLASSIC: protected(True, names=("tests",)), RULES: NO_RULES},
        )
        self.seed(15)
        before = len(self.starts())

        def uuids():
            # The step's uuid first, then the reviewer's for every later call.
            yield uuid.UUID(box_session.U)
            while True:
                yield uuid.UUID(R)

        with mock.patch("uuid.uuid4", side_effect=uuids().__next__):
            code, _, err = self.run_steps("on")
        calls = self.gh_of()
        first = next(
            (n for n, call in enumerate(calls) if call[:2] == ["issue", "create"]), len(calls)
        )
        found = (
            code,
            self.held(err),
            len(self.starts()) - before,
            [call for call in calls if call[:2] == ["issue", "create"]],
            [call for call in calls[:first] if call[0] == "api"],
        )
        same(
            self,
            found,
            (2, [LINE_KIT_CHECKS], 0, [], [["api", CLASSIC], ["api", RULES]]),
        )

    def first_switch(self):
        # The switch log's first line, its "at" left out; None when `on` wrote none.
        path = self.state / "switches.jsonl"
        if not path.exists():
            return None
        first = path.read_bytes().decode("utf-8").splitlines()[0]
        return without_at(json.loads(first))

    def test_waived_printed_and_logged(self):
        # C15.8: a waived check is named before the session, in the config's order, and the switch log's `on`
        # line names the waived checks. The protection the fake gh answers lacks them, and the start goes on.
        reviewer_answer = json.dumps(
            {"type": "result", "is_error": False, "result": "REVIEW: none", "session_id": R}
        )
        self.box(
            "waived_printed",
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
        rewrite(self.folder / "driver.json", level=2, waived_checks=WAIVED)
        rewrite(
            self.folder / "gh" / "fake.json",
            api={
                CLASSIC: protected(
                    True, names=[name for name in KIT if name not in WAIVED] + ["tests"]
                ),
                RULES: NO_RULES,
            },
        )
        self.seed(15)

        def uuids():
            # The step's uuid first, then the reviewer's for every later call.
            yield uuid.UUID(box_session.U)
            while True:
                yield uuid.UUID(R)

        with mock.patch("uuid.uuid4", side_effect=uuids().__next__):
            code, out, err = self.run_steps("on")
        found = (code, self.held(err), out.splitlines()[:3], self.first_switch())
        same(
            self,
            found,
            (
                0,
                [],
                [
                    'level 2: waived check "A track\'s breaks replay"',
                    'level 2: waived check "A closed day\'s evidence replays"',
                    "opened: #12 from `day-01/track-a-x`",
                ],
                {"event": "on", "waived_checks": WAIVED},
            ),
        )

    def test_level_1_ignores_waived(self):
        # C15.9: at level 1 the protection is not read, and no waived line is printed or logged, whatever the
        # config waives.
        reviewer_answer = json.dumps(
            {"type": "result", "is_error": False, "result": "REVIEW: none", "session_id": R}
        )
        self.box(
            "level_1_waived",
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
        rewrite(self.folder / "driver.json", waived_checks=["A track's breaks replay"])
        rewrite(
            self.folder / "gh" / "fake.json",
            api={CLASSIC: protected(True), RULES: NO_RULES},
        )
        self.seed(15)

        def uuids():
            # The step's uuid first, then the reviewer's for every later call.
            yield uuid.UUID(box_session.U)
            while True:
                yield uuid.UUID(R)

        with mock.patch("uuid.uuid4", side_effect=uuids().__next__):
            _, out, _ = self.run_steps("on")
        found = (
            [call for call in self.gh_of() if call[:1] == ["api"] and "--method" not in call],
            [line for line in out.splitlines() if line.startswith("level 2: waived")],
            self.first_switch(),
        )
        same(self, found, ([], [], {"event": "on"}))

    def test_none_waived(self):
        # C15.17: an empty list waives nothing: no waived line is printed, and the switch log's `on` line is the
        # one it was before the key existed.
        reviewer_answer = json.dumps(
            {"type": "result", "is_error": False, "result": "REVIEW: none", "session_id": R}
        )
        self.box(
            "none_waived",
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
        rewrite(self.folder / "driver.json", level=2, waived_checks=[])
        rewrite(
            self.folder / "gh" / "fake.json",
            api={CLASSIC: protected(True), RULES: NO_RULES},
        )
        self.seed(15)

        def uuids():
            # The step's uuid first, then the reviewer's for every later call.
            yield uuid.UUID(box_session.U)
            while True:
                yield uuid.UUID(R)

        with mock.patch("uuid.uuid4", side_effect=uuids().__next__):
            code, out, _ = self.run_steps("on")
        same(
            self,
            (code, [line for line in out.splitlines() if line.startswith("level 2: waived")]),
            (0, []),
        )
        same(self, self.first_switch(), {"event": "on"})
