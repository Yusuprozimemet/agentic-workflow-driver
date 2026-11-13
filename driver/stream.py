"""The session's stdout under --output-format stream-json: one JSON object per line, from the session's
start to its end. The result event, the last one, is the record of the session's cost, its session
and its refusals, so --once reads that line and skips the rest. kind names each line's kind, and
append keeps the session's events file as its lines are read (Day 11)."""

import json
import os

from driver import lock


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
