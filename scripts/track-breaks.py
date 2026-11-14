"""Replay a track PR's breaks, and the day's earlier tracks', on the PR's code, before the close does.

    python scripts/track-breaks.py --branch day-NN/track-x-slug --body <body.md> [--earlier <body.md> ...]
    python scripts/track-breaks.py --branch day-NN/track-x-slug --pr <n>   # bodies read with gh

A track PR records each break as a `manifest: {...}` line and its `broken: <what> → <report>` line
(scripts/break.py prints both). Until now they were first replayed at the close, on Linux, after
every track had merged, and Days 06 to 08 failed 16 lines there: a report that held Windows-only
text (D06.23, D07.40, D08.83), or a find that a later track had changed (D07.39, D08.82). Here
each entry runs through scripts/break.py --replay on the code checked out (in CI, the PR's merge
commit, on Linux), as scripts/evidence.py does at the close, and its report is compared with the
recorded one. The day's earlier merged track PRs' entries run too, so a track that changes another's
find fails, not the close; an entry in this PR's body with the same <what> replaces theirs: re-run
the break on this PR's code and record its lines here.

Earlier Days' breaks are checked too, on every branch: each `broken:` line of an in-force criterion
(behaviour-index.py) of a closed Day, one whose break file sits in specs/breaks, other than the
branch's own Day. Their finds went stale unseen until the re-check after a merge said "break no
longer applies" (ten of them, fixed in #184). Two tiers: each find must still occur once in its
file (static, cheap), and the break runs only when the PR touches its file, its test module, its
Day's break file or its Day's spec (`git diff --name-only <base>`). The fix for a stale one is in
this PR: re-run the break with break.py and record its entry in specs/breaks/day-NN.json and its
`broken:` line in the Day's spec, as #184 did.

One line per break; exits 1 when one no longer applies or reports something else, 0 otherwise. A
branch that is not a day's track has no PR body to replay; its earlier Days' breaks are checked.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys

import evidence
from evidence import BROKEN, PR_SUFFIX, joined, normal, run_break

_spec = importlib.util.spec_from_file_location(
    "behaviour_index", os.path.join(os.path.dirname(os.path.abspath(__file__)), "behaviour-index.py"))
bi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bi)

TRACK = re.compile(r"^day-(\d+)/track-")
DAY = re.compile(r"^day-(\d+)/")
TEST_ARG = re.compile(r"^(tests(?:\.\w+)*?\.test_\w+)(?:\.|$)")
MANIFEST = re.compile(r"^\s*manifest: (\{.*\})\s*$")


def entries(body):
    """{what: entry} from a PR body, each manifest entry with the report its `broken:` line gives;
    a manifest line whose broken: line is missing is kept with no report."""
    lines = joined(body.replace("\r\n", "\n").split("\n"))
    reports = {m.group(1).strip("` "): m.group(2).strip().rstrip("`") for m in map(BROKEN.match, lines) if m}
    found = {}
    for line in lines:
        m = MANIFEST.match(line.strip("`"))
        if not m:
            continue
        try:
            entry = json.loads(m.group(1))
        except ValueError:
            found[f"<unparsed line {line.strip()[:60]}>"] = {"unparsed": True}
            continue
        found[entry["what"]] = dict(entry, report=reports.get(entry["what"]))
    return found


def replay(found, root="."):
    """[(ok, line)] for each entry, run at root."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    out = []
    for what, entry in found.items():
        if entry.get("unparsed"):
            out.append((False, f"unparsed: {what}: copy the manifest line from the raw body, as break.py printed it"))
            continue
        if entry["report"] is None:
            out.append((False, f"no broken: line: {what}: paste it beside its manifest line"))
            continue
        status, got = run_break({k: v for k, v in entry.items() if k not in ("report", "pr")}, root, env)
        if status == "reported" and normal(got) == normal(entry["report"]):
            out.append((True, f"replays: {what}"))
        elif status == "reported":
            out.append((False, f"differs: {what}: recorded {PR_SUFFIX.sub('', entry['report'])!r}, "
                               f"replayed {got!r}{' (from #' + str(entry['pr']) + ')' if 'pr' in entry else ''}"))
        else:
            out.append((False, f"{status}: {what}: {got}{' (from #' + str(entry['pr']) + ')' if 'pr' in entry else ''}"))
    return out


def earlier_days(specs, own=None):
    """[(day, cid, what, entry or None, report, spec path)] for each `broken:` line of an in-force
    ticked criterion of each closed Day but own, in order."""
    breaks = os.path.join(specs, "breaks")
    if not os.path.isdir(breaks):
        return []
    in_force = {r["id"] for r in bi.collect(specs)[0] if r["state"] == "in force"}
    out = []
    for name in sorted(os.listdir(breaks)):
        m = re.fullmatch(r"day-(\d+)\.json", name)
        if not m or m.group(1) == own:
            continue
        day = m.group(1)
        paths = [p for p in sorted(os.listdir(specs)) if p.startswith(f"day-{day}-") and p.endswith(".md")]
        if not paths:
            continue
        with open(os.path.join(breaks, name), encoding="utf-8") as f:
            recorded = {e["what"]: e for e in json.load(f)}
        with open(os.path.join(specs, paths[0]), encoding="utf-8") as f:
            text = f.read()
        for cid, lines in evidence.criteria(text).items():
            if not lines[0].startswith("- [x]") or cid not in in_force:
                continue
            for what, report in (b.groups() for line in joined(lines) if (b := BROKEN.match(line))):
                if what != "none":
                    out.append((day, cid, what, recorded.get(what), report, f"specs/{paths[0]}"))
    return out


