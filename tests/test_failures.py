"""decide() goes on past a phase's end the maintainer answered, and runlog.failures() lists the
sessions of a prefix that ended as a park, or refuses a log it cannot read."""

import importlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SPEC = "Day 03: read the spec against the code, then the spec-change PR"
ANSWER = "park: the end of Phase 0: Day 03 starts Phase 1"
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


class AnsweredTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone, and
        # scripts/track-red.py counts a module that does not load as not run, not as red.
        self.decide = importlib.import_module("driver.decide")

    def facts(self, **changes):
        return self.decide.Facts(**{**CLEAN, **changes})

    def test_answered_phase_end_starts(self):
        decide = self.decide.decide
        drift = drift_of(SPEC, [], [1, 2, 3], {1: 0, 2: 0, 3: 1})
        got = decide(drift, self.facts(), frozenset({ANSWER}))
        self.assertEqual((got.line, got.kind), ("start: " + SPEC, "start"))
        with self.subTest("without an answer, Day 1's park holds"):
            got = decide(drift, self.facts())
            self.assertEqual((got.line, got.kind), (ANSWER, "park"))

    def test_answered_still_checks_branches(self):
        decide = self.decide.decide
        drift = drift_of(SPEC, [], [1, 2, 3], {1: 0, 2: 0, 3: 1})
        facts = self.facts(remote_branches=("day-03/spec-x",))
        got = decide(drift, facts, frozenset({ANSWER}))
        self.assertEqual(
            (got.line, got.kind),
            ("park: a branch of this step exists: day-03/spec-x", "park"),
        )

    def test_other_answer(self):
        decide = self.decide.decide
        drift = drift_of(SPEC, [], [1, 2, 3], {1: 0, 2: 0, 3: 1})
        answered = frozenset({"park: the end of Phase 1: Day 03 starts Phase 2"})
        got = decide(drift, self.facts(), answered)
        self.assertEqual((got.line, got.kind), (ANSWER, "park"))


class FailuresTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone, and
        # scripts/track-red.py counts a module that does not load as not run, not as red.
        self.runlog = importlib.import_module("driver.runlog")
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state)

    def test_failures(self):
        runlog = self.runlog
        step = "Day 05 Track B: C05.4"
        prefix = "day-05/track-b"
        s1, s2, s3, s4, o1 = "s1", "s2", "s3", "s4", "o1"
        runlog.start(self.state, step, prefix, s1, "2.1.312")
        runlog.end(self.state, s1, "opened: #5 Day 05 track B: x", 0.5, 0)
        runlog.start(self.state, step, prefix, s2, "2.1.312")
        runlog.end(self.state, s2, "park: no pull request and no PARK line", 0.5, 0)
        runlog.start(self.state, "Day 05 Track A1", "day-05/track-a1", o1, "2.1.312")
        runlog.end(self.state, o1, "park: x", 0.5, 0)
        runlog.start(self.state, step, prefix, s3, "2.1.312")
        runlog.end(self.state, s3, "park: the step's checks failed", 0.5, 0)
        runlog.start(self.state, step, prefix, s4, "2.1.312")
        self.assertEqual(runlog.failures(self.state, prefix), ([s2, s3], None))

    def test_no_log(self):
        self.assertEqual(self.runlog.failures(self.state, "day-05/track-b"), ([], None))

    def test_torn_log(self):
        runlog = self.runlog
        runlog.start(self.state, "Day 05 Track B", "day-05/track-b", "s1", "2.1.312")
        with open(runlog.path(self.state), "ab") as f:
            f.write(b'{"event": "end"')
        self.assertEqual(
            runlog.failures(self.state, "day-05/track-b"),
            (None, "the run log cannot be read at line 2"),
        )


if __name__ == "__main__":
    unittest.main()
