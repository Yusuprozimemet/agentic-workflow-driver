"""A closing PR's defect views, printed from one record: the Defect lines in the day spec's Notes.

    python scripts/close-views.py specs/day-NN-slug.md

It prints three blocks to paste unchanged: the Defects bullet of the Day's entry in
docs/lab-notebook.md, the Day's cell in its "Escapes per day" row, and the closing PR body's
"## Defects" section. The Notes stay the only record (specs/README.md, "Record every defect"):
a tag is changed there, and this run again, never in a view. Lines are read and staged as
spec-drift.py reads them (spec_drift_specs.defect_lines, spec_drift_metrics.found_stage), so the
counts here are the dashboard's. Exit 1 when the spec has no Defect line.
"""

import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline  # noqa: E402,F401  (importing it puts the pipeline's folders on the path)
from spec_drift_metrics import CAUSES, LAYER_RANK, found_stage, found_tag
from spec_drift_specs import DEFECT_FIELD, DEFECT_LINE


def read(text):
    """Each Defect line: its ID (or its place, for a short spec's), its fields and its text, as
    spec_drift_specs.defect_lines splits them: fields until the first part that is not one."""
    lines, out = text.splitlines(), []
    for i, line in enumerate(lines):
        m = DEFECT_LINE.match(line)
        if not m:
            continue
        rest = [m.group(2)]
        for more in lines[i + 1 :]:
            if not more.startswith("  ") or not more.strip():
                break
            rest.append(more.strip())
        parts, fields = [p.strip() for p in " ".join(rest).split(" · ")], {}
        while parts and (f := DEFECT_FIELD.match(parts[0])) and f.group(1) not in fields:
            fields[f.group(1)] = f.group(2)
            parts.pop(0)
        out.append(
            dict(id=m.group(1) or f"Defect {len(out) + 1}", text=" · ".join(parts), **fields)
        )
    return out


def shown(value):
    """A found: or cause: value as written, without the "the " and "(…)" older Notes add."""
    return re.sub(r" \(.*\)$", "", re.sub(r"^the ", "", (value or "").strip()))


def made_day(row):
    m = re.fullmatch(r"day 0*(\d+)", (row.get("made") or "").strip().lower())
    return int(m.group(1)) if m else None


def ids(rows):
    return ", ".join(r["id"] for r in rows)


def found_counts(rows, day):
    """Found values in the order the layers run (ties in the Notes' order), then those off the list."""
    on, off = {}, {}
    for r in rows:
        stage = found_stage(r.get("found"), day)
        (on if stage else off).setdefault(found_tag(r.get("found")), []).append(r)
    order = sorted(on.values(), key=lambda g: LAYER_RANK[found_stage(g[0].get("found"), day)])
    text = ", ".join(f"{shown(g[0].get('found'))} {len(g)}" for g in order)
    if off:
        text += "; off the found: list: " + ", ".join(
            f"{shown(g[0].get('found')) or 'none'} {len(g)} ({ids(g)})" for g in off.values()
        )
    return text


def cause_counts(rows):
    tags = Counter(found_tag(r.get("cause")) for r in rows)
    on = sorted((c for c in CAUSES if tags[c]), key=lambda c: -tags[c])
    text = ", ".join(f"{c} {tags[c]}" for c in on)
    off = [r for r in rows if found_tag(r.get("cause")) not in CAUSES]
    if off:
        text += "; off the cause: list: " + ids(off)
    return text


def earlier(rows, day):
    """The lines whose catchable: names a layer that runs before the one that found them."""
    out = []
    for r in rows:
        s, c = (
            found_stage(r.get("found"), day),
            found_stage(r.get("catchable"), day) if r.get("catchable") else None,
        )
        if s and c and LAYER_RANK[c] < LAYER_RANK[s]:
            out.append(r)
    return out


def views(rows, day):
    n = len(rows)
    escapes = [r for r in rows if made_day(r) not in (None, day)]
    by_day = {}
    for r in escapes:
        by_day.setdefault(made_day(r), []).append(r)
    from_days = sorted(by_day.items())
    none = [r for r in rows if (r.get("made") or "").strip().lower() == "none"]
    untagged = [r for r in rows if made_day(r) is None and r not in none]
    soon = earlier(rows, day)
    no_catch = [r for r in rows if not r.get("catchable")]
    off_catch = [r for r in rows if r.get("catchable") and found_stage(r["catchable"], day) is None]

    esc = (
        f"Escapes: {len(escapes)}"
        + (
            ", from " + ", ".join(f"Day {d:02d} ({ids(g)})" for d, g in from_days)
            if escapes
            else ""
        )
        + "."
    )
    catch = f"Catchable earlier: {len(soon)} of {n}" + (
        " ("
        + "; ".join(
            f"{r['id']} found by {shown(r.get('found'))}, catchable by {shown(r.get('catchable'))}"
            for r in soon
        )
        + ")"
        if soon
        else ""
    )
    if no_catch:
        catch += (
            "; no line has a `catchable:`"
            if len(no_catch) == n
            else f"; {len(no_catch)} with no `catchable:` ({ids(no_catch)})"
        )
    if off_catch:
        catch += f"; off the found: list in catchable: {ids(off_catch)}"
    notebook = f"- **Defects:** {n}. {found_counts(rows, day)}.\n  Causes: {cause_counts(rows)}. {esc}\n  {catch}."

    this = n - len(escapes) - len(none) - len(untagged)
    if not escapes and not none and not untagged:
        cell = f"0: all {n} are `made: Day {day:02d}`"
    else:
        cell = [
            f"{len(escapes)}: "
            + ", ".join(f"{len(g)} from Day {d:02d} ({ids(g)})" for d, g in from_days)
            if escapes
            else "0 from a day"
        ]
        if none:
            cell.append(
                f"{none[0]['id']} is `made: none`"
                if len(none) == 1
                else f"{len(none)} `made: none` ({ids(none)})"
            )
        if untagged:
            cell.append(f"{len(untagged)} with no `made:` day ({ids(untagged)})")
        cell = "; ".join(cell + [f"{this} of the {n} are `made: Day {day:02d}`"])

    pr = [
        "## Defects",
        "",
        f"From the Notes' {n} Defect lines, by `scripts/close-views.py`.",
        "",
        f"- Found: {found_counts(rows, day)}",
        f"- Cause: {cause_counts(rows)}",
    ]
    pr += [f"- Escapes: {r['id']} (made: {r['made']}): {r['text']}" for r in escapes] or [
        "- Escapes: none"
    ]
    pr += [
        f"- An earlier layer could have caught: {r['id']} (found: {shown(r.get('found'))}, catchable: "
        f"{shown(r.get('catchable'))}): {r['text']}"
        for r in soon
    ] or ["- An earlier layer could have caught: none"]
    if no_catch:
        pr.append(f"- No catchable: {'all ' + str(n) if len(no_catch) == n else ids(no_catch)}")
    if off_catch:
        pr.append(f"- Catchable: off the found: list: {ids(off_catch)}")
    return notebook, cell, "\n".join(pr)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[2].strip())
        return 2
    path = argv[0]
    day = int(re.search(r"day-(\d+)", os.path.basename(path)).group(1))
    with open(path, encoding="utf-8") as f:
        rows = read(f.read())
    if not rows:
        print(f"no Defect line in {os.path.basename(path)}")
        return 1
    notebook, cell, pr = views(rows, day)
    print(
        f"Notebook, the Day's entry:\n{notebook}\n\nNotebook, Escapes per day:\n{cell}\n\nClosing PR body:\n{pr}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
