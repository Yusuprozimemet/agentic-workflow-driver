"""--once's end line names the tools a session was refused: one entry per denial, its tool and its
input cut to 200 characters, and a reply with no denial list gets no refused key. Each case runs
--once with the fake claude, as test_once_outcome does."""

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

from tests import test_once_outcome as outcome
from tests.test_once import driver_copy


class RefusedTest(unittest.TestCase):
    def setUp(self):
        # Imported here, as in test_once: where driver/ is missing, each test fails alone.
        importlib.import_module("driver.once")
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def end_of(self, denials=None):
        # The reply's permission_denials is denials; None leaves the key out of the reply.
        reply = {"type": "result", "is_error": False, "result": "done"}
        if denials is not None:
            reply["permission_denials"] = denials
        copy = driver_copy(tempfile.mkdtemp(dir=self.root))
        result = outcome.OutcomeTest.run_case(self, copy=copy, result=reply)
        return result["records"][-1]

    def test_end_names_refused_tools(self):
        denials = [
            {
                "tool_name": "Bash",
                "tool_use_id": "toolu_1",
                "tool_input": {"command": "git push --force"},
            },
            {},
            "x",
        ]
        end = self.end_of(denials)
        self.assertEqual(end["denials"], 3)
        self.assertEqual(
            end["refused"],
            [
                {"tool": "Bash", "input": '{"command": "git push --force"}'},
                {"tool": "unknown", "input": "{}"},
                {"tool": "unknown", "input": "{}"},
            ],
        )
        for denials in (None, []):
            with self.subTest(denials=denials):
                end = self.end_of(denials)
                self.assertNotIn("refused", end)
                self.assertEqual(end["denials"], 0)

    def test_malformed_denials(self):
        denials = [
            {"tool_name": None, "tool_input": {"a": 1}},
            {"tool_name": 5},
            5,
            None,
            [],
        ]
        end = self.end_of(denials)
        self.assertEqual(end["denials"], 5)
        self.assertEqual(
            end["refused"],
            [
                {"tool": "unknown", "input": '{"a": 1}'},
                {"tool": "unknown", "input": "{}"},
                {"tool": "unknown", "input": "{}"},
                {"tool": "unknown", "input": "{}"},
                {"tool": "unknown", "input": "{}"},
            ],
        )
        end = self.end_of("x")
        self.assertEqual(end["denials"], 0)
        self.assertNotIn("refused", end)

    def test_input_cut(self):
        end = self.end_of([{"tool_name": "Write", "tool_input": {"content": "a" * 500}}])
        refused = end["refused"]
        self.assertEqual(refused[0]["tool"], "Write")
        self.assertEqual(refused[0]["input"], json.dumps({"content": "a" * 500})[:200])
        self.assertEqual(len(refused[0]["input"]), 200)
