"""Measure how the spec and the code move against each other, merge by merge.

Writes one JSON file for the migration dashboard: gap and name coverage per merge on
main, and each day's status, tracks and criteria. Needs git, the gh CLI and numpy.

    python scripts/spec-drift.py --out data.json
    python scripts/spec-drift.py --build dashboard.html  # docs/dashboard/ as one file, data inlined

Gap: angle between spec and code over the code-like names the specs put in backticks, counted in
the specs and in the code (Markdown, data/, screenshots, this dashboard and comment lines left
out: a comment naming a thing is not the thing). A code file or folder whose name is a spec name
counts once, at its path: a spec cites a test by its file. Python's own names (ImportError) are not
spec names. Each merge's gap uses only the names the specs had used by then, so a later spec does
not move an earlier point.

The angle needs a reference to be read. Two vectors of counts are never negative, so they sit
well under 90° even when they have nothing to do with each other. Gap chance is the gap to the
same code counts shuffled across the names (the mean and 95% band of CHANCE_DRAWS, seeded): a gap near it says
the code uses the spec's names in no particular proportion. The angle is the secondary reading;
two plain set figures come first. Name coverage: of the names the specs use at a merge, the share
the code has. Jaccard: the names in both, over the names in either (a name the specs have dropped
but the code keeps counts against it). Names kept: that other direction alone, how many names the
specs once used and have dropped that the code still has. Names retired: of the names the specs
use that the code lacks, those it had at an earlier merge.

Per merge, the gap read against chance (what the dashboard draws):
  gap_excess: the gap less its chance value, so zero is chance; gap_excess_band: the 95% band of
  the shuffles around that value; gap_percentile: the share of the shuffles the gap sits above.
  class_coverage: of the reached names, the share in the code, by class (prod, test, flags);
  class_names: the named names per class, and the flags the specs name, counted apart as they
  do not enter the gap. A test helper found only in test files counts as a test name.
  names_added, names_dropped: per class, the names the specs use at this merge and not the one
  before, and the other way round (None at the origin). The dashboard plots each spec-change
  PR's names added against its step on gap_excess.

Boundaries: for the services the project file names, how much of their main source has left the
monolith for services/, and how many imports still cross from one service's packages into
another's. Both are read from the tree, like the gap; neither depends on what a day ticked.

The project file, spec-drift.config.json at the root, holds what git cannot tell about this
repository, every field optional: tests renamed to another stem and directories moved, by PR
(`renamed`, `moved`: [pr, old, new]), the directories a Verify block may cd into (`verify_bases`),
the packages each service takes under `package_root` (`services`), and the infra workflow's file
(`infra_workflow`; none, and gh is not asked for its runs).
"""
import argparse
import ast
import builtins
import collections
import datetime
import fnmatch
import functools
import hashlib
import importlib.util
import json
import os
import platform
import posixpath
import re
import shlex
import subprocess
import sys
import tempfile

import numpy as np

# The modules spec-drift.py is split into sit beside it, also when a test loads it by path.
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from spec_drift_common import *  # noqa: F403
from spec_drift_git import *  # noqa: F403
from spec_drift_specs import *  # noqa: F403
from spec_drift_handoffs import *  # noqa: F403
from spec_drift_data import *  # noqa: F403
from spec_drift_metrics import *  # noqa: F403
from spec_drift_page import *  # noqa: F403
from spec_drift_plan import plan_graph
from spec_drift_score import quality_score


# What every figure built on the backticked names cannot see; the dashboard lists these as written.
CAVEATS = [
    "Gap, name coverage and Jaccard see only identifiers the specs put in backticks: a name written "
    "in plain prose is not counted.",
    "They match names, not meaning: prose is not understood, so a spec can name a thing the code has "
    "and still describe it wrongly.",
    "A name a spec says should disappear still counts as shared vocabulary while the code has it.",
    "Name coverage counts test and tooling files as code.",
    "A code file or folder named after a spec name counts as that name in the code; Python's own "
    "names, such as ImportError, are not spec names.",
    "Production name coverage counts only files the path rules call production: a path, not proof "
    "that the file runs in the product. Test and tool names may legitimately be absent from it.",
    "The clock graph shows the clock of the machine that last ran scripts/token-usage.py: its sessions "
    "are stamped with its offset, and GitHub's times are moved to it. A session on another machine is not drawn.",
    "The clock graph draws only what leaves a time: a session's transcript, a pull request, its checks, a merge. "
    "A session is busy while it writes and while it waits on a command it ran. The maintainer's reading, thinking "
    "and typing leave no time, and neither does a command sent to the background, one run outside a session, "
    "or a check that runs after a merge.",
    "Every dollar here is what the tokens would cost on the pay-per-token API at list prices, counted from this "
    "repository's sessions on the maintainer's computer. It is not what was paid: a subscription costs the same "
    "whatever was used. A date with no cost is a date with no session in this repository.",
    "A yardstick's figure for a Day covers everything merged between the close before it and its own, whichever "
    "Day the work belonged to.",
]


