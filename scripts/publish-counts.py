#!/usr/bin/env python3
"""Publishes this machine's count of the sessions without a pull request.

    python scripts/publish-counts.py            # count, push to the data branch, rebuild the page
    python scripts/publish-counts.py --detach   # the same in the background (the session hooks)
    python scripts/publish-counts.py --put <file> --message <subject>   # CI: one file to the branch

The sessions' times, tokens, gates and refusals are counted from transcripts only this machine
holds (scripts/token-usage.py), and `main` is protected: when a close committed them, the page's
session lanes stood still between closes while GitHub's pull requests went on. The five count files go to a branch that
holds nothing else, as a commit built from git objects: no checkout, no index, and the working
tree and the current branch are left as they were. A push to that branch starts no workflow (the
branch has none), so the page's rebuild is asked for on `main`; the build reads the files from the
branch (scripts/spec-drift.py, data_branch). Nothing commits them to `main`: the branch is their only
store, and a count starts from what it holds.

The driver's run log sits beside run-steps.py on this machine too, so the count also runs
scripts/driver-runs.py and pushes driver-runs.json as a sixth file (none while there is no log).
The re-check job in CI (recheck.yml) pushes replay-history.json to the same branch with --put. Each
push keeps the files it does not write, and a push rejected because another one landed first is
built again on the branch as it now stands.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ("token-usage.json", "refusals.json", "gates.json", "sessions.json", "counted.json")
DRIVER = "driver-runs.json"
REPLAY = "replay-history.json"
FOLDER = "docs/dashboard"
BRANCH = "dashboard-data"
# Two sessions that end together push together: 4 of the first 13 pushes were rejected that way.
TRIES = 4
REJECTED = ("non-fast-forward", "fetch first", "[rejected]", "failed to update ref", "cannot lock ref")


def git(repo, *args, data=None, check=True):
    p = subprocess.run(["git", "-C", repo, *args], input=data, capture_output=True,
                       env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))
    if check and p.returncode:
        sys.exit(f"publish-counts: git {' '.join(args)}: {p.stderr.decode('utf-8', 'replace').strip()}")
    return p


def fetched(repo, remote, branch):
    """The remote branch's commit after a fetch, or None when the remote has no such branch."""
    ref = f"refs/remotes/{remote}/{branch}"
    if git(repo, "fetch", "-q", remote, f"+refs/heads/{branch}:{ref}", check=False).returncode:
        return None
    return git(repo, "rev-parse", ref).stdout.decode().strip()


def blob(repo, commit, name):
    """One count file's bytes at a commit, or None."""
    p = git(repo, "show", f"{commit}:{FOLDER}/{name}", check=False)
    return None if p.returncode else p.stdout


def tree(repo, entries):
    lines = "".join(f"{mode} {kind} {sha}\t{name}\n" for mode, kind, sha, name in entries)
    return git(repo, "mktree", data=lines.encode()).stdout.decode().strip()


def push(repo, remote, branch, build):
    """Pushes the files build(parent) returns ({name: bytes} under FOLDER, or None for nothing new)
    as one commit on the branch, keeping the files it does not name. When the push is rejected
    because another publisher pushed first, the branch is fetched again and build runs on it again:
    a dropped count stayed off the page till the next session. Returns (pushed, message)."""
    for attempt in range(1, TRIES + 1):
        parent = fetched(repo, remote, branch)
        made = build(parent)
        if made is None:
            return False, None
        new, message = made
        kept = {}
        if parent:
            listing = git(repo, "ls-tree", f"{parent}:{FOLDER}", check=False).stdout.decode()
            for line in listing.splitlines():
                info, name = line.split("\t", 1)
                kept[name] = tuple(info.split())
        for name, data in new.items():
            kept[name] = ("100644", "blob", git(repo, "hash-object", "-w", "--stdin", "--no-filters", data=data).stdout.decode().strip())
        root = tree(repo, [(*kept[n], n) for n in sorted(kept)])
        for part in reversed(FOLDER.split("/")):
            root = tree(repo, [("040000", "tree", root, part)])
        commit = git(repo, "commit-tree", root, *(["-p", parent] if parent else []), "-m", message).stdout.decode().strip()
        p = git(repo, "push", "-q", remote, f"{commit}:refs/heads/{branch}", check=False)
        if not p.returncode:
            return True, message
        why = p.stderr.decode("utf-8", "replace").strip()
        if attempt == TRIES or not any(r in why for r in REJECTED):
            sys.exit(f"publish-counts: the push failed after {attempt} tries: {why}")
        print(f"publish-counts: the push was rejected (another publisher pushed first), try {attempt + 1} of {TRIES}", flush=True)


def ask_rebuild(repo):
    p = subprocess.run(["gh", "workflow", "run", "dashboard.yml", "--ref", "main"], cwd=repo, capture_output=True)
    if p.returncode:
        print(f"publish-counts: the page's rebuild was not started: {p.stderr.decode('utf-8', 'replace').strip()}")
        return 1
    print("publish-counts: asked for the page's rebuild on main")
    return 0


