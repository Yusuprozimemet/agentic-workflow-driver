"""The reviewer: a session the driver starts once a pull request's checks are green, new and never the
step's, from the brief rules/reviewer.md. agents() writes <state>/agents.json, the file --agents reads,
afresh: one agent, reviewer, whose prompt is the brief. The file goes in <state>, not on the command
line: cmd.exe drops a newline and what follows it.

snapshot() reads HEAD, the refs, the stash's top and git status with read-only git commands;
changed() names the first that moved."""

import json
import os
import subprocess

DESCRIPTION = (
    "Reviews one pull request the driver's step opened, reads only, and ends with a REVIEW line."
)
TOOLS = ["Read", "Grep", "Glob", "Bash"]
NAMES = (
    ("head", "HEAD"),
    ("refs", "the refs"),
    ("stash_top", "the stash"),
    ("status", "`git status`"),
)


def agents(state, home, inside=False):
    state = os.path.abspath(state)
    os.makedirs(state, exist_ok=True)
    with open(os.path.join(home, "rules", "reviewer.md"), "rb") as f:
        prompt = f.read().decode("utf-8")
    body = {"reviewer": {"description": DESCRIPTION, "prompt": prompt, "tools": TOOLS}}
    path = os.path.join(state, "agents.json")
    with open(path, "wb") as f:
        f.write(json.dumps(body, indent=2).encode("utf-8"))
    return "/state/agents.json" if inside else path


def _read(project, git, *args):
    # cwd, not -C: the arguments start with the subcommand. A git that cannot run, or fails, is None.
    try:
        done = subprocess.run(
            [*git, *args],
            cwd=project,
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except OSError:
        return None
    if done.returncode != 0:
        return None
    return done.stdout.decode("utf-8", errors="replace")


def snapshot(project, git=("git",)):
    # Read-only git only. The refs and the stash's top come from one listing; the stash's line is
    # split off so that a new stash moves stash_top and not refs.
    parts = [
        _read(project, git, "rev-parse", "HEAD"),
        _read(project, git, "rev-parse", "--symbolic-full-name", "HEAD"),
    ]
    head = None if None in parts else "\n".join(part.strip() for part in parts)
    listed = _read(project, git, "for-each-ref", "--format=%(refname) %(objectname)")
    if listed is None:
        refs = stash_top = None
    else:
        lines = listed.splitlines()
        tops = [line for line in lines if line.startswith("refs/stash ")]
        stash_top = tops[0] if tops else ""
        refs = "\n".join(line for line in lines if not line.startswith("refs/stash "))
    status = _read(project, git, "status", "--porcelain=v1", "--untracked-files=all")
    return {"head": head, "refs": refs, "stash_top": stash_top, "status": status}


def changed(before, after):
    for key, name in NAMES:
        if before[key] != after[key]:
            return name
    return None
