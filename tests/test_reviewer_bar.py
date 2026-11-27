"""The driver's reviewer meets its bar on the brief as it is (Day 16, Track D; C16.18).

specs/agent-cases/reviewer.json's recorded count must be of today's rules/reviewer.md, of 3 runs,
and its per-case record must show the two faults found after they merged
(agentic-workflow-driver#214 and #250) filed as blockers and named in at least 2 of the 3 runs,
and the two clean bearing pull requests (#153, #154) given `none` in at least 2. The test sits in
tests/ so that every pull request runs it, one that edits only rules/reviewer.md included: the
next edit to the brief fails it until a new `agent-cases.py reviewer --record` meets the bar.
"""

import json
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
BLOCKERS = ["agentic-workflow-driver#214", "agentic-workflow-driver#250"]
CLEAN = ["bearing#153", "bearing#154"]


def shortfall(data, sha):
    """None when the recorded count meets the bar on the brief at `sha`, else the first shortfall
    in fixed words."""
    recorded = data.get("recorded")
    if not recorded or "cases" not in recorded:
        return "no per-case record"
    if recorded.get("brief") != sha:
        return f"recorded on brief {recorded.get('brief')}, rules/reviewer.md is {sha}"
    if recorded.get("runs") != 3:
        return f"recorded on {recorded.get('runs')} runs, the bar is of 3"
    entries = {e.get("case"): e for e in recorded["cases"]}
    for name in BLOCKERS:
        if name not in entries:
            return f"{name}: no entry"
        said, named = entries[name]["said"], entries[name]["named"]
        if said.count("blocker") < 2:
            return f"{name}: blocker in {said.count('blocker')} of {len(said)} runs, the bar is 2"
        if named < 2:
            return f"{name}: named in {named} of {len(said)} runs, the bar is 2"
    for name in CLEAN:
        if name not in entries:
            return f"{name}: no entry"
        said = entries[name]["said"]
        if said.count("none") < 2:
            return f"{name}: none in {said.count('none')} of {len(said)} runs, the bar is 2"
    return None


class ReviewerBarTest(unittest.TestCase):
    def test_brief_meets_the_bar(self):
        # C16.18: the recorded count is of today's brief and each known case meets the bar.
        data = json.loads((ROOT / "specs" / "agent-cases" / "reviewer.json").read_bytes())
        done = subprocess.run(
            ["git", "hash-object", "rules/reviewer.md"], cwd=ROOT, capture_output=True, check=True
        )
        sha = done.stdout.decode().strip()[:7]
        got = shortfall(data, sha)
        self.assertIsNone(got, got)


if __name__ == "__main__":
    unittest.main()
