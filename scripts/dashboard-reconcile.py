"""Hold each new section of the dashboard to the graph it is drawn beside: one line per section, the new total against
the original's, both read from the page's own model of the data; where the original has left the page, against the
same figure counted here from the data.

    python scripts/dashboard-reconcile.py [spec-drift.json]     # the data spec-drift.py --out wrote
    python scripts/dashboard-reconcile.py --demo                # scripts/demo-data.py's made-up data

Graphs 1, 2, 6, 7 and 10 stay on the page, folded under their new drawings, so the two can be reconciled on every
build. The ring, the proteins, the energy budget and the growth rings have no original on the page: each is checked
against a recount of the data (days_finished, last_recheck, dollars, lines_placed). The reflex arcs have none either,
and are held to the proteins' count of the same steps. Prints one line per section and exits 1 when any disagrees.
Needs node, as the page's model runs in it.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "docs", "dashboard", "dashboard.js")

# model() on the data from stdin, printed as JSON.
MODEL = r"""
const fs = require("fs"), vm = require("vm");
const ctx = vm.createContext({ DATA: JSON.parse(fs.readFileSync(0, "utf8")) });
console.log(JSON.stringify(vm.runInContext(fs.readFileSync(process.argv[1], "utf8") + "\nmodel(DATA)", ctx)));
"""


def model(data):
    """The page's model of `data`, from dashboard.js run in node."""
    out = subprocess.run(["node", "-e", MODEL, SCRIPT], input=json.dumps(data), capture_output=True,
                         encoding="utf-8", check=True)
    return json.loads(out.stdout)


# The recounts: four figures counted here from the data as spec-drift.py wrote it, by none of the view functions in
# spec_drift_views.py, so a section drawn from those is held to something that is not itself.
FINISHED = ("done", "closed", "cut")
# The count a replay state goes in; None is counted nowhere. tests/test_dashboard_gap.py holds these keys to the states
# scripts/replay-history.py writes, and tests/test_dashboard_views.py the groups to spec_drift_views.REPLAY_GROUP.
REPLAY_GROUP = {"code broken": "broken", "test weakened": "repair", "break no longer applies": "repair",
                "not runnable": "skipped", "not applicable on this platform": "skipped", "live only": "skipped",
                "holds, never broken": "unproven", "holds": "proven", "not yet in force": None}
WORK = ("spec", "context", "prod", "test", "tooling")


def days_finished(data):
    """(finished, numbered): the Days plan.md numbers in a phase that is not cut, and those of them the data has as
    done, closed or cut. None when the plan lists no phase."""
    rows = ((data.get("meta") or {}).get("where") or {}).get("rows") or []
    if not rows:
        return None
    by = {d["day"]: d for d in sorted(data.get("days") or [], key=lambda d: d["day"])}
    numbered = [n for r in rows if not r.get("cut") for n in r.get("days") or []]
    return sum(1 for n in numbered if n in by and by[n].get("status") in FINISHED), len(numbered)


def last_recheck(data):
    """The newest merge the replay ran on, as {"pr", "proven", "total"}: each criterion not replaced counts in the group
    of its newest re-check at or before that merge, and one whose state has no group is not counted. None with no merge."""
    replay = data.get("replay") or {}
    merges = sorted(replay.get("merges") or [], key=lambda m: m["n"])
    if not merges:
        return None
    replaced = {c["id"] for c in data.get("criteria_index") or [] if c.get("replaced_by")}
    group = {}
    for cell in sorted(replay.get("cells") or [], key=lambda c: c["n"]):
        if cell["n"] <= merges[-1]["n"] and cell["criterion"] not in replaced:
            group[cell["criterion"]] = REPLAY_GROUP.get(cell["state"])
    counted = [g for g in group.values() if g]
    return {"pr": merges[-1]["pr"], "proven": counted.count("proven"), "total": len(counted)}


def dollars(data):
    """Every row of the token counts, summed and rounded to the cent."""
    return round(sum(t.get("cost") or 0 for t in data.get("tokens") or []), 2)


