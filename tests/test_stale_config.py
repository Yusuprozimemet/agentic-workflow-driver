"""The optional stale_minutes in driver.json (Day 11, Track E2): a number above 0, and absent, which means 10.
config.load() is called on a driver.json written into a temporary folder, and the lines it returns are compared
with the path replaced by <path>, so a failure message holds no absolute path."""

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def good(project):
    return {"project": str(project), "human_only": [], "budget_usd": 5, "steps_per_night": 3}


class StaleConfigTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top, so a missing module fails each test alone.
        self.config = importlib.import_module("driver.config")

    def folder(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        return Path(os.path.realpath(tmp.name))

    def load(self, tmp, **keys):
        # Written as bytes: on Windows, text mode would add a carriage return to the file.
        path = tmp / "driver.json"
        path.write_bytes(json.dumps({**good(tmp), **keys}).encode("utf-8"))
        config, lines = self.config.load(path)
        return config, [line.replace(str(path), "<path>") for line in lines]

    def test_stale_minutes(self):
        tmp = self.folder()
        message = "cannot start: <path>'s stale_minutes must be a number above 0"
        for number, value in enumerate(["10", 0, -1, True]):
            with self.subTest(case=number):
                config, lines = self.load(tmp, stale_minutes=value)
                self.assertEqual((config is None, lines), (True, [message]))
        config, lines = self.load(tmp, stale_minutes=0.5)
        self.assertEqual((config is not None, lines), (True, []))
        self.assertEqual(config.get("stale_minutes"), 0.5)
        config, lines = self.load(tmp)
        self.assertEqual((config is not None, lines), (True, []))
        self.assertEqual(config.get("stale_minutes", 10), 10)


if __name__ == "__main__":
    unittest.main()
