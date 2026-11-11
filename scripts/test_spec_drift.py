"""The dashboard's numbers move when they should and only then.

Each drift test builds a small git repository, one commit per merge, and runs spec-drift.py's
trajectory over it; the roadmap tests check the run order, the statuses and the next step. Needs
git and numpy; the page tests run docs/dashboard/dashboard.js and need node.

    python scripts/test_spec_drift.py
"""
import contextlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("spec_drift", os.path.join(HERE, "spec-drift.py"))
sd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sd)


def split_modules(name):
    """spec-drift.py and the modules it is split into that hold name: what was one global is a
    name in each module that reads it, and a test patches them all."""
    mods = (sd, *(sys.modules[m] for m in sorted(sys.modules) if m.startswith("spec_drift_")))
    return [m for m in mods if hasattr(m, name)]


def setall(name, value):
    for m in split_modules(name):
        setattr(m, name, value)


@contextlib.contextmanager
def patch_all(name, new=None, **kwargs):
    """mock.patch.object on every module that holds name, with one mock or value for all."""
    new = mock.MagicMock(**kwargs) if new is None else new
    with contextlib.ExitStack() as stack:
        for m in split_modules(name):
            stack.enter_context(mock.patch.object(m, name, new))
        yield new

PLAN = "# Plan\n\nThe plan names `FooService` and `bar_table`.\n"
DAY = "# Day 01\n\nThe day adds `FooService`, then the rest of the day.\n"
# The source project's file under neutral names: its two tests renamed to another stem,
# its six directory moves, its Verify base, its four services by package, and its infra workflow.
PROJECT = dict(
    renamed=[[296, "OrdersUserDeletedConsumerIT", "UserDeletedConsumerTest"],
             [298, "CircuitBreakerIT", "StockLookupBreakerTest"]],
    moved=[[174, "core/stock", "services/stock-service"], [224, "core/pricing", "services/pricing-service"],
           [296, "core/orders", "services/order-service"], [315, "core", "services/account-service"],
           [416, "services/account-service/docs", "docs/system"],
           [419, "services/account-service/app", "services/account-service"]],
    verify_bases=["core"], package_root="org.example.shop",
    services=dict(auth="account", user="account", profile="account", account="account", stock="stock",
                  catalog="stock", saved="orders", orders="orders", pricing="pricing"),
    infra_workflow="infra.yaml")


def use_project(test, fields):
    """fields as the project file, read as spec-drift.py reads its own, until the test ends."""
    folder = tempfile.mkdtemp(prefix="spec-drift-config-")
    test.addCleanup(shutil.rmtree, folder, True)
    path = os.path.join(folder, "spec-drift.config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fields, f)
    for name, value in sd.project_config(path).items():
        test.addCleanup(setall, name, getattr(sd, name))
        setall(name, value)


class Repo:
    def __init__(self):
        self.path = tempfile.mkdtemp(prefix="spec-drift-test-")
        self.git("init", "-q")
        self.snaps = []

    def git(self, *args):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false",
                               *args], cwd=self.path, capture_output=True, text=True, check=True).stdout

    def merge(self, files):
        """One commit, standing in for one merge on main."""
        for name, text in files.items():
            full = os.path.join(self.path, name)
            if text is None:  # deleted, or moved when the new path is in the same merge
                os.remove(full)
                continue
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", f"merge {len(self.snaps)}")
        n = len(self.snaps)
        self.snaps.append(dict(sha=self.git("rev-parse", "--short", "HEAD").strip(), date="2026-09-20",
                               pr=n or None, title=f"Day 01 track A: {n}", branch="day-01/track-a-x" if n else ""))
        return self

    def rows(self):
        return self.inside(lambda blobs: sd.trajectory([dict(s) for s in self.snaps], blobs)[0])

    def inside(self, fn):
        """fn(blobs), run in the repository."""
        cwd = os.getcwd()
        os.chdir(self.path)
        try:
            with sd.Blobs() as blobs:
                return fn(blobs)
        finally:
            os.chdir(cwd)

    def close(self):
        shutil.rmtree(self.path, ignore_errors=True)


class SpecDriftTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo().merge({"plan.md": PLAN, "specs/day-01-x.md": DAY, "src/App.java": "class App {}\n"})

    def tearDown(self):
        self.repo.close()

    def test_code_that_names_a_spec_name_narrows_the_gap(self):
        rows = self.repo.merge({"src/Foo.java": "class FooService {}\n"}).rows()
        self.assertIsNone(rows[0]["gap_full"])  # no spec name in the code: no direction to compare
        self.assertLess(rows[1]["gap_full"], 90.0)

    def test_name_coverage_is_the_share_of_spec_names_the_code_has(self):
        rows = self.repo.merge({"src/Foo.java": "class FooService { FooService f; }\n"}).rows()
        self.assertEqual((rows[0]["name_coverage"], rows[1]["name_coverage"]), (0.0, 0.5))  # bar_table not yet
        rows = self.repo.merge({"src/Bar.java": "bar_table b;\n"}).rows()
        self.assertEqual(rows[2]["name_coverage"], 1.0)
        rows = self.repo.merge({"plan.md": "# Plan\n\nThe plan names nothing.\n"}).rows()
        self.assertEqual(rows[3]["name_coverage"], 1.0)  # bar_table, in the code only, is not asked for

    def test_jaccard_counts_a_name_the_specs_dropped_but_the_code_keeps(self):
        rows = self.repo.merge({"src/Foo.java": "class FooService { bar_table b; }\n"}).rows()
        self.assertEqual((rows[1]["name_coverage"], rows[1]["jaccard"]), (1.0, 1.0))
        rows = self.repo.merge({"plan.md": "# Plan\n\nThe plan names nothing.\n"}).rows()
        self.assertEqual((rows[2]["name_coverage"], rows[2]["jaccard"]), (1.0, 0.5))  # bar_table: code only
        self.assertEqual((rows[1]["names_kept"], rows[2]["names_kept"]), (0, 1))

    def test_a_file_under_specs_is_never_code_whatever_its_extension(self):
        # A break manifest copies the spec's names: at #25 one moved the gap with no code changed.
        rows = self.repo.merge({"src/Foo.java": "class FooService {}\n"}).rows()
        rows = self.repo.merge({"specs/breaks/day-01.json": '{"names": ["FooService", "bar_table"]}\n',
                                "specs/notes.py": "bar_table = 1\n"}).rows()
        for field in ("gap_full", "name_coverage", "jaccard", "coverage"):
            self.assertEqual(rows[2][field], rows[1][field], field)
        self.assertEqual(rows[2]["name_coverage"], 0.5)  # bar_table is only under specs/

    def test_a_spec_name_that_is_a_file_or_folder_in_the_code_is_in_the_code(self):
        # On Bearing 36 of the 41 names missing at Day 12 were test files the specs cite by path.
        rows = self.repo.merge({"plan.md": PLAN + "Tested in `tests/test_widget.py`, under `src/foo_parts/`.\n",
                                "tests/test_widget.py": "def test_it():\n    pass\n",
                                "src/foo_parts/a.txt": "x\n"}).rows()
        self.assertEqual(rows[1]["name_coverage"], 0.5)  # test_widget and foo_parts; not FooService or bar_table
        self.assertLess(rows[1]["gap_full"], 90.0)

    def test_a_file_name_outside_the_code_does_not_count(self):
        rows = self.repo.merge({"plan.md": PLAN + "Tested in `tests/test_widget.py`.\n",
                                "docs/test_widget.md": "notes\n", "specs/breaks/test_widget.json": "{}\n",
                                "data/test_widget.csv": "x\n"}).rows()
        self.assertEqual(rows[1]["name_coverage"], 0.0)

    def test_a_python_builtin_name_is_not_a_spec_name(self):
        # The specs cite Python's errors to describe a failure; Bearing's code was never meant to hold them.
        rows = self.repo.merge({"plan.md": PLAN + "It fails with an `ImportError` or a `SyntaxWarning`.\n"}).rows()
        self.assertEqual(rows[1]["spec_names"], rows[0]["spec_names"])

    def test_a_name_in_a_test_or_a_script_still_counts_as_code(self):
        rows = self.repo.merge({"tests/test_foo.py": "FooService = None\n", "scripts/bar.py": "bar_table = 1\n"}).rows()
        self.assertEqual(rows[1]["name_coverage"], 1.0)

    def test_a_name_only_in_a_test_or_a_script_is_code_but_not_production(self):
        self.addCleanup(sd.CACHE.clear)
        rows = self.repo.merge({"tests/test_foo.py": "FooService = None\n", "scripts/bar.py": "bar_table = 1\n",
                                "experiments/e1/cases.json": '{"names": "FooService bar_table"}\n'}).rows()
        self.assertEqual((rows[1]["name_coverage"], rows[1]["prod_name_coverage"]), (1.0, 0.0))
        self.assertEqual((rows[1]["spec_names"], rows[1]["names_in_code"], rows[1]["names_in_prod"]), (2, 2, 0))
        self.assertEqual(sd.CACHE["code"][self.repo.snaps[1]["sha"]],
                         {"FooService": {"tests/test_foo.py": 1, "experiments/e1/cases.json": 1},
                          "bar_table": {"scripts/bar.py": 1, "experiments/e1/cases.json": 1}})

    def test_a_name_outside_production_is_listed_once_with_each_place_and_path(self):
        rows = self.repo.merge({"tests/test_foo.py": "FooService = None\n", "scripts/foo.py": "FooService = 1\n",
                                "scripts/foo2.py": "FooService = 2\n"}).rows()
        self.assertEqual(rows[1]["names_outside_prod"],
                         {"FooService": {"test": ["tests/test_foo.py"], "tooling": ["scripts/foo.py", "scripts/foo2.py"]}})
        self.assertEqual(rows[1]["names_absent"], ["bar_table"])
        rows = self.repo.merge({"src/Foo.java": "class FooService {}\n"}).rows()
        self.assertEqual((rows[2]["names_outside_prod"], rows[2]["names_absent"]), ({}, ["bar_table"]))
        rows = self.repo.merge({"src/Foo.java": None}).rows()
        self.assertEqual(list(rows[3]["names_outside_prod"]), ["FooService"])
        rows = self.repo.merge({"tests/test_foo.py": None, "scripts/foo.py": None, "scripts/foo2.py": None}).rows()
        self.assertEqual((rows[4]["names_outside_prod"], rows[4]["names_absent"]), ({}, ["FooService", "bar_table"]))

    def test_a_name_in_production_raises_production_coverage_and_its_removal_lowers_it(self):
        self.repo.merge({"tests/test_foo.py": "FooService = None\n"})
        rows = self.repo.merge({"src/Foo.java": "class FooService {}\n"}).rows()
        self.assertEqual([r["prod_name_coverage"] for r in rows], [0.0, 0.0, 0.5])
        self.assertEqual([r["names_in_prod"] for r in rows], [0, 0, 1])
        rows = self.repo.merge({"src/Foo.java": None}).rows()
        self.assertEqual((rows[3]["name_coverage"], rows[3]["prod_name_coverage"]), (0.5, 0.0))

    def test_a_line_is_split_where_it_was_before_the_path_was_kept(self):
        # str.splitlines also ends a line at a form feed; git grep does not, so after a comment the name still counts.
        rows = self.repo.merge({"src/Foo.java": "// note\x0cclass FooService {}\n"}).rows()
        self.assertEqual((rows[1]["name_coverage"], rows[1]["names_in_prod"]), (0.5, 1))

    def test_production_coverage_skips_comments_and_with_no_spec_name_is_not_measured(self):
        rows = self.repo.merge({"src/Foo.java": "// FooService\nclass Foo {} // bar_table\n"}).rows()
        self.assertEqual((rows[1]["prod_name_coverage"], rows[1]["names_in_prod"]), (0.0, 0))
        rows = self.repo.merge({"plan.md": "# Plan\n", "specs/day-01-x.md": "# Day 01\n",
                                "src/Foo.java": "class FooService { bar_table b; }\n"}).rows()
        self.assertEqual((rows[2]["prod_name_coverage"], rows[2]["name_coverage"], rows[2]["spec_names"]), (None, None, 0))

    def test_a_failed_blob_read_names_the_commit_and_the_path(self):
        sha = self.repo.snaps[0]["sha"]

        def read_after_git_dies(blobs):
            self.assertEqual(blobs.read(sha, "no/such/file"), "")  # missing is not a failure
            blobs.proc.kill()
            blobs.proc.wait()
            return blobs.read(sha, "plan.md")
        with self.assertRaises(RuntimeError) as failed:
            self.repo.inside(read_after_git_dies)
        self.assertIn(f"plan.md at {sha}", str(failed.exception))

    def test_a_run_from_the_cache_reads_what_a_fresh_one_does(self):
        # Merge 1 is cached before any spec names BazClient; merge 2's spec does, which shifts
        # every name's place in the vocabulary.
        self.addCleanup(sd.CACHE.clear)
        self.repo.merge({"src/Baz.java": "class BazClient { FooService f; }\n"})
        sd.CACHE.clear()
        self.repo.rows()
        self.repo.merge({"specs/day-01-x.md": DAY + "It calls `BazClient`.\n", "src/Use.java": "BazClient b;\n"})
        calls, real = [], sd.run
        setall("run", lambda *a: calls.append(a) or real(*a))
        try:
            cached = self.repo.rows()
            sd.CACHE.clear()
            fresh_from = len(calls)
            fresh = self.repo.rows()
        finally:
            setall("run", real)
        self.assertEqual(cached, fresh)
        self.assertLess(fresh_from, len(calls) - fresh_from)

    def test_every_module_of_the_script_is_one_of_its_sources(self):
        # The two tests below loop over SOURCES: a module left out of it would pass them both.
        beside = sorted(n for n in os.listdir(HERE) if re.fullmatch(r"spec_drift_\w+\.py", n))
        self.assertEqual(sorted(sd.SOURCES), sorted(["spec-drift.py", *beside]))

    def test_a_change_to_any_file_of_the_script_starts_the_cache_over(self):
        # The script is split into modules beside it: an edit to one of them is an edit to it.
        folder = tempfile.mkdtemp(prefix="spec-drift-split-")
        self.addCleanup(shutil.rmtree, folder, True)
        for name in sd.SOURCES:
            shutil.copy(os.path.join(HERE, name), folder)
        self.addCleanup(setattr, sd, "__file__", sd.__file__)
        self.addCleanup(sd.CACHE.clear)
        sd.__file__ = os.path.join(folder, "spec-drift.py")
        cache = os.path.join(folder, "c.json")
        sd.load_cache(cache)
        sd.CACHE["git"] = {"k": "v"}
        sd.save_cache(cache)
        sd.load_cache(cache)
        self.assertEqual(sd.CACHE["git"], {"k": "v"})
        with open(os.path.join(folder, sd.SOURCES[-1]), "a", encoding="utf-8") as f:
            f.write("# edited\n")
        sd.load_cache(cache)
        self.assertEqual(sorted(sd.CACHE), ["version"])

    def test_a_comment_naming_a_spec_name_is_not_code(self):
        rows = self.repo.merge({"src/Foo.java": "// FooService comes later\n /* FooService */\n",
                                "src/V1.sql": "-- bar_table comes later\nSELECT 1; -- bar_table\n",
                                "run.sh": "# FooService\n"}).rows()
        self.assertIsNone(rows[1]["gap_full"])

    def test_a_later_spec_name_does_not_move_an_earlier_gap(self):
        self.repo.merge({"src/Foo.java": "class FooService { BazClient baz; }\n"})
        before = self.repo.rows()[1]["gap_full"]
        self.repo.merge({"specs/day-01-x.md": DAY + "It calls `BazClient`.\n"})
        self.assertEqual(self.repo.rows()[1]["gap_full"], before)

    def test_a_file_under_kit_is_tooling_and_not_code_the_gap_reads(self):
        self.repo.merge({"src/Foo.java": "class FooService {}\n"})
        rows = self.repo.merge({"kit/page/data.json": '{"names": "FooService bar_table bar_table bar_table"}\n'}).rows()
        self.assertEqual(rows[2]["gap_full"], rows[1]["gap_full"])
        self.assertEqual(rows[2]["work"], dict(spec=0, context=0, prod=0, test=0, tooling=1))

    def test_each_merge_counts_its_own_lines_by_box_and_a_move_only_what_changed(self):
        rows = self.repo.merge({"src/test/FooTest.java": "a\nb\n", "CLAUDE.md": "c\n", "specs/day-01-x.md": DAY + "d\n",
                                "scripts/x.py": "e\n", "package-lock.json": "{}\n", "src/Big.java": "f\ng\nh\ni\n"}).rows()
        self.assertEqual(rows[1]["work"], dict(spec=1, context=1, prod=4, test=2, tooling=1))
        os.remove(os.path.join(self.repo.path, "src", "Big.java"))
        rows = self.repo.merge({"src/test/BigTest.java": "f\ng\nh\ni\nj\n"}).rows()
        self.assertEqual(rows[2]["work"], dict(spec=0, context=0, prod=0, test=1, tooling=0))

    def test_fixture_lines_stay_in_the_tests_box_and_are_counted_apart_for_the_ratio(self):
        rows = self.repo.merge({"tests/fixtures/expected/out.txt": "a\nb\nc\n", "tests/fixtures/make_repo.py": "d\n",
                                "tests/test_x.py": "e\nf\n", "bearing/x.py": "g\n"}).rows()
        self.assertEqual(rows[1]["work"], dict(spec=0, context=0, prod=1, test=6, tooling=0))
        self.assertEqual(rows[1]["test_fixtures"], 4)
        self.assertEqual(rows[0]["test_fixtures"], 0)

    def test_a_file_goes_in_the_first_box_its_path_matches(self):
        for path, box in [("plan.md", "spec"), ("specs/README.md", "spec"), ("specs/day-01-test-harness.md", "spec"),
                          ("CLAUDE.md", "context"), ("backend/app/README.md", "context"), (".claude/agents/x.md", "context"),
                          (".claude/settings.json", "context"), ("docs/workflow.svg", "context"),
                          ("backend/app/src/test/java/x/support/Harness.java", "test"), ("services/job/src/FooIT.java", "test"),
                          ("scripts/test_spec_drift.py", "test"), ("data/tests/conftest.py", "test"), ("web/a.spec.ts", "test"),
                          ("scripts/spec-drift.py", "tooling"), (".github/workflows/ci.yml", "tooling"),
                          ("docs/dashboard/dashboard.js", "tooling"), ("backend/app/src/main/java/x/Latest.java", "prod"),
                          ("app/count.py", "prod"), ("tests/contract/test_word_rule.py", "test"),
                          ("experiments/jev/e1/build.py", "tooling"), ("experiments/jev/e1/test_build.py", "test"),
                          ("docker-compose.yml", "prod"), ("docs/dashboard/token-usage.json", None),
                          ("docs/dashboard/deployment.json", None),
                          ("frontend/package-lock.json", None), ("screenshots/a.png", None)]:
            self.assertEqual(sd.work_kind(path), box, path)
        self.assertEqual(sd.renamed_to("backend/{app => job}/src/X.java"), "backend/job/src/X.java")
        self.assertEqual(sd.renamed_to("src/{ => job}/X.java"), "src/job/X.java")
        self.assertEqual(sd.renamed_to("a.txt => b/a.txt"), "b/a.txt")

    def test_a_pr_records_a_break_in_one_fixed_line_and_nothing_else(self):
        checklist = "- [x] Spec changes only: each check has been seen to fail (see `specs/README.md`)\n"
        for body, state in [("broken: `ISSUER` back → `AuthIT` failed 2 of 8\n", "recorded"),
                            ("- broken: the guard removed -> expected: 401 but was: 200\n", "recorded"),
                            ("broken: none → this track adds no test\nbroken: the sort reversed → 3 red\n", "recorded"),
                            ("broken: none → this track adds no test\n", "none"),
                            # The free text the regexes read before #310 is not the line.
                            ("**Broken on purpose:** `ISSUER` back. It fails 2 of 8.\n", "silent"),
                            ("Seen red, broken: the guard removed → it failed\n", "silent"),
                            ("broken: the guard removed\n", "silent"),
                            ("", "silent"), (None, "silent")]:
            self.assertEqual(sd.break_state(body and body + checklist, 310), state, body)
        self.assertEqual(sd.break_state(checklist, 310), "silent")
        self.addCleanup(setall, "BREAK_LINE_FROM_PR", sd.BREAK_LINE_FROM_PR)
        setall("BREAK_LINE_FROM_PR", 310)  # the source project asked for the line from #310
        self.assertEqual(sd.break_state("broken: the guard removed → 401\n", 309), "not measured")

    def test_a_new_project_reads_the_break_line_from_its_first_pr(self):
        self.assertEqual(sd.BREAK_LINE_FROM_PR, 0)
        self.assertEqual(sd.break_state("broken: the guard removed → 401\n", 1), "recorded")
        self.assertEqual(sd.break_state("No break.\n", 7), "silent")

    def test_ci_counts_each_pushed_commit_once_and_only_pull_request_runs(self):
        run = lambda sha, result, flow="PR checks", event="pull_request": dict(
            headBranch="day-01/track-a-x", headSha=sha, conclusion=result, workflowName=flow, event=event)
        runs = [run("a", "failure"), run("a", "failure", "Backend CI/CD"), run("a", "success", "Dashboard"),
                run("b", "success"), run("b", "cancelled", "Backend CI/CD"), run("c", "failure", event="push")]
        self.assertEqual(sd.ci_pushes(runs), {"day-01/track-a-x": (2, 1, ["Backend CI/CD", "PR checks"])})

    def test_the_clock_reads_each_merged_prs_opening_merge_and_the_span_of_its_checks(self):
        pr = lambda n, title, branch, state="MERGED": dict(number=n, title=title, headRefName=branch, state=state, body="",
                                                          createdAt=f"2026-01-02T09:{n}0:00Z", mergedAt=f"2026-01-02T10:{n}0:00Z" if state == "MERGED" else None)
        prs = {1: pr(1, "Day 02 track A: x", "day-02/track-a-x"), 2: pr(2, "Day 02 track B: y", "day-02/track-b-y", "OPEN"), 3: pr(3, "Faster tests", "tooling/faster")}
        run = lambda branch, sha, result, start, end, event="pull_request": dict(headBranch=branch, headSha=sha, conclusion=result, workflowName="PR checks",
                                                                                event=event, createdAt=f"2026-01-02T{start}:00Z", updatedAt=f"2026-01-02T{end}:00Z")
        runs = [run("day-02/track-a-x", "a", "failure", "09:11", "09:15"), run("day-02/track-a-x", "a", "success", "09:12", "09:16"),
                run("day-02/track-a-x", "b", "success", "09:40", "09:44"),
                run("day-02/track-a-x", "c", "success", "09:50", "09:52", event="push"), run("day-02/track-b-y", "d", "success", "09:21", "09:25")]
        got = sd.clock(prs, runs, sessions=[])
        self.assertEqual(got["sessions"], [])
        self.assertEqual([(p["number"], p["day"], p["kind"], p["branch"], p["opened"], p["merged"]) for p in got["prs"]],
                         [(1, 2, "code", "day-02/track-a-x", "2026-01-02T09:10:00Z", "2026-01-02T10:10:00Z"),
                          (3, None, "other", "tooling/faster", "2026-01-02T09:30:00Z", "2026-01-02T10:30:00Z")])
        # The checks span the first start to the last end of the pull request's own runs, a push run left out.
        # And the stretches they were running in: two runs of one push that overlap are one stretch, and the 24
        # minutes between the two pushes are in neither. Three workflow runs, two pushes.
        self.assertEqual([p["checks"] for p in got["prs"]], [dict(
            start="2026-01-02T09:11:00Z", end="2026-01-02T09:44:00Z", runs=3, failed=1, pushes=2,
            spans=[["2026-01-02T09:11:00Z", "2026-01-02T09:16:00Z", 1], ["2026-01-02T09:40:00Z", "2026-01-02T09:44:00Z", 0]]), None])
        # Without the sessions file, no sessions; nothing fails.
        self.assertIsInstance(sd.clock({}, [])["sessions"], list)

    def test_the_clock_gives_area_work_no_day_even_when_its_branch_names_one(self):
        pr = dict(number=33, title="Status", headRefName="specs/status-day-05", state="MERGED", body="",
                  createdAt="2026-01-02T09:00:00Z", mergedAt="2026-01-02T10:00:00Z")
        self.assertIsNone(sd.clock({33: pr}, [], sessions=[])["prs"][0]["day"])

    def test_the_page_is_given_when_the_transcripts_were_last_counted_or_nothing(self):
        with DataBranch({"sessions.json": "[]\n"}):
            self.assertIsNone(sd.counted())  # before the first count reached the branch
        with DataBranch({"counted.json": '{"at": "2026-11-08T20:00:00+01:00"}\n'}):
            self.assertEqual(sd.counted(), dict(at="2026-11-08T20:00:00+01:00"))

    def test_a_gh_list_as_long_as_its_limit_is_refused(self):
        real = sd.run
        try:
            setall("run", lambda *args: "[" + ",".join(["{}"] * n) + "]")
            n = 2
            self.assertEqual(len(sd.gh_list(3, "pr", "list")), 2)
            n = 3
            with self.assertRaisesRegex(SystemExit, "pr list returned its limit of 3"):
                sd.gh_list(3, "pr", "list")
        finally:
            setall("run", real)

    def test_a_gh_list_of_a_thousand_is_refused_under_a_larger_limit(self):
        # GitHub gives at most 1,000 for a filtered run list, so 1,000 may be cut whatever the limit.
        real = sd.run
        try:
            setall("run", lambda *args: "[" + ",".join(["{}"] * 1000) + "]")
            with self.assertRaisesRegex(SystemExit, "run list returned 1000"):
                sd.gh_list(5000, "run", "list")
            setall("run", lambda *args: "[" + ",".join(["{}"] * 999) + "]")
            self.assertEqual(len(sd.gh_list(5000, "run", "list")), 999)
        finally:
            setall("run", real)

    def test_an_infra_run_whose_artifact_does_not_download_is_skipped(self):
        def fake(*args):
            if args[2] == "list":
                self.assertEqual(args[4], "infra.yaml")
                return json.dumps([dict(databaseId=2, headSha="b" * 40, conclusion="failure",
                                        createdAt="2026-10-08T10:00:00Z", url="u2"),
                                   dict(databaseId=1, headSha="a" * 40, conclusion="success",
                                        createdAt="2026-10-07T10:00:00Z", url="u1")])
            if args[3] == "2":
                raise subprocess.CalledProcessError(1, args)
            with open(os.path.join(args[-1], "infra-summary.json"), "w", encoding="utf-8") as f:
                json.dump({"criteria": {"C32.2": "pass"}}, f)
            return ""
        real = sd.run
        try:
            setall("run", fake)
            got = sd.infra("infra.yaml")
        finally:
            setall("run", real)
        self.assertEqual([r["sha"] for r in got["runs"]], ["bbbbbbb", "aaaaaaa"])
        self.assertEqual(got["latest"], dict(sha="aaaaaaa", conclusion="success", date="2026-10-07", url="u1",
                                             summary={"criteria": {"C32.2": "pass"}}))

    def test_with_no_github_remote_there_are_no_prs_and_a_note_says_so(self):
        def fake(*args):
            if args[1:3] == ("repo", "view"):
                if remote:
                    return "me"
                raise subprocess.CalledProcessError(1, args, stderr="no git remotes found")
            if args[1:3] == ("pr", "list"):
                return json.dumps([dict(number=1, author=dict(login="me")), dict(number=2, author=dict(login="x"))])
            return "[]"
        real = sd.run
        try:
            setall("run", fake)
            remote = False
            self.assertEqual(sd.github(), ([], [], sd.NO_REMOTE))
            remote = True
            self.assertEqual(sd.github(), ([dict(number=1, author=dict(login="me"))], [], None))
        finally:
            setall("run", real)
        self.assertTrue(sd.NO_REMOTE.startswith("No GitHub remote"))

    def test_the_deployment_is_its_checks_and_none_without_the_file(self):
        real = sd.PAGE
        setall("PAGE", tempfile.mkdtemp())
        try:
            self.assertIsNone(sd.deployment())
            checks = [dict(criterion="C35.16", name="the site answers", ok=True, detail="200", at="2026-10-10T09:00:00Z"),
                      dict(criterion="C35.17", name="login sets the cookie", ok=False, detail="no Secure",
                           at="2026-10-10T09:01:00Z")]
            with open(os.path.join(sd.PAGE, "deployment.json"), "w", encoding="utf-8") as f:
                json.dump(dict(domain="example.test", checkedAt="2026-10-10T09:01:00Z", checks=checks), f)
            self.assertEqual(sd.deployment()["checks"], checks)
        finally:
            shutil.rmtree(sd.PAGE)
            setall("PAGE", real)

    def test_the_data_names_the_commit_versions_and_draws_that_made_it(self):
        p = sd.provenance()
        self.assertRegex(p["commit"], "^[0-9a-f]{40}$")
        self.assertEqual((p["numpy"], p["chance_draws"]), (sd.np.__version__, sd.CHANCE_DRAWS))
        self.assertRegex(p["python"], r"^3\.\d+\.\d+")
        self.assertIsInstance(p["script_edited"], bool)

    def test_before_the_first_commit_the_data_names_no_commit(self):
        # a pilot's first run: git rev-parse HEAD exited 128 in a repository with no commit yet.
        empty = Repo()
        self.addCleanup(empty.close)
        script = os.path.join(empty.path, "spec-drift.py")
        open(script, "w").close()
        self.addCleanup(setattr, sd, "__file__", sd.__file__)
        sd.__file__ = script
        p = empty.inside(lambda blobs: sd.provenance())
        self.assertEqual((p["commit"], p["script_edited"]), (None, True))

    def test_an_edit_to_a_module_of_the_script_is_the_script_edited(self):
        # The script is split into modules beside it: an edit to one of them is an edit to it.
        repo = Repo().merge({name: "" for name in sd.SOURCES})
        self.addCleanup(repo.close)
        self.addCleanup(setattr, sd, "__file__", sd.__file__)
        sd.__file__ = os.path.join(repo.path, "spec-drift.py")
        self.assertFalse(repo.inside(lambda blobs: sd.provenance())["script_edited"])
        with open(os.path.join(repo.path, sd.SOURCES[-1]), "w", encoding="utf-8") as f:
            f.write("# edited\n")
        self.assertTrue(repo.inside(lambda blobs: sd.provenance())["script_edited"])

    def test_the_spec_rules_and_template_are_not_specs_for_the_vocabulary(self):
        # a pilot: 5 of the 8 names "missing" from its code were the source project's examples there.
        before = self.repo.inside(lambda blobs: sd.trajectory([dict(s) for s in self.repo.snaps], blobs)[2])
        self.repo.merge({"specs/README.md": "Name `AccountDeletionIT` and `savedCount`.\n",
                         "specs/_template.md": "- [ ] C28.1 **new** — `SameSite` is set.\n"})
        rows, _, vocab = self.repo.inside(lambda blobs: sd.trajectory([dict(s) for s in self.repo.snaps], blobs)[:3])
        self.assertEqual(vocab, before)
        self.assertEqual(rows[-1]["name_coverage"], rows[0]["name_coverage"])

    def test_a_day_that_runs_later_is_not_reached_by_a_higher_number(self):
        self.repo.merge({"specs/day-17-x.md": "Day 17 adds `LaterThing`.\n",
                         "specs/day-38-x.md": "Day 38 adds `PlatformThing`.\n"})
        self.repo.merge({"src/P.java": "class PlatformThing { FooService foo; }\n"})
        self.repo.snaps[-1]["branch"] = "day-38/track-a-x"
        by_number = self.repo.rows()[-1]["coverage"]
        rows, files = self.repo.inside(lambda blobs: sd.trajectory([dict(s) for s in self.repo.snaps], blobs,
                                                                   [1, 38, 17])[:2])
        self.assertEqual((by_number, rows[-1]["coverage"]), (0.667, 1.0))  # LaterThing is Day 17's
        self.assertEqual(files, ["plan.md", "specs/day-01-x.md", "specs/day-38-x.md", "specs/day-17-x.md"])
        self.repo.merge({"src/L.java": "class LaterThing {}\n"})
        self.repo.snaps[-1]["branch"] = "day-17/track-a-y"
        rows = self.repo.inside(lambda blobs: sd.trajectory([dict(s) for s in self.repo.snaps], blobs, [1, 38, 17])[0])
        self.assertEqual(rows[-1]["day"], 17)  # after 38 in the run order, though lower in number

    def test_a_wildcard_prefix_is_no_name_the_code_could_miss(self):
        self.assertFalse(sd.code_like("aws_ecs_"))
        self.assertFalse(sd.code_like("check_c34_"))
        self.assertTrue(sd.code_like("aws_ecs_service"))
        self.repo.merge({"src/Foo.java": "class FooService { FooService f; }\n"})
        rows = self.repo.merge({"specs/day-02-y.md": "It writes `aws_ecs_*`.\n", "src/Cloud.java": "aws_ecs_service e;\n"}).rows()
        self.assertEqual((rows[1]["name_coverage"], rows[2]["name_coverage"]), (0.5, 0.5))  # bar_table still missing

    def test_a_name_the_code_had_and_lost_is_retired_and_still_a_miss(self):
        self.repo.merge({"src/Foo.java": "class FooService { }\n"})
        rows = self.repo.merge({"src/Foo.java": None}).rows()
        self.assertEqual([r["names_retired"] for r in rows], [0, 0, 1])  # bar_table was never in the code
        self.assertEqual((rows[1]["name_coverage"], rows[2]["name_coverage"]), (0.5, 0.0))

    def test_code_in_the_spec_proportions_sits_below_chance(self):
        rows = self.repo.merge({"src/Foo.java": "class FooService { FooService f; bar_table b; }\n"}).rows()
        self.assertEqual((rows[0]["gap_full"], rows[0]["gap_chance"]), (None, None))  # no code: no angle
        self.assertEqual(rows[1]["gap_full"], 0.0)  # FooService twice and bar_table once, as the specs
        self.assertGreater(rows[1]["gap_chance"], 10.0)
        lo, hi = rows[1]["gap_chance_band"]
        self.assertTrue(lo <= rows[1]["gap_chance"] <= hi)
        rows = self.repo.merge({"src/Foo.java": "class FooService { bar_table a; bar_table b; }\n"}).rows()
        self.assertGreater(rows[2]["gap_full"], rows[1]["gap_full"])
        self.assertEqual(rows[2]["gap_chance"], rows[1]["gap_chance"])  # the same counts, shuffled

