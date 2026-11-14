"""spec-drift.py's measures: the clock, the chance bands, the names in code, boundaries and yardsticks."""

import builtins
import collections
import posixpath
import re
import subprocess

import numpy as np

from spec_drift_common import (
    BREAK_LINE,
    BREAK_LINE_FROM_PR,
    CACHE,
    CHANCE_DRAWS,
    COMMENT_LINE,
    COMMENT_TAIL,
    FLAG,
    IDENT,
    IMPORT,
    OWN_PACKAGE,
    PLACEHOLDERS,
    SERVICE,
    TEST_NAME,
    TICK,
    WORDS,
)
from spec_drift_git import (
    at_commits,
    ci_pushes,
    day_branch,
    day_of,
    hours_open,
    kind,
    own_day,
    run_spans,
    step_kind,
)
from spec_drift_specs import (
    DEFECT_ID,
    TEST_PATH,
    broke,
)
from spec_drift_data import (
    page_json,
)


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
        # Nothing on a pull request is waited on after it merged: a run that sat queued until GitHub
        # cancelled it days later (#147) ends at the merge, not at its cancellation.
        merged = p.get("mergedAt")
        ended = [dict(r, updatedAt=min(r.get("updatedAt") or r["createdAt"], merged) if merged else r.get("updatedAt"))
                 for r in on if not merged or r["createdAt"] <= merged]
        cancelled = sum(r.get("conclusion") == "cancelled" for r in on)
        unfinished = sum(not r.get("conclusion") for r in on)
        checks = dict(start=min(r["createdAt"] for r in ended), end=max(r.get("updatedAt") or r["createdAt"] for r in ended),
                      runs=len(on), failed=sum(r.get("conclusion") == "failure" for r in on),
                      pushes=len({r.get("headSha") for r in on}),
                      **({"cancelled": cancelled} if cancelled else {}), **({"unfinished": unfinished} if unfinished else {}),
                      spans=run_spans(ended)) if ended else None
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


# The closed list of found: values (specs/README.md), read into stages. self, review and Track <X>
# are one stage, the work. Before the twelfth Day (specs/README.md), evidence replay named both
# the close's rehearsal and the replay after its merge: those lines are read as "unsplit", not
# rewritten. A value off the list is in no stage, and reported.
STAGES = ("auditor", "spec-change PR", "seen red", "break on purpose", "work", "close", "rehearsal",
          "evidence replay", "unsplit", "dashboard", "Day review")
EARLY = ("auditor", "spec-change PR")  # before any code: every other stage is a late catch
SPLIT_FROM = 12


def found_stage(value, day):
    """The stage of a Defect line's found: on a Day, or None when the value is off the list."""
    f = found_tag(value)
    if f in ("self", "review") or re.fullmatch(r"track [a-z]\d*", f):
        return "work"
    if re.fullmatch(r"day \d+ review", f):
        return "Day review"
    if f == "evidence replay" and day < SPLIT_FROM:
        return "unsplit"
    return next((s for s in STAGES if s.lower() == f and s not in ("work", "unsplit", "Day review")), None)


def defect_counts(days):
    """Per Day: its Defect lines, by stage, per criterion, caught late (after a track started) and
    escaped (made on another Day); the blind rater's agreement per tag; and the IDs off the found:
    list. Totals over the Days with a Defect line."""
    rows, rater, off = [], {}, []
    for d in days:
        lines = d.get("defects", [])
        if not lines:
            continue
        stages = [found_stage(x.get("found"), d["day"]) for x in lines]
        made = [re.fullmatch(r"day 0*(\d+)", (x.get("made") or "").strip().lower()) for x in lines]
        criteria = (d.get("criteria") or {}).get("total") or 0
        off += [x.get("id") or f"Day {d['day']}: {x.get('found')}" for x, s in zip(lines, stages) if s is None]
        for tag, (agreed, of) in (d.get("relabel") or {}).items():
            rater[tag] = [a + b for a, b in zip(rater.get(tag, [0, 0]), (agreed, of))]
        rows.append(dict(day=d["day"], defects=len(lines), criteria=criteria,
                         per_criterion=round(len(lines) / criteria, 2) if criteria else None,
                         stages={s: stages.count(s) for s in STAGES if s in stages},
                         late=sum(s is not None and s not in EARLY for s in stages),
                         escapes=sum(bool(m) and int(m.group(1)) != d["day"] for m in made)))
    total = {k: sum(r[k] for r in rows) for k in ("defects", "criteria", "late", "escapes")}
    return dict(days=rows, rater=rater, off_list=off,
                **total, per_criterion=round(total["defects"] / total["criteria"], 2) if total["criteria"] else None)


