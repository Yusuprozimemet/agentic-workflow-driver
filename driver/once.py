"""--once does one step's checks in order, and the first that applies ends the run: the halt file,
the config, the lock, the driver's own repository, the kit and the CLI (preflight), the project's
issues (the STOP switch, the parks), the decision, the evidence run, then the run log and the
step's failures. Steps 10 and 11 open the run's issue, write `run.json`, the settings and the run
log's start line, then start one `claude -p` session, its prompt on stdin. Step 12 reads the
session's outcome from its stdout, writes the run log's end line, and checks the driver's
repository again: a change or a moved HEAD sets the halt file, because the session ran with the
driver's own files in reach. Then the run's issue is closed with the outcome as its comment, and
`run.json` removed. Every park it prints is also an open issue (Day 5), so that the maintainer can
close it to let the driver go on. While the session runs, --once reads the project's issues every
--poll seconds: an open STOP issue halts the driver, reports on the run's issue and kills the session
(Day 5, "The phone's STOP during a session"). A session that runs past --session-minutes has its tree
killed, and the step parks with a park line."""

import json
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from collections import namedtuple

from driver import github, issues, livecheck, lock, runlog, tree
from driver import home as driver_home
from driver import settings as driver_settings
from driver.config import load as load_config
from driver.decide import decide
from driver.preflight import cli_lines, kit_lines
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


def write_halt(state, why):
    # Written as bytes, as the rest of the state is; the next --once refuses with this file.
    with open(os.path.join(state, "halt"), "wb") as halt:
        halt.write(f"halted at {lock.now().strftime(lock.STAMP)}: {why}".encode())


def stop_session(proc, args, project, number, record, stop_number):
    # The halt file is written first, so that every tool call the session makes is refused from here
    # on. The report is written before the kill and cannot keep it: a report that fails or hangs
    # still ends in the kill. On POSIX the kill is --once's own group, so this does not return.
    write_halt(args.state, f"STOP issue #{stop_number}")
    print(f"halt: the STOP issue #{stop_number} is open; the session is stopped", flush=True)
    try:
        reason = issues.close(project, args.gh, number, issues.report(project, record), timeout=10)
        if reason is None:
            print(f"halt: reported on #{number}", flush=True)
        else:
            print(f"halt: no report on #{number}: {reason}", flush=True)
    except Exception as exc:  # noqa: BLE001 - the kill comes next whatever the report raised
        print(f"halt: no report on #{number}: {type(exc).__name__}", flush=True)
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False
            )
            proc.wait()
            os.remove(os.path.join(args.state, "run.json"))
        else:
            os.killpg(os.getpgid(0), signal.SIGKILL)


def write_end(state, session, line, out):
    # The cost and the refusals are the session's own counts; a reply that is not JSON has neither.
    data = parsed(out) or {}
    denials = data.get("permission_denials")
    runlog.end(
        state,
        session,
        line,
        data.get("total_cost_usd"),
        len(denials) if isinstance(denials, list) else 0,
    )


# What run_session returns when the session ran past --session-minutes: its tree is killed, and the
# step parks on it (past_bound).
PAST = object()


def past_bound(args, session):
    # A session past its bound has no reply, so its end line carries no cost and no refusals.
    line = f"park: the session ran past {args.session_minutes:g} minutes (session `{session}`)"
    write_end(args.state, session, line, "")
    return line, 1


def descendants(pid):
    # The pids under pid, from one snapshot of the process table. The whole snapshot is read before
    # any kill, so a parent that dies first does not hide its children.
    table = subprocess.run(["ps", "-A", "-o", "pid=,ppid="], capture_output=True, check=False)
    children = {}
    for line in table.stdout.decode("utf-8", errors="replace").splitlines():
        fields = line.split()
        if len(fields) == 2:
            children.setdefault(int(fields[1]), []).append(int(fields[0]))
    found, todo = [], [pid]
    while todo:
        for child in children.get(todo.pop(), []):
            found.append(child)
            todo.append(child)
    return found