CRITERIA = """- [x] **hold** — Refused: `contract/FooIT` passes. Broken on purpose: the check removed.
      #2: `FooIT.refuses`.
      broken: the guard removed → `expected: 401 but was: 200`
- [x] **new** — Saved in `BarIT`, or a case added to `FooIT`. Red today: no table.
      #3: a case in `FooIT.saves`.
- [ ] **new** — Not started.
"""


class EvidenceTest(unittest.TestCase):
    """A closed day's evidence: what each criterion cites, and whether its tests are still there."""

    def setUp(self):
        # The day's PR is #1, the second commit; later commits stand for later days.
        self.repo = Repo().merge({"plan.md": PLAN}).merge(
            {"src/FooIT.java": "class FooIT { void refuses() {} void saves() {} }\n"})

    def tearDown(self):
        self.repo.close()

    def state(self):
        days = [dict(day=1, status="done", prs=[dict(number=1)], evidence=sd.criteria(CRITERIA))]
        return self.repo.inside(lambda blobs: sd.evidence(days, self.repo.snaps, blobs))[0]["evidence"]

    def test_a_criterion_is_read_for_its_kind_prs_tests_and_break(self):
        hold, new, open_ = sd.criteria(CRITERIA)
        self.assertEqual((hold["kind"], hold["ticked"], hold["prs"], hold["red"]), ("hold", True, [2], True))
        self.assertEqual(hold["tests"], ["FooIT", "FooIT.refuses"])
        self.assertEqual((new["red"], open_["ticked"], open_["prs"]), (False, False, []))
        self.assertTrue(hold["claim"].startswith("Refused: `contract/FooIT` passes."), hold["claim"])
        cut = sd.criteria("- [x] **hold** — " + "x" * 130 + " `a/LongNameIT`\n")[0]["claim"]
        self.assertEqual(cut.count("`"), 0)

    def test_a_criterion_from_day_28_on_carries_its_id_and_an_older_one_none(self):
        tagged, untagged = sd.criteria("- [ ] C28.3 **new** — `FooIT` refuses.\n- [ ] **hold** — C28.3 holds.\n")
        self.assertEqual((tagged["id"], tagged["kind"], tagged["claim"]), ("C28.3", "new", "`FooIT` refuses."))
        self.assertEqual((untagged["id"], untagged["claim"]), (None, "C28.3 holds."))

    def test_a_criterion_is_seen_red_only_by_a_broken_line_with_what_it_reported(self):
        red = lambda text: sd.criteria(f"- [x] C28.1 **hold** — X. #2: `FooIT`.\n      {text}\n")[0]["red"]
        self.assertTrue(red("broken: the guard removed → `FooIT` failed 1 of 3"))
        self.assertTrue(red("broken: the sort reversed -> 31 of 31 red"))
        # A baseline, a break planned but not reported, a `none`, or the free text the regexes read
        # before #310 is not a break seen red.
        for text in ["Red today: the route does not exist.", "broken: the guard removed",
                     "broken: none → the grep is the check",
                     "Broken on purpose in #74: the auth tests reported `Tests run: 49, Failures: 8`.",
                     "Red again with the migration's revoke removed. broken: x → y"]:
            self.assertFalse(red(text), text)

    def test_a_criterion_whose_every_break_cites_the_close_was_first_broken_at_the_close(self):
        crit = sd.criteria("- [x] C28.1 **hold** — X.\n      broken: the guard removed → 1 of 3 (#40)\n"
                           "- [x] C28.2 **new** — Y.\n      broken: a → b (#40)\n      broken: c → d (#38)\n"
                           "- [x] C28.3 **new** — Z.\n      broken: a → b, as #38 showed\n"
                           "- [x] C28.4 **new** — W. #40\n      broken: none → the grep is the check\n")
        self.assertEqual([c["broke_in"] for c in crit], [[40], [38, 40], [38], []])
        day = dict(prs=[dict(number=38, kind="code"), dict(number=40, kind="close")], evidence=crit)
        # C28.2 was also broken in its track; C28.3 in a track; C28.4 records no break to judge.
        self.assertEqual(sd.broken_at_close(day), ["C28.1"])
        self.assertEqual(sd.broken_at_close(dict(day, prs=day["prs"][:1])), [])

    def test_a_spec_with_no_criterion_tagged_predates_the_evidence_format(self):
        self.assertFalse(sd.in_evidence_format(sd.criteria("- [x] Login returns 200.\n- [x] Logout clears it.\n")))
        self.assertTrue(sd.in_evidence_format(sd.criteria("- [x] Login returns 200.\n- [x] **hold** — X.\n")))
        self.assertTrue(sd.in_evidence_format(sd.criteria(CRITERIA)))

    def test_a_name_not_in_the_tree_when_the_day_ended_is_not_evidence(self):
        self.assertEqual(self.state()[1]["tests"], {"FooIT": "present", "FooIT.saves": "present"})

    def test_a_test_that_leaves_the_tree_or_can_be_skipped_is_reported(self):
        self.repo.merge({"src/FooIT.java": "@Disabled class FooIT { void refuses() {} }\n"})
        self.assertEqual(self.state()[1]["tests"], {"FooIT": "skippable", "FooIT.saves": "missing"})
        self.repo.merge({"src/FooIT.java": ""})
        self.repo.git("rm", "-q", "src/FooIT.java")
        self.repo.git("commit", "-q", "-m", "gone")
        self.repo.snaps.append(dict(self.repo.snaps[-1], sha=self.repo.git("rev-parse", "--short", "HEAD").strip()))
        self.assertEqual(set(self.state()[0]["tests"].values()), {"missing"})

    def test_a_python_test_is_found_by_its_class_in_any_test_file(self):
        # a pilot: CliTest lives in tests/test_cli.py, and every criterion's tests read "missing".
        self.repo.merge({"tests/test_cli.py": "import unittest\n\n\nclass CliTest(unittest.TestCase):\n"
                                              "    def test_counts(self):\n        pass\n",
                         "tests/test_rule.py": "class RuleTest:\n    @pytest.mark.skipif(True, reason='x')\n"
                                               "    def test_word(self):\n        pass\n",
                         "src/helper.py": "class HelperTest:\n    pass\n"})
        names = {"CliTest", "CliTest.test_counts", "CliTest.test_gone", "RuleTest.test_word", "HelperTest"}
        state = self.repo.inside(lambda blobs: sd.test_state(names, self.repo.snaps[-1]["sha"], blobs))
        self.assertEqual(state, {"CliTest": "present", "CliTest.test_counts": "present",
                                 "CliTest.test_gone": "missing", "RuleTest.test_word": "skippable",
                                 "HelperTest": "missing"})  # src/helper.py is not a test file

    def test_a_python_test_in_a_root_tests_py_is_found(self):
        # python-json-pointer keeps its tests in one tests.py at the root; contests.py is a near miss.
        self.repo.merge({"tests.py": "import unittest\n\n\nclass RootTest(unittest.TestCase):\n"
                                     "    def test_b(self):\n        pass\n",
                         "contests.py": "class ContestTest:\n    def test_c(self):\n        pass\n"})
        names = {"RootTest.test_b", "ContestTest.test_c"}
        state = self.repo.inside(lambda blobs: sd.test_state(names, self.repo.snaps[-1]["sha"], blobs))
        self.assertEqual(state, {"RootTest.test_b": "present", "ContestTest.test_c": "missing"})
        self.assertEqual([sd.work_kind(p) for p in ("tests.py", "test.py", "contests.py")], ["test", "test", "prod"])

    def test_javascript_skip_markers_and_near_misses(self):
        for marker in ("it.skip(", "test.skip(", "describe.skip(", "xit(", "xdescribe(", "it.todo(", "test.todo("):
            self.assertIsNotNone(sd.SKIPPABLE.search(marker), marker)
        for marker in ("omit.skip(", "mytest.skip(", "exit(", "prefixdescribe.skip("):
            self.assertIsNone(sd.SKIPPABLE.search(marker), marker)

    def test_a_python_test_that_calls_skip_test_is_skippable(self):
        # a pilot: a test can skip itself from its body, as CI on a missing tool does.
        self.repo.merge({"tests/test_cli.py": "import unittest\n\n\nclass CliTest(unittest.TestCase):\n"
                                              "    def test_bash(self):\n        self.skipTest('no bash')\n"})
        state = self.repo.inside(lambda blobs: sd.test_state({"CliTest.test_bash"}, self.repo.snaps[-1]["sha"], blobs))
        self.assertEqual(state, {"CliTest.test_bash": "skippable"})

    def test_a_test_moved_under_a_new_name_is_followed_from_the_merge_it_arrives(self):
        # Day 17: SavedJobCountsUnavailableIT left in #174, and its Test arrived in #180. A helper
        # leaving as a test of its name arrives is not a move: only tests are followed.
        self.repo.merge({"src/Stub.java": "class Stub {}\n"})
        self.repo.git("rm", "-q", "src/FooIT.java", "src/Stub.java")
        self.repo.merge({"src/Other.java": "class Other {}\n"})
        self.repo.merge({"svc/FooTest.java": "class FooTest { void refuses() {} void saves() {} }\n",
                         "svc/StubTest.java": "class StubTest {}\n"})
        self.assertEqual(self.repo.inside(lambda blobs: sd.moves(self.repo.snaps)), [(4, "FooIT", "FooTest")])
        self.assertEqual(self.state()[1]["tests"], {"FooIT": "present", "FooIT.saves": "present"})

    def test_a_class_of_the_same_stem_there_before_the_test_left_is_not_where_it_went(self):
        self.repo.merge({"svc/FooTest.java": "class FooTest { void refuses() {} void saves() {} }\n"})
        self.repo.git("rm", "-q", "src/FooIT.java")
        self.repo.merge({"src/Other.java": "class Other {}\n"})
        self.assertEqual(self.repo.inside(lambda blobs: sd.moves(self.repo.snaps)), [])
        self.assertEqual(set(self.state()[1]["tests"].values()), {"missing"})

    def test_a_name_there_before_the_test_left_and_arriving_again_after_is_followed_to_the_later(self):
        # InternalCallsObservedTest: in matching-service from Day 21, then in application-service
        # in #305, after InternalCallsObservedIT left in #296.
        self.repo.merge({"svc/FooTest.java": "class FooTest { void other() {} }\n"})
        self.repo.git("rm", "-q", "src/FooIT.java")
        self.repo.merge({"src/Other.java": "class Other {}\n"})
        self.repo.merge({"app/FooTest.java": "class FooTest { void refuses() {} void saves() {} }\n"})
        self.assertEqual(self.repo.inside(lambda blobs: sd.moves(self.repo.snaps)), [(4, "FooIT", "FooTest")])
        self.assertEqual(self.state()[1]["tests"], {"FooIT": "present", "FooIT.saves": "present"})

    def test_a_move_to_another_stem_is_followed_only_by_the_rename_table(self):
        self.repo.git("rm", "-q", "src/FooIT.java")
        self.repo.merge({"svc/BarTest.java": "class BarTest { void refuses() {} void saves() {} }\n"})
        self.assertEqual(set(self.state()[1]["tests"].values()), {"missing"})
        use_project(self, dict(renamed=[[2, "FooIT", "BarTest"]]))
        self.assertEqual(self.repo.inside(lambda blobs: sd.moves(self.repo.snaps)), [(2, "FooIT", "BarTest")])
        self.assertEqual(self.state()[1]["tests"], {"FooIT": "present", "FooIT.saves": "present"})

    def test_a_test_run_on_a_system_property_is_run_when_ci_passes_it_and_disabled_is_not(self):
        on = '@EnabledIfSystemProperty(named = "harness.gateway", matches = "true")\n'
        self.repo.merge({"src/FooIT.java": on + "class FooIT { void refuses() {} void saves() {} }\n"})
        self.assertEqual(set(self.state()[1]["tests"].values()), {"skippable"})
        self.repo.merge({".github/workflows/ci.yml": "run: ./build verify -Dharness.gateway=false\n"})
        self.assertEqual(set(self.state()[1]["tests"].values()), {"skippable"})
        self.repo.merge({".github/workflows/ci.yml": "run: ./build verify -pl app -am -Dharness.gateway=true\n"})
        self.assertEqual(set(self.state()[1]["tests"].values()), {"present"})
        self.repo.merge({"src/FooIT.java": on + "@Disabled class FooIT { void refuses() {} void saves() {} }\n"})
        self.assertEqual(set(self.state()[1]["tests"].values()), {"skippable"})

    def test_the_history_counts_a_moved_test_missing_until_it_arrives(self):
        days = [dict(day=1, status="done", prs=[dict(number=1)], evidence=sd.criteria(CRITERIA))]
        self.repo.git("rm", "-q", "src/FooIT.java")
        self.repo.merge({"src/Other.java": "class Other {}\n"})
        self.repo.merge({"svc/FooTest.java": "class FooTest { void refuses() {} void saves() {} }\n"})
        rows = [{} for _ in self.repo.snaps]
        self.repo.inside(lambda blobs: sd.evidence_history(rows, sd.evidence(days, self.repo.snaps, blobs),
                                                           self.repo.snaps, blobs))
        self.assertEqual([r["evidence"] for r in rows][1:], [
            dict(present=3, skippable=0, missing=0, retired=0),
            dict(present=0, skippable=0, missing=3, retired=0),
            dict(present=3, skippable=0, missing=0, retired=0)])


    def test_the_history_starts_when_the_day_ends_and_shows_the_merge_a_test_left(self):
        self.repo.merge({"src/FooIT.java": "class FooIT { void refuses() {} }\n"})
        days = [dict(day=1, status="done", prs=[dict(number=1)], evidence=sd.criteria(CRITERIA))]
        rows = [{} for _ in self.repo.snaps]

        def history(blobs):
            sd.evidence_history(rows, sd.evidence(days, self.repo.snaps, blobs), self.repo.snaps, blobs)
        self.repo.inside(history)
        self.assertEqual([r["evidence"] for r in rows], [
            None,
            dict(present=3, skippable=0, missing=0, retired=0),
            dict(present=2, skippable=0, missing=1, retired=0)])

    def history_after_removal(self, spec):
        """Day 1's tests, then a day 2 merge that removes FooIT and writes day 2's spec, as `spec`."""
        days = [dict(day=1, status="done", prs=[dict(number=1)], evidence=sd.criteria(CRITERIA)),
                dict(day=2, file="specs/day-02-y.md", status="done", prs=[dict(number=2)], evidence=[])]
        self.repo.merge({"src/FooIT.java": None, "specs/day-02-y.md": spec})
        self.repo.snaps[-1]["branch"] = "day-02/track-a-x"
        rows = [{} for _ in self.repo.snaps]
        self.repo.inside(lambda blobs: sd.evidence_history(rows, sd.evidence(days, self.repo.snaps, blobs),
                                                           self.repo.snaps, blobs))
        return rows, days

    def test_a_test_a_later_days_spec_names_as_removed_is_retired_not_missing(self):
        rows, days = self.history_after_removal("# Day 02\n\nIt removes `FooIT`.\n")
        self.assertEqual(rows[-1]["evidence"], dict(present=0, skippable=0, missing=0, retired=3))
        self.assertEqual({v for c in days[0]["evidence"] for v in c["tests"].values()}, {"retired"})

    def test_a_test_gone_that_no_later_spec_names_stays_missing(self):
        rows, days = self.history_after_removal("# Day 02\n\nIt removes the rest.\n")
        self.assertEqual(rows[-1]["evidence"], dict(present=0, skippable=0, missing=3, retired=0))
        self.assertEqual({v for c in days[0]["evidence"] for v in c["tests"].values()}, {"missing"})


