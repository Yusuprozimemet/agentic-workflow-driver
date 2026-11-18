"""The wait on a pull request's required checks. A pull request a session opened, or one found open
at a start, is polled every --poll seconds: first the halt file, then the project's open issues,
then the checks. Red checks on a pull request the run's session opened resume that session to fix
them, at most twice; red checks on a pull request with no session, or no checks at all for longer
than --wait-minutes, end the wait with a park line. A STOP issue halts the run, and the run's issue
closed ends it with no new step. Once the checks are green, the path check parks a pull request that
touches plan.md or a human-only path, the merge wait holds until the maintainer merges it, pulls
main, and waits for the evidence run on the new head. `on` runs these steps one after another, until
steps_per_night sessions have started or a park, a refusal or a halt ends the night. With `review`
on in driver.json, wait_reviewed runs the reviewer once the checks are green, before the merge
wait."""

import os
import re
from time import monotonic, sleep

from driver import github, issues, livecheck, once, review, runlog, status, switchlog, tree
from driver import home as driver_home
from driver.preflight import image_claude, kit_lines
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
        switchlog.append(args.state, "off", issue=record["issue"])
        return f"off: the run's issue #{record['issue']} is closed; nothing new starts", 0, None
    return None, None, None


# Absent is off, so the tests' own driver.json files keep their call lists.
def reviewing(config):
    return config is not None and config.get("review") is True


def wait_found(args, project, line, record, home=None, config=None):
    # `line` is decide()'s "wait: #3, #5" for a pull request found at a start. That pull request has
    # no session of this run, so a red check parks it.
    numbers = re.findall(r"#(\d+)", line)
    if len(numbers) > 1:
        return "park: more than one open pull request: " + ", ".join(f"#{n}" for n in numbers), 1
    if reviewing(config):
        return wait_reviewed(args, home, project, int(numbers[0]), record, None, config)
    return wait_pr(args, project, int(numbers[0]), record)


def resume(args, project, number, record, command, failed, used):
    # Builds the fix's prompt from the failed checks and runs it through fix().
    names = ", ".join(entry["name"] for entry in failed)
    log = github.failed_lines(project, args.gh, failed)
    prompt = (
        f"The required checks failed on #{number}: {names}.\n{log}\n"
        "Fix this step's pull request, push, and stop.\n"
    )
    return fix(args, project, number, record, command, prompt, used)


def fix(args, project, number, record, command, prompt, used):
    # Runs one fix of a pull request: the fix line is written before the session starts, so that a
    # crash during it still counts. Returns (line, code), as the session's outcome reads.
    session = record["session"]
    runlog.fix(args.state, session, number, used + 1)
    again = ["--resume" if part == "--session-id" else part for part in command]
    done = once.run_session(again, prompt, args, project, record["issue"], record)
    if done is None:
        # A STOP issue stopped the session; the report and the halt file are already written.
        return "halt: the resumed session was stopped", 1
    if done is once.PAST:
        return once.past_bound(args, session)
    stdout, returncode = done
    halted = once.halted_after(args, session)
    if halted:
        return halted, 1
    out = stdout.decode("utf-8", errors="replace")
    line, code = once.outcome(out, returncode, session, project, args.gh, record["step"])
    once.write_end(args.state, session, line, out)
    return line, code


def wait_pr(args, project, number, record, command=None):
    # `command` is the session's claude command, or None for a pull request with no session of this
    # run. Returns (line, code); (None, 0) means the checks are green.
    runlog.wait(args.state, number)
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
            runlog.wait(args.state, number)
        sleep(args.poll)


# A pull request's fixes, shared by the red checks and the reviewer's blockers: the run parks when a
# pull request has had this many. wait_pr's own red-check limit is written out where it is used.
FIXES = 2


def review_pass(args, home, project, number, record, command, config):
    # One pass of the reviewer: returns (line, code, blockers). (None, 0, []) means the merge wait goes
    # on with no blocker. The reviewer reads the head the pull request had when its checks went green; a
    # change to the project during its session parks.
    line, code = wait_pr(args, project, number, record, command)
    if line:
        return line, code, []
    number = record["pr"]  # a fix may have moved the pull request
    heads = []

    def read():
        state, _, _, _, failed, head = github.pr_state(project, args.gh, number)
        if failed:
            return None, failed
        if state in ("MERGED", "CLOSED"):
            return (None, 0), None
        if head is None:
            return None, f"gh pr view gave #{number} no head"
        heads.append(head)
        return (None, 0), None

    line, code = poll(args, project, record, read)
    if line:
        return line, code, []
    if not heads:
        return None, 0, []
    head = heads[0]
    before = review.snapshot(project)
    if None in before.values():
        return f"cannot read the project: git failed before the review of #{number}", 2, []
    session, line, code, found = review.run(args, home, project, number, record, config, head)
    if line:
        return line, code, []
    where = f"#{number} (session `{session}`)"
    after = review.snapshot(project)
    if None in after.values():
        return f"cannot read the project: git failed before the review of #{number}", 2, []
    what = review.changed(before, after)
    if what:
        return f"park: the reviewer changed {what} in the project on {where}", 1, []
    if found is None:
        return f"park: the reviewer gave no verdict on {where}", 1, []
    lines, blockers = found
    print(f"review: #{number}, {len(blockers)} blockers", flush=True)
    failed = issues.pr_comment(project, args.gh, number, review.body(head, session, lines))
    if failed:
        print(f"review: no comment on #{number}: {failed}", flush=True)
    runlog.review(args.state, number, session, head, len(blockers))
    return None, 0, blockers


