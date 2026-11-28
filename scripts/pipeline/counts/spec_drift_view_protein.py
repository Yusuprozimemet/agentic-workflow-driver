"""Graphs 3 to 5: the abilities as proteins, each promise a cell on its chain (`protein`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

from spec_drift_view_common import _order, _plain, _round, _runs, _stamp


# The replay's states that count as re-checked: the proteins' proven of re-checked counts these five.
RECHECKED = ("proven", "unproven", "repair", "broken", "skipped")


# What the driver's run log shows of each ability in use. This is the maintainer's mapping, as the mockup at #228
# draws it, not something the data states: a step that reached its merge with no park used "loop"; every park used
# "park"; a step with a crash used "recover"; a step that ended stopped used "stop" (none has yet); the run log keeps
# no rehearsal, so "rehearse" is not counted. A rail is needed at every level and is no step of a run.
RUN_USE = {
    "loop": "loop",
    "park": "park",
    "recover": "recover",
    "stop": "stop",
    "rehearse": "uncounted",
}


def _tally(cells):
    out = {}
    for x in cells:
        out[x["state"]] = out.get(x["state"], 0) + 1
    return out


def _per_day(cells):
    """[[day, criteria]] for each Day that wrote one of `cells`, in Day order: what the page says of a chosen Day."""
    days = sorted({x["day"] for x in cells if x.get("day") is not None})
    return [[day, sum(1 for x in cells if x.get("day") == day)] for day in days]


def protein(d):
    """Graphs 3 to 5 as proteins: one chain per ability, one cell per criterion in the order built (its Day, then its
    number), each in the state criterion_states gave it; the criteria that name no ability make a chain of their own.
    A criterion is drawn once, under the first ability it names; naming none, it sits in the chain of its own. `proven` of `rechecked` counts only the states the replay re-checks; a criterion in
    force outside them (written and not built, or not re-checked yet) is in `outside`."""
    index = [c for c in d.get("criteria_index") or [] if isinstance(c, dict)]
    us = d.get("user_stories") or {}
    named, stories = us.get("abilities") or [], us.get("stories") or []
    if not index:
        return dict(empty="no criterion is on record yet, so there is no chain to fold.")
    keys = [a.get("key") for a in named]
    steps = (d.get("driver_runs") or {}).get("steps") or []
    runs, scores = _runs(steps), (d.get("score") or {}).get("abilities") or {}
    cells = {}
    for c in sorted(index, key=lambda c: _order(c.get("id"))):
        mine = [a for a in c.get("abilities") or [] if a in keys]
        seen = c.get("seen") or {}
        cells.setdefault(mine[0] if mine else None, []).append(
            dict(
                id=c.get("id"),
                day=c.get("day"),
                tag=c.get("tag"),
                state=c.get("state") or "unchecked",
                back=bool(c.get("back")),
                text=_plain(c.get("plain") or c.get("claim")),
                prs=c.get("prs") or [],
                last=seen.get("last"),
                stops=seen.get("stops") or [],
                replaced_by=c.get("replaced_by") or [],
                also=mine[1:],
            )
        )

    def run(a):
        how = "rail" if a.get("role") == "rail" else RUN_USE.get(a.get("key"), "uncounted")
        got = runs.get(how)
        return dict(
            how=how,
            n=None if got is None else len(got),
            of=len(steps),
            prs=[x["pr"] if isinstance(x, dict) else x for x in got or []],
            parks=runs["park"],
            crashes=runs["recover"],
            open=runs["open"],
            merged=runs["loop"],
        )

    chains = []
    for a in named + ([dict(key=None, name="Not tied to an ability yet")] if None in cells else []):
        k, mine = a.get("key"), cells.get(a.get("key"), [])
        own = [s for s in stories if s.get("ability") == k] if k is not None else []
        by_day = {}
        for s in own:
            if s.get("day") is not None:
                by_day.setdefault(s["day"], []).append(s.get("number"))
        n = _tally(mine)
        chains.append(
            dict(
                key=k,
                name=_plain(a.get("name")),
                role=a.get("role"),
                cells=mine,
                counts=n,
                proven=n.get("proven", 0),
                rechecked=sum(n.get(s, 0) for s in RECHECKED),
                score=_round((scores.get(k) or {}).get("score")) if k is not None else None,
                prs=[[day, sorted(by_day[day])] for day in sorted(by_day)],
                between=sorted(s.get("number") for s in own if s.get("day") is None),
                run=run(a) if k is not None else None,
                per_day=_per_day(mine),
            )
        )
    every = [x for list_ in cells.values() for x in list_]
    n = _tally(every)
    rate = lambda c: (c["proven"] / c["rechecked"], c["rechecked"])  # noqa: E731
    ranked = [c for c in chains if c["key"] is not None and c["rechecked"]]
    pick = lambda c: dict(
        key=c["key"], name=c["name"], proven=c["proven"], rechecked=c["rechecked"]
    )  # noqa: E731
    rungs = [c for c in chains if c["role"] == "rung"]
    runs_of = d.get("driver_runs") or {}
    return dict(
        _stamp(d),
        chains=chains,
        counts=n,
        written=len(every),
        per_day=_per_day(every),
        replaced=n.get("replaced", 0),
        in_force=sum(v for s, v in n.items() if s != "replaced"),
        proven=n.get("proven", 0),
        rechecked=sum(n.get(s, 0) for s in RECHECKED),
        back=sum(1 for x in every if x["back"] and x["state"] == "proven"),
        outside=[
            x["id"] for x in every if x["state"] not in RECHECKED and x["state"] != "replaced"
        ],
        weakest=pick(min(ranked, key=rate)) if ranked else None,
        strongest=pick(max(ranked, key=rate)) if ranked else None,
        used=dict(
            n=sum(1 for c in rungs if (c["run"] or {}).get("n")), of=len(rungs), steps=len(steps)
        ),
        source=runs_of.get("source"),
        counted=runs_of.get("counted"),
    )
