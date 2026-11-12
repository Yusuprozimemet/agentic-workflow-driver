"""The trial's Day 10 record in docs/trial/day-10.md names the container run: its run log holds one
start, pid and end line for one session, run in the driver-<session> container, which opened a pull
request whose head commit is by the image's git user and not by the PC's. The test reads the file
itself, so importing this module reads nothing."""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RECORD = ROOT / "docs" / "trial" / "day-10.md"
EVENTS = ["start", "pid", "end"]
OUTCOME = r"opened: #(\d+) from `([^`]+)`"


class TrialTenTest(unittest.TestCase):
    def label(self, text, name):
        match = re.search(rf"^- \*\*{re.escape(name)}:\*\* (.*)$", text, re.MULTILINE)
        if match is None:
            self.fail(f"line missing: {name}")
        return match.group(1).strip()

    def unquote(self, value):
        if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
            return value[1:-1]
        return value

    def test_record_names_the_container_run(self):
        if not RECORD.exists():
            self.fail("docs/trial/day-10.md does not exist")
        text = RECORD.read_text(encoding="utf-8")

        records = []
        for line in text.split("\n"):
            if not line.startswith('{"event": '):
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                self.fail("run log line is not JSON")
        self.assertEqual(
            [record.get("event") for record in records],
            EVENTS,
            msg="run log lines are not start, pid, end",
        )
        start, pid, end = records

        session = start.get("session")
        self.assertEqual(pid.get("session"), session, msg="sessions differ")
        self.assertEqual(end.get("session"), session, msg="sessions differ")

        container = "driver-" + str(session)
        self.assertEqual(start.get("container"), container, msg="container is not driver-<session>")
        self.assertEqual(pid.get("container"), container, msg="container is not driver-<session>")

        outcome = end.get("outcome")
        match = re.fullmatch(OUTCOME, outcome if isinstance(outcome, str) else "")
        self.assertIsNotNone(match, msg="outcome is not opened")
        number = match.group(1)

        cost = end.get("cost_usd")
        self.assertTrue(
            isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost > 0,
            msg="no cost_usd",
        )

        self.assertEqual(
            self.label(text, "Pull request"),
            f"https://github.com/Yusuprozimemet/bearing/pull/{number}",
            msg="pull request differs from the end line",
        )

        author = self.unquote(self.label(text, "Head commit's author"))
        git_name = self.unquote(self.label(text, "The image's `GIT_NAME`"))
        pc_name = self.unquote(self.label(text, "The PC's `git config user.name`"))
        self.assertEqual(author, git_name, msg="author is not the image's GIT_NAME")
        self.assertNotEqual(author, pc_name, msg="author is the PC's user")
        self.assertTrue(author and git_name and pc_name, msg="a name is empty")

        self.assertEqual(
            self.label(text, "`git status --short` in `../bearing` after"),
            "empty",
            msg="project checkout not clean",
        )
