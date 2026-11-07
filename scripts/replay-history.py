"""Whether each in-force criterion still holds at each merge on main: its breaks re-run on that merge's code.

    python scripts/replay-history.py [--out docs/dashboard/replay-history.json] [--since <sha>] [--ref main]

evidence.py replays a day at its own close commit; this replays the criteria on later code. For each
merge on --ref's first-parent line from --since on (read from --out after the first run) that has no
row for this platform yet, at a scratch worktree of that merge:

- a closing merge samples every in-force criterion (behaviour-index.py) of the days closed by then;
- a `day-NN/...` merge samples Day NN's criteria, once Day NN has closed (till then it waits);
- any other merge samples the criteria of the last day closed before it.

Each `broken:` line under a sampled criterion re-runs through break.py from specs/breaks/day-NN.json,
which runs the check clean first; a criterion with no `broken:` line runs its named tests clean. The
specs and breaks files are read as they stand now, so a corrected manifest corrects the history.
Each check gets one state:

- holds: the check passes clean and fails with the break in (a near miss: passes with it in);
- holds, never broken: the tests pass clean and no `broken:` line was ever recorded, so nothing shows
  they can fail;
- code broken: the check fails clean: the code no longer does what was promised;
- test weakened: the check passes with the break in, or its named test was removed;
- break no longer applies: the file is gone, or the find text no longer occurs exactly once;
- not applicable on this platform: a "posix_only" break, on Windows;
- not runnable: no recorded arguments, `broken: none`, nothing to run, or break.py refused to run;
- live only: `broken: none` under a criterion that names DRIVER_LIVE_CLI, a check on the installed
  Claude Code that has no replay;
- not yet in force: a merge before the day's close, where the named test or the edited code is not there yet.

A check is keyed by a hash of what it reads at the merge: the trees of tests/, driver/, hooks/ and
rules/, run-steps.py, the file a break edits and the files the named test modules name under scripts/
or the root, the entry, break.py, the platform and Python. A key already measured is copied, with
`reused_from`, not run again. Rows are written in a fixed order, one a line, with no times.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ev = load("evidence", "evidence.py")
bi = load("behaviour_index", "behaviour-index.py")
git = ev.git

OUT = "docs/dashboard/replay-history.json"
STATES = ["holds", "holds, never broken", "code broken", "test weakened", "break no longer applies",
          "not applicable on this platform", "not runnable", "live only", "not yet in force"]
NEVER_BROKEN = "holds, never broken"


def upgrade(row):
    """A row an older run wrote as "holds" with no break to check its teeth, as the state it now gets."""
    if row.get("state") == "holds" and (row.get("detail") or "").startswith("teeth unchecked"):
        return dict(row, state=NEVER_BROKEN)
    return row
READS = ["tests", "driver", "hooks", "rules", "run-steps.py", ".gitignore", "pyproject.toml", "requirements.txt"]
DAY_BRANCH = re.compile(r"^Merge pull request #\d+ from \S+?/day-(\d{2})/|^Day (\d{2}) ")
PR = re.compile(r"#(\d+)")
DOTTED = re.compile(r"^tests\.(\w+)\.(\w+)\.(test_\w+)$")
# A path a test module builds or names: ROOT / "scripts" / "spec-drift.py", or scripts/pr-names.py.
NAMED = re.compile(r'"(scripts|hooks|rules|docs|specs)"\s*/\s*"([\w.-]+)"|\b((?:scripts|specs|docs)/[\w./-]+\.\w+)')
PLATFORM = "windows" if os.name == "nt" else "linux" if sys.platform.startswith("linux") else sys.platform


def merges(ref, since):
    """(position, sha, subject) for each first-parent commit of ref from since on, oldest first."""
    out = git("log", "--first-parent", "--reverse", "--format=%H%x00%s", f"{since}^..{ref}").splitlines()
    first = int(git("rev-list", "--first-parent", "--count", since).strip())
    return [(first + i, *line.split("\0", 1)) for i, line in enumerate(out)]


def closes(ref):
    """{day: first-parent position of its close} for each closed day on ref."""
    out = {}
    for path in ev.closed_specs(ref):
        day = re.match(r"specs/day-(\d{2})-", path).group(1)
        out[day] = int(git("rev-list", "--first-parent", "--count", ev.close_commit(day, ref)).strip())
    return out


def sampled_days(n, subject, closed):
    """The days whose criteria a merge at position n samples, and "all" or "day"; None to wait."""
    done = sorted(d for d, at in closed.items() if at <= n)
    if any(at == n for at in closed.values()):
        return done, "all"
    m = DAY_BRANCH.match(subject)
    if m:
        day = m.group(1) or m.group(2)
        return ([day], "day") if day in closed else None
    before = [d for d in done if closed[d] < n]
    return before[-1:], "day"


def checks(specs, days):
    """(day, criterion, check name, entry or None, tests, report, live) for each sampled in-force
    criterion, in order; live when the criterion names DRIVER_LIVE_CLI."""
    in_force = {r["id"] for r in bi.collect(specs)[0] if r["state"] == "in force"}
    out = []
    for day in days:
        path = [p for p in os.listdir(specs) if p.startswith(f"day-{day}-") and p.endswith(".md")][0]
        with open(os.path.join(specs, path), encoding="utf-8") as f:
            text = f.read()
        breaks = os.path.join(specs, "breaks", f"day-{day}.json")
        recorded = {}
        if os.path.isfile(breaks):
            with open(breaks, encoding="utf-8") as f:
                recorded = {e["what"]: e for e in json.load(f)}
        for cid, lines in ev.criteria(text).items():
            if not lines[0].startswith("- [x]") or cid not in in_force:
                continue
            tests = sorted(set(ev.TEST.findall("\n".join(lines))))
            found = [m.groups() for line in ev.joined(lines) if (m := ev.BROKEN.match(line))]
            live = "DRIVER_LIVE_CLI" in "\n".join(lines)
            for what, report in found:
                out.append((day, cid, what, recorded.get(what), tests, report, live))
            if not found:
                out.append((day, cid, "tests", None, tests, None, live))
    return out


def order(cid):
    return tuple(int(x) for x in re.findall(r"\d+", cid))


def key(sha, entry, tests, pre):
    """What a check reads at the merge, hashed."""
    h = hashlib.sha256(json.dumps([entry, tests, pre, PLATFORM, platform.python_version()]).encode())
    paths = list(READS)
    if entry:
        paths.append(entry["file"])
        paths += [f"tests/{m.group(1)}.py" for a in entry["command"] if (m := DOTTED.match(a))]
    paths += [f"{mod.replace('.', '/')}.py" for cls, _ in tests if (mod := test_module(sha, cls))]
    for path in list(paths):
        if path.startswith("tests/") and path.endswith(".py"):
            source = git("show", f"{sha}:{path}", check=False)
            paths += ["/".join(p for p in m.groups()[:2]) if m.group(1) else m.group(3) for m in NAMED.finditer(source)]
    for path in sorted(set(paths)):
        h.update(f"\0{path}\0{git('rev-parse', '-q', '--verify', f'{sha}:{path}', check=False).strip()}".encode())
    with open(ev.BREAK, "rb") as f:
        h.update(f.read())
    return h.hexdigest()[:16]


def test_module(sha, cls):
    hit = git("grep", "-l", "-E", rf"^class {cls}\b", sha, "--", "tests", check=False).split()
    return hit[0].split(":", 1)[1][:-3].replace("/", ".") if hit else None


def classify(entry, tests, report, worktree, sha, pre, env):
    """(state, detail) of one check at the worktree of sha; pre: the merge comes before the day's close.
    A check that holds has a detail only when it reported other than the spec's `broken:` line."""
    missing = lambda why: ("not yet in force", why) if pre else ("test weakened", why)
    if entry is None and not tests:
        return "not runnable", "no test or break to replay"
    if entry is None:
        for cls, name in tests:
            if not ev.test_exists(sha, cls, name):
                return missing(f"{cls}.{name} not defined")
        names = [f"{test_module(sha, cls)}.{cls}.{name}" for cls, name in tests]
        run = subprocess.run([sys.executable, "-m", "unittest", *names], cwd=worktree, env=env,
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        if run.returncode == 0:
            return NEVER_BROKEN, "teeth unchecked: no broken: line"
        return "code broken", ev.normal(run.stderr.strip().splitlines()[-1] if run.stderr.strip() else "failed")
    for arg in entry["command"]:
        m = DOTTED.match(arg)
        if m and not ev.test_exists(sha, m.group(2), m.group(3)):
            return missing(f"{m.group(2)}.{m.group(3)} not defined")
    path = os.path.join(worktree, entry["file"])
    if not os.path.isfile(path):
        return ("not yet in force" if pre else "break no longer applies"), f"{entry['file']} is gone"
    with open(path, "rb") as f:
        count = f.read().count(entry["find"].encode())
    if count != 1:
        return ("not yet in force" if pre else "break no longer applies"), f"the find text occurs {count} times"
    if entry.get("posix_only") and os.name == "nt":
        return "not applicable on this platform", "a POSIX-only break"
    command = [ev.bash(), *entry["command"][1:]] if entry["command"][0] == "bash" else entry["command"]
    expect = ["--expect-stdout", entry["expect_stdout"]] if "expect_stdout" in entry else []
    run = subprocess.run([sys.executable, ev.BREAK, "--file", path, "--find", entry["find"], "--replace",
                          entry["replace"], "--what", entry["what"], "--cwd", worktree, *expect, "--", *command],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    lines = (run.stdout + run.stderr).strip().splitlines() or [f"break.py exited {run.returncode}"]
    said = ev.normal(lines[-1].split(" → ", 1)[-1] if run.returncode == 0 else lines[0])
    if run.returncode == 1 and lines[0].startswith(ev.PASSED):
        return ("holds", None) if entry.get("passes") else ("test weakened", said)
    if run.returncode == 0:
        if entry.get("passes"):
            return "code broken", "the near miss now fails"
        return "holds", None if report is None or said == ev.normal(report) else f"reported {said}"
    if "the check fails without the break" in lines[0]:
        return "code broken", said
    return "not runnable", said


def sample(n, sha, subject, mode, items, known, pre_of):
    """The rows of one merge: each check classified, or copied from a row with the same key."""
    rows, env = [], dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    worktree = None
    try:
        for day, cid, what, entry, tests, report, live in items:
            pre = n < pre_of[day]
            row = {"n": n, "merge": sha[:12], "pr": int(m.group(1)) if (m := PR.search(subject)) else None,
                   "sample": mode, "day": day, "criterion": cid, "check": what, "platform": PLATFORM}
            if entry is None and what == "none" and live:
                row.update(state="live only", detail="broken: none; the criterion names DRIVER_LIVE_CLI")
                rows.append(row)
                continue
            if entry is None and what != "tests":
                row.update(state="not runnable", detail="broken: none" if what == "none" else "no recorded arguments")
                rows.append(row)
                continue
            row["key"] = key(sha, entry, tests, pre)
            if row["key"] in known:
                old = known[row["key"]]
                row.update(state=old["state"], detail=old.get("detail"), reused_from=old["merge"])
            else:
                if worktree is None:
                    worktree = tempfile.mkdtemp(prefix="replay-")
                    git("worktree", "add", "--detach", worktree, sha)
                row["state"], row["detail"] = classify(entry, tests, report, worktree, sha, pre, env)
                known[row["key"]] = row
            rows.append(row)
    finally:
        if worktree:
            git("worktree", "remove", "--force", worktree, check=False)
            shutil.rmtree(worktree, ignore_errors=True)
    return [{k: v for k, v in r.items() if v is not None} for r in rows]


def write(path, since, rows):
    """The history, in a fixed order: one row a line, keys sorted."""
    rows = sorted(rows, key=lambda r: (r["n"], r["platform"], r["day"], order(r["criterion"]), r["check"]))
    body = ",\n".join("  " + json.dumps(r, sort_keys=True, ensure_ascii=False) for r in rows)
    text = (f'{{"schema": 1, "since": {json.dumps(since)}, "states": {json.dumps(STATES)}, "rows": [\n'
            f"{body}\n]}}\n" if rows else f'{{"schema": 1, "since": {json.dumps(since)}, "states": '
            f'{json.dumps(STATES)}, "rows": []}}\n')
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", default=OUT)
    p.add_argument("--since", help="the first merge to sample; read from --out once it exists")
    p.add_argument("--ref", default="main")
    p.add_argument("--specs", default="specs")
    a = p.parse_args(argv)
    old = {"rows": []}
    if os.path.isfile(a.out):
        with open(a.out, encoding="utf-8") as f:
            old = json.load(f)
    since = a.since or old.get("since")
    if not since:
        p.error("--since is needed until --out exists")
    since = git("rev-parse", since).strip()[:12]
    rows = [upgrade(r) for r in old["rows"]]
    known = {r["key"]: r for r in rows if "key" in r and "reused_from" not in r}
    done = {(r["n"], r["platform"]) for r in rows}
    closed = closes(a.ref)
    for n, sha, subject in merges(a.ref, since):
        days = sampled_days(n, subject, closed)
        if (n, PLATFORM) in done or not days or not days[0]:
            continue
        new = sample(n, sha, subject, days[1], checks(a.specs, days[0]), known, closed)
        print(f"{sha[:7]} {days[1]} {len(new)} checks: " + ", ".join(
            f"{s} {c}" for s in STATES if (c := sum(r["state"] == s for r in new))), flush=True)
        rows += new
    write(a.out, since, rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
