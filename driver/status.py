"""status prints where the driver is: its mode and halt, the run's issue and the open parks, the
step in progress, one line per step, the parks by reason, the refusals and the cost per merged
pull request, and the tools the driver refused and the Level 2 count. While a session is live it adds
three progress lines, and with --watch it prints again at each poll until no session is live. It
reads the state folder and the project's open issues, takes no lock and writes nothing."""

import collections
import json
import os
import re
import sys
import time

from driver import issues, lock, runlog

# plan.md, "What it is judged against": the cost per merged pull request the driver is held to.
BASELINE = 1.86
# plan.md, "Levels": the pull requests merged in a row without a change asked, for Level 2.
LEVEL_2_RUN = 15


def run(project, gh, state, watch=None) -> int:
    # With watch (seconds), the report is printed again at each poll until a report finds no live
    # session; that report's code is the run's. The report's own reading decides, so the last
    # block printed is the one that showed no session live.
    if watch is None:
        return _report(project, gh, state)
    while True:
        seen = []
        code = _report(project, gh, state, seen)
        sys.stdout.flush()
        if seen[0] is None:
            return code
        time.sleep(watch)
        print()


def _report(project, gh, state, seen=None) -> int:
    # seen, when given, receives the live session this report read, or None.
    listed, gh_reason = issues.open_issues(project, gh)
    mode, live = _mode(state)
    lines = [mode, "level: 1", _halt(state)]
    if gh_reason:
        lines += ["run's issue: unknown", "open parks: unknown"]
    else:
        lines += [f"run's issue: {_run_issue(listed)}", f"open parks: {_open_parks(listed)}"]
    session, _, reason = runlog.live_session(state)
    if seen is not None:
        seen.append(session)
    records, later = runlog.read(state)
    reason = reason or later
    if reason:
        lines += ["in progress: unknown", f"run log: {reason}"]
    else:
        records = records or []
        late = runlog.late_refusals(state, records)
        lines.append(_in_progress(state, live, records, session))
        if session:
            lines += progress(records, session, _events(state, session), lock.now())
        lines += _steps(records, late)
        lines += _parks(records)
        lines.append(f"refusals: {_refusals(records, late)}")
        lines += _refused(records, late)
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


def progress(records, session, events, now):
    # The three lines a live session adds under its "in progress:" line (Day 11, plan.md N32, N33).
    return [_running(records, session, now), _last_event(events, now), _tokens(events)]


def _running(records, session, now):
    start = next(
        (r for r in records if r.get("event") == "start" and r.get("session") == session), None
    )
    if start is None:
        return "running: unknown (no start line)"
    begun = _time(start.get("at"))
    if begun is None:
        return "running: unknown (no start time)"
    elapsed = _clock(_seconds(now, begun))
    kind = _kind(start.get("prefix"))
    if kind is None:
        return f"running: {elapsed} (no estimate: the step has no kind)"
    lengths = sorted(_earlier_lengths(records, session, kind))
    n = len(lengths)
    if n < 3:
        return f"running: {elapsed} (no estimate: {n} earlier {kind} sessions)"
    middle = n // 2
    if n % 2:
        estimate = lengths[middle]
    else:
        # The mean of the middle two, rounded down to the second.
        estimate = (lengths[middle - 1] + lengths[middle]) // 2
    return (
        f"running: {elapsed} (estimate {_clock(estimate)}, "
        f"the median of {n} earlier {kind} sessions)"
    )


def _earlier_lengths(records, session, kind):
    # The length of each other session of the kind that has an end line: its first end's time minus
    # its first start's. A session with no start line, of another kind, or whose start or end time
    # does not read, is not counted.
    starts = {}
    ends = {}
    for record in records:
        other = record.get("session")
        if other == session:
            continue
        if record.get("event") == "start":
            starts.setdefault(other, record)
        elif record.get("event") == "end":
            ends.setdefault(other, record)
    lengths = []
    for other, start in starts.items():
        if other not in ends or _kind(start.get("prefix")) != kind:
            continue
        begun, ended = _time(start.get("at")), _time(ends[other].get("at"))
        if begun is not None and ended is not None:
            lengths.append(_seconds(ended, begun))
    return lengths


