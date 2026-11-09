"""The dashboard's plots: each is drawn from the page's data, says "not measured" when it has none,
and stays visible with its table collapsed under it. The page tests run dashboard.js and need node.

    python scripts/test_dashboard_plots.py
"""

import html.parser
import os
import pathlib
import re
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_spec_drift import a_day, drawn, page_row  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
ROWS = [page_row(0, None, "origin", 50)]


def draw(**more):
    error, panels, _ = drawn(
        ROWS, **more
    )  # older panels log on data this thin; a plot that fails says so in its box
    assert error is None, error
    return panels


def cell(criterion, state):
    return dict(criterion=criterion, day=criterion[1:3], n=1, state=state, mixed=False, checks=[])


def replay(*cells):
    return dict(state="loaded", states=[], merges=[dict(n=1, pr=7, merge="abc")], cells=list(cells))


def widths(box):
    return re.findall(r'class="stack"[^>]*style="width:([\d.]+)%"', box)


NONE = 'class="not-measured"'


@unittest.skipUnless(shutil.which("node"), "needs node")
class PromisePlotsTest(unittest.TestCase):
    CELLS = (
        cell("C01.1", "holds"),
        cell("C01.2", "holds"),
        cell("C01.3", "holds, never broken"),
        cell("C01.4", "live only"),
        cell("C02.1", "code broken"),
    )

    def test_the_headline_says_how_many_promises_are_proven(self):
        box = draw(replay=replay(*self.CELLS))["plot-all"]
        self.assertIn(
            '<b class="num">2 of 5</b> promises are proven: their test caught a planted bug', box
        )

    def test_the_bar_has_a_segment_per_state_and_labels_only_the_big_ones(self):
        box = draw(replay=replay(*self.CELLS))["plot-all"]
        bar = re.search(r'<div class="promise-bar"[^>]*>(.*?)</div>', box, re.S).group(1)
        parts = re.findall(r'<span class="promise (\w+)" style="flex:(\d+) 0 0"[^>]*>(.*?)</span>', bar)
        self.assertEqual(
            [(state, n) for state, n, _ in parts],
            [("proven", "2"), ("unproven", "1"), ("skipped", "1"), ("broken", "1")],
        )
        # 2 of 5 is over a fifth of the bar and says what it is; 1 of 5 is not, and the key says it.
        self.assertEqual([label for _, _, label in parts], ["<b>2</b><em> proven</em>", "", "", ""])

    def test_the_key_counts_every_state_and_says_what_it_means(self):
        box = draw(replay=replay(*self.CELLS))["plot-all"]
        key = box[box.index('class="promise-states"') :]
        for line in (
            "<b>2</b> proven",
            "<b>1</b> passes, not yet proven",
            "<b>1</b> not checked here",
            "<b>0</b> tests need repair",
            "<b>1</b> broken",
        ):
            self.assertIn(line, key)
        self.assertIn("a bug was planted on purpose and its test caught it", key)
        self.assertEqual(re.findall(r'<i class="promise proven">([^<]*)</i>', key), ["✓"])
        self.assertEqual(re.findall(r'<i class="promise unproven">([^<]*)</i>', key), [""])

    def test_no_recheck_is_not_measured_and_not_an_empty_bar(self):
        panels = draw(replay=dict(state="absent"))
        self.assertIn(NONE, panels["plot-all"])
        self.assertNotIn("promise-bar", panels["plot-all"])


@unittest.skipUnless(shutil.which("node"), "needs node")
class TrustHistoryPlotTest(unittest.TestCase):
    """Is trust growing? The five states counted at each re-checked merge, a promise keeping its last state."""

    MERGES = [dict(n=1, pr=7, merge="aaa"), dict(n=2, pr=8, merge="bbb"), dict(n=3, pr=None, merge="ccc")]

    @staticmethod
    def at(criterion, n, state):
        return dict(cell(criterion, state), n=n)

    def draw(self, cells, **more):
        data = dict(state="loaded", states=[], merges=self.MERGES, cells=cells)
        return draw(replay=data, **more)

    def cells(self):
        return [
            self.at("C01.1", 1, "holds"),
            self.at("C01.2", 1, "holds, never broken"),
            self.at("C01.2", 2, "holds"),  # C01.1 is not re-checked at the second merge
            self.at("C02.1", 2, "not yet in force"),
            self.at("C01.1", 3, "break no longer applies"),
            self.at("C02.1", 3, "holds"),
        ]

    @staticmethod
    def rows(table):
        return [re.findall(r"<td[^>]*>([^<]*)</td>", row) for row in re.findall(r"<tr>(.*?)</tr>", table)][1:]

    def test_a_promise_keeps_its_last_state_until_it_is_checked_again(self):
        table = self.draw(self.cells())["history-table"]
        self.assertEqual(
            self.rows(table),
            [["#7", "1", "1", "0", "0", "0", "2"], ["#8", "2", "0", "0", "0", "0", "2"], ["ccc", "2", "0", "0", "1", "0", "3"]],
        )

    def test_a_replaced_promise_is_left_out_of_every_merge(self):
        index = [dict(id="C01.2", day=1, tag="hold", claim="x", spec="s.md", track="A", prs=[3], tests=[], cited=True,
                      test_found=None, seen_red=dict(state=False, lines=[]), replaces=[], replaced_by=["C09.1"],
                      replay=dict(state="current", status=None, why=[], checks=[]))]
        table = self.draw(self.cells(), criteria_index=index)["history-table"]
        self.assertEqual([row[1:] for row in self.rows(table)][:2], [["1", "0", "0", "0", "0", "1"]] * 2)

    def test_one_stepped_area_per_state_that_was_ever_seen(self):
        box = self.draw(self.cells())["plot-history"]
        self.assertEqual(re.findall(r'<path d="[^"]+" class="area ([\w-]+)"', box), ["s-proven", "s-unproven", "s-repair"])
        proven = re.search(r'<path d="([^"]+)" class="area s-proven"', box).group(1)
        self.assertNotIn("L", proven)  # steps, not slopes: a count holds until the next re-check
        self.assertIn("3 re-checked changes", box)

    def test_the_latest_counts_are_written_beside_the_plot(self):
        box = self.draw(self.cells())["plot-history"]
        labels = re.findall(r'<text[^>]*class="strong"[^>]*>([^<]+)</text>', box)
        self.assertEqual(labels, ["2 proven", "0 pass, not yet proven", "1 test needs repair"])

    def test_no_recheck_is_not_measured(self):
        panels = draw(replay=dict(state="absent"))
        self.assertIn(NONE, panels["plot-history"])
        self.assertNotIn("<path", panels["plot-history"])


