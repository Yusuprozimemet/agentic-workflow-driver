"""Graph 10: the clock as an actogram, a lane per actor (`actogram`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

import datetime
import math
import re

from spec_drift_view_common import _MONTHS, _lower_median, _ms, _offset


# Graph 10's actors, in its lane order, and what a session waited on (scripts/token-usage.py's RUN_KINDS).
ACT_LANES = ("main", "implementer", "auditors", "other")


ACT_RUNS = ("tests", "checks", "other")


ACT_PR_KINDS = ("spec", "code", "close", "other")  # dashboard.js's KINDS but the first commit


_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _act_lane(agent):
    """graph 10's laneOf: the main session, the implementer, the auditors (the defect-rater with them), the rest."""
    if agent in ("main", "implementer"):
        return agent
    return "auditors" if re.search(r"-auditor$|^defect-rater$", agent or "") else "other"


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


def _twice(spans):
    """The stretches two or more of the spans share, merged, in order."""
    over, end = [], -math.inf
    for a, b in sorted(spans, key=lambda s: s[0]):
        if a < end:
            over.append([a, min(b, end)])
        end = max(end, b)
    return _union(over)


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
    the lower median of the pull requests merged on it. Minutes are counted from the date's 05:00, rounded to 0.1.

    A row of the page has five lanes, and each date carries what they draw. The main session: `segs` of kind main,
    the waits of `wait_segs` whose lane is 0, and `two`, the stretches two or more main sessions were busy at once
    (`two_min` their minutes). The sub-agents: `subs`, every session that is not the main one, two at once drawn once
    (`sub` its minutes), and the waits whose lane is 1. The pull requests: `prs`, each one open on the date, from its
    opening to its merge, to its close without a merge, or to the date's end while it is still open, as graph 10
    draws them; one that opens while an earlier full-height bar is still open is `half`. Their checks: `checks`, each
    stretch the workflow runs were running as [from, to, failed, pr], or the first start to the last end where the
    stretches were not kept (`checks_min` its minutes, a minute two of them share counted once). The merges:
    `merges`."""
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

    def pr_kind(p):
        return p.get("kind") if p.get("kind") in ACT_PR_KINDS else "other"

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
        spans, main_spans, sub_spans, wait_segs = [], [], [], []
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
                        wait_segs.append([_r1(x[0]), _r1(x[1]), kind_of(r), 0 if k == "main" else 1])  # the lane it is drawn in
                if s.get("day") is not None:
                    days.add(s["day"])
            for i in range(3):
                ran[i] += sum(m[i] for m in bar_ran)
            busy = _covered([c for _, c in mine])
            lanes[k], waits[k] = _r1(busy), _r1(min(busy, sum(sum(m) for m in bar_ran)))
            spans += [c for _, c in mine]
            if k == "main":
                main_spans = [c for _, c in mine]
            else:
                sub_spans += [c for _, c in mine]
        for p in prs:
            if any(t and date_of(t) == date for t in (p["opened"], p.get("merged"))) and p.get("day") is not None:
                days.add(p["day"])
        # The pull requests open on the date and the stretches their checks ran, by graph 10's rule (clockGraph).
        open_prs, checks = [], []
        for p in prs:
            end = p.get("merged") or p.get("closed")
            a, b = (_ms(p["opened"]) - start) / 60000, (_ms(end) - start) / 60000 if end else math.inf
            if b >= 0 and a <= 1440:
                open_prs.append(dict(pr=p.get("number"), **{"from": max(0, a)}, to=min(1440, max(b, a)), kind=pr_kind(p), half=False,
                                     state="merged" if p.get("merged") else "closed" if end else "open",
                                     wait=_r1(whole(p["opened"], end)) if end else None, cut=a < 0, day=p.get("day")))
            ch = p.get("checks") or {}
            for run in ch.get("spans") or [[ch.get("start"), ch.get("end"), ch.get("failed")]]:
                x = clip(date, run[0], run[1]) if run[0] and run[1] else None
                if x:
                    checks.append([x[0], x[1], 1 if len(run) > 2 and run[2] else 0, p.get("number")])
        # A pull request that opens while an earlier full-height bar is still open is drawn at half height under it.
        open_prs.sort(key=lambda bar: bar["from"])
        full_to = -math.inf
        for bar in open_prs:
            bar["half"] = bar["from"] < full_to
            if not bar["half"]:
                full_to = bar["to"]
            bar["from"], bar["to"] = _r1(bar["from"]), _r1(bar["to"])
        checks.sort(key=lambda c: c[0])
        checks_min = _covered([c[:2] for c in checks])
        checks = [[_r1(a), _r1(b), failed, pr] for a, b, failed, pr in checks]
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
        two = _twice(main_spans)
        out.append(dict(
            date=date, label=f"{int(dd)} {_MONTHS[int(m) - 1]}", weekday=_WEEKDAYS[datetime.date.fromisoformat(date).weekday()],
            days=sorted(days), lanes=lanes, waits=waits,
            ran=[_r1(x) for x in ran], merged=len(merges), median=_r1(_lower_median(true)) if true else None, busy=_r1(_covered(spans)), main=_r1(_covered(main_spans)), up_to=_r1(up_to),
            segs=segs, wait_segs=sorted(wait_segs, key=lambda s: s[0]), merges=merges,
            subs=[[_r1(a), _r1(b)] for a, b in _union(sub_spans)], sub=_r1(_covered(sub_spans)),
            two=[[_r1(a), _r1(b)] for a, b in two], two_min=_r1(sum(b - a for a, b in two)),
            prs=open_prs, open=len(open_prs), checks=checks, checks_min=_r1(checks_min),
            session=bool(spans)))
    worked = [x for x in out if x["session"]]
    whole_dates = [x for x in worked if x["up_to"] == 1440]
    all_waits = [(whole(p["opened"], p["merged"]), p.get("number")) for p in merged_all]
    busy, ran = sum(x["busy"] for x in worked), [sum(x["ran"][i] for x in out) for i in range(3)]
    longest = max(all_waits, key=lambda w: w[0]) if all_waits else None  # the first of the longest
    totals = dict(
        dates=len(worked), first=worked[0]["date"] if worked else None, last=worked[-1]["date"] if worked else None,
        busy=_r1(busy), main=_r1(sum(x["main"] for x in worked)), ran=[_r1(r) for r in ran],
        two=_r1(sum(x["two_min"] for x in out)), sub=_r1(sum(x["sub"] for x in out)),
        waiting_share=sum(ran) / busy if busy else None, merged=len(merged_all),
        median=_r1(_lower_median([w for w, _ in all_waits])) if all_waits else None,
        over_hour=sum(1 for w, _ in all_waits if w > 60),
        longest=dict(pr=longest[1], wait=_r1(longest[0])) if longest else None,
        after_midnight=sum(1 for x in whole_dates if any(s[1] > 1140 for s in x["segs"])), whole=len(whole_dates))
    return dict(missing=_act_missing(d), zone=zone_text, counted=counted, dates=out, totals=totals)
