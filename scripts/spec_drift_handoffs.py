"""spec-drift.py's reading of hand-offs: what one day defers to a later one, and what lies ahead."""

import os
import re
import subprocess

from spec_drift_common import (
    CACHE,
    COMMENT_LINE,
    CRITERION,
    DAY_REF,
    FINISHED,
    HAND_OFF_LINE,
    HAND_OFF_RANGE,
    PHASE_READ,
    PLACEHOLDERS,
)
from spec_drift_git import (
    at_commits,
    day_branch,
    day_of,
    run,
)
from spec_drift_specs import (
    excerpt,
    merged_tracks,
    section,
    track_criteria,
)


def days_named(text):
    out = set()
    for m in DAY_REF.finditer(text):
        nums = [int(m.group(1))] + [int(n) for n in re.findall(r"\d+", m.group(2))]
        out.add(nums[0])
        for sep, a, b in zip(re.findall(r"[–-]|,|and|or", m.group(2)), nums, nums[1:]):
            out.update(range(a, b + 1) if sep in "–-" else {b})
    return out


def hand_off_ids(text):
    """Every hand-off ID a text cites, a range (H34.1–H34.3, or H34.1–3) as each ID in it."""
    out = set()
    for day, a, b in HAND_OFF_RANGE.findall(text):
        out.update(f"H{day}.{n}" for n in range(int(a), int(b or a) + 1))
    return out


def written_by_day(sha, path, number):
    """The day whose PR added a line: its first-parent commit's subject names the day's branch."""
    commit = run("git", "blame", "--first-parent", "--porcelain", "-L", f"{number},{number}",
                 sha, "--", path).split()[0]
    return day_of(run("git", "log", "-1", "--format=%s", commit))


def hand_offs(days, order, sha, blobs):
    """What finished days hand to days not yet run, and whether the receiving spec picked it up.
    A Notes item with an ID of its day (H28.1) is picked up only by a spec that cites the ID; with
    no day ahead to take it and no spec citing it, it is listed with `to` None, as no later day
    picks it up. A day is ahead once plan.md puts it in the order and it is not finished, its spec
    written or not: a day writes its own spec, so between days the next one has none. An item
    without one is picked up when the receiving spec names its day, or a finished day the item
    names (Day 39 points to Day 38's findings); a code comment, when the spec names its file. A
    code comment is not handed to the day whose own PR wrote it: a workflow's
    "(Day 35)" written by Day 35."""
    finished = {d["day"] for d in days if d["status"] in FINISHED}
    text = {d["day"]: blobs.read(sha, d["file"]) for d in days}
    ahead = {d: i for i, d in enumerate(order) if d not in finished and d not in PLACEHOLDERS}
    cited = {t: hand_off_ids(text[t]) for t in text}
    out = []
    for d in days:
        if d["day"] not in finished:
            continue
        for item in re.split(r"\n(?=\s*- )", section(text[d["day"]], "Notes")):
            named = days_named(item)
            ids = sorted(i for i in hand_off_ids(item) if int(i[1:].split(".")[0]) == d["day"])
            if ids and not HAND_OFF_LINE.match(item):
                continue  # cites its day's hand-off, "(H1.2)", and is not one
            if ids:
                cites = {t for t in text if t != d["day"] and set(ids) & cited[t]}
                for t in named & set(ahead) - {d["day"]}:
                    out.append(dict(to=t, id=ids[0], source=f"Day {d['day']:02d} Notes", picked=t in cites, text=item))
                if not cites and not named & set(ahead) - {d["day"]}:
                    out.append(dict(to=None, id=ids[0], source=f"Day {d['day']:02d} Notes", picked=False, text=item))
                continue
            for t in named & set(ahead):
                picked = bool(({d["day"]} | named & finished) & days_named(text.get(t, "")))
                out.append(dict(to=t, source=f"Day {d['day']:02d} Notes", picked=picked, text=item))
    listed = run("git", "grep", "-n", "-I", "-E", r"\bDays? [0-9]+\b", sha, "--", ".", ":(exclude)*.md",
                 ":(exclude)docs/dashboard", ":(exclude)data")
    for line in listed.splitlines():
        path, number, code = line.split(":", 3)[1:]
        stem = os.path.basename(path)
        stem = os.path.splitext(stem)[0] if stem.endswith((".java", ".sql", ".ts", ".py")) else stem
        if COMMENT_LINE.match(code):
            named = days_named(code) & set(ahead)
            if named:
                named -= {written_by_day(sha, path, number)}
            for t in named:
                out.append(dict(to=t, source=f"{path}:{number}", picked=stem in text.get(t, ""), text=code))
    for h in out:
        h["text"] = excerpt(re.sub(r"^\s*(- |//|/\*+|\*|--|#|<!--)\s*", "", h["text"]), 160)
    return sorted(out, key=lambda h: (ahead.get(h["to"], len(order)), h["picked"], h["source"]))


