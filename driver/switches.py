"""halt, clear and off, the switches a person pulls with run-steps.py. halt writes <state>/halt and,
when the lock names a live driver, kills that process's tree; it also kills a session the run log
names as still alive. Then it reports on the run's issue from <state>/run.json. clear removes the
halt file and a stale lock, and refuses while a driver lives. off closes the project's open "Driver
run" issues, so the run ends after its current step. Each prints its lines and returns its exit
code; none starts anything."""

import json
import os
import signal
import subprocess
import sys

from driver import issues, lock, once, runlog

TREE = "halt: set; killed pid {} and the processes it started"
REPORT_KEYS = ("project", "gh", "issue", "step", "session")


def halt(state):
    os.makedirs(state, exist_ok=True)
    with open(os.path.join(state, "halt"), "wb") as f:
        f.write(f"halted at {lock.now().strftime(lock.STAMP)}".encode())
    # Read before the lock's kill, so that a session outside the driver's tree is still known.
    session, pid, reason = runlog.live_session(state)
    if reason:
        print(f"halt: {reason}; no session was looked for")
    code, reported, found = 0, False, False
    if os.path.exists(lock.path(state)):
        held = lock.read(state)
        if held is None:
            print(f"halt: set; {lock.path(state)} cannot be read, so nothing was killed")
            code, found = 1, True
        elif lock.lives(*held):
            found = True
            code = kill(held[0])
            if code == 0:
                _report(state)
                reported = True
    # Alive after the lock's kill means it was outside that tree; one the kill ended is not read.
    tried = session is not None and runlog.live_session(state)[:2] == (session, pid)
    if tried and kill_session(session, pid) and not reported:
        _report(state)
    if not found and not tried:
        print("halt: set; no driver is running")
    return code


def kill(pid):
    if os.name == "nt":
        reason = _taskkill(pid)
        if reason is None:
            print(TREE.format(pid))
            return 0
        print(f"halt: set; could not kill pid {pid}: {reason}")
        return 1
    # Only a process that leads its group takes its children with a group kill.
    try:
        if os.getpgid(pid) != pid:
            os.kill(pid, signal.SIGKILL)
            print(f"halt: set; killed pid {pid} only: it does not lead its process group")
            return 0
        os.killpg(pid, signal.SIGKILL)
    except OSError as exc:
        print(f"halt: set; could not kill pid {pid}: {exc.strerror or exc}")
        return 1
    print(TREE.format(pid))
    return 0


def _taskkill(pid):
    # None when taskkill ends the tree, else the reason it did not.
    done = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, check=False
    )
    if done.returncode == 0:
        return None
    lines = [line.strip() for line in done.stderr.splitlines() + done.stdout.splitlines()]
    return next((line for line in lines if line), f"taskkill exited {done.returncode}")


def _kill_tree(pid):
    # None when the session's tree is killed, else why not. A session leads no process group.
    if os.name == "nt":
        return _taskkill(pid)
    for target in [pid, *once.descendants(pid)]:
        try:
            os.kill(target, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError as exc:
            return exc.strerror or str(exc)
    return None


def kill_session(session, pid):
    # True when killed. A failure is said, and changes no exit code: the halt file stands.
    reason = _kill_tree(pid)
    if reason is None:
        print(f"halt: set; killed session `{session}` (pid {pid}) and the processes it started")
        return True
    print(f"halt: set; could not kill session `{session}` (pid {pid}): {reason}")
    return False


def _report(state):
    # The run's issue gets what the halt found, so the person reads it on the phone. A run.json that
    # cannot be read is said so; the halt stands either way.
    path = os.path.join(state, "run.json")
    if not os.path.exists(path):
        return
    try:
        with open(path, "rb") as f:
            record = json.loads(f.read())
    except (OSError, ValueError):
        record = None
    if not isinstance(record, dict) or not all(key in record for key in REPORT_KEYS):
        print(f"halt: no report: {path} cannot be read")
        return
    number = record["issue"]
    reason = issues.close(
        record["project"], record["gh"], number, issues.report(record["project"], record)
    )
    if reason is None:
        print(f"halt: reported on #{number}")
    else:
        print(f"halt: no report on #{number}: {reason}")


def clear(state):
    if os.path.exists(lock.path(state)):
        held = lock.read(state)
        if held is not None and lock.lives(*held):
            print(f"clear: pid {held[0]} still runs; halt again, or stop it by hand")
            return 1
        os.remove(lock.path(state))
    if os.path.exists(lock.guard(state)):
        os.remove(lock.guard(state))
    halt_file = os.path.join(state, "halt")
    if not os.path.exists(halt_file):
        print("clear: no halt is set")
        return 0
    os.remove(halt_file)
    print("clear: the halt is removed; the driver is off")
    return 0


def off(project, gh):
    # Closing a run's issue is the switch (plan.md, "The switches"). Only the maintainer's issues
    # count, as open_issues reads them: a run someone else opened is not a switch.
    listed, reason = issues.open_issues(project, gh)
    if reason is not None:
        print(f"cannot read the project: {reason}", file=sys.stderr)
        return 2
    runs = [issue["number"] for issue in listed if issue["title"].startswith("Driver run")]
    if not runs:
        print("off: no run is going")
        return 0
    for number in runs:
        comment = f"off from the PC at {lock.now().strftime(lock.STAMP)}\n"
        reason = issues.close(project, gh, number, comment)
        if reason is not None:
            print(f"cannot read the project: {reason}", file=sys.stderr)
            return 2
        print(
            f"off: closed the run's issue #{number}; the current step finishes, nothing new starts"
        )
    return 0