# The files this script is split into, beside it: a change to any of them starts the cache over
# (load_cache) and counts as the script edited (provenance).
SOURCES = ("spec-drift.py", "spec_drift_common.py", "spec_drift_git.py", "spec_drift_specs.py",
           "spec_drift_handoffs.py", "spec_drift_data.py", "spec_drift_metrics.py", "spec_drift_page.py",
           "spec_drift_plan.py", "spec_drift_score.py")


def load_cache(path):
    version = hashlib.sha256()
    for name in SOURCES:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name), "rb") as f:
            version.update(f.read().replace(b"\r\n", b"\n"))
    version = version.hexdigest()
    try:
        with open(path, encoding="utf-8") as f:
            cached = json.load(f)
    except (OSError, ValueError):
        cached = {}
    CACHE.clear()
    CACHE.update(cached if cached.get("version") == version else dict(version=version))


def save_cache(path):
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(CACHE, f, separators=(",", ":"))
    os.replace(path + ".tmp", path)


def unwritten(days, order):
    """The cleanup or close-out day before its spec exists: its number, and the phase of the day it
    follows in the run order, so the roadmap shows it where it runs."""
    which = next((p for p in (CLEANUP, CLOSEOUT) if p in order), None)
    if which is None:
        return None
    phase = {d["day"]: d.get("phase") for d in days}
    before = [d for d in order[:order.index(which)] if d not in PLACEHOLDERS]
    return dict(day=max(d["day"] for d in days) + 1,
                phase=phase.get(before[-1]) if before else None, title=f"The {which} day")


def unwritten_lines(plan):
    """The plan item each unwritten day comes from, by placeholder, read as run_order() reads it."""
    out = {}
    for line in plan_items(plan):
        if "numbered from" in line:
            out[PLATFORM] = line
        if "numbered after the last" in line:
            out[CLOSEOUT if "close-out" in line else CLEANUP] = line
    return out


def next_step(days, open_prs, order, stop, lines=None):
    """What to do next. An unwritten day quotes the plan item it comes from (`lines`, from unwritten_lines())."""
    if open_prs:
        return "Waiting on " + ", ".join(f"#{p['number']} {p['title']}" for p in open_prs)
    by_day = {d["day"]: d for d in days}
    left = [d for d in order if d in PLACEHOLDERS or d not in by_day or by_day[d]["status"] not in FINISHED]
    if not left:
        return "Every day is done." if days else "No day specs yet: fill in plan.md, then write the first day's spec (specs/README.md)."
    if left[0] in PLACEHOLDERS:
        line = (lines or {}).get(left[0], "")
        first = re.search(r"numbered from (\d+)", line)
        day = int(first.group(1)) if left[0] == PLATFORM and first else unwritten(days, order)["day"]
        return f'Day {day:02d}: write its day spec (plan.md: "{line}")'
    if stop is not None and order.index(left[0]) > order.index(stop):
        return f"Day {stop:02d} is done: stop and evaluate before going on (plan.md)"
    if left[0] not in by_day:
        return f"Day {left[0]:02d}: write its day spec (plan.md lists it, specs/ has none)"
    day = by_day[left[0]]
    if not any(p["kind"] == "spec" for p in day["prs"]):
        return f"Day {day['day']:02d}: read the spec against the code, then the spec-change PR"
    left = [t for t in day["tracks"] if t not in day["tracks_merged"]]
    if left:
        return f"Day {day['day']:02d} Track {left[0]}: {day['track_work'][left[0]]}"
    for t in day.get("tracks_unopened", []):
        return f"Day {day['day']:02d} Track {t['track']}: announced in #{t['pr']}, no branch names it"
    return f"Day {day['day']:02d}: the closing PR"


