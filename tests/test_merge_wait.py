"""The path check, the merge wait and the evidence wait after a green pull request (driver/loop.py,
C06.6, C06.7, C06.13). Each case runs the fake gh of tests/test_github.py beside a scratch project
with a bare remote, and the real git behind a recorder."""

import importlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import clone, commit_file, drift_of, git, make_project
from tests.test_github import fake_gh, read_bodies, read_calls
from tests.test_once import DASHED
from tests.test_tree import MERGE, recorded, recorder
from tests.test_wait import RUN_ISSUE, SESSION, STEP, STOP_ISSUE

BRANCH = "day-01/track-a-x"


def view(state, paths=("driver/once.py",), body=""):
    merge = {"oid": "a" * 40} if state == "MERGED" else None
    files = [{"path": p} for p in paths]
    out = {"state": state, "mergeCommit": merge, "files": files, "body": body}
    return {"code": 0, "out": out}


def run(status, conclusion=""):
    return {"code": 0, "out": [{"status": status, "conclusion": conclusion}]}


def run_steps():
    # run-steps.py is not a module name Python can import, so it is loaded by its path, as in
    # tests/test_tree.py.
    spec = importlib.util.spec_from_file_location("run_steps", ROOT / "run-steps.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GateTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top, as in test_wait: where driver/loop.py is missing, each test
        # fails alone with ModuleNotFoundError.
        self.loop = importlib.import_module("driver.loop")

    def test_parks(self):
        cases = [
            (["plan.md", "docs/kit.md"], "Oversized: yes", ["docs/"], "park: #12 touches plan.md"),
            (
                ["docs/kit.md"],
                "Oversized: yes",
                ["docs/"],
                "park: #12 touches a human-only path: `docs/kit.md`",
            ),
            (
                ["docs/kit.md"],
                "",
                ["docs/kit.md"],
                "park: #12 touches a human-only path: `docs/kit.md`",
            ),
            (
                ["driver/once.py"],
                "text\nOversized: 500 lines\n",
                ["docs/"],
                "park: #12 carries Oversized:",
            ),
        ]
        for paths, body, human_only, want in cases:
            with self.subTest(paths=paths, body=body, human_only=human_only):
                self.assertEqual(self.loop.gated(paths, body, human_only, 12), want)

    def test_passes(self):
        cases = [
            (["driver/once.py"], "", ["docs/"]),
            (["driver/once.py"], "this is not Oversized: at all", ["docs/"]),
            (["docs/plan.md"], "", []),
            (["docs/kit.md"], "", ["docs"]),
            (["docsy/x"], "", ["docs/"]),
        ]
        for paths, body, human_only in cases:
            with self.subTest(paths=paths, body=body, human_only=human_only):
                self.assertIsNone(self.loop.gated(paths, body, human_only, 12))


class MergeWaitTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top, as in test_wait.
        self.loop = importlib.import_module("driver.loop")
        self.read_facts = run_steps().read_facts

    def build(self, views, runs=None, issues=None, wait_minutes=30, issue_code=0):
        # A clean project on the step's own branch, with its local main one commit behind origin/main:
        # the maintainer's merge is the commit `other` pushes.
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        (self.root / "gh").mkdir()
        (self.root / "state").mkdir()
        project = make_project(self.root, drift_of(DASHED))
        git(project, "switch", "-c", BRANCH)
        commit_file(project, "work.txt")
        other = clone(project, "other")
        commit_file(other, "merged.txt")
        git(other, "push", "origin", "main")
        self.head = git(other, "rev-parse", "HEAD").stdout.strip()
        gh = fake_gh(
            self.root / "gh",
            issues=[RUN_ISSUE] if issues is None else issues,
            issue_code=issue_code,
            views=views,
            run_steps=runs or [run("completed", "success")],
        )
        self.args = SimpleNamespace(
            state=str(self.root / "state"), gh=gh, poll=0.01, wait_minutes=wait_minutes
        )
        self.record = {"issue": 7, "step": STEP, "session": SESSION}
        self.project = str(project)
        self.git = recorder(self.root)

    def wait(self, human_only=()):
        line, code = self.loop.wait_merge(
            self.args, self.project, 12, self.record, list(human_only), self.read_facts, self.git
        )
        # The scratch commit's sha differs each run; a break's report must not (the close replays it).
        return line and line.replace(self.head[:7], "<head>"), code

    def gh_of(self, *prefix):
        # The recorded gh calls that begin with prefix; each call is its argument list.
        if not (self.root / "gh" / "calls.jsonl").exists():
            return []
        calls = read_calls(self.root / "gh")
        return [call for call in calls if call[: len(prefix)] == list(prefix)]

    def edit_fake(self, change):
        # The fake's spec is read and written as bytes, as the fake reads and writes it.
        path = self.root / "gh" / "fake.json"
        spec = json.loads(path.read_bytes())
        change(spec)
        path.write_bytes(json.dumps(spec).encode("utf-8"))

    def on_sleep(self, change):
        # change runs during the first sleep only, so that the next poll reads what it wrote. A wait
        # that does not end on it fails here, instead of polling for ever.
        ran = []

        def once_only(poll):
            ran.append(poll)
            if len(ran) == 1:
                change()
            elif len(ran) > 5:
                raise AssertionError("the wait did not end on what the first sleep changed")

        return mock.patch.object(self.loop, "sleep", side_effect=once_only)

    def test_merged_pulled_evidence_waited(self):
        self.build(
            [view("OPEN"), view("OPEN"), view("MERGED")],
            [run("in_progress"), run("completed", "success")],
        )
        result = self.wait()
        self.assertEqual(result, (None, 0))
        self.assertEqual(recorded(self.root), MERGE)
        self.assertEqual(git(self.project, "branch", "--show-current").stdout.strip(), "main")
        self.assertEqual(git(self.project, "rev-parse", "main").stdout.strip(), self.head)
        self.assertEqual(len(self.gh_of("pr", "view")), 3)
        evidence = self.gh_of("run", "list")
        self.assertEqual(len(evidence), 2)
        for call in evidence:
            self.assertTrue(call[call.index("--commit") + 1] == self.head, "another commit read")

    def test_gated_pr_parks(self):
        cases = [
            (view("OPEN", paths=["plan.md"]), (), "park: #12 touches plan.md"),
            (
                view("OPEN", paths=["docs/kit.md"]),
                ("docs/",),
                "park: #12 touches a human-only path: `docs/kit.md`",
            ),
        ]
        for pr_view, human_only, want in cases:
            with self.subTest(want=want):
                # CLOSED second: without the path check the wait ends instead of polling for ever.
                self.build([pr_view, view("CLOSED")])
                result = self.wait(human_only)
                self.assertEqual(result, (want, 1))
                self.assertEqual(recorded(self.root), [])
                self.assertEqual(self.gh_of("run", "list"), [])

    def test_closed_parks(self):
        self.build([view("CLOSED")])
        self.assertEqual(self.wait(), ("park: #12 was closed without a merge", 1))
        self.assertEqual(recorded(self.root), [])

    def test_evidence_failed_parks(self):
        self.build([view("MERGED")], [run("completed", "failure")])
        self.assertEqual(self.wait(), ("park: the evidence run on `<head>` ended `failure`", 1))
        self.assertEqual(len(self.gh_of("run", "list")), 1)

    def test_evidence_unfinished_parks(self):
        self.build([view("MERGED")], [run("in_progress")], wait_minutes=0.01)
        line = "park: the evidence run on `<head>` has not finished (`in_progress`)"
        self.assertEqual(self.wait(), (f"{line} after 0.01 minutes", 1))

    def test_failed_read_bounded(self):
        self.build([{"code": 1, "out": ""}], wait_minutes=0.01)
        self.assertEqual(self.wait(), ("cannot read the project: gh pr view exited 1", 2))
        self.assertGreater(len(self.gh_of("pr", "view")), 1)

    def test_evidence_failed_read_bounded(self):
        self.build([view("MERGED")], [{"code": 1, "out": ""}], wait_minutes=0.01)
        self.assertEqual(self.wait(), ("cannot read the project: gh run list exited 1", 2))
        self.assertGreater(len(self.gh_of("run", "list")), 1)

    def test_nothing_read_while_issues_cannot_be(self):
        self.build([view("MERGED")], wait_minutes=0.01, issue_code=1)
        self.assertEqual(self.wait(), ("cannot read the project: gh issue list exited 1", 2))
        self.assertEqual(self.gh_of("pr", "view"), [])

    def test_no_origin_main(self):
        self.build([view("MERGED")])

        def without_origin(project):
            return replace(self.read_facts(project), origin_main=None)

        result = self.loop.wait_merge(
            self.args, self.project, 12, self.record, [], without_origin, self.git
        )
        self.assertEqual(result, ("cannot read the project: no origin/main after #12 merged", 2))

    def test_halt_during_merge_wait(self):
        self.build([view("OPEN")])

        def halt():
            (self.root / "state" / "halt").write_bytes(b"by hand\n")

        with self.on_sleep(halt):
            line, code = self.wait()
        self.assertTrue(line.startswith("halt:"), line)
        self.assertEqual(code, 1)
        self.assertEqual(len(self.gh_of("pr", "view")), 1)
        self.assertEqual(recorded(self.root), [])

    def test_stop_during_evidence_wait(self):
        self.build([view("MERGED")], [run("in_progress")])

        def add_stop():
            self.edit_fake(lambda spec: spec["issues"].append(STOP_ISSUE))

        with self.on_sleep(add_stop):
            result = self.wait()
        self.assertEqual(result, ("halt: the STOP issue #9 is open; nothing more starts", 1))
        halt = (self.root / "state" / "halt").read_bytes().decode("utf-8")
        self.assertIn("STOP issue #9", halt)
        bodies = [
            body
            for body in read_bodies(self.root / "gh")
            if body["args"][:3] == ["issue", "comment", "7"]
        ]
        self.assertEqual(len(bodies), 1)
        self.assertEqual(len(self.gh_of("run", "list")), 1)

    def test_off_during_merge_wait(self):
        self.build([view("OPEN")])

        def close_run():
            def closed(spec):
                for issue in spec["issues"]:
                    if issue["number"] == 7:
                        issue["state"] = "closed"

            self.edit_fake(closed)

        with self.on_sleep(close_run):
            result = self.wait()
        self.assertEqual(result, ("off: the run's issue #7 is closed; nothing new starts", 0))
        self.assertEqual(self.gh_of("pr", "close"), [])
        self.assertEqual(recorded(self.root), [])


if __name__ == "__main__":
    unittest.main()
