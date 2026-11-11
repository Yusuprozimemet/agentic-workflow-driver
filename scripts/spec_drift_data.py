"""spec-drift.py's reading of what git and GitHub cannot give: the dashboard-data branch and the evidence report."""

import json
import os
import re
import subprocess

from spec_drift_common import (
    DATA,
    DATA_BRANCH,
    DATA_FILES,
    DATA_FOLDER,
    FINISHED,
    PAGE,
)
from spec_drift_git import (
    day_of,
    park_issue,
)


def counted():
    """When scripts/token-usage.py last counted this machine's transcripts and refusal log
    (docs/dashboard/counted.json), or None before it wrote one: the page's dollars, refusals,
    gate runs and sessions end there, while its pull requests come from GitHub and go on."""
    return page_json("counted.json") or None


def driver_runs(issues, runs=None):
    """What the page knows of the driver, for whichever project this runs in: the steps the driver
    started as scripts/driver-runs.py last counted its run log into docs/dashboard/driver-runs.json
    (that file's format is the contract; before its first count, steps is None and the page draws
    nothing of the driver), each park given the number of its issue, beside the parked issues from
    GitHub. Times are UTC, as both give them; the page moves them to the sessions' clock."""
    runs = page_json("driver-runs.json") if runs is None else runs
    runs = runs if isinstance(runs, dict) else {}
    steps = runs.get("steps")
    if steps is not None:
        steps = [dict(s, parks=[dict(p, issue=park_issue(p, issues or [])) for p in s.get("parks", [])]) for s in steps]
    return dict(source="docs/dashboard/driver-runs.json", counted=runs.get("counted"), steps=steps, parks=issues)


def data_git(*args):
    return subprocess.run(["git", "-C", os.path.join(PAGE, os.pardir, os.pardir), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))


def data_branch(remote="origin"):
    """Fetches the data branch and keeps in DATA its commit, the time of that commit and the files it
    holds; with no such branch on the remote, or no remote, DATA stays empty and every file is absent.
    A fetch that fails (offline) leaves the branch as it was last fetched."""
    ref = f"refs/remotes/{remote}/{DATA_BRANCH}"
    data_git("fetch", "-q", remote, f"+refs/heads/{DATA_BRANCH}:{ref}")
    p = data_git("log", "-1", "--format=%H %cI", ref, "--")
    if p.returncode or not p.stdout.strip():
        DATA.update(commit=None, at=None, held=())
        return DATA
    commit, at = p.stdout.split()
    held = data_git("ls-tree", "--name-only", f"{commit}:{DATA_FOLDER}").stdout.split()
    DATA.update(commit=commit, at=at, held=tuple(held))
    return DATA


def data_text(name):
    """One of DATA_FILES as the data branch holds it, or None when the branch or the file is missing."""
    if not DATA["commit"] or name not in DATA["held"]:
        return None
    p = data_git("show", f"{DATA['commit']}:{DATA_FOLDER}/{name}")
    return None if p.returncode else p.stdout


def data_source():
    """What the page says of where its counts and re-check rows came from: the branch's commit and when
    it was made, or None when there is no branch; and the files it lacks, each drawn as not on record."""
    return dict(branch=DATA_BRANCH, commit=DATA["commit"] and DATA["commit"][:12], at=DATA["at"],
                absent=[n for n in DATA_FILES if n not in DATA["held"]])


def page_json(name):
    """One of the files on the data branch, parsed, or nothing when it is not there."""
    text = data_text(name)
    return json.loads(text) if text else []


def token_usage():
    """Tokens per date, migration day and model, as scripts/token-usage.py last counted them."""
    return page_json("token-usage.json")


# A criterion's state at a merge is the first of these any of its checks is in (scripts/replay-history.py).
REPLAY_WORST = ["code broken", "test weakened", "break no longer applies", "not runnable",
                "not applicable on this platform", "live only", "holds, never broken", "holds"]
