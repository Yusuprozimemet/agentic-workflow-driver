"""run-steps.py --dry-run prints the one action the driver would take, reads the project and its
remote, and changes nothing. Each test builds a project and a bare remote in a temporary folder."""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCRIPT = ROOT / "run-steps.py"
START = "Day 01: read the spec against the code, then the spec-change PR"
CAVEAT = "No GitHub remote: read from git only, so there are no PRs and the PR panels are empty."
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}
# The fixture's spec-drift.py: it writes the drift it was given, to the --out it is passed.
SCRIPT_TEMPLATE = """import argparse
import json

parser = argparse.ArgumentParser()
parser.add_argument("--out")
parser.add_argument("--cache")
args = parser.parse_args()
with open(args.out, "w", encoding="utf-8") as f:
    json.dump(json.loads({drift!r}), f)
"""


def git(cwd, *args):
    kwargs = {"capture_output": True, "text": True, "encoding": "utf-8", "env": GIT_ENV}
    return subprocess.run(["git", *args], cwd=cwd, check=True, **kwargs)


def drift_of(next_step=START, open_prs=()):
    return {
        "now": {"next_step": next_step, "open_prs": [{"number": n} for n in open_prs]},
        "order": [1],
        "days": [{"day": 1, "phase": 0, "status": "active"}],
        "meta": {"caveats": []},
    }


def without(drift, key):
    return {k: v for k, v in drift.items() if k != key}


def make_project(tmp, drift=None, script=None):
    # Files are written as bytes: on Windows, text mode would add a carriage return to each line.
    git(tmp, "init", "--bare", "-b", "main", "remote.git")
    project = Path(tmp) / "project"
    project.mkdir()
    git(project, "init", "-b", "main")
    git(project, "config", "core.autocrlf", "false")
    (project / "scripts").mkdir()
    if script is None:
        drift = drift_of() if drift is None else drift
        script = SCRIPT_TEMPLATE.format(drift=json.dumps(drift))
    (project / "scripts" / "spec-drift.py").write_bytes(script.encode("utf-8"))
    (project / "scripts" / "pr-names.py").write_bytes(b"")
    (project / ".github" / "workflows").mkdir(parents=True)
    (project / ".github" / "workflows" / "evidence.yml").write_bytes(b"")
    git(project, "add", "-A")
    git(project, "commit", "-m", "fixture")
    git(project, "remote", "add", "origin", str(Path(tmp) / "remote.git"))
    git(project, "push", "-u", "origin", "main")
    return project


def clone(project, name):
    # A second clone of the remote, used to move the remote without fetching into the project.
    git(project.parent, "clone", str(project.parent / "remote.git"), name)
    return project.parent / name


def commit_file(repo, name):
    (repo / name).write_bytes(b"x\n")
    git(repo, "add", name)
    git(repo, "commit", "-m", name)


def dry_run(project):
    cmd = [sys.executable, str(SCRIPT), "--dry-run", "--project", str(project)]
    done = subprocess.run(cmd, check=False, capture_output=True, text=True, encoding="utf-8")
    return done.returncode, done.stdout, done.stderr


