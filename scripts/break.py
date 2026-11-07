"""Break the code on purpose once, run the check, put the code back, and print the `broken:` line.

    python scripts/break.py --file <path> --find <text> --replace <text> --what "<what was broken>" \
        [--cwd <dir>] [--expect-stdout <regex>] [--] <command> [args...]

for example `... --what "the guard removed" python -m unittest tests.test_cli`: everything from the
command on is the command's, options included.

The break is one exact replacement in one file: --find must occur exactly once. The file's bytes are
kept in memory and written back as they were, line endings included, whatever the command does; git
is never used to revert, so unstaged work elsewhere is untouched. The command runs as an argument
list, with no shell: on Windows, `mvnw` runs as `mvnw.cmd`. A Maven command must clean, or an
incremental build can skip the broken source and pass. One break at a time: a second run while one
is active refuses; a break run by the check of another takes a lock of its own. --file is taken
from where break.py runs; with --cwd it must sit in the tree the check runs in (--cwd's git work
tree, or --cwd outside git): a break in one tree with the check in another is refused, not run.

It runs the check first without the break, and refuses if it does not pass. It exits 0 only when
the check then failed with the break in and the file is back as it was, and prints
the record for the PR (specs/README.md): `broken: <what> → <what the check reported>`, and before it
the break's entry for the close's break manifest, `manifest: {...}`. A check judged
by what it prints, not its exit code (`grep -c` exits 1 at a count of 0), takes --expect-stdout: it
failed when the regex no longer matches its stdout. break.py checks that the regex matches without
the break itself. A command that started but did not run the check (on
Windows, `bash` can be WSL's: "execvpe(/bin/bash) failed") is refused, not recorded. <what> holds
no arrow: spec-drift.py reads the line up to its first one. A temporary directory in the report is
written <tmp>, so no local path, a user name in it, reaches the PR.

Each rule here is a defect the paper's record holds (docs/paper, Appendix F): an incremental compile
that skipped a break (D23-027), breaks run through cmd.exe into WSL's bash that never started Maven
(D26-056), `git checkout` over unstaged work (D21-007, D25-050), two breaks run together (D25-043).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

# The lines a failed check reports, in order of preference: a JUnit or pytest summary, then an
# assertion, then a failure line. The last match of the first pattern found is the report.
REPORTED = [re.compile(p) for p in (
    r"Tests run: \d+, Failures: \d+, Errors: \d+.*",
    r"Tests(?::|\s+)\s*\d+ failed.*",
    r"\d+ failed.*",
    r"(?:AssertionError|AssertionFailedError|ComparisonFailure)[:\s].*",
    r"(?:FAIL|FAILED|ERROR|BUILD FAILURE)\b.*",
)]
# A command that started but never ran the check: WSL's bash with no Linux shell to start, a shell
# that could not find or run the program.
NOT_RUN = re.compile(r"execvpe\(.*?\) failed|command not found|is not recognized as an internal or external command")
LOCK = ".break-active"
ARROW = re.compile(r"→|->")
# tempfile's own names (tmp and 8 characters), the whole path up to them; unittest may have cut its start.
TEMP_NAME = re.compile(r"[^\s'\"()\[\]]*?[\\/]+tmp[a-z0-9_]{8}(?![a-z0-9_])")


def untemp(line):
    """The line with each temporary directory written <tmp>: the local one, as a path or a repr, and
    tempfile's own names under it. The directory only as a whole name: /tmp is also the start of
    /tmp2ewplof6."""
    line = TEMP_NAME.sub("<tmp>", line)
    for form in {tempfile.gettempdir(), os.path.realpath(tempfile.gettempdir())}:
        for written in (form, form.replace("\\", "\\\\"), form.replace("\\", "/")):
            line = re.sub(re.escape(written) + r"(?![\w.~-])", "<tmp>", line)
    return line


def reported(output):
    """The line a failed check's output is summed up by, or its last non-empty line. git's warnings
    ("LF will be replaced by CRLF") are not the check's report."""
    lines = [l.strip() for l in output.splitlines() if l.strip() and not l.startswith("warning: ")]
    for pattern in REPORTED:
        hits = [m.group(0) for l in lines if (m := pattern.search(l))]
        if hits:
            return hits[-1]
    return lines[-1] if lines else "no output"


def not_run(returncode, output):
    """The line saying the check never ran though its command started, or None. A shell's 126 and
    127 are a program it could not run or find."""
    hit = NOT_RUN.search(output)
    if hit:
        return next(l.strip() for l in output.splitlines() if hit.group(0) in l)
    return f"exit {returncode}: the shell could not run the program" if returncode in (126, 127) else None


def caught(returncode, stdout, expect=None):
    """Whether the check saw the break: it failed, or, with --expect-stdout, its stdout no longer
    matches the regex, whatever its exit code."""
    if expect is not None:
        return re.search(expect, stdout, re.M) is None
    return returncode != 0


def argv_for(command, cwd):
    """The command as it runs here: a relative path to the program taken from cwd (Windows looks
    for it from the caller's directory), and mvnw as mvnw.cmd on Windows, since a sh script needs a
    shell."""
    head = command[0]
    if os.sep in head or "/" in head:
        head = os.path.abspath(os.path.join(cwd, head))
    if os.name == "nt" and os.path.basename(head) == "mvnw":
        head += ".cmd"
    return [head, *command[1:]]


