"""run-steps.py runs the kit's day loop on a project. --dry-run reads the project and its remote,
prints the one action the driver would take on the next step, and writes nothing in the project.
It exits 0 for start or wait, 1 for park, and 2 when the project lacks a piece of the kit (one
line on stderr for each piece missing)."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from driver.decide import Facts, decide
from driver.preflight import git, kit_lines


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
    lines, drift = kit_lines(args.project)
    if lines:
        for line in lines:
            print(line, file=sys.stderr)
        return 2
    facts = read_facts(args.project)
    action = decide(drift, facts)
    print(action.line)
    return 1 if action.kind == "park" else 0


if __name__ == "__main__":
    sys.exit(main())
