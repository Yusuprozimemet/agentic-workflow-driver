"""The docker run command a session runs in: the project mounted at /work, the driver's hooks and
rules mounted read-only, the state folder and its refusals and Claude config mounted. The driver's
own folder (its .env, driver.json, .git) is never mounted. Plain stdlib: command() returns the list
and runs nothing."""

import os


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