def lines_placed(data):
    """The lines each merge changed, placed by one rule: a pull request whose branch names a Day is that Day's; any
    other pull request is outside any Day, beside the furthest Day begun when it merged; a row with no pull request, or
    merged before any Day began, comes before Day 1. Returns {"days": {day: (lines, spec and agent context)},
    "beside": {day: lines}, "before": lines}, the Days being the data's own."""
    order, top = data.get("order") or [], 0
    rank = lambda d: order.index(d) if d in order else d  # noqa: E731
    days = {d["day"]: [0, 0] for d in sorted(data.get("days") or [], key=lambda d: d["day"])}
    beside, before = {}, 0
    for r in data.get("rows") or []:
        work = r.get("work") or {}
        lines = sum(work.get(k) or 0 for k in WORK)
        own = r.get("own_day") if r.get("pr") and r.get("own_day") is not None else None
        if own is not None and (not top or rank(own) > rank(top)):
            top = own
        if own is not None and own in days:
            days[own][0] += lines
            days[own][1] += (work.get("spec") or 0) + (work.get("context") or 0)
        if own is None and r.get("pr") and top in days:
            beside[top] = beside.get(top, 0) + lines
        if own is None and top == 0:
            before += lines
    return {"days": {d: tuple(v) for d, v in days.items()}, "beside": beside, "before": before}


def gene_line(m):
    """The gene against graph 12: the same commitments, and the same ones due and named by no criterion in force; and
    its beads of merges no criterion cites against the merge graph's rows of them."""
    gene, plan = m.get("gene") or {}, m.get("g12") or {}
    if gene.get("error") or plan.get("error"):
        return False, f"gene: not drawn ({gene.get('error') or plan.get('error')})"
    if gene.get("empty") or plan.get("empty"):
        return True, "gene: no plan, and graph 12 has none either: agree"
    cols = [c for c in plan["all"] if c["arm"] in ("p", "n")]
    due = sorted(c["key"] for c in cols if c["is"]["due"])
    uncovered, figs = sorted(gene["uncovered"]), sum(f["n"] for f in gene["figs"])
    # the beads under its ring against the merge graph's "No criterion cites it" rows
    beads, rows = len(gene.get("uncited") or []), len(((m.get("mrg") or {}).get("all") or {}).get("loose") or [])
    agree = gene["total"] == len(cols) == figs and uncovered == due and beads == rows
    return agree, (f"gene: {gene['total']} commitments ({figs} in its classes), {len(uncovered)} uncovered | "
                   f"graph 12: {len(cols)} commitments, {len(due)} should be covered by now; "
                   f"{beads} uncited merges | merge graph: {rows}: "
                   + ("agree" if agree else "DISAGREE" if beads != rows
                      else f"DISAGREE (gene {', '.join(uncovered) or 'none'}; graph 12 {', '.join(due) or 'none'})"))


# The merge graph's verdict tiles and the promise tiles' states they count: the same criteria in each.
MERGE_TILES = (("st ok", "hold proved", ("proven",)), ("st un", "hold unproved", ("unproven",)),
               ("st bad", "not holding", ("broken", "repair")), ("st none", "not run", ("skipped", "unchecked")),
               ("st due", "not built", ("open", "building")), ("tri", "replaced", ("replaced",)))


def merge_line(m):
    """The merge graph against the page's promise counts (the model's promises key, each criterion in its state): each
    verdict tile counts the criteria in the states it stands for, and all of them every criterion."""
    g, p = m.get("mrg") or {}, m.get("promises") or {}
    if g.get("error") or p.get("error"):
        return False, f"merge graph: not drawn ({g.get('error') or p.get('error')})"
    states = p.get("states") or {}
    if g.get("empty"):
        agree = not sum(states.values())
        return agree, "merge graph: no criteria | promise tiles: " + ("none either: agree" if agree else "DISAGREE")
    tiles = {t["sw"]: t["n"] for t in g["all"]["verdict"]}
    ours = [(word, tiles.get(sw, 0)) for sw, word, _ in MERGE_TILES]
    theirs = [("+".join(group), sum(states.get(s, 0) for s in group)) for _, _, group in MERGE_TILES]
    agree = [n for _, n in ours] == [n for _, n in theirs] and sum(n for _, n in ours) == sum(states.values())
    say = lambda pairs: ", ".join(f"{n} {w}" for w, n in pairs)  # noqa: E731
    return agree, (f"merge graph: {sum(n for _, n in ours)} criteria ({say(ours)}) | "
                   f"promise tiles: {sum(states.values())} ({say(theirs)}): " + ("agree" if agree else "DISAGREE"))