def steps_of(data):
    """A driver count without its moment, which differs every time."""
    try:
        return json.loads(data).get("steps")
    except (ValueError, AttributeError):
        return data


def count(repo, counter, driver_counter, parent):
    """The five count files, and driver-runs.json when the driver has a run log; None when nothing
    but the moments of the counts changed since the branch's last count."""
    with tempfile.TemporaryDirectory() as tmp:
        # The counter never lowers a row it finds, so it starts from the last count published.
        for name in FILES:
            old = blob(repo, parent, name) if parent else None
            if old is not None:
                with open(os.path.join(tmp, name), "wb") as f:
                    f.write(old)
        done = subprocess.run([sys.executable, counter, "--out", os.path.join(tmp, FILES[0])], capture_output=True)
        if done.returncode:
            sys.exit(f"publish-counts: the count failed: {done.stderr.decode('utf-8', 'replace').strip()[-500:]}")
        new = {}
        for name in FILES:
            with open(os.path.join(tmp, name), "rb") as f:
                new[name] = f.read()
        # The driver's log is read whole each time; a log it cannot read leaves the last count standing.
        driver = subprocess.run([sys.executable, driver_counter, "--out", os.path.join(tmp, DRIVER)], capture_output=True)
        if driver.returncode:
            print(f"publish-counts: the driver count failed: {driver.stderr.decode('utf-8', 'replace').strip()[-300:]}")
        elif os.path.exists(os.path.join(tmp, DRIVER)):
            with open(os.path.join(tmp, DRIVER), "rb") as f:
                new[DRIVER] = f.read()
    # counted.json and the driver's "counted" are the moment of the count and differ every time: alone, no news.
    if parent and all(blob(repo, parent, n) == new[n] for n in FILES if n != "counted.json") and (
            DRIVER not in new or steps_of(blob(repo, parent, DRIVER) or b"{}") == steps_of(new[DRIVER])):
        return None
    return new, f"Count the sessions up to {json.loads(new['counted.json'])['at']}"


def publish(repo, remote, branch, counter, driver_counter, dispatch):
    pushed, message = push(repo, remote, branch, lambda parent: count(repo, counter, driver_counter, parent))
    if not pushed:
        print("publish-counts: nothing new since the last count published")
        return 0
    print(f"publish-counts: pushed to {remote}/{branch}: {message}")
    return ask_rebuild(repo) if dispatch else 0


def put(repo, remote, branch, paths, message, dispatch):
    """Pushes files a job in CI wrote (the re-check's replay-history.json) as they are."""
    new = {}
    for path in paths:
        with open(path, "rb") as f:
            new[os.path.basename(path)] = f.read()

    def build(parent):
        if parent and all(blob(repo, parent, n) == data for n, data in new.items()):
            return None
        return new, message
    pushed, _ = push(repo, remote, branch, build)
    if not pushed:
        print(f"publish-counts: {', '.join(sorted(new))} unchanged on {remote}/{branch}, nothing pushed")
        return 0
    print(f"publish-counts: pushed to {remote}/{branch}: {message}")
    return ask_rebuild(repo) if dispatch else 0


def detach(argv, repo):
    """Starts the same command without --detach and returns at once: a session's end hook is given
    about a second, and the count and the push take longer. What it printed is in the log."""
    log = os.path.join(repo, ".claude", "state", "publish-counts.log")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    cmd = [sys.executable, os.path.abspath(__file__)] + [a for a in argv if a != "--detach"]
    with open(log, "ab") as out:
        io = dict(stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, cwd=repo)
        if os.name != "nt":
            subprocess.Popen(cmd, start_new_session=True, **io)
            return 0
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        try:  # outside the session's job, where the job allows it, so the session's end does not end it
            subprocess.Popen(cmd, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, **io)
        except OSError:
            subprocess.Popen(cmd, creationflags=flags, **io)
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=os.path.normpath(os.path.join(HERE, os.pardir)))
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--branch", default=BRANCH)
    ap.add_argument("--counter", default=os.path.join(HERE, "token-usage.py"), help="the script that writes the five files")
    ap.add_argument("--no-dispatch", action="store_true", help="push only; do not ask for the page's rebuild")
    ap.add_argument("--detach", action="store_true", help="run in the background and return at once")
    ap.add_argument("--driver-counter", default=os.path.join(HERE, "driver-runs.py"),
                    help="the script that writes driver-runs.json from the driver's run log")
    ap.add_argument("--put", nargs="+", metavar="FILE", help="push these files to the branch as they are, no count")
    ap.add_argument("--message", help="the commit subject for --put")
    args = ap.parse_args(argv)
    if args.detach:
        return detach(argv, args.repo)
    if args.put:
        if not args.message:
            ap.error("--put needs --message")
        return put(args.repo, args.remote, args.branch, args.put, args.message, not args.no_dispatch)
    return publish(args.repo, args.remote, args.branch, args.counter, args.driver_counter, not args.no_dispatch)


if __name__ == "__main__":
    sys.exit(main())
