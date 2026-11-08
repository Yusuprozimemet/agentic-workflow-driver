"""--once brings a clean project to main before it decides (C06.1): tree.to_main fetches, switches and
fast-forwards, and parks on what git refuses. Each test builds a project, a bare remote and, for
--once, a copy of the driver in its own temporary folder. The git commands to_main runs are recorded
through its git parameter, and the real git runs behind the recorder."""

import importlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import clone, commit_file, drift_of, dry_run, git, make_project
from tests.test_github import fake_gh, read_calls
from tests.test_once import (
    DASHED,
    OPENED,
    STEP_PR,
    driver_copy,
    fake_claude,
    once,
    write_config,
)

# The recorder logs its arguments beside itself, then runs the real git with them.
RECORDER = """import json
import subprocess
import sys
from pathlib import Path

log = Path(__file__).resolve().parent / "git.jsonl"
with log.open("ab") as f:
    f.write(json.dumps(sys.argv[1:]).encode("utf-8") + b"\\n")
sys.exit(subprocess.run(["git", *sys.argv[1:]]).returncode)
"""
DAY_05 = "day-05/close-the-day"
MERGE = [["fetch", "origin"], ["switch", "main"], ["merge", "--ff-only", "origin/main"]]
# On main already: no switch.
FETCH_MERGE = [["fetch", "origin"], ["merge", "--ff-only", "origin/main"]]


def recorder(root):
    # Files are written as bytes: on Windows, text mode would add a carriage return to each line.
    path = Path(root) / "git-recorder.py"
    path.write_bytes(RECORDER.encode("utf-8"))
    return (sys.executable, str(path))


def recorded(root):
    log = Path(root) / "git.jsonl"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def behind(root):
    # A clean project on day-05's branch, with its local main one commit behind origin/main.
    project = make_project(root, drift_of(DASHED))
    git(project, "switch", "-c", DAY_05)
    commit_file(project, "close.txt")
    other = clone(project, "other")
    commit_file(other, "next.txt")
    git(other, "push", "origin", "main")
    return project


def position(project):
    # The branch HEAD names (empty when detached), and the shas of HEAD, local main and origin/main.
    shas = git(project, "rev-parse", "HEAD", "main", "origin/main").stdout
    return git(project, "branch", "--show-current").stdout, shas


def read_facts_of(project):
    spec = importlib.util.spec_from_file_location("run_steps", ROOT / "run-steps.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read_facts(project)


class TreeTest(unittest.TestCase):
    def scratch(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        return Path(root)

    def test_brought_to_main(self):
        tree = importlib.import_module("driver.tree")
        classify = importlib.import_module("driver.steps").classify
        root = self.scratch()
        project = behind(root)
        moved, line = tree.to_main(
            project, read_facts_of(project), classify(DASHED), git=recorder(root)
        )
        self.assertEqual((moved, line), (True, None))
        self.assertEqual(recorded(root), MERGE)
        self.assertEqual(git(project, "branch", "--show-current").stdout.strip(), "main")
        origin = git(project, "rev-parse", "origin/main").stdout
        self.assertEqual(git(project, "rev-parse", "main").stdout, origin)
        self.assertEqual(git(root / "other", "rev-parse", "HEAD").stdout, origin)

        # The same fixture again, this time through --once: the step starts on the moved project.
        root = self.scratch()
        project = behind(root)
        copy = driver_copy(root)
        claude_dir, gh_dir = root / "claude", root / "gh"
        claude_dir.mkdir()
        gh_dir.mkdir()
        claude = fake_claude(claude_dir)
        gh = fake_gh(gh_dir, runs=[{"status": "completed", "conclusion": "success"}], prs=[STEP_PR])
        config = write_config(root, project)
        flags = ["--config", str(config), "--state", str(root / "state"), "--claude", claude]
        code, out, err = once(copy, *flags, "--gh", gh)
        self.assertEqual(code, 0, err)
        self.assertEqual(out.splitlines()[-1], OPENED)
        calls = read_calls(claude_dir)
        sessions = [call for call in calls if call["args"] not in (["--version"], ["--help"])]
        self.assertEqual(len(sessions), 1)
        self.assertEqual(git(project, "branch", "--show-current").stdout.strip(), "main")
        origin = git(project, "rev-parse", "origin/main").stdout
        self.assertEqual(git(project, "rev-parse", "main").stdout, origin)

    def test_refusals_park(self):
        tree = importlib.import_module("driver.tree")
        classify = importlib.import_module("driver.steps").classify
        decide = importlib.import_module("driver.decide").decide
        drift = drift_of(DASHED)

        def attempt(project, root):
            facts = read_facts_of(project)
            return tree.to_main(project, facts, classify(DASHED), git=recorder(root))

        with self.subTest("diverged"):
            root = self.scratch()
            project = make_project(root, drift)
            commit_file(project, "local.txt")
            other = clone(project, "other")
            commit_file(other, "next.txt")
            git(other, "push", "origin", "main")
            before = git(project, "rev-parse", "main").stdout
            line = "park: cannot bring the project to main: git merge exited 128"
            self.assertEqual(attempt(project, root), (True, line))
            self.assertEqual(recorded(root), FETCH_MERGE)
            self.assertEqual(git(project, "rev-parse", "main").stdout, before)

        with self.subTest("ahead only"):
            root = self.scratch()
            project = make_project(root, drift)
            commit_file(project, "local.txt")
            before = git(project, "rev-parse", "main").stdout
            self.assertEqual(attempt(project, root), (True, None))
            self.assertEqual(recorded(root), FETCH_MERGE)
            self.assertEqual(git(project, "rev-parse", "main").stdout, before)
            line = decide(drift, read_facts_of(project)).line
            self.assertEqual(line, "park: main is not origin/main")

        with self.subTest("dirty"):
            root = self.scratch()
            project = behind(root)
            (project / "stray.txt").write_bytes(b"x\n")
            before = position(project)
            self.assertEqual(attempt(project, root), (False, None))
            self.assertEqual(recorded(root), [])
            self.assertEqual(position(project), before)
            line = decide(drift, read_facts_of(project)).line
            self.assertEqual(line, "park: the project's tree is not clean (1 paths)")

        with self.subTest("detached"):
            root = self.scratch()
            project = behind(root)
            git(project, "switch", "--detach")
            before = position(project)
            self.assertEqual(attempt(project, root), (False, None))
            self.assertEqual(recorded(root), [])
            self.assertEqual(position(project), before)
            line = decide(drift, read_facts_of(project)).line
            self.assertEqual(line, "park: the project is on a detached HEAD, not on main")

        with self.subTest("branch of the step"):
            root = self.scratch()
            project = behind(root)
            git(project, "branch", "day-01/track-a-x")
            before = position(project)
            self.assertEqual(attempt(project, root), (False, None))
            self.assertEqual(recorded(root), [])
            self.assertEqual(position(project), before)
            line = decide(drift, read_facts_of(project)).line
            self.assertEqual(line, f"park: the project is on {DAY_05}, not on main")

    def test_dry_run_moves_nothing(self):
        root = self.scratch()
        project = behind(root)
        before = position(project)
        code, out, _ = dry_run(project)
        self.assertEqual((code, out), (1, f"park: the project is on {DAY_05}, not on main\n"))
        self.assertEqual(position(project), before)


if __name__ == "__main__":
    unittest.main()
