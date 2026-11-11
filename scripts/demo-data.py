"""Made-up data in the shape scripts/spec-drift.py writes for the dashboard: the one dict it puts in
window.SPEC_DRIFT, for a project called sample-shop. Nothing in it was measured, and every value is
written out here, so the same call gives the same dict every time.

    python scripts/demo-data.py      # prints the dict as JSON
"""
import json

PROJECT = "sample-shop"
PHASES = ["Catalogue", "Checkout", "Shipping"]
HEAD = "3a7c1e4f9b2d0e8a6c5b4d3e2f1a0b9c8d7e6f5a"
FINISHED = ("done", "closed")

# Each day: its title, phase, status, the work of its one track, and three criteria, each
# (kind, claim, ticked, test). Days 1-5 have merged PRs; day 6 has two, its close still open.
DAYS = {
    1: dict(title="Product list", phase=1, status="done", work="C1.1–C1.3 the list page", criteria=[
        ("new", "The list shows 20 products a page", True, "ProductListTest.test_pages"),
        ("new", "Products sort by price", True, "ProductListTest.test_sort"),
        ("hold", "The list makes one query, not one per row", True, "ProductListTest.test_one_query")]),
    2: dict(title="Product detail", phase=1, status="done", work="C2.1–C2.3 the product page", criteria=[
        ("new", "A product page shows its photos and price", True, "ProductDetailTest.test_photos"),
        ("new", "An unknown product id returns 404", True, "ProductDetailTest.test_missing"),
        ("hold", "Prices are stored in cents", True, "PriceTest.test_cents")]),
    3: dict(title="Cart", phase=1, status="done", work="C3.1–C3.3 the cart", criteria=[
        ("new", "Adding a product twice raises its quantity", True, "CartTest.test_add_twice"),
        ("new", "The cart total sums its lines in cents", True, "CartTest.test_total"),
        ("hold", "The cart survives a page reload", True, "CartTest.test_reload")]),
    4: dict(title="Checkout totals", phase=2, status="done", work="C4.1–C4.3 the totals", criteria=[
        ("new", "Tax is added after the discount", True, "TotalsTest.test_order"),
        ("new", "Shipping is free over 50 units of currency", True, "TotalsTest.test_free_shipping"),
        ("hold", "Totals round half up to the cent", True, "TotalsTest.test_rounding")]),
    5: dict(title="Payment", phase=2, status="closed", work="C5.1–C5.3 the payment", criteria=[
        ("new", "A declined card leaves the cart as it was", True, "PaymentTest.test_decline"),
        ("new", "A paid order is written once, even on retry", True, "PaymentTest.test_retry"),
        ("hold", "Card numbers never reach the logs", False, "PaymentTest.test_no_card_in_logs")]),
    6: dict(title="Receipts", phase=2, status="active", work="C6.1–C6.3 the receipt email", criteria=[
        ("new", "A receipt is emailed after payment", False, "ReceiptTest.test_sent"),
        ("new", "A receipt lists tax on its own line", False, "ReceiptTest.test_tax_line"),
        ("hold", "Receipt numbers are never reused", False, "ReceiptTest.test_numbering")]),
    7: dict(title="Delivery slots", phase=3, status="ready", work="C7.1–C7.3 the slots", criteria=[
        ("new", "Customers see slots for the next 7 days", False, "SlotTest.test_horizon"),
        ("new", "A full slot is not offered", False, "SlotTest.test_full"),
        ("hold", "Slots are kept in UTC", False, "SlotTest.test_utc")]),
    8: dict(title="Tracking", phase=3, status="provisional", work="C8.1–C8.3 the tracking page", criteria=[
        ("new", "A shipped order shows its carrier and number", False, "TrackingTest.test_carrier"),
        ("new", "Tracking pages load without a login", False, "TrackingTest.test_public"),
        ("hold", "Carrier updates are idempotent", False, "TrackingTest.test_idempotent")]),
}
SHIPPED = range(1, 7)  # the days that have PRs
CLOSE_DAY = 9  # the day after the last written one


def slug(d):
    return DAYS[d]["title"].lower().replace(" ", "-")


