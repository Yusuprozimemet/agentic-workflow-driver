"""Each criterion's state, worked out once for every view and the page (`criteria_index[].state`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

from spec_drift_view_common import FAILED_GROUPS, FINISHED, REPLAY_GROUP, _cells


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
    """Give each criterion of `index` its `state`, as the page reads it; `back`: the replay saw
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
