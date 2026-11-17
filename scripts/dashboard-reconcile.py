"""Hold each new section of the dashboard to the graph it is drawn beside: one line per section, the new total against
the original's, both read from the page's own model of the data.

    python scripts/dashboard-reconcile.py [spec-drift.json]     # the data spec-drift.py --out wrote
    python scripts/dashboard-reconcile.py --demo                # scripts/demo-data.py's made-up data

The old graphs stay on the page, folded under the new ones, so the two can be reconciled on every build. Prints one
line per section and exits 1 when any disagrees. Needs node, as the page's model runs in it.
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


def gene_line(m):
    """The gene against graph 12: the same commitments, and the same ones due and named by no criterion in force."""
    gene, plan = m.get("gene") or {}, m.get("g12") or {}
    if gene.get("error") or plan.get("error"):
        return False, f"gene: not drawn ({gene.get('error') or plan.get('error')})"
    if gene.get("empty") or plan.get("empty"):
        return True, "gene: no plan, and graph 12 has none either: agree"
    cols = [c for c in plan["all"] if c["arm"] in ("p", "n")]
    due = sorted(c["key"] for c in cols if c["is"]["due"])
    uncovered, figs = sorted(gene["uncovered"]), sum(f["n"] for f in gene["figs"])
    agree = gene["total"] == len(cols) == figs and uncovered == due
    return agree, (f"gene: {gene['total']} commitments ({figs} in its classes), {len(uncovered)} uncovered | "
                   f"graph 12: {len(cols)} commitments, {len(due)} should be covered by now: "
                   + ("agree" if agree else f"DISAGREE (gene {', '.join(uncovered) or 'none'}; graph 12 {', '.join(due) or 'none'})"))


# The merge graph's verdict tiles and the promise tiles' states they count: the same criteria in each.
MERGE_TILES = (("st ok", "hold proved", ("proven",)), ("st un", "hold unproved", ("unproven",)),
               ("st bad", "not holding", ("broken", "repair")), ("st none", "not run", ("skipped", "unchecked")),
               ("st due", "not built", ("open", "building")), ("tri", "replaced", ("replaced",)))


def merge_line(m):
    """The merge graph against the promise tiles (graphs 3 to 5): each verdict tile counts the criteria in the tile
    states it stands for, and all of them every criterion."""
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


def ring_line(m):
    """The ring against the old tiles ("Where we are", folded under it): the same Days closed of the same Days
    numbered; and its promises built against graph 1's (the look-ahead's last column)."""
    w, tiles, g1 = m.get("whr") or {}, m.get("where") or {}, m.get("g1") or {}
    if w.get("error") or w.get("empty"):
        agree = not tiles or bool(tiles.get("error"))
        return agree, f"where we are: no ring ({w.get('error') or w.get('empty')}) | tiles: " + ("none either: agree" if agree else "DISAGREE")
    a, b = (re.match(r"(\d+) of (\d+) numbered Days finished", tiles.get("count") or "") or re.match("()()", "")).groups()
    c, e = (re.match(r"(\d+) of (\d+) promises built", (g1.get("read") or {}).get("t") or "") or re.match("()()", "")).groups()
    ours, theirs = [w["closed"], w["numbered"], w["built"], w["written"]], [a, b, c, e]
    agree = [str(n) for n in ours] == theirs
    return agree, (f"where we are: ring {w['closed']} of {w['numbered']} Days closed, {w['built']} of {w['written']} promises built | "
                   f"tiles {a or '?'} of {b or '?'}, look-ahead {c or '?'} of {e or '?'}: " + ("agree" if agree else "DISAGREE"))


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


def prt_line(m):
    """The proteins' headline (proven, of the criteria re-checked) against the trust strip's last column (graph 3's,
    folded) and the merge graph's verdict tiles. The strip counts at a merge the replay ran on: an older one than the
    last merge is said, and never agrees."""
    p, b, g = m.get("prt") or {}, m.get("g4") or {}, m.get("mrg") or {}
    for x, name in ((p, "proteins"), (b, "trust strip"), (g, "merge graph")):
        if x.get("error"):
            return False, f"proteins: not drawn ({name}: {x['error']})"
    if p.get("empty"):
        agree = not (b.get("hist") or [])
        return agree, "proteins: no criteria | trust strip: " + ("none either: agree" if agree else "DISAGREE")
    last = (b.get("hist") or [None])[-1]
    tiles = {t["sw"]: t["n"] for t in (g.get("all") or {}).get("verdict") or []}
    seen = sum(tiles.get(k, 0) for k in ("st ok", "st un", "st bad", "st none"))
    ours = [p["proven"], p["rechecked"], p["rechecked"] + p["counts"].get("unchecked", 0)]
    strip = [last["counts"]["proven"], last["total"]] if last else [None, None]
    agree = ours[:2] == strip and [ours[0], ours[2]] == [tiles.get("st ok"), seen]
    why = ""
    if last and not agree and p.get("last_pr") is not None and last["pr"] < p["last_pr"]:
        why = f"; the strip's last column is #{last['pr']}, older than the last merge #{p['last_pr']}, and the replay has not run since"
    return agree, (f"proteins: {ours[0]} of {ours[1]} proven | trust strip at #{last['pr'] if last else '?'}: "
                   f"{strip[0]} of {strip[1]}, merge graph {tiles.get('st ok', 0)} proven of {seen} in force and built: "
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


def atp_line(m):
    """The energy budget against graph 8 (folded under it): what it split by kind plus what it could not split is graph
    8's dollars, to the cent; and the whole beads are the dollars over the unit, rounded, in both views."""
    a, g8 = m.get("atp") or {}, m.get("g8") or {}
    if a.get("error") or g8.get("error"):
        return False, f"budget: not drawn ({a.get('error') or g8.get('error')})"
    theirs = round(sum(b.get("total") or 0 for b in g8.get("bars") or []), 2)
    if a.get("empty"):
        return theirs == 0, f"budget: not drawn | graph 8: ${theirs:.2f}: " + ("agree" if theirs == 0 else "DISAGREE")
    split, rest = round(sum(a["kinds"][:3]), 2), round(a["kinds"][3], 2)
    ours, unit, beads = round(sum(a["kinds"]), 2), a["unit"], a["beads"]
    views = [sum(c["b"] for c in a["cols"][v]) for v in ("date", "day")]
    agree = ours == theirs == round(a["total"], 2) and views == [beads, beads] and beads == int(a["total"] / unit + 0.5)
    return agree, (f"budget: split ${split:.2f} + not split ${rest:.2f} = ${ours:.2f} | graph 8: ${theirs:.2f}: "
                   + ("agree" if agree else f"DISAGREE (beads by date {views[0]}, by Day {views[1]})")
                   + f"; {beads} beads x ${unit} = ${beads * unit:.2f} against ${a['total']:.2f} exact")