def tree(cwd):
    """The tree the check runs in: the git work tree that holds cwd, or cwd itself outside git."""
    top = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return os.path.realpath(top.stdout.strip() if top.returncode == 0 else cwd)


def in_tree(file, cwd):
    """Whether file sits in the tree the check runs in. --file is taken from break.py's own working
    directory and --cwd's check from --cwd: run from one tree with --cwd in another, the break went
    into the first while the check ran on the second, and passed."""
    root, path = tree(cwd), os.path.realpath(file)
    try:
        return os.path.commonpath([os.path.normcase(root), os.path.normcase(path)]) == os.path.normcase(root)
    except ValueError:  # another drive
        return False


def manifest(a):
    """The line before the broken: line: the break's entry for specs/breaks/day-NN.json
    (specs/README.md), to copy into the track PR beside it, or why there is none. The replay runs the
    command from the repository root, so the entry holds only a break run from there."""
    try:
        file = os.path.relpath(a.file)
    except ValueError:  # another drive
        file = os.pardir
    if os.path.abspath(a.cwd) != os.getcwd() or file.startswith(os.pardir):
        return "manifest: none → run break.py from the repository root, without --cwd, for an entry the replay can run"
    entry = {"what": a.what, "file": file.replace(os.sep, "/"), "find": a.find, "replace": a.replace,
             "command": a.command}
    if a.expect_stdout is not None:
        entry["expect_stdout"] = a.expect_stdout
    return "manifest: " + json.dumps(entry, ensure_ascii=False)


def refuse(message):
    print(f"break.py: {message}", file=sys.stderr)
    return 2


def main(args=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--file", required=True)
    p.add_argument("--find", required=True)
    p.add_argument("--replace", required=True)
    p.add_argument("--what", required=True, help="what was broken, for the broken: line")
    p.add_argument("--cwd", help="where the check runs; --file must then sit in its tree")
    p.add_argument("--expect-stdout", metavar="REGEX",
                   help="the check's stdout without the break; the break is caught when it no longer matches")
    p.add_argument("command", nargs=argparse.REMAINDER, help="the check, with its options; a leading -- is dropped")
    a = p.parse_args(args)
    a.command = a.command[1:] if a.command[:1] == ["--"] else a.command
    elsewhere, a.cwd = a.cwd is not None, a.cwd or "."
    if not a.command:
        p.error("the command to run is required")
    sys.stdout.reconfigure(encoding="utf-8")  # the arrow; a Windows console's default is cp1252

    if ARROW.search(a.what):
        return refuse("--what holds an arrow: spec-drift.py would end <what> there; write it without one")
    if os.path.basename(a.command[0]) in ("mvnw", "mvn") and "clean" not in a.command:
        return refuse("a Maven check must clean, or the broken source may not be recompiled")
    try:
        re.compile(a.expect_stdout or "")
    except re.error as e:
        return refuse(f"--expect-stdout is not a regex: {e}")
    if elsewhere and not in_tree(a.file, a.cwd):
        return refuse(f"--file {a.file} is outside the tree --cwd {a.cwd} runs the check in ({tree(a.cwd)}): "
                      "the break would not be in the code the check runs; name the file in that tree")
    with open(a.file, "rb") as f:
        original = f.read()
    find, replace = a.find.encode(), a.replace.encode()
    if original.count(find) != 1:
        return refuse(f"--find occurs {original.count(find)} times in {a.file}, want exactly once")
    # A break's check that runs break.py itself (a break of break.py, or of evidence.py) takes the
    # lock its parent names, in a directory of its own: one under the same root would be refused.
    lock = os.environ.get("BREAK_LOCK") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", LOCK)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return refuse(f"another break is active ({os.path.normpath(lock)}); finish it, or delete the file")
    nested = tempfile.mkdtemp()
    env = dict(os.environ, BREAK_LOCK=os.path.join(nested, LOCK))
    try:
        os.write(fd, a.file.encode())
        os.close(fd)
        try:
            baseline = subprocess.run(argv_for(a.command, a.cwd), cwd=a.cwd, capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", env=env)
        except FileNotFoundError as e:
            return refuse(f"the command did not start: {e}")
        output = baseline.stdout + baseline.stderr
        said = not_run(baseline.returncode, output)
        if said:
            return refuse(f"the command started but the check did not run, so nothing is recorded: {untemp(said)}")
        if caught(baseline.returncode, baseline.stdout, a.expect_stdout):
            return refuse(f"the check fails without the break, so a failure with it proves nothing: {untemp(reported(output))}")
        with open(a.file, "wb") as f:
            f.write(original.replace(find, replace))
        try:
            run = subprocess.run(argv_for(a.command, a.cwd), cwd=a.cwd, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", env=env)
        except FileNotFoundError as e:
            return refuse(f"the command did not start: {e}")
    finally:
        with open(a.file, "wb") as f:
            f.write(original)
        os.remove(lock)
        shutil.rmtree(nested, ignore_errors=True)
    with open(a.file, "rb") as f:
        if f.read() != original:
            return refuse(f"{a.file} is not back as it was: restore it by hand")
    output = run.stdout + run.stderr
    said = not_run(run.returncode, output)
    if said:
        return refuse(f"the command started but the check did not run, so nothing is recorded: {untemp(said)}")
    if not caught(run.returncode, run.stdout, a.expect_stdout):
        print(f"The check passed with the break in: it cannot see this break.\n  last line: {reported(output)}")
        return 1
    print(manifest(a))
    print(f"broken: {a.what} → {untemp(reported(output))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
