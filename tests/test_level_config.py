"""Day 13, C13.1: driver.config.problems gives no line for a config without `level` or with 1 or 2, and
one line for 3, "2", true and 2.0. Nothing reads `level` yet; this checks the config's check only."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver.config import problems
from tests.test_review_loop import same

BASE = {"project": "p", "human_only": [], "budget_usd": 5, "steps_per_night": 1}
BAD = "cannot start: driver.json's level must be 1 or 2"


class LevelConfigTest(unittest.TestCase):
    def test_level_values(self):
        # Keyed by repr(value), so a failure names the value that differs; True and 2.0 equal 1 and 2 in
        # Python, which is why the check tests the type first.
        found = {"absent": problems("driver.json", dict(BASE))}
        for value in [1, 2, 3, "2", True, 2.0]:
            found[repr(value)] = problems("driver.json", dict(BASE, level=value))
        expected = {
            "absent": [],
            "1": [],
            "2": [],
            "3": [BAD],
            "'2'": [BAD],
            "True": [BAD],
            "2.0": [BAD],
        }
        same(self, found, expected)
