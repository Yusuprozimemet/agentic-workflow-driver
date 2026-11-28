"""Graph 6's rewrites frame: replaced promises joined to what replaced them (`rewrites`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

from spec_drift_view_common import _n, _order, _stamp


def _rewrites_line(sink, index, problems):
    """One sink's line: its nodes (the sink and every wording reached through Replaces:), its edges [old, new] and
    its main chain, oldest first; None when it reaches nothing. An absent short spec's id is a node of its own."""
    nodes, edges, seen, todo = {}, [], {sink["id"]}, [sink["id"]]
    while todo:
        new = todo.pop(0)
        c = index.get(new)
        if c is not None:
            nodes[new] = c
        for old in dict.fromkeys((c or {}).get("replaces") or []):  # an id named twice is one edge
            if old not in index and not str(old).startswith("S-"):
                problems.append(f"{old}, named by {new}'s Replaces: line, is not in the index")
                continue
            edges.append([old, new])
            if old not in seen:
                seen.add(old)
                todo.append(old)
                if old not in index:
                    nodes[old] = None
    if len(nodes) < 2:
        return None
    by = {}
    for old, new in edges:
        by.setdefault(old, []).append(new)
    days = {}
    for cid, c in nodes.items():
        if c is not None:
            days[cid] = c.get("day")
    for cid in nodes:
        if cid not in days:
            later = [days[b] for b in by.get(cid, []) if isinstance(days.get(b), (int, float))]
            days[cid] = min(later) - 0.5 if later else None
    preds = {cid: [old for old, new in edges if new == cid] for cid in nodes}
    deep = {}

    def depth(cid, path):
        # the longest chain behind a node; a node already on the path is skipped, so a cycle ends
        if cid not in deep:
            deep[cid] = max((1 + depth(p, path | {cid}) for p in preds[cid] if p not in path and p != cid),
                            default=0)
        return deep[cid]

    main, at = [sink["id"]], sink["id"]
    while True:
        left = [p for p in preds[at] if p not in main]
        if not left:
            break
        at = max(left, key=lambda p: (depth(p, set(main)), -left.index(p)))
        main.append(at)
    main.reverse()

    def text(c):
        t = c.get("plain") or c.get("claim") or ""
        return t if len(t) <= 260 else t[:259] + "…"

    out = []
    for cid, c in nodes.items():
        if c is None:
            slug = str(cid)[2:].rsplit(".", 1)[0]
            out.append(dict(id=cid, label=f"S.{str(cid).rsplit('.', 1)[-1]}", day=days[cid], state="replaced",
                            short=True, text=f'A promise of the short spec "{slug}". Its words are in '
                            f"specs/changes/{slug}.md, not in the page's data."))
        else:
            out.append(dict(id=cid, label=cid, day=days[cid], state=c.get("state"), short=False, text=text(c)))
    out.sort(key=lambda n: (n["day"] if n["day"] is not None else 0, _order(n["id"]), n["id"]))
    place = {n["id"]: i for i, n in enumerate(out)}
    for n in out:
        n["by"] = sorted(by.get(n["id"], []), key=place.get)
        n["main"] = n["id"] in main
    edges.sort(key=lambda e: place[e[1]])  # stable: within a new node, the order of its Replaces:
    return dict(sink=sink["id"], text=text(sink), state=sink.get("state"), day=sink.get("day"),
                first=min((n["day"] for n in out if n["day"] is not None), default=None), rewrites=len(main) - 1,
                n=len(out), main=main, nodes=out, edges=edges)


def rewrites(d):
    """Promises rewritten: for each criterion in force that replaced others (the sink), a line of every wording it
    reached through Replaces:, the edges from each wording to the one that replaced it, and its main chain (at each
    step back, the predecessor with the longest chain behind it, the first named on a tie). A short spec's
    criterion is not in the index: it is a node between the Days, half a Day before the first that replaced it."""
    index = {c["id"]: c for c in d.get("criteria_index") or [] if isinstance(c, dict) and c.get("id")}
    lines, alone = [], []
    for c in index.values():
        if c.get("replaces") and not c.get("replaced_by"):
            said = []
            line = _rewrites_line(c, index, said)
            if line:
                lines.append((line, said))
            else:
                alone += said
    lines.sort(key=lambda x: (-x[0]["rewrites"], -x[0]["n"], _order(x[0]["sink"])))
    # an absent id's problem in line order, then a sink's that made no line, then each wording on no line
    problems = [p for _, said in lines for p in said] + alone
    lines = [x for x, _ in lines]
    on = {n["id"] for x in lines for n in x["nodes"]}
    problems += [f"{cid} is replaced by {', '.join(c['replaced_by'])} and stands on no line"
                 for cid, c in index.items() if c.get("replaced_by") and cid not in on]
    sinks = {x["sink"] for x in lines}
    states = {}
    for x in lines:
        states[x["state"]] = states.get(x["state"], 0) + 1
    stats = dict(replaced=len(on - sinks), lines=len(lines), multi=sum(x["rewrites"] > 1 for x in lines),
                 longest=max((x["rewrites"] for x in lines), default=0), states=states)
    days = [dict(day=x.get("day"), phase=x.get("phase")) for x in d.get("days") or [] if isinstance(x, dict)]
    return dict(_stamp(d), days=days, lines=lines, stats=stats, problems=problems)


def rewrites_line(v):
    """The build's line: how many promises were replaced, on how many lines, and the longest line's rewrites."""
    s = v["stats"]
    return (f"rewrites: {_n(s['replaced'], 'promise')} replaced, on {_n(s['lines'], 'line')}; "
            f"the longest was rewritten {_n(s['longest'], 'time')}")
