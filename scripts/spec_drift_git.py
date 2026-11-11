"""spec-drift.py's reading of git and GitHub: commands, merges, branches, PRs, runs and parked issues."""

import collections
import datetime
import json
import os
import re
import subprocess
import sys

from spec_drift_common import (
    CACHE,
)


# The most gh is asked for: a list that comes back this long may have been cut, and nothing else says so.
PR_LIMIT = 500
RUN_LIMIT = 5000
# GitHub's API returns at most this many for a filtered run list, so a list that long may be cut.
GH_CAP = 1000


def run(*args):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=True).stdout


def gh_list(limit, *args):
    """A gh list call's JSON, refused when it is as long as the limit: what was cut is not known."""
    items = json.loads(run("gh", *args, "--limit", str(limit)))
    if len(items) >= limit:
        raise SystemExit(f"gh {' '.join(args[:2])} returned its limit of {limit}: some are missing, raise it")
    if len(items) == GH_CAP:
        raise SystemExit(f"gh {' '.join(args[:2])} returned {GH_CAP}, the most GitHub gives for it: some may be missing")
    return items


def at_commits(*args):
    """git with only commit SHAs for revisions: the output is fixed, so it comes from the cache."""
    key = "\0".join(args)
    out = CACHE.setdefault("git", {}).get(key)
    if out is None:
        out = CACHE["git"][key] = run("git", *args)
    return out


