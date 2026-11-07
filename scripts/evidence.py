"""Each ticked criterion's evidence holds up at the commit its day's close merged.

    python scripts/evidence.py specs/day-05-json.md [...] [--ref main]

For each spec, at the merge commit of its day's close (`day-NN/close-the-day`) on --ref, or for a
short spec, `specs/changes/<slug>.md`, at the merge of `change/<slug>` (or the squash that added
the spec), its breaks in specs/breaks/<slug>.json:

- every test a ticked criterion names (`CliTest.test_name`) is defined there, in a class of that
  name under tests/ or in a tests.py at the root;
- every line of the Verify block runs, with bash, in a scratch worktree at that commit, and gives
  what its comment says. A comment is a list split at ", ", a trailing "(...)" dropped: "nothing"
  wants no output, "exit N" that exit status, and anything else a line of output that is it or
  starts with it and a space. A line with no comment wants exit 0. `main` given to git on this
  repository means the close's first parent, so a line written as `git diff main` reads the day's
  base, not today's; given to any other command, or to `git -C`, it is left as written;
- every `broken:` line under a ticked criterion re-runs through scripts/break.py, from the
  arguments recorded for it in specs/breaks/day-NN.json, and reports what the line says, temporary
  directory names aside, and a report pasted across lines or with its backslashes undoubled read
  as the escapes break.py printed. A `broken:` line with no recorded arguments fails: prose cannot
  be re-run. A near miss recorded with "passes" must pass with the break in instead, its report
  the check's last line;
- every criterion names what proved it: a test, a command (`git ...`, `python ...` and the like,
  quoted), a break, or a reader. An unticked criterion is `not proven`, and a ticked one with none
  of the first three fails, each unless a `Not proven: <why>` line sits under it in the spec at that
  commit: a line added to the spec since does not count.

The breaks file is a list of {"what", "file", "find", "replace", "command"}, "what" being the text
of the `broken:` line before its last arrow and unique in the file (a name recorded twice fails),
"file" a path from the repository root, and "command" an argument list run from that root, `bash`
meaning Git's bash on Windows. Four keys are optional:
"posix_only": true for a break no Windows run can see (`os.setpgid` there changes nothing), which
a replay on Windows reports not applicable and a replay elsewhere runs as any other;
"passes": true for a near miss that passes by design, which break.py does not record (it exits 1);
"at": a commit to run the break at instead of the close, when the close no longer has what the
break edits; and "expect_stdout": the regex break.py's --expect-stdout took, for a check judged by
what it prints (`grep -c`), without which such a check replays as passing with the break in.

Missing evidence is a check that fails, not one that is skipped: a criterion nothing proved, an
unticked one with no `Not proven:` line, a hold criterion with no `broken:` line, a spec with no Verify block or no
ticked criterion. A criterion checked by a command instead of a named test, and a `broken: none →
<why>`, are recorded as not applicable, with the reason.

With --criterion ID (repeatable) only the named criteria's checks replay, from one spec, and the Verify
block does not run: a partial replay is not the close's, so it cannot go with --cache, which keeps only
whole replays. An ID the spec does not have fails.

Item 6 of the lab notebook's open items: no step checked the evidence a close ticks a box on. It
prints one line per check and exits 1 if any failed or could not run. With --json PATH it also
writes the same checks as a report (docs/spec-drift-improvement.md, Step 2): each with an id, a
kind, its criterion and the commit it ran at, and a status, passed, failed, error (the checker
could not run it) or not_applicable, a proof check also its proved_by (`proved_by` below, null for
an unticked criterion); and what was checked, from which inputs, by which runner. It
changes no file outside the worktree but that report.
"""
import argparse
import datetime
import fnmatch
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BREAK = os.path.join(HERE, "break.py")