def day_prs(d):
    """Day d's PRs in the order they were opened: spec change, track, close. Only day 6's close is open."""
    base = 100 + 3 * (d - 1)
    title = DAYS[d]["title"].lower()
    named = dict(spec=(f"Day {d:02d} spec change: {title}", f"day-{d:02d}/spec-{slug(d)}"),
                 code=(f"Day {d:02d} track A: {DAYS[d]['work']}", f"day-{d:02d}/track-a-{slug(d)}"),
                 close=(f"Day {d:02d} close: {title}", f"day-{d:02d}/close-the-day"))
    return [dict(number=base + j, kind=k, title=named[k][0], branch=named[k][1], day=d,
                 state="OPEN" if (d == 6 and k == "close") else "MERGED")
            for j, k in enumerate(("spec", "code", "close"), 1)]


# A day's spec adds names the code does not have yet, so coverage dips at its spec PR; its track puts them in.
DIP = {1: 0.95, 2: 0.94, 3: 0.94, 4: 0.93, 5: 0.94, 6: 0.94}


def coverage_at(p):
    """Share of reached-day spec names in the code at a merge: None at the origin, as spec-drift.py gives it."""
    if p["kind"] == "origin":
        return None
    return DIP[p["day"]] if p["kind"] == "spec" else 1.0


def evidence_at(closed, p):
    """Tests named by the closed days: three each, all present at its close. Day 4's close finds one missing
    (orange), and the next merge has it back. Nothing is skippable or retired."""
    if not closed:
        return None
    missing = int(p["kind"] == "close" and p["day"] == 4)
    return dict(present=3 * closed - missing, skippable=0, missing=missing, retired=0)


def row(i, p):
    """One snapshot: a PR as it merged, its line counts, and the gap and name figures after it."""
    gap = round(71.5 - 2.6 * i, 2)
    chance = round(gap + 6.3, 2)
    work = dict(spec=0, context=0, prod=0, test=0, tooling=0)
    if p["kind"] == "spec":
        work["spec"] = 30
    elif p["kind"] == "code":
        work.update(prod=40 + i, test=18)
    else:
        work["tooling"] = 12
    return dict(i=i, sha=f"{(i * 2654435761) % 16 ** 7:07x}", date=f"2026-10-{i:02d}", pr=p["number"],
                title=p["title"], branch=p["branch"], kind=p["kind"], day=p["day"],
                own_day=p["day"] if p["branch"].startswith("day-") else None, added=40 + 3 * i, deleted=2 * i, gap_full=gap, gap_chance=chance,
                gap_chance_band=[round(chance - 4, 2), round(chance + 4, 2)], coverage=coverage_at(p),
                name_coverage=min(1.0, round(0.2 + 0.04 * i, 3)), jaccard=round(0.1 + 0.03 * i, 3),
                names_kept=i, names_retired=0, prod_name_coverage=round(0.1 + 0.02 * i, 3),
                spec_names=12 + i, names_in_code=8 + i, names_in_prod=6 + i,
                names_outside_prod={"ProductListTest": {"test": ["tests/test_product_list.py"]}} if i == 1 else {},
                names_absent=["test_hold"] if i == 1 else [], spec_files={}, code_churn=58 + i,
                work=work, evidence=None, placed={}, crossings={})


def build_rows():
    """The origin snapshot, then one per merged PR, in merge order."""
    merged = [p for d in SHIPPED for p in day_prs(d) if p["state"] == "MERGED"]
    origin = dict(row(0, dict(number=None, kind="origin", title="Plan and specs as written", branch="", day=0)),
                  date="2026-09-29", sha="5e1f0a2", pr=None, branch="", kind="origin", day=0, own_day=None, added=0, deleted=0,
                  gap_full=71.5, gap_chance=77.8, gap_chance_band=[73.8, 81.8], name_coverage=0.2, jaccard=0.2,
                  names_kept=0, work=dict(spec=0, context=0, prod=0, test=0, tooling=0))
    rows, closed = [origin], 0
    for i, p in enumerate(merged, 1):
        closed += p["kind"] == "close"
        rows.append(dict(row(i, p), evidence=evidence_at(closed, p)))
    return rows


