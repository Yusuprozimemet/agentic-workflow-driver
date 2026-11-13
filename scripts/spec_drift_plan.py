"""spec-drift.py's plan graph: what `plan.md` commits to, and which criteria say they serve each commitment.

Read at the head commit, never from a reader: `specs/plan/promises.json` (the commitments), the backfill
`specs/plan/links-days-01-10.json` for Days 1 to 10, and each later criterion's own `Plan:` line, parsed with
`scripts/plan-links.py`'s patterns so the page and the check read one format. A project with no promise file
gets no plan graph, and the page says so.
"""

import importlib.util
import json
import os

from spec_drift_git import run

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("plan_links", os.path.join(HERE, "plan-links.py"))
plan_links = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plan_links)

PROMISES = "specs/plan/promises.json"
BACKFILL = "specs/plan/links-days-01-10.json"
# The plan a person approved: the first commit, which landed with Day 1's spec. P01 to P69 come from it.
REFERENCE = "2d64383"


def _json(text):
    try:
        return json.loads(text) if text.strip() else None
    except ValueError:
        return None


def plan_line_pairs(block):
    """The (commitment, quote) pairs one criterion's `Plan:` line names: a list (empty for `Plan: none`), or None
    with no line."""
    fields = plan_links.PLAN_FIELD.findall(block)
    if len(fields) != 1:
        return None
    value = plan_links.flat(fields[0])
    if plan_links.PLAN_NONE.fullmatch(value):
        return []
    return plan_links.PLAN_LINK.findall(value) or None


def plan_line_links(block):
    """The commitments one criterion's `Plan:` line names: a list (empty for `Plan: none`), or None with no line."""
    pairs = plan_line_pairs(block)
    return None if pairs is None else [pid for pid, _ in pairs]


def criterion_links(head, blobs, backfill, said=None):
    """Every criterion of every day spec at `head`, with the commitments it says it serves: the backfill for the
    Days it covers, the criterion's own `Plan:` line from Day 11 on. A criterion with no readable line is left
    out, and listed apart. Returns (links, quotes, unlined); `said`, when given, is filled with each criterion's
    quotes in the order of its links, for the page to show the line as written."""
    links, quotes, unlined = {}, 0, []
    for name in run("git", "ls-tree", "--name-only", head, "specs/").split():
        m = plan_links.DAY_FILE.fullmatch(os.path.basename(name))
        if not m:
            continue
        day = int(m.group(1))
        for cid, block in plan_links.CRITERION.findall(blobs.read(head, name)):
            if day in plan_links.BACKFILL_DAYS:
                pairs = [(x.get("p"), x.get("quote", "")) for x in backfill[cid] if isinstance(x, dict)] if cid in backfill else None
            elif day >= plan_links.PLAN_LINES_FROM:
                pairs = plan_line_pairs(block)
            else:
                pairs = None
            if pairs is None:
                unlined.append(cid)
                continue
            links[cid] = [pid for pid, _ in pairs]
            if said is not None:
                said[cid] = [quote for _, quote in pairs]
            quotes += len(pairs)
    return links, quotes, sorted(unlined)


def plan_rewrites(head, rows):
    """Each merge to `main` that changed `plan.md` after the plan was approved, and the last Day whose first
    pull request had merged before it: the Days above a rewrite wrote their criteria against the older plan."""
    changed = [s for s in run("git", "log", "--first-parent", "--format=%H", head, "--", "plan.md").split() if s]
    out, started = [], None
    for r in rows:
        if r.get("own_day") is not None and r.get("pr"):
            started = r["own_day"] if started is None else max(started, r["own_day"])
        sha = r.get("sha") or ""
        if sha and r.get("pr") and started is not None and any(c.startswith(sha) for c in changed):
            out.append(dict(pr=r["pr"], after_day=started))
    return out


def plan_graph(head, blobs, rows):
    """The plan graph's data, or None when the project keeps no promise file."""
    promises = _json(blobs.read(head, PROMISES))
    if not isinstance(promises, list):
        return None
    backfill = _json(blobs.read(head, BACKFILL))
    said = {}
    links, quotes, unlined = criterion_links(head, blobs, backfill if isinstance(backfill, dict) else {}, said)
    commitments = [dict(id=p.get("id"), short=p.get("short", ""), section=p.get("section", ""),
                        owner_day=p.get("owner_day"), rule=bool(p.get("rule_about_people")),
                        change=p.get("first_plan") if p.get("first_plan") in ("changed", "reworded") else None,
                        text=p.get("text", ""), note=p.get("change", ""))
                   for p in promises if isinstance(p, dict) and p.get("id")]
    return dict(reference=REFERENCE, commitments=commitments, links=links, said=said, quotes=quotes, unlined=unlined,
                rewrites=plan_rewrites(head, rows))
