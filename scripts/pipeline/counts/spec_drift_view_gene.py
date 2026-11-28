"""The gene: each commitment of plan.md by the state of the criteria that serve it (`gene`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

from spec_drift_view_common import FINISHED, _quote


# The gene's classes, one per commitment, in the order the page shows them.
GENE_CLASSES = ("proved", "unproved", "unreplayable", "repair", "fails", "unbuilt", "spliced", "untranscribed")


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
