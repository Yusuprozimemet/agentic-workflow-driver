"""to_main brings a clean project to main before --once decides: when the project is on another
branch, or its main is not origin/main, it fetches, switches to main and fast-forwards main to
origin/main. It runs no other git command that changes the project. Standard library only."""

import os
import subprocess

from driver.decide import _is_branch_of


def to_main(project, facts, step, git=("git",)):
    # Returns (moved, line): moved is True when it ran git commands, so the caller reads the facts
    # again; line is a park line, or None. A dirty tree, a detached HEAD and a branch of the step
    # are left to decide(), which parks on them: a reset, stash or clean would lose work (rule 7
    # and "Recovery" in plan.md), and the step's own branch is the step's to take.
    if facts.dirty or facts.branch is None or facts.origin_main is None:
        return False, None
    names = (*facts.branches, *facts.remote_branches)
    if step.kind == "step" and any(_is_branch_of(step, name) for name in names):
        return False, None
    if facts.branch == "main" and facts.main == facts.origin_main:
        return False, None
    commands = [["fetch", "origin"]]
    if facts.branch != "main":
        commands.append(["switch", "main"])
    commands.append(["merge", "--ff-only", "origin/main"])
    for args in commands:
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        done = subprocess.run([*git, *args], cwd=project, check=False, capture_output=True, env=env)
        if done.returncode != 0:
            line = f"park: cannot bring the project to main: git {args[0]} exited {done.returncode}"
            return True, line
    return True, None