REMOVALS = """## Acceptance criteria
- [x] **new** — `grep -rn "OldThing\\|old_table" --include=*.java .`
      returns nothing. Red today: two.

## Verify
```bash
cd core
grep -rn "TODO day-01" */src/ || echo "clean"
grep -rn "kept" app/ | wc -l
```

## Notes
- `grep -rn "NotACheck"` returns nothing, but a note is not a check.
"""


class RemovalTest(unittest.TestCase):
    """A day's greps that must print nothing, run at every merge from the day's end."""

    def setUp(self):
        use_project(self, PROJECT)

    def test_the_checks_are_the_criteria_and_verify_greps_that_expect_nothing(self):
        self.assertEqual(sd.removal_checks(REMOVALS), ['grep -rn "OldThing\\|old_table" --include=*.java .',
                                                       'grep -rn "TODO day-01" */src/'])

    def test_a_basic_regex_alternation_is_an_alternation_and_a_bare_bar_is_literal(self):
        rx, paths, include = sd.grep_rule('grep -rn "OldThing\\|old_table" --include=*.java .')
        self.assertEqual((bool(rx.search("old_table")), paths, include), (True, ["."], "*.java"))
        self.assertFalse(sd.grep_rule('grep -rn "a|b" x/')[0].search("a"))
        self.assertTrue(sd.grep_rule('grep -rnE "a|b" x/')[0].search("a"))
        self.assertIsNone(sd.grep_rule('grep -rn "x" a/ | grep -v b'))

    def test_a_check_counts_lines_in_its_scope_from_the_day_it_ended(self):
        repo = Repo().merge({"core/app/A.java": "OldThing a;\nold_table b;\n", "core/app/B.txt": "OldThing\n",
                             "other/C.java": "OldThing c;\n", "core/app/src/D.java": "",
                             "core/pom.txt": "TODO day-01\n"})
        repo.merge({"core/app/A.java": "class A {}\n"})
        repo.merge({"core/app/A.java": "class A { OldThing back; }\n", "core/app/src/D.java": "// TODO day-01\n"})
        def run(ended_at):
            days = [dict(day=1, ended_at=ended_at, removal_checks=sd.removal_checks(REMOVALS))]
            return [(c["base"], c["hits"]) for c in repo.inside(lambda blobs: sd.removal_history(days, repo.snaps, blobs))]
        try:
            # B.txt is not *.java, other/ is not under core/, and pom.txt is not under */src/.
            self.assertEqual(run(0), [("core", [2, 0, 1]), ("core", [0, 0, 1])])
            self.assertEqual(run(1), [("core", [0, 1]), ("core", [0, 1])])
        finally:
            repo.close()

    def test_a_path_follows_a_move_and_a_parent_of_it_also_reads_where_it_went(self):
        moves = [("backend/jobs", "services/orders-service"), ("backend", "services/account-service")]
        self.assertEqual(sd.follow("backend/jobs/src", moves), ["services/orders-service/src"])
        self.assertEqual(sd.follow("backend/docs", moves), ["services/account-service/docs"])
        self.assertEqual(sd.follow("backend/*/src/main", moves),
                         ["services/orders-service/src/main", "services/account-service/*/src/main"])
        self.assertEqual(sd.follow("backend", moves[:1]), ["services/orders-service", "backend"])
        self.assertEqual(sd.follow("docker-compose.yml", moves), ["docker-compose.yml"])

    def test_the_project_files_moves_follow_moved_docs_on_to_docs_system(self):
        moves = [(old, new) for _, old, new in sd.MOVED]
        self.assertEqual(sd.follow("core/docs", moves), ["docs/system"])
        self.assertEqual(sd.follow("core/docs/api.md", moves), ["docs/system/api.md"])

    def test_the_project_files_moves_follow_a_lifted_app_to_the_service_root(self):
        moves = [(old, new) for _, old, new in sd.MOVED]
        self.assertEqual(sd.follow("core/app/src/main/java", moves), ["services/account-service/src/main/java"])
        self.assertEqual(sd.follow("services/account-service/app/src", moves), ["services/account-service/src"])

    def test_a_check_reads_moved_code_counts_its_files_and_lists_its_lines_on_the_last_merge(self):
        repo = Repo().merge({"core/stock/src/A.java": "class A {}\n", "core/app/src/B.java": "class B {}\n"})
        repo.merge({"core/stock/src/A.java": None, "services/stock-service/src/A.java": "// TODO day-01 here\n"})
        repo.merge({"core/app/src/B.java": None, "services/stock-service/src/A.java": "class A {}\n"})
        def run(moved):
            days = [dict(day=1, ended_at=0, removal_checks=sd.removal_checks(REMOVALS))]
            return repo.inside(lambda blobs: sd.removal_history(days, repo.snaps, blobs, moved))[1]
        try:
            # Merge 2's tree has no core/ left: unfollowed, the check reads nothing and passes.
            still = run([])
            self.assertEqual((still["files"], still["hits"]), ([2, 1, 0], [0, 0, 0]))
            followed = run([(1, "core/stock", "services/stock-service")])
            self.assertEqual((followed["files"], followed["hits"], followed["found"]), ([2, 2, 1], [0, 1, 0], []))
            repo.merge({"services/stock-service/src/A.java": "x\n// TODO day-01 again\n"})
            self.assertEqual(run([(1, "core/stock", "services/stock-service")])["found"],
                             [dict(path="services/stock-service/src/A.java", line=2, text="// TODO day-01 again")])
        finally:
            repo.close()


DEFECT_NOTES = {
    21: """## Notes
- **Defect** D21.1 — found: auditor · cause: spec · made: Day 21 · C21.3 counted the wrong files.
- **Defect** D21.2 — found: review · cause: implementation · made: Day 21 · the grep
  matched comments.
- **Defect** — found: close · cause: process · made: Day 21 · an older line, with no ID.
""",
    28: """## Notes
- **Defect** D28.1 — found: close · cause: spec · made: Day 28 · same-as: D21.2 · the grep
  matched comments again.
- **Defect** D28.2 — found: review · cause: spec · made: Day 28 ·
  same-as: D21.1 · counted the wrong files again.
- **Defect** D28.3 — found: self · cause: spec · made: Day 28 · same-as: D21.9 · no such defect.
- **Defect** D27.4 — found: self · cause: spec · made: Day 28 · an ID of another day.
- **Defect** D28.5 — found: self · cause: spec · made: Day 28 · same-as: D30.1 · a later one.
- **Defect** D28.6 — found: self · cause: spec · made: Day 28 · same-as: 21.2 · no D.
- **Defect** D28 — found: self · cause: spec · made: Day 28 · no number.
- **Defect** D28.8 — found: self · cause: spec · made: Day 28 · the text · same-as: D21.1 · is text.
- A line citing D21.2 · same-as: D21.1 is not a Defect line.
""",
    30: "## Notes\n- **Defect** D30.1 — found: self · cause: spec · made: Day 30 · later.\n",
}