@unittest.skipUnless(shutil.which("node"), "needs node")
class TestGroupsPlotTest(unittest.TestCase):
    INVENTORY = dict(
        total=120,
        unreadable=[],
        groups=[
            dict(key="a", label="Driver", when="Every push and pull request", files=1, tests=100),
            dict(key="b", label="Live", when="By hand only: skipped in CI", files=1, tests=20),
        ],
    )

    def test_one_bar_per_group_with_its_count_and_when_it_runs(self):
        box = draw(test_inventory=self.INVENTORY)["plot-groups"]
        rows = re.findall(
            r'<div class="inv-row"><span class="plot-name">(.*?)</span><span class="inv-bar">'
            r'<i [^>]*style="width:([\d.]+)%"></i><b class="num">(\d+)</b>'
            r'<span class="(when[^"]*)">(.*?)</span>',
            box,
        )
        self.assertEqual(
            rows,
            [
                ("Driver", "62", "100", "when", "Every push and pull request"),
                ("Live", "12.4", "20", "when by-hand", "By hand only"),
            ],
        )
        self.assertNotIn("skipped in CI", re.sub(r'(title|aria-label)="[^"]*"', "", box))

    def test_the_headline_counts_the_tests_no_person_has_to_run(self):
        box = draw(test_inventory=self.INVENTORY)["plot-groups"]
        self.assertIn(
            '<b class="num">100 of 120</b> tests run without a person; 20 are run by hand</p>', box
        )
        no_hand = dict(self.INVENTORY, groups=self.INVENTORY["groups"][:1])
        self.assertIn(
            '<b class="num">100 of 100</b> tests run without a person</p>',
            draw(test_inventory=no_hand)["plot-groups"],
        )

    def test_no_inventory_is_not_measured(self):
        self.assertIn(NONE, draw(test_inventory=None)["plot-groups"])


def evidence_day(n, c_red=True, **more):
    day = dict(
        a_day(n),
        status="done",
        phase=1,
        title="t",
        prs=[],
        evidence_format=True,
        break_format=True,
        evidence=[
            dict(
                id=f"C{n:02d}.1",
                ticked=True,
                prs=[7],
                tests={"A.b": "present"},
                red=c_red,
                claim="c",
            ),
            dict(
                id=f"C{n:02d}.2",
                ticked=True,
                prs=[],
                tests={"Live.c": "skippable"},
                red=False,
                claim="c",
            ),
        ],
    )
    return {**day, **more}


def report_day(n, state="current", failed=0):
    return dict(
        day=n,
        state=state,
        why=["inputs changed"] if state == "stale" else [],
        problems=[],
        counts=dict(named_test=dict(passed=3, failed=failed, error=0, not_applicable=0)),
    )


def report(*days):
    return dict(
        state="loaded",
        generated="2026-01-01T00:00",
        ref="main",
        ref_sha="abc",
        runner={},
        days=list(days),
    )


