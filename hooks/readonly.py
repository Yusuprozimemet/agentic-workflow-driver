"""The read-only hook: the reviewer's PreToolUse check, which passes the reads and refuses any other
git or gh call in a shell tool.

`python hooks/readonly.py <refusals folder>` reads Claude Code's PreToolUse JSON on stdin. It exits 2
with one line on stderr when a Bash or PowerShell call runs git or gh for anything but a read, and
when the call cannot be read at all. Otherwise it exits 0 and prints nothing. Given a refusals
folder, each refusal is also appended to its hooks.jsonl.

Known limit: the hook reads the command, not what a program does. `python -c` that runs git, a
script, `$(...)` or backticks, and `bash -c "git commit"` pass. The reviewer's settings keep the
guard hook beside it.
"""

import json
import os
import re
import shlex
import sys

import hook_log

ONLY_READS = "refused by the driver: the reviewer only reads"
UNREAD = "refused by the driver: the read-only hook could not read the tool call"

SHELL_TOOLS = ("Bash", "PowerShell")
# guard.py's, plus a single &; && must stay first so that it is not split into two.
SEGMENT_RE = re.compile(r"&&|\|\||;|\||&|\n")
PREFIX_WORDS = ("&", "(", "env")
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
GIT_READS = {
    "status",
    "diff",
    "log",
    "show",
    "rev-parse",
    "ls-files",
    "ls-tree",
    "cat-file",
    "for-each-ref",
    "show-ref",
    "merge-base",
    "rev-list",
    "blame",
    "grep",
    "describe",
}
GH_READS = {
    ("pr", "view"),
    ("pr", "diff"),
    ("pr", "checks"),
    ("pr", "list"),
    ("pr", "status"),
    ("issue", "view"),
    ("issue", "list"),
    ("run", "view"),
    ("run", "list"),
    ("repo", "view"),
}
FIELD_FLAGS = ("-f", "-F", "--field", "--raw-field", "--input")
FIELD_PREFIXES = ("-f", "-F", "--field=", "--raw-field=", "--input=")


def words(segment):
    text = segment.lstrip(" \t\r\n(")
    try:
        tokens = shlex.split(text)
    except ValueError:
        tokens = text.split()
    while tokens and (tokens[0] in PREFIX_WORDS or ASSIGN_RE.match(tokens[0])):
        tokens.pop(0)
    return tokens


def program(word):
    name = os.path.basename(word.replace("\\", "/")).lower()
    return name.removesuffix(".exe")


def git_reads(args):
    args = list(args)
    while args:
        if args[0] == "--no-pager":
            args.pop(0)
        elif args[0] in ("-C", "-c"):
            del args[:2]
        else:
            break
    if not args:
        return True
    return args[0] in GIT_READS


def api_writes(args):
    for index, word in enumerate(args):
        following = args[index + 1] if index + 1 < len(args) else ""
        if word in ("-X", "--method") and following.upper() != "GET":
            return True
        if word.startswith("-X") and len(word) > 2 and word[2:].upper() != "GET":
            return True
        if word.startswith("--method=") and word[len("--method=") :].upper() != "GET":
            return True
        if word in FIELD_FLAGS or word.startswith(FIELD_PREFIXES):
            return True
    return False


def gh_reads(args):
    if tuple(args[:2]) in GH_READS:
        return True
    if args[:1] == ["api"]:
        return not api_writes(args[1:])
    return False


def command_refusal(command):
    for segment in SEGMENT_RE.split(command):
        args = words(segment)
        if not args:
            continue
        name = program(args[0])
        if (name == "git" and not git_reads(args[1:])) or (name == "gh" and not gh_reads(args[1:])):
            return ONLY_READS
    return None


def refusal(call):
    if not isinstance(call, dict):
        return UNREAD
    if call.get("tool_name") not in SHELL_TOOLS:
        return None
    tool_input = call.get("tool_input")
    if not isinstance(tool_input, dict):
        return UNREAD
    command = tool_input.get("command")
    if not isinstance(command, str):
        return UNREAD
    return command_refusal(command)


def main(argv, stdin):
    try:
        call = json.loads(stdin)
    except ValueError:
        call = None
        line = UNREAD
    else:
        line = refusal(call)
    if line is None:
        return 0
    print(line, file=sys.stderr)
    if len(argv) > 1 and argv[1]:
        hook_log.log(argv[1], "readonly", call, line)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv, sys.stdin.buffer.read().decode("utf-8", "replace")))
