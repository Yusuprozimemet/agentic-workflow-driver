"""The driver's run log, the file <state>/run.jsonl: one JSON object per line, a start line before
each session, a pid line once its process has started, an end line after it, and a fix line before
each resume. Each line is fsynced before the call returns, so a crash leaves at most a torn last
line. open_session() names the last session started for a prefix that has no end line, and a log
it cannot read parks the driver: a torn log is never guessed past."""

import datetime
import json
import os

from driver import lock

STAMP = "%Y-%m-%dT%H:%M:%SZ"
USED_WHEN_UNREADABLE = 2


def path(state):
    return os.path.join(state, "run.jsonl")


def stamp():
    return datetime.datetime.now(datetime.UTC).strftime(STAMP)


def start(state, step, prefix, session, claude, issue=None):
    record = {
        "event": "start",
        "at": stamp(),
        "step": step,
        "prefix": prefix,
        "session": session,
        "claude": claude,
    }
    # The run's issue goes last, and only when there is one, so that a start line without it keeps
    # its keys; issue_cost reads it to show the run's issue what the run has cost.
    if issue is not None:
        record["issue"] = issue
    append(state, record)


def end(state, session, outcome, cost_usd, denials, refused=None):
    record = {
        "event": "end",
        "at": stamp(),
        "session": session,
        "outcome": outcome,
        "cost_usd": cost_usd,
        "denials": denials,
    }
    # The refused tools go last, and only when the session was refused any, so that an end line
    # without them keeps its keys, as start does with its issue.
    if refused is not None:
        record["refused"] = refused
    append(state, record)


def wait(state, pr):
    # Written before the first read of the pull request, so a wait that ends in any way names it.
    append(state, {"event": "wait", "at": stamp(), "pr": pr})


def park(state, step, line, pr=None, head=None):
    # Every park the driver prints is counted, one written before a session and one after it alike.
    # pr and head go last, only the gated parks give them: the other park lines keep their keys.
    record = {"event": "park", "at": stamp(), "step": step, "line": line}
    if pr is not None:
        record["pr"] = pr
    if head is not None:
        record["head"] = head
    append(state, record)


def merged(state, pr, head=None, changed=None):
    # changed is True or False when both heads are known, else null; head goes only when known.
    record = {"event": "merged", "at": stamp(), "pr": pr}
    if head is not None:
        record["head"] = head
    record["changed"] = changed
    append(state, record)


def closed(state, pr):
    append(state, {"event": "closed", "at": stamp(), "pr": pr})


def fix(state, session, pr, n):
    # Written before the resume it records, so a crash during the resume still counts it.
    append(state, {"event": "fix", "at": stamp(), "session": session, "pr": pr, "n": n})


def pid(state, session, pid, started):
    # Written right after the process starts, a first session or a resume: live_session reads it
    # after a crash, with lock.lives, so a reused pid counts as gone.
    append(
        state, {"event": "pid", "at": stamp(), "session": session, "pid": pid, "started": started}
    )


