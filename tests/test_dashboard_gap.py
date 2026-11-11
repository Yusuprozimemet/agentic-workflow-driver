"""The dashboard's gap against chance, and the names split by class: the helpers in
scripts/spec-drift.py that the name-gap chart and its caption read."""

import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_spec_drift():
    spec = importlib.util.spec_from_file_location("spec_drift", ROOT / "scripts" / "spec-drift.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


spec_drift = load_spec_drift()


class NameClassTest(unittest.TestCase):
    def test_test_shapes_are_test_names(self):
        self.assertEqual(spec_drift.name_class("test_once_parks", set()), "test")
        self.assertEqual(spec_drift.name_class("HaltTest", {"prod"}), "test")
        self.assertEqual(spec_drift.name_class("TestCase", set()), "test")

    def test_helper_only_in_tests_is_a_test_name(self):
        self.assertEqual(spec_drift.name_class("fake_gh", {"test"}), "test")
        self.assertEqual(spec_drift.name_class("fake_gh", {"test", "prod"}), "prod")
        self.assertEqual(spec_drift.name_class("next_step", set()), "prod")


class FlagTest(unittest.TestCase):
    def test_flags_from_backtick_spans(self):
        texts = {
            "specs/day-01-x.md": "Run `python run-steps.py --once --dry-run` then --poll outside ticks, "
            "and `--max-budget-usd 5`; not `a--b` or `---`."
        }
        self.assertEqual(spec_drift.spec_flags(texts), {"--once", "--dry-run", "--max-budget-usd"})


class ChanceTest(unittest.TestCase):
    def test_percentile_in(self):
        self.assertEqual(spec_drift.percentile_in(np.array([1.0, 2.0, 3.0, 4.0]), 3.0), 62.5)
        self.assertEqual(spec_drift.percentile_in(np.array([1.0, 2.0]), 0.5), 0.0)
        self.assertIsNone(spec_drift.percentile_in(np.array([]), 1.0))
        self.assertIsNone(spec_drift.percentile_in(np.array([1.0]), None))

    def test_chance_angle_unchanged(self):
        x = np.log1p(np.array([3, 0, 1, 5, 2.0]))
        y = np.log1p(np.array([1, 4, 0, 2, 2.0]))
        keep = np.array([True] * 5)
        chance = spec_drift.chance_angle(x, y, keep)
        self.assertEqual(chance, spec_drift.band(spec_drift.chance_draws(x, y, keep)))
        self.assertEqual(len(chance), 3)
        one = np.array([True, False, False, False, False])
        self.assertEqual(spec_drift.chance_angle(x, y, one), [round(spec_drift.angle(x, y), 2)] * 3)


class NameStepsTest(unittest.TestCase):
    """name_steps: what a merge added to the specs and dropped, per class, against the merge before."""

    def test_added_and_dropped_by_class(self):
        klass = np.array(["prod", "test", "test", "prod"])
        before = (np.array([True, True, False, False]), klass, {"--a", "--b"})
        after = (np.array([False, True, True, True]), klass, {"--b", "--c", "--d"})
        added, dropped = spec_drift.name_steps(before, after)
        self.assertEqual(added, {"prod": 1, "test": 1, "flags": 2})
        self.assertEqual(dropped, {"prod": 1, "test": 0, "flags": 1})

    def test_a_dropped_name_keeps_its_class_from_before(self):
        # The name was a test name where the specs named it; at the merge that drops it, it is found
        # nowhere and reads as prod. It is counted where it was.
        before = (np.array([True]), np.array(["test"]), set())
        after = (np.array([False]), np.array(["prod"]), set())
        added, dropped = spec_drift.name_steps(before, after)
        self.assertEqual(dropped, {"prod": 0, "test": 1, "flags": 0})
        self.assertEqual(added, {"prod": 0, "test": 0, "flags": 0})


def load_evidence():
    spec = importlib.util.spec_from_file_location("evidence", ROOT / "scripts" / "evidence.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProvedByTest(unittest.TestCase):
    """evidence.py's proved_by: every kind that proved a ticked criterion, in a fixed order."""

    def test_every_kind_found_in_order(self):
        evidence = load_evidence()
        test = {("CliTest", "test_x"): None}
        self.assertEqual(
            evidence.proved_by(test, "git x", True, None), ["test", "command", "break"]
        )
        self.assertEqual(evidence.proved_by({}, None, True, None), ["break"])

    def test_reader_only_with_nothing_else(self):
        evidence = load_evidence()
        self.assertEqual(evidence.proved_by({}, None, False, "a person reads it"), ["reader"])
        self.assertEqual(evidence.proved_by({}, "git x", False, "a person reads it"), ["command"])
        self.assertEqual(evidence.proved_by({}, None, False, None), [])


class ReplayHistoryTest(unittest.TestCase):
    """spec-drift.py's replay_history: one cell per criterion and merge, its checks' worst state."""

    WORST_FIRST = (
        "code broken",
        "test weakened",
        "break no longer applies",
        "not runnable",
        "not applicable on this platform",
        "live only",
        "holds, never broken",
        "holds",
    )

    def write(self, data):
        folder = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(folder, ignore_errors=True))
        path = os.path.join(folder, "replay-history.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return path

    def test_a_criterion_takes_its_worst_check_and_not_yet_in_force_only_when_every_check_is(self):
        for i, worse in enumerate(self.WORST_FIRST):
            for better in (*self.WORST_FIRST[i + 1 :], "not yet in force"):
                self.assertEqual(spec_drift.replay_state({worse, better}), worse, (worse, better))
        self.assertEqual(spec_drift.replay_state({"not yet in force"}), "not yet in force")

    def test_the_page_reads_every_state_replay_history_writes(self):
        spec = importlib.util.spec_from_file_location(
            "replay_history", ROOT / "scripts" / "replay-history.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(sorted(spec_drift.REPLAY_STATES), sorted(module.STATES))
        script = (ROOT / "docs" / "dashboard" / "dashboard.js").read_text(encoding="utf-8")
        look = re.search(r"const REPLAY_LOOK = \{(.*?)\n\};", script, re.DOTALL).group(1)
        drawn = set(re.findall(r'^\s*"([^"]+)":', look, re.MULTILINE))
        self.assertEqual(sorted(drawn), sorted(module.STATES))
        self.assertEqual(sorted(drawn), sorted((*self.WORST_FIRST, "not yet in force")))

    def test_an_old_holds_row_with_its_teeth_unchecked_reads_as_never_broken(self):
        row = {"day": "01", "platform": "windows", "pr": 9, "sample": "all", "merge": "aaa", "n": 5}
        rows = [
            dict(
                row,
                criterion="C01.1",
                check="tests",
                state="holds",
                detail="teeth unchecked: no broken: line",
            ),
            dict(row, criterion="C01.2", check="b", state="holds", detail="reported X"),
            dict(
                row,
                criterion="C01.4",
                check="tests",
                state="holds, never broken",
                detail="teeth unchecked",
            ),
        ]
        got = spec_drift.replay_history(self.write({"schema": 1, "rows": rows}))
        self.assertEqual(
            [(c["criterion"], c["state"], c["checks"][0]["state"]) for c in got["cells"]],
            [
                ("C01.1", "holds, never broken", "holds, never broken"),
                ("C01.2", "holds", "holds"),
                ("C01.4", "holds, never broken", "holds, never broken"),
            ],
        )

    def test_cells_in_criterion_order_with_their_checks_and_each_merge_counts_runs_and_copies(self):
        row = {"day": "04", "platform": "windows", "pr": 9, "sample": "all", "merge": "aaa", "n": 5}
        rows = [
            dict(row, criterion="C04.10", check="tests", state="not yet in force", key="k1"),
            dict(row, criterion="C04.2", check="b", state="holds", key="k2"),
            dict(
                row,
                criterion="C04.2",
                check="a",
                state="test weakened",
                detail="passes with it in",
                key="k3",
            ),
            dict(
                row,
                n=6,
                merge="bbb",
                pr=10,
                sample="day",
                criterion="C04.2",
                check="a",
                state="holds",
                key="k4",
                reused_from="aaa",
            ),
            dict(
                row,
                n=6,
                merge="bbb",
                pr=10,
                sample="day",
                criterion="C04.13",
                check="none",
                state="live only",
            ),
        ]
        got = spec_drift.replay_history(self.write({"schema": 1, "rows": rows}))
        self.assertEqual(got["state"], "loaded")
        self.assertEqual(
            [(c["criterion"], c["n"], c["state"], c["mixed"]) for c in got["cells"]],
            [
                ("C04.2", 5, "test weakened", True),
                ("C04.2", 6, "holds", False),
                ("C04.10", 5, "not yet in force", False),
                ("C04.13", 6, "live only", False),
            ],
        )
        self.assertEqual(
            got["cells"][0]["checks"][1],
            {
                "check": "a",
                "state": "test weakened",
                "detail": "passes with it in",
                "platform": "windows",
            },
        )
        self.assertEqual(
            [(m["n"], m["pr"], m["sample"], m["run"], m["copied"]) for m in got["merges"]],
            [(5, 9, "all", 3, 0), (6, 10, "day", 0, 1)],
        )

    def test_a_merge_on_two_platforms_takes_the_check_that_ran_and_counts_one_platform(self):
        row = {"day": "04", "pr": 9, "sample": "all", "merge": "aaa", "n": 5}
        win, lin = dict(row, platform="windows"), dict(row, platform="linux")
        skipped = "not applicable on this platform"
        rows = [
            dict(win, criterion="C04.1", check="posix", state=skipped, key="w1"),
            dict(win, criterion="C04.1", check="b", state="holds", key="w2"),
            dict(win, criterion="C04.2", check="posix", state=skipped, key="w3"),
            dict(win, criterion="C04.3", check="a", state="holds", key="w4"),
            dict(lin, criterion="C04.1", check="posix", state="holds", key="l1"),
            dict(lin, criterion="C04.1", check="b", state="holds", key="l2", reused_from="zzz"),
            dict(lin, criterion="C04.2", check="posix", state="code broken", key="l3"),
        ]
        got = spec_drift.replay_history(self.write({"schema": 1, "rows": rows}))
        self.assertEqual(
            [
                (
                    c["criterion"],
                    c["state"],
                    c["mixed"],
                    sorted(ch["platform"] for ch in c["checks"]),
                )
                for c in got["cells"]
            ],
            [
                ("C04.1", "holds", False, ["linux", "linux", "windows"]),
                ("C04.2", "code broken", False, ["linux"]),
                ("C04.3", "holds", False, ["windows"]),
            ],
        )
        self.assertEqual([(m["n"], m["run"], m["copied"]) for m in got["merges"]], [(5, 2, 1)])
        only_windows = [r for r in rows if r["platform"] == "windows"]
        got = spec_drift.replay_history(self.write({"schema": 1, "rows": only_windows}))
        self.assertEqual([c["state"] for c in got["cells"]], [skipped, skipped, "holds"])
        self.assertEqual([(m["run"], m["copied"]) for m in got["merges"]], [(4, 0)])

    def test_no_file_is_absent_and_one_it_cannot_read_is_invalid(self):
        self.assertEqual(
            spec_drift.replay_history(os.path.join(tempfile.gettempdir(), "no-such-replay.json")),
            {"state": "absent"},
        )
        bad = {
            "day": "04",
            "platform": "windows",
            "sample": "all",
            "merge": "aaa",
            "n": 5,
            "criterion": "C04.1",
            "check": "x",
            "state": "flaky",
        }
        self.assertEqual(
            spec_drift.replay_history(self.write({"schema": 1, "rows": [bad]}))["state"], "invalid"
        )
        self.assertEqual(
            spec_drift.replay_history(self.write({"schema": 2, "rows": []}))["state"], "invalid"
        )


class ProofKindsTest(unittest.TestCase):
    """spec-drift.py's proof_kinds: each criterion once, under its strongest kind."""

    def test_strongest_kind_counts_once(self):
        checks = [
            {"kind": "proof", "proved_by": ["test", "command", "break"]},
            {"kind": "proof", "proved_by": ["command", "break"]},
            {"kind": "proof", "proved_by": ["break"]},
            {"kind": "proof", "proved_by": ["reader"]},
            {"kind": "proof", "proved_by": []},
            {"kind": "proof", "proved_by": None},
            {"kind": "proof"},
            {"kind": "break", "proved_by": ["break"]},
        ]
        self.assertEqual(
            spec_drift.proof_kinds(checks),
            {"test": 1, "command": 1, "break": 1, "reader": 1, "unproved": 2, "not_recorded": 1},
        )

    def test_report_day_gets_its_proof_counts(self):
        report = {
            "schema": spec_drift.EVIDENCE_SCHEMA,
            "generated": "2026-11-07T00:00:00",
            "ref": "main",
            "ref_sha": "abc",
            "runner": {},
            "days": [
                {
                    "spec": {"path": "specs/day-03-x.md"},
                    "checks": [
                        {
                            "id": "a",
                            "kind": "proof",
                            "status": "passed",
                            "proved_by": ["test", "break"],
                        },
                        {"id": "b", "kind": "proof", "status": "passed", "proved_by": ["reader"]},
                    ],
                }
            ],
        }
        days = [{"day": 3, "status": "done", "prs": [], "file": "specs/day-03-x.md"}]
        with tempfile.TemporaryDirectory() as page:
            with open(os.path.join(page, "evidence-checks.json"), "w", encoding="utf-8") as f:
                json.dump(report, f)
            with mock.patch.object(spec_drift, "PAGE", page):
                out = spec_drift.evidence_checks(days, [{"sha": "abc", "pr": None}])
        self.assertEqual(out["state"], "loaded", out.get("diagnostic"))
        proof = out["days"][0]["proof"]
        self.assertEqual((proof["test"], proof["reader"], proof["break"]), (1, 1, 0))
        self.assertEqual(
            [c["proved_by"] for c in out["days"][0]["checks"]], [["test", "break"], ["reader"]]
        )


RELABEL_FULL = {"stage": [7, 15], "cause": [13, 15], "made": [14, 15]}


def run_lines(stage, cause, made):
    return f"stage: {stage} agree\ncause: {cause} agree\nmade: {made} agree\n"


class RelabelCountsTest(unittest.TestCase):
    """The second reader's counts come from what `relabel.py compare` printed into a closing PR."""

    def test_a_pasted_run_is_counted(self):
        body = (
            "Blind relabel:\n\n```\n"
            + run_lines("7 of 15", "13 of 15", "14 of 15")
            + "rater unclear: stage 7\n```\n"
        )
        self.assertEqual(spec_drift.relabel("", [body]), RELABEL_FULL)

    def test_crlf_and_a_not_compared_note_still_count(self):
        body = run_lines("7 of 15", "13 of 15", "14 of 15").replace(
            "agree", "agree (1 untagged, not compared)", 1
        )
        self.assertEqual(spec_drift.relabel("", [body.replace("\n", "\r\n")])["stage"], [7, 15])

    def test_the_last_run_wins(self):
        body = (
            run_lines("14 of 16", "15 of 16", "16 of 16")
            + "then again\n"
            + run_lines("7 of 15", "13 of 15", "14 of 15")
        )
        self.assertEqual(spec_drift.relabel("", [body]), RELABEL_FULL)

    def test_prose_about_an_earlier_run_is_not_a_run(self):
        body = (
            run_lines("7 of 15", "13 of 15", "14 of 15")
            + "The first run gave stage 12 of 16 and cause: 1 of 2.\n"
        )
        self.assertEqual(spec_drift.relabel("", [body]), RELABEL_FULL)

    def test_lines_that_are_not_whole_runs_are_not_counted(self):
        for body in (
            "stage: 1 of 2 agree\ncause: 1 of 2 agree\n",
            run_lines("1 of 2", "1 of 2", "1 of 2") + "stage: 2 of 2 agree\n",
            "cause: 1 of 2 agree\nstage: 1 of 2 agree\nmade: 1 of 2 agree\n",
            run_lines("3 of 2", "1 of 2", "1 of 2"),
            run_lines("0 of 0", "1 of 2", "1 of 2"),
        ):
            with self.subTest(body=body):
                self.assertIsNone(spec_drift.relabel("", [body]))

    def test_an_unclear_body_does_not_fall_back_to_the_notes(self):
        notes = "(`relabel.py compare`): stage 3 of 4, cause 3 of 4, made 4 of 4"
        self.assertIsNone(spec_drift.relabel(notes, ["stage: 1 of 2 agree\n"]))

    def test_two_closing_prs_that_differ_are_not_counted(self):
        one, other = (
            run_lines("7 of 15", "13 of 15", "14 of 15"),
            run_lines("8 of 15", "13 of 15", "14 of 15"),
        )
        self.assertIsNone(spec_drift.relabel("", [one, other]))
        self.assertEqual(spec_drift.relabel("", [one, one, None]), RELABEL_FULL)

    def test_with_no_paste_the_notes_are_still_read(self):
        notes = "(`relabel.py compare`): stage 3 of 4, cause 3 of 4, made 4 of 4"
        self.assertEqual(spec_drift.relabel(notes, ["no counts here", None])["made"], [4, 4])
        self.assertIsNone(spec_drift.relabel("told in prose", ["no counts here"]))

    def test_a_merged_pr_carries_its_link(self):
        pr = {
            "number": 9,
            "state": "MERGED",
            "url": "https://example.test/pull/9",
            "title": "Tooling: x",
            "headRefName": "tooling/x",
            "body": "",
            "createdAt": "2026-11-08T10:00:00Z",
            "mergedAt": "2026-11-08T10:06:00Z",
        }
        self.assertEqual(
            spec_drift.verification({9: pr}, [])[0]["url"], "https://example.test/pull/9"
        )


if __name__ == "__main__":
    unittest.main()
