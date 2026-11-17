"""spec-drift.py's newer views: one function per section of the page, each counted here and written under its own
key of spec-drift.json, so that `docs/dashboard/dashboard.js` only lays them out and counts nothing of its own.
`scripts/demo-data.py` calls the same functions on its made-up data.

The page used to work out each criterion's state in the browser (`promises()` in dashboard.js); it is worked
out here now, in `criterion_states`, and the browser reads it.

A criterion is *in force* while no later criterion's `Replaces:` line names it (its `replaced_by` is empty):
`scripts/plan-links.py`, graph 12 and the gene count the same set.
"""

# Each replay state, as the group a reader sees it in: dashboard.js's REPLAY_LOOK keeps the same groups, and
# tests/test_dashboard_views.py holds the two to each other.
REPLAY_GROUP = {
    "code broken": "broken",
    "test weakened": "repair",
    "break no longer applies": "repair",
    "not runnable": "skipped",
    "not applicable on this platform": "skipped",
    "live only": "skipped",
    "holds, never broken": "unproven",
    "holds": "proven",
    "not yet in force": None,
}
# A Day the page treats as over: its criteria are no longer being built.
FINISHED = ("done", "closed", "cut")
FAILED_GROUPS = ("broken", "repair")

# The gene's classes, one per commitment, in the order the page shows them.
GENE_CLASSES = ("proved", "unproved", "unreplayable", "repair", "fails", "unbuilt", "spliced", "untranscribed")


def _cells(replay):
    """Each criterion's replay cells, oldest first."""
    out = {}
    for cell in sorted((replay or {}).get("cells") or [], key=lambda c: c.get("n", 0)):
        out.setdefault(cell.get("criterion"), []).append(cell)
    return out


def _stops(seen, pr_of):
    """Each time the replay saw a criterion stop holding (broken, or needing repair): the pull request it was first
    reported at, what the replay reported, and the pull request it was seen holding again by, None if never."""
    out, last = [], None
    for cell in seen:
        group = REPLAY_GROUP.get(cell.get("state"))
        if group in FAILED_GROUPS and last is None:
            last = dict(pr=pr_of.get(cell.get("n")), state=cell.get("state"), held=None)
            out.append(last)
        elif group in ("proven", "unproven") and last is not None:
            last["held"], last = pr_of.get(cell.get("n")), None
    return out


def criterion_states(index, days, replay):
    """Give each criterion of `index` its `state`, as the page's promise tiles read it; `back`: the replay saw
    it stop holding (broken, or needing repair) at an earlier merge, and it holds now; and `seen`: how many merges
    the replay ran it at, the last one's pull request, and each stop (`_stops`)."""
    by_day = {d.get("day"): d for d in days}
    cells = _cells(replay)
    pr_of = {m.get("n"): m.get("pr") for m in (replay or {}).get("merges") or []}
    for c in index:
        if not isinstance(c, dict):
            continue
        day, seen = by_day.get(c.get("day")), cells.get(c.get("id"), [])
        group = REPLAY_GROUP.get(seen[-1].get("state")) if seen else None
        c["state"] = ("building" if not day or day.get("status") not in FINISHED
                      else "replaced" if c.get("replaced_by") else "open" if c.get("ticked") is False
                      else group or "unchecked")
        c["back"] = bool(group in ("proven", "unproven")
                         and any(REPLAY_GROUP.get(x.get("state")) in FAILED_GROUPS for x in seen[:-1]))
        c["seen"] = dict(merges=len(seen), last=pr_of.get(seen[-1].get("n")) if seen else None,
                         stops=_stops(seen, pr_of))
    return index


def _class(states):
    """A named commitment's class, from the states of the criteria in force that name it."""
    s = set(states)
    if "broken" in s:
        return "fails"
    for state, cls in (("proven", "proved"), ("unproven", "unproved"), ("skipped", "unreplayable"), ("repair", "repair")):
        if state in s:
            return cls
    return "unbuilt"


def _quote(c, text=""):
    """One quote of the plan as the gene draws it: the criterion that makes it, and the words it quotes."""
    return dict(id=c["id"], day=c.get("day"), tag=c.get("tag"), state=c.get("state"), back=bool(c.get("back")),
                gone=bool(c.get("replaced_by")), quote=text)


