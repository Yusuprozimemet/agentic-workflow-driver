"""The review snapshot (Day 12, Track C): driver.review.snapshot reads HEAD, the refs, the stash
and git status with read-only git commands, and changed names the first of them that moved.
Checks C12.6 and C12.7."""

import importlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# A git that records its arguments and exits with the code in code.txt, and prints nothing.
FAKE_GIT = """import json
import os
import sys

here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "calls.jsonl"), "ab") as log:
    log.write((json.dumps(sys.argv[1:]) + "\\n").encode("utf-8"))
with open(os.path.join(here, "code.txt"), "rb") as code:
    sys.exit(int(code.read().strip()))
"""


class ReviewSnapshotTest(unittest.TestCase):
    def setUp(self):
        self.review = importlib.import_module("driver.review")
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def git(self, repo, *args):
        return subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)

    def repo(self):
        # A scratch repository with one commit on main; each case gets a fresh one.
        repo = tempfile.mkdtemp(dir=self.root)
        self.git(repo, "init", "-q", "-b", "main")
        self.git(repo, "config", "user.email", "test@example.com")
        self.git(repo, "config", "user.name", "Test")
        Path(repo, "a.txt").write_bytes(b"one\n")
        self.git(repo, "add", "a.txt")
        self.git(repo, "commit", "-q", "-m", "one")
        return repo

    def test_changes_named(self):
        # C12.6: each kind of change is named by the first of the four keys that moved.
        def nothing(repo):
            return None

        def new_commit(repo):
            Path(repo, "b.txt").write_bytes(b"two\n")
            self.git(repo, "add", "b.txt")
            self.git(repo, "commit", "-q", "-m", "two")

        def new_branch(repo):
            self.git(repo, "branch", "x")

        def edit_tracked(repo):
            Path(repo, "a.txt").write_bytes(b"changed\n")

        def stash_edit(repo):
            self.git(repo, "stash")

        def untracked(repo):
            Path(repo, "c.txt").write_bytes(b"new\n")

        def switch_branch(repo):
            self.git(repo, "switch", "-c", "y")

        cases = [
            ("a new commit", nothing, new_commit, "HEAD"),
            ("a new branch", nothing, new_branch, "the refs"),
            # The edit is made before the snapshot, so the stash is what moves.
            ("a stashed edit", edit_tracked, stash_edit, "the stash"),
            ("an untracked file", nothing, untracked, "`git status`"),
            ("a switch to a new branch", nothing, switch_branch, "HEAD"),
            ("nothing done", nothing, nothing, None),
        ]
        for label, prepare, act, expected in cases:
            with self.subTest(case=label):
                repo = self.repo()
                prepare(repo)
                before = self.review.snapshot(repo)
                act(repo)
                after = self.review.snapshot(repo)
                self.assertEqual(self.review.changed(before, after), expected)

        repo = self.repo()
        before = self.review.snapshot(repo)
        self.assertEqual(sorted(before), ["head", "refs", "stash_top", "status"])
        self.assertTrue(all(value is not None for value in before.values()))

    def test_reads_only(self):
        # C12.7: snapshot runs only read-only git commands; when git fails, every key is None.
        folder = self.repo()
        fake_dir = tempfile.mkdtemp(dir=self.root)
        script = Path(fake_dir, "fake-git.py")
        script.write_bytes(FAKE_GIT.encode("utf-8"))
        code = Path(fake_dir, "code.txt")
        log = Path(fake_dir, "calls.jsonl")
        fake = (sys.executable, str(script))

        code.write_bytes(b"0")
        self.review.snapshot(folder, git=fake)
        calls = []
        if log.exists():
            calls = [json.loads(line) for line in log.read_bytes().decode("utf-8").splitlines()]
        firsts = {call[0] for call in calls if call}
        read_only = {"rev-parse", "for-each-ref", "status"}
        self.assertEqual(sorted(firsts - read_only), [])
        self.assertEqual([name for name in sorted(read_only) if name not in firsts], [])

        code.write_bytes(b"1")
        self.assertEqual(
            self.review.snapshot(folder, git=fake),
            {"head": None, "refs": None, "stash_top": None, "status": None},
        )