def ring_line(m, data):
    """The ring against the Days counted from the data (days_finished): the same Days closed of the same Days numbered;
    and its promises built against graph 1's (the look-ahead's last column)."""
    w, g1, days = m.get("whr") or {}, m.get("g1") or {}, days_finished(data)
    if w.get("error") or w.get("empty"):
        agree = days is None
        return agree, (f"where we are: no ring ({w.get('error') or w.get('empty')}) | counted from the data: "
                       + ("no numbered Day either: agree" if agree else "DISAGREE"))
    a, b = days or ("", "")
    c, e = (re.match(r"(\d+) of (\d+) promises built", (g1.get("read") or {}).get("t") or "") or re.match("()()", "")).groups()
    ours, theirs = [w["closed"], w["numbered"], w["built"], w["written"]], [a, b, c, e]
    agree = [str(n) for n in ours] == [str(n) for n in theirs]
    return agree, (f"where we are: ring {w['closed']} of {w['numbered']} Days closed, {w['built']} of {w['written']} promises built | "
                   f"counted from the data: {'?' if a == '' else a} of {'?' if b == '' else b} Days, look-ahead {c or '?'} of {e or '?'}: "
                   + ("agree" if agree else "DISAGREE"))


def reading_line(m):
    """Graph 1's reading against the look-ahead it is read from: an arc for every hand-off of its ledger, and as many
    open, and open with a number, as its last column counts."""
    r = m.get("rdg") or {}
    if r.get("error") or r.get("empty"):
        return False, f"reading: not drawn ({r.get('error') or r.get('empty')})"
    led = r["ledger"]
    ours, theirs = [len(r["h"]), r["open"], r["numbered"]], [led["n"], led["open"], led["numbered"]]
    agree = ours == theirs
    return agree, (f"reading: {ours[0]} arcs, {ours[1]} open, {ours[2]} numbered | "
                   f"look-ahead {theirs[0]} hand-offs, {theirs[1]} open, {theirs[2]} numbered: " + ("agree" if agree else "DISAGREE"))


def gel_line(m):
    """The gel against graph 2 (folded under it): each yardstick's last figure, its Day and its average so far, on the
    Days the gel has lanes for (the Days the yardsticks are counted at; graph 2 has a column for a Day in progress too)."""
    g, two = m.get("gel") or {}, m.get("g2") or {}
    if g.get("error") or two.get("error"):
        return False, f"gel: not drawn ({g.get('error') or two.get('error')})"
    if g.get("empty"):
        agree = not two.get("rows")
        return agree, "gel: no yardsticks | graph 2: " + ("none either: agree" if agree else "DISAGREE")
    ours = {p["key"]: (p["last"] and (p["last"]["day"], p["last"]["value"]), p["average"]) for p in g["panels"]}
    theirs = {}
    for r in two.get("rows") or []:
        got = [c for c in r.get("cells") or [] if c.get("value") is not None and c.get("day") in g["days"]]
        avg = [a["value"] for a in r.get("avg") or [] if a.get("value") is not None]
        theirs[r["key"]] = ((got[-1]["day"], got[-1]["value"]) if got else None, avg[-1] if avg else None)
    differ = sorted(k for k in set(ours) | set(theirs) if ours.get(k) != theirs.get(k))
    return not differ, (f"gel: {len(ours)} yardsticks, each one's last figure and average on Days {g['days'][0]} to {g['days'][-1]} | "
                        f"graph 2: {len(theirs)} rows: "
                        + ("agree" if not differ else f"DISAGREE ({', '.join(differ)})"))


