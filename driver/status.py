"""status prints where the driver is: its mode and halt, the run's issue and the open parks, the
step in progress, one line per step, the parks by reason, the refusals and the cost per merged
pull request, and the tools the driver refused and the Level 2 count. It reads the state folder and
the project's open issues, takes no lock and writes nothing."""

import collections
import json
import os
import re
import sys

from driver import issues, lock, runlog

# plan.md, "What it is judged against": the cost per merged pull request the driver is held to.
BASELINE = 1.86
# plan.md, "Levels": the pull requests merged in a row without a change asked, for Level 2.
LEVEL_2_RUN = 15


def run(project, gh, state) -> int:
    listed, gh_reason = issues.open_issues(project, gh)
    mode, live = _mode(state)
    lines = [mode, "level: 1", _halt(state)]
    if gh_reason:
        lines += ["run's issue: unknown", "open parks: unknown"]
    else:
        lines += [f"run's issue: {_run_issue(listed)}", f"open parks: {_open_parks(listed)}"]
    session, _, reason = runlog.live_session(state)
    records, later = runlog.read(state)
    reason = reason or later
    if reason:
        lines += ["in progress: unknown", f"run log: {reason}"]
    else:
        records = records or []
        lines.append(_in_progress(state, live, records, session))
        lines += _steps(records)
        lines += _parks(records)
        lines.append(f"refusals: {_refusals(records)}")
        lines += _refused(records)
        lines.append(_cost(records))
        lines.append(_level_2(records))
    for line in lines:
        print(line)
    if gh_reason:
        print(f"cannot read the project: {gh_reason}", file=sys.stderr)
    return 2 if gh_reason or reason else 0


def _mode(state):
    # Returns (the mode line, whether the lock's process lives).
    if not os.path.exists(lock.path(state)):
        return "mode: off", False
    held = lock.read(state)
    if held is None:
        return "mode: off (the lock cannot be read)", False
    pid, started = held
    if lock.lives(pid, started):
        return f"mode: on (pid {pid}, since {started})", True
    return f"mode: off (a lock names pid {pid}, which is gone)", False


def _halt(state):
    path = os.path.join(state, "halt")
    if not os.path.exists(path):
        return "halt: none"
    try:
        with open(path, "rb") as f:
            text = f.read().decode("utf-8", errors="replace").strip()
    except OSError as error:
        return f"halt: set: the halt file cannot be read: {error.strerror}"
    return f"halt: set: {text}"


def _run_issue(listed):
    # listed is sorted by number, so the first match is the lowest.
    for issue in listed:
        if issue["title"].startswith("Driver run"):
            return f"#{issue['number']}"
    return "none"


def _open_parks(listed):
    parks = [f"#{issue['number']}" for issue in listed if "parked" in issue["labels"]]
    return ", ".join(parks) or "none"


def _in_progress(state, live, records, session):
    if session is not None:
        step = _step(records, session)
    elif live:
        # A wait has no session with a live pid; while the lock's process lives, run.json names it.
        record = _run_json(state)
        if record is None:
            return "in progress: none"
        step, session = record
    else:
        return "in progress: none"
    cost = _cost_of(records, session)
    return f"in progress: {step} (session `{session}`), cost so far ${cost:.2f}"


def _step(records, session):
    # The step of the newest start line for the session; a pid line with no start line has none.
    for record in reversed(records):
        if record.get("event") == "start" and record.get("session") == session:
            return record.get("step")
    return "no start line"


def _run_json(state):
    # Returns (step, session) from run.json, or None when it is absent, unreadable or lacks a key.
    try:
        with open(os.path.join(state, "run.json"), "rb") as f:
            record = json.loads(f.read())
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or "step" not in record or "session" not in record:
        return None
    return record["step"], record["session"]


def _cost_of(records, session):
    return sum(
        _number(record.get("cost_usd"))
        for record in records
        if record.get("event") == "end" and record.get("session") == session
    )


def _steps(records):
    starts = [record for record in records if record.get("event") == "start"]
    if not starts:
        return ["steps: none"]
    lines = ["steps:"]
    for start in starts:
        session = start.get("session")
        ends = [r for r in records if r.get("event") == "end" and r.get("session") == session]
        outcome = str(ends[-1].get("outcome")) if ends else "no end"
        cost = sum(_number(r.get("cost_usd")) for r in ends)
        refusals = sum(_number(r.get("denials")) for r in ends)
        lines.append(
            f"  {start.get('at')} {start.get('step')}: {outcome}, ${cost:.2f}, "
            f"refusals {refusals}, session `{session}`"
        )
    return lines


def _parks(records):
    # A park counts by its text with the session, the pull request and the path count left out.
    counts = collections.Counter(
        _reason(record["line"])
        for record in records
        if record.get("event") == "park" and isinstance(record.get("line"), str)
    )
    if not counts:
        return ["parks by reason: none"]
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return ["parks by reason:"] + [f"  {count} {text}" for text, count in ranked]


def _reason(line):
    line = re.sub(r"`[^`]*`", "`…`", line)
    line = re.sub(r"#\d+", "#n", line)
    return re.sub(r"\(\d+ paths\)", "(n paths)", line)


def _refusals(records):
    return sum(_number(record.get("denials")) for record in records if record.get("event") == "end")


def _refused(records):
    # One line per tool and input the driver refused, the most often refused first.
    counts = collections.Counter(
        f"{item['tool']}: {item['input']}"
        for record in records
        if record.get("event") == "end"
        for item in record.get("refused") or []
    )
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [f"  {count} {text}" for text, count in ranked]


def _cost(records):
    total = sum(
        _number(record.get("cost_usd")) for record in records if record.get("event") == "end"
    )
    merged = sum(1 for record in records if record.get("event") == "merged")
    if not merged:
        return f"cost: ${total:.2f}, merged pull requests 0 (baseline ${BASELINE:.2f})"
    return (
        f"cost: ${total:.2f}, merged pull requests {merged}, ${total / merged:.2f} each "
        f"(baseline ${BASELINE:.2f})"
    )


def _level_2(records):
    # Counts back from the newest line until a merge asked for a change, a close, or a park that
    # says a check is still red; any other line is passed over.
    k = 0
    for record in reversed(records):
        event = record.get("event")
        line = _text(record.get("line"))
        if event == "merged":
            if record.get("changed") is not False:
                break
            k += 1
        elif event == "closed" or (event == "park" and "still red after two fixes" in line):
            break
    return f"level 2: {k} of {LEVEL_2_RUN} pull requests in a row merged without a change asked"


def _text(value):
    return value if isinstance(value, str) else ""


def _number(value):
    # A null, a bool or anything else that is not a number counts 0, as issue_cost counts it.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return value
