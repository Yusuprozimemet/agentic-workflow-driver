"""A track-reviewer's whole run is the track-reviewer gate (scripts/token-usage.py, gates), so the dashboard can give
its catches a cost. Kept apart from scripts/test_token_usage.py, which C15.16 freezes; it borrows that file's
transcript lines."""

import collections
import importlib.util
import json
import os
import tempfile
import unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
spec = importlib.util.spec_from_file_location(
    "token_usage_lines", os.path.join(SCRIPTS, "test_token_usage.py")
)
lines = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lines)


class TrackReviewerGateTest(unittest.TestCase):
    def gates(self, agent):
        """Each gate's (runs, replies) for a session that ran `ls`, and a subagent of this type that ran seen-red.py
        and then read a file."""
        call, result = lines.call, lines.result
        run = [
            call("x", "Bash", {"command": "python scripts/seen-red.py -- pytest"}),
            result("x", "seen red"),
            call("y", "Read"),
            result("y", "text"),
        ]
        with tempfile.TemporaryDirectory() as folder:
            paths = [
                os.path.join(folder, "session.jsonl"),
                os.path.join(folder, "subagents", "agent-1.jsonl"),
            ]
            os.makedirs(os.path.join(folder, "subagents"))
            with open(paths[0], "w", encoding="utf-8") as f:
                f.write(call("a", "Bash", {"command": "ls"}) + "\n")
            with open(paths[1], "w", encoding="utf-8") as f:
                f.write("\n".join(run) + "\n")
            with open(
                os.path.join(folder, "subagents", "agent-1.meta.json"), "w", encoding="utf-8"
            ) as f:
                json.dump({"agentType": agent}, f)
            rows = lines.tu.gates(paths)
        out = collections.defaultdict(lambda: [0, 0])
        for (_, _, gate), t in rows.items():
            out[gate][0] += t["runs"]
            out[gate][1] += t["replies"]
        return sorted((gate, runs, replies) for gate, (runs, replies) in out.items())

    def test_a_track_reviewers_run_is_all_its_replies_and_its_calls_are_no_other_gate(self):
        self.assertEqual(self.gates("track-reviewer"), [("track-reviewer", 1, 2)])

    def test_another_agents_run_is_no_gate_and_its_calls_keep_theirs(self):
        self.assertEqual(self.gates("implementer"), [("seen red", 1, 2)])


class TrackReviewerReportTest(unittest.TestCase):
    def test_the_gate_report_gives_the_track_reviewers_catches_its_runs_and_cost(self):
        spec = importlib.util.spec_from_file_location(
            "spec_drift_metrics", os.path.join(SCRIPTS, "spec_drift_metrics.py")
        )
        metrics = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(metrics)
        days = [
            {
                "defects": [
                    {"found": "track-reviewer", "cause": "spec"},
                    {"found": "Track A", "cause": "spec"},
                ]
            }
        ]
        gates = [
            {
                "gate": "track-reviewer",
                "runs": 2,
                "replies": 3,
                "context": 10,
                "output": 5,
                "cost": 1.5,
            }
        ]
        report = metrics.gate_report(days, gates, [])
        rows = {r["gate"]: r for r in report["gates"]}
        self.assertIn("track-reviewer", sorted(rows))
        row = rows["track-reviewer"]
        self.assertEqual(
            (row["found"], row["defects"], row["runs"], row["cost"]), ("track-reviewer", 1, 2, 1.5)
        )
        self.assertEqual(report["elsewhere"], 1)


if __name__ == "__main__":
    unittest.main()
