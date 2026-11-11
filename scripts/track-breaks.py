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

One line per break; exits 1 when one no longer applies or reports something else, 0 otherwise. A
branch that is not a day's track has nothing to replay and passes.
"""
import argparse
import json
import os
import re
import subprocess
import sys

from evidence import BROKEN, PR_SUFFIX, joined, normal, run_break

TRACK = re.compile(r"^day-(\d+)/track-")
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
    a = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    track = TRACK.match(a.branch)
    if not track:
        print(f"track-breaks: {a.branch} is not a day's track: nothing to replay")
        return 0
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
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
