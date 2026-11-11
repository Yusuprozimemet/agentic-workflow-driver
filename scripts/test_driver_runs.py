"""driver-runs.py counts the driver's run log into the file the dashboard reads: one row per step,
how it ended, its fix rounds, its crashes and whose each park is.

    python scripts/test_driver_runs.py
"""
import contextlib
import datetime
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("driver_runs", os.path.join(HERE, "driver-runs.py"))
dr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dr)

TRACK_A = "Day 08 Track A: the first track"
TRACK_B = "Day 08 Track B: the second track"
CLOSE = "Day 08: the closing PR"
PARK_LINE = "park: the session parked: a criterion cannot be met as written (session `s1`)"


def at(minute):
    return f"2026-11-12T09:{minute:02d}:00Z"


def start(session, minute, step=TRACK_A, prefix="day-08/track-a"):
    return dict(event="start", at=at(minute), step=step, prefix=prefix, session=session, claude="2.1.312", issue=7)


def end(session, minute, outcome="opened: #12", cost=1.5, denials=0):
    return dict(event="end", at=at(minute), session=session, outcome=outcome, cost_usd=cost, denials=denials)


def fix(session, minute, n=1, pr=12):
    return dict(event="fix", at=at(minute), session=session, pr=pr, n=n)


def merged(minute, pr=12):
    return dict(event="merged", at=at(minute), pr=pr)


def park(minute, line=PARK_LINE, step=TRACK_A):
    return dict(event="park", at=at(minute), step=step, line=line)


class StepsTest(unittest.TestCase):
    def test_a_step_that_merged_with_no_fix_and_no_park_ended_merged(self):
        (step,) = dr.count([start("s1", 0), dict(event="pid", at=at(0), session="s1", pid=41, started=at(0)),
                            end("s1", 20, denials=2), merged(35)])
        self.assertEqual((step["ended"], step["pr"], step["merged"], step["fixes"], step["crashes"], step["parks"]),
                         ("merged", 12, at(35), 0, 0, []))
        self.assertEqual((step["step"], step["day"], step["prefix"]), (TRACK_A, 8, "day-08/track-a"))
        self.assertEqual(step["sessions"], [dict(session="s1", start=at(0), end=at(20), cost=1.5, denials=2,
                                                 fixes=0, crashed=False)])

    def test_fix_rounds_make_it_fixed_and_each_resumes_cost_is_added(self):
        (step,) = dr.count([start("s1", 0), end("s1", 20, cost=1.5), fix("s1", 25), end("s1", 30, cost=0.25),
                            fix("s1", 35, n=2), end("s1", 40, cost=0.5, denials=1), merged(50)])
        self.assertEqual((step["ended"], step["fixes"]), ("fixed", 2))
        self.assertEqual(step["sessions"], [dict(session="s1", start=at(0), end=at(40), cost=2.25, denials=1,
                                                 fixes=2, crashed=False)])

    def test_a_step_with_no_merge_yet_is_open(self):
        (step,) = dr.count([start("s1", 0), end("s1", 20)])
        self.assertEqual((step["ended"], step["pr"], step["merged"]), ("open", 12, None))

    def test_a_park_makes_it_parked_whatever_came_after(self):
        (step,) = dr.count([start("s1", 0), end("s1", 20, outcome=PARK_LINE), park(20),
                            start("s2", 40), end("s2", 50), merged(55)])
        self.assertEqual((step["ended"], step["merged"], len(step["sessions"])), ("parked", at(55), 2))
        self.assertEqual(step["parks"], [dict(at=at(20), line=PARK_LINE, by="maintainer")])

    def test_a_park_before_any_session_is_a_step_and_joins_the_sessions_started_for_it_later(self):
        line = "park: the project's tree is not clean (2 paths)"
        steps = dr.count([park(0, line, CLOSE), start("s1", 30, CLOSE, "day-08/close-the-day"), end("s1", 40)])
        self.assertEqual(len(steps), 1)
        self.assertEqual((steps[0]["prefix"], steps[0]["ended"], steps[0]["parks"][0]["by"], len(steps[0]["sessions"])),
                         ("day-08/close-the-day", "parked", "fault", 1))

    def test_a_park_on_a_sentence_the_driver_does_not_know_is_its_own_step_with_no_day(self):
        line = "park: the next step is not one this driver knows"
        steps = dr.count([start("s1", 0), end("s1", 20), merged(30), park(31, line, "Do something new")])
        self.assertEqual([(s["step"], s["day"], s["prefix"], s["ended"], s["sessions"]) for s in steps[1:]],
                         [("Do something new", None, None, "parked", [])])
        self.assertEqual(steps[1]["parks"][0]["by"], "fault")

    def test_each_step_is_one_row_in_the_logs_order_and_a_merge_goes_to_the_step_that_opened_it(self):
        steps = dr.count([start("s1", 0), end("s1", 10), start("s2", 20, TRACK_B, "day-08/track-b"),
                          end("s2", 30, outcome="opened: #13"), merged(31, pr=13), merged(32, pr=12)])
        self.assertEqual([(s["prefix"], s["pr"], s["merged"]) for s in steps],
                         [("day-08/track-a", 12, at(32)), ("day-08/track-b", 13, at(31))])

    def test_the_merge_of_a_pull_request_no_session_opened_is_no_steps(self):
        steps = dr.count([merged(5, pr=3), start("s1", 10), end("s1", 20)])
        self.assertEqual([(s["pr"], s["merged"]) for s in steps], [(12, None)])