def defect_count_line(c):
    """The counts' line on the console, and the rater's agreement on cause: alone."""
    cause = c["rater"].get("cause")
    return (f"defect counts: {c['defects']} over {c['criteria']} criteria ({c['per_criterion']} each), "
            f"{c['late']} caught late, {c['escapes']} escaped"
            + (f", rater agreed on cause {cause[0]} of {cause[1]}" if cause else ""))


# The phase-end table (scripts/phase-table.py): the gates it asks whether each found anything, and the
# stages counted as after the close. PHASE_GATES is apart from GATES, which gate_report reads.
AFTER_CLOSE = ("evidence replay", "unsplit", "dashboard", "Day review")
PHASE_GATES = ("auditor", "seen red", "break on purpose", "close", "rehearsal", "evidence replay")


def tally_counts(counted):
    """One tally over the counted Days it holds: the Defect lines by stage, caught late, escaped, found
    after the close, and the gates that found none. A tally of Days all before SPLIT_FROM counts its
    unsplit lines as evidence replay, and has no rehearsal gate to miss."""
    ids = [d["day"] for d in counted]
    lines = [(d["day"], x) for d in counted for x in d.get("defects", [])]
    stages = [found_stage(x.get("found"), day) for day, x in lines]
    made = [(x.get("made") or "").strip().lower() for _, x in lines]
    escapes = 0
    for (day, _), m in zip(lines, made):
        mm = re.fullmatch(r"day 0*(\d+)", m)
        escapes += bool(mm) and int(mm.group(1)) != day
    after = [s in AFTER_CLOSE and m not in ("", "none") for s, m in zip(stages, made)]
    found = collections.Counter(stages)
    old = all(day < SPLIT_FROM for day in ids)
    if old:
        found["evidence replay"] += found["unsplit"]
    silent = [g for g in PHASE_GATES if found[g] == 0 and not (old and g == "rehearsal")]
    criteria = sum((d.get("criteria") or {}).get("total") or 0 for d in counted)
    defects = len(lines)
    return dict(criteria=criteria, defects=defects,
                per_criterion=round(defects / criteria, 2) if criteria else None,
                stages={s: stages.count(s) for s in STAGES if s in stages},
                late=sum(s is not None and s not in EARLY for s in stages),
                escapes=escapes, after_close=sum(after),
                after_close_unsplit=sum(a and s == "unsplit" for a, s in zip(after, stages)),
                silent=silent)


def phase_table(days, prs, tokens, refusals):
    """Per phase, and per counted Day inside one, the tally_counts and the cost. A phase's window starts
    at the earliest PR opened for one of its Days, and a date belongs to the latest start on or before
    it: a date before every start, or a phase with no PR, holds no cost or refusal. Day rows have none."""
    phase_of = {d["day"]: d["phase"] for d in days}
    starts = {}
    for p in prs:
        ph = phase_of.get(p.get("day"))
        if ph is not None:
            starts[ph] = min(starts.get(ph, p["opened"][:10]), p["opened"][:10])

    def owner(date):
        return max(((s, ph) for ph, s in starts.items() if s <= date), default=(None, None))[1]

    def cost(ids):
        return round(sum((t["cost"] for t in tokens if t["day"] in ids), 0.0), 2)

    ordered = sorted(days, key=lambda d: d["day"])
    phase_rows, day_rows = [], []
    for ph in sorted({d["phase"] for d in days}):
        mine = {d["day"] for d in ordered if d["phase"] == ph}
        counted = [d for d in ordered if d["phase"] == ph and d.get("defects")]
        guards = collections.Counter()
        for r in refusals:
            if owner(r["date"][:10]) == ph:
                guards[r["guard"]] += r["refused"]
        between = sum((t["cost"] for t in tokens if t["day"] is None and owner(t["date"][:10]) == ph), 0.0)
        phase_rows.append(dict(phase=ph, days=[d["day"] for d in counted], **tally_counts(counted),
                               cost_days=cost(mine), cost_between=round(between, 2),
                               refusals=dict(sorted(guards.items()))))
        day_rows += [dict(day=d["day"], phase=ph, **tally_counts([d]), cost_days=cost({d["day"]}),
                          cost_between=None, refusals=None) for d in counted]
    return dict(phases=phase_rows, days=day_rows)
