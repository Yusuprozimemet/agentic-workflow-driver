"""The guard hook: a session's PreToolUse check against the calls a session never makes.

`python hooks/guard.py <driver folder>` reads Claude Code's PreToolUse JSON on stdin. It exits 2
with one line on stderr when the call merges a pull request, pushes to main, names the driver's
folder or edits inside it, and when the call cannot be read at all. Otherwise it exits 0 and
prints nothing.

Known limit: the hook reads the command, not git's configuration or the shell's working directory.
A bare `git push` on main names no destination and passes, and a path relative to the project
(`../<driver folder>/state/halt`) is not resolved.
"""

import json
import os
import re
import shlex
import sys

MERGE = "refused by the driver: a session never merges"
PUSH = "refused by the driver: a session never pushes to main"
FOLDER = "refused by the driver: the driver's folder is not a session's"
UNREAD = "refused by the driver: the guard could not read the tool call"
NO_FOLDER = "refused by the driver: the guard was given no driver folder"

SHELL_TOOLS = ("Bash", "PowerShell")
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
MERGE_RE = re.compile(r"(?<![\w-])gh\s+pr\s+merge(?![\w-])")
SEGMENT_RE = re.compile(r"&&|\|\||;|\||\n")
PUSH_RE = re.compile(r"(?<![\w-])git\s+push(?![\w-])")


def norm(text):
    # Either slash counts: a Windows command may write the folder with forward or back slashes.
    return re.sub(r"[\\/]+", "/", text)


def folder_forms(folder):
    # Git Bash writes a drive path as /c/..., so that form names the folder too.
    drive, rest = os.path.splitdrive(folder)
    forms = [folder]
    if drive.endswith(":"):
        forms.append("/" + drive[0].lower() + rest)
    return forms


def pushes_to_main(command):
    for segment in SEGMENT_RE.split(command):
        match = PUSH_RE.search(segment)
        if match is None:
            continue
        rest = segment[match.end() :]
        try:
            tokens = shlex.split(rest, posix=True)
        except ValueError:
            tokens = rest.split()
        for token in tokens:
            if token.startswith("-"):
                continue
            token = token.removeprefix("+")
            if token == "main" or token.endswith((":main", ":refs/heads/main")):
                return True
    return False


def names_folder(folder, command):
    # On Windows the folder's case does not matter; the lookahead keeps "<folder>-old" a
    # different folder.
    flags = re.IGNORECASE if os.name == "nt" else 0
    text = norm(command)
    return any(
        re.search(re.escape(form) + r"(?![\w.-])", text, flags) for form in folder_forms(folder)
    )


def command_refusal(home, command):
    if MERGE_RE.search(command):
        return MERGE
    if pushes_to_main(command):
        return PUSH
    if names_folder(norm(os.path.abspath(home)).rstrip("/"), command):
        return FOLDER
    return None


def edit_refusal(home, tool_input):
    path = tool_input.get("file_path", tool_input.get("notebook_path"))
    if path is None or path == "":
        return None
    if not isinstance(path, str):
        return UNREAD
    # realpath and normcase make a symlink or a differently cased path name the same folder.
    target = os.path.normcase(os.path.realpath(home))
    inside = os.path.normcase(os.path.realpath(path))
    if inside == target or inside.startswith(target + os.sep):
        return FOLDER
    return None


def refusal(home, call):
    if not isinstance(call, dict):
        return UNREAD
    tool_input = call.get("tool_input")
    if not isinstance(tool_input, dict):
        return UNREAD
    tool = call.get("tool_name")
    if tool in SHELL_TOOLS:
        command = tool_input.get("command")
        if not isinstance(command, str):
            return UNREAD
        return command_refusal(home, command)
    if tool in EDIT_TOOLS:
        return edit_refusal(home, tool_input)
    return None


def main(argv, stdin):
    if len(argv) < 2 or not argv[1]:
        print(NO_FOLDER, file=sys.stderr)
        return 2
    try:
        call = json.loads(stdin)
    except ValueError:
        line = UNREAD
    else:
        line = refusal(argv[1], call)
    if line is None:
        return 0
    print(line, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv, sys.stdin.buffer.read().decode("utf-8", "replace")))
