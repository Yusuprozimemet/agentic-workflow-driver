"""The driver's lock, the file <state>/lock that says a run is going. take() creates it with O_EXCL,
so two runs cannot both hold it; release() removes it only when it names this process. lives()
asks the OS whether the pid the lock names is still a driver, and never ends that process. Plain
stdlib: on Windows the questions go through ctypes, since signal 0 there is Ctrl+C."""

import ctypes
import datetime
import json
import os
import subprocess

STAMP = "%Y-%m-%dT%H:%M:%SZ"
# The lock is stamped in whole seconds, after the driver starts; 2 s covers that and ps rounding.
SLACK = datetime.timedelta(seconds=2)
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259
ERROR_ACCESS_DENIED = 5
EPOCH = datetime.datetime(1601, 1, 1, tzinfo=datetime.UTC)


def path(state):
    return os.path.join(state, "lock")


def now():
    return datetime.datetime.now(datetime.UTC)


def stamp_time(text):
    return datetime.datetime.strptime(text, STAMP).replace(tzinfo=datetime.UTC)


def take(state):
    os.makedirs(state, exist_ok=True)
    try:
        fd = os.open(path(state), os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0))
    except FileExistsError:
        return refusal(state)
    body = {"pid": os.getpid(), "started": now().strftime(STAMP)}
    with os.fdopen(fd, "wb") as f:
        f.write(json.dumps(body).encode("utf-8"))
    return None


def refusal(state):
    # Nothing here writes or removes the lock: the person decides, with run-steps.py clear.
    held = read(state)
    if held is None:
        return f"cannot start: {path(state)} cannot be read; run-steps.py clear removes it"
    pid, started = held
    if lives(pid, started):
        return f"cannot start: the driver is already running (pid {pid}, since {started})"
    return f"cannot start: a lock names pid {pid}, which is gone; run-steps.py clear removes it"


def read(state):
    try:
        with open(path(state), "rb") as f:
            lock = json.loads(f.read().decode("utf-8"))
    except (OSError, ValueError):
        # Absent and unreadable both come back as None; a caller checks whether the file exists.
        return None
    if not isinstance(lock, dict):
        return None
    pid = lock.get("pid")
    started = lock.get("started")
    # bool is an int in Python, but a true pid is not a bool; one past pid_t's range would crash
    # the OS call that asks after it, so it is a lock that cannot be read.
    if not isinstance(pid, int) or isinstance(pid, bool) or not 0 < pid < 2**31:
        return None
    if not isinstance(started, str):
        return None
    try:
        stamp_time(started)
    except ValueError:
        return None
    return pid, started


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
