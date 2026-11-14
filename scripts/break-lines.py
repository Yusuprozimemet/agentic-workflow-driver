"""Print a branch's break lines from its break record, or check a spec's `broken:` lines against it.

    python scripts/break-lines.py [--manifest <path>] [--base <rev>]    # the PR body's lines
    python scripts/break-lines.py --spec specs/day-NN-slug.md [--manifest <path>]   # the close's check

`break.py --record` writes each break's entry, with its report, into the branch's manifest
(specs/breaks/day-NN.json on day-NN/, specs/breaks/<slug>.json on change/<slug>). The first form
prints, for each entry the branch added or re-recorded since --base (by default, where HEAD left
main), its `manifest: {...}` line and its `broken: <what> → <report>` line, as break.py printed them:
paste the output into the PR body, so nothing in it is retyped. The second form reads every
`broken:` line in the spec's Acceptance criteria, `broken: none` aside, and fails one with no entry
in the manifest, a name recorded twice, or a report other than the recorded one; it prints each
recorded entry the spec cites nowhere as the `broken:` line to put under its criterion. It runs
nothing: the replay (close-evidence.py --rehearse) still runs each break. An entry copied by hand,
with no "report", is listed as unchecked, not failed. Of Days 1-11's 73 process defects, 33 were
break bookkeeping, most a line copied by hand between the PR, the spec and the manifest (bearing
D10.20: two breaks shared a name, two lines had no entry, one ended in "(close, D10.19)").
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys

from evidence import BROKEN, PR_SUFFIX, criteria, joined, normal

_spec = importlib.util.spec_from_file_location("break_", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                      "break.py"))
brk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(brk)

# The keys break.py's `manifest:` line holds; "report" and "blob" are the record's own.
RECORD_ONLY = ("report", "blob")
SPEC_DAY = re.compile(r"day-(\d+)-")


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace")


def load(text):
    return json.loads(text or "[]")


def added(path, base):
    """The entries at path that base's copy does not hold as they are: those this branch recorded."""
    with open(path, encoding="utf-8") as f:
        now = load(f.read())
    shown = git("show", f"{base}:{path}") if base else None
    before = load(shown.stdout) if shown is not None and shown.returncode == 0 else []
    return [e for e in now if e not in before]


def pr_lines(entries):
    """(lines, unrecorded whats): the manifest and broken: line of each entry that has a report."""
    lines, unrecorded = [], []
    for e in entries:
        if "report" not in e:
            unrecorded.append(e["what"])
            continue
        lines.append("manifest: " + json.dumps({k: v for k, v in e.items() if k not in RECORD_ONLY},
                                               ensure_ascii=False))
        lines.append(f"broken: {e['what']} → {e['report']}")
    return lines, unrecorded


def check(text, entries):
    """[(ok, line)] for each broken: line of the spec, then each entry the spec does not cite."""
    times = {}
    for e in entries:
        times[e["what"]] = times.get(e["what"], 0) + 1
    recorded = {e["what"]: e for e in entries}
    out, cited = [], set()
    for cid, lines in criteria(text).items():
        for what, report in (m.groups() for line in joined(lines) if (m := BROKEN.match(line))):
            if what == "none":
                continue
            cited.add(what)
            label = f"{what} ({cid})"
            if what not in recorded:
                out.append((False, f"no entry: {label}: record it with break.py --record"))
            elif times[what] > 1:
                out.append((False, f"recorded {times[what]} times: {label}: give each break a name of its own"))
            elif "report" not in recorded[what]:
                out.append((True, f"unchecked: {label}: its entry has no report (copied by hand)"))
            elif normal(report) != normal(recorded[what]["report"]):
                out.append((False, f"differs: {label}: the spec says {PR_SUFFIX.sub('', report).strip()!r}, "
                                   f"recorded {recorded[what]['report']!r}"))
            else:
                out.append((True, f"matches: {label}"))
    for e in entries:
        if e["what"] not in cited and "report" in e:
            out.append((True, f"not in the spec: broken: {e['what']} → {e['report']}"))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--manifest", help="the break record (default: the branch's, or the spec's Day's)")
    p.add_argument("--base", help="the PR lines' base (default: where HEAD left main)")
    p.add_argument("--spec", help="check this spec's broken: lines against the record instead")
    a = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    path = a.manifest
    if path is None and a.spec:
        m = SPEC_DAY.search(os.path.basename(a.spec))
        path = f"specs/breaks/day-{m.group(1)}.json" if m else None
    if path is None:
        path, why = brk.record_path("")
        if path is None:
            p.error(why)
    if not os.path.exists(path):
        print(f"break-lines: {path} does not exist: no break recorded")
        return 1
    if a.spec:
        with open(path, encoding="utf-8") as f:
            entries = load(f.read())
        with open(a.spec, encoding="utf-8") as f:
            results = check(f.read(), entries)
        for _, line in results:
            print(line)
        bad = sum(not ok for ok, _ in results)
        cites = sum(not line.startswith("not in the spec") for _, line in results)
        print(f"break-lines: {cites - bad} of {cites} broken: lines in {a.spec} agree with {path}")
        return 1 if bad else 0
    base = a.base or git("merge-base", "main", "HEAD").stdout.strip() or None
    lines, unrecorded = pr_lines(added(path, base))
    for line in lines:
        print(line)
    for what in unrecorded:
        print(f"break-lines: no report for {what!r}: re-run it with break.py --record", file=sys.stderr)
    if not lines:
        print(f"break-lines: no break recorded in {path} on this branch")
    return 1 if unrecorded or not lines else 0


if __name__ == "__main__":
    sys.exit(main())
