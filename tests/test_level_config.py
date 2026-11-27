"""Day 13, C13.1, and Day 16, C16.1: driver.config.problems gives no line for a config without `level`
or with 1, 2 or 3, and one line for 0, 4, "2", "3", true, 2.0 and 3.0. This checks the config's check
only; the level in force is driver/switchlog.py's."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver.config import problems
from tests.test_review_loop import same

BASE = {"project": "p", "human_only": [], "budget_usd": 5, "steps_per_night": 1}
BAD = "cannot start: driver.json's level must be 1, 2 or 3"


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
            "3": [],
            "'2'": [BAD],
            "True": [BAD],
            "2.0": [BAD],
        }
        same(self, found, expected)

    def test_level_three(self):
        # C16.1: 3 is a level from Day 16; 3.0 equals 3 and True equals 1, so they are refused by type.
        found = {"absent": problems("driver.json", dict(BASE))}
        for value in [1, 2, 3, 0, 4, 3.0, True, "3"]:
            found[repr(value)] = problems("driver.json", dict(BASE, level=value))
        expected = {
            "absent": [],
            "1": [],
            "2": [],
            "3": [],
            "0": [BAD],
            "4": [BAD],
            "3.0": [BAD],
            "True": [BAD],
            "'3'": [BAD],
        }
        same(self, found, expected)