class GateReportTest(unittest.TestCase):
    """Each gate's Defect lines by cause, or the hooks' refusals, beside what gates.json says it cost."""

    def test_each_gate_joins_its_found_lines_by_cause_with_its_runs_and_cost(self):
        days = [dict(day=1, defects=sd.defect_lines(
            "- **Defect** D1.1 — found: auditor (spec-auditor) · cause: spec · made: Day 1 · a.\n"
            "- **Defect** D1.2 — found: seen red · cause: implementation · made: Day 1 · b.\n"
            "- **Defect** D1.3 — found: break on purpose · cause: Process · made: Day 1 · c.\n"
            "- **Defect** D1.4 — found: evidence replay · cause: environment · made: Day 1 · d.\n"
            "- **Defect** D1.5 — found: review · cause: spec · made: Day 1 · e.\n"
            "- **Defect** D1.6 — found: auditor · cause: tooling · made: Day 1 · f.\n", 1))]
        spent = [dict(date="2026-11-05", day=1, gate="break on purpose", runs=2, replies=3, context=100, output=10, cost=0.5),
                 dict(date="2026-11-06", day=None, gate="break on purpose", runs=1, replies=2, context=50, output=5, cost=0.254),
                 dict(date="2026-11-06", day=None, gate="hooks", runs=1, replies=2, context=7, output=1, cost=0.01)]
        refused = [dict(date="2026-11-05", guard="read-guard", refused=2), dict(date="2026-11-06", guard="step-guard", refused=1)]
        r = sd.gate_report(days, spent, refused)
        self.assertEqual((r["defects"], r["elsewhere"]), (6, 1))
        self.assertEqual([(g["gate"], g["defects"], g["refused"], [n for n in g["causes"].values()], g["runs"], g["replies"], g["cost"])
                          for g in r["gates"]], [
            ("auditors", 2, None, [1, 0, 0, 0, 1], 0, 0, 0),
            ("seen red", 1, None, [0, 1, 0, 0, 0], 0, 0, 0),
            ("break on purpose", 1, None, [0, 0, 1, 0, 0], 3, 5, 0.75),
            ("evidence replay", 1, None, [0, 0, 0, 1, 0], 0, 0, 0),
            ("hooks", 0, 3, [0, 0, 0, 0, 0], 1, 2, 0.01)])
        # Before refusals.json exists, the hooks' count is not known, not zero.
        self.assertIsNone(sd.gate_report(days, spent, [])["gates"][-1]["refused"])
        # The console line says so, and reports no refusal it did not count.
        self.assertEqual(sd.gate_line(sd.gate_report(days, spent, [])["gates"][-1]),
                         "gate hooks: no refusal log yet, 1 runs, $0.01")
        self.assertEqual(sd.gate_line(r["gates"][-1]), "gate hooks: 3 refused, 1 runs, $0.01")
        self.assertEqual(sd.gate_line(r["gates"][0]), "gate auditors: 2 defects, 0 runs, $0.00")


class DefectTest(unittest.TestCase):
    """Defect lines' IDs, and the ones that repeat an earlier defect (specs/README.md)."""

    def setUp(self):
        self.days = [dict(day=d, defects=sd.defect_lines(t, d)) for d, t in DEFECT_NOTES.items()]

    def test_each_defect_line_gives_its_id_and_same_as_and_no_other_line_does(self):
        self.assertEqual([[(x["id"], x["same_as"]) for x in d["defects"]] for d in self.days], [
            [("D21.1", None), ("D21.2", None), (None, None)],
            [("D28.1", "D21.2"), ("D28.2", "D21.1"), ("D28.3", "D21.9"), ("D27.4", None), ("D28.5", "D30.1"),
             ("D28.6", "21.2"), ("D28", None), ("D28.8", None)],
            [("D30.1", None)]])

    def test_a_recurrence_names_an_earlier_defect_and_every_bad_id_is_reported(self):
        self.assertEqual(sd.recurrence(self.days), dict(
            defects=12, with_id=9,
            recurrences=[dict(id="D28.1", same_as="D21.2"), dict(id="D28.2", same_as="D21.1")],
            problems=["D28.3: same-as: D21.9 names no Defect line",
                      "Day 28: Defect ID D27.4 is not D28.<n>",
                      "D28.5: same-as: D30.1 is not an earlier defect",
                      "D28.6: same-as: 21.2 is not an ID like D21.2",
                      "Day 28: Defect ID D28 is not D28.<n>"]))

    def test_a_defect_line_keeps_the_day_it_was_made_as_written(self):
        lines = sd.defect_lines(
            "- **Defect** D6.1 — found: dashboard · cause: spec · made: Day 04 · C04.14 restated a hold.\n"
            "- **Defect** D6.2 — found: self · cause: implementation · made: none · same-as: D6.1 · a tool.\n"
            "- **Defect** D6.3 — found: self · no made: field before the text.\n", 6)
        self.assertEqual([x["made"] for x in lines], ["Day 04", "none", None])

    def test_an_id_used_twice_or_a_same_as_with_no_id_is_reported(self):
        days = [dict(day=5, defects=sd.defect_lines(
            "- **Defect** D5.1 — found: self · x.\n- **Defect** D5.1 — found: self · y.\n"
            "- **Defect** — same-as: D5.1 · found: self · z.\n", 5))]
        self.assertEqual(sd.recurrence(days), dict(defects=3, with_id=1, recurrences=[], problems=[
            "Day 5: Defect ID D5.1 is used twice", "Day 5: a Defect line with same-as: D5.1 has no ID"]))


class HandOffTest(unittest.TestCase):
    """What finished days leave to days not yet run, and whether the receiving spec took it."""

    def test_an_excerpt_ends_at_a_word_and_outside_a_code_span(self):
        self.assertEqual(sd.excerpt("alpha  beta\n gamma", 40), "alpha beta gamma")
        self.assertEqual(sd.excerpt("alpha beta gamma", 12), "alpha beta…")
        self.assertEqual(sd.excerpt("see `foo bar baz` now", 12), "see…")

    def test_the_days_a_sentence_names(self):
        self.assertEqual(sd.days_named("Day 17 adds it; Days 18-19 and Days 19, 21 and 24 build theirs"),
                         {17, 18, 19, 21, 24})
        self.assertEqual(sd.days_named("Days 26–28, or Day 30"), {26, 27, 28, 30})

    def test_a_hand_off_is_picked_up_by_the_spec_that_names_its_day_or_its_file(self):
        repo = Repo().merge({
            "specs/day-01-a.md": "## Notes\n- For Day 03: the key.\n- Day 02's findings for Day 04 are there.\n"
                                 "- Day 05 has nothing from this day.\n",
            "specs/day-02-b.md": "# Day 02\n",
            "specs/day-03-c.md": "# Day 03\n\nFrom Day 01: the key.\n",
            "specs/day-04-d.md": "# Day 04\n\nFrom Day 02.\n",
            "specs/day-05-e.md": "# Day 05\n\nIt reads `Foo`.\n",
            "src/Foo.java": "// Day 05 moves this.\nclass Foo {} // Day 05\n",
            "src/Bar.java": "/* Day 04 deletes this. */\n",
        })
        days = [dict(day=n, file=f"specs/day-0{n}-{c}.md", status="done" if n < 3 else "ready")
                for n, c in zip(range(1, 6), "abcde")]
        try:
            found = repo.inside(lambda blobs: sd.hand_offs(days, [1, 2, 3, 4, 5], repo.snaps[-1]["sha"], blobs))
        finally:
            repo.close()
        self.assertEqual([(h["to"], h["source"], h["picked"]) for h in found], [
            (3, "Day 01 Notes", True),          # in run order, open ones first within a day
            (4, "src/Bar.java:1", False),       # Day 04 never names Bar
            (4, "Day 01 Notes", True),          # points to Day 02, which Day 04 names
            (5, "Day 01 Notes", False),
            (5, "src/Foo.java:1", True)])       # the code line after it is not a comment
        self.assertEqual(found[4]["text"], "Day 05 moves this.")

    def test_a_hand_off_with_an_id_is_picked_up_only_by_a_spec_citing_it(self):
        repo = Repo().merge({
            "specs/day-01-a.md": "## Notes\n- **Hand-off** H01.1 → Day 03: the key.\n"
                                 "- **Hand-off** H01.2 → Day 02: the queue.\n"
                                 "- **Hand-off** H01.3 → the maintainer: branch protection.\n"
                                 "- **Hand-off** H01.4 → the maintainer: the volume.\n",
            "specs/day-02-b.md": "# Day 02\n\nFrom Day 01: nothing cited.\n",
            "specs/day-03-c.md": "# Day 03\n\nFrom Day 01: the key.\n\n## Notes\n- H01.4 done by hand.\n",
            "specs/day-04-d.md": "# Day 04\n\nPicks up H01.1.\n",
            "src/Foo.java": "// Day 01 wrote this.\n",
        })
        days = [dict(day=n, file=f"specs/day-0{n}-{c}.md", status="done" if n < 3 else "ready")
                for n, c in zip(range(1, 5), "abcd")]
        try:
            found = repo.inside(lambda blobs: sd.hand_offs(days, [1, 2, 3, 4], repo.snaps[-1]["sha"], blobs))
        finally:
            repo.close()
        self.assertEqual([(h["to"], h["id"], h["picked"]) for h in found], [
            (3, "H01.1", False),                # Day 03 names Day 01, not the ID; Day 04 cites it
            (None, "H01.2", False),             # Day 02 finished without citing it
            (None, "H01.3", False)])            # no day takes it; H01.4 is cited by Day 03's Notes

    def test_a_day_plan_md_puts_ahead_takes_its_hand_off_before_its_spec_is_written(self):
        # a pilot, order 1, 3, 2, 4, 5: at its #5 H1.1 and H1.2 sat under "No later day picks these
        # up"; at its #10 H1.1 was gone, as Day 3's spec cites its ID.
        repo = Repo().merge({
            "specs/day-01-a.md": "## Notes\n- **Hand-off** H1.1 → Day 2: the stopwords.\n"
                                 "- **Hand-off** H1.2 → Day 3: the exit code.\n",
            "specs/day-03-c.md": "# Day 03\n\nH1.2 is picked up here; H1.1 stays with Day 2.\n",
            "src/Foo.java": "// Day 01 wrote this.\n",
        })
        one = dict(day=1, file="specs/day-01-a.md", status="done")
        three = dict(day=3, file="specs/day-03-c.md", status="done")
        try:
            found = [repo.inside(lambda blobs: sd.hand_offs(days, [1, 3, 2, 4, 5], repo.snaps[-1]["sha"], blobs))
                     for days in ([one], [one, three])]
        finally:
            repo.close()
        self.assertEqual([[(h["to"], h["id"], h["picked"]) for h in f] for f in found], [
            [(3, "H1.2", False), (2, "H1.1", False)],   # at #5: Days 3 and 2 have no spec yet
            [(2, "H1.1", False)]])                      # at #10: Day 3 done; Day 2 has no spec yet

    def test_a_track_a_pr_announces_that_no_branch_names_is_the_next_step(self):
        prs = [dict(number=298, headRefName="day-25/track-e1b-x", body="**E1c** (next). Not Day 21's E1d; `grep -A3`."),
               dict(number=297, headRefName="day-25/track-e1a-x", body="Track E1 splits; B1 stays."),
               dict(number=290, headRefName="day-25/track-b-x", body="B1 here")]
        self.assertEqual(sd.unopened_tracks(prs), [dict(track="E1c", pr=298)])
        self.assertEqual(sd.unopened_tracks(prs + [dict(number=305, headRefName="day-25/track-e1c-y", body="")]), [])
        day = dict(a_day(25), status="active", prs=[dict(kind="spec")], tracks_merged=["A"],
                   tracks_unopened=sd.unopened_tracks(prs))
        self.assertEqual(sd.next_step([day], [], [25], None), "Day 25 Track E1c: announced in #298, no branch names it")

    def test_a_criterion_id_is_not_a_track(self):
        self.assertEqual(sd.unopened_tracks([dict(number=1, headRefName="day-32/track-c1-x", body="Ticks C32.5 and H32.1.")]), [])

    def test_a_day_numbered_name_is_not_a_track(self):
        body = 'It read `C32.x` as "C32", a track C32: wrong.'
        self.assertEqual(sd.unopened_tracks([dict(number=1, headRefName="day-32/track-c1-x", body=body)]), [])

    def test_a_notes_item_that_only_cites_its_days_hand_off_is_not_one(self):
        # a pilot, Day 1: a Note ending "(H1.2)" was listed as H1.2 a second time, to no day.
        repo = Repo().merge({
            "specs/day-01-a.md": "## Notes\n- The condition is in one place, so Day 03 decides it (H01.2).\n"
                                 "- **Hand-off** H01.2 → Day 03: the stop decides it.\n",
            "specs/day-03-c.md": "# Day 03\n\nNothing cited.\n",
            "src/Foo.java": "// Day 01 wrote this.\n",
        })
        days = [dict(day=1, file="specs/day-01-a.md", status="done"), dict(day=3, file="specs/day-03-c.md", status="ready")]
        try:
            found = repo.inside(lambda blobs: sd.hand_offs(days, [1, 3], repo.snaps[-1]["sha"], blobs))
        finally:
            repo.close()
        self.assertEqual([(h["to"], h["id"], h["text"][:12]) for h in found], [(3, "H01.2", "**Hand-off**")])

    def test_a_hand_off_range_names_every_id_in_it(self):
        self.assertEqual(sd.hand_off_ids("H34.1–H34.3 and H35.2-4, H36.7"),
                         {"H34.1", "H34.2", "H34.3", "H35.2", "H35.3", "H35.4", "H36.7"})

    def test_a_hand_off_range_picks_up_each_id_in_it(self):
        repo = Repo().merge({
            "specs/day-01-a.md": "## Notes\n- **Hand-off** H01.2 → the maintainer: the middle one.\n",
            "specs/day-02-b.md": "# Day 02\n\nPicks up H01.1–H01.3.\n",
            "src/App.java": "// Day 01 wrote this.\n",  # git grep fails on a tree with no day in its code
        })
        days = [dict(day=1, file="specs/day-01-a.md", status="done"),
                dict(day=2, file="specs/day-02-b.md", status="ready")]
        try:
            found = repo.inside(lambda blobs: sd.hand_offs(days, [1, 2], repo.snaps[-1]["sha"], blobs))
        finally:
            repo.close()
        self.assertEqual(found, [])  # Day 02's range cites H01.2, so no hand-off is left open

    def test_a_code_comment_is_not_handed_to_the_day_whose_pr_wrote_it(self):
        repo = Repo().merge({
            "specs/day-01-a.md": "# Day 01\n",
            "specs/day-02-b.md": "# Day 02\n",
            "specs/day-03-c.md": "# Day 03\n",
            "src/Foo.java": "// Day 02 finishes this.\n// Day 03 removes this.\n",
        })
        repo.git("commit", "--amend", "-q", "-m", "Merge pull request #7 from o/day-02/track-a-x")
        repo.snaps[-1]["sha"] = repo.git("rev-parse", "--short", "HEAD").strip()
        days = [dict(day=n, file=f"specs/day-0{n}-{c}.md", status="done" if n < 2 else "ready")
                for n, c in zip(range(1, 4), "abc")]
        try:
            found = repo.inside(lambda blobs: sd.hand_offs(days, [1, 2, 3], repo.snaps[-1]["sha"], blobs))
        finally:
            repo.close()
        self.assertEqual([(h["to"], h["source"]) for h in found], [(3, "src/Foo.java:2")])


class ProjectFileTest(unittest.TestCase):
    """spec-drift.config.json: what git cannot tell about a repository, empty in a new one."""

    def test_with_no_file_or_no_field_nothing_is_set_and_verify_reads_the_root(self):
        for fields in (None, {}):
            folder = tempfile.mkdtemp(prefix="spec-drift-config-")
            self.addCleanup(shutil.rmtree, folder, True)
            path = os.path.join(folder, "spec-drift.config.json")
            if fields is not None:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(fields, f)
            c = sd.project_config(path)
            self.assertEqual((c["RENAMED"], c["MOVED"], c["VERIFY_BASES"], c["SERVICE"], c["INFRA_WORKFLOW"]),
                             ({}, [], ("",), {}, ""))

    def test_renames_moves_and_verify_bases_are_the_files(self):
        use_project(self, PROJECT)
        self.assertEqual(sd.RENAMED, {296: ("OrdersUserDeletedConsumerIT", "UserDeletedConsumerTest"),
                                      298: ("CircuitBreakerIT", "StockLookupBreakerTest")})
        self.assertEqual(len(sd.MOVED), 6)
        self.assertEqual(sd.MOVED[3], (315, "core", "services/account-service"))
        self.assertEqual(sd.VERIFY_BASES, ("core", ""))

    def test_boundaries_place_and_cross_the_files_services_under_its_package_root(self):
        root = "src/main/java/org/example/shop"
        repo = Repo().merge({
            f"core/{root}/orders/Order.java": "import org.example.shop.auth.User;\n"
                                               "import org.example.shop.util.Text;\nclass Order {}\n",
            f"core/{root}/util/Text.java": "class Text {}\n",
            f"services/stock-service/{root}/catalog/Item.java": "import static org.example.shop.orders.Order.x;\n"
                                                                 "class Item {}\n",
            f"core/src/test/java/org/example/shop/orders/OrderTest.java": "import org.example.shop.auth.User;\n"})
        self.addCleanup(repo.close)
        def boundaries():
            rows = [{}]
            repo.inside(lambda blobs: sd.boundaries(rows, repo.snaps, blobs))
            return rows[0]["placed"], rows[0]["crossings"]
        use_project(self, PROJECT)
        self.assertEqual(boundaries(), ({"orders": [3, 0], "stock": [0, 2]}, {"orders>account": 1, "stock>orders": 1}))
        use_project(self, {})
        self.assertEqual(boundaries(), ({}, {}))

    def test_the_infra_workflow_is_the_files_and_with_none_gh_is_not_asked(self):
        asked, real = [], sd.run
        self.addCleanup(setall, "run", real)
        setall("run", lambda *args: asked.append(args) or "[]")
        use_project(self, PROJECT)
        sd.infra(sd.INFRA_WORKFLOW)
        self.assertEqual([a[:5] for a in asked], [("gh", "run", "list", "--workflow", "infra.yaml")])
        use_project(self, {})
        asked.clear()
        self.assertEqual((sd.infra(sd.INFRA_WORKFLOW), asked), (dict(runs=[], latest=None), []))


class OwnerAndCaveatTest(unittest.TestCase):
    """Only the owner's PRs are read (SO-12), and the dashboard says what name coverage cannot see."""

    def test_only_the_owners_prs_are_kept(self):
        listed = [dict(number=1, author=dict(login="Yusuprozimemet")),
                  dict(number=2, author=dict(login="app/dependabot")),
                  dict(number=3)]
        self.assertEqual([p["number"] for p in sd.owners_prs(listed, "Yusuprozimemet")], [1])

    def test_another_authors_pr_is_not_the_next_step(self):
        mine = dict(number=50, title="Day 25 track A", state="OPEN", author=dict(login="Yusuprozimemet"))
        theirs = dict(number=51, title="Bump x", state="OPEN", author=dict(login="app/dependabot"))
        day = a_day(25, kinds=["spec"])
        everyone = sd.next_step([day], [mine, theirs], [25], None)
        mine_only = [p for p in sd.owners_prs([mine, theirs], "Yusuprozimemet") if p["state"] == "OPEN"]
        self.assertIn("#51", everyone)
        self.assertEqual(sd.next_step([day], mine_only, [25], None), "Waiting on #50 Day 25 track A")

    def test_another_authors_body_names_no_track(self):
        theirs = dict(number=51, headRefName="day-25/track-e1a-x", title="x", body="Ticks E1c.",
                      author=dict(login="app/dependabot"))
        self.assertEqual(sd.unopened_tracks([theirs]), [dict(track="E1c", pr=51)])
        self.assertEqual(sd.unopened_tracks(sd.owners_prs([theirs], "Yusuprozimemet")), [])

    def test_the_coverage_caveat_says_tests_and_tooling_count_and_cites_no_measurement(self):
        self.assertIn("Name coverage counts test and tooling files as code.", sd.CAVEATS)
        for c in sd.CAVEATS:  # another project has no such audit, file or figure
            self.assertNotRegex(c, r"\d|\.md\b", c)

    def test_the_project_is_the_repositorys_name_or_with_no_remote_its_folders(self):
        def fake(*args):
            if args[:3] == ("gh", "repo", "view"):
                if remote:
                    return "toy-repo\n"
                raise subprocess.CalledProcessError(1, args, stderr="no git remotes found")
            if args[:2] == ("git", "rev-parse"):
                return "/home/someone/toy-folder\n"
        real = sd.run
        try:
            setall("run", fake)
            remote = True
            self.assertEqual(sd.project_name(), "toy-repo")
            remote = False
            self.assertEqual(sd.project_name(), "toy-folder")
        finally:
            setall("run", real)


