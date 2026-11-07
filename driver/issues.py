"""The driver reads and writes the project's issues through gh: the parks, the run's issue, the
phone's STOP (Day 5). Each call is one gh call, a failed one is a reason, never a guess."""

import os
import re
import shutil
import signal
import subprocess

from driver import lock
from driver.github import _gh


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


def open_run(project, gh, step, session, issues):
    # One run, one issue: the run's later steps comment on the issue the run opened, so that
    # `off` finds the run by its title.
    body = f"step: {step}\nsession: {session}\n\nClose this issue to turn the driver off after this step.\n"
    runs = [issue for issue in issues if issue["title"].startswith("Driver run")]
    if runs:
        number = min(issue["number"] for issue in runs)
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
