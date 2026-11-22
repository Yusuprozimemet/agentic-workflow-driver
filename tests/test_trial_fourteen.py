"""The trial's Day 14 record, docs/trial/day-14.md, and the copies beside it: run-14.jsonl (the run
log), switches-14.jsonl, refusals-14.jsonl and install-14.jsonl. The record names every merge, park,
refusal and cost the copies hold, and answers the hand-offs from them. The test reads the record and
the copies only, never the state folder: the copies go into a temporary state folder for runlog and
status, so importing this module reads nothing."""

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver import runlog, status

TRIAL = ROOT / "docs" / "trial"
SECTIONS = [
    "Set-up",
    "The count run",
    "The level 2 day",
    "Merges",
    "Parks",
    "Refusals",
    "The reviewer",
    "Cost",
    "The usage limit",
    "The install",
    "The first merge",
    "Unverified",
    "Evidence",
]
HEX40 = r"[0-9a-f]{40}"
COMMENT = r"comment https://github.com/Yusuprozimemet/bearing/pull/{pr}#issuecomment-\d+"
STAMP = r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ"


def _at(record):
    # The copies' times are all UTC stamps, so a string comparison orders them; a line without one
    # sorts before every stamp.
    value = record.get("at")
    return value if isinstance(value, str) else ""


