"""Graph 7's One Day ring: one Day step by step, each defect at the step it was caught (`one_day`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

import re

from spec_drift_view_budget import _part
from spec_drift_view_common import _quote, _stamp
from spec_drift_view_proofreading import _tag


# A Defect line's at: is read from this Day on (specs/README.md): before it, a line is placed from its found: alone.
ONE_DAY_FROM = 16


# The first Day whose close has a rehearsal and a replay: spec_drift_metrics.SPLIT_FROM, which imports numpy.
ONE_DAY_SPLIT = 12


# Each agent as the Day's steps name it: its name, what it does, and the [step kind, sub] pairs it covers.
ONE_DAY_ROLES = {
    "main": ("Main session", "runs each step and starts the others", [["*", "*"]]),
    "plan-auditor": ("Plan-auditor", "reads the phase's specs against the plan", [["audit", "audit"]]),
    "spec-auditor": ("Spec-auditor", "runs every check of the Day's spec", [["audit", "*"]]),
    "track-reviewer": ("Track-reviewer", "reads each track's brief and diff", [["code", "brief"], ["code", "diff"]]),
    "implementer": ("Implementer", "writes the code and tests from a brief", [["code", "build"]]),
    "defect-rater": ("Defect-rater", "labels the Day's defects blind", [["close", "rehearsal"]]),
}


# An at: value and a found: value, through _tag, as the (step, sub) they place a line on; a track is read apart.
ONE_DAY_AT = {"audit": ("audit", "audit"), "recheck": ("audit", "recheck"), "spec-change pr": ("spec", "pr"),
              "close": ("close", "pr"), "rehearsal": ("close", "rehearsal"), "replay": ("close", "replay")}


ONE_DAY_FOUND = {"auditor": ("audit", None), "spec-change pr": ("spec", "pr"), "close": ("close", "pr"),
                 "rehearsal": ("close", "rehearsal"), "evidence replay": ("close", "replay")}


def _one_day_subs(kind, day):
    if day >= ONE_DAY_FROM:
        return dict(audit=["audit", "recheck"], spec=["pr"], code=["brief", "build", "diff", "pr"],
                    close=["rehearsal", "pr", "replay"])[kind]
    return dict(audit=[], spec=["pr"], code=["build"], close=["rehearsal", "pr", "replay"] if day >= ONE_DAY_SPLIT
                else [])[kind]


def _one_day_track(name, keys):
    """The track step a found: or at: value names ("c1"), as merged_tracks reads a branch: the whole name, then
    without its last letter part, then its first character, the first that is one of the keys; else None."""
    m = re.fullmatch(r"([0-9a-z])([0-9]*)([a-z]?)", name)
    by_lower = {k.lower(): k for k in keys}
    return next((by_lower[t] for t in [name] + ([m.group(1) + m.group(2), m.group(1)] if m else []) if t in by_lower),
                None)


def _one_day_place(v, day, keys, tracks, table):
    """(step, sub) for an at: value (table ONE_DAY_AT) or a found: one (ONE_DAY_FOUND), or None when it names no
    step the Day has."""
    if table is ONE_DAY_AT and (m := re.fullmatch(r"track (\S+) (brief|build|diff|pr)", v)):
        step, sub = _one_day_track(m.group(1), tracks), m.group(2)
    elif table is ONE_DAY_FOUND and (m := re.fullmatch(r"track (\S+)", v)):
        step, sub = _one_day_track(m.group(1), tracks), "build"
    elif table is ONE_DAY_FOUND and (v == "dashboard" or re.fullmatch(r"day \d+ review", v)):
        return "after", None
    elif v in table:
        step, sub = table[v]
        if table is ONE_DAY_FOUND and step == "close" and day < ONE_DAY_SPLIT:
            sub = None
    else:
        return None
    return (step, sub) if step in keys else None


def one_day(d):
    """One Day step by step: its steps, each Defect line placed on one, its criteria per step, its agents and totals.

    A Day's steps are its audit (shown when a line is placed on it or an auditor spent on the Day), one step per spec
    PR, one per track holding all its PRs (the track read from the branch as merged_tracks reads it), its close,
    then each listed track with no PR yet, and a close with none. A line is placed from its at: (from ONE_DAY_FROM;
    one off the Day's steps, or written earlier, is a problem and the line falls back), else from its found:. A line
    on "after" was found after the Day; one with no step is counted, from ONE_DAY_FROM, in no_step."""
    from spec_drift_specs import merged_tracks

    rows = [r for r in d.get("rows") or [] if isinstance(r, dict)]
    days, problems, late, of = [], [], [], 0
    for x in d.get("days") or []:
        day = x.get("day")
        if not isinstance(day, int):
            continue
        tracks, groups, specs = x.get("tracks") or [], {}, 0
        for r in (r for r in rows if r.get("own_day") == day):
            kind, named = r.get("kind"), merged_tracks([r.get("branch") or ""], tracks)
            if kind == "spec":
                specs += 1
                key, name = ("spec", "Spec change") if specs == 1 else (f"spec{specs}", f"Spec change {specs}")
            elif kind == "code" and named:
                key, name = named[0], f"Track {named[0]}"
            elif kind == "close":
                key, name = "close", "Close"
            else:
                continue
            step = groups.setdefault(key, dict(key=key, name=name, kind=kind, prs=[], date=r.get("date"),
                                               title=r.get("title") or "", subs=_one_day_subs(kind, day)))
            step["prs"].append(r.get("pr"))
        for key, kind in [(t, "code") for t in tracks] + [("close", "close")]:
            groups.setdefault(key, dict(key=key, name="Close" if kind == "close" else f"Track {key}", kind=kind,
                                        prs=[], date=None, title="", subs=_one_day_subs(kind, day)))
        audit = dict(key="audit", name="Audit", kind="audit", prs=[], date=None, title="",
                     subs=_one_day_subs("audit", day))
        keys, code = {"audit", *groups}, [k for k, s in groups.items() if s["kind"] == "code"]
        spent = {}
        for t in d.get("tokens") or []:
            if isinstance(t, dict) and _part(t) == (0, day):
                a = spent.setdefault(str(t.get("agent") or ""), [0, 0])
                a[0], a[1] = a[0] + (t.get("replies") or 0), a[1] + (t.get("cost") or 0)
        lines = []
        for f in x.get("defects") or []:
            at, got, by = f.get("at"), None, None
            if at is not None and day < ONE_DAY_FROM:
                problems.append(f"Day {day}: {f.get('id')} has at: before Day {ONE_DAY_FROM}")
            elif at is not None:
                got, by = _one_day_place(_tag(at), day, keys, code, ONE_DAY_AT), "at"
                if not got:
                    problems.append(f'Day {day}: {f.get("id")} at: "{at}" is not a step of the Day')
            if not got:
                got, by = _one_day_place(_tag(f.get("found")), day, keys, code, ONE_DAY_FOUND), "found"
            text = f.get("text") or ""
            lines.append(dict(id=f.get("id"), found=f.get("found"), cause=_tag(f.get("cause")), same=f.get("same_as"),
                              text=text if len(text) <= 260 else text[:259] + "…", step=got[0] if got else None,
                              sub=got[1] if got else None, by=by if got else None))
        steps = ([audit] if any(n["step"] == "audit" for n in lines) or {"plan-auditor", "spec-auditor"} & set(spent)
                 else []) + list(groups.values())
        mine = [c for c in d.get("criteria_index") or [] if isinstance(c, dict) and c.get("id") and c.get("day") == day]
        crit = []
        for c in mine:
            step = _one_day_track(str(c["track"]).lower(), code) if c.get("track") else None
            step = step or next((s["key"] for s in steps if set(s["prs"]) & set(c.get("prs") or [])), None)
            crit.append(dict(_quote(c, c.get("plain") or ""), step=step))
        order = list(ONE_DAY_ROLES)
        agents = [dict(agent=a, name=ONE_DAY_ROLES.get(a, (a,))[0], does=ONE_DAY_ROLES.get(a, (a, ""))[1],
                       replies=spent[a][0], cost=round(spent[a][1], 4),
                       covers=[list(p) for p in ONE_DAY_ROLES.get(a, (a, "", []))[2]])
                  for a in sorted(spent, key=lambda a: (order.index(a) if a in order else len(order), a))]
        placed = [n for n in lines if n["step"] not in (None, "after")]
        totals = dict(prs=sum(len(s["prs"]) for s in steps), new=sum(c["tag"] == "new" for c in crit),
                      hold=sum(c["tag"] == "hold" for c in crit), ticked=sum(c.get("ticked") is True for c in mine),
                      cost=round(sum(a["cost"] for a in agents), 2), replies=sum(a["replies"] for a in agents),
                      defects=len(lines), placed=len(placed), no_step=sum(n["step"] is None for n in lines),
                      after=sum(n["step"] == "after" for n in lines))
        if day >= ONE_DAY_FROM:
            of += len(lines)
            late += [n["id"] for n in lines if n["step"] is None]
        days.append(dict(day=day, title=x.get("title"), status=x.get("status"), steps=steps, defects=lines,
                         criteria=crit, agents=agents, totals=totals))
    return dict(_stamp(d), from_day=ONE_DAY_FROM, days=days, problems=problems,
                no_step=dict(lines=len(late), of=of, ids=late))


def one_day_line(v):
    """The build's line: how many Defect lines from ONE_DAY_FROM take no step."""
    n = v["no_step"]
    return f"defect steps: {n['lines']} of {n['of']} Defect lines from Day {v['from_day']} take no step"
