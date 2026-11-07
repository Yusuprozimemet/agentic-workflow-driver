"""run-steps.py runs the kit's day loop on a project. --dry-run reads the project and its remote,
prints the one action the driver would take on the next step, and writes nothing in the project.
It exits 0 for start or wait, 1 for park, and 2 when the project lacks a piece of the kit (one
line on stderr for each piece missing). preflight [--project <path>] [--claude <program>] checks the
kit, then the Claude Code CLI, and prints "preflight: ok" and exits 0, or one line per missing
piece on stderr and exits 2. The project is --project; when it is not given, it is the project in
the config (--config, default driver.json beside this file), and a config with a problem exits 2
with one stderr line per problem. halt [--state <dir>] writes <dir>/halt and kills the driver's
process tree when its lock names a live process; clear [--state <dir>] removes the halt file and a
stale lock, and refuses while a driver lives. Neither needs a project or a config; --state defaults
to the state folder beside this file."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from driver import switches
from driver.config import load as load_config
from driver.decide import Facts, decide
from driver.preflight import cli_lines, git, kit_lines


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
        "command",
        nargs="?",
        choices=["preflight", "halt", "clear"],
        help="check the kit and the Claude Code CLI, or halt or clear the driver",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the next action, change nothing"
    )
    parser.add_argument("--project", default=None, type=Path, help="the project's folder")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parent / "driver.json",
        help="the driver's config, read when --project is not given",
    )
    parser.add_argument(
        "--claude",
        default="claude",
        help="the Claude Code program the preflight checks, found on PATH",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=Path(__file__).resolve().parent / "state",
        help="the driver's state folder: halt, lock, settings",
    )
    args = parser.parse_args(argv)
    # halt and clear touch only the state folder, so they run with no project and no config.
    if args.command == "halt":
        return switches.halt(args.state)
    if args.command == "clear":
        return switches.clear(args.state)
    # The config is opened only when --project is not given: a project named on the command line
    # must not depend on a file the person may not have.
    if args.project is None:
        config, lines = load_config(args.config)
        if lines:
            for line in lines:
                print(line, file=sys.stderr)
            return 2
        args.project = config["project"]
    if args.command == "preflight":
        lines, _ = kit_lines(args.project)
        lines += cli_lines(args.claude)
        if lines:
            for line in lines:
                print(line, file=sys.stderr)
            return 2
        print("preflight: ok")
        return 0
    if not args.dry_run:
        print("run-steps.py: only --dry-run and preflight exist yet", file=sys.stderr)
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
    # A parent reading through a pipe reads UTF-8, whatever the locale and PYTHONIOENCODING say;
    # a console keeps its own encoding. Here, not in main(): tests call main() under StringIO.
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty():
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())
