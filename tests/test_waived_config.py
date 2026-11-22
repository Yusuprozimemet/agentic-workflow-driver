"""Day 15's `waived_checks` in `driver.json` (`driver/config.py`, `problems`): C15.6. The key is a list of the
kit's check names, each once; anything else is one line, and an absent key or a list of them gives none."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver import config
from tests.test_merge_gh import KIT
from tests.test_review_loop import same

PATH = "driver.json"
BASE = {"project": ".", "human_only": [], "budget_usd": 1, "steps_per_night": 1}
LINE = (
    "cannot start: driver.json's waived_checks must be a list of the kit's check names, each once"
)


class WaivedConfigTest(unittest.TestCase):
    def test_not_a_list(self):
        found = (
            config.problems(PATH, {**BASE, "waived_checks": "A track's breaks replay"}),
            config.problems(PATH, BASE),
        )
        same(self, found, ([LINE], []))

    def test_unknown_name(self):
        found = (
            config.problems(PATH, {**BASE, "waived_checks": ["nope"]}),
            config.problems(PATH, {**BASE, "waived_checks": []}),
        )
        same(self, found, ([LINE], []))

    def test_twice(self):
        found = (
            config.problems(
                PATH, {**BASE, "waived_checks": ["Track tests seen red", "Track tests seen red"]}
            ),
            config.problems(PATH, {**BASE, "waived_checks": list(KIT)}),
        )
        same(self, found, ([LINE], []))


if __name__ == "__main__":
    unittest.main()
