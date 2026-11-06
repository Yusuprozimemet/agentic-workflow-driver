"""run-steps.py runs the kit's day loop on a project. --dry-run reads the project and its remote,
prints the one action the driver would take on the next step, and writes nothing in the project.
It exits 0 for start or wait, 1 for park, and 2 when the project cannot be read (the reason goes
to stderr)."""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from driver.decide import Facts, decide

# How every command runs: its output read as UTF-8 text; each caller checks its exit code.
READ = {"capture_output": True, "text": True, "encoding": "utf-8"}


class Unreadable(Exception):
    """The project cannot be read, so the dry run has no action to print."""


def git(project, *args):
    # Only the reads the dry run needs; the tests fail on any other subcommand.
    return subprocess.run(["git", *args], check=False, cwd=project, **READ)


def run_drift(project):
    script = project / "scripts" / "spec-drift.py"
    if not script.exists():
        raise Unreadable(f"cannot read the project: {script} is missing")
    # The output and the cache go outside the project, so the dry run leaves nothing in it.
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "spec-drift.json"
        cache = Path(tmp) / "cache.json"
        cmd = [sys.executable, str(script), "--out", str(out), "--cache", str(cache)]
        done = subprocess.run(cmd, check=False, cwd=project, **READ)
        if done.returncode != 0:
            code = done.returncode
            raise Unreadable(f"cannot read the project: scripts/spec-drift.py exited {code}")
        try:
            drift = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            drift = None
    if not isinstance(drift, dict):
        raise Unreadable("cannot read the project: scripts/spec-drift.py wrote no JSON")
    return drift


def check_fields(drift):
    for path in ("now.next_step", "now.open_prs", "order", "days"):
        node = drift
        for key in path.split("."):
            if not isinstance(node, dict) or key not in node:
                raise Unreadable(f"cannot read the project: spec-drift.py's JSON has no {path}")
            node = node[key]


def check_github(project, drift):
    # Without a GitHub login spec-drift.py exits 0 with no pull requests, so a dry run would
    # start a step it should wait on. The kit's caveat says it found no GitHub remote.
    meta = drift.get("meta")
    caveats = meta.get("caveats", []) if isinstance(meta, dict) else []
    if not any(str(c).startswith("No GitHub remote") for c in caveats):
        return
    if "github.com" in git(project, "ls-remote", "--get-url", "origin").stdout:
        raise Unreadable(
            "cannot read the project: GitHub could not be read (spec-drift.py found no GitHub "
            "remote, but origin is on github.com)"
        )


def sha_of(done, ref):
    # The sha `git ls-remote` printed for the ref, or None when it printed no such line.
    for line in done.stdout.splitlines():
        if line.endswith("\t" + ref):
            return line.split("\t")[0]
    return None


def read_facts(project):
    # The remote is read live with ls-remote, not through the remote-tracking refs a fetch moves.
    status = git(project, "status", "--porcelain")
    branch = git(project, "symbolic-ref", "-q", "--short", "HEAD")
    main = git(project, "rev-parse", "--verify", "-q", "refs/heads/main")
    origin = git(project, "ls-remote", "origin", "refs/heads/main")
    heads = git(project, "ls-remote", "--heads", "origin")
    refs = git(project, "for-each-ref", "--format=%(refname:short)", "refs/heads")
    return Facts(
        dirty=tuple(line for line in status.stdout.splitlines() if line),
        branch=branch.stdout.strip() if branch.returncode == 0 else None,
        main=main.stdout.strip() if main.returncode == 0 else None,
        origin_main=sha_of(origin, "refs/heads/main"),
        branches=tuple(line for line in refs.stdout.splitlines() if line),
        remote_branches=tuple(
            line.partition("\t")[2].removeprefix("refs/heads/")
            for line in heads.stdout.splitlines()
            if "\t" in line
        ),
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the kit's day loop on a project.")
    parser.add_argument(
        "--dry-run", action="store_true", help="print the next action, change nothing"
    )
    parser.add_argument("--project", required=True, type=Path, help="the project's folder")
    args = parser.parse_args(argv)
    if not args.dry_run:
        print("run-steps.py: only --dry-run exists yet", file=sys.stderr)
        return 2
    try:
        drift = run_drift(args.project)
        check_fields(drift)
        check_github(args.project, drift)
        facts = read_facts(args.project)
    except Unreadable as error:
        print(error, file=sys.stderr)
        return 2
    action = decide(drift, facts)
    print(action.line)
    return 1 if action.kind == "park" else 0


if __name__ == "__main__":
    sys.exit(main())
