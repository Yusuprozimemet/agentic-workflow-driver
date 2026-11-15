"""scripts/session-size.py warns past 150k tokens of context, once per 50k, and blocks nothing."""

import importlib.util
import json
import os
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location("session_size", os.path.join(HERE, "session-size.py"))
ss = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ss)


def reply(read, sidechain=False):
    return {"type": "assistant", "isSidechain": sidechain,
            "message": {"usage": {"input_tokens": 10, "cache_creation_input_tokens": 990, "cache_read_input_tokens": read}}}


class SessionSizeTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.transcript = os.path.join(self.dir, "t.jsonl")
        self.state = os.path.join(self.dir, "state", "session-size.json")

    def at(self, *entries):
        with open(self.transcript, "w", encoding="utf-8") as f:
            f.write("".join(json.dumps(e) + "\n" for e in entries))
        return ss.handle({"session_id": "s1", "transcript_path": self.transcript}, self.state)

    def test_below_150k_nothing_is_said(self):
        self.assertIsNone(self.at(reply(148_000)))

    def test_past_150k_both_are_warned_once_then_again_at_200k(self):
        out = self.at(reply(100_000), reply(160_000))
        self.assertTrue(out["systemMessage"].startswith("This session's context is 161k tokens, past 150k"))
        self.assertEqual(out["hookSpecificOutput"], {"hookEventName": "PostToolUse",
                                                     "additionalContext": out["systemMessage"]})
        self.assertNotIn("decision", out)  # a warning, never a refusal
        self.assertIsNone(self.at(reply(190_000)), "once per step")
        self.assertIn("context is 211k", self.at(reply(210_000))["systemMessage"])

    def test_a_subagent_s_reply_is_not_the_session_s_size(self):
        self.assertIsNone(self.at(reply(10_000), reply(400_000, sidechain=True), {"type": "user"}))

    def test_an_unreadable_or_empty_transcript_says_nothing(self):
        self.assertIsNone(ss.handle({"session_id": "s1", "transcript_path": os.path.join(self.dir, "none")}, self.state))
        self.assertIsNone(self.at({"type": "user"}))


if __name__ == "__main__":
    unittest.main()
