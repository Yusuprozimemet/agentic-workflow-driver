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


SECTIONS = [gene_line, merge_line]


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
