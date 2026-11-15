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
    def names(self, **args):
        a = argparse.Namespace(**{"body": None, "title": None, "skip_tests": False, **args})
        return {name: what for name, what in pp.checks(a, "HEAD", "tooling/x", ["scripts/x.py", "README.md"])}

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
