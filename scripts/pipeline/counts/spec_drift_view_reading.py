"""Graph 1: the plan being read, merge by merge (`reading`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

from spec_drift_view_common import _finished, _placed, _plain, _stamp


def reading(d):
    """Graph 1 as the plan being read: every merge in order on one strand, a Day's merges as a block (its main span, and any
    fragment away from it), the merges no Day owns as stretches between the blocks, the promises each merge built
    under it, the hand-offs as arcs from the merge that opened them to the one that closed them (or on to the Day ahead
    they wait for), and the Days plan.md lists with no spec yet, up to the stop."""
    rows = d.get("rows") or []
    if not rows:
        return dict(empty="nothing is merged yet, so there is no strand to read.")
    look, now, meta = d.get("look_ahead") or {}, d.get("now") or {}, d.get("meta") or {}
    cols, ledger = look.get("columns") or [], look.get("hand_offs") or []
    by = {x["day"]: x for x in d.get("days") or []}
    order = [n for n in d.get("order") or [] if isinstance(n, int)]
    rank = lambda day: order.index(day) if day in order else len(order) + (day or 0)  # noqa: E731
    names = (meta.get("where") or {}).get("names") or {}
    index = d.get("criteria_index") or []
    tag = {c["id"]: [c.get("tag") or "new", c.get("day")] for c in index}
    placed = _placed(d)
    m = [dict(pr=r.get("pr"), t=r.get("title") or "", k=p["kind"], own=p["own"], w=p["whose"],
              g=[[g, *tag.get(g, ["new", None])] for g in (cols[i] if i < len(cols) else {}).get("got") or []])
         for i, (r, p) in enumerate(zip(rows, placed))]
    strand = []
    for i, x in enumerate(m):
        if x["own"] is not None:
            strand.append(dict(m=i))
        elif strand and "iv" in strand[-1]:
            strand[-1]["iv"].append(i)
        else:
            strand.append(dict(iv=[i]))
    ivs = [x["iv"] for x in strand if "iv" in x]
    cells = [x["m"] for x in strand if "m" in x]
    days = []
    for day in sorted({m[i]["own"] for i in cells}, key=rank):
        groups, frags, prev = [], 0, None
        for i in cells:
            if m[i]["own"] == day:
                if prev is None or m[prev]["own"] != day:
                    groups.append([])
                groups[-1].append(i)
            prev = i
        run = False
        for x in strand:
            mine = "m" in x and m[x["m"]]["own"] == day
            frags += mine and not run
            run = mine
        main = max(groups, key=len)
        crit = (by.get(day) or {}).get("criteria") or {}
        days.append(dict(day=day, main=[main[0], main[-1]], strays=[[g[0], g[-1]] for g in groups if g is not main],
                         frags=frags, ticked=crit.get("ticked", 0), total=crit.get("total", 0)))
    last_of = {x["day"]: max(i for i in cells if m[i]["own"] == x["day"]) for x in days}
    finished = lambda n: _finished(by.get(n))  # noqa: E731
    h = []
    for x in ledger:
        to = [t for t in x.get("to") or [] if isinstance(t, int)]
        waits = None
        if x.get("closed") is None and to:
            waits = next((t for t in sorted(to, key=rank) if not finished(t)), max(to, key=rank))
        h.append(dict(id=x.get("id"), s=x.get("source") or "", x=x.get("text") or "", o=x.get("opened"),
                      c=x.get("closed"), how=x.get("how"), w=waits))
    stop = now.get("stop_after")
    ahead = [dict(day=n, n=_plain(names.get(str(n))), w=[x["id"] or "unnumbered" for x in h
                                                        if x["c"] is None and x["w"] == n])
             for n in order if n not in by and (stop is None or rank(n) <= rank(stop))]
    gap = [dict(id=c["id"], d=c.get("day"), at=last_of[c.get("day")],
                x=(lambda t: t if len(t) <= 200 else t[:199].rstrip() + "…")(" ".join(_plain(c.get("claim")).split())))
           for c in index if c.get("ticked") is False and not c.get("replaced_by") and finished(c.get("day"))
           and c.get("day") in last_of]
    lifted = []
    for r in (meta.get("where") or {}).get("rows") or []:
        if r.get("stop") is not None and r.get("lifted") and r["stop"] in last_of:
            at = last_of[r["stop"]]
            nxt = next((i for i in cells if i > at and m[i]["own"] != r["stop"]), len(m))
            lifted.append(dict(day=r["stop"], at=at, between=nxt - at - 1))
    stretch = []
    for j, x in enumerate(strand):
        if "iv" in x:
            after = strand[j + 1]["m"] if j + 1 < len(strand) and "m" in strand[j + 1] else None
            nd = m[after]["own"] if after is not None else None
            stretch.append(dict(n=len(x["iv"]), a=m[x["iv"][0]]["pr"], b=m[x["iv"][-1]]["pr"], w=m[x["iv"][0]]["w"],
                                next=nd, first=after is not None and min(i for i in cells if m[i]["own"] == nd) == after))
    kinds, between = {}, {}
    for i, x in enumerate(m):
        kinds[x["k"]] = kinds.get(x["k"], 0) + 1
    for i in (i for iv in ivs for i in iv):
        between[m[i]["k"]] = between.get(m[i]["k"], 0) + 1
    how = {}
    for x in h:
        k = x["how"] if x["c"] is not None else "open"
        how[k] = how.get(k, 0) + 1
    phases = [dict(phase=r.get("phase"), name=(meta.get("phases") or [])[r["phase"]]
                   if r.get("phase") is not None and r["phase"] < len(meta.get("phases") or []) else "",
                   days=r.get("days") or [], stop=r.get("stop"), lifted=bool(r.get("lifted")),
                   from_day=r.get("from_day"), later=not r.get("days"))
              for r in (meta.get("where") or {}).get("rows") or [] if not r.get("cut")]
    return dict(
        _stamp(d), m=m, strand=strand, days=days, h=h, ahead=ahead, gap=gap, lifted=lifted, phases=phases,
        stop=None if stop is None else dict(day=stop, name=_plain(names.get(str(stop)) or (by.get(stop) or {}).get("title"))),
        built=look.get("built", 0), written=look.get("written", 0), merges=len(m), stretches=len(ivs),
        between=sum(len(iv) for iv in ivs), between_kinds=between, kinds=kinds, how=how,
        open=sum(1 for x in h if x["c"] is None), numbered=sum(1 for x in h if x["c"] is None and x["id"]),
        opens=[dict(h=j, id=x["id"], to=x["w"], pr=m[x["o"]]["pr"] if x["o"] is not None else None, x=x["x"])
               for j, x in enumerate(h) if x["c"] is None and x["id"]],
        longest=sorted(stretch, key=lambda s: -s["n"])[:3],
        cut=sorted(([x["day"], x["frags"]] for x in days if x["frags"] > 1), key=lambda x: -x[1])[:3],
        unbroken=[x["day"] for x in days if x["frags"] == 1], strayed=[x["day"] for x in days if x["strays"]])
