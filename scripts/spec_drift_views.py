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
