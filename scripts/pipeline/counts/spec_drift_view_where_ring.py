"""Where we are: the plan as one turn of the cell cycle, a checkpoint at each stop (`where_ring`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

from spec_drift_view_common import _finished, _plain, _round, _stamp


def where_ring(d):
    """"Where we are" as a ring: one segment per Day plan.md numbers, in its order and its phases, a gate at each stop
    and the place the work stands, with everything the ring and its lists print. A Day's state is one of: closed, closed with a promise not ticked, in progress, spec written, next, or provisional; a
    phase with no Day numbered yet is one segment, a stub."""
    meta, now = d.get("meta") or {}, d.get("now") or {}
    where = meta.get("where") or {}
    rows = where.get("rows") or []
    if not rows:
        return dict(empty="plan.md lists no phase with its Days, so there is no plan to draw as a ring.")
    names, phase_names = where.get("names") or {}, meta.get("phases") or []
    by = {x["day"]: x for x in d.get("days") or []}
    order = [n for n in d.get("order") or [] if isinstance(n, int)]
    current, stop = now.get("current_day"), now.get("stop_after")
    next_day = next((n for n in order if not _finished(by.get(n))), None)
    scores = (d.get("score") or {}).get("days") or {}
    index = d.get("criteria_index") or []
    look = d.get("look_ahead") or {}
    slots, phases, gates = [], [], []
    for r in rows:
        p, ds, cut = r.get("phase"), r.get("days") or [], bool(r.get("cut"))
        name = phase_names[p] if p is not None and p < len(phase_names) else f"Phase {p}" if p is not None else ""
        phases.append(dict(k=f"p{p}", phase=p, name=name, days=ds, total=len(ds), cut=cut,
                           closed=sum(1 for n in ds if _finished(by.get(n))), stop=r.get("stop"),
                           lifted=bool(r.get("lifted")), from_day=r.get("from_day")))
        for i, n in enumerate(ds):
            x = by.get(n) or {}
            crit, sc = x.get("criteria") or {}, scores.get(str(n)) or {}
            if cut or x.get("status") == "cut":
                state = "cut"
            elif _finished(x):
                state = "done" if x.get("status") == "done" else "open"
            else:
                state = "active" if x and n == current else "ready" if x else "next" if n == next_day else "planned"
            low = next((q.get("name") for q in sc.get("parts") or [] if q.get("key") == sc.get("low")), None)
            kinds = [q.get("kind") for q in x.get("prs") or []]
            slots.append(dict(
                k=f"d{n}", day=n, phase=p, state=state, title=_plain(x.get("title")), name=_plain(names.get(str(n))),
                ticked=crit.get("ticked", 0), total=crit.get("total", 0),
                prs=dict(n=len(kinds), code=kinds.count("code"), spec=kinds.count("spec"), close=kinds.count("close")),
                score=_round(sc.get("score")), low=low.lower() if low else None,
                end=not cut and i == len(ds) - 1 and p is not None,
                stop=None if n != r.get("stop") else "passed" if r.get("lifted") else "ahead",
                tracks=len(x.get("tracks") or []), merged=len(x.get("tracks_merged") or [])))
        if not ds and r.get("from_day") is not None:
            slots.append(dict(k=f"stub{p}", day=None, phase=p, state="stub", from_day=r["from_day"]))
        if r.get("stop") is not None:
            at = next((i for i, s in enumerate(slots) if s["day"] == r["stop"]), len(slots) - 1)
            gates.append(dict(k=f"s{r['stop']}", day=r["stop"], passed=bool(r.get("lifted")), slot=at))
    days = [s for s in slots if s["day"] is not None]
    counted = [s["day"] for s in days if s["state"] != "cut"]
    if current is not None and any(s["day"] == current for s in days):
        place = dict(between=None, day=current, slot=next(i for i, s in enumerate(slots) if s["day"] == current))
    else:
        at = next((i for i, s in enumerate(slots) if s["day"] is not None and not _finished(by.get(s["day"]))), None)
        before = [i for i, s in enumerate(slots[:at] if at is not None else slots) if s["day"] is not None]
        place = dict(between=[slots[before[-1]]["day"] if before else None, slots[at]["day"] if at is not None else None],
                     day=None, slot=before[-1] if before else -1)
    ahead = counted[:counted.index(stop) + 1] if stop in counted else counted
    scored = [s for s in days if s["score"] is not None]
    last = next((r for r in reversed(d.get("rows") or []) if r.get("pr")), None)
    unticked = {}
    for c in index:
        if c.get("ticked") is False and not c.get("replaced_by"):
            unticked.setdefault(c.get("day"), []).append(c["id"])
    out = dict(
        _stamp(d), slots=slots, phases=phases, gates=gates, now=place, next_step=_plain(now.get("next_step")),
        last=last and dict(pr=last.get("pr"), sha=(last.get("sha") or "")[:7] or None, date=last.get("date"),
                           title=last.get("title") or ""),
        open_prs=[dict(pr=p.get("number"), title=p.get("title") or "") for p in now.get("open_prs") or []],
        closed=sum(1 for n in counted if _finished(by.get(n))), numbered=len(counted),
        left=[n for n in ahead if not _finished(by.get(n))], stop=stop,
        stop_name=_plain((by.get(stop) or {}).get("title") or names.get(str(stop))) if stop is not None else None,
        built=look.get("built", 0), written=look.get("written", 0),
        boxes=[dict(day=s["day"], ticked=s["ticked"], total=s["total"], ids=unticked.get(s["day"], []))
               for s in days if s["state"] == "open"],
        score=_round(((d.get("score") or {}).get("all") or {}).get("score")),
        lo=scored and dict(day=min(scored, key=lambda s: s["score"])["day"], n=min(s["score"] for s in scored)),
        hi=scored and dict(day=max(scored, key=lambda s: s["score"])["day"], n=max(s["score"] for s in scored)),
        repo_url=meta.get("repo_url"))
    out["lo"], out["hi"] = out["lo"] or None, out["hi"] or None
    return out
