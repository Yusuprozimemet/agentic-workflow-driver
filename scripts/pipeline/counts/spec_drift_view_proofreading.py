"""Graph 7: the checking as error correction, gate by gate (`proofreading`).
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

import datetime
import re

from spec_drift_view_common import _round, _stamp


# Graph 7's gates, in the order work passes them: `key` is the found: value a Defect line names, `name` graph 7's
# name for it and `at` how a sentence names it (they moved here from dashboard.js's GATES unchanged). `label`, `sub`
# and `does` are the proofreading stream's words for it, as the mockup at #228 has them.
PRF_FROM = 16  # the metrics module's PR_LAYERS_FROM: the Day from which CI and the driver's reviewer are gates


PRF_GATES = (
    dict(key="auditor", name="Auditors, before any code", at="the auditors", label="The auditors",
         sub="plan-auditor, spec-auditor",
         does="Before any code, the spec-auditor runs every check in the Day's spec on the code as it is and tries "
         "to break every hold; on a phase's first Day the plan-auditor reads the phase. The Notes do not say which "
         "auditor."),
    dict(key="spec-change PR", name="The spec-change pull request", at="the spec-change pull request",
         label="The spec-change pull request", sub="",
         does="The pull request that fixes what the auditors found in the Day's spec, before any track starts. A "
         "defect found while writing it is caught here."),
    dict(key="track-reviewer", name="The track-reviewer", at="the track-reviewer", label="The track-reviewer",
         sub="the brief, then the diff",
         does="An agent with a fresh context reads each track twice: the brief before the implementer starts, and "
         "the diff before the pull request. Counted from Day 13."),
    dict(key="seen red", name="A test seen failing", at="a test seen failing", label="A test seen failing",
         sub="seen-red.py",
         does="Runs the branch's new tests on main's code: they must fail, for the reason the spec gives."),
    dict(key="break on purpose", name="A break on purpose", at="a break on purpose", label="A break on purpose",
         sub="break.py",
         does="Breaks the code on purpose and runs the check twice with the break in. A test that still passes "
         "would not catch a real failure."),
    dict(key="review", name="The main session's diff review", at="the diff review", label="The diff review",
         sub="the main session",
         does="The main session reads the implementer's diff before it runs the checks and commits."),
    dict(key="CI", name="CI on the pull request", at="CI", label="CI", sub=f"required checks, from Day {PRF_FROM}",
         does="The required checks on the open pull request. A defect a failed check showed is caught here. Counted "
         f"from Day {PRF_FROM}: before it the Notes had no value for CI, and such a catch sits where the Notes put it."),
    dict(key="driver reviewer", name="The driver's reviewer", at="the driver's reviewer", label="The driver's reviewer",
         sub=f"on driver runs, from Day {PRF_FROM}", none="none yet: on driver runs only",
         does="A session with a fresh context reads the pull request once it is open, when the driver runs the step. "
         f"Counted from Day {PRF_FROM}. It reads only what the driver runs: where a person's session runs the Days, its "
         "tray stays empty."),
    dict(key="work", name="Noticed during the work", at="the work", label="Noticed in the work", sub="no gate: a leak",
         does="No gate: a defect someone noticed while working, in a track or the session. A catch by a gate the "
         "Notes do not name is counted here too."),
    dict(key="close", name="The close", at="the close", label="The close", sub="each criterion ticked",
         does="The closing pull request ticks every criterion with its evidence and writes the Day's Notes. A "
         "defect found doing it is caught here."),
    dict(key="rehearsal", name="The close's rehearsal", at="the rehearsal", label="The close's rehearsal",
         sub="in CI, counted from Day 12",
         does="Replays the closing branch as its merge into main would, before the merge. Until Day 12 the Notes "
         "named its catches evidence replay: they sit with the replay after the merge."),
    dict(key="evidence replay", name="The evidence replay", at="the evidence replay", label="The evidence replay",
         sub="on the closing merge",
         does="evidence.yml on the closing merge commit, checked before the next step. Before Day 12 it holds the "
         "rehearsal's catches too."),
    dict(key="dashboard", name="The dashboard", at="the dashboard", label="The dashboard",
         sub="seen on the published page", does="A defect seen on the published page, after the Day closed."),
    dict(key="Day review", name="A later Day's review", at="a later Day's review", label="A later Day's review",
         sub="a later Day reads it", does="A defect a later Day found in a closed Day's work."),
)


# Graph 7's phases, the bar above its pipe (dashboard.js's PHASES, unchanged): the four layers of checking, in order,
# and the gates each holds. "Noticed in the work" sits in the second: it leaves the stream there, with no gate.
PRF_LAYERS = (
    dict(name="Before any code", bio="reading the template", gates=("auditor", "spec-change PR"),
         what="The auditors read the spec against the code before anything is copied from it."),
    dict(name="While writing", bio="proofreading",
         gates=("track-reviewer", "seen red", "break on purpose", "review", "CI", "driver reviewer", "work"),
         what="Checks run as each track is written: the track-reviewer on the brief and the diff, the test seen "
         "failing, the break on purpose, the diff review; then, on the open pull request, CI and the driver's reviewer."),
    dict(name="At the close", bio="repair after the copy", gates=("close", "rehearsal"),
         what="The Day is finished and read again: every criterion is ticked with its evidence."),
    dict(name="After the merge", bio="surveillance", gates=("evidence replay", "dashboard", "Day review"),
         what="The Day is closed: the evidence replay, the published page and later Days find what is left."),
)


PRF_CAUSES = ("spec", "process", "implementation", "environment", "other")


PRF_GUARDS = ("step-guard", "read-guard", "auditor-guard")  # the hooks' order on graph 7 (HOOKS); others after


def _tag(value):
    """A Defect line's found: or cause: value as graph 7 read it (dashboard.js, tagOf): older Notes write
    "The auditor (spec-auditor)"."""
    v = "" if value is None else str(value)
    return re.sub(r" \(.*\)$", "", re.sub(r"^the ", "", v.strip().lower()))


def gate_of(value, day=None):
    """The gate a found: value names, by graph 7's rule (dashboard.js's gateOf up to #237): "Day N review" is a later
    Day's review; a gate's key, in any case; anything else (a track, a review nobody named, the session) was noticed
    during the work. On a Day before PRF_FROM, CI and the driver's reviewer were no value, and read as the work."""
    f = _tag(value)
    if re.fullmatch(r"day \d+ review", f):
        return "Day review"
    key = next(
        (g["key"] for g in PRF_GATES if g["key"].lower() == f and g["key"] not in ("work", "Day review")), "work"
    )
    return "work" if key in ("CI", "driver reviewer") and day is not None and day < PRF_FROM else key


