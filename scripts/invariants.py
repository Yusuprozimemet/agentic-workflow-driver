"""Fail a pull request that edits what the project must not change, and name each file.

The frozen files are the project's safety net: applied migrations, which are never changed once
they have run, and the tests that prove the behaviour a change has to keep. The project file,
spec-drift.config.json at the root, lists them as regular expressions over the path (`frozen`),
read as the base has it, so a pull request cannot unfreeze what it edits; none, and nothing is
frozen. Additions and pure renames within the frozen set pass, so a move stays possible; a
modification, a deletion, a type change, a rename with an edit or a rename to a path no pattern
matches fails. Reads the same three-dot diff as the size check in pr-checks.yml.

The project file's `test_count` rule, also read at the base, counts the tests without running
them: the lines matching `test` in the files whose path matches `files`. The count at head must
not fall below the count where the branch left the base, so a move that hides a test from
discovery, or a deleted test, fails too. No rule, and nothing is counted.

The specs freeze files too: a ticked `hold` still in force (behaviour-index.py's reading) whose
own lines name the commit of its spec's Verify line `git ... diff --exit-code <sha> -- <paths>`
holds those paths unchanged since it. Read as the base has them, so a pull request cannot replace
the hold it breaks: the spec-change PR that replaces it lands first, and its `Replaces:` lifts the
freeze before the day ticks the criterion (#123, #149). The paths are git's
pathspecs, so a file added under a listed directory fails as well (D10.1: Day 9's #142 edited
`driver/settings.py` and added `hooks/hook_log.py`, which C08.1 froze; only the replay after the
merge saw it).

    python scripts/invariants.py <base> <head>
"""
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

CONFIG = "spec-drift.config.json"
WORDS = {"M": "modified", "D": "deleted", "T": "type changed"}
SPECS = "specs"
HERE = os.path.dirname(os.path.abspath(__file__))
FREEZE = re.compile(r"\bdiff --exit-code ([0-9a-f]{7,40}) -- (.+)$")
NOTE = re.compile(r"^\s*(Evidence|Replaces|broken|seen red|manifest|Test|Plan):")
ADDED = {"A": "added", **WORDS}


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")


def base_config(base):
    """The project file at base; empty with no file."""
    shown = git("show", f"{base}:{CONFIG}")
    return {} if shown.returncode else json.loads(shown.stdout)


def frozen_patterns(config):
    """The project file's `frozen` patterns; none with no field."""
    return tuple(re.compile(p) for p in config.get("frozen", []))


def spec_freezes(base, scratch):
    """(criterion, sha, paths) per Verify freeze line whose hold is in force in the base's specs."""
    names = [p for p in git("ls-tree", "-r", "--name-only", base, "--", SPECS).stdout.splitlines()
             if re.search(r"(^|/)day-\d+-[^/]+\.md$", p) or "/changes/" in p]
    if not any(re.search(r"(^|/)day-\d+-", p) for p in names):
        return []
    for path in names:
        out = os.path.join(scratch, os.path.relpath(path, SPECS))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="") as f:
            f.write(git("show", f"{base}:{path}").stdout)
    loaded = importlib.util.spec_from_file_location("behaviour_index", os.path.join(HERE, "behaviour-index.py"))
    index = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(index)  # spec-drift.py's parser, which needs numpy
    rows, _ = index.collect(scratch)
    # A merged spec-change PR's Replaces: lifts the freeze before its day ticks the criterion.
    pending = {target for r in rows for target in r["replaces"]}
    live = {(r["spec"], r["id"]) for r in rows if r["state"] == "in force" and r["id"] not in pending}
    found = []
    for name in sorted(os.listdir(scratch)):
        if not index.DAY_FILE.fullmatch(name):
            continue
        with open(os.path.join(scratch, name), encoding="utf-8-sig") as f:
            text = f.read()
        verify = re.search(r"^## Verify\s*\n```\w*\n(.*?)^```", text, re.M | re.S)
        blocks = re.split(r"^(?=- \[[ x]\])", index.sd.section(text, "Acceptance criteria"), flags=re.M)
        for line in verify.group(1).splitlines() if verify else []:
            if not (m := FREEZE.search(line.strip())):
                continue
            sha, paths = m.group(1), shlex.split(m.group(2))
            for block in blocks:
                own = re.match(r"- \[x\] (C\d+\.\d+) \*\*hold\*\*", block)
                body = "\n".join(l for l in block.splitlines() if not NOTE.match(l))
                if own and (name, own.group(1)) in live and sha in body:
                    found.append((own.group(1), sha, paths))
    return found


