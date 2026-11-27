"""The PR checks against their local runner (scripts/pre-push.py), and each CI job's time limit."""

import argparse
import glob
import importlib.util
import os
import unittest

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
WORKFLOWS = sorted(glob.glob(os.path.join(HERE, "..", ".github", "workflows", "*.yml")))
SPEC = importlib.util.spec_from_file_location("pre_push", os.path.join(HERE, "pre-push.py"))
pp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pp)
# A job that runs nothing of its own: it sums up the jobs it needs, or decides whether they run.
NOT_A_CHECK = {"Dashboard metric tests gate"}


def workflows():
    for path in WORKFLOWS:
        with open(path, encoding="utf-8") as f:
            flow = yaml.safe_load(f)
        yield os.path.basename(path), flow.get("on", flow.get(True)) or {}, flow["jobs"]


class PrePushTest(unittest.TestCase):
    def names(self, files=("scripts/x.py", "README.md"), **args):
        a = argparse.Namespace(**{"body": None, "title": None, "skip_tests": False, **args})
        return {name: what for name, what in pp.checks(a, "HEAD", "tooling/x", list(files))}

    def test_changed_test_files_run_several_times_inside_the_whole_run(self):
        # Nine tests failed on and off under load on Days 9 to 12, and one of them passed 25 of 25
        # alone (D12.34): the files a branch changes are repeated with the whole suite as the load.
        [plain] = self.names()["Tests"]
        self.assertEqual(plain[1:], ["scripts/test-parallel.py"])
        # A deleted file, a file in a folder under tests/ and the scripts' own tests are not repeated.
        files = ["tests/test_on.py", "tests/test_gone.py", "tests/fakes/test_x.py", "scripts/test_pre_push.py"]
        [again] = self.names(files=files)["Tests"]
        self.assertEqual(again[2:], ["--repeat", "5", "--of", "test_on.py"])
        self.assertEqual(self.names(files=files, skip_tests=True)["Tests"], "skip: --skip-tests")

    def test_the_tests_line_carries_the_runs_count(self):
        # The Tests step is the track's one full run (CLAUDE.md, "Before pushing"), so its line says
        # how many tests ran: the count a change should give is read there, not from a second run.
        output = "$ py scripts/test-parallel.py\nRan 738 tests in 401.2s (8 workers; slowest test_on.py 190.0s)\nOK\n"
        self.assertEqual(pp.ran_line(output), "Ran 738 tests in 401.2s (8 workers; slowest test_on.py 190.0s)")
        self.assertEqual(pp.ran_line("$ ruff check .\nAll checks passed!\n"), "")

    def test_every_check_ci_runs_on_a_pull_request_has_a_line(self):
        # A check added to CI and not to pre-push.py is the one a first push meets (#212 S23, #213 B12).
        local = {name.strip('"') for name in self.names()}
        missing = [f"{flow}: {job['name']}" for flow, on, jobs in workflows() if "pull_request" in on
                   for job in jobs.values() if job.get("name") and job["name"] not in NOT_A_CHECK | local]
        self.assertFalse(missing, "CI checks with no line in pre-push.py")

    def test_what_only_a_pull_request_has_is_a_skip_that_names_it(self):
        checks = self.names()
        self.assertEqual(checks["Branch, title, commits and Jira keys agree"], "skip: pass --title")
        self.assertEqual(checks["Description uses the template"], "skip: pass --body <file>")
        self.assertTrue(checks["A track's breaks replay"].startswith("skip: needs Linux"))
        self.assertEqual(checks["Frozen files stay unedited"], [[pp.PY, "scripts/invariants.py", "HEAD", "HEAD"]])
        self.assertEqual(checks["Links in the Markdown touched"], [[pp.PY, "scripts/check-links.py", "README.md"]])

    def test_every_ci_job_has_a_time_limit(self):
        # One run on 11 Nov took about 40 minutes (#212, S16).
        for flow, _, jobs in workflows():
            for key, job in jobs.items():
                self.assertIsInstance(job.get("timeout-minutes"), int, f"{flow}: job {key} has no timeout-minutes")

    def test_the_settings_are_checked_on_a_schedule(self):
        # #211 N2: a setting that drifts from the documents fails where it is seen.
        on = {flow: on for flow, on, _ in workflows()}["setup-check.yml"]
        self.assertIn("schedule", on)
        self.assertIn("workflow_dispatch", on)


if __name__ == "__main__":
    unittest.main()
