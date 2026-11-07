"""--once does one step's checks in order, and the first that applies ends the run: the halt file,
the config, the lock, the driver's own repository, the kit and the CLI (preflight), the project's
issues (the STOP switch, the parks), the decision, the evidence run, then the run log and the
step's failures. Steps 10 and 11 write the settings and the run log's start line, then start one
`claude -p` session, its prompt on stdin. Step 12 reads the session's outcome from its stdout,
writes the run log's end line, and checks the driver's repository again: a change or a moved HEAD
sets the halt file, because the session ran with the driver's own files in reach. Every park it
prints is also an open issue (Day 5), so that the maintainer can close it to let the driver go on."""

import json
import os
import shutil
import subprocess
import sys
import uuid

from driver import github, issues, lock, runlog
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


def parsed(out):
    # The session's stdout is one JSON object under --output-format json; anything else is None.
    try:
        data = json.loads(out)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def outcome(out, returncode, session, project, gh, sentence):
    # Returns (line, code): the first rule that applies to the session's stdout, as the spec's table.
    data = parsed(out)
    if data is None:
        return (
            f"park: the session ended without a result (exit {returncode}; session `{session}`)",
            1,
        )
    if data.get("is_error") is True:
        subtype = data.get("subtype") or "unknown"
        return f"park: the session ended in an error: `{subtype}` (session `{session}`)", 1
    result = data.get("result")
    if isinstance(result, str):
        lines = [line.strip() for line in result.splitlines() if line.strip()]
        # A PARK line ends the session's reply; it wins over a pull request the session opened.
        if lines and lines[-1].startswith("PARK:"):
            rest = lines[-1][len("PARK:") :].strip()
            return f"park: the session parked: {rest} (session `{session}`)", 1
    prs, reason = github.step_prs(project, gh, sentence)
    if reason:
        return reason, 2
    if len(prs) == 1:
        return f"opened: #{prs[0]['number']} from `{prs[0]['headRefName']}`", 0
    if not prs:
        return (
            f"park: the session ended with no pull request and no PARK line (session `{session}`)",
            1,
        )
    numbers = ", ".join(f"#{pr['number']}" for pr in prs)
    return f"park: the step has more than one pull request: {numbers}", 1


def park_issue(project, gh, line, sentence, session, open_list):
    # Every park --once prints is an issue (Day 5): the maintainer closes it to let the driver go on.
    body = (
        f"{line}\n\nstep: {sentence}\nsession: {session or 'none'}\n"
        f"at: {lock.now().strftime(lock.STAMP)}\n\nClose this issue to let the driver go on.\n"
    )
    number, reason = issues.park(project, gh, line, body, open_list)
    if reason:
        print(f"cannot open the park's issue: {reason}", file=sys.stderr)
    return number


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
        # An earlier run's record goes, so that a halt before this run's session reads none.
        try:
            os.remove(os.path.join(args.state, "run.json"))
        except FileNotFoundError:
            pass
        return checked(args, home, project, read_facts, config)
    finally:
        lock.release(args.state)


def checked(args, home, project, read_facts, config):
    started, reason = driver_home.check(home)
    if reason:
        return refuse([f"cannot start: {reason}"])
    lines, drift = kit_lines(project)
    lines += cli_lines(args.claude)
    if lines:
        return refuse(lines)
    open_list, reason = issues.open_issues(project, args.gh)
    if reason:
        return refuse([f"cannot read the project: {reason}"])
    # The lowest-numbered STOP issue; only the maintainer's own, as open_issues reads them.
    stops = [issue for issue in open_list if issue["title"].startswith("STOP")]
    if stops:
        number = stops[0]["number"]
        # Written as bytes, as the halt file is at the end of this module.
        with open(os.path.join(args.state, "halt"), "wb") as halt:
            halt.write(
                f"halted at {lock.now().strftime(lock.STAMP)}: STOP issue #{number}".encode()
            )
        text = f"cannot start: halted: the STOP issue #{number} is open;"
        return refuse([f"{text} close it, then run-steps.py clear"])
    parked = [f"#{issue['number']}" for issue in open_list if "parked" in issue["labels"]]
    if parked:
        print(f"wait: parked {', '.join(parked)}")
        return 0
    facts = read_facts(project)
    # Read before decide, so that every park below can name the step it parked on.
    sentence = drift["now"]["next_step"]
    action = decide(drift, facts)
    # A phase's end is answered by a closed parked issue of its exact title (decide's `answered`).
    answered = None
    if action.kind == "park" and action.line.startswith("park: the end of Phase "):
        answered, reason = issues.closed_parks(project, args.gh)
        if reason:
            return refuse([f"cannot read the project: {reason}"])
        action = decide(drift, facts, answered)
    if action.kind != "start":
        print(action.line)
        if action.kind == "park":
            park_issue(project, args.gh, action.line, sentence, None, open_list)
            return 1
        return 0
    line = github.evidence_line(project, args.gh, facts.origin_main)
    if line:
        if line.startswith("park:"):
            print(line)
            park_issue(project, args.gh, line, sentence, None, open_list)
            return 1
        return refuse([line])
    session, reason = runlog.open_session(args.state, classify(sentence).prefix)
    if session:
        line = f"park: the run log names session `{session}` for this step, with no end"
        print(line)
        park_issue(project, args.gh, line, sentence, None, open_list)
        return 1
    if reason:
        line = f"park: {reason}"
        print(line)
        park_issue(project, args.gh, line, sentence, None, open_list)
        return 1
    failed, reason = runlog.failures(args.state, classify(sentence).prefix)
    if reason:
        line = f"park: {reason}"
        print(line)
        park_issue(project, args.gh, line, sentence, None, open_list)
        return 1
    if len(failed) >= 2:
        line = f"park: the step failed twice: sessions `{failed[-2]}` and `{failed[-1]}`"
        # A step that failed twice parks until the maintainer closes its park issue, as a phase does.
        if answered is None:
            answered, reason = issues.closed_parks(project, args.gh)
            if reason:
                return refuse([f"cannot read the project: {reason}"])
        if line not in answered:
            print(line)
            park_issue(project, args.gh, line, sentence, None, open_list)
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
    out = done.stdout.decode("utf-8", errors="replace")
    line, code = outcome(out, done.returncode, session, project, args.gh, sentence)
    if code == 2:
        print(line, file=sys.stderr)
    else:
        print(line)
    # The cost and the refusals are the session's own counts; a reply that is not JSON has neither.
    data = parsed(out) or {}
    denials = data.get("permission_denials")
    runlog.end(
        args.state,
        session,
        line,
        data.get("total_cost_usd"),
        len(denials) if isinstance(denials, list) else 0,
    )
    if code == 1:
        park_issue(project, args.gh, line, sentence, session, open_list)
    _, reason = driver_home.check(home, started)
    if reason:
        # Written as bytes, as the rest of the state is; the next --once refuses with this file.
        with open(os.path.join(args.state, "halt"), "wb") as halt:
            halt.write(f"halted at {lock.now().strftime(lock.STAMP)}: {reason}".encode())
        print(f"halt: set during the step; {reason}")
        return 1
    return code