REPLAY_STATES = REPLAY_WORST + ["not yet in force"]


def replay_row_state(r):
    """A row's state; an older file's "holds" with no break to check its teeth reads as "holds, never broken"."""
    if r["state"] == "holds" and (r.get("detail") or "").startswith("teeth unchecked"):
        return "holds, never broken"
    return r["state"]


def replay_state(states):
    """The worst of a criterion's check states; "not yet in force" only when every check is."""
    live = [s for s in states if s != "not yet in force"]
    return min(live, key=REPLAY_WORST.index) if live else "not yet in force"


def replay_history(path=None):
    """replay-history.json on the data branch (or the file at path), as scripts/replay-history.py wrote it in
    recheck.yml, read, never run here: one cell per criterion and merge, its checks' worst state, mixed when
    they differ. No file is "absent", one this cannot read "invalid": neither a pass.

    A merge re-checked on two platforms (the Windows history and the Linux re-check job) has a row
    for each: a check one platform ran outranks the other's "not applicable on this platform", and a
    merge's run and copied counts are one platform's, Linux's where it has rows (CI's)."""
    if path is None:
        text = data_text("replay-history.json")
    elif os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            text = f.read()
    else:
        text = None
    if text is None:
        return dict(state="absent")
    try:
        data = json.loads(text)
        if data.get("schema") != 1:
            raise ValueError(f"schema {data.get('schema')!r}, this page reads 1")
        merges, cells = {}, {}
        for r in data["rows"]:
            r = dict(r, state=replay_row_state(r))
            if r["state"] not in REPLAY_STATES:
                raise ValueError(f"{r['criterion']} at {r['merge']}: state {r['state']!r}")
            m = merges.setdefault(r["n"], dict(n=r["n"], merge=r["merge"], pr=r.get("pr"), sample=r["sample"], by={}))
            if "key" in r:
                tally = m["by"].setdefault(r.get("platform"), dict(run=0, copied=0))
                tally["copied" if "reused_from" in r else "run"] += 1
            cells.setdefault((r["criterion"], r["n"]), dict(day=r["day"], checks=[]))["checks"].append(
                {k: r[k] for k in ("check", "state", "detail", "reused_from", "platform") if k in r})
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        return dict(state="invalid", why=str(e))
    for m in merges.values():
        by = m.pop("by")
        m.update(by.get("linux") or (by[min(by, key=str)] if by else dict(run=0, copied=0)))
    num = lambda cid: tuple(int(x) for x in re.findall(r"\d+", cid))  # noqa: E731
    out = []
    for (cid, n), c in sorted(cells.items(), key=lambda kv: (num(kv[0][0]), kv[0][1])):
        ran = {ch["check"] for ch in c["checks"] if ch["state"] != "not applicable on this platform"}
        c["checks"] = [ch for ch in c["checks"] if ch["state"] != "not applicable on this platform" or ch["check"] not in ran]
        states = {ch["state"] for ch in c["checks"]}
        out.append(dict(criterion=cid, day=c["day"], n=n, state=replay_state(states), mixed=len(states) > 1,
                        checks=c["checks"]))
    return dict(state="loaded", states=REPLAY_STATES, merges=[merges[n] for n in sorted(merges)], cells=out)


def refusals(name="refusals.json"):
    """The guards' refusals per date and guard, or with gates.json each gate's runs and tokens, as
    scripts/token-usage.py last counted them onto the data branch."""
    return page_json(name)


EVIDENCE_SCHEMA = 1  # scripts/evidence.py's SCHEMA
EVIDENCE_STATUSES = ("passed", "failed", "error", "not_applicable")
PROOF_RANK = ("test", "command", "break", "reader")  # strongest first