class TrialFourteenTest(unittest.TestCase):
    longMessage = False

    def _text(self, name):
        path = TRIAL / name
        if not path.exists():
            self.fail(f"docs/trial/{name} does not exist")
        return path.read_bytes().decode("utf-8")

    def _jsonl(self, name):
        return [json.loads(line) for line in self._text(name).splitlines() if line.strip()]

    def _records(self):
        # The run log copy is read first, so that its absence is the first failure of a test.
        run = self._text("run-14.jsonl")
        switches = self._text("switches-14.jsonl")
        refusals = self._text("refusals-14.jsonl")
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        state = folder.name
        os.makedirs(os.path.join(state, "refusals"))
        copies = {
            os.path.join(state, "run.jsonl"): run,
            os.path.join(state, "switches.jsonl"): switches,
            os.path.join(state, "refusals", "hooks.jsonl"): refusals,
        }
        for path, text in copies.items():
            with open(path, "wb") as f:
                f.write(text.encode("utf-8"))
        records, reason = runlog.read(state)
        self.assertIsNone(reason, msg="the run log copy cannot be read")
        self.assertIsInstance(records, list, msg="the run log copy cannot be read")
        return state, records

    def _section(self, text, title):
        lines = [line.rstrip("\r") for line in text.split("\n")]
        heading = "## " + title
        if heading not in lines:
            self.fail(f"section missing: {title}")
        start = lines.index(heading) + 1
        end = next(
            (i for i in range(start, len(lines)) if lines[i].startswith("## ")),
            len(lines),
        )
        return lines[start:end]

    def _label(self, lines, name):
        prefix = "- " + name + ": "
        found = [line[len(prefix) :] for line in lines if line.startswith(prefix)]
        if not found:
            self.fail(f"line missing: {name}")
        if len(found) > 1:
            self.fail(f"line twice: {name}")
        return found[0]

    def _level_2_from(self):
        ons = [
            record.get("at")
            for record in self._jsonl("switches-14.jsonl")
            if record.get("event") == "on"
        ]
        self.assertTrue(ons, msg="switches-14.jsonl has no on line")
        return ons[-1]

    def test_run_log_is_a_level_2_trial(self):
        folder, records = self._records()
        switches = self._jsonl("switches-14.jsonl")
        ended = {r.get("session") for r in records if r.get("event") == "end"}
        halted = {r.get("session") for r in switches if r.get("event") == "halt"}
        for index, record in enumerate(records):
            if record.get("event") != "start":
                continue
            session = record.get("session")
            parked = any(
                later.get("event") == "park"
                and f"the run log names session `{session}` for this step, with no end"
                in str(later.get("line"))
                for later in records[index + 1 :]
            )
            self.assertTrue(
                session in ended or parked or session in halted,
                msg="a start line has no end",
            )

        for index, record in enumerate(records):
            if record.get("event") not in ("merged", "closed"):
                continue
            waited = any(
                r.get("event") == "wait" and r.get("pr") == record.get("pr")
                for r in records[:index]
            )
            self.assertTrue(waited, msg="a merged or closed line has no earlier wait")

        driver = [
            index
            for index, record in enumerate(records)
            if record.get("event") == "merged" and record.get("by") == "driver"
        ]
        self.assertTrue(driver, msg="no merged line is by the driver")
        for index in driver:
            pr = records[index].get("pr")
            reviewed = any(
                r.get("event") == "review" and r.get("pr") == pr and r.get("blockers") == 0
                for r in records[:index]
            )
            self.assertTrue(reviewed, msg="a driver merge has no review with blockers 0")

        self.assertEqual(
            runlog.late_refusals(folder, records),
            [],
            msg="a hook refusal is not counted by its end line",
        )

    def test_every_driver_merge_named(self):
        text = self._text("day-14.md")
        _, records = self._records()
        level_2 = self._level_2_from()
        merges = self._section(text, "Merges")
        by_hand = self._section(text, "The level 2 day")

        for record in records:
            if record.get("event") == "merged" and record.get("by") == "driver":
                pr = record.get("pr")
                line = f"- #{pr} at {record.get('at')}, head {record.get('head')}"
                self.assertIn(line, merges, msg=f"Merges does not name #{pr}")

        expected = {
            f"- merged by hand: #{record.get('pr')}"
            for record in records
            if record.get("event") == "merged"
            and record.get("by") is None
            and _at(record) >= level_2
        }
        named = {line for line in by_hand if line.startswith("- merged by hand: #")}
        self.assertEqual(
            named,
            expected,
            msg="The level 2 day does not name the merges made by hand",
        )

    def test_every_park_named(self):
        text = self._text("day-14.md")
        _, records = self._records()
        parks = self._section(text, "Parks")

        for record in records:
            if record.get("event") == "park":
                at = record.get("at")
                line = f"{at} {record.get('line')}"
                self.assertIn(line, parks, msg=f"Parks does not name the park at {at}")

        for line in status._parks(records):
            self.assertIn(line, parks, msg="Parks lacks a parks by reason line")

    def test_every_refusal_named(self):
        text = self._text("day-14.md")
        _, records = self._records()
        refusals = self._section(text, "Refusals")

        for record in records:
            if record.get("event") != "end":
                continue
            for item in record.get("refused") or []:
                line = f"{record.get('session')}: {item.get('tool')}: {item.get('input')}"
                self.assertIn(line, refusals, msg="Refusals does not name a refused tool")

        for line in self._text("refusals-14.jsonl").splitlines():
            if line.strip():
                self.assertIn(line, refusals, msg="Refusals does not name a hook refusal")

        dates = {_at(record)[:10] for record in records if _at(record)}
        rows = []
        for line in refusals:
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if (
                isinstance(value, dict)
                and {"date", "guard", "refused"} <= set(value)
                and value["date"] in dates
            ):
                rows.append(value)
        self.assertTrue(rows, msg="Refusals holds no refusals.json row for the trial's dates")

    def test_sections_in_order(self):
        text = self._text("day-14.md")
        headings = [
            line[len("## ") :].rstrip("\r") for line in text.split("\n") if line.startswith("## ")
        ]
        self.assertEqual(headings, SECTIONS, msg="the sections are not in the order In scope gives")

    def test_cost_lines_are_status(self):
        text = self._text("day-14.md")
        _, records = self._records()
        level_2 = self._level_2_from()
        cost_section = self._section(text, "Cost")

        cost = status._cost(records)
        reviewer = status._reviewer(records)
        self.assertIn(cost, cost_section, msg="Cost lacks status's cost line")
        index = cost_section.index(cost)
        self.assertEqual(
            cost_section[index + 1 : index + 2],
            [reviewer],
            msg="Cost lacks the reviewer line after the cost line",
        )

        before = [record for record in records if _at(record) < level_2]
        after = [record for record in records if _at(record) >= level_2]
        for name, part in (("count run alone", before), ("level 2 alone", after)):
            worked = status._cost(part)
            self.assertTrue(worked.startswith("cost: "), msg="status's cost line has no cost: ")
            self.assertIn(
                f"{name}: " + worked[len("cost: ") :],
                cost_section,
                msg=f"Cost lacks the {name} line",
            )

    def test_cost_beside_level_1_and_baseline(self):
        text = self._text("day-14.md")
        cost_section = self._section(text, "Cost")

        between = [
            line for line in cost_section if line.startswith("from ") and ", before " in line
        ]
        after = [line for line in cost_section if line.startswith("after ")]
        if not between:
            self.fail("Cost lacks the between side")
        if not after:
            self.fail("Cost lacks the after side")

        for side, line in (("between", between[0]), ("after", after[0])):
            cost = re.search(r"\$([0-9.]+) at the list prices", line)
            pulls = re.search(r"(\d+) pull requests merged on main", line)
            replies = re.search(r"([0-9.]+) replies per merged pull request", line)
            if cost is None or pulls is None or replies is None:
                self.fail(f"Cost lacks the figures of the {side} side")
            per_pull = f"{float(cost.group(1)) / int(pulls.group(1)):.2f}"
            expected = (
                f"- {side}: ${cost.group(1)} / {pulls.group(1)} = ${per_pull} per merged "
                f"pull request (baseline $1.86); {replies.group(1)} replies per merged pull "
                f"request (baseline 34.4)"
            )
            self.assertIn(expected, cost_section, msg=f"Cost does not work the {side} side")

    def test_set_up(self):
        text = self._text("day-14.md")
        lines = self._section(text, "Set-up")

        self.assertEqual(
            self._label(lines, "project"), "bearing", msg="Set-up does not name the project"
        )
        self.assertEqual(self._label(lines, "budget_usd"), "10", msg="budget_usd is not 10")
        self.assertEqual(self._label(lines, "steps_per_night"), "6", msg="steps_per_night is not 6")
        paths = re.findall(r"`([^`]+)`", self._label(lines, "human_only"))
        self.assertEqual(len(paths), 10, msg="human_only does not hold ten paths")
        self.assertEqual(len(set(paths)), 10, msg="human_only holds a path twice")
        self.assertEqual(
            self._label(lines, "level of the count run"), "1", msg="the count run is not level 1"
        )
        self.assertTrue(
            self._label(lines, "level of the level 2 day").startswith("2"),
            msg="the level 2 day is not level 2",
        )
        self.assertIn(
            "`agentic-workflow-driver-session:",
            self._label(lines, "image"),
            msg="Set-up does not name the image",
        )
        for name in (
            "driver's main",
            "bearing's copy of the kit's scripts/spec-drift.py",
            "bearing at the level 2 day",
        ):
            self.assertTrue(
                re.fullmatch(HEX40, self._label(lines, name)),
                msg=f"{name} is not 40 hex characters",
            )
        stamp = self._label(lines, "level 2 from")
        self.assertEqual(stamp, self._level_2_from(), msg="level 2 from is not the last on line")
        self.assertTrue(re.fullmatch(STAMP, stamp), msg="level 2 from is not a UTC stamp")

    def test_evidence_section(self):
        text = self._text("day-14.md")
        _, records = self._records()
        lines = self._section(text, "Evidence")

        closing = self._label(lines, "closing PR")
        match = re.fullmatch(r"#(\d+)", closing)
        self.assertTrue(match, msg="closing PR is not a pull request number")
        number = int(match.group(1))
        self.assertTrue(
            any(r.get("event") == "merged" and r.get("pr") == number for r in records),
            msg="the closing PR has no merged line",
        )
        self.assertTrue(
            re.fullmatch(HEX40, self._label(lines, "merge commit")),
            msg="merge commit is not 40 hex characters",
        )
        self.assertTrue(
            re.fullmatch(r"\d+", self._label(lines, "evidence run")),
            msg="evidence run is not a run id",
        )
        self.assertEqual(
            self._label(lines, "conclusion"), "success", msg="the evidence run did not succeed"
        )

    def test_escapes_counted(self):
        text = self._text("day-14.md")
        lines = self._section(text, "Evidence")

        count = self._label(lines, "escapes")
        self.assertTrue(re.fullmatch(r"\d+", count), msg="escapes is not a count")
        index = lines.index("- escapes: " + count)
        quoted = []
        for line in lines[index + 1 :]:
            if not line.startswith("  - "):
                break
            quoted.append(line)
        self.assertEqual(
            int(count), len(quoted), msg="escapes does not count the lines quoted under it"
        )

    def test_usage_limit_follows_the_copy(self):
        text = self._text("day-14.md")
        met = any("usage limit" in line for line in self._text("run-14.jsonl").splitlines())
        lines = self._section(text, "The usage limit")
        self.assertEqual(
            self._label(lines, "usage limit"),
            "met" if met else "not met",
            msg="The usage limit does not follow run-14.jsonl",
        )

    def test_install_before_tests(self):
        text = self._text("day-14.md")
        install = [line for line in self._text("install-14.jsonl").splitlines() if line.strip()]
        self.assertEqual(len(install), 3, msg="install-14.jsonl does not hold three lines")
        first, second, third = (json.loads(line) for line in install)

        session_id = "76bd4a7f-98fc-4049-800f-4c791d2adc90"
        self.assertEqual(
            first.get("session"), session_id, msg="install-14.jsonl names another session"
        )
        _, records = self._records()
        level_2 = self._level_2_from()
        self.assertTrue(
            any(
                record.get("event") == "start"
                and record.get("session") == session_id
                and _at(record) >= level_2
                and record.get("prefix") != "review"
                for record in records
            ),
            msg="the install's session is not a level 2 step",
        )

        self.assertTrue(
            isinstance(second.get("command"), str) and isinstance(third.get("command"), str),
            msg="an install line holds no command",
        )
        self.assertEqual(second, third, msg="the install and the tests are not one tool_use")
        install_match = re.search(
            r"""pip install (?:-q )?-e ['"]?\.\[dev\]['"]?""", second["command"]
        )
        test_match = re.search(r"\bpytest\b", third["command"])
        self.assertTrue(install_match, msg="the install line does not install as CI does")
        self.assertTrue(test_match, msg="the tests line does not run pytest")
        self.assertLess(
            install_match.start(),
            test_match.start(),
            msg="the install does not come before the tests",
        )

        lines = self._section(text, "The install")
        self.assertIn(second["command"], lines, msg="The install does not quote the command")

    def test_every_review_named(self):
        text = self._text("day-14.md")
        _, records = self._records()
        lines = self._section(text, "The reviewer")

        for record in records:
            if record.get("event") != "review":
                continue
            pr = record.get("pr")
            prefix = f"- #{pr}, head {record.get('head')}, blockers {record.get('blockers')}, "
            rests = [line[len(prefix) :] for line in lines if line.startswith(prefix)]
            named = any(
                re.fullmatch(COMMENT.format(pr=pr), rest)
                or (rest.startswith("no comment: ") and rest[len("no comment: ") :].strip())
                for rest in rests
            )
            self.assertTrue(named, msg=f"The reviewer does not name the review of #{pr}")

    def test_first_merge(self):
        text = self._text("day-14.md")
        _, records = self._records()
        driver = [
            record
            for record in records
            if record.get("event") == "merged" and record.get("by") == "driver"
        ]
        self.assertTrue(driver, msg="no merged line is by the driver")
        first = driver[0]
        lines = self._section(text, "The first merge")

        self.assertIn(
            f"- first merge: #{first.get('pr')}, head {first.get('head')}",
            lines,
            msg="The first merge does not name the first driver merge",
        )
        command = next(
            (
                index
                for index, line in enumerate(lines)
                if line.startswith("$ gh pr merge ") and "--match-head-commit " in line
            ),
            None,
        )
        self.assertIsNotNone(command, msg="The first merge quotes no gh pr merge command")
        exit_line = next(
            (
                index
                for index in range(command + 1, len(lines))
                if re.fullmatch(r"exit \d+", lines[index])
            ),
            None,
        )
        self.assertIsNotNone(exit_line, msg="The first merge has no exit line after the command")
        output = lines[command + 1 : exit_line]
        self.assertTrue(output, msg="gh's output after the command is empty")
        self.assertFalse(
            any(not line.strip() or line.startswith("```") for line in output),
            msg="gh's output holds an empty line or a fence",
        )
