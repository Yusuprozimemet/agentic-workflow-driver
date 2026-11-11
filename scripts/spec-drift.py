"""Measure how the spec and the code move against each other, merge by merge.

Writes one JSON file for the migration dashboard: gap and name coverage per merge on
main, and each day's status, tracks and criteria. Needs git, the gh CLI and numpy.

    python scripts/spec-drift.py --out data.json
    python scripts/spec-drift.py --build dashboard.html  # docs/dashboard/ as one file, data inlined

Gap: angle between spec and code over the code-like names the specs put in backticks, counted in
the specs and in the code (Markdown, data/, screenshots, this dashboard and comment lines left
out: a comment naming a thing is not the thing). A code file or folder whose name is a spec name
counts once, at its path: a spec cites a test by its file. Python's own names (ImportError) are not
spec names. Each merge's gap uses only the names the specs had used by then, so a later spec does
not move an earlier point.

The angle needs a reference to be read. Two vectors of counts are never negative, so they sit
well under 90° even when they have nothing to do with each other. Gap chance is the gap to the
same code counts shuffled across the names (the mean and 95% band of CHANCE_DRAWS, seeded): a gap near it says
the code uses the spec's names in no particular proportion. The angle is the secondary reading;
two plain set figures come first. Name coverage: of the names the specs use at a merge, the share
the code has. Jaccard: the names in both, over the names in either (a name the specs have dropped
but the code keeps counts against it). Names kept: that other direction alone, how many names the
specs once used and have dropped that the code still has. Names retired: of the names the specs
use that the code lacks, those it had at an earlier merge.

Per merge, the gap read against chance (what the dashboard draws):
  gap_excess: the gap less its chance value, so zero is chance; gap_excess_band: the 95% band of
  the shuffles around that value; gap_percentile: the share of the shuffles the gap sits above.
  class_coverage: of the reached names, the share in the code, by class (prod, test, flags);
  class_names: the named names per class, and the flags the specs name, counted apart as they
  do not enter the gap. A test helper found only in test files counts as a test name.
  names_added, names_dropped: per class, the names the specs use at this merge and not the one
  before, and the other way round (None at the origin). The dashboard plots each spec-change
  PR's names added against its step on gap_excess.

Boundaries: for the services the project file names, how much of their main source has left the
monolith for services/, and how many imports still cross from one service's packages into
another's. Both are read from the tree, like the gap; neither depends on what a day ticked.

The project file, spec-drift.config.json at the root, holds what git cannot tell about this
repository, every field optional: tests renamed to another stem and directories moved, by PR
(`renamed`, `moved`: [pr, old, new]), the directories a Verify block may cd into (`verify_bases`),
the packages each service takes under `package_root` (`services`), and the infra workflow's file
(`infra_workflow`; none, and gh is not asked for its runs).
"""
import argparse
import ast
import builtins
import collections
import datetime
import fnmatch
import functools
import hashlib
import importlib.util
import json
import os
import platform
import posixpath
import re
import shlex
import subprocess
import sys
import tempfile

import numpy as np

# The modules spec-drift.py is split into sit beside it, also when a test loads it by path.
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from spec_drift_common import *  # noqa: F403
from spec_drift_git import *  # noqa: F403
from spec_drift_specs import *  # noqa: F403
from spec_drift_handoffs import *  # noqa: F403
from spec_drift_data import *  # noqa: F403


# What every figure built on the backticked names cannot see; the dashboard lists these as written.
CAVEATS = [
    "Gap, name coverage and Jaccard see only identifiers the specs put in backticks: a name written "
    "in plain prose is not counted.",
    "They match names, not meaning: prose is not understood, so a spec can name a thing the code has "
    "and still describe it wrongly.",
    "A name a spec says should disappear still counts as shared vocabulary while the code has it.",
    "Name coverage counts test and tooling files as code.",
    "A code file or folder named after a spec name counts as that name in the code; Python's own "
    "names, such as ImportError, are not spec names.",
    "Production name coverage counts only files the path rules call production: a path, not proof "
    "that the file runs in the product. Test and tool names may legitimately be absent from it.",
    "The clock graph shows the clock of the machine that last ran scripts/token-usage.py: its sessions "
    "are stamped with its offset, and GitHub's times are moved to it. A session on another machine is not drawn.",
    "The clock graph draws only what leaves a time: a session's transcript, a pull request, its checks, a merge. "
    "A session is busy while it writes and while it waits on a command it ran. The maintainer's reading, thinking "
    "and typing leave no time, and neither does a command sent to the background, one run outside a session, "
    "or a check that runs after a merge.",
    "Every dollar here is what the tokens would cost on the pay-per-token API at list prices, counted from this "
    "repository's sessions on the maintainer's computer. It is not what was paid: a subscription costs the same "
    "whatever was used. A date with no cost is a date with no session in this repository.",
    "A yardstick's figure for a Day covers everything merged between the close before it and its own, whichever "
    "Day the work belonged to.",
]


# The files this script is split into, beside it: a change to any of them starts the cache over
# (load_cache) and counts as the script edited (provenance).
SOURCES = ("spec-drift.py", "spec_drift_common.py", "spec_drift_git.py", "spec_drift_specs.py",
           "spec_drift_handoffs.py", "spec_drift_data.py")


def load_cache(path):
    version = hashlib.sha256()
    for name in SOURCES:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name), "rb") as f:
            version.update(f.read().replace(b"\r\n", b"\n"))
    version = version.hexdigest()
    try:
        with open(path, encoding="utf-8") as f:
            cached = json.load(f)
    except (OSError, ValueError):
        cached = {}
    CACHE.clear()
    CACHE.update(cached if cached.get("version") == version else dict(version=version))


def save_cache(path):
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(CACHE, f, separators=(",", ":"))
    os.replace(path + ".tmp", path)


def code_like(tok):
    """Whether a backticked token is a code name. One ending in "_" is a pattern's prefix (`aws_ecs_*`), not a name.
    Nor is one of Python's own (ImportError): a spec cites it for a failure, not for the code to hold."""
    if tok.endswith("_") or tok in PYTHON_NAMES:
        return False
    return bool(re.search(r"[a-z][A-Z]", tok)) or ("_" in tok.strip("_") and tok.lower() == tok)


WORK_KINDS = ("spec", "context", "prod", "test", "tooling")
FIXTURE_PATH = re.compile(r"(^|/)tests?/fixtures/")  # counted as test, left out of the tests-per-line ratio
PLACES = ("prod", "test", "tooling", "other")  # where a code name was found: a work kind, or other for the rest
NOT_WRITTEN = re.compile(r"(^|/)package-lock\.json$|^docs/dashboard/(token-usage|refusals|gates)\.json$|^docs/dashboard/deployment\.json$|^screenshots/")


def renamed_to(path):
    """numstat writes a moved file as src/{a => b}/X.java or a => b; its lines count where it went."""
    path = re.sub(r"\{[^{}]* => ([^{}]*)\}", r"\1", path)
    return path.split(" => ")[-1].replace("//", "/")


def work_kind(path):
    """Which box a changed file's lines go in; the first rule that matches wins. None: generated
    by a tool, not written, so not counted. A path no rule names is prod: the package, and also
    root files such as a config. experiments/ is tooling: E1's cases copy spec text, and as prod
    they raised production name coverage at #30 with no product code changed."""
    if NOT_WRITTEN.search(path):
        return None
    if path == "plan.md" or path.startswith("specs/"):
        return "spec"
    if path.endswith(".md") or path.startswith(".claude/") or (path.startswith("docs/")
                                                               and not path.startswith("docs/dashboard/")):
        return "context"
    if TEST_PATH.search(path):
        return "test"
    if path.startswith(("scripts/", ".github/", "docs/dashboard/", "kit/", "experiments/")):
        return "tooling"
    return "prod"


def place_of(path):
    """Where a code name was found: the file's work_kind, or other for any box not in PLACES."""
    w = work_kind(path)
    return w if w in PLACES else "other"


def recurrence(days):
    """How many Defect lines repeat an earlier defect: a same-as: naming the ID of a Defect line from
    before it. A malformed, unknown, duplicate or later ID is a problem, reported, never counted."""
    key = lambda i: tuple(map(int, DEFECT_ID.fullmatch(i).groups()))
    lines = [(d["day"], x) for d in sorted(days, key=lambda d: d["day"]) for x in d.get("defects", [])]
    known = {x["id"] for _, x in lines if x["id"] and not x["problem"]}
    found, problems, seen = [], [], set()
    for day, x in lines:
        if x["problem"] or not x["id"]:
            if x["problem"] or x["same_as"]:
                problems.append(x["problem"] or f"Day {day}: a Defect line with same-as: {x['same_as']} has no ID")
            continue
        if x["id"] in seen:
            problems.append(f"Day {day}: Defect ID {x['id']} is used twice")
            continue
        seen.add(x["id"])
        if not x["same_as"]:
            continue
        why = ("is not an ID like D21.2" if not DEFECT_ID.fullmatch(x["same_as"])
               else "names no Defect line" if x["same_as"] not in known
               else "is not an earlier defect" if key(x["same_as"]) >= key(x["id"]) else None)
        if why:
            problems.append(f"{x['id']}: same-as: {x['same_as']} {why}")
        else:
            found.append(dict(id=x["id"], same_as=x["same_as"]))
    return dict(defects=len(lines), with_id=len(known), recurrences=found, problems=problems)