def wait_reviewed(args, home, project, number, record, command, config):
    # Returns (line, code); (None, 0) means the merge wait goes on. A blocker resumes the step's session
    # to fix it, and the reviewer reads the fixed pull request again, FIXES fixes at most.
    while True:
        line, code, blockers = review_pass(args, home, project, number, record, command, config)
        if line or not blockers:
            return line, code
        number = record["pr"]
        first = blockers[0].removeprefix(review.BLOCKER)
        if not command:
            return f"park: the reviewer has a blocker on #{number}: {first}", 1
        used = runlog.fixes(args.state, record["session"])
        if used >= FIXES:
            return f"park: the reviewer still has a blocker on #{number} after two fixes", 1
        prompt = (
            f"The reviewer found a blocker on #{number}:\n"
            + "\n".join(blockers)
            + "\nFix this step's pull request, push, and stop.\n"
        )
        line, code = fix(args, project, number, record, command, prompt, used)
        if code != 0:
            return line, code
        print(line, flush=True)
        record["pr"] = int(re.match(r"opened: #(\d+)", line).group(1))
        number = record["pr"]


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


def reviewed_head(records, number):
    # The head of the newest review line for the pull request, when that review has no blocker; else None.
    for record in reversed(records or []):
        if record.get("event") == "review" and record.get("pr") == number:
            return record.get("head") if record.get("blockers") == 0 else None
    return None


def level_2_merge(args, project, number, level2, asked, now):
    # Level 2's merge, decided once per pull request: the count, then the driver's own repository, then
    # the head of the newest review line, then gh pr merge with that head. The head check parks when the
    # review's head is not now, the head this read of the pull request gave. Returns the (line, code) that
    # ends the wait, or None to go on waiting as at level 1; on a failed merge asked holds its reason.
    # Whether it merged is read from GitHub next.
    records, _ = runlog.read(args.state)
    in_a_row = status.level_2_run(records) if records is not None else 0
    if in_a_row < status.LEVEL_2_RUN:
        line = (
            f"level 2: #{number} waits for the maintainer: "
            f"{in_a_row} of {status.LEVEL_2_RUN} in a row"
        )
        print(line, flush=True)
        runlog.level(args.state, number, line)
        asked.append(False)
        return None
    home, started = level2
    _, reason = driver_home.check(home, started)
    if reason:
        return f"halt: {reason}; #{number} not merged", 1
    head = reviewed_head(records, number)
    if head is None or head != now:
        return f"park: #{number} moved after the review", 1
    reason = github.merge(project, args.gh, number, head)
    # A failed merge is kept as its reason: wait_merge then reads the pull request once more.
    asked.append(True if reason is None else reason)
    return None


def wait_merge(args, project, number, record, human_only, read_facts, git=("git",), level2=None):
    # After wait_pr's green: the path check, the maintainer's merge (no bound on it), main pulled,
    # and the evidence run on the new origin/main head. Returns (line, code, keys); (None, 0, {})
    # means the next step can start. keys is a gated park's pr and head, for once.finish; {} in
    # every other return. level2 is (home, started) at level 2, and the driver then asks the merge
    # itself once, at the first OPEN read whose path check passes (level_2_merge); a moved head parks
    # there, and a failed merge is read once more.
    heads, keys, asked = [], {}, []

    def read():
        state, _, paths, body, reason, head = github.pr_state(project, args.gh, number)
        if reason:
            return None, reason
        # The head of the first successful read is kept: a commit pushed after the green changes it.
        if not heads:
            heads.append(head)
        line = gated(paths, body, human_only, number)
        if line:
            keys.update(pr=number)
            if head is not None:
                keys["head"] = head
            return (line, 1), None
        if state == "CLOSED":
            return (f"park: #{number} was closed without a merge", 1), None
        if level2 is not None and state == "OPEN" and not asked:
            ended = level_2_merge(args, project, number, level2, asked, head)
            if ended is not None:
                if ended[0].startswith("park:"):
                    # The moved park keeps pr and head, as a gated park does.
                    keys.update(pr=number, **({} if head is None else {"head": head}))
                return ended, None
            failed = asked[-1] if isinstance(asked[-1], str) else None
            if failed is not None:
                # Whether it merged is read from GitHub, not from the merge's exit: someone else may have.
                state, _, _, _, again, head = github.pr_state(project, args.gh, number)
                if again or state != "MERGED":
                    return (f"park: the merge of #{number} failed: {failed}", 1), None
        if state == "MERGED":
            changed = None if head is None or heads[0] is None else head != heads[0]
            runlog.merged(args.state, number, head, changed, "driver" if True in asked else None)
            return (None, 0), None
        return None, None

    line, code = poll(args, project, record, read)
    if line is not None:
        return line, code, keys
    _, line = tree.to_main(project, read_facts(project), MERGED, git)
    if line:
        return line, 1, {}
    sha = read_facts(project).origin_main
    if sha is None:
        return f"cannot read the project: no origin/main after #{number} merged", 2, {}
    line, code = wait_evidence(args, project, record, sha)
    return line, code, {}