CRITERION_ID = r"C\d+\.\d+|S-[a-z0-9]+(?:-[a-z0-9]+)*\.\d+"
CRITERION = re.compile(rf"^- \[([ x])\] ({CRITERION_ID})\b")
CHANGE_MERGE = re.compile(r"^Merge pull request #\d+ from \S+/change/([a-z0-9]+(?:-[a-z0-9]+)*)$")
SQUASHED = re.compile(r" \(#\d+\)$")
TEST = re.compile(r"`(\w+)\.(test_\w+)`")
# At the last arrow: what was broken can hold an arrow itself.
BROKEN = re.compile(r"^\s*broken: (.+) → (.*)$", re.S)
PR_SUFFIX = re.compile(r"\s+\(#\d+\)$")
TEMP_NAME = re.compile(r"tmp[0-9a-z_]{8}")
# break.py's own: it writes a temporary directory, the whole path up to it, as <tmp>.
TEMP_PATH = re.compile(r"[^\s'\"()\[\]]*?[\\/]+tmp[a-z0-9_]{8}(?![a-z0-9_])")
# pytest's run time in its summary ("1 failed in 0.14s", "in 61.20s (0:01:01)"): no two runs agree.
DURATION = re.compile(r" in \d+(?:\.\d+)?s(?: \(\d+:\d{2}:\d{2}\))?")
COMMENT = re.compile(r"^(.*?)\s{2,}#\s*(.*)$")
# A criterion checked by a command it quotes, not by a named test, as a hold criterion often is.
COMMAND = re.compile(r"`((?:git|python|diff|grep|bash) [^`]+)`")
NOT_PROVEN = re.compile(r"^\s+Not proven: (\S.*)$")
SCHEMA = 1
MARK = {"passed": "ok  ", "failed": "FAIL", "error": "ERR ", "not_applicable": "n/a "}


def git(*args, check=True):
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=check).stdout


def close_pattern(day):
    return re.compile(rf"^Merge pull request #\d+ from \S+/day-{day}/close-the-day(?:-\S*)?$")


def squash_pattern(day):
    key = os.environ.get("JIRA_KEY", "")
    key_text = re.escape(key) if key else "(?!)"
    return re.compile(rf"^(?:{key_text}-\d+ )?Day {day} close\b.* \(#\d+\)$")


def closing_spec(commit):
    """Spec at a closing merge or squash commit; None otherwise, or ValueError for bad specs."""
    parents, subject = git("show", "-s", "--format=%P%n%s", commit).splitlines()[:2]
    count = len(parents.split())
    day_pattern = r"(?P<day>\d{2})"
    match = (close_pattern(day_pattern).match(subject) if count >= 2 else
             squash_pattern(day_pattern).match(subject) if count == 1 else None)
    if not match:
        spec = change_spec(commit, count, subject)
        if spec and not git("ls-tree", "--name-only", commit, "--", spec).strip():
            raise ValueError(f"{spec}: not at {commit[:7]}")
        return spec  # None: this commit neither closes a day nor lands a short spec.
    day = match.group("day")
    specs = [p for p in git("ls-tree", "-r", "--name-only", commit, "--", "specs").splitlines()
             if fnmatch.fnmatchcase(p, f"specs/day-{day}-*.md") and p.count("/") == 1]
    if len(specs) != 1:
        raise ValueError(f"day-{day}: expected one spec, found {len(specs)}")
    return specs[0]


def close_commit(day, ref):
    """The latest closing merge or squash commit on ref for the day, or None."""
    merge, squash = close_pattern(day), squash_pattern(day)
    for line in git("log", "--first-parent", "--format=%H%x00%P%x00%s", ref).splitlines():
        sha, parent_text, subject = line.split("\0", 2)
        parents = parent_text.split()
        if (len(parents) >= 2 and merge.match(subject) or
                len(parents) == 1 and squash.match(subject)):
            return sha
    return None


def closed_specs(ref):
    """Each day spec on ref whose day has a closing commit there, in path order: what the dashboard replays."""
    paths = git("ls-tree", "--name-only", ref, "--", "specs/").split()
    days = [(p, re.match(r"specs/day-(\d{2})-[^/]*\.md$", p)) for p in sorted(paths)]
    return [p for p, m in days if m and close_commit(m.group(1), ref)]


def change_spec(commit, count, subject):
    """The short spec a commit with that many parents and that subject lands: the merge of
    `change/<slug>`, or a squash that adds one `specs/changes/<slug>.md`; or None."""
    if count >= 2:
        m = CHANGE_MERGE.match(subject)
        return f"specs/changes/{m.group(1)}.md" if m else None
    if count != 1 or not SQUASHED.search(subject):
        return None
    added = [p for p in git("diff-tree", "--no-commit-id", "--name-only", "-r", "--diff-filter=A", commit,
                            "--", "specs/changes").splitlines() if p.endswith(".md") and p.count("/") == 2]
    return added[0] if len(added) == 1 else None