def build_days(rows):
    """Each day's record, its criteria with their evidence, and the criteria index and attention they feed."""
    by_pr = {r["pr"]: r for r in rows if r["pr"]}
    days, index, attention, checks, removals = [], [], [], [], []
    for d in sorted(DAYS):
        spec = DAYS[d]
        prs = day_prs(d) if d in SHIPPED else []
        mine = [p for p in prs if p["state"] == "MERGED"]
        finished = spec["status"] in FINISHED
        track = next((p["number"] for p in prs if p["kind"] == "code"), None)
        close = next((p["number"] for p in prs if p["kind"] == "close"), None)
        state = "stale" if d == 5 else "current" if finished else "not checked"
        evidence, why = [], ["checked at close 5b1c0d2, main's is 7e9a4f1"] if d == 5 else []
        for n, (kind, claim, ticked, test) in enumerate(spec["criteria"], 1):
            cid = f"C{d}.{n}"
            broke = [track] if ticked else []
            block = (f"- [{'x' if ticked else ' '}] {cid} **{kind}** — {claim}\n"
                     f"  Evidence: `{test}` in #{track}\n")
            block += f"  broken: the check was first run red → {test} failed (#{track})\n" if ticked else ""
            tests = {test: "present"} if finished else {}
            evidence.append(dict(id=cid, ticked=ticked, kind=kind, claim=claim, prs=[track] if track else [],
                                 tests=tests, red=ticked, broke_in=broke, block=block))
            index.append(dict(id=cid, day=d, phase=spec["phase"], tag=kind, claim=claim,
                              spec=f"specs/day-{d:02d}-{slug(d)}.md#acceptance-criteria", track="A",
                              prs=[track] if track else [], tests=[test], cited=True if ticked else None,
                              ticked=bool(ticked), test_found=True, seen_red=dict(state=ticked or None, lines=[block.splitlines()[-1]] if ticked else []),
                              replay=dict(state=state, status=["passed"] if finished else None,
                                          why=why, checks=[dict(criterion=cid, kind="test", status="passed",
                                                                label=test, diagnostic=None)] if finished else []),
                              replaces=[], replaced_by=[], abilities=list(DAY_ABILITIES.get(d, ())) if ticked else []))
            if d == 5:
                attention.append(dict(id=cid, reason="replay_stale", detail="; ".join(why)))
        ticks = sum(c["ticked"] for c in evidence)
        record = dict(day=d, file=f"specs/day-{d:02d}-{slug(d)}.md", title=spec["title"], phase=spec["phase"],
                      status=spec["status"], expected=3, expected_first=3, tracks=["A"],
                      track_work={"A": spec["work"]}, tracks_merged=["A"] if track else [],
                      tracks_unopened=[dict(track="B", pr=close)] if d == 6 else [],
                      track_prs=1 if track else 0,
                      prs=[dict(number=p["number"], kind=p["kind"], title=p["title"]) for p in mine],
                      criteria=dict(total=3, ticked=ticks, new=sum(c[0] == "new" for c in spec["criteria"]),
                                    hold=sum(c[0] == "hold" for c in spec["criteria"])),
                      worked=[by_pr[mine[0]["number"]]["date"], by_pr[mine[-1]["number"]]["date"]] if mine else None,
                      evidence_format=True, break_format=True, evidence=evidence,
                      removal_checks=[f'grep -rn "TODO day {d:02d}" src/'],
                      relabel=dict(stage=[3, 4], cause=[3, 4], made=[4, 4]) if d in (1, 2) else None,
                      defects=[dict(id=i, same_as=same, found=found, cause=cause, made=made, problem=None)
                               for day, i, found, cause, made, same in DEFECTS if day == d],
                      broken_at_close=[])
        if finished:
            record["ended_at"] = by_pr[close]["i"]
            n = len(rows) - record["ended_at"]
            removals.append(dict(day=d, cmd=record["removal_checks"][0], base="src", since=record["ended_at"],
                                 hits=[max(0, 2 - k) for k in range(n)], files=[12 + k for k in range(n)], found=[]))
            checks.append(dict(day=d, state=state, why=why, counts={"test": dict(passed=3, failed=0, error=0,
                                                                                 not_applicable=0)},
                               checks=[dict(criterion=c["id"], kind="test", status="passed",
                                            label=next(iter(c["tests"])), diagnostic=None) for c in evidence],
                               problems=[]))
        days.append(record)
    return days, index, attention, checks, removals


