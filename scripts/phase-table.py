"""The phase-end table: what the maintainer reads at a phase's stop, beside the plan-auditor's report.
It prints, per phase, the Defect lines' counts, the gates that found nothing, the cost and the hooks'
refusals, from the JSON spec-drift.py --out writes. With --phase N it prints that phase's counted Days
beside it. It takes the JSON path and --phase, and no other flags.

    python scripts/phase-table.py [spec-drift.json] [--phase N]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spec_drift_metrics import STAGES, defect_counts, phase_table  # noqa: E402

NOTE = (
    "Found after the close: evidence replay, dashboard or Day NN review, made: not none. "
    "Before Day 12 evidence replay named the rehearsal too: its unsplit part is an upper bound."
)


def header(row):
    days = row["days"]
    if not days:
        return f"Phase {row['phase']}"
    if len(days) == 1:
        return f"Phase {row['phase']} (Day {days[0]})"
    return f"Phase {row['phase']} (Days {min(days)}-{max(days)})"


def per(value):
    return "-" if value is None else str(value)


def refusals_text(row):
    return ", ".join(f"{g} {n}" for g, n in row["refusals"].items()) or "none"


def main():
    parser = argparse.ArgumentParser(
        description="Print the phase-end table from spec-drift.py's JSON."
    )
    parser.add_argument("path", nargs="?", default="spec-drift.json")
    parser.add_argument("--phase", type=int)
    args = parser.parse_args()
    with open(args.path, encoding="utf-8") as f:
        d = json.load(f)
    t = phase_table(d["days"], d["clock"]["prs"], d.get("tokens") or [], d.get("refusals") or [])
    rater = defect_counts(d["days"])["rater"]
    if args.phase is None:
        cols = [(header(r), r, False) for r in t["phases"]]
    else:
        mine = [r for r in t["phases"] if r["phase"] == args.phase]
        if not mine or not mine[0]["days"]:
            sys.exit(f"phase {args.phase} has no counted Day")
        cols = [(f"Day {r['day']}", r, True) for r in t["days"] if r["phase"] == args.phase]
        cols.append((header(mine[0]), mine[0], False))
    body = [
        ("Criteria", lambda r, day: str(r["criteria"])),
        ("Defects (per criterion)", lambda r, day: f"{r['defects']} ({per(r['per_criterion'])})"),
        ("Caught late", lambda r, day: str(r["late"])),
        ("Escapes (made on another Day)", lambda r, day: str(r["escapes"])),
        (
            "Found after the close (unsplit)",
            lambda r, day: f"{r['after_close']} ({r['after_close_unsplit']})",
        ),
    ]
    body += [
        (f"Found by {s}", lambda r, day, s=s: str(r["stages"].get(s, 0)))
        for s in STAGES
        if any(r["stages"].get(s) for _, r, _ in cols)
    ]
    body += [
        ("Gates that found nothing", lambda r, day: ", ".join(r["silent"]) or "none"),
        ("Cost, its Days", lambda r, day: f"${r['cost_days']:.2f}"),
        ("Cost, the rest of its dates", lambda r, day: "-" if day else f"${r['cost_between']:.2f}"),
        ("Refusals in its dates", lambda r, day: "-" if day else refusals_text(r)),
    ]
    heads = [""] + [title for title, _, _ in cols]
    lines = [
        "|" + "|".join(f" {c} " if c else " " for c in heads) + "|",
        "|" + "|".join("---" for _ in heads) + "|",
    ]
    for label, value in body:
        cells = [label] + [value(r, day) for _, r, day in cols]
        lines.append("|" + "|".join(f" {c} " if c else " " for c in cells) + "|")
    lines.append("")
    agree = [
        f"{tag} {rater[tag][0]} of {rater[tag][1]}"
        for tag in ("stage", "cause", "made")
        if tag in rater
    ]
    if agree:
        lines.append("Rater agreement, all Days: " + ", ".join(agree))
    lines.append(NOTE)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