class OtherGroupsTest(unittest.TestCase):
    def test_groups_other_merges_by_branch_prefix(self):
        rows = [
            dict(pr=1, kind="other", branch="tooling/a"),
            dict(pr=2, kind="other", branch="tooling/b"),
            dict(pr=3, kind="other", branch="tooling/c"),
            dict(pr=4, kind="other", branch="dashboard/a"),
            dict(pr=5, kind="other", branch="dashboard/b"),
            dict(pr=6, kind="other", branch="docs/a"),
            dict(pr=7, kind="other", branch="release"),
            dict(pr=8, kind="code", branch="day-01/track-a-x"),
        ]
        self.assertEqual(sd.other_groups(rows), [
            {"name": "tooling", "count": 3},
            {"name": "dashboard", "count": 2},
            {"name": "docs", "count": 1},
            {"name": "other", "count": 1},
        ])

    def test_groups_cap_the_smallest_prefixes(self):
        rows = [dict(pr=i, kind="other", branch=f"{name}/x")
                for i, name in enumerate(("a", "a", "a", "b", "b", "c", "d", "e", "f"), 1)]
        self.assertEqual(sd.other_groups(rows), [
            {"name": "a", "count": 3},
            {"name": "b", "count": 2},
            {"name": "c", "count": 1},
            {"name": "other", "count": 3},
        ])


class MergeTimeTest(unittest.TestCase):
    PRS = {n: dict(number=n, title=t, headRefName=b, state=s, body="", createdAt=o, mergedAt=m)
           for n, t, b, s, o, m in (
               (1, "Day 01 spec change: x", "day-01/spec-x", "MERGED", "2026-11-01T08:00:00Z", "2026-11-01T14:30:00Z"),
               (2, "Day 01 track A: y", "day-01/track-a-y", "MERGED", "2026-11-01T15:00:00Z", "2026-11-01T15:45:00Z"),
               (3, "Day 01 close the day", "day-01/close-the-day", "MERGED", "2026-11-01T16:00:00Z", "2026-11-03T16:00:00Z"),
               (4, "Add a check", "tooling/check", "MERGED", "2026-11-04T09:00:00Z", "2026-11-04T10:00:00Z"),
               (5, "Fix a link", "docs/link", "MERGED", None, None),
               (6, "Still open", "tooling/open", "OPEN", "2026-11-05T09:00:00Z", None))}

    def test_each_merged_pr_has_its_step_and_hours_open(self):
        got = [(v["number"], v["kind"], v["step"], v["hours"]) for v in sd.verification(self.PRS, [])]
        self.assertEqual(got, [(1, "spec", "spec", 6.5), (2, "code", "code", 0.75), (3, "close", "close", 48.0),
                               (4, "other", "tooling", 1.0), (5, "other", "other", None)])


class ConclusionTest(unittest.TestCase):
    NOTEBOOK = ("# Notebook\n\n## What is being measured\n\n"
                "| Question | Evidence | Day 01 | Day 02 |\n| --- | --- | --- | --- |\n"
                "| Cost per PR | `token-usage.json` | $5.51 | $4.10 |\n| Escapes | Notes | 0 | 3 |\n\n## Retrospective\n")

    def test_a_table_with_a_column_per_day_is_kept_whole(self):
        got = sd.conclusion(self.NOTEBOOK)
        self.assertEqual(got["measured_head"], ["Question", "Evidence", "Day 01", "Day 02"])
        self.assertEqual(got["measured"], [["Cost per PR", "`token-usage.json`", "$5.51", "$4.10"],
                                           ["Escapes", "Notes", "0", "3"]])


def a_report(close, rev, checks, state="clean", **more):
    """An evidence.py --json report of Day 01, checked at close on its spec and breaks file at rev."""
    day = dict(spec=dict(path="specs/day-01-x.md", sha256="0" * 64, state=state, revision=rev), day="01",
               close_sha=close, verify_base_sha=None, checks=checks,
               breaks=dict(path="specs/breaks/day-01.json", sha256=None, state="missing", revision=None))
    return dict(dict(schema=1, runner=dict(revision="r" * 40, dirty=False), generated="2026-10-29T10:00:00+00:00",
                     ref="main", ref_sha=close, days=[day]), **more)


def a_check(kind, status, label="C1.1", diagnostic=None):
    return dict(id=f"day-01-x.md/{label}", kind=kind, criterion="C1.1", sha=None, status=status, label=label,
                diagnostic=diagnostic)


class CriterionIndexTest(unittest.TestCase):
    def test_representative_evidence_and_attention(self):
        repo = Repo()
        self.addCleanup(repo.close)
        files = {"plan.md": PLAN, "tests/test_example.py": "class ExampleTest:\n    def test_ok(self): pass\n"}
        for day in range(1, 4):
            blocks = []
            for number in range(1, 5):
                cid = f"C{day}.{number}"
                test = "MissingTest.test_lost" if cid == "C2.2" else "ExampleTest.test_ok"
                red = "" if cid == "C2.1" else "      broken: guard removed → FAILED (#1)\n"
                evidence = "" if cid == "C1.4" else f"      Evidence: `{test}` (#1).\n"
                replaces = ("      Replaces: C1.1 — was: the old claim\n" if cid == "C2.4" else
                            "      Replaces: C2.4 — was: the old claim\n" if cid == "C3.4" else "")
                blocks.append(f"- [x] {cid} **hold** — Claim {cid}.\n{evidence}{red}{replaces}")
            files[f"specs/day-{day:02d}-x.md"] = (f"# Day {day:02d} — Example\n\n**Phase:** {1 if day < 3 else 2}\n\n"
                "## Tracks\n\n| A | work | C1.1 |\n\n## Acceptance criteria\n\n" + "\n".join(blocks) + "\n## Notes\n")
        repo.merge(files)
        days = []
        for day in range(1, 4):
            path = f"specs/day-{day:02d}-x.md"
            days.append(dict(day=day, phase=1 if day < 3 else 2, file=path, status="done",
                             track_work={"A": "C1.1–C1.3", "B": "C1.4"},
                             evidence=sd.criteria(sd.section(files[path], "Acceptance criteria"))))
        reports = dict(state="loaded", days=[
            dict(day=1, state="current", why=[], checks=[
                dict(criterion="C1.1", status="failed", diagnostic="wrong result"),
                dict(criterion="C1.2", status="error", diagnostic="runner failed"),
                dict(criterion="C1.3", status="passed", diagnostic=None),
                dict(criterion="C1.3", status="not_applicable", diagnostic="checked by command"),
                dict(criterion=None, status="error", diagnostic="runner crashed")]),
            dict(day=2, state="stale", why=["spec changed"], checks=[]),
            dict(day=3, state="not checked")])
        handoffs = [dict(to=4, picked=False, text="C3.1 needs follow-up", source="Day 03 Notes")]
        rows, attention = repo.inside(lambda blobs: sd.criterion_index(days, reports, handoffs, repo.snaps, blobs))
        self.assertEqual(len(rows), 12)
        by_id = {row["id"]: row for row in rows}
        self.assertEqual((by_id["C1.1"]["phase"], by_id["C1.1"]["track"]), (1, "A"))
        self.assertEqual((by_id["C1.2"]["track"], by_id["C1.4"]["track"]), ("A", "B"))
        self.assertEqual((by_id["C1.1"]["day"], by_id["C1.1"]["tag"], by_id["C1.1"]["claim"]),
                         (1, "hold", "Claim C1.1."))
        self.assertEqual(by_id["C1.1"]["spec"], "specs/day-01-x.md#acceptance-criteria")
        self.assertEqual(by_id["C1.1"]["replaced_by"], ["C2.4"])
        self.assertEqual(by_id["C3.4"]["replaces"], ["C2.4"])
        self.assertIsNone(by_id["C3.1"]["replay"]["status"])
        self.assertTrue(by_id["C1.3"]["cited"])
        self.assertTrue(by_id["C1.3"]["test_found"])
        self.assertEqual(by_id["C1.3"]["replay"]["status"], ["passed", "not_applicable"])
        self.assertEqual(by_id["C1.3"]["replay"]["why"], ["checked by command"])
        self.assertEqual(by_id["C1.3"]["replay"]["checks"], reports["days"][0]["checks"][2:4])
        self.assertEqual(by_id["C1.3"]["prs"], [1])
        self.assertEqual(by_id["C1.3"]["tests"], ["ExampleTest.test_ok"])
        self.assertEqual(by_id["C1.3"]["seen_red"], dict(state=True, lines=["broken: guard removed → FAILED (#1)"], none=[]))
        self.assertIsNone(by_id["C1.4"]["test_found"])
        self.assertFalse(by_id["C2.2"]["test_found"])
        self.assertEqual([(a["id"], a["reason"]) for a in attention], [
            ("C1.1", "replay_failed"), ("C1.2", "replay_error"), ("Day 01", "replay_error"),
            *((f"C2.{n}", "replay_stale") for n in range(1, 5)),
            ("C1.4", "evidence_missing"), *((f"C3.{n}", "evidence_missing") for n in range(1, 5)),
            ("C2.1", "not_seen_red"),
            ("C2.2", "test_not_found"), ("C3.1", "handoff_unclaimed")])
        self.assertEqual([a["detail"] for a in attention if a["id"] == "Day 01"], ["runner crashed"])
        self.assertEqual([a["id"] for a in attention if a["reason"] == "replay_error"
                          and a["id"].startswith("C1.")], ["C1.2"])
        days[0]["evidence_format"] = False
        unknown, _ = repo.inside(lambda blobs: sd.criterion_index(days, dict(state="absent"), [], repo.snaps, blobs))
        self.assertIsNone(unknown[0]["cited"])
        self.assertIsNone(unknown[0]["seen_red"]["state"])
        self.assertEqual(unknown[0]["replay"], dict(state="absent", status=None, why=[], checks=[]))

    def test_a_command_above_counts_and_a_break_that_cannot_run_is_noted_apart(self):
        repo = Repo()
        self.addCleanup(repo.close)
        blocks = [
            "- [x] C1.1 **hold** — Frozen: `git diff --exit-code abc -- tests/` prints nothing.\n"
            "      Evidence: the command above, exit 0 in #3.\n      broken: a frozen file edited → 1 (#3)\n",
            "- [x] C1.2 **hold** — Both hold: `git diff a -- x` and `git diff b -- y`.\n"
            "      Evidence: both commands above, nothing printed in #3.\n      broken: x edited → 1 (#3)\n",
            "- [x] C1.3 **hold** — Run by hand: `python -m bearing ingest <kit>` prints 91.\n"
            "      Evidence: run by hand at the close, 91 (#3).\n      broken: x → y (#3)\n",
            "- [x] C1.4 **hold** — Outside the repository.\n      Evidence: `ExampleTest.test_ok` (#3).\n"
            "      broken: none → the check needs a clone CI has not\n",
            "- [x] C1.5 **hold** — Set outside: `gh variable list` shows X.\n"
            "      broken: none → the variables live outside the repository\n"
            "      Not proven: a reader read gh variable list (#3): X.\n",
            "- [x] C1.6 **hold** — Set outside: `gh variable list` shows Y.\n"
            "      broken: none → the variables live outside the repository\n"
            "      Not proven: a reader read gh variable list.\n"]
        path = "specs/day-01-x.md"
        files = {"plan.md": PLAN, "tests/test_example.py": "class ExampleTest:\n    def test_ok(self): pass\n",
                 path: "# Day 01 — Example\n\n**Phase:** 1\n\n## Acceptance criteria\n\n" + "\n".join(blocks) + "\n## Notes\n"}
        repo.merge(files)
        days = [dict(day=1, phase=1, file=path, status="active", evidence=sd.criteria(sd.section(files[path], "Acceptance criteria")))]
        rows, attention = repo.inside(lambda blobs: sd.criterion_index(days, dict(state="loaded", days=[]), [], repo.snaps, blobs))
        by_id = {row["id"]: row for row in rows}
        # A reader's Not proven: line is the replay's proof for a ticked box; with its PR it is cited.
        self.assertEqual([by_id[f"C1.{n}"]["cited"] for n in range(1, 7)], [True, True, False, True, True, False])
        self.assertEqual(by_id["C1.4"]["seen_red"], dict(state=False, lines=[], none=["the check needs a clone CI has not"]))
        self.assertEqual(by_id["C1.1"]["seen_red"]["none"], [])
        self.assertEqual([(a["id"], a["reason"], a["detail"]) for a in attention if a["reason"] != "evidence_missing"],
                         [("C1.4", "not_breakable", "the check needs a clone CI has not"),
                          ("C1.5", "not_breakable", "the variables live outside the repository"),
                          ("C1.6", "not_breakable", "the variables live outside the repository")])
        self.assertEqual([a["id"] for a in attention if a["reason"] == "evidence_missing"], ["C1.3", "C1.6"])

    def one_day(self, block, test_file=""):
        repo = Repo()
        self.addCleanup(repo.close)
        path = "specs/day-01-x.md"
        files = {"plan.md": PLAN, path: "# Day 01 — Example\n\n**Phase:** 1\n\n## Acceptance criteria\n\n" + block + "\n## Notes\n"}
        if test_file:
            files["tests/test_live.py"] = test_file
        repo.merge(files)
        return repo, [dict(day=1, phase=1, file=path, status="done", evidence=sd.criteria(sd.section(files[path], "Acceptance criteria")))]

    def test_open_hand_offs_for_the_next_day_and_unpicked_ones_follow_the_criteria(self):
        # handoff_unclaimed needs a hand-off to name a criterion; these name their own ID and a day.
        repo, days = self.one_day("- [x] C1.1 **hold** — Claim.\n      broken: x → y (#1)\n")
        handoffs = [dict(to=2, id="H01.1", picked=False, source="Day 01 Notes", text="- **Hand-off** H01.1 → Day 2: do x."),
                    dict(to=2, id="H01.2", picked=True, source="Day 01 Notes", text="picked"),
                    dict(to=3, picked=False, source="Day 01 Notes", text="for a later day"),
                    dict(to=None, id="H01.3", picked=False, source="Day 01 Notes", text="**Hand-off** H01.3 → the maintainer: y.")]
        _, attention = repo.inside(lambda blobs: sd.criterion_index(
            days, dict(state="loaded", days=[]), handoffs, repo.snaps, blobs, order=[1, 2, 3]))
        self.assertEqual([a["id"] for a in attention[:-2]], ["C1.1"] * (len(attention) - 2))
        self.assertEqual(attention[-2:], [
            dict(id="H01.1", reason="handoff_next", detail="Day 02: **Hand-off** H01.1 → Day 2: do x."),
            dict(id="H01.3", reason="handoff_unpicked", detail="**Hand-off** H01.3 → the maintainer: y.")])

    def test_a_named_test_ci_can_skip_is_noted_last(self):
        live = ("import os, unittest\n\n\n@unittest.skipUnless(os.environ.get('DRIVER_LIVE_CLI'), 'live')\n"
                "class LiveTest(unittest.TestCase):\n    def test_live(self): pass\n")
        repo, days = self.one_day("- [x] C1.1 **hold** — Claim.\n      Evidence: `LiveTest.test_live` (#1).\n"
                                  "      broken: x → y (#1)\n", live)
        rows, attention = repo.inside(lambda blobs: sd.criterion_index(days, dict(state="loaded", days=[]), [], repo.snaps, blobs))
        self.assertTrue(rows[0]["test_found"])
        self.assertEqual(attention[-1], dict(id="C1.1", reason="test_skippable", detail="LiveTest.test_live"))
        # "Tests on main" counts the names the whole block gives (C04.14 names LiveOnceTest in its claim).
        days[0]["evidence"][0]["tests"] = {"LiveTest.test_live": "skippable", "LiveOnceTest": "skippable"}
        _, attention = repo.inside(lambda blobs: sd.criterion_index(days, dict(state="loaded", days=[]), [], repo.snaps, blobs))
        self.assertEqual(attention[-1]["detail"], "LiveTest.test_live, LiveOnceTest")


class EvidenceReportTest(unittest.TestCase):
    """The committed evidence report: read, never replayed, and current only on main's inputs."""

    def setUp(self):
        self.repo = Repo().merge({"specs/day-01-x.md": "# Day 01\n"}).merge({"app/a.py": "x = 1\n"})
        self.addCleanup(self.repo.close)
        self.close = self.repo.git("rev-parse", "HEAD").strip()
        self.days = [dict(day=1, status="done", file="specs/day-01-x.md", prs=[dict(number=1, kind="close")]),
                     dict(day=2, status="done", file="specs/day-02-y.md", prs=[]),
                     dict(day=3, status="active", file="specs/day-03-z.md", prs=[])]
        page = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, page, True)
        self.addCleanup(setall, "PAGE", sd.PAGE)
        setall("PAGE", page)

    def read(self, report):
        if report is not None:
            with open(os.path.join(sd.PAGE, "evidence-checks.json"), "w", encoding="utf-8") as f:
                f.write(report if isinstance(report, str) else json.dumps(report))
        return self.repo.inside(lambda _: sd.evidence_checks(self.days, self.repo.snaps))

    def test_no_report_is_absent_not_a_pass(self):
        self.assertEqual(self.read(None), dict(state="absent"))

    def test_a_report_on_mains_inputs_is_current_and_counted_by_kind_and_status(self):
        checks = [a_check("named_test", "passed"), a_check("named_test", "not_applicable"),
                  a_check("break", "failed", "C1.2 broken: x", "reported 'y'"), a_check("runner", "error", "w", "no worktree")]
        got = self.read(a_report(self.close, self.close, checks))
        self.assertEqual(got["state"], "loaded")
        one, two = got["days"]
        self.assertEqual((one["state"], one["why"]), ("current", []))
        self.assertEqual(one["counts"]["named_test"], dict(passed=1, failed=0, error=0, not_applicable=1))
        self.assertEqual(one["counts"]["break"]["failed"], 1)
        self.assertEqual([c["status"] for c in one["checks"]], ["passed", "not_applicable", "failed", "error"])
        self.assertEqual(one["checks"][1]["criterion"], "C1.1")
        self.assertEqual([p["label"] for p in one["problems"]], ["C1.2 broken: x", "w"])
        self.assertEqual(two, dict(day=2, state="not checked"))  # finished, left out; Day 3 is not finished

    def test_a_report_checked_elsewhere_is_stale(self):
        first = self.repo.snaps[0]["sha"]
        self.assertIn("checked at close", self.read(a_report(first, self.close, []))["days"][0]["why"][0])
        self.assertIn("was edited when checked", self.read(a_report(self.close, self.close, [], state="edited"))["days"][0]["why"][0])
        self.repo.merge({"specs/day-01-x.md": "# Day 01, edited\n"})
        got = self.read(a_report(self.close, self.close, []))["days"][0]
        self.assertEqual(got["state"], "stale")
        self.assertEqual(got["why"], [f"specs/day-01-x.md changed since {self.close[:7]}"])

    def test_a_report_this_cannot_read_is_invalid_with_its_reason(self):
        for report, why in (("{not json", "JSONDecodeError"), (dict(a_report(self.close, self.close, []), schema=2), "schema 2"),
                            (a_report(self.close, self.close, [a_check("verify", "skipped")]), "status 'skipped'"),
                            (dict(schema=1), "KeyError")):
            got = self.read(report)
            self.assertEqual(got["state"], "invalid", why)
            self.assertIn(why, got["diagnostic"])


