"""The driver reads the project's GitHub state through the gh CLI: the evidence run on
`origin/main`'s head, and the open pull requests of a step (H01.5; Phase 1 audit, finding 8). Each
read is one gh call, and a call that fails is a reason to park, never a guess. Plain stdlib."""

import json
import os
import shutil
import subprocess

from driver.decide import _is_branch_of
from driver.steps import classify


def _gh(project, gh, args):
    # Returns (exit code, parsed output or None). A program that cannot be started exits 127, the
    # shell's code for a missing program, so the caller reports it the same way as a failed run.
    program = shutil.which(gh) or gh
    try:
        result = subprocess.run(
            [program, *args],
            cwd=project,
            env={**os.environ, "GH_PROMPT_DISABLED": "1"},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return 127, None
    try:
        parsed = json.loads(result.stdout)
    except ValueError:
        return result.returncode, None
    return result.returncode, parsed if isinstance(parsed, list) else None


def evidence_line(project, gh, sha):
    # The newest evidence run for the commit: the kit's evidence.yml runs on every push to main.
    # gh matches no abbreviated sha, so the caller passes all 40 characters.
    code, runs = _gh(
        project,
        gh,
        [
            "run",
            "list",
            "--workflow",
            "evidence.yml",
            "--commit",
            sha,
            "--limit",
            "1",
            "--json",
            "status,conclusion",
        ],
    )
    if code != 0 or runs is None:
        return f"cannot read the project: gh run list exited {code}"
    if not runs:
        return f"park: no evidence run on `{sha[:7]}` yet"
    status = runs[0].get("status")
    if status != "completed":
        return f"park: the evidence run on `{sha[:7]}` has not finished (`{status}`)"
    conclusion = runs[0].get("conclusion")
    if conclusion != "success":
        return f"park: the evidence run on `{sha[:7]}` ended `{conclusion}`"
    return None


def step_prs(project, gh, step):
    # The open pull requests of the step's own branches, by the same rule the driver uses to find
    # them in decide(). Only the author's pull requests are read: another person's branch is not
    # the driver's to resume.
    code, prs = _gh(
        project,
        gh,
        [
            "pr",
            "list",
            "--state",
            "open",
            "--author",
            "@me",
            "--limit",
            "100",
            "--json",
            "number,headRefName,url",
        ],
    )
    if code != 0 or prs is None:
        return [], f"cannot read the project: gh pr list exited {code}"
    classified = classify(step)
    mine = [pr for pr in prs if _is_branch_of(classified, pr["headRefName"])]
    return sorted(mine, key=lambda pr: pr["number"]), None
