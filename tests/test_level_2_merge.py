"""Day 13's level 2 merge in `on` (driver/loop.py, wait_merge): C13.17 first, at level 1 nothing merges,
however much else holds. C13.8 to C13.13 are here too."""

import contextlib
import io
import json
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver import status
from tests import test_box_preflight as preflight
from tests import test_box_session as box_session
from tests import test_merge_wait as merge_wait
from tests.test_dry_run import commit_file, git
from tests.test_level_2_blocker import container_merges
from tests.test_level_2_start import CLASSIC, NO_RULES, RULES, protected
from tests.test_merge_wait import view
from tests.test_review_loop import HEAD, NIGHT, R, ReviewCase, rewrite, same
from tests.test_tree import MERGE, recorded

# The pull request's merge as the driver asks it: the head named, so gh refuses a moved pull request.
PR_MERGE = ["pr", "merge", "12", "--merge", "--match-head-commit", HEAD]
# A head that is not the review's: the pull request moved after the review.
MOVED = "b" * 40


def seeded_run(k):
    # The run log for k merges in a row, then a clean review of #12 on HEAD: the count and the review
    # that level 2 reads before it asks the merge.
    review = {"event": "review", "pr": 12, "session": R, "head": HEAD, "blockers": 0}
    return container_merges(101, k) + [review]


