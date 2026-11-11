"""spec-drift.py's reading of plan.md and the day specs: steps, tracks, criteria, evidence and removals."""

import collections
import fnmatch
import os
import posixpath
import re
import shlex

from spec_drift_common import (
    BREAK_LINE,
    BREAK_LINE_FROM_PR,
    CITED_PR,
    CI_PROPERTY,
    CLEANUP,
    CLOSEOUT,
    CRITERION,
    CRITERION_ID,
    EVIDENCE_TEST,
    FINISHED,
    FOUND_SHOWN,
    GREP_OR_ECHO,
    GREP_SAYS_NOTHING,
    MOVED,
    ON_PROPERTY,
    PLACEHOLDERS,
    PLATFORM,
    PY_CLASS,
    RENAMED,
    SKIPPABLE,
    TRACK_NAMED,
    VERIFY_BASES,
)
from spec_drift_git import (
    at_commits,
    day_branch,
    day_of,
    kind,
    run,
)


TEST_PATH = re.compile(r"(^|/)tests?/|(^|/)(tests?|test_[^/]*|[^/]*_test|conftest)\.py$|(Test|Tests|IT)\.java$"
                       r"|\.(test|spec)\.[jt]sx?$")


def broke(text):
    """Whether text has a `broken:` line for a break, not a `broken: none → <why>`."""
    return any(w.lower() != "none" for w in BREAK_LINE.findall(text or ""))


def broke_in(text):
    """The PRs the `broken:` lines in text cite, for the breaks they record (not `none`)."""
    return sorted({int(n) for m in BREAK_LINE.finditer(text or "") if m.group(1).lower() != "none"
                   for n in CITED_PR.findall(text[m.start():].split("\n", 1)[0])})


def broken_at_close(day):
    """A day's ticked criteria whose every break cites its closing PR: the check was first seen
    red at the close, not in the PR that wrote it. Four of the paper's six spec escapes were these
    (docs/paper, Appendix F). A criterion whose break lines cite no PR is not judged."""
    closing = {p["number"] for p in day["prs"] if p["kind"] == "close"}
    return [c["id"] or c["claim"] for c in day["evidence"]
            if c["ticked"] and closing and c["broke_in"] and set(c["broke_in"]) <= closing]


RELABEL = re.compile(r"relabel\.py compare`\)?:?\s*([^`]{0,120})")
RELABEL_FIELD = re.compile(r"\b(stage|cause|made)\s+(\d+)\s+of\s+(\d+)")


# The count lines `relabel.py compare` prints and a closing PR pastes, one line per axis.
RELABEL_LINE = re.compile(r"^[ \t]*(stage|cause|made): (\d+) of (\d+) agree\b", re.M)


