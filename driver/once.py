"""--once does one step's checks in order, and the first that applies ends the run: the halt file,
the config, the lock, the driver's own repository, the kit and the CLI (preflight), the decision,
the evidence run, then the run log. Until Track E a step that passes them prints
"would start: <sentence>" and starts nothing."""

import os
import sys

from driver import github, lock, runlog
from driver import home as driver_home
from driver.config import load as load_config
from driver.decide import decide
from driver.preflight import cli_lines, kit_lines
from driver.steps import classify


def refuse(lines):  # exit-2 lines go to stderr, as the preflight's do
    for line in lines:
        print(line, file=sys.stderr)
    return 2


def run(args, home, read_facts):
    # read_facts is passed in from run-steps.py, so the dry run's own function is used unchanged.
    if hasattr(os, "setpgid"):
        # So that halt kills the session with it (Day 3, "The tree"). This fails only when the
        # process already leads a session, and then the group is already its own.
        try:
            os.setpgid(0, 0)
        except OSError:
            pass
    halt = os.path.join(args.state, "halt")
    if os.path.exists(halt):
        return refuse([f"cannot start: halted: `{halt}` exists; run-steps.py clear removes it"])
    config, lines = load_config(args.config)
    if lines:
        return refuse(lines)
    # The config is read even when --project is given: later tracks need its budget_usd.
    project = args.project if args.project is not None else config["project"]
    refusal = lock.take(args.state)
    if refusal:
        return refuse([refusal])
    try:
        return checked(args, home, project, read_facts)
    finally:
        lock.release(args.state)


def checked(args, home, project, read_facts):
    _started, reason = driver_home.check(home)
    if reason:
        return refuse([f"cannot start: {reason}"])
    lines, drift = kit_lines(project)
    lines += cli_lines(args.claude)
    if lines:
        return refuse(lines)
    facts = read_facts(project)
    action = decide(drift, facts)
    if action.kind != "start":
        print(action.line)
        return 1 if action.kind == "park" else 0
    line = github.evidence_line(project, args.gh, facts.origin_main)
    if line:
        if line.startswith("park:"):
            print(line)
            return 1
        return refuse([line])
    sentence = drift["now"]["next_step"]
    session, reason = runlog.open_session(args.state, classify(sentence).prefix)
    if session:
        print(f"park: the run log names session `{session}` for this step, with no end")
        return 1
    if reason:
        print(f"park: {reason}")
        return 1
    # Until Track E: no settings are written and no run-log line is, so nothing is started.
    print(f"would start: {sentence}")
    return 0