class CrashTest(unittest.TestCase):
    def test_a_session_with_no_end_line_crashed_unless_its_process_lives(self):
        records = [start("s1", 0), start("s2", 30)]
        (step,) = dr.count(records)
        self.assertEqual(([run["crashed"] for run in step["sessions"]], step["crashes"]), ([True, True], 2))
        (step,) = dr.count(records, live="s2")
        self.assertEqual(([run["crashed"] for run in step["sessions"]], step["crashes"]), ([True, False], 1))

    def test_a_session_that_died_in_a_fix_round_crashed_though_it_has_an_earlier_end_line(self):
        (step,) = dr.count([start("s1", 0), end("s1", 20), fix("s1", 25)])
        self.assertEqual((step["sessions"][0]["end"], step["sessions"][0]["crashed"], step["crashes"]), (None, True, 1))


class ByTest(unittest.TestCase):
    """Every park line the driver prints, as driver/ writes them, and whose each is."""

    def test_the_parks_the_plan_keeps_for_the_maintainer(self):
        for line in (PARK_LINE,
                     "park: the end of Phase 1: Day 05 starts Phase 2",
                     "park: a stopping point after Day 08",
                     "park: Day 09 has no spec: writing it is the maintainer's",
                     "park: every day is done",
                     "park: there are no day specs",
                     "park: #12 touches plan.md",
                     "park: #12 touches a human-only path: `.github/workflows/tests.yml`",
                     "park: #12 carries Oversized:",
                     "park: #12 was closed without a merge"):
            self.assertEqual(dr.by(line), "maintainer", line)

    def test_every_other_park_is_a_fault(self):
        for line in ("park: the next step is not one this driver knows",
                     "park: the session ended without a result (exit 1; session `s1`)",
                     "park: the session ended in an error: `error_max_budget_usd` (session `s1`)",
                     "park: the session ended with no pull request and no PARK line (session `s1`)",
                     "park: the step has more than one pull request: #12, #13",
                     "park: the session ran past 90 minutes (session `s1`)",
                     "park: the run log names session `s1` for this step, with no end",
                     "park: the step failed twice: sessions `s1` and `s2`",
                     "park: the run log cannot be read at line 4",
                     "park: the checks on #12 are still red after two fixes: tests",
                     "park: no required checks on #12 after 30 minutes",
                     "park: the evidence run on `4006543` ended `failure`",
                     "park: Track B of Day 08 was announced in #9 and has no branch",
                     "park: the project's tree is not clean (2 paths)",
                     "a line that is no park"):
            self.assertEqual(dr.by(line), "fault", line)


