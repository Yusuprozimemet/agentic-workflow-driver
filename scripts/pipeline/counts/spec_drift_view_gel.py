"""Graph 2: the yardsticks drawn as a gel (`gel`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

from spec_drift_view_common import _plain, _stamp


# Which way is better for each yardstick: lower, for these. This is the maintainer's judgement, not something the data
# states (it moved here unchanged from dashboard.js's LOWER_BETTER). Refusals are left unjudged: no direction is better.
LOWER_BETTER = ("cost", "replies", "escapes", "parks", "gates", "reread")


def _parks_from_runs(row, steps, days):
    """The parks row with the driver's run log standing in for a Day the lab notebook has no figure for, as graph 2
    does (dashboard.js, parksFromRuns): the parks over that Day's steps. Only the Days with a lane are filled."""
    values = {v.get("day"): v for v in row.get("values") or []}
    for day in sorted({s.get("day") for s in steps if s.get("day") in days}):
        if (values.get(day) or {}).get("value") is not None:
            continue
        n = sum(len(s.get("parks") or []) for s in steps if s.get("day") == day)
        values[day] = dict(
            day=day,
            value=n,
            text=f"{n} {'park' if n == 1 else 'parks'}, counted from the driver's run "
            "log; the lab notebook has no figure for this Day yet.",
        )
    return values


def _slope(points):
    """The sign of a straight line fitted to (day, value) points: up, down or flat; None under two points."""
    if len(points) < 2:
        return None
    mx, my = sum(x for x, _ in points) / len(points), sum(y for _, y in points) / len(points)
    s = sum((x - mx) * (y - my) for x, y in points)
    return "up" if s > 1e-9 else "down" if s < -1e-9 else "flat"


def gel(d):
    """Graph 2 as a gel: one panel per yardstick, a lane per Day it is counted at, and a ladder lane with the kit's
    figure (where the kit recorded one) and the average so far. Each panel's last figure is judged against its average
    where lower is better (LOWER_BETTER); the headline counts those below it, and the Days above the kit's figure."""
    Y = d.get("yardsticks") or {}
    days, rows = sorted(Y.get("days") or []), Y.get("rows") or []
    if not rows or not days:
        return dict(empty="no yardstick is counted yet, so there is no gel to run.")
    steps = (d.get("driver_runs") or {}).get("steps") or []
    panels = []
    for r in rows:
        values = (
            _parks_from_runs(r, steps, days)
            if r.get("key") == "parks" and steps
            else {v.get("day"): v for v in r.get("values") or []}
        )
        lanes = [
            dict(
                day=day,
                value=(values.get(day) or {}).get("value"),
                text=_plain((values.get(day) or {}).get("text")),
            )
            for day in days
        ]
        got = [x for x in lanes if x["value"] is not None]
        avg = next((a for a in reversed(r.get("average") or []) if a is not None), None)
        last = dict(day=got[-1]["day"], value=got[-1]["value"]) if got else None
        better, kit = r.get("key") in LOWER_BETTER, r.get("baseline")
        verdict = (
            None
            if not last or avg is None
            else "flat"
            if not better
            else "better"
            if last["value"] < avg
            else "worse"
            if last["value"] > avg
            else "even"
        )
        panels.append(
            dict(
                key=r.get("key"),
                name=_plain(r.get("name") or r.get("key")),
                unit=r.get("unit") or "",
                decimals=r.get("decimals") or 0,
                lower_better=better,
                kit=kit,
                average=avg,
                average_over=r.get("average_over"),
                source=r.get("source"),
                lanes=lanes,
                last=last,
                verdict=verdict,
                counted=len(got),
                empty=len(lanes) - len(got),
                above_kit=None if kit is None else sum(1 for x in got if x["value"] > kit),
                drift=_slope([(x["day"], x["value"]) for x in got]),
            )
        )
    judged = [p for p in panels if p["lower_better"]]
    return dict(
        _stamp(d),
        days=days,
        panels=panels,
        named=len(panels),
        judged=len(judged),
        below=[p["key"] for p in judged if p["verdict"] == "better"],
        kit=[
            dict(key=p["key"], above=p["above_kit"], of=p["counted"], kit=p["kit"], last=p["last"])
            for p in panels
            if p["kit"] is not None
        ],
    )
