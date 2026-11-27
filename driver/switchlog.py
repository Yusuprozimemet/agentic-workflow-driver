"""The switch log, the file <state>/switches.jsonl: one JSON object per line, a record of each switch
the driver saw: on, off, halt, clear and level. scripts/driver-runs.py reads it for the count, so that
a session a halt names is not counted as crashed. The run log keeps the sessions, and this file keeps
the switches beside it. From Day 16 the driver reads its level lines, at driver.json's level 2 or 3
only, for the level in force: a lowering holds the level below the config's until a raise lifts it."""

import json
import os

from driver import runlog


def path(state):
    return os.path.join(state, "switches.jsonl")


def append(state, event, **fields):
    # A field with no value is left out. An error writing the line is not raised: a halt must still
    # happen when its line cannot be written.
    record = {
        "event": event,
        "at": runlog.stamp(),
        **{k: v for k, v in fields.items() if v is not None},
    }
    line = json.dumps(record, ensure_ascii=False) + "\n"
    try:
        os.makedirs(state, exist_ok=True)
        # Binary, so no carriage return is written on Windows; fsynced, as the run log's lines are.
        with open(path(state), "ab") as f:
            f.write(line.encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        pass


def read(state):
    # Returns (records, reason): [] when there is no switch log yet, and the reason at the first line
    # that is not a JSON object.
    try:
        with open(path(state), "rb") as f:
            lines = f.read().split(b"\n")
    except FileNotFoundError:
        return [], None
    # The empty piece after a final newline is not a line.
    if lines[-1] == b"":
        lines.pop()
    records = []
    for number, raw in enumerate(lines, start=1):
        try:
            record = json.loads(raw.decode("utf-8"))
        except ValueError:
            return None, f"{path(state)}: line {number} cannot be read"
        if not isinstance(record, dict):
            return None, f"{path(state)}: line {number} cannot be read"
        records.append(record)
    return records, None


def _is_level(value):
    # True equals 1 in Python, so a bool is refused by type first.
    return isinstance(value, int) and not isinstance(value, bool) and value in (1, 2, 3)


def in_force(state, level):
    # Returns (level in force, newest level line or None, reason): driver.json's level, or a lower one
    # a lowering line holds it at; the reason is read's, and then the level is not known.
    # Level 1 has no lower level, so nothing is read and a bad switch log changes nothing (C16.6).
    if level == 1:
        return level, None, None
    records, reason = read(state)
    if reason:
        return None, None, reason
    # A level line whose level is not the int 1, 2 or 3 is passed over, as if it were not there.
    newest = next(
        (r for r in reversed(records) if r.get("event") == "level" and _is_level(r.get("level"))),
        None,
    )
    if newest is None:
        return level, None, None
    return min(level, newest["level"]), newest, None


def lowered(level, in_force, newest):
    # The line on and status print when a lowering holds the level below driver.json's, or None. The
    # level it was lowered from is the line's own, not driver.json's.
    if newest is None or in_force >= level:
        return None
    # A raise line has no "from": a level in force below driver.json's after one prints no lowering.
    if "from" not in newest or not ("escapes" in newest or "evidence" in newest):
        return None
    m = newest["from"]
    if "escapes" in newest:
        return f"level: {in_force}, lowered from {m} on an escape: {', '.join(newest['escapes'])}; run-steps.py raise lifts it"
    if "evidence" in newest:
        return f"level: {in_force}, lowered from {m} on a failed evidence run of {newest['evidence'][:7]}; run-steps.py raise lifts it"
    return None
