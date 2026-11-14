"""scripts/break.py puts the code back as it was, and reports a break only when the check failed.

Each test writes a scratch file and runs break.py over it as a subprocess, with a short Python
command as the check: it fails when the file holds the broken text.

    python scripts/test_break.py
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "break.py")
LOCK = os.environ.get("BREAK_LOCK") or os.path.join(HERE, "..", ".break-active")


def check(path):
    """A check that fails, with an assertion line, when the file says `broken`."""
    return [sys.executable, "-c",
            f"import sys; t = open({path!r}).read(); "
            "sys.exit('AssertionError: expected ok but was broken') if 'broken' in t else print('1 passed')"]


def load():
    """break.py as a module, for the functions a test calls without a run."""
    spec = importlib.util.spec_from_file_location("break_script", SCRIPT)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    return script


class SummaryTest(unittest.TestCase):
    def test_javascript_summaries_precede_failure_details(self):
        script = load()
        for summary in ("Tests: 1 failed, 4 passed, 5 total", "Tests  1 failed | 4 passed (5)"):
            self.assertEqual(script.reported("FAIL detail\n" + summary + "\n"), summary)

    def test_a_plain_report_holds_nothing_unstable(self):
        script = load()
        for line in ("AssertionError: 3 != 4", "Tests: 1 failed, 4 passed, 5 total",
                     "AssertionError: '--resume' not found in ['-p', '--settings', '<tmp>/state/settings.json']",
                     "AssertionError: ['plan.md', 'driver/loop.py'] != []", "see https://github.com/a/b/pull/12",
                     "AssertionError: 1234567 != 7654321", "AssertionError: 'deadbeef' != 'defaced'",
                     "FAILED (failures=1)", "AssertionError: <uuid> on <head> != None"):
            self.assertIsNone(script.unstable(line), line)
        self.assertEqual(script.unstable("run on 1dc0f03 failed"), ("a commit hash", "1dc0f03"))


class BreakTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.file = os.path.join(self.dir, "Guard.java")
        # CRLF on purpose: a revert in text mode would write LF back.
        self.original = b"class Guard {\r\n    boolean ok = true; // ok\r\n}\r\n"
        with open(self.file, "wb") as f:
            f.write(self.original)

    def run_break(self, find, replace, command=None, extra=(), what="the guard removed", dash=("--",)):
        return subprocess.run([sys.executable, SCRIPT, "--file", self.file, "--find", find, "--replace", replace,
                               "--what", what, *extra, *dash, *(command or check(self.file))],
                              capture_output=True, text=True, encoding="utf-8")

    def contents(self):
        with open(self.file, "rb") as f:
            return f.read()

    def test_a_check_that_fails_gives_the_broken_line_and_the_file_comes_back_byte_for_byte(self):
        run = self.run_break("// ok", "// broken")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip().splitlines()[-1], "broken: the guard removed → AssertionError: expected ok but was broken")
        self.assertEqual(self.contents(), self.original)
        self.assertFalse(os.path.exists(LOCK))

    def test_a_command_with_options_needs_no_dashes_before_it(self):
        run = self.run_break("// ok", "// broken", dash=())
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip().splitlines()[-1], "broken: the guard removed → AssertionError: expected ok but was broken")

    def test_an_arrow_in_what_is_refused_before_anything_changes(self):
        # spec-drift.py reads <what> up to the first arrow: a pilot's "if not paths: → if False:".
        for what in ("if not paths: → if False:", "66 -> 67"):
            run = self.run_break("// ok", "// broken", what=what)
            self.assertEqual(run.returncode, 2, what)
            self.assertIn("--what holds an arrow", run.stderr)
            self.assertEqual(self.contents(), self.original)

    def test_a_git_warning_is_not_what_the_check_reported(self):
        # a pilot: git diff --exit-code on Windows ends with git's CRLF warning on stderr.
        diff = [sys.executable, "-c", f"import sys; t = open({self.file!r}).read(); "
                "print(' 1 file changed, 1 insertion(+)') if 'broken' in t else None; "
                "sys.exit(\"warning: in the working copy of 'a.py', LF will be replaced by CRLF\") if 'broken' in t else None"]
        run = self.run_break("// ok", "// broken", command=diff)
        self.assertEqual(run.stdout.strip().splitlines()[-1], "broken: the guard removed → 1 file changed, 1 insertion(+)")

    def test_a_temporary_path_in_the_report_is_written_tmp(self):
        # a pilot: unittest's repr of a path under the user's temp directory, its start cut.
        full = os.path.join(tempfile.gettempdir(), "tmp2ewplof6", "a.txt")
        said = f"AssertionError: {full!r} != '[27 chars]1\\\\AppData\\\\Local\\\\Temp\\\\tmp2ewplof6\\\\a.txt' in {full}"
        run = self.run_break("// ok", "// broken", command=[sys.executable, "-c",
                             f"import sys; t = open({self.file!r}).read(); sys.exit({said!r}) if 'broken' in t else None"])
        line = run.stdout.strip().splitlines()[-1]
        self.assertNotIn(tempfile.gettempdir(), line)
        self.assertNotIn("tmp2ewplof6", line)
        self.assertEqual(line.count("<tmp>"), 3, line)
        # On Linux the directory is /tmp, which a tempfile name under it also starts with (CI on #20).
        spec = importlib.util.spec_from_file_location("break_script", SCRIPT)
        script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(script)
        with mock.patch.object(script.tempfile, "gettempdir", return_value="/tmp"):
            self.assertEqual(script.untemp("'/tmp/tmp2ewplof6/a.txt' in /tmp/x, not /tmpfoo"),
                             "'<tmp>/a.txt' in <tmp>/x, not /tmpfoo")

    def test_a_check_that_passes_with_the_break_in_is_reported_as_blind(self):
        run = self.run_break("true", "false")
        self.assertEqual(run.returncode, 1)
        self.assertIn("cannot see this break", run.stdout)
        self.assertNotIn("broken:", run.stdout)
        self.assertEqual(self.contents(), self.original)

    def test_a_find_that_is_missing_or_ambiguous_changes_nothing(self):
        for find in ("absent", "o"):
            run = self.run_break(find, "broken")
            self.assertEqual(run.returncode, 2, find)
            self.assertIn("want exactly once", run.stderr)
            self.assertEqual(self.contents(), self.original)

    def test_an_ambiguous_find_names_the_lines_it_occurs_on(self):
        # D08.69: the refusal said "occurs 2 times" and the line had to be found by hand.
        run = self.run_break("a", "broken")
        self.assertEqual(run.returncode, 2)
        self.assertIn("(lines 1, 2)", run.stderr)

    def test_a_multi_line_find_written_with_lf_breaks_a_crlf_file(self):
        # D08.68, D08.72: a two-line --find never matched a CRLF checkout, and was redone on one line.
        crlf = [sys.executable, "-c", f"import sys; t = open({self.file!r}, 'rb').read(); "
                "sys.exit('AssertionError: broken') if b'{\\r\\n    boolean ok = true; // broken' in t else None"]
        run = self.run_break("Guard {\n    boolean ok = true; // ok", "Guard {\n    boolean ok = true; // broken",
                             command=crlf)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip().splitlines()[-1], "broken: the guard removed → AssertionError: broken")
        self.assertEqual(self.contents(), self.original)

    def test_a_maven_check_without_clean_is_refused_before_anything_changes(self):
        run = self.run_break("// ok", "// broken", ["../../mvnw", "verify", "-Dtest=GuardIT"])
        self.assertEqual(run.returncode, 2)
        self.assertIn("must clean", run.stderr)
        self.assertEqual(self.contents(), self.original)

    def test_a_command_that_does_not_start_is_not_a_break(self):
        run = self.run_break("// ok", "// broken", ["no-such-command-here"])
        self.assertEqual(run.returncode, 2)
        self.assertIn("did not start", run.stderr)
        self.assertEqual(self.contents(), self.original)
        self.assertFalse(os.path.exists(LOCK))

    def test_a_command_that_starts_but_never_runs_the_check_is_known(self):
        # a pilot, Day 3: `bash` was WSL's, and break.py printed broken: lines for checks never run.
        script = load()
        wsl = "<3>WSL (9) ERROR: CreateProcessCommon:559: execvpe(/bin/bash) failed: No such file or directory\n"
        self.assertEqual(script.not_run(1, wsl), wsl.strip())
        self.assertEqual(script.not_run(127, "x\n"), "exit 127: the shell could not run the program")
        self.assertIsNone(script.not_run(1, "FAILED (failures=1)\n"))

    def test_a_command_that_starts_but_never_runs_the_check_is_refused(self):
        wsl = [sys.executable, "-c", "import sys; sys.exit('<3>WSL (9) ERROR: execvpe(/bin/bash) failed')"]
        run = self.run_break("// ok", "// broken", wsl)
        self.assertEqual((run.returncode, run.stdout), (2, ""))
        self.assertIn("the check did not run", run.stderr)
        self.assertEqual(self.contents(), self.original)

    def test_expect_stdout_judges_the_check_by_its_output(self):
        # a pilot, Days 4 and 5: `grep -c` prints 0 and exits 1 when no test was edited.
        script = load()
        self.assertFalse(script.caught(1, "0\n", "^0$"))
        self.assertTrue(script.caught(1, "3\n", "^0$"))
        self.assertTrue(script.caught(0, "removed=2\n", "removed=0"))
        self.assertEqual((script.caught(1, "", None), script.caught(0, "", None)), (True, False))

    def test_expect_stdout_records_a_count_check(self):
        count = [sys.executable, "-c", f"import sys; n = open({self.file!r}).read().count('broken'); "
                 "print(n); sys.exit(0 if n else 1)"]
        run = self.run_break("// ok", "// broken", count, extra=("--expect-stdout", "^0$"))
        self.assertEqual((run.returncode, run.stdout.strip().splitlines()[-1]), (0, "broken: the guard removed → 1"))
        by_exit = self.run_break("// ok", "// broken", count)
        self.assertEqual(by_exit.returncode, 2)  # by exit code, the unbroken check fails
        self.assertIn("fails without the break", by_exit.stderr)
        blind = [sys.executable, "-c", f"print(open({self.file!r}).read().count('broken'))"]
        self.assertEqual(self.run_break("// ok", "// broken", blind).returncode, 1)  # by exit code, blind

    def test_a_check_that_fails_without_the_break_is_refused_and_nothing_is_recorded(self):
        run = self.run_break("// ok", "// broken", [sys.executable, "-c", "raise RuntimeError('unrelated')"])
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("fails without the break", run.stderr)
        self.assertIn("RuntimeError: unrelated", run.stderr)
        self.assertNotIn("broken:", run.stdout)
        self.assertEqual(self.contents(), self.original)
        self.assertFalse(os.path.exists(LOCK))

    def test_expect_stdout_that_never_matches_without_the_break_is_refused(self):
        run = self.run_break("// ok", "// broken", extra=("--expect-stdout", "never matches"))
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("fails without the break", run.stderr)
        self.assertNotIn("broken:", run.stdout)
        self.assertEqual(self.contents(), self.original)
        self.assertFalse(os.path.exists(LOCK))

    def test_the_lock_is_held_during_the_baseline_run(self):
        marker = os.path.join(self.dir, "baseline-ran")
        command = [sys.executable, "-c", f"import os, sys; t = open({self.file!r}).read(); "
                   f"sys.exit('AssertionError: broken') if 'broken' in t else "
                   f"open({marker!r}, 'w').write('locked') if os.path.exists({LOCK!r}) else sys.exit(1)"]
        run = self.run_break("// ok", "// broken", command)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("broken:", run.stdout)
        self.assertTrue(os.path.exists(marker))
        self.assertFalse(os.path.exists(LOCK))

    def test_a_relative_program_is_found_from_cwd(self):
        # `--cwd services/job-service -- ../../mvnw` names the root's mvnw; Windows would look for
        # it from the caller's directory. A bare name is left for PATH.
        spec = importlib.util.spec_from_file_location("break_script", SCRIPT)
        script = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(script)
        head = script.argv_for(["../../mvnw", "clean"], os.path.join(self.dir, "services", "job-service"))[0]
        self.assertEqual(head, os.path.join(self.dir, "mvnw") + (".cmd" if os.name == "nt" else ""))
        self.assertEqual(script.argv_for(["python", "-V"], self.dir), ["python", "-V"])

    def test_the_manifest_entry_comes_before_the_broken_line(self):
        # the comparison's run A: no track PR kept break.py's arguments, and the close rebuilt 15.
        command = [sys.executable, "-c", "import sys; t = open('Guard.java').read(); print(t.count('broken'))"]
        run = subprocess.run([sys.executable, SCRIPT, "--file", "Guard.java", "--find", "// ok", "--replace",
                              "// broken", "--what", "the guard removed", "--expect-stdout", "^0$", "--", *command],
                             capture_output=True, text=True, encoding="utf-8", cwd=self.dir)
        self.assertEqual(run.returncode, 0, run.stderr)
        manifest, broken = run.stdout.strip().splitlines()[-2:]
        self.assertTrue(broken.startswith("broken: the guard removed → "), broken)
        self.assertEqual(json.loads(manifest[len("manifest: "):]),
                         {"what": "the guard removed", "file": "Guard.java", "find": "// ok", "replace": "// broken",
                          "command": command, "expect_stdout": "^0$"})

    def test_a_break_run_from_another_directory_says_why_it_has_no_manifest_entry(self):
        run = self.run_break("// ok", "// broken", extra=("--cwd", self.dir))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("manifest: none → ", run.stdout.strip().splitlines()[-2])

    def test_a_file_outside_the_tree_cwd_runs_in_is_refused_before_anything_changes(self):
        # seen 2026-11-07: run from the root with --cwd <worktree>, the break went into the main
        # tree's file, the worktree's copy ran, and the check "passed with the break in".
        other = tempfile.mkdtemp()
        with open(os.path.join(other, "Guard.java"), "wb") as f:
            f.write(self.original)
        command = [sys.executable, "-c", "import sys; t = open('Guard.java').read(); "
                   "sys.exit('AssertionError: broken') if 'broken' in t else print('1 passed')"]
        run = self.run_break("// ok", "// broken", command=command, extra=("--cwd", other))
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertIn("is outside the tree --cwd", run.stderr)
        self.assertEqual(self.contents(), self.original)

    def test_a_file_elsewhere_in_cwd_s_git_work_tree_is_broken(self):
        # a shared file at the root, its check run from a service directory of the same work tree.
        subprocess.run(["git", "init", "-q", self.dir], check=True)
        service = os.path.join(self.dir, "services", "job")
        os.makedirs(service)
        run = self.run_break("// ok", "// broken", extra=("--cwd", service))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("broken: the guard removed → ", run.stdout)
        self.assertEqual(self.contents(), self.original)

    def test_a_break_inside_a_break_s_check_takes_its_own_lock(self):
        # item 130: a break of break.py, or of what runs it, needed break.py run from a scratch copy.
        inner = [sys.executable, SCRIPT, "--file", self.file, "--find", "// ok", "--replace", "// broken",
                 "--what", "inner", "--", *check(self.file)]
        run = self.run_break("// ok", "// broken", command=inner)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("broken: the guard removed → ", run.stdout)
        self.assertEqual(self.contents(), self.original)

    def test_a_second_break_while_one_is_active_is_refused(self):
        with open(LOCK, "w") as f:
            f.write("other")
        try:
            run = self.run_break("// ok", "// broken")
        finally:
            os.remove(LOCK)
        self.assertEqual(run.returncode, 2)
        self.assertIn("another break is active", run.stderr)
        self.assertEqual(self.contents(), self.original)

    def test_the_check_runs_twice_with_the_break_in(self):
        # the baseline, then two runs with the break in: the count is what the replay on another machine repeats
        runs = os.path.join(self.dir, "runs.txt")
        command = [sys.executable, "-c", f"import sys; t = open({self.file!r}).read(); "
                   f"open({runs!r}, 'a').write('run\\n'); "
                   "sys.exit('AssertionError: expected ok but was broken') if 'broken' in t else print('1 passed')"]
        run = self.run_break("// ok", "// broken", command)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip().splitlines()[-1],
                         "broken: the guard removed → AssertionError: expected ok but was broken")
        with open(runs) as f:
            count = len(f.read().splitlines())
        self.assertEqual(count, 3)

    def test_a_report_that_differs_between_the_two_runs_is_refused(self):
        # a pid in the report: each run with the break in prints another one
        command = [sys.executable, "-c", f"import os, sys; t = open({self.file!r}).read(); "
                   "sys.exit(f'AssertionError: worker {os.getpid()} died') if 'broken' in t else print('1 passed')"]
        run = self.run_break("// ok", "// broken", command)
        self.assertEqual(run.returncode, 2)
        self.assertIn("the report differs between two runs", run.stderr)
        self.assertNotIn("broken:", run.stdout)
        self.assertEqual(self.contents(), self.original)

    def test_a_check_that_fails_once_and_passes_once_with_the_break_in_is_refused(self):
        # a flaky check: the first run with the break in creates the marker and fails, the second finds it
        marker = os.path.join(self.dir, "failed-once")
        command = [sys.executable, "-c", f"import os, sys; t = open({self.file!r}).read(); m = {marker!r}; "
                   "print('1 passed') if 'broken' not in t or os.path.exists(m) else "
                   "(open(m, 'w').close(), sys.exit('AssertionError: expected ok but was broken'))"]
        run = self.run_break("// ok", "// broken", command)
        self.assertEqual(run.returncode, 2)
        self.assertIn("failed in one run with the break in and passed in the other", run.stderr)
        self.assertNotIn("broken:", run.stdout)
        self.assertEqual(self.contents(), self.original)

    def test_a_report_that_holds_a_pid_uuid_commit_hash_or_absolute_path_is_refused(self):
        cases = (
            ("a pid", "AssertionError: pid 4242 still holds the lock"),
            ("a uuid", "AssertionError: session 00000000-0000-4000-8000-000000000000 was not resumed"),
            ("a commit hash", "AssertionError: None != 'park: the evidence run on `1dc0f03` ended `failure`'"),
            ("an absolute path", "AssertionError: 'C:\\Users\\me\\repo\\plan.md' is missing"),
            ("an absolute path", "AssertionError: '/home/me/repo/plan.md' is missing"),
        )
        for name, message in cases:
            with self.subTest(what=name, message=message):
                command = [sys.executable, "-c", f"import sys; t = open({self.file!r}).read(); "
                           f"sys.exit({message!r}) if 'broken' in t else print('1 passed')"]
                run = self.run_break("// ok", "// broken", command)
                self.assertEqual(run.returncode, 2)
                self.assertIn(f"the report holds {name}", run.stderr)
                self.assertNotIn("broken:", run.stdout)
                self.assertEqual(self.contents(), self.original)

    def test_replay_runs_the_break_once_and_leaves_the_report_to_its_caller(self):
        # evidence.py and replay-history.py pass --replay: a recorded uuid replays, one run only
        runs = os.path.join(self.dir, "runs.txt")
        message = "AssertionError: session 00000000-0000-4000-8000-000000000000 was not resumed"
        command = [sys.executable, "-c", f"import sys; t = open({self.file!r}).read(); "
                   f"open({runs!r}, 'a').write('run\\n'); "
                   f"sys.exit({message!r}) if 'broken' in t else print('1 passed')"]
        run = self.run_break("// ok", "// broken", command, extra=("--replay",))
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip().splitlines()[-1],
                         "broken: the guard removed → AssertionError: session 00000000-0000-4000-8000-000000000000 was not resumed")
        with open(runs) as f:
            count = len(f.read().splitlines())
        self.assertEqual(count, 2)


class RecordTest(unittest.TestCase):
    """--record writes the entry into the break manifest, so the close copies nothing by hand."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.git("init", "-q", "-b", "day-12/track-a-guard")
        self.original = b"class Guard {\r\n    boolean ok = true; // ok\r\n}\r\n"
        with open(os.path.join(self.dir, "Guard.java"), "wb") as f:
            f.write(self.original)
        self.git("add", "Guard.java")
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "guard")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.dir, capture_output=True, text=True, check=True).stdout.strip()

    def run_break(self, *extra, what="the guard removed", find="// ok", replace="// broken"):
        command = [sys.executable, "-c", "import sys; t = open('Guard.java').read(); "
                   "sys.exit('AssertionError: expected ok but was broken') if 'broken' in t else print('1 passed')"]
        return subprocess.run([sys.executable, SCRIPT, "--file", "Guard.java", "--find", find, "--replace",
                               replace, "--what", what, *extra, "--", *command],
                              capture_output=True, text=True, encoding="utf-8", cwd=self.dir)

    def manifest(self, name="specs/breaks/day-12.json"):
        with open(os.path.join(self.dir, name), encoding="utf-8") as f:
            return json.load(f)

    def test_record_writes_the_entry_its_report_and_the_blob_into_the_day_s_manifest(self):
        run = self.run_break("--record")
        self.assertEqual(run.returncode, 0, run.stderr)
        [entry] = self.manifest()
        self.assertEqual(entry["what"], "the guard removed")
        self.assertEqual(entry["file"], "Guard.java")
        self.assertEqual(entry["report"], "AssertionError: expected ok but was broken")
        # the blob of the code the break ran on, as git holds it, not a commit that holds the record
        self.assertTrue(entry["blob"] == self.git("rev-parse", "HEAD:Guard.java"), "the blob is not the file's")
        self.assertIn("recorded: added in specs/breaks/day-12.json", run.stdout)

    def test_a_second_record_with_the_same_what_replaces_it_and_keeps_the_others(self):
        self.assertEqual(self.run_break("--record", what="another break", find="true").returncode, 0)
        self.assertEqual(self.run_break("--record").returncode, 0)
        with open(os.path.join(self.dir, "Guard.java"), "ab") as f:
            f.write(b"// later\r\n")
        run = self.run_break("--record")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("recorded: replaced in", run.stdout)
        entries = self.manifest()
        self.assertEqual([e["what"] for e in entries], ["another break", "the guard removed"])
        self.assertNotEqual(entries[1]["blob"], self.git("rev-parse", "HEAD:Guard.java"))

    def test_record_on_a_change_branch_writes_its_slug_s_manifest(self):
        self.git("checkout", "-q", "-b", "change/guard-fix")
        self.assertEqual(self.run_break("--record").returncode, 0)
        self.assertEqual(len(self.manifest("specs/breaks/guard-fix.json")), 1)

    def test_record_on_another_branch_needs_a_path_and_changes_nothing(self):
        self.git("checkout", "-q", "-b", "tooling/guard")
        run = self.run_break("--record")
        self.assertEqual(run.returncode, 2)
        self.assertIn("--record <path>", run.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "specs")))
        run = self.run_break("--record", "specs/breaks/day-03.json")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(len(self.manifest("specs/breaks/day-03.json")), 1)

    def test_record_with_no_entry_or_with_replay_is_refused_before_anything_runs(self):
        os.mkdir(os.path.join(self.dir, "sub"))
        for extra, why in ((("--record", "--cwd", "sub"), "--record has no entry to write"),
                           (("--record", "--replay"), "--record with --replay")):
            run = self.run_break(*extra)
            self.assertEqual(run.returncode, 2, extra)
            self.assertIn(why, run.stderr)
            self.assertNotIn("broken:", run.stdout)
            self.assertFalse(os.path.exists(os.path.join(self.dir, "specs")))

    def test_a_check_that_cannot_see_the_break_records_nothing(self):
        run = self.run_break("--record", find="class", replace="klass")
        self.assertEqual(run.returncode, 1)
        self.assertFalse(os.path.exists(os.path.join(self.dir, "specs")))


if __name__ == "__main__":
    unittest.main()