def prt_line(m, data):
    """The proteins' headline (proven, of the criteria re-checked) against the same count made from the data at the
    newest merge the replay ran on (last_recheck), and against the merge graph's verdict tiles. A re-check older than
    the last merge is said, and never agrees."""
    p, g, last = m.get("prt") or {}, m.get("mrg") or {}, last_recheck(data)
    for x, name in ((p, "proteins"), (g, "merge graph")):
        if x.get("error"):
            return False, f"proteins: not drawn ({name}: {x['error']})"
    if p.get("empty"):
        agree = last is None
        return agree, "proteins: no criteria | counted from the data: " + ("no re-check either: agree" if agree else "DISAGREE")
    tiles = {t["sw"]: t["n"] for t in (g.get("all") or {}).get("verdict") or []}
    seen = sum(tiles.get(k, 0) for k in ("st ok", "st un", "st bad", "st none"))
    ours = [p["proven"], p["rechecked"], p["rechecked"] + p["counts"].get("unchecked", 0)]
    theirs = [last["proven"], last["total"]] if last else [None, None]
    agree = ours[:2] == theirs and [ours[0], ours[2]] == [tiles.get("st ok"), seen]
    why = ""
    if last and not agree and p.get("last_pr") is not None and last["pr"] < p["last_pr"]:
        why = f"; the last re-check is at #{last['pr']}, older than the last merge #{p['last_pr']}, and the replay has not run since"
    return agree, (f"proteins: {ours[0]} of {ours[1]} proven | counted from the data at the re-check of #{last['pr'] if last else '?'}: "
                   f"{theirs[0]} of {theirs[1]}, merge graph {tiles.get('st ok', 0)} proven of {seen} in force and built: "
                   + ("agree" if agree else f"DISAGREE{why}"))


def prf_line(m):
    """The proofreading stream against graph 7 (folded under it): the defects in all, the catches of each layer (graph
    7's phases, counted from its own dots), and each gate's catches and cost per catch."""
    p, g7 = m.get("prf") or {}, m.get("g7") or {}
    if p.get("error") or g7.get("error"):
        return False, f"proofreading: not drawn ({p.get('error') or g7.get('error')})"
    if p.get("empty") and not p.get("gates"):
        agree = not any(r.get("dots") for r in g7.get("rows") or [])
        return agree, "proofreading: no stream | graph 7: " + ("no defect either: agree" if agree else "DISAGREE")
    ours = (p["total"], [x["caught"] for x in p["layers"]], [(g["key"], g["caught"], g["per"]) for g in p["gates"]])
    dots = sum(len(r.get("dots") or []) for r in g7.get("rows") or [])
    theirs = (dots, [x["n"] for x in (g7.get("pipe") or {}).get("phases") or []],
              [(g.get("key"), g.get("n"), g.get("per")) for g in g7.get("gates") or []])
    differ = [w for w, a, b in zip(("total", "layers", "gates"), ours, theirs) if a != b]
    priced = sum(1 for _, _, per in ours[2] if per is not None)
    return not differ, (f"proofreading: {ours[0]} defects, layers {'/'.join(map(str, ours[1]))}, {priced} gates priced | "
                        f"graph 7: {theirs[0]} dots, phases {'/'.join(map(str, theirs[1]))}: "
                        + ("agree" if not differ else f"DISAGREE ({', '.join(differ)})"))


def atp_line(m, data):
    """The energy budget against the dollars counted from the data (dollars): what it split by kind plus what it could
    not split is every row of the token counts, to the cent; and the whole beads are the dollars over the unit,
    rounded, in both views."""
    a, theirs = m.get("atp") or {}, dollars(data)
    if a.get("error"):
        return False, f"budget: not drawn ({a['error']})"
    if a.get("empty"):
        return theirs == 0, f"budget: not drawn | counted from the data: ${theirs:.2f}: " + ("agree" if theirs == 0 else "DISAGREE")
    split, rest = round(sum(a["kinds"][:3]), 2), round(a["kinds"][3], 2)
    ours, unit, beads = round(sum(a["kinds"]), 2), a["unit"], a["beads"]
    views = [sum(c["b"] for c in a["cols"]["date"]), sum(c["b"] for c in a["cols"]["day"] + a["cols"]["between"])]
    placed = round(sum(a["parts"]), 2)
    agree = (ours == theirs == round(a["total"], 2) == placed and views == [beads, beads]
             and beads == int(a["total"] / unit + 0.5))
    return agree, (f"budget: split ${split:.2f} + not split ${rest:.2f} = ${ours:.2f} | counted from the data: ${theirs:.2f}: "
                   + ("agree" if agree else f"DISAGREE (beads by date {views[0]}, by Day {views[1]}; placed ${placed:.2f})")
                   + f"; {beads} beads x ${unit} = ${beads * unit:.2f} against ${a['total']:.2f} exact")


