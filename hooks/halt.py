"""The halt hook: a session's PreToolUse check that refuses every call while the driver is halted.

`python hooks/halt.py <halt file> [<refusals folder>]` exits 2 with one line on stderr while the halt
file exists, and exits 0 with nothing printed when it does not. It reads no environment variable. The
session's folder does not matter, only the path it was given. Given a refusals folder, it logs each
refusal to its hooks.jsonl, with the fields of the call it reads from stdin, for at most 2 seconds
and only then; what it decides depends on the halt file alone.
"""

import json
import os
import sys
import threading

import hook_log


def read_stdin():
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return b""
    except (OSError, ValueError, AttributeError):
        return b""
    chunks = []

    def pump():
        # os.read, not sys.stdin.buffer: a daemon thread holding the buffered reader's lock
        # makes interpreter shutdown abort.
        while True:
            try:
                chunk = os.read(0, 65536)
            except OSError:
                return
            if not chunk:
                return
            chunks.append(chunk)

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    reader.join(timeout=2)
    return b"".join(chunks)


def read_call():
    try:
        return json.loads(read_stdin().decode("utf-8", "replace"))
    except ValueError:
        return None


def main(argv):
    if len(argv) < 2 or not argv[1]:
        print("halted: the halt hook was given no halt file", file=sys.stderr)
        return 2
    if os.path.exists(argv[1]):
        line = f"halted: {argv[1]} exists; run-steps.py clear removes it"
        print(line, file=sys.stderr)
        if len(argv) > 2 and argv[2]:
            hook_log.log(argv[2], "halt", read_call(), line)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
