"""The driver reads and writes the project's issues through gh: the parks, the run's issue, the
phone's STOP (Day 5). Each call is one gh call, a failed one is a reason, never a guess."""

import json
import os
import re
import shutil
import signal
import subprocess

from driver import home, lock, runlog
from driver.github import _gh

CLOSE_LINE = "Close this issue to turn the driver off after this step."


def open_issues(project, gh):
    # Only the maintainer's account counts: an issue anyone else opens is not a switch (plan.md,
    # "The switches").
    code, issues = _gh(
        project,
        gh,
        [
            "issue",
            "list",
            "--state",
            "open",
            "--author",
            "@me",
            "--limit",
            "100",
            "--json",
            "number,title,labels",
        ],
    )
    if code != 0 or issues is None:
        return [], f"gh issue list exited {code}"
    listed = [
        {
            "number": issue["number"],
            "title": issue["title"],
            "labels": [label["name"] for label in issue["labels"]],
        }
        for issue in issues
    ]
    return sorted(listed, key=lambda issue: issue["number"]), None


def closed_parks(project, gh):
    # A closed park is an answered one: the maintainer approved a phase's end, or a step failed
    # twice and was looked at. Only those count as answers, so an open park still parks the run.
    code, issues = _gh(
        project,
        gh,
        [
            "issue",
            "list",
            "--state",
            "closed",
            "--author",
            "@me",
            "--label",
            "parked",
            "--limit",
            "100",
            "--json",
            "number,title",
        ],
    )
    if code != 0 or issues is None:
        return set(), f"gh issue list exited {code}"
    return {issue["title"] for issue in issues}, None


def _write(project, gh, args, body=None, timeout=None):
    # Returns (exit code, stdout text), the code None when the call timed out. The body goes on stdin
    # as bytes: text mode would turn each "\n" into "\r\n" on Windows.
    program = shutil.which(gh) or gh
    try:
        proc = subprocess.Popen(
            [program, *args],
            cwd=project,
            env={**os.environ, "GH_PROMPT_DISABLED": "1"},
            stdin=subprocess.PIPE if body is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=os.name != "nt",
        )
    except OSError:
        return 127, ""
    try:
        stdout, _ = proc.communicate(
            None if body is None else body.encode("utf-8"), timeout=timeout
        )
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        return None, ""
    return proc.returncode, stdout.decode("utf-8", errors="replace")


def _kill_tree(proc):
    # The whole tree, not just the process: the tests' gh.cmd starts a python child that keeps the
    # pipes open, and communicate() would wait for it until the child exits.
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    proc.communicate()


def _comment(project, gh, number, body, timeout=None):
    code, _ = _write(
        project, gh, ["issue", "comment", str(number), "--body-file", "-"], body, timeout
    )
    return code


def _create(project, gh, args, body):
    # gh prints the new issue's URL as its last line; the number is the end of that URL.
    code, out = _write(project, gh, ["issue", "create", *args, "--body-file", "-"], body)
    if code != 0:
        return None, f"gh issue create exited {code}"
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    match = re.search(r"/issues/(\d+)$", lines[-1]) if lines else None
    if match is None:
        return None, "gh issue create printed no issue URL"
    return int(match.group(1)), None


def park(project, gh, line, body, issues):
    # One park per reason: a reason that is already parked and open gets a comment on its issue, not
    # a second issue (plan.md, "Recovery", rule 6).
    title = line[:200]
    again = [issue for issue in issues if "parked" in issue["labels"] and issue["title"] == title]
    if again:
        number = min(issue["number"] for issue in again)
        stamp = lock.now().strftime(lock.STAMP)
        code = _comment(project, gh, number, f"parked again at {stamp}")
        if code != 0:
            return None, f"gh issue comment exited {code}"
        return number, None
    code, _ = _write(
        project,
        gh,
        [
            "label",
            "create",
            "parked",
            "--color",
            "D93F0B",
            "--description",
            "The driver parked; close to let it go on",
            "--force",
        ],
    )
    if code != 0:
        return None, f"gh label create exited {code}"
    return _create(project, gh, ["--title", title, "--label", "parked"], body)


