"""--once does one step's checks in order, and the first that applies ends the run: the halt file,
the config, the lock, the driver's own repository, the kit and the CLI (preflight), the project's
issues (the STOP switch), the run log, the parks, the decision, the evidence run, then the
step's failures. Steps 10 and 11 open the run's issue, write `run.json`, the settings and the run
log's start line, then start one `claude -p` session, its prompt on stdin. Step 12 reads the
session's outcome from its stdout, writes the run log's end line, and checks the driver's
repository again: a change or a moved HEAD sets the halt file, because the session ran with the
driver's own files in reach. Then the run's issue is closed with the outcome as its comment, and
`run.json` removed. Every park it prints is also an open issue (Day 5), so that the maintainer can
close it to let the driver go on. While the session runs, --once reads the project's issues every
--poll seconds: an open STOP issue halts the driver, reports on the run's issue and kills the session
(Day 5, "The phone's STOP during a session"). A session that runs past --session-minutes has its tree
killed, and the step parks with a park line. A session whose transcript's last assistant record is
the usage limit waits for the reset and is resumed once, or parks when the reset is more than
--limit-hours away (Day 9). A halt file found when a session returns, its own or a resumed one,
ends the step with a halt line before its outcome is read, and with no end line. The session's
stdout is read line by line on a reader thread, and each line's time and kind are appended to
`<state>/sessions/<session>.events.jsonl`."""

import glob
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections import namedtuple

from driver import box, github, issues, livecheck, lock, runlog, status, stream, tree
from driver import home as driver_home
from driver import settings as driver_settings
from driver.config import load as load_config
from driver.decide import decide
from driver.preflight import box_line, cli_lines, image_claude, kit_lines
from driver.steps import classify


def refuse(lines):  # exit-2 lines go to stderr, as the preflight's do
    for line in lines:
        print(line, file=sys.stderr)
    return 2


def outcome(out, returncode, session, project, gh, sentence):
    # Returns (line, code): the first rule that applies to the session's stdout, as the spec's table.
    data = stream.result(out)
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


def park_issue(project, gh, state, line, sentence, session, open_list, pr=None, head=None):
    # Every park --once prints is an issue (Day 5): the maintainer closes it to let the driver go on.
    # A park before a session names none, and loop.py's between-steps record the string "none":
    # both fall back to the newest session the log has for the step.
    runlog.park(state, sentence, line, pr, head)
    if session in (None, "none"):
        prefix = classify(sentence).prefix
        session = runlog.last_session(state, prefix) if prefix else None
    body = issues.park_body(project, line, sentence, session)
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
        if record.get("container"):
            end_container(proc, args.docker, record["container"])
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, check=False
            )
            proc.wait()
            os.remove(os.path.join(args.state, "run.json"))
        else:
            os.killpg(os.getpgid(0), signal.SIGKILL)


def refusal(entry):
    # The input is cut to 200 characters, so a long Write does not put a file into the log.
    if not isinstance(entry, dict):
        return {"tool": "unknown", "input": "{}"}
    tool = entry.get("tool_name")
    return {
        "tool": tool if isinstance(tool, str) else "unknown",
        "input": json.dumps(entry.get("tool_input", {}))[:200],
    }


def write_end(state, session, line, out):
    # The cost and the refusals are the session's own counts; a reply that is not JSON has neither.
    data = stream.result(out) or {}
    denials = data.get("permission_denials")
    refused = None
    if isinstance(denials, list) and denials:
        refused = [refusal(entry) for entry in denials]
    runlog.end(
        state,
        session,
        line,
        data.get("total_cost_usd"),
        len(denials) if isinstance(denials, list) else 0,
        refused=refused,
    )


# What run_session returns when the session ran past --session-minutes: its tree is killed, and the
# step parks on it (past_bound).
PAST = object()

# The prompt of the session that is resumed once the usage limit has reset: the step's own prompt
# is not sent again, the resumed session has it already.
LIMIT_PROMPT = (
    "The usage limit has reset. Carry on with this step as before, open its one pull request, "
    "and stop.\n"
)


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


