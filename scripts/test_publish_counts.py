#!/usr/bin/env python3
"""Tests for scripts/publish-counts.py: small repositories with a bare remote and a counter that
writes five files, since the real one reads this machine's transcripts.

    python scripts/test_publish_counts.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SCRIPT = os.path.join(HERE, "publish-counts.py")
FILES = ["counted.json", "gates.json", "refusals.json", "sessions.json", "token-usage.json"]
ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
           GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")

# Stands in for token-usage.py: sessions.json gains one entry per run whose COUNT differs from the
# last entry it finds, so a test sees both what the count started from and a count with no news.
COUNTER = """import json, os, sys
d = os.path.dirname(sys.argv[sys.argv.index("--out") + 1])
p = os.path.join(d, "sessions.json")
rows = json.load(open(p)) if os.path.exists(p) else []
if os.environ["COUNT"] not in rows:
    rows.append(os.environ["COUNT"])
for n in ("token-usage.json", "refusals.json", "gates.json"):
    open(os.path.join(d, n), "w", newline="\\n").write("[]\\n")
open(p, "w", newline="\\n").write(json.dumps(rows) + "\\n")
open(os.path.join(d, "counted.json"), "w", newline="\\n").write(json.dumps({"at": os.environ["AT"]}) + "\\n")
"""


def git(cwd, *args):
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, env=ENV, check=True).stdout.strip()


class PublishCountsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.origin = os.path.join(tmp.name, "origin.git")
        self.repo = os.path.join(tmp.name, "repo")
        self.counter = os.path.join(tmp.name, "counter.py")
        with open(self.counter, "w") as f:
            f.write(COUNTER)
        git(tmp.name, "init", "-q", "--bare", "-b", "main", self.origin)
        git(tmp.name, "init", "-q", "-b", "main", self.repo)
        git(self.repo, "config", "core.autocrlf", "false")
        os.makedirs(os.path.join(self.repo, "docs", "dashboard"))
        self.write("sessions.json", '["committed"]\n')
        self.write("counted.json", '{"at": "2026-01-02T00:00:00+01:00"}\n')
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "first")
        git(self.repo, "remote", "add", "origin", self.origin)
        git(self.repo, "push", "-q", "origin", "main")

    def write(self, name, text):
        with open(os.path.join(self.repo, "docs", "dashboard", name), "w", newline="\n") as f:
            f.write(text)

    def read(self, name):
        with open(os.path.join(self.repo, "docs", "dashboard", name)) as f:
            return f.read()

    def run_script(self, *args, count="one", at="2026-01-03T00:00:00+01:00"):
        return subprocess.run([sys.executable, SCRIPT, "--repo", self.repo, "--counter", self.counter, *args],
                              capture_output=True, text=True, env=dict(ENV, COUNT=count, AT=at))

    def test_the_count_lands_on_the_data_branch_and_nothing_local_moves(self):
        head = git(self.repo, "rev-parse", "HEAD")
        p = self.run_script("--no-dispatch")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(git(self.origin, "ls-tree", "-r", "--name-only", "dashboard-data").split("\n"),
                         ["docs/dashboard/" + n for n in FILES])
        # started from the committed count, since the branch did not exist yet
        self.assertEqual(json.loads(git(self.origin, "show", "dashboard-data:docs/dashboard/sessions.json")), ["committed", "one"])
        self.assertEqual((git(self.repo, "rev-parse", "HEAD"), git(self.repo, "branch", "--show-current"),
                          git(self.repo, "status", "--porcelain")), (head, "main", ""))

    def test_a_later_count_starts_from_the_branch_and_a_count_with_no_news_is_not_pushed(self):
        self.run_script("--no-dispatch")
        first = git(self.origin, "rev-parse", "dashboard-data")
        p = self.run_script("--no-dispatch", at="2026-01-04T00:00:00+01:00")
        self.assertIn("nothing new", p.stdout)
        self.assertEqual(git(self.origin, "rev-parse", "dashboard-data"), first)
        self.run_script("--no-dispatch", count="two", at="2026-01-05T00:00:00+01:00")
        self.assertEqual(git(self.origin, "rev-parse", "dashboard-data^"), first)
        self.assertEqual(json.loads(git(self.origin, "show", "dashboard-data:docs/dashboard/sessions.json")),
                         ["committed", "one", "two"])

    def test_take_writes_the_branchs_count_only_when_it_is_the_later_one(self):
        p = self.run_script("--take")
        self.assertEqual((p.returncode, self.read("sessions.json")), (0, '["committed"]\n'), p.stderr)  # no branch yet
        self.run_script("--no-dispatch")
        self.run_script("--take")
        self.assertEqual((self.read("sessions.json"), json.loads(self.read("counted.json"))["at"]),
                         ('["committed", "one"]\n', "2026-01-03T00:00:00+01:00"))
        self.write("sessions.json", '["a close, later"]\n')
        self.write("counted.json", '{"at": "2026-01-09T00:00:00+01:00"}\n')
        p = self.run_script("--take")
        self.assertIn("keeping it", p.stdout)
        self.assertEqual(self.read("sessions.json"), '["a close, later"]\n')


class WiringTest(unittest.TestCase):
    def test_the_session_hooks_publish_in_the_background(self):
        with open(os.path.join(ROOT, ".claude", "settings.json"), encoding="utf-8") as f:
            hooks = json.load(f)["hooks"]
        for event in ("SessionStart", "SessionEnd"):
            commands = [h["command"] for group in hooks.get(event, []) for h in group["hooks"]]
            self.assertTrue(any("'publish-counts.py'" in c and "'--detach'" in c for c in commands), event)

    def test_the_workflow_takes_the_newer_count_before_it_builds(self):
        with open(os.path.join(ROOT, ".github", "workflows", "dashboard.yml"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("workflow_dispatch", text)
        self.assertLess(text.index("python scripts/publish-counts.py --take"), text.index("python scripts/spec-drift.py --build"))


if __name__ == "__main__":
    unittest.main()
