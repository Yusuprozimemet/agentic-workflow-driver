"""Does it learn? Read by the cell and graph 1's row of old problems back: repeats per Day and each fix's before and after (`learning`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

import collections

from spec_drift_view_common import _finished, _list, _ms, _order, _round, _stamp
from spec_drift_view_proofreading import PRF_LAYERS, gate_of


def _day_of_id(i):
    return int(i[1:].split(".")[0])


# A verdict waits for this many Days after a fix counts (the maintainer's choice): a rate over fewer is rough.
LRN_WAIT = 5


# The gates before the close: a repeat one of them caught was caught before it got into the work
LRN_GATED = tuple(k for L in PRF_LAYERS[:2] for k in L["gates"] if k != "work")


def learning(d):
    """"Does it learn?": the two graphs' figures, from the Days' Defect lines, their same-as: tags and specs/fixes.json.

    A problem is a chain of same-as: links, followed both ways: every Defect line linked to another is the same
    problem. A fix counts from the first Day whose spec merged after the fix merged (no such Day yet: it counts from
    none, and everything is before it). Per fix, "before" is the defects of the chains its stops sit in on earlier
    Days and "after" those from that Day on; a stop in no chain is a chain of one. Per Day, a repeat is a Defect line
    with a same-as: tag, and it got past a fix when a fix of its chain counted from that Day or earlier; only the
    Days whose spec has merged get a row, and a fix's days_since counts those of them that have finished, as a Day
    still open has observed nothing yet.

    A rate is times a Day: the problems before a fix over the Days before it (from the first Day they were
    recorded), and the ones after it over the Days since. A verdict is "gone" when nothing came back, "reduced" when
    they came back at most half as often a Day, else "not reduced", and waits for LRN_WAIT Days. A repeat is "gated"
    when a gate before the close (LRN_GATED) caught it, else "leaked": it got past the gates."""
    lines = [(x_day["day"], x) for x_day in d.get("days") or [] for x in x_day.get("defects") or []
             if x.get("id") and not x.get("problem")]
    days = sorted(x["day"] for x in d.get("days") or [] if isinstance(x.get("day"), int))
    row_of = {x["day"]: x for x in d.get("days") or [] if isinstance(x.get("day"), int)}
    ids = {x["id"]: day for day, x in lines}
    count = collections.Counter(day for day, _ in lines)
    gated_ids = {x["id"] for day, x in lines if gate_of(x.get("found"), day) in LRN_GATED}
    reps = [r for r in (d.get("defect_recurrence") or {}).get("recurrences") or [] if r.get("id") in ids]
    root = {}

    def find(i):
        root.setdefault(i, i)
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i

    for r in reps:
        root[find(r["id"])] = find(r["same_as"])
    chain = collections.defaultdict(set)
    for i in list(root):
        chain[find(i)].add(i)
    members = lambda i: chain.get(find(i)) if i in root else {i}  # noqa: E731
    spec_at = {}
    for p in (d.get("clock") or {}).get("prs") or []:
        if p.get("kind") == "spec" and p.get("merged") and isinstance(p.get("day"), int):
            spec_at[p["day"]] = min(spec_at.get(p["day"], p["merged"]), p["merged"])
    record = d.get("fixes") or {}
    problems, fixes, past = list(record.get("problems") or []), [], collections.defaultdict(set)
    for f in record.get("fixes") or []:
        unknown = [s for s in f["stops"] if s not in ids]
        if unknown:
            problems.append(f"#{f['pr']}: stops {_list(unknown)} {'names' if len(unknown) == 1 else 'name'} no Defect line")
        known = [s for s in f["stops"] if s in ids]
        if not known:
            continue
        later = [day for day in days if day in spec_at and _ms(spec_at[day]) > _ms(f["merged"])]
        start = later[0] if later else None
        hit = set().union(*(members(s) for s in known))
        after = sorted((i for i in hit if start is not None and ids[i] >= start), key=_order)
        for i in hit:
            past[find(i) if i in root else i].add(start)
        first = min((ids[i] for i in hit if i in ids), default=None)
        days_since = sum(1 for day in spec_at if start is not None and day >= start and _finished(row_of.get(day)))
        days_before = sum(1 for day in days if day in spec_at and first is not None and day >= first
                          and (start is None or day < start))
        before = len(hit) - len(after)
        rate_before = round(before / days_before, 2) if days_before else None
        rate_after = round(len(after) / days_since, 2) if days_since else None
        verdict = None
        if start is not None and days_since >= LRN_WAIT and rate_before is not None:
            verdict = ("gone" if not after else "reduced" if len(after) / days_since <= before / days_before / 2
                       else "not reduced")
        fixes.append(dict(pr=f["pr"], title=f.get("title") or "", merged=f["merged"], from_day=start, stops=known,
                          before=before, after=len(after), after_ids=after, days_since=days_since, first_day=first,
                          days_before=days_before, rate_before=rate_before, rate_after=rate_after,
                          gated=[i for i in after if i in gated_ids], leaked=[i for i in after if i not in gated_ids],
                          verdict=verdict))
    fixes.sort(key=lambda f: (f["from_day"] is None, f["from_day"] or 0, f["pr"]))
    by_day = collections.defaultdict(lambda: dict(before=[], past_fix=[]))
    for r in sorted(reps, key=lambda r: _order(r["id"])):
        day, starts = ids[r["id"]], past.get(find(r["id"]), ())
        by_day[day]["past_fix" if any(s is not None and s <= day for s in starts) else "before"].append(r["id"])

    def row(day):
        n, past_fix = len(by_day[day]["before"]) + len(by_day[day]["past_fix"]), by_day[day]["past_fix"]
        return dict(day=day, n=n, **by_day[day], defects=count[day],
                    share=_round(100 * n / count[day]) if count[day] else None,
                    gated=[i for i in past_fix if i in gated_ids], leaked=[i for i in past_fix if i not in gated_ids],
                    fixes=[f["pr"] for f in fixes if f["from_day"] == day])

    rows = [row(day) for day in days if day in spec_at]
    seen = collections.Counter(i for f in fixes for i in f["after_ids"])
    return dict(_stamp(d), days=rows, fixes=fixes, repeats=sum(r["n"] for r in rows),
                past_fix=sum(len(r["past_fix"]) for r in rows),
                held=sum(1 for f in fixes if f["from_day"] is not None and not f["after"]), problems=problems,
                wait=LRN_WAIT, past_gated=sum(len(r["gated"]) for r in rows),
                past_leaked=sum(len(r["leaked"]) for r in rows),
                shared=sorted((i for i in seen if seen[i] > 1), key=_order))
