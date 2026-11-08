"""The wait on a pull request's required checks. A pull request a session opened, or one found open
at a start, is polled every --poll seconds: first the halt file, then the project's open issues,
then the checks. Red checks on a pull request the run's session opened resume that session to fix
them, at most twice; red checks on a pull request with no session, or no checks at all for longer
than --wait-minutes, end the wait with a park line. A STOP issue halts the run, and the run's issue
closed ends it with no new step. Once the checks are green, the path check parks a pull request that
touches plan.md or a human-only path, the merge wait holds until the maintainer merges it, pulls
main, and waits for the evidence run on the new head. `on` runs these steps one after another, until
steps_per_night sessions have started or a park, a refusal or a halt ends the night."""

import os
import re
from time import monotonic, sleep

from driver import github, issues, livecheck, once, runlog, tree
from driver import home as driver_home
from driver.preflight import kit_lines
from driver.steps import Step


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
    if done is once.PAST:
        return once.past_bound(args, session)
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
            record["pr"] = number
        sleep(args.poll)


# to_main keeps off a project with a branch of the step it is given. The step that just merged still
# has its branch, and the project is usually on it; nothing is left there to protect.
MERGED = Step("merged")


def gated(paths, body, human_only, number):
    # The first that applies, or None. The number is only for the line.
    if "plan.md" in paths:
        return f"park: #{number} touches plan.md"
    for path in paths:
        for entry in human_only:
            if path == entry or (entry.endswith("/") and path.startswith(entry)):
                return f"park: #{number} touches a human-only path: `{path}`"
    if any(line.startswith("Oversized:") for line in body.splitlines()):
        return f"park: #{number} carries Oversized:"
    return None


def poll(args, project, record, read):
    # Every --poll seconds, as wait_pr: the switches first, then read(), which returns (result,
    # reason): result is the (line, code) that ends the wait, or None to go on; reason says a read
    # failed. A failed read is skipped, and nothing is read while the issues cannot be, up to
    # --wait-minutes.
    blind_since = None
    while True:
        line, code, reason = read_switches(args, project, record)
        if line:
            return line, code
        result, reason = (None, reason) if reason else read()
        if result:
            return result
        if reason is None:
            blind_since = None
        else:
            blind_since = monotonic() if blind_since is None else blind_since
            if monotonic() - blind_since > args.wait_minutes * 60:
                return f"cannot read the project: {reason}", 2
        sleep(args.poll)


def wait_evidence(args, project, record, sha):
    # Day 4's line for the commit: a run that ended badly parks at once; one not finished, or not
    # there yet, is waited out up to --wait-minutes.
    started = monotonic()

    def read():
        line = github.evidence_line(project, args.gh, sha)
        if line is None:
            return (None, 0), None
        if line.startswith("cannot read the project: "):
            return None, line.removeprefix("cannot read the project: ")
        if " ended `" in line:
            return (line, 1), None
        if monotonic() - started > args.wait_minutes * 60:
            return (f"{line} after {args.wait_minutes:g} minutes", 1), None
        return None, None

    return poll(args, project, record, read)


def wait_merge(args, project, number, record, human_only, read_facts, git=("git",)):
    # After wait_pr's green: the path check, the maintainer's merge (no bound on it), main pulled,
    # and the evidence run on the new origin/main head. Returns (line, code); (None, 0) means the
    # next step can start.
    def read():
        state, _, paths, body, reason = github.pr_state(project, args.gh, number)
        if reason:
            return None, reason
        line = gated(paths, body, human_only, number)
        if line:
            return (line, 1), None
        if state == "CLOSED":
            return (f"park: #{number} was closed without a merge", 1), None
        if state == "MERGED":
            return (None, 0), None
        return None, None

    line, code = poll(args, project, record, read)
    if line is not None:
        return line, code
    _, line = tree.to_main(project, read_facts(project), MERGED, git)
    if line:
        return line, 1
    sha = read_facts(project).origin_main
    if sha is None:
        return f"cannot read the project: no origin/main after #{number} merged", 2
    return wait_evidence(args, project, record, sha)


def run(args, home, read_facts):
    # `on`: --once's halt, config and lock checks, the lock held for the whole run.
    return once.run(args, home, read_facts, steps)


def steps(args, home, project, read_facts, config):
    # Each step: the same start as --once's, then its pull request waited on, merged and pulled. A
    # resume does not count as a step, and a pull request found at a start starts no session.
    started, reason = driver_home.check(home)
    if reason:
        return once.refuse([f"cannot start: {reason}"])
    drift, code = once.preflight(args, project)
    if drift is None:
        return code
    line = livecheck.refusal(args.state, args.claude)
    if line:
        return once.refuse([line])
    record, count, open_list = None, 0, []

    def end(line, code):
        once.say(line, code)
        return once.finish(args, home, project, started, record, line, code, open_list)

    while True:
        if record is not None:
            # A STOP or a closed run's issue between steps, read as during a wait. A failed read
            # goes on: ready() reads the issues next and refuses.
            line, code, _ = read_switches(args, project, record)
            if line:
                return end(line, code)
            # The project moved on when the step merged: the next step is read from the new main.
            lines, drift = kit_lines(project)
            if lines:
                return end("\n".join(lines), 2)
        step = once.ready(args, project, read_facts, drift)
        open_list = step.open_list
        if step.kind in ("park", "end"):
            if record is None:
                return once.stopped(args, project, step)
            record = {**record, "step": step.sentence or record["step"], "session": "none"}
            return end(step.line, step.code)
        if step.kind == "wait":
            once.say(step.line, step.code)
            record, reason = once.open_record(args, project, step.sentence, "none", open_list)
            if reason:
                return once.refuse([f"cannot read the project: {reason}"])
            record["pr"] = int(re.search(r"#(\d+)", step.line).group(1))
            line, code = wait_found(args, project, step.line, record)
        else:
            record, command, prompt, reason = once.begin(args, home, project, config, step)
            if reason:
                return once.refuse([f"cannot read the project: {reason}"])
            count += 1
            done = once.one_session(command, prompt, args, project, record)
            if done is None:
                # The STOP issue stopped the session; the halt file and the report are written.
                return 1
            line, code = done
            if code != 0 or driver_home.check(home, started)[1]:
                return once.finish(args, home, project, started, record, line, code, open_list)
            record["pr"] = int(re.match(r"opened: #(\d+)", line).group(1))
            line, code = wait_pr(args, project, record["pr"], record, command)
        if line is None:
            line, code = wait_merge(
                args, project, record["pr"], record, config["human_only"], read_facts
            )
        if line is None:
            if count >= config["steps_per_night"]:
                line, code = f"on: {count} steps, the night's count", 0
            elif driver_home.check(home, started)[1]:
                # A resume can change the driver's files too: finish() halts on it.
                line, code = f"merged: #{record['pr']}", 0
        if line is not None:
            return end(line, code)
