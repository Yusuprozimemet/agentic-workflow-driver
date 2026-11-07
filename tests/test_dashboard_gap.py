"""The dashboard's gap against chance, and the names split by class: the helpers in
scripts/spec-drift.py that the name-gap chart and its caption read."""

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_spec_drift():
    spec = importlib.util.spec_from_file_location("spec_drift", ROOT / "scripts" / "spec-drift.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


spec_drift = load_spec_drift()


class NameClassTest(unittest.TestCase):
    def test_test_shapes_are_test_names(self):
        self.assertEqual(spec_drift.name_class("test_once_parks", set()), "test")
        self.assertEqual(spec_drift.name_class("HaltTest", {"prod"}), "test")
        self.assertEqual(spec_drift.name_class("TestCase", set()), "test")

    def test_helper_only_in_tests_is_a_test_name(self):
        self.assertEqual(spec_drift.name_class("fake_gh", {"test"}), "test")
        self.assertEqual(spec_drift.name_class("fake_gh", {"test", "prod"}), "prod")
        self.assertEqual(spec_drift.name_class("next_step", set()), "prod")


class FlagTest(unittest.TestCase):
    def test_flags_from_backtick_spans(self):
        texts = {
            "specs/day-01-x.md": "Run `python run-steps.py --once --dry-run` then --poll outside ticks, "
            "and `--max-budget-usd 5`; not `a--b` or `---`."
        }
        self.assertEqual(spec_drift.spec_flags(texts), {"--once", "--dry-run", "--max-budget-usd"})


class ChanceTest(unittest.TestCase):
    def test_percentile_in(self):
        self.assertEqual(spec_drift.percentile_in(np.array([1.0, 2.0, 3.0, 4.0]), 3.0), 62.5)
        self.assertEqual(spec_drift.percentile_in(np.array([1.0, 2.0]), 0.5), 0.0)
        self.assertIsNone(spec_drift.percentile_in(np.array([]), 1.0))
        self.assertIsNone(spec_drift.percentile_in(np.array([1.0]), None))

    def test_chance_angle_unchanged(self):
        x = np.log1p(np.array([3, 0, 1, 5, 2.0]))
        y = np.log1p(np.array([1, 4, 0, 2, 2.0]))
        keep = np.array([True] * 5)
        chance = spec_drift.chance_angle(x, y, keep)
        self.assertEqual(chance, spec_drift.band(spec_drift.chance_draws(x, y, keep)))
        self.assertEqual(len(chance), 3)
        one = np.array([True, False, False, False, False])
        self.assertEqual(spec_drift.chance_angle(x, y, one), [round(spec_drift.angle(x, y), 2)] * 3)


if __name__ == "__main__":
    unittest.main()
