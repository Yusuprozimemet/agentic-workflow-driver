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


SECTIONS = [gene_line, merge_line, ring_line, reading_line, gel_line, prt_line]


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