def kill_container(docker, name):
    # The container is killed by its name; the result says whether docker did it.
    return subprocess.run([docker, "kill", name], capture_output=True, text=True, check=False)


def end_container(proc, docker, name):
    # Killing the docker client leaves the container running, so the container is killed first: the
    # client then ends by itself. A docker that cannot run is left to the tree kill that follows.
    try:
        kill_container(docker, name)
        proc.wait(timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        pass


def kill_session(proc, docker=None, name=None, reader=None):
    # Kills the session's tree. Not killpg: the session stays in the driver's own process group so
    # that `halt` still kills it (Day 3, "The tree"), and killing that group here would kill the
    # driver before it can park.
    if name is not None:
        end_container(proc, docker, name)
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
    if reader is not None:
        reader.join(10)
    else:
        try:
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            pass


def read_stdout(proc, lines, state, session):
    # The only reader of the session's stdout, on its own thread: each line is kept for the outcome and
    # named in the events file. A line the events file cannot take is read on all the same, so that
    # the pipe is always drained.
    for line in iter(proc.stdout.readline, b""):
        lines.append(line)
        try:
            stream.append(state, session, line)
        except OSError:
            pass


def quiet_for(state, session, begun):
    # The seconds from the session's newest event, or from its start when it has none, to now. When neither
    # time reads, the session is not quiet: 0 seconds, so no stale comment.
    now = lock.now()
    for stamp in (stream.last_event(state, session), begun):
        try:
            return (now - lock.stamp_time(stamp)).total_seconds()
        except (TypeError, ValueError):
            pass
    return 0


def run_session(command, prompt, args, project, number, record):
    # Returns (stdout, return code), PAST when the session ran past --session-minutes, or None when a
    # STOP issue stopped the session. The reader thread takes the session's stdout line by line, and
    # the prompt goes on stdin once, after the reader has started. Each --poll seconds the project's
    # issues are read while the session runs, and the bound is checked at each poll.
    proc = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, cwd=os.path.realpath(project)
    )
    runlog.pid(
        args.state,
        record["session"],
        proc.pid,
        lock.now().strftime(lock.STAMP),
        container=record.get("container"),
    )
    lines = []
    reader = threading.Thread(
        target=read_stdout, args=(proc, lines, args.state, record["session"]), daemon=True
    )
    reader.start()
    begun = stream.started(args.state, record["session"])
    stream.beat(args.state, record["session"], record.get("step"), begun)
    deadline = time.monotonic() + args.session_minutes * 60
    try:
        proc.stdin.write(prompt.encode("utf-8"))
        proc.stdin.close()
    except OSError:
        # A session that has already exited has closed its input: there is no prompt to send it.
        pass
    while True:
        # The wait ends at the next poll or at the bound, whichever comes first.
        timeout = min(args.poll, max(0, deadline - time.monotonic()))
        reader.join(timeout)
        if not reader.is_alive():
            # The reader ends with the session's stdout, so what is awaited next is the session's exit.
            try:
                proc.wait(timeout=timeout)
                return b"".join(lines), proc.returncode
            except subprocess.TimeoutExpired:
                pass
        if time.monotonic() >= deadline:
            kill_session(proc, args.docker, record.get("container"), reader)
            return PAST
        stream.beat(args.state, record["session"], record.get("step"), begun)
        open_list, reason = issues.open_issues(project, args.gh)
        if reason:
            # A read that fails is skipped; the next poll reads again.
            continue
        stops = sorted(issue["number"] for issue in open_list if issue["title"].startswith("STOP"))
        if stops:
            stop_session(proc, args, project, number, record, stops[0])
            return None
        # The heartbeat and the stale check are made at a poll that read the issues, so a session that ends
        # before its first poll leaves no comment on the run's issue. The comment's id and stale flag are read
        # from the session's file at each poll, and kept there only when one of them changed.
        body = issues.heartbeat_body(
            record.get("step"), record["session"], status.live_lines(args.state, record["session"])
        )
        comment_id, stale = stream.comment_state(args.state, record["session"])
        new_id = issues.heartbeat(project, args.gh, number, comment_id, body)
        minutes = getattr(args, "stale_minutes", 10)
        now_stale = stale or (
            quiet_for(args.state, record["session"], begun) >= minutes * 60
            and issues.stale_comment(project, args.gh, number, record["session"], minutes)
        )
        if (new_id, now_stale) != (comment_id, stale):
            stream.keep_comment(args.state, record["session"], new_id, now_stale)


