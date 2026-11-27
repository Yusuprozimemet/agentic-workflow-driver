"""agent-cases.py --record keeps, for the driver's reviewer, what each case got in each run (Day 16,
Track D). C16.16: the worst counts alone cannot say which case a brief edit lost, so the bar
in tests/test_reviewer_bar.py reads `recorded.cases`.

No test starts a model: the runner is a small Python file that prints a reply. The case
repositories have fixed names, `driver` and `bearing`, so a case reads `driver#7` on any machine.
"""

import contextlib
import importlib.util
import io
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "agent-cases.py"
spec = importlib.util.spec_from_file_location("agent_cases", SCRIPT)
agent_cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_cases)

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "core.autocrlf=false"]


def write(root, path, text):
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full) or root, exist_ok=True)
    with open(full, "wb") as f:
        f.write(text.encode("utf-8"))


def committed(path):
    """A git repository at `path` with note.txt committed; its head commit."""
    write(path, "note.txt", "no manifest entry")
    subprocess.run(GIT + ["-C", path, "init", "-q"], check=True)
    subprocess.run(GIT + ["-C", path, "add", "."], check=True)
    subprocess.run(GIT + ["-C", path, "commit", "-q", "-m", "a"], check=True)
    head = subprocess.run(["git", "-C", path, "rev-parse", "HEAD"], capture_output=True, check=True)
    return head.stdout.decode().strip()


class ReviewerRecordTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.repo = os.path.join(self.root, "work")
        driver, bearing = os.path.join(self.root, "driver"), os.path.join(self.root, "bearing")
        cases = [
            {
                "repo": driver,
                "pr": 7,
                "at": committed(driver),
                "expect": "blocker",
                "names": "manifest",
            },
            {"repo": bearing, "pr": 8, "at": committed(bearing), "expect": "none"},
        ]
        write(
            self.repo,
            "reply.py",
            "import re, sys\nsys.stdout.reconfigure(encoding='utf-8')\n"
            "n = re.search(r'#(\\d+)', sys.stdin.read()).group(1)\n"
            "note = open('note.txt', encoding='utf-8').read()\n"
            "print('found: blocker — ' + note + '\\nREVIEW: blocker' if n == '7' else 'REVIEW: none')\n",
        )
        write(self.repo, "rules/reviewer.md", "brief\n")
        subprocess.run(GIT + ["-C", self.repo, "init", "-q"], check=True)
        self.cases = os.path.join(self.repo, "specs", "agent-cases", "reviewer.json")
        write(
            self.repo,
            "specs/agent-cases/reviewer.json",
            json.dumps({"kind": "review", "brief": "rules/reviewer.md", "cases": cases}),
        )

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_record_keeps_each_case(self):
        # C16.16: --record keeps one entry per case, in order, beside the worst counts.
        runner = [sys.executable, os.path.join(self.repo, "reply.py")]
        with contextlib.redirect_stdout(io.StringIO()):
            code = agent_cases.main(["reviewer", "--runs", "2", "--record"], self.repo, runner)
        self.assertEqual(0, code)
        with open(self.cases, "rb") as f:
            recorded = json.loads(f.read().decode("utf-8"))["recorded"]
        # The keys, not the dict: its brief is a hash a red would print.
        self.assertIn("cases", sorted(recorded))
        self.assertEqual(
            [
                {"case": "driver#7", "said": ["blocker", "blocker"], "named": 2},
                {"case": "bearing#8", "said": ["none", "none"], "named": 0},
            ],
            recorded["cases"],
        )
        self.assertEqual(
            {"verdict": 2, "named": 1, "runs": 2},
            {k: recorded[k] for k in ("verdict", "named", "runs")},
        )
        sha = subprocess.run(
            ["git", "hash-object", "rules/reviewer.md"],
            cwd=self.repo,
            capture_output=True,
            check=True,
        )
        self.assertEqual(sha.stdout.decode()[:7], recorded["brief"])


if __name__ == "__main__":
    unittest.main()
