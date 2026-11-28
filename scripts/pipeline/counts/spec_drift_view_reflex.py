"""Graph 11: the driver's steps as reflex arcs (`reflex`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

import datetime
import re

from spec_drift_view_common import _MONTHS, _list, _lower_median, _ms, _n, _offset, _plain, _runs


# Graph 11 as reflex arcs: how a step ended, as the mark at the end of its row (`fin`) and the words beside it.
RFX_END = dict(merged="Merged, with no park", fixed="Merged after fixing itself", still="Still open, no park so far")


RFX_BY = dict(fault=("Parked by a fault", "parked by a fault", "The driver or the kit was at fault."),
              maintainer=("Parked for the maintainer", "parked for the maintainer", "A decision that is the maintainer's."))


RFX_GO = "the maintainer's go-ahead, which the plan requires at every pull request"


def _rfx_missing(d):
    """Why no step of the driver can be drawn: the dashboard-data branch or its driver-runs.json is missing, or the run
    log is not counted for this project."""
    src = d.get("data")
    if src and not src.get("commit"):
        return f"the {src.get('branch')} branch is missing, so no step of the driver is drawn."
    if src and "driver-runs.json" in (src.get("absent") or []):
        return f"the {src.get('branch')} branch has no driver-runs.json, so no step of the driver is drawn."
    if (d.get("driver_runs") or {}).get("steps") is None:
        return "the driver's run log is not counted for this project yet, so no step is drawn."
    return None


def _rfx_label(step):
    """A step's sentence as its row names it: before the first ": ", with the criteria after it as the row's sub line;
    a sentence whose second part names no criteria keeps it ("Day 13: the closing PR")."""
    parts = _plain(step).split(": ")
    if len(parts) > 1 and re.match(r"C\d", parts[1]):
        return parts[0], parts[1]
    label = ": ".join(parts[:2])
    return (label if len(label) <= 38 else label[:37].rstrip() + "…"), None


def _said(label):
    """A step's label inside a sentence: one that is a sentence of its own ("Every day is done.") is quoted."""
    return f'"{label}"' if label[-1:] in ".!?" else label


def _ago(seconds):
    """A short time between two moments: seconds under a minute and a half, else whole minutes."""
    return f"{round(seconds)} s" if seconds < 90 else f"{round(seconds / 60)} min"


