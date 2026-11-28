"""Graph 6: the merges against the spec, a stripe per criterion (`merge_graph`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

from spec_drift_view_common import FAILED_GROUPS, REPLAY_GROUP, _cells


# The merge graph: what the replay's last state of a criterion is drawn as, in the strip under its stripe.
MERGE_ST = {"holds": "ok", "holds, never broken": "un", "code broken": "bad", "test weakened": "bad",
            "break no longer applies": "stale"}


HELD = ("proven", "unproven")


def _day_name(day):
    return "Start" if day == 0 else f"Day {day}"


def _merge_events(crit, cells, i_of, pr_of, rows):
    """Each stop of each criterion, as the merge graph draws it: where it was first seen failing (`pr`, and `n`, the
    row's place in merge order), the check that failed, where it held again (`end`), and its suspect window: the last
    merge before it where it held (`lon`, `lo`), how many merges from there to the stop (`wn`) and which merges in
    between changed product code (`sus`)."""
    out = []
    for pos, c in enumerate(crit):
        held, cur = None, None
        for cell in cells.get(c["id"], []):
            group, n = REPLAY_GROUP.get(cell.get("state")), cell.get("n")
            if group in FAILED_GROUPS and cur is None:
                check = next((k for k in cell.get("checks") or [] if k.get("state") == cell.get("state")), {})
                i = i_of.get(n)
                lon, lo = held if held else (None, None)
                known = lon is not None and i is not None
                cur = dict(c=pos, pr=pr_of.get(n), n=i, state=cell.get("state"), check=check.get("check"),
                           detail=check.get("detail"), end=None, lon=lon, lo=lo, wn=i - lon if known else 0,
                           sus=[r["pr"] for r in rows if known and lon < r["i"] < i
                                and (r.get("work") or {}).get("prod", 0) > 0])
                out.append(cur)
            elif group in HELD:
                if cur is not None:
                    cur["end"], cur = pr_of.get(n), None
                held = (i_of.get(n), pr_of.get(n))
    return out


def _flap(cells):
    """The replay's single checks, each a (criterion, check, platform) followed from merge to merge: how many it
    followed, how many ever stopped holding, and how many stopped, held again and stopped a second time."""
    runs = {}
    for cid, seen in cells.items():
        for cell in seen:
            for k in cell.get("checks") or []:
                group = REPLAY_GROUP.get(k.get("state"))
                how = "fail" if group in FAILED_GROUPS else "held" if group in HELD else None
                runs.setdefault((cid, k.get("check"), k.get("platform")), []).append(how)
    stopped = twice = 0
    for seq in runs.values():
        fails, last = 0, None
        for how in seq:
            if how == "fail" and last != "fail":
                fails += 1
            if how is not None:
                last = how
        stopped += fails > 0
        twice += fails > 1
    return dict(series=len(runs), stopped=stopped, twice=twice)


def _merge_view(crit, merges, events, finds, cs, ms, ls, future=None):
    """What the merge graph prints for one view, all Days or one Day (`cs` its criteria, `ms` its merges, `ls` its
    merges none cites): the verdict tiles, the findings by group, the stops grouped by suspect window, the doubtful
    citations, and each row's counts."""
    inc, by_pr = set(cs), {m["pr"]: m for m in merges}
    evs = [k for k, e in enumerate(events) if e["c"] in inc]
    sel = [crit[i] for i in cs]
    live, gone = [c for c in sel if not c["rep"]], [c for c in sel if c["rep"]]

    def n(cs_, sts):
        return sum(1 for c in cs_ if c["st"] in sts)

    unrun, why = [c for c in live if c["st"] == "none"], {}
    for c in unrun:
        why[c["why"]] = why.get(c["why"], 0) + 1
    due = [c for c in live if c["st"] == "due"]
    later = f"{' and '.join(_day_name(f['day']) for f in future)} are not due: no spec yet" if future else ""
    verdict = [
        dict(sw="st ok", n=n(live, ["ok"]), label="hold, with a break on purpose recorded", sub=""),
        dict(sw="st un", n=n(live, ["un"]), label="hold, with no break on purpose recorded",
             sub="the test was never seen to fail"),
        dict(sw="st bad", n=n(live, ["bad", "stale"]), label="not holding, and still in force",
             sub=", ".join(c["id"] for c in live if c["st"] in ("bad", "stale"))),
        dict(sw="st none", n=len(unrun), label="the replay does not run",
             sub=", ".join(f"{v} {k}" for k, v in why.items())),
        dict(sw="st due", n=len(due), label="written, not built yet",
             sub=" · ".join(x for x in (", ".join(f"{c['id']}: {c['why']}" for c in due), later) if x)),
        dict(sw="tri", n=len(gone), label="replaced by a later criterion",
             sub=f"{n(gone, ['bad', 'stale'])} not holding when last run" if gone else ""),
    ]
    shown = [f for f in finds if (f["pr"] in ls if f["kind"] == "loose" else f["c"] in inc)]
    piles = {}
    for k in evs:
        piles.setdefault((events[k]["pr"], events[k]["lo"]), []).append(k)
    piled = sorted(piles.values(), key=lambda p: (-len(p), events[p[0]]["pr"] or 0))
    doubt = sorted((i, m) for m in ms for i in by_pr[m]["lands"] if i in inc and i in by_pr[m]["early"])
    by_day, stopped = {}, {}
    for m in ms:
        by_day.setdefault(by_pr[m]["day"], []).append(m)
    for k in evs:
        stopped[events[k]["pr"]] = stopped.get(events[k]["pr"], 0) + 1
    return dict(criteria=len(cs), events=len(evs), merges=list(ms), loose=list(ls), verdict=verdict,
                finds={k: [f["n"] for f in shown if f["kind"] == k] for k in ("fix", "retired", "replaced", "back", "loose")},
                piles=[dict(e=p[0], n=len(p), pr=events[p[0]]["pr"], ids=[crit[events[k]["c"]]["id"] for k in p])
                       for p in piled],
                pile_merges=len({events[k]["pr"] for k in evs}),
                doubt=[f"{crit[i]['id']}→#{m}" for i, m in doubt],
                drawn=len(ms), dead=sum(1 for m in ms if not by_pr[m]["rp"]),
                nocite=[m for m in ms if by_pr[m]["nocite"]],
                stopped={str(pr): k for pr, k in stopped.items() if pr is not None},
                rows=[dict(day=day, ran=sum(1 for m in prs if by_pr[m]["rp"]), drawn=len(prs),
                           stopped=sum(stopped.get(m, 0) for m in prs),
                           nocite=sum(1 for m in prs if by_pr[m]["nocite"]))
                      for day, prs in sorted(by_day.items())])


def _merge_crit(c, seen, pr_of):
    """One criterion as the merge graph draws it: its stripe (`nt`, the tests it names), what it cites, and its cell in
    the strip (`st`), from its page state while it is due and from the replay's last report after."""
    state, last = c.get("state"), seen[-1].get("state") if seen else None
    if state in ("open", "building"):
        st, why = "due", "not ticked at its Day's close" if state == "open" else "its Day is not closed yet"
    else:
        st, why = MERGE_ST.get(last, "none"), last or "never replayed"
    return dict(id=c.get("id"), day=c.get("day"), tag=c.get("tag"), nt=len(c.get("tests") or []),
                prs=list(c.get("prs") or []), rep=list(c.get("replaced_by") or []),
                txt=c.get("plain") or c.get("claim") or "", st=st, why=why,
                lp=pr_of.get(seen[-1].get("n")) if seen else None, nc=len(seen))


def uncited_merges(d):
    """The merges no criterion cites that changed product code, in merge order: a code or other merge (not a Day's
    spec or close) with product lines, not a short spec's (a `change/` branch). #235's rule, and the one list the merge
    graph's "No criterion cites it" rows (`loose`) and the gene's beads are both drawn from: [{pr, title, date, prod}]."""
    cited = {p for c in d.get("criteria_index") or [] if isinstance(c, dict) for p in c.get("prs") or []}
    rows = sorted((r for r in d.get("rows") or [] if r.get("pr")), key=lambda r: r.get("i", 0))
    return [dict(pr=r["pr"], title=r.get("title", ""), date=r.get("date", ""), prod=(r.get("work") or {}).get("prod", 0))
            for r in rows if r["pr"] not in cited and (r.get("work") or {}).get("prod", 0) > 0
            and r.get("kind") in ("code", "other") and not (r.get("branch") or "").startswith("change/")]


def merge_graph(d):
    """The merge graph: every merge a criterion cites, or that changed product code and none cites, as rows over the
    spec's criteria, one stripe each; the stops the replay saw, each with its suspect window; and everything the page
    prints about them, counted here for all Days (`all`) and for each Day (`by_day`). `d` is spec-drift's
    data, its criteria given their state by `criterion_states` first. A merge none cites is `loose` when it changed
    product code, is a code or other merge (not a Day's spec or close), and is not a short spec's (a `change/` branch,
    whose criteria in `specs/changes/` cite it and the page does not draw). A merge where the replay first saw a stop,
    or saw it hold again, is drawn too, marked `nocite` with which of the two it was."""
    rows = sorted((r for r in d.get("rows") or [] if r.get("pr")), key=lambda r: r.get("i", 0))
    index = [c for c in d.get("criteria_index") or [] if isinstance(c, dict)]
    replay, now = d.get("replay") or {}, d.get("now") or {}
    rmerges = sorted(replay.get("merges") or [], key=lambda m: m.get("n", 0))
    row_at = {r["pr"]: r for r in rows}
    # a cell's n is the replay's count of merges; a row's i is the page's: the pull request ties them
    pr_of = {m.get("n"): m.get("pr") for m in rmerges}
    i_of = {m.get("n"): row_at[m["pr"]]["i"] for m in rmerges if m.get("pr") in row_at}
    cells = _cells(replay)
    crit = [_merge_crit(c, cells.get(c.get("id"), []), pr_of) for c in sorted(index, key=lambda c: c.get("day") or 0)]
    cited, ran = {p for c in crit for p in c["prs"]}, {m.get("pr") for m in rmerges}
    followed = {c["id"]: cells.get(c["id"], []) for c in crit}
    events = _merge_events(crit, followed, i_of, pr_of, rows)
    # where the replay first saw a stop, or saw it hold again: drawn whether or not a criterion cites the merge, or
    # the stop would have no row to sit in
    stop_at, held_at = {e["pr"] for e in events}, {e["end"] for e in events}
    seen = (stop_at | held_at) - {None}
    merges, skipped, uncited = [], {}, uncited_merges(d)
    loose_prs = {u["pr"] for u in uncited}
    for r in rows:
        w = r.get("work") or {}
        loose = r["pr"] in loose_prs
        if r["pr"] not in cited and r["pr"] not in seen and not loose:
            skipped[r.get("kind")] = skipped.get(r.get("kind"), 0) + 1
            continue
        merges.append(dict(pr=r["pr"], day=r.get("day"), kind=r.get("kind"), title=r.get("title", ""),
                           date=r.get("date", ""), n=r.get("i"), prod=w.get("prod", 0), test=w.get("test", 0),
                           spec=w.get("spec", 0), tool=w.get("tooling", 0), rp=r["pr"] in ran, loose=loose,
                           lands=[], early=[],
                           # drawn only because the replay saw a stop start, or end, at it: no criterion cites it
                           nocite=[] if r["pr"] in cited or loose
                           else [k for k, at_ in (("stop", stop_at), ("held", held_at)) if r["pr"] in at_]))
    at = {m["pr"]: m for m in merges}
    for i, c in enumerate(crit):
        for p in c["prs"]:
            if p in at:
                at[p]["lands"].append(i)
                if (at[p]["day"] or 0) < (c["day"] or 0):
                    at[p]["early"].append(i)
    # one finding per criterion that ever stopped holding, then one per merge none cites, numbered as the bar runs;
    # a stop whose replacement chain ends in a criterion that holds is settled ("replaced"), else still read ("retired")
    by_id = {c["id"]: c for c in crit}

    def chain_end(c):
        for _ in range(9):  # the page's chain() walks as far
            if not c["rep"] or c["rep"][0] not in by_id:
                break
            c = by_id[c["rep"][0]]
        return c

    finds = []
    for i, c in enumerate(crit):
        ev = [e for e in events if e["c"] == i]
        if ev:
            kind = ("back" if all(e["end"] for e in ev) else "fix" if not c["rep"]
                    else "replaced" if chain_end(c)["st"] in ("ok", "un") else "retired")
            finds.append(dict(kind=kind, c=i))
    settled = {f["c"] for f in finds if f["kind"] == "replaced"}
    finds += [dict(kind="loose", pr=m["pr"]) for m in merges if m["loose"]]
    for k, f in enumerate(finds, 1):
        f["n"] = k
    find_of = {f["c"]: f["n"] for f in finds if "c" in f}
    for e in events:
        e["find"] = find_of.get(e["c"])
    spec_days = {x.get("day") for x in d.get("days") or []}
    names = ((d.get("meta") or {}).get("where") or {}).get("names") or {}
    commitments = (d.get("plan") or {}).get("commitments") or []
    future = [dict(day=day, title=names.get(str(day), ""),
                   ho=sum(1 for h in d.get("hand_offs") or [] if h.get("to") == day),
                   pc=sum(1 for p in commitments if p.get("owner_day") == day))
              for day in d.get("order") or [] if day not in spec_days]
    days = [dict(day=x["day"], title=x.get("title", "")) for x in sorted(d.get("days") or [], key=lambda x: x["day"])
            if any(c["day"] == x["day"] for c in crit)]
    all_at = [m.get("pr") for m in rmerges if m.get("sample") == "all"]
    states = {}
    for cell in replay.get("cells") or []:
        states[cell.get("state")] = states.get(cell.get("state"), 0) + 1
    wins = [e["wn"] for e in events if e["lon"] is not None]
    per = {}
    for e in events:
        per[e["c"]] = per.get(e["c"], 0) + 1
    loose = [m["pr"] for m in merges if m["loose"]]
    groups = (d.get("test_inventory") or {}).get("groups") or []
    out = dict(head=(now.get("head") or "")[:7], last_pr=now.get("last_pr"), generated=now.get("generated") or "",
               crit=crit, merges=merges, events=events, finds=finds, days=days, future=future, skipped=skipped,
               skipped_total=sum(skipped.values()), cells=len(replay.get("cells") or []), replayed_merges=len(rmerges),
               first_replayed_pr=rmerges[0].get("pr") if rmerges else None,
               newest_pr=rmerges[-1].get("pr") if rmerges else None, all_at=all_at,
               at_all=sum(1 for e in events if e["pr"] in all_at), states=states, nyf=states.get("not yet in force", 0),
               tests_cited=len({t for c in index for t in c.get("tests") or []}),
               inventory={g.get("key"): g["tests"] if isinstance(g.get("tests"), int) else len(g.get("tests") or [])
                          for g in groups},
               win=dict(min=min(wins), max=max(wins)) if wins else dict(min=0, max=0),
               flap=dict(_flap(followed), crit_twice=sum(1 for k in per.values() if k > 1)),
               early_n=sum(len(m["early"]) for m in merges),
               # a stop not come back is open, unless a criterion that holds has replaced it
               open_events=sum(1 for e in events if not e["end"] and e["c"] not in settled),
               replaced_events=sum(1 for e in events if not e["end"] and e["c"] in settled),
               nocite=[m["pr"] for m in merges if m["nocite"]], uncited=uncited)
    out["all"] = _merge_view(crit, merges, events, finds, list(range(len(crit))), [m["pr"] for m in merges], loose,
                             future)
    out["by_day"] = {}
    for x in days:
        day = x["day"]
        evs = [e for e in events if crit[e["c"]]["day"] == day]
        ms = [m["pr"] for m in merges if m["day"] == day or any(crit[i]["day"] == day for i in m["lands"])
              or any(m["pr"] in (e["pr"], e["end"]) or m["pr"] in e["sus"] for e in evs)]
        out["by_day"][str(day)] = _merge_view(crit, merges, events, finds,
                                              [i for i, c in enumerate(crit) if c["day"] == day], ms,
                                              [m["pr"] for m in merges if m["loose"] and m["day"] == day])
    return out