def _when(stamp):
    """A timestamp as a moment, or None when it does not read as one. A stamp with no offset is taken as UTC."""
    try:
        t = datetime.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=datetime.timezone.utc)


def _prf_missing(d):
    """Why the stream cannot be drawn: the dashboard-data branch is missing, or has no gates.json. None when it can."""
    src = d.get("data")
    why = "so the gates' runs and cost are not known and the stream is not drawn."
    if not src:
        return None
    if not src.get("commit"):
        return f"the {src.get('branch')} branch is missing, {why}"
    if "gates.json" in (src.get("absent") or []):
        return f"the {src.get('branch')} branch has no gates.json, {why}"
    return None


def _prf_defects(d):
    """Every Defect line of every Day, in the Days' order and then the Notes', at the gate and in the layer graph 7
    puts it: its cause, the Day that made it (a number, "none", or None when the line does not say), whether it
    escaped (made on another Day) or came back (it names an earlier defect), and who noticed one caught in the work."""
    back = {r.get("id"): r.get("same_as") for r in (d.get("defect_recurrence") or {}).get("recurrences") or []}
    layer_of = {k: i for i, L in enumerate(PRF_LAYERS) for k in L["gates"]}
    out = []
    for day in sorted(d.get("days") or [], key=lambda x: x.get("day")):
        n = day.get("day")
        for i, x in enumerate(day.get("defects") or []):
            gate, cause, f, said = gate_of(x.get("found"), n), _tag(x.get("cause")), _tag(x.get("found")), x.get("made") or ""
            m = re.fullmatch(r"Day 0*(\d+)", said, re.I)
            made = int(m.group(1)) if m else "none" if re.fullmatch(r"none", said, re.I) else None
            xid = x.get("id")
            by = None if gate != "work" else "track" if re.match(r"track\b", f) else "self" if f == "self" else "other"
            out.append(
                dict(
                    id=xid or f"Day {n}, defect {i + 1}", day=n, i=i, cause=cause if cause in PRF_CAUSES else "other",
                    gate=gate, layer=layer_of[gate], made=made, escaped=isinstance(made, int) and made != n,
                    back=bool(xid) and xid in back, same_as=back.get(xid) if xid else None,
                    noticed=x.get("found") if gate == "work" and x.get("found") else None, by=by,
                )
            )
    return out


