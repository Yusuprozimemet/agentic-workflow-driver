"""The session's stdout under --output-format stream-json: one JSON object per line, from the session's
start to its end. The result event, the last one, is the record of the session's cost, its session
and its refusals, so --once reads that line and skips the rest."""

import json


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
