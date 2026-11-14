"""Break the code on purpose once, run the check, put the code back, and print the `broken:` line.

    python scripts/break.py --file <path> --find <text> --replace <text> --what "<what was broken>" \
        [--cwd <dir>] [--expect-stdout <regex>] [--replay] [--] <command> [args...]

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
the break itself, and refuses one that matches any output: `^$` under re.M matches the empty end
of every stdout that ends in a newline, so no break could be caught (D11.21); for "prints
nothing", write `\\A\\Z`. A command that started but did not run the check (on
Windows, `bash` can be WSL's: "execvpe(/bin/bash) failed") is refused, not recorded. <what> holds
no arrow: spec-drift.py reads the line up to its first one. A temporary directory in the report is
written <tmp>, so no local path, a user name in it, reaches the PR.

It runs the check twice with the break in, and refuses a report that differs between the two runs, or
a check that failed in one and passed in the other. It refuses a report that holds a pid, a uuid, a
commit hash or an absolute path: the close replays the line on another machine, and 12 of this
project's 23 recurring defects up to Day 7 were such reports (D03.17 to D07.40). --replay, which
evidence.py passes, runs the check once and leaves the comparison with the recorded line to the caller.

--record writes the entry into the break manifest itself, so no one retypes it: the manifest's keys,
"report" (the report of the broken: line) and "blob" (`git hash-object` of the file before the
break: the code it ran on, which a commit's own hash cannot name before the commit holds the
record). The manifest is specs/breaks/day-NN.json on a day-NN/ branch and specs/breaks/<slug>.json
on change/<slug>; on another branch, name it: --record <path>. An entry with the same "what" is
replaced in place, so a re-run re-records; the others are kept. A break that cannot give an entry
(--cwd, a file outside the tree) is refused before anything changes, as is --record with --replay.
Break-bookkeeping defects were 33 of Days 1-11's 73 process defects, most of them a copy by hand.

A later PR whose code an earlier Day's break no longer fits (track-breaks.py: "no longer applies")
re-records it or retires it (specs/README.md, "Evidence at the close"). A re-record is --record into
that Day's manifest, under the same --what and command: a closed Day's replay runs the entry at the
Day's close, so a find that does not occur once there as well is refused. When no find fits both,

    python scripts/break.py --retire specs/breaks/day-NN.json --what "<what>" [--at <commit>]

pins the entry with "at" where its find still occurs once, by default where HEAD left main, and
runs nothing: the replay runs it there, and track-breaks reports it pinned. And when CI's Linux
replay words a recorded report otherwise, `--take-reports <file>` writes the reports it saved
(track-breaks.py --reports) into the record: Linux's report is the one the close replays.

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


# What another run or another machine prints differently, looked for in the report after untemp().
UNSTABLE = [(name, re.compile(p)) for name, p in (
    ("a uuid", r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"),
    ("a pid", r"(?i)\b(?:pid|process id)\b\W{0,3}\d+"),
    ("a commit hash", r"\b(?=[0-9a-f]*\d)(?=\d*[a-f])[0-9a-f]{7,40}\b"),
    ("an absolute path", r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]|(?<![\w/:.<>~-])/[\w.-]+(?:/[\w.-]+)+"),
)]


def reported(output):
    """The line a failed check's output is summed up by, or its last non-empty line. git's warnings
    ("LF will be replaced by CRLF") are not the check's report."""
    lines = [l.strip() for l in output.splitlines() if l.strip() and not l.startswith("warning: ")]
    for pattern in REPORTED:
        hits = [m.group(0) for l in lines if (m := pattern.search(l))]
        if hits:
            return hits[-1]
    return lines[-1] if lines else "no output"


def unstable(report):
    """(what, the text) for the first thing in a report that another run or machine prints
    differently, or None. A hash is 7 to 40 hex characters with a digit and a letter among them: a
    count or a word is not one. <tmp> is not a path: untemp() wrote it."""
    for name, pattern in UNSTABLE:
        hit = pattern.search(report)
        if hit:
            return name, hit.group(0)
    return None


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


def matches_anything(expect):
    """Whether the regex matches the empty output and outputs that say something, the way caught()
    reads them, each ending in a newline as a printed line does: then the check's stdout could
    never stop matching."""
    return all(re.search(expect, out, re.M) for out in ("", "1 broken\n", "AssertionError: broken\n"))


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


