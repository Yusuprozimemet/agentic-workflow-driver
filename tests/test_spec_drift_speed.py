"""What keeps spec-drift.py fast: the cache's parts outlive an edit to a file that does not make
them, a file is read once however many merges hold it, and the first run's greps overlap."""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


specs = load("spec_drift_specs", os.path.join(SCRIPTS, "spec_drift_specs.py"))
metrics = load("spec_drift_metrics", os.path.join(SCRIPTS, "spec_drift_metrics.py"))

PARTS = dict(git={"ls-tree\0abc": "plan.md\n"}, code={"abc": {"load_cache": {"scripts/spec-drift.py": 2}}},
             flags={"abc": {"asked": ["--out"], "found": ["--out"]}}, comments={"abc": "abc:run-steps.py:7:# Day 3\n"})


class CacheKeptTest(unittest.TestCase):
    """load_cache on a copy of the script's files, one of them edited between two runs."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        for name in os.listdir(SCRIPTS):
            if name == "spec-drift.py" or name.startswith("spec_drift_"):
                shutil.copy(os.path.join(SCRIPTS, name), self.dir)
        self.drift = load("spec_drift_copy", os.path.join(self.dir, "spec-drift.py"))
        self.addCleanup(lambda: self.dir in sys.path and sys.path.remove(self.dir))
        self.addCleanup(self.drift.CACHE.clear)
        self.cache = os.path.join(self.dir, "cache.json")
        self.drift.load_cache(self.cache)
        self.drift.CACHE.update(json.loads(json.dumps(PARTS)))
        self.drift.save_cache(self.cache)

    def kept_after_editing(self, name):
        with open(os.path.join(self.dir, name), "ab") as f:
            f.write(b"# edited\n")
        self.drift.load_cache(self.cache)
        return sorted(part for part in PARTS if self.drift.CACHE.get(part) == PARTS[part])

    def test_an_unedited_script_keeps_every_part(self):
        self.drift.load_cache(self.cache)
        self.assertEqual({part: self.drift.CACHE.get(part) for part in PARTS}, PARTS)

    def test_an_edit_to_a_view_keeps_every_part(self):
        self.assertEqual(self.kept_after_editing("spec_drift_views.py"), ["code", "comments", "flags", "git"])

    def test_an_edit_to_the_script_itself_keeps_every_part(self):
        self.assertEqual(self.kept_after_editing("spec-drift.py"), ["code", "comments", "flags", "git"])

    def test_an_edit_to_the_counting_starts_the_counts_over(self):
        self.assertEqual(self.kept_after_editing("spec_drift_metrics.py"), ["comments", "git"])

    def test_an_edit_to_the_patterns_starts_the_counts_over(self):
        self.assertEqual(self.kept_after_editing("spec_drift_common.py"), ["comments", "git"])

    def test_an_edit_to_the_hand_offs_starts_their_grep_over(self):
        self.assertEqual(self.kept_after_editing("spec_drift_handoffs.py"), ["code", "flags", "git"])

    def test_an_edit_to_the_git_reader_starts_every_part_over(self):
        self.assertEqual(self.kept_after_editing("spec_drift_git.py"), [])

    def test_a_cache_written_before_the_parts_starts_over(self):
        with open(self.cache, "w", encoding="utf-8") as f:
            json.dump(dict(PARTS, version="0" * 64), f)
        self.drift.load_cache(self.cache)
        self.assertEqual([part for part in PARTS if part in self.drift.CACHE], [])

    def test_every_part_the_script_fills_is_one_load_cache_checks(self):
        """A part with no files named would never start over: each CACHE key in the code has them."""
        import re

        used = set()
        for name in os.listdir(SCRIPTS):
            if name.startswith("spec_drift_"):
                with open(os.path.join(SCRIPTS, name), encoding="utf-8") as f:
                    used.update(re.findall(r'CACHE(?:\.setdefault\(|\[)"(\w+)"', f.read()))
        self.assertEqual(sorted(used), sorted(self.drift.CACHE_PARTS))


class Blobs:
    """Stands in for git cat-file: the text of each path at each commit, and how often it was asked."""

    def __init__(self, texts):
        self.texts, self.reads = texts, 0

    def read(self, sha, path):
        self.reads += 1
        return self.texts[sha][path]


CLI = "class CliTest(unittest.TestCase):\n    def test_help(self):\n        pass\n"
SLOW = '@EnabledIfSystemProperty(named = "slow", matches = "true")\nclass SlowIT {}\n'
PATHS = ("tests/test_cli.py", "src/test/java/SlowIT.java", ".github/workflows/tests.yml")
NAMED = {"CliTest.test_help", "CliTest.test_gone", "SlowIT", "Absent"}


def tree(*ids):
    return "\n".join(f"100644 blob {i}\t{p}" for i, p in zip(ids, PATHS))


class ReadOnceTest(unittest.TestCase):
    """test_state at two commits: what the second one reads again."""

    def setUp(self):
        getattr(specs, "BLOB_TEXTS", {}).clear()  # absent before the change, which read every file each time

    def states(self, trees, texts):
        blobs = Blobs(texts)
        with mock.patch.object(specs, "at_commits", side_effect=lambda *args: trees[args[-1]]):
            return [specs.test_state(NAMED, sha, blobs) for sha in trees], blobs.reads

    def test_files_unchanged_at_the_next_commit_are_not_read_again(self):
        at = dict(zip(PATHS, (CLI, SLOW, "run: mvn -Dslow=true verify\n")))
        (first, second), reads = self.states({"one": tree("a1", "b1", "c1"), "two": tree("a1", "b1", "c1")},
                                             {"one": at, "two": at})
        self.assertEqual(first, {"CliTest.test_help": "present", "CliTest.test_gone": "missing",
                                 "SlowIT": "present", "Absent": "missing"})
        self.assertEqual(second, first)
        self.assertEqual(reads, 3)

    def test_a_changed_file_is_read_again_and_judged_as_it_is_now(self):
        at = dict(zip(PATHS, (CLI, SLOW, "run: mvn -Dslow=true verify\n")))
        now = dict(at, **{PATHS[0]: "class CliTest(unittest.TestCase):\n    pass\n", PATHS[2]: "run: mvn verify\n"})
        (first, second), reads = self.states({"one": tree("a1", "b1", "c1"), "two": tree("a2", "b1", "c2")},
                                             {"one": at, "two": now})
        self.assertEqual((first["CliTest.test_help"], first["SlowIT"]), ("present", "present"))
        self.assertEqual((second["CliTest.test_help"], second["SlowIT"]), ("missing", "skippable"))
        self.assertEqual(reads, 5)


class GrepsOverlapTest(unittest.TestCase):
    """count_code: which commits it greps, and that two greps are in flight at once."""

    def setUp(self):
        self.addCleanup(metrics.CACHE.clear)
        metrics.CACHE.clear()
        metrics.CACHE["code"] = {"old": {"kept": {"a.py": 1}}}

    def count(self, grep):
        with mock.patch.object(metrics, "names_in_code", side_effect=grep), \
                mock.patch.object(metrics, "at_commits", return_value="scripts/load_cache.py\nspecs/load_cache.py\n"):
            metrics.count_code(["old", "new1", "new2", "new1"], "load_cache\n", {"load_cache": 0})

    def test_only_the_commits_the_cache_lacks_are_grepped_and_each_once(self):
        asked = []
        self.count(lambda sha, patterns, index: asked.append(sha) or {"load_cache": {"run.py": 2}})
        self.assertEqual(sorted(asked), ["new1", "new2"])
        self.assertEqual(metrics.CACHE["code"], {
            "old": {"kept": {"a.py": 1}},
            "new1": {"load_cache": {"run.py": 2, "scripts/load_cache.py": 1}},
            "new2": {"load_cache": {"run.py": 2, "scripts/load_cache.py": 1}}})

    def test_two_greps_run_at_the_same_time(self):
        both = threading.Barrier(2, timeout=5)

        def grep(sha, patterns, index):
            try:
                both.wait()
            except threading.BrokenBarrierError:
                raise AssertionError("one grep waited 5 s and no other started") from None
            return {}

        self.count(grep)
        self.assertEqual(sorted(metrics.CACHE["code"]), ["new1", "new2", "old"])


if __name__ == "__main__":
    unittest.main()
