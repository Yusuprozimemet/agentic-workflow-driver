"""What needs attention: the header's panel, by one rule (`needs_attention`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

import re

from spec_drift_view_common import FAILED_GROUPS, _list, _order, _stamp


# "Needs attention", by one rule (the header's panel; the page draws what this returns and counts nothing). Each
# reason, as the group it counts in, the mark it is drawn with and what it says; the order is worst first. The first
# three groups make the headline; the last two are folded under it and stay out of the count. The reasons up to
# "test_skippable" are criterion_index's, as today's `attention` list has them; the rest are read from what a graph
# already draws, so a line the list never held is a graph's own verdict and never a second count of it.
NEEDS_GROUPS = (("broken", "broken", "a check that fails today"),
                ("repair", "to repair", "a missing test, tick or line; a yardstick above its average; a commitment due"),
                ("waiting", "waiting for you", "hand-offs nobody has picked up"),
                ("never", "hold, never proved", ""), ("expected", "expected, not counted", ""))


NEEDS_COUNTED = ("broken", "repair", "waiting")


NEEDS_WHY = {
    "replay_failed": ("broken", "bad", "The replay fails: {}."),
    "replay_error": ("broken", "bad", "The replay could not run its check: {}."),
    "replay_stale": ("repair", "rep", "The replay report is out of date: {}."),
    "evidence_missing": ("repair", "rep", "Ticked, and its Evidence line cites no test or command together with a pull request."),
    "not_seen_red": ("repair", "rep", "No test of it was seen failing: it has no seen-red or broken line."),
    "test_not_found": ("repair", "rep", "The test it names is not found: {}."),
    "not_ticked": ("repair", "rep", "Not ticked at its Day's close."),
    "story": ("repair", "rep", "{}."),
    "yardstick": ("repair", "rep", "{}."),
    "due": ("repair", "due", "Due by Day {}."),
    "handoff_unclaimed": ("waiting", "hnd", "{}."),
    "handoff_next": ("waiting", "hnd", "{}."),
    "handoff_unpicked": ("waiting", "hnd", "{}."),
    "unproven": ("never", "unp", "Holds, and no break on purpose is on record: its test was never seen to fail."),
    "unreplayable": ("never", "unp", "The replay cannot run its check, so nothing re-checks it."),
    "commitment_unproved": ("never", "unp", "Holds, never seen to fail: no criterion in force that names it has a break on purpose on record."),
    "commitment_unreplayable": ("never", "unp", "The replay cannot run the check of the criteria in force that name it."),
    "not_breakable": ("expected", "exp", "Cannot be broken from the repository: {}."),
    "test_skippable": ("expected", "exp", "A test it names can be skipped in CI: {}."),
    "replaced_stopped": ("expected", "stl", "Its old check stopped holding: {}."),
}


# The graphs a line can name, in page order, and the marks a graph's title carries a chip for: nothing expected.
NEEDS_GRAPHS = ("rdg", "gel", "prt", "gene", "g12", "mrg")


NEEDS_CHIPS = {"bad": "broken", "rep": "to repair", "due": "due", "hnd": "waiting for you", "unp": "never proved"}


# criterion_index flags a finished Day's criterion when the build has no replay report to read: a local build has no
# docs/dashboard/evidence-checks.json. That is the build missing a file, so it is said once, outside the count.
NEEDS_UNREAD = "Replay report: "


def needs_attention(d):
    """Everything open on the page, each id once under its worst mark: `groups` (the headline: broken, to repair,
    waiting) and `count`, their sum; `folded` (never proved, expected); `lines`, worst first, the ids that share a
    sentence on one line, each line naming the graphs that draw it; `chips`, per graph, how many ids of each mark its
    lines hold; `days`, the marks under the Day each id belongs to (None: no Day); and `unread`, what this build could
    not read. Whatever is flagged on a replaced criterion is expected: the criterion that replaced it is the promise now."""
    index = {c.get("id"): c for c in d.get("criteria_index") or [] if isinstance(c, dict)}
    mrg = {c.get("id"): c for c in (d.get("merge_graph") or {}).get("crit") or []}
    prt = {c.get("id"): c.get("state") for ch in (d.get("protein") or {}).get("chains") or [] for c in ch.get("cells") or []}
    rdg = d.get("reading") or {}
    arcs, gap = {o.get("id") for o in rdg.get("opens") or []}, {g.get("id") for g in rdg.get("gap") or []}
    found, unread, whys = {}, {}, list(NEEDS_WHY)
    rank = {g[0]: i for i, g in enumerate(NEEDS_GROUPS)}

    def st(cid):
        return (mrg.get(cid) or {}).get("st")

    def add(why, cid, detail="", graphs=(), day=None):
        group, mark, says = NEEDS_WHY.get(why) or ("repair", "rep", "{}.")
        c, text = index.get(cid) or {}, says.format(str(detail).rstrip("."))
        if c.get("replaced_by"):
            group, mark, text = "expected", mark if group == "expected" else "exp", f"Replaced by {_list(c['replaced_by'])}. {text}"
            graphs = graphs if why == "replaced_stopped" else ()
        numbered = re.match(r"[A-Z](\d+)\.|Day (\d+)$", str(cid))
        found.setdefault(cid, []).append(dict(
            group=group, mark=mark, why=why, id=cid, text=text, graphs=[g for g in NEEDS_GRAPHS if g in graphs],
            day=c.get("day") if c else day if day is not None else int(numbered.group(1) or numbered.group(2)) if numbered else None))

    for a in d.get("attention") or []:
        cid, why, detail = a.get("id"), a.get("reason"), a.get("detail") or ""
        if why == "evidence_missing" and detail.startswith(NEEDS_UNREAD):
            unread[detail] = unread.get(detail, 0) + 1
        elif why == "replay_failed":
            add(why, cid, detail, ["mrg"] * (st(cid) in ("bad", "stale")) + ["prt"] * (prt.get(cid) in FAILED_GROUPS))
        else:
            add(why, cid, detail, ["rdg"] * (cid in arcs))
    for cid, c in mrg.items():  # the merge graph's "replaced by a later criterion": those not holding when last run
        if c.get("rep") and c.get("st") in ("bad", "stale"):
            add("replaced_stopped", cid, f"{c.get('why')} when last run, at #{c.get('lp')}", ["mrg"])
    for cid, c in index.items():
        if c.get("state") == "open":
            add("not_ticked", cid, "", ["prt"] * (prt.get(cid) == "open") + ["mrg"] * (st(cid) == "due") + ["rdg"] * (cid in gap))
    for p in (d.get("user_stories") or {}).get("problems") or []:
        pr = re.match(r"#\d+\s+", p)
        rest = p[pr.end():] if pr else p
        add("story", pr.group().strip() if pr else p, rest[:1].upper() + rest[1:])
    for p in (d.get("gel") or {}).get("panels") or []:
        if p.get("verdict") == "worse":
            places = p.get("decimals") or 0  # an average of whole numbers is seldom whole: one place more for it
            fig = lambda v, k: ("$" if p.get("unit") == "$" else "") + f"{v:,.{k}f}"  # noqa: E731
            add("yardstick", p.get("name"), f"{fig(p['last']['value'], places)} on Day {p['last']['day']}, above its average "
                                             f"so far of {fig(p['average'], places or int(p['average'] != int(p['average'])))}", ["gel"])
    for c in (d.get("gene") or {}).get("commitments") or []:
        if c.get("uncovered"):
            owed = f"; specs/plan/overdue.json records it, to be settled by Day {c['settled_by']}" if c.get("settled_by") else ""
            add("due", c["id"], f"{c.get('owner_day')}, and no criterion in force names it{owed}", ["gene", "g12"], c.get("owner_day"))
        elif c.get("cls") in ("unproved", "unreplayable"):
            add("commitment_" + c["cls"], c["id"], "", ["gene"])
    for cid, state in prt.items():
        if state in ("unproven", "skipped"):
            add("unproven" if state == "unproven" else "unreplayable", cid, "",
                ["prt"] + ["mrg"] * (st(cid) == ("un" if state == "unproven" else "none")))
    worst = lambda x: (rank[x["group"]], whys.index(x["why"]) if x["why"] in whys else len(whys))  # noqa: E731
    items = []
    for got in found.values():  # an id once: its worst group, and every sentence said of it there
        got.sort(key=worst)
        top = [x for x in got if x["group"] == got[0]["group"]]
        items.append(dict(top[0], text=" ".join(dict.fromkeys(x["text"] for x in top)),
                          graphs=[g for g in NEEDS_GRAPHS if any(g in x["graphs"] for x in top)]))
    items.sort(key=lambda x: (*worst(x), x["day"] is None, x["day"] or 0, _order(x["id"]), str(x["id"])))
    lines, shared = [], ("group", "mark", "why", "text", "graphs")
    for x in items:
        if not lines or any(lines[-1][k] != x[k] for k in shared):
            lines.append(dict({k: x[k] for k in shared}, ids=[]))
        lines[-1]["ids"].append(dict(id=x["id"], day=x["day"]))
    n = {g[0]: sum(1 for x in items if x["group"] == g[0]) for g in NEEDS_GROUPS}
    chips = {}
    for g in NEEDS_GRAPHS:
        # a chip is its graph's own figure: an id the list shows under a worse mark still counts in it
        held = [dict(mark=m, name=name, n=sum(1 for got in found.values() if any(x["mark"] == m and g in x["graphs"] for x in got)))
                for m, name in NEEDS_CHIPS.items()]
        if any(c["n"] for c in held):
            chips[g] = [c for c in held if c["n"]]
    known = sorted(x["day"] for x in d.get("days") or [] if isinstance(x.get("day"), int))
    under = lambda day: [x for x in items if (x["day"] if x["day"] in known else None) == day]  # noqa: E731
    return dict(_stamp(d), count=sum(n[k] for k in NEEDS_COUNTED),
                groups=[dict(key=k, name=name, sub=sub, n=n[k]) for k, name, sub in NEEDS_GROUPS if k in NEEDS_COUNTED],
                folded=[dict(key=k, name=name, n=n[k]) for k, name, _ in NEEDS_GROUPS if k not in NEEDS_COUNTED],
                lines=lines, chips=chips,
                days=[dict(day=day, n=sum(1 for x in under(day) if x["group"] in NEEDS_COUNTED),
                           marks=[dict(mark=x["mark"], id=x["id"]) for x in under(day)]) for day in known + [None]],
                unread=[dict(text=k, n=v) for k, v in unread.items()])