@unittest.skipUnless(shutil.which("node"), "needs node")
class EvidencePlotTest(unittest.TestCase):
    PROOF = dict(test=3, command=1, reader=0, unproved=0, not_recorded=0, **{"break": 0})

    def cells(self, box):
        """The checklist's rows, each a list of its cells' HTML."""
        return [
            re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row)
            for row in re.findall(r"<tr[^>]*>(.*?)</tr>", box)
        ]

    def table(self, box):
        """The same rows with the tags dropped: what each cell says."""
        return [[re.sub(r"<[^>]+>", "", c) for c in row] for row in self.cells(box)]

    def test_one_row_per_finished_day_one_column_per_fact_and_a_row_that_adds_them_up(self):
        box = draw(
            days=[evidence_day(1), evidence_day(2, False)],
            order=[1, 2],
            evidence_checks=report(report_day(1), report_day(2)),
        )["plot-evidence"]
        head, one, two, total = self.table(box)
        self.assertEqual(
            head,
            [
                "Day",
                "Cites its pull request",
                "Names a test",
                "Failure recordedwhen it was built",
                "Strongest evidenceon record",
                "Replays today",
            ],
        )
        self.assertTrue(one[0].startswith("Day 01"), one[0])
        self.assertEqual(one[1:4], ["1 of 2", "all 2", "1 of 2"])
        self.assertEqual(two[1:4], ["1 of 2", "all 2", "0 of 2"])
        self.assertEqual(total[:4], ["All finished days", "2 of 4", "all 4", "1 of 4"])
        self.assertEqual(total[5], "2 of 2 days")

    def test_a_whole_cell_is_quiet_and_a_gap_draws_a_meter(self):
        box = draw(days=[evidence_day(1)], order=[1])["plot-evidence"]
        self.assertIn('<td><span class="whole num">all 2</span></td>', box)
        self.assertIn(
            '<span class="gap-meter" role="img" aria-label="1 of 2"><i style="width:50%"></i></span>1 of 2',
            box,
        )
        self.assertNotIn("<button", box)

    def test_replay_is_quiet_unless_it_failed_or_is_stale(self):
        days = [evidence_day(n) for n in (1, 2, 3, 4)]
        box = draw(
            days=days,
            order=[1, 2, 3, 4],
            evidence_checks=report(
                report_day(1), report_day(2, failed=2), report_day(3, state="stale")
            ),
        )["plot-evidence"]
        status = [row[-1] for row in self.cells(box)[1:]]
        self.assertEqual(
            status[0],
            '<span class="whole" title="3 named tests found; 0 Verify commands and 0 breaks re-run">none failed</span>',
        )
        self.assertIn('class="plot-bad"', status[1])
        self.assertIn(">2 failed<", status[1])
        self.assertIn('class="plot-bad"', status[2])
        self.assertIn("stale", status[2])
        self.assertIn(NONE, status[3])
        self.assertIn("not checked", status[3])
        self.assertIn('aria-label="1 of 4"', status[4])
        self.assertIn("1 of 4 days", status[4])

    def counted_day(self):
        n = lambda p: dict(passed=p, failed=0, error=0, not_applicable=0)  # noqa: E731
        return report(
            dict(
                day=1,
                state="current",
                why=[],
                problems=[],
                counts=dict(named_test=n(3), verify=n(2), proof=n(5), **{"break": n(1)}),
            )
        )

    def test_a_named_test_looked_up_is_not_counted_as_re_run(self):
        box = draw(days=[evidence_day(1)], order=[1], evidence_checks=self.counted_day())[
            "plot-evidence"
        ]
        self.assertIn(
            'title="3 named tests found; 2 Verify commands and 1 break re-run">none failed', box
        )

    def test_the_collapsed_column_says_found_only_for_named_tests(self):
        box = draw(days=[evidence_day(1)], order=[1], evidence_checks=self.counted_day())[
            "evidence-checks"
        ]
        self.assertIn(">3/3 found</td>", box)
        self.assertIn(">2/2 passed</td>", box)
        self.assertIn(">1/1 passed</td>", box)
        self.assertNotIn("3/3 passed", box)

    def test_no_report_is_never_drawn_as_a_pass(self):
        box = draw(days=[evidence_day(1)], order=[1], evidence_checks=dict(state="absent"))[
            "plot-evidence"
        ]
        day, total = self.table(box)[1:]
        self.assertEqual((day[4], day[5]), ("no report", "no report"))
        self.assertEqual((total[4], total[5]), ("no report", "no report"))
        self.assertNotIn("none failed", box)
        self.assertNotIn('class="whole">', box)

    def test_a_day_written_before_a_fact_was_asked_for_is_not_measured_and_not_added_up(self):
        days = [evidence_day(1, False, break_format=False, evidence_format=False), evidence_day(2)]
        old, new, total = self.table(draw(days=days, order=[1, 2])["plot-evidence"])[1:]
        self.assertEqual(old[1:4], ["not measured"] * 3)
        self.assertEqual(new[1:4], ["1 of 2", "all 2", "1 of 2"])
        self.assertEqual(total[1:4], ["1 of 2", "all 2", "1 of 2"])

    def test_strongest_evidence_is_the_reports_count_of_each_kind(self):
        gap = dict(self.PROOF, test=1, command=0, unproved=1)
        box = draw(
            days=[evidence_day(n) for n in (1, 2, 3)],
            order=[1, 2, 3],
            evidence_checks=report(
                dict(report_day(1), proof=self.PROOF), dict(report_day(2), proof=gap), report_day(3)
            ),
        )["plot-evidence"]
        self.assertEqual(
            [row[4] for row in self.table(box)[1:]],
            [
                "3 tests · 1 command",
                "1 test · 1 with nothing on record",
                "not checked",
                "4 tests · 1 command · 1 with nothing on record",
            ],
        )

    def test_skipped_live_tests_are_one_line(self):
        skip = draw(days=[evidence_day(1)], order=[1])["evidence-skip"]
        self.assertEqual(skip, "1 live test needs real Claude; CI skips them, run by hand.")

    def test_no_finished_day_is_not_measured(self):
        panels = draw()
        self.assertIn(NONE, panels["plot-evidence"])
        self.assertIn(NONE, panels["plot-recorded"])


@unittest.skipUnless(shutil.which("node"), "needs node")
class RecordedLinePlotTest(unittest.TestCase):
    """The line over the checklist: the share of a day's ticked promises with a failure recorded when built."""

    def line(self, *days):
        box = draw(days=list(days), order=[d["day"] for d in days])["plot-recorded"]
        runs = [
            [tuple(map(float, p.split(","))) for p in points.split()]
            for points in re.findall(r'<polyline points="([^"]+)" class="trend">', box)
        ]
        return box, runs

    def test_a_point_per_day_at_its_share_with_the_count_written_on_it(self):
        box, runs = self.line(evidence_day(1), evidence_day(2, False), evidence_day(3))
        self.assertEqual(
            re.findall(r'class="strong num">([^<]+)</text>', box), ["1 of 2", "0 of 2", "1 of 2"]
        )
        self.assertEqual(len(runs), 1)
        (x1, half), (x2, zero), (x3, again) = runs[0]
        self.assertEqual(half, again)
        self.assertGreater(zero, half)  # lower on the page
        self.assertAlmostEqual(x2 - x1, x3 - x2, delta=0.2)
        self.assertEqual(re.findall(r'class="num">(Day \d+)</text>', box), ["Day 01", "Day 02", "Day 03"])

    def test_a_day_that_was_not_asked_for_it_breaks_the_line_and_is_not_a_zero(self):
        days = [evidence_day(n) for n in (1, 2, 3, 4)]
        days[1] = evidence_day(2, False, break_format=False)
        box, runs = self.line(*days)
        self.assertEqual([len(r) for r in runs], [2])
        self.assertEqual(box.count("<circle"), 3)
        self.assertEqual(re.findall(r'class="none">([^<]+)</text>', box), ["not measured"])
        self.assertNotIn("0 of 2", box.split("</svg>")[0].split('">', 1)[1])

    def test_no_day_asked_for_it_is_not_measured(self):
        box, runs = self.line(evidence_day(1, False, break_format=False))
        self.assertIn(NONE, box)
        self.assertEqual(runs, [])


def pr(number, hours=None, failed_in=(), step="code", url=None):
    out = dict(
        number=number,
        kind="code",
        step=step,
        breaks="recorded",
        pushes=1,
        failed=1 if failed_in else 0,
        failed_in=list(failed_in),
    )
    if hours is not None:
        out["hours"] = hours
    if url:
        out["url"] = url
    return out