class Blobs:
    """One git cat-file process for every file read, instead of one git show each. Use as
    `with Blobs() as blobs:`, so the process is closed however the block ends."""

    def __enter__(self):
        self.proc = subprocess.Popen(["git", "cat-file", "--batch"], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return self

    def __exit__(self, *exc):
        for f in (self.proc.stdin, self.proc.stdout):
            try:
                f.close()
            except OSError:
                pass
        self.proc.wait()

    def read(self, sha, path):
        try:
            self.proc.stdin.write(f"{sha}:{path}\n".encode())
            self.proc.stdin.flush()
            header = self.proc.stdout.readline().split()
        except (OSError, ValueError) as e:
            raise RuntimeError(f"git cat-file failed reading {path} at {sha}: {e}") from e
        if header[-1:] == [b"missing"]:
            return ""
        if len(header) != 3 or not header[2].isdigit():
            said = b" ".join(header).decode("utf-8", "replace") or "nothing (the process ended)"
            raise RuntimeError(f"git cat-file failed reading {path} at {sha}: it said {said}")
        body = self.proc.stdout.read(int(header[2]))
        self.proc.stdout.read(1)
        return body.decode("utf-8", "replace")


def day_of(path):
    m = re.search(r"day-(\d+)", path)
    return int(m.group(1)) if m else None


TITLED_TRACK = re.compile(r"\bDay (\d{2}) track ([0-9A-Za-z]+):")


def day_branch(pr):
    """The branch a PR is read by. One whose branch names no day but whose title names its track
    is read as that track's branch: #321, Day 28's Track D, was opened from
    `claude/focused-bell-qqwqdx`, and the day showed D unmerged. CI runs stay on the real branch."""
    branch = pr["headRefName"]
    m = None if day_of(branch) else TITLED_TRACK.search(pr.get("title") or "")
    return f"day-{m.group(1)}/track-{m.group(2).lower()}-titled" if m else branch


def own_day(pr):
    """The Day a pull request belongs to, on every graph: the one its branch names (as day_branch reads it),
    wherever it merged. None for area work (dashboard/, tooling/, specs/...), which is no Day's."""
    m = re.match(r"day-(\d+)/", day_branch(pr))
    return int(m.group(1)) if m else None


def ci_pushes(runs):
    """Per branch: the commits CI ran on for a pull request, and those that failed a workflow."""
    shas, failed = collections.defaultdict(set), collections.defaultdict(set)
    for r in runs:
        if r["event"] == "pull_request":
            shas[r["headBranch"]].add(r["headSha"])
            if r["conclusion"] == "failure":
                failed[r["headBranch"]].add((r["headSha"], r["workflowName"]))
    return {b: (len(s), len({sha for sha, _ in failed[b]}), sorted({w for _, w in failed[b]})) for b, s in shas.items()}


def run_spans(on):
    """The stretches in which a branch's workflow runs were running, as [start, end, failed] in
    order: runs that overlap or touch are one stretch, and the time between two pushes is in none."""
    out = []
    for r in sorted(on, key=lambda r: r["createdAt"]):
        start, end, failed = r["createdAt"], r.get("updatedAt") or r["createdAt"], int(r.get("conclusion") == "failure")
        if out and start <= out[-1][1]:
            out[-1][1], out[-1][2] = max(out[-1][1], end), out[-1][2] + failed
        else:
            out.append([start, end, failed])
    return out


PARK_LIMIT = 500
PARK_SLACK = datetime.timedelta(minutes=10)  # a park's issue is opened after its line is in the run log


def parked_issues(note=None):
    """The project's issues labelled "parked", open and closed, by number: the driver opens one for each
    park and the maintainer closes it to let the driver go on, so how long a park waited is GitHub's to
    say. None when they cannot be read: with no GitHub remote (the note), or when gh refuses."""
    if note:
        return None
    try:
        listed = gh_list(PARK_LIMIT, "issue", "list", "--label", "parked", "--state", "all", "--json",
                         "number,title,url,createdAt,closedAt")
    except subprocess.CalledProcessError as e:
        print(f"The parked issues could not be read (gh issue list: {(e.stderr or '').strip()})", file=sys.stderr)
        return None
    return [dict(number=i["number"], title=i["title"], url=i["url"], opened=i["createdAt"], closed=i.get("closedAt"))
            for i in sorted(listed, key=lambda i: i["number"])]


def moment(stamp):
    """A UTC time as GitHub and the driver's run log write it, or None when it is not one: a time
    with no zone is none, since it cannot be set against one that has it."""
    try:
        at = datetime.datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else None


def park_issue(park, issues):
    """The number of the issue a park in the run log opened, or commented on when its reason was parked
    and open already: the issue titled with the park's line (its first 200 characters, as the driver
    cuts it) that was not closed before the park and was opened no later than PARK_SLACK after it; the
    newest of those, or None."""
    at, line = moment(park.get("at")), park.get("line")
    if at is None or not isinstance(line, str):
        return None
    found = None
    for i in issues:
        opened, closed = moment(i["opened"]), moment(i["closed"]) if i["closed"] else None
        if i["title"] != line[:200] or opened is None or opened > at + PARK_SLACK or (closed and closed < at):
            continue
        found = i if found is None or opened > moment(found["opened"]) else found
    return found["number"] if found else None


def step_kind(k, branch):
    """The step a merged PR was: its kind, with a tooling/ area branch taken out of other."""
    return "tooling" if k == "other" and branch.lower().startswith("tooling/") else k


def hours_open(pr):
    """Hours from a PR's opening to its merge, or None when GitHub gave either time as empty: the
    waiting is the maintainer's review, which leaves nothing in git."""
    opened, merged = pr.get("createdAt"), pr.get("mergedAt")
    if not (opened and merged):
        return None
    at = lambda s: datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return round((at(merged) - at(opened)).total_seconds() / 3600, 2)


def kind(title, branch, files=None):
    """What a merge was. A spec change must touch the spec (a day spec or plan.md) when its files
    are known: #55 changed the spec rules and #59 and #107 the dashboard, none of them a spec."""
    t, b = title.lower(), branch.lower()
    if ("spec change" in t or "plan change" in t or re.match(r"day-\d+/spec", b)
            or b.startswith(("specs/", "plan/"))):
        if files is None or any(f == "plan.md" or day_of(f) for f in files):
            return "spec"
        return "other"
    if re.search(r"\btick", t) or "close" in b:  # the word: #96's "yardsticks" made a dashboard PR a close
        return "close"
    if "track" in b or "track" in t:
        return "code"
    return "other"


def snapshots(prs):
    """Each commit on main's first-parent history, oldest first: a PR's merge or squash, or a commit with no PR."""
    if subprocess.run(["git", "rev-parse", "--verify", "-q", "main"], capture_output=True).returncode:
        sys.exit("spec-drift.py reads the branch main, and this repository has none: git branch -m main")
    out = []
    for line in run("git", "log", "--first-parent", "main", "--reverse",
                    "--format=%h|%ad|%P|%s", "--date=short").splitlines():
        sha, date, parents, subject = line.split("|", 3)
        m = re.match(r"Merge pull request #(\d+)", subject)
        if not m and len(parents.split()) == 1:
            squash = re.search(r" \(#(\d+)\)$", subject)
            if squash and prs.get(int(squash.group(1)), {}).get("state") == "MERGED":
                m = squash
        p = prs.get(int(m.group(1)), {}) if m else {}
        title = p.get("title", subject)
        out.append(dict(sha=sha, date=date, pr=int(m.group(1)) if m else None, title=title,
                        branch=p.get("headRefName", "")))
    return out


def owners_prs(listed, owner):
    """Only PRs the repository's owner opened. Anyone can open a PR on a public repository, and its
    body and title would reach the next step and an agent's context through this page (SO-12)."""
    return [p for p in listed if (p.get("author") or {}).get("login") == owner]


NO_REMOTE = "No GitHub remote: read from git only, so there are no PRs and the PR panels are empty."


def github():
    """The owner's PRs and the CI runs, and a note: with no GitHub remote, none of either and the
    note says so, so a new repository gets a page from git alone."""
    try:
        owner = run("gh", "repo", "view", "--json", "owner", "-q", ".owner.login").strip()
    except subprocess.CalledProcessError as e:
        print(f"{NO_REMOTE} (gh repo view: {(e.stderr or '').strip()})", file=sys.stderr)
        return [], [], NO_REMOTE
    listed = owners_prs(gh_list(PR_LIMIT, "pr", "list", "--state", "all", "--json",
                                "number,title,headRefName,state,url,body,author,createdAt,mergedAt"), owner)
    runs = gh_list(RUN_LIMIT, "run", "list", "--json", "headBranch,headSha,conclusion,event,workflowName,createdAt,updatedAt")
    return listed, runs, None


def project_name():
    """The repository's name on GitHub; with no remote, its folder's."""
    try:
        return run("gh", "repo", "view", "--json", "name", "-q", ".name").strip()
    except subprocess.CalledProcessError:
        return os.path.basename(run("git", "rev-parse", "--show-toplevel").strip())
