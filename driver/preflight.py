"""The checks run before a dry run or a session: the project's kit (spec-drift.py, pr-names.py,
evidence.yml and the fields of spec-drift.py's JSON) and the remote origin. Each check returns the
lines of what is missing, none when nothing is."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# How every command runs: its output read as UTF-8 text; each caller checks its exit code.
READ = {"capture_output": True, "text": True, "encoding": "utf-8"}


def git(project, *args):
    # Only the reads the dry run needs; the tests fail on any other subcommand. A login prompt
    # would wait for a person, so git is told to fail instead.
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(["git", *args], check=False, cwd=project, env=env, **READ)


def run_drift(project):
    # Returns the drift dict, or None and the line saying why there is none.
    script = project / "scripts" / "spec-drift.py"
    # The output and the cache go outside the project, so the dry run leaves nothing in it.
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "spec-drift.json"
        cache = Path(tmp) / "cache.json"
        cmd = [sys.executable, str(script), "--out", str(out), "--cache", str(cache)]
        done = subprocess.run(cmd, check=False, cwd=project, **READ)
        if done.returncode != 0:
            code = done.returncode
            return None, f"cannot read the project: scripts/spec-drift.py exited {code}"
        try:
            drift = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            drift = None
    if not isinstance(drift, dict):
        return None, "cannot read the project: scripts/spec-drift.py wrote no JSON"
    return drift, None


def field_lines(drift):
    lines = []
    for path in ("now.next_step", "now.open_prs", "order", "days"):
        node = drift
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                lines.append(f"cannot read the project: spec-drift.py's JSON has no {path}")
                break
            node = node[part]
    # A key present with the value None is not missing: a day with no phase is a park, not a refusal.
    days = drift.get("days")
    if isinstance(days, list):
        for i, entry in enumerate(days):
            for key in ("day", "phase", "status"):
                if not isinstance(entry, dict) or key not in entry:
                    lines.append(
                        f"cannot read the project: spec-drift.py's JSON has no days[{i}].{key}"
                    )
    return lines


def github_line(project, drift):
    # Without a GitHub login spec-drift.py exits 0 with no pull requests, so a dry run would
    # start a step it should wait on. The kit's caveat says it found no GitHub remote.
    meta = drift.get("meta")
    caveats = meta.get("caveats", []) if isinstance(meta, dict) else []
    if not any(str(c).startswith("No GitHub remote") for c in caveats):
        return None
    if "github.com" in git(project, "ls-remote", "--get-url", "origin").stdout:
        return (
            "cannot read the project: GitHub could not be read (spec-drift.py found no GitHub "
            "remote, but origin is on github.com)"
        )
    return None


def remote_line(project):
    # With no remote named origin, `ls-remote --get-url` prints "origin" itself; the dry run
    # then parks on "no origin/main" rather than refusing here.
    url = git(project, "ls-remote", "--get-url", "origin").stdout.strip()
    if url == "origin":
        return None
    done = git(project, "ls-remote", "origin")
    if done.returncode != 0:
        return f"cannot read the project: origin could not be read (git ls-remote exited {done.returncode})"
    return None


def kit_lines(project):
    # One line for each piece missing, in the order of the spec's table. The drift is read only
    # when its script is there, and the checks on it only when it was read.
    lines = []
    script = project / "scripts" / "spec-drift.py"
    if not script.exists():
        lines.append(f"cannot read the project: {script} is missing")
    for piece in ("scripts/pr-names.py", ".github/workflows/evidence.yml"):
        if not (project / piece).exists():
            lines.append(f"cannot read the project: {piece} is missing")
    drift = None
    if script.exists():
        drift, line = run_drift(project)
        if line is not None:
            lines.append(line)
    if drift is not None:
        lines += field_lines(drift)
    github = github_line(project, drift) if drift is not None else None
    if github is not None:
        lines.append(github)
    else:
        remote = remote_line(project)
        if remote is not None:
            lines.append(remote)
    return lines, drift
