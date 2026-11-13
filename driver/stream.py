"""The session's stdout under --output-format stream-json: one JSON object per line, from the session's
start to its end. The result event, the last one, is the record of the session's cost, its session
and its refusals, so --once reads that line and skips the rest. kind names each line's kind, and
append keeps the session's events file as its lines are read (Day 11)."""

import json
import os
import tempfile

from driver import lock, runlog


def result(text):
    # Bytes are decoded as UTF-8; a byte that is not UTF-8 is replaced, and its line is then skipped.
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    found = None
    for line in text.splitlines():
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("type") == "result":
            found = data
    return found


def decoded(line):
    # Bytes are decoded as UTF-8; a byte that is not UTF-8 is replaced, as in result.
    if isinstance(line, bytes):
        return line.decode("utf-8", errors="replace")
    return line


def parsed(line):
    # The line as a JSON object with a string type, or None: a partial line, a list or no type is none.
    try:
        data = json.loads(decoded(line))
    except ValueError:
        return None
    if isinstance(data, dict) and isinstance(data.get("type"), str):
        return data
    return None


def content(data):
    # The items of an assistant message's content; a message or content of the wrong type has none.
    message = data.get("message")
    items = message.get("content") if isinstance(message, dict) else None
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def assistant_kind(data):
    items = content(data)
    for item in items:
        if item.get("type") == "tool_use":
            name = item.get("name")
            return f"tool {name}" if isinstance(name, str) else "tool"
    if any(item.get("type") == "text" for item in items):
        return "reply"
    return "assistant"


def kind(line):
    # The kind of one line of the session's stdout, as the events file names it.
    data = parsed(line)
    if data is None:
        return "unparsed"
    if data["type"] == "system":
        subtype = data.get("subtype")
        return f"system {subtype}" if isinstance(subtype, str) else "system"
    if data["type"] == "assistant":
        return assistant_kind(data)
    if data["type"] == "user":
        return "tool result"
    return data["type"]


def count(usage, key):
    # A token count that is missing or not an integer counts as 0.
    value = usage.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def append(state, session, line):
    # Appends one line of the session's stdout to its events file, with the time it was read. A blank
    # line writes nothing. An assistant message also keeps its id and its tokens, so the tokens so far
    # can be counted from the file.
    text = decoded(line)
    if not text.strip():
        return
    event = {"at": lock.now().strftime(lock.STAMP), "kind": kind(text)}
    data = parsed(text)
    if data is not None and data["type"] == "assistant":
        message = data.get("message")
        message = message if isinstance(message, dict) else {}
        usage = message.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        event["message"] = message.get("id")
        event["in"] = sum(
            count(usage, key)
            for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
        )
        event["out"] = count(usage, "output_tokens")
    folder = os.path.join(state, "sessions")
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, f"{session}.events.jsonl"), "ab") as events:
        events.write((json.dumps(event) + "\n").encode("utf-8"))


def last_event(state, session):
    # The time of the session's newest event, or None when its events file is missing, empty, or ends in a
    # line that is not a JSON object with a time. The file is read as bytes, as append writes it.
    try:
        with open(os.path.join(state, "sessions", f"{session}.events.jsonl"), "rb") as events:
            lines = [line for line in events.read().split(b"\n") if line.strip()]
    except OSError:
        return None
    if not lines:
        return None
    try:
        data = json.loads(decoded(lines[-1]))
    except ValueError:
        return None
    return data.get("at") if isinstance(data, dict) else None


def started(state, session):
    # The time of the session's start line in the run log, or None when there is none or the log cannot be read.
    records, reason = runlog.read(state)
    if reason or records is None:
        return None
    for record in records:
        if record.get("event") == "start" and record.get("session") == session:
            return record.get("at")
    return None


def comment_state(state, session):
    # The heartbeat comment's id and whether its stale comment was made, from the session's comment file. It is
    # a file, not a variable of run_session, because a resumed session runs run_session again and must edit the
    # same comment. A missing, unreadable or non-object file is no comment yet.
    try:
        with open(os.path.join(state, "sessions", f"{session}.comment.json"), "rb") as comment:
            data = json.loads(comment.read().decode("utf-8"))
    except (OSError, ValueError):
        return None, False
    if not isinstance(data, dict):
        return None, False
    comment_id = data.get("id")
    if isinstance(comment_id, bool) or not isinstance(comment_id, int):
        comment_id = None
    return comment_id, data.get("stale") is True


def keep_comment(state, session, comment_id, stale):
    # Written as bytes, as comment_state reads it. A file that cannot be written is skipped: the next poll
    # finds the comment again, or makes it again.
    path = os.path.join(state, "sessions", f"{session}.comment.json")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as comment:
            comment.write(json.dumps({"id": comment_id, "stale": stale}).encode("utf-8"))
    except OSError:
        pass


def beat(state, session, step, begun):
    # Writes heartbeat.json beside the run's files, so that a reader sees the session's last event and the
    # time of this poll, even while the session is quiet. The file is written under a temporary name and
    # moved over the old one, so a reader never sees half of it. An OSError, a Windows reader holding the
    # file included, skips this beat; the temporary file is removed, and heartbeat.json is never removed.
    data = {
        "session": session,
        "step": step,
        "started": begun,
        "poll": lock.now().strftime(lock.STAMP),
        "last_event": last_event(state, session),
    }
    temp = None
    try:
        handle, temp = tempfile.mkstemp(dir=state, prefix="heartbeat.", suffix=".tmp")
        with os.fdopen(handle, "wb") as beating:
            beating.write((json.dumps(data) + "\n").encode("utf-8"))
        os.replace(temp, os.path.join(state, "heartbeat.json"))
    except OSError:
        if temp is not None:
            try:
                os.remove(temp)
            except OSError:
                pass
