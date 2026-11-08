"""The excerpts the dashboard's "How this works" panel shows: read from the real files at build
time, and marked missing when a file or passage has gone."""

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


def real(path):
    return (ROOT / path).read_text(encoding="utf-8")


def flat(text):
    return re.sub(r"\s+", " ", text).strip()


class ExcerptTest(unittest.TestCase):
    def test_the_build_puts_them_in_the_data(self):
        self.assertIn('real["how_this_works"] = how_excerpts(', real("scripts/spec-drift.py"))

    def test_every_excerpt_is_read_from_its_file(self):
        got = spec_drift.how_excerpts(real)
        self.assertEqual([k for k, x in got.items() if "text" not in x], [])
        spec_text = flat(real(spec_drift.HOW_SPEC))
        for key in ("claim", "red_today", "evidence", "seen_red", "day_goal"):
            self.assertIn(got[key]["text"], spec_text, key)
        self.assertIn(got["form"]["text"], real(spec_drift.HOW_TEMPLATE))
        self.assertIn(got["plan_halt"]["text"], real(spec_drift.HOW_PLAN))
        self.assertIn(got["plan_phase"]["text"], real(spec_drift.HOW_PLAN))

    def test_the_planted_bugs_are_the_manifests(self):
        got = spec_drift.how_excerpts(real)["bugs"]["text"]
        manifest = {b["what"]: b for b in json.loads(real(spec_drift.HOW_BREAKS))}
        self.assertEqual(len(got), 2)
        for bug in got:
            self.assertEqual(
                (bug["find"], bug["replace"]),
                (manifest[bug["what"]]["find"], manifest[bug["what"]]["replace"]),
            )
            self.assertTrue(bug["reported"].startswith("AssertionError"), bug)

    def test_the_recheck_is_the_promises_newest(self):
        got = spec_drift.how_excerpts(real)["recheck"]["text"]
        rows = [
            r
            for r in json.loads(real(spec_drift.HOW_REPLAY))["rows"]
            if r["criterion"] == spec_drift.HOW_PROMISE
        ]
        newest = max(r["n"] for r in rows)
        self.assertEqual(
            sorted(c["check"] for c in got["checks"]),
            sorted(r["check"] for r in rows if r["n"] == newest),
        )
        self.assertEqual(got["pr"], next(r["pr"] for r in rows if r["n"] == newest))

    def test_a_missing_file_is_marked_missing(self):
        files = (
            spec_drift.HOW_SPEC,
            spec_drift.HOW_TEMPLATE,
            spec_drift.HOW_BREAKS,
            spec_drift.HOW_REPLAY,
            spec_drift.HOW_PLAN,
        )
        for gone in files:
            with self.subTest(gone=gone):
                got = spec_drift.how_excerpts(lambda p, gone=gone: "" if p == gone else real(p))
                mine = [x for x in got.values() if x["source"] == gone]
                self.assertTrue(mine)
                for x in mine:
                    self.assertNotIn("text", x)
                    self.assertIn("missing", x["missing"])

    def test_a_passage_that_has_gone_is_marked_missing(self):
        cases = [
            ("claim", spec_drift.HOW_SPEC, lambda t: t.replace("C03.3 **new**", "C03.33 **new**")),
            ("form", spec_drift.HOW_TEMPLATE, lambda t: t.replace("CNN.1", "XNN.1")),
            (
                "bugs",
                spec_drift.HOW_BREAKS,
                lambda t: t.replace("the halt hook passes while", "something else while"),
            ),
            ("recheck", spec_drift.HOW_REPLAY, lambda t: t.replace('"C03.3"', '"C99.9"')),
            (
                "plan_parts",
                spec_drift.HOW_PLAN,
                lambda t: t.replace("## Stopping points", "## Halts"),
            ),
        ]
        for key, path, change in cases:
            with self.subTest(key=key):
                got = spec_drift.how_excerpts(
                    lambda p, change=change, path=path: change(real(p)) if p == path else real(p)
                )[key]
                self.assertNotIn("text", got)
                self.assertIn("no longer there", got["missing"])


if __name__ == "__main__":
    unittest.main()