def rng_line(m, data):
    """The rings against the lines counted from the data (lines_placed): the Days' lines, the lines outside any Day and
    the lines before Day 1, Day by Day; and specs plus agent context, Day by Day. Rows in neither (a Day not in the
    data, no pull request after Day 1 began) are in no ring and in no count here; they are printed, and the rings' total
    with them must be every row's lines, so none vanishes."""
    r, placed = m.get("rng") or {}, lines_placed(data)
    if r.get("error"):
        return False, f"rings: not drawn ({r['error']})"
    days_c, out_c = sum(v[0] for v in placed["days"].values()), sum(placed["beside"].values())
    before_c = placed["before"]
    if r.get("empty"):
        agree = days_c + out_c + before_c == 0
        return agree, "rings: no ring | counted from the data: " + ("no line either: agree" if agree else "DISAGREE")
    days, out, before = r["inside"]["lines"], r["out"]["lines"], r["before"]["lines"]
    per_day = {x["day"]: (x["lines"], x["w"]["spec"] + x["w"]["context"]) for x in r["days"]}
    per_day_c = {d: v for d, v in placed["days"].items() if v[0]}
    per_at = {x["at"]: x["lines"] for x in r["outside"]}
    per_at_c = {d: n for d, n in placed["beside"].items() if n}
    spec, ctx, spec_c = r["inside"]["w"]["spec"], r["inside"]["w"]["context"], sum(v[1] for v in placed["days"].values())
    loose = r["unplaced"]["lines"]
    differ = [w for w, a, b in (("Days", (days, per_day), (days_c, per_day_c)), ("outside", (out, per_at), (out_c, per_at_c)),
                                ("before Day 1", before, before_c), ("spec", spec + ctx, spec_c),
                                ("every row", r["total"] + loose, r["all_lines"])) if a != b]
    return not differ, (f"rings: Days {days:,} + outside {out:,} + before Day 1 {before:,} = {r['total']:,} | counted from the data: "
                        f"Days {days_c:,} + outside {out_c:,} + before Day 1 {before_c:,} = {days_c + out_c + before_c:,}; "
                        f"specs {spec:,} + context {ctx:,} = {spec_c:,} counted; {loose:,} lines in neither: "
                        + ("agree" if not differ else f"DISAGREE ({', '.join(differ)})"))


# Graph 10's bars by class: a pull request open, by its kind, and a stretch of its checks, passed or with a failed run.
ACT_PR_BARS = ("spec", "code", "close", "other")
ACT_CHECK_BARS = ("ok", "failed")


