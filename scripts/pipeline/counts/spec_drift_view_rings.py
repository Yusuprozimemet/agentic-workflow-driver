"""Graph 9: the files as growth rings (`rings`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

import datetime

from spec_drift_view_common import _placed, _plain, _round, _stamp


# Graph 9 as growth rings (the mockup at #228's rng): the kinds of file, in the bands' order, top to bottom. Specs
# and agent context are two bands.
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
    below, one hatched ring for the work no Day owns, at the Day it is placed beside (`_placed`'s `at`: the
    furthest Day begun when it merged). Rows before Day 1 began are "before Day 1": counted, in no ring.
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