def a_day(n, ticked=1, total=1, kinds=(), titles=()):
    return dict(day=n, status="provisional", criteria=dict(ticked=ticked, total=total),
                prs=[dict(kind=k, title=t) for k, t in zip(kinds, list(titles) + [""] * len(kinds))],
                tracks=["A"], tracks_merged=[], track_work={"A": "work"})


class RoadmapTest(unittest.TestCase):
    """Where the dashboard says the work is: the run order plan.md gives, and what counts as done."""

    PLAN = """## Day-by-day specs

Days keep their numbers; they run in this order:

1. The record fix and the platform step (new day specs, numbered from 38).
2. Phase 3: Days 18, 19, 17, 20.
3. Phase 4: the profile endpoint out of Day 24 first, then Days 21, 22, 23, the rest of 24.
4. Phase 5: Days 26, 27, 25, 28. **Stop and evaluate.**
5. Phases 6–7 (Days 29–37): rewritten after the evaluation, or not started.
"""

    def test_a_spec_change_must_touch_a_spec(self):
        self.assertEqual(sd.kind("Spec change: every criterion is new or hold", "specs/criterion-kinds",
                                 ["specs/README.md", "specs/_template.md"]), "other")
        self.assertEqual(sd.kind("Day 16 spec change: checks", "day-16/spec-x", ["specs/day-16-cutover.md"]), "spec")
        self.assertEqual(sd.kind("Plan change: seam first", "plan/course", ["plan.md"]), "spec")
        self.assertEqual(sd.kind("Add spec-drift.py", "tooling/spec-drift-script", []), "other")

    def test_code_is_a_track_and_an_early_day_has_no_exception(self):
        self.assertEqual(sd.kind("Day 01 track A: the harness", "day-01/track-a-harness"), "code")
        self.assertEqual(sd.kind("Day 01: the harness", "day-01/harness"), "other")
        self.assertEqual(sd.kind("Day 02: a fix", "day-02/fix"), "other")

    def test_a_close_is_named_by_the_word_tick_not_by_its_letters_inside_another_word(self):
        # #96's title held "yardsticks", and the page drew a dashboard PR as Day 7's close.
        self.assertEqual(sd.kind("Dashboard: each promise's abilities and the plan's yardsticks, as data",
                                 "dashboard/promise-abilities-and-yardsticks"), "other")
        self.assertEqual(sd.kind("Day 06: tick C06.1-C06.13 with evidence", "day-06/evidence"), "close")
        self.assertEqual(sd.kind("Day 06: criteria ticked", "day-06/evidence"), "close")
        self.assertEqual(sd.kind("Day 06 close: the Notes", "day-06/close-the-day"), "close")

    def test_a_commit_with_no_pr_keeps_its_subject_and_a_repo_without_main_says_so(self):
        repo = Repo().merge({"plan.md": "# Plan\n"})
        self.addCleanup(repo.close)
        repo.git("commit", "--amend", "-q", "-m", "Start the toy project")
        repo.git("branch", "-M", "trunk")
        try:
            said = repo.inside(lambda blobs: sd.snapshots({}))
        except SystemExit as e:
            said = str(e)
        except subprocess.CalledProcessError as e:
            said = f"git exited {e.returncode}"
        self.assertEqual(said, "spec-drift.py reads the branch main, and this repository has none: git branch -m main")
        repo.git("branch", "-M", "main")
        snaps = repo.inside(lambda blobs: sd.snapshots({}))
        self.assertEqual([(s["pr"], s["title"]) for s in snaps], [(None, "Start the toy project")])

    def test_a_squash_commit_reads_the_merged_pr_like_a_merge(self):
        repo = Repo().merge({"plan.md": "# Plan\n"})
        self.addCleanup(repo.close)
        repo.git("branch", "-M", "main")
        repo.git("commit", "--allow-empty", "-q", "-m", "Day 01 track A: thing (#5)")
        prs = {5: dict(number=5, state="MERGED", headRefName="day-01/track-a-thing",
                       title="Day 01 track A: thing")}
        squash = repo.inside(lambda blobs: sd.snapshots(prs))[-1]
        repo.git("checkout", "-q", "-b", "side")
        repo.git("commit", "--allow-empty", "-q", "-m", "side")
        repo.git("checkout", "-q", "main")
        repo.git("merge", "--no-ff", "-q", "side", "-m", "Merge pull request #5 from side")
        merge = repo.inside(lambda blobs: sd.snapshots(prs))[-1]
        self.assertEqual((squash["pr"], squash["title"], squash["branch"]),
                         (5, prs[5]["title"], prs[5]["headRefName"]))
        self.assertEqual(sd.kind(squash["title"], squash["branch"]), sd.kind(merge["title"], merge["branch"]))
        self.assertEqual(sd.kind(squash["title"], squash["branch"]), "code")

    def test_a_squash_subject_without_a_merged_pr_keeps_the_subject(self):
        repo = Repo().merge({"plan.md": "# Plan\n"})
        self.addCleanup(repo.close)
        repo.git("branch", "-M", "main")
        subject = "Day 01 track A: thing (#5)"
        repo.git("commit", "--allow-empty", "-q", "-m", subject)
        for prs in ({}, {5: dict(number=5, state="OPEN", title="other", headRefName="day-01/track-a-thing")}):
            with self.subTest(prs=prs):
                snap = repo.inside(lambda blobs: sd.snapshots(prs))[-1]
                self.assertEqual((snap["pr"], snap["title"], snap["branch"]), (None, subject, ""))

    def test_a_two_parent_commit_with_a_squash_subject_is_not_a_pr(self):
        repo = Repo().merge({"plan.md": "# Plan\n"})
        self.addCleanup(repo.close)
        repo.git("branch", "-M", "main")
        repo.git("checkout", "-q", "-b", "side")
        repo.git("commit", "--allow-empty", "-q", "-m", "side")
        repo.git("checkout", "-q", "main")
        subject = "Day 01 track A: thing (#5)"
        repo.git("merge", "--no-ff", "-q", "side", "-m", subject)
        prs = {5: dict(number=5, state="MERGED", title="other", headRefName="day-01/track-a-thing")}
        snap = repo.inside(lambda blobs: sd.snapshots(prs))[-1]
        self.assertEqual((snap["pr"], snap["title"], snap["branch"]), (None, subject, ""))

    def test_phases_are_the_plans_headings_and_stops_the_days_its_list_marks(self):
        plan = """# Toy plan

### Phase 0 — Lay the ground
### Phase 2 – Build it (later)

## Day-by-day specs

1. Phase 0: Days 3, 1, 2. **Stop and evaluate.**
2. Phase 2: Days 4-6. **Stop and evaluate.**
3. Phase 2: Day 7.

## Course correction after Phase 0

Go on.
"""
        self.assertEqual(sd.phases(plan), ["Lay the ground", "", "Build it (later)"])
        self.assertEqual(sd.stops(plan), [2, 6])  # Day 2's stop, lifted since, is still marked
        self.assertEqual(sd.run_order(plan, list(range(1, 8)))[1], 6)
        self.assertEqual((sd.phases("# Plan\n"), sd.stops("# Plan\n")), ([], []))

    def test_a_course_corrections_entry_naming_the_phase_lifts_its_stop(self):
        # a pilot, Day 4: the stop's decisions went under the template's "Course corrections",
        # and Days 2, 4 and 5 ran under "Day 03 is done: stop".
        plan = ("# Plan\n\n## Course corrections\n\n<!-- A stop's decision, e.g. after Phase 0. -->\n\n{}\n"
                "## Day-by-day specs\n\n1. Phase 0: Days 3, 1. **Stop and evaluate.**\n2. Phase 1: Days 2, 4.\n")
        stop = lambda entry: sd.run_order(plan.format(entry), list(range(1, 5)))[1]
        self.assertEqual([stop(""), stop("- **Phase 0 stop:** go on.\n"), stop("- **Phase 10 stop:** go on.\n")],
                         [1, None, 1])  # the comment's "Phase 0" lifts nothing

    def test_naming_the_phase_in_passing_lifts_no_stop(self):
        # bearing, Day 4: a correction written before Day 2 mentioned Phase 1, and the stop read as lifted.
        plan = ("# Plan\n\n## Course corrections\n\n{}\n"
                "## Day-by-day specs\n\n1. Phase 0: Day 1.\n2. Phase 1: Days 2-4. **Stop and evaluate.**\n"
                "3. Phase 2: Days 5-7.\n")
        stop = lambda entry: sd.run_order(plan.format(entry), [])[1]
        self.assertEqual([stop("### 2026-11-04: after the Phase 0/1 audit\n\nPhase 1 keeps its days.\n"),
                          stop("### 2026-11-05: Course correction after Phase 1\n\nGo on.\n"),
                          stop("### 2026-11-05: Course correction after Phase 10\n")],
                         [4, None, 4])

    def test_the_plan_templates_list_marks_its_stop_once_filled(self):
        with open(os.path.join(HERE, "..", "plan.md"), encoding="utf-8") as f:
            plan = f.read()
        if not plan.startswith("# <Project> plan"):
            self.skipTest("plan.md is filled in")
        self.assertEqual((sd.phases(plan), sd.stops(plan)), (["<name>", "<name>"], []))  # no day yet
        filled = plan.replace("Days <NN>, <NN>.", "Days 1, 2.").replace("Days <NN>-<NN>.", "Days 3-5.")
        self.assertEqual((sd.stops(filled), sd.run_order(filled, [])), ([2], ([1, 2, 3, 4, 5], 2)))

    def test_the_run_order_is_the_plans(self):
        order, stop = sd.run_order(self.PLAN, list(range(1, 38)))
        self.assertEqual(order[:17], list(range(1, 17)) + [sd.PLATFORM])
        self.assertEqual(order[17:29], [18, 19, 17, 20, 21, 22, 23, 24, 26, 27, 25, 28])
        self.assertEqual(order[29:], list(range(29, 38)))
        self.assertEqual(stop, 28)
        self.assertEqual(sd.run_order(self.PLAN, list(range(1, 40)))[0][16:18], [38, 39])

    def test_a_day_under_10_is_a_day_and_only_a_phase_number_is_not(self):
        plan = "## Day-by-day specs\n\n1. Phase 0: Days 3, 1, 2. **Stop and evaluate.**\n2. Phase 1: Days 4-5.\n"
        self.assertEqual(sd.run_order(plan, [1, 2, 3, 4, 5]), ([3, 1, 2, 4, 5], 2))

    def test_the_first_stop_not_lifted_is_the_one_work_waits_at(self):
        # bearing's plan, stops at Days 4 and 10: the last one won, so Day 5 was offered after Day 4.
        plan = ("## Day-by-day specs\n\n1. Phase 0: Day 1.\n2. Phase 1: Days 2-4. **Stop and evaluate.**\n"
                "3. Phase 2: Days 5-7.\n4. Phase 3: Days 8-10. **Stop and evaluate.**\n5. Phase 4: Days 11-12.\n")
        lift = "## Course corrections\n\n- **Phase 1 stop:** go on.\n\n"
        self.assertEqual([sd.run_order(plan, [])[1], sd.run_order(lift + plan, [])[1]], [4, 10])

    def test_the_source_projects_plan_runs_in_its_order(self):
        # The source project's list as it ended: phase numbers inside words and after "after".
        plan = """## Day-by-day specs

1. The record fix and the platform step (new day specs, numbered from 38).
2. Phase 3: Days 18, 19, 17, 20.
3. Phase 4: Day 41 (the profile endpoint and user id, split out of Day 24) first, then Days 21, 22
   (no dual write), 23, 24.
4. Phase 5: Days 26, 27, 25, 28. **Stop and evaluate.**
5. The cleanup day (course correction after Phase 5), Day 42; done.
6. Phase 7 for the cloud, in this order: Days 32, 33 (the code before the cloud), 36 (the services in
   the cloud), 34, 35; done.
7. Phase 6 (Days 29–31): **cut** after Phase 7 (*Phase 7 outcome*).
8. The close-out day, Day 43: the end-of-Phase-7 audits' findings; done.

## Course correction after Phase 5

The cleanup day first.
"""
        specs = list(range(1, 37)) + list(range(38, 44))  # its specs: no Day 37; Days 29-31 written, then cut
        order, stop = sd.run_order(plan, specs)
        self.assertEqual(order, list(range(1, 17)) + [38, 39, 40, 18, 19, 17, 20, 41, 21, 22, 23, 24, 26, 27, 25, 28,
                                                      42, 32, 33, 36, 34, 35, 43])
        self.assertIsNone(stop)

    def test_the_days_out_of_order_are_those_that_break_the_rising_run(self):
        order = list(range(1, 17)) + [38, 39, 40, 18, 19, 17, 20, 21, 26, 27, 25, 28, sd.PLATFORM]
        self.assertEqual(sd.out_of_order(order), [38, 39, 40, 17, 25])
        self.assertEqual(sd.out_of_order(list(range(1, 10))), [])
        self.assertEqual(sd.out_of_order([]), [])

    def test_a_plan_and_its_specs_parse(self):
        root = tempfile.mkdtemp()
        os.mkdir(os.path.join(root, "specs"))
        for n in range(10, 19):
            open(os.path.join(root, "specs", f"day-{n}-x.md"), "w").close()
        with open(os.path.join(root, "plan.md"), "w", encoding="utf-8") as f:
            f.write("## Day-by-day specs\n\n1. Phase 2: Days 12, 11, 13.\n"
                    "2. Phase 3: Days 14, 15. **Stop and evaluate.**\n3. Phase 4 (Days 16–17): **cut**.\n"
                    "4. Phase 5: Day 18.\n\n## Course correction after Phase 3\n\nGo on.\n")
        with open(os.path.join(root, "plan.md"), encoding="utf-8") as f:
            plan = f.read()
        days = sorted({sd.day_of(n) for n in os.listdir(os.path.join(root, "specs")) if sd.day_of(n)})
        order, stop = sd.run_order(plan, days)
        self.assertEqual(sorted(d for d in order if d not in sd.PLACEHOLDERS), [d for d in days if d not in (16, 17)])
        self.assertIsNone(stop)  # evaluated: the plan has the course correction after Phase 3

    def test_the_cleanup_day_comes_after_the_stop_once_it_is_evaluated(self):
        plan = self.PLAN.replace("5. Phases 6–7 (Days 29–37): rewritten after the evaluation, or not started.",
                                 "5. The cleanup day: its spec is written next, numbered\n"
                                 "   after the last.\n"
                                 "6. Phases 6–7 (Days 29–37).") + "\n## Course correction after Phase 5\n\nCleanup first.\n"
        order, stop = sd.run_order(plan, list(range(1, 39)))
        self.assertIsNone(stop)
        self.assertEqual(order[order.index(28) + 1], sd.CLEANUP)
        days = sd.settle([a_day(28, kinds=["close"]), a_day(29)], [28, sd.CLEANUP, 29])
        self.assertEqual(sd.next_step(days, [], [28, sd.CLEANUP, 29], None, sd.unwritten_lines(plan)),
                         'Day 30: write its day spec (plan.md: "The cleanup day: its spec is written next, numbered after the last.")')
        days[0]["phase"], days[1]["phase"] = 5, 6
        self.assertEqual(sd.unwritten(days, [28, sd.CLEANUP, 29]),
                         dict(day=30, phase=5, title="The cleanup day"))  # the roadmap shows it after Day 28
        self.assertIsNone(sd.unwritten(days, [28, 29]))
        order, _ = sd.run_order(plan, list(range(1, 40)))
        self.assertEqual(order[order.index(28) + 1], 39)  # written: the day takes the placeholder's place
        self.assertEqual(sd.run_order(plan.split("\n## Course correction")[0], list(range(1, 42)))[1], 28)

    def test_a_cut_phase_leaves_the_order_and_the_close_out_day_comes_last(self):
        plan = self.PLAN.replace("5. Phases 6–7 (Days 29–37): rewritten after the evaluation, or not started.",
                                 "5. Phase 7: Days 32-35.\n"
                                 "6. Phase 6 (Days 29–31): **cut** after Phase 7.\n"
                                 "7. The close-out day, numbered after the last.") + "\n## Course correction after Phase 5\n"
        order, stop = sd.run_order(plan, list(range(1, 36)))
        self.assertNotIn(29, order)  # not first, as a day the list does not name would be
        self.assertEqual(order[-2:], [35, sd.CLOSEOUT])
        days = sd.settle([a_day(35, kinds=["close"]), a_day(36)], [35, sd.CLOSEOUT])
        days[0]["phase"] = 7
        self.assertEqual(sd.next_step(days, [], [35, sd.CLOSEOUT], None, sd.unwritten_lines(plan)),
                         'Day 37: write its day spec (plan.md: "The close-out day, numbered after the last.")')
        self.assertEqual(sd.unwritten(days, [35, sd.CLOSEOUT]), dict(day=37, phase=7, title="The close-out day"))
        order, _ = sd.run_order(plan, list(range(1, 36)) + [39])  # after the last named, Day 38
        self.assertEqual(order[-1], 39)  # written: the day takes the placeholder's place
        self.assertEqual(sd.run_order(plan.replace("**cut**", "cut"), list(range(1, 36)))[0][-4:-1], [29, 30, 31])

    def test_a_higher_number_does_not_finish_a_day_that_runs_later(self):
        days = sd.settle([a_day(17), a_day(18, kinds=["code"])], [18, 17])
        self.assertEqual([d["status"] for d in days], ["provisional", "active"])  # 17 waits for 18

    def test_a_planned_day_without_a_spec_is_next_to_write(self):
        plan = "## Day-by-day specs\n\n1. Phase 1: Days 10-12.\n"
        order, _ = sd.run_order(plan, [10, 12])
        self.assertEqual(order, [10, 11, 12])  # plan.md lists Day 11; specs/ has no file for it
        days = sd.settle([a_day(10), a_day(12)], order)
        self.assertEqual(sd.next_step(days, [], order, None),
                         "Day 10: read the spec against the code, then the spec-change PR")  # as before
        days = sd.settle([a_day(10, kinds=["close"]), a_day(12)], order)
        self.assertEqual([d["status"] for d in days], ["done", "provisional"])  # none active: between days
        self.assertEqual(sd.next_step(days, [], order, None),
                         "Day 11: write its day spec (plan.md lists it, specs/ has none)")

    def test_an_unwritten_day_quotes_the_plan_item_it_comes_from(self):
        plan = ("## Day-by-day specs\n\n1. Phase 1: Days 1-2.\n2. A step the plan adds, numbered\n"
                "   from 20.\n3. One more day, numbered after the last.\n")
        self.assertEqual(sd.unwritten_lines(plan), {sd.PLATFORM: "A step the plan adds, numbered from 20.",
                                                    sd.CLEANUP: "One more day, numbered after the last."})
        order, _ = sd.run_order(plan, [1, 2])
        days = sd.settle([a_day(1, kinds=["close"]), a_day(2, kinds=["close"])], order)
        self.assertEqual(sd.next_step(days, [], order, None, sd.unwritten_lines(plan)),
                         'Day 20: write its day spec (plan.md: "A step the plan adds, numbered from 20.")')
        order, _ = sd.run_order(plan, [1, 2, 20])
        days = sd.settle([a_day(1, kinds=["close"]), a_day(2, kinds=["close"]), a_day(20, kinds=["close"])], order)
        self.assertEqual(sd.next_step(days, [], order, None, sd.unwritten_lines(plan)),
                         'Day 21: write its day spec (plan.md: "One more day, numbered after the last.")')

    def test_a_finished_day_with_boxes_open_is_closed_not_done(self):
        days = sd.settle([a_day(1, ticked=0, total=7), a_day(2), a_day(3, kinds=["code"])], [1, 2, 3])
        self.assertEqual([d["status"] for d in days], ["closed", "done", "active"])

    def test_a_split_close_ends_the_day_only_with_its_last_part(self):
        part1 = a_day(43, ticked=1, total=27, kinds=["close"], titles=["Day 43 close, part 1: the ledger"])
        self.assertEqual(sd.settle([part1], [43])[0]["status"], "active")  # #428: boxes still open
        part2 = a_day(43, ticked=27, total=27, kinds=["close", "close"], titles=["Day 43 close, part 1", "Day 43 close, part 2"])
        self.assertEqual(sd.settle([part2], [43])[0]["status"], "done")
        whole = a_day(5, ticked=5, total=7, kinds=["close"], titles=["Day 05: tick the boxes"])
        self.assertEqual(sd.settle([whole], [5])[0]["status"], "closed")  # one close, boxes left open

    def test_the_next_step_is_the_platform_then_the_stop(self):
        days = sd.settle([a_day(16, kinds=["close"]), a_day(17)], [16, sd.PLATFORM, 17])
        lines = {sd.PLATFORM: "New day specs, numbered from 38."}
        self.assertEqual(sd.next_step(days, [], [16, sd.PLATFORM, 17], None, lines),
                         'Day 38: write its day spec (plan.md: "New day specs, numbered from 38.")')
        days = sd.settle([a_day(28, kinds=["close"]), a_day(29)], [28, 29])
        self.assertIn("stop and evaluate", sd.next_step(days, [], [28, 29], 28))

    def test_with_no_day_specs_the_next_step_is_not_that_every_day_is_done(self):
        # The empty starter read "Every day is done." with 0 days.
        self.assertEqual(sd.next_step([], [], [], None),
                         "No day specs yet: fill in plan.md, then write the first day's spec (specs/README.md).")
        self.assertEqual(sd.next_step(sd.settle([a_day(1, kinds=["close"])], [1]), [], [1], None), "Every day is done.")

    def test_numbered_tracks_are_their_own_and_a_split_track_is_its_letter(self):
        tracks_section = """| Track | Owner | Work |
|---|---|---|
| 0 | | Work |
| A1 | | Work |
| A2 | | Work |
| B | | Work |"""
        self.assertEqual(sd.track_names(tracks_section), ["0", "A1", "A2", "B"])
        self.assertEqual(sd.merged_tracks(["day-39/track-0-x", "day-39/track-a1-key"], ["0", "A1", "A2", "B"]),
                         ["0", "A1"])
        self.assertEqual(sd.merged_tracks(["day-15/track-c1-rate", "day-15/track-c2-cors", "day-38/track-c-fix-harness"],
                                          ["0", "A", "B", "C", "D"]),
                         ["C"])
        self.assertEqual(sd.merged_tracks(["day-39/spec-written"], ["0", "A1", "A2", "B"]), [])
        # A track split again past the gate (Day 17's B1 into b1a..b1c): the letter after the digits
        # is a part of that track, not a track of its own.
        self.assertEqual(sd.merged_tracks(["day-17/track-b1a-service-key", "day-17/track-b1c-trusted-callers",
                                           "day-17/track-b2b-internal-client-and-breaker"],
                                          ["0", "A1", "A2", "B1", "B2", "C1"]),
                         ["B1", "B2"])
        # A table that names the letter (Day 20's 0a, 0b) makes it a track of its own.
        self.assertEqual(sd.track_names("| 0a | | Work |\n| 0b | | Work |\n| A | | Work |"), ["0a", "0b", "A"])
        self.assertEqual(sd.merged_tracks(["day-20/track-0a-jobs-db-seams"], ["0a", "0b", "A"]), ["0a"])

    def test_a_branch_that_names_no_day_is_read_by_its_title(self):
        # #321, Day 28's Track D, came from a branch that named no day.
        pr = dict(headRefName="claude/focused-bell-qqwqdx",
                  title="ABC-82 Day 28 track D: stopping-point review, plan changed after Phase 5")
        self.assertEqual(sd.merged_tracks([sd.day_branch(pr)], ["0", "A1", "E", "D"]), ["D"])
        # A day's own branch wins over its title, and a title that names no track changes nothing.
        own = dict(headRefName="day-28/track-e-ABC-84-account-healthcheck", title="Day 28 track D: wrong")
        self.assertEqual(sd.day_branch(own), own["headRefName"])
        other = dict(headRefName="claude/focused-sagan-96xo1w", title="account-service README: pull the image")
        self.assertEqual(sd.day_branch(other), other["headRefName"])

    def test_own_day_is_the_day_the_branch_names_and_none_for_area_work(self):
        self.assertEqual(sd.own_day(dict(headRefName="day-07/track-a-x", title="t")), 7)
        self.assertIsNone(sd.own_day(dict(headRefName="dashboard/one-day-rule", title="Show one rule on every graph")))
        self.assertIsNone(sd.own_day(dict(headRefName="specs/status-day-05", title="t")))
        self.assertEqual(sd.own_day(dict(headRefName="claude/focused-bell", title="ABC-82 Day 28 track D: stopping-point review")), 28)