@unittest.skipUnless(shutil.which("node"), "needs node")
class CiPlotTest(unittest.TestCase):
    def test_bars_by_workflow_longest_first(self):
        box = draw(
            verification=[
                pr(1, failed_in=["Tests"]),
                pr(2, failed_in=["Checks"]),
                pr(3, failed_in=["Checks"]),
            ]
        )["plot-ci"]
        self.assertEqual(re.findall(r'plot-name">([^<]+)<', box), ["Checks", "Tests"])
        self.assertEqual(widths(box), ["100", "50"])
        self.assertEqual(box.count('<i class="ci-failed"'), 2)

    def test_says_so_when_the_bars_add_up_to_more_than_the_prs(self):
        box = draw(verification=[pr(1, failed_in=["Tests", "Checks"])])["plot-ci"]
        self.assertIn("The bars add up to 2, more than the 1 pull requests", box)
        box = draw(verification=[pr(1, failed_in=["Tests"])])["plot-ci"]
        self.assertNotIn("add up to", box)

    def test_nothing_failed_is_said_and_no_prs_is_not_measured(self):
        self.assertIn("CI failed on no merged pull request", draw(verification=[pr(1)])["plot-ci"])
        self.assertIn(NONE, draw(verification=[])["plot-ci"])


@unittest.skipUnless(shutil.which("node"), "needs node")
class OpenTimesPlotTest(unittest.TestCase):
    PRS = [
        pr(1, 1 / 60, url="https://x/1"),
        pr(2, 10 / 60, ["Tests"]),
        pr(3, 100 / 60, step="spec"),
    ]

    def marks(self, box):
        """Where each pull request's mark sits: a circle's centre, or the centre a diamond is turned about."""
        found = re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="4" class="pr"><title>#(\d+)', box)
        found += re.findall(
            r'transform="rotate\(45 ([\d.]+) ([\d.]+)\)" class="pr failed"><title>#(\d+)', box
        )
        return {int(n): (float(x), float(y)) for x, y, n in found}

    def test_marks_sit_on_a_log_axis_labelled_in_minutes_and_hours(self):
        box = draw(verification=self.PRS)["plot-open"]
        at = self.marks(box)
        self.assertEqual(sorted(at), [1, 2, 3])
        self.assertAlmostEqual(at[2][0] - at[1][0], at[3][0] - at[2][0], delta=0.3)
        self.assertGreater(at[2][0], at[1][0])
        self.assertEqual(
            re.findall(r'class="num tick">([^<]+)</text>', box),
            ["1 min", "5 min", "10 min", "30 min", "1 h", "2 h"],
        )

    def test_marks_at_the_same_time_do_not_cover_each_other(self):
        at = self.marks(draw(verification=[pr(n, 3 / 60) for n in range(1, 13)])["plot-open"])
        self.assertEqual(len(at), 12)
        self.assertEqual(len({x for x, _ in at.values()}), 1)
        gaps = [
            ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
            for i, a in at.items()
            for j, b in at.items()
            if i < j
        ]
        self.assertGreaterEqual(min(gaps), 9.4)

    def test_a_mark_links_to_its_pr_and_one_with_no_link_is_still_drawn(self):
        box = draw(verification=self.PRS)["plot-open"]
        self.assertRegex(box, r'<a href="https://x/1" aria-label="#1 · 1 min"><circle')
        self.assertEqual(box.count("<a "), 1)
        self.assertRegex(box, r'class="pr failed"><title>#2 · 10 min · CI failed on it first</title>')

    def test_the_median_is_marked_per_step_and_speed_is_never_green(self):
        panels = draw(verification=self.PRS)
        box = panels["plot-open"]
        self.assertEqual(box.count('class="median"'), 2)
        self.assertEqual(re.findall(r">(median [^<]+)</text>", box), ["median 1.7 h", "median 6 min"])
        self.assertIn("CI failed on it first", panels["open-key"])
        self.assertNotRegex(box + panels["open-key"], r"--close|--r-|--s-|proven")

    def test_no_times_is_not_measured(self):
        panels = draw(verification=[pr(1)])
        self.assertIn(NONE, panels["plot-open"])
        self.assertEqual(panels["open-key"], "")


@unittest.skipUnless(shutil.which("node"), "needs node")
class RepeatsPlotTest(unittest.TestCase):
    REC = dict(
        with_id=9,
        problems=[],
        recurrences=[
            dict(id="D02.1", same_as="D01.1"),
            dict(id="D03.1", same_as="D02.1"),
            dict(id="D03.2", same_as="D03.1"),
            dict(id="D05.2", same_as="D05.1"),
        ],
    )

    def lanes(self):
        box = draw(defect_recurrence=self.REC)["plot-repeats"]
        return box, re.findall(r'<div class="lane">(.*?)</div>', box)

    def test_links_are_followed_to_one_lane_per_problem(self):
        box, lanes = self.lanes()
        self.assertEqual(
            [re.findall(r'lane-name num">(D\d+\.\d+)<small>([^<]+)<', lane) for lane in lanes],
            [[("D01.1", "4 records, 3 days")], [("D05.1", "2 records, one day")]],
        )
        self.assertEqual(
            [re.findall(r'title="([^"]+)">(\d+)</i>', lane) for lane in lanes],
            [[("D01.1", "1"), ("D02.1", "1"), ("D03.1, D03.2", "2")], [("D05.1, D05.2", "2")]],
        )

    def test_every_day_from_the_first_to_the_last_has_a_column(self):
        box, lanes = self.lanes()
        self.assertEqual(
            re.findall(r"<span>(Day \d+)</span>", box), [f"Day 0{n}" for n in (1, 2, 3, 4, 5)]
        )
        self.assertIn('style="--n:5"', box)
        # The first problem's line runs from Day 01 to Day 03; a problem seen on one day has none.
        self.assertIn('<span class="lane-line" style="grid-column:2 / 5;--span:3"></span>', lanes[0])
        self.assertNotIn("lane-line", lanes[1])
        self.assertEqual(
            re.findall(r'lane-day" style="grid-column:(\d)"><i', lanes[1]), ["6"]
        )

    def test_a_first_record_alone_on_its_day_is_drawn_hollow(self):
        box, lanes = self.lanes()
        self.assertEqual(lanes[0].count('class="lane-dot num first"'), 1)
        self.assertRegex(lanes[0], r'class="lane-dot num first"[^>]*title="D01.1">1</i>')
        self.assertNotIn("first", lanes[1])

    def test_same_day_repeats_are_told_apart(self):
        box, _ = self.lanes()
        self.assertIn(
            "<b>4 repeats</b> of <b>2 problems</b>: <b>2</b> on a later day, <b>2</b> within the same day",
            box,
        )

    def test_no_repeats_and_no_data_are_different(self):
        self.assertIn(
            "No problem has been recorded",
            draw(defect_recurrence=dict(with_id=1, problems=[], recurrences=[]))["plot-repeats"],
        )
        self.assertIn(NONE, draw(defect_recurrence=None)["plot-repeats"])


