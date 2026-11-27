"""The driver's reviewer meets its bar on the brief as it is (Day 16, Track D; C16.18).

specs/agent-cases/reviewer.json's recorded count must be of today's rules/reviewer.md, of 3 runs,
with a worst `verdict` not lower than the record at 2561efb (brief 401eb39), and its per-case
record must give the two clean bearing pull requests (#153, #154) `none` in at least 2 of the
3 runs: a brief that reads the callers must not cost a clean PR its `none`. The baseline is a
constant, since CI's Tests job checks out one commit and cannot read 2561efb; every later brief
is held to the same 2, so the bar does not ratchet. `named` carries no bar (that record's is 0).
The test sits in tests/ so that every pull request runs it, one that edits only
rules/reviewer.md included: the next edit to the brief fails it until a new
`agent-cases.py reviewer --record` meets the bar.
"""

import json
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
VERDICT_BAR = 2  # recorded.verdict at 2561efb, brief 401eb39
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
    if recorded.get("verdict", 0) < VERDICT_BAR:
        return f"worst verdict {recorded.get('verdict')}, the bar is {VERDICT_BAR}"
    entries = {e.get("case"): e for e in recorded["cases"]}
    for name in CLEAN:
        if name not in entries:
            return f"{name}: no entry"
        said = entries[name]["said"]
        if said.count("none") < 2:
            return f"{name}: none in {said.count('none')} of {len(said)} runs, the bar is 2"
    return None


class ReviewerBarTest(unittest.TestCase):
    def test_brief_meets_the_bar(self):
        # C16.18: the recorded count is of today's brief and meets the bar.
        data = json.loads((ROOT / "specs" / "agent-cases" / "reviewer.json").read_bytes())
        done = subprocess.run(
            ["git", "hash-object", "rules/reviewer.md"], cwd=ROOT, capture_output=True, check=True
        )
        sha = done.stdout.decode().strip()[:7]
        got = shortfall(data, sha)
        self.assertIsNone(got, got)


def good():
    """A record that meets the bar, for ShortfallTest to spoil one way at a time."""
    each = [{"case": n, "said": ["none"] * 3, "named": 0} for n in CLEAN]
    return {"recorded": {"verdict": 2, "named": 0, "runs": 3, "brief": "abc1234", "cases": each}}


class ShortfallTest(unittest.TestCase):
    """Each way the record can fall short gives its own line; the good record gives none."""

    def test_each_shortfall(self):
        self.assertIsNone(shortfall(good(), "abc1234"))
        spoil = {
            "no cases": (lambda r: r.pop("cases"), "no per-case record"),
            "brief": (
                lambda r: r.update(brief="def5678"),
                "recorded on brief def5678, rules/reviewer.md is abc1234",
            ),
            "runs": (lambda r: r.update(runs=2), "recorded on 2 runs, the bar is of 3"),
            "verdict": (lambda r: r.update(verdict=1), "worst verdict 1, the bar is 2"),
            "no clean entry": (lambda r: r["cases"].pop(0), "bearing#153: no entry"),
            "none": (
                lambda r: r["cases"][1].update(said=["none", "blocker", "unreadable"]),
                "bearing#154: none in 1 of 3 runs, the bar is 2",
            ),
        }
        for what, (change, line) in spoil.items():
            with self.subTest(what=what):
                data = good()
                change(data["recorded"])
                self.assertEqual(line, shortfall(data, "abc1234"))


if __name__ == "__main__":
    unittest.main()
