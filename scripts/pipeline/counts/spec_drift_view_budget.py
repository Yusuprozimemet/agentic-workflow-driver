"""Graph 8: the dollars as an energy budget (`budget`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

from spec_drift_view_common import _finished, _round, _stamp
from spec_drift_view_proofreading import PRF_GUARDS


# Graph 8 as an energy budget: one bead for each BUDGET_UNIT dollars, placed by where the dollars went (a Day, or
# the work between Days by what it was), with what they bought and who spent them beside it. A row is split by kind
# by pricing its tokens again with token-usage.py's own list prices; one that comes out more than BUDGET_OFF off its
# recorded cost is not split.
BUDGET_UNIT = 2


BUDGET_OFF = 0.01


BUDGET_KINDS = ("re-reading", "writing context", "writing output", "not split")


BUDGET_WHO = ("main session", "auditors", "defect-rater", "implementer", "other agents")


# Where a row's dollars went, as token-usage.py placed them (`part`, `part_day`): a reply on a branch goes to that
# branch, a reply on main to the branch its session spent the most on. The first is the Days; the next four are the
# work between Days; the last is a row counted before the parts, on no Day's branch.
BUDGET_PARTS = ("the Days", "dashboard", "tooling", "other branches", "stayed on main", "not placed")


_BUDGET_PART = {"dashboard": 1, "tooling": 2, "main": 4, None: 5}


_TOKEN_USAGE = []


def _token_usage():
    """scripts/token-usage.py, loaded once: its PRICES and DATED are the list prices the dollars were counted with."""
    if not _TOKEN_USAGE:
        import importlib.util
        import os

        here = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir)  # scripts/
        spec = importlib.util.spec_from_file_location("token_usage", os.path.join(here, "token-usage.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _TOKEN_USAGE.append(module)
    return _TOKEN_USAGE[0]


def _who(agent):
    """Who spent a row's dollars, as an index of BUDGET_WHO."""
    a = str(agent or "")
    return 0 if a == "main" else 1 if "auditor" in a else 2 if a == "defect-rater" else 3 if a == "implementer" else 4


def _part(t):
    """Where a token row's dollars went: an index of BUDGET_PARTS, and the Day when it is a Day's. A row counted before
    the parts has no `part`: on a Day's branch it is that Day's, on none it is not placed."""
    part, day = (t.get("part"), t.get("part_day")) if "part" in t else ("day", t.get("day"))
    if part == "day":
        return (0, day) if day is not None else (5, None)
    return _BUDGET_PART.get(part, 3), None


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
    """One column's figures: its dollars, its beads, its dollars by kind and by who, its dollars past 150k (None when
    no row has the figure: a row without it is not known) and its replies."""
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
    return dict(u=sum(t.get("cost") or 0 for t in rows), b=beads, k=k, w=w,
                p=round(sum(t["cost_past_150k"] for t in known), 6) if known else None,
                pm=round(sum(t["cost_past_150k"] for t in main), 6) if main else None,
                rp=sum(t.get("replies") or 0 for t in rows))


def _guard_order(guards):
    return [g for g in PRF_GUARDS if g in guards] + sorted(str(g) for g in guards if g not in PRF_GUARDS)


