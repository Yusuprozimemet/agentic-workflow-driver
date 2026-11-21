"""The rules the driver gives its sessions (rules/session.md): C13.14, the install line that sits before
the project's tests, and C14.19, the after-PR line that lets the driver wait for the merge itself."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# rules/session.md at commit 5d4f1b5, held here as text: CI clones at depth 1, so git cannot show it there.
AT_5D4F1B5 = """# Rules for a session the driver started

- This session was started by the driver, and nobody watches it while it runs.
- When the step needs the maintainer, open no pull request, and end the last reply with one line: `PARK: <the reason, in one sentence>`.
- You never merge a pull request, and you never push to `main`.
- A lesson for CLAUDE.md goes in the day's Notes as a `Hand-off` line to the maintainer; do not edit CLAUDE.md.
"""

INSTALL = "- Before running the project's tests, install the project as its CI does (its workflows in `.github/workflows/`)."

AFTER_PR = "- After you open the step's pull request, end the last reply without a `PARK:` line, even where the project's CLAUDE.md says to stop and wait for \"merged\": the driver waits for the merge itself."


class SessionRulesTest(unittest.TestCase):
    def test_after_pr_line(self):
        # C13.14 and C14.19: the session rules tell the session to install the project as its CI does,
        # before the tests run, and not to end on PARK once its pull request is open: the install line
        # goes right after the one that forbids merging, the after-PR line right after the PARK line,
        # and nothing else changes.
        found_lines = (ROOT / "rules" / "session.md").read_bytes().decode("utf-8").splitlines()
        held = AT_5D4F1B5.splitlines()
        anchors = [i for i, line in enumerate(held) if line.startswith("- You never merge")]
        self.assertEqual(len(anchors), 1)
        expected_lines = held[: anchors[0] + 1] + [INSTALL] + held[anchors[0] + 1 :]
        parks = [i for i, line in enumerate(expected_lines) if "PARK: <" in line]
        self.assertEqual(len(parks), 1)
        expected_lines = (
            expected_lines[: parks[0] + 1] + [AFTER_PR] + expected_lines[parks[0] + 1 :]
        )
        # The line count and the places that differ, not the two lists: unittest shortens a list's repr
        # in its failure ("[N chars]"), and a break's report must replay the same on every machine.
        differing = [
            i for i, (found, want) in enumerate(zip(found_lines, expected_lines)) if found != want
        ]
        self.assertEqual((len(found_lines), differing), (len(expected_lines), []))


if __name__ == "__main__":
    unittest.main()