# kind is "start", "running" (a live session), "wait", "park" or "end"; ready() says which, and why.
Ready = namedtuple("Ready", "kind line code sentence open_list")


def say(line, code):
    # Exit-2 lines go to stderr, as refuse() sends them; the rest go to stdout.
    print(line, file=sys.stderr if code == 2 else sys.stdout, flush=True)


def preflight(args, project, config):
    # The kit and the CLI are checked before the project's issues are read.
    lines, drift = kit_lines(project)
    if "container_image" in config:
        # The keys come as a pair (driver.config.load), and only the first of Docker, the image and
        # the secrets file that fails is printed; the image's Claude Code is checked in place of
        # the PC's.
        image = config["container_image"]
        line = box_line(args.docker, image, config["container_secrets"])
        lines += (
            [line] if line else cli_lines("the image's claude", image_claude(args.docker, image))
        )
    else:
        lines += cli_lines(args.claude)
    if lines:
        return None, refuse(lines)
    return drift, None


def halted_line(halt):
    return f"cannot start: halted: `{halt}` exists; run-steps.py clear removes it"


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
        return refuse([halted_line(halt)])
    config, lines = load_config(args.config)
    if lines:
        return refuse(lines)
    args.stale_minutes = config.get("stale_minutes", 10)
    # The config is read even when --project is given: later tracks need its budget_usd.
    project = args.project if args.project is not None else config["project"]
    refusal = lock.take(args.state)
    if refusal:
        return refuse([refusal])
    try:
        old = lock.took_over(args.state)
        if old is not None:
            print(f"lock: taken over from pid {old}, which is gone", flush=True)
        # An earlier run's record goes, so that a halt before this run's session reads none.
        try:
            os.remove(os.path.join(args.state, "run.json"))
        except FileNotFoundError:
            pass
        # `on` passes its own body, which runs the same checks and then the steps (driver/loop.py).
        return (body or checked)(args, home, project, read_facts, config)
    finally:
        lock.release(args.state)


def settle(args, project):
    # Each pull request the log names and has not settled is asked once, so that its merged or
    # closed line is written at this start, before the run's own steps. A reason means GitHub
    # could not say, and nothing is written for it.
    for number, parked in runlog.unsettled(args.state):
        state, _, _, _, reason, head = github.pr_state(project, args.gh, number)
        if reason:
            return reason
        if state == "MERGED":
            changed = None if head is None or parked is None else head != parked
            runlog.merged(args.state, number, head, changed)
        elif state == "CLOSED":
            runlog.closed(args.state, number)
    return None


def checked(args, home, project, read_facts, config):
    started, reason = driver_home.check(home)
    if reason:
        return refuse([f"cannot start: {reason}"])
    drift, code = preflight(args, project, config)
    if drift is None:
        return code
    reason = settle(args, project)
    if reason:
        return refuse([f"cannot read the project: {reason}"])
    step = ready(args, project, read_facts, drift, "container_image" in config)
    if step.kind != "start":
        return stopped(args, project, step)
    session, line = reached(args, home, project, config)
    if line:
        return refuse([line])
    record, command, prompt, reason = begin(args, home, project, config, step, session)
    if reason:
        return refuse([f"cannot read the project: {reason}"])
    done = one_session(command, prompt, args, project, record)
    if done is None:
        # The STOP issue stopped the session: no outcome, no park and no close; the halt file says why.
        return 1
    line, code = done
    return finish(args, home, project, started, record, line, code, step.open_list)


