"""The trial's record in docs/trial/ holds what the trial did: the run log reads as a trial, and
day-08.md names its parks, refusals, cost, phone times and evidence as status and the log give them.
Each test reads both files itself, so importing this module reads nothing."""

import datetime
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver import runlog, status

TRIAL = ROOT / "docs" / "trial"
HEADINGS = [
    "Set-up",
    "Steps",
    "Parks",
    "Refusals",
    "Cost",
    "The phone",
    "The usage limit",
    "Unverified",
    "Evidence",
]
STAMP = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ"
STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class TrialRecordTest(unittest.TestCase):
    def load(self):
        records, reason = runlog.read(str(TRIAL))
        self.assertIsNone(reason, msg="run log cannot be read")
        self.assertTrue(records, msg="run log is empty")
        return records

    def section(self, name):
        lines = (TRIAL / "day-08.md").read_text(encoding="utf-8").split("\n")
        if f"## {name}" not in lines:
            self.fail(f"heading missing: {name}")
        start = lines.index(f"## {name}") + 1
        end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
        return "\n".join(lines[start:end])

    def seconds_between(self, first, second, seconds):
        try:
            delta = datetime.datetime.strptime(second, STAMP_FORMAT) - datetime.datetime.strptime(
                first, STAMP_FORMAT
            )
        except ValueError:
            self.fail("phone stamp is not a time")
        self.assertEqual(int(delta.total_seconds()), int(seconds), msg="seconds differ")

    def test_sections_in_order(self):
        lines = (TRIAL / "day-08.md").read_text(encoding="utf-8").split("\n")
        headings = [line[3:] for line in lines if line.startswith("## ")]
        self.assertEqual(headings, HEADINGS, msg="section headings differ from the spec")

    def test_run_log_is_a_trial(self):
        records, reason = runlog.read(str(TRIAL))
        self.assertIsNone(reason, msg="run log has a reason")
        self.assertTrue(records, msg="run log is empty")
        for index, record in enumerate(records):
            if record.get("event") != "start":
                continue
            session = record.get("session")
            ended = any(
                later.get("event") == "end" and later.get("session") == session for later in records
            )
            parked = any(
                later.get("event") == "park"
                and later.get("line")
                == f"park: the run log names session `{session}` for this step, with no end"
                for later in records[index + 1 :]
            )
            self.assertTrue(ended or parked, msg="start line with no end and no park naming it")
        steps = self.section("Steps")
        for index, record in enumerate(records):
            if record.get("event") in ("merged", "closed"):
                named = any(
                    earlier.get("event") == "wait" and earlier.get("pr") == record.get("pr")
                    for earlier in records[:index]
                )
                self.assertTrue(named, msg="merged or closed pull request has no earlier wait")
            if record.get("event") == "wait":
                pr = record.get("pr")
                self.assertIsInstance(pr, int, msg="wait line without a pull request number")
                self.assertTrue(
                    re.search(rf"#{pr}\b", steps) is not None,
                    msg="wait pull request missing from Steps",
                )

    def test_every_park_named(self):
        records = self.load()
        parks = [record for record in records if record.get("event") == "park"]
        parks_section = self.section("Parks")
        previous = -1
        for park in parks:
            at = park.get("at")
            self.assertIsInstance(at, str, msg="park line without a time")
            self.assertTrue(at in parks_section, msg="park time missing from Parks")
            self.assertTrue(park.get("line") in parks_section, msg="park line missing from Parks")
            position = parks_section.find(at)
            self.assertTrue(position > previous, msg="parks out of log order")
            previous = position
        items = [line for line in parks_section.split("\n") if line.startswith("- 20")]
        self.assertEqual(len(items), len(parks), msg="Parks item count differs from park lines")

    def test_every_refusal_named(self):
        records = self.load()
        refused = status._refused(records)
        self.assertTrue(refused, msg="log holds no refused tool")
        lines = self.section("Refusals").split("\n")
        for line in refused:
            self.assertTrue(line in lines, msg="refused tool line missing from Refusals")
        self.assertTrue(
            f"refusals: {status._refusals(records)}" in lines, msg="refusals line missing"
        )

    def test_cost_line_is_status(self):
        records = self.load()
        cost = self.section("Cost")
        cost_lines = cost.split("\n")
        self.assertTrue(status._cost(records) in cost_lines, msg="cost line missing from Cost")
        self.assertEqual(
            status._level_2(records),
            "level 2: 0 of 15 pull requests in a row merged without a change asked",
        )
        steps = self.section("Steps").split("\n")
        for line in status._steps(records):
            self.assertTrue(line in steps, msg="steps line missing from Steps")
        self.assertTrue(
            re.search(
                r"^cost per merged pull request: \$\d+\.\d\d \(baseline \$1\.86\)$",
                cost,
                re.MULTILINE,
            )
            is not None,
            msg="cost per merged pull request line missing",
        )
        self.assertTrue(
            re.search(
                r"^replies per merged pull request: \d+\.\d \(baseline 34\.4\)$", cost, re.MULTILINE
            )
            is not None,
            msg="replies per merged pull request line missing",
        )

    def test_evidence_section(self):
        records = self.load()
        evidence = self.section("Evidence")
        closing = re.search(r"^closing PR: #(\d+)$", evidence, re.MULTILINE)
        self.assertTrue(closing is not None, msg="closing PR line missing")
        self.assertTrue(
            re.search(r"^merge commit: [0-9a-f]{40}$", evidence, re.MULTILINE) is not None,
            msg="merge commit line missing",
        )
        self.assertTrue(
            re.search(r"^evidence run: \d+$", evidence, re.MULTILINE) is not None,
            msg="evidence run line missing",
        )
        self.assertTrue(
            re.search(r"^conclusion: success$", evidence, re.MULTILINE) is not None,
            msg="conclusion line missing",
        )
        number = int(closing.group(1))
        self.assertTrue(
            any(
                record.get("event") == "merged" and record.get("pr") == number for record in records
            ),
            msg="no merged line for the closing PR",
        )

    def test_phone_lines(self):
        records = self.load()
        phone = self.section("The phone")
        stop = re.search(
            rf"^STOP: opened ({STAMP}), halted ({STAMP}), (\d+) s$", phone, re.MULTILINE
        )
        self.assertTrue(stop is not None, msg="STOP line missing from The phone")
        self.seconds_between(stop.group(1), stop.group(2), stop.group(3))
        closed = re.search(
            rf"^park closed: ({STAMP}), started again ({STAMP}), (\d+) s$", phone, re.MULTILINE
        )
        self.assertTrue(closed is not None, msg="park closed line missing from The phone")
        self.seconds_between(closed.group(1), closed.group(2), closed.group(3))
        starts = [record.get("at") for record in records if record.get("event") == "start"]
        self.assertTrue(closed.group(2) in starts, msg="started again time is no start line")
