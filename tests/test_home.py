"""check() reads the driver's own repository: clean, changes named, the close files left out, a
moved HEAD, and a folder that is not a repository. The scratch repository is made per test."""

import importlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GIT = [
    "git",
    "-c",
    "user.name=t",
    "-c",
    "user.email=t@t",
    "-c",
    "core.autocrlf=false",
    "-c",
    "commit.gpgsign=false",
]


def clear_readonly(func, path, exc):
    # Git marks its object files read-only on Windows; removing the scratch repository needs them
    # writable first.
    os.chmod(path, stat.S_IWRITE)
    func(path)


class HomeTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone, and
        # scripts/track-red.py counts a module that does not load as not run, not as red.
        self.home = importlib.import_module("driver.home")
        self.repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.repo, onexc=clear_readonly)
        self.git("init", "-q")
        self.commit("a.txt", b"one\n")
        os.mkdir(os.path.join(self.repo, "sub"))
        self.commit("sub/b.txt", b"two\n")

    def git(self, *args):
        result = subprocess.run([*GIT, *args], cwd=self.repo, capture_output=True, check=True)
        return result.stdout.decode("utf-8").strip()

    def write(self, name, body):
        Path(self.repo, name).write_bytes(body)

    def commit(self, name, body):
        self.write(name, body)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", f"change {name}")

    def test_clean(self):
        head = self.git("rev-parse", "HEAD")
        self.assertEqual(len(head), 40)
        self.assertEqual(self.home.check(self.repo), (head, None))

    def test_changes_named(self):
        head = self.git("rev-parse", "HEAD")
        self.write("a.txt", b"edited\n")
        self.write("notes.txt", b"untracked\n")
        self.assertEqual(
            self.home.check(self.repo),
            (head, "the driver's repository has changes: `a.txt`, `notes.txt`"),
        )

    def test_ignored_close_files(self):
        head = self.git("rev-parse", "HEAD")
        self.write("evidence-rehearsal.json", b"{}\n")
        self.write("evidence.json", b"{}\n")
        self.assertEqual(self.home.check(self.repo), (head, None))
        self.write("sub/evidence.json", b"{}\n")
        self.assertEqual(
            self.home.check(self.repo),
            (head, "the driver's repository has changes: `sub/evidence.json`"),
        )

    def test_moved(self):
        started = self.git("rev-parse", "HEAD")
        self.commit("a.txt", b"two\n")
        head = self.git("rev-parse", "HEAD")
        self.assertEqual(
            self.home.check(self.repo, started),
            (head, f"the driver's repository moved from `{started[:7]}` to `{head[:7]}`"),
        )
        with self.subTest("a move and an untracked file name the changes"):
            self.write("notes.txt", b"untracked\n")
            self.assertEqual(
                self.home.check(self.repo, started),
                (head, "the driver's repository has changes: `notes.txt`"),
            )

    def test_not_a_repository(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        self.assertEqual(
            self.home.check(folder),
            (None, f"the driver's folder `{folder}` is not a git repository"),
        )
