"""The repository's copy of the kit's dashboard script loads, and its next step reads as the kit
words it. The driver reads that sentence (plan.md, "What the driver needs from the kit")."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_spec_drift():
    spec = importlib.util.spec_from_file_location("spec_drift", ROOT / "scripts" / "spec-drift.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KitCopyTest(unittest.TestCase):
    def test_next_step_with_no_days_asks_for_the_first_spec(self):
        step = load_spec_drift().next_step([], [], [], None)
        self.assertEqual(
            step,
            "No day specs yet: fill in plan.md, then write the first day's spec (specs/README.md).",
        )


if __name__ == "__main__":
    unittest.main()