class LevelMergeTest(ReviewCase, unittest.TestCase):
    # BoxSessionTest's container helpers and BoxPreflightTest's in-process runner, by assignment.
    box = box_session.BoxSessionTest.box
    hidden = box_session.BoxSessionTest.hidden
    plain = box_session.BoxSessionTest.plain
    named = box_session.BoxSessionTest.named
    names = box_session.BoxSessionTest.names
    run_steps = preflight.BoxPreflightTest.run_steps

    def test_level_1_never_merges(self):
        # C13.17: with level 1, review on, the container keys, a run log counting 15 and a clean review
        # line on the views' head, the run records no merge and waits for the views' MERGED. Only level 2
        # may merge; a break that merges at level 1 gives a pr merge line and fails here.
        reviewer_answer = json.dumps(
            {"type": "result", "is_error": False, "result": "REVIEW: none", "session_id": R}
        )
        self.box(
            "level_1",
            run=[
                {
                    "tail": ["--session-id", box_session.U],
                    "stdout": box_session.result(box_session.U),
                },
                {"tail": ["--session-id", R], "stdout": reviewer_answer},
            ],
            steps=1,
        )
        # Three views, not reviewed()'s two: the review's poll takes the first OPEN, so the wait must read
        # OPEN once more before MERGED, where a merge asked at OPEN would be reached and the test would fail.
        self.reviewed(
            views=[view("OPEN", head=HEAD), view("OPEN", head=HEAD), view("MERGED", head=HEAD)]
        )
        rewrite(self.folder / "driver.json", level=1)
        seeded = container_merges(101, 15)
        (self.state / "run.jsonl").write_bytes(
            b"".join(json.dumps(record).encode("utf-8") + b"\n" for record in seeded)
        )

        def uuids():
            # The step's uuid first, then the reviewer's for every later call.
            yield uuid.UUID(box_session.U)
            while True:
                yield uuid.UUID(R)

        with mock.patch("uuid.uuid4", side_effect=uuids().__next__):
            code, out, _ = self.run_steps("on")
        log = self.run_log()
        found = (
            status.level_2_run(seeded),
            code,
            out.splitlines()[-1:],
            self.gh_of("pr", "merge"),
            [call[2] for call in self.gh_of("pr", "view") if len(call) > 2],
            [
                (r.get("pr"), r.get("blockers"), r.get("head") == HEAD)
                for r in log
                if r.get("event") == "review"
            ],
            ["by" in r for r in log if r.get("event") == "merged" and r.get("pr") == 12],
        )
        same(
            self,
            found,
            (15, 0, [NIGHT], [], ["12", "12", "12"], [(12, 0, True)], [False]),
        )

    def test_on_merges(self):
        # C13.8: the same run as test_level_1_never_merges at level 2, main protected with no bypass: the
        # driver asks the merge once, with the reviewed head, and the run ends on the night's count.
        reviewer_answer = json.dumps(
            {"type": "result", "is_error": False, "result": "REVIEW: none", "session_id": R}
        )
        self.box(
            "level_2",
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
        rewrite(self.folder / "gh" / "fake.json", api={CLASSIC: protected(True), RULES: NO_RULES})
        seeded = container_merges(101, 15)
        (self.state / "run.jsonl").write_bytes(
            b"".join(json.dumps(record).encode("utf-8") + b"\n" for record in seeded)
        )

        def uuids():
            # The step's uuid first, then the reviewer's for every later call.
            yield uuid.UUID(box_session.U)
            while True:
                yield uuid.UUID(R)

        with mock.patch("uuid.uuid4", side_effect=uuids().__next__):
            code, out, _ = self.run_steps("on")
        log = self.run_log()
        found = (
            status.level_2_run(seeded),
            code,
            out.splitlines()[-1:],
            [call == PR_MERGE for call in self.gh_of("pr", "merge")],
            [
                (r.get("pr"), r.get("blockers"), r.get("head") == HEAD)
                for r in log
                if r.get("event") == "review"
            ],
            [r.get("by") for r in log if r.get("event") == "merged" and r.get("pr") == 12],
        )
        same(self, found, (15, 0, [NIGHT], [True], [(12, 0, True)], ["driver"]))

    def log_of(self, case):
        # The run log of a direct call: one JSON record per line, read as bytes.
        path = case.root / "state" / "run.jsonl"
        return [json.loads(line) for line in path.read_bytes().splitlines()]

    def direct(self, views, seeded, human_only=(), home_change=None, merge_code=0):
        # MergeWaitTest's project, fake gh and git recorder; the run log seeded; a clean driver folder as home,
        # its HEAD as started. home_change(home) runs after started is read; merge_code is the code the fake
        # gh exits on pr merge. Returns (line, code, keys, out, case, home, started).
        case = merge_wait.MergeWaitTest("test_closed_parks")
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.build(views)
        if merge_code != 0:
            rewrite(case.root / "gh" / "fake.json", merge_code=merge_code)
        (case.root / "state" / "run.jsonl").write_bytes(
            b"".join(json.dumps(r).encode("utf-8") + b"\n" for r in seeded)
        )
        home = case.root / "home"
        home.mkdir()
        git(home, "init", "-b", "main")
        git(home, "config", "core.autocrlf", "false")
        commit_file(home, "a.txt")
        started = git(home, "rev-parse", "HEAD").stdout.strip()
        if home_change:
            home_change(home)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            line, code, keys = case.loop.wait_merge(
                case.args,
                case.project,
                12,
                case.record,
                list(human_only),
                case.read_facts,
                case.git,
                level2=(str(home), started),
            )
        return line, code, keys, buffer.getvalue(), case, home, started

    def test_merges_the_reviewed_head(self):
        # C13.8: with 15 merges in a row and a clean review on the views' head, the merge is asked once,
        # after the first pr view and before the second, with that head; the merged line says by driver.
        views = [view("OPEN", head=HEAD), view("OPEN", head=HEAD), view("MERGED", head=HEAD)]
        seeded = seeded_run(15)
        line, code, keys, _, case, _, _ = self.direct(views, seeded)
        calls = case.gh_of()
        view_at = [i for i, call in enumerate(calls) if call[:2] == ["pr", "view"]]
        merge_at = [i for i, call in enumerate(calls) if call == PR_MERGE]
        found = (
            status.level_2_run(seeded),
            (line, code, keys),
            [call == PR_MERGE for call in case.gh_of("pr", "merge")],
            len(view_at) >= 2 and len(merge_at) == 1 and view_at[0] < merge_at[0] < view_at[1],
            [
                r.get("by")
                for r in self.log_of(case)
                if r.get("event") == "merged" and r.get("pr") == 12
            ],
            recorded(case.root) == MERGE,
            len(case.gh_of("run", "list")) >= 1,
        )
        same(self, found, (15, (None, 0, {}), [True], True, ["driver"], True, True))

    def test_path_check_first(self):
        # C13.9: the path check comes before the merge, with 15 merges in a row and a clean review: each
        # gated pull request parks with today's line, its pr and head, and no merge is asked.
        cases = [
            (view("OPEN", paths=["plan.md"], head=HEAD), (), "park: #12 touches plan.md"),
            (
                view("OPEN", paths=["docs/kit.md"], head=HEAD),
                ("docs/",),
                "park: #12 touches a human-only path: `docs/kit.md`",
            ),
            (
                view("OPEN", body="Oversized: 500 lines", head=HEAD),
                (),
                "park: #12 carries Oversized:",
            ),
        ]
        for index, (gated, human_only, want) in enumerate(cases):
            with self.subTest(index=index):
                line, code, keys, _, case, _, _ = self.direct(
                    [gated, view("CLOSED", head=HEAD)], seeded_run(15), human_only
                )
                found = (
                    (line, code),
                    keys == {"pr": 12, "head": HEAD},
                    case.gh_of("pr", "merge"),
                )
                same(self, found, ((want, 1), True, []))

    def test_count_fallen_waits(self):
        # C13.10: with 14 merges in a row the wait goes on as at level 1: one level line, no merge asked,
        # and no by on the merged line once the views say MERGED.
        seeded = seeded_run(14)
        views = [view("OPEN", head=HEAD), view("MERGED", head=HEAD)]
        line, code, keys, out, case, _, _ = self.direct(views, seeded)
        log = self.log_of(case)
        want = "level 2: #12 waits for the maintainer: 14 of 15 in a row"
        found = (
            status.level_2_run(seeded),
            (line, code, keys),
            [row for row in out.splitlines() if "level 2:" in row],
            [(r.get("pr"), r.get("line")) for r in log if r.get("event") == "level"],
            case.gh_of("pr", "merge"),
            ["by" in r for r in log if r.get("event") == "merged" and r.get("pr") == 12],
        )
        same(self, found, (14, (None, 0, {}), [want], [(12, want)], [], [False]))

    def test_driver_changed_no_merge(self):
        # C13.11: a file left in the driver's folder halts before the merge is asked.
        views = [view("OPEN", head=HEAD), view("MERGED", head=HEAD)]
        line, code, _, _, case, _, _ = self.direct(
            views,
            seeded_run(15),
            home_change=lambda home: (home / "x.txt").write_bytes(b"x\n"),
        )
        found = ((line, code), case.gh_of("pr", "merge"))
        want = ("halt: the driver's repository has changes: `x.txt`; #12 not merged", 1)
        same(self, found, (want, []))

    def test_driver_moved_no_merge(self):
        # C13.11: a HEAD that moved from the one the step started on halts before the merge is asked; the
        # two short heads are put back as <head>, so the report replays on every machine.
        views = [view("OPEN", head=HEAD), view("MERGED", head=HEAD)]
        line, code, _, _, case, home, started = self.direct(
            views,
            seeded_run(15),
            home_change=lambda home: commit_file(home, "b.txt"),
        )
        moved = git(home, "rev-parse", "HEAD").stdout.strip()
        line = line and line.replace(started[:7], "<head>").replace(moved[:7], "<head>")
        found = ((line, code), case.gh_of("pr", "merge"))
        want = ("halt: the driver's repository moved from `<head>` to `<head>`; #12 not merged", 1)
        same(self, found, (want, []))

    def test_head_moved_parks(self):
        # C13.12: the head the pull request has now is not the reviewed one: the wait parks with pr and head
        # kept, and no merge is asked, with 15 merges in a row and a clean review on HEAD.
        views = [view("OPEN", head=MOVED), view("MERGED", head=MOVED)]
        line, code, keys, _, case, _, _ = self.direct(views, seeded_run(15))
        found = ((line, code), keys == {"pr": 12, "head": MOVED}, case.gh_of("pr", "merge"))
        same(self, found, (("park: #12 moved after the review", 1), True, []))

    def test_no_clean_review_parks(self):
        # C13.12: with no review line for #12, or one with a blocker, there is no clean review of the head: the
        # wait parks as a moved head, and no merge is asked, with 15 merges in a row.
        blocked = {"event": "review", "pr": 12, "session": R, "head": HEAD, "blockers": 1}
        seeds = [container_merges(101, 15), container_merges(101, 15) + [blocked]]
        views = [view("OPEN", head=HEAD), view("MERGED", head=HEAD)]
        for index, seeded in enumerate(seeds):
            with self.subTest(index=index):
                line, code, keys, _, case, _, _ = self.direct(views, seeded)
                found = ((line, code), keys == {"pr": 12, "head": HEAD}, case.gh_of("pr", "merge"))
                same(self, found, (("park: #12 moved after the review", 1), True, []))

    def test_merge_fails_parks(self):
        # C13.13: gh pr merge exits 1 and the pull request reads CLOSED: the wait parks with the exit named,
        # the merge asked once, and no merged line written.
        views = [view("OPEN", head=HEAD), view("OPEN", head=HEAD), view("CLOSED", head=HEAD)]
        line, code, keys, _, case, _, _ = self.direct(views, seeded_run(15), merge_code=1)
        found = (
            (line, code, keys),
            [call == PR_MERGE for call in case.gh_of("pr", "merge")],
            [r for r in self.log_of(case) if r.get("event") == "merged" and r.get("pr") == 12],
        )
        want = (("park: the merge of #12 failed: gh pr merge exited 1", 1, {}), [True], [])
        same(self, found, want)

    def test_merge_fails_but_merged(self):
        # C13.13: gh pr merge exits 1, but the pull request then reads MERGED: the wait goes on to the merged
        # line, which has no by, since the merge was not the driver's.
        views = [view("OPEN", head=HEAD), view("MERGED", head=HEAD)]
        line, code, keys, _, case, _, _ = self.direct(views, seeded_run(15), merge_code=1)
        found = (
            (line, code, keys),
            [call == PR_MERGE for call in case.gh_of("pr", "merge")],
            [
                "by" in r
                for r in self.log_of(case)
                if r.get("event") == "merged" and r.get("pr") == 12
            ],
        )
        same(self, found, ((None, 0, {}), [True], [False]))
