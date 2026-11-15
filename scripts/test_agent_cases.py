"""scripts/agent-cases.py runs an agent on cases whose answer is known and counts what it got.

No test starts a model: the runner is a small Python file that prints a reply. The last class
builds a scratch repository, since a case is a spec at a commit.

    python scripts/test_agent_cases.py
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("agent_cases", os.path.join(HERE, "agent-cases.py"))
agent_cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_cases)

NOTES = """## Notes
- **Defect** — found: auditor · cause: spec · made: Day 44 · C44.2 counted 9 files; there are 11.
- **Defect** — found: review · cause: implementation · made: Day 44 · a dead branch.
- **Defect** — found: the close · cause: process · made: Day 43 · a box ticked without evidence.
"""
RIGHT = [
    {"id": "D44-1", "stage": "before_code", "cause": "spec", "made": "this"},
    {"id": "D44-2", "stage": "before_merge", "cause": "implementation", "made": "this"},
    {"id": "D44-3", "stage": "escape", "cause": "process", "made": "earlier"},
]
ONE_CAUSE_OFF = [RIGHT[0], dict(RIGHT[1], cause="spec"), RIGHT[2]]


def key():
    d = tempfile.mkdtemp()
    path = os.path.join(d, "day-44-example.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(NOTES)
    return agent_cases.relabel.entries(path)


class LabelsTest(unittest.TestCase):
    def test_the_array_is_read_from_a_fenced_reply(self):
        reply = "Here are the labels:\n```json\n" + json.dumps(RIGHT) + "\n```\n"
        self.assertEqual(RIGHT, agent_cases.labels(reply))

    def test_a_reply_with_no_array_is_none(self):
        self.assertIsNone(agent_cases.labels("I could not read the file."))
        self.assertIsNone(agent_cases.labels("[1, 2]"))


class ReportTest(unittest.TestCase):
    def test_the_worst_run_is_the_count_and_each_run_is_shown(self):
        lines, worst = agent_cases.report(
            key(), [json.dumps(RIGHT), json.dumps(ONE_CAUSE_OFF)], None
        )
        self.assertEqual(
            [
                "stage: 3 of 3 agree at worst (3, 3)",
                "cause: 2 of 3 agree at worst (3, 2)",
                "made: 3 of 3 agree at worst (3, 3)",
            ],
            lines,
        )
        self.assertEqual({"stage": 3, "cause": 2, "made": 3, "runs": 2}, worst)

    def test_a_fall_below_the_recorded_count_is_named(self):
        recorded = {"stage": 3, "cause": 3, "made": 3, "runs": 3, "brief": "abc1234"}
        lines, _ = agent_cases.report(key(), [json.dumps(ONE_CAUSE_OFF)], recorded)
        self.assertEqual(
            [
                "recorded: stage 3, cause 3, made 3 (brief abc1234, 3 runs)",
                "lower than recorded: cause 2 < 3",
            ],
            lines[-2:],
        )
        lines, _ = agent_cases.report(key(), [json.dumps(RIGHT)], recorded)
        self.assertEqual("not lower than recorded", lines[-1])

    def test_a_run_with_no_array_or_a_missing_entry_is_not_counted(self):
        lines, worst = agent_cases.report(
            key(), ["no", json.dumps(RIGHT[:2]), json.dumps(RIGHT)], None
        )
        self.assertEqual(
            [
                "run 1: not counted (no JSON array in the reply)",
                "run 2: not counted (no label for D44-3)",
            ],
            lines[:2],
        )
        self.assertEqual(1, worst["runs"])
        self.assertEqual(
            (["run 1: not counted (no JSON array in the reply)", "no run counted"], None),
            agent_cases.report(key(), ["no"], None),
        )


class RunTest(unittest.TestCase):
    """A scratch repository: the spec committed, then its Notes edited in the working tree."""

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        for path, text in [
            ("specs/day-44-example.md", NOTES),
            (".claude/agents/rater.md", "brief\n"),
            (
                "reply.py",
                "import sys\nsys.stdin.read()\nprint(open(sys.argv[1], encoding='utf-8').read())\n",
            ),
        ]:
            os.makedirs(os.path.dirname(os.path.join(self.repo, path)), exist_ok=True)
            with open(os.path.join(self.repo, path), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        git = [
            "git",
            "-C",
            self.repo,
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "-c",
            "core.autocrlf=false",
        ]
        subprocess.run(git + ["init", "-q"], check=True)
        subprocess.run(git + ["add", "."], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "a spec"], check=True)
        at = (
            subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, check=True)
            .stdout.decode()
            .strip()
        )
        with open(os.path.join(self.repo, "specs/day-44-example.md"), "w", encoding="utf-8") as f:
            f.write("## Notes\n")
        self.cases = os.path.join(self.repo, "specs", "agent-cases", "rater.json")
        os.makedirs(os.path.dirname(self.cases))
        with open(self.cases, "w", encoding="utf-8") as f:
            json.dump({"cases": [{"spec": "specs/day-44-example.md", "at": at}]}, f)

    def saved(self):
        with open(self.cases, encoding="utf-8") as f:
            return json.load(f)

    def run_it(self, reply, *argv):
        with open(os.path.join(self.repo, "reply.txt"), "w", encoding="utf-8") as f:
            f.write(reply)
        runner = [
            sys.executable,
            os.path.join(self.repo, "reply.py"),
            os.path.join(self.repo, "reply.txt"),
        ]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = agent_cases.main(["rater", "--runs", "2", *argv], repo=self.repo, runner=runner)
        return code, out.getvalue().splitlines()

    def test_the_case_is_the_spec_at_its_commit_and_record_keeps_the_count(self):
        code, lines = self.run_it(json.dumps(ONE_CAUSE_OFF), "--record")
        self.assertEqual(0, code)
        self.assertRegex(lines[0], r"^rater: 3 entries from 1 specs, 2 runs, brief [0-9a-f]{7}$")
        self.assertEqual("cause: 2 of 3 agree at worst (2, 2)", lines[2])
        recorded = self.saved()["recorded"]
        self.assertEqual(
            {"stage": 3, "cause": 2, "made": 3, "runs": 2},
            {k: v for k, v in recorded.items() if k != "brief"},
        )
        code, lines = self.run_it(json.dumps(RIGHT))
        self.assertEqual("not lower than recorded", lines[-1])

    def test_no_run_counted_exits_1_and_records_nothing(self):
        code, lines = self.run_it("the file was not there", "--record")
        self.assertEqual(1, code)
        self.assertEqual("no run counted", lines[-1])
        self.assertNotIn("recorded", self.saved())


if __name__ == "__main__":
    unittest.main()
