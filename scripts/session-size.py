"""Warn when a session's context passes 150k tokens, and again at each further 50k; never block.

    python scripts/session-size.py     # PostToolUse on every tool: prints the warning, if one is due

The hook in the project settings (.claude/settings.json) runs it after every tool call. It reads the
session's transcript (the hook's `transcript_path`) from the end for the last reply of the main
session, and takes its context as that reply's input tokens, cache writes and cache reads. Past
150,000, it warns the maintainer (`systemMessage`) and the session (`additionalContext`) once, then
once more at 200k, 250k and so on: every later reply re-reads the whole context, and on Days 9 to 12
the tokens read again for each one written rose from 104 to 122 (#212, S20). It refuses nothing.

Which step a session was last warned at is kept in .claude/state/session-size.json (gitignored), by
session id. A transcript it cannot read, or one with no reply yet, prints nothing.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, ".claude", "state", "session-size.json")
FIRST, STEP = 150_000, 50_000
TAIL = 1 << 20  # the last reply is near the end; a long transcript is not read whole


def context(transcript):
    """The main session's context at its last reply, in tokens, or None."""
    try:
        with open(transcript, "rb") as f:
            f.seek(max(0, os.path.getsize(transcript) - TAIL))
            lines = f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        usage = (entry.get("message") or {}).get("usage") if isinstance(entry, dict) else None
        if entry.get("type") == "assistant" and usage and not entry.get("isSidechain"):
            return sum(usage.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    return None


def step(tokens):
    """0 below 150k, 1 from 150k, 2 from 200k, ..."""
    return 0 if tokens < FIRST else 1 + (tokens - FIRST) // STEP


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def handle(data, state_path=STATE):
    """The hook's reply for one tool call, or None."""
    tokens = context(data.get("transcript_path") or "")
    if tokens is None or not step(tokens):
        return None
    warned = load(state_path)
    session = str(data.get("session_id", ""))
    if warned.get(session, 0) >= step(tokens):
        return None
    warned[session] = step(tokens)
    try:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(warned, f)
    except OSError:
        pass
    text = (f"This session's context is {tokens // 1000}k tokens, past {FIRST // 1000}k: every reply re-reads it. "
            "At the next point where the work can be handed on, suggest /compact or a new session (#212, S20).")
    return {"systemMessage": text, "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    out = handle(data) if isinstance(data, dict) else None
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