def kill_session(proc):
    # Kills the session's tree. Not killpg: the session stays in the driver's own process group so
    # that `halt` still kills it (Day 3, "The tree"), and killing that group here would kill the
    # driver before it can park.
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False
        )
    else:
        for pid in [proc.pid, *descendants(proc.pid)]:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    # A process that escaped the kill and still holds the output pipe must not hang the driver.
    try:
        proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def run_session(command, prompt, args, project, number, record):
    # Returns (stdout, return code), PAST when the session ran past --session-minutes, or None when a
    # STOP issue stopped the session. The prompt goes on stdin once; each --poll seconds the project's
    # issues are read while the session runs, and the bound is checked at each poll.
    proc = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=os.path.realpath(project)
    )
    deadline = time.monotonic() + args.session_minutes * 60
    data = prompt.encode("utf-8")
    while True:
        try:
            # The wait ends at the next poll or at the bound, whichever comes first.
            out, _ = proc.communicate(
                data, timeout=min(args.poll, max(0, deadline - time.monotonic()))
            )
            return out, proc.returncode
        except subprocess.TimeoutExpired:
            # Passing the input again raises ValueError, so later calls send none.
            data = None
            if time.monotonic() >= deadline:
                kill_session(proc)
                return PAST
        open_list, reason = issues.open_issues(project, args.gh)
        if reason:
            # A read that fails is skipped; the next poll reads again.
            continue
        stops = sorted(issue["number"] for issue in open_list if issue["title"].startswith("STOP"))
        if stops:
            stop_session(proc, args, project, number, record, stops[0])
            return None


# kind is "start" (a session may start), "wait", "park" or "end"; ready() says which, and why.
Ready = namedtuple("Ready", "kind line code sentence open_list")


def say(line, code):
    # Exit-2 lines go to stderr, as refuse() sends them; the rest go to stdout.
    print(line, file=sys.stderr if code == 2 else sys.stdout, flush=True)


def preflight(args, project):
    # The kit and the CLI are checked before the project's issues are read.
    lines, drift = kit_lines(project)
    lines += cli_lines(args.claude)
    if lines:
        return None, refuse(lines)
    return drift, None


def run(args, home, read_facts, body=None):
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
        # `on` passes its own body, which runs the same checks and then the steps (driver/loop.py).
        return (body or checked)(args, home, project, read_facts, config)
    finally:
        lock.release(args.state)


def checked(args, home, project, read_facts, config):
    started, reason = driver_home.check(home)
    if reason:
        return refuse([f"cannot start: {reason}"])
    drift, code = preflight(args, project)
    if drift is None:
        return code
    step = ready(args, project, read_facts, drift)
    if step.kind != "start":
        return stopped(args, project, step)
    record, command, prompt, reason = begin(args, home, project, config, step)
    if reason:
        return refuse([f"cannot read the project: {reason}"])
    done = one_session(command, prompt, args, project, record)
    if done is None:
        # The STOP issue stopped the session: no outcome, no park and no close; the halt file says why.
        return 1
    line, code = done
    return finish(args, home, project, started, record, line, code, step.open_list)


def ready(args, project, read_facts, drift):
    # The step --once would reach, as a Ready. Nothing is printed and no park issue is opened here:
    # stopped() and finish() do both, so that `on` ends its run through the same lines.
    open_list, reason = issues.open_issues(project, args.gh)
    if reason:
        return Ready("end", f"cannot read the project: {reason}", 2, None, [])
    # The lowest-numbered STOP issue; only the maintainer's own, as open_issues reads them.
    stops = [issue for issue in open_list if issue["title"].startswith("STOP")]
    if stops:
        number = stops[0]["number"]
        write_halt(args.state, f"STOP issue #{number}")
        text = f"cannot start: halted: the STOP issue #{number} is open;"
        return Ready("end", f"{text} close it, then run-steps.py clear", 2, None, open_list)
    parked = [f"#{issue['number']}" for issue in open_list if "parked" in issue["labels"]]
    if parked:
        return Ready("end", f"wait: parked {', '.join(parked)}", 0, None, open_list)
    facts = read_facts(project)
    # Read before decide, so that every park below can name the step it parked on.
    sentence = drift["now"]["next_step"]

    def parked_on(line):
        return Ready("park", line, 1, sentence, open_list)

    moved, line = tree.to_main(project, facts, classify(sentence))
    if line:
        return parked_on(line)
    if moved:
        facts = read_facts(project)
    action = decide(drift, facts)
    # A phase's end is answered by a closed parked issue of its exact title (decide's `answered`).
    answered = None
    if action.kind == "park" and action.line.startswith("park: the end of Phase "):
        answered, reason = issues.closed_parks(project, args.gh)
        if reason:
            return Ready("end", f"cannot read the project: {reason}", 2, sentence, open_list)
        action = decide(drift, facts, answered)
    if action.kind != "start":
        if action.kind == "park":
            return parked_on(action.line)
        return Ready("wait", action.line, 0, sentence, open_list)
    line = github.evidence_line(project, args.gh, facts.origin_main)
    if line:
        if line.startswith("park:"):
            return parked_on(line)
        return Ready("end", line, 2, sentence, open_list)
    session, reason = runlog.open_session(args.state, classify(sentence).prefix)
    if session:
        return parked_on(f"park: the run log names session `{session}` for this step, with no end")
    if reason:
        return parked_on(f"park: {reason}")
    failed, reason = runlog.failures(args.state, classify(sentence).prefix)
    if reason:
        return parked_on(f"park: {reason}")
    if len(failed) >= 2:
        line = f"park: the step failed twice: sessions `{failed[-2]}` and `{failed[-1]}`"
        # A step that failed twice parks until the maintainer closes its park issue, as a phase does.
        if answered is None:
            answered, reason = issues.closed_parks(project, args.gh)
            if reason:
                return Ready("end", f"cannot read the project: {reason}", 2, sentence, open_list)
        if line not in answered:
            return parked_on(line)
    return Ready("start", None, 0, sentence, open_list)