def _time(value):
    # A run log or events time, or None when it is not a lock.STAMP string.
    try:
        return lock.stamp_time(value)
    except (TypeError, ValueError):
        return None


def _kind(prefix):
    # The kind of a step by its prefix; a prefix that is none of the three has none.
    if not isinstance(prefix, str):
        return None
    if prefix.endswith("/spec"):
        return "spec"
    if "/track-" in prefix:
        return "track"
    if prefix.endswith("/close-the-day"):
        return "close"
    return None


def _seconds(later, earlier):
    # Whole seconds from earlier to later; a negative span counts as 0.
    return max(0, int((later - earlier).total_seconds()))


def _clock(seconds):
    # Minutes and seconds with no hours: 75m03s.
    return f"{seconds // 60}m{seconds % 60:02d}s"


def _last_event(events, now):
    if not events:
        return "last event: none yet"
    last = events[-1]
    kind = _text(last.get("kind"))
    at = _time(last.get("at"))
    if at is None:
        return f"last event: {kind}, unknown ago"
    return f"last event: {kind}, {_clock(_seconds(now, at))} ago"


def _tokens(events):
    # Each distinct message counts the last in and out its lines carried: a message's lines repeat
    # the counts of the same reply.
    last = {}
    for event in events:
        if "message" in event:
            # Keyed by the id's JSON text, so an id that is not a string cannot fail the read.
            key = json.dumps(event["message"], sort_keys=True)
            last[key] = (_count(event.get("in")), _count(event.get("out")))
    tokens_in = sum(counts[0] for counts in last.values())
    tokens_out = sum(counts[1] for counts in last.values())
    return f"tokens so far: {tokens_in} in, {tokens_out} out"


def _count(value):
    # A missing or non-int count is 0.
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _events(state, session):
    # The session's events file, read as bytes as stream writes it. A missing or unreadable file is
    # no events; nothing is created here (C08.2).
    try:
        with open(os.path.join(state, "sessions", f"{session}.events.jsonl"), "rb") as events:
            lines = events.read().split(b"\n")
    except OSError:
        return []
    found = []
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            found.append(record)
    return found


def _steps(records, late=()):
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
        refusals += sum(1 for item in late if item["session"] == session)
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


def _refusals(records, late=()):
    # The end lines' denials, and the hook log's refusals after each session's last end line.
    ended = sum(
        _number(record.get("denials")) for record in records if record.get("event") == "end"
    )
    return ended + len(late)


def _refused(records, late=()):
    # One line per tool and input the driver refused, the most often refused first.
    counts = collections.Counter(
        f"{item['tool']}: {item['input']}"
        for record in records
        if record.get("event") == "end"
        for item in record.get("refused") or []
    )
    counts.update(f"{item['tool']}: {item['input']}" for item in late)
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


def _container_opened(records, pr):
    # The newest session that opened this pull request decides: the merge counts only when that
    # session ran in a container.
    ends = []
    for record in records:
        if record.get("event") == "end":
            match = re.match(r"opened: #(\d+)", _text(record.get("outcome")))
            if match and int(match.group(1)) == pr:
                ends.append(record)
    if not ends:
        return False
    session = ends[-1].get("session")
    if session is None:
        return False
    starts = [
        record
        for record in records
        if record.get("event") == "start" and record.get("session") == session
    ]
    return bool(starts) and bool(starts[-1].get("container"))


def level_2_run(records):
    # Counts back from the newest line until a merge asked for a change, a merge whose pull request
    # no container session opened, a close, or a park that says a check is still red; any other
    # line is passed over.
    k = 0
    for record in reversed(records):
        event = record.get("event")
        line = _text(record.get("line"))
        if event == "merged":
            if record.get("changed") is not False:
                break
            if not _container_opened(records, record.get("pr")):
                break
            k += 1
        elif event == "closed" or (event == "park" and "still red after two fixes" in line):
            break
    return k


def _level_2(records):
    return f"level 2: {level_2_run(records)} of {LEVEL_2_RUN} pull requests in a row merged without a change asked"


def _text(value):
    return value if isinstance(value, str) else ""


def _number(value):
    # A null, a bool or anything else that is not a number counts 0, as issue_cost counts it.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return value
