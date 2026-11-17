"""spec-drift.py's newer views: one function per section of the page, each counted here and written under its own
key of spec-drift.json, so that `docs/dashboard/dashboard.js` only lays them out and counts nothing of its own.
`scripts/demo-data.py` calls the same functions on its made-up data.

The page used to work out each criterion's state in the browser (`promises()` in dashboard.js); it is worked
out here now, in `criterion_states`, and the browser reads it.

A criterion is *in force* while no later criterion's `Replaces:` line names it (its `replaced_by` is empty):
`scripts/plan-links.py`, graph 12 and the gene count the same set.
"""

import datetime
import math
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
        # `at` and `area` as the page's PLACED has them: the Day a merge is placed at (its own, or the furthest Day
        # begun; None before Day 1, the page's 0), and whether it is a pull request no Day owns.
        out.append(dict(own=own, kind=kind, whose=whose, at=own if own is not None else top,
                        area=bool(r.get("pr")) and own is None))
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


# Graph 8 as an energy budget (the mockup at #228's atp): one bead for each BUDGET_UNIT dollars, split by what the
# dollars bought and by who spent them. A row is split by pricing its tokens again with token-usage.py's own list
# prices; one that comes out more than BUDGET_OFF off its recorded cost is not split.
BUDGET_UNIT = 2
BUDGET_OFF = 0.01
BUDGET_KINDS = ("re-reading", "writing context", "writing output", "not split")
BUDGET_WHO = ("main session", "auditors", "defect-rater", "implementer", "other agents")
_TOKEN_USAGE = []


