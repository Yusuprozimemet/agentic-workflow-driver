"""classify() reads each sentence of the table in specs/day-01-dry-run.md as its kind, and phase_end()
reads a phase's end from the run order and each day's phase."""

import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def days_of(phases):
    return [{"day": n, "phase": p, "status": "done"} for n, p in phases.items()]


class ClassifyTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone, and
        # scripts/track-red.py counts a module that does not load as not run, not as red.
        self.steps = importlib.import_module("driver.steps")

    def test_each_sentence_of_the_table(self):
        Step = self.steps.Step
        no_spec = "Day 05 has no spec: writing it is the maintainer's"
        cases = [
            ("Waiting on #7 Day 02 track A: counts", Step("wait")),
            ("Every day is done.", Step("park", reason="every day is done")),
            (
                "No day specs yet: fill in plan.md, then write the first day's spec (specs/README.md).",
                Step("park", reason="there are no day specs"),
            ),
            (
                "Day 05: write its day spec (plan.md lists it, specs/ has none)",
                Step("park", day=5, reason=no_spec),
            ),
            (
                'Day 05: write its day spec (plan.md: "Day 5: the cleanup day")',
                Step("park", day=5, reason=no_spec),
            ),
            (
                "Day 04 is done: stop and evaluate before going on (plan.md)",
                Step("park", day=4, reason="a stopping point after Day 04"),
            ),
            (
                "Day 03: read the spec against the code, then the spec-change PR",
                Step("step", day=3, prefix="day-03/spec"),
            ),
            (
                "Day 03 Track B: C03.2–C03.3",
                Step("step", day=3, track="B", prefix="day-03/track-b"),
            ),
            ("Day 03 Track B: ", Step("step", day=3, track="B", prefix="day-03/track-b")),
            (
                "Day 03 Track A1: w",
                Step("step", day=3, track="A1", prefix="day-03/track-a1"),
            ),
            (
                "Day 03 Track 0: x",
                Step("step", day=3, track="0", prefix="day-03/track-0"),
            ),
            (
                "Day 03 Track C: announced in #9, no branch names it",
                Step(
                    "park",
                    day=3,
                    track="C",
                    reason="Track C of Day 03 was announced in #9 and has no branch",
                ),
            ),
            (
                "Day 03: the closing PR",
                Step("step", day=3, prefix="day-03/close-the-day"),
            ),
        ]
        for sentence, want in cases:
            with self.subTest(sentence=sentence):
                self.assertEqual(self.steps.classify(sentence), want)

    def test_near_misses_are_unknown(self):
        for sentence in [
            "Day 3: the closing PR",
            "day 03: the closing PR",
            "Day 03: the closing PR today",
            "Re: Day 03: the closing PR",
            "Day 03 Track : x",
            "",
        ]:
            with self.subTest(sentence=sentence):
                self.assertEqual(
                    self.steps.classify(sentence),
                    self.steps.Step("park", reason=self.steps.UNKNOWN),
                )


class PhaseEndTest(unittest.TestCase):
    def setUp(self):
        self.steps = importlib.import_module("driver.steps")

    def spec_step(self, n):
        return self.steps.classify(
            f"Day {n:02d}: read the spec against the code, then the spec-change PR"
        )

    def test_first_step_of_a_new_phase_parks(self):
        self.assertEqual(
            self.steps.phase_end(self.spec_step(3), [1, 2, 3], days_of({1: 0, 2: 0, 3: 1})),
            "the end of Phase 0: Day 03 starts Phase 1",
        )
        order = [1, 3, 2]
        phases = {1: 0, 2: 1, 3: 1}
        self.assertEqual(
            self.steps.phase_end(self.spec_step(3), order, days_of(phases)),
            "the end of Phase 0: Day 03 starts Phase 1",
        )
        self.assertIsNone(self.steps.phase_end(self.spec_step(2), order, days_of(phases)))

    def test_same_phase_first_day_and_later_steps_do_not(self):
        self.assertIsNone(
            self.steps.phase_end(self.spec_step(3), [1, 2, 3], days_of({1: 0, 2: 1, 3: 1}))
        )
        self.assertIsNone(
            self.steps.phase_end(self.spec_step(1), [1, 2, 3], days_of({1: 0, 2: 1, 3: 1}))
        )
        phases = days_of({1: 0, 2: 0, 3: 1})
        for sentence in ["Day 03 Track B: x", "Day 03: the closing PR"]:
            with self.subTest(sentence=sentence):
                step = self.steps.classify(sentence)
                self.assertIsNone(self.steps.phase_end(step, [1, 2, 3], phases))

    def test_missing_phase_parks(self):
        no_phase = "Day 03 or the day before it names no phase"
        # Day 3 has no phase.
        self.assertEqual(
            self.steps.phase_end(self.spec_step(3), [1, 2, 3], days_of({1: 0, 2: 0, 3: None})),
            no_phase,
        )
        # Day 2 has no phase key at all.
        days = [
            {"day": 1, "phase": 0, "status": "done"},
            {"day": 2, "status": "done"},
            {"day": 3, "phase": 1, "status": "planned"},
        ]
        self.assertEqual(self.steps.phase_end(self.spec_step(3), [1, 2, 3], days), no_phase)
        # Phase 0 is a phase, not a missing one.
        self.assertIsNone(
            self.steps.phase_end(self.spec_step(3), [1, 2, 3], days_of({1: 0, 2: 0, 3: 0}))
        )


if __name__ == "__main__":
    unittest.main()