def provenance():
    """What made these numbers: the script's commit, the versions, and the draws behind each band."""
    here = os.path.dirname(os.path.abspath(__file__))
    dirty = bool(run("git", "status", "--porcelain", "--", *(os.path.join(here, n) for n in SOURCES)).strip())
    head = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], capture_output=True, text=True)
    return dict(commit=head.stdout.strip() or None, script_edited=dirty,  # None before the first commit
                python=platform.python_version(), numpy=np.__version__,
                chance_draws=CHANCE_DRAWS)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    out = ap.add_mutually_exclusive_group()
    out.add_argument("--out", default="spec-drift.json")
    out.add_argument("--build", help="write docs/dashboard/ here as one page, with the data inlined")
    ap.add_argument("--cache", default=CACHE_FILE, help="what earlier runs read from git (default: %(default)s)")
    ap.add_argument("--no-cache", action="store_true", help="read everything from git, and keep nothing")
    args = ap.parse_args()
    if not args.no_cache:
        load_cache(args.cache)
    listed, runs, note = github()
    data_branch()
    prs = {p["number"]: p for p in listed}
    open_prs = sorted((p for p in listed if p["state"] == "OPEN"), key=lambda p: p["number"])
    with Blobs() as blobs:
        snaps = snapshots(prs)
        head = snaps[-1]["sha"]
        spec_days = [d for d in map(day_of, run("git", "ls-tree", "--name-only", head, "specs/").split()) if d]
        plan = blobs.read(head, "plan.md")
        rows, files, vocab, lines = trajectory(snaps, blobs, run_order(plan, spec_days)[0])
        days, order, stop = roadmap(snaps, prs, blobs)
        evidence_history(rows, days, snaps, blobs)
        boundaries(rows, snaps, blobs)
        handoffs = hand_offs(days, order, head, blobs)
        checks = evidence_checks(days, snaps)
        index, attention = criterion_index(days, checks, handoffs, snaps, blobs, order)
        attach_plain(index)
        stories = user_stories(listed)
        attach_abilities(index, stories["stories"])
        tests = test_inventory(run("git", "ls-tree", "-r", "--name-only", head, "tests/", "scripts/").split("\n"),
                               lambda path: blobs.read(head, path))
        now = dict(generated=datetime.datetime.now().astimezone().isoformat(timespec="minutes"),
                   head=snaps[-1]["sha"], last_pr=snaps[-1]["pr"],
                   current_day=next((d["day"] for d in days if d["status"] == "active"), None),
                   next_step=next_step(days, open_prs, order, stop, unwritten_lines(plan)), stop_after=stop,
                   unwritten=unwritten(days, order),
                   open_prs=[dict(number=p["number"], title=p["title"], url=p["url"]) for p in open_prs])
        concluded = conclusion(blobs.read(snaps[-1]["sha"], "docs/lab-notebook.md"))
        tokens = token_usage()
        real = dict(now=now, rows=rows, files=files, days=days, origin_lines=lines,
                    order=[d for d in order if d not in PLACEHOLDERS],
                    out_of_order=out_of_order(order),
                    removals=removal_history(days, snaps, blobs),
                    hand_offs=handoffs, look_ahead=look_ahead(snaps, days, index, order, blobs),
                    criteria_index=index, attention=attention, test_inventory=tests,
                    defect_recurrence=recurrence(days),
                    user_stories=stories, plan=plan_graph(head, blobs, rows),
                    gate_report=gate_report(days, refusals("gates.json"), refusals()),
                    other_groups=other_groups(rows),
                    vocab_size=vocab, tokens=tokens, refusals=refusals(),
                    verification=verification(prs, runs),
                    infra=infra(INFRA_WORKFLOW),
                    deployment=deployment(),
                    evidence_checks=checks, replay=replay_history(),
                    conclusion=concluded, yardsticks=yardsticks(concluded, tokens),
                    clock=clock(prs, runs), counted=counted(), driver_runs=driver_runs(parked_issues(note)),
                    data=data_source(),
                    meta=dict(caveats=CAVEATS + [note] * bool(note), provenance=provenance(),
                              break_line_from_pr=BREAK_LINE_FROM_PR, project=project_name(),
                              phases=phases(plan), stops=stops(plan)))
        real["score"] = quality_score(real)
        if args.build:
            # The re-check rows are on the data branch, every other file the panel quotes on main.
            how_read = lambda path: (data_text("replay-history.json") or "") if path == HOW_REPLAY else blobs.read(head, path)  # noqa: E731
            real["how_this_works"] = how_excerpts(how_read, how_specs(days))
    payload = page_data(real, spec_days) if args.build else real
    data = json.dumps(payload, separators=(",", ":"))
    target = args.build or args.out
    if args.build:
        data = build(data)
    with open(target, "w", encoding="utf-8") as f:
        f.write(data)
    if not args.no_cache:
        save_cache(args.cache)
    print(f"{target}: {len(rows)} snapshots, {len(days)} days, next: {now['next_step']}" + (f" ({note})" if note else "")
          + (" (example data: no day specs yet)" if payload.get("demo") else ""))
    rec = real["defect_recurrence"]
    print(f"defects: {len(rec['recurrences'])} of {rec['with_id']} with an ID repeat an earlier one")
    for p in rec["problems"]:
        print(f"defect ID not counted: {p}")
    for p in real["yardsticks"]["problems"]:
        print(f"yardstick not counted: {p}")
    for g in real["gate_report"]["gates"]:
        print(gate_line(g))


def gate_line(g):
    """One gate's line on the console: what it caught, its runs and cost. A hooks gate with no
    refusal log yet has caught nothing that can be counted, not refused anything."""
    caught = (f"{g['defects']} defects" if g["found"] is not None else
              "no refusal log yet" if g["refused"] is None else f"{g['refused']} refused")
    return f"gate {g['gate']}: {caught}, {g['runs']} runs, ${g['cost']:,.2f}"


if __name__ == "__main__":
    main()