class JunkTest(unittest.TestCase):
    def test_values_of_the_wrong_kind_are_counted_as_nothing(self):
        steps = dr.count([start("s1", 0), end("s1", 10, outcome=None, cost=None, denials=True),
                          dict(event="merged", at=at(11), pr=[12]), dict(event="park", at=at(12), step=["x"], line=None),
                          dict(event="end", at=at(13), session=["s1"]), dict(event="fix", at=at(14), session="s9")])
        self.assertEqual([(s["step"], s["pr"], s["ended"]) for s in steps], [(TRACK_A, None, "open"), ("", None, "parked")])
        self.assertEqual((steps[0]["sessions"][0]["cost"], steps[0]["sessions"][0]["denials"]), (0.0, 0))
        self.assertEqual(steps[1]["parks"], [dict(at=at(12), line="", by="fault")])


class WriteTest(unittest.TestCase):
    NOW = datetime.datetime(2026, 11, 12, 18, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=1)))

    def run_main(self, root, lines, *extra):
        state = os.path.join(root, "state")
        if lines is not None:
            os.makedirs(state)
            with open(os.path.join(state, "run.jsonl"), "wb") as f:
                f.write("".join(lines).encode("utf-8"))
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = dr.main(["--state", state, *extra], now=self.NOW)
        return code, out.getvalue(), err.getvalue()

    def test_the_file_holds_the_moment_of_the_count_and_the_steps(self):
        with tempfile.TemporaryDirectory() as root:
            out = os.path.join(root, "driver-runs.json")
            # merged() gives no "changed"; Level 2 counts a merge only when it says the head did not change.
            records = [start("s1", 0), end("s1", 20), dict(merged(30), changed=False), park(31, step=TRACK_B)]
            lines = [json.dumps(r) + "\n" for r in records]
            code, said, _ = self.run_main(root, lines, "--out", out)
            with open(out, "rb") as f:
                raw = f.read()
        self.assertEqual(code, 0)
        self.assertNotIn(b"\r", raw)
        doc = json.loads(raw)
        # The same moment, on the clock of the machine that counts: its offset is the machine's, not NOW's.
        self.assertEqual(doc["counted"], self.NOW.astimezone().isoformat(timespec="seconds"))
        self.assertEqual(datetime.datetime.fromisoformat(doc["counted"]), self.NOW)
        self.assertEqual(doc["level_2"], {"run": 1, "of": 15})
        self.assertEqual(doc["steps"], dr.count(records))
        self.assertIn("2 steps: 1 merged with no person, 0 after fixing themselves, 1 parked (0 by a fault), 0 open", said)

    def test_project_writes_the_projects_dashboard_file(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "shop", "docs", "dashboard"))
            code, _, _ = self.run_main(root, [json.dumps(start("s1", 0)) + "\n"], "--project", os.path.join(root, "shop"))
            self.assertEqual(code, 0)
            with open(os.path.join(root, "shop", "docs", "dashboard", "driver-runs.json"), encoding="utf-8") as f:
                self.assertEqual(len(json.load(f)["steps"]), 1)

    def test_no_run_log_writes_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            out = os.path.join(root, "driver-runs.json")
            code, said, _ = self.run_main(root, None, "--out", out)
            self.assertEqual((code, os.path.exists(out)), (0, False))
            self.assertIn("no run log; nothing written", said)

    def test_a_torn_run_log_writes_nothing_and_exits_2(self):
        with tempfile.TemporaryDirectory() as root:
            out = os.path.join(root, "driver-runs.json")
            code, _, err = self.run_main(root, [json.dumps(start("s1", 0)) + "\n", '{"event": "end", "at'], "--out", out)
            self.assertEqual((code, os.path.exists(out)), (2, False))
            self.assertIn("the run log cannot be read at line 2; nothing written", err)

    def test_a_project_with_no_dashboard_folder_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            code, _, err = self.run_main(root, [json.dumps(start("s1", 0)) + "\n"], "--project", os.path.join(root, "shop"))
            self.assertEqual(code, 2)
            self.assertIn("its folder does not exist; nothing written", err)


if __name__ == "__main__":
    unittest.main()