def _token_usage():
    """scripts/token-usage.py, loaded once: its PRICES and DATED are the list prices the dollars were counted with."""
    if not _TOKEN_USAGE:
        import importlib.util
        import os

        here = os.path.dirname(os.path.abspath(__file__))
        spec = importlib.util.spec_from_file_location("token_usage", os.path.join(here, "token-usage.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _TOKEN_USAGE.append(module)
    return _TOKEN_USAGE[0]


def _who(agent):
    """Who spent a row's dollars, as an index of BUDGET_WHO."""
    a = str(agent or "")
    return 0 if a == "main" else 1 if "auditor" in a else 2 if a == "defect-rater" else 3 if a == "implementer" else 4


def _priced(t, tu):
    """A token row's dollars split as [re-reading, writing context, writing output], scaled to sum to its recorded
    cost, and how far off (a fraction of the cost) its tokens priced again came; (None, None) when it is not split.
    Re-reading is the cache reads; writing context the input and the cache writes, the main session's at the 1-hour
    price and an agent's at the 5-minute one; writing output the output."""
    p = tu.PRICES.get(tu.DATED.sub("", t.get("model") or ""))
    cost = t.get("cost") or 0
    if p is None:
        return None, None
    write = p[2] if t.get("agent") == "main" else p[1]
    parts = [(t.get("cache_read") or 0) * p[3] / 1e6,
             ((t.get("input") or 0) * p[0] + (t.get("cache_write") or 0) * write) / 1e6,
             (t.get("output") or 0) * p[4] / 1e6]
    again = sum(parts)
    if abs(again - cost) > BUDGET_OFF * cost:
        return None, None
    return ([x * cost / again for x in parts] if again else [0.0, 0.0, 0.0]), (abs(again - cost) / cost if cost else 0.0)


def _lr(values, n):
    """n whole beads shared out over `values` by largest remainder: each gets the whole part of its quota of n, and
    the beads left go to the largest remainders, the earlier on a tie. They always add up to n."""
    whole = sum(values)
    if n <= 0 or whole <= 0:
        return [0] * len(values)
    quota = [n * v / whole for v in values]
    out = [int(q) for q in quota]
    for i in sorted(range(len(values)), key=lambda i: (-(quota[i] - out[i]), i))[: n - sum(out)]:
        out[i] += 1
    return out


def _budget_missing(d):
    """Why the beads cannot be drawn: the dashboard-data branch is missing, or has no token-usage.json."""
    src = d.get("data")
    why = "so the dollars are not known and the beads are not drawn."
    if not src:
        return None
    if not src.get("commit"):
        return f"the {src.get('branch')} branch is missing, {why}"
    if "token-usage.json" in (src.get("absent") or []):
        return f"the {src.get('branch')} branch has no token-usage.json, {why}"
    return None


def _budget_col(rows, split, beads):
    """One column's figures: its dollars by kind and by who, the beads of each, and its rail (the dollars past 150k;
    None when no row has the figure, as graph 8 reads a row without it: not known)."""
    k, w = [0.0] * 4, [0.0] * 5
    for t in rows:
        parts = split[id(t)]
        if parts is None:
            k[3] += t.get("cost") or 0
        else:
            for i in range(3):
                k[i] += parts[i]
        w[_who(t.get("agent"))] += t.get("cost") or 0
    known = [t for t in rows if t.get("cost_past_150k") is not None]
    main = [t for t in known if t.get("agent") == "main"]
    return dict(u=sum(t.get("cost") or 0 for t in rows), b=beads, k=k, kb=_lr(k, beads), w=w, wb=_lr(w, beads),
                p=round(sum(t["cost_past_150k"] for t in known), 6) if known else None,
                pm=round(sum(t["cost_past_150k"] for t in main), 6) if main else None,
                rp=sum(t.get("replies") or 0 for t in rows),
                nd=sum(t.get("cost") or 0 for t in rows if t.get("day") is None))


def _guard_order(guards):
    return [g for g in PRF_GUARDS if g in guards] + sorted(str(g) for g in guards if g not in PRF_GUARDS)


def budget(d):
    """Graph 8's dollars as an energy budget: beads of BUDGET_UNIT dollars in a column for each date with token rows,
    or for each Day and one for no Day. Every figure, bead and share is counted here; dashboard.js lays them out.

    The whole beads are round(total / unit), shared out over the columns by largest remainder; inside a column the
    kinds and the who are each shared out over its beads the same way. With the dashboard-data branch or its
    token-usage.json missing, `empty` says why and nothing is drawn."""
    missing = _budget_missing(d)
    tokens = [] if missing else list(d.get("tokens") or [])
    out = dict(_stamp(d), unit=BUDGET_UNIT, kinds_named=list(BUDGET_KINDS), who_named=list(BUDGET_WHO))
    if missing or not tokens:
        out["empty"] = missing or ("no token counts yet: they are counted on the maintainer's computer and pushed to "
                                   "the dashboard-data branch.")
        return out
    tu = _token_usage()
    split, offs = {}, []
    for t in tokens:
        parts, off = _priced(t, tu)
        split[id(t)] = parts
        if parts is not None:
            offs.append(off)
    cost = lambda rows: sum(t.get("cost") or 0 for t in rows)  # noqa: E731
    total = cost(tokens)
    beads = _round(total / BUDGET_UNIT)
    days = sorted(d.get("days") or [], key=lambda x: x.get("day"))
    # a column for each date, and the Days worked on it (graph 8's rule: the date is within a Day's `worked`)
    dates = sorted({t.get("date") for t in tokens})
    by_date = [[t for t in tokens if t.get("date") == x] for x in dates]
    refused = {}
    for r in d.get("refusals") or []:
        if r.get("refused"):
            mine = refused.setdefault(r.get("date"), {})
            mine[r.get("guard")] = mine.get(r.get("guard"), 0) + r["refused"]
    date_cols = []
    for x, rows, b in zip(dates, by_date, _lr([cost(r) for r in by_date], beads)):
        on = [y.get("day") for y in days if y.get("worked") and y["worked"][0] <= x <= y["worked"][1]]
        rf = refused.get(x, {})
        date_cols.append(dict(_budget_col(rows, split, b), label=x, date=x, days=on,
                              rf=[[g, rf[g]] for g in _guard_order(rf)], refused=sum(rf.values()),
                              cut=sum(t.get("cut") or 0 for t in rows)))
    # a column for each Day the token rows name (the branch the session worked on), and one for no Day
    named = sorted({t.get("day") for t in tokens if t.get("day") is not None})
    keys = named + ([None] if any(t.get("day") is None for t in tokens) else [])
    by_day = [[t for t in tokens if t.get("day") == k] for k in keys]
    day_cols = []
    for k, rows, b in zip(keys, by_day, _lr([cost(r) for r in by_day], beads)):
        seen = sorted({t.get("date") for t in rows})
        day_cols.append(dict(_budget_col(rows, split, b), label=f"Day {k}" if k is not None else "No Day", day=k,
                             dates=[seen[0], seen[-1]], n_dates=len(seen)))
    # a pill for each Day over the date columns it was worked on, in the first lane free
    pills, lanes = [], []
    for y in days:
        w = y.get("worked")
        idx = [i for i, x in enumerate(dates) if w and w[0] <= x <= w[1]]
        if not idx:
            continue
        lane = next((i for i, end in enumerate(lanes) if end < idx[0]), len(lanes))
        lanes[lane:lane + 1] = [idx[-1]]
        pills.append({"day": y.get("day"), "lane": lane, "from": idx[0], "to": idx[-1]})
    # the figures, the key's dollars and the lists
    kinds = [sum(c["k"][i] for c in date_cols) for i in range(4)]
    who = [sum(c["w"][i] for c in date_cols) for i in range(5)]
    known = [t for t in tokens if t.get("cost_past_150k") is not None]
    past = sum(t["cost_past_150k"] for t in known)
    pct = lambda x: _round(100 * x / total) if total else 0  # noqa: E731
    closed = sum(1 for y in days if _finished(y))
    states = [c.get("state") for c in d.get("criteria_index") or [] if isinstance(c, dict)]
    built = sum(1 for s in states if s and s not in ("open", "building")) if any(states) else None
    unsplit = [t for t in tokens if split[id(t)] is None]
    model = lambda t: tu.DATED.sub("", t.get("model") or "")  # noqa: E731
    main_rows = [t for t in tokens if t.get("agent") == "main"]
    main_model = max(sorted({model(t) for t in main_rows}), default=None,
                     key=lambda m: cost([t for t in main_rows if model(t) == m]))
    price = tu.PRICES.get(main_model) if main_model else None
    all_tokens = sum(t.get(k) or 0 for t in tokens for k in ("input", "cache_write", "cache_read", "output"))
    own = [c for c in day_cols if c["day"] is not None]
    no_day = sum(c["nd"] for c in date_cols)
    guards = {}
    for c in date_cols:
        for g, n in c["rf"]:
            guards[g] = guards.get(g, 0) + n
    steps = (d.get("driver_runs") or {}).get("steps")
    sessions = [s for x in steps or [] for s in x.get("sessions") or []]
    first = lambda cols, f: max(range(len(cols)), key=lambda i: (f(cols[i]), -i)) if cols else None  # noqa: E731
    out.update(
        total=total, beads=beads, kinds=kinds, who=who, kind_pct=[pct(x) for x in kinds], who_pct=[pct(x) for x in who],
        cols=dict(date=date_cols, day=day_cols), pills=pills, lanes=len(lanes),
        replies=sum(t.get("replies") or 0 for t in tokens), dates=len(dates),
        closed=closed, per_closed=total / closed if closed else None, built=built,
        per_built=total / built if built else None,
        past=past if known else None, past_pct=pct(past) if known else None,
        past_main=sum(t["cost_past_150k"] for t in known if t.get("agent") == "main") if known else None,
        past_unknown=len(tokens) - len(known),
        past_most=first(date_cols, lambda c: (c["p"] or 0) / (c["u"] or 1)) if known else None,
        # split rows whose dollars past 150k are more than their re-reading: why the rail is not a part of the upkeep
        rail_over=sum(1 for t in tokens if split[id(t)] is not None and (t.get("cost_past_150k") or 0) > split[id(t)][0]),
        split=dict(rows=len(tokens) - len(unsplit), dollars=sum(kinds[:3]), off=round(100 * max(offs), 2) if offs else None),
        unsplit=dict(rows=len(unsplit), dollars=kinds[3], models=sorted({model(t) or "no model" for t in unsplit})),
        furthest=round(max(abs(c["b"] - c["u"] / BUDGET_UNIT) for c in date_cols), 2),
        read_tokens_pct=_round(100 * sum(t.get("cache_read") or 0 for t in tokens) / all_tokens) if all_tokens else None,
        main_model=main_model, write_price=price[2] if price else None, read_price=price[3] if price else None,
        write_over_read=_round(price[2] / price[3]) if price and price[3] else None,
        dear=first(date_cols, lambda c: c["u"]), cheap=first(date_cols, lambda c: -c["u"]),
        no_day=no_day, no_day_pct=pct(no_day),
        dear_day=first(own, lambda c: c["u"]), cheap_day=first(own, lambda c: -c["u"]),
        refused=sum(guards.values()), guards=[[g, guards[g]] for g in _guard_order(guards)],
        most_refused=first(date_cols, lambda c: c["refused"]), cut=sum(c["cut"] for c in date_cols),
        driver=dict(steps=len(steps), sessions=len(sessions), cost=sum(s.get("cost") or 0 for s in sessions)) if steps else None,
        prices_checked=tu.PRICES_CHECKED,
    )
    return out


# Graph 9 as growth rings (the mockup at #228's rng): the kinds of file, in the bands' order, top to bottom. Graph 9
# counts specs and agent context as one kind; here they are two bands.
RING_KINDS = ("prod", "test", "spec", "context", "tooling")


def _share(x):
    """A share as the rings print it: a whole percent from 10%, one decimal from 1%, two below; "<0.01%" for a share
    too small to print, and "0%" for none."""
    p = 100 * (x or 0)
    if p <= 0:
        return "0%"
    if p >= 9.95:
        return f"{_round(p)}%"
    if p >= 0.995:
        return f"{p:.1f}%"
    return "<0.01%" if p < 0.005 else f"{p:.2f}%"


def _ring(rows, key, **extra):
    """One ring: its lines by kind, each kind's share as printed and as a fraction (the band's height), its pull
    requests and what kind each was, and its test lines for each production line."""
    w = {k: sum((r.get("work") or {}).get(k) or 0 for r in rows) for k in RING_KINDS}
    lines = sum(w.values())
    prs = [r for r in rows if r.get("pr")]
    kinds = {}
    for r in prs:
        kinds[r.get("kind") or "other"] = kinds.get(r.get("kind") or "other", 0) + 1
    dates = sorted(r.get("date") for r in rows if r.get("date"))
    return dict(extra, key=key, lines=lines, prs=len(prs), pr_list=[r["pr"] for r in prs],
                pr_kinds=[[k, kinds[k]] for k in ("spec", "code", "close", "other") if kinds.get(k)], w=w,
                k=[[k, w[k], _share(w[k] / lines) if lines else "0%", w[k] / lines if lines else 0] for k in RING_KINDS],
                ratio=round(w["test"] / w["prod"], 1) if w["prod"] else None,
                first=dates[0] if dates else None, last=dates[-1] if dates else None)


def rings(d):
    """Graph 9's lines as growth rings: one ring for each Day, its own pull requests (the Day its branch names), and
    below, one hatched ring for the work no Day owns, at the Day graph 9 places it beside (`_placed`'s `at`: the
    furthest Day begun when it merged). Rows before Day 1 began are graph 9's "before Day 1": counted, in no ring.
    Rows in neither (a Day not in the data, or no pull request after Day 1 began) are `unplaced`, counted apart, so
    none vanishes. Every width in lines and every share is counted here; dashboard.js turns lines into px."""
    rows, placed = d.get("rows") or [], _placed(d)
    pairs = list(zip(rows, placed))
    days = sorted(d.get("days") or [], key=lambda x: x.get("day"))
    numbers = {y.get("day") for y in days}
    inside, outside = [], []
    for y in days:
        mine = [r for r, p in pairs if p["own"] == y.get("day")]
        if mine:
            inside.append(_ring(mine, f"d{y.get('day')}", day=y.get("day"), title=_plain(y.get("title"))))
        beside = [r for r, p in pairs if p["area"] and p["at"] == y.get("day")]
        if beside:
            outside.append(_ring(beside, f"o{y.get('day')}", at=y.get("day")))
    is_in = lambda p: p["own"] in numbers  # noqa: E731
    is_out = lambda p: p["own"] is None and p["area"] and p["at"] in numbers  # noqa: E731
    inner = _ring([r for r, p in pairs if is_in(p)], "all")
    outer = _ring([r for r, p in pairs if is_out(p)], "out")
    before = _ring([r for r, p in pairs if p["own"] is None and p["at"] is None], "before")
    loose = _ring([r for r, p in pairs if not is_in(p) and not is_out(p) and not (p["own"] is None and p["at"] is None)],
                  "unplaced")
    drawn = inner["lines"] + outer["lines"]
    share = lambda x: _share(x / drawn) if drawn else "0%"  # noqa: E731
    widths = [x["lines"] for x in inside]
    ratios = [(x["ratio"], x["day"]) for x in inside if x["ratio"] is not None]
    top2 = sorted(outside, key=lambda x: -x["lines"])[:2]
    span = {}
    for y in days:
        w = y.get("worked")
        if w and w[0] and w[1]:
            n = (datetime.date.fromisoformat(w[1][:10]) - datetime.date.fromisoformat(w[0][:10])).days + 1
            span[n] = span.get(n, 0) + 1
    first = lambda xs, f: max(range(len(xs)), key=lambda i: (f(xs[i]), -i)) if xs else None  # noqa: E731
    return dict(
        _stamp(d), kinds=list(RING_KINDS), days=inside, outside=outside, before=before, unplaced=loose,
        inside=dict(inner, share=share(inner["lines"]), n_days=len(inside)), out=dict(outer, share=share(outer["lines"])),
        total=drawn + before["lines"], drawn=drawn, prs=inner["prs"] + outer["prs"], merges=len(rows),
        all_lines=sum(sum((r.get("work") or {}).get(k) or 0 for k in RING_KINDS) for r in rows),
        prod_lines=inner["w"]["prod"] + outer["w"]["prod"], prod_share=share(inner["w"]["prod"] + outer["w"]["prod"]),
        ratio=inner["ratio"], ratio_low=list(min(ratios)) if ratios else None,
        ratio_high=list(max(ratios, key=lambda x: (x[0], -x[1]))) if ratios else None,
        heavy=first(inside, lambda x: x["lines"]), light=first(inside, lambda x: -x["lines"]),
        wide_out=first(outside, lambda x: x["lines"]), thin_out=first(outside, lambda x: -x["lines"]),
        spread=round(max(widths) / min(widths), 1) if widths and min(widths) else None,
        top_out=dict(at=[x["at"] for x in top2], lines=sum(x["lines"] for x in top2),
                     share=_share(sum(x["lines"] for x in top2) / outer["lines"]) if outer["lines"] else "0%"),
        # the tallest band of each Day's ring: the kind that leads in the most Days (the earlier kind on a tie)
        tallest=sorted(([k, sum(1 for x in inside if x["lines"] and max(RING_KINDS, key=lambda j: (x["w"][j], -RING_KINDS.index(j))) == k)]
                        for k in RING_KINDS), key=lambda kc: (-kc[1], RING_KINDS.index(kc[0])))[:1],
        spec_over_test=[x["day"] for x in inside if x["w"]["spec"] + x["w"]["context"] > x["w"]["test"]],
        seasons=[[n, span[n]] for n in sorted(span)],
    )


# Graph 10's actors, in its lane order, and what a session waited on (scripts/token-usage.py's RUN_KINDS).
ACT_LANES = ("main", "implementer", "auditors", "other")
ACT_RUNS = ("tests", "checks", "other")
ACT_PR_KINDS = ("spec", "code", "close", "other")  # dashboard.js's KINDS but the first commit
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _act_lane(agent):
    """graph 10's laneOf: the main session, the implementer, the auditors (the defect-rater with them), the rest."""
    if agent in ("main", "implementer"):
        return agent
    return "auditors" if re.search(r"-auditor$|^defect-rater$", agent or "") else "other"


def _offset(stamp):
    """The minutes east of UTC a time is stamped with (graph 10's offsetOf); none or Z is 0."""
    m = re.search(r"(Z|[+-]\d\d:\d\d)$", stamp or "")
    if not m or m.group(1) == "Z":
        return 0
    return (-1 if m.group(1)[0] == "-" else 1) * (int(m.group(1)[1:3]) * 60 + int(m.group(1)[4:6]))


def _ms(stamp):
    """Milliseconds since the epoch, as Date.parse gives them; a time with no offset is taken as UTC."""
    t = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return t.timestamp() * 1000


def _r1(x):
    """Rounded to 0.1 as Math.round(x * 10) / 10 rounds: a half goes up."""
    return math.floor(x * 10 + 0.5) / 10


def _covered(spans):
    """graph 10's covered(): minutes under a list of [from, to], a minute two of them share counted once."""
    n, end = 0, -math.inf
    for a, b in sorted(spans, key=lambda s: s[0]):
        n += max(0, b - max(a, end))
        end = max(end, b)
    return n


def _union(spans):
    """The spans merged where they touch or overlap, in order."""
    out = []
    for a, b in sorted(spans, key=lambda s: s[0]):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        elif b > a:
            out.append([a, b])
    return out


def _lower_median(values):
    v = sorted(values)
    return v[(len(v) - 1) // 2] if v else None


def _act_missing(d):
    """Why no session can be drawn: the dashboard-data branch is missing, or has no sessions.json."""
    src = d.get("data")
    if not src:
        return None
    if not src.get("commit"):
        return f"the {src.get('branch')} branch is missing, so no session is drawn."
    if "sessions.json" in (src.get("absent") or []):
        return f"the {src.get('branch')} branch has no sessions.json, so no session is drawn."
    return None


def actogram(d):
    """Graph 10 as an actogram: every date on one clock, 05:00 to 05:00 on the clock of the machine that recorded the
    sessions, a row each. Counted by graph 10's rules (clockGraph in dashboard.js, which now reads its figures from
    here): the zone is the offset most sessions are stamped with; a moment's date is the local date five hours
    earlier; a lane's busy minutes count two of its sessions at once once; a session's waits are its runs of a minute
    or more cut to the date, plus the rest of its `ran` shared by the part of it on the date; a date's median wait is
    the lower median of the pull requests merged on it. Minutes are counted from the date's 05:00, rounded to 0.1."""
    clock = d.get("clock") or {}
    sessions = [s for s in clock.get("sessions") or [] if s.get("from") and s.get("to")]
    prs = [p for p in clock.get("prs") or [] if p.get("opened")]
    counted = (d.get("counted") or {}).get("at")
    counts = {}
    for s in sessions:
        counts[_offset(s["from"])] = counts.get(_offset(s["from"]), 0) + 1
    zone = max(counts.items(), key=lambda kv: kv[1])[0] if counts else 0  # the first seen wins a tie, as JS's sort
    zone_text = f"UTC{'+' if zone > 0 else '−'}{abs(zone) // 60:02d}:{abs(zone) % 60:02d}" if zone else "UTC"

    def date_of(stamp):
        return datetime.datetime.fromtimestamp((_ms(stamp) + (zone - 300) * 60000) / 1000, datetime.timezone.utc).date().isoformat()

    def day_start(date):
        return _ms(f"{date}T05:00:00Z") - zone * 60000

    def clip(date, a, b):
        t0 = day_start(date)
        x, y = (_ms(a) - t0) / 60000, (_ms(b) - t0) / 60000
        return None if y < 0 or x > 1440 else [max(0, x), min(1440, max(y, x))]

    def kind_of(run):
        return run[2] if run[2] in ACT_RUNS else "other"

    def whole(a, b):
        return (_ms(b) - _ms(a)) / 60000

    dates = sorted({date_of(s["from"]) for s in sessions}
                   | {date_of(t) for p in prs for t in (p["opened"], p.get("merged") or p.get("closed")) if t})
    lane_keys = [k for k in ACT_LANES if k != "other" or any(_act_lane(s.get("agent")) == "other" for s in sessions)]
    counted_ms = _ms(counted) if counted else None
    merged_all = [p for p in prs if p.get("merged")]
    out = []
    for date in dates:
        start = day_start(date)
        up_to = 1440 if counted_ms is None else max(0, min(1440, (counted_ms - start) / 60000))
        lanes, waits, ran, days = {}, {}, [0.0, 0.0, 0.0], set()
        spans, main_spans, wait_segs = [], [], []
        for k in lane_keys:
            mine = [(s, c) for s in sessions if _act_lane(s.get("agent")) == k for c in [clip(date, s["from"], s["to"])] if c]
            if not mine:
                continue
            bar_ran = []
            for s, c in mine:
                every = whole(s["from"], s["to"])
                part = (c[1] - c[0]) / every if every > 0 else 1
                mins = []
                for kind in ACT_RUNS:
                    long = [r for r in s.get("runs") or [] if kind_of(r) == kind]
                    cut = sum((x[1] - x[0]) for x in (clip(date, r[0], r[1]) for r in long) if x)
                    rest = max(0, ((s.get("ran") or {}).get(kind) or 0) / 60 - sum(whole(r[0], r[1]) for r in long))
                    mins.append(cut + rest * part)
                bar_ran.append(mins)
                for r in s.get("runs") or []:
                    x = clip(date, r[0], r[1])
                    if x:
                        wait_segs.append([_r1(x[0]), _r1(x[1]), kind_of(r)])
                if s.get("day") is not None:
                    days.add(s["day"])
            for i in range(3):
                ran[i] += sum(m[i] for m in bar_ran)
            busy = _covered([c for _, c in mine])
            lanes[k], waits[k] = _r1(busy), _r1(min(busy, sum(sum(m) for m in bar_ran)))
            spans += [c for _, c in mine]
            if k == "main":
                main_spans = [c for _, c in mine]
        for p in prs:
            if any(t and date_of(t) == date for t in (p["opened"], p.get("merged"))) and p.get("day") is not None:
                days.add(p["day"])
        merges = []
        for p in merged_all:
            if date_of(p["merged"]) != date:
                continue
            opened = (_ms(p["opened"]) - start) / 60000
            merges.append(dict(pr=p.get("number"), at=_r1((_ms(p["merged"]) - start) / 60000), **{"from": _r1(max(0, opened))},
                               wait=_r1(whole(p["opened"], p["merged"])), kind=p.get("kind") if p.get("kind") in ACT_PR_KINDS else "other",
                               cut=opened < 0, day=p.get("day")))
        main_u = _union(main_spans)
        segs = [[a, b, "main"] for a, b in main_u]
        for a, b in _union(spans):
            at = a
            for m0, m1 in main_u:
                if m1 <= at or m0 >= b:
                    continue
                if m0 > at:
                    segs.append([at, m0, "sub"])
                at = max(at, m1)
            if at < b:
                segs.append([at, b, "sub"])
        segs = [[_r1(a), _r1(b), kind] for a, b, kind in sorted(segs, key=lambda s: s[0])]
        true = [whole(p["opened"], p["merged"]) for p in merged_all if date_of(p["merged"]) == date]
        _, m, dd = date.split("-")
        out.append(dict(
            date=date, label=f"{int(dd)} {_MONTHS[int(m) - 1]}", days=sorted(days), lanes=lanes, waits=waits,
            ran=[_r1(x) for x in ran], merged=len(merges), median=_r1(_lower_median(true)) if true else None, busy=_r1(_covered(spans)), main=_r1(_covered(main_spans)), up_to=_r1(up_to),
            segs=segs, wait_segs=sorted(wait_segs, key=lambda s: s[0]), merges=merges,
            session=bool(spans)))
    worked = [x for x in out if x["session"]]
    whole_dates = [x for x in worked if x["up_to"] == 1440]
    all_waits = [(whole(p["opened"], p["merged"]), p.get("number")) for p in merged_all]
    busy, ran = sum(x["busy"] for x in worked), [sum(x["ran"][i] for x in out) for i in range(3)]
    longest = max(all_waits, key=lambda w: w[0]) if all_waits else None  # the first of the longest
    totals = dict(
        dates=len(worked), first=worked[0]["date"] if worked else None, last=worked[-1]["date"] if worked else None,
        busy=_r1(busy), main=_r1(sum(x["main"] for x in worked)), ran=[_r1(r) for r in ran],
        waiting_share=sum(ran) / busy if busy else None, merged=len(merged_all),
        median=_r1(_lower_median([w for w, _ in all_waits])) if all_waits else None,
        over_hour=sum(1 for w, _ in all_waits if w > 60),
        longest=dict(pr=longest[1], wait=_r1(longest[0])) if longest else None,
        after_midnight=sum(1 for x in whole_dates if any(s[1] > 1140 for s in x["segs"])), whole=len(whole_dates))
    return dict(missing=_act_missing(d), zone=zone_text, counted=counted, dates=out, totals=totals)


# Graph 11 as reflex arcs: how a step ended, as the mark at the end of its row (`fin`) and the words beside it.
RFX_END = dict(merged="Merged, with no park", fixed="Merged after fixing itself", still="Still open, no park so far")
RFX_BY = dict(fault=("Parked by a fault", "parked by a fault", "The driver or the kit was at fault."),
              maintainer=("Parked for the maintainer", "parked for the maintainer", "A decision that is the maintainer's."))
RFX_GO = "the maintainer's go-ahead, which the plan requires at every pull request"


def _n(k, one, many=None):
    return f"{k} {one if k == 1 else many or one + 's'}"


def _rfx_missing(d):
    """Why no step of the driver can be drawn: the dashboard-data branch or its driver-runs.json is missing, or the run
    log is not counted for this project."""
    src = d.get("data")
    if src and not src.get("commit"):
        return f"the {src.get('branch')} branch is missing, so no step of the driver is drawn."
    if src and "driver-runs.json" in (src.get("absent") or []):
        return f"the {src.get('branch')} branch has no driver-runs.json, so no step of the driver is drawn."
    if (d.get("driver_runs") or {}).get("steps") is None:
        return "the driver's run log is not counted for this project yet, so no step is drawn."
    return None


def _rfx_label(step):
    """A step's sentence as its row names it: before the first ": ", with the criteria after it as the row's sub line;
    a sentence whose second part names no criteria keeps it ("Day 13: the closing PR")."""
    parts = _plain(step).split(": ")
    if len(parts) > 1 and re.match(r"C\d", parts[1]):
        return parts[0], parts[1]
    label = ": ".join(parts[:2])
    return (label if len(label) <= 38 else label[:37].rstrip() + "…"), None


def _said(label):
    """A step's label inside a sentence: one that is a sentence of its own ("Every day is done.") is quoted."""
    return f'"{label}"' if label[-1:] in ".!?" else label


def _ago(seconds):
    """A short time between two moments: seconds under a minute and a half, else whole minutes."""
    return f"{round(seconds)} s" if seconds < 90 else f"{round(seconds / 60)} min"


def reflex(d):
    """Graph 11 as reflex arcs: one row per step the driver started, in its run log's order, read left to right from
    the step, through its sessions, to its pull request; a step that parked climbs to the band of the person. The
    counts of steps, parks, crashed steps, open and merged steps are _runs()'s, the proteins' "In real runs". No park
    is given a wait: a park names no issue whose closing would time it, so only the next session's start is said."""
    runs_of = d.get("driver_runs") or {}
    steps = runs_of.get("steps") or []
    counted = runs_of.get("counted")
    zone = _offset(counted)
    zone_text = "UTC" if not zone else f"UTC{'+' if zone > 0 else '−'}" + (
        str(abs(zone) // 60) if abs(zone) % 60 == 0 else f"{abs(zone) // 60:02d}:{abs(zone) % 60:02d}")

    def local(stamp):
        return datetime.datetime.fromtimestamp(_ms(stamp) / 1000 + zone * 60, datetime.timezone.utc)

    def when(stamp):
        t = local(stamp)
        return f"{t.day} {_MONTHS[t.month - 1]} {t:%H:%M}"

    def secs(a, b):
        return (_ms(b) - _ms(a)) / 1000

    runs = _runs(steps)
    rows, tips, dates = [], {}, set()
    for i, s in enumerate(steps):
        label, crit = _rfx_label(s.get("step"))
        day = s.get("day")
        where = f"project's Day {day}" if day is not None else "no project Day"
        sessions, parks = s.get("sessions") or [], s.get("parks") or []
        first = min([x["start"] for x in sessions if x.get("start")] + [p["at"] for p in parks if p.get("at")], default=None)
        if first:
            dates.add(local(first).date())
        ses = []
        for j, x in enumerate(sessions):
            crashed = bool(x.get("crashed")) or not x.get("end")
            minutes = None if crashed else round(secs(x["start"], x["end"]) / 60)
            fixes, denied = x.get("fixes") or 0, x.get("denials") or 0
            ses.append(dict(crashed=crashed, minutes=minutes, cost=x.get("cost") or 0, fixes=fixes, denials=denied))
            t = local(x["start"])
            head = (f"Started {when(x['start'])} ({zone_text}). The run log has no end for it: it crashed." if crashed else
                    f"{t.day} {_MONTHS[t.month - 1]}, {t:%H:%M} to {local(x['end']):%H:%M} ({zone_text}): {minutes} min.")
            tips[f"s{i}x{j}"] = dict(
                t=f"Session {j + 1} of {len(sessions)}" + (" · crashed" if crashed else ""),
                l=[head, f"{'No fix round' if not fixes else _n(fixes, 'fix round')}. "
                         f"{'No tool call refused' if not denied else _n(denied, 'tool call') + ' refused'}. "
                         f"${x.get('cost') or 0:.2f} at API list prices."],
                a=f"{label}, Session {j + 1} of {len(sessions)}" + (" · crashed" if crashed else ""))
        pk = []
        for j, p in enumerate(parks):
            by = p.get("by") if p.get("by") in RFX_BY else "maintainer"
            before = [k for k, x in enumerate(sessions) if x.get("start") and p.get("at") and _ms(x["start"]) <= _ms(p["at"])]
            after = [k for k, x in enumerate(sessions) if x.get("start") and p.get("at") and _ms(x["start"]) > _ms(p["at"])]
            up, back = (before[-1] if before else None), (after[0] if after else None)
            later = (f"the next session started {_n(round(secs(p['at'], sessions[back]['start']) / 60), 'minute')} later"
                     if back is not None else "no session started after it in this step")
            went = ("It went up before any session ran." if up is None else
                    f"It went up at session {up + 1} of {len(sessions)}" + (", which crashed." if ses[up]["crashed"] else "."))
            known = (f"It names issue #{p['issue']}; how long a person was needed is not counted here." if p.get("issue") else
                     "How long a person was needed is not known: the park names no issue.")
            pk.append(dict(by=by, up=up, back=back, at=when(p["at"]) if p.get("at") else None, later=later, issue=p.get("issue")))
            tips[f"s{i}p{j}"] = dict(
                t=f"{RFX_BY[by][0]} · {when(p['at'])} ({zone_text})" if p.get("at") else RFX_BY[by][0],
                l=[f"{RFX_BY[by][2]} {went}",
                   f"It came back down at session {back + 1}: {later}." if back is not None else f"It did not come back: {later}.",
                   known],
                q=_plain(p.get("line")) or None, a=f"{label}, {RFX_BY[by][0]}" + (f" · {when(p['at'])} ({zone_text})" if p.get("at") else ""))
        ended = s.get("ended")
        last_by = pk[-1]["by"] if pk else None
        fin = (("fault" if last_by == "fault" else "maint") if pk else "still" if ended == "open"
               else "fixed" if ended == "fixed" or (ended == "merged" and s.get("fixes")) else "merged" if s.get("merged") else "maint")
        how = (f"{RFX_BY[last_by][1]}" if pk else "still open" if fin == "still" else
               "merged after fixing itself" if fin == "fixed" else "merged with no park" if fin == "merged" else _plain(ended) or "ended")
        end = (RFX_BY[last_by][0] + (", then merged" if s.get("merged") else "") if pk else RFX_END.get(fin) or "Stopped")
        crashed_n, ran = sum(x["crashed"] for x in ses), sum(x["minutes"] or 0 for x in ses)
        cost = sum(x["cost"] for x in ses)
        bits = ([_n(len(ses), "session") + (f", {crashed_n} crashed" if crashed_n else ""), f"{ran} min", f"${cost:.2f}"]
                if ses else ["no session"])
        pr = None
        if s.get("pr") is not None:
            ends = [x.get("end") for x in sessions if x.get("end")]
            after = secs(max(ends, key=_ms), s["merged"]) if s.get("merged") and ends else None
            pr = dict(number=s["pr"], state="merged" if s.get("merged") else "open", after=None if after is None else round(after))
            if pr["state"] == "open":
                bits.append("go-ahead awaited")
            tips[f"s{i}r"] = dict(
                t=f"Pull request #{s['pr']} · {pr['state']}",
                l=([f"Merged {when(s['merged'])} ({zone_text})" + (f", {_ago(after)} after its last session ended." if after is not None else "."),
                    f"The merge is {RFX_GO}. It is not a park.", f"The step ended {how}."] if pr["state"] == "merged" else
                   ["Opened by the step; not merged when the run log was counted.",
                    f"It waits for {RFX_GO}. That is not a park.", "The step is still open."]),
                a=f"{label}, Pull request #{s['pr']} · {pr['state']}")
        else:
            tips[f"s{i}r"] = dict(t=f"No pull request · {how}",
                                  l=["The step opened none: " + (f"it ran {_n(len(ses), 'session')}." if ses else "it ran no session."),
                                     "So no go-ahead was asked for it."],
                                  a=f"{label}, No pull request · {how}")
        tips[f"s{i}"] = dict(
            t=f"{where[0].upper() + where[1:]} · step {i + 1} of {len(steps)}",
            l=[_plain(s.get("step")),
               f"Branch prefix {s['prefix']}." if s.get("prefix") else
               "It has no branch: the driver started no session for it." if not ses else "It has no branch.",
               f"First seen in the run log at {when(first)} ({zone_text})." if first else "",
               "It is still open." if fin == "still" else f"It ended {how}."],
            a=f"{where[0].upper() + where[1:]} · step {i + 1} of {len(steps)}: {label}")
        tips[f"s{i}"]["l"] = [x for x in tips[f"s{i}"]["l"] if x]
        rows.append(dict(label=label, sub=where + (f" · {crit}" if crit else ""), day=day, sessions=ses, parks=pk, pr=pr,
                         fin=fin, end=end, end_sub=" · ".join(bits), ended=ended))

    n = len(rows)
    ended = [r for r in rows if r["fin"] != "still"]
    alone = [r for r in ended if not r["parks"]]
    parked = [r for r in rows if r["parks"]]
    by_fault = sum(1 for r in parked if r["parks"][-1]["by"] == "fault")
    by_day = {}
    for r in rows:
        by_day[r["day"]] = by_day.get(r["day"], 0) + 1
    split = [f"{k} on the project's Day {day}" if i == 0 else f"{k} on Day {day}"
             for i, (day, k) in enumerate((day, k) for day, k in sorted(by_day.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)) if day is not None)]
    if None in by_day:
        split.append(f"{by_day[None]} with no Day")
    all_ses = [x for r in rows for x in r["sessions"]]
    per = sorted(len(r["sessions"]) for r in rows)
    crashed_ses, fixes = sum(x["crashed"] for x in all_ses), sum(x["fixes"] for x in all_ses)
    none_ran = sum(1 for r in rows if not r["sessions"])
    opened = [r for r in rows if r["pr"]]
    merged = [r for r in opened if r["pr"]["state"] == "merged"]
    still = [r for r in opened if r["pr"]["state"] == "open"]
    too_few = f"All on {_n(len(dates), 'date')}: too few to judge by." if len(dates) < 5 else f"On {len(dates)} dates."
    figs = [
        dict(num=str(n), small=None, what="step the driver started" if n == 1 else "steps the driver started",
             sub=(_list(split) + ". " if split else "") + too_few),
        dict(num=str(len(alone)), small=f"of {len(ended)} ended", what="finished without a park",
             sub=f"{len(parked)} parked" + (f": {by_fault} by a fault and {len(parked) - by_fault} for the maintainer" if parked else "")
             + "." + (f" {len(rows) - len(ended)} more {'is' if len(rows) - len(ended) == 1 else 'are'} still open." if len(rows) > len(ended) else "")),
        dict(num=str(_lower_median(per) if per else 0), small=None,
             what="session a step, at the median" if (_lower_median(per) if per else 0) == 1 else "sessions a step, at the median",
             sub=f"{_n(len(all_ses), 'session')} in {_n(n, 'step')}: {crashed_ses} crashed, "
             + ("no fix round" if not fixes else _n(fixes, "fix round")) + "." + (f" {_n(none_ran, 'step')} ran none." if none_ran else "")),
        dict(num=str(len(merged)), small=f"of {len(opened)} opened", what="pull requests merged" if len(merged) != 1 else "pull request merged",
             sub="Each on the maintainer's go-ahead." + (f" {_list(['#' + str(r['pr']['number']) for r in still])} "
                                                       f"{'is' if len(still) == 1 else 'are'} still open." if still else "")),
    ]
    l2 = runs_of.get("level_2")
    if l2:
        tips["l2"] = dict(t=f"Trial for level 2: {l2.get('run')} of {l2.get('of')} in a row",
                          l=[f"{_n(l2.get('run') or 0, 'pull request')} in a row with no change asked, of the {l2.get('of')} the plan asks for.",
                             "At level 2 the driver merges, and the go-ahead mark leaves the rows. The driver's own count, as graph 1's level card shows it."],
                          a=f"Trial for level 2: {l2.get('run')} of {l2.get('of')} in a row")
    afters = [r["pr"]["after"] for r in merged if r["pr"]["after"] is not None]
    cost, ran = sum(x["cost"] for x in all_ses), sum(x["minutes"] or 0 for x in all_ses)
    finds = []
    if ended:
        finds.append(["good", f"{len(alone)} of the {len(ended)} steps that ended needed no park.",
                      _list([_said(r["label"]) for r in alone]) + (": one session each." if alone and all(len(r["sessions"]) == 1 for r in alone) else ".")
                      if alone else "Every step that ended parked at least once."])
    for r in parked:
        p = r["parks"][-1]
        cls = "fault" if p["by"] == "fault" else "maint"
        if p["back"] is not None:
            finds.append([cls, f"{_said(r['label'])} went up {'for a fault' if cls == 'fault' else 'for the maintainer'}, and came back.",
                          f"The driver parked at {p['at'][-5:]}; {p['later']}"
                          + (f" and pull request #{r['pr']['number']} {'merged' if r['pr']['state'] == 'merged' else 'is open'}." if r["pr"] else ".")])
        else:
            finds.append([cls, f"{_said(r['label'])} went up and stayed.",
                          f"It ran {_n(len(r['sessions']), 'session') if r['sessions'] else 'no session'} and opened "
                          + (f"pull request #{r['pr']['number']}" if r["pr"] else "no pull request") + ": "
                          + ("the park is a decision that is the maintainer's." if cls == "maint" else "the driver or the kit was at fault.")])
    if still:
        finds.append(["", f"{_n(len(still), 'step')} {'is' if len(still) == 1 else 'are'} still open.",
                      " ".join(f"{_said(r['label'])} opened pull request #{r['pr']['number']} after {_n(len(r['sessions']), 'session')}; the go-ahead has not come."
                               for r in still)])
    if opened:
        finds.append(["", "Every row with a pull request ends at the go-ahead.",
                      f"{_n(len(merged), 'pull request')} merged" + (f", {_ago(min(afters))} to {_ago(max(afters))} after the last session ended" if afters else "")
                      + (f"; {len(still)} awaited." if still else ".")])
    if all_ses:
        finds.append(["", f"{'No fix round' if not fixes else _n(fixes, 'fix round')} and {_n(crashed_ses, 'crash', 'crashes')} in {_n(len(all_ses), 'session')}.",
                      f"The sessions cost ${cost:.2f} at API list prices, and ran {ran} min in all."])
    if l2:
        finds.append(["", f"The trial for level 2 stands at {l2.get('run')} of {l2.get('of')}.",
                      "It counts pull requests in a row with no change asked. At level 2 the driver merges, and the go-ahead mark would leave the rows."])
    all_parks = [p for r in rows for p in r["parks"]]
    unnamed = sum(1 for p in all_parks if not p["issue"])
    bends = [
        ["Every arc still ends at a person.", "A reflex never asks the brain. Here the plan requires the maintainer's go-ahead at every pull request: "
         f"{len(merged)} given, {len(still)} awaited. So \"without a person\" means without a park, and nothing more."],
        ["A reflex is wired; these steps are chosen.", "The body's wiring fixes what a reflex does. The plan and the Day's spec choose each step here, "
         "and people wrote both."],
        [f"{_n(n, 'step')} prove little." if n < 30 else f"{n} steps are a start.",
         f"They ran on {_n(len(dates), 'date')}, on one project. A reflex is trusted because it has fired the same way countless times; "
         f"this picture has {_n(len(alone), 'clean run')} and {_n(len(all_parks), 'park')} to go on."],
        ["Distance along a row is order, not time.", "A short session and a long one are the same dot."
         + (f" How long a park kept a person is not known for {unnamed} of the {_n(len(all_parks), 'park')}: the park names no issue." if unnamed else "")],
    ]
    idle = [r for r in parked if not r["sessions"]]
    if idle:
        bends.append(["A park is not always a reflex that failed.", f"{_list([_said(r['label']) for r in idle])} ran no session: the driver stopped because "
                      "the plan had nothing more for it, which is the plan working."])
    t = local(counted) if counted else None
    return dict(
        missing=_rfx_missing(d), zone=zone_text, source=runs_of.get("source"), counted=counted,
        stamp=(f"the driver's run log counted up to {t:%H:%M} on {t.day} {_MONTHS[t.month - 1]} ({zone_text})" if t else "the driver's run log")
        + (f", from {runs_of.get('source')}" if runs_of.get("source") else ""),
        counts=dict(steps=len(steps), parks=len(runs["park"]), crashed=len(runs["recover"]), open=len(runs["open"]), merged=len(runs["loop"]),
                    ended=len(ended), alone=len(alone), crashed_sessions=crashed_ses),
        level_2=dict(run=l2.get("run"), of=l2.get("of")) if l2 else None,
        rows=rows, tips=tips, figs=figs, finds=finds, bends=bends,
        aria=f"{_n(n, 'step')} the driver started, one row each. {len(alone)} of the {len(ended)} that ended needed no park; "
        f"{_n(len(all_parks), 'park')} went up to the person.",
        hint="Point at a mark, or reach it with the Tab key, for the session, the park or the pull request."
        + (f" Only {_n(n, 'step')} on {_n(len(dates), 'date')} are counted: the picture is true, and proves little yet." if len(dates) < 5 else ""))


def _list(items):
    items = list(items)
    return " and ".join(items) if len(items) < 3 else f"{', '.join(items[:-1])} and {items[-1]}"
