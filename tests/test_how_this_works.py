"""The excerpts the dashboard's "How this works" panel shows: read from the real files at build
time, for a promise picked at build time, and marked missing when a file or passage has gone."""

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "dashboard"
spec = importlib.util.spec_from_file_location("spec_drift", ROOT / "scripts" / "spec-drift.py")
spec_drift = importlib.util.module_from_spec(spec)
spec.loader.exec_module(spec_drift)

SPECS = sorted(((ROOT / "specs").glob("day-*.md")), reverse=True)
SPECS = [p.relative_to(ROOT).as_posix() for p in SPECS]


def real(path):
    return (ROOT / path).read_text(encoding="utf-8")


def flat(text):
    return re.sub(r"\s+", " ", text).strip()


NEW, OLD = "specs/day-98-newer.md", "specs/day-97-older.md"
NEW_BREAKS, OLD_BREAKS = "specs/breaks/day-98.json", "specs/breaks/day-97.json"
PLAN = (
    "### Phase 1 — Level 1\n**Goal:** one day.\n"
    "- Day 97: the older day,\n  on two lines.\n- Day 98: the newer day.\n\n## Next\n"
)
TEMPLATE = "## Goal\n\n- [ ] CNN.1 a form\n- [ ] CNN.2 more\n"
SEEN = "seen red: python -m unittest t on main → FAILED (errors=1) (#7)"


def criterion(cid, tag="new", box="x", evidence="`T.test_a` (#7)", seen=SEEN, bug=None):
    bug = f"{cid} bug" if bug is None else bug
    lines = [
        f"- [{box}] {cid} **{tag}** — does a thing.",
        "      Red today: it does not.",
        "      Test: `T.test_a`.",
        f"      Evidence: {evidence}.",
    ]
    lines += [f"      {seen}"] if seen else []
    lines += [f"      broken: {bug} → AssertionError: no (#7)"] if bug else []
    return "\n".join(lines) + "\n"


def day_spec(day, criteria, untracked=()):
    ids = [re.search(r"C\d+\.\d+", c).group(0) for c in criteria]
    rows = "".join(
        f"| {letter} | | {cid}: the work |\n"
        for letter, cid in zip(("A2", "B", "C"), ids)
        if cid not in untracked
    )
    return (
        f"# Day {day}\n\n**Phase:** 1 · **Depends on:** x\n\n## Goal\nThe goal.\n\n"
        "## Out of scope\n- Left out.\n\n"
        f"## Tracks\n\n| Track | Owner | Work |\n|---|---|---|\n{rows}\n"
        f"## Acceptance criteria\n\n{''.join(criteria)}\n## Notes\n"
    )


def manifest(*ids):
    return json.dumps(
        [{"what": f"{c} bug", "file": "driver/x.py", "find": "a", "replace": "b"} for c in ids]
    )


def world(newest=None, untracked=(), rechecked=("C98.1", "C98.2", "C97.1"), plan=PLAN, gone=()):
    """A `read` over two finished days whose first promises are all on record, unless told not."""
    files = {
        NEW: day_spec(98, newest or [criterion("C98.1"), criterion("C98.2")], untracked),
        NEW_BREAKS: manifest("C98.1", "C98.2"),
        OLD: day_spec(97, [criterion("C97.1")]),
        OLD_BREAKS: manifest("C97.1"),
        spec_drift.HOW_TEMPLATE: TEMPLATE,
        spec_drift.HOW_PLAN: plan,
        spec_drift.HOW_REPLAY: json.dumps(
            {
                "rows": [
                    {"criterion": c, "n": 1, "pr": 7, "check": "T.test_a", "state": "pass"}
                    for c in rechecked
                ]
            }
        ),
    }
    return lambda path: "" if path in gone else files.get(path, "")


def picked(read):
    return spec_drift.how_excerpts(read, [NEW, OLD])["promise"]["text"]["id"]


