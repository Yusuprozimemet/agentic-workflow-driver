"""scripts/auditor-guard.py lets an auditor refresh a clone of its own, and nothing more.

The instrument-auditor works in a scratch clone outside the repository; the guard blocked every
`git fetch`, wherever it pointed, so the clone could not be brought up to date (its audit of
2026-11-15). A fetch named with `-C` at another repository passes now; a fetch here, or in a
worktree of this repository (it shares the refs), is still blocked, and so is every other write.
"""

import importlib.util
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "auditor-guard.py"


def _load():
    spec = importlib.util.spec_from_file_location("auditor_guard", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(*args):
    subprocess.run(["git", *args], check=True, capture_output=True)


class FetchOutsideTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guard = _load()
        cls.tmp = tempfile.mkdtemp()
        base = pathlib.Path(cls.tmp)
        cls.project = str(base / "project")
        cls.clone = str(base / "clone")
        cls.worktree = str(base / "worktree")
        _git("init", "-q", cls.project)
        _git(
            "-C",
            cls.project,
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "first",
        )
        _git("clone", "-q", cls.project, cls.clone)
        _git("-C", cls.project, "worktree", "add", "-q", cls.worktree)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def blocked(self, command):
        """What the hook says to an instrument-auditor's Bash call: None when it passes."""
        data = {
            "agent_type": "instrument-auditor",
            "agent_id": "t",
            "tool_input": {"command": command},
        }
        code, message = self.guard.run("pre", data, self.project, os.path.join(self.tmp, "store"))
        if not code:
            return None
        return re.match(r"auditor-guard: blocked, (.*?)[.] Auditors", message).group(1)

    def test_a_fetch_in_another_repository_passes(self):
        self.assertIsNone(self.blocked(f'git -C "{self.clone}" fetch'))
        self.assertIsNone(self.blocked(f'git -C "{self.clone}" fetch origin dashboard-data'))

    def test_a_fetch_here_is_blocked(self):
        self.assertEqual(self.blocked("git fetch"), "git fetch changes a repository")
        self.assertEqual(
            self.blocked(f'git -C "{self.project}" fetch'), "git fetch changes a repository"
        )

    def test_a_fetch_in_a_worktree_of_this_repository_is_blocked(self):
        self.assertEqual(
            self.blocked(f'git -C "{self.worktree}" fetch'), "git fetch changes a repository"
        )

    def test_a_fetch_at_a_relative_or_missing_path_is_blocked(self):
        self.assertEqual(self.blocked("git -C ../clone fetch"), "git fetch changes a repository")
        missing = os.path.join(self.tmp, "nowhere")
        self.assertEqual(
            self.blocked(f'git -C "{missing}" fetch'), "git fetch changes a repository"
        )

    def test_other_writes_in_another_repository_are_still_blocked(self):
        self.assertEqual(
            self.blocked(f'git -C "{self.clone}" checkout main'),
            "git checkout changes a repository",
        )
        self.assertEqual(
            self.blocked(f'git -C "{self.clone}" pull'), "git pull changes a repository"
        )


if __name__ == "__main__":
    unittest.main()
