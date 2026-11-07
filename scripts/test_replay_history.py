"""scripts/replay-history.py tells each state apart, samples the right days and writes a fixed order.

Each test builds a small repository and classifies one check at its HEAD, as the script does at a merge.

    python scripts/test_replay_history.py
"""
import importlib.util
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("replay_history", os.path.join(HERE, "replay-history.py"))
rh = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rh)
GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@t")
# Fails, with an assertion line, when app.txt says `broken`.
CHECK = [sys.executable, "-c",
         "import sys; sys.exit('AssertionError: broken') if 'broken' in open('app.txt').read() else None"]
BREAK = {"what": "keep broken", "file": "app.txt", "find": "keep", "replace": "broken", "command": CHECK}
TEST = "class CliTest(unittest.TestCase):\n    def test_a(self):\n        pass\n"


class Classify(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        cwd = os.getcwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, cwd)
        lock = os.path.join(tempfile.mkdtemp(), "lock")  # a break.py lock of this test's own
        self.addCleanup(shutil.rmtree, os.path.dirname(lock), ignore_errors=True)
        self.env = dict(GIT_ENV, PYTHONDONTWRITEBYTECODE="1", BREAK_LOCK=lock)
        self.commit({"app.txt": "ok\nkeep\n", "tests/__init__.py": "", "tests/test_cli.py": "import unittest\n" + TEST})

    def commit(self, files):
        for path, text in files.items():
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        for args in (["init", "-q", "-b", "main"], ["add", "."], ["commit", "-q", "-m", "c"]):
            subprocess.run(["git", *args], env=GIT_ENV, capture_output=True, check=True)
        return rh.git("rev-parse", "HEAD").strip()

    def state(self, entry, tests=(), report="AssertionError: broken", pre=False):
        sha = rh.git("rev-parse", "HEAD").strip()
        return rh.classify(entry, list(tests), report, self.repo, sha, pre, self.env)

    def test_a_break_the_check_sees_holds_with_no_detail_when_it_reports_as_recorded(self):
        self.assertEqual(self.state(BREAK), ("holds", None))
        self.assertEqual(self.state(BREAK, report="AssertionError: other"), ("holds", "reported AssertionError: broken"))

    def test_a_check_that_fails_clean_is_code_broken(self):
        self.commit({"app.txt": "broken\nkeep\n"})
        self.assertEqual(self.state(BREAK)[0], "code broken")

    def test_a_check_that_passes_with_the_break_in_is_a_weakened_test(self):
        self.assertEqual(self.state(dict(BREAK, command=[sys.executable, "-c", "pass"]))[0], "test weakened")

    def test_a_removed_test_is_weakened_after_the_close_and_not_yet_in_force_before_it(self):
        gone = dict(BREAK, command=["python", "-m", "unittest", "tests.test_cli.CliTest.test_gone"])
        self.assertEqual(self.state(gone), ("test weakened", "CliTest.test_gone not defined"))
        self.assertEqual(self.state(gone, pre=True), ("not yet in force", "CliTest.test_gone not defined"))
        self.assertEqual(self.state(None, [("CliTest", "test_gone")])[0], "test weakened")

    def test_edited_code_that_is_gone_no_longer_applies_and_before_the_close_is_not_yet_in_force(self):
        self.assertEqual(self.state(dict(BREAK, find="absent")), ("break no longer applies", "the find text occurs 0 times"))
        self.assertEqual(self.state(dict(BREAK, find="\n")), ("break no longer applies", "the find text occurs 2 times"))
        self.assertEqual(self.state(dict(BREAK, file="gone.txt")), ("break no longer applies", "gone.txt is gone"))
        self.assertEqual(self.state(dict(BREAK, find="absent"), pre=True)[0], "not yet in force")

    def test_a_posix_only_break_is_not_applicable_on_windows_and_runs_elsewhere(self):
        want = "not applicable on this platform" if os.name == "nt" else "holds"
        self.assertEqual(self.state(dict(BREAK, posix_only=True))[0], want)

    def test_what_cannot_run_is_not_runnable(self):
        self.assertEqual(self.state(dict(BREAK, command=["no-such-program-xyz"]))[0], "not runnable")
        self.assertEqual(self.state(None), ("not runnable", "no test or break to replay"))

    def test_a_criterion_with_no_break_runs_its_tests_clean(self):
        self.assertEqual(self.state(None, [("CliTest", "test_a")]), ("holds", "teeth unchecked: no broken: line"))
        self.commit({"tests/test_cli.py": "import unittest\n" + TEST.replace("pass", "self.fail('no')")})
        self.assertEqual(self.state(None, [("CliTest", "test_a")])[0], "code broken")

    def test_a_key_already_measured_is_copied_and_a_change_under_driver_measures_again(self):
        sha = rh.git("rev-parse", "HEAD").strip()
        item = ("01", "C01.1", "keep broken", BREAK, [], None)
        known = {rh.key(sha, BREAK, [], False): {"state": "code broken", "merge": "abc"}}
        row = rh.sample(5, sha, "Merge pull request #9 from me/x", "day", [item], known, {"01": 1})[0]
        self.assertEqual((row["state"], row["reused_from"], row["pr"]), ("code broken", "abc", 9))
        other = self.commit({"driver/x.py": "x = 1\n"})
        self.assertNotIn(rh.key(other, BREAK, [], False), known)


class Sampling(unittest.TestCase):
    closed = {"04": 10, "05": 20}

    def test_a_close_samples_every_day_closed_by_then(self):
        self.assertEqual(rh.sampled_days(20, "Merge pull request #43 from me/day-05/close-the-day", self.closed),
                         (["04", "05"], "all"))

    def test_a_day_s_merge_samples_that_day_once_it_has_closed(self):
        self.assertEqual(rh.sampled_days(15, "Merge pull request #40 from me/day-05/track-a-x", self.closed), (["05"], "day"))
        self.assertIsNone(rh.sampled_days(22, "Merge pull request #50 from me/day-06/track-a-x", self.closed))

    def test_any_other_merge_samples_the_last_day_closed_before_it(self):
        self.assertEqual(rh.sampled_days(22, "Merge pull request #44 from me/dashboard/x", self.closed), (["05"], "day"))
        self.assertEqual(rh.sampled_days(15, "Merge pull request #30 from me/tooling/x", self.closed), (["04"], "day"))


class Order(unittest.TestCase):
    def test_the_file_is_the_same_whatever_order_the_rows_come_in(self):
        rows = [{"n": n, "platform": p, "day": d, "criterion": c, "check": k, "state": "holds", "merge": "m"}
                for n in (3, 1) for p in ("windows", "linux") for d, c in (("05", "C05.10"), ("05", "C05.2"))
                for k in ("b", "a")]
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        texts = []
        for seed in (1, 2):
            random.Random(seed).shuffle(rows)
            rh.write(os.path.join(out, "h.json"), "abc", rows)
            with open(os.path.join(out, "h.json"), "rb") as f:
                texts.append(f.read())
        self.assertEqual(texts[0], texts[1])
        lines = texts[0].decode("utf-8").splitlines()
        self.assertEqual(len(lines), len(rows) + 2)  # one row a line, and the head and the end
        first = json.loads(lines[1].rstrip(","))
        self.assertEqual((first["n"], first["platform"], first["criterion"], first["check"]), (1, "linux", "C05.2", "a"))
        self.assertEqual(json.loads(texts[0])["rows"][-1]["criterion"], "C05.10")


if __name__ == "__main__":
    unittest.main()
