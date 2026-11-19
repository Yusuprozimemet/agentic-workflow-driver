"""token-usage.py reads the driver container's transcripts with --container: its Claude Code runs in /work,
so its sessions are under -work, and --container is refused without --compare or --tools (C14.2, C14.3)."""

import datetime
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, os.pardir, "scripts", "token-usage.py")


def load():
    spec = importlib.util.spec_from_file_location("token_usage", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tu = load()


def reply(message_id, context, when):
    entry = {
        "type": "assistant",
        "requestId": "req_" + message_id,
        "timestamp": when,
        "isSidechain": False,
        "message": {
            "id": message_id,
            "model": "claude-haiku-5-5-20260101",
            "usage": {
                "input_tokens": 1,
                "cache_creation_input_tokens": 9,
                "cache_read_input_tokens": context - 10,
                "output_tokens": 5,
            },
        },
    }
    return json.dumps(entry)


def write(path, *lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(line + "\n" for line in lines))


class ContainerTest(unittest.TestCase):
    """The container's transcripts are the ones under -work, and only those, and --compare counts them."""

    def test_work_folder_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "root")
            repo = os.path.join(tmp, "repo")
            d = os.path.join(tmp, "d")
            os.makedirs(root)
            write(os.path.join(d, "-work", "s1.jsonl"), reply("1", 50_000, "2026-11-20T12:00:00Z"))
            write(
                os.path.join(d, "-work", "s1", "subagents", "agent-a1.jsonl"),
                reply("2", 60_000, "2026-11-20T12:00:00Z"),
            )
            write(os.path.join(d, "stray.jsonl"), reply("3", 70_000, "2026-11-20T12:00:00Z"))
            write(os.path.join(d, "-other", "s2.jsonl"), reply("4", 80_000, "2026-11-20T12:00:00Z"))
            found = [
                os.path.relpath(p.replace("\\\\?\\", ""), d).replace(os.sep, "/")
                for p in tu.transcripts(root, repo, container=d)
            ]
            self.assertEqual(sorted(found), ["-work/s1.jsonl", "-work/s1/subagents/agent-a1.jsonl"])

    def test_compare_counts_container_replies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "root")
            repo = os.path.join(tmp, "repo")
            d = os.path.join(tmp, "d")
            os.makedirs(root)
            write(
                os.path.join(d, "-work", "s1.jsonl"),
                reply("1", 50_000, "2026-11-20T12:00:00Z"),
                reply("2", 60_000, "2026-11-20T12:00:00Z"),
            )
            write(
                os.path.join(d, "-work", "s1", "subagents", "agent-a1.jsonl"),
                reply("3", 70_000, "2026-11-20T12:00:00Z"),
            )
            files = [p for p in tu.transcripts(root, repo, container=d) if tu.agent(p) == "main"]
            s = tu.compare(files, (datetime.date(2026, 11, 2),))
            self.assertIn("contexts", s["after"])
            self.assertEqual(len(s["after"]["contexts"]), 2)
            self.assertEqual(s["after"]["contexts"], [50_000, 60_000])
            self.assertEqual(s["before"]["contexts"], [])

    def test_container_without_compare_or_tools_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = os.path.join(tmp, "empty")
            container = os.path.join(tmp, "container")
            out = os.path.join(tmp, "token-usage.json")
            os.makedirs(empty)
            os.makedirs(container)
            run = subprocess.run(
                [
                    sys.executable,
                    SCRIPT,
                    "--transcripts",
                    empty,
                    "--container",
                    container,
                    "--out",
                    out,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 2)
            self.assertIn("--container needs --compare or --tools", run.stderr)
            self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
