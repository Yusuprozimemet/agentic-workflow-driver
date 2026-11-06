"""decide() gives the dry run's one line: the first reason that applies, and a branch of the step that
stops it from starting."""

import dataclasses
import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TRACK_B = "Day 03 Track B: C03.2–C03.3"
SPEC = "Day 03: read the spec against the code, then the spec-change PR"
CLEAN = {
    "dirty": (),
    "branch": "main",
    "main": "a" * 40,
    "origin_main": "a" * 40,
    "branches": (),
    "remote_branches": (),
}


def drift_of(sentence, open_prs=(), order=(1, 2, 3), phases=None):
    phases = {1: 0, 2: 0, 3: 0} if phases is None else phases
    return {
        "now": {
            "next_step": sentence,
            "open_prs": [{"number": n, "title": "t", "url": "u"} for n in open_prs],
        },
        "order": list(order),
        "days": [{"day": n, "phase": p, "status": "planned"} for n, p in phases.items()],
    }


class DecideTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone, and
        # scripts/track-red.py counts a module that does not load as not run, not as red.
        self.decide = importlib.import_module("driver.decide")

    def facts(self, **changes):
        return self.decide.Facts(**{**CLEAN, **changes})

    def test_first_reason_wins(self):
        decide = self.decide.decide
        replace = dataclasses.replace
        # Every reason applies at once; each step below removes one, so the next reason shows.
        facts = self.decide.Facts(
            dirty=("a", "b"),
            branch=None,
            main="a" * 40,
            origin_main=None,
            branches=("day-03/track-b-old",),
        )
        order, phases = [1, 2, 3], {1: 0, 2: 0, 3: 0}

        got = decide(drift_of("Waiting on #12 Day 03 track B: x", [12, 13], order, phases), facts)
        self.assertEqual((got.line, got.kind), ("wait: #12, #13", "wait"))

        got = decide(drift_of("Waiting on #12 Day 03 track B: x", [], order, phases), facts)
        self.assertEqual(
            (got.line, got.kind),
            ("park: the next step waits on no open pull request", "park"),
        )

        got = decide(drift_of(TRACK_B, [], order, phases), facts)
        self.assertEqual(
            (got.line, got.kind),
            ("park: the project's tree is not clean (2 paths)", "park"),
        )

        facts = replace(facts, dirty=())
        got = decide(drift_of(TRACK_B, [], order, phases), facts)
        self.assertEqual(
            (got.line, got.kind),
            ("park: the project is on a detached HEAD, not on main", "park"),
        )

        facts = replace(facts, branch="day-03/track-b-counts")
        got = decide(drift_of(TRACK_B, [], order, phases), facts)
        self.assertEqual(
            (got.line, got.kind),
            ("park: the project is on day-03/track-b-counts, not on main", "park"),
        )

        facts = replace(facts, branch="main")
        got = decide(drift_of(TRACK_B, [], order, phases), facts)
        self.assertEqual((got.line, got.kind), ("park: the project has no origin/main", "park"))

        facts = replace(facts, origin_main="b" * 40)
        got = decide(drift_of(TRACK_B, [], order, phases), facts)
        self.assertEqual((got.line, got.kind), ("park: main is not origin/main", "park"))
        # A local main that is missing is not origin/main either.
        got = decide(drift_of(TRACK_B, [], order, phases), replace(facts, main=None))
        self.assertEqual((got.line, got.kind), ("park: main is not origin/main", "park"))

        facts = replace(facts, main="a" * 40, origin_main="a" * 40)
        got = decide(drift_of("Every day is done.", [], order, phases), facts)
        self.assertEqual((got.line, got.kind), ("park: every day is done", "park"))

        got = decide(drift_of(SPEC, [], [1, 2, 3], {1: 0, 2: 0, 3: 1}), facts)
        self.assertEqual(
            (got.line, got.kind),
            ("park: the end of Phase 0: Day 03 starts Phase 1", "park"),
        )

        got = decide(drift_of(TRACK_B, [], order, phases), facts)
        self.assertEqual(
            (got.line, got.kind),
            ("park: a branch of this step exists: day-03/track-b-old", "park"),
        )

        facts = replace(facts, branches=())
        got = decide(drift_of(TRACK_B, [], order, phases), facts)
        self.assertEqual((got.line, got.kind), ("start: " + TRACK_B, "start"))

    def test_a_branch_of_the_step_parks(self):
        decide = self.decide.decide
        track_cases = [
            ("day-03/track-b-old", "branches"),
            ("day-03/track-b-old", "remote_branches"),
            ("day-03/track-b", "remote_branches"),
            ("day-03/track-bb-x", "remote_branches"),
            ("day-03/track-b1-x", "remote_branches"),
        ]
        for name, where in track_cases:
            with self.subTest(sentence=TRACK_B, name=name, where=where):
                got = decide(drift_of(TRACK_B), self.facts(**{where: (name,)}))
                self.assertEqual(got.kind, "park")
                self.assertEqual(got.line, f"park: a branch of this step exists: {name}")
        for name in ["day-03/spec", "day-03/spec-x"]:
            with self.subTest(sentence=SPEC, name=name):
                got = decide(drift_of(SPEC), self.facts(branches=(name,)))
                self.assertEqual(got.kind, "park")
                self.assertEqual(got.line, f"park: a branch of this step exists: {name}")

    def test_near_miss_branches_start(self):
        decide = self.decide.decide
        names = ["day-13/track-b-x", "day-03/track-a-x", "day-03/spec-x"]
        name_sets = [(name,) for name in names] + [tuple(names)]
        for name_set in name_sets:
            for where in ["branches", "remote_branches"]:
                with self.subTest(names=name_set, where=where):
                    got = decide(drift_of(TRACK_B), self.facts(**{where: name_set}))
                    self.assertEqual((got.line, got.kind), ("start: " + TRACK_B, "start"))


if __name__ == "__main__":
    unittest.main()