def budget(d):
    """Graph 8's dollars as an energy budget: beads of BUDGET_UNIT dollars, in a column for each date with token rows,
    or in a column for each Day beside the work between Days, one block for each of its parts. Every figure, bead and
    share is counted here; dashboard.js lays them out.

    The whole beads are round(total / unit). By date they are shared out over the dates by largest remainder, and
    inside a date over the parts the same way; by Day they are shared out over the Days and the parts between them.
    A Day's dollars are its own branch's and its sessions' replies on main (`own`, `home`); the average Day is the
    mean of the closed Days that have a token row. With the dashboard-data branch or its token-usage.json missing,
    `empty` says why and nothing is drawn."""
    missing = _budget_missing(d)
    tokens = [] if missing else list(d.get("tokens") or [])
    out = dict(_stamp(d), unit=BUDGET_UNIT, kinds_named=list(BUDGET_KINDS), who_named=list(BUDGET_WHO),
               parts_named=list(BUDGET_PARTS))
    if missing or not tokens:
        out["empty"] = missing or ("no token counts yet: they are counted on the maintainer's computer and pushed to "
                                   "the dashboard-data branch.")
        return out
    tu = _token_usage()
    split, offs, placed = {}, [], {}
    for t in tokens:
        parts, off = _priced(t, tu)
        split[id(t)] = parts
        placed[id(t)] = _part(t)
        if parts is not None:
            offs.append(off)
    cost = lambda rows: sum(t.get("cost") or 0 for t in rows)  # noqa: E731
    by_part = lambda rows: [cost([t for t in rows if placed[id(t)][0] == i]) for i in range(len(BUDGET_PARTS))]  # noqa: E731
    total = cost(tokens)
    beads = _round(total / BUDGET_UNIT)
    days = sorted(d.get("days") or [], key=lambda x: x.get("day"))
    # a column for each date, and the Days worked on it (a Day is worked on a date within its `worked`)
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
        rf, pt = refused.get(x, {}), by_part(rows)
        date_cols.append(dict(_budget_col(rows, split, b), label=x, date=x, days=on, pt=pt, pb=_lr(pt, b),
                              rf=[[g, rf[g]] for g in _guard_order(rf)], refused=sum(rf.values()),
                              cut=sum(t.get("cut") or 0 for t in rows)))
    # a column for each Day the rows are placed on, and the work between Days: a block for each part with a row
    named = sorted({placed[id(t)][1] for t in tokens if placed[id(t)][0] == 0})
    by_day = [[t for t in tokens if placed[id(t)] == (0, k)] for k in named]
    rest = [i for i in range(1, len(BUDGET_PARTS)) if any(placed[id(t)][0] == i for t in tokens)]
    by_rest = [[t for t in tokens if placed[id(t)][0] == i] for i in rest]
    shares = _lr([cost(r) for r in by_day + by_rest], beads)
    done = {y.get("day") for y in days if _finished(y)}
    day_cols = []
    for k, rows, b in zip(named, by_day, shares):
        seen = sorted({t.get("date") for t in rows})
        own = cost([t for t in rows if t.get("day") is not None])
        col = _budget_col(rows, split, b)
        day_cols.append(dict(col, label=f"Day {k}", day=k, dates=[seen[0], seen[-1]], n_dates=len(seen), own=own,
                             home=col["u"] - own, closed=k in done))
    between = [dict(_budget_col(rows, split, b), part=i, label=BUDGET_PARTS[i],
                    n_dates=len({t.get("date") for t in rows}))
               for i, rows, b in zip(rest, by_rest, shares[len(named):])]
    # the average Day: the closed Days with a token row, by what each cost
    closed_cols = [i for i, c in enumerate(day_cols) if c["closed"]]
    costs = sorted(day_cols[i]["u"] for i in closed_cols)
    mean = sum(costs) / len(costs) if costs else None
    median = (costs[(len(costs) - 1) // 2] + costs[len(costs) // 2]) / 2 if costs else None
    for c in day_cols:
        c["over"] = c["u"] - mean if c["closed"] else None
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
    parts = by_part(tokens)
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
    guards = {}
    for c in date_cols:
        for g, n in c["rf"]:
            guards[g] = guards.get(g, 0) + n
    steps = (d.get("driver_runs") or {}).get("steps")
    sessions = [s for x in steps or [] for s in x.get("sessions") or []]
    first = lambda cols, f: max(range(len(cols)), key=lambda i: (f(cols[i]), -i)) if cols else None  # noqa: E731
    out.update(
        total=total, beads=beads, kinds=kinds, who=who, kind_pct=[pct(x) for x in kinds], who_pct=[pct(x) for x in who],
        parts=parts, part_pct=[pct(x) for x in parts],
        cols=dict(date=date_cols, day=day_cols, between=between), pills=pills, lanes=len(lanes),
        replies=sum(t.get("replies") or 0 for t in tokens), dates=len(dates),
        closed=closed, per_closed=total / closed if closed else None, built=built,
        on_days=parts[0], on_days_pct=pct(parts[0]), days_per_built=parts[0] / built if built else None,
        between=total - parts[0], between_pct=pct(total - parts[0]),
        own=sum(c["own"] for c in day_cols), home=sum(c["home"] for c in day_cols),
        mean=mean, median=median, mean_over=len(costs),
        dear_day=max(closed_cols, key=lambda i: (day_cols[i]["u"], -i), default=None),
        cheap_day=min(closed_cols, key=lambda i: (day_cols[i]["u"], i), default=None),
        past=past if known else None, past_pct=pct(past) if known else None,
        past_main=sum(t["cost_past_150k"] for t in known if t.get("agent") == "main") if known else None,
        past_unknown=len(tokens) - len(known),
        past_most=first(date_cols, lambda c: (c["p"] or 0) / (c["u"] or 1)) if known else None,
        split=dict(rows=len(tokens) - len(unsplit), dollars=sum(kinds[:3]), off=round(100 * max(offs), 2) if offs else None),
        unsplit=dict(rows=len(unsplit), dollars=kinds[3], models=sorted({model(t) or "no model" for t in unsplit})),
        furthest=round(max(abs(c["b"] - c["u"] / BUDGET_UNIT) for c in date_cols), 2),
        read_tokens_pct=_round(100 * sum(t.get("cache_read") or 0 for t in tokens) / all_tokens) if all_tokens else None,
        main_model=main_model, write_price=price[2] if price else None, read_price=price[3] if price else None,
        write_over_read=_round(price[2] / price[3]) if price and price[3] else None,
        dear=first(date_cols, lambda c: c["u"]), cheap=first(date_cols, lambda c: -c["u"]),
        refused=sum(guards.values()), guards=[[g, guards[g]] for g in _guard_order(guards)],
        most_refused=first(date_cols, lambda c: c["refused"]), cut=sum(c["cut"] for c in date_cols),
        driver=dict(steps=len(steps), sessions=len(sessions), cost=sum(s.get("cost") or 0 for s in sessions)) if steps else None,
        prices_checked=tu.PRICES_CHECKED,
    )
    return out
