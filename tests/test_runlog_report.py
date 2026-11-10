"""The run log's park, merged and issue lines (Day 7, C07.16), and the cost a run's issue shows
(C07.19): a park before a session and one after it, the merge wait, a start line with and without
an issue, and `on` with a fake claude that reports its cost. Each case is a copy of the driver with
the fake claude and fake gh of tests/test_once.py and tests/test_github.py, as tests/test_on.py and
tests/test_park_body.py run them."""

import importlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import test_merge_wait, test_wait
from tests.test_dry_run import drift_of
from tests.test_github import fake_gh, read_bodies
from tests.test_merge_wait import view
from tests.test_on import GREEN, RED, OnCase
from tests.test_once import DASHED, driver_copy, fake_claude, once
from tests.test_once_park_issues import build, dirty_tree
from tests.test_preflight import HELP

# The fake claude's reply for each session: one that cost $1.50 and opened no pull request.
PAID = {"type": "result", "is_error": False, "result": "done", "total_cost_usd": 1.5}


class RunLogLines:
    # The helpers the run-log cases share; not a TestCase, so that importing it collects no tests.
    def log_of(self, state):
        # The run log's lines as objects, read from the bytes the driver wrote; none before a write.
        path = Path(state) / "run.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_bytes().splitlines()]

    def merge_wait(self, views):
        # MergeWaitTest's own case, built here without collecting its tests a second time; returns
        # the wait's result and the run log's lines.
        case = test_merge_wait.MergeWaitTest("test_closed_parks")
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.build(views)
        return case.wait(), self.log_of(case.root / "state")