NO_ENTRY = "run break.py from the repository root, without --cwd, for an entry the replay can run"


def entry_of(a):
    """The break's entry for specs/breaks/day-NN.json (specs/README.md), or None. The replay runs
    the command from the repository root, so there is an entry only for a break run from there."""
    try:
        file = os.path.relpath(a.file)
    except ValueError:  # another drive
        file = os.pardir
    if os.path.abspath(a.cwd) != os.getcwd() or file.startswith(os.pardir):
        return None
    entry = {"what": a.what, "file": file.replace(os.sep, "/"), "find": a.find, "replace": a.replace,
             "command": a.command}
    if a.expect_stdout is not None:
        entry["expect_stdout"] = a.expect_stdout
    return entry


def manifest(a):
    """The line before the broken: line: the break's entry, to copy into the track PR beside it, or
    why there is none."""
    entry = entry_of(a)
    if entry is None:
        return f"manifest: none → {NO_ENTRY}"
    return "manifest: " + json.dumps(entry, ensure_ascii=False)


DAY_BRANCH = re.compile(r"^day-(\d+)/")
CHANGE_BRANCH = re.compile(r"^change/([\w.-]+)$")


def record_path(given):
    """The manifest --record writes: the one given, or the branch's (day-NN/ or change/<slug>);
    (path, None) or (None, why there is none)."""
    if given:
        return given, None
    head = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
    branch = head.stdout.strip()
    if m := DAY_BRANCH.match(branch):
        return f"specs/breaks/day-{m.group(1)}.json", None
    if m := CHANGE_BRANCH.match(branch):
        return f"specs/breaks/{m.group(1)}.json", None
    return None, f"{branch or 'this branch'} is not a day-NN/ or change/<slug> branch: name the manifest, --record <path>"


def blob_of(path, content):
    """git's blob hash of content as path would be committed (its line-ending filters applied), or None."""
    run = subprocess.run(["git", "hash-object", "--stdin", "--path", path], input=content, capture_output=True)
    return run.stdout.decode().strip() if run.returncode == 0 else None


def record(path, entry):
    """Write entry into the manifest at path, in place of one with the same "what" or at its end, one
    entry a line as the close writes them, in the file's own line endings. "added" or "replaced"."""
    entries, newline = [], "\n"
    if os.path.exists(path):
        with open(path, "rb") as f:
            raw = f.read()
        newline = "\r\n" if b"\r\n" in raw else "\n"
        entries = json.loads(raw.decode("utf-8") or "[]")
    at = next((i for i, e in enumerate(entries) if e.get("what") == entry["what"]), None)
    if at is None:
        entries.append(entry)
    else:
        entries[at] = entry
    body = ("," + newline).join(" " + json.dumps(e, ensure_ascii=False) for e in entries)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(("[" + newline + body + newline + "]" + newline if entries else "[]" + newline).encode("utf-8"))
    return "added" if at is None else "replaced"


def git_out(*args):
    """git's stdout, or None when it fails."""
    run = subprocess.run(["git", *args], capture_output=True)
    return run.stdout if run.returncode == 0 else None


def finds_at(commit, file, find):
    """How often find occurs in file at commit, as committed; None when the file is not there."""
    content = git_out("show", f"{commit}:{file}")
    return None if content is None else content.count(find.encode("utf-8"))


def times(count, file, commit):
    return f"{file} is not at {commit[:7]}" if count is None else f"the find occurs {count} times in {file} at {commit[:7]}"


def closed_day_misses(path, file, find):
    """Why find cannot be recorded into a closed Day's manifest, or None: the Day's replay runs its
    entries at the Day's close, so a re-recorded find must occur once there too."""
    m = re.fullmatch(r"day-(\d+)\.json", os.path.basename(path))
    if not m:
        return None
    import evidence  # the close's own rule for which commit closed a Day

    close = evidence.close_commit(m.group(1), "HEAD")
    if close is None or (count := finds_at(close, file, find)) == 1:
        return None
    return (f"Day {m.group(1)} is closed and its replay runs this break at its close, where {times(count, file, close)}: "
            f"choose a find that occurs once there and here, or pin the old entry: break.py --retire {path} --what ...")