def rng_line(m):
    """The rings against graph 9 (folded under them): the Days' lines, the lines outside any Day and the lines before
    Day 1 are graph 9's bars, its paler bars beside them and its "before Day 1"; specs plus agent context are graph 9's
    spec, Day by Day. Rows in neither (a Day not in the data, no pull request after Day 1 began) are in no ring and no
    bar of graph 9; they are printed, and the rings' total with them must be every row's lines, so none vanishes."""
    r, g9 = m.get("rng") or {}, m.get("g9") or {}
    if r.get("error") or g9.get("error"):
        return False, f"rings: not drawn ({r.get('error') or g9.get('error')})"
    bars = g9.get("bars") or []
    days_9, out_9 = sum(b["total"] for b in bars), sum((b.get("aside") or {}).get("total", 0) for b in bars)
    before_9 = g9.get("before") or 0
    if r.get("empty"):
        agree = days_9 + out_9 + before_9 == 0
        return agree, "rings: no ring | graph 9: " + ("no line either: agree" if agree else "DISAGREE")
    days, out, before = r["inside"]["lines"], r["out"]["lines"], r["before"]["lines"]
    per_day = {x["day"]: (x["lines"], x["w"]["spec"] + x["w"]["context"]) for x in r["days"]}
    per_day_9 = {b["day"]: (b["total"], b["w"]["spec"]) for b in bars if b["total"]}
    per_at = {x["at"]: x["lines"] for x in r["outside"]}
    per_at_9 = {b["day"]: b["aside"]["total"] for b in bars if b.get("aside") and b["aside"]["total"]}
    spec, ctx, spec_9 = r["inside"]["w"]["spec"], r["inside"]["w"]["context"], sum(b["w"]["spec"] for b in bars)
    loose = r["unplaced"]["lines"]
    differ = [w for w, a, b in (("Days", (days, per_day), (days_9, per_day_9)), ("outside", (out, per_at), (out_9, per_at_9)),
                                ("before Day 1", before, before_9), ("spec", spec + ctx, spec_9),
                                ("every row", r["total"] + loose, r["all_lines"])) if a != b]
    return not differ, (f"rings: Days {days:,} + outside {out:,} + before Day 1 {before:,} = {r['total']:,} | graph 9: "
                        f"Days {days_9:,} + beside {out_9:,} + before Day 1 {before_9:,} = {days_9 + out_9 + before_9:,}; "
                        f"specs {spec:,} + context {ctx:,} = graph 9's spec {spec_9:,}; {loose:,} lines in neither: "
                        + ("agree" if not differ else f"DISAGREE ({', '.join(differ)})"))


