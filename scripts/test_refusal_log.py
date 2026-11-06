"""Each guard logs a refusal, and only a refusal; token-usage.py counts the log into refusals.json
without losing counts already committed.

    python scripts/test_refusal_log.py
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import refusal_log  # noqa: E402


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), os.path.join(HERE, name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(script, mode, data, env):
    args = [sys.executable, os.path.join(HERE, script)] + ([mode] if mode else [])
    return subprocess.run(args, input=json.dumps(data), capture_output=True, text=True, env=env)


class GuardsLogTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.log = os.path.join(self.dir, "state", "refusals.jsonl")
        self.env = dict(os.environ, CLAUDE_PROJECT_DIR=self.dir, GUARD_REFUSAL_LOG=self.log,
                        TMP=self.dir, TEMP=self.dir, TMPDIR=self.dir)

    def entries(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as f:
            return [json.loads(line) for line in f]

    def test_read_guard_logs_a_refusal_and_not_a_pass(self):
        big = os.path.join(self.dir, "big.md")
        with open(big, "wb") as f:
            f.write(b"x" * 9000 + b"\n")
        read = {"session_id": "s1", "tool_name": "Read", "tool_input": {"file_path": big}}
        self.assertEqual(run("read-guard.py", None, read, self.env).returncode, 2)
        read["tool_input"]["limit"] = 5
        self.assertEqual(run("read-guard.py", None, read, self.env).returncode, 0)
        got = self.entries()
        self.assertEqual([(e["guard"], e["session"], e["tool"], e["agent"]) for e in got],
                         [("read-guard", "s1", "Read", "main")])
        self.assertTrue(got[0]["reason"].startswith("read-guard: "))

    def test_step_guard_logs_a_refusal(self):
        os.makedirs(os.path.join(self.dir, ".claude", "state"))
        with open(os.path.join(self.dir, ".claude", "state", "step-guard.json"), "w") as f:
            json.dump({"session_id": "s2"}, f)
        agent = {"session_id": "s2", "tool_name": "Agent", "tool_input": {"subagent_type": "Explore"}}
        self.assertEqual(run("step-guard.py", "pre", agent, self.env).returncode, 2)
        self.assertEqual([e["guard"] for e in self.entries()], ["step-guard"])

    def test_auditor_guard_logs_a_block_and_not_a_read(self):
        def bash(command):
            return {"agent_id": "a1", "agent_type": "spec-auditor", "tool_name": "Bash",
                    "tool_input": {"command": command}}
        subprocess.run(["git", "init", "-q", self.dir], check=True)
        self.assertEqual(run("auditor-guard.py", "pre", bash("git commit -m x"), self.env).returncode, 2)
        self.assertEqual(run("auditor-guard.py", "pre", bash("git log -1"), self.env).returncode, 0)
        self.assertEqual([(e["guard"], e["agent"]) for e in self.entries()], [("auditor-guard", "spec-auditor")])

    def test_a_log_that_cannot_be_written_does_not_stop_the_refusal(self):
        os.makedirs(self.log)  # a directory where the file should be
        big = os.path.join(self.dir, "big.md")
        with open(big, "wb") as f:
            f.write(b"x" * 9000)
        read = {"tool_name": "Read", "tool_input": {"file_path": big}}
        self.assertEqual(run("read-guard.py", None, read, self.env).returncode, 2)


class CountsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.log = os.path.join(self.dir, "refusals.jsonl")
        lines = [{"time": "2026-11-05T10:00:00+01:00", "guard": "read-guard"},
                 {"time": "2026-11-05T11:00:00+01:00", "guard": "read-guard"},
                 {"time": "2026-11-06T09:00:00+01:00", "guard": "step-guard"}]
        with open(self.log, "w", encoding="utf-8") as f:
            f.write("".join(json.dumps(e) + "\n" for e in lines) + '{"time": "2026-11-0')  # cut short

    def test_counts_per_date_and_guard_skipping_a_broken_line(self):
        self.assertEqual(refusal_log.counts(self.log),
                         [{"date": "2026-11-05", "guard": "read-guard", "refused": 2},
                          {"date": "2026-11-06", "guard": "step-guard", "refused": 1}])
        self.assertEqual(refusal_log.counts(os.path.join(self.dir, "none.jsonl")), [])

    def test_token_usage_keeps_the_larger_count_of_each(self):
        out = os.path.join(self.dir, "refusals.json")
        with open(out, "w", encoding="utf-8") as f:  # committed from another machine
            json.dump([{"date": "2026-11-04", "guard": "auditor-guard", "refused": 3},
                       {"date": "2026-11-05", "guard": "read-guard", "refused": 5}], f)
        load("token-usage").write_refusals(out, self.log)
        with open(out, encoding="utf-8") as f:
            self.assertEqual(json.load(f), [{"date": "2026-11-04", "guard": "auditor-guard", "refused": 3},
                                            {"date": "2026-11-05", "guard": "read-guard", "refused": 5},
                                            {"date": "2026-11-06", "guard": "step-guard", "refused": 1}])

    def test_no_log_and_no_file_writes_nothing(self):
        out = os.path.join(self.dir, "refusals.json")
        load("token-usage").write_refusals(out, os.path.join(self.dir, "none.jsonl"))
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