class RunLogReportTest(RunLogLines, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp()
        cls.copy = driver_copy(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def setUp(self):
        # Imported here, as in tests/test_runlog.py: where driver/ is missing, each test fails.
        self.runlog = importlib.import_module("driver.runlog")

    def test_park_lines(self):
        # One park before a session (the tree is dirty, so decide parks first) and one after it (the
        # session opens no pull request, so the driver parks on its outcome).
        cases = [
            ("before_session", {"setup": dirty_tree}),
            ("after_session", {"prs": ()}),
        ]
        for name, kwargs in cases:
            with self.subTest(name):
                folder = Path(self.root) / name
                folder.mkdir()
                code, out, _ = once(self.copy, *build(folder, drift=drift_of(DASHED), **kwargs))
                line = out.strip()
                parks = [r for r in self.log_of(folder / "state") if r["event"] == "park"]
                self.assertEqual((code, line.startswith("park: "), len(parks)), (1, True, 1))
                self.assertEqual(
                    (list(parks[0]), parks[0]["line"] == line, parks[0]["step"] == DASHED),
                    (["event", "at", "step", "line"], True, True),
                )

    def test_merged_line(self):
        result, lines = self.merge_wait([view("MERGED")])
        merged = [(list(r), r["pr"], r.get("changed")) for r in lines if r["event"] == "merged"]
        self.assertEqual(
            (result, merged), ((None, 0), [(["event", "at", "pr", "changed"], 12, None)])
        )
        # A wait that parks because the pull request was closed writes no merged line.
        result, lines = self.merge_wait([view("CLOSED")])
        merged = [r for r in lines if r["event"] == "merged"]
        self.assertEqual((result, merged), (("park: #12 was closed without a merge", 1), []))

    def test_issue_on_start(self):
        state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, state, ignore_errors=True)
        self.runlog.start(state, "s", "p", "sess", "v", issue=12)
        self.runlog.start(state, "s", "p", "sess", "v")
        first, second = self.log_of(state)
        self.assertEqual(
            (list(first)[-1], first.get("issue"), list(second)),
            ("issue", 12, ["event", "at", "step", "prefix", "session", "claude"]),
        )


class RunIssueCostTest(OnCase, unittest.TestCase):
    def setUp(self):
        # Imported here, as in RunLogReportTest.setUp.
        self.runlog = importlib.import_module("driver.runlog")
        self.issues = importlib.import_module("driver.issues")

    def build_paid(self, name):
        # OnCase.build has no result: the fake claude of the test's own replaces the default one.
        self.build(name)
        fake_claude(self.folder / "claude", help=HELP, result=PAID)

    def test_first_body(self):
        self.build_paid("first_body")
        code, _, _ = self.on()
        bodies = [
            record["body"]
            for record in read_bodies(self.folder / "gh")
            if record["args"][:2] == ["issue", "create"]
            and record["args"][3].startswith("Driver run")
        ]
        self.assertEqual((code, len(bodies), "cost so far: $0.00" in bodies[0]), (0, 1, True))

    def test_second_step_comment(self):
        self.build_paid("second_comment")
        code, _, _ = self.on()
        # The run's issue is commented on for the second step; the close comment has no "step: ".
        steps = [body for body in self.comments() if "step: " in body]
        self.assertEqual((code, len(steps), "cost so far: $1.50" in steps[0]), (0, 1, True))

    def test_other_issue_not_counted(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        state = str(folder / "state")
        self.runlog.start(state, "a", "p", "s1", "v", issue=99)
        self.runlog.end(state, "s1", "opened", 2.0, 0)
        self.runlog.start(state, "b", "p", "s2", "v", issue=12)
        self.runlog.end(state, "s2", "opened", 0.25, 0)
        self.runlog.end(state, "s2", "fixed", None, 0)
        self.runlog.start(state, "c", "p", "s4", "v")
        self.runlog.end(state, "s4", "opened", 4.0, 0)
        gh = fake_gh(
            folder,
            issues=[
                {
                    "number": 12,
                    "title": "Driver run x",
                    "labels": [],
                    "state": "open",
                    "author": "me",
                }
            ],
        )
        issue = [{"number": 12, "title": "Driver run x", "labels": []}]
        result = self.issues.open_run(str(folder), gh, "Step", "s3", issue, state=state)
        body = read_bodies(folder)[0]["body"]
        self.assertEqual((result, "cost so far: $0.25" in body), ((12, None), True))
        # A new issue has no number yet: the start line with no issue, and its $4.00, is not its own.
        self.issues.open_run(str(folder), gh, "Step", "s5", [], state=state)
        self.assertIn("cost so far: $0.00", read_bodies(folder)[1]["body"])


class MergeWaitHeadTest(RunLogLines, OnCase, unittest.TestCase):
    # The pr and head that the wait, the merged and the gated park lines carry (Day 8). The
    # assertions compare each line's event, pr, head and changed only: no time or sha in a report.

    def test_wait_line(self):
        # The wait line is written before the first read: a wait that ends at its first read still
        # names #7, and no check is read for it.
        case = test_wait.WaitTest("test_red_without_session_parks")
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.build([GREEN])
        result = case.loop.wait_pr(case.args, case.project, 7, case.record)
        waits = [r for r in self.log_of(case.args.state) if r["event"] == "wait"]
        self.assertEqual((result, [r["pr"] for r in waits]), ((None, 0), [7]))
        case.build([GREEN], issues=[])
        result = case.loop.wait_pr(case.args, case.project, 7, case.record)
        waits = [r for r in self.log_of(case.args.state) if r["event"] == "wait"]
        self.assertEqual(
            (result, [r["pr"] for r in waits], case.gh_of("pr", "checks")),
            (("off: the run's issue #7 is closed; nothing new starts", 0), [7], []),
        )

    def build_pr7(self, name, **kwargs):
        # OnCase.build opens #5 in fake gh; the drift and the fake gh must both have #7 open, so
        # that the run waits on it at the start, as a pull request found there.
        self.build(name, drift=drift_of(DASHED, open_prs=(7,)), **kwargs)
        path = self.folder / "gh" / "fake.json"
        spec = json.loads(path.read_bytes())
        spec["prs"] = [{**pr, "number": 7} for pr in spec["prs"]]
        path.write_bytes(json.dumps(spec).encode("utf-8"))

    def test_gated_park_carries_pr_head(self):
        self.build_pr7("gated", views=[view("OPEN", paths=["plan.md"], head="aaa")])
        code, out, _ = self.on()
        parks = [r for r in self.log_of(self.state) if r["event"] == "park"]
        self.assertEqual(
            (code, out.splitlines()[-1], [(r.get("pr"), r.get("head")) for r in parks]),
            (1, "park: #7 touches plan.md", [(7, "aaa")]),
        )

    def test_park_without_pr(self):
        # C08.17: the park that ends a wait on #7 carries no pr, though record["pr"] is set; its
        # keys are C04.4's.
        cases = [
            ("red", {"checks": [RED]}, "park: the checks on #7 are red: tests"),
            ("closed", {"views": [view("CLOSED")]}, "park: #7 was closed without a merge"),
        ]
        for name, kwargs, line in cases:
            with self.subTest(name):
                self.build_pr7(name, **kwargs)
                code, out, _ = self.on()
                parks = [r for r in self.log_of(self.state) if r["event"] == "park"]
                self.assertEqual(
                    (code, out.splitlines()[-1], [list(r) for r in parks]),
                    (1, line, [["event", "at", "step", "line"]]),
                )

    def test_changed(self):
        _, lines = self.merge_wait([view("OPEN", head="aaa"), view("MERGED", head="bbb")])
        merged = [r for r in lines if r["event"] == "merged"]
        self.assertEqual(
            [(r["pr"], r.get("head"), r["changed"]) for r in merged], [(12, "bbb", True)]
        )

    def test_unchanged(self):
        _, lines = self.merge_wait([view("OPEN", head="aaa"), view("MERGED", head="aaa")])
        merged = [r for r in lines if r["event"] == "merged"]
        self.assertEqual(
            [(r["pr"], r.get("head"), r["changed"]) for r in merged], [(12, "aaa", False)]
        )

    def test_no_head(self):
        _, lines = self.merge_wait([view("OPEN"), view("MERGED")])
        merged = [r for r in lines if r["event"] == "merged"]
        self.assertEqual(
            [("head" in r, "changed" in r, r.get("changed")) for r in merged], [(False, True, None)]
        )
