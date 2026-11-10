"""scripts/evidence.py fails a ticked criterion whose test, Verify line or break does not hold up.

Each test builds a small repository with one day's close merged, writes the day's spec and its
breaks file, and runs evidence.py over it as a subprocess.

    python scripts/test_evidence.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "evidence.py")
GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t")
# A check that fails, with an assertion line, when app.txt says `broken`.
CHECK = [sys.executable, "-c",
         "import sys; sys.exit('AssertionError: broken') if 'broken' in open('app.txt').read() else None"]
BREAK = {"what": "the ok removed", "file": "app.txt", "find": "ok", "replace": "broken", "command": CHECK}


UNTICKED = "- [ ] C1.2 **new** — not ticked: `CliTest.test_never` is not checked.\n"


def spec(test="CliTest.test_a", verify="echo 0    # 0", report="AssertionError: broken (#2)", more=""):
    return (f"# Day 01\n\n## Acceptance criteria\n"
            f"- [x] C1.1 **new** — Test: `{test}`.\n"
            f"      broken: the ok removed → {report}\n{more}\n"
            f"## Verify\n```bash\n{verify}\n```\n")


class Repo(unittest.TestCase):
    """The fixture: a repository with one day's close merged, and helpers to write and run a spec in it."""

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.write("tests/test_cli.py",
                   "class CliTest(unittest.TestCase):\n    def test_a(self):\n        pass\n")
        # a project whose tests are one tests.py at the root (python-json-pointer), and a module that is not a test file
        self.write("tests.py", "class RootTest(unittest.TestCase):\n    def test_b(self):\n        pass\n")
        self.write("helper.py", "class HelperTest:\n    def test_c(self):\n        pass\n")
        self.write("app.txt", "ok\n")
        self.git("init", "-q", "-b", "main")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.git("switch", "-q", "-c", "day-01/close-the-day")
        self.write("close.txt", "closed\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "close")
        self.git("switch", "-q", "main")
        self.git("merge", "-q", "--no-ff", "-m", "Merge pull request #2 from me/day-01/close-the-day",
                 "day-01/close-the-day")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, env=GIT_ENV, capture_output=True, text=True,
                              check=True).stdout

    def write(self, path, text):
        full = os.path.join(self.repo, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def run_evidence(self, text, breaks=(BREAK,), *args):
        self.write("specs/day-01-x.md", text)
        self.write("specs/breaks/day-01.json", json.dumps(list(breaks)))
        return subprocess.run([sys.executable, SCRIPT, "specs/day-01-x.md", *args], cwd=self.repo, env=GIT_ENV,
                              capture_output=True, text=True, encoding="utf-8")

    def report(self, text, breaks=(BREAK,)):
        """The run and the report it wrote."""
        run = self.run_evidence(text, breaks, "--json", "report.json")
        with open(os.path.join(self.repo, "report.json"), encoding="utf-8") as f:
            return run, json.load(f)

    def statuses(self, report):
        return {c["id"].split("/", 1)[1]: c["status"] for d in report["days"] for c in d["checks"]}

    def failures(self, run):
        return [l for l in run.stdout.splitlines() if l.startswith("FAIL")]

    def close_with(self, text):
        """A second close of the day, which merges the spec as written."""
        self.git("switch", "-q", "-c", "day-01/close-the-day-2")
        self.write("specs/day-01-x.md", text)
        self.git("add", "specs/day-01-x.md")
        self.git("commit", "-q", "-m", "spec")
        self.git("switch", "-q", "main")
        self.git("merge", "-q", "--no-ff", "-m", "Merge pull request #4 from me/day-01/close-the-day-2",
                 "day-01/close-the-day-2")


class EvidenceTest(Repo):
    """Each check a spec's close makes, and what it reports."""

    def test_evidence_that_holds_passes(self):
        run = self.run_evidence(spec())
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("all evidence holds", run.stdout)
        self.assertIn("ok    C1.1 proved by a test, a break", run.stdout)
        self.assertIn("C1.1 broken: the ok removed", run.stdout)

    def test_an_unticked_criterion_with_no_not_proven_line_fails(self):
        run = self.run_evidence(spec(more=UNTICKED))
        self.assertEqual(run.returncode, 1, run.stdout)
        self.assertEqual(self.failures(run), ["FAIL  C1.2 not proven → no Not proven: line under it at "
                                              + self.git("rev-parse", "--short=7", "HEAD").strip()])
        self.assertNotIn("test_never", run.stdout)

    def test_an_unticked_criterion_passes_with_a_not_proven_line_only_as_the_close_merged_it(self):
        text = spec(more=UNTICKED + "      Not proven: the page needs a browser.\n")
        run = self.run_evidence(text)
        self.assertIn("FAIL  C1.2 not proven → no Not proven: line under it at", run.stdout)
        self.close_with(text)
        run, report = self.report(text)
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertIn("ok    C1.2 not proven → the page needs a browser.", run.stdout)
        self.assertEqual(self.statuses(report)["C1.2/proof"], "passed")

    def test_a_renamed_test_fails(self):
        run = self.run_evidence(spec(test="CliTest.test_renamed"))
        self.assertEqual(run.returncode, 1)
        self.assertEqual(len(self.failures(run)), 1, run.stdout)
        self.assertIn("CliTest.test_renamed → not defined", run.stdout)

    def test_a_test_in_a_root_tests_py_is_found_and_one_in_another_module_is_not(self):
        run = self.run_evidence(spec(test="RootTest.test_b"))
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("all evidence holds", run.stdout)
        run = self.run_evidence(spec(test="HelperTest.test_c"))
        self.assertEqual(run.returncode, 1)
        self.assertIn("HelperTest.test_c → not defined", run.stdout)

    def test_a_test_in_another_class_fails(self):
        run = self.run_evidence(spec(test="OtherTest.test_a"))
        self.assertIn("OtherTest.test_a → not defined", run.stdout)
        self.assertEqual(run.returncode, 1)

    def test_a_verify_line_whose_output_differs_from_its_comment_fails(self):
        run = self.run_evidence(spec(verify="echo 1    # 0"))
        self.assertEqual(run.returncode, 1)
        self.assertIn("wanted a line '0', got '1'", run.stdout)

    def test_a_verify_line_without_a_comment_fails_on_a_nonzero_exit(self):
        run = self.run_evidence(spec(verify="false"))
        self.assertIn("Verify: false → exit 1", run.stdout)

    def test_nothing_and_an_exit_status_in_a_comment_are_both_checked(self):
        self.assertEqual(self.run_evidence(spec(verify="true    # nothing, exit 0")).returncode, 0)
        run = self.run_evidence(spec(verify="echo x; false    # nothing, exit 0"))
        self.assertIn("wanted nothing, got 'x'", run.stdout)

    def test_main_in_a_verify_line_means_the_close_s_first_parent(self):
        run = self.run_evidence(spec(verify=f"git rev-parse main    # {self.base}"))
        self.assertEqual(run.returncode, 0, run.stdout)
        run = self.run_evidence(spec(verify=f"true && git rev-parse main | cat    # {self.base}"))
        self.assertEqual(run.returncode, 0, run.stdout)

    def test_main_given_to_another_command_or_repository_is_left_as_written(self):
        # Day 05's Verify ran `bearing snapshot <fixture repo> main`: the fixture's own branch.
        for verify in ("echo main    # main", "git -C . rev-parse --abbrev-ref main    # main"):
            run = self.run_evidence(spec(verify=verify))
            self.assertEqual(run.returncode, 0, run.stdout)

    def test_a_break_with_no_recorded_arguments_fails(self):
        run = self.run_evidence(spec(), breaks=())
        self.assertEqual(run.returncode, 1)
        self.assertIn("C1.1 broken: the ok removed → no arguments in", run.stdout)

    def test_a_break_that_reports_something_else_fails(self):
        run = self.run_evidence(spec(report="AssertionError: something else"))
        self.assertEqual(run.returncode, 1)
        self.assertIn("reported 'AssertionError: broken', the spec says 'AssertionError: something else'",
                      run.stdout)

    def test_a_recorded_report_that_holds_a_uuid_still_replays(self):
        # the break runs once with --replay: a uuid in the report is compared with the spec, not refused
        message = "AssertionError: session 00000000-0000-4000-8000-000000000000 was not resumed"
        check = [sys.executable, "-c", f"import sys; sys.exit({message!r}) if 'broken' in open('app.txt').read() "
                 "else None"]
        run = self.run_evidence(spec(report=message), breaks=(dict(BREAK, command=check),))
        self.assertEqual(run.returncode, 0)  # no output in the message: it holds the uuid
        self.assertEqual(run.stdout.count("all evidence holds"), 1)

    def test_a_name_recorded_twice_fails_rather_than_replay_the_last(self):
        # bearing #66: two breaks named alike, and the second entry replaced the first.
        run = self.run_evidence(spec(), breaks=(dict(BREAK, command=[sys.executable, "-c", "pass"]), BREAK))
        self.assertEqual(run.returncode, 1)
        self.assertIn("C1.1 broken: the ok removed → recorded 2 times in", run.stdout)

    def test_a_break_the_check_cannot_see_fails(self):
        run = self.run_evidence(spec(), breaks=(dict(BREAK, command=[sys.executable, "-c", "pass"]),))
        self.assertEqual(run.returncode, 1)
        self.assertIn("passed with the break in", run.stdout)

    def test_a_check_judged_by_what_it_prints_sees_the_break_only_with_its_expected_stdout(self):
        # as `grep -c`: it prints a count, and exits 0 at 1 and with the break in
        check = [sys.executable, "-c", "print(open('app.txt').read().split().count('ok'))"]
        run = self.run_evidence(spec(report="0"), breaks=(dict(BREAK, command=check, expect_stdout="^1$"),))
        self.assertEqual(run.returncode, 0, run.stdout)
        run = self.run_evidence(spec(report="0"), breaks=(dict(BREAK, command=check),))
        self.assertEqual(run.returncode, 1)
        self.assertIn("passed with the break in", run.stdout)

    def test_a_temporary_directory_s_name_does_not_count_as_a_difference(self):
        report = "AssertionError: C:\\Temp\\tmpab12cd34\\a.txt"
        check = [sys.executable, "-c",
                 "import sys; sys.exit('AssertionError: C:\\\\Temp\\\\tmpzz99yy00\\\\a.txt') "
                 "if 'broken' in open('app.txt').read() else None"]
        run = self.run_evidence(spec(report=report), breaks=(dict(BREAK, command=check),))
        self.assertEqual(run.returncode, 0, run.stdout)

    def test_pytest_s_duration_does_not_count_as_a_difference_and_its_counts_do(self):
        # pytest -q sums a failure up as "1 failed in 0.14s", and the seconds change every run.
        check = [sys.executable, "-c",
                 "import sys; sys.exit('1 failed in 0.37s') if 'broken' in open('app.txt').read() else None"]
        for recorded in ("1 failed in 0.14s", "1 failed in 61.20s (0:01:01)"):
            run = self.run_evidence(spec(report=recorded), breaks=(dict(BREAK, command=check),))
            self.assertEqual(run.returncode, 0, run.stdout)
        run = self.run_evidence(spec(report="2 failed in 0.37s"), breaks=(dict(BREAK, command=check),))
        self.assertEqual(run.returncode, 1, run.stdout)
        self.assertIn("reported '1 failed in 0.37s', the spec says '2 failed in 0.37s'", run.stdout)

    def test_an_arrow_inside_what_was_broken_cannot_run_again(self):
        # break.py refuses it, since spec-drift.py ends <what> at the first arrow: not run, not failed.
        what = "the ok (ok → broken)"
        run = self.run_evidence(spec().replace("the ok removed", what), breaks=(dict(BREAK, what=what),))
        self.assertEqual(run.returncode, 1, run.stdout)
        self.assertIn("ERR   C1.1 broken: the ok (ok → broken) → break.py: --what holds an arrow", run.stdout)
        self.assertIn("1 could not run", run.stdout)

    def test_a_report_recorded_across_lines_with_its_backslashes_undoubled_is_the_same(self):
        report = "AssertionError: 'C:\\x\n'"  # as a close pasted it: \\ as \, \n as a new line
        check = [sys.executable, "-c", "import sys; sys.exit(\"AssertionError: 'C:\\\\\\\\x\\\\n'\") "
                 "if 'broken' in open('app.txt').read() else None"]
        run = self.run_evidence(spec(report=report), breaks=(dict(BREAK, command=check),))
        self.assertEqual(run.returncode, 0, run.stdout)
        run = self.run_evidence(spec(report=report.replace("x", "y")), breaks=(dict(BREAK, command=check),))
        self.assertEqual(run.returncode, 1, run.stdout)

    def test_a_bash_command_runs_in_git_s_bash(self):
        check = ["bash", "-c", "grep -qx ok app.txt || { echo 'AssertionError: broken'; exit 1; }"]
        run = self.run_evidence(spec(), breaks=(dict(BREAK, command=check),))
        self.assertEqual(run.returncode, 0, run.stdout)

    def test_a_near_miss_recorded_as_passing_must_pass_and_report_its_last_line(self):
        check = [sys.executable, "-c", "print('removed=0')"]
        near = dict(BREAK, command=check, passes=True)
        run = self.run_evidence(spec(report="removed=0"), breaks=(near,))
        self.assertEqual(run.returncode, 0, run.stdout)
        run = self.run_evidence(spec(), breaks=(dict(BREAK, passes=True),))
        self.assertEqual(run.returncode, 1)
        self.assertIn("failed with the break in: this near miss should pass", run.stdout)

    def test_a_posix_only_break_is_not_applicable_on_windows_and_replays_elsewhere(self):
        # A break the check cannot see: replayed, it fails; on Windows it is not replayed at all.
        blind = dict(BREAK, command=[sys.executable, "-c", "pass"], posix_only=True)
        run, report = self.report(spec(), breaks=(blind,))
        check = [c for d in report["days"] for c in d["checks"] if c["kind"] == "break"][0]
        if os.name == "nt":
            self.assertEqual((check["status"], check["diagnostic"]),
                             ("not_applicable", "a POSIX-only break: not replayed on Windows"))
        else:
            self.assertEqual(check["status"], "failed", check)
            self.assertIn("The check passed with the break in", check["diagnostic"])

    def test_a_break_recorded_at_a_commit_runs_there_not_at_the_close(self):
        check = [sys.executable, "-c", "import os, sys; sys.exit('AssertionError: broken') if 'broken' in "
                 "open('app.txt').read() and not os.path.exists('close.txt') else None"]
        run = self.run_evidence(spec(), breaks=(dict(BREAK, command=check),))
        self.assertIn("passed with the break in", run.stdout)
        run = self.run_evidence(spec(), breaks=(dict(BREAK, command=check, at=self.base),))
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertEqual(len(self.git("worktree", "list").splitlines()), 1)

    def test_a_day_whose_close_has_not_merged_fails(self):
        self.write("specs/day-02-y.md", spec())
        run = subprocess.run([sys.executable, SCRIPT, "specs/day-02-y.md"], cwd=self.repo, env=GIT_ENV,
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(run.returncode, 1)
        self.assertIn("no merged day-02/close-the-day on main", run.stdout)

    def test_the_worktree_is_removed(self):
        self.run_evidence(spec())
        self.assertEqual(len(self.git("worktree", "list").splitlines()), 1)

    def test_the_report_holds_the_checks_the_console_prints(self):
        run, report = self.report(spec())
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertEqual(self.statuses(report), {"close": "passed", "C1.1/test/CliTest.test_a": "passed",
                                                 "C1.1/proof": "passed", "verify/1": "passed",
                                                 "C1.1/break/the ok removed": "passed"})
        printed = run.stdout.splitlines()[:-1]
        self.assertEqual(len(printed), 5)
        for line, check in zip(printed, report["days"][0]["checks"]):
            self.assertEqual(line, "ok    " + check["label"])
        self.assertEqual(report["summary"]["break"], {"passed": 1, "failed": 0, "error": 0, "not_applicable": 0})

    def test_the_report_writes_each_check_on_a_line_of_its_own(self):
        self.report(spec())
        with open(os.path.join(self.repo, "report.json"), encoding="utf-8") as f:
            lines = f.read().splitlines()
        report = json.loads("\n".join(lines))
        for check in report["days"][0]["checks"]:
            self.assertIn("  " + json.dumps(check, ensure_ascii=False, separators=(",", ":")),
                          [l.rstrip(",") for l in lines])

    def test_the_report_records_the_commits_and_inputs_checked(self):
        close = self.git("rev-parse", "HEAD").strip()
        self.run_evidence(spec())
        self.git("add", "specs")
        self.git("commit", "-q", "-m", "specs")
        _, report = self.report(spec())  # the same text: the files are as committed
        day = report["days"][0]
        self.assertEqual((report["schema"], report["ref"]), (1, "main"))
        self.assertEqual(report["ref_sha"], self.git("rev-parse", "HEAD").strip())
        self.assertEqual((day["close_sha"], day["verify_base_sha"]), (close, self.base))
        self.assertEqual((day["spec"]["state"], day["spec"]["revision"]), ("clean", report["ref_sha"]))
        self.assertEqual(len(day["breaks"]["sha256"]), 64)
        _, report = self.report(spec(verify="true"))
        self.assertEqual((report["days"][0]["spec"]["state"], report["days"][0]["spec"]["revision"]), ("edited", None))

    def test_a_break_recorded_at_a_commit_reports_that_commit(self):
        _, report = self.report(spec(), breaks=(dict(BREAK, at=self.base),))
        check = report["days"][0]["checks"][-1]
        self.assertEqual((check["status"], check["sha"]), ("passed", self.base))

    def test_a_criterion_with_no_test_command_or_break_fails_unless_a_reader_judged_it(self):
        by_eye = spec().replace("Test: `CliTest.test_a`", "Test: by eye")
        run, report = self.report(by_eye)
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertIn("ok    C1.1 proved by a break", run.stdout)
        self.assertIn("n/a   C1.1 named test → none: checked by its break", run.stdout)
        text = by_eye.replace("      broken: the ok removed → AssertionError: broken (#2)\n", "")
        run = self.run_evidence(text)
        self.assertEqual(run.returncode, 1)
        self.assertEqual(self.failures(run), ["FAIL  C1.1 proved by nothing → no test, command or break, and no "
                                              "Not proven: line under it at " + self.git("rev-parse", "--short=7",
                                                                                          "HEAD").strip()])
        text = text.replace("by eye.\n", "by eye.\n      Not proven: a reader compared the page with the design.\n")
        self.close_with(text)
        run = self.run_evidence(text)
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertIn("ok    C1.1 proved by a reader → a reader compared the page with the design.", run.stdout)
        self.assertIn("n/a   C1.1 named test → none: judged by a reader", run.stdout)

    def test_a_criterion_checked_by_a_command_is_not_applicable_for_a_named_test(self):
        run, report = self.report(spec().replace("`CliTest.test_a`", "`git diff --exit-code main`"))
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertEqual(self.statuses(report)["C1.1/test"], "not_applicable")
        self.assertIn("n/a   C1.1 named test → none: checked by `git diff --exit-code main`", run.stdout)

    def test_a_missing_verify_block_fails(self):
        run, report = self.report(spec().split("## Verify")[0])
        self.assertEqual(run.returncode, 1)
        self.assertEqual(self.statuses(report)["verify"], "failed")

    def test_a_hold_criterion_with_no_broken_line_fails_and_broken_none_is_not_applicable(self):
        hold = spec().replace("**new**", "**hold**")
        run, report = self.report(hold.replace("      broken: the ok removed → AssertionError: broken (#2)\n", ""))
        self.assertEqual(run.returncode, 1)
        self.assertEqual(self.statuses(report)["C1.1/break"], "failed")
        run, report = self.report(hold.replace("the ok removed → AssertionError: broken", "none → docs only"))
        self.assertEqual(run.returncode, 0, run.stdout)
        check = report["days"][0]["checks"][-1]
        self.assertEqual((check["status"], check["diagnostic"]), ("not_applicable", "docs only (#2)"))

    def test_a_spec_with_no_ticked_criterion_does_not_pass(self):
        run, report = self.report(spec().replace("- [x]", "- [ ]"))
        self.assertEqual(run.returncode, 1)
        self.assertEqual(self.statuses(report)["criteria"], "failed")

    def test_a_break_that_cannot_be_run_is_an_error_and_still_leaves_a_report(self):
        run, report = self.report(spec(), breaks=(dict(BREAK, at="0" * 40),))
        self.assertEqual(run.returncode, 1)
        self.assertIn("1 could not run", run.stdout)
        check = report["days"][0]["checks"][-1]
        self.assertEqual(check["status"], "error")
        self.assertTrue(check["diagnostic"].startswith("no worktree at 0000"), check["diagnostic"])
        self.assertIsNone(check["sha"])

    def test_a_command_that_does_not_start_is_an_error_and_a_find_no_longer_there_a_failure(self):
        _, report = self.report(spec(), breaks=(dict(BREAK, command=["no-such-program-x1"]),))
        check = report["days"][0]["checks"][-1]
        self.assertEqual(check["status"], "error", check["diagnostic"])
        self.assertIn("the command did not start", check["diagnostic"])
        _, report = self.report(spec(), breaks=(dict(BREAK, find="gone"),))
        check = report["days"][0]["checks"][-1]
        self.assertEqual((check["status"], check["diagnostic"]),
                         ("failed", f"break.py: --find occurs 0 times in {check['diagnostic'].split(' in ', 1)[1]}"))

    def test_a_spec_that_does_not_exist_fails_in_the_report(self):
        run = subprocess.run([sys.executable, SCRIPT, "specs/day-03-gone.md", "--json", "r.json"], cwd=self.repo,
                             env=GIT_ENV, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(run.returncode, 1)
        with open(os.path.join(self.repo, "r.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["days"][0]["checks"][0]["status"], "failed")


class CacheTest(unittest.TestCase):
    """--cache reuses a replay that held until something it reads changes. Each replay's Verify line
    appends to runs.txt, outside the worktree: the number of lines is the number of real replays."""
    git, write, run_evidence = EvidenceTest.git, EvidenceTest.write, EvidenceTest.run_evidence

    def setUp(self):
        EvidenceTest.setUp(self)
        self.runs = os.path.join(self.repo, "runs.txt").replace(os.sep, "/")

    def cached(self, verify="", breaks=(BREAK,)):
        run = self.run_evidence(spec(verify=f'echo run >> "{self.runs}"{verify}'), breaks,
                                "--json", "report.json", "--cache", "cache.json")
        with open(os.path.join(self.repo, "report.json"), encoding="utf-8") as f:
            report = json.load(f)
        with open(self.runs, encoding="utf-8") as f:
            return run, report, len(f.read().splitlines())

    def test_a_replay_that_held_is_reused_until_what_it_reads_changes(self):
        run, first, n = self.cached()
        self.assertEqual((run.returncode, n), (0, 1), run.stdout + run.stderr)
        self.assertNotIn("reused", run.stdout)
        run, second, n = self.cached()
        self.assertEqual((run.returncode, n), (0, 1), run.stdout + run.stderr)
        self.assertIn("reused  specs/day-01-x.md: replayed " + first["generated"], run.stdout)
        self.assertIn("all evidence holds", run.stdout)
        self.assertEqual(second["days"][0]["reused_from"], first["generated"])
        self.assertEqual(second["days"][0]["checks"], first["days"][0]["checks"])
        # a changed breaks file is a changed input: the day replays again
        run, _, n = self.cached(breaks=(dict(BREAK, replace="broken "),))
        self.assertEqual(n, 2, run.stdout + run.stderr)
        self.assertNotIn("reused", run.stdout)
        # and so is a changed dependency file
        self.write("requirements.txt", "numpy\n")
        run, _, n = self.cached(breaks=(dict(BREAK, replace="broken "),))
        self.assertEqual(n, 3, run.stdout + run.stderr)
        self.assertNotIn("reused", run.stdout)

    def test_a_replay_that_failed_is_never_reused(self):
        for n in (1, 2):
            run, _, runs = self.cached(verify="; exit 3")
            self.assertEqual((run.returncode, runs), (1, n), run.stdout + run.stderr)
            self.assertNotIn("reused", run.stdout)


SHORT = ("# Keep the ok\n\n## Acceptance criteria\n"
         "- [x] S-keep-ok.1 **hold** — Test: `CliTest.test_a`.\n"
         "      broken: the ok removed → AssertionError: broken (#3)\n"
         "- [ ] S-keep-ok.2 **new** — the ok stays bold.\n"
         "      Not proven: left to a day spec.\n\n"
         "## Verify\n```bash\necho 0    # 0\n```\n")


class ShortSpecTest(unittest.TestCase):
    """A short spec, specs/changes/<slug>.md, replays at the merge of change/<slug>."""
    git, write = EvidenceTest.git, EvidenceTest.write

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        self.write("tests/test_cli.py",
                   "class CliTest(unittest.TestCase):\n    def test_a(self):\n        pass\n")
        self.write("app.txt", "ok\n")
        self.git("init", "-q", "-b", "main")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "base")
        self.git("switch", "-q", "-c", "change/keep-ok")
        self.write("specs/changes/keep-ok.md", SHORT)
        self.write("specs/breaks/keep-ok.json", json.dumps([BREAK]))
        self.git("add", ".")
        self.git("commit", "-q", "-m", "keep the ok")
        self.git("switch", "-q", "main")
        self.git("merge", "-q", "--no-ff", "-m", "Merge pull request #3 from me/change/keep-ok", "change/keep-ok")
        self.merge = self.git("rev-parse", "HEAD").strip()

    def run_evidence(self, spec="specs/changes/keep-ok.md"):
        return subprocess.run([sys.executable, SCRIPT, spec, "--json", "report.json"], cwd=self.repo, env=GIT_ENV,
                              capture_output=True, text=True, encoding="utf-8")

    def test_a_short_spec_replays_at_its_change_merge_with_its_own_breaks(self):
        run = self.run_evidence()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn(f"keep-ok.md: change merged in {self.merge[:7]}", run.stdout)
        self.assertIn("ok    S-keep-ok.1 broken: the ok removed", run.stdout)
        self.assertIn("ok    S-keep-ok.2 not proven → left to a day spec.", run.stdout)
        with open(os.path.join(self.repo, "report.json"), encoding="utf-8") as f:
            day = json.load(f)["days"][0]
        self.assertEqual((day["day"], day["change"], day["close_sha"]), (None, "keep-ok", self.merge))
        self.assertEqual(day["breaks"]["path"], "specs/breaks/keep-ok.json")

    def test_a_short_spec_whose_recorded_break_no_longer_fails_is_reported(self):
        self.write("specs/breaks/keep-ok.json", json.dumps([dict(BREAK, command=[sys.executable, "-c", "pass"])]))
        run = self.run_evidence()
        self.assertEqual(run.returncode, 1)
        failures = [l for l in run.stdout.splitlines() if l.startswith("FAIL")]
        self.assertEqual(len(failures), 1, run.stdout)
        self.assertIn("S-keep-ok.1 broken: the ok removed", failures[0])

    def test_a_short_spec_s_unticked_criterion_with_no_not_proven_line_fails(self):
        self.write("specs/changes/keep-ok.md", SHORT.replace("\n\n## Verify", "\n- [ ] S-keep-ok.3 **new** — x.\n\n## Verify"))
        run = self.run_evidence()
        self.assertEqual(run.returncode, 1)
        self.assertEqual([l for l in run.stdout.splitlines() if l.startswith("FAIL")],
                         [f"FAIL  S-keep-ok.3 not proven → no Not proven: line under it at {self.merge[:7]}"])

    def test_a_short_spec_never_merged_and_a_file_outside_changes_fail(self):
        self.write("specs/changes/other.md", SHORT)
        self.assertIn("no merged change/other on main", self.run_evidence("specs/changes/other.md").stdout)
        self.write("specs/keep-ok.md", SHORT)
        self.assertIn("neither a day spec nor a short spec", self.run_evidence("specs/keep-ok.md").stdout)


# A second criterion whose recorded break no longer fails: its find and replace are the same, so the check passes.
FINE = dict(BREAK, what="the fine removed", replace="ok")
TWO_CRITERIA = spec(verify="echo 1    # 0", more=(
    "- [x] C1.2 **new** — Test: `CliTest.test_a`.\n"
    "      broken: the fine removed → AssertionError: broken (#2)\n"))


class CriterionTest(Repo):
    """--criterion replays only the named criteria's checks, from one spec, and runs no Verify line."""

    def limited(self, *criteria, text=TWO_CRITERIA):
        """The run with --criterion for each of criteria, and the report it wrote."""
        flags = [f for c in criteria for f in ("--criterion", c)]
        run = self.run_evidence(text, (BREAK, FINE), *flags, "--json", "report.json")
        with open(os.path.join(self.repo, "report.json"), encoding="utf-8") as f:
            return run, json.load(f)

    def by_key(self, report):
        return {c["id"].split("/", 1)[1]: c for c in report["days"][0]["checks"]}

    def test_one_criterion_replays_its_checks_alone(self):
        run, report = self.limited("C1.1")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        ids = [c["id"].split("/", 1)[1] for c in report["days"][0]["checks"]]
        self.assertEqual(ids, ["close", "C1.1/test/CliTest.test_a", "C1.1/proof", "C1.1/break/the ok removed"])

    def test_the_other_criterion_fails_on_its_own_break(self):
        run, report = self.limited("C1.2")
        self.assertEqual(run.returncode, 1, run.stdout)
        self.assertEqual(self.by_key(report)["C1.2/break/the fine removed"]["status"], "failed")
        self.assertFalse([k for k in self.by_key(report) if k.startswith("C1.1")], run.stdout)

    def test_an_unknown_criterion_fails(self):
        run, report = self.limited("C1.9")
        self.assertEqual(run.returncode, 1, run.stdout)
        check = self.by_key(report)["C1.9/criterion"]
        self.assertEqual(check["status"], "failed")
        self.assertIn("no criterion C1.9", check["diagnostic"])

    def test_criterion_and_cache_cannot_go_together(self):
        run = self.run_evidence(TWO_CRITERIA, (BREAK,), "--criterion", "C1.1", "--cache", "cache.json")
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn("--criterion cannot go with --cache", run.stderr)

    def test_criterion_takes_one_spec_and_a_criterion_id(self):
        run = subprocess.run([sys.executable, SCRIPT, "specs/day-01-x.md", "specs/day-02-y.md", "--criterion", "C1.1"],
                             cwd=self.repo, env=GIT_ENV, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn("--criterion takes exactly one spec", run.stderr)
        run = self.run_evidence(TWO_CRITERIA, (BREAK,), "--criterion", "bogus")
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn("not a criterion id: 'bogus'", run.stderr)

    def test_the_report_names_the_criteria_it_was_limited_to(self):
        _, report = self.limited("C1.1")
        self.assertEqual(report["days"][0]["criteria"], ["C1.1"])
        _, report = self.report(TWO_CRITERIA)
        self.assertIsNone(report["days"][0]["criteria"])


if __name__ == "__main__":
    unittest.main()
