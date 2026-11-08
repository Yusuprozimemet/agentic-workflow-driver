"""The dashboard's plots: each is drawn from the page's data, says "not measured" when it has none,
and stays visible with its table collapsed under it. The page tests run dashboard.js and need node.

    python scripts/test_dashboard_plots.py
"""

import html.parser
import os
import re
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_spec_drift import a_day, drawn, page_row  # noqa: E402

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

    def test_one_bar_for_all_promises_with_the_count_and_the_lag(self):
        box = draw(replay=replay(*self.CELLS))["plot-all"]
        self.assertIn("<b>2 of 5</b> promises caught a planted bug", box)
        self.assertEqual(widths(box), ["100"])
        self.assertIn("Re-checked by hand, so this can be behind the latest change", box)

    def test_no_bug_tried_and_not_checked_look_different(self):
        box = draw(replay=replay(*self.CELLS))["plot-all"]
        for look in ("promise proven", "promise unproven", "promise skipped", "promise broken"):
            self.assertIn(look, box)

    def test_a_feature_bar_is_as_long_as_its_promise_count_in_day_order(self):
        box = draw(replay=replay(*self.CELLS))["plot-features"]
        self.assertEqual(widths(box), ["100", "25"])
        self.assertEqual(re.findall(r'plot-value num">([^<]+)<', box), ["2 of 4", "0 of 1"])

    def test_no_recheck_is_not_measured_and_not_an_empty_bar(self):
        panels = draw(replay=dict(state="absent"))
        self.assertIn(NONE, panels["plot-all"])
        self.assertIn(NONE, panels["plot-features"])


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

    def test_one_plain_bar_per_group_coloured_by_when_it_runs(self):
        box = draw(test_inventory=self.INVENTORY)["plot-groups"]
        self.assertEqual(widths(box), ["100", "20"])
        self.assertIn('<i class="n-strong"', box)
        self.assertIn('<i class="n-hollow"', box)
        self.assertIn("<b>By hand only</b>", box)
        self.assertNotIn("skipped in CI", re.sub(r'(title|aria-label)="[^"]*"', "", box))

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
    def rows(self, box):
        return re.findall(
            r'<div class="ev-row"><span class="plot-name">(.*?)</span>.*?<span class="ev-status">(.*?)</span></div>',
            box,
        )

    def test_a_tile_per_ticked_promise_that_opens_its_detail(self):
        box = draw(days=[evidence_day(1)], order=[1], evidence_checks=report(report_day(1)))[
            "plot-evidence"
        ]
        self.assertIn('<button type="button" class="ev-tile rec-yes" data-id="C01.1"', box)
        self.assertIn('<button type="button" class="ev-tile rec-no" data-id="C01.2"', box)

    def test_replay_is_quiet_unless_it_failed_or_is_stale(self):
        days = [evidence_day(n) for n in (1, 2, 3, 4)]
        box = draw(
            days=days,
            order=[1, 2, 3, 4],
            evidence_checks=report(
                report_day(1), report_day(2, failed=2), report_day(3, state="stale")
            ),
        )["plot-evidence"]
        status = [s for _, s in self.rows(box)]
        self.assertIn("3 checks replayed, none failed", status[0])
        self.assertIn('class="plot-bad">2 failed', status[1])
        self.assertIn('class="plot-bad"', status[2])
        self.assertIn("stale", status[2])
        self.assertIn(NONE, status[3])
        self.assertIn("not checked", status[3])

    def test_no_report_is_never_drawn_as_a_pass(self):
        box = draw(days=[evidence_day(1)], order=[1], evidence_checks=dict(state="absent"))[
            "plot-evidence"
        ]
        self.assertIn("no report", box)
        self.assertNotIn("none failed", box)

    def test_a_day_before_the_format_is_not_measured(self):
        day = evidence_day(1, False, break_format=False)
        box = draw(days=[day], order=[1])["plot-evidence"]
        self.assertIn("ev-tile rec-none", box.split("</div>", 1)[1])
        self.assertNotIn('ev-tile rec-no"', box.split("</div>", 1)[1])

    def test_the_headline_counts_only_days_asked_for_that_evidence(self):
        old = evidence_day(1, evidence_format=False)
        panels = draw(days=[old, evidence_day(2)], order=[1, 2])
        self.assertIn('<b class="num">1 of 2</b><span>promises cite', panels["evidence-headline"])
        self.assertIn(
            '<b class="num">2 of 4</b><span>named tests are still', panels["evidence-headline"]
        )

    def test_skipped_live_tests_are_one_line(self):
        skip = draw(days=[evidence_day(1)], order=[1])["evidence-skip"]
        self.assertEqual(skip, "1 live test needs real Claude; CI skips them, run by hand.")

    def test_no_finished_day_is_not_measured(self):
        self.assertIn(NONE, draw()["plot-evidence"])


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

    def test_dots_sit_on_a_log_axis_labelled_in_minutes(self):
        box = draw(verification=self.PRS)["plot-open"]
        at = {
            int(n): round(float(x))
            for x, n in re.findall(r'left:([\d.]+)%;top:\d+px"[^>]*title="#(\d+)', box)
        }
        self.assertEqual(at, {1: 0, 2: 50, 3: 100})
        self.assertEqual(
            re.findall(r'<span style="left:[\d.]+%">([\d,.]+)</span>', box), ["1", "10", "100"]
        )
        self.assertIn(">minutes<", box)

    def test_a_dot_links_to_its_pr_and_one_with_no_link_is_still_drawn(self):
        box = draw(verification=self.PRS)["plot-open"]
        self.assertRegex(box, r'<a class="pr-dot"[^>]*href="https://x/1"')
        self.assertRegex(box, r'<i class="pr-dot failed"[^>]*title="#2')

    def test_the_median_is_marked_per_step_and_speed_is_never_green(self):
        box = draw(verification=self.PRS)["plot-open"]
        self.assertEqual(box.count('<i class="pr-median"'), 2)
        self.assertNotRegex(box, r"--close|--r-holds|proven")

    def test_no_times_is_not_measured(self):
        self.assertIn(NONE, draw(verification=[pr(1)])["plot-open"])


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

    def test_links_are_followed_to_one_family_per_problem(self):
        box = draw(defect_recurrence=self.REC)["plot-repeats"]
        chains = re.findall(r'<div class="chain">(.*?)</div>', box)
        self.assertEqual(
            [re.findall(r">(D\d+\.\d+)<", c) for c in chains],
            [["D01.1", "D02.1", "D03.1", "D03.2"], ["D05.1", "D05.2"]],
        )

    def test_same_day_repeats_are_told_apart(self):
        box = draw(defect_recurrence=self.REC)["plot-repeats"]
        self.assertIn(
            "<b>4</b> problems repeated an earlier one: <b>2</b> on a later day, <b>2</b> the same day",
            box,
        )
        self.assertEqual(
            re.findall(r'chain-id same-day" title="(D\d+\.\d+) ', box), ["D03.2", "D05.2"]
        )

    def test_no_repeats_and_no_data_are_different(self):
        self.assertIn(
            "No problem has been recorded",
            draw(defect_recurrence=dict(with_id=1, problems=[], recurrences=[]))["plot-repeats"],
        )
        self.assertIn(NONE, draw(defect_recurrence=None)["plot-repeats"])


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
        "plot-all",
        "plot-features",
        "plot-groups",
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
        "plot-features": "trust-table",
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

    def test_what_a_plot_would_mislead_without_stays_visible(self):
        for sentence in (
            "does not establish complete behavioral coverage or current correctness",
            "a gate that finds nothing may still be what kept a defect from being made",
        ):
            around = [stack for data, stack in self.shape.text if sentence in data]
            self.assertTrue(around, sentence)
            self.assertTrue(all(open_ for stack in around for _, open_ in stack), sentence)


if __name__ == "__main__":
    unittest.main()
