"""The read-only hook refuses a call that writes to git or GitHub, or that runs one behind a prefix,
a subshell or a pipe, and passes the reads a reviewer makes; a call it cannot read is refused too.
Each refusal is appended to the refusals log as one line. It runs as a subprocess, as Claude Code
runs it."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ONLY_READS = "refused by the driver: the reviewer only reads"
UNREAD = "refused by the driver: the read-only hook could not read the tool call"


def call(tool, command):
    return json.dumps({"tool_name": tool, "tool_input": {"command": command}})


class ReadonlyHookTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        self.cwd = folder
        self.refusals = os.path.join(folder, "refusals")

    def run_hook(self, stdin):
        return subprocess.run(
            [sys.executable, str(ROOT / "hooks" / "readonly.py"), self.refusals],
            input=stdin,
            capture_output=True,
            text=True,
            check=False,
            cwd=self.cwd,
        )

    def lines(self):
        path = os.path.join(self.refusals, "hooks.jsonl")
        if not os.path.exists(path):
            return 0
        with open(path, encoding="utf-8") as handle:
            return len(handle.read().splitlines())

    def test_refuses(self):
        commands = [
            ("Bash", "git commit -m x"),
            ("Bash", "git push"),
            ("Bash", "git checkout -b x"),
            ("Bash", "git switch main"),
            ("Bash", "git stash"),
            ("Bash", "git fetch"),
            ("Bash", "git -C . reset --hard"),
            ("Bash", "ls && git add ."),
            ("Bash", "gh pr merge 3"),
            ("Bash", "gh pr comment 3 --body x"),
            ("Bash", "gh pr review 3 --approve"),
            ("Bash", "gh issue close 3"),
            ("Bash", "gh api -X POST repos/o/r/issues"),
            ("Bash", "gh api repos/o/r/issues -f title=x"),
            ("Bash", "gh api --input body.json repos/o/r/issues"),
            ("Bash", "GIT_X=1 git commit -m x"),
            ("Bash", "env git commit -m x"),
            ("Bash", "(git commit -m x)"),
            ("Bash", "ls & git commit -m x"),
            ("PowerShell", "& git commit -m x"),
        ]
        for tool, command in commands:
            with self.subTest(command=command):
                before = self.lines()
                result = self.run_hook(call(tool, command))
                self.assertEqual(result.returncode, 2)
                self.assertTrue(ONLY_READS in result.stderr, msg=command)
                self.assertTrue(result.stdout == "", msg=command)
                self.assertEqual(self.lines(), before + 1)

        before = self.lines()
        result = self.run_hook("not json")
        self.assertEqual(result.returncode, 2)
        self.assertTrue(UNREAD in result.stderr)
        self.assertEqual(self.lines(), before + 1)
        self.assertEqual(self.lines(), 21)

    def test_passes(self):
        commands = [
            "git status",
            "git diff main...HEAD",
            "git --no-pager diff",
            "git log --oneline -5",
            "git show HEAD:plan.md",
            "git -C . rev-parse HEAD",
            "git ls-files",
            "gh pr view 3 --json files",
            "gh pr diff 3",
            "gh pr checks 3",
            "gh api repos/o/r/pulls/3",
            "gh api -X GET repos/o/r/pulls/3/files",
            "grep -n x plan.md",
            "python -m unittest",
        ]
        for command in commands:
            with self.subTest(command=command):
                result = self.run_hook(call("Bash", command))
                self.assertEqual(result.returncode, 0)
                self.assertTrue(result.stdout == "", msg=command)
                self.assertTrue(result.stderr == "", msg=command)

        read = json.dumps({"tool_name": "Read", "tool_input": {"file_path": "plan.md"}})
        result = self.run_hook(read)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout == "")
        self.assertTrue(result.stderr == "")

        self.assertFalse(os.path.exists(os.path.join(self.refusals, "hooks.jsonl")))


if __name__ == "__main__":
    unittest.main()
