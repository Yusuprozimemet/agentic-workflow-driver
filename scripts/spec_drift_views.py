"""spec-drift.py's newer views: one function per section of the page, each counted here and written under its own
key of spec-drift.json, so that `docs/dashboard/dashboard.js` only lays them out and counts nothing of its own.
`scripts/demo-data.py` calls the same functions on its made-up data.

The page used to work out each criterion's state in the browser (`promises()` in dashboard.js); it is worked
out here now, in `criterion_states`, and the browser reads it.

A criterion is *in force* while no later criterion's `Replaces:` line names it (its `replaced_by` is empty):
`scripts/plan-links.py`, graph 12 and the gene count the same set.
"""

import datetime
import re

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


# The replay's states that count as re-checked: graph 3's ring and its trust strip count the same five.
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


def _order(cid):
    """A criterion's place in the order built: its Day, then its number."""
    return tuple(
        int(x) for x in "".join(ch if ch.isdigit() else " " for ch in str(cid)).split()
    ) or (0,)


def _runs(steps):
    """The run log's steps, read by RUN_USE: a step may be in more than one (a crash that parked)."""
    return dict(
        loop=[s.get("pr") for s in steps if s.get("ended") == "merged" and not s.get("parks")],
        park=[
            dict(pr=s.get("pr"), day=s.get("day"), by=p.get("by"), line=_plain(p.get("line")))
            for s in steps
            for p in s.get("parks") or []
        ],
        stop=[s.get("pr") for s in steps if s.get("ended") == "stopped"],
        recover=[
            dict(
                pr=s.get("pr"),
                crashes=s.get("crashes"),
                sessions=len(s.get("sessions") or []),
                ended=s.get("ended"),
            )
            for s in steps
            if (s.get("crashes") or 0) > 0
        ],
        open=[s.get("pr") for s in steps if s.get("ended") == "open"],
    )


def _tally(cells):
    out = {}
    for x in cells:
        out[x["state"]] = out.get(x["state"], 0) + 1
    return out


