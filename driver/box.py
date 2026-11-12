"""The docker run command a session runs in: the project mounted at /work, the driver's hooks and
rules mounted read-only, the state folder and its refusals and Claude config mounted. The driver's
own folder (its .env, driver.json, .git) is never mounted. Plain stdlib: command() returns the list
and runs nothing; reach() runs the probe in the container before a session starts."""

import os
import subprocess

# The probe's inner command, run in the session's container: the folders it checks, in its order.
# The first three must refuse a write, the last three must allow one (reach()).
FOLDERS = ["/driver/hooks", "/driver/rules", "/state", "/work", "/state/refusals", "/claude"]
PROBE = ["python", "/driver/hooks/probe.py", *FOLDERS]


def command(docker, image, secrets, home, state, project, name, inner, stdin=True):
    # Each source is resolved first: docker takes the path as the host has it, and on Windows a
    # temporary folder may be given by its 8.3 short name.
    home = os.path.realpath(home)
    state = os.path.realpath(state)
    run = [docker, "run"]
    if stdin:
        run.append("-i")
    run += ["--rm", "--name", name, "--env-file", secrets, "-e", "CLAUDE_CONFIG_DIR=/claude"]
    run += ["-w", "/work"]
    mounts = [
        f"type=bind,source={os.path.realpath(project)},target=/work",
        f"type=bind,source={os.path.join(home, 'hooks')},target=/driver/hooks,readonly",
        f"type=bind,source={os.path.join(home, 'rules')},target=/driver/rules,readonly",
        f"type=bind,source={state},target=/state,readonly",
        f"type=bind,source={os.path.join(state, 'refusals')},target=/state/refusals",
        f"type=bind,source={os.path.join(state, 'claude')},target=/claude",
    ]
    for mount in mounts:
        run += ["--mount", mount]
    return [*run, image, *inner]


def reach(docker, image, secrets, home, state, project, session):
    # The probe runs with the session's mounts, so what it prints is what the session can write.
    # Returns None when the folders are as they should be, else the one line the start refuses with.
    run = command(
        docker, image, secrets, home, state, project, f"driver-probe-{session}", PROBE, stdin=False
    )
    done = subprocess.run(run, capture_output=True, stdin=subprocess.DEVNULL, check=False)
    out = done.stdout.decode("utf-8", errors="replace").splitlines()
    err = done.stderr.decode("utf-8", errors="replace").splitlines()
    # A probe that exits non-zero, or prints other than one line per folder, is not believed.
    shaped = len(out) == len(FOLDERS) and all(
        line in (f"written {folder}", f"refused {folder}") for line, folder in zip(out, FOLDERS)
    )
    if done.returncode != 0 or not shaped:
        last = [line.strip() for line in err if line.strip()]
        why = last[-1] if last else f"exit {done.returncode}"
        return f"cannot start: the session's container cannot run the probe: {why}"
    words = [line.split(" ", 1)[0] for line in out]
    # A folder that must refuse but was written is named before one that must write but was refused.
    for word, folder in zip(words, FOLDERS):
        if word == "written" and folder in FOLDERS[:3]:
            return f"cannot start: the session's container can write `{folder}`"
    for word, folder in zip(words, FOLDERS):
        if word == "refused" and folder in FOLDERS[3:]:
            return f"cannot start: the session's container cannot write `{folder}`"
    return None