# The seven abilities, as spec-drift.py's ABILITIES has them: the demo imports nothing from that script.
ABILITIES = (
    dict(key="rehearse", name="Shows what it would do", role="rung"),
    dict(key="stop", name="Can be stopped, from anywhere", role="rung"),
    dict(key="loop", name="Works through the night", role="rung"),
    dict(key="park", name="Asks only when it must", role="rung"),
    dict(key="recover", name="Picks itself up after a crash", role="rung"),
    dict(key="see", name="Shows the world what still works", role="rail"),
    dict(key="record", name="Proves every claim", role="rail"),
)


# What each finished day's promises grew, the first being where graph 5 draws them.
DAY_ABILITIES = {1: ("rehearse",), 2: ("rehearse", "stop"), 3: ("stop",), 4: ("loop",), 5: ("park", "loop")}
# One made-up defect at each gate: its day, ID, found:, cause:, made: and same-as:, as a Defect line has them.
DEFECTS = (
    (1, "D1.1", "auditor", "spec", "Day 01", None),
    (2, "D2.1", "Track A", "implementation", "Day 01", "D1.1"),
    (3, "D3.1", "seen red", "implementation", "Day 03", None),
    (4, "D4.1", "break on purpose", "process", "none", None),
    (5, "D5.1", "close", "spec", "Day 05", None),
    (5, "D5.2", "evidence replay", "environment", "none", None),
)
# The newest re-check of each finished promise, so the board shows every state a tile can be in.
RECHECKED = {
    "C1.1": "holds", "C1.2": "holds", "C1.3": "live only",
    "C2.1": "holds", "C2.2": "holds, never broken", "C2.3": "holds",
    "C3.1": "test weakened", "C3.2": "holds", "C3.3": "holds, never broken",
    "C4.1": "holds", "C4.2": "code broken", "C4.3": "not applicable on this platform",
    "C5.1": "holds", "C5.2": "holds, never broken",
}


def yardsticks():
    """Made-up figures for the plan's yardsticks, one per finished day; the parks are never counted."""
    def row(key, name, unit, decimals, baseline, values):
        # The average so far, as if every day had merged the same number of pull requests.
        average = [None if v is None else round(sum(values[:n]) / n, 2) for n, v in enumerate(values, 1)]
        return dict(key=key, name=name, unit=unit, decimals=decimals, baseline=baseline, source="docs/lab-notebook.md",
                    values=[dict(day=d, value=v, text="none yet" if v is None else f"Made-up figure for Day {d}.")
                            for d, v in enumerate(values, 1)],
                    average=average, average_over="pull requests" if key in ("cost", "replies") else "days")
    return dict(days=[1, 2, 3, 4, 5], problems=[], rows=[
        row("cost", "Cost of each merged pull request, main sessions", "$", 2, 1.5, [1.2, 1.8, 1.4, 1.65, 1.3]),
        row("replies", "Replies for each merged pull request, main sessions", "", 1, 30.0, [24.5, 33.0, 28.0, 31.5, 26.0]),
        row("escapes", "Defects that escaped from an earlier Day", "", 0, None, [0, 1, 0, 0, 0]),
        row("parks", "Times the driver stopped for a person", "", 0, None, [None] * 5),
        row("refusals", "Calls the hooks refused", "", 0, None, [0, 0, 2, 1, 2])])


