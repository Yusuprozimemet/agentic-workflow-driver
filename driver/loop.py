"""The wait on a pull request's required checks. A pull request a session opened, or one found open
at a start, is polled every --poll seconds: first the halt file, then the project's open issues,
then the checks. Red checks on a pull request the run's session opened resume that session to fix
them, at most twice; red checks on a pull request with no session, or no checks at all for longer
than --wait-minutes, end the wait with a park line. A STOP issue halts the run, and the run's issue
closed ends it with no new step."""

import os
import re
from time import monotonic, sleep

from driver import github, issues, once, runlog


def read_switches(args, project, record):
    # Returns (line, code, reason): (line, code, None) when the run must end, (None, None, None) to
    # go on, and (None, None, reason) when the issues could not be read.
    halt = os.path.join(args.state, "halt")
    if os.path.exists(halt):
        return f"halt: `{halt}` exists; nothing more starts", 1, None
    open_list, reason = issues.open_issues(project, args.gh)
    if reason:
        return None, None, reason
    # The lowest-numbered STOP issue, sorted as once.run_session sorts them.
    stops = sorted(issue["number"] for issue in open_list if issue["title"].startswith("STOP"))
    if stops:
        number = stops[0]
        once.write_halt(args.state, f"STOP issue #{number}")
        reason = issues.close(
            project, args.gh, record["issue"], issues.report(project, record), timeout=10
        )
        if reason is None:
            print(f"halt: reported on #{record['issue']}", flush=True)
        else:
            print(f"halt: no report on #{record['issue']}: {reason}", flush=True)
        return f"halt: the STOP issue #{number} is open; nothing more starts", 1, None
    if record["issue"] not in [issue["number"] for issue in open_list]:
        return f"off: the run's issue #{record['issue']} is closed; nothing new starts", 0, None
    return None, None, None


def wait_found(args, project, line, record):
    # `line` is decide()'s "wait: #3, #5" for a pull request found at a start. That pull request has
    # no session of this run, so a red check parks it.
    numbers = re.findall(r"#(\d+)", line)
    if len(numbers) > 1:
        return "park: more than one open pull request: " + ", ".join(f"#{n}" for n in numbers), 1
    return wait_pr(args, project, int(numbers[0]), record)


def resume(args, project, number, record, command, failed, used):
    # Runs one fix: the fix line is written before the session starts, so that a crash during it
    # still counts. Returns (line, code), as the session's outcome reads.
    session = record["session"]
    names = ", ".join(entry["name"] for entry in failed)
    log = github.failed_lines(project, args.gh, failed)
    runlog.fix(args.state, session, number, used + 1)
    prompt = (
        f"The required checks failed on #{number}: {names}.\n{log}\n"
        "Fix this step's pull request, push, and stop.\n"
    )
    again = ["--resume" if part == "--session-id" else part for part in command]
    done = once.run_session(again, prompt, args, project, record["issue"], record)
    if done is None:
        # A STOP issue stopped the session; the report and the halt file are already written.
        return "halt: the resumed session was stopped", 1
    stdout, returncode = done
    out = stdout.decode("utf-8", errors="replace")
    line, code = once.outcome(out, returncode, session, project, args.gh, record["step"])
    once.write_end(args.state, session, line, out)
    return line, code


def wait_pr(args, project, number, record, command=None):
    # `command` is the session's claude command, or None for a pull request with no session of this
    # run. Returns (line, code); (None, 0) means the checks are green.
    blind_since = None  # since when nothing could be read, or no check exists
    while True:
        line, code, reason = read_switches(args, project, record)
        if line:
            return line, code
        # A failed read is skipped, as once.run_session skips one: one failed gh call in a night's
        # polling must not end the run, and nothing is acted on while blind. The wait is bounded by
        # --wait-minutes, so a gh that stays broken does not wait for ever.
        state, failed, reason = (
            (None, [], reason) if reason else github.checks(project, args.gh, number)
        )
        if state in (None, "none"):
            blind_since = blind_since if blind_since is not None else monotonic()
            if monotonic() - blind_since > args.wait_minutes * 60:
                if reason:
                    return f"cannot read the project: {reason}", 2
                return (
                    f"park: no required checks on #{number} after {args.wait_minutes:g} minutes",
                    1,
                )
        else:
            blind_since = None
        if state == "green":
            return None, 0
        if state == "red":
            names = ", ".join(entry["name"] for entry in failed)
            if command is None:
                return f"park: the checks on #{number} are red: {names}", 1
            used = runlog.fixes(args.state, record["session"])
            if used >= 2:
                return f"park: the checks on #{number} are still red after two fixes: {names}", 1
            line, code = resume(args, project, number, record, command, failed, used)
            if code != 0:
                return line, code
            print(line, flush=True)
            number = int(re.match(r"opened: #(\d+)", line).group(1))
        sleep(args.poll)
