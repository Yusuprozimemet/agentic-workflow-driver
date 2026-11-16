"""The switch log, the file <state>/switches.jsonl: one JSON object per line, a record of each switch
the driver saw: on, off, halt and clear. scripts/driver-runs.py reads it for the count, so that a
session a halt names is not counted as crashed. The driver never reads it to decide anything: the run
log keeps the sessions, and this file keeps the switches beside it."""

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
