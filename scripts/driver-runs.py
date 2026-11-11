#!/usr/bin/env python3
"""Count the driver's run log into docs/dashboard/driver-runs.json, for the dashboard.

    python scripts/driver-runs.py --project <the project the driver ran on> [--state <dir>]
    python scripts/driver-runs.py --out <file> [--state <dir>]

The run log (<state>/run.jsonl, driver/runlog.py) sits on the maintainer's machine, uncommitted: CI
cannot read it, and a step session cannot either (the driver's hook refuses a command that names its
folder). So, as scripts/token-usage.py does for the transcripts, it runs on that machine, outside a
session: scripts/publish-counts.py runs it with --out at each session's start and end and pushes the
file to the dashboard-data branch, where the page's build takes it (one may also be committed in the
project). That file is all the page knows of the driver; its format is the contract, and the page
draws nothing of the driver without it:

    {"counted": "<when, on this machine's clock with its offset>",
     "steps": [one per step the log names, in the log's order:
       {"step": "<the kit's sentence>", "day": <its Day, or null>, "prefix": "<branch prefix, or null>",
        "sessions": [{"session": "<uuid>", "start": "<UTC>", "end": "<UTC, or null>", "cost": <dollars>,
                      "denials": <refused tool calls>, "fixes": <fix rounds>, "crashed": <true or false>}],
        "fixes": <the sessions' fix rounds>, "crashes": <its sessions that crashed>,
        "pr": <the pull request it opened, or null>, "merged": "<UTC, or null>",
        "parks": [{"at": "<UTC>", "line": "<the park line>", "by": "maintainer" or "fault"}],
        "ended": "merged", "fixed", "parked" or "open"}]}

A step is the sessions started for one branch prefix, with the parks written for its sentence; a park
before any session (the end of a phase, a sentence the driver does not know) is a step with no
session. It ended "parked" when it has a park, whatever came after: it needed a person. Otherwise
"fixed" when it merged after a fix round, "merged" when it merged with none, and "open" until then.
A session crashed when its last line is not an end line and its process is gone. A park's wait is not
here: it is how long its issue stayed open, which scripts/spec-drift.py reads from GitHub.

What the log does not hold is not here either: when the driver was switched on and off, and a halt.
The log does not name its project, so one state folder serves one project, or the count mixes them.
"""
import argparse
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
sys.path.insert(0, ROOT)
from driver import runlog  # noqa: E402
from driver.steps import classify  # noqa: E402

FILE = os.path.join("docs", "dashboard", "driver-runs.json")
OPENED = re.compile(r"opened: #(\d+)")
# The parks that are a decision the plan keeps for the maintainer (plan.md, "When the driver parks"):
# the session's own PARK line, the end of a phase or of the plan, a spec nobody may write but them,
# and a pull request the driver may not merge or that they closed. Every other park is a fault: of
# the driver, the kit, the session or the machine.
MAINTAINERS = tuple(re.compile(p) for p in (
    r"park: the session parked: ",
    r"park: the end of Phase ",
    r"park: a stopping point after Day ",
    r"park: Day \d+ has no spec: ",
    r"park: every day is done",
    r"park: there are no day specs",
    r"park: #\d+ touches plan\.md",
    r"park: #\d+ touches a human-only path: ",
    r"park: #\d+ carries Oversized:",
    r"park: #\d+ was closed without a merge",
))


def by(line):
    """Whose a park is: "maintainer" for a decision that is theirs, "fault" for everything else."""
    return "maintainer" if any(p.match(line) for p in MAINTAINERS) else "fault"


def number(value):
    # A null, a bool or anything else that is not a number counts 0, as driver/status.py counts it.
    return 0 if isinstance(value, bool) or not isinstance(value, (int, float)) else value


def text(value):
    return value if isinstance(value, str) else None


