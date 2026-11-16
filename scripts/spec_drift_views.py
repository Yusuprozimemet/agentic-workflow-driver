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


def criterion_states(index, days, replay):
    """Give each criterion of `index` its `state`, as the page's promise tiles read it, and `back`: the replay saw
    it stop holding (broken, or needing repair) at an earlier merge, and it holds now."""
    by_day = {d.get("day"): d for d in days}
    cells = _cells(replay)
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


def gene(plan, index, days):
    """The gene: every commitment of the plan in exactly one class, read down from the plan through the criteria that
    quote it (as written, then in force) to the state of their code. `uncovered` is what is due by the last
    finished Day and named by no criterion in force: graph 12's "should be covered by now" set. None with no plan."""
    if not plan or not plan.get("commitments"):
        return None
    links = plan.get("links") or {}
    crit = {c["id"]: c for c in index if isinstance(c, dict) and c.get("id") in links}
    closed_to = max([d["day"] for d in days if d.get("status") in FINISHED], default=0)
    naming = {}
    for cid, named in links.items():
        for pid in named:
            naming.setdefault(pid, []).append(cid)
    cell = lambda c: dict(id=c["id"], day=c.get("day"), state=c.get("state"), back=bool(c.get("back")))  # noqa: E731
    rows, counts = [], dict.fromkeys(GENE_CLASSES, 0)
    for p in plan["commitments"]:
        written = [crit[cid] for cid in naming.get(p["id"], []) if cid in crit]
        live = [c for c in written if not c.get("replaced_by")]
        owner, rule = p.get("owner_day"), bool(p.get("rule"))
        if live:
            cls = _class([c.get("state") for c in live])
            sub = ("full" if all(c.get("state") == "proven" for c in live) else "part") if cls == "proved" else None
        elif written:
            cls, sub = "spliced", None
        else:
            cls = "untranscribed"
            sub = "rule" if rule else "later" if owner is None or owner > closed_to else "due"
        counts[cls] += 1
        rows.append(dict(id=p["id"], short=p.get("short", ""), section=p.get("section", ""),
                         arm="first" if p["id"].startswith("P") else "added", rule=rule, owner_day=owner,
                         change=p.get("change"), written=[c["id"] for c in written],
                         replaced=[c["id"] for c in written if c.get("replaced_by")],
                         cells=[cell(c) for c in live], cls=cls, sub=sub,
                         uncovered=not rule and owner is not None and owner <= closed_to and not live))
    off = [cell(c) | dict(tag=c.get("tag")) for cid, c in sorted(crit.items(), key=lambda kv: (kv[1].get("day") or 0, kv[0]))
           if not links[cid] and not c.get("replaced_by")]
    return dict(closed_to=closed_to, commitments=rows, counts=counts, off=off,
                proved_full=sum(1 for r in rows if r["sub"] == "full"),
                untranscribed={k: sum(1 for r in rows if r["cls"] == "untranscribed" and r["sub"] == k)
                               for k in ("rule", "later", "due")},
                stacks=dict(written=max([len(r["written"]) for r in rows], default=0),
                            cells=max([len(r["cells"]) for r in rows], default=0)),
                uncovered=[r["id"] for r in rows if r["uncovered"]],
                quotes=sum(len(r["written"]) for r in rows), live_quotes=sum(len(r["cells"]) for r in rows),
                criteria=len(crit), in_force=sum(1 for c in crit.values() if not c.get("replaced_by")))