class PlainWordsTest(unittest.TestCase):
    FILE = os.path.join(HERE, "..", "docs", "dashboard", "plain-promises.json")

    def test_the_first_sentence_is_cut_at_its_end_and_loses_its_backticks(self):
        self.assertEqual(sd.first_sentence("`classify()` gives a kind. Then more."), "classify() gives a kind.")
        self.assertEqual(sd.first_sentence("Run `run-steps.py --once` first. Next."), "Run run-steps.py --once first.")
        self.assertEqual(sd.first_sentence("No full stop here"), "No full stop here")
        long = sd.first_sentence("word " * 80)
        self.assertLessEqual(len(long), 201)
        self.assertTrue(long.endswith("…"))

    def write(self, text):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "plain.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_a_written_sentence_is_used_and_a_promise_with_none_falls_back(self):
        rows = [dict(id="C1", claim="`x` does a thing. More."), dict(id="C2", claim="`y` does another. More.")]
        sd.attach_plain(rows, self.write('{"C1": "Written for a reader."}'))
        self.assertEqual((rows[0]["plain"], rows[0]["plain_source"]), ("Written for a reader.", "written"))
        self.assertEqual((rows[1]["plain"], rows[1]["plain_source"]), ("y does another.", "first sentence"))

    def test_a_file_that_cannot_be_read_breaks_nothing(self):
        for text in ("not json", "[1]", '{"C1": 3}', '{"C1": "  "}'):
            rows = [dict(id="C1", claim="It works. More.")]
            sd.attach_plain(rows, self.write(text))
            self.assertEqual(rows[0]["plain"], "It works.", text)
        rows = [dict(id="C1", claim="It works.")]
        sd.attach_plain(rows, os.path.join(HERE, "no-such-file.json"))
        self.assertEqual(rows[0]["plain_source"], "first sentence")

    def test_each_written_sentence_is_one_short_plain_sentence_of_a_real_criterion(self):
        with open(self.FILE, encoding="utf-8") as f:
            written = json.load(f)
        specs = ""
        for name in sorted(os.listdir(os.path.join(HERE, "..", "specs"))):
            if re.match(r"day-\d+.*\.md$", name):
                with open(os.path.join(HERE, "..", "specs", name), encoding="utf-8") as f:
                    specs += f.read()
        self.assertGreaterEqual(len(written), 62)
        self.assertEqual([k for k in written if not re.search(rf"^- \[[ x]\] {re.escape(k)}\b", specs, re.M)], [])
        for cid, text in written.items():
            self.assertRegex(text, r"^[A-Z].*\.$", cid)
            self.assertLessEqual(len(text), 200, cid)
            self.assertNotIn("`", text, cid)
            self.assertNotRegex(text, r"\bC\d\d\.\d", cid)


class TestInventoryTest(unittest.TestCase):
    MODULE = ("import unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        pass\n"
              "    def test_b(self):\n        text = 'def test_in_a_string(self): pass'\n    def helper(self):\n        pass\n"
              "def test_state():\n    pass\n")

    def inventory(self, paths):
        return {g["key"]: g for g in sd.test_inventory(paths, lambda path: self.MODULE)["groups"]}

    def test_each_file_counts_in_the_first_group_that_names_it(self):
        groups = self.inventory(["tests/test_live_cli.py", "tests/test_dashboard_gap.py", "tests/test_once.py", "scripts/test_break.py"])
        self.assertEqual({k: g["tests"] for k, g in groups.items()}, dict(driver=2, live=2, gap=2, tooling=2))
        self.assertEqual({k: g["files"] for k, g in groups.items()}, dict(driver=1, live=1, gap=1, tooling=1))

    def test_only_a_test_method_of_a_class_counts(self):
        self.assertEqual(self.inventory(["tests/test_x.py"])["driver"]["tests"], 2)

    def test_files_that_are_not_tests_are_left_out_and_the_total_is_the_sum(self):
        out = sd.test_inventory(["tests/helpers.py", "tests/test_a.py", "scripts/test_b.py", "scripts/break.py"], lambda path: self.MODULE)
        self.assertEqual(out["total"], 4)

    def test_a_module_that_does_not_parse_is_named_not_counted_as_zero_silently(self):
        out = sd.test_inventory(["tests/test_bad.py"], lambda path: "def broken(:")
        self.assertEqual(out["total"], 0)
        self.assertEqual(out["unreadable"], ["tests/test_bad.py"])

    def test_every_group_says_when_it_runs(self):
        for g in sd.test_inventory([], lambda path: "")["groups"]:
            self.assertTrue(g["label"] and g["when"], g)


class UserStoriesTest(unittest.TestCase):
    KEYS = [a["key"] for a in sd.ABILITIES]
    TEMPLATE = ("As a [type of user], I want [goal or capability], so that [benefit or outcome]. "
                "Ability: [one of rehearse, stop, loop, park, recover, see, record]")

    def pr(self, number, body=None, branch="day-05/track-a", state="MERGED"):
        return dict(number=number, title=f"PR {number}", url=f"https://example.test/pull/{number}",
                    headRefName=branch, state=state, body=body, mergedAt="2026-11-01T10:00:00Z")

    def written(self, data):
        folder = tempfile.mkdtemp(prefix="user-stories-")
        self.addCleanup(shutil.rmtree, folder, True)
        path = os.path.join(folder, "user-stories.json")
        with open(path, "wb") as f:
            f.write(json.dumps(data).encode("utf-8"))
        return path

    def test_story_section_keeps_the_story_and_the_ability_line_and_drops_the_comment(self):
        body = ("## User story\n\n<!-- plain words only -->\nAs the maintainer, I want x,\nso that y.\n"
                "Ability: loop\n\n## What I built\n\nSomething else.\n")
        self.assertEqual(sd.story_section(body), "As the maintainer, I want x, so that y. Ability: loop")

    def test_story_section_is_empty_without_the_section(self):
        self.assertEqual(sd.story_section(""), "")
        self.assertEqual(sd.story_section("## What I built\n\nx\n"), "")

    def test_story_ability_reads_the_key_and_refuses_the_template_and_other_words(self):
        self.assertEqual(sd.story_ability("Ability: loop"), "loop")
        self.assertEqual(sd.story_ability("Ability: [stop]"), "stop")
        self.assertEqual(sd.story_ability("Ability: LOOP"), "loop")
        self.assertIsNone(sd.story_ability(self.TEMPLATE))
        self.assertIsNone(sd.story_ability("As the maintainer, I want x"))
        self.assertIsNone(sd.story_ability("Ability: flying"))

    def test_story_sentence_drops_the_ability_line_and_the_untouched_template(self):
        self.assertEqual(sd.story_sentence("As the maintainer, I want x, so that y. Ability: loop"),
                         "As the maintainer, I want x, so that y.")
        self.assertEqual(sd.story_sentence(self.TEMPLATE), "")

    def test_story_reader_says_who_the_story_is_written_for(self):
        self.assertEqual(sd.story_reader("As the maintainer, I want x"), "desk")
        self.assertEqual(sd.story_reader("As the maintainer away from my desk, I want x"), "away")
        self.assertEqual(sd.story_reader("As someone reading the project's dashboard, I want x"), "reader")
        self.assertEqual(sd.story_reader("As the maintainer reading the dashboard on my phone, I want x"), "away")
        self.assertEqual(sd.story_reader("no clause here"), "desk")

    def test_user_stories_takes_the_body_then_the_file_and_names_what_is_missing(self):
        prs = [
            self.pr(1, "## User story\n\nAs the maintainer, I want x, so that y.\nAbility: loop\n\n## What I built\n"),
            self.pr(2, "## What I built\n"),
            self.pr(3, "## What I built\n"),
            self.pr(4, "## User story\n\nAs the maintainer, I want z.\nAbility: see\n", state="OPEN"),
        ]
        path = self.written({"2": dict(ability="see", story="As the maintainer, I want w, so that v.")})
        data = sd.user_stories(prs, path)
        self.assertEqual([r["number"] for r in data["stories"]], [1, 2, 3])
        first, second, third = data["stories"]
        self.assertEqual((first["story_source"], first["ability_source"]), ("pr", "pr"))
        self.assertEqual((second["story_source"], second["ability_source"]), ("written", "written"))
        self.assertEqual((second["story"], second["ability"]), ("As the maintainer, I want w, so that v.", "see"))
        self.assertEqual((third["story"], third["ability"]), ("", None))
        self.assertEqual((first["day"], first["date"]), (5, "2026-11-01"))
        self.assertEqual([a["key"] for a in data["abilities"]], self.KEYS)
        self.assertEqual(len(data["problems"]), 2)
        self.assertTrue(all(p.startswith("#3 ") for p in data["problems"]))

    def test_user_stories_gives_area_work_no_day_and_a_pr_with_no_branch_does_not_crash(self):
        prs = [self.pr(6, "## User story\n\nAs the maintainer, I want q.\nAbility: see\n", branch="specs/status-day-05"),
               dict(number=7, title="PR 7", url="https://example.test/pull/7", state="MERGED", body=None, mergedAt="2026-11-01T10:00:00Z")]
        data = sd.user_stories(prs, self.written({}))
        self.assertEqual([(r["number"], r["day"]) for r in data["stories"]], [(6, None), (7, None)])

    def test_user_stories_falls_back_as_if_empty_on_a_missing_or_unreadable_file(self):
        prs = [self.pr(1, "## User story\n\nAs the maintainer, I want x, so that y.\nAbility: loop\n")]
        folder = tempfile.mkdtemp(prefix="user-stories-")
        self.addCleanup(shutil.rmtree, folder, True)
        bad = os.path.join(folder, "bad.json")
        with open(bad, "wb") as f:
            f.write(b"not json")
        for path in (os.path.join(folder, "missing.json"), bad):
            data = sd.user_stories(prs, path)
            self.assertEqual([(r["number"], r["ability"]) for r in data["stories"]], [(1, "loop")])

    def test_the_template_lists_the_abilities_in_the_same_order(self):
        with open(os.path.join(HERE, "..", ".github", "pull_request_template.md"), encoding="utf-8") as f:
            line = re.search(r"^Ability: \[one of ([^\]]*)\]$", f.read(), re.M)
        self.assertIsNotNone(line)
        self.assertEqual(line.group(1).split(", "), self.KEYS)

    def test_the_backfill_names_known_abilities_and_a_story_for_each_of_1_to_29(self):
        with open(os.path.join(HERE, "..", "docs", "dashboard", "user-stories.json"), encoding="utf-8") as f:
            data = json.load(f)
        numbers = [k for k in data if k != "_about"]
        for k in numbers:
            self.assertRegex(k, r"^[1-9][0-9]*$")
            self.assertIn(data[k]["ability"], self.KEYS)
        for n in range(1, 30):
            if str(n) in data:
                self.assertTrue(data[str(n)].get("story", "").strip(), n)
        self.assertEqual(sum(1 for k in numbers if data[k].get("story")), 29)


class PromiseAbilitiesTest(unittest.TestCase):
    STORIES = [dict(number=13, ability="stop"), dict(number=16, ability="stop"),
               dict(number=18, ability="rehearse"), dict(number=5, ability="rehearse"),
               dict(number=28, ability="loop"), dict(number=22, ability="loop"),
               dict(number=29, ability="stop"), dict(number=40, ability=None)]

    def abilities(self, prs):
        index = [dict(id="C1", prs=prs)]
        sd.attach_abilities(index, self.STORIES)
        return index[0]["abilities"]

    def test_a_promise_takes_the_ability_most_of_its_pull_requests_grew(self):
        self.assertEqual(self.abilities([13, 16, 18]), ["stop", "rehearse"])
        self.assertEqual(self.abilities([5, 13, 16]), ["stop", "rehearse"])

    def test_a_tie_goes_to_the_pull_request_cited_first(self):
        self.assertEqual(self.abilities([5, 28]), ["rehearse", "loop"])
        self.assertEqual(self.abilities([22, 29]), ["loop", "stop"])

    def test_a_promise_citing_no_pull_request_with_an_ability_has_none(self):
        self.assertEqual(self.abilities([]), [])
        self.assertEqual(self.abilities([40]), [])
        self.assertEqual(self.abilities([999]), [])
        self.assertEqual(self.abilities([40, 28]), ["loop"])