def change_commit(slug, ref):
    """The latest commit on ref that lands specs/changes/<slug>.md, or None."""
    path = f"specs/changes/{slug}.md"
    for line in git("log", "--first-parent", "--format=%H%x00%P%x00%s", ref, "--", path).splitlines():
        sha, parent_text, subject = line.split("\0", 2)
        if change_spec(sha, len(parent_text.split()), subject) == path:
            return sha
    return None


def criteria(text):
    """{id: lines} for each criterion under Acceptance criteria, ticked or not: its first line says which."""
    found, current, inside = {}, None, False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## Acceptance criteria"
            current = None
            continue
        if not inside:
            continue
        m = CRITERION.match(line)
        if m:
            current = m.group(2)
            found[current] = []
        elif line.startswith("- "):
            current = None
        if current:
            found[current].append(line)
    return found


def not_proven(lines):
    """The reason a `Not proven:` line under a criterion gives, or None."""
    return next((m.group(1).strip() for line in lines[1:] if (m := NOT_PROVEN.match(line))), None)


def proved_by(tests, command, broken, reason):
    """What proved a ticked criterion, every kind found, in this order: "test", "command", "break";
    ["reader"] when none of them but a `Not proven:` line; [] when nothing. The dashboard ranks them."""
    found = [k for k, hit in (("test", tests), ("command", command), ("break", broken)) if hit]
    return found or (["reader"] if reason else [])


def spec_at(commit, path):
    """The spec's text at the commit, or "" when it is not there."""
    prefix = git("-C", os.path.dirname(os.path.abspath(path)), "rev-parse", "--show-prefix").strip()
    return git("show", f"{commit}:{prefix}{os.path.basename(path)}", check=False)


def verify_lines(text):
    """The commands of the Verify block's first fenced block."""
    block = re.search(r"^## Verify\s*\n```\w*\n(.*?)^```", text, re.M | re.S)
    return [l for l in block.group(1).splitlines() if l.strip()] if block else []


def test_exists(commit, cls, name):
    # tests/ as in most projects, or one tests.py at the root as in python-json-pointer
    hits = git("grep", "-l", "-E", rf"^class {cls}\b", commit, "--", "tests", "tests.py", check=False).split()
    for hit in hits:  # <commit>:<path>
        if re.search(rf"^\s+def {name}\(", git("show", hit), re.M):
            return True
    return False


def bash():
    """Git's own bash on Windows: the first bash on PATH there may be WSL's, which cannot run git."""
    if os.name == "nt":
        root = os.path.dirname(shutil.which("git") or "")
        while root and os.path.dirname(root) != root:
            if os.path.isfile(os.path.join(root, "bin", "bash.exe")):
                return os.path.join(root, "bin", "bash.exe")
            root = os.path.dirname(root)
    return shutil.which("bash") or "bash"


def expected(comment, code, output):
    """Why the output is not what the comment says, or None."""
    lines = [l.strip() for l in output.splitlines()]
    for part in re.sub(r"\s*\(.*\)$", "", comment).split(", "):
        if part == "nothing":
            if output.strip():
                return f"wanted nothing, got {lines[0]!r}"
        elif m := re.fullmatch(r"exit (\d+)", part):
            if code != int(m.group(1)):
                return f"wanted {part}, got exit {code}"
        elif not any(l == part or l.startswith(part + " ") for l in lines):
            return f"wanted a line {part!r}, got {(lines[-1] if lines else 'nothing')!r}"
    return None


def at_base(command, base):
    """The command with `main` read as `base` in each part (split at |, &&, || and ;) that runs
    git on this repository: a `git` with no -C. Elsewhere `main` may be another repository's
    branch (Day 05: `bearing snapshot <fixture repo> main`) and is left as written."""
    parts = re.split(r"(\|\||&&|\||;)", command)
    return "".join(
        re.sub(r"\bmain\b", base, part)
        if re.match(r"\s*git\s", part) and not re.search(r"\s-C\b", part)
        else part
        for part in parts
    )


