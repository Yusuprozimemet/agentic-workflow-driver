"""The driver reads the project's GitHub state through the gh CLI: the evidence run on
`origin/main`'s head, the open pull requests of a step (H01.5; Phase 1 audit, finding 8), and the
checks and state of a pull request. Each read is one gh call, and a call that fails is a reason to
park, never a guess. Plain stdlib."""

import json
import os
import re
import shutil
import subprocess

from driver.decide import _is_branch_of
from driver.steps import classify

# A check's link to its GitHub Actions job, and how much of a failed job's log a prompt gets.
_ACTIONS_JOB = re.compile(r"/actions/runs/\d+/job/(\d+)")
_LOG_LINES = 40
_LOG_CHARS = 6000


def _gh(project, gh, args, want=list):
    # Returns (exit code, parsed output or None). A program that cannot be started exits 127, the
    # shell's code for a missing program, so the caller reports it the same way as a failed run.
    # want=str returns the output as it is: a job's log is text, not JSON.
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
    if want is str:
        return result.returncode, result.stdout
    try:
        parsed = json.loads(result.stdout)
    except ValueError:
        return result.returncode, None
    return result.returncode, parsed if isinstance(parsed, want) else None


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


def checks(project, gh, number):
    # gh exits 8 while checks are pending, so the state is read from the JSON, not treated as a
    # failed call.
    code, rows = _gh(
        project,
        gh,
        ["pr", "checks", str(number), "--required", "--json", "name,bucket,link"],
    )
    if code not in (0, 8) or rows is None:
        return None, [], f"gh pr checks exited {code}"
    # Each failed check keeps its link: failed_lines() needs it to find the job's log.
    failed = [
        {"name": row["name"], "link": row.get("link", "")}
        for row in rows
        if row.get("bucket") in ("fail", "cancel")
    ]
    # Red beats pending: a check that failed is final whatever the others are still doing.
    if failed:
        return "red", failed, None
    if any(row.get("bucket") == "pending" for row in rows):
        return "pending", [], None
    if not rows:
        return "none", [], None
    return "green", [], None


def failed_lines(project, gh, links):
    # The end of each failed job's log, so the session sees why a check went red. A link that is
    # not a job, or a log that cannot be read, is named by its link instead: that tells the session
    # less, and is never taken for a fact about the project.
    lines = []
    for entry in links:
        name, link = entry["name"], entry["link"]
        match = _ACTIONS_JOB.search(link)
        if match:
            code, log = _gh(
                project,
                gh,
                ["run", "view", "--job", match.group(1), "--log-failed"],
                want=str,
            )
            if code == 0 and log is not None:
                lines.extend(log.splitlines()[-_LOG_LINES:])
                continue
        lines.append(f"{name} {link}".strip())
    return "\n".join(lines)[-_LOG_CHARS:]


def pr_state(project, gh, number):
    # The body is read only for an `Oversized:` line and never goes into a prompt.
    code, view = _gh(
        project,
        gh,
        ["pr", "view", str(number), "--json", "state,mergeCommit,files,body"],
        want=dict,
    )
    if code != 0 or view is None:
        return None, None, [], "", f"gh pr view exited {code}"
    merge = view.get("mergeCommit") or {}
    return (
        view.get("state"),
        merge.get("oid"),
        [f["path"] for f in view.get("files") or []],
        view.get("body") or "",
        None,
    )