def stale(entry, root):
    """Why entry's break no longer applies to the code at root, or None."""
    path = os.path.join(root, entry["file"])
    if not os.path.isfile(path):
        return f"{entry['file']} is gone"
    with open(path, "rb") as f:
        count = f.read().count(entry["find"].encode())
    return None if count == 1 else f"the find occurs {count} times in {entry['file']}"


def watched(entry, day, spec):
    """The paths whose change makes an earlier Day's break run, not only its static check."""
    paths = {entry["file"], f"specs/breaks/day-{day}.json", spec}
    for arg in entry["command"]:
        m = TEST_ARG.match(arg)
        paths.add(m.group(1).replace(".", "/") + ".py" if m else arg)
    return paths


def changed_since(base, root="."):
    """The paths changed between base and the working tree; none when base is None."""
    if base is None:
        return set()
    run = subprocess.run(["git", "diff", "--name-only", base], cwd=root, capture_output=True, text=True,
                         encoding="utf-8")
    if run.returncode:
        raise SystemExit(f"track-breaks: cannot diff against {base}: {run.stderr.strip()}")
    return set(run.stdout.split())


def default_base(root="."):
    """Where HEAD left main, or None when there is no main to diff against."""
    run = subprocess.run(["git", "merge-base", "main", "HEAD"], cwd=root, capture_output=True, text=True)
    return run.stdout.strip() or None


RAN = ("replays:", "differs:", "failed:", "error:")


def check_earlier(items, changed, root="."):
    """[(ok, line)] for each earlier Day's break: the static check always, the run when changed touches it."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    out = []
    for day, cid, what, entry, report, spec in items:
        label = f"{what} ({cid})"
        if entry is None:
            out.append((False, f"no arguments: {label}: no entry in specs/breaks/day-{day}.json"))
            continue
        if "at" in entry:
            out.append((True, f"pinned: {label}: runs at {entry['at']}, in the close's replay"))
            continue
        why = stale(entry, root)
        if why:
            out.append((False, f"no longer applies: {label}: {why}: re-record it in this PR "
                               f"(specs/breaks/day-{day}.json and {spec})"))
            continue
        if not watched(entry, day, spec) & changed:
            out.append((True, f"applies: {label}"))
            continue
        if entry.get("posix_only") and os.name == "nt":
            out.append((True, f"applies: {label}: a POSIX-only break, not run on Windows"))
            continue
        status, got = run_break(entry, root, env)
        if status == "reported" and normal(got) == normal(report):
            out.append((True, f"replays: {label}"))
        elif status == "reported":
            out.append((False, f"differs: {label}: recorded {PR_SUFFIX.sub('', report)!r}, replayed {got!r}"))
        else:
            out.append((False, f"{status}: {label}: {got}"))
    return out


def from_github(day, pr):
    """(this PR's body, [(number, body)] of the day's merged track PRs) through gh."""
    gh = lambda *a: subprocess.run(["gh", *a], capture_output=True, text=True, encoding="utf-8", check=True).stdout
    body = json.loads(gh("pr", "view", str(pr), "--json", "body"))["body"]
    merged = json.loads(gh("pr", "list", "--state", "merged", "--limit", "200", "--json", "number,headRefName,body"))
    earlier = [(p["number"], p["body"]) for p in merged if p["headRefName"].startswith(f"day-{day}/track-")]
    return body, sorted(earlier)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--branch", required=True)
    p.add_argument("--body", help="this PR's body, in a file")
    p.add_argument("--earlier", nargs="*", default=[], help="the day's merged track PRs' bodies, in files")
    p.add_argument("--pr", type=int, help="this PR's number: read its body and the earlier ones with gh")
    p.add_argument("--base", help="what the PR's changes are diffed against (default: where HEAD left main)")
    p.add_argument("--specs", default="specs", help="the specs folder, for earlier Days' breaks")
    a = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    track = TRACK.match(a.branch)
    results = []
    if not track:
        print(f"track-breaks: {a.branch} is not a day's track: no PR body to replay")
    else:
        if a.pr is not None:
            body, earlier = from_github(track.group(1), a.pr)
        elif a.body:
            read = lambda path: open(path, encoding="utf-8").read()
            body, earlier = read(a.body), [(None, read(path)) for path in a.earlier]
        else:
            p.error("give --body or --pr")
        found = {}
        for number, text in earlier:
            found.update({w: dict(e, pr=number) if number else e for w, e in entries(text).items()})
        found.update(entries(body))
        results = replay(found)
        for _, line in results:
            print(line)
        bad = sum(not ok for ok, _ in results)
        print(f"track-breaks: {len(results) - bad} of {len(results)} breaks replay on this code")
    own = DAY.match(a.branch)
    later = check_earlier(earlier_days(a.specs, own and own.group(1)), changed_since(a.base or default_base()))
    for _, line in later:
        print(line)
    late_bad = sum(not ok for ok, _ in later)
    ran = sum(line.startswith(RAN) for _, line in later)
    print(f"track-breaks: {len(later) - late_bad} of {len(later)} earlier Days' breaks still apply, "
          f"{ran} run because this change touches them")
    return 1 if late_bad or any(not ok for ok, _ in results) else 0


if __name__ == "__main__":
    sys.exit(main())
