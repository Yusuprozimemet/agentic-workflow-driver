"""run-steps.py runs the kit's day loop on a project. --dry-run reads the project and its remote,
prints the one action the driver would take on the next step, and writes nothing in the project.
It exits 0 for start or wait, 1 for park, and 2 when the project lacks a piece of the kit (one
line on stderr for each piece missing). preflight [--project <path>] [--claude <program>] checks the
kit, then the Claude Code CLI, and prints "preflight: ok" and exits 0, or one line per missing
piece on stderr and exits 2. The project is --project; when it is not given, it is the project in
the config (--config, default driver.json beside this file), and a config with a problem exits 2
with one stderr line per problem. halt [--state <dir>] writes <dir>/halt and kills the driver's
process tree when its lock names a live process, then reports on the run's issue from
<dir>/run.json; clear [--state <dir>] removes the halt file and a stale lock, and refuses while a
driver lives. Neither needs a project or a config; --state defaults to the state folder beside this
file. live-check [--state] [--claude] [--python] runs the driver's own tests on the installed Claude
Code and, when they end "OK" with no skip, records its version in <state>/live-checked.txt; on
refuses to start on a version that file does not list. off [--config] [--project] [--gh] closes the project's open "Driver run" issues. status [--config] [--project] [--state] [--gh] prints where the driver is, one line per step, parks by reason and the cost per merged pull request; it takes no lock and writes nothing. --once
[--config] [--project] [--state] [--claude] [--gh] [--model] [--poll] [--session-minutes] does one step's checks in order:
halt, config, lock, the driver's own repository, preflight, the tree brought to main, decide, the
evidence run, then the run log;
for now it prints "would start: <sentence>" and starts nothing."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from driver import issues, livecheck, loop, once, status, switches
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
        choices=["preflight", "halt", "clear", "off", "status", "on", "live-check"],
        help="check the kit and the Claude Code CLI, halt, clear or turn off the driver, print its status, run on, or run the live check",
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
        "--python",
        default=sys.executable,
        help="the Python that runs live-check's tests",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=Path(__file__).resolve().parent / "state",
        help="the driver's state folder: halt, lock, settings",
    )
    parser.add_argument(
        "--once", action="store_true", help="do one step: check, then start its session"
    )
    parser.add_argument("--gh", default="gh", help="the GitHub CLI program, found on PATH")
    parser.add_argument("--model", default="opus", help="the session's model")
    parser.add_argument(
        "--poll",
        type=float,
        default=30,
        help="seconds between reads of the project's issues during a session or a wait",
    )
    parser.add_argument(
        "--wait-minutes",
        type=float,
        default=30,
        help="minutes on waits that have a bound: no checks, the evidence run",
    )
    parser.add_argument(
        "--session-minutes",
        type=float,
        default=120,
        help="minutes a session may run before its tree is killed and the step parks",
    )
    args = parser.parse_args(argv)
    if args.once:
        if args.dry_run or args.command:
            print("run-steps.py: --once goes alone", file=sys.stderr)
            return 2
        return once.run(args, Path(__file__).resolve().parent, read_facts)
    if args.command == "on":
        if args.dry_run:
            print("run-steps.py: on goes alone", file=sys.stderr)
            return 2
        return loop.run(args, Path(__file__).resolve().parent, read_facts)
    # halt and clear touch only the state folder, so they run with no project and no config.
    if args.command == "halt":
        return switches.halt(args.state)
    if args.command == "clear":
        return switches.clear(args.state)
    # live-check needs no project or config either: it runs the driver's own tests.
    if args.command == "live-check":
        return livecheck.run(args, Path(__file__).resolve().parent)
    # The config is opened only when --project is not given: a project named on the command line
    # must not depend on a file the person may not have.
    if args.project is None:
        config, lines = load_config(args.config)
        if lines:
            for line in lines:
                print(line, file=sys.stderr)
            return 2
        args.project = config["project"]
    if args.command == "off":
        return switches.off(args.project, args.gh)
    if args.command == "status":
        return status.run(args.project, args.gh, args.state)
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
        print("run-steps.py: give --dry-run, --once or a command", file=sys.stderr)
        return 2
    lines, drift = kit_lines(args.project)
    if lines:
        for line in lines:
            print(line, file=sys.stderr)
        return 2
    facts = read_facts(args.project)
    action = decide(drift, facts)
    # As --once: a closed parked issue of a phase's end's exact title answers it. Nothing else reads one.
    if action.kind == "park" and action.line.startswith("park: the end of Phase "):
        answered, reason = issues.closed_parks(args.project, args.gh)
        if reason:
            print(f"cannot read the project: {reason}", file=sys.stderr)
            return 2
        action = decide(drift, facts, answered)
    print(action.line)
    return 1 if action.kind == "park" else 0


if __name__ == "__main__":
    # A parent reading through a pipe reads UTF-8, whatever the locale and PYTHONIOENCODING say;
    # a console keeps its own encoding. Here, not in main(): tests call main() under StringIO.
    for stream in (sys.stdout, sys.stderr):
        if not stream.isatty():
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())
