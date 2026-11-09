"""The driver's lock, the file <state>/lock that says a run is going. take() creates it with O_EXCL,
so two runs cannot both hold it; a start that finds a lock whose process is gone takes it over, one
start at a time. release() removes it only when it names this process. lives() asks the OS whether
the pid the lock names is still a driver, and never ends that process. Plain stdlib: on Windows the
questions go through ctypes, since signal 0 there is Ctrl+C."""

import ctypes
import datetime
import json
import os
import subprocess
import time

STAMP = "%Y-%m-%dT%H:%M:%SZ"
# The lock is stamped in whole seconds, after the driver starts; 2 s covers that and ps rounding.
SLACK = datetime.timedelta(seconds=2)
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
ERROR_ACCESS_DENIED = 5
EPOCH = datetime.datetime(1601, 1, 1, tzinfo=datetime.UTC)
FLAGS = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
# How often, and how far apart, a takeover tries again while another start has the lock open.
REPLACE_TRIES = 20
REPLACE_PAUSE = 0.05


def path(state):
    return os.path.join(state, "lock")


def now():
    return datetime.datetime.now(datetime.UTC)


def stamp_time(text):
    return datetime.datetime.strptime(text, STAMP).replace(tzinfo=datetime.UTC)


def guard(state):
    return path(state) + ".takeover"


def body(**extra):
    record = {"pid": os.getpid(), "started": now().strftime(STAMP), **extra}
    return json.dumps(record).encode("utf-8")


def take(state):
    os.makedirs(state, exist_ok=True)
    try:
        fd = os.open(path(state), FLAGS)
    except (FileExistsError, PermissionError):
        # PermissionError is what Windows says while another start is replacing the file.
        return takeover(state)
    with os.fdopen(fd, "wb") as f:
        f.write(body())
    return None


def takeover(state):
    # None when this start now holds the lock; otherwise the line that refuses.
    held = read(state)
    if held is None or lives(*held):
        return refusal(state, held)
    try:
        fd = os.open(guard(state), FLAGS)
    except (FileExistsError, PermissionError):
        return (
            f"cannot start: {guard(state)} exists: another start is taking the lock over; "
            "run-steps.py clear removes it"
        )
    # Read again now no other start can replace it: one may have done so before this guard.
    held = read(state)
    stale = held is not None and not lives(*held)
    with os.fdopen(fd, "wb") as f:
        if stale:
            f.write(body(took_over=held[0]))
    if not stale:
        os.remove(guard(state))
        return refusal(state, held)
    return replace(state)


def replace(state):
    # The guard holds the new lock, so one os.replace swaps the lock and removes the guard.
    for _ in range(REPLACE_TRIES):
        try:
            os.replace(guard(state), path(state))
            return None
        except PermissionError:
            # Windows refuses while another start has the lock open to read it.
            time.sleep(REPLACE_PAUSE)
    os.remove(guard(state))
    return f"cannot start: {path(state)} cannot be replaced; run-steps.py clear removes it"


def refusal(state, held):
    # Nothing here writes or removes the lock: the person decides, with run-steps.py clear.
    if held is None:
        return f"cannot start: {path(state)} cannot be read; run-steps.py clear removes it"
    pid, started = held
    return f"cannot start: the driver is already running (pid {pid}, since {started})"


def load(state):
    # The lock's fields, or None: absent and unreadable both. A caller checks whether the file exists.
    try:
        with open(path(state), "rb") as f:
            lock = json.loads(f.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    return lock if isinstance(lock, dict) else None


def good_pid(pid):
    # bool is an int in Python, but a true pid is not a bool; one past pid_t's range would crash
    # the OS call that asks after it, so it is a lock that cannot be read.
    return isinstance(pid, int) and not isinstance(pid, bool) and 0 < pid < 2**31


def read(state):
    lock = load(state)
    if lock is None:
        return None
    pid = lock.get("pid")
    started = lock.get("started")
    if not good_pid(pid) or not isinstance(started, str):
        return None
    try:
        stamp_time(started)
    except ValueError:
        return None
    return pid, started


def took_over(state):
    # The pid this run's lock replaced, or None when the lock was free.
    lock = load(state)
    pid = None if lock is None else lock.get("took_over")
    return pid if good_pid(pid) else None


def lives(pid, started):
    # pid 0 and below would name a process group, not a driver.
    if pid <= 0:
        return False
    alive, begun = process(pid)
    if not alive:
        return False
    if begun is None:
        return True
    # A process that started after the lock was written has taken over the pid: it is not the driver.
    return begun <= stamp_time(started) + SLACK


def process(pid):
    # Returns (alive, started); started is None when the OS would not say.
    if os.name == "nt":
        return windows_process(pid)
    return posix_process(pid)


def windows_process(pid):
    # Imported here: ctypes.wintypes and WinDLL exist for Windows, and this runs only there.
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.GetExitCodeProcess.restype = wintypes.BOOL
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        # Access denied means the process is there and belongs to someone else; any other
        # failure means no such process.
        return ctypes.get_last_error() == ERROR_ACCESS_DENIED, None
    try:
        # A process that has exited still opens while a handle to it is held; its code says so.
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False, None
        if code.value != STILL_ACTIVE:
            return False, None
        created, exited, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return True, None
        ticks = (created.dwHighDateTime << 32) | created.dwLowDateTime
        return True, EPOCH + datetime.timedelta(microseconds=ticks // 10)
    finally:
        kernel32.CloseHandle(handle)


def posix_process(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False, None
    except PermissionError:
        # Someone else's process is still there; ps can still say when it started.
        pass
    return True, ps_started(pid)


def ps_started(pid):
    # ps prints the elapsed time as [[dd-]hh:]mm:ss; any failure leaves the start unknown.
    try:
        done = subprocess.run(
            ["ps", "-o", "etime=", "-p", str(pid)], check=False, capture_output=True, text=True
        )
        if done.returncode != 0:
            return None
        text = done.stdout.strip()
        days = 0
        if "-" in text:
            head, text = text.split("-", 1)
            days = int(head)
        parts = text.split(":")
        if len(parts) > 3:
            return None
        seconds = 0
        for part in parts:
            seconds = seconds * 60 + int(part)
    except (OSError, ValueError):
        return None
    return now() - datetime.timedelta(days=days, seconds=seconds)


def release(state):
    held = read(state)
    # Only this process's lock is ours to remove; a lock naming another pid stays as it is.
    if held is not None and held[0] == os.getpid():
        os.remove(path(state))