def stopped(args, project, step):
    # A step that starts no session ends here: its line, and a park's issue, as Day 5's.
    say(step.line, step.code)
    if step.kind == "park":
        park_issue(project, args.gh, step.line, step.sentence, None, step.open_list)
    return step.code


def open_record(args, project, sentence, session, open_list):
    # The run's issue, opened or reused, and run.json beside it: the record a halt's report reads.
    number, reason = issues.open_run(project, args.gh, sentence, session, open_list)
    if reason:
        return None, reason
    record = {
        "project": os.path.realpath(project),
        "gh": shutil.which(args.gh),
        "issue": number,
        "step": sentence,
        "session": session,
    }
    # Written as bytes, as the rest of the state is. The session may halt the driver, and the
    # halt's report reads the run's issue from here; the file goes once the step's outcome is out.
    run_path = os.path.join(args.state, "run.json")
    with open(run_path, "wb") as run_file:
        run_file.write(json.dumps(record).encode("utf-8"))
    return record, None


def begin(args, home, project, config, step):
    # Everything a session needs before it starts: its uuid, the run's issue, the settings, the run
    # log's start line, the command and the prompt. Returns (record, command, prompt, None), or
    # (None, None, None, reason) when the run's issue could not be opened.
    sentence = step.sentence
    session = str(uuid.uuid4())
    record, reason = open_record(args, project, sentence, session, step.open_list)
    if reason:
        return None, None, None, reason
    # The settings are written afresh, and the start line is in the log before the session runs.
    settings_path = driver_settings.write(args.state, home)
    path = shutil.which(args.claude)
    version = livecheck.version(path)
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
    return record, command, prompt, None


def one_session(command, prompt, args, project, record):
    # Runs the session and reads its outcome: (line, code), or None when a STOP issue stopped it.
    done = run_session(command, prompt, args, project, record["issue"], record)
    if done is None:
        return None
    if done is PAST:
        line, code = past_bound(args, record["session"])
        say(line, code)
        return line, code
    stdout, returncode = done
    out = stdout.decode("utf-8", errors="replace")
    line, code = outcome(out, returncode, record["session"], project, args.gh, record["step"])
    say(line, code)
    write_end(args.state, record["session"], line, out)
    return line, code


def finish(args, home, project, started, record, line, code, open_list):
    # The step's end, once its outcome is printed: the park's issue, a halt set during the step, and
    # the run's issue closed with the outcome as its comment. A gh that failed (exit 2) is what the
    # step cannot use, so no further gh call is made.
    number = record["issue"]
    parked = None
    if line.startswith("park:"):
        parked = park_issue(project, args.gh, line, record["step"], record["session"], open_list)
    _, reason = driver_home.check(home, started)
    if reason:
        # Written as bytes, as the rest of the state is; the next --once refuses with this file.
        with open(os.path.join(args.state, "halt"), "wb") as halt:
            halt.write(f"halted at {lock.now().strftime(lock.STAMP)}: {reason}".encode())
        print(f"halt: set during the step; {reason}")
    # off's line is printed after its issue was closed, so that issue is not closed again.
    if code != 2 and not line.startswith("off:"):
        # The run's issue is closed with the outcome as its comment, and a halt's report.
        comment = [line]
        if parked is not None:
            comment.append(f"parked: #{parked}")
        if reason:
            comment.append(f"halt: set during the step; {reason}")
            comment.append(issues.report(project, record))
        error = issues.close(project, args.gh, number, "\n".join(comment))
        if error:
            print(f"cannot close the run's issue #{number}: {error}", file=sys.stderr)
    # The step is over: a halt from the PC after it has no run to report on.
    try:
        os.remove(os.path.join(args.state, "run.json"))
    except FileNotFoundError:
        # stop_session removes it on Windows before the kill, so there is nothing left to remove.
        pass
    return 1 if reason else code