def append(state, record):
    os.makedirs(state, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    # Binary, so no carriage return is written on Windows; fsynced, so the line is on disk before
    # the session it records starts or the driver goes on.
    with open(path(state), "ab") as f:
        f.write(line.encode("utf-8"))
        f.flush()
        os.fsync(f.fileno())


def _records(state):
    # Returns (records, reason): every line of the log as an object, or why the log cannot be read.
    # records is None when there is no log yet.
    try:
        with open(path(state), "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return None, None
    lines = data.split(b"\n")
    # The empty piece after a final newline is not a line; a torn last line, with none, is one.
    if lines[-1] == b"":
        lines.pop()
    records = []
    for number, raw in enumerate(lines, start=1):
        try:
            record = json.loads(raw.decode("utf-8"))
        except ValueError:
            return None, f"the run log cannot be read at line {number}"
        if not isinstance(record, dict):
            return None, f"the run log cannot be read at line {number}"
        if _bad(record):
            return None, f"the run log cannot be read at line {number}"
        records.append(record)
    return records, None


def read(state):
    # Returns (records, reason), as _records does, and an OSError is a reason too, for a reader
    # outside this module.
    try:
        return _records(state)
    except OSError as error:
        return None, f"the run log cannot be read: {error.strerror}"


def unsettled(state):
    # The (pr, head) of each pull request a wait or park named, in the order first named, that has
    # no merged or closed line yet. head is the newest park's, None when that park has none. A log
    # that cannot be read gives [], and the recovery table decides what that start does.
    records, reason = read(state)
    if reason or records is None:
        return []
    settled = {record["pr"] for record in records if record.get("event") in ("merged", "closed")}
    named, heads = [], {}
    for record in records:
        event = record.get("event")
        if event == "wait" or (event == "park" and "pr" in record):
            if record["pr"] not in named:
                named.append(record["pr"])
            if event == "park":
                heads[record["pr"]] = record.get("head")
    return [(pr, heads.get(pr)) for pr in named if pr not in settled]


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _bad(record):
    # A line the readers would trip over counts as unreadable, as a torn one does: a start or end
    # line with no str session, a pr that is not an int, a head that is not a str, a refused list
    # that is not a list of tool and input strings, or a pid line that lock.read would refuse.
    if record.get("event") == "start":
        return not isinstance(record.get("session"), str)
    if record.get("event") == "end":
        if not isinstance(record.get("session"), str):
            return True
        if "refused" in record:
            refused = record["refused"]
            return not isinstance(refused, list) or not all(
                isinstance(item, dict)
                and isinstance(item.get("tool"), str)
                and isinstance(item.get("input"), str)
                for item in refused
            )
        return False
    if record.get("event") in ("merged", "closed", "wait") and not _is_int(record.get("pr")):
        return True
    # A park or merged line may lack head, and a park line may lack pr: a default that passes stands
    # in for the missing key.
    if record.get("event") in ("park", "merged") and not isinstance(record.get("head", ""), str):
        return True
    if record.get("event") == "park" and not _is_int(record.get("pr", 0)):
        return True
    if record.get("event") != "pid":
        return False
    pid = record.get("pid")
    started = record.get("started")
    if not isinstance(record.get("session"), str):
        return True
    if not isinstance(pid, int) or isinstance(pid, bool) or not 0 < pid < 2**31:
        return True
    if not isinstance(started, str):
        return True
    try:
        lock.stamp_time(started)
    except ValueError:
        return True
    return False


def failures(state, prefix):
    # Returns (sessions, reason): the sessions for prefix that ended as a park, in the log's order.
    records, reason = _records(state)
    if reason:
        return None, reason
    if records is None:
        return [], None
    ended = {
        record.get("session"): record.get("outcome")
        for record in records
        if record.get("event") == "end"
    }
    sessions = []
    for record in records:
        if record.get("event") != "start" or record.get("prefix") != prefix:
            continue
        outcome = ended.get(record.get("session"))
        if isinstance(outcome, str) and outcome.startswith("park:"):
            sessions.append(record.get("session"))
    return sessions, None


def open_session(state, prefix):
    # Returns (session, reason): the open session for prefix, or why the log cannot be read.
    records, reason = _records(state)
    if reason:
        return None, reason
    if records is None:
        return None, None
    # The whole log is read before anything is returned, so a bad line anywhere parks the driver.
    ended = [record.get("session") for record in records if record.get("event") == "end"]
    for record in reversed(records):
        if record.get("event") != "start" or record.get("prefix") != prefix:
            continue
        if record.get("session") not in ended:
            return record.get("session"), None
    return None, None


def live_session(state):
    # Returns (session, pid, None) for the newest session whose last pid line has no later end line
    # and whose process lives, of any prefix; (None, None, None) when none does or there is no log;
    # (None, None, reason) when the log cannot be read.
    records, reason = read(state)
    if reason:
        return None, None, reason
    # Read from the end: a session's first pid line met here is its last, and its later end lines
    # have already been met. A list, since an end line's session is not checked to be hashable.
    closed = []
    for record in reversed(records or []):
        session = record.get("session")
        if record.get("event") == "end":
            closed.append(session)
        elif record.get("event") == "pid" and session not in closed:
            if lock.lives(record["pid"], record["started"]):
                return session, record["pid"], None
            closed.append(session)
    return None, None, None


def last_session(state, prefix):
    # The newest session started for prefix, or None: also when the log cannot be read, since a
    # park's body only names it.
    try:
        records, reason = _records(state)
    except OSError:
        return None
    if reason or records is None:
        return None
    for record in reversed(records):
        if record.get("event") == "start" and record.get("prefix") == prefix:
            return record["session"]
    return None


def fixes(state, session):
    # Returns how many fix lines the session has. A log that cannot be read says nothing about how
    # many were used, so it counts as both used (plan.md, "Recovery", rule 4).
    try:
        records, reason = _records(state)
    except OSError:
        return USED_WHEN_UNREADABLE
    if reason:
        return USED_WHEN_UNREADABLE
    if records is None:
        return 0
    return sum(
        1 for record in records if record.get("event") == "fix" and record.get("session") == session
    )


def issue_cost(state, number):
    # The cost so far of the sessions whose start line carries the run's issue number (Day 7).
    # No number, no log or a log that cannot be read is $0.00; a start with no issue never matches,
    # None included, and an end line with a null or non-number cost counts 0.
    if number is None:
        return 0.0
    records, reason = _records(state)
    if reason or records is None:
        return 0.0
    sessions = {
        record.get("session")
        for record in records
        if record.get("event") == "start" and record.get("issue") == number
    }
    total = 0.0
    for record in records:
        cost = record.get("cost_usd")
        if record.get("event") != "end" or record.get("session") not in sessions:
            continue
        if isinstance(cost, bool) or not isinstance(cost, (int, float)):
            continue
        total += cost
    return total


def late_refusals(state, records):
    # The hook log's refusals the run log does not count: those of a session with a start line in
    # records, when they are later than the session's last end line, or all of them when it has none.
    # A hook line in the same second as that end line is counted by it, so only a later one is kept.
    # A missing or unreadable hook log, or a line that is not a refusal, gives none; this writes nothing.
    try:
        with open(os.path.join(state, "refusals", "hooks.jsonl"), "rb") as f:
            data = f.read()
    except OSError:
        return []
    started = {record.get("session") for record in records if record.get("event") == "start"}
    last_end = {}
    for record in records:
        if record.get("event") == "end":
            at = record.get("at")
            last_end[record.get("session")] = at if isinstance(at, str) else ""
    late = []
    for raw in data.split(b"\n"):
        try:
            line = json.loads(raw.decode("utf-8"))
        except ValueError:
            continue
        if not isinstance(line, dict) or not isinstance(line.get("at"), str):
            continue
        session = line.get("session")
        if not isinstance(session, str) or session not in started:
            continue
        if session in last_end and not line["at"] > last_end[session]:
            continue
        tool, tool_input = line.get("tool"), line.get("input")
        late.append(
            {
                "session": session,
                "tool": tool if isinstance(tool, str) else "unknown",
                "input": tool_input if isinstance(tool_input, str) else "{}",
            }
        )
    return late
