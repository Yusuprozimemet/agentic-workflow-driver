#!/usr/bin/env python3
"""Publishes this machine's count of the sessions without a pull request.

    python scripts/publish-counts.py            # count, push to the data branch, rebuild the page
    python scripts/publish-counts.py --detach   # the same in the background (the session hooks)
    python scripts/publish-counts.py --take     # the dashboard workflow: use the branch's count if newer

The sessions' times, tokens, gates and refusals are counted from transcripts only this machine
holds (scripts/token-usage.py), and `main` is protected, so between two closes the page's session
lanes stood still while GitHub's pull requests went on. The five count files go to a branch that
holds nothing else, as a commit built from git objects: no checkout, no index, and the working
tree and the current branch are left as they were. A push to that branch starts no workflow (the
branch has none), so the page's rebuild is asked for on `main`, where the workflow takes whichever
count is newer, the branch's or the one a close committed.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ("token-usage.json", "refusals.json", "gates.json", "sessions.json", "counted.json")
FOLDER = "docs/dashboard"
BRANCH = "dashboard-data"


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


def publish(repo, remote, branch, counter, dispatch):
    parent = fetched(repo, remote, branch)
    with tempfile.TemporaryDirectory() as tmp:
        # The counter never lowers a row it finds, so it starts from the last count published.
        for name in FILES:
            old = blob(repo, parent, name) if parent else None
            path = os.path.join(repo, FOLDER, name)
            if old is None and os.path.exists(path):
                with open(path, "rb") as f:
                    old = f.read()
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
        # counted.json is the moment of the count and differs every time: alone, it is no news.
        if parent and all(blob(repo, parent, n) == new[n] for n in FILES if n != "counted.json"):
            print("publish-counts: nothing new since the last count published")
            return 0
        blobs = [("100644", "blob", git(repo, "hash-object", "-w", "--no-filters", os.path.join(tmp, n)).stdout.decode().strip(), n)
                 for n in sorted(FILES)]
    root = tree(repo, blobs)
    for part in reversed(FOLDER.split("/")):
        root = tree(repo, [("040000", "tree", root, part)])
    at = json.loads(new["counted.json"])["at"]
    commit = git(repo, "commit-tree", root, *(["-p", parent] if parent else []),
                 "-m", f"Count the sessions up to {at}").stdout.decode().strip()
    git(repo, "push", "-q", remote, f"{commit}:refs/heads/{branch}")
    print(f"publish-counts: pushed the count up to {at} to {remote}/{branch}")
    if dispatch:
        p = subprocess.run(["gh", "workflow", "run", "dashboard.yml", "--ref", "main"], cwd=repo, capture_output=True)
        if p.returncode:
            print(f"publish-counts: the page's rebuild was not started: {p.stderr.decode('utf-8', 'replace').strip()}")
            return 1
        print("publish-counts: asked for the page's rebuild on main")
    return 0


def take(repo, remote, branch):
    """Writes the branch's five files over the working tree's when its count is the later one."""
    commit = fetched(repo, remote, branch)
    theirs = commit and blob(repo, commit, "counted.json")
    if not theirs:
        print(f"publish-counts: no count on {remote}/{branch}, keeping the committed one")
        return 0
    at = json.loads(theirs)["at"]
    mine = os.path.join(repo, FOLDER, "counted.json")
    if os.path.exists(mine):
        with open(mine, encoding="utf-8") as f:
            have = json.load(f)["at"]
        if datetime.datetime.fromisoformat(have) >= datetime.datetime.fromisoformat(at):
            print(f"publish-counts: the committed count ({have}) is not older than the branch's ({at}), keeping it")
            return 0
    for name in FILES:
        data = blob(repo, commit, name)
        if data is None:
            sys.exit(f"publish-counts: {remote}/{branch} has no {name}: the five are published together")
        with open(os.path.join(repo, FOLDER, name), "wb") as f:
            f.write(data)
    print(f"publish-counts: took the count up to {at} from {remote}/{branch}")
    return 0


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
    ap.add_argument("--take", action="store_true", help="write the branch's count into the working tree if it is newer")
    args = ap.parse_args(argv)
    if args.take:
        return take(args.repo, args.remote, args.branch)
    if args.detach:
        return detach(argv, args.repo)
    return publish(args.repo, args.remote, args.branch, args.counter, not args.no_dispatch)


if __name__ == "__main__":
    sys.exit(main())
