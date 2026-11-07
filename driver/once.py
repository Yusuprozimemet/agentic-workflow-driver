"""--once does one step's checks in order, and the first that applies ends the run: the halt file,
the config, the lock, the driver's own repository, the kit and the CLI (preflight), the decision,
the evidence run, then the run log. Steps 10 and 11 write the settings and the run log's start
line, then start one `claude -p` session, its prompt on stdin. Until Track F it prints
"ended: session `<uuid>`" and no outcome."""

import os
import shutil
import subprocess
import sys
import uuid

from driver import github, lock, runlog
from driver import home as driver_home
from driver import settings as driver_settings
from driver.config import load as load_config
from driver.decide import decide
from driver.preflight import CLI, cli_lines, kit_lines
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
        return checked(args, home, project, read_facts, config)
    finally:
        lock.release(args.state)


def checked(args, home, project, read_facts, config):
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
    # The settings are written afresh, and the start line is in the log before the session runs.
    settings_path = driver_settings.write(args.state, home)
    session = str(uuid.uuid4())
    path = shutil.which(args.claude)
    probe = subprocess.run([path, "--version"], check=False, **CLI)
    lines = probe.stdout.splitlines()
    version = lines[0].strip() if lines else ""
    runlog.start(args.state, sentence, classify(sentence).prefix, session, version)
    command = [
        path,
        "-p",
        "--model",
        args.model,
        "--output-format",
        "json",
        "--max-budget-usd",
        str(config["budget_usd"]),
        "--permission-mode",
        "auto",
        "--strict-mcp-config",
        "--settings",
        settings_path,
        "--append-system-prompt-file",
        os.path.join(os.path.abspath(str(home)), "rules", "session.md"),
        "--session-id",
        session,
    ]
    # The prompt is on stdin, not in an argument: cmd.exe drops a newline and what follows it.
    prompt = (
        f"Next step: {sentence}\n"
        "Do this one step as CLAUDE.md says, open its one pull request, and stop.\n"
    )
    done = subprocess.run(
        command,
        input=prompt.encode("utf-8"),
        stdout=subprocess.PIPE,
        cwd=os.path.realpath(project),
        check=False,
    )
    _out = done.stdout.decode("utf-8", errors="replace")
    # Until Track F: the session's outcome is read from _out and no end line is written.
    print(f"ended: session `{session}`")
    return 0