@unittest.skipUnless(shutil.which("node"), "needs node")
class ReaderTablePlotTest(unittest.TestCase):
    """The second reader: a row per day, a column per question, a cell shaded by the share that differed."""

    SOME = dict(stage=[7, 15], cause=[13, 15], made=[14, 15])
    ALL = dict(stage=[5, 5], cause=[5, 5], made=[5, 5])

    def box(self, *relabels):
        days = [evidence_day(n + 1, relabel=r) for n, r in enumerate(relabels)]
        return draw(days=days, order=[d["day"] for d in days])["relabel-plot"]

    def test_a_cell_says_how_many_agreed_and_darkens_with_the_share_that_differed(self):
        cells = re.findall(
            r'<div class="reader-cell num" style="--d:(\d+)" title="([^"]+)"><span>([^<]+)</span><span>([^<]+)</span>',
            self.box(self.SOME, self.ALL),
        )
        self.assertEqual(
            cells[:3],
            [
                ("70", "8 of 15 labels differ", "7 of 15", "47%"),
                ("19", "2 of 15 labels differ", "13 of 15", "87%"),
                ("9", "1 of 15 labels differ", "14 of 15", "93%"),
            ],
        )
        self.assertEqual(cells[3:], [("0", "0 of 5 labels differ", "5 of 5", "100%")] * 3)

    def test_each_question_is_added_up_in_its_heading(self):
        heads = re.findall(
            r'<th scope="col"><b class="num">(\d+)%</b>([^<]+)<small class="num">([^<]+)</small></th>',
            self.box(self.SOME, self.ALL),
        )
        self.assertEqual(
            heads,
            [
                ("60", "When it was found", "12 of 20 agree"),
                ("90", "Why it happened", "18 of 20 agree"),
                ("95", "Which day made it", "19 of 20 agree"),
            ],
        )

    def test_a_day_with_no_count_is_not_counted_and_not_drawn_as_agreeing(self):
        box = self.box(self.SOME, None)
        self.assertIn(
            '<th scope="row" class="num">Day 02</th><td colspan="3"><span class="not-measured">not counted</span></td>',
            box,
        )
        self.assertEqual(box.count("reader-cell"), 3)
        self.assertIn(NONE, self.box(None))

    def test_differing_wears_no_alarm_colour(self):
        self.assertNotRegex(self.box(self.SOME), r"--s-|--r-|--close|--fail|plot-bad")


def tokens(day, date="2026-01-01", model="claude-opus-5-5", output=100, cache_read=300, **more):
    return dict(
        date=date,
        day=day,
        model=model,
        agent="main",
        input=0,
        cache_write=0,
        cache_read=cache_read,
        output=output,
        replies=2,
        **more,
    )


@unittest.skipUnless(shutil.which("node"), "needs node")
class TokenPlotsTest(unittest.TestCase):
    ROWS = [
        tokens(None, cache_read=300),
        tokens(1, cache_read=100),
        tokens(1, model="claude-haiku-5-5", output=300),
        tokens(2, output=200, cache_read=0),
    ]

    def test_between_days_against_days_on_context(self):
        box = draw(tokens=self.ROWS)["plot-context"]
        self.assertIn("<b>42.9%</b> of the context read was between days", box)
        self.assertIn("Between days (300)", box)
        self.assertIn("During days (400)", box)
        self.assertIn('<b class="num">88</b> tokens of context', box)

    def test_each_day_is_split_by_model_and_between_days_is_not_a_row(self):
        box = draw(tokens=self.ROWS)["plot-days"]
        self.assertEqual(re.findall(r'plot-name">([^<]+)<', box), ["Day 01", "Day 02"])
        self.assertEqual(widths(box), ["100", "50"])
        self.assertIn("background:var(--m-haiku)", box)
        self.assertIn("background:var(--m-opus)", box)

    def test_output_by_date_keeps_fewer_date_labels_at_phone_width(self):
        many = [tokens(1, date=f"2026-01-{d:02d}") for d in range(1, 10)]
        box = draw(tokens=many)["token-bars"]
        self.assertEqual(box.count("tk-date"), 9)
        self.assertEqual(box.count("tk-skip"), 4)
        self.assertRegex(box, r'class="num tk-date">01-09<')
        self.assertEqual(draw(tokens=many[:3])["token-bars"].count("tk-skip"), 0)
        css = (HERE / ".." / "docs" / "dashboard" / "dashboard.css").read_text(encoding="utf-8")
        self.assertIn("#token-bars .tk-skip, #token-bars .tk-ctx { display: none; }", css)

    def test_no_tokens_is_not_measured(self):
        panels = draw(tokens=[])
        self.assertIn(NONE, panels["plot-context"])
        self.assertIn(NONE, panels["plot-days"])


def gate(name, defects, found="x", refused=None, **causes):
    return dict(
        gate=name,
        found=found,
        defects=defects,
        refused=refused,
        causes=dict(dict(spec=0, implementation=0, process=0, environment=0, other=0), **causes),
        runs=1,
        replies=1,
        context=1,
        output=1,
        cost=10.0,
    )


@unittest.skipUnless(shutil.which("node"), "needs node")
class GatePlotTest(unittest.TestCase):
    GATES = dict(
        defects=4,
        elsewhere=0,
        gates=[
            gate("small", 1, implementation=1),
            gate("big", 4, spec=3, process=1),
            gate("hooks", None, found=None, refused=9),
        ],
    )

    def test_each_gate_is_split_by_cause_in_the_data_order(self):
        box = draw(gate_report=self.GATES)["plot-gates"]
        self.assertEqual(re.findall(r'plot-name">([^<]+)<', box), ["small", "big", "hooks"])
        self.assertEqual(widths(box)[:2], ["25", "100"])
        self.assertIn("background:var(--c-spec)", box)
        self.assertIn('title="3 spec, 1 process"', box)

    def test_hooks_sit_apart_because_a_refusal_is_not_a_defect(self):
        box = draw(gate_report=self.GATES)["plot-gates"]
        apart = box.index("a refusal is not a defect")
        self.assertLess(box.index(">big<"), apart)
        self.assertLess(apart, box.index(">hooks<"))
        self.assertIn("9 refused", box[apart:])

    def test_cost_per_catch_is_a_quiet_number_not_a_bar(self):
        box = draw(gate_report=self.GATES)["plot-gates"]
        self.assertIn("<small>$2.50 each</small>", box)
        self.assertEqual(len(re.findall(r'class="stack"', box)), 3)

    def test_no_report_is_not_measured(self):
        self.assertIn(NONE, draw(gate_report=None)["plot-gates"])


