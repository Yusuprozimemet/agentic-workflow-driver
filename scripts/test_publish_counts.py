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
# RACE: the first count lets another publisher land a commit on the branch, with a file of its own,
# between this publisher's fetch and its push.
race = os.environ.get("RACE")
if race and not os.path.exists(race + ".done"):
    open(race + ".done", "w").close()
    # bytes, not text: text mode on Windows would write a carriage return into each tree entry's name
    g = lambda *a, data=None: subprocess.run(["git", "-C", race, *a], input=data and data.encode(), capture_output=True,
                                             check=True).stdout.decode().strip()
    tip = g("rev-parse", "dashboard-data")
    tree = g("mktree", data=g("ls-tree", tip + ":docs/dashboard") + "\\n100644 blob "
             + g("hash-object", "-w", "--stdin", data="other") + "\\tother.json\\n")
    for part in ("dashboard", "docs"):
        tree = g("mktree", data="040000 tree " + tree + "\\t" + part + "\\n")
    g("update-ref", "refs/heads/dashboard-data", g("commit-tree", tree, "-p", tip, "-m", "the other publisher"))
"""
COUNTER = "import subprocess\n" + COUNTER

# Stands in for driver-runs.py: writes STEPS as the driver's steps, or nothing when STEPS is unset (no log).
DRIVER_COUNTER = """import json, os, sys
if "STEPS" in os.environ:
    out = sys.argv[sys.argv.index("--out") + 1]
    open(out, "w", newline="\\n").write(json.dumps({"counted": os.environ["AT"], "steps": json.loads(os.environ["STEPS"])}) + "\\n")
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
        self.driver_counter = os.path.join(tmp.name, "driver.py")
        with open(self.driver_counter, "w") as f:
            f.write(DRIVER_COUNTER)
        git(tmp.name, "init", "-q", "--bare", "-b", "main", self.origin)
        git(tmp.name, "init", "-q", "-b", "main", self.repo)
        git(self.repo, "config", "core.autocrlf", "false")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "first")
        git(self.repo, "remote", "add", "origin", self.origin)
        git(self.repo, "push", "-q", "origin", "main")

    def write(self, name, text):
        with open(os.path.join(self.repo, "docs", "dashboard", name), "w", newline="\n") as f:
            f.write(text)

    def read(self, name):
        with open(os.path.join(self.repo, "docs", "dashboard", name)) as f:
            return f.read()

    def run_script(self, *args, count="one", at="2026-01-03T00:00:00+01:00", **env):
        return subprocess.run([sys.executable, SCRIPT, "--repo", self.repo, "--counter", self.counter,
                               "--driver-counter", self.driver_counter, *args],
                              capture_output=True, text=True, env=dict(ENV, COUNT=count, AT=at, **env))

    def on_branch(self, name):
        return git(self.origin, "show", f"dashboard-data:docs/dashboard/{name}")

    def test_a_push_rejected_because_another_landed_first_is_built_again_on_it(self):
        self.run_script("--no-dispatch")
        first = git(self.origin, "rev-parse", "dashboard-data")
        p = self.run_script("--no-dispatch", count="two", at="2026-01-05T00:00:00+01:00", RACE=self.origin)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("rejected", p.stdout)
        self.assertEqual(git(self.origin, "log", "--format=%s", "-2", "dashboard-data").split("\n"),
                         ["Count the sessions up to 2026-01-05T00:00:00+01:00", "the other publisher"])
        self.assertEqual(git(self.origin, "rev-parse", "dashboard-data^^"), first)
        # the other publisher's file is kept, and the count is the one built on its commit
        self.assertEqual((self.on_branch("other.json"), json.loads(self.on_branch("sessions.json"))),
                         ("other", ["one", "two"]))

    def test_the_driver_count_is_a_sixth_file_and_its_moment_alone_is_no_news(self):
        self.run_script("--no-dispatch")  # no run log: no sixth file
        self.assertNotIn("driver-runs.json", git(self.origin, "ls-tree", "-r", "--name-only", "dashboard-data"))
        self.run_script("--no-dispatch", STEPS='[{"step": "a"}]')
        self.assertEqual(json.loads(self.on_branch("driver-runs.json"))["steps"], [{"step": "a"}])
        tip = git(self.origin, "rev-parse", "dashboard-data")
        p = self.run_script("--no-dispatch", at="2026-01-06T00:00:00+01:00", STEPS='[{"step": "a"}]')
        self.assertIn("nothing new", p.stdout)
        self.assertEqual(git(self.origin, "rev-parse", "dashboard-data"), tip)
        self.run_script("--no-dispatch", at="2026-01-07T00:00:00+01:00", STEPS='[{"step": "a"}, {"step": "b"}]')
        self.assertEqual(len(json.loads(self.on_branch("driver-runs.json"))["steps"]), 2)
        self.assertEqual(json.loads(self.on_branch("sessions.json")), ["one"])

    def test_put_pushes_a_file_as_it_is_and_keeps_the_count(self):
        self.run_script("--no-dispatch")
        rows = os.path.join(self.repo, os.pardir, "replay-history.json")
        with open(rows, "w", newline="\n") as f:
            f.write('{"rows": []}\n')
        p = self.run_script("--no-dispatch", "--put", rows, "--message", "Re-check")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual((self.on_branch("replay-history.json"), json.loads(self.on_branch("sessions.json"))),
                         ('{"rows": []}', ["one"]))
        tip = git(self.origin, "rev-parse", "dashboard-data")
        self.assertIn("nothing pushed", self.run_script("--no-dispatch", "--put", rows, "--message", "Re-check").stdout)
        self.assertEqual(git(self.origin, "rev-parse", "dashboard-data"), tip)

    def test_the_count_lands_on_the_data_branch_and_nothing_local_moves(self):
        head = git(self.repo, "rev-parse", "HEAD")
        os.makedirs(os.path.join(self.repo, "docs", "dashboard"))
        self.write("sessions.json", '["left in the working tree"]\n')
        p = self.run_script("--no-dispatch")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(git(self.origin, "ls-tree", "-r", "--name-only", "dashboard-data").split("\n"),
                         ["docs/dashboard/" + n for n in FILES])
        # the branch is the only store: with none yet, the count starts from nothing, not from a file left here
        self.assertEqual(json.loads(git(self.origin, "show", "dashboard-data:docs/dashboard/sessions.json")), ["one"])
        self.assertEqual((git(self.repo, "rev-parse", "HEAD"), git(self.repo, "branch", "--show-current"),
                          git(self.repo, "status", "--porcelain"), self.read("sessions.json")),
                         (head, "main", "?? docs/", '["left in the working tree"]\n'))

    def test_a_later_count_starts_from_the_branch_and_a_count_with_no_news_is_not_pushed(self):
        self.run_script("--no-dispatch")
        first = git(self.origin, "rev-parse", "dashboard-data")
        p = self.run_script("--no-dispatch", at="2026-01-04T00:00:00+01:00")
        self.assertIn("nothing new", p.stdout)
        self.assertEqual(git(self.origin, "rev-parse", "dashboard-data"), first)
        self.run_script("--no-dispatch", count="two", at="2026-01-05T00:00:00+01:00")
        self.assertEqual(git(self.origin, "rev-parse", "dashboard-data^"), first)
        self.assertEqual(json.loads(git(self.origin, "show", "dashboard-data:docs/dashboard/sessions.json")),
                         ["one", "two"])


