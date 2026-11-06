"""Replay the day closed, or the short spec landed, by a push, or an explicitly requested day on main;
with --all, every closed day on main, into the report the dashboard reads; with --rehearse, a closing
branch before it merges.

    python scripts/close-evidence.py --rehearse day-NN/close-the-day [--base main] [--head <rev>]

A rehearsal replays the branch as its merge would: the merge of --head (the branch) into --base, made
as a commit on no branch whose subject is a closing merge's, checked out in a scratch worktree, and
evidence.py run there. It moves no ref and touches no file but its report, evidence-rehearsal.json.
A branch that closes no day and lands no short spec has nothing to rehearse, and passes. It reads
what is committed: commit the close first. It is not the replay after the merge: `main` can move in
between, and a squash merge is found by its title, which a rehearsal never sees.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from evidence import close_commit, closed_specs, closing_spec

EVIDENCE = str(Path(__file__).with_name("evidence.py"))
REHEARSAL = "evidence-rehearsal.json"
# The rehearsal commit's author: a CI runner has no identity, and commit-tree refuses without one.
IDENTITY = {f"GIT_{who}_{what}": value for who in ("AUTHOR", "COMMITTER")
            for what, value in (("NAME", "rehearsal"), ("EMAIL", "rehearsal@localhost"))}


def run(*args, **more):
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", **more)


def rehearse(branch, base, head):
    """Replay `branch` as merged into `base`; evidence.py's exit status, or 1 when there is no merge to replay."""
    sides = []
    for rev in (base, head):
        sha = run("rev-parse", "--verify", "-q", f"{rev}^{{commit}}").stdout.strip()
        if not sha:
            print(f"FAIL  {rev}: no such commit")
            return 1
        sides.append(sha)
    merged = run("merge-tree", "--write-tree", "--no-messages", *sides)
    if merged.returncode:
        print(f"FAIL  {head} does not merge into {base}: " +
              ("conflicts" if merged.returncode == 1 else merged.stderr.strip()))
        return 1
    commit = run("commit-tree", merged.stdout.split()[0], "-p", sides[0], "-p", sides[1], "-m",
                 f"Merge pull request #0 from rehearsal/{branch}", env=dict(os.environ, **IDENTITY)).stdout.strip()
    try:
        spec = closing_spec(commit)
    except ValueError as error:
        print(f"FAIL  {error}")
        return 1
    if spec is None:
        print("not a closing branch: nothing to rehearse")
        return 0
    report, worktree = os.path.abspath(REHEARSAL), tempfile.mkdtemp(prefix="rehearsal-")
    added = run("worktree", "add", "--detach", worktree, commit)
    if added.returncode:
        shutil.rmtree(worktree, ignore_errors=True)
        print(f"FAIL  no worktree at {commit[:7]}: {added.stderr.strip()}")
        return 1
    try:
        print(f"rehearsal: {branch} merged into {sides[0][:7]} as {commit[:7]}, a commit on no branch", flush=True)
        return subprocess.call([sys.executable, EVIDENCE, spec, "--ref", commit, "--json", report], cwd=worktree)
    finally:
        run("worktree", "remove", "--force", worktree)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--day", default="", help="optional day number to replay on main")
    parser.add_argument("--all", metavar="PATH", help="replay every closed day on main into this report")
    parser.add_argument("--cache", metavar="PATH", help="with --all: evidence.py's --cache, so a day replays "
                        "again only when something it reads has changed")
    parser.add_argument("--rehearse", metavar="BRANCH", help="replay this closing branch as its merge into "
                        f"--base would, before it merges, into {REHEARSAL}")
    parser.add_argument("--base", default="main", help="with --rehearse: what the branch merges into")
    parser.add_argument("--head", help="with --rehearse: the branch's commit, when it is not the branch by name")
    args = parser.parse_args()
    if args.rehearse:
        return rehearse(args.rehearse, args.base, args.head or args.rehearse)
    if args.all:
        specs = closed_specs("main")
        if not specs:
            print("no closed day on main")
            return 0
        cache = ["--cache", args.cache] if args.cache else []
        return subprocess.call([sys.executable, EVIDENCE, *specs, "--ref", "main", "--json", args.all, *cache])
    try:
        commit = args.commit
        if args.day:
            if not args.day.isascii() or not args.day.isdecimal() or not 0 <= int(args.day) <= 99:
                raise ValueError("day must be a number from 0 to 99")
            day = f"{int(args.day):02d}"
            commit = close_commit(day, "main")
            if not commit:
                raise ValueError(f"day-{day}: no closing commit on main")
        spec = closing_spec(commit)
    except ValueError as error:
        print(f"FAIL  {error}")
        return 1
    if spec is None:
        print("not a closing commit")
        return 0
    return subprocess.call([sys.executable, EVIDENCE, spec, "--ref", "main", "--json", "evidence.json"])


if __name__ == "__main__":
    sys.exit(main())