@unittest.skipUnless(shutil.which("node"), "needs node")
class HookPlotsTest(unittest.TestCase):
    ROWS = [
        tokens(1, date="2026-01-01", bash=10, cut=0, reads=5, whole=2),
        tokens(1, date="2026-01-02", bash=10, cut=1, reads=10, whole=4),
        tokens(1, date="2026-01-03", bash=20, cut=4, reads=8, whole=3),
    ]
    REFUSED = [
        dict(date="2026-01-02", guard="read-guard", refused=3),
        dict(date="2026-01-03", guard="step-guard", refused=5),
    ]

    def test_the_line_is_the_share_cut_on_each_date(self):
        box = draw(tokens=self.ROWS, refusals=self.REFUSED)["plot-cut"]
        self.assertIn('points="0,100 50,50 100,0"', box)
        self.assertEqual(
            re.findall(r'class="num" style="[^"]*">([\d.]+%)<', box), ["0.0%", "20.0%"]
        )
        self.assertIn('title="2026-01-02: 1 of 10 cut"', box)

    def test_a_refused_read_is_not_counted_as_allowed(self):
        box = draw(tokens=self.ROWS, refusals=self.REFUSED)["plot-reads"]
        self.assertIn('title="2026-01-02: 3 refused, 7 allowed"', box)
        self.assertRegex(
            box,
            r'<i class="n-strong" style="flex:7 1 0"></i><i class="n-hollow" style="flex:3 1 0"></i>',
        )

    def test_only_the_read_guard_counts_on_the_read_plot(self):
        box = draw(tokens=self.ROWS, refusals=self.REFUSED)["plot-reads"]
        self.assertIn('title="2026-01-03: 0 refused, 8 allowed"', box)

    def test_a_date_before_the_refusal_log_is_not_a_zero(self):
        box = draw(tokens=self.ROWS, refusals=self.REFUSED)["plot-reads"]
        first = box[box.index(">01-01<") : box.index(">01-02<")]
        self.assertIn(NONE, first)
        self.assertNotIn("0 of", first)
        self.assertIn(NONE, draw(tokens=self.ROWS, refusals=[])["plot-reads"])

    def test_no_counts_are_not_measured(self):
        panels = draw(tokens=[], refusals=[])
        self.assertIn(NONE, panels["plot-cut"])
        self.assertIn(NONE, panels["plot-reads"])


ABILITIES = [
    dict(key="rehearse", name="Shows what it would do", role="rung"),
    dict(key="stop", name="Can be stopped", role="rung"),
    dict(key="loop", name="Works through the night", role="rung"),
    dict(key="see", name="Shows what still works", role="rail"),
]


def story(number, ability, day=None):
    return dict(number=number, title=f"Change {number}", url="u", day=day, ability=ability)


def ladder(*stories, days=()):
    """The ladder's and the night's boxes for these stories; `days` are (day, status) pairs."""
    panels = draw(
        user_stories=dict(abilities=ABILITIES, stories=list(stories), problems=[]),
        days=[dict(a_day(n), status=status) for n, status in days],
    )
    return panels["plot-ladder"], panels["plot-night"]


def rung(box, name):
    """One step's HTML: from its label to the next step's, or the end of the ladder."""
    return box.split(f"<b>{name}</b>")[1].split('<div class="rung ')[0].split('<div class="inline-detail')[0]