def reflex(d):
    """Graph 11 as reflex arcs: one row per step the driver started, in its run log's order, read left to right from
    the step, through its sessions, to its pull request; a step that parked climbs to the band of the person. The
    counts of steps, parks, crashed steps, open and merged steps are _runs()'s, the proteins' "In real runs". No park
    is given a wait: a park names no issue whose closing would time it, so only the next session's start is said."""
    runs_of = d.get("driver_runs") or {}
    steps = runs_of.get("steps") or []
    counted = runs_of.get("counted")
    zone = _offset(counted)
    zone_text = "UTC" if not zone else f"UTC{'+' if zone > 0 else '−'}" + (
        str(abs(zone) // 60) if abs(zone) % 60 == 0 else f"{abs(zone) // 60:02d}:{abs(zone) % 60:02d}")

    def local(stamp):
        return datetime.datetime.fromtimestamp(_ms(stamp) / 1000 + zone * 60, datetime.timezone.utc)

    def when(stamp):
        t = local(stamp)
        return f"{t.day} {_MONTHS[t.month - 1]} {t:%H:%M}"

    def secs(a, b):
        return (_ms(b) - _ms(a)) / 1000

    runs = _runs(steps)
    rows, tips, dates = [], {}, set()
    for i, s in enumerate(steps):
        label, crit = _rfx_label(s.get("step"))
        day = s.get("day")
        where = f"project's Day {day}" if day is not None else "no project Day"
        sessions, parks = s.get("sessions") or [], s.get("parks") or []
        first = min([x["start"] for x in sessions if x.get("start")] + [p["at"] for p in parks if p.get("at")], default=None)
        if first:
            dates.add(local(first).date())
        ses = []
        for j, x in enumerate(sessions):
            crashed = bool(x.get("crashed")) or not x.get("end")
            minutes = None if crashed else round(secs(x["start"], x["end"]) / 60)
            fixes, denied = x.get("fixes") or 0, x.get("denials") or 0
            ses.append(dict(crashed=crashed, minutes=minutes, cost=x.get("cost") or 0, fixes=fixes, denials=denied))
            t = local(x["start"])
            head = (f"Started {when(x['start'])} ({zone_text}). The run log has no end for it: it crashed." if crashed else
                    f"{t.day} {_MONTHS[t.month - 1]}, {t:%H:%M} to {local(x['end']):%H:%M} ({zone_text}): {minutes} min.")
            tips[f"s{i}x{j}"] = dict(
                t=f"Session {j + 1} of {len(sessions)}" + (" · crashed" if crashed else ""),
                l=[head, f"{'No fix round' if not fixes else _n(fixes, 'fix round')}. "
                         f"{'No tool call refused' if not denied else _n(denied, 'tool call') + ' refused'}. "
                         f"${x.get('cost') or 0:.2f} at API list prices."],
                a=f"{label}, Session {j + 1} of {len(sessions)}" + (" · crashed" if crashed else ""))
        pk = []
        for j, p in enumerate(parks):
            by = p.get("by") if p.get("by") in RFX_BY else "maintainer"
            before = [k for k, x in enumerate(sessions) if x.get("start") and p.get("at") and _ms(x["start"]) <= _ms(p["at"])]
            after = [k for k, x in enumerate(sessions) if x.get("start") and p.get("at") and _ms(x["start"]) > _ms(p["at"])]
            up, back = (before[-1] if before else None), (after[0] if after else None)
            later = (f"the next session started {_n(round(secs(p['at'], sessions[back]['start']) / 60), 'minute')} later"
                     if back is not None else "no session started after it in this step")
            went = ("It went up before any session ran." if up is None else
                    f"It went up at session {up + 1} of {len(sessions)}" + (", which crashed." if ses[up]["crashed"] else "."))
            known = (f"It names issue #{p['issue']}; how long a person was needed is not counted here." if p.get("issue") else
                     "How long a person was needed is not known: the park names no issue.")
            pk.append(dict(by=by, up=up, back=back, at=when(p["at"]) if p.get("at") else None, later=later, issue=p.get("issue")))
            tips[f"s{i}p{j}"] = dict(
                t=f"{RFX_BY[by][0]} · {when(p['at'])} ({zone_text})" if p.get("at") else RFX_BY[by][0],
                l=[f"{RFX_BY[by][2]} {went}",
                   f"It came back down at session {back + 1}: {later}." if back is not None else f"It did not come back: {later}.",
                   known],
                q=_plain(p.get("line")) or None, a=f"{label}, {RFX_BY[by][0]}" + (f" · {when(p['at'])} ({zone_text})" if p.get("at") else ""))
        ended = s.get("ended")
        last_by = pk[-1]["by"] if pk else None
        fin = (("fault" if last_by == "fault" else "maint") if pk else "still" if ended == "open"
               else "fixed" if ended == "fixed" or (ended == "merged" and s.get("fixes")) else "merged" if s.get("merged") else "maint")
        how = (f"{RFX_BY[last_by][1]}" if pk else "still open" if fin == "still" else
               "merged after fixing itself" if fin == "fixed" else "merged with no park" if fin == "merged" else _plain(ended) or "ended")
        end = (RFX_BY[last_by][0] + (", then merged" if s.get("merged") else "") if pk else RFX_END.get(fin) or "Stopped")
        crashed_n, ran = sum(x["crashed"] for x in ses), sum(x["minutes"] or 0 for x in ses)
        cost = sum(x["cost"] for x in ses)
        bits = ([_n(len(ses), "session") + (f", {crashed_n} crashed" if crashed_n else ""), f"{ran} min", f"${cost:.2f}"]
                if ses else ["no session"])
        pr = None
        if s.get("pr") is not None:
            ends = [x.get("end") for x in sessions if x.get("end")]
            after = secs(max(ends, key=_ms), s["merged"]) if s.get("merged") and ends else None
            pr = dict(number=s["pr"], state="merged" if s.get("merged") else "open", after=None if after is None else round(after))
            if pr["state"] == "open":
                bits.append("go-ahead awaited")
            tips[f"s{i}r"] = dict(
                t=f"Pull request #{s['pr']} · {pr['state']}",
                l=([f"Merged {when(s['merged'])} ({zone_text})" + (f", {_ago(after)} after its last session ended." if after is not None else "."),
                    f"The merge is {RFX_GO}. It is not a park.", f"The step ended {how}."] if pr["state"] == "merged" else
                   ["Opened by the step; not merged when the run log was counted.",
                    f"It waits for {RFX_GO}. That is not a park.", "The step is still open."]),
                a=f"{label}, Pull request #{s['pr']} · {pr['state']}")
        else:
            tips[f"s{i}r"] = dict(t=f"No pull request · {how}",
                                  l=["The step opened none: " + (f"it ran {_n(len(ses), 'session')}." if ses else "it ran no session."),
                                     "So no go-ahead was asked for it."],
                                  a=f"{label}, No pull request · {how}")
        tips[f"s{i}"] = dict(
            t=f"{where[0].upper() + where[1:]} · step {i + 1} of {len(steps)}",
            l=[_plain(s.get("step")),
               f"Branch prefix {s['prefix']}." if s.get("prefix") else
               "It has no branch: the driver started no session for it." if not ses else "It has no branch.",
               f"First seen in the run log at {when(first)} ({zone_text})." if first else "",
               "It is still open." if fin == "still" else f"It ended {how}."],
            a=f"{where[0].upper() + where[1:]} · step {i + 1} of {len(steps)}: {label}")
        tips[f"s{i}"]["l"] = [x for x in tips[f"s{i}"]["l"] if x]
        rows.append(dict(label=label, sub=where + (f" · {crit}" if crit else ""), day=day, sessions=ses, parks=pk, pr=pr,
                         fin=fin, end=end, end_sub=" · ".join(bits), ended=ended))

    n = len(rows)
    ended = [r for r in rows if r["fin"] != "still"]
    alone = [r for r in ended if not r["parks"]]
    parked = [r for r in rows if r["parks"]]
    by_fault = sum(1 for r in parked if r["parks"][-1]["by"] == "fault")
    by_day = {}
    for r in rows:
        by_day[r["day"]] = by_day.get(r["day"], 0) + 1
    split = [f"{k} on the project's Day {day}" if i == 0 else f"{k} on Day {day}"
             for i, (day, k) in enumerate((day, k) for day, k in sorted(by_day.items(), key=lambda kv: (kv[0] is None, kv[0] or 0)) if day is not None)]
    if None in by_day:
        split.append(f"{by_day[None]} with no Day")
    all_ses = [x for r in rows for x in r["sessions"]]
    per = sorted(len(r["sessions"]) for r in rows)
    crashed_ses, fixes = sum(x["crashed"] for x in all_ses), sum(x["fixes"] for x in all_ses)
    none_ran = sum(1 for r in rows if not r["sessions"])
    opened = [r for r in rows if r["pr"]]
    merged = [r for r in opened if r["pr"]["state"] == "merged"]
    still = [r for r in opened if r["pr"]["state"] == "open"]
    too_few = f"All on {_n(len(dates), 'date')}: too few to judge by." if len(dates) < 5 else f"On {len(dates)} dates."
    figs = [
        dict(num=str(n), small=None, what="step the driver started" if n == 1 else "steps the driver started",
             sub=(_list(split) + ". " if split else "") + too_few),
        dict(num=str(len(alone)), small=f"of {len(ended)} ended", what="finished without a park",
             sub=f"{len(parked)} parked" + (f": {by_fault} by a fault and {len(parked) - by_fault} for the maintainer" if parked else "")
             + "." + (f" {len(rows) - len(ended)} more {'is' if len(rows) - len(ended) == 1 else 'are'} still open." if len(rows) > len(ended) else "")),
        dict(num=str(_lower_median(per) if per else 0), small=None,
             what="session a step, at the median" if (_lower_median(per) if per else 0) == 1 else "sessions a step, at the median",
             sub=f"{_n(len(all_ses), 'session')} in {_n(n, 'step')}: {crashed_ses} crashed, "
             + ("no fix round" if not fixes else _n(fixes, "fix round")) + "." + (f" {_n(none_ran, 'step')} ran none." if none_ran else "")),
        dict(num=str(len(merged)), small=f"of {len(opened)} opened", what="pull requests merged" if len(merged) != 1 else "pull request merged",
             sub="Each on the maintainer's go-ahead." + (f" {_list(['#' + str(r['pr']['number']) for r in still])} "
                                                       f"{'is' if len(still) == 1 else 'are'} still open." if still else "")),
    ]
    l2 = runs_of.get("level_2")
    if l2:
        tips["l2"] = dict(t=f"Trial for level 2: {l2.get('run')} of {l2.get('of')} in a row",
                          l=[f"{_n(l2.get('run') or 0, 'pull request')} in a row with no change asked, of the {l2.get('of')} the plan asks for.",
                             "At level 2 the driver merges, and the go-ahead mark leaves the rows. The driver's own count, as graph 1's level card shows it."],
                          a=f"Trial for level 2: {l2.get('run')} of {l2.get('of')} in a row")
    afters = [r["pr"]["after"] for r in merged if r["pr"]["after"] is not None]
    cost, ran = sum(x["cost"] for x in all_ses), sum(x["minutes"] or 0 for x in all_ses)
    finds = []
    if ended:
        finds.append(["good", f"{len(alone)} of the {len(ended)} steps that ended needed no park.",
                      _list([_said(r["label"]) for r in alone]) + (": one session each." if alone and all(len(r["sessions"]) == 1 for r in alone) else ".")
                      if alone else "Every step that ended parked at least once."])
    for r in parked:
        p = r["parks"][-1]
        cls = "fault" if p["by"] == "fault" else "maint"
        if p["back"] is not None:
            finds.append([cls, f"{_said(r['label'])} went up {'for a fault' if cls == 'fault' else 'for the maintainer'}, and came back.",
                          f"The driver parked at {p['at'][-5:]}; {p['later']}"
                          + (f" and pull request #{r['pr']['number']} {'merged' if r['pr']['state'] == 'merged' else 'is open'}." if r["pr"] else ".")])
        else:
            finds.append([cls, f"{_said(r['label'])} went up and stayed.",
                          f"It ran {_n(len(r['sessions']), 'session') if r['sessions'] else 'no session'} and opened "
                          + (f"pull request #{r['pr']['number']}" if r["pr"] else "no pull request") + ": "
                          + ("the park is a decision that is the maintainer's." if cls == "maint" else "the driver or the kit was at fault.")])
    if still:
        finds.append(["", f"{_n(len(still), 'step')} {'is' if len(still) == 1 else 'are'} still open.",
                      " ".join(f"{_said(r['label'])} opened pull request #{r['pr']['number']} after {_n(len(r['sessions']), 'session')}; the go-ahead has not come."
                               for r in still)])
    if opened:
        finds.append(["", "Every row with a pull request ends at the go-ahead.",
                      f"{_n(len(merged), 'pull request')} merged" + (f", {_ago(min(afters))} to {_ago(max(afters))} after the last session ended" if afters else "")
                      + (f"; {len(still)} awaited." if still else ".")])
    if all_ses:
        finds.append(["", f"{'No fix round' if not fixes else _n(fixes, 'fix round')} and {_n(crashed_ses, 'crash', 'crashes')} in {_n(len(all_ses), 'session')}.",
                      f"The sessions cost ${cost:.2f} at API list prices, and ran {ran} min in all."])
    if l2:
        finds.append(["", f"The trial for level 2 stands at {l2.get('run')} of {l2.get('of')}.",
                      "It counts pull requests in a row with no change asked. At level 2 the driver merges, and the go-ahead mark would leave the rows."])
    all_parks = [p for r in rows for p in r["parks"]]
    unnamed = sum(1 for p in all_parks if not p["issue"])
    bends = [
        ["Every arc still ends at a person.", "A reflex never asks the brain. Here the plan requires the maintainer's go-ahead at every pull request: "
         f"{len(merged)} given, {len(still)} awaited. So \"without a person\" means without a park, and nothing more."],
        ["A reflex is wired; these steps are chosen.", "The body's wiring fixes what a reflex does. The plan and the Day's spec choose each step here, "
         "and people wrote both."],
        [f"{_n(n, 'step')} prove little." if n < 30 else f"{n} steps are a start.",
         f"They ran on {_n(len(dates), 'date')}, on one project. A reflex is trusted because it has fired the same way countless times; "
         f"this picture has {_n(len(alone), 'clean run')} and {_n(len(all_parks), 'park')} to go on."],
        ["Distance along a row is order, not time.", "A short session and a long one are the same dot."
         + (f" How long a park kept a person is not known for {unnamed} of the {_n(len(all_parks), 'park')}: the park names no issue." if unnamed else "")],
    ]
    idle = [r for r in parked if not r["sessions"]]
    if idle:
        bends.append(["A park is not always a reflex that failed.", f"{_list([_said(r['label']) for r in idle])} ran no session: the driver stopped because "
                      "the plan had nothing more for it, which is the plan working."])
    t = local(counted) if counted else None
    return dict(
        missing=_rfx_missing(d), zone=zone_text, source=runs_of.get("source"), counted=counted,
        stamp=(f"the driver's run log counted up to {t:%H:%M} on {t.day} {_MONTHS[t.month - 1]} ({zone_text})" if t else "the driver's run log")
        + (f", from {runs_of.get('source')}" if runs_of.get("source") else ""),
        counts=dict(steps=len(steps), parks=len(runs["park"]), crashed=len(runs["recover"]), open=len(runs["open"]), merged=len(runs["loop"]),
                    ended=len(ended), alone=len(alone), crashed_sessions=crashed_ses),
        level_2=dict(run=l2.get("run"), of=l2.get("of")) if l2 else None,
        rows=rows, tips=tips, figs=figs, finds=finds, bends=bends,
        aria=f"{_n(n, 'step')} the driver started, one row each. {len(alone)} of the {len(ended)} that ended needed no park; "
        f"{_n(len(all_parks), 'park')} went up to the person.",
        hint="Point at a mark, or reach it with the Tab key, for the session, the park or the pull request."
        + (f" Only {_n(n, 'step')} on {_n(len(dates), 'date')} are counted: the picture is true, and proves little yet." if len(dates) < 5 else ""))
