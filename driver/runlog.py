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


def start(state, step, prefix, session, claude):
    append(
        state,
        {
            "event": "start",
            "at": stamp(),
            "step": step,
            "prefix": prefix,
            "session": session,
            "claude": claude,
        },
    )


def end(state, session, outcome, cost_usd, denials):
    append(
        state,
        {
            "event": "end",
            "at": stamp(),
            "session": session,
            "outcome": outcome,
            "cost_usd": cost_usd,
            "denials": denials,
        },
    )


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


def _bad(record):
    # A line the readers would trip over counts as unreadable, as a torn one does: a start line
    # with no session, or a pid line that lock.read would refuse as a lock.
    if record.get("event") == "start":
        return not isinstance(record.get("session"), str)
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
    try:
        records, reason = _records(state)
    except OSError as error:
        return None, None, f"the run log cannot be read: {error.strerror}"
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