class WiringTest(unittest.TestCase):
    def test_the_session_hooks_publish_in_the_background(self):
        with open(os.path.join(ROOT, ".claude", "settings.json"), encoding="utf-8") as f:
            hooks = json.load(f)["hooks"]
        for event in ("SessionStart", "SessionEnd"):
            commands = [h["command"] for group in hooks.get(event, []) for h in group["hooks"]]
            self.assertTrue(any("'publish-counts.py'" in c and "'--detach'" in c for c in commands), event)

    def test_the_page_build_reads_the_data_branch_alone_and_main_holds_none_of_its_files(self):
        with open(os.path.join(ROOT, ".github", "workflows", "dashboard.yml"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("workflow_dispatch", text)
        self.assertIn("python scripts/spec-drift.py --build", text)
        self.assertNotIn("python scripts/publish-counts.py", text)  # nothing taken into the working tree: spec-drift.py reads the branch
        self.assertNotIn("replay-history.py", text)  # the re-check is its own job: the page's build stays fast
        self.assertNotIn("--take", subprocess.run([sys.executable, SCRIPT, "--help"], capture_output=True, text=True).stdout)
        listed = subprocess.run(["git", "-C", ROOT, "ls-files", "docs/dashboard"], capture_output=True, text=True, check=True)
        on_branch = FILES + ["driver-runs.json", "replay-history.json"]
        self.assertEqual([p for p in listed.stdout.split() if p.rsplit("/", 1)[-1] in on_branch], [])

    def test_the_re_check_job_pushes_its_rows_to_the_data_branch_even_when_stopped(self):
        with open(os.path.join(ROOT, ".github", "workflows", "recheck.yml"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("branches: [main]", text)
        self.assertIn("contents: write", text)
        self.assertIn("actions: write", text)
        run, push = text.index("python scripts/replay-history.py"), text.index("python scripts/publish-counts.py --put")
        self.assertLess(run, push)
        self.assertIn("if: always()", text[run:push])


if __name__ == "__main__":
    unittest.main()