class PickTest(unittest.TestCase):
    def test_the_newest_finished_days_first_whole_promise_is_picked(self):
        got = spec_drift.how_excerpts(world(), [NEW, OLD])
        self.assertEqual(
            got["promise"]["text"], {"id": "C98.1", "day": 98, "spec": NEW, "breaks": NEW_BREAKS}
        )
        self.assertEqual(
            got["crumbs"]["text"],
            ["plan.md", "Phase 1", "Day 98", "Track A2 (PR #7)", "Promise C98.1"],
        )
        self.assertEqual(got["day_tracks"]["text"], "Tracks A2, B")
        self.assertEqual(got["claim"]["text"], "does a thing.")
        self.assertEqual(got["bugs"]["source"], NEW_BREAKS)
        self.assertEqual(got["seen_red"]["text"], SEEN)

    def test_the_plan_excerpt_is_the_picked_days_schedule(self):
        heading = "### Phase 1 — Level 1\n**Goal:** one day.\n"
        got = spec_drift.how_excerpts(world(), [NEW, OLD])
        self.assertEqual(got["plan_phase"]["text"], heading + "- Day 98: the newer day.")
        got = spec_drift.how_excerpts(world(), [OLD])
        self.assertEqual(
            got["plan_phase"]["text"], heading + "- Day 97: the older day,\n  on two lines."
        )

    def test_a_promise_missing_a_step_is_skipped(self):
        second = criterion("C98.2")
        cases = {
            "hold": {"newest": [criterion("C98.1", tag="hold"), second]},
            "unticked": {"newest": [criterion("C98.1", box=" "), second]},
            "no_pr": {"newest": [criterion("C98.1", evidence="`T.test_a`"), second]},
            "no_seen_red": {"newest": [criterion("C98.1", seen=""), second]},
            "no_bug": {"newest": [criterion("C98.1", bug=""), second]},
            "bug_not_in_manifest": {"newest": [criterion("C98.1", bug="another"), second]},
            "no_track": {"untracked": ("C98.1",)},
            "no_recheck": {"rechecked": ("C98.2", "C97.1")},
        }
        for name, kwargs in cases.items():
            with self.subTest(name):
                self.assertEqual(picked(world(**kwargs)), "C98.2")

    def test_either_wording_of_seen_red_counts(self):
        line = "seen red first on `main`'s code: `python x` → FAILED"
        read = world(newest=[criterion("C98.1", seen=line)])
        self.assertEqual(spec_drift.how_excerpts(read, [NEW, OLD])["seen_red"]["text"], line)

    def test_an_older_day_serves_when_the_newest_has_none_whole(self):
        for name, read in (
            ("no re-check", world(rechecked=("C97.1",))),
            ("spec gone", world(gone=(NEW,))),
            ("breaks gone", world(gone=(NEW_BREAKS,))),
            ("not scheduled", world(plan=PLAN.replace("- Day 98: the newer day.\n", ""))),
        ):
            with self.subTest(name):
                self.assertEqual(picked(read), "C97.1")

    def test_only_finished_days_are_read_newest_first(self):
        days = [
            {"day": 5, "status": "closed", "file": "five"},
            {"day": 7, "status": "active", "file": "seven"},
            {"day": 6, "status": "done", "file": "six"},
            {"day": 8, "status": "ready", "file": "eight"},
        ]
        self.assertEqual(spec_drift.how_specs(days), ["six", "five"])

    def test_no_whole_promise_shows_as_missing(self):
        got = spec_drift.how_excerpts(world(rechecked=()), [NEW, OLD])
        self.assertNotIn("text", got["promise"])
        for key in spec_drift.HOW_NEEDED:
            self.assertEqual(got[key]["missing"], spec_drift.HOW_NO_PROMISE, key)
        self.assertIn("text", got["form"])
        self.assertEqual(
            spec_drift.how_excerpts(real, [])["form"]["source"], spec_drift.HOW_TEMPLATE
        )

    def test_a_shared_file_gone_does_not_end_the_pick(self):
        for gone in (spec_drift.HOW_TEMPLATE, spec_drift.HOW_PLAN):
            with self.subTest(gone=gone):
                got = spec_drift.how_excerpts(world(gone=(gone,)), [NEW, OLD])
                self.assertEqual(got["promise"]["text"]["id"], "C98.1")
                mine = [x for x in got.values() if x["source"] == gone]
                self.assertTrue(mine)
                for x in mine:
                    self.assertNotIn("text", x)
                    self.assertIn("missing", x["missing"])


class ExcerptTest(unittest.TestCase):
    def setUp(self):
        self.got = spec_drift.how_excerpts(real, SPECS)
        self.chosen = self.got["promise"]["text"]

    def test_the_build_puts_them_in_the_data(self):
        self.assertIn('real["how_this_works"] = how_excerpts(', real("scripts/spec-drift.py"))
        self.assertIn("how_specs(days))", real("scripts/spec-drift.py"))

    def test_the_page_follows_the_data_not_a_fixed_promise(self):
        page = real("docs/dashboard/dashboard.js")
        for fixed in ("C03.3", "day-03", "Day 3's"):
            self.assertNotIn(fixed, page)

    def test_every_excerpt_is_read_from_its_file(self):
        got = self.got
        self.assertEqual([k for k, x in got.items() if "text" not in x], [])
        spec_text = flat(real(self.chosen["spec"]))
        for key in ("claim", "red_today", "evidence", "seen_red", "day_goal"):
            self.assertIn(got[key]["text"], spec_text, key)
        self.assertIn(got["form"]["text"], real(spec_drift.HOW_TEMPLATE))
        for part in got["plan_phase"]["text"].split("\n"):
            self.assertIn(part, real(spec_drift.HOW_PLAN))

    def test_the_planted_bugs_are_the_manifests(self):
        got = self.got["bugs"]["text"]
        manifest_now = {b["what"]: b for b in json.loads(real(self.chosen["breaks"]))}
        self.assertTrue(got)
        for bug in got:
            self.assertEqual(
                (bug["find"], bug["replace"]),
                (manifest_now[bug["what"]]["find"], manifest_now[bug["what"]]["replace"]),
            )
            self.assertTrue(bug["reported"], bug)

    def test_the_recheck_is_the_promises_newest(self):
        got = self.got["recheck"]["text"]
        rows = [
            r
            for r in json.loads(real(spec_drift.HOW_REPLAY))["rows"]
            if r["criterion"] == self.chosen["id"]
        ]
        newest = max(r["n"] for r in rows)
        self.assertEqual(
            sorted(c["check"] for c in got["checks"]),
            sorted(r["check"] for r in rows if r["n"] == newest),
        )
        self.assertEqual(got["pr"], next(r["pr"] for r in rows if r["n"] == newest))

    def test_a_passage_every_promise_shares_going_is_marked_missing(self):
        cases = [
            ("form", spec_drift.HOW_TEMPLATE, lambda t: t.replace("CNN.1", "XNN.1")),
            (
                "plan_parts",
                spec_drift.HOW_PLAN,
                lambda t: t.replace("## Stopping points", "## Halts"),
            ),
        ]
        for key, path, change in cases:
            with self.subTest(key=key):
                got = spec_drift.how_excerpts(
                    lambda p, change=change, path=path: change(real(p)) if p == path else real(p),
                    SPECS,
                )[key]
                self.assertNotIn("text", got)
                self.assertIn("no longer there", got["missing"])


if __name__ == "__main__":
    unittest.main()