def protein(d):
    """Graphs 3 to 5 as proteins: one chain per ability, one cell per criterion in the order built (its Day, then its
    number), each in the state criterion_states gave it; the criteria that name no ability make a chain of their own.
    A criterion is drawn once, under the first ability it names (the folded graph 5's rule, so the two count the
    same cells per ability); naming none, it sits in the chain of its own. `proven` of `rechecked` counts only the states the replay re-checks; a criterion in
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


# Graph 7's gates, in the order work passes them: `key` is the found: value a Defect line names, `name` graph 7's
# name for it and `at` how a sentence names it (they moved here from dashboard.js's GATES unchanged). `label`, `sub`
# and `does` are the proofreading stream's words for it, as the mockup at #228 has them.
PRF_GATES = (
    dict(key="auditor", name="Auditors, before any code", at="the auditors", label="The auditors",
         sub="plan-auditor, spec-auditor",
         does="Before any code, the spec-auditor runs every check in the Day's spec on the code as it is and tries "
         "to break every hold; on a phase's first Day the plan-auditor reads the phase. The Notes do not say which "
         "auditor."),
    dict(key="spec-change PR", name="The spec-change pull request", at="the spec-change pull request",
         label="The spec-change pull request", sub="",
         does="The pull request that fixes what the auditors found in the Day's spec, before any track starts. A "
         "defect found while writing it is caught here."),
    dict(key="seen red", name="A test seen failing", at="a test seen failing", label="A test seen failing",
         sub="seen-red.py",
         does="Runs the branch's new tests on main's code: they must fail, for the reason the spec gives."),
    dict(key="break on purpose", name="A break on purpose", at="a break on purpose", label="A break on purpose",
         sub="break.py",
         does="Breaks the code on purpose and runs the check twice with the break in. A test that still passes "
         "would not catch a real failure."),
    dict(key="review", name="The main session's diff review", at="the diff review", label="The diff review",
         sub="the main session",
         does="The main session reads the implementer's diff before it runs the checks and commits."),
    dict(key="work", name="Noticed during the work", at="the work", label="Noticed in the work", sub="no gate: a leak",
         does="No gate: a defect someone noticed while working, in a track or the session. A catch by a gate the "
         "Notes do not name is counted here too."),
    dict(key="close", name="The close", at="the close", label="The close", sub="each criterion ticked",
         does="The closing pull request ticks every criterion with its evidence and writes the Day's Notes. A "
         "defect found doing it is caught here."),
    dict(key="rehearsal", name="The close's rehearsal", at="the rehearsal", label="The close's rehearsal",
         sub="in CI, counted from Day 12",
         does="Replays the closing branch as its merge into main would, before the merge. Until Day 12 the Notes "
         "named its catches evidence replay: they sit with the replay after the merge."),
    dict(key="evidence replay", name="The evidence replay", at="the evidence replay", label="The evidence replay",
         sub="on the closing merge",
         does="evidence.yml on the closing merge commit, checked before the next step. Before Day 12 it holds the "
         "rehearsal's catches too."),
    dict(key="dashboard", name="The dashboard", at="the dashboard", label="The dashboard",
         sub="seen on the published page", does="A defect seen on the published page, after the Day closed."),
    dict(key="Day review", name="A later Day's review", at="a later Day's review", label="A later Day's review",
         sub="a later Day reads it", does="A defect a later Day found in a closed Day's work."),
)
# Graph 7's phases, the bar above its pipe (dashboard.js's PHASES, unchanged): the four layers of checking, in order,
# and the gates each holds. "Noticed in the work" sits in the second: it leaves the stream there, with no gate.
PRF_LAYERS = (
    dict(name="Before any code", bio="reading the template", gates=("auditor", "spec-change PR"),
         what="The auditors read the spec against the code before anything is copied from it."),
    dict(name="While writing", bio="proofreading", gates=("seen red", "break on purpose", "review", "work"),
         what="Checks run as each track is written: the test seen failing, the break on purpose, the diff review."),
    dict(name="At the close", bio="repair after the copy", gates=("close", "rehearsal"),
         what="The Day is finished and read again: every criterion is ticked with its evidence."),
    dict(name="After the merge", bio="surveillance", gates=("evidence replay", "dashboard", "Day review"),
         what="The Day is closed: the evidence replay, the published page and later Days find what is left."),
)
PRF_CAUSES = ("spec", "process", "implementation", "environment", "other")
PRF_GUARDS = ("step-guard", "read-guard", "auditor-guard")  # the hooks' order on graph 7 (HOOKS); others after


def _tag(value):
    """A Defect line's found: or cause: value as graph 7 read it (dashboard.js, tagOf): older Notes write
    "The auditor (spec-auditor)"."""
    v = "" if value is None else str(value)
    return re.sub(r" \(.*\)$", "", re.sub(r"^the ", "", v.strip().lower()))


def gate_of(value):
    """The gate a found: value names, by graph 7's rule (dashboard.js's gateOf up to #237): "Day N review" is a later
    Day's review; a gate's key, in any case; anything else (a track, a review nobody named, the session) was noticed
    during the work."""
    f = _tag(value)
    if re.fullmatch(r"day \d+ review", f):
        return "Day review"
    return next(
        (g["key"] for g in PRF_GATES if g["key"].lower() == f and g["key"] not in ("work", "Day review")), "work"
    )


def _when(stamp):
    """A timestamp as a moment, or None when it does not read as one. A stamp with no offset is taken as UTC."""
    try:
        t = datetime.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)


def _prf_missing(d):
    """Why the stream cannot be drawn: the dashboard-data branch is missing, or has no gates.json. None when it can."""
    src = d.get("data")
    why = "so the gates' runs and cost are not known and the stream is not drawn."
    if not src:
        return None
    if not src.get("commit"):
        return f"the {src.get('branch')} branch is missing, {why}"
    if "gates.json" in (src.get("absent") or []):
        return f"the {src.get('branch')} branch has no gates.json, {why}"
    return None


def _prf_defects(d):
    """Every Defect line of every Day, in the Days' order and then the Notes', at the gate and in the layer graph 7
    puts it: its cause, the Day that made it (a number, "none", or None when the line does not say), whether it
    escaped (made on another Day) or came back (it names an earlier defect), and who noticed one caught in the work."""
    back = {r.get("id"): r.get("same_as") for r in (d.get("defect_recurrence") or {}).get("recurrences") or []}
    layer_of = {k: i for i, L in enumerate(PRF_LAYERS) for k in L["gates"]}
    out = []
    for day in sorted(d.get("days") or [], key=lambda x: x.get("day")):
        n = day.get("day")
        for i, x in enumerate(day.get("defects") or []):
            gate, cause, f, said = gate_of(x.get("found")), _tag(x.get("cause")), _tag(x.get("found")), x.get("made") or ""
            m = re.fullmatch(r"Day 0*(\d+)", said, re.I)
            made = int(m.group(1)) if m else "none" if re.fullmatch(r"none", said, re.I) else None
            xid = x.get("id")
            by = None if gate != "work" else "track" if re.match(r"track\b", f) else "self" if f == "self" else "other"
            out.append(
                dict(
                    id=xid or f"Day {n}, defect {i + 1}", day=n, i=i, cause=cause if cause in PRF_CAUSES else "other",
                    gate=gate, layer=layer_of[gate], made=made, escaped=isinstance(made, int) and made != n,
                    back=bool(xid) and xid in back, same_as=back.get(xid) if xid else None,
                    noticed=x.get("found") if gate == "work" and x.get("found") else None, by=by,
                )
            )
    return out


def _prf_late(d, defects):
    """The Days with a defect whose pull requests did not all merge by the count: a gate's dollars end at the count,
    so their catches do not share them (graph 7's rule, dayInCount)."""
    counted_at = (d.get("counted") or {}).get("at")
    cms = _when(counted_at) if counted_at else None
    if cms is None:
        return []
    times = [p for p in (d.get("clock") or {}).get("prs") or [] if p.get("opened") and p.get("merged")]
    after = {p.get("day") for p in times if (_when(p["merged"]) or cms) > cms}
    return sorted({o["day"] for o in defects} & after)


def _prf_hooks(d):
    """The hooks' refusals per guard, all dates, and the hooks gate's runs and cost: beside the stream, not in it."""
    refused = {}
    for r in d.get("refusals") or []:
        refused[r.get("guard")] = refused.get(r.get("guard"), 0) + (r.get("refused") or 0)
    order = [g for g in PRF_GUARDS if g in refused] + sorted(str(g) for g in refused if g not in PRF_GUARDS)
    h = next((g for g in (d.get("gate_report") or {}).get("gates") or [] if g.get("gate") == "hooks"), None)
    return dict(
        guards=[dict(guard=g, refused=refused[g]) for g in order if refused[g]],
        refused=sum(refused.values()),
        runs=h.get("runs") if h else None,
        cost=h.get("cost") if h else None,
    )


def _prf_ci(d):
    """CI on every pull request, as graph 7 counts it: per workflow, the pull requests it failed on
    (verification[].failed_in), of those merged; and how many failed at least one."""
    failed, checked = {}, d.get("verification") or []
    for v in checked:
        for w in set(v.get("failed_in") or []):
            failed[w] = failed.get(w, 0) + 1
    return dict(
        workflows=[dict(name=w, failed=n) for w, n in sorted(failed.items(), key=lambda x: (-x[1], x[0]))],
        merged=sum(1 for r in d.get("rows") or [] if r.get("pr")),
        failed_any=sum(1 for v in checked if v.get("failed_in")),
        rehearsal=failed.get("Evidence replay", 0),
        counted=bool(checked),
    )


def _prf_reader(days):
    """The second reader (relabel.py and the defect-rater): tags read differently, of the tags read, over the Days
    read; and the same for the tag that decides the tray, the gate (`stage`)."""
    read = [x["relabel"] for x in days if x.get("relabel")]
    if not read:
        return None
    pairs = [p for r in read for p in r.values()]
    stage = [r["stage"] for r in read if r.get("stage")]
    return dict(
        differ=sum(b - a for a, b in pairs),
        tags=sum(b for _, b in pairs),
        stage=[sum(b - a for a, b in stage), sum(b for _, b in stage)] if stage else None,
    )


def proofreading(d):
    """Graph 7 as one stream of defects through four layers of checking. Every count is graph 7's (its rules moved
    here from dashboard.js): each Defect line at the gate its found: names (gate_of), each gate in its phase, and a
    gate's dollars shared only over the catches of the Days whose pull requests all merged by the count. The folded
    graph 7 reads the same fields, so the two cannot disagree.

    With the dashboard-data branch or its gates.json missing, `empty` says why and the stream is not drawn; the
    defects, the gates and the layers are still counted, with no runs, cost or refusals, for graph 7 to draw."""
    missing = _prf_missing(d)
    defects = _prf_defects(d)
    total, late = len(defects), _prf_late(d, defects)
    found = (d.get("gate_report") or {}).get("gates") or []
    spent = {} if missing else {g["found"]: g for g in found if g.get("found")}
    gates = []
    for g in PRF_GATES:
        k = g["key"]
        mine, s = [o for o in defects if o["gate"] == k], spent.get(k)
        counted, cost = sum(1 for o in mine if o["day"] not in late), (s or {}).get("cost")
        gates.append(
            dict(
                g, layer=next(i for i, L in enumerate(PRF_LAYERS) if k in L["gates"]), caught=len(mine),
                causes=[sum(1 for o in mine if o["cause"] == c) for c in PRF_CAUSES],
                runs=(s or {}).get("runs"), cost=cost, in_count=counted,
                per=cost / counted if cost and cost > 0 and counted else None,
                back=sum(1 for o in mine if o["back"]), escaped=sum(1 for o in mine if o["escaped"]),
                by={b: sum(1 for o in mine if o["by"] == b) for b in ("track", "self", "other")} if k == "work" else None,
            )
        )
    layers, reached = [], total
    for L in PRF_LAYERS:
        caught = sum(g["caught"] for g in gates if g["key"] in L["gates"])
        layers.append(
            dict(
                name=L["name"], bio=L["bio"], what=L["what"], gates=list(L["gates"]), reached=reached, caught=caught,
                went_on=reached - caught, pct=_round(100 * caught / reached) if reached else 0,
                share=_round(100 * caught / total) if total else 0,
            )
        )
        reached -= caught

    def mark(pick):
        mine = [o for o in defects if pick(o)]
        return dict(n=len(mine), layers=[sum(1 for o in mine if o["layer"] == i) for i in range(len(PRF_LAYERS))])

    last = len(PRF_LAYERS) - 1
    marks = dict(
        escaped=mark(lambda o: o["escaped"]),
        back=mark(lambda o: o["back"]),
        both=sum(1 for o in defects if o["escaped"] and o["back"]),
        after_merge=layers[last]["caught"],
        shared=sum(1 for o in defects if o["back"] and o["layer"] == last),
    )
    out = dict(
        _stamp(d), counted_at=(d.get("counted") or {}).get("at"), total=total, causes=list(PRF_CAUSES),
        cause_counts={c: sum(1 for o in defects if o["cause"] == c) for c in PRF_CAUSES},
        days=sorted({o["day"] for o in defects}), gates=gates, layers=layers, leak="work", defects=defects, late=late,
        marks=marks, hooks=None if missing else _prf_hooks(d), ci=_prf_ci(d), reader=_prf_reader(d.get("days") or []),
    )
    if missing or not total:
        out["empty"] = missing or "no defect is recorded in any Day's Notes yet, so there is no stream to draw."
    return out