def container_running(docker, name):
    # True when docker says the container runs. A docker that cannot run says it does not, so the
    # rows below decide as they do without a container.
    try:
        done = subprocess.run(
            [docker, "inspect", "--format", "{{.State.Running}}", name],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return done.stdout.strip() == "true"


def ready(args, project, read_facts, drift, boxed=False):
    # The step --once would reach, as a Ready. Nothing is printed and no park issue is opened here:
    # stopped() and finish() do both, so that `on` ends its run through the same lines.
    halt = os.path.join(args.state, "halt")
    if os.path.exists(halt):
        return Ready("end", halted_line(halt), 2, None, [])
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
    # A live session is waited on, and the rows below are not read until it ends.
    live, pid, reason = runlog.live_session(args.state)
    if live:
        line = f"wait: session `{live}` is still running (pid {pid})"
        return Ready("running", line, 0, None, open_list)
    # A session in a container may outlive its docker client, so a gone pid does not end the wait
    # while docker says the container runs.
    if boxed:
        session, name = runlog.live_container(args.state)
        if name and container_running(args.docker, name):
            line = f"wait: session `{session}` is still running (container `{name}`)"
            return Ready("running", line, 0, None, open_list)
    # A start that took over a lock with no log has nothing to say what the last driver left.
    old = lock.took_over(args.state)
    if old is not None and not os.path.exists(runlog.path(args.state)):
        line = f"park: the run log is missing, and a lock shows a driver ran (pid {old})"
        return Ready("park", line, 1, drift["now"]["next_step"], open_list)
    # A torn log parks here, unless its own park is open: that one waits at row 3, with no comment.
    parks = [issue for issue in open_list if "parked" in issue["labels"]]
    if reason and f"park: {reason}" not in [issue["title"] for issue in parks]:
        return Ready("park", f"park: {reason}", 1, drift["now"]["next_step"], open_list)
    parked = [f"#{issue['number']}" for issue in parks]
    if parked:
        return Ready("end", f"wait: parked {', '.join(parked)}", 0, None, open_list)
    facts = read_facts(project)
    # Read before decide, so that every park below can name the step it parked on.
    sentence = drift["now"]["next_step"]

    def parked_on(line):
        return Ready("park", line, 1, sentence, open_list)

    # Row 4: only the maintainer's own pull requests hold the step, and while one is open the
    # tree is not touched. No open pull request, no read.
    if drift["now"]["open_prs"]:
        numbers, line = github.mine(project, args.gh)
        if line:
            return Ready("end", line, 2, sentence, open_list)
        kept = [pr for pr in drift["now"]["open_prs"] if pr["number"] in numbers]
        drift = {**drift, "now": {**drift["now"], "open_prs": kept}}
    if not drift["now"]["open_prs"]:
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
    prefix = classify(sentence).prefix
    session, reason = runlog.open_session(args.state, prefix)
    if reason:
        return parked_on(f"park: {reason}")
    failed, reason = runlog.failures(args.state, prefix)
    if reason:
        return parked_on(f"park: {reason}")
    # A crash's session and a step that failed twice park until a closed park of the same title.
    lines = []
    if session:
        lines.append(f"park: the run log names session `{session}` for this step, with no end")
    if len(failed) >= 2:
        lines.append(f"park: the step failed twice: sessions `{failed[-2]}` and `{failed[-1]}`")
    if lines and answered is None:
        answered, reason = issues.closed_parks(project, args.gh)
        if reason:
            return Ready("end", f"cannot read the project: {reason}", 2, sentence, open_list)
    for line in lines:
        if line not in answered:
            return parked_on(line)
    return Ready("start", None, 0, sentence, open_list)


def stopped(args, project, step):
    # A step that starts no session ends here: its line, and a park's issue, as Day 5's.
    say(step.line, step.code)
    if step.kind == "park":
        park_issue(project, args.gh, args.state, step.line, step.sentence, None, step.open_list)
    return step.code


def open_record(args, project, sentence, session, open_list):
    # The run's issue, opened or reused, and run.json beside it: the record a halt's report reads.
    number, reason = issues.open_run(
        project, args.gh, sentence, session, open_list, state=args.state
    )
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


def reached(args, home, project, config):
    # The session's uuid, and with the container keys the probe that checks the session's folders
    # first: a line from it refuses the start, before any issue is opened or any run log line made.
    session = str(uuid.uuid4())
    if "container_image" not in config:
        return session, None
    for folder in ("refusals", "claude"):
        os.makedirs(os.path.join(args.state, folder), exist_ok=True)
    image, secrets = config["container_image"], config["container_secrets"]
    return session, box.reach(args.docker, image, secrets, home, args.state, project, session)


def begin(args, home, project, config, step, session):
    # Everything a session needs before it starts: its uuid, the run's issue, the settings, the run
    # log's start line, the command and the prompt. Returns (record, command, prompt, None), or
    # (None, None, None, reason) when the run's issue could not be opened.
    sentence = step.sentence
    record, reason = open_record(args, project, sentence, session, step.open_list)
    if reason:
        return None, None, None, reason
    # The settings are written afresh, and the start line is in the log before the session runs.
    settings_path = driver_settings.write(args.state, home)
    path = shutil.which(args.claude)
    boxed = "container_image" in config
    if boxed:
        # The session runs in a container named for it: its Claude Code is the image's, and its
        # settings and rules are the copies the container mounts.
        image = config["container_image"]
        record["container"] = f"driver-{session}"
        driver_settings.write(args.state, home, inside=True)
        version = livecheck.version(*image_claude(args.docker, image))
    else:
        version = livecheck.version(path)
    runlog.start(
        args.state,
        sentence,
        classify(sentence).prefix,
        session,
        version,
        issue=record["issue"],
        container=record.get("container"),
    )
    command = [
        "claude" if boxed else path,
        "-p",
        "--model",
        args.model,
        "--output-format",
        "stream-json",
        "--verbose",
        "--max-budget-usd",
        str(config["budget_usd"]),
        "--permission-mode",
        "auto",
        "--strict-mcp-config",
        "--settings",
        "/state/container-settings.json" if boxed else settings_path,
        "--append-system-prompt-file",
        "/driver/rules/session.md"
        if boxed
        else os.path.join(os.path.abspath(str(home)), "rules", "session.md"),
        "--session-id",
        session,
    ]
    if boxed:
        command = box.command(
            args.docker,
            image,
            config["container_secrets"],
            home,
            args.state,
            project,
            record["container"],
            command,
        )
    # The prompt is on stdin, not in an argument: cmd.exe drops a newline and what follows it.
    prompt = (
        f"Next step: {sentence}\n"
        "Do this one step as CLAUDE.md says, open its one pull request, and stop.\n"
    )
    return record, command, prompt, None


def transcripts(args, record):
    # The folder the session's CLI keeps its transcript in, when the session runs in a container:
    # the container's config folder is <state>/claude. None reads the PC's own folder.
    if record.get("container"):
        return os.path.join(args.state, "claude")
    return None


def limit_reset(session, folder=None):
    # The resetsAt of the session's transcript when its last assistant record is the usage limit,
    # else None. The CLI writes the transcript, one JSON object per line, under its config folder.
    config = folder
    if config is None:
        config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(
            os.path.expanduser("~"), ".claude"
        )
    pattern = os.path.join(glob.escape(config), "projects", "*", f"{session}.jsonl")
    for path in glob.glob(pattern):
        try:
            with open(path, "rb") as transcript:
                text = transcript.read().decode("utf-8", errors="replace")
        except OSError:
            return None
        # Split on newlines only: a line separator inside a JSON string is not the end of a record.
        last = None
        for line in text.split("\n"):
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if isinstance(record, dict) and record.get("type") == "assistant":
                last = record
        if last is None or last.get("apiError") != "usage_limit_reached":
            continue
        params = last.get("apiErrorParams")
        info = params.get("rate_limit_info") if isinstance(params, dict) else None
        reset = info.get("resetsAt") if isinstance(info, dict) else None
        if isinstance(reset, bool) or not isinstance(reset, (int, float)):
            return None
        return reset
    return None


def wait_limit(args, reset, session):
    # Sleeps a poll at a time until the reset and one more poll; the halt file is read after each
    # sleep. Returns the halt's line when it is set during the wait, None when the wait ran out.
    halt = os.path.join(args.state, "halt")
    while True:
        remaining = reset + args.poll - time.time()
        if remaining <= 0:
            return None
        time.sleep(min(args.poll, remaining))
        if os.path.exists(halt):
            return (
                "halt: the halt file was set during the wait for the usage limit "
                f"(session `{session}`)"
            )


def halted_after(args, session):
    # A halt file set while the session ran (by `halt` or a hook) leaves its outcome unread, no end line.
    if os.path.exists(os.path.join(args.state, "halt")):
        return f"halt: the halt file was set while the session ran (session `{session}`)"
    return None


def usage_limit(command, args, project, record, out, reset):
    # The session's transcript ends in the usage limit: the driver parks when the reset is further
    # away than --limit-hours, else waits for it and resumes the session once. Returns (line, code),
    # or None when a STOP issue stopped the resumed session.
    session = record["session"]
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(reset))
    if reset - time.time() > args.limit_hours * 3600:
        line = (
            f"park: the usage limit resets at {when}, more than {args.limit_hours:g} hours away "
            f"(session `{session}`)"
        )
        say(line, 1)
        write_end(args.state, session, line, out)
        return line, 1
    line = f"limit: the usage limit was reached; waiting until {when} (session `{session}`)"
    say(line, 0)
    write_end(args.state, session, line, out)
    halted = wait_limit(args, reset, session)
    if halted:
        say(halted, 1)
        return halted, 1
    # The resumed command is the session's own, with --resume in place of --session-id.
    resumed = list(command)
    resumed[resumed.index("--session-id")] = "--resume"
    done = run_session(resumed, LIMIT_PROMPT, args, project, record["issue"], record)
    if done is None:
        return None
    if done is PAST:
        line, code = past_bound(args, session)
        say(line, code)
        return line, code
    stdout, returncode = done
    out = stdout.decode("utf-8", errors="replace")
    halted = halted_after(args, session)
    if halted:
        say(halted, 1)
        return halted, 1
    if limit_reset(session, transcripts(args, record)) is not None:
        line, code = f"park: the usage limit was reached (session `{session}`)", 1
    else:
        line, code = outcome(out, returncode, session, project, args.gh, record["step"])
    say(line, code)
    write_end(args.state, session, line, out)
    return line, code


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
    halted = halted_after(args, record["session"])
    if halted:
        say(halted, 1)
        return halted, 1
    out = stdout.decode("utf-8", errors="replace")
    # A session that hit the usage limit is waited for and resumed, or parked, before its outcome.
    reset = limit_reset(record["session"], transcripts(args, record))
    if reset is not None:
        return usage_limit(command, args, project, record, out, reset)
    line, code = outcome(out, returncode, record["session"], project, args.gh, record["step"])
    say(line, code)
    write_end(args.state, record["session"], line, out)
    return line, code


def finish(args, home, project, started, record, line, code, open_list, pr=None, head=None):
    # The step's end, once its outcome is printed: the park's issue, a halt set during the step, and
    # the run's issue closed with the outcome as its comment. A gh that failed (exit 2) is what the
    # step cannot use, so no further gh call is made. pr and head come from a gated park only.
    number = record["issue"]
    parked = None
    if line.startswith("park:"):
        parked = park_issue(
            project,
            args.gh,
            args.state,
            line,
            record["step"],
            record["session"],
            open_list,
            pr,
            head,
        )
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