@unittest.skipUnless(shutil.which("node"), "needs node")
class LadderPlotTest(unittest.TestCase):
    STORIES = (
        story(1, "rehearse", 1),
        story(2, "rehearse", 1),
        story(3, "rehearse"),
        story(4, "stop", 1),
        story(5, "stop", 2),
        story(6, "see"),
    )
    DAYS = ((1, "done"), (2, "active"))

    def test_a_dot_per_story_on_the_step_its_ability_names(self):
        box, _ = ladder(*self.STORIES, days=self.DAYS)
        built = rung(box, "Shows what it would do")
        self.assertEqual(built.count('class="mini-tile story"'), 3)
        self.assertIn(">3 stories</button><span>Day 1</span>", built)
        self.assertIn('title="#3 Change 3"', built)
        stopping = rung(box, "Can be stopped")
        self.assertEqual(stopping.count('class="mini-tile story"'), 2)
        self.assertIn(">2 stories</button><span>Days 1, 2</span>", stopping)
        self.assertIn('aria-controls="stories-see">1 story</button> · Shows what still works</span>', box)
        self.assertEqual(box.count('class="mini-tile story"'), 7)

    def test_a_step_is_still_being_built_while_a_day_that_added_to_it_is_open(self):
        box, _ = ladder(*self.STORIES, days=self.DAYS)
        self.assertIn('<div class="rung built" style="--i:1">', box)
        self.assertIn('<div class="rung open" style="--i:2">', box)
        self.assertIn("<span>Day 2 still open</span>", rung(box, "Can be stopped"))
        self.assertNotIn("still open", rung(box, "Shows what it would do"))
        box, _ = ladder(*self.STORIES, days=((1, "done"), (2, "done")))
        self.assertNotIn("rung open", box)
        self.assertIn("<b>2 of 3</b> steps reached</p>", box)

    def test_you_are_here_is_the_highest_step_with_a_story(self):
        box, _ = ladder(*self.STORIES, days=self.DAYS)
        self.assertEqual(box.count("You are here"), 1)
        self.assertIn("You are here", rung(box, "Can be stopped"))
        self.assertIn('<div class="rung none" style="--i:3">', box)
        self.assertIn("<span>Not started</span>", rung(box, "Works through the night"))
        self.assertNotIn("mini-tile", rung(box, "Works through the night"))
        self.assertIn("<b>2 of 3</b> steps reached, <b>1</b> still being built", box)
        self.assertIn('<i class="rung-key none"></i><b>Not started</b>', box)

    def test_a_pull_request_that_names_no_ability_is_said_not_drawn(self):
        box, _ = ladder(*self.STORIES, story(7, None), story(8, "nonsense"), days=self.DAYS)
        self.assertIn("2 pull requests named no ability and are not drawn.", box)
        self.assertEqual(box.count('class="mini-tile story"'), 7)
        box, _ = ladder(*self.STORIES, story(7, None), days=self.DAYS)
        self.assertIn("1 pull request named no ability and is not drawn.", box)
        box, _ = ladder(*self.STORIES, days=self.DAYS)
        self.assertNotIn("named no ability", box)

    def test_a_count_opens_the_list_of_that_abilitys_stories(self):
        told = dict(story(4, "stop", 1), story="As a <b>reader</b>, I want x.", date="2026-01-05")
        box, _ = ladder(*self.STORIES[:3], told, *self.STORIES[4:], days=self.DAYS)
        button = '<button type="button" class="story-open" data-stories="stop" aria-expanded="false" aria-controls="stories-stop">2 stories</button>'
        self.assertIn(button, rung(box, "Can be stopped"))
        self.assertEqual(box.count('class="story-open"'), 3)
        self.assertNotIn("story-open", rung(box, "Works through the night"))
        self.assertEqual(box.count('class="inline-detail story-list"'), 3)
        self.assertNotIn('id="stories-loop"', box)
        listed = box.split('id="stories-stop" hidden>')[1].split("</div>")[0]
        self.assertTrue(listed.startswith("<h3>Can be stopped · 2 stories</h3><ol>"), listed)
        self.assertIn(
            '<li><a href="u" target="_blank" rel="noopener">#4</a> As a &lt;b&gt;reader&lt;/b&gt;, I want x.<small>Day 1 · Jan 5</small></li>',
            listed,
        )
        self.assertIn('rel="noopener">#5</a> Change 5<small>Day 2</small></li>', listed)
        self.assertEqual(listed.count("<li>"), 2)
        railed = box.split('id="stories-see" hidden>')[1].split("</div>")[0]
        self.assertIn('rel="noopener">#6</a> Change 6<small>Between days</small></li>', railed)
        self.assertLess(box.index('class="rung-here"'), box.index('id="stories-rehearse"'))

    def test_the_night_marks_each_moment_by_its_step(self):
        _, night = ladder(*self.STORIES, days=self.DAYS)
        self.assertEqual(night.count("<li "), 6)
        self.assertIn('<li class="built"><span class="night-time">21:00</span>', night)
        self.assertIn('<li class="open"><span class="night-time">any time</span>', night)
        self.assertEqual(night.count("<small>Still being built.</small>"), 1)
        self.assertEqual(night.count("<small>Not built yet.</small>"), 4)

    def test_no_stories_is_not_measured_and_old_data_still_draws(self):
        panels = draw()
        self.assertIn(NONE, panels["plot-ladder"])
        self.assertIn(NONE, panels["plot-night"])
        self.assertNotIn("This panel failed", panels["plot-ladder"])
        box, night = ladder(story(1, None))
        self.assertIn(NONE, box)
        self.assertIn(NONE, night)


def grew(*stories, days=()):
    """The grew-by-day box for these stories; `days` are (day, status) pairs."""
    return draw(
        user_stories=dict(abilities=ABILITIES, stories=list(stories), problems=[]),
        days=[dict(a_day(n), status=status) for n, status in days],
    )["plot-grew"]


def grew_row(box, name):
    """One ability's cells: from the end of its row header to the end of its row."""
    return box.split(f'<th scope="row">{name}')[1].split("</th>", 1)[1].split("</tr>")[0]


@unittest.skipUnless(shutil.which("node"), "needs node")
class GrewPlotTest(unittest.TestCase):
    STORIES = LadderPlotTest.STORIES
    DAYS = LadderPlotTest.DAYS

    def test_a_dot_for_each_ability_and_day_sized_by_its_stories(self):
        box = grew(*self.STORIES, days=self.DAYS)
        self.assertIn(
            '<tr><td></td><th scope="col">Day 1</th><th scope="col" class="open">Day 2</th><th scope="col">Between days</th></tr>',
            box,
        )
        self.assertEqual(
            grew_row(box, "Shows what it would do"),
            '<td><i class="grew-dot" style="--d:26.0px" title="Day 1 · Shows what it would do: 2 stories"></i><small>2</small></td>'
            '<td class="open"></td>'
            '<td><i class="grew-dot" style="--d:20.7px" title="Between days · Shows what it would do: 1 story"></i><small>1</small></td>',
        )
        self.assertEqual(grew_row(box, "Works through the night"), '<td></td><td class="open"></td><td></td>')
        self.assertEqual(box.count('class="grew-dot"'), 5)
        self.assertIn("<b>4</b> stories on <b>2</b> days, <b>2</b> between days</p>", box)
        self.assertIn('<table class="grew" style="--n:3">', box)

    def test_an_open_day_is_drawn_open_and_the_key_says_so(self):
        box = grew(*self.STORIES, days=self.DAYS)
        self.assertIn('<td class="open"><i class="grew-dot" style="--d:20.7px"', grew_row(box, "Can be stopped"))
        self.assertIn('<i class="grew-dot key open"></i><b>Its day is not closed</b>', box)
        box = grew(*self.STORIES, days=((1, "done"), (2, "done")))
        self.assertNotIn('class="open"', box)
        self.assertNotIn("Its day is not closed", box)

    def test_a_day_that_added_no_story_keeps_its_column(self):
        box = grew(story(1, "rehearse", 1), story(2, "stop", 3))
        self.assertIn('<th scope="col">Day 1</th><th scope="col">Day 2</th><th scope="col">Day 3</th></tr>', box)
        self.assertNotIn("Between days", box)
        self.assertEqual(
            grew_row(box, "Can be stopped"),
            '<td></td><td></td><td><i class="grew-dot" style="--d:26.0px" title="Day 3 · Can be stopped: 1 story"></i><small>1</small></td>',
        )
        self.assertIn("<b>2</b> stories on <b>2</b> days</p>", box)

    def test_the_railing_rows_are_named_and_a_story_with_no_ability_is_not_counted(self):
        box = grew(*self.STORIES, story(7, None, 1), story(8, "nonsense"), days=self.DAYS)
        self.assertIn('<tr class="rail"><th scope="row">Shows what still works<small>the railing</small></th>', box)
        self.assertEqual(box.count('<tr class="rail">'), 1)
        self.assertIn("<b>4</b> stories on <b>2</b> days, <b>2</b> between days</p>", box)
        box = grew(story(1, "see"))
        self.assertIn('<tr><td></td><th scope="col">Between days</th></tr>', box)
        self.assertIn("<b>0</b> stories on <b>0</b> days, <b>1</b> between days</p>", box)

    def test_no_stories_is_not_measured_and_old_data_still_draws(self):
        self.assertIn(NONE, draw()["plot-grew"])
        self.assertNotIn("This panel failed", draw()["plot-grew"])
        self.assertIn(NONE, grew(story(1, None)))


