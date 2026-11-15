"""A fake claude that also answers the reviewer: a session with --agent reviewer gets the next of the
case's replies, in order, one per reviewer call, as a result line with its cost and session id. It
answers whether the reviewer's session ends with a verdict, a change to the project, or an error, which
is what the driver's review reads. Every other call is tests/test_once.py's fake claude."""

import json
import os
import sys

from tests.test_once import FAKE, claude_program
from tests.test_preflight import HELP

# The branch goes in before the step's own `do`, so that a reviewer call never runs it.
ANCHOR = 'if spec["do"]:\n'
REVIEWER = """def is_reviewer(args):
    return any(args[i : i + 2] == ["--agent", "reviewer"] for i in range(len(args)))


if is_reviewer(args):
    # calls.jsonl already holds this call's record, so n is at least 1: the n-th reviewer call's reply.
    lines = (folder / "calls.jsonl").read_bytes().splitlines()
    n = sum(is_reviewer(json.loads(line)["args"]) for line in lines)
    reply = spec["replies"][min(n, len(spec["replies"])) - 1]
    if reply.get("do"):
        exec(reply["do"])
    session = args[args.index("--session-id") + 1]
    result = {
        "type": "result",
        "is_error": reply.get("is_error", False),
        "result": reply["text"],
        "total_cost_usd": reply.get("cost", 0.25),
        "session_id": session,
    }
    print(json.dumps(result))
    sys.exit(0)
"""


def fake_review(folder, replies, help=HELP, do=""):
    spec = {
        "version": "2.1.170 (Claude Code)",
        "help": help,
        "do": do,
        "result": {"type": "result", "is_error": False, "result": "done"},
        "replies": replies,
    }
    # Files are written as bytes: on Windows, text mode would add a carriage return to each line.
    (folder / "fake.json").write_bytes(json.dumps(spec).encode("utf-8"))
    assert FAKE.count(ANCHOR) == 1, (
        "FAKE no longer has the one line the reviewer branch goes before"
    )
    text = FAKE.replace(ANCHOR, REVIEWER + ANCHOR)
    (folder / "fake.py").write_bytes(text.encode("utf-8"))
    program = claude_program(folder)
    if os.name == "nt":
        program.write_bytes(f'@"{sys.executable}" "%~dp0fake.py" %*\r\n'.encode())
    else:
        program.write_bytes(f"#!{sys.executable}\n{text}".encode())
        program.chmod(0o755)
    return str(program)