class YardsticksTest(unittest.TestCase):
    HEAD = "| Question | Evidence it will be judged on | Day 01 | Day 02 |\n| --- | --- | --- | --- |\n"
    COST = ("| Cost per merged PR, main sessions, beside the kit's baseline of $1.86 (`plan.md`, "
            "\"What it is judged against\") | `docs/dashboard/token-usage.json` | $5.51 over 5 merged PRs on "
            "2026-11-06, $1.10 each ($2.45 attributed to Day 1 by branch, $3.06 on `main`) | $7.97 over 3 merged "
            "PRs since Day 01's count, $2.66 each |\n")
    REPLIES = ("| Replies per merged PR, main sessions, beside 34.4 | `docs/dashboard/token-usage.json` | "
               "118 replies over 5 PRs, 23.6 each | 1,311 replies over 32 PRs, 41.0 each |\n")
    ESCAPES = ("| Escapes per day | the Notes' Defect lines | 0 from a day; 1 from the repository's start (D01.15) | "
               "3 from Day 01 (D02.2, D02.3, D02.11) |\n")
    PARKS = "| Parks by reason | the driver's run log | none yet: the driver does not run steps until Phase 1 | none yet |\n"
    REFUSALS = ("| Hook refusals | `docs/dashboard/refusals.json` | 1, read-guard, 2026-11-06 | "
                "13 more, 2026-11-07 to 2026-11-08: 11 read-guard, 1 auditor-guard, 1 step-guard (33 in all) |\n")
    GATES = ("| What each gate cost | `docs/dashboard/gates.json` | Day 1: seen red, 5 runs for $0.36; break on purpose, "
             "8 runs for $0.39 | Day 2: seen red, 5 runs for $0.36; break on purpose, 1 run for $0.12 |\n")
    NOTEBOOK = "# Notebook\n\n## What is being measured\n\n" + HEAD + COST + REPLIES + ESCAPES + PARKS + REFUSALS + GATES
    NOTEBOOK += "\n## Retrospective\n"
    TOKENS = [dict(day=1, input=10, cache_write=90, cache_read=6100, output=100),
              dict(day=1, input=0, cache_write=0, cache_read=200, output=0),
              dict(day=None, input=5, cache_write=5, cache_read=5, output=5)]

    @staticmethod
    def figures(got):
        return {r["key"]: [v["value"] for v in r["values"]] for r in got["rows"]}

    def test_each_yardstick_is_read_as_a_number_for_each_day(self):
        got = sd.yardsticks(sd.conclusion(self.NOTEBOOK), self.TOKENS)
        self.assertEqual(got["days"], [1, 2])
        self.assertEqual([r["key"] for r in got["rows"]],
                         ["cost", "replies", "escapes", "parks", "refusals", "gates", "reread"])
        self.assertEqual(self.figures(got), dict(cost=[1.1, 2.66], replies=[23.6, 41.0], escapes=[0, 3],
                                                 parks=[None, None], refusals=[1, 13], gates=[0.75, 0.48],
                                                 reread=[64.0, None]))
        self.assertEqual(got["problems"], [])
        cost = got["rows"][0]
        self.assertEqual(cost["values"][0]["text"], "$5.51 over 5 merged PRs on 2026-11-06, $1.10 each "
                                                    "($2.45 attributed to Day 1 by branch, $3.06 on `main`)")
        self.assertEqual(got["rows"][-1]["values"][0]["text"],
                         "6,400 tokens read for 100 written, in the sessions tagged Day 1")

    def test_the_baseline_comes_from_the_question(self):
        got = sd.yardsticks(sd.conclusion(self.NOTEBOOK), self.TOKENS)
        baselines = {r["key"]: r["baseline"] for r in got["rows"]}
        self.assertEqual(baselines, dict(cost=1.86, replies=34.4, escapes=None, parks=None, refusals=None,
                                         gates=None, reread=None))

    def test_a_cell_with_no_figure_is_a_problem_line_and_never_a_guess(self):
        old = ["$7.97 over 3 merged PRs since Day 01's count, $2.66 each", "1, read-guard, 2026-11-06"]
        for text in old:
            self.assertIn(text, self.NOTEBOOK)
        notebook = self.NOTEBOOK.replace(old[0], "about three dollars a pull request")
        notebook = notebook.replace(old[1], "read-guard, once")
        self.assertNotIn(old[0], notebook)
        self.assertNotIn(old[1], notebook)
        got = sd.yardsticks(sd.conclusion(notebook), self.TOKENS)
        figures = self.figures(got)
        self.assertIsNone(figures["cost"][1])
        self.assertIsNone(figures["refusals"][0])
        self.assertEqual(got["problems"], ["Day 02, Cost per merged PR: no figure read from the notebook's cell",
                                           "Day 01, Hook refusals: no figure read from the notebook's cell"])

    def test_a_yardstick_the_notebook_does_not_measure_is_left_out(self):
        got = sd.yardsticks(sd.conclusion(ConclusionTest.NOTEBOOK), self.TOKENS)
        self.assertEqual([r["key"] for r in got["rows"]], ["reread"])
        self.assertEqual(got["problems"], [])
        empty = dict(reads=[], measured=[], measured_head=[])
        self.assertEqual(sd.yardsticks(empty, self.TOKENS), dict(days=[], rows=[], problems=[]))

    def test_the_notebook_on_main_reads_with_no_problem(self):
        with open(os.path.join(HERE, "..", "docs", "lab-notebook.md"), encoding="utf-8") as f:
            text = f.read()
        got = sd.yardsticks(sd.conclusion(text), [])
        self.assertEqual(got["problems"], [])
        self.assertEqual(got["days"][:6], [1, 2, 3, 4, 5, 6])
        self.assertEqual([r["key"] for r in got["rows"]],
                         ["cost", "replies", "escapes", "parks", "refusals", "gates"])
        figures = self.figures(got)
        expected = dict(cost=[1.1, 2.66, 1.67, 2.16, 1.96, 2.61], replies=[23.6, 46.7, 31.2, 36.3, 33.2, 41.0],
                        escapes=[0, 3, 0, 0, 0, 2], refusals=[1, 2, 1, 8, 8, 13],
                        gates=[0.75, 0.48, 1.7, 4.93, 6.04, 4.01])
        for key, values in expected.items():
            self.assertEqual(figures[key][:6], values, key)

    def test_each_yardstick_has_its_average_so_far(self):
        got = sd.yardsticks(sd.conclusion(self.NOTEBOOK), self.TOKENS)
        average = {r["key"]: (r["average_over"], r["average"]) for r in got["rows"]}
        self.assertEqual(average, dict(
            cost=("pull requests", [1.1, 1.69]),          # $5.51 over 5, then $13.48 over 8, not the mean of 1.10 and 2.66
            replies=("pull requests", [23.6, 38.62]),     # 118 over 5, then 1,429 over 37
            escapes=("days", [0.0, 1.5]), parks=("days", [None, None]), refusals=("days", [1.0, 7.0]),
            gates=("days", [0.75, 0.61]),
            reread=("tokens written", [64.0, 64.0])))     # Day 02 wrote nothing: it is left out, not a zero
        self.assertEqual(got["problems"], [])

    def test_an_average_stops_at_a_cell_with_no_total(self):
        notebook = self.NOTEBOOK.replace("$7.97 over 3 merged PRs since Day 01's count, $2.66 each", "$2.66 each")
        got = sd.yardsticks(sd.conclusion(notebook), [])
        self.assertEqual(got["rows"][0]["average"], [1.1, None])
        self.assertEqual(got["problems"], ["Day 02, Cost per merged PR: no total and count read from the notebook's cell"])


class LookAheadTest(unittest.TestCase):
    """What the graph that looks ahead reads: at each merge, the promises built and written and the hand-offs open."""

    NOTES = ("## Notes\n- **Hand-off** H01.1 → Day 02: the key.\n- **Hand-off** H01.2 → Day 03: the queue, after H01.1.\n"
             "- For Day 02: the rest.\n")

    def test_a_hand_off_has_the_merge_that_opened_it_and_the_merge_that_closed_it(self):
        repo = Repo().merge({"specs/day-01-a.md": "# Day 01\n", "specs/day-02-b.md": "# Day 02\n",
                             "src/Foo.py": "# Day 02 moves this.\n"})
        repo.merge({"specs/day-01-a.md": "# Day 01\n\n" + self.NOTES + "- For Day 03: later.\n"})
        repo.merge({"specs/day-02-b.md": "# Day 02\n\nPicks up H01.1. It reads `Foo`.\n",
                    "src/Bar.py": "# Day 02 keeps this.\n"})
        repo.merge({"specs/day-01-a.md": "# Day 01\n\n" + self.NOTES})
        repo.snaps[2]["branch"] = "day-02/spec-x"
        days = [dict(day=1, file="specs/day-01-a.md", status="done", prs=[dict(number=1, kind="close")]),
                dict(day=2, file="specs/day-02-b.md", status="done",
                     prs=[dict(number=2, kind="spec"), dict(number=3, kind="close")])]
        try:
            got = repo.inside(lambda blobs: sd.look_ahead(repo.snaps, days, [], [1, 2, 3], blobs))
        finally:
            repo.close()
        self.assertEqual([(h["id"] or h["source"], h["to"], h["opened_pr"], h["closed_pr"], h["how"])
                          for h in got["hand_offs"]], [
            ("src/Foo.py", [2], None, 2, "picked"),         # there from the start; Day 02's spec names the file
            ("Day 01 Notes", [2], 1, 3, "lapsed"),          # Day 02 closed and its spec never named Day 01
            ("Day 01 Notes", [3], 1, 3, "withdrawn"),       # the line was taken out of the Notes
            ("H01.1", [2], 1, 2, "picked"),
            ("H01.2", [3], 1, None, None)])                 # it cites H01.1, and Day 02 citing that picks up only H01.1
        # src/Bar.py's comment names Day 02 and Day 02's own merge wrote it: never a hand-off.
        self.assertEqual([(c["open"], c["open_numbered"], c["opened"], c["closed"]) for c in got["columns"]],
                         [(1, 0, 1, 0), (5, 2, 4, 0), (3, 1, 0, 2), (1, 1, 0, 2)])

    def test_a_promise_is_built_at_the_last_merge_its_evidence_cites_and_written_when_its_spec_merged(self):
        one = "## Acceptance criteria\n- [{0}] C01.1 **new** — a.\n- [{0}] C01.2 **new** — b.\n- [{0}] C01.3 **hold** — c.\n"
        two = "## Acceptance criteria\n- [ ] C02.1 **new** — a.\n- [ ] C02.2 **new** — b.\n- [ ] C02.3 **hold** — c.\n"
        repo = Repo().merge({"specs/day-01-a.md": one.format(" ")})
        repo.merge({"src/a.py": "a = 1\n"}).merge({"src/b.py": "b = 1\n"})
        repo.merge({"specs/day-01-a.md": one.format("x")}).merge({"specs/day-02-b.md": two}).merge({"src/c.py": "c = 1\n"})
        repo.snaps[5]["branch"] = "day-02/track-a-x"
        days = [dict(day=1, status="done", tracks=["A", "B"],
                     prs=[dict(number=1, kind="code"), dict(number=2, kind="code"), dict(number=3, kind="close")]),
                dict(day=2, status="active", tracks=["A", "B"], tracks_merged=["A"],
                     track_work=dict(A="The first: C02.1", B="The second: C02.2"),
                     prs=[dict(number=4, kind="spec"), dict(number=5, kind="code")])]
        index = [dict(id="C01.1", day=1, ticked=True, prs=[1], track="A"),
                 dict(id="C01.2", day=1, ticked=True, prs=[1, 2], track="B"),
                 dict(id="C01.3", day=1, ticked=True, prs=[], track=None),     # cites no PR: built at its day's close
                 dict(id="C02.1", day=2, ticked=False, prs=[], track="A"),     # the open day: built when its track merged
                 dict(id="C02.2", day=2, ticked=False, prs=[], track="B"),
                 dict(id="C02.3", day=2, ticked=False, prs=[], track=None)]
        try:
            got = repo.inside(lambda blobs: sd.look_ahead(repo.snaps, days, index, [1, 2], blobs))
        finally:
            repo.close()
        self.assertEqual([(c["pr"], c["built"], c["written"], c["got"]) for c in got["columns"]], [
            (None, 0, 3, []), (1, 1, 3, ["C01.1"]), (2, 2, 3, ["C01.2"]), (3, 3, 3, ["C01.3"]),
            (4, 3, 6, []), (5, 4, 6, ["C02.1"])])
        self.assertEqual((got["built"], got["written"]), (4, 6))
        self.assertEqual(got["pending"], dict(day=2, tracks=[dict(track="B", ids=["C02.2"])], at_close=["C02.3"]))


class DataBranch:
    """A repository whose remote holds a dashboard-data branch with these files ({name: text}), or no such
    branch with None; sd.PAGE points into it and sd.data_branch() has fetched it. The working tree holds
    other files of the same names: the page must not read them."""

    def __init__(self, files):
        self.files = files

    def __enter__(self):
        self.tmp = tempfile.mkdtemp()
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
        repo, origin = os.path.join(self.tmp, "repo"), os.path.join(self.tmp, "origin.git")
        git = lambda *a: subprocess.run(["git", "-C", repo, *a], capture_output=True, env=env, check=True)  # noqa: E731
        subprocess.run(["git", "init", "-q", "--bare", origin], capture_output=True, check=True)
        subprocess.run(["git", "init", "-q", repo], capture_output=True, check=True)
        git("remote", "add", "origin", origin)
        page = os.path.join(repo, "docs", "dashboard")
        os.makedirs(page)
        if self.files is not None:
            git("checkout", "-q", "--orphan", "dashboard-data")
            for name, text in self.files.items():
                with open(os.path.join(page, name), "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
            git("add", "-A")
            git("commit", "-q", "--allow-empty", "-m", "count")
            git("push", "-q", "origin", "dashboard-data")
        for name in sd.DATA_FILES:
            with open(os.path.join(page, name), "w", encoding="utf-8") as f:
                f.write('{"left": "in the working tree"}')
        self.patch = patch_all("PAGE", page)
        self.patch.__enter__()
        self.saved = dict(sd.DATA)
        sd.data_branch()
        return self

    def __exit__(self, *exc):
        self.patch.__exit__(None, None, None)
        sd.DATA.update(self.saved)
        shutil.rmtree(self.tmp, ignore_errors=True)


class DataBranchTest(unittest.TestCase):
    def test_the_files_are_read_from_the_data_branch_and_what_it_lacks_is_named(self):
        with DataBranch({"counted.json": '{"at": "2026-11-08T20:00:00+01:00"}\n', "gates.json": "[]\n"}):
            self.assertEqual(sd.counted(), dict(at="2026-11-08T20:00:00+01:00"))
            self.assertEqual(sd.refusals("gates.json"), [])
            self.assertEqual(sd.refusals(), [])  # absent on the branch, though the working tree has one
            self.assertEqual(sd.replay_history(), dict(state="absent"))
            got = sd.data_source()
            self.assertEqual(len(got["commit"]), 12)
            self.assertEqual(got["absent"], [n for n in sd.DATA_FILES if n not in ("counted.json", "gates.json")])

    def test_with_no_data_branch_every_file_is_absent_and_none_is_read_from_the_working_tree(self):
        with DataBranch(None):
            self.assertIsNone(sd.counted())
            self.assertEqual((sd.token_usage(), sd.driver_runs([])["steps"]), ([], None))
            self.assertEqual(sd.replay_history(), dict(state="absent"))
            self.assertEqual(sd.data_source(), dict(branch="dashboard-data", commit=None, at=None, absent=list(sd.DATA_FILES)))

    def test_the_re_check_rows_on_the_branch_are_read(self):
        rows = {"schema": 1, "rows": [dict(n=1, merge="m", pr=2, sample="all", criterion="C01.1", day="01", check="t",
                                            state="holds", platform="linux", key="k")]}
        with DataBranch({"replay-history.json": json.dumps(rows)}):
            got = sd.replay_history()
        self.assertEqual((got["state"], [c["criterion"] for c in got["cells"]]), ("loaded", ["C01.1"]))


def parked(number, title, opened, closed=None):
    return dict(number=number, title=title, url=f"https://github.com/example/shop/issues/{number}", opened=opened, closed=closed)


class DriverRunsTest(unittest.TestCase):
    """The driver's steps come from the file driver-runs.py wrote, its parks' waits from GitHub."""
    LINE = "park: the session parked: a criterion cannot be met as written (session `s1`)"

    def test_the_parked_issues_are_read_open_and_closed_and_come_out_by_number(self):
        listed = [dict(number=9, title="park: b", url="u9", createdAt="2026-11-12T13:00:05Z", closedAt=None),
                  dict(number=4, title="park: a", url="u4", createdAt="2026-11-12T09:00:05Z", closedAt="2026-11-12T10:10:00Z")]
        with patch_all("run", return_value=json.dumps(listed)) as run:
            got = sd.parked_issues()
        self.assertEqual(got, [dict(number=4, title="park: a", url="u4", opened="2026-11-12T09:00:05Z", closed="2026-11-12T10:10:00Z"),
                               dict(number=9, title="park: b", url="u9", opened="2026-11-12T13:00:05Z", closed=None)])
        asked = run.call_args.args
        self.assertEqual(asked[:7], ("gh", "issue", "list", "--label", "parked", "--state", "all"))

    def test_with_no_remote_or_a_gh_that_refuses_the_parks_are_unread_not_none_found(self):
        with patch_all("run") as run:
            self.assertIsNone(sd.parked_issues(sd.NO_REMOTE))
            run.assert_not_called()
        refused = subprocess.CalledProcessError(1, "gh", stderr="issues are disabled")
        with patch_all("run", side_effect=refused), mock.patch("sys.stderr"):
            self.assertIsNone(sd.parked_issues())

    def test_a_park_is_given_the_issue_of_its_line_that_was_open_for_it(self):
        park = dict(at="2026-11-12T13:00:00Z", line=self.LINE)
        answered = parked(3, self.LINE, "2026-11-11T09:00:05Z", "2026-11-11T09:30:00Z")
        opened = parked(5, self.LINE, "2026-11-12T13:00:04Z", "2026-11-12T14:10:00Z")
        later = parked(8, self.LINE, "2026-11-12T16:00:00Z")
        other = parked(6, "park: #12 carries Oversized:", "2026-11-12T13:00:04Z")
        self.assertEqual(sd.park_issue(park, [answered, opened, later, other]), 5)
        # Parked again while its issue was open: the driver comments on that issue and opens no other.
        self.assertEqual(sd.park_issue(dict(park, at="2026-11-12T13:40:00Z"), [answered, opened, later, other]), 5)
        # No issue was opened for it (gh failed): one closed before it, or opened long after, is not its.
        self.assertIsNone(sd.park_issue(park, [answered, later, other]))
        self.assertIsNone(sd.park_issue(dict(at="not a time", line=self.LINE), [opened]))
        self.assertIsNone(sd.park_issue(dict(at="2026-11-12T13:00:00", line=self.LINE), [opened]))

    def test_an_issue_is_titled_with_the_first_200_characters_of_the_line(self):
        line = "park: " + "x" * 300
        issue = parked(5, line[:200], "2026-11-12T13:00:04Z")
        self.assertEqual(sd.park_issue(dict(at="2026-11-12T13:00:00Z", line=line), [issue]), 5)

    def test_before_the_first_count_there_are_no_steps_and_the_parks_are_still_githubs(self):
        issues = [parked(5, self.LINE, "2026-11-12T13:00:04Z")]
        with DataBranch({}):
            got = sd.driver_runs(issues)
        self.assertEqual(got, dict(source="docs/dashboard/driver-runs.json", counted=None, steps=None, parks=issues))
        self.assertEqual(sd.driver_runs(None, {})["parks"], None)

    def test_the_counted_file_is_read_from_the_data_branch_and_each_park_names_its_issue(self):
        step = dict(step="Day 08 Track A: the first track", day=8, prefix="day-08/track-a", sessions=[], fixes=0, crashes=0,
                    pr=None, merged=None, ended="parked",
                    parks=[dict(at="2026-11-12T13:00:00Z", line=self.LINE, by="maintainer"),
                           dict(at="2026-11-12T15:00:00Z", line="park: #12 carries Oversized:", by="maintainer")])
        issues = [parked(5, self.LINE, "2026-11-12T13:00:04Z", "2026-11-12T14:10:00Z")]
        with DataBranch({"driver-runs.json": json.dumps(dict(counted="2026-11-12T18:00:00+01:00", steps=[step]))}):
            got = sd.driver_runs(issues)
        self.assertEqual(got["counted"], "2026-11-12T18:00:00+01:00")
        self.assertEqual([p["issue"] for p in got["steps"][0]["parks"]], [5, None])
        self.assertEqual({k: v for k, v in got["steps"][0].items() if k != "parks"}, {k: v for k, v in step.items() if k != "parks"})
        # With the parks unread, the steps are still the file's, and no park names an issue.
        self.assertEqual([p["issue"] for p in sd.driver_runs(None, dict(steps=[step]))["steps"][0]["parks"]], [None, None])


if __name__ == "__main__":
    unittest.main()