class PageShape(html.parser.HTMLParser):
    """Where each id sits: the <details> around it, innermost last."""

    def __init__(self):
        super().__init__()
        self.stack, self.where, self.order, self.text = [], {}, [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "details":
            self.stack.append((a.get("class") or "", "open" in a))
        if "id" in a:
            self.where[a["id"]] = list(self.stack)
            self.order.append(a["id"])

    def handle_endtag(self, tag):
        if tag == "details":
            self.stack.pop()

    def handle_data(self, data):
        self.text.append((data, list(self.stack)))


class PageLayoutTest(unittest.TestCase):
    """Every plot is visible by default; its table stays in the page, collapsed under it."""

    PLOTS = (
        "plot-ladder",
        "plot-night",
        "plot-grew",
        "plot-all",
        "plot-history",
        "plot-groups",
        "plot-recorded",
        "plot-evidence",
        "plot-ci",
        "plot-open",
        "relabel-plot",
        "plot-repeats",
        "plot-context",
        "plot-days",
        "plot-gates",
        "plot-cut",
        "plot-reads",
    )
    TABLES = {
        "plot-all": "trust-table",
        "plot-history": "history-table",
        "plot-groups": "test-groups",
        "plot-evidence": "evidence",
        "plot-ci": "ci-fails",
        "plot-open": "merge-time",
        "relabel-plot": "relabel",
        "plot-days": "token-days",
        "plot-gates": "gate-report",
        "plot-reads": "token-hooks",
    }

    @classmethod
    def setUpClass(cls):
        with open(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "..", "docs", "dashboard", "index.html"
            ),
            encoding="utf-8",
        ) as f:
            cls.page = f.read()
        cls.shape = PageShape()
        cls.shape.feed(cls.page)

    def test_every_plot_is_outside_anything_collapsed(self):
        for plot in self.PLOTS:
            closed = [d for d in self.shape.where[plot] if not d[1]]
            self.assertEqual(closed, [], plot)

    def test_each_table_is_collapsed_right_under_its_plot(self):
        for plot, table in self.TABLES.items():
            self.assertEqual(self.shape.where[table][-1], ("exact", False), table)
            self.assertLess(self.shape.order.index(plot), self.shape.order.index(table), table)

    def test_the_promises_are_drawn_once(self):
        for gone in ("plot-features", "replay-legend", "Promises by feature", "Do the promises still hold?"):
            self.assertNotIn(gone, self.page)
        promises = self.page[self.page.index('<section class="panel" id="promises">') :]
        promises = promises[: promises.index("</section>")]
        boxes = ("plot-all", "replay", "promise-days", "promise-key", "trust-table", "plot-history", "history-table", "replay-table")
        at = [promises.find(f'id="{box}"') for box in boxes]
        self.assertNotIn(-1, at)
        self.assertEqual(at, sorted(at))

    def test_the_evidence_is_one_checklist(self):
        for gone in ("proof-kinds", "evidence-headline", "What evidence each criterion has on record", "Select a tile"):
            self.assertNotIn(gone, self.page)
        ticks = self.page[self.page.index('<section class="panel" id="ticks">') :]
        at = [ticks.find(f'id="{box}"') for box in ("plot-recorded", "plot-evidence", "evidence", "evidence-checks")]
        self.assertNotIn(-1, at)
        self.assertEqual(at, sorted(at))

    def test_only_a_promises_state_wears_a_promise_colour(self):
        """In this chapter amber, green, blue and red say what state a promise is in; a count or a mark is neutral."""
        here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "dashboard")
        with open(os.path.join(here, "dashboard.css"), encoding="utf-8") as f:
            css = f.read()
        with open(os.path.join(here, "dashboard.js"), encoding="utf-8") as f:
            script = f.read()
        marks = (".ci-failed", ".swarm .pr", ".swarm .pr.failed", ".swarm .median", ".inv-bar i", ".gap-meter i", ".meter i", ".lane-dot, .legend i.lane-dot", ".lane-line", ".svg-plot .trend", ".svg-plot .pt")
        for mark in marks:
            rule = re.search(r"^" + re.escape(mark) + r" \{([^}]*)\}", css, re.M)
            self.assertIsNotNone(rule, mark)
            self.assertRegex(rule.group(1), r"var\(--(ink|ink-2|muted)\)", mark)
            self.assertNotRegex(rule.group(1), r"--s-|--r-|--close|--code|--spec", mark)
        merges = re.search(r'getElementById\("evidence-history"\).*?\n  \}\);', script, re.S).group(0)
        self.assertNotIn("--close", merges)
        self.assertIn('{ name: "present", color: "var(--ink-2)"', merges)

    def test_what_a_plot_would_mislead_without_stays_visible(self):
        for sentence in (
            "does not establish complete behavioral coverage or current correctness",
            "a gate that finds nothing may still be what kept a defect from being made",
            "An illustration, not a record",
        ):
            around = [stack for data, stack in self.shape.text if sentence in data]
            self.assertTrue(around, sentence)
            self.assertTrue(all(open_ for stack in around for _, open_ in stack), sentence)


if __name__ == "__main__":
    unittest.main()