def gene(plan, index, days):
    """The gene: every commitment of the plan in exactly one class, read down from the plan through the criteria that
    quote it (as written, then in force) to the state of their code. `uncovered` is what is due by the last
    finished Day and named by no criterion in force: graph 12's "should be covered by now" set. `ring` is every
    criterion whose Plan: line names no commitment, and `off` the ones of them in force. None with no plan."""
    if not plan or not plan.get("commitments"):
        return None
    links, said, owed = plan.get("links") or {}, plan.get("said") or {}, plan.get("overdue") or {}
    crit = {c["id"]: c for c in index if isinstance(c, dict) and c.get("id") in links}
    closed_to = max([d["day"] for d in days if d.get("status") in FINISHED], default=0)
    naming = {}
    for cid, named in links.items():
        words = said.get(cid) or []
        for k, pid in enumerate(named if cid in crit else []):
            naming.setdefault(pid, []).append(_quote(crit[cid], words[k] if k < len(words) else ""))
    rows, counts = [], dict.fromkeys(GENE_CLASSES, 0)
    for p in plan["commitments"]:
        written = naming.get(p["id"], [])
        live = [q for q in written if not q["gone"]]
        owner, rule = p.get("owner_day"), bool(p.get("rule"))
        if live:
            cls = _class([q["state"] for q in live])
            sub = ("full" if all(q["state"] == "proven" for q in live) else "part") if cls == "proved" else None
        elif written:
            cls, sub = "spliced", None
        else:
            cls = "untranscribed"
            sub = "rule" if rule else "later" if owner is None or owner > closed_to else "due"
        counts[cls] += 1
        rows.append(dict(id=p["id"], short=p.get("short", ""), section=p.get("section", ""),
                         arm="first" if p["id"].startswith("P") else "added", rule=rule, owner_day=owner,
                         change=p.get("change"), note=p.get("note", ""), text=p.get("text", ""),
                         settled_by=owed.get(p["id"]), written=written, cells=live, cls=cls, sub=sub,
                         criteria=len({q["id"] for q in written}),
                         tally={s: sum(1 for q in live if q["state"] == s) for s in sorted({q["state"] for q in live})},
                         uncovered=not rule and owner is not None and owner <= closed_to and not live))
    # an arm keeps a section's commitments together, where the section first comes up: one the plan added later
    # sits with its section, not at the end
    first = {}
    for i, r in enumerate(rows):
        first.setdefault((r["arm"], r["section"]), i)
    rows.sort(key=lambda r: (r["arm"] != "first", first[(r["arm"], r["section"])]))
    ring = [_quote(c) for cid, c in sorted(crit.items(), key=lambda kv: (kv[1].get("day") or 0, kv[0])) if not links[cid]]
    quoting = {q["id"]: q for r in rows for q in r["written"]}
    in_force = [q for q in quoting.values() if not q["gone"]]
    return dict(closed_to=closed_to, commitments=rows, counts=counts, ring=ring, off=[q for q in ring if not q["gone"]],
                proved_full=sum(1 for r in rows if r["sub"] == "full"),
                untranscribed={k: sum(1 for r in rows if r["cls"] == "untranscribed" and r["sub"] == k)
                               for k in ("rule", "later", "due")},
                stacks=dict(written=max([len(r["written"]) for r in rows], default=0),
                            cells=max([len(r["cells"]) for r in rows], default=0)),
                uncovered=[r["id"] for r in rows if r["uncovered"]],
                quotes=sum(len(r["written"]) for r in rows), live_quotes=sum(len(r["cells"]) for r in rows),
                criteria=len(crit), in_force=sum(1 for c in crit.values() if not c.get("replaced_by")),
                # the criteria that quote the plan at least once: how many, and of those in force, how they stand
                quoting=dict(criteria=len(quoting), in_force=len(in_force),
                             not_proved=sum(1 for q in in_force if q["state"] != "proven"),
                             came_back=sum(1 for q in in_force if q["back"])),
                named=sum(1 for r in rows if r["written"]), live=sum(1 for r in rows if r["cells"]),
                changed=sum(1 for r in rows if r["change"]), rewrites=len(plan.get("rewrites") or []))


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
                finds={k: [f["n"] for f in shown if f["kind"] == k] for k in ("fix", "retired", "back", "loose")},
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
    merges, skipped = [], {}
    for r in rows:
        w = r.get("work") or {}
        loose = (r["pr"] not in cited and w.get("prod", 0) > 0 and r.get("kind") in ("code", "other")
                 and not (r.get("branch") or "").startswith("change/"))
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
    # one finding per criterion that ever stopped holding, then one per merge none cites, numbered as the bar runs
    finds = []
    for i, c in enumerate(crit):
        ev = [e for e in events if e["c"] == i]
        if ev:
            finds.append(dict(kind="back" if all(e["end"] for e in ev) else "retired" if c["rep"] else "fix", c=i))
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
               early_n=sum(len(m["early"]) for m in merges), open_events=sum(1 for e in events if not e["end"]),
               nocite=[m["pr"] for m in merges if m["nocite"]])
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


def _finished(day):
    return bool(day) and day.get("status") in FINISHED


def _round(x):
    """As the page's Math.round: a half goes up."""
    return None if x is None else int(x + 0.5)


def _plain(s):
    return str(s or "").replace("`", "")


def _placed(d):
    """The Day each merge belongs to, as the page places it (dashboard.js, PLACED): the Day its branch names; for a
    merge no Day owns, the furthest Day begun when it merged, and whether that Day was open or closed by then. A code
    merge or a close no Day owns is counted as other work."""
    order = d.get("order") or []
    rank = lambda day: order.index(day) if day in order else day  # noqa: E731
    top, shut, out = None, set(), []
    for r in d.get("rows") or []:
        own = r.get("own_day") if r.get("pr") and r.get("own_day") is not None else None
        if own is not None and (top is None or rank(own) > rank(top)):
            top = own
        kind = r.get("kind") if r.get("kind") in ("origin", "spec", "code", "close", "other") else "other"
        if r.get("pr") and own is None and kind in ("code", "close"):
            kind = "other"
        if not r.get("pr"):
            whose = "before Day 1"
        elif own is not None:
            whose = f"Day {own}"
        elif top is None:
            whose = "outside any Day, merged before Day 1 began"
        else:
            whose = f"outside any Day, merged {f'after Day {top} closed' if top in shut else f'while Day {top} was open'}"
        if own is not None and r.get("kind") == "close":
            shut.add(own)
        out.append(dict(own=own, kind=kind, whose=whose))
    return out


def _stamp(d):
    now = d.get("now") or {}
    return dict(head=(now.get("head") or "")[:7], last_pr=now.get("last_pr"), generated=now.get("generated") or "")


def where_ring(d):
    """"Where we are" as a ring: one segment per Day plan.md numbers, in its order and its phases, a gate at each stop
    and the place the work stands, with everything the ring and its lists print. A Day's state is the tiles' (the
    page's whereNow): closed, closed with a promise not ticked, in progress, spec written, next, or provisional; a
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


def reading(d):
    """Graph 1 read as a gene: every merge in order on one strand, a Day's merges as a block (its main span, and any
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
