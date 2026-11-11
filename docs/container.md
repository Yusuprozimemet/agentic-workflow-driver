# The session's container

From Day 10 the driver can start each step's `claude -p` in a Docker container instead of on the
PC (`plan.md`, "The session's container"). The driver itself stays on the PC; only the session
moves. This page is what the maintainer sets up once: the image, the secrets file, the two
`driver.json` keys and the protection on the project's `main`.

It needs Docker Desktop running (checked on 29.4.3, WSL 2).

## The image

[`docker/Dockerfile`](../docker/Dockerfile) builds it from `node:22-trixie-slim`: Claude Code,
Python 3 in a virtual environment at `/opt/venv` (first on `PATH`, so `python` and `pip` are
its), git and `gh`, run as the user `node`. Build it from the driver's repository:

```bash
docker build --build-arg CLAUDE_VERSION=2.1.322 --build-arg GIT_NAME="Driver session" --build-arg GIT_EMAIL=<your email> -t agentic-workflow-driver-session:2.1.322 docker
```

- `CLAUDE_VERSION` is the Claude Code version the image installs. Use one that
  `run-steps.py live-check` has passed on (`state/live-checked.txt`), and give the tag the same
  version: the driver checks the image's Claude Code before a session.
- `GIT_NAME` and `GIT_EMAIL` are the commit identity inside the container. Give a `GIT_NAME`
  other than the one on the PC (`git config --global user.name`), so that a commit made in the
  container can be told from one made on the PC. The email can stay yours, so GitHub links the
  commit to your account.
- All three are required: the build stops if one is empty.

The image's system git config (`/etc/gitconfig`) sets what the PC's global config would have:
`safe.directory = /work` (the mounted checkout's files are owned by root, and git refuses them
otherwise), `core.autocrlf = true` and `core.filemode = false` (else every file of a Windows
checkout reads as changed), the identity above, and `credential.helper = !gh auth git-credential`,
so that `git push` uses `GH_TOKEN`.

The image carries no project's test tools. The session installs the project as CI does, with
`pip install` into `/opt/venv` (for a kit project, `python -m pip install -r requirements.txt` and
`pip install -e .` when CI runs them), before its tests: bearing's console-script test fails
without the install.

## The secrets file

Two secrets reach the session as environment variables, from one file the driver passes with
`--env-file`. They are never on the command line, in the run log, or in a mount:

```text
GH_TOKEN=<the fine-grained token>
CLAUDE_CODE_OAUTH_TOKEN=<the token claude setup-token prints>
```

- `CLAUDE_CODE_OAUTH_TOKEN`: run `claude setup-token` on the PC and copy the token it prints. It
  is long-lived and spends your subscription.
- `GH_TOKEN`: a fine-grained personal access token, as "The token" in `plan.md` scopes it: the
  trial's repository only; contents, pull requests and issues; no Administration, no Workflows.
  GitHub then refuses a change to the protection and a push that edits `.github/workflows/`.

Keep the file outside both repositories (the driver's and the project's), for example
`C:\Users\<you>\driver-secrets.env`. It is never mounted into the container.

## The two `driver.json` keys

Given together, or not at all:

```json
{
  "container_image": "agentic-workflow-driver-session:2.1.322",
  "container_secrets": "C:\\Users\\<you>\\driver-secrets.env"
}
```

- `container_image`: the tag built above.
- `container_secrets`: the secrets file's absolute path.

With neither, the driver runs every session on the PC as before, at level 1 only. With both,
every session runs in the container, and only those sessions count toward level 2.

## What the session sees

The driver runs `docker run -i --rm --name <a name from the session's id> --env-file <secrets>
-e CLAUDE_CONFIG_DIR=/claude -w /work`, the image and `claude -p ...`, with these six mounts and
no other:

| Mount | In the container | |
|---|---|---|
| `--mount type=bind,source=<project>,target=/work` | the project's checkout | writable |
| `--mount type=bind,source=<home>/hooks,target=/driver/hooks,readonly` | the driver's hooks | read-only |
| `--mount type=bind,source=<home>/rules,target=/driver/rules,readonly` | the driver's rules | read-only |
| `--mount type=bind,source=<state>,target=/state,readonly` | the state folder: the halt file, the settings file | read-only |
| `--mount type=bind,source=<state>/refusals,target=/state/refusals` | the hooks' log | writable |
| `--mount type=bind,source=<state>/claude,target=/claude` | the session's Claude Code folder: its transcripts | writable |

`<home>` is the driver's folder and `<state>` its state folder. The driver's folder itself (its
`.env`, `driver.json` and `.git`) is not mounted, nor is the Docker socket, your profile or
`~/.claude`, the folder that holds the repositories, or the secrets file. The container is never
started `--privileged`. Any of those would hand the session the PC back.

## On GitHub

On the project's repository, protect `main` with a rule that requires a pull request, and turn on
"Do not allow bypassing the above settings", so that administrators, and the driver merging under
your login, cannot merge past a red check. `python scripts/setup-check.py` reports it.

## Checking the image

```bash
DRIVER_CONTAINER_IMAGE=agentic-workflow-driver-session:2.1.322 python -m unittest tests.test_image_live
```

It runs `python`, `pip`, git's system config, the user and `claude --version` in the image.
Without the variable it skips.