def run(args, home, read_facts):
    # `on`: --once's halt, config and lock checks, the lock held for the whole run.
    return once.run(args, home, read_facts, steps)


def level_2_refusals(args, project, config):
    # Level 2 starts only with review on, the sessions in the container, 15 merges in a row without a change
    # and main protected with no bypass. One line per condition that fails, in this order; the protection
    # is read only when the first three hold, so a start that is refused for them makes no api call.
    path = args.config
    lines = []
    if config.get("review") is not True:
        lines.append(f'cannot start: level 2 needs "review": true in {path}')
    if "container_image" not in config:
        lines.append(
            f"cannot start: level 2 needs the sessions in the container: {path} has no container_image"
        )
    records, _ = runlog.read(args.state)
    k = status.level_2_run(records) if records is not None else 0
    if k < status.LEVEL_2_RUN:
        lines.append(
            f"cannot start: level 2 needs {status.LEVEL_2_RUN} of {status.LEVEL_2_RUN} pull requests "
            f"in a row merged without a change asked; status counts {k}"
        )
    if lines:
        return lines
    reason = github.protection(project, args.gh)
    if reason is not None:
        lines.append(
            "cannot start: level 2 needs main to require a pull request and its checks with no bypass: "
            f"{reason}"
        )
    return lines


def steps(args, home, project, read_facts, config):
    # Each step: the same start as --once's, then its pull request waited on, merged and pulled. A
    # resume does not count as a step, and a pull request found at a start starts no session.
    started, reason = driver_home.check(home)
    if reason:
        return once.refuse([f"cannot start: {reason}"])
    drift, code = once.preflight(args, project, config)
    if drift is None:
        return code
    command = (
        image_claude(args.docker, config["container_image"])
        if "container_image" in config
        else None
    )
    line = livecheck.refusal(args.state, args.claude, command)
    if line:
        return once.refuse([line])
    if config.get("level") == 2:
        lines = level_2_refusals(args, project, config)
        if lines:
            return once.refuse(lines)
    reason = once.settle(args, project)
    if reason:
        return once.refuse([f"cannot read the project: {reason}"])
    switchlog.append(args.state, "on")
    record, count, open_list, shown = None, 0, [], None

    def end(line, code, **keys):
        once.say(line, code)
        return once.finish(args, home, project, started, record, line, code, open_list, **keys)

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
        step = once.ready(args, project, read_facts, drift, "container_image" in config)
        open_list = step.open_list
        if step.kind == "running":
            # Row 2: said once. Each poll reads the table again; row 1 or the row below ends it.
            if step.line != shown:
                once.say(step.line, step.code)
            shown = step.line
            sleep(args.poll)
            if record is None:  # with a record, the top of the loop reads the kit
                lines, drift = kit_lines(project)
                if lines:
                    return once.refuse(lines)
            continue
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
            line, code = wait_found(args, project, step.line, record, home=home, config=config)
        else:
            session, line = once.reached(args, home, project, config)
            if line:
                return once.refuse([line])
            record, command, prompt, reason = once.begin(args, home, project, config, step, session)
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
            if reviewing(config):
                line, code = wait_reviewed(
                    args, home, project, record["pr"], record, command, config
                )
            else:
                line, code = wait_pr(args, project, record["pr"], record, command)
        keys = {}
        if line is None:
            line, code, keys = wait_merge(
                args,
                project,
                record["pr"],
                record,
                config["human_only"],
                read_facts,
                level2=(home, started) if config.get("level") == 2 else None,
            )
        if line is None:
            if count >= config["steps_per_night"]:
                line, code = f"on: {count} steps, the night's count", 0
            elif driver_home.check(home, started)[1]:
                # A resume can change the driver's files too: finish() halts on it.
                line, code = f"merged: #{record['pr']}", 0
        if line is not None:
            return end(line, code, **keys)
