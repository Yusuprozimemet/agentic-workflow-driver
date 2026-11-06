"""halt and clear, the two switches a person pulls with run-steps.py. halt writes <state>/halt and,
when the lock names a live driver, kills that process's tree. clear removes the halt file and a
stale lock, and refuses while a driver lives. Each prints one line and returns its exit code; neither
starts anything."""

import os
import signal
import subprocess

from driver import lock

TREE = "halt: set; killed pid {} and the processes it started"


def halt(state):
    os.makedirs(state, exist_ok=True)
    with open(os.path.join(state, "halt"), "wb") as f:
        f.write(f"halted at {lock.now().strftime(lock.STAMP)}".encode())
    if os.path.exists(lock.path(state)):
        held = lock.read(state)
        if held is None:
            print(f"halt: set; {lock.path(state)} cannot be read, so nothing was killed")
            return 1
        if lock.lives(*held):
            return kill(held[0])
    print("halt: set; no driver is running")
    return 0


def kill(pid):
    if os.name == "nt":
        done = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, check=False
        )
        if done.returncode == 0:
            print(TREE.format(pid))
            return 0
        lines = [line.strip() for line in done.stderr.splitlines() + done.stdout.splitlines()]
        reason = next((line for line in lines if line), f"taskkill exited {done.returncode}")
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


def clear(state):
    if os.path.exists(lock.path(state)):
        held = lock.read(state)
        if held is not None and lock.lives(*held):
            print(f"clear: pid {held[0]} still runs; halt again, or stop it by hand")
            return 1
        os.remove(lock.path(state))
    halt_file = os.path.join(state, "halt")
    if not os.path.exists(halt_file):
        print("clear: no halt is set")
        return 0
    os.remove(halt_file)
    print("clear: the halt is removed; the driver is off")
    return 0