def spec_violations(base, head, freezes):
    """One line per path a freeze in force holds that the branch adds, edits, deletes or retypes."""
    found = []
    for crit, sha, paths in freezes:
        diff = git("diff", "--name-status", "--no-renames", f"{base}...{head}", "--", *paths)
        for line in diff.stdout.splitlines():
            status, path = line.split("\t", 1)
            found.append(f"{crit} freezes {path} (unchanged since {sha}): {ADDED.get(status[0], status)}")
    return found


def test_count(rev, rule):
    """How many lines matching the rule's `test` the files matching its `files` hold at rev."""
    files, test = re.compile(rule["files"]), re.compile(rule["test"], re.M)
    paths = git("ls-tree", "-r", "--name-only", rev).stdout.splitlines()
    return sum(len(test.findall(git("show", f"{rev}:{p}").stdout)) for p in paths if files.search(p))


def protected(path, patterns):
    return any(p.search(path) for p in patterns)


def entries(name_status_lines):
    """(code, status, similarity, old path, new path) per line of `git diff --name-status -M`."""
    for line in name_status_lines:
        if not line.strip():
            continue
        fields = line.split("\t")
        code = fields[0]
        new = fields[2] if len(fields) > 2 else fields[1]
        yield code, code[0], int(code[1:] or 100), fields[1], new


def violations(name_status_lines, patterns):
    """One line per protected file that is modified, deleted, retyped, renamed with an edit or
    renamed out of the frozen set."""
    found = []
    for code, status, _, old, new in entries(name_status_lines):
        if status == "R" and protected(old, patterns) and not protected(new, patterns):
            found.append(f"renamed out of the frozen set ({code}): {old} -> {new}")
        elif status == "R" and code != "R100" and protected(old, patterns):
            found.append(f"renamed with an edit ({code}): {old} -> {new}")
        elif status in WORDS and protected(old, patterns):
            found.append(f"{WORDS[status]}: {old}")
    return found


def passed(name_status_lines, patterns):
    """How many protected files the diff adds or moves as they are: the count the OK line prints."""
    count = 0
    for code, status, _, old, new in entries(name_status_lines):
        if status == "A" or status == "C" or code == "R100":
            count += protected(old, patterns) or protected(new, patterns)
    return count


def main(argv):
    if len(argv) != 2:
        print("usage: python scripts/invariants.py <base> <head>", file=sys.stderr)
        return 2
    base, head = argv
    diff = git("diff", "--name-status", "-M", "-l0", f"{base}...{head}")
    if diff.returncode:
        print(diff.stderr, file=sys.stderr)
        return 2
    config = base_config(base)
    patterns, rule = frozen_patterns(config), config.get("test_count")
    with tempfile.TemporaryDirectory() as scratch:
        freezes = spec_freezes(base, scratch)
    if not patterns and not rule and not freezes:
        print(f"Nothing frozen: {CONFIG} sets no `frozen` patterns.")
        return 0
    lines = diff.stdout.splitlines()
    found = violations(lines, patterns) + spec_violations(base, head, freezes)
    owners = sorted({crit for crit, _, _ in freezes})
    held = f"; {len(owners)} spec freeze{'s' * (len(owners) != 1)} in force ({', '.join(owners)})" if owners else ""
    counted = ""
    if rule:
        # Where the branch left the base, as the three-dot diff does: tests the base gained since are not the branch's.
        fork = git("merge-base", base, head).stdout.strip()
        before, after = test_count(fork, rule), test_count(head, rule)
        counted = f", {before} tests before and {after} after"
        if after < before:
            found.append(f"test count dropped: {before} where the branch left the base, {after} at head")
    if found:
        for line in found:
            print(line)
        print("These files are frozen: add a new migration instead of editing an applied one. "
              "A frozen test edit, a move out of the frozen set or a lost test means stop and ask (see CLAUDE.md). "
              "A file a hold freezes is edited only after a spec-change PR replaces the hold (Replaces:).")
        return 1
    print(f"OK: no frozen file was modified, deleted or renamed with an edit "
          f"({passed(lines, patterns)} frozen files added or moved unchanged{counted}{held}).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