def proof_kinds(checks):
    """A day's criteria by what proved them, each once, under its strongest kind in PROOF_RANK:
    unproved for an unticked criterion or one nothing proved, not_recorded for a proof check from a
    report written before evidence.py recorded proved_by (not counted as either)."""
    out = dict.fromkeys((*PROOF_RANK, "unproved", "not_recorded"), 0)
    for c in checks:
        if c.get("kind") != "proof":
            continue
        if "proved_by" not in c:
            out["not_recorded"] += 1
            continue
        out[next((k for k in PROOF_RANK if k in (c["proved_by"] or ())), "unproved")] += 1
    return out


def blob_id(sha, path):
    """The blob a commit holds at path, or None where it has none."""
    r = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{sha}:{path}"], capture_output=True, text=True)
    return r.stdout.strip() or None


def input_drift(record, head, path):
    """Why an input the report read is not path as main has it now, or None if it is the same file.
    Compared by blob, not by the report's hash: that hashes the working tree's bytes, CRLF on Windows."""
    state, rev = record.get("state"), record.get("revision")
    if state == "missing":
        return None if blob_id(head, path) is None else f"{path} was missing when checked"
    if state != "clean" or not rev:
        return f"{path} was {state} when checked"
    return None if blob_id(rev, record.get("path") or path) == blob_id(head, path) else f"{path} changed since {rev[:7]}"


def evidence_checks(days, snaps):
    """The report of scripts/evidence.py --json (close-evidence.py --all, which the dashboard workflow
    runs before the build), read, never replayed here: each finished day's
    checks counted by kind and status, current if checked at main's close and on main's spec and
    breaks file, stale if not. No report is "absent", one this cannot read "invalid": neither a pass."""
    path = os.path.join(PAGE, "evidence-checks.json")
    if not os.path.exists(path):
        return dict(state="absent")
    head, merged = snaps[-1]["sha"], {s["pr"]: s["sha"] for s in snaps if s["pr"]}
    try:
        with open(path, encoding="utf-8") as f:
            report = json.load(f)
        if report.get("schema") != EVIDENCE_SCHEMA:
            raise ValueError(f"schema {report.get('schema')!r}, this page reads {EVIDENCE_SCHEMA}")
        by_day = {}
        for d in report["days"]:
            for c in d["checks"]:
                if c["status"] not in EVIDENCE_STATUSES:
                    raise ValueError(f"{c['id']}: status {c['status']!r}")
            by_day[day_of(d["spec"]["path"])] = d
        out = []
        for d in (d for d in days if d["status"] in FINISHED):
            r = by_day.get(d["day"])
            if r is None:
                out.append(dict(day=d["day"], state="not checked"))
                continue
            close = max((p["number"] for p in d["prs"] if p["kind"] == "close"), default=None)
            close = merged.get(close)
            why = [] if close and (r.get("close_sha") or "").startswith(close) else [
                f"checked at close {(r.get('close_sha') or 'none')[:7]}, main's is {close or 'none'}"]
            why += [w for w in (input_drift(r.get("spec") or {}, head, d["file"]),
                                input_drift(r.get("breaks") or {}, head, f"specs/breaks/day-{d['day']:02d}.json")) if w]
            counts = {}
            for c in r["checks"]:
                counts.setdefault(c["kind"], dict.fromkeys(EVIDENCE_STATUSES, 0))[c["status"]] += 1
            out.append(dict(day=d["day"], state="stale" if why else "current", why=why, counts=counts,
                            proof=proof_kinds(r["checks"]),
                            checks=[{k: c.get(k) for k in ("criterion", "kind", "status", "label", "diagnostic",
                                                           "proved_by")}
                                    for c in r["checks"]],
                            problems=[{k: c.get(k) for k in ("kind", "status", "label", "diagnostic")}
                                      for c in r["checks"] if c["status"] in ("failed", "error")]))
        return dict(state="loaded", generated=report["generated"], ref=report["ref"], ref_sha=report["ref_sha"],
                    runner=report["runner"], days=out)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        return dict(state="invalid", diagnostic=f"{type(e).__name__}: {e}")