def break_state(body, number):
    """What a PR description says about breaking the code on purpose: "recorded", "none" (only
    `broken: none → <why>`), "silent", or "not measured" for a PR from before the line."""
    if number < BREAK_LINE_FROM_PR:
        return "not measured"
    if broke(body):
        return "recorded"
    return "none" if BREAK_LINE.search(body or "") else "silent"


def clock(prs, runs, sessions=None):
    """Graph 10's times: each merged PR's opening and merge, with the checks on its branch (their
    first start and last end, the stretches they were running in, how many workflow runs over how
    many pushes, and how many failed), beside this machine's stretches of work from
    docs/dashboard/sessions.json (scripts/token-usage.py). GitHub's times are UTC, as it gives them;
    the page moves them to the sessions' clock."""
    on_branch = collections.defaultdict(list)
    for r in runs:
        if r.get("event") == "pull_request" and r.get("createdAt"):
            on_branch[r["headBranch"]].append(r)
    out = []
    for p in sorted(prs.values(), key=lambda p: p["number"]):
        if p.get("state") != "MERGED":
            continue
        on = on_branch.get(p["headRefName"], [])
        checks = dict(start=min(r["createdAt"] for r in on), end=max(r.get("updatedAt") or r["createdAt"] for r in on),
                      runs=len(on), failed=sum(r.get("conclusion") == "failure" for r in on),
                      pushes=len({r.get("headSha") for r in on}), spans=run_spans(on)) if on else None
        out.append(dict(number=p["number"], day=own_day(p), kind=kind(p["title"], day_branch(p)),
                        branch=p["headRefName"], opened=p.get("createdAt"), merged=p.get("mergedAt"), checks=checks))
    return dict(prs=out, sessions=page_json("sessions.json") if sessions is None else sessions)


def verification(prs, runs):
    """Every merged PR: whether it recorded a break, how many of its pushes CI failed, its step and
    the hours it stayed open."""
    ci, out = ci_pushes(runs), []
    for p in sorted(prs.values(), key=lambda p: p["number"]):
        if p.get("state") == "MERGED":
            pushes, failed, failed_in = ci.get(p["headRefName"], (0, 0, []))
            k = kind(p["title"], day_branch(p))
            out.append(dict(number=p["number"], url=p.get("url"), day=own_day(p), kind=k, step=step_kind(k, p["headRefName"]),
                            hours=hours_open(p), breaks=break_state(p.get("body"), p["number"]), pushes=pushes,
                            failed=failed, failed_in=failed_in))
    return out


def other_group(branch):
    """The branch prefix used to split merges that are not day work."""
    if "/" not in branch:
        return "other"
    prefix = branch.split("/", 1)[0].lower()
    return prefix or "other"


def other_groups(rows):
    """Group other pull requests by branch prefix, keeping the largest three visible."""
    counts = collections.Counter(other_group(row["branch"]) for row in rows
                                 if row["pr"] and row["kind"] == "other")
    groups = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    if len(groups) > 4:
        groups = groups[:3] + [("other", sum(count for _, count in groups[3:]))]
    return [dict(name=name, count=count) for name, count in groups]


def angle(x, y):
    """None when either vector is all zeros: it has no direction, so no angle to the other."""
    nx, ny = np.linalg.norm(x), np.linalg.norm(y)
    if nx == 0 or ny == 0:
        return None
    return float(np.degrees(np.arccos(np.clip(x @ y / (nx * ny), -1, 1))))


def deg(a):
    return None if a is None else round(a, 2)


def band(angles):
    """The mean of a set of angles and the 95% interval they fall in, rounded; None if it is empty."""
    if not len(angles):
        return None
    return [round(float(v), 2) for v in (np.mean(angles), *np.percentile(angles, [2.5, 97.5]))]


def angles(X, y):
    """The angle between each row of X and y; the rows with no direction are left out."""
    nx, ny = np.linalg.norm(X, axis=1), np.linalg.norm(y)
    ok = nx > 0
    if ny == 0:
        return np.array([])
    return np.degrees(np.arccos(np.clip(X[ok] @ y / (nx[ok] * ny), -1, 1)))


def chance_draws(x, y, keep):
    """The angles between x and y with y's entries in keep shuffled among themselves, one per
    CHANCE_DRAWS shuffles; with fewer than two entries to shuffle, the one angle, or none. Seeded per
    call, so the same counts give the same draws at every merge."""
    idx, rng = np.flatnonzero(keep), np.random.default_rng(0)
    if len(idx) < 2:
        a = angle(x, y)
        return np.array([] if a is None else [a])
    Z = np.tile(y, (CHANCE_DRAWS, 1))
    # sorted first: only the counts matter, not their order
    Z[:, idx] = rng.permuted(np.tile(np.sort(y[idx]), (CHANCE_DRAWS, 1)), axis=1)
    return angles(Z, x)


def chance_angle(x, y, keep):
    """The chance draws of chance_draws as [mean, 2.5th, 97.5th percentile], or None with no angle."""
    return band(chance_draws(x, y, keep))


def percentile_in(draws, gap):
    """The share of draws below gap, half of those equal to it, as a percentage to one decimal;
    None with no gap or no draws."""
    if gap is None or not len(draws):
        return None
    return round(float((np.sum(draws < gap) + np.sum(draws == gap) / 2) / len(draws) * 100), 1)


def name_overlap(spec, code, known):
    """Name coverage and Jaccard over the names known at a merge: of the names the specs use, the
    share the code has; and the names in both over the names in either. None with nothing to divide.
    Last, the other direction: how many names the specs once used and have dropped, that the code keeps."""
    named, in_code = (spec > 0) & known, (code > 0) & known
    both, either = (named & in_code).sum(), (named | in_code).sum()
    return (round(float(both / named.sum()), 3) if named.any() else None,
            round(float(both / either), 3) if either else None,
            int((in_code & ~named).sum()))


NOT_CODE_DIRS = ("data", "screenshots", "docs/dashboard", "kit", "specs")
PYTHON_NAMES = frozenset(dir(builtins))


def is_code_path(path):
    """Whether a path is one the code counts read: the same files git grep reads, set by NOT_CODE_DIRS."""
    return not (path.endswith(".md") or posixpath.basename(path) == "package-lock.json"
                or any(path == d or path.startswith(d + "/") for d in NOT_CODE_DIRS))


def path_names(path):
    """The names a path gives: each folder's, and the file's without its extension."""
    *folders, file = path.split("/")
    return {p.lstrip(".") for p in (*folders, posixpath.splitext(file)[0])}


def code_names(line, index):
    """The vocabulary names on one line of code, or none if the line is a comment."""
    if COMMENT_LINE.match(line):
        return []
    return [w for w in WORDS.findall(COMMENT_TAIL.sub("", line)) if w in index]


def name_class(tok, places):
    """The class of a vocabulary name: "test" or "prod". A test helper found only in test files
    counts as a test name; places is the set of places the name is found in at the merge."""
    return "test" if TEST_NAME.search(tok) or (places and places <= {"test"}) else "prod"


def spec_flags(texts):
    """The flags the specs put in backticks, read as code_flags reads the code."""
    return {f for t in texts.values() for span in TICK.findall(t) for f in FLAG.findall(span)}


def name_steps(before, after):
    """The names a merge added to the specs and dropped from them, per class, against the merge
    before. Each side is (named, klass, flags): the mask of names the specs use, each name's class,
    and the set of flags. A dropped name takes its class from the merge before, where it was named."""
    (n0, k0, f0), (n1, k1, f1) = before, after
    added = {k: int((n1 & ~n0 & (k1 == k)).sum()) for k in ("prod", "test")}
    dropped = {k: int((n0 & ~n1 & (k0 == k)).sum()) for k in ("prod", "test")}
    added["flags"], dropped["flags"] = len(f1 - f0), len(f0 - f1)
    return added, dropped