def look_ahead(rows, index):
    """Made-up figures for the graph that looks ahead: a day's promises are written at its spec change and built at
    its track, the days with no pull request yet have theirs written from the start, and three hand-offs open, of
    which one is picked up."""
    ids = {}
    for c in index:
        ids.setdefault(c["day"], []).append(c["id"])
    at = {r["pr"]: i for i, r in enumerate(rows) if r["pr"]}
    ledger = [dict(id=None, source="src/receipts/views.py", to=[6], opened=0, closed=None, how=None,
                   text="Receipts are numbered per shop, not per customer"),
              dict(id="H2.1", source="Day 02 Notes", to=[4], opened=at[106], closed=at[110], how="picked",
                   text="Checkout totals reuse the cart's rounding helper (H2.1)"),
              dict(id="H3.1", source="Day 03 Notes", to=[], opened=at[109], closed=None, how=None,
                   text="Ask the shop owner about gift cards (H3.1)")]
    for h in ledger:
        h.update(opened_pr=rows[h["opened"]]["pr"], closed_pr=None if h["closed"] is None else rows[h["closed"]]["pr"])
    columns, built = [], 0
    written = sum(len(ids.get(d, [])) for d in DAYS if d not in SHIPPED)
    for i, r in enumerate(rows):
        got = ids.get(r["day"], []) if r["kind"] == "code" else []
        built += len(got)
        written += len(ids.get(r["day"], [])) if r["kind"] == "spec" else 0
        still = [h for h in ledger if h["opened"] <= i and (h["closed"] is None or h["closed"] > i)]
        columns.append(dict(pr=r["pr"], built=built, got=got, written=written, open=len(still),
                            open_numbered=sum(bool(h["id"]) for h in still),
                            opened=sum(h["opened"] == i for h in ledger), closed=sum(h["closed"] == i for h in ledger)))
    return dict(columns=columns, hand_offs=ledger, pending=dict(day=6, tracks=[], at_close=[]),
                built=built, written=written)


def clock(rows):
    """Made-up times for graph 10: each merged PR opened and merged on its date, its checks a few
    minutes after it opened, and three agents' stretches of work on every date with a merge, all
    stamped +02:00 so the page shows the machine's clock and not the reader's."""
    def stamp(date, minutes, offset="Z"):
        return f"{date}T{minutes // 60:02d}:{minutes % 60:02d}:00{offset}"
    open_for = dict(spec=45, code=25, close=190, other=12)
    prs, sessions = [], []
    for r in (r for r in rows if r["pr"]):
        opened = 8 * 60 + (r["pr"] % 5) * 60 + (r["pr"] * 7) % 60  # 08:00 to 12:59 UTC, 10:00 to 14:59 on the clock
        merged = opened + open_for[r["kind"]] + (r["pr"] % 3) * 5
        failed = 1 if r["kind"] == "code" and r["pr"] % 2 else 0
        prs.append(dict(number=r["pr"], day=r["own_day"], kind=r["kind"], branch=r["branch"], opened=stamp(r["date"], opened),
                        merged=stamp(r["date"], merged), checks=dict(start=stamp(r["date"], opened + 1), end=stamp(r["date"], opened + 5 + failed * 4),
                                                                   runs=4 + failed * 5, failed=failed)))
    for date in sorted({r["date"] for r in rows if r["pr"]}):
        day = next(r["day"] for r in rows if r["date"] == date)
        for agent, stretches, replies in (("main", ((8 * 60 + 10, 9 * 60 + 40), (10 * 60 + 5, 12 * 60 + 30), (13 * 60 + 40, 16 * 60 + 55)), 38),
                                          ("implementer", ((10 * 60 + 20, 10 * 60 + 35), (11 * 60 + 10, 11 * 60 + 30), (14 * 60, 14 * 60 + 25)), 9),
                                          ("spec-auditor", ((8 * 60 + 15, 8 * 60 + 40),), 6)):
            sessions.extend({"date": date, "day": day, "agent": agent, "from": stamp(date, a, "+02:00"), "to": stamp(date, b, "+02:00"), "replies": replies}
                            for a, b in stretches)
    return dict(prs=prs, sessions=sessions)


