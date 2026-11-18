"""Day 13's level 2 merge in `on` (driver/loop.py, wait_merge): C13.17 first, at level 1 nothing merges,
however much else holds. Track E1 adds C13.8 to C13.11 here."""

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
from tests.test_level_2_blocker import container_merges
from tests.test_merge_wait import view
from tests.test_review_loop import HEAD, NIGHT, R, ReviewCase, rewrite, same


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
