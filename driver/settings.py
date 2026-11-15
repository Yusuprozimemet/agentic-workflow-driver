"""The settings file the driver writes for a session: <state>/settings.json, with the halt hook and
the guard hook as PreToolUse commands. Each command names sys.executable and a script by absolute
path, each quoted, so a space in a path does not split it. Both hooks log their refusals to
<state>/refusals/hooks.jsonl. write() rewrites the file afresh. With inside=True it writes
<state>/container-settings.json instead, whose commands name the paths the container mounts the
hooks at, so the session in the container runs them there. review() writes
<state>/review-settings.json (inside: review-container-settings.json), the same two hooks then
hooks/readonly.py on Bash and PowerShell, for the reviewer's session."""

import json
import os
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "hooks"
GUARDED = "Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit"
READONLY = "Bash|PowerShell"


def entry(matcher, script, *arguments):
    quoted = " ".join(f'"{argument}"' for argument in arguments)
    command = f'"{sys.executable}" "{HOOKS / script}" {quoted}'
    return {"matcher": matcher, "hooks": [{"type": "command", "command": command}]}


def hooks(state, home, inside):
    # The halt hook and the guard hook, as a session's settings name them; state is absolute.
    refusals = os.path.join(state, "refusals")
    if inside:
        # Typed out as POSIX paths: inside the container os.path would build the host's paths.
        halt = 'python "/driver/hooks/halt.py" "/state/halt" "/state/refusals"'
        guard = 'python "/driver/hooks/guard.py" "/driver" "/state/refusals"'
        return [
            {"matcher": "*", "hooks": [{"type": "command", "command": halt}]},
            {"matcher": GUARDED, "hooks": [{"type": "command", "command": guard}]},
        ]
    return [
        entry("*", "halt.py", os.path.join(state, "halt"), refusals),
        entry(GUARDED, "guard.py", os.path.abspath(home), refusals),
    ]


def dump(path, hooks_list):
    body = {"hooks": {"PreToolUse": hooks_list}}
    with open(path, "wb") as f:
        f.write(json.dumps(body, indent=2).encode("utf-8"))
    return path


def write(state, home, inside=False):
    state = os.path.abspath(state)
    os.makedirs(state, exist_ok=True)
    if inside:
        path = os.path.join(state, "container-settings.json")
    else:
        path = os.path.join(state, "settings.json")
    return dump(path, hooks(state, home, inside))


def review(state, home, inside=False):
    # The reviewer's settings: the step's two hooks, then the read-only hook on Bash and PowerShell.
    state = os.path.abspath(state)
    os.makedirs(state, exist_ok=True)
    listed = hooks(state, home, inside)
    if inside:
        readonly = 'python "/driver/hooks/readonly.py" "/state/refusals"'
        listed.append({"matcher": READONLY, "hooks": [{"type": "command", "command": readonly}]})
        path = os.path.join(state, "review-container-settings.json")
    else:
        listed.append(entry(READONLY, "readonly.py", os.path.join(state, "refusals")))
        path = os.path.join(state, "review-settings.json")
    return dump(path, listed)