def driver_runs(rows, at):
    """Made-up steps of a driver that drove Days 4 to 6, in the format scripts/driver-runs.py writes and
    scripts/spec-drift.py passes on: one step per pull request of those Days, its last session ending as
    the pull request opens. Every way a step can end is here: merged untouched, merged after one or two
    fix rounds, parked on a decision that is the maintainer's, parked by a fault, merged after a first
    session crashed, and still open. Each park names its issue, which was closed when it was answered."""
    def stamp(date, minutes):
        return f"{date}T{minutes // 60:02d}:{minutes % 60:02d}:00Z"

    def run(pr, k, date, start, end, fixes=0):
        return dict(session=f"demo-session-{pr}-{k}", start=stamp(date, start), end=None if end is None else stamp(date, end),
                    cost=0.0 if end is None else round(0.9 + (pr % 4) * 0.3 + fixes * 0.25, 2), denials=0, fixes=fixes,
                    crashed=end is None)
    named = dict(spec=("Day {:02d}: read the spec against the code, then the spec-change PR", "day-{:02d}/spec"),
                 code=("Day {:02d} Track A: {}", "day-{:02d}/track-a"), close=("Day {:02d}: the closing PR", "day-{:02d}/close-the-day"))
    asked = "park: the session parked: a criterion cannot be met as written (session `{}`)"
    lost = "park: the session ended with no pull request and no PARK line (session `{}`)"
    steps, parks = [], []
    driven = [p for p in clock(rows)["prs"] if p["day"] in (4, 5, 6) and p["kind"] in named]
    last = day_prs(6)[-1]  # Day 6's close: its pull request is open
    driven.append(dict(number=last["number"], day=6, kind="close", opened=stamp(max(r["date"] for r in rows), 15 * 60), merged=None))
    for i, p in enumerate(driven):
        pr, day, date = p["number"], p["day"], p["opened"][:10]
        opened = int(p["opened"][11:13]) * 60 + int(p["opened"][14:16])
        sentence, prefix = (text.format(day, DAYS[day]["work"]) for text in named[p["kind"]])
        fixes = {1: 2, 7: 1}.get(i, 0)
        sessions, parked = [], []
        if i in (2, 4):
            # The first session parks; the maintainer closes the issue; a second session opens the pull request.
            line, by, began, waited = ((asked, "maintainer", opened - 120, 70), (lost, "fault", opened - 70, 25))[i == 4]
            sessions.append(run(pr, 1, date, began, began + 15))
            number = 900 + len(parks) + 1
            parked.append(dict(at=stamp(date, began + 15), line=line.format(sessions[0]["session"]), by=by, issue=number))
            parks.append(dict(number=number, title=parked[0]["line"], url=f"https://github.com/example/{PROJECT}/issues/{number}",
                              opened=stamp(date, began + 15), closed=stamp(date, began + 15 + waited)))
        if i == 5:
            sessions.append(run(pr, 1, date, opened - 60, None))
        sessions.append(run(pr, len(sessions) + 1, date, opened - 20, opened + 10 * fixes, fixes))
        steps.append(dict(step=sentence, day=day, prefix=prefix.format(day), sessions=sessions, fixes=fixes,
                          crashes=sum(s["crashed"] for s in sessions), pr=pr, merged=p["merged"], parks=parked,
                          ended="parked" if parked else "open" if p["merged"] is None else "fixed" if fixes else "merged"))
    return dict(source="docs/dashboard/driver-runs.json", counted=at, steps=steps, parks=parks)