def load_entries(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def one_entry(path, what):
    """(entry, None), or (None, why not): the one entry of the manifest at path named what."""
    if not os.path.isfile(path):
        return None, f"{path} does not exist"
    found = [e for e in load_entries(path) if e.get("what") == what]
    if len(found) != 1:
        return None, f"{what!r} is recorded {len(found)} times in {path}: name one entry, as the manifest holds it"
    return found[0], None


def retire(path, what, at=None):
    """Pin an entry with "at", where its find still occurs once; nothing runs, no other entry changes."""
    if not what:
        return refuse("--retire needs --what, the break's name in the manifest")
    entry, why = one_entry(path, what)
    if entry is None:
        return refuse(why)
    ref = at or (git_out("merge-base", "main", "HEAD") or b"").decode().strip()
    if not ref:
        return refuse("there is no main to pin it at: name the commit, --at <commit>")
    sha = (git_out("rev-parse", "--verify", "-q", f"{ref}^{{commit}}") or b"").decode().strip()
    if not sha:
        return refuse(f"{ref} is not a commit")
    if (count := finds_at(sha, entry["file"], entry["find"])) != 1:
        return refuse(f"{times(count, entry['file'], sha)}: pin it where it still applied, --at <commit>")
    record(path, {**entry, "at": sha})
    print(f"retired: {what} in {path}, pinned at {sha[:7]}: the replay runs it there")
    return 0


def take_reports(path):
    """Write the reports CI's Linux replay saved into the entries they name; all are checked first."""
    with open(path, encoding="utf-8") as f:
        takes = json.load(f)
    found = []
    for take in takes:
        entry, why = one_entry(take["manifest"], take["what"])
        if entry is None:
            return refuse(f"nothing taken: {why}")
        found.append((take, entry))
    for take, entry in found:
        record(take["manifest"], {**entry, "report": take["report"]})
        print(f"took: {take['what']}: {entry.get('report')!r} became {take['report']!r} in {take['manifest']}")
    return 0


def endings(find, replace, original):
    """A multi-line --find typed with LF, in a file checked out with CRLF: both in the file's endings.
    The manifest keeps them as typed, which an LF checkout (CI's) replays."""
    if find not in original and b"\n" in find and b"\r" not in find and b"\r\n" in original:
        return find.replace(b"\n", b"\r\n"), replace.replace(b"\n", b"\r\n")
    return find, replace


def lines_of(find, original):
    """The lines a find occurs on, each once, for a refusal to name."""
    found, at = set(), original.find(find)
    while at != -1:
        found.add(original.count(b"\n", 0, at) + 1)
        at = original.find(find, at + len(find))
    return sorted(found)


def refuse(message):
    print(f"break.py: {message}", file=sys.stderr)
    return 2


def main(args=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--file")
    p.add_argument("--find")
    p.add_argument("--replace")
    p.add_argument("--what", help="what was broken, for the broken: line")
    p.add_argument("--cwd", help="where the check runs; --file must then sit in its tree")
    p.add_argument("--expect-stdout", metavar="REGEX",
                   help="the check's stdout without the break; the break is caught when it no longer matches")
    p.add_argument("--replay", action="store_true",
                   help="for evidence.py: one run with the break in and no look at its report, which the caller "
                   "compares with the line recorded")
    p.add_argument("--record", nargs="?", const="", metavar="PATH",
                   help="write the entry, its report and the file's blob into the break manifest: PATH, or the "
                   "branch's (specs/breaks/day-NN.json on day-NN/, specs/breaks/<slug>.json on change/<slug>)")
    p.add_argument("--retire", metavar="MANIFEST",
                   help="pin the entry named --what with \"at\" where its find still occurs once; runs nothing")
    p.add_argument("--at", metavar="COMMIT", help="with --retire: the commit to pin at (default: where HEAD left main)")
    p.add_argument("--take-reports", metavar="FILE",
                   help="write the reports CI's Linux replay saved (track-breaks.py --reports) into the record")
    p.add_argument("command", nargs=argparse.REMAINDER, help="the check, with its options; a leading -- is dropped")
    a = p.parse_args(args)
    sys.stdout.reconfigure(encoding="utf-8")  # the arrow; a Windows console's default is cp1252
    if a.retire:
        return retire(a.retire, a.what, a.at)
    if a.take_reports:
        return take_reports(a.take_reports)
    missing = [f"--{name}" for name in ("file", "find", "replace", "what") if getattr(a, name) is None]
    if missing:
        p.error(f"the following arguments are required: {', '.join(missing)}")
    a.command = a.command[1:] if a.command[:1] == ["--"] else a.command
    elsewhere, a.cwd = a.cwd is not None, a.cwd or "."
    if not a.command:
        p.error("the command to run is required")

    if ARROW.search(a.what):
        return refuse("--what holds an arrow: spec-drift.py would end <what> there; write it without one")
    if os.path.basename(a.command[0]) in ("mvnw", "mvn") and "clean" not in a.command:
        return refuse("a Maven check must clean, or the broken source may not be recompiled")
    try:
        re.compile(a.expect_stdout or "")
    except re.error as e:
        return refuse(f"--expect-stdout is not a regex: {e}")
    if a.expect_stdout is not None and matches_anything(a.expect_stdout):
        return refuse(f"--expect-stdout {a.expect_stdout!r} matches any output, so no break could be caught; "
                      "for a check that prints nothing, write \\A\\Z")
    if elsewhere and not in_tree(a.file, a.cwd):
        return refuse(f"--file {a.file} is outside the tree --cwd {a.cwd} runs the check in ({tree(a.cwd)}): "
                      "the break would not be in the code the check runs; name the file in that tree")
    target = None
    if a.record is not None:
        if a.replay:
            return refuse("--record with --replay: a replay checks a recorded entry, it does not record one")
        if entry_of(a) is None:
            return refuse(f"--record has no entry to write: {NO_ENTRY}")
        target, why = record_path(a.record)
        if target is None or (why := closed_day_misses(target, entry_of(a)["file"], a.find)):
            return refuse(why)
    with open(a.file, "rb") as f:
        original = f.read()
    blob = blob_of(entry_of(a)["file"], original) if target else None
    if target and blob is None:
        return refuse(f"--record needs git to hash {a.file}: run it inside the repository")
    find, replace = endings(a.find.encode(), a.replace.encode(), original)
    if original.count(find) != 1:
        where = f" (lines {', '.join(map(str, lines_of(find, original)))})" if find in original else ""
        return refuse(f"--find occurs {original.count(find)} times in {a.file}{where}, want exactly once")
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
        runs = []
        try:
            # Twice, so a report that changes from one run to the next (a pid, a temporary name) is refused,
            # not recorded: the replay on another machine would print another line.
            for _ in range(1 if a.replay else 2):
                runs.append(subprocess.run(argv_for(a.command, a.cwd), cwd=a.cwd, capture_output=True, text=True,
                                           encoding="utf-8", errors="replace", env=env))
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
    for run in runs:
        said = not_run(run.returncode, run.stdout + run.stderr)
        if said:
            return refuse(f"the command started but the check did not run, so nothing is recorded: {untemp(said)}")
    seen = [caught(run.returncode, run.stdout, a.expect_stdout) for run in runs]
    if not any(seen):
        output = runs[0].stdout + runs[0].stderr
        print(f"The check passed with the break in: it cannot see this break.\n  last line: {reported(output)}")
        return 1
    if not all(seen):
        return refuse("the check failed in one run with the break in and passed in the other: "
                      "it is flaky, so nothing is recorded")
    reports = [untemp(reported(run.stdout + run.stderr)) for run in runs]
    if len(set(reports)) > 1:
        return refuse(f"the report differs between two runs with the break in, so the replay would not print it "
                      f"again: {reports[0]!r} then {reports[1]!r}; have the test print a fixed word in place of "
                      "what changes")
    if not a.replay and (found := unstable(reports[0])):
        name, text = found
        return refuse(f"the report holds {name} ({text}), which another run or machine prints differently: "
                      f"{reports[0]!r}; have the test print a fixed word in its place (<uuid>, <head>, <pid>, "
                      "a relative path)")
    if target:
        how = record(target, {**entry_of(a), "report": reports[0], "blob": blob})
        print(f"recorded: {how} in {target}")
    print(manifest(a))
    print(f"broken: {a.what} → {reports[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
