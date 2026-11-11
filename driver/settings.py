"""The settings file the driver writes for a session: <state>/settings.json, with the halt hook and
the guard hook as PreToolUse commands. Each command names sys.executable and a script by absolute
path, each quoted, so a space in a path does not split it. Both hooks log their refusals to
<state>/refusals/hooks.jsonl. write() rewrites the file afresh. With inside=True it writes
<state>/container-settings.json instead, whose commands name the paths the container mounts the
hooks at, so the session in the container runs them there."""

import json
import os
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "hooks"
GUARDED = "Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit"


def entry(matcher, script, *arguments):
    quoted = " ".join(f'"{argument}"' for argument in arguments)
    command = f'"{sys.executable}" "{HOOKS / script}" {quoted}'
    return {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}


def write(state, home, inside=False):
    state = os.path.abspath(state)
    os.makedirs(state, exist_ok=True)
    refusals = os.path.join(state, "refusals")
    if inside:
        # Typed out as POSIX paths: inside the container os.path would build the host's paths.
        halt = 'python "/driver/hooks/halt.py" "/state/halt" "/state/refusals"'
        guard = 'python "/driver/hooks/guard.py" "/driver" "/state/refusals"'
        hooks = [
            {"matcher": "*", "hooks": [{"type": "command", "command": halt}]},
            {"matcher": GUARDED, "hooks": [{"type": "command", "command": guard}]},
        ]
        path = os.path.join(state, "container-settings.json")
    else:
        hooks = [
            entry("*", "halt.py", os.path.join(state, "halt"), refusals),
            entry(GUARDED, "guard.py", os.path.abspath(home), refusals),
        ]
        path = os.path.join(state, "settings.json")
    body = {"hooks": {"PreToolUse": hooks}}
    with open(path, "wb") as f:
        f.write(json.dumps(body, indent=2).encode("utf-8"))
    return path
