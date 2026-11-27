"""The reviewer's brief and settings (Day 12, Track A): driver.review.agents writes the agents file
--agents reads, and driver.settings.review writes the reviewer's settings, the step's two hooks then
the read-only hook. Checks C12.1 to C12.3."""

import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class ReviewAgentsTest(unittest.TestCase):
    def setUp(self):
        self.review = importlib.import_module("driver.review")
        self.root = tempfile.mkdtemp()
        self.state = os.path.join(self.root, "state")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_agents_file(self):
        # C12.1: the agents file names one agent, the reviewer, with its brief and its tools.
        path = self.review.agents(self.state, ROOT)
        self.assertTrue(path == os.path.join(os.path.abspath(self.state), "agents.json"))
        data = json.loads(Path(path).read_bytes())
        self.assertEqual(list(data), ["reviewer"])
        reviewer = data["reviewer"]
        self.assertEqual(sorted(reviewer), ["description", "prompt", "tools"])
        self.assertIsInstance(reviewer["description"], str)
        self.assertNotEqual(reviewer["description"].strip(), "")
        brief = (ROOT / "rules" / "reviewer.md").read_bytes().decode("utf-8")
        self.assertTrue(reviewer["prompt"] == brief)
        self.assertEqual(reviewer["tools"], ["Read", "Grep", "Glob", "Bash"])
        # Written afresh each time: a file someone changed is overwritten by the next call.
        first = Path(path).read_bytes()
        Path(path).write_bytes(b"{}")
        self.review.agents(self.state, ROOT)
        self.assertTrue(Path(path).read_bytes() == first)
        inside = self.review.agents(self.state, ROOT, inside=True)
        self.assertEqual(inside, "/state/agents.json")

    def test_brief_names_the_reply(self):
        # C12.2: the brief tells the reviewer the exact words the driver reads back.
        text = (ROOT / "rules" / "reviewer.md").read_bytes().decode("utf-8")
        for phrase in [
            "found: blocker — ",
            "found: advice — ",
            "REVIEW: blocker",
            "REVIEW: none",
            "gh pr diff",
            "change nothing",
        ]:
            with self.subTest(phrase=phrase):
                # Not assertIn: its message would print the whole brief, dashes and all.
                self.assertTrue(phrase in text, f"the brief lacks {phrase!r}")

    def test_brief_reads_the_callers(self):
        # C16.17: the brief sends the reviewer to the callers of what the diff changes, and has it
        # review a merged pull request as an open one (D12.38, D14.68).
        text = (ROOT / "rules" / "reviewer.md").read_bytes().decode("utf-8")
        for phrase in ["callers", "already merged", "as if it were open"]:
            with self.subTest(phrase=phrase):
                # Not assertIn: its message would print the whole brief.
                self.assertTrue(phrase in text, f"{phrase!r} not found in the brief")


class ReviewSettingsTest(unittest.TestCase):
    def setUp(self):
        self.settings = importlib.import_module("driver.settings")
        self.root = tempfile.mkdtemp()
        self.state = os.path.join(self.root, "state")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_review_settings(self):
        # C12.3: the reviewer's settings are the step's two hooks, then the read-only hook.
        path = self.settings.review(self.state, ROOT)
        state = os.path.abspath(self.state)
        self.assertTrue(path == os.path.join(state, "review-settings.json"))
        data = json.loads(Path(path).read_bytes())
        self.assertEqual(list(data), ["hooks"])
        entries = data["hooks"]["PreToolUse"]
        self.assertEqual(
            [e["matcher"] for e in entries], ["*", self.settings.GUARDED, "Bash|PowerShell"]
        )
        commands = [e["hooks"][0]["command"] for e in entries]
        self.assertTrue(len(commands) == 3)
        self.assertIn("halt.py", commands[0])
        self.assertIn("guard.py", commands[1])
        readonly = '"{}" "{}" "{}"'.format(
            sys.executable, ROOT / "hooks" / "readonly.py", os.path.join(state, "refusals")
        )
        self.assertTrue(commands[2] == readonly)
        write_entries = json.loads(Path(self.settings.write(self.state, ROOT)).read_bytes())[
            "hooks"
        ]["PreToolUse"]
        self.assertTrue(entries[:2] == write_entries)

    def test_inside(self):
        # C12.3, in the container: the same three hooks, typed as the paths the container mounts.
        path = self.settings.review(self.state, ROOT, inside=True)
        self.assertTrue(
            path == os.path.join(os.path.abspath(self.state), "review-container-settings.json")
        )
        entries = json.loads(Path(path).read_bytes())["hooks"]["PreToolUse"]
        self.assertEqual(
            [e["matcher"] for e in entries], ["*", self.settings.GUARDED, "Bash|PowerShell"]
        )
        self.assertEqual(len(entries), 3)
        self.assertEqual(
            entries[2]["hooks"][0]["command"],
            'python "/driver/hooks/readonly.py" "/state/refusals"',
        )
        write_entries = json.loads(
            Path(self.settings.write(self.state, ROOT, inside=True)).read_bytes()
        )["hooks"]["PreToolUse"]
        self.assertTrue(entries[:2] == write_entries)


if __name__ == "__main__":
    unittest.main()
