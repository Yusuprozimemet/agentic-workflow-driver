"""The driver knows every sentence the repository's copy of the kit's next_step() returns (plan.md,
"What the driver needs from the kit"). A sentence the kit adds fails here, until the table in
driver/steps.py takes it."""

import ast
import importlib
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_spec_drift():
    spec = importlib.util.spec_from_file_location("spec_drift", ROOT / "scripts" / "spec-drift.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def day(n, status="planned", **kw):
    fields = {
        "day": n,
        "status": status,
        "phase": 0,
        "prs": [],
        "tracks": [],
        "tracks_merged": [],
        "track_work": {},
        "tracks_unopened": [],
    }
    fields.update(kw)
    return fields


class ContractTest(unittest.TestCase):
    def test_every_sentence_next_step_returns_is_known(self):
        steps = importlib.import_module("driver.steps")
        kit = load_spec_drift()

        source = (ROOT / "scripts" / "spec-drift.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        next_step_def = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "next_step"
        )
        returns = sum(isinstance(n, ast.Return) for n in ast.walk(next_step_def))
        self.assertEqual(
            returns,
            9,
            "the kit's next_step() changed: add its sentences to driver/steps.py's table",
        )

        pr7 = {"number": 7, "title": "Day 02 track A: counts"}
        cases = [
            # (days, open_prs, order, stop, lines, expected kind)
            ([], [pr7], [], None, None, "wait"),
            ([day(1, "done")], [], [1], None, None, "park"),
            ([], [], [], None, None, "park"),
            (
                [day(1, "done")],
                [],
                [1, kit.CLEANUP],
                None,
                {kit.CLEANUP: "Day 2: the cleanup day"},
                "park",
            ),
            ([day(1, "done"), day(2)], [], [1, 2], 1, None, "park"),
            ([day(1, "done")], [], [1, 2], None, None, "park"),
            ([day(3)], [], [3], None, None, "step"),
            (
                [day(3, prs=[{"kind": "spec"}], tracks=["B"], track_work={"B": "C03.2–C03.3"})],
                [],
                [3],
                None,
                None,
                "step",
            ),
            (
                [day(3, prs=[{"kind": "spec"}], tracks_unopened=[{"track": "C", "pr": 9}])],
                [],
                [3],
                None,
                None,
                "park",
            ),
            ([day(3, prs=[{"kind": "spec"}])], [], [3], None, None, "step"),
        ]

        sentences = set()
        for days, open_prs, order, stop, lines, kind in cases:
            sentence = kit.next_step(days, open_prs, order, stop, lines)
            sentences.add(sentence)
            with self.subTest(sentence=sentence):
                step = steps.classify(sentence)
                self.assertEqual(step.kind, kind)
                self.assertNotEqual(step.reason, steps.UNKNOWN)
        self.assertEqual(len(sentences), 10)


if __name__ == "__main__":
    unittest.main()