def act_line(m):
    """The actogram against graph 10 (folded under it): each date's busy time, two sessions at once counted once, is at
    least its busiest lane's and at most its lanes' sum; its merge ticks are graph 10's merge marks, and its wait marks
    are graph 10's marks of a session waiting on a command, summed over the dates. On each of the actogram's dates,
    its pull requests open are as many as graph 10's pull request bars on that date (spec, code, close or other), and
    its checks as many as graph 10's check bars (ok or failed); the line gives both totals over the actogram's dates
    and, when they differ, the dates."""
    a, g10 = m.get("act") or {}, m.get("g10") or {}
    if a.get("error") or g10.get("error"):
        return False, f"actogram: not drawn ({a.get('error') or g10.get('error')})"
    by_date = {x["date"]: [b["cls"] for lane in x["lanes"] for b in lane["bars"]] for x in g10.get("dates") or []}
    bars = [b for x in g10.get("dates") or [] for lane in x["lanes"] for b in lane["bars"]]
    merges_10 = sum(1 for b in bars if b["cls"] == "merge")
    waits_10 = sum(1 for b in bars if b["cls"].startswith("run "))
    if a.get("empty"):
        agree = merges_10 + waits_10 == 0
        return agree, (f"actogram: not drawn ({a['empty']}) | graph 10: {merges_10} merge marks, {waits_10} wait marks: "
                       + ("agree" if agree else "DISAGREE"))
    figs = {x["date"]: x.get("fig") or {} for x in g10.get("dates") or []}
    low = high = busy = prs = prs_10 = checks = checks_10 = 0
    bad, bad_prs, bad_checks = [], [], []
    for x in a["dates"]:
        lanes = list((figs.get(x["date"]) or {}).get("lanes", {}).values())
        lo, hi = max(lanes, default=0), sum(lanes)
        low, high, busy = low + lo, high + hi, busy + x["busy"]
        if not lo - 0.05 <= x["busy"] <= hi + 0.05 * len(lanes):
            bad.append(x["date"])
        drawn = by_date.get(x["date"]) or []
        p, p10 = len(x.get("prs") or []), sum(1 for cls in drawn if cls in ACT_PR_BARS)
        c, c10 = len(x.get("checks") or []), sum(1 for cls in drawn if cls in ACT_CHECK_BARS)
        prs, prs_10, checks, checks_10 = prs + p, prs_10 + p10, checks + c, checks_10 + c10
        if p != p10:
            bad_prs.append(x["date"])
        if c != c10:
            bad_checks.append(x["date"])
    merges, waits = sum(len(x["merges"]) for x in a["dates"]), sum(len(x["wait_segs"]) for x in a["dates"])
    agree = not bad and not bad_prs and not bad_checks and merges == merges_10 and waits == waits_10
    differ = "; ".join(f"{what} on {', '.join(dates)}" for what, dates in (
        ("busy outside its lanes", bad), ("pull requests differ", bad_prs), ("checks differ", bad_checks)) if dates)
    return agree, (f"actogram: {len(a['dates'])} dates, busy {busy / 60:.1f} h (lanes {low / 60:.1f} to {high / 60:.1f} h), "
                   f"{merges} merges, {waits} waits, {prs} pull requests open, {checks} checks | graph 10: {merges_10} merge marks, "
                   f"{waits_10} wait marks, {prs_10} pull request bars, {checks_10} check bars: "
                   + ("agree" if agree else f"DISAGREE{' (' + differ + ')' if differ else ''}"))


def rfx_line(m):
    """The reflex arcs against the proteins' "In real runs" (graphs 3 to 5, from the same _runs()): the same steps,
    parks, crashed steps and open steps. With no arc drawn, the proteins count no step either."""
    r, p = m.get("rfx") or {}, m.get("prt") or {}
    for x, name in ((r, "reflex"), (p, "proteins")):
        if x.get("error"):
            return False, f"reflex: not drawn ({name}: {x['error']})"
    run = next((ch["run"] for ch in p.get("chains") or [] if ch.get("run")), None)
    prt = [run["of"], len(run["parks"]), len(run["crashes"]), len(run["open"])] if run else None
    if r.get("empty"):
        agree = not (prt and prt[0])
        return agree, (f"reflex: not drawn ({r['empty']}) | proteins' real runs: {f'{prt[0]} steps' if prt else 'none'}: "
                       + ("agree" if agree else "DISAGREE"))
    c = r["counts"]
    ours, n = [c["steps"], c["parks"], c["crashed"], c["open"]], c["crashed_sessions"]
    agree = prt is None or prt == ours
    return agree, (f"reflex: {ours[0]} steps, {ours[1]} parks, {ours[2]} crashed ({n} {'session' if n == 1 else 'sessions'}), {ours[3]} open | "
                   f"proteins' real runs: {', '.join(map(str, prt)) if prt else 'none'}: " + ("agree" if agree else "DISAGREE"))


SECTIONS = [gene_line, merge_line, ring_line, reading_line, gel_line, prt_line, prf_line, atp_line, rng_line, act_line, rfx_line]
# The sections whose original has left the page: each takes the data too, and recounts its figure from it.
RECOUNTED = (ring_line, prt_line, atp_line, rng_line)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("data", nargs="?", default="spec-drift.json", help="spec-drift.json (default: %(default)s)")
    ap.add_argument("--demo", action="store_true", help="reconcile scripts/demo-data.py's made-up data instead")
    args = ap.parse_args(argv)
    if args.demo:
        spec = importlib.util.spec_from_file_location("demo_data", os.path.join(HERE, "demo-data.py"))
        demo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo)
        data = demo.demo()
    else:
        with open(args.data, encoding="utf-8") as f:
            data = json.load(f)
    m = model(data)
    ok = True
    for section in SECTIONS:
        agree, line = section(m, data) if section in RECOUNTED else section(m)
        ok = ok and agree
        print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