def act_line(m):
    """The actogram against graph 10 (folded under it): each date's busy time, two sessions at once counted once, is at
    least its busiest lane's and at most its lanes' sum; its merge ticks are graph 10's merge marks, and its wait marks
    are graph 10's marks of a session waiting on a command, summed over the dates."""
    a, g10 = m.get("act") or {}, m.get("g10") or {}
    if a.get("error") or g10.get("error"):
        return False, f"actogram: not drawn ({a.get('error') or g10.get('error')})"
    bars = [b for x in g10.get("dates") or [] for lane in x["lanes"] for b in lane["bars"]]
    merges_10 = sum(1 for b in bars if b["cls"] == "merge")
    waits_10 = sum(1 for b in bars if b["cls"].startswith("run "))
    if a.get("empty"):
        agree = merges_10 + waits_10 == 0
        return agree, (f"actogram: not drawn ({a['empty']}) | graph 10: {merges_10} merge marks, {waits_10} wait marks: "
                       + ("agree" if agree else "DISAGREE"))
    figs = {x["date"]: x.get("fig") or {} for x in g10.get("dates") or []}
    low = high = busy = 0
    bad = []
    for x in a["dates"]:
        lanes = list((figs.get(x["date"]) or {}).get("lanes", {}).values())
        lo, hi = max(lanes, default=0), sum(lanes)
        low, high, busy = low + lo, high + hi, busy + x["busy"]
        if not lo - 0.05 <= x["busy"] <= hi + 0.05 * len(lanes):
            bad.append(x["date"])
    merges, waits = sum(len(x["merges"]) for x in a["dates"]), sum(len(x["wait_segs"]) for x in a["dates"])
    agree = not bad and merges == merges_10 and waits == waits_10
    return agree, (f"actogram: {len(a['dates'])} dates, busy {busy / 60:.1f} h (lanes {low / 60:.1f} to {high / 60:.1f} h), "
                   f"{merges} merges, {waits} waits | graph 10: {merges_10} merge marks, {waits_10} wait marks: "
                   + ("agree" if agree else f"DISAGREE{' (busy outside its lanes on ' + ', '.join(bad) + ')' if bad else ''}"))


SECTIONS = [gene_line, merge_line, ring_line, reading_line, gel_line, prt_line, prf_line, atp_line, rng_line, act_line]


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
        agree, line = section(m)
        ok = ok and agree
        print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