def _prf_late(d, defects):
    """The Days with a defect whose pull requests did not all merge by the count: a gate's dollars end at the count,
    so their catches do not share them (graph 7's rule, dayInCount)."""
    counted_at = (d.get("counted") or {}).get("at")
    cms = _when(counted_at) if counted_at else None
    if cms is None:
        return []
    times = [p for p in (d.get("clock") or {}).get("prs") or [] if p.get("opened") and p.get("merged")]
    after = {p.get("day") for p in times if (_when(p["merged"]) or cms) > cms}
    return sorted({o["day"] for o in defects} & after)


def _prf_hooks(d):
    """The hooks' refusals per guard, all dates, and the hooks gate's runs and cost: beside the stream, not in it."""
    refused = {}
    for r in d.get("refusals") or []:
        refused[r.get("guard")] = refused.get(r.get("guard"), 0) + (r.get("refused") or 0)
    order = [g for g in PRF_GUARDS if g in refused] + sorted(str(g) for g in refused if g not in PRF_GUARDS)
    h = next((g for g in (d.get("gate_report") or {}).get("gates") or [] if g.get("gate") == "hooks"), None)
    return dict(
        guards=[dict(guard=g, refused=refused[g]) for g in order if refused[g]],
        refused=sum(refused.values()),
        runs=h.get("runs") if h else None,
        cost=h.get("cost") if h else None,
    )


def _prf_ci(d):
    """CI on every pull request, as graph 7 counts it: per workflow, the pull requests it failed on
    (verification[].failed_in), of those merged; and how many failed at least one."""
    failed, checked = {}, d.get("verification") or []
    for v in checked:
        for w in set(v.get("failed_in") or []):
            failed[w] = failed.get(w, 0) + 1
    return dict(
        workflows=[dict(name=w, failed=n) for w, n in sorted(failed.items(), key=lambda x: (-x[1], x[0]))],
        merged=sum(1 for r in d.get("rows") or [] if r.get("pr")),
        failed_any=sum(1 for v in checked if v.get("failed_in")),
        rehearsal=failed.get("Evidence replay", 0),
        counted=bool(checked),
    )


def _prf_reader(days):
    """The second reader (relabel.py and the defect-rater): tags read differently, of the tags read, over the Days
    read; and the same for the tag that decides the tray, the gate (`stage`)."""
    read = [x["relabel"] for x in days if x.get("relabel")]
    if not read:
        return None
    pairs = [p for r in read for p in r.values()]
    stage = [r["stage"] for r in read if r.get("stage")]
    return dict(
        differ=sum(b - a for a, b in pairs),
        tags=sum(b for _, b in pairs),
        stage=[sum(b - a for a, b in stage), sum(b for _, b in stage)] if stage else None,
    )