def open_run(project, gh, step, session, issues, state=None):
    # One run, one issue: the run's later steps comment on the issue the run opened, so that
    # `off` finds the run by its title.
    runs = [issue for issue in issues if issue["title"].startswith("Driver run")]
    number = min(issue["number"] for issue in runs) if runs else None
    body = f"step: {step}\nsession: {session}\n"
    # Given the state, the body shows what the run has cost so far, $0.00 on a new issue.
    if state is not None:
        body += f"cost so far: ${runlog.issue_cost(state, number):.2f}\n"
    body += f"\n{CLOSE_LINE}\n"
    if number is not None:
        code = _comment(project, gh, number, body)
        if code != 0:
            return None, f"gh issue comment exited {code}"
        return number, None
    stamp = lock.now().strftime(lock.STAMP)
    return _create(project, gh, ["--title", f"Driver run {stamp}"], body)


def close(project, gh, number, comment, timeout=None):
    # `gh issue close` on an issue already closed is taken to exit 0, so that a run's issue the
    # maintainer closed from the phone closes again without an error (unverified, see the spec's
    # Notes).
    code = _comment(project, gh, number, comment, timeout)
    if code is None:
        return "gh issue comment timed out"
    if code != 0:
        return f"gh issue comment exited {code}"
    code, _ = _write(project, gh, ["issue", "close", str(number)], None, timeout)
    if code is None:
        return "gh issue close timed out"
    if code != 0:
        return f"gh issue close exited {code}"
    return None


def heartbeat_body(step, session, lines):
    # The comment a live session's run edits in place: the step and session, the run's own
    # wording, then the progress lines the session shows at a poll.
    return f"step: {step}\nsession: {session}\n\n{CLOSE_LINE}\n" + "".join(
        line + "\n" for line in lines
    )


def heartbeat(project, gh, number, comment_id, body):
    # The first beat posts a comment and keeps its id; each later beat edits that comment, so the
    # issue holds one heartbeat, not one per poll. A failed call is skipped: the next poll tries
    # again, and a beat that has no id yet is posted again.
    if comment_id is None:
        code, out = _write(
            project, gh, ["issue", "comment", str(number), "--body-file", "-"], body, timeout=10
        )
        match = re.search(r"#issuecomment-(\d+)", out)
        if code != 0 or match is None:
            return None
        return int(match.group(1))
    _write(
        project,
        gh,
        [
            "api",
            "--method",
            "PATCH",
            f"repos/{{owner}}/{{repo}}/issues/comments/{comment_id}",
            "--input",
            "-",
        ],
        json.dumps({"body": body}),
        timeout=10,
    )
    return comment_id


def park_body(project, line, sentence, session):
    # What a park's issue holds (Day 7, H05.4): the session, the branch and last commit, and the
    # paths the tree holds uncommitted, so the maintainer sees what the park left. A git that fails
    # reads as none.
    branch = (home.git(project, "symbolic-ref", "-q", "--short", "HEAD") or "").strip()
    head = (home.git(project, "rev-parse", "--verify", "-q", "HEAD") or "").strip()
    status = home.git(project, "status", "--porcelain") or ""
    # Not stripped on the left: a porcelain line starts with the index column, a space when the
    # file is unstaged.
    paths = [path for path in status.splitlines() if path.strip()]
    lines = [
        line,
        "",
        f"step: {sentence}",
        f"session: {session or 'none'}",
        f"branch: {branch or 'detached HEAD'}",
        f"last commit: {head[:7] if head else 'none'}",
    ]
    if paths:
        lines.append("uncommitted paths:")
        lines.extend(paths[:50])
        if len(paths) > 50:
            lines.append(f"and {len(paths) - 50} more")
    else:
        lines.append("uncommitted paths: none")
    lines += [
        f"at: {lock.now().strftime(lock.STAMP)}",
        "",
        "Close this issue to let the driver go on.",
    ]
    return "\n".join(lines) + "\n"


def report(project, record):
    # What a halt writes, read from the run's issue: when, which step and session, and what the
    # project's repository held then (plan.md, "Recovery", rule 7). A git that fails reads as none.
    branch = (home.git(project, "symbolic-ref", "-q", "--short", "HEAD") or "").strip()
    head = (home.git(project, "rev-parse", "--verify", "-q", "HEAD") or "").strip()
    status = home.git(project, "status", "--porcelain") or ""
    changed = len([line for line in status.splitlines() if line.strip()])
    lines = [
        f"halted at {lock.now().strftime(lock.STAMP)}",
        f"step: {record['step']}",
        f"session: {record['session']}",
        f"branch: {branch or 'detached HEAD'}",
        f"last commit: {head[:7] if head else 'none'}",
        f"uncommitted changes: {changed} paths" if changed else "uncommitted changes: none",
    ]
    return "\n".join(lines) + "\n"