def run_verify(line, worktree, base, env):
    m = COMMENT.match(line)
    command, comment = (m.group(1), m.group(2)) if m else (line, None)
    command = at_base(command, base)
    run = subprocess.run([bash(), "-c", command], cwd=worktree, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", env=env)
    if comment is None:
        return None if run.returncode == 0 else f"exit {run.returncode}"
    return expected(comment, run.returncode, run.stdout + run.stderr)


def joined(lines):
    """The lines, a line indented less than a `broken:` line before it joined to it: a report
    recorded across lines."""
    indent = lambda line: len(line) - len(line.lstrip())
    out = []
    for line in lines:
        if out and BROKEN.match(out[-1]) and line.strip() and indent(line) < indent(out[-1]):
            out[-1] += "\n" + line
        else:
            out.append(line)
    return out


def normal(report):
    """A report as compared: temporary names aside, and a newline and a run of backslashes read as
    the escapes they were pasted from, and a run time as any other."""
    report = DURATION.sub(" in <time>", report)
    report = TEMP_NAME.sub("tmp*", TEMP_PATH.sub("<tmp>", PR_SUFFIX.sub("", report.strip())))
    return re.sub(r"\\+", r"\\", report.replace("\n", "\\n"))


PASSED = "The check passed with the break in"


def run_break(entry, worktree, env):
    """("reported", what break.py reported for the recorded break), or ("failed", why it did not):
    the break no longer applies, or the check cannot see it; or ("error", why) when the break could
    not be run at all."""
    if "at" in entry:
        other = tempfile.mkdtemp(prefix="evidence-")
        try:
            git("worktree", "add", "--detach", other, entry["at"])
        except subprocess.CalledProcessError as e:
            shutil.rmtree(other, ignore_errors=True)
            return "error", f"no worktree at {entry['at']}: {e.stderr.strip()}"
        try:
            return run_break({k: v for k, v in entry.items() if k != "at"}, other, env)
        finally:
            git("worktree", "remove", "--force", other, check=False)
    command = entry["command"]
    if command[0] == "bash":
        command = [bash(), *command[1:]]
    expect = ["--expect-stdout", entry["expect_stdout"]] if "expect_stdout" in entry else []
    run = subprocess.run([sys.executable, BREAK, "--file", os.path.join(worktree, entry["file"]),
                          "--find", entry["find"], "--replace", entry["replace"], "--what", entry["what"],
                          "--cwd", worktree, *expect, "--", *command],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    lines = (run.stdout + run.stderr).strip().splitlines()
    if entry.get("passes"):
        if run.returncode == 0:
            return "failed", "failed with the break in: this near miss should pass"
        if lines and lines[0].startswith(PASSED):
            return "reported", lines[-1].strip()[len("last line: "):]
    if run.returncode == 2 and not (lines and "--find occurs" in lines[0]):
        return "error", lines[0] if lines else "break.py exited 2"  # it refused to run the check
    if run.returncode != 0:
        return "failed", lines[0] if lines else f"break.py exited {run.returncode}"
    return "reported", lines[-1][len(f"broken: {entry['what']} → "):]


def input_file(path):
    """A spec or breaks file as this run read it: its hash, and whether it is the file at HEAD
    ("clean", with that revision), "edited", "untracked" or "missing"."""
    record = {"path": path.replace(os.sep, "/"), "sha256": None, "state": "missing", "revision": None}
    if os.path.isfile(path):
        with open(path, "rb") as f:
            record["sha256"] = hashlib.sha256(f.read()).hexdigest()
        if not git("ls-files", "--", path, check=False).strip():
            record["state"] = "untracked"
        elif git("status", "--porcelain", "--", path, check=False).strip():
            record["state"] = "edited"
        else:
            record.update(state="clean", revision=git("rev-parse", "HEAD").strip())
    return record


def check_spec(path, ref, only=None):
    """One spec's record: what it was checked from and at, and its checks; only, a partial replay's criteria."""
    name = os.path.basename(path)
    record = {"spec": input_file(path), "day": None, "change": None, "close_sha": None, "verify_base_sha": None,
              "breaks": None, "criteria": list(only) if only else None, "checks": []}

    def add(key, kind, status, label, diagnostic=None, criterion=None, sha=None, proof=None):
        record["checks"].append({"id": f"{name}/{key}", "kind": kind, "criterion": criterion, "sha": sha,
                                 "status": status, "label": label, "diagnostic": diagnostic})
        if kind == "proof":  # null for an unticked criterion: not proven
            record["checks"][-1]["proved_by"] = proof

    day = re.match(r"day-(\d{2})-", name)
    # A short spec, specs/changes/<slug>.md, replays at the merge of change/<slug>.
    slug = re.fullmatch(r"([a-z0-9]+(?:-[a-z0-9]+)*)\.md", name)
    slug = slug and os.path.basename(os.path.dirname(os.path.abspath(path))) == "changes" and slug.group(1)
    if not (day or slug) or not os.path.isfile(path):
        add("close", "close", "failed", name, "no such file" if day or slug else "neither a day spec nor a short spec")
        return record
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if day:
        record["day"] = day.group(1)
        commit = record["close_sha"] = close_commit(day.group(1), ref)
        breaks_file = os.path.join(os.path.dirname(path), "breaks", f"day-{day.group(1)}.json")
        landed, missing = "close merged", f"no merged day-{day.group(1)}/close-the-day on {ref}"
    else:
        record["change"] = slug
        commit = record["close_sha"] = change_commit(slug, ref)
        breaks_file = os.path.join(os.path.dirname(os.path.dirname(path)), "breaks", f"{slug}.json")
        landed, missing = "change merged", f"no merged change/{slug} on {ref}"
    record["breaks"] = input_file(breaks_file)
    if not commit:
        add("close", "close", "failed", name, missing)
        return record
    add("close", "close", "passed", f"{name}: {landed} in {commit[:7]}", sha=commit)
    found = criteria(text)
    ticked = {cid: lines for cid, lines in found.items() if lines[0].startswith("- [x]")}
    if not ticked and not only:
        add("criteria", "close", "failed", name, "no ticked criterion: nothing was checked")
    for cid in only or []:
        if cid not in found:
            add(f"{cid}/criterion", "criterion", "failed", cid, f"no criterion {cid} in {name}", cid)
    if only:
        found = {cid: lines for cid, lines in found.items() if cid in only}
        ticked = {cid: lines for cid, lines in ticked.items() if cid in only}
    # A Not proven: line counts as the close merged it, not as added to the spec since.
    reasons = {cid: not_proven(lines) for cid, lines in criteria(spec_at(commit, path)).items()}

    for cid, lines in found.items():
        reason = reasons.get(cid)
        if cid not in ticked:
            add(f"{cid}/proof", "proof", "passed" if reason else "failed", f"{cid} not proven",
                reason or f"no Not proven: line under it at {commit[:7]}", cid, commit)
            continue
        body = "\n".join(lines)
        tests = dict.fromkeys(TEST.findall(body))
        for cls, test in tests:
            ok = test_exists(commit, cls, test)
            add(f"{cid}/test/{cls}.{test}", "named_test", "passed" if ok else "failed", f"{cid} {cls}.{test}",
                None if ok else f"not defined at {commit[:7]}", cid, commit)
        command = COMMAND.search(body)
        broken = any(m and m.group(1) != "none" for m in map(BROKEN.match, joined(lines)))
        proof = [w for w, hit in (("a test", tests), ("a command", command), ("a break", broken)) if hit]
        kinds = proved_by(tests, command, broken, reason)
        if not tests and (proof or reason):
            add(f"{cid}/test", "named_test", "not_applicable", f"{cid} named test",
                f"none: checked by `{command.group(1)}`" if command else
                "none: checked by its break" if broken else "none: judged by a reader", cid)
        if proof:
            add(f"{cid}/proof", "proof", "passed", f"{cid} proved by {', '.join(proof)}", None, cid, commit, kinds)
        else:
            add(f"{cid}/proof", "proof", "passed" if reason else "failed", f"{cid} proved by a reader" if reason
                else f"{cid} proved by nothing", reason or "no test, command or break, and no Not proven: line "
                f"under it at {commit[:7]}", cid, commit, kinds)

    recorded, times = {}, {}
    if os.path.exists(breaks_file):
        with open(breaks_file, encoding="utf-8") as f:
            for e in json.load(f):
                recorded[e["what"]] = e
                times[e["what"]] = times.get(e["what"], 0) + 1

    # A partial replay with no break to run reads the spec alone: no worktree, and no Verify block.
    runs = [m for lines in ticked.values() for m in map(BROKEN.match, joined(lines)) if m and m.group(1) != "none"]
    if only and not runs:
        return record
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    worktree = tempfile.mkdtemp(prefix="evidence-")
    try:
        git("worktree", "add", "--detach", worktree, commit)
    except subprocess.CalledProcessError as e:
        shutil.rmtree(worktree, ignore_errors=True)
        add("worktree", "runner", "error", name, f"no worktree at {commit[:7]}: {e.stderr.strip()}", sha=commit)
        return record
    try:
        base = record["verify_base_sha"] = git("rev-parse", f"{commit}^1").strip()
        commands = [] if only else verify_lines(text)  # a partial replay runs no Verify line
        if not commands and not only:
            add("verify", "verify", "failed", "Verify", "no Verify block, or an empty one")
        for i, line in enumerate(commands, 1):
            why = run_verify(line, worktree, base, env)
            add(f"verify/{i}", "verify", "failed" if why else "passed", f"Verify: {line.strip()}", why, sha=commit)
        for cid, lines in ticked.items():
            found = [m.groups() for l in joined(lines) if (m := BROKEN.match(l))]
            if not found and "**hold**" in lines[0]:
                add(f"{cid}/break", "break", "failed", f"{cid} broken:", "a hold criterion with no broken: line", cid)
            for what, report in found:
                key, label = f"{cid}/break/{what}", f"{cid} broken: {what}"
                if what == "none":
                    add(key, "break", "not_applicable", label, report.strip(), cid)
                    continue
                if what not in recorded:
                    add(key, "break", "failed", label, f"no arguments in {breaks_file}", cid)
                    continue
                if recorded[what].get("posix_only") and os.name == "nt":
                    add(key, "break", "not_applicable", label, "a POSIX-only break: not replayed on Windows", cid)
                    continue
                if times[what] > 1:
                    add(key, "break", "failed", label, f"recorded {times[what]} times in {breaks_file}: "
                        "give each break a name of its own", cid)
                    continue
                at = recorded[what].get("at")
                sha = git("rev-parse", "--verify", "-q", f"{at}^{{commit}}", check=False).strip() if at else commit
                status, got = run_break(recorded[what], worktree, env)
                if status == "reported":
                    same = normal(got) == normal(report)
                    status, got = ("passed", None) if same else (
                        "failed", f"reported {got!r}, the spec says {PR_SUFFIX.sub('', report)!r}")
                add(key, "break", status, label, got, cid, sha or None)
    finally:
        git("worktree", "remove", "--force", worktree, check=False)
    return record


def runner():
    """The checker's own revision, and whether its scripts differ from it."""
    at = lambda *args: subprocess.run(["git", "-C", HERE, *args], capture_output=True, text=True).stdout.strip()
    return {"revision": at("rev-parse", "HEAD") or None,
            "dirty": bool(at("status", "--porcelain", "--", "evidence.py", "break.py")),
            "python": platform.python_version(), "platform": platform.platform()}


def replay_key(path, ref):
    """A hash of everything a spec's replay reads: the commit it replays at, its spec and breaks files,
    this checker's scripts, the project's dependency files and the Python running them; None when it
    has no close on ref. Two replays with the same key run the same checks on the same code."""
    name = os.path.basename(path)
    day = re.match(r"day-(\d{2})-", name)
    slug = re.fullmatch(r"([a-z0-9]+(?:-[a-z0-9]+)*)\.md", name)
    if day:
        commit = close_commit(day.group(1), ref)
        breaks = os.path.join(os.path.dirname(path), "breaks", f"day-{day.group(1)}.json")
    elif slug and os.path.basename(os.path.dirname(os.path.abspath(path))) == "changes":
        commit = change_commit(slug.group(1), ref)
        breaks = os.path.join(os.path.dirname(os.path.dirname(path)), "breaks", f"{slug.group(1)}.json")
    else:
        return None
    if not commit:
        return None
    h = hashlib.sha256(f"{commit}\n{platform.python_version()}\n".encode())
    # The repository root, as the spec path is relative to. PROJECT: add any other file the replayed
    # checks install from.
    for f in (path, breaks, os.path.abspath(__file__), BREAK, "pyproject.toml", "requirements.txt"):
        h.update(b"\0" + (open(f, "rb").read() if os.path.isfile(f) else b"missing"))
    return h.hexdigest()


def load_cache(path):
    """The replays a --cache file kept, by spec path; none when it is missing, unreadable or of another schema."""
    try:
        with open(path, encoding="utf-8") as f:
            kept = json.load(f)
        return kept["specs"] if kept.get("schema") == SCHEMA else {}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def report_text(report):
    """The report as JSON with one check per line, so a committed one diffs by check, as token-usage.json by row."""
    one = lambda v: json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    days = []
    for d in report["days"]:
        head = "".join(f"{one(k)}:{one(v)}," for k, v in d.items() if k != "checks")
        days.append(" {" + head + '"checks":[\n' + ",\n".join("  " + one(c) for c in d["checks"]) + "\n ]}")
    fields = [f"{one(k)}:" + ("[\n" + ",\n".join(days) + "\n]" if k == "days" else one(v)) for k, v in report.items()]
    return "{\n" + ",\n".join(fields) + "\n}\n"


def criterion_id(text):
    if not re.fullmatch(CRITERION_ID, text):
        raise argparse.ArgumentTypeError(f"not a criterion id: {text!r}")
    return text


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("specs", nargs="+")
    p.add_argument("--ref", default="main")
    p.add_argument("--json", metavar="PATH", help="also write the checks as a report")
    p.add_argument("--cache", metavar="PATH", help="reuse a spec's replay kept here when its replay_key is "
                   "unchanged and every check held; keep this run's held replays here")
    p.add_argument("--criterion", action="append", metavar="ID", type=criterion_id,
                   help="replay only this criterion's checks (repeatable; one spec only; skips the Verify block)")
    a = p.parse_args(argv)
    if a.criterion and a.cache:
        p.error("--criterion cannot go with --cache: a partial replay is never kept")
    if a.criterion and len(a.specs) != 1:
        p.error("--criterion takes exactly one spec")
    sys.stdout.reconfigure(encoding="utf-8")
    report = {"schema": SCHEMA, "runner": runner(),
              "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
              "ref": a.ref, "ref_sha": git("rev-parse", "--verify", "-q", a.ref, check=False).strip() or None,
              "days": []}
    cache = load_cache(a.cache) if a.cache else {}
    kept = {}
    for spec in a.specs:
        path, key, hit = spec.replace(os.sep, "/"), None, None
        try:
            key = a.cache and replay_key(spec, a.ref)
            hit = key and cache.get(path)
            if hit and hit.get("key") == key:
                day = dict(hit["record"], reused_from=hit["replayed"])
                print(f"reused  {path}: replayed {hit['replayed']}, nothing it reads has changed since")
            else:
                hit = None
                day = check_spec(spec, a.ref, a.criterion)
        except Exception as e:  # what the checker did not foresee still leaves a report
            key = None
            day = {"spec": {"path": path}, "checks": [
                {"id": f"{os.path.basename(spec)}/runner", "kind": "runner", "criterion": None, "sha": None,
                 "status": "error", "label": os.path.basename(spec), "diagnostic": f"{type(e).__name__}: {e}"}]}
        # Only a replay that held is kept: a failed or unrun check runs again next time.
        if key and all(c["status"] in ("passed", "not_applicable") for c in day["checks"]):
            kept[path] = {"key": key, "replayed": hit["replayed"] if hit else report["generated"],
                          "record": {k: v for k, v in day.items() if k != "reused_from"}}
        report["days"].append(day)
        for c in day["checks"]:
            print(f"{MARK[c['status']]}  {c['label']}" + (f" → {c['diagnostic']}" if c["diagnostic"] else ""))
    checks = [c for d in report["days"] for c in d["checks"]]
    report["summary"] = {k: {s: sum(c["kind"] == k and c["status"] == s for c in checks) for s in MARK}
                         for k in dict.fromkeys(c["kind"] for c in checks)}
    if a.json:
        with open(a.json, "w", encoding="utf-8", newline="\n") as f:
            f.write(report_text(report))
    if a.cache:
        with open(a.cache, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"schema": SCHEMA, "specs": kept}, f, ensure_ascii=False)
    failed = sum(c["status"] == "failed" for c in checks)
    errors = sum(c["status"] == "error" for c in checks)
    print(", ".join(f"{n} {w}" for n, w in ((failed, "failed"), (errors, "could not run")) if n)
          or "all evidence holds")
    return 1 if failed or errors else 0


if __name__ == "__main__":
    sys.exit(main())