def finished_at(days, order, at):
    """The column of the merge that finished each finished day: its last closing PR, or with none
    on main, the first code or close of a day later in the run order."""
    pos = {d: i for i, d in enumerate(order)}
    out = {}
    for d in days:
        if d["status"] not in FINISHED:
            continue
        mine = [at[p["number"]] for p in d["prs"] if p["kind"] == "close" and p["number"] in at]
        later = [at[p["number"]] for o in days if pos.get(o["day"], len(order)) > pos.get(d["day"], len(order))
                 for p in o["prs"] if p["kind"] in ("code", "close") and p["number"] in at]
        if mine or later:
            out[d["day"]] = max(mine) if mine else min(later)
    return out


def spec_texts(sha, blobs):
    """Each day's spec as it stood at a commit, by day."""
    paths = at_commits("ls-tree", "--name-only", sha, "specs/").split("\n")
    return {day_of(p): blobs.read(sha, p) for p in paths if day_of(p)}


def day_comments(sha):
    """(path, line) for each line outside Markdown that names a day at a commit. git grep exits 1
    when it finds none, which an early commit does."""
    key = "\0".join(("day-comments", sha))
    cached = CACHE.setdefault("git", {})
    if key not in cached:
        got = subprocess.run(["git", "grep", "-n", "-I", "-E", r"\bDays? [0-9]+\b", sha, "--", ".",
                              ":(exclude)*.md", ":(exclude)docs/dashboard", ":(exclude)data"],
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
        if got.returncode > 1:
            raise RuntimeError(f"git grep failed at {sha}: {got.stderr.strip()}")
        cached[key] = got.stdout
    return [tuple(line.split(":", 3)[1::2]) for line in cached[key].splitlines()]


def hand_off_ledger(snaps, days, order, blobs):
    """Every hand-off there has been, with the merge that opened it and the merge that closed it:
    hand_offs() above, asked at each merge and remembered. A Notes line with an ID opens at its
    day's close and is picked up by the first merge after which the spec of each day it names
    cites the ID (any other day's spec, when it names none still ahead); until then it stays
    open. A Notes item or a comment with no ID opens when it first names a
    day still ahead, and closes as picked up by hand_offs()'s rule, as lapsed when the day it
    names finishes without that, or as withdrawn when the line is gone. A comment is not handed
    to the day whose own merge wrote it."""
    at = {s["pr"]: i for i, s in enumerate(snaps) if s["pr"]}
    done = finished_at(days, order, at)
    listed = {d for d in order if d not in PLACEHOLDERS}
    ledger, own = {}, set()
    for i, snap in enumerate(snaps):
        text = spec_texts(snap["sha"], blobs)
        finished = {d for d, col in done.items() if col <= i}
        ahead = listed - finished
        cited = {d: hand_off_ids(t) for d, t in text.items()}
        seen = {}
        for d in sorted(finished & set(text)):
            for item in re.split(r"\n(?=\s*- )", section(text[d], "Notes")):
                named = days_named(item)
                mine = {n for n in hand_off_ids(item) if int(n[1:].split(".")[0]) == d}
                # The ID the line opens with is the hand-off; one it cites further on is another's.
                first = HAND_OFF_RANGE.search(item) if HAND_OFF_LINE.match(item) else None
                source = f"Day {d:02d} Notes"
                to = sorted(named & listed - {d})
                for n in sorted(hand_off_ids(first.group(0)) & mine) if first else ():
                    # As hand_offs() has it: each day it names that is still ahead must cite it; with
                    # none ahead, any other day's spec citing it picks it up.
                    waits = [t for t in to if t in ahead]
                    picked = (all(n in cited.get(t, ()) for t in waits) if waits
                              else any(n in cited[t] for t in text if t != d))
                    seen[n] = dict(id=n, source=source, to=to, text=item, picked=picked)
                if mine:
                    continue  # a hand-off with an ID, or a line citing its day's and not one
                for t in named & ahead - {d}:
                    picked = bool(({d} | named & finished) & days_named(text.get(t, "")))
                    seen[(source, t, item)] = dict(id=None, source=source, to=[t], text=item, picked=picked)
        wrote = day_of(snap.get("branch") or "") or day_of(snap["title"])
        for path, code in day_comments(snap["sha"]):
            if not COMMENT_LINE.match(code):
                continue
            stem = os.path.basename(path)
            stem = os.path.splitext(stem)[0] if stem.endswith((".java", ".sql", ".ts", ".py")) else stem
            for t in days_named(code) & ahead:
                key = (path, t, code.strip())
                if key not in ledger and key not in own and t == wrote:
                    own.add(key)
                if key not in own:
                    seen[key] = dict(id=None, source=path, to=[t], text=code, picked=stem in text.get(t, ""))
        for key, now in seen.items():
            if key not in ledger:
                ledger[key] = dict(id=now["id"], source=now["source"], to=now["to"], opened=i, closed=None, how=None,
                                   text=excerpt(re.sub(r"^\s*(- |//|/\*+|\*|--|#|<!--)\s*", "", now["text"]), 160))
        for key, h in ledger.items():
            if h["closed"] is not None:
                continue
            now = seen.get(key)
            how = ("picked" if now and now["picked"] else
                   "lapsed" if not h["id"] and h["to"][0] in finished else None if now else "withdrawn")
            if how:
                h.update(closed=i, how=how)
    for h in ledger.values():
        h.update(opened_pr=snaps[h["opened"]]["pr"], closed_pr=None if h["closed"] is None else snaps[h["closed"]]["pr"])
    return sorted(ledger.values(), key=lambda h: (h["opened"], h["source"], h["id"] or "", h["to"]))


def built_at(index, days, snaps, order):
    """The column of the merge after which each promise counts as built. A ticked one: the last
    merge among the PRs its evidence cites, or its day's close when it cites none on main. On a
    day still open nothing is ticked, so it counts once its track has merged, at the last merge
    on that track's branch so far."""
    at = {s["pr"]: i for i, s in enumerate(snaps) if s["pr"]}
    done = finished_at(days, order, at)
    by_day = {d["day"]: d for d in days}
    out = {}
    for c in index:
        day = by_day[c["day"]]
        if c["ticked"]:
            cols = [at[p] for p in c["prs"] if p in at]
            col = max(cols) if cols else done.get(c["day"])
        elif day["status"] not in FINISHED and c.get("track"):
            prefix = f"day-{c['day']:02d}/"
            cols = [i for i, s in enumerate(snaps)
                    if (b := day_branch(dict(headRefName=s.get("branch") or "", title=s["title"]))).startswith(prefix)
                    and c["track"] in merged_tracks([b], day.get("tracks", []))]
            col = max(cols) if cols else None
        else:
            col = None
        if col is not None:
            out[c["id"]] = col
    return out


def look_ahead(snaps, days, index, order, blobs):
    """What the graph that looks ahead draws. `columns` has one entry per merge, in the order of
    `rows`: the promises built once it landed and the ones it built (`got`), the promises the
    specs then held (`written`, counted from the specs at that merge), and the hand-offs open
    after it (`open`; `open_numbered` those with an ID). `hand_offs` is the ledger behind the
    bars. `pending` is the open day's tracks that are specified and not merged, each with the
    promises it would build, and the promises no track owns, which wait for the close."""
    ledger = hand_off_ledger(snaps, days, order, blobs)
    built = built_at(index, days, snaps, order)
    columns = []
    for i, snap in enumerate(snaps):
        specs = spec_texts(snap["sha"], blobs)
        still = [h for h in ledger if h["opened"] <= i and (h["closed"] is None or h["closed"] > i)]
        columns.append(dict(
            pr=snap["pr"], built=sum(col <= i for col in built.values()),
            got=[c for c, col in built.items() if col == i],
            written=sum(len(CRITERION.findall(section(t, "Acceptance criteria"))) for t in specs.values()),
            open=len(still), open_numbered=sum(bool(h["id"]) for h in still),
            opened=sum(h["opened"] == i for h in ledger), closed=sum(h["closed"] == i for h in ledger)))
    pending = None
    day = next((d for d in days if d["status"] == "active"), None)
    if day:
        left = [c["id"] for c in index if c["day"] == day["day"] and c["id"] not in built]
        tracks = [dict(track=t, ids=[c for c in track_criteria(day.get("track_work", {}).get(t, "")) if c in left])
                  for t in day.get("tracks", []) if t not in day.get("tracks_merged", [])]
        owned = {c for t in tracks for c in t["ids"]}
        pending = dict(day=day["day"], tracks=tracks, at_close=[c for c in left if c not in owned])
    return dict(columns=columns, hand_offs=ledger, pending=pending,
                built=columns[-1]["built"], written=columns[-1]["written"])


def conclusion(notebook):
    """What the lab notebook says at the head of main: its phase reads, and its measurement table."""
    reads = [dict(phase=int(m.group(1)), text=m.group(0).strip()) for m in PHASE_READ.finditer(notebook)]
    rows = [[c.strip() for c in r.strip().strip("|").split("|")]
            for r in section(notebook, "What is being measured").splitlines() if r.startswith("|")]
    # Any width: the notebook adds a column per day beside the question and its evidence.
    head = rows[0] if len(rows) > 2 and len(rows[0]) >= 2 else []
    return dict(reads=reads, measured=[r for r in rows[2:] if len(r) == len(head)], measured_head=head)