def proofreading(d):
    """Graph 7 as one stream of defects through four layers of checking. Every count is graph 7's (its rules moved
    here from dashboard.js): each Defect line at the gate its found: names (gate_of), each gate in its phase, and a
    gate's dollars shared only over the catches of the Days whose pull requests all merged by the count. The folded
    graph 7 reads the same fields, so the two cannot disagree.

    With the dashboard-data branch or its gates.json missing, `empty` says why and the stream is not drawn; the
    defects, the gates and the layers are still counted, with no runs, cost or refusals, for graph 7 to draw."""
    missing = _prf_missing(d)
    defects = _prf_defects(d)
    total, late = len(defects), _prf_late(d, defects)
    found = (d.get("gate_report") or {}).get("gates") or []
    spent = {} if missing else {g["found"]: g for g in found if g.get("found")}
    gates = []
    for g in PRF_GATES:
        k = g["key"]
        mine, s = [o for o in defects if o["gate"] == k], spent.get(k)
        # a gate with no run in gates.json has no cost to count: its cost is not zero
        s = s if (s or {}).get("runs") else None
        counted, cost = sum(1 for o in mine if o["day"] not in late), (s or {}).get("cost")
        gates.append(
            dict(
                g, layer=next(i for i, L in enumerate(PRF_LAYERS) if k in L["gates"]), caught=len(mine),
                causes=[sum(1 for o in mine if o["cause"] == c) for c in PRF_CAUSES],
                runs=(s or {}).get("runs"), cost=cost, in_count=counted,
                per=cost / counted if cost and cost > 0 and counted else None,
                back=sum(1 for o in mine if o["back"]), escaped=sum(1 for o in mine if o["escaped"]),
                by={b: sum(1 for o in mine if o["by"] == b) for b in ("track", "self", "other")} if k == "work" else None,
            )
        )
    layers, reached = [], total
    for L in PRF_LAYERS:
        caught = sum(g["caught"] for g in gates if g["key"] in L["gates"])
        # a catch that was only noticed in the work has no gate: the layer's rate counts the gates' catches alone
        leak = sum(g["caught"] for g in gates if g["key"] in L["gates"] and g["key"] == "work")
        gated = caught - leak
        layers.append(
            dict(
                name=L["name"], bio=L["bio"], what=L["what"], gates=list(L["gates"]), reached=reached, caught=caught,
                went_on=reached - caught, pct=_round(100 * caught / reached) if reached else 0,
                share=_round(100 * caught / total) if total else 0, leak=leak, gated=gated,
                gated_pct=_round(100 * gated / reached) if reached else 0,
            )
        )
        reached -= caught

    def mark(pick):
        mine = [o for o in defects if pick(o)]
        return dict(n=len(mine), layers=[sum(1 for o in mine if o["layer"] == i) for i in range(len(PRF_LAYERS))])

    last = len(PRF_LAYERS) - 1
    marks = dict(
        escaped=mark(lambda o: o["escaped"]),
        back=mark(lambda o: o["back"]),
        both=sum(1 for o in defects if o["escaped"] and o["back"]),
        after_merge=layers[last]["caught"],
        shared=sum(1 for o in defects if o["back"] and o["layer"] == last),
    )
    out = dict(
        _stamp(d), counted_at=(d.get("counted") or {}).get("at"), total=total, causes=list(PRF_CAUSES),
        cause_counts={c: sum(1 for o in defects if o["cause"] == c) for c in PRF_CAUSES},
        days=sorted({o["day"] for o in defects}), gates=gates, layers=layers, leak="work", defects=defects, late=late,
        marks=marks, hooks=None if missing else _prf_hooks(d),
        ci=dict(_prf_ci(d), from_day=PRF_FROM, caught=next(g["caught"] for g in gates if g["key"] == "CI")),
        reader=_prf_reader(d.get("days") or []), never=d.get("never_found"),
    )
    if missing or not total:
        out["empty"] = missing or "no defect is recorded in any Day's Notes yet, so there is no stream to draw."
    return out