def final_run(body):
    """The last `relabel.py compare` run a closing PR's body pastes (a day may rerun the rater): its
    counts, None where it pastes none, False where the lines are not whole runs or their last run
    cannot be right. False is never guessed into a count."""
    lines = RELABEL_LINE.findall(body or "")
    if not lines:
        return None
    if [f for f, _, _ in lines] != ["stage", "cause", "made"] * (len(lines) // 3):
        return False
    last = {f: [int(a), int(n)] for f, a, n in lines[-3:]}
    return last if all(0 < n and a <= n for a, n in last.values()) else False


def relabel(text, bodies=()):
    """How often the blind defect-rater agreed with the tags the close gave: the final run the day's
    closing PR bodies paste; where none pastes one, what the spec's Notes quote from `relabel.py
    compare` ("stage 3 of 4, cause 3 of 4, made 4 of 4"). None where a body's lines are unclear, two
    closing PRs differ, or the day tells it in prose: not counted, and not counted as agreeing."""
    runs = [r for r in map(final_run, bodies) if r is not None]
    if runs:
        return runs[0] if runs[0] and all(r == runs[0] for r in runs) else None
    for m in RELABEL.finditer(text):
        found = {f: [int(a), int(n)] for f, a, n in RELABEL_FIELD.findall(m.group(1))}
        if found:
            return found
    return None


# A Defect line (specs/README.md): "- **Defect** D28.1 — found: … · same-as: D21.2 · <text>". The
# ID and same-as: are optional; same-as: is one of the fields before the text, as relabel.py reads them.
DEFECT_LINE = re.compile(r"^- \*\*Defect\*\*(?:[ \t]+(\S+))?\s*[—-]\s*(.*)$")
DEFECT_FIELD = re.compile(r"^(found|cause|made|same-as):\s*(.*)$")
DEFECT_ID = re.compile(r"D(\d+)\.(\d+)")


def defect_lines(text, day):
    """Each Defect line in a spec: its ID and the ID its same-as: names, as written (None if absent),
    and a problem when its own ID is not one of this day's."""
    lines, out = text.splitlines(), []
    for i, line in enumerate(lines):
        m = DEFECT_LINE.match(line)
        if not m:
            continue
        rest = [m.group(2)]
        for more in lines[i + 1:]:
            if not more.startswith("  ") or not more.strip():
                break
            rest.append(more.strip())
        fields = {}
        for part in (p.strip() for p in " ".join(rest).split(" · ")):
            f = DEFECT_FIELD.match(part)
            if not f or f.group(1) in fields:
                break
            fields[f.group(1)] = f.group(2)
        ok = DEFECT_ID.fullmatch(m.group(1) or "")
        out.append(dict(id=m.group(1), same_as=fields.get("same-as"), found=fields.get("found"), cause=fields.get("cause"),
                        made=fields.get("made"),  # as written: "Day 04", or "none" for one made outside any day
                        problem=None if m.group(1) is None or ok and int(ok.group(1)) == day
                        else f"Day {day}: Defect ID {m.group(1)} is not D{day}.<n>"))
    return out


def section(text, heading):
    m = re.search(rf"^## {heading}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


# Every number is a day but a phase's: "Phase 3:", "Phases 6–7", "after Phase 7", "end-of-Phase-7".
UNPHASED = re.compile(r"Phases?[\s-]*\d+(?:\s*[–-]\s*\d+)?")


def plan_items(plan):
    """The numbered items of plan.md's "Day-by-day specs" list, each on one line: an item may wrap mid-phrase."""
    return [" ".join(item.split()) for item in
            re.findall(r"^\d+\.\s+(.*(?:\n {3}.*)*)", section(plan, "Day-by-day specs"), re.M)]


def stops(plan):
    """The days plan.md's list marks **Stop and evaluate.**, each the last day its item names. A stop
    a course correction has lifted is still one: the roadmap shows where the plan stopped."""
    out = []
    for item in plan_items(plan):
        days = re.findall(r"\d+", UNPHASED.sub("", item))
        if "Stop and evaluate" in item and days:
            out.append(int(days[-1]))
    return out


def phases(plan):
    """Each phase's name, by number, from plan.md's "### Phase N — <name>" headings; "" for a number with none."""
    named = {int(n): name.strip() for n, name in re.findall(r"^### Phase (\d+) [—–-] (.+)$", plan, re.M)}
    return [named.get(p, "") for p in range(max(named, default=-1) + 1)]


def lifted(plan, phase):
    """Whether plan.md lifts the stop of Phase `phase`: a "Course correction after Phase N" section,
    or an entry for it under the template's "Course corrections", outside its comment: a heading
    saying "after Phase N" or a bullet opening "**Phase N stop:**". A pilot of the kit put its
    stop's decisions there, and three days ran under the stop. Naming the phase in passing lifts
    nothing: bearing's entry before Day 2 mentioned Phase 1, and the dashboard offered Day 5."""
    corrections = re.sub(r"<!--.*?-->", "", section(plan, "Course corrections"), flags=re.S)
    return bool(section(plan, f"Course correction after Phase {phase}")
                or re.search(rf"^(?:#+ .*\bafter Phase {phase}\b|[-*] \*\*Phase {phase} stop\b)",
                             corrections, re.M))


def run_order(plan, spec_days):
    """The order days run in, from plan.md's "Day-by-day specs" list, and the day after which work
    stops to be evaluated. Days the list does not name (the finished ones) come first. A day named
    twice runs at its last mention: Day 24's profile endpoint comes first, the rest of it last.
    "Numbered after the last" is a day not yet written, after every day the list names. A stop is
    lifted once plan.md has the course correction for its phase; work waits at the first stop not
    lifted, not the last (bearing: stops at Days 4 and 10). An item marked **cut** takes its
    days out of the order: Phase 6's Days 29-31, cut after Phase 7, run nowhere."""
    listed, cut, stop = [], [], None
    lines = plan_items(plan)
    unphased = lambda line: UNPHASED.sub("", line)
    last = max((int(n) for line in lines for n in re.findall(r"\d+", unphased(line))), default=0)
    for line in lines:
        days = []
        for a, b in re.findall(r"(\d+)(?:\s*[–-]\s*(\d+))?", unphased(line)):
            if "numbered from" in line:
                days += sorted(d for d in spec_days if d >= int(a)) or [PLATFORM]
            else:
                days += range(int(a), int(b or a) + 1)
        if "numbered after the last" in line:
            days = sorted(d for d in spec_days if d > last) or [CLOSEOUT if "close-out" in line else CLEANUP]
        if "**cut**" in line:
            cut += days
            continue
        listed += days
        phase = re.search(r"Phase (\d+)", line)
        if (stop is None and "Stop and evaluate" in line and days
                and not (phase and lifted(plan, phase.group(1)))):
            stop = days[-1]
    listed = [d for i, d in enumerate(listed) if d not in listed[i + 1:]]
    return [d for d in sorted(spec_days) if d not in listed + cut] + listed, stop


def out_of_order(order):
    """The days that do not run in numeric order: those outside the longest run of the order that
    rises by number: Days 38-40 ran ahead of Day 17, Day 17 behind Days 18-19, and Day 25 is planned
    behind Days 26-27."""
    days = [d for d in order if d not in PLACEHOLDERS]
    best = []  # best[i]: the longest rising run that ends at days[i]
    for i, d in enumerate(days):
        best.append(max((best[j] for j in range(i) if days[j] < d), key=len, default=[]) + [d])
    keep = set(max(best, key=len, default=[]))
    return [d for d in days if d not in keep]


# A closing PR the gate split, "Day 43 close, part 1": one part of the close, not all of it.
CLOSE_PART = re.compile(r"\bpart \d+\b", re.I)


def closes(day):
    """Whether a day's own closing PR has merged. A part of a split close (#428) ends the day only
    once every box is ticked: until the last part merges, its boxes are still open."""
    c = day["criteria"]
    return any(p["kind"] == "close" and not (CLOSE_PART.search(p.get("title", "")) and c["ticked"] < c["total"])
               for p in day["prs"])


def settle(days, order):
    """Each day's status. A day is finished once a day later in the run order has code merged, or
    its own closing PR has; finished with every box ticked is done, with boxes open is closed
    (Day 05 left two open). The first unfinished day is active."""
    pos = {d: i for i, d in enumerate(order)}
    worked = max((pos[d["day"]] for d in days if d["day"] in pos
                  and any(p["kind"] in ("code", "close") for p in d["prs"])), default=-1)
    for d in days:
        at = pos.get(d["day"], len(order))
        c = d["criteria"]
        if at < worked or (at == worked and closes(d)):
            d["status"] = "done" if c["total"] and c["ticked"] == c["total"] else "closed"
        elif d["status"] == "done":
            d["status"] = "ready"
    by_day = {d["day"]: d for d in days}
    for d in order:
        if d in PLACEHOLDERS or d not in by_day:  # not written yet: no day to mark
            break
        if by_day[d]["status"] not in FINISHED:
            by_day[d]["status"] = "active"
            break
    return days


# A track's name is a letter or a digit, with a number when a day splits one (Day 39's A1, A2),
# or a lowercase letter (Day 20's 0a, 0b).
TRACK_ROW = re.compile(r"^\| *([0-9A-Z][0-9]?[a-z]?) *\|")


def track_names(section_text):
    """The tracks a day's table lists, in its order."""
    return [m.group(1) for line in section_text.splitlines() if (m := TRACK_ROW.match(line))]


def merged_tracks(branches, tracks):
    """The tracks with a merged branch. `track-a1-...` is A1 when the table lists A1; otherwise it
    is part of A, as Day 15's `track-c1`..`c4` were its one track C. A letter after the digits is a
    part of that track: Day 17 split B1 again into `track-b1a`..`b1c`, unless the table lists it
    with that letter, as Day 20 lists 0a and 0b."""
    by_lower = {t.lower(): t for t in tracks}
    merged = set()
    for branch in branches:
        m = re.search(r"/track-([0-9a-z])([0-9]*)([a-z]?)(?:-|$)", branch)
        if m:
            head, number, part = m.groups()
            name = next((by_lower[c] for c in (head + number + part, head + number) if c in by_lower),
                        head.upper())
            merged.add(name)
    return sorted(merged)


def unopened_tracks(day_prs):
    """Tracks a day's PRs name that no branch of the day ever did: #298 announced E1c, and the day
    read as done for a day before #305 opened it. A branch covers the tracks it begins (`track-e1`
    covers E1c) and those that begin it (`track-b` was Day 22's B1). Only letters a branch uses count."""
    branches = {m.group(1) for p in day_prs if (m := re.search(r"/track-([0-9a-z]+?)(?:-|$)", day_branch(p)))}
    found = {}
    for p in sorted(day_prs, key=lambda p: p["number"]):
        for t in TRACK_NAMED.findall(p.get("body") or ""):
            low = t.lower()
            if low[0] in {b[0] for b in branches} and not any(b.startswith(low) or low.startswith(b) for b in branches):
                found.setdefault(t, p["number"])
    return [dict(track=t, pr=n) for t, n in sorted(found.items())]


def excerpt(text, n):
    """text on one line, cut at a word within n characters and never inside a code span."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0]
    if cut.count("`") % 2:
        cut = cut[:cut.rindex("`")].rstrip()
    return cut + "…"


def criteria(section_text):
    """Each criterion under "Acceptance criteria": its kind, whether it is ticked, and the PRs,
    tests and `broken:` lines written into it."""
    out = []
    for block in re.split(r"^(?=- \[[ x]\])", section_text, flags=re.M):
        if not block.startswith("- ["):
            continue
        tag = re.search(r"\*\*(new|hold)\*\*", block)
        body = block[5:].lstrip()
        cid = CRITERION_ID.match(body)
        claim = excerpt(re.sub(r"^(\*\*\w+\*\*\s*—\s*)?", "", body[cid.end() if cid else 0:]), 140)
        out.append(dict(id=f"C{cid.group(1)}.{cid.group(2)}" if cid else None,
                        ticked=block.startswith("- [x]"), kind=tag.group(1) if tag else None,
                        claim=claim, prs=sorted({int(n) for n in CITED_PR.findall(block)}),
                        tests=sorted({c + ("." + m if m else "") for c, m in EVIDENCE_TEST.findall(block)}),
                        red=broke(block), broke_in=broke_in(block), block=block))
    return out


def replacement_lines(block):
    """The IDs before '— was:' on each Replaces line, as used by the behaviour index."""
    short = r"S-[a-z0-9]+(?:-[a-z0-9]+)*\.\d+"
    return [(line, re.findall(rf"\b(?:C\d+\.\d+|{short})\b", line.split("\u2014")[0]))
            for line in re.findall(r"^[ \t]*Replaces:(.*)$", block, re.M)]


def in_evidence_format(crit):
    """Whether a spec was written to the evidence format (#55: every criterion new or hold, every
    check seen to fail), which came in on Day 9. A spec written before it tags no criterion, and
    nothing asked its ticks to cite a PR, name a test or record a break: its zeros are not measured."""
    return any(c["kind"] for c in crit)


def moves(snaps):
    """The test classes that moved under a new name, and the merge each move completed at, as
    (index, old, new). A test moved into a service ends in Test, not IT (the unit-test run takes it there),
    and is rewritten for that service's harness, too much for git to call it a rename: Day 21
    moved PostingShortlistUnavailableIT to matching-service at 27% alike. So a move is told by
    name: a class leaves the tree, and a class of the same stem arrives in that merge or a later
    one. Day 17 deleted SavedJobCountsUnavailableIT in #174, and its Test arrived in #180. Only a
    test moves: StubLlm leaving and StubLlmTest arriving is a helper gone and a test of it. A
    name can arrive more than once (InternalCallsObservedTest in matching-service on Day 21, then
    in application-service in #305, after the IT left in #296): the first arrival at or after
    the test left is where it went. A move to another stem is in RENAMED."""
    at = {s["sha"]: i for i, s in enumerate(snaps)}
    added, deleted, i = collections.defaultdict(list), {}, None
    for line in run("git", "log", "--first-parent", "--diff-merges=first-parent", "--no-renames", "--reverse",
                    "--name-status", "--format=@%h", snaps[-1]["sha"], "--", "*.java", "*.kt").splitlines():
        if line.startswith("@"):
            i = at.get(line[1:])
        elif line[:1] in ("A", "D") and i is not None:
            name = os.path.splitext(os.path.basename(line.split("\t")[-1]))[0]
            if line[0] == "A":
                added[name].append(i)
            else:
                deleted[name] = i
    stem = lambda n: re.sub(r"(?:IT|Tests?)$", "", n)
    out = []
    for old, gone in ((n, k) for n, k in deleted.items() if stem(n) != n):
        new = min(((k, n) for n, ks in added.items() if n != old and stem(n) == stem(old)
                   for k in ks if k >= gone), default=None)
        if new:
            out.append((new[0], old, new[1]))
    pr_at = {s["pr"]: i for i, s in enumerate(snaps) if s.get("pr")}
    return out + [(pr_at[n], old, new) for n, (old, new) in RENAMED.items() if n in pr_at]


def test_state(tests, sha, blobs, moved=None):
    """Where each named test stands at a commit: present, skippable (a class or file CI can skip,
    unless CI meets its condition), or missing. CI runs every test that is present, so a hold
    goes quiet only by its test leaving the tree or being switched off. A class that has left
    the tree is looked for under the name it moved to by then (moved: old to new). A Java or Kotlin
    class is its file's name; a Python test file holds its classes under other names (CliTest in
    tests/test_cli.py), so they are read from it."""
    files, ci = collections.defaultdict(list), set()
    for path in (line.split("\t", 1)[1] for line in at_commits("ls-tree", "-r", sha).splitlines()):
        if path.endswith((".java", ".kt")):
            files[os.path.splitext(os.path.basename(path))[0]].append(path)
        elif path.endswith(".py") and TEST_PATH.search(path):
            for cls in set(PY_CLASS.findall(blobs.read(sha, path))):
                files[cls].append(path)
        elif path.startswith(".github/workflows/"):
            ci.update(CI_PROPERTY.findall(blobs.read(sha, path)))
    met = lambda m: "" if m.group(1) in ci else m.group(0)
    out = {}
    for t in tests:
        cls, _, member = t.partition(".")
        seen = {cls}
        while cls not in files and (moved or {}).get(cls) not in seen | {None}:
            cls = moved[cls]
            seen.add(cls)
        texts = [blobs.read(sha, p) for p in files.get(cls, [])]
        if not any(not member or re.search(rf"\b{member}\b", x) for x in texts):
            out[t] = "missing"
        else:
            out[t] = "skippable" if any(SKIPPABLE.search(ON_PROPERTY.sub(met, x)) for x in texts) else "present"
    return out


def roadmap(snaps, prs, blobs):
    head = snaps[-1]["sha"]
    merged = [p for p in prs.values() if p.get("state") == "MERGED"]
    days = []
    # A day's spec can be renamed (Day 10 was), so its first estimate is looked up by day.
    first_files = {day_of(f): f for f in run("git", "ls-tree", "--name-only", snaps[0]["sha"], "specs/").split()}
    for path in sorted(run("git", "ls-tree", "--name-only", head, "specs/").split()):
        d = day_of(path)
        if not d:
            continue
        text, first = blobs.read(head, path), blobs.read(snaps[0]["sha"], first_files.get(d, path))
        crit = section(text, "Acceptance criteria")
        tracks = track_names(section(text, "Tracks"))
        work = {r.split("|")[1].strip(): r.split("|")[3].strip() for r in section(text, "Tracks").splitlines()
                if TRACK_ROW.match(r)}
        mine = sorted((p for p in merged if day_branch(p).startswith(f"day-{d:02d}/")), key=lambda p: p["number"])
        done_tracks = merged_tracks([day_branch(p) for p in mine], tracks)
        worked = sorted(s["date"] for s in snaps if s["pr"] in {p["number"] for p in mine})
        ticked, total = crit.count("- [x]"), len(CRITERION.findall(crit))
        exp = re.search(r"Expected PRs:\*\* *(\d+)", text)
        exp0 = re.search(r"Expected PRs:\*\* *(\d+)", first)
        phase = re.search(r"\*\*Phase:\*\* *(\d+)", text)
        title = re.search(r"^# Day \d+ — (.+)$", text, re.M)
        ev = criteria(crit)
        status = ("done" if total and ticked == total
                  else "cut" if "**Status:** cut" in text
                  else "provisional" if "**Status:** provisional" in text else "ready")
        days.append(dict(day=d, file=path, title=title.group(1) if title else path, phase=int(phase.group(1)) if phase else None,
                         status=status, expected=int(exp.group(1)) if exp else None,
                         expected_first=int(exp0.group(1)) if exp0 else None,
                         tracks=tracks, track_work=work, tracks_merged=done_tracks,
                         tracks_unopened=unopened_tracks([p for p in prs.values()
                                                          if day_branch(p).startswith(f"day-{d:02d}/")]),
                         track_prs=sum(kind(p["title"], day_branch(p)) == "code" for p in mine),
                         prs=[dict(number=p["number"], kind=kind(p["title"], day_branch(p)), title=p["title"]) for p in mine],
                         criteria=dict(total=total, ticked=ticked, new=crit.count("**new**"), hold=crit.count("**hold**")),
                         worked=[worked[0], worked[-1]] if worked else None,
                         evidence_format=in_evidence_format(ev),
                         break_format=any(p["number"] >= BREAK_LINE_FROM_PR for p in mine),
                         evidence=ev, removal_checks=removal_checks(text),
                         relabel=relabel(text, [p.get("body") for p in mine if kind(p["title"], day_branch(p)) == "close"]),
                         defects=defect_lines(text, d)))
        days[-1]["broken_at_close"] = broken_at_close(days[-1])
    order, stop = run_order(blobs.read(head, "plan.md"), [d["day"] for d in days])
    return evidence(settle(days, order), snaps, blobs), order, stop


def evidence(days, snaps, blobs):
    """Where each finished day's named tests stand on main. A name counts as evidence if it was in
    the tree when the day's last PR merged: a claim can offer a choice (Day 14: one IT "or a case
    added to" another), and a day can rewrite a test it names (Day 11), and neither is a loss."""
    at = {s["pr"]: i for i, s in enumerate(snaps) if s["pr"]}
    named = {t for d in days for c in d["evidence"] for t in c["tests"]}
    now = test_state(named, snaps[-1]["sha"], blobs, {old: new for _, old, new in moves(snaps)})
    for d in days:
        ended = sorted(at[p["number"]] for p in d["prs"] if p["number"] in at)
        if d["status"] not in FINISHED or not ended:
            d["evidence"] = [dict(c, tests={}) for c in d["evidence"]]
            continue
        d["ended_at"] = ended[-1]
        then = test_state({t for c in d["evidence"] for t in c["tests"]}, snaps[ended[-1]]["sha"], blobs)
        for c in d["evidence"]:
            c["tests"] = {t: now[t] for t in c["tests"] if then[t] != "missing"}
    return days


def snap_day(s):
    """The day a merge is read as, as day_branch reads its PR: the day its branch names, or its title's track."""
    return day_of(day_branch(dict(headRefName=s["branch"], title=s["title"])))


def spec_names(text, test):
    """Whether a spec names a test, by its class or its member, as a word."""
    cls, _, member = test.partition(".")
    return any(re.search(rf"\b{w}\b", text) for w in (cls, member) if w)


def evidence_history(rows, days, snaps, blobs):
    """At each merge, where the tests of the days finished by then stand: the check that a hold's
    test has not left the tree or been switched off, merge by merge, as CI cannot see it. A test that
    goes missing in a merge whose day's spec names it is retired, not lost: a later day took it out."""
    moved, head = moves(snaps), snaps[-1]["sha"]
    specs = {d["day"]: blobs.read(head, d["file"]) for d in days if d.get("file")}
    last, retired = {}, set()
    for i, (r, s) in enumerate(zip(rows, snaps)):
        names = {t for d in days if d.get("ended_at", len(snaps)) <= i for c in d["evidence"] for t in c["tests"]}
        states = test_state(names, s["sha"], blobs, {old: new for k, old, new in moved if k <= i})
        spec = specs.get(snap_day(s), "")
        for t, st in states.items():
            if st == "missing" and (last.get(t) == "retired" or (last.get(t) == "present" and spec_names(spec, t))):
                states[t] = "retired"
            last[t] = states[t]
        retired = {t for t, st in states.items() if st == "retired"}
        r["evidence"] = ({k: list(states.values()).count(k) for k in ("present", "skippable", "missing", "retired")}
                         if names else None)
    for d in days:  # the page's list agrees with the last merge's count
        for c in d["evidence"]:
            c["tests"] = {t: "retired" if t in retired else st for t, st in c["tests"].items()}


def removal_checks(text):
    """The greps a day's criteria and Verify say print nothing, each once. Notes and Goal can quote
    a grep without it being a check (Day 08's "TODO day-08"), so they are not read."""
    crit = re.sub(r"\s+", " ", section(text, "Acceptance criteria"))
    verify = "\n".join(re.findall(r"^```bash\n(.*?)^```", section(text, "Verify"), re.M | re.S))
    return list(dict.fromkeys(c.strip() for c in GREP_SAYS_NOTHING.findall(crit) + GREP_OR_ECHO.findall(verify)))


def grep_rule(cmd):
    """A grep as (regex, paths, include glob), or None for one this does not run (a pipe)."""
    try:
        args = shlex.split(cmd)[1:]
    except ValueError:
        return None
    if "|" in args:
        return None
    flags = "".join(a[1:] for a in args if a.startswith("-") and not a.startswith("--"))
    include = next((a.split("=", 1)[1] for a in args if a.startswith("--include=")), None)
    words = [a for a in args if not a.startswith("-")]
    if not words:
        return None
    pattern = words[0]
    if "E" not in flags:  # basic regex: \| \( \+ ... are the operators, | ( + ... are literal
        pattern = re.sub(r"\\([|(){}+?])|([|(){}+?])", lambda m: m.group(1) or "\\" + m.group(2), pattern)
    return re.compile(pattern, re.I if "i" in flags else 0), words[1:] or ["."], include


def in_scope(path, scope):
    """Whether a tree path is the file, or under the directory, a shell path names; * stays in one level."""
    want = [p for p in scope.split("/") if p not in ("", ".")]
    have = path.split("/")
    return len(have) >= len(want) and all(fnmatch.fnmatchcase(h, w) for h, w in zip(have, want))


def follow(scope, moves):
    """The paths a shell path names after these moves, (old, new) in order. A path inside a moved
    directory goes with it; one that names a parent of it (backend, backend/*/src) keeps reading
    where it was and also reads where the directory went."""
    out = [scope]
    for old, new in moves:
        o, nxt = old.split("/"), []
        for sc in out:
            s = [p for p in sc.split("/") if p not in ("", ".")]
            if s[:len(o)] == o:
                nxt.append("/".join([new] + s[len(o):]))
                continue
            if all(fnmatch.fnmatchcase(a, b) for a, b in zip(o, s)):
                nxt.append("/".join([new] + s[len(o):]))
            nxt.append(sc)
        out = nxt
    return out


def removal_history(days, snaps, blobs, moved=None):
    """Each finished day's removal checks, run at every merge from the day's end: the files each
    reads, the lines it finds, and on the last merge which lines. Paths are read from the Verify
    base under which more of them exist, the first on a tie, and follow the directories that moved
    (MOVED, unless given). A check that reads no files prints
    nothing too, so the files are counted. Blobs are counted once, by id."""
    checks = [dict(day=d["day"], cmd=cmd, since=d["ended_at"], rule=grep_rule(cmd), hits=[], files=[], found=[])
              for d in days if "ended_at" in d for cmd in d["removal_checks"]]
    checks = [c for c in checks if c["rule"]]
    pr_at = {s["pr"]: i for i, s in enumerate(snaps) if s.get("pr")}
    seen = {}
    for i, s in enumerate(snaps):
        live = [c for c in checks if c["since"] <= i]
        if not live:
            continue
        moves = [(old, new) for n, old, new in (MOVED if moved is None else moved) if pr_at.get(n, len(snaps)) <= i]
        scopes_from = lambda b, paths: [f for p in paths for f in follow(posixpath.normpath(posixpath.join(b, p)), moves)]
        tree = [(meta.split()[2], path) for meta, path in (line.split("\t", 1) for line in
                at_commits("ls-tree", "-r", s["sha"]).splitlines()) if meta.split()[1] == "blob"]
        for c in live:
            rx, paths, include = c["rule"]
            if "base" not in c:
                c["base"] = max(VERIFY_BASES, key=lambda b: sum(
                    any(in_scope(f, sc) for _, f in tree) for sc in scopes_from(b, paths)))
            scopes = scopes_from(c["base"], paths)
            n = files = 0
            for oid, path in tree:
                if (any(in_scope(path, sc) for sc in scopes)
                        and (include is None or fnmatch.fnmatchcase(posixpath.basename(path), include))):
                    files += 1
                    if (c["cmd"], oid) not in seen:
                        text = blobs.read(s["sha"], path)
                        seen[c["cmd"], oid] = 0 if "\0" in text else sum(bool(rx.search(x)) for x in text.splitlines())
                    n += seen[c["cmd"], oid]
                    if i == len(snaps) - 1 and seen[c["cmd"], oid]:
                        c["found"] += [dict(path=path, line=k, text=x.strip()[:160]) for k, x in
                                       enumerate(blobs.read(s["sha"], path).splitlines(), 1) if rx.search(x)]
            c["hits"].append(n)
            c["files"].append(files)
            c["found"] = c["found"][:FOUND_SHOWN]
    return [dict(day=c["day"], cmd=c["cmd"], base=c["base"] or ".", since=c["since"], hits=c["hits"],
                 files=c["files"], found=c["found"]) for c in checks]


def criterion_evidence(block):
    match = re.search(r"(?im)^\s*Evidence:\s*(.*(?:\n(?!\s*(?:broken:|Replaces:))\s+[^\n]+)*)", block)
    return match.group(1) if match else ""


def track_criteria(work):
    ids = []
    for match in re.finditer(r"C(\d+)\.(\d+)(?:\s*[–-]\s*C?\1\.(\d+))?", work):
        day, start, end = match.groups()
        ids.extend(f"C{day}.{n}" for n in range(int(start), int(end or start) + 1))
    return ids


def evidence_test_names(block):
    return sorted({c + ("." + m if m else "") for c, m in EVIDENCE_TEST.findall(criterion_evidence(block))})