def dry_run_recorded(project):
    # Loads run-steps.py in this process, so the patched subprocess.run sees each command it runs.
    real_run = subprocess.run
    commands = []

    def record(*args, **kwargs):
        commands.append(list(args[0]))
        return real_run(*args, **kwargs)

    spec = importlib.util.spec_from_file_location("run_steps", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    out, err = io.StringIO(), io.StringIO()
    with (
        mock.patch("subprocess.run", side_effect=record),
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
    ):
        code = module.main(["--dry-run", "--project", str(project)])
    return code, out.getvalue(), err.getvalue(), commands


def inside(path, project):
    return Path(path).resolve().is_relative_to(project.resolve())


def is_read(cmd, project):
    script = str(project / "scripts" / "spec-drift.py")
    if cmd[1:2] == [script]:
        return all(
            flag in cmd and not inside(cmd[cmd.index(flag) + 1], project)
            for flag in ("--out", "--cache")
        )
    return cmd[0] == "git" and (
        cmd[1:3] == ["status", "--porcelain"]
        or cmd[1:2] in (["rev-parse"], ["for-each-ref"], ["ls-remote"])
        or cmd[1:] == ["symbolic-ref", "-q", "--short", "HEAD"]
    )


class DryRunTest(unittest.TestCase):
    def project(self, drift=None, script=None):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        return make_project(tmp.name, drift, script)

    def test_prints_one_action_and_its_exit_code(self):
        cases = [
            ("start", drift_of(), 0, f"start: {START}\n"),
            ("wait", drift_of(open_prs=(12, 13)), 0, "wait: #12, #13\n"),
            ("park", drift_of("Every day is done."), 1, "park: every day is done\n"),
        ]
        for name, drift, code, line in cases:
            with self.subTest(name):
                actual, out, _ = dry_run(self.project(drift))
                self.assertEqual((actual, out), (code, line))

    def test_unreadable_project_exits_2(self):
        gone = self.project()
        git(gone, "rm", "scripts/spec-drift.py")
        git(gone, "commit", "-m", "remove the script")
        cases = [
            ("no script", gone, str(gone / "scripts" / "spec-drift.py")),
            (
                "script fails",
                self.project(script="import sys\nsys.exit(3)\n"),
                "scripts/spec-drift.py exited 3",
            ),
            (
                "no now.next_step",
                self.project({**drift_of(), "now": {"open_prs": []}}),
                "now.next_step",
            ),
            (
                "no now.open_prs",
                self.project({**drift_of(), "now": {"next_step": START}}),
                "now.open_prs",
            ),
            ("no order", self.project(without(drift_of(), "order")), "order"),
            ("no days", self.project(without(drift_of(), "days")), "days"),
        ]
        for name, project, text in cases:
            with self.subTest(name):
                code, out, err = dry_run(project)
                self.assertEqual((code, out), (2, ""))
                self.assertEqual(len(err.splitlines()), 1, err)
                self.assertIn(text, err)

    def test_github_unread_exits_2(self):
        drift = drift_of()
        drift["meta"]["caveats"] = [CAVEAT]
        project = self.project(drift)
        git(project, "remote", "set-url", "origin", "https://github.com/example/example.git")
        code, out, err = dry_run(project)
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(len(err.splitlines()), 1, err)
        self.assertIn("GitHub could not be read", err)
        # The same caveat with a local remote is not a failure: there is no GitHub to read.
        code, out, _ = dry_run(self.project(drift))
        self.assertEqual(code, 0, out)

    def test_origin_main_is_read_live(self):
        ahead = self.project()
        other = clone(ahead, "other")
        commit_file(other, "new.txt")
        git(other, "push", "origin", "main")
        local = self.project()
        commit_file(local, "local.txt")
        gone = self.project()
        git(gone, "remote", "remove", "origin")
        behind = "park: main is not origin/main\n"
        cases = [
            (ahead, behind),
            (local, behind),
            (gone, "park: the project has no origin/main\n"),
        ]
        for project, line in cases:
            with self.subTest(line=line):
                code, out, _ = dry_run(project)
                self.assertEqual((code, out), (1, line))

    def test_runs_only_reads(self):
        project = self.project()
        code, out, _, commands = dry_run_recorded(project)
        self.assertIn(code, (0, 1))
        self.assertTrue(out.startswith(("start: ", "wait: ", "park: ")), out)
        self.assertTrue(
            any(cmd[1:2] == [str(project / "scripts" / "spec-drift.py")] for cmd in commands),
            commands,
        )
        self.assertTrue(any(cmd[:2] == ["git", "status"] for cmd in commands), commands)
        for cmd in commands:
            self.assertTrue(is_read(cmd, project), f"not a read: {cmd}")
        # A branch only the remote has: the dry run must see it through ls-remote, not a fetch.
        project = self.project()
        other = clone(project, "other")
        git(other, "checkout", "-b", "day-01/spec-x")
        commit_file(other, "x.txt")
        git(other, "push", "origin", "day-01/spec-x")
        _, out, _, _ = dry_run_recorded(project)
        self.assertEqual(out, "park: a branch of this step exists: day-01/spec-x\n")

    def test_project_is_unchanged(self):
        project = self.project()

        def snapshot():
            status = git(project, "status", "--porcelain", "--ignored").stdout
            return status, git(project, "for-each-ref").stdout

        before = snapshot()
        code, out, _ = dry_run(project)
        self.assertIn(code, (0, 1))
        self.assertTrue(out.startswith(("start: ", "wait: ", "park: ")), out)
        self.assertEqual(snapshot(), before)


if __name__ == "__main__":
    unittest.main()