def demo():
    rows = build_rows()
    days, index, attention, checks, removals = build_days(rows)
    merged = [r for r in rows if r["pr"]]
    files = ["plan.md"] + [f"specs/day-{d:02d}-{slug(d)}.md" for d in DAYS]
    # Hours open: a spec change waits on review, a close on its replay; one tooling PR beside them.
    hours = dict(spec=5.5, code=3.25, close=20.0, other=0.75)
    verification = [dict(number=r["pr"], day=r["day"], kind=r["kind"], step=r["kind"],
                         hours=hours.get(r["kind"], 1.0) + (r["pr"] % 3) * 0.5,
                         breaks="none" if r["kind"] == "spec" else "recorded",
                         pushes=2 if r["kind"] == "code" else 1, failed=1 if r["kind"] == "code" else 0,
                         failed_in=["unit"] if r["kind"] == "code" else [])
                    for r in merged]
    verification.append(dict(number=max(r["pr"] for r in merged) + 1, day=None, kind="other", step="tooling",
                             hours=0.75, breaks="recorded", pushes=1, failed=0, failed_in=[]))

    def hooks(n):
        # The story: the hooks arrive on day 4. Days 1 to 3 have no cut Bash results, days 4 to 6 no whole Reads.
        if n <= 3:
            return dict(bash=6 * n, cut=0, reads=2 * n + 1, whole=n + 1)
        return dict(bash=6 * n, cut=n - 2, reads=n, whole=0)
    tokens = [dict(date=f"2026-10-{n + 2:02d}", day=n, model=model, agent=agent,
                   input=900 * n + 400, cache_write=12000 * n, cache_read=310000 * n + 2000,
                   output=5200 * n + 300 if agent == "main" else 2100 * n, replies=40 * n + 7,
                   cost=round(1.9 * n + 0.4 if agent == "main" else 0.2 * n, 2), **hooks(n),
                   # The story: once the hooks are in, less of the main session's dollars is spent past 150k tokens.
                   cost_past_150k=round((1.9 * n + 0.4) * (0.45, 0.5, 0.55, 0.3, 0.2, 0.15)[n - 1], 2) if agent == "main" else 0.0)
              for n in range(1, 7)
              for agent, model in (("main", "claude-sonnet-5-5"), ("implementer", "claude-haiku-5-5"))]
    refusals = [dict(date=f"2026-10-{n + 2:02d}", guard=g, refused=k) for n, g, k in
                ((3, "read-guard", 2), (4, "step-guard", 1), (5, "read-guard", 1), (5, "auditor-guard", 1))]
    items = [dict(name="web task", count=2, per_hour=0.0412), dict(name="database", count=1, per_hour=0.095)]
    summary = dict(criteria={"C1": "pass", "C2": "pass"}, steps={"build": "pass", "deploy": "pass", "smoke": "pass"},
                   resources={"web": 2, "worker": 1, "database": 1},
                   cost=dict(items=items, per_hour=round(sum(i["per_hour"] for i in items), 3), region="eu-central-1",
                             note="estimate from list prices, not billed spend; example data, usage charges not counted"))
    runs = [dict(sha=f"{n:07x}", conclusion="success", date=f"2026-10-{20 - n:02d}",
                 url=f"https://github.com/example/{PROJECT}/actions/runs/{1000 + n}") for n in range(3)]
    return dict(
        now=dict(generated="2026-10-29T10:00+00:00", head=HEAD[:7], last_pr=merged[-1]["pr"], current_day=6,
                 next_step="Waiting on #118 Day 06 close: receipts", stop_after=None,
                 unwritten=dict(day=CLOSE_DAY, phase=3, title="The close-out day"),
                 open_prs=[dict(number=118, title="Day 06 close: receipts",
                                url=f"https://github.com/example/{PROJECT}/pull/118")]),
        rows=rows, files=files, days=days, origin_lines=412, order=list(DAYS), out_of_order=[],
        removals=removals,
        hand_offs=[dict(to=4, id="H2.1", source="Day 02 Notes", picked=True,
                        text="Checkout totals reuse the cart's rounding helper (H2.1)"),
                   dict(to=None, id="H3.1", source="Day 03 Notes", picked=False,
                        text="Ask the shop owner about gift cards (H3.1)"),
                   dict(to=6, source="src/receipts/views.py:12", picked=False,
                        text="Receipts are numbered per shop, not per customer")],
        look_ahead=look_ahead(rows, index),
        criteria_index=index, attention=attention,
        test_inventory=dict(total=46, unreadable=[], groups=[
            dict(key="driver", label="Driver behaviour", when="Every push and pull request", files=4, tests=30),
            dict(key="live", label="Live runs", when="By hand only", files=1, tests=1),
            dict(key="gap", label="The dashboard's gap numbers", when="Every push and pull request", files=1, tests=3),
            dict(key="tooling", label="Project tooling", when="On pull requests that touch a script", files=2, tests=12)]),
        defect_recurrence=dict(defects=len(DEFECTS), with_id=len(DEFECTS),
                               recurrences=[dict(id="D2.1", same_as="D1.1")], problems=[]),
        gate_report=dict(defects=len(DEFECTS), elsewhere=2, gates=[
            dict(gate=g, found=f, defects=sum(x[2] == f for x in DEFECTS), refused=r, runs=k, replies=3 * k,
                 context=90000 * k, output=1500 * k, cost=round(0.4 * k, 2),
                 causes={c: sum(x[2] == f and x[3] == c for x in DEFECTS)
                         for c in ("spec", "implementation", "process", "environment", "other")})
            for g, f, r, k in (("auditors", "auditor", None, 6), ("seen red", "seen red", None, 9),
                               ("break on purpose", "break on purpose", None, 14),
                               ("evidence replay", "evidence replay", None, 5), ("hooks", None, 5, 5))]),
        other_groups=[dict(name="tooling", count=4), dict(name="docs", count=3), dict(name="dashboard", count=2)],
        vocab_size=136, tokens=tokens, refusals=refusals, verification=verification,
        infra=dict(runs=runs, latest=dict(runs[0], summary=summary)), deployment=dict(
            domain="shop.example.com", checkedAt="2026-10-30T08:00+00:00",
            checks=[dict(criterion="C1", name="Product list loads", ok=True, detail="200 in 180 ms",
                         at="2026-10-30T08:00+00:00"),
                    dict(criterion="C4", name="Totals match the cart", ok=True, detail="3 of 3 orders",
                         at="2026-10-30T08:00+00:00"),
                    dict(criterion="C5", name="Declined card keeps the cart", ok=False, detail="cart emptied",
                         at="2026-10-30T08:00+00:00")]),
        evidence_checks=dict(state="loaded", generated="2026-10-29T10:00+00:00", ref="main", ref_sha=HEAD,
                             runner="evidence.py 1", days=checks),
        replay=dict(state="loaded", states=["holds", "holds, never broken", "code broken", "test weakened", "break no longer applies",
                                            "not applicable on this platform", "not runnable", "live only",
                                            "not yet in force"],
                    merges=[dict(n=n, merge=f"demo{n}", pr=merged[-1]["pr"] - 2 * (23 - n), sample=s, run=r, copied=c)
                            for n, s, r, c in ((20, "all", 5, 0), (21, "day", 1, 2), (23, "all", 2, 3))],
                    # The first two re-checks ran on Days 1 to 3, before a bug was planted in Day 3; the third on all five.
                    cells=[dict(criterion=cid, day=f"{int(cid[1]):02d}", n=n, state=st, mixed=cid == "C3.1" and n == 23,
                                checks=[dict(check="tests", state=st, platform="linux")])
                           for n in (20, 21, 23) for cid, last in RECHECKED.items() if n == 23 or cid[1] in "123"
                           for st in ["holds, never broken" if n < 23 and cid[1] == "3" else last]]
                    + [dict(criterion="C6.1", day="06", n=23, state="not yet in force", mixed=False,
                            checks=[dict(check="tests", state="not yet in force", platform="linux")])]),
        user_stories=dict(
            abilities=[dict(a) for a in ABILITIES], problems=[], source="docs/dashboard/user-stories.json",
            stories=[dict(number=r["pr"], title=r["title"], url=f"https://github.com/example/{PROJECT}/pull/{r['pr']}",
                          branch=r["branch"], day=r["own_day"], date=r["date"], ability=a, ability_source="pr",
                          story=f"Made-up story for pull request {r['pr']}.", story_source="pr", reader="desk")
                     for r in merged
                     for a in [DAY_ABILITIES[r["day"]][0] if r["kind"] != "other" and r["day"] in DAY_ABILITIES
                               else ("see", "record")[r["pr"] % 2]]]),
        conclusion=dict(reads=[dict(phase=1, text="**Read at the end of Phase 1.** Products and the cart work; "
                                                  "the checkout is next.")],
                        measured=[["Checkout abandonment", "31%"], ["Median page load", "1.2 s"]]),
        yardsticks=yardsticks(),
        clock=clock(rows), counted=dict(at=f"{max(r['date'] for r in rows)}T18:00:00+02:00"),
        driver_runs=driver_runs(rows, f"{max(r['date'] for r in rows)}T18:00:00+02:00"),
        # every file of the data branch on record, so no missing-data banner shows beside the example one
        data=dict(branch="dashboard-data", commit="example", at=f"{max(r['date'] for r in rows)}T18:00:00+02:00", absent=[]),
        meta=dict(caveats=["Made-up data for the dashboard's layout: no number here was measured.",
                           "A panel drawn from this data shows nothing about any real project."],
                  provenance=dict(commit=HEAD, script_edited=False, python="3.12.0", numpy="2.0.0",
                                  chance_draws=1000),
                  break_line_from_pr=0, project=PROJECT, phases=PHASES, stops=[]))


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2, ensure_ascii=True))
