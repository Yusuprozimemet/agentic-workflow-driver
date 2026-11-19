"""The leftover "How this works" picker is gone (Day 14, C14.16): #259 removed the views and kept
the picker that fed them. The test runs the criterion's `git grep` with `-l` from the repository's
root and asserts it found nothing: exit code 1 (0 would be a match, 128 no repository) and no
file listed. The names are spelled in parts, so the grep does not find this file."""

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PAGE_NAMES = ["how" + part for part in ("Recheck", "Has", "Missing", "Excerpt")]


def grep_files(names, paths):
    command = ["git", "grep", "-l", "-w"]
    for name in names:
        command += ["-e", name]
    command += ["--", *paths]
    done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    return done.returncode, done.stdout.splitlines()


class PickerGoneTest(unittest.TestCase):
    def test_page_half_gone(self):
        code, files = grep_files(PAGE_NAMES, ["docs/dashboard", "scripts", "tests"])
        self.assertEqual(files, [])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
