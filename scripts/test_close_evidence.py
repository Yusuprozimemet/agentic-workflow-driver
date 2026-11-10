"""Commit-to-spec lookup, and the rehearsal of a close, against real throwaway Git repositories."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from evidence import change_commit, close_commit, closed_specs, closing_spec
from test_evidence import BREAK, GIT_ENV, spec

CLOSE_EVIDENCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "close-evidence.py")


class ClosingSpecTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.git("init", "-q", "-b", "main")
        self.git("commit", "-q", "--allow-empty", "-m", "base")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, env=GIT_ENV,
                              capture_output=True, text=True, check=True).stdout

    def merge(self, specs=(), subject="Merge pull request #9 from owner/day-07/close-the-day"):
        self.git("switch", "-q", "-c", "close")
        os.makedirs(os.path.join(self.repo, "specs"))
        for name in specs:
            with open(os.path.join(self.repo, "specs", name), "w") as file:
                file.write("# Day 07\n")
        self.git("add", ".")
        self.git("commit", "-q", "--allow-empty", "-m", "close")
        self.git("switch", "-q", "main")
        self.git("merge", "-q", "--no-ff", "-m", subject, "close")

    def lookup(self):
        # Only route the production Git calls to the fixture; Git itself is real.
        with patch("evidence.git", side_effect=self.git):
            return closing_spec("HEAD")

    def test_one_spec(self):
        self.merge(("day-07-example.md",))
        self.assertEqual(self.lookup(), "specs/day-07-example.md")

    def test_ordinary_merge(self):
        self.merge(subject="Merge pull request #9 from owner/tooling/example")
        self.assertIsNone(self.lookup())

    def test_direct_commit(self):
        self.assertIsNone(self.lookup())  # A root commit has no parents.
        self.git("commit", "-q", "--allow-empty", "-m",
                 "Merge pull request #9 from owner/day-07/close-the-day")
        self.assertIsNone(self.lookup())

    def test_missing_spec(self):
        self.merge()
        with self.assertRaisesRegex(ValueError, "day-07: expected one spec, found 0"):
            self.lookup()

    def test_two_specs(self):
        self.merge(("day-07-a.md", "day-07-b.md"))
        with self.assertRaisesRegex(ValueError, "day-07: expected one spec, found 2"):
            self.lookup()

    def squash(self, subject):
        os.makedirs(os.path.join(self.repo, "specs"), exist_ok=True)
        with open(os.path.join(self.repo, "specs", "day-01-example.md"), "w") as file:
            file.write("# Day 01\n")
        self.git("add", ".")
        self.git("commit", "-q", "--allow-empty", "-m", subject)
        return self.git("rev-parse", "HEAD").strip()

    def test_squash_spec(self):
        self.squash("Day 01 close: tick criteria (#2)")
        self.assertEqual(self.lookup(), "specs/day-01-example.md")

    def test_squash_close_commit(self):
        sha = self.squash("Day 01 close: tick criteria (#2)")
        with patch("evidence.git", side_effect=self.git):
            self.assertEqual(close_commit("01", "main"), sha)

    def test_close_without_pr_number(self):
        self.squash("Day 01 close")
        self.assertIsNone(self.lookup())

    def test_track_squash_is_not_close(self):
        self.squash("Day 01 track A: x (#3)")
        self.assertIsNone(self.lookup())

    def test_tracker_key_squash(self):
        self.squash("ABC-12 Day 01 close: tick criteria (#2)")
        with patch.dict(os.environ, {"JIRA_KEY": "ABC"}):
            self.assertEqual(self.lookup(), "specs/day-01-example.md")

    def test_latest_close_wins(self):
        self.squash("Day 01 close: first (#2)")
        latest = self.squash("Day 01 close: second (#3)")
        with patch("evidence.git", side_effect=self.git):
            self.assertEqual(close_commit("01", "main"), latest)

    def change(self, slug="keep-ok", subject="Merge pull request #9 from owner/change/keep-ok"):
        """A change branch that adds specs/changes/<slug>.md, merged with that subject."""
        self.git("switch", "-q", "-c", "change")
        os.makedirs(os.path.join(self.repo, "specs", "changes"), exist_ok=True)
        if slug:
            with open(os.path.join(self.repo, "specs", "changes", f"{slug}.md"), "w") as file:
                file.write("# Keep the ok\n")
        self.git("add", ".")
        self.git("commit", "-q", "--allow-empty", "-m", "change")
        self.git("switch", "-q", "main")
        self.git("merge", "-q", "--no-ff", "-m", subject, "change")
        return self.git("rev-parse", "HEAD").strip()

    def test_change_merge_lands_its_short_spec(self):
        sha = self.change()
        self.assertEqual(self.lookup(), "specs/changes/keep-ok.md")
        with patch("evidence.git", side_effect=self.git):
            self.assertEqual(change_commit("keep-ok", "main"), sha)
            self.assertIsNone(change_commit("other", "main"))

    def test_change_merge_without_its_spec_fails(self):
        self.change(slug=None)
        with self.assertRaisesRegex(ValueError, "specs/changes/keep-ok.md: not at"):
            self.lookup()

    def test_squash_that_adds_a_short_spec_lands_it(self):
        os.makedirs(os.path.join(self.repo, "specs", "changes"))
        with open(os.path.join(self.repo, "specs", "changes", "keep-ok.md"), "w") as file:
            file.write("# Keep the ok\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "Keep the ok (#4)")
        sha = self.git("rev-parse", "HEAD").strip()
        self.assertEqual(self.lookup(), "specs/changes/keep-ok.md")
        with patch("evidence.git", side_effect=self.git):
            self.assertEqual(change_commit("keep-ok", "main"), sha)
        self.git("commit", "-q", "--allow-empty", "-m", "Another change (#5)")
        self.assertIsNone(self.lookup())  # a squash that adds no short spec lands none

    def test_merge_with_squash_subject_is_not_close(self):
        self.merge(subject="Day 01 close: wrong branch (#2)")
        self.assertIsNone(self.lookup())
        with patch("evidence.git", side_effect=self.git):
            self.assertIsNone(close_commit("01", "main"))

    def test_closed_specs_lists_only_days_with_a_closing_commit(self):
        # One day closed by a merge, the next day's spec merged but not closed, and a template beside them.
        self.merge(("day-07-example.md", "_template.md"))
        with open(os.path.join(self.repo, "specs", "day-08-next.md"), "w") as file:
            file.write("# Day 08\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "Day 08 spec")
        with patch("evidence.git", side_effect=self.git):
            self.assertEqual(closed_specs("main"), ["specs/day-07-example.md"])


class RehearseTest(unittest.TestCase):
    """close-evidence.py --rehearse: a closing branch replays before it merges, and nothing moves."""

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.write("tests/test_cli.py", "class CliTest(unittest.TestCase):\n    def test_a(self):\n        pass\n")
        self.write("app.txt", "ok\n")
        self.git("init", "-q", "-b", "main")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "base")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, env=GIT_ENV, capture_output=True, text=True,
                              check=True).stdout

    def write(self, path, text):
        full = os.path.join(self.repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def close(self, text, branch="day-01/close-the-day"):
        """The closing branch, committed and not merged; main is checked out again."""
        self.git("switch", "-q", "-c", branch)
        self.write("specs/day-01-x.md", text)
        self.write("specs/breaks/day-01.json", json.dumps([BREAK]))
        self.git("add", ".")
        self.git("commit", "-q", "-m", "close")
        self.git("switch", "-q", "main")

    def rehearse(self, *args):
        # No identity but the script's own: a CI runner has none, and commit-tree refuses without one.
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_"))}
        env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        return subprocess.run([sys.executable, CLOSE_EVIDENCE, "--rehearse", *args], cwd=self.repo, env=env,
                              capture_output=True, text=True, encoding="utf-8")

    def test_a_closing_branch_replays_before_it_merges(self):
        self.close(spec())
        before = self.git("for-each-ref") + self.git("status", "--porcelain") + self.git("worktree", "list")
        run = self.rehearse("day-01/close-the-day")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("all evidence holds", run.stdout)
        self.assertIn("ok    C1.1 broken: the ok removed", run.stdout)
        with open(os.path.join(self.repo, "evidence-rehearsal.json"), encoding="utf-8") as f:
            report = json.load(f)
        self.assertNotEqual(report["days"][0]["close_sha"], self.git("rev-parse", "main").strip())
        os.remove(os.path.join(self.repo, "evidence-rehearsal.json"))
        after = self.git("for-each-ref") + self.git("status", "--porcelain") + self.git("worktree", "list")
        self.assertEqual(after, before)  # no ref, file or worktree is left: main is where it was

    def test_a_verify_line_that_fails_fails_the_rehearsal(self):
        self.close(spec(verify="echo 1    # 0"))
        run = self.rehearse("day-01/close-the-day")
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("FAIL  Verify: echo 1", run.stdout)

    def test_the_merge_commit_ci_checks_out_rehearses_by_its_parents(self):
        # A pull request's checkout: the merge of the branch into the base, on no branch, its
        # subject not a closing merge's. CI names the two sides by its parents.
        self.close(spec())
        self.git("switch", "-q", "--detach", "main")
        self.git("merge", "-q", "--no-ff", "-m", "Merge 1111111 into 2222222", "day-01/close-the-day")
        run = self.rehearse("day-01/close-the-day", "--base", "HEAD^1", "--head", "HEAD^2")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("all evidence holds", run.stdout)

    def test_a_branch_that_closes_nothing_passes_without_a_replay(self):
        self.close(spec(), branch="tooling/example")
        run = self.rehearse("tooling/example")
        self.assertEqual((run.returncode, run.stdout.strip()), (0, "not a closing branch: nothing to rehearse"))
        self.assertFalse(os.path.exists(os.path.join(self.repo, "evidence-rehearsal.json")))

    def test_a_branch_that_does_not_merge_fails(self):
        self.close(spec())
        self.write("specs/day-01-x.md", "# another Day 01\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "main moved")
        run = self.rehearse("day-01/close-the-day")
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("FAIL  day-01/close-the-day does not merge into main", run.stdout)

    def test_an_unknown_branch_fails(self):
        run = self.rehearse("day-01/close-the-day")
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn("FAIL  day-01/close-the-day: no such commit", run.stdout)


if __name__ == "__main__":
    unittest.main()
