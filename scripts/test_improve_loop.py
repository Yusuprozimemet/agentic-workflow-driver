"""improve-loop.py: the draft and each deletion are counted, and only a deletion no count falls
below the draft's is proposed. The counts are faked here: agent-cases.py's own tests run them.

    python scripts/test_improve_loop.py
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
spec = importlib.util.spec_from_file_location("improve_loop", os.path.join(HERE, "improve-loop.py"))
improve_loop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(improve_loop)

REPLY = """miss: day-44 -> the brief never says to read the Notes
DRAFT
a
TRIM
KEEP
END DRAFT
DELETIONS:
[{"passage": "TRIM\\n", "why": "unused"}, {"passage": "KEEP\\n", "why": "unused"},
 {"passage": "absent\\n", "why": "gone"}]
"""


class LoopTest(unittest.TestCase):
    """A scratch repository with one agent and its cases; the drafter replies from a file."""

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        subprocess.run(["git", "-C", self.repo, "init", "-q"], check=True)
        for path, text in [
            (".claude/agents/rater.md", "brief\n"),
            ("specs/agent-cases/rater.json", json.dumps({"cases": []})),
            (
                "reply.py",
                "import sys\nopen(sys.argv[2], 'w').write(sys.stdin.read())\n"
                "print(open(sys.argv[1], encoding='utf-8').read())\n",
            ),
        ]:
            os.makedirs(os.path.dirname(os.path.join(self.repo, path)), exist_ok=True)
            with open(os.path.join(self.repo, path), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        self.calls = []
        self.real = improve_loop.cases.count
        improve_loop.cases.count = self.count

    def tearDown(self):
        improve_loop.cases.count = self.real

    def count(self, agent, runs, brief, out, repo, runner):
        """Stage 2 with KEEP in the brief counted (and on the agent's own), 1 without."""
        text = "KEEP" if brief is None else open(brief, encoding="utf-8").read()
        self.calls.append(os.path.basename(brief) if brief else "brief")
        return f"{agent}: head", ["a line"], {"stage": 2 if "KEEP" in text else 1, "runs": runs}

    def run_it(self, reply):
        with open(os.path.join(self.repo, "reply.txt"), "w", encoding="utf-8") as f:
            f.write(reply)
        prompt = os.path.join(self.repo, "prompt.txt")
        drafter = [sys.executable, os.path.join(self.repo, "reply.py"), "reply.txt", prompt]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = improve_loop.main(["rater", "--runs", "2"], repo=self.repo, drafter=drafter)
        with open(prompt, encoding="utf-8") as f:
            return code, f.read()

    def read(self, name):
        with open(os.path.join(self.repo, ".claude/state/improve-loop/rater", name)) as f:
            return f.read()

    def test_a_deletion_is_proposed_only_when_no_count_falls_below_the_drafts(self):
        code, prompt = self.run_it(REPLY)
        self.assertEqual(0, code)
        self.assertEqual(["brief", "draft.md", "deletion-1.md", "deletion-2.md"], self.calls)
        self.assertIn("The last count of this brief is", prompt)
        self.assertEqual("a\nTRIM\nKEEP\n", self.read("draft.md"))
        self.assertEqual("a\nKEEP\n", self.read("proposed.md"))
        report = self.read("report.md").splitlines()
        for want in [
            "1. 'TRIM' (unused): proposed",
            "2. 'KEEP' (unused): not proposed, stage 1 < 2",
            "3. 'absent' (gone): not counted, not exactly once in the draft",
            "+a",
            "+KEEP",
        ]:
            self.assertIn(want, report)

    def test_a_count_recorded_on_todays_brief_is_before_and_not_run_again(self):
        sha = subprocess.run(
            ["git", "-C", self.repo, "hash-object", ".claude/agents/rater.md"],
            capture_output=True,
            check=True,
        ).stdout.decode()[:7]
        data = {"cases": [], "recorded": {"stage": 2, "runs": 3, "brief": sha}}
        with open(os.path.join(self.repo, "specs/agent-cases/rater.json"), "w") as f:
            json.dump(data, f)
        code, prompt = self.run_it(REPLY)
        self.assertEqual(0, code)
        self.assertEqual(["draft.md", "deletion-1.md", "deletion-2.md"], self.calls)
        self.assertIn("No count of this brief was kept", prompt)
        self.assertIn(f"recorded on today's brief {sha}: stage 2 (3 runs)", self.read("report.md"))

    def test_a_reply_with_no_draft_exits_1_and_counts_no_draft(self):
        code, _ = self.run_it("DELETIONS: []\n")
        self.assertEqual(1, code)
        self.assertEqual(["brief"], self.calls)


if __name__ == "__main__":
    unittest.main()