def code_flags(sha, flags):
    """The flags, of those asked for, that the code at sha has. git grep reads it as code_counts
    does, comment lines left out; cached under the SHA with the flags asked, as sorted lists."""
    asked = sorted(flags)
    if not asked:
        return set()
    cached = CACHE.setdefault("flags", {}).get(sha)
    if cached is None or cached["asked"] != asked:
        out = subprocess.run(["git", "grep", "-h", "-I", "-F", "-f", "-", sha, "--", ".",
                              ":(exclude)*.md", ":(exclude)**/package-lock.json",
                              *(f":(exclude){d}" for d in NOT_CODE_DIRS)], input="\n".join(asked) + "\n",
                             capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        found = set()
        for line in out.splitlines():
            if not COMMENT_LINE.match(line):
                found.update(FLAG.findall(COMMENT_TAIL.sub("", line)))
        cached = CACHE["flags"][sha] = {"asked": asked, "found": sorted(found & set(asked))}
    return set(cached["found"])


def ranker(order):
    """A day's place in the run order: 0 (and plan.md) first, a day the order does not list after it by number."""
    pos = {d: i for i, d in enumerate(d for d in order if d not in PLACEHOLDERS)}
    return lambda d: -1 if not d else pos.get(d, len(pos) + d)


# The rules and the template are about specs, not specs: their examples are the source project's names.
NOT_SPECS = ("specs/README.md", "specs/_template.md")


def trajectory(snaps, blobs, order=()):
    """Gap and coverage per merge. Days compare by their place in the run order, so from
    Day 38 the unbuilt Days 17-37 are not reached; with no order, by number."""
    rank = ranker(order)
    for s in snaps:
        names = at_commits("ls-tree", "-r", "--name-only", s["sha"], "--", "plan.md", "specs").split()
        s["texts"] = {n: blobs.read(s["sha"], n) for n in names if n.endswith(".md") and n not in NOT_SPECS}
    first_seen = {}
    for i, s in enumerate(snaps):
        for t in s["texts"].values():
            for span in TICK.findall(t):
                for tok in IDENT.findall(span):
                    if code_like(tok):
                        first_seen.setdefault(tok, i)
    vocab = sorted(first_seen)
    index = {v: i for i, v in enumerate(vocab)}
    born = np.array([first_seen[v] for v in vocab])
    patterns = "\n".join(vocab) + "\n"

    def spec_counts(texts):
        c = np.zeros(len(vocab))
        for t in texts.values():
            for span in TICK.findall(t):
                for tok in IDENT.findall(span):
                    if tok in index:
                        c[index[tok]] += 1
        return c

    def code_counts(sha):
        """A merge's counts need only the names the specs had used by then (later ones are masked
        by born), and a SHA fixes its history, so counts cached under it stay right. kit/ is the
        starter cleanup's tooling and the source project's data, which a copy deletes: not this project's code.
        specs/ is the spec side, every file in it: its break manifests copy the spec's names, and
        counted as code they narrowed the gap at #25 with no code changed.
        One count vector per place, by the file's work_kind: prod, test, tooling, and other for
        any box else; summed, they are the all-code counts. The cache keeps each name's count per
        path, so a merge's lists can say where a name is; the second return is name -> paths."""
        cached = CACHE.setdefault("code", {}).get(sha)
        if cached is None:
            out = subprocess.run(["git", "grep", "-z", "-I", "-w", "-F", "-f", "-", sha, "--", ".",
                                  ":(exclude)*.md", ":(exclude)**/package-lock.json",
                                  *(f":(exclude){d}" for d in NOT_CODE_DIRS)], input=patterns,
                                 capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
            cached = {}
            for match in out.split("\n"):
                where, _, text = match.partition("\0")  # -z: "<sha>:<path>\0<line>"
                path = where.split(":", 1)[-1]
                for line in text.splitlines():  # as the lines were read before the path was kept
                    for tok in code_names(line, index):
                        cached.setdefault(tok, {}).setdefault(path, 0)
                        cached[tok][path] += 1
            # A spec cites a file by its path (`tests/test_config.py`): the file is the thing, though
            # no line holds its name. Each file or folder named so counts once, at its path.
            for path in at_commits("ls-tree", "-r", "--name-only", sha).splitlines():
                if not is_code_path(path):
                    continue
                for tok in path_names(path):
                    if tok in index:
                        cached.setdefault(tok, {}).setdefault(path, 0)
                        cached[tok][path] += 1
            CACHE["code"][sha] = cached
        counts = {p: np.zeros(len(vocab)) for p in PLACES}
        for tok, paths in cached.items():
            for path, n in paths.items() if tok in index else ():
                counts[place_of(path)][index[tok]] += n
        return counts, cached

    day, rows, ever, before = 0, [], np.zeros(len(vocab), dtype=bool), None
    for i, s in enumerate(snaps):
        touched = at_commits("diff", "--name-only", snaps[i - 1]["sha"], s["sha"], "--", "plan.md", "specs").split() if i else []
        s["kind"] = "origin" if s["pr"] is None else kind(s["title"], s["branch"], touched)
        m = re.match(r"day-(\d+)/", s["branch"])
        if m and s["kind"] in ("code", "close"):
            day = max(day, int(m.group(1)), key=rank)
        spec, (places, where) = spec_counts(s["texts"]), code_counts(s["sha"])
        code = sum(places.values())
        reached_texts = {f: t for f, t in s["texts"].items() if day_of(f) and rank(day_of(f)) <= rank(max(day, 1))}
        reached = spec_counts(reached_texts)
        added = deleted = 0
        for line in at_commits("diff", "--numstat", snaps[0]["sha"], s["sha"], "--", "plan.md", "specs").splitlines():
            a, d, _ = line.split("\t")
            added, deleted = added + int(a), deleted + int(d)
        spec_files, churn, work, fixtures = {}, 0, dict.fromkeys(WORK_KINDS, 0), 0
        if i:
            for line in at_commits("diff", "--numstat", snaps[i - 1]["sha"], s["sha"]).splitlines():
                a, d, f = line.split("\t")
                w = work_kind(renamed_to(f))
                if a != "-" and w:
                    work[w] += int(a) + int(d)
                    # Golden files and sample data under tests/fixtures/: in the Tests box, but not tests the ratio counts.
                    fixtures += int(a) + int(d) if w == "test" and FIXTURE_PATH.search(renamed_to(f)) else 0
            for line in at_commits("diff", "--numstat", snaps[i - 1]["sha"], s["sha"], "--", "plan.md", "specs").splitlines():
                a, d, f = line.split("\t")
                spec_files[f] = int(a) + int(d)
            for line in at_commits("diff", "--numstat", snaps[i - 1]["sha"], s["sha"], "--", ".", ":(exclude)*.md",
                                ":(exclude)docs/dashboard").splitlines():
                a, d, _ = line.split("\t")
                churn += 0 if a == "-" else int(a) + int(d)
        mask, known = reached > 0, born <= i
        spec_v, code_v = np.log1p(spec) * known, np.log1p(code) * known
        name_coverage, jaccard, names_kept = name_overlap(spec, code, known)
        # A name the code had at an earlier merge and lacks now: `ever` holds only the merges before this one.
        in_code = (code > 0) & known
        names_retired = int(((spec > 0) & known & ~in_code & ever).sum())
        # Production coverage: the same share, of the names in files work_kind calls prod; the
        # counts beside it are its numerator and the all-code one, over spec_names.
        named = (spec > 0) & known
        prod_name_coverage = name_overlap(spec, places["prod"], known)[0]
        # The names behind the two counts' difference, and behind the all-code miss: sorted, each
        # outside-production name with the places it is in and its paths there.
        outside = [vocab[k] for k in np.flatnonzero(named & in_code & (places["prod"] == 0))]
        names_outside_prod = {v: {p: sorted(f for f in where[v] if place_of(f) == p)
                                  for p in PLACES if any(place_of(f) == p for f in where[v])} for v in outside}
        names_absent = [vocab[k] for k in np.flatnonzero(named & ~in_code)]
        ever |= in_code
        # The shuffles run once: the chance band and the gap's place among them both come from them.
        draws = chance_draws(spec_v, code_v, known)
        chance, gap = band(draws), angle(spec_v, code_v)
        gap_full = deg(gap)
        gap_excess = round(gap_full - chance[0], 2) if gap_full is not None and chance else None
        gap_excess_band = [round(chance[1] - chance[0], 2), round(chance[2] - chance[0], 2)] if chance else None
        gap_percentile = percentile_in(draws, gap)
        # Each vocabulary name's class, from its own name and the places it is found in at this merge.
        klass = np.array([name_class(v, {place_of(p) for p in where.get(v, {})}) for v in vocab])
        reached_class = {k: mask & (klass == k) for k in ("prod", "test")}
        # On a merge with a PR only, as coverage: the origin has no day reached.
        class_coverage = {k: round(float((code[m] > 0).mean()), 3) if s["pr"] and m.any() else None
                          for k, m in reached_class.items()}
        flags = spec_flags(reached_texts)
        class_coverage["flags"] = round(len(code_flags(s["sha"], flags)) / len(flags), 3) if s["pr"] and flags else None
        class_names = {k: int((named & (klass == k)).sum()) for k in ("prod", "test")}
        all_flags = spec_flags(s["texts"])
        class_names["flags"] = len(all_flags)
        # Against the merge before; the origin has none, so its two are None.
        names_added, names_dropped = name_steps(before, (named, klass, all_flags)) if before else (None, None)
        before = (named, klass, all_flags)
        rows.append(dict(i=i, sha=s["sha"], date=s["date"], pr=s["pr"], title=s["title"], branch=s["branch"], kind=s["kind"],
                         day=day if s["pr"] else 0,
                         own_day=own_day(dict(headRefName=s["branch"] or "", title=s["title"])) if s["pr"] else None,
                         added=added, deleted=deleted,
                         gap_full=gap_full,
                         gap_chance=chance and chance[0], gap_chance_band=chance and chance[1:],
                         gap_excess=gap_excess, gap_excess_band=gap_excess_band, gap_percentile=gap_percentile,
                         class_coverage=class_coverage, class_names=class_names,
                         names_added=names_added, names_dropped=names_dropped,
                         coverage=round(float((code[mask] > 0).mean()), 3) if s["pr"] and mask.any() else None,
                         name_coverage=name_coverage, jaccard=jaccard, names_kept=names_kept, names_retired=names_retired,
                         prod_name_coverage=prod_name_coverage, spec_names=int(named.sum()),
                         names_in_code=int((named & in_code).sum()), names_in_prod=int((named & (places["prod"] > 0)).sum()),
                         names_outside_prod=names_outside_prod, names_absent=names_absent,
                         spec_files=spec_files, code_churn=churn, work=work, test_fixtures=fixtures))
    files = sorted({f for s in snaps for f in s["texts"] if f == "plan.md" or day_of(f)},
                   key=lambda f: (rank(day_of(f)), f))
    lines = sum(t.count("\n") for t in snaps[0]["texts"].values())
    return rows, files, len(vocab), lines


def boundaries(rows, snaps, blobs):
    """At each merge, for the project file's services: the lines of main source still in the monolith
    and in the service's own directory under services/, and the imports where one service's
    package reaches into another's ("matching>identity"). Tests are left out, as a test may
    assemble modules; a fully qualified name used without an import is not seen."""
    seen = {}
    for r, s in zip(rows, snaps):
        placed, crossed = {}, collections.Counter()
        for line in at_commits("ls-tree", "-r", s["sha"]).splitlines():
            meta, path = line.split("\t", 1)
            m = OWN_PACKAGE.search(path)
            if not path.endswith(".java") or not m or m.group(1) not in SERVICE:
                continue
            blob = meta.split()[2]
            if blob not in seen:
                text = blobs.read(s["sha"], path)
                seen[blob] = (text.count("\n"), IMPORT.findall(text))
            n, imports = seen[blob]
            owner = SERVICE[m.group(1)]
            placed.setdefault(owner, [0, 0])[path.startswith("services/")] += n
            crossed.update(f"{owner}>{SERVICE[p]}" for p in imports if SERVICE.get(p, owner) != owner)
        r["placed"], r["crossings"] = placed, dict(crossed)


# The yardsticks plan.md judges the driver on ("What it is judged against"), and two the notebook adds, as
# numbers: each is a row of the lab notebook's measurement table, found by how its Question cell starts, and
# `read` says where its figure sits in a day's cell. The notebook is the count made at each close; nothing
# here recounts it.
YARDSTICKS = (
    dict(key="cost", name="Cost of each merged pull request, main sessions", question="Cost per merged PR",
         unit="$", decimals=2, read="each"),
    dict(key="replies", name="Replies for each merged pull request, main sessions",
         question="Replies per merged PR", unit="", decimals=1, read="each"),
    dict(key="escapes", name="Defects that escaped from an earlier Day", question="Escapes per day",
         unit="", decimals=0, read="first"),
    dict(key="parks", name="Times the driver stopped for a person", question="Parks by reason",
         unit="", decimals=0, read="first"),
    dict(key="refusals", name="Calls the hooks refused", question="Hook refusals", unit="", decimals=0,
         read="first"),
    dict(key="gates", name="Cost of the gates", question="What each gate cost", unit="$", decimals=2,
         read="sum"),
)


def notebook_figure(cell, read):
    """The figure a day's cell gives a yardstick, or None when it gives none: "each" is the number before " each",
    "first" the number the cell starts with, "sum" the dollars it names added up."""
    if read == "each":
        match = re.search(r"\$?([\d,]+(?:\.\d+)?) each\b", cell)
        return float(match.group(1).replace(",", "")) if match else None
    if read == "first":
        match = re.match(r"([\d,]+)\b", cell)
        return int(match.group(1).replace(",", "")) if match else None
    dollars = re.findall(r"\$([\d,]+(?:\.\d+)?)", cell)
    return round(sum(float(d.replace(",", "")) for d in dollars), 2) if dollars else None


def notebook_total(cell):
    """The total and the count an "each" cell divides, "$5.51 over 5 merged PRs" or "118 replies over
    5 PRs", or None when the cell names none."""
    match = re.search(r"\$?([\d,]+(?:\.\d+)?)(?: [a-z]+)? over ([\d,]+)\b", cell)
    return (float(match.group(1).replace(",", "")), int(match.group(2).replace(",", ""))) if match else None


def running_average(parts, skip=False):
    """For each day, the total so far over the count so far, from each day's (total, count). A day
    with none is left out of the sums when `skip` (a yardstick not measured that day); otherwise
    the average stops there, since a sum that misses a day is not the average over every one."""
    out, total, count = [], 0, 0
    for part in parts:
        if part is None and not skip:
            total = None
        elif part is not None and total is not None:
            total, count = total + part[0], count + part[1]
        out.append(round(total / count, 2) if total is not None and count else None)
    return out


def yardsticks(concluded, tokens):
    """The yardsticks as the lab notebook's own cells give them, one value per day column. The figures are the
    notebook's, read and not recounted. A cell whose figure cannot be read is a problem line, never a guess; a cell
    that says "none" is not measured yet and is no problem. The last row, the tokens read again for each written, is
    counted from docs/dashboard/token-usage.json, not the notebook."""
    columns = []
    for i, cell in enumerate(concluded["measured_head"]):
        match = re.fullmatch(r"Day (\d+)", cell)
        if match:
            columns.append((i, int(match.group(1))))
    if not columns:
        return dict(days=[], rows=[], problems=[])
    days = [day for _, day in columns]
    rows, problems = [], []
    for y in YARDSTICKS:
        found = next((r for r in concluded["measured"] if r[0].startswith(y["question"])), None)
        if found is None:
            # Another project's notebook may not measure it.
            continue
        beside = re.search(r"beside\D*?([\d,]+(?:\.\d+)?)", found[0])
        values = []
        for i, day in columns:
            figure = notebook_figure(found[i], y["read"])
            if figure is None and not found[i].strip().lower().startswith("none"):
                problems.append(
                    f"Day {day:02d}, {y['question']}: no figure read from the notebook's cell")
            values.append(dict(day=day, value=figure, text=found[i]))
        if y["read"] == "each":
            parts = [notebook_total(v["text"]) for v in values]
            problems += [f"Day {v['day']:02d}, {y['question']}: no total and count read from the notebook's cell"
                         for v, p in zip(values, parts) if p is None and v["value"] is not None]
            average, over = running_average(parts), "pull requests"
        else:
            average, over = running_average([None if v["value"] is None else (v["value"], 1) for v in values],
                                            skip=True), "days"
        rows.append(dict(key=y["key"], name=y["name"], unit=y["unit"], decimals=y["decimals"],
                         baseline=float(beside.group(1).replace(",", "")) if beside else None,
                         source="docs/lab-notebook.md", values=values, average=average, average_over=over))
    if any(t["day"] in days and t["output"] > 0 for t in tokens):
        values, parts = [], []
        for day in days:
            mine = [t for t in tokens if t["day"] == day]
            read = sum(t["input"] + t["cache_write"] + t["cache_read"] for t in mine)
            written = sum(t["output"] for t in mine)
            parts.append((read, written) if written > 0 else None)
            if written > 0:
                text = f"{read:,} tokens read for {written:,} written, in the sessions tagged Day {day}"
                values.append(dict(day=day, value=round(read / written, 1), text=text))
            else:
                values.append(dict(day=day, value=None, text=""))
        rows.append(dict(key="reread", name="Tokens read again for each token written", unit="", decimals=0,
                         baseline=None, source="docs/dashboard/token-usage.json", values=values,
                         average=running_average(parts, skip=True), average_over="tokens written"))
    return dict(days=days, rows=rows, problems=problems)


# Each gate and the found: value its Defect lines carry (specs/README.md); the hooks find no Defect
# line: what they catch is each refusal, from refusals.json.
GATES = (("auditors", "auditor"), ("seen red", "seen red"), ("break on purpose", "break on purpose"),
         ("evidence replay", "evidence replay"), ("hooks", None))
CAUSES = ("spec", "implementation", "process", "environment")


def found_tag(value):
    """A Defect line's found: or cause: value as relabel.py reads it: older Notes qualify the value,
    "auditor (spec-auditor)". The page's graph 7 reads it the same way (tagOf, dashboard.js)."""
    return re.sub(r" \(.*\)$", "", re.sub(r"^the ", "", (value or "").strip().lower()))


def gate_report(days, gates, refused):
    """Per gate: the Defect lines whose found: names it, by cause (other: a cause not in CAUSES), the
    hooks' refusals, and its runs, replies, context, output and cost from gates.json; and how many
    Defect lines no gate found."""
    tag = found_tag
    lines = [x for d in days for x in d.get("defects", [])]
    rows = []
    for gate, found in GATES:
        mine = [x for x in lines if found and tag(x.get("found")) == found]
        causes = {c: sum(tag(x.get("cause")) == c for x in mine) for c in CAUSES}
        causes["other"] = len(mine) - sum(causes.values())
        spent = {k: sum(r.get(k, 0) for r in gates if r["gate"] == gate) for k in ("runs", "replies", "context", "output", "cost")}
        rows.append(dict(gate=gate, found=found, defects=len(mine), causes=causes,
                         # with no refusals.json yet, no count is not zero
                         refused=sum(r["refused"] for r in refused) if found is None and refused else None,
                         **dict(spent, cost=round(spent["cost"], 2))))
    named = {f for _, f in GATES if f}
    return dict(gates=rows, defects=len(lines),
                elsewhere=sum(tag(x.get("found")) not in named for x in lines))


def deployment():
    """The live checks of the one deployment (the project's own), or None if nothing was deployed."""
    path = os.path.join(PAGE, "deployment.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def criterion_index(days, reports, handoffs, snaps, blobs, order=()):
    """Join recorded evidence without treating an unavailable source as a negative result."""
    names = {t for d in days for c in d["evidence"] for t in evidence_test_names(c["block"])}
    states = test_state(names, snaps[-1]["sha"], blobs, {old: new for _, old, new in moves(snaps)})
    report_days = {d["day"]: d for d in reports.get("days", [])}
    rows, attention = [], []
    def flag(row, reason, detail):
        attention.append(dict(id=row["id"], reason=reason, detail=detail, day=row["day"]))

    for day in days:
        report = report_days.get(day["day"], {})
        for check in report.get("checks", []):
            if check.get("criterion") is None and check["status"] in ("failed", "error"):
                flag(dict(id=f"Day {day['day']:02d}", day=day["day"]), "replay_" + check["status"],
                     check.get("diagnostic") or check.get("label") or "")
        for c in day["evidence"]:
            if not c["id"]:
                continue
            block = c["block"]
            evidence_text = criterion_evidence(block)
            tests = evidence_test_names(block)
            # An Evidence line that points at "the command above" cites the claim's own command.
            claim_text = re.split(r"(?im)^\s*Evidence:", block, maxsplit=1)[0]
            command = re.search(COMMAND, evidence_text) or (
                re.search(r"\bcommands? above\b", evidence_text, re.I) and re.search(COMMAND, claim_text))
            measured = c["ticked"] and day.get("evidence_format", True)
            # A ticked box a reader judged has its Not proven: line as proof (specs/README.md), and cites its PR there.
            reader = re.search(r"(?m)^\s+Not proven:\s*(.*(?:\n(?!\s*(?:broken:|Replaces:|Evidence:))\s+[^\n]+)*)", block)
            cited = bool(CITED_PR.search(evidence_text) and (tests or command)
                         or reader and CITED_PR.search(reader.group(1))) if measured else None
            red_lines = [line.strip() for line in block.splitlines()
                         if broke(line) or re.search(r"\bseen[- ]red\b", line, re.I)]
            red = bool(red_lines) if measured else None
            # `broken: none → <why>`: a check that cannot be broken from the repository, and why.
            none = [why.strip() for what, why in BREAK_NONE.findall(block) if what.lower() == "none"]
            found = all(states[t] != "missing" for t in tests) if tests else None
            state = report.get("state", reports["state"] if reports["state"] != "loaded" else "not checked")
            checks = [x for x in report.get("checks", []) if x.get("criterion") == c["id"]]
            replay = dict(state=state, status=[x["status"] for x in checks] or None,
                          why=report.get("why", []) + ([reports["diagnostic"]] if reports.get("diagnostic") else [])
                          + [x["diagnostic"] for x in checks if x.get("diagnostic")], checks=checks)
            track = next((name for name, work in day.get("track_work", {}).items()
                          if c["id"] in track_criteria(work)), None)
            if track is None and len(day.get("tracks", [])) == 1:
                track = day["tracks"][0]
            claim = re.split(r"\n\s*(?:Evidence|Test|broken|Replaces):", block, maxsplit=1, flags=re.I)[0]
            claim = re.sub(r"^- \[[ x]\]\s*\S+\s*(?:\*\*(?:new|hold)\*\*\s*[—-]\s*)?", "", claim)
            row = dict(id=c["id"], day=day["day"], phase=day.get("phase"), tag=c["kind"], claim=" ".join(claim.split()),
                       ticked=bool(c["ticked"]),
                       spec=day["file"] + "#acceptance-criteria", track=track,
                       prs=sorted({int(n) for n in CITED_PR.findall(evidence_text)}), tests=tests,
                       cited=cited, test_found=found, seen_red=dict(state=red, lines=red_lines, none=none), replay=replay,
                       replaces=[i for _, ids in replacement_lines(block) for i in ids], replaced_by=[])
            rows.append(row)
            for check in checks:
                if check["status"] in ("failed", "error"):
                    flag(row, "replay_" + check["status"], check.get("diagnostic") or check.get("label") or "")
            if state == 'stale':
                flag(row, "replay_stale", "; ".join(replay["why"]))
            if cited is False:
                flag(row, "evidence_missing", "No evidence and PR cited together")
            if day["status"] in FINISHED and state in ("absent", "invalid", "not checked"):
                flag(row, "evidence_missing", "Replay report: " + state)
            if red is False and none:
                flag(row, "not_breakable", "; ".join(none))
            elif red is False:
                flag(row, "not_seen_red", "No seen-red or broken line")
            if found is False:
                flag(row, "test_not_found", ", ".join(t for t in tests if states[t] == "missing"))
            # The "Tests on main" column's orange: a test CI can skip is noted here, not a fault. That
            # column reads the states evidence_history gives the names in the whole block, not only the
            # Evidence line's; before it runs, `tests` is still the list of names.
            day_states = c["tests"] if isinstance(c.get("tests"), dict) else {}
            skips = list(dict.fromkeys([t for t in tests if states[t] == "skippable"]
                                       + [t for t, s in day_states.items() if s == "skippable"]))
            if skips:
                flag(row, "test_skippable", ", ".join(skips))
            for h in handoffs:
                if not h["picked"] and re.search(rf"\b{re.escape(c['id'])}\b", h["text"]):
                    flag(row, "handoff_unclaimed", h["text"])
    by_id = {r["id"]: r for r in rows}
    for row in rows:
        for target in row["replaces"]:
            if target in by_id:
                by_id[target]["replaced_by"].append(row["id"])
    severity = ("replay_failed", "replay_error", "replay_stale", "evidence_missing",
                "not_seen_red", "test_not_found", "handoff_unclaimed", "not_breakable", "test_skippable")
    attention.sort(key=lambda a: (severity.index(a["reason"]), a["day"], a["id"]))
    for item in attention:
        del item["day"]
    # handoff_unclaimed above needs a hand-off to name a criterion; hand-offs name their own ID and
    # a day, and the day they go to has no criteria yet. So each open one is listed, after the rest:
    # those for the next day to run, then those no later day picks up.
    finished = {d["day"] for d in days if d["status"] in FINISHED}
    upcoming = next((d for d in order if d not in finished and d not in PLACEHOLDERS), None)
    for reason, to in ((("handoff_next", upcoming),) if upcoming else ()) + (("handoff_unpicked", None),):
        for h in handoffs:
            if not h["picked"] and h.get("to") == to:
                text = " ".join(re.sub(r"^\s*-\s*", "", h["text"]).split())
                attention.append(dict(id=h.get("id") or h["source"], reason=reason,
                                      detail=(f"Day {to:02d}: " if to is not None else "") + text))
    return rows, attention


def first_sentence(text, limit=200):
    """A claim's first sentence for a reader, its backticks gone: the fallback for a promise with no plain
    sentence. It ends at a full stop before a capital, a quote or the end, so `run-steps.py --once` stays whole."""
    text = " ".join(text.replace("`", "").split())
    match = re.match(r"(.+?[.!?])(?=\s+[A-Z\"]|\s*$)", text)
    sentence = match.group(1) if match else text
    return sentence if len(sentence) <= limit else sentence[:limit].rsplit(" ", 1)[0] + "…"


def attach_plain(index, path=None):
    """Each criterion's plain sentence from docs/dashboard/plain-promises.json, or the first sentence of
    its claim: a new day with no entry, or a file that cannot be read, must not break the page."""
    path = path or os.path.join(PAGE, "plain-promises.json")
    try:
        with open(path, encoding="utf-8") as f:
            written = json.load(f)
    except (OSError, ValueError):
        written = {}
    if not isinstance(written, dict):
        written = {}
    for row in index:
        text = written.get(row["id"])
        ok = isinstance(text, str) and text.strip()
        row["plain"] = text.strip() if ok else first_sentence(row["claim"])
        row["plain_source"] = "written" if ok else "first sentence"


ABILITIES = (
    dict(key="rehearse", name="Shows what it would do", role="rung"),
    dict(key="stop", name="Can be stopped, from anywhere", role="rung"),
    dict(key="loop", name="Works through the night", role="rung"),
    dict(key="park", name="Asks only when it must", role="rung"),
    dict(key="recover", name="Picks itself up after a crash", role="rung"),
    dict(key="see", name="Shows the world what still works", role="rail"),
    dict(key="record", name="Proves every claim", role="rail"),
)
STORY_TEMPLATE = re.compile(r"As an? \[type of user\],? I want \[goal or capability\],? so that \[benefit or outcome\]\.?")


def story_section(body):
    """The "## User story" section of a PR body, HTML comments gone, or "" when there is none."""
    # The comments are the template's advice; the section ends at the next "## " heading.
    lines = re.sub(r"<!--.*?-->", "", body or "", flags=re.S).splitlines()
    start = next((i for i, line in enumerate(lines) if re.match(r"##\s*User story\s*$", line)), None)
    if start is None:
        return ""
    rest = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        rest.append(line)
    return " ".join(" ".join(rest).split())


def story_ability(section):
    """The Ability: line's key, or None: `Ability: <key>` with the key one of ABILITIES, in any case and with its
    square brackets optional. The unfilled template, "[one of ...]", names no key, so it is None."""
    match = re.search(r"Ability:\s*\[?\s*(\w+)", section, re.I)
    key = match.group(1).lower() if match else None
    return key if key in [a["key"] for a in ABILITIES] else None


def story_sentence(section):
    """The story's own words: the section with the Ability: line removed; "" when that is only the template's
    placeholders, so a PR that left the template as it was has no story."""
    text = " ".join(re.sub(r"Ability:\s*(\[[^\]]*\]|\S+)", "", section, flags=re.I).split())
    return "" if not text or STORY_TEMPLATE.fullmatch(text) else text


def story_reader(sentence):
    """Who the story is written for, from its "As ..." clause: "away" when they are not at a desk, "reader" when
    they only read the dashboard, else "desk". "away" wins when both match; with no clause it is "desk"."""
    match = re.match(r"\s*As\s+(.*?)(?:,\s*|\s+)I want\b", sentence, re.I)
    if not match:
        return "desk"
    clause = match.group(1).lower()
    if any(w in clause for w in ("phone", "away", "overnight", "asleep", "night", "leaves", "leave", "running",
                                 "runs the driver")):
        return "away"
    if any(w in clause for w in ("dashboard", "page", "reading", "reads", "reader", "looking", "visiting",
                                 "opening", "someone")):
        return "reader"
    return "desk"


def user_stories(prs, path=None):
    """Every merged pull request's user story with its ability, for the dashboard: the PR body's own section and
    Ability: line first, docs/dashboard/user-stories.json for the ones written before the template asked, and a
    problem line for each PR that has neither. The page must not break on a missing or unreadable file."""
    source = path or "docs/dashboard/user-stories.json"
    path = path or os.path.join(PAGE, "user-stories.json")
    try:
        with open(path, encoding="utf-8") as f:
            written = json.load(f)
    except (OSError, ValueError):
        written = {}
    if not isinstance(written, dict):
        written = {}
    keys = [a["key"] for a in ABILITIES]
    rows, problems = [], []
    for p in sorted((p for p in prs if p["state"] == "MERGED"), key=lambda p: p["number"]):
        number = p["number"]
        section = story_section(p.get("body"))
        sentence = story_sentence(section)
        ability = story_ability(section)
        entry = written.get(str(number))
        entry = entry if isinstance(entry, dict) else {}
        kept = entry.get("story")
        kept = kept.strip() if isinstance(kept, str) else ""
        story, story_source = (sentence, "pr") if sentence else (kept, "written" if kept else "missing")
        if ability:
            ability_source = "pr"
        elif entry.get("ability") in keys:
            ability, ability_source = entry["ability"], "written"
        else:
            ability_source = "missing"
        if story_source == "missing":
            problems.append(f"#{number} has no user story")
        if ability_source == "missing":
            problems.append(f"#{number} names no ability: add an Ability: line or an entry in "
                            "docs/dashboard/user-stories.json")
        named = dict(headRefName=p.get("headRefName") or "", title=p.get("title") or "")
        rows.append(dict(number=number, title=p["title"], url=p["url"], branch=p.get("headRefName") or "",
                         day=own_day(named),
                         date=(p.get("mergedAt") or "")[:10] or None, ability=ability,
                         ability_source=ability_source, story=story, story_source=story_source,
                         reader=story_reader(story)))
    return dict(abilities=[dict(a) for a in ABILITIES], stories=rows, problems=problems, source=source)


def attach_abilities(index, stories):
    """Each promise's abilities: the ones its pull requests grew, the most-grown first and a tie going to the one
    whose pull request is cited first. A promise is kept by the pull requests that grew it, so one that cites none
    yet, or none with an ability, gets []."""
    ability = {s["number"]: s["ability"] for s in stories}
    for row in index:
        keys = [ability[n] for n in row["prs"] if ability.get(n)]
        # sorted() is stable, so keys that are equally common keep the order they were cited in.
        row["abilities"] = sorted(dict.fromkeys(keys), key=lambda k: -keys.count(k))


# What runs each test file, first match wins: tests.yml runs tests/ on every push and pull request, where
# the live modules skip without DRIVER_LIVE_CLI; spec-drift-tests.yml runs scripts/test_*.py.
TEST_GROUPS = (
    ("live", r"^tests/test_live_", "Live runs against real Claude",
     "By hand only: skipped in CI, which has no login or budget"),
    ("gap", r"^tests/test_dashboard_gap\.py$", "The dashboard's gap numbers", "Every push and pull request"),
    ("driver", r"^tests/test_[^/]*\.py$", "Driver behaviour", "Every push and pull request"),
    ("tooling", r"^scripts/test_[^/]*\.py$", "Project tooling",
     "Only on pull requests that touch a script or a file they read (spec-drift-tests.yml)"),
)


def count_tests(source):
    """The test methods of a module's classes, as unittest finds them; a module that does not parse is None."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    return sum(isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.name.startswith("test")
               for c in ast.walk(tree) if isinstance(c, ast.ClassDef) for f in c.body)


def test_inventory(paths, read):
    """The tests on main by what runs them: each file counted once, in the first of TEST_GROUPS that
    names it. `read` gives a path's text; a module that does not parse is named, not counted."""
    groups = {key: dict(key=key, label=label, when=when, files=0, tests=0) for key, _, label, when in TEST_GROUPS}
    unreadable = []
    for path in sorted(paths):
        key = next((k for k, pattern, _, _ in TEST_GROUPS if re.search(pattern, path)), None)
        if key is None:
            continue
        count = count_tests(read(path))
        if count is None:
            unreadable.append(path)
            continue
        groups[key]["files"] += 1
        groups[key]["tests"] += count
    # In the order a reader meets them: what the driver does first.
    ordered = [groups[k] for k in ("driver", "live", "gap", "tooling")]
    return dict(groups=ordered, total=sum(g["tests"] for g in ordered), unreadable=unreadable)


INFRA_TRIES = 5


def infra_summary(run_id):
    """One infra workflow run's summary (scripts/infra-summary.py), or None if its artifact does not download."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            run("gh", "run", "download", str(run_id), "-n", "infra-summary", "-D", tmp)
            with open(os.path.join(tmp, "infra-summary.json"), encoding="utf-8") as f:
                return json.load(f)
        except (subprocess.CalledProcessError, OSError, ValueError):
            return None


def infra(workflow):
    """The infra workflow's runs on main, and the summary of the newest completed run whose artifact
    downloads (artifacts expire, so an old run may have none). With no workflow, none: gh is not asked."""
    if not workflow:
        return dict(runs=[], latest=None)
    try:
        listed = json.loads(run("gh", "run", "list", "--workflow", workflow, "--branch", "main",
                                "--event", "push", "--limit", "30",
                                "--json", "databaseId,headSha,conclusion,createdAt,url"))
    except subprocess.CalledProcessError:
        return dict(runs=[], latest=None)
    runs = [dict(sha=r["headSha"][:7], conclusion=r["conclusion"], date=r["createdAt"][:10], url=r["url"])
            for r in listed]
    latest, tries = None, 0
    for i, r in enumerate(listed):
        if not r["conclusion"]:
            continue  # still running
        if tries == INFRA_TRIES:
            break
        tries += 1
        summary = infra_summary(r["databaseId"])
        if summary is not None:
            latest = dict(runs[i], summary=summary)
            break
    return dict(runs=runs, latest=latest)


# The "How this works" panel follows one real promise, picked by how_excerpts, through its day's
# files and these.
HOW_TEMPLATE = "specs/_template.md"
HOW_REPLAY = "docs/dashboard/replay-history.json"
HOW_PLAN = "plan.md"
HOW_PLAN_PARTS = ("Short answer", "Who does what", "When the driver parks", "Phases", "Stopping points")
# A promise is followed only if every one of these is on record: its track, PR, seen-red line and
# planted bugs among them. Its re-check is not: the newest day has none until the replay reaches it.
HOW_NEEDED = ("crumbs", "day_goal", "day_out_of_scope", "day_tracks", "day_criteria", "claim", "red_today", "test",
              "evidence", "seen_red", "tick", "bugs", "plan_phase")
HOW_NO_PROMISE = "every finished promise is missing a step of its record"


def how_specs(days):
    """The finished days' spec files, newest day first: what the panel may pick a promise from."""
    return [d["file"] for d in sorted(days, key=lambda d: d["day"], reverse=True) if d["status"] in FINISHED]


def how_excerpts(read, specs):
    """The panel's excerpts for the first promise in `specs` (newest day first) tagged new, ticked and
    on record at every step, under "promise" {id, day, spec, breaks}. Each is {source, text} from the
    real files through `read(path)` ("" for no file), or {source, missing: why}: a file or passage that
    has gone shows as gone, never filled in. A file every promise shares going does not end the pick."""
    read = functools.cache(read)
    for path in specs:
        day = int(re.search(r"day-(\d+)", path).group(1))
        for cid in re.findall(r"^- \[x\] (C\d+\.\d+) \*\*new\*\*", read(path), re.M):
            promise = dict(id=cid, day=day, spec=path, breaks=f"specs/breaks/day-{day:02d}.json")
            got = how_excerpts_of(read, promise)
            if all("text" in got[k] for k in HOW_NEEDED if k != "plan_phase" or read(HOW_PLAN)):
                return dict(got, promise=dict(source=path, text=promise))
    return dict(how_excerpts_of(read, None), promise=dict(source="specs/", missing=HOW_NO_PROMISE))


def how_excerpts_of(read, promise):
    """The excerpts for one promise, or with None only those every promise shares."""
    cid = promise["id"] if promise else ""
    spec_path, breaks_path = (promise["spec"], promise["breaks"]) if promise else ("specs/", "specs/breaks/")
    files = {p: read(p) for p in (HOW_TEMPLATE, HOW_REPLAY, HOW_PLAN) + ((spec_path, breaks_path) if promise else ())}
    spec, template, plan = files.get(spec_path, ""), files[HOW_TEMPLATE], files[HOW_PLAN]

    def flat(text):
        return re.sub(r"\s+", " ", text).strip()

    def passage(text, pattern):
        m = re.search(pattern, text, re.M | re.S)
        return m.group(1).rstrip() if m else None

    def section(heading):
        return passage(spec, rf"^## {heading}\n(.*?)(?=^## |\Z)")

    block = passage(spec, rf"^(- \[[ x]\] {re.escape(cid)} .*?)(?=^- \[|^## |\Z)")

    def field(pattern):
        return flat(passage(block, pattern))

    def evidence():
        return field(r"^\s*Evidence: (.*?)(?=^\s*seen red|^\s*broken:|\Z)")

    def crumbs():
        track = passage(section("Tracks"), rf"^\| (\w\d?) \|[^\n]*{re.escape(cid)}\b")
        pr = passage(evidence(), r"\(#(\d+)\)")
        phase = passage(spec, r"\*\*Phase:\*\* (\d+)")
        return track and pr and phase and [HOW_PLAN, f"Phase {phase}", f"Day {promise['day']}", f"Track {track} (PR #{pr})", f"Promise {cid}"]

    def criteria_count():
        day = cid.split(".")[0]
        count = len(re.findall(rf"^- \[[ x]\] {day}\.\d+ ", spec, re.M))
        return f"{count} on this day" if count else None

    def tracks():
        letters = re.findall(r"^\| (\w\d?) \|", section("Tracks"), re.M)
        return "Tracks " + ", ".join(letters) if letters else None

    def bugs():
        manifest = json.loads(files[breaks_path])
        out = []
        for what, said in re.findall(r"broken: (.+?) → (.+?) \(#\d+\)", block):
            entry = next(b for b in manifest if b["what"] == what)
            out.append(dict(what=what, file=entry["file"], find=entry["find"], replace=entry["replace"], reported=said))
        return out

    def recheck():
        rows = [r for r in json.loads(files[HOW_REPLAY])["rows"] if r["criterion"] == cid]
        if promise and not rows:
            return dict(pr=None, checks=[])  # read, and none on record: not the same as a file gone
        newest = max(r["n"] for r in rows)
        rows = [r for r in rows if r["n"] == newest]
        return dict(pr=rows[0].get("pr"), checks=[dict(check=r["check"], state=replay_row_state(r)) for r in rows])

    def plan_parts():
        headings = re.findall(r"^## (.+)$", plan, re.M)
        return list(HOW_PLAN_PARTS) if all(p in headings for p in HOW_PLAN_PARTS) else None

    def plan_phase():
        phase = passage(spec, r"\*\*Phase:\*\* (\d+)")
        heading = passage(plan, rf"^(### Phase {phase}\b.*?)(?=^- Day )")
        scheduled = passage(plan, rf"^(- Day {promise['day']}:.*?)(?=^\S|\Z)")
        return heading and scheduled and f"{heading}\n{scheduled}"

    wanted = dict(
        crumbs=(spec_path, crumbs),
        day_goal=(spec_path, lambda: flat(section("Goal"))),
        day_out_of_scope=(spec_path, lambda: flat(passage(section("Out of scope"), r"^- (.*?)(?=^- |\Z)"))),
        day_tracks=(spec_path, tracks),
        day_criteria=(spec_path, criteria_count),
        claim=(spec_path, lambda: field(r"\*\*(?:new|hold)\*\* — (.*?)^\s*Red today:")),
        red_today=(spec_path, lambda: field(r"^\s*Red today: (.*?)^\s*Test:")),
        test=(spec_path, lambda: field(r"^\s*Test: (.*?)^\s*Evidence:")),
        evidence=(spec_path, evidence),
        seen_red=(spec_path, lambda: field(r"^\s*(seen red\b.*?)$")),
        tick=(spec_path, lambda: passage(block, r"^(- \[[ x]\] \S+ \*\*\w+\*\*)")),
        form=(HOW_TEMPLATE, lambda: passage(template, r"^(- \[ \] CNN\.1 .*?)(?=^- \[ \] CNN\.2)")),
        template_parts=(HOW_TEMPLATE, lambda: re.findall(r"^## (.+)$", template, re.M)),
        bugs=(breaks_path, bugs),
        recheck=(HOW_REPLAY, recheck),
        plan_phase=(HOW_PLAN, plan_phase),
        plan_parts=(HOW_PLAN, plan_parts),
    )
    out = {}
    for key, (source, get) in wanted.items():
        try:
            value = get()
        except (ValueError, KeyError, TypeError, IndexError, AttributeError, StopIteration):
            value = None
        why = (HOW_NO_PROMISE if not promise and key in HOW_NEEDED + ("recheck",) else
               "the file is missing or empty" if not files[source] else "the passage is no longer there")
        out[key] = dict(source=source, text=value) if value else dict(source=source, missing=why)
    return out


def fill(page, data, name):
    # PR titles and spec text are written by anyone: no "<" may reach the HTML parser from the data
    # line. "</script>" would end it early; "<!--" then "<script" (a spec quoting HTML, Day 12) keeps
    # the real end tag from closing it, and the page never ran. JSON reads "<" back as "<".
    data = data.replace("<", "\\u003c")
    page, n = re.subn(r"^window\.SPEC_DRIFT = .*;$", lambda _: f"window.SPEC_DRIFT = {data};", page, flags=re.M)
    if n != 1:
        raise SystemExit(f"{name}: expected one window.SPEC_DRIFT line, found {n}")
    return page


def build(data):
    """docs/dashboard/ as a single page: the stylesheet and script inlined, the data filled in."""
    def read(name):
        with open(os.path.join(PAGE, name), encoding="utf-8") as f:
            return f.read()
    page = read("index.html")
    for tag, name, wrap in (('<link rel="stylesheet" href="dashboard.css">', "dashboard.css", "style"),
                            ('<script src="dashboard.js"></script>', "dashboard.js", "script")):
        if page.count(tag) != 1:
            raise SystemExit(f"index.html: expected one {tag}")
        page = page.replace(tag, f"<{wrap}>\n{read(name)}</{wrap}>")
    return fill(page, data, "index.html")


def page_data(real, spec_days):
    """What --build writes: the real data, or with no day specs yet, demo-data.py's example data marked
    "demo": true, which the page shows under a banner. --out never uses this."""
    if spec_days:
        return real
    spec = importlib.util.spec_from_file_location("demo_data", os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo-data.py"))
    demo_data = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo_data)
    return dict(demo_data.demo(), demo=True)


def unwritten(days, order):
    """The cleanup or close-out day before its spec exists: its number, and the phase of the day it
    follows in the run order, so the roadmap shows it where it runs."""
    which = next((p for p in (CLEANUP, CLOSEOUT) if p in order), None)
    if which is None:
        return None
    phase = {d["day"]: d.get("phase") for d in days}
    before = [d for d in order[:order.index(which)] if d not in PLACEHOLDERS]
    return dict(day=max(d["day"] for d in days) + 1,
                phase=phase.get(before[-1]) if before else None, title=f"The {which} day")


def unwritten_lines(plan):
    """The plan item each unwritten day comes from, by placeholder, read as run_order() reads it."""
    out = {}
    for line in plan_items(plan):
        if "numbered from" in line:
            out[PLATFORM] = line
        if "numbered after the last" in line:
            out[CLOSEOUT if "close-out" in line else CLEANUP] = line
    return out


def next_step(days, open_prs, order, stop, lines=None):
    """What to do next. An unwritten day quotes the plan item it comes from (`lines`, from unwritten_lines())."""
    if open_prs:
        return "Waiting on " + ", ".join(f"#{p['number']} {p['title']}" for p in open_prs)
    by_day = {d["day"]: d for d in days}
    left = [d for d in order if d in PLACEHOLDERS or d not in by_day or by_day[d]["status"] not in FINISHED]
    if not left:
        return "Every day is done." if days else "No day specs yet: fill in plan.md, then write the first day's spec (specs/README.md)."
    if left[0] in PLACEHOLDERS:
        line = (lines or {}).get(left[0], "")
        first = re.search(r"numbered from (\d+)", line)
        day = int(first.group(1)) if left[0] == PLATFORM and first else unwritten(days, order)["day"]
        return f'Day {day:02d}: write its day spec (plan.md: "{line}")'
    if stop is not None and order.index(left[0]) > order.index(stop):
        return f"Day {stop:02d} is done: stop and evaluate before going on (plan.md)"
    if left[0] not in by_day:
        return f"Day {left[0]:02d}: write its day spec (plan.md lists it, specs/ has none)"
    day = by_day[left[0]]
    if not any(p["kind"] == "spec" for p in day["prs"]):
        return f"Day {day['day']:02d}: read the spec against the code, then the spec-change PR"
    left = [t for t in day["tracks"] if t not in day["tracks_merged"]]
    if left:
        return f"Day {day['day']:02d} Track {left[0]}: {day['track_work'][left[0]]}"
    for t in day.get("tracks_unopened", []):
        return f"Day {day['day']:02d} Track {t['track']}: announced in #{t['pr']}, no branch names it"
    return f"Day {day['day']:02d}: the closing PR"


def provenance():
    """What made these numbers: the script's commit, the versions, and the draws behind each band."""
    here = os.path.dirname(os.path.abspath(__file__))
    dirty = bool(run("git", "status", "--porcelain", "--", *(os.path.join(here, n) for n in SOURCES)).strip())
    head = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], capture_output=True, text=True)
    return dict(commit=head.stdout.strip() or None, script_edited=dirty,  # None before the first commit
                python=platform.python_version(), numpy=np.__version__,
                chance_draws=CHANCE_DRAWS)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    out = ap.add_mutually_exclusive_group()
    out.add_argument("--out", default="spec-drift.json")
    out.add_argument("--build", help="write docs/dashboard/ here as one page, with the data inlined")
    ap.add_argument("--cache", default=CACHE_FILE, help="what earlier runs read from git (default: %(default)s)")
    ap.add_argument("--no-cache", action="store_true", help="read everything from git, and keep nothing")
    args = ap.parse_args()
    if not args.no_cache:
        load_cache(args.cache)
    listed, runs, note = github()
    data_branch()
    prs = {p["number"]: p for p in listed}
    open_prs = sorted((p for p in listed if p["state"] == "OPEN"), key=lambda p: p["number"])
    with Blobs() as blobs:
        snaps = snapshots(prs)
        head = snaps[-1]["sha"]
        spec_days = [d for d in map(day_of, run("git", "ls-tree", "--name-only", head, "specs/").split()) if d]
        plan = blobs.read(head, "plan.md")
        rows, files, vocab, lines = trajectory(snaps, blobs, run_order(plan, spec_days)[0])
        days, order, stop = roadmap(snaps, prs, blobs)
        evidence_history(rows, days, snaps, blobs)
        boundaries(rows, snaps, blobs)
        handoffs = hand_offs(days, order, head, blobs)
        checks = evidence_checks(days, snaps)
        index, attention = criterion_index(days, checks, handoffs, snaps, blobs, order)
        attach_plain(index)
        stories = user_stories(listed)
        attach_abilities(index, stories["stories"])
        tests = test_inventory(run("git", "ls-tree", "-r", "--name-only", head, "tests/", "scripts/").split("\n"),
                               lambda path: blobs.read(head, path))
        now = dict(generated=datetime.datetime.now().astimezone().isoformat(timespec="minutes"),
                   head=snaps[-1]["sha"], last_pr=snaps[-1]["pr"],
                   current_day=next((d["day"] for d in days if d["status"] == "active"), None),
                   next_step=next_step(days, open_prs, order, stop, unwritten_lines(plan)), stop_after=stop,
                   unwritten=unwritten(days, order),
                   open_prs=[dict(number=p["number"], title=p["title"], url=p["url"]) for p in open_prs])
        concluded = conclusion(blobs.read(snaps[-1]["sha"], "docs/lab-notebook.md"))
        tokens = token_usage()
        real = dict(now=now, rows=rows, files=files, days=days, origin_lines=lines,
                    order=[d for d in order if d not in PLACEHOLDERS],
                    out_of_order=out_of_order(order),
                    removals=removal_history(days, snaps, blobs),
                    hand_offs=handoffs, look_ahead=look_ahead(snaps, days, index, order, blobs),
                    criteria_index=index, attention=attention, test_inventory=tests,
                    defect_recurrence=recurrence(days),
                    user_stories=stories,
                    gate_report=gate_report(days, refusals("gates.json"), refusals()),
                    other_groups=other_groups(rows),
                    vocab_size=vocab, tokens=tokens, refusals=refusals(),
                    verification=verification(prs, runs),
                    infra=infra(INFRA_WORKFLOW),
                    deployment=deployment(),
                    evidence_checks=checks, replay=replay_history(),
                    conclusion=concluded, yardsticks=yardsticks(concluded, tokens),
                    clock=clock(prs, runs), counted=counted(), driver_runs=driver_runs(parked_issues(note)),
                    data=data_source(),
                    meta=dict(caveats=CAVEATS + [note] * bool(note), provenance=provenance(),
                              break_line_from_pr=BREAK_LINE_FROM_PR, project=project_name(),
                              phases=phases(plan), stops=stops(plan)))
        if args.build:
            # The re-check rows are on the data branch, every other file the panel quotes on main.
            how_read = lambda path: (data_text("replay-history.json") or "") if path == HOW_REPLAY else blobs.read(head, path)  # noqa: E731
            real["how_this_works"] = how_excerpts(how_read, how_specs(days))
    payload = page_data(real, spec_days) if args.build else real
    data = json.dumps(payload, separators=(",", ":"))
    target = args.build or args.out
    if args.build:
        data = build(data)
    with open(target, "w", encoding="utf-8") as f:
        f.write(data)
    if not args.no_cache:
        save_cache(args.cache)
    print(f"{target}: {len(rows)} snapshots, {len(days)} days, next: {now['next_step']}" + (f" ({note})" if note else "")
          + (" (example data: no day specs yet)" if payload.get("demo") else ""))
    rec = real["defect_recurrence"]
    print(f"defects: {len(rec['recurrences'])} of {rec['with_id']} with an ID repeat an earlier one")
    for p in rec["problems"]:
        print(f"defect ID not counted: {p}")
    for p in real["yardsticks"]["problems"]:
        print(f"yardstick not counted: {p}")
    for g in real["gate_report"]["gates"]:
        print(gate_line(g))


def gate_line(g):
    """One gate's line on the console: what it caught, its runs and cost. A hooks gate with no
    refusal log yet has caught nothing that can be counted, not refused anything."""
    caught = (f"{g['defects']} defects" if g["found"] is not None else
              "no refusal log yet" if g["refused"] is None else f"{g['refused']} refused")
    return f"gate {g['gate']}: {caught}, {g['runs']} runs, ${g['cost']:,.2f}"


if __name__ == "__main__":
    main()
