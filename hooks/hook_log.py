"""The refusal log the hooks share: one JSON line per refusal, appended to <folder>/hooks.jsonl.

The hooks import nothing from driver/, so the UTC format of `at` is written out here; it is the run
log's format. A write that fails is dropped, and the hook still refuses.
"""

import json
import os
import time


def string_field(call, key):
    value = call.get(key) if isinstance(call, dict) else None
    return value if isinstance(value, str) else None


def log(folder, hook, call, line):
    tool_input = None
    if isinstance(call, dict) and "tool_input" in call:
        tool_input = json.dumps(call["tool_input"])[:200]
    record = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session": string_field(call, "session_id"),
        "hook": hook,
        "tool": string_field(call, "tool_name"),
        "input": tool_input,
        "line": line,
    }
    try:
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "hooks.jsonl"), "ab") as f:
            f.write(json.dumps(record).encode("utf-8") + b"\n")
    except OSError:
        pass