def count(records, live=None):
    """The steps the log's records name, as the docstring above gives them. `live` is the session whose
    process still runs (runlog.live_session), which has no end line and has not crashed."""
    steps, sessions, by_pr = {}, {}, {}

    def step_of(sentence, prefix=None):
        sentence = text(sentence) or ""
        known = classify(sentence)
        prefix = prefix or known.prefix
        return steps.setdefault(prefix or sentence, dict(
            step=sentence, day=known.day, prefix=prefix, sessions=[], fixes=0, crashes=0, pr=None, merged=None,
            parks=[], ended="open"))

    for record in records:
        event, at, session = record.get("event"), text(record.get("at")), text(record.get("session"))
        if event == "start":
            step = step_of(record.get("step"), text(record.get("prefix")))
            run = dict(session=session, start=at, end=None, cost=0.0, denials=0, fixes=0, crashed=False)
            step["sessions"].append(run)
            sessions[session] = (step, run)
        elif event == "end" and session in sessions:
            # A session has an end line for its first run and one more for each resume: the last is
            # its end, and their costs and refusals add up.
            step, run = sessions[session]
            run["end"] = at
            run["cost"] = round(run["cost"] + number(record.get("cost_usd")), 4)
            run["denials"] += int(number(record.get("denials")))
            opened = OPENED.match(text(record.get("outcome")) or "")
            if opened:
                step["pr"] = int(opened.group(1))
                by_pr[step["pr"]] = step
        elif event == "fix" and session in sessions:
            # Written before the resume it records: until that resume's end line, the session is open again.
            run = sessions[session][1]
            run["fixes"] += 1
            run["end"] = None
        elif event == "park":
            line = text(record.get("line")) or ""
            step_of(record.get("step"))["parks"].append(dict(at=at, line=line, by=by(line)))
        elif event == "merged":
            # A pull request found open at a start has no session of the driver's: its merge is no step's.
            pr = record.get("pr")
            step = by_pr.get(pr) if isinstance(pr, int) else None
            if step is not None and step["merged"] is None:
                step["merged"] = at
    for step in steps.values():
        for run in step["sessions"]:
            run["crashed"] = run["end"] is None and run["session"] != live
        step["fixes"] = sum(run["fixes"] for run in step["sessions"])
        step["crashes"] = sum(run["crashed"] for run in step["sessions"])
        step["ended"] = ("parked" if step["parks"] else "open" if step["merged"] is None
                         else "fixed" if step["fixes"] else "merged")
    return list(steps.values())


def summary(steps):
    ended = [step["ended"] for step in steps]
    faults = sum(any(p["by"] == "fault" for p in step["parks"]) for step in steps)
    return (f"{len(steps)} steps: {ended.count('merged')} merged with no person, {ended.count('fixed')} after fixing "
            f"themselves, {ended.count('parked')} parked ({faults} by a fault), {ended.count('open')} open")


def main(argv=None, now=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--state", default=os.path.join(ROOT, "state"),
                    help="the driver's state folder (default: the one beside run-steps.py)")
    where = ap.add_mutually_exclusive_group(required=True)
    where.add_argument("--project", help=f"the project the driver ran on: writes its {FILE.replace(os.sep, '/')}")
    where.add_argument("--out", help="the file to write, instead of the project's")
    args = ap.parse_args(argv)
    out = args.out or os.path.join(args.project, FILE)
    log = runlog.path(args.state)
    records, reason = runlog.read(args.state)
    if reason:
        print(f"{log}: {reason}; nothing written", file=sys.stderr)
        return 2
    if records is None:
        print(f"{log}: no run log; nothing written")
        return 0
    if not os.path.isdir(os.path.dirname(os.path.abspath(out))):
        print(f"{out}: its folder does not exist; nothing written", file=sys.stderr)
        return 2
    steps = count(records, runlog.live_session(args.state)[0])
    at = (now or datetime.datetime.now()).astimezone().isoformat(timespec="seconds")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        rows = ",\n".join(json.dumps(step, separators=(",", ":"), ensure_ascii=False) for step in steps)
        f.write('{\n"counted":' + json.dumps(at) + ',\n"steps":[\n' + rows + "\n]\n}\n")
    print(f"{out}: counted up to {at}, {summary(steps)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
