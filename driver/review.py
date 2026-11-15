"""The reviewer: a session the driver starts once a pull request's checks are green, new and never the
step's, from the brief rules/reviewer.md. agents() writes <state>/agents.json, the file --agents reads,
afresh: one agent, reviewer, whose prompt is the brief. The file goes in <state>, not on the command
line: cmd.exe drops a newline and what follows it.

snapshot() reads HEAD, the refs, the stash's top and git status with read-only git commands;
changed() names the first that moved.

verdict() reads the reviewer's result: its found: lines and blockers, when the REVIEW line agrees
with them; body() is the comment the driver posts on the pull request.

run() starts the reviewer's session for a pull request with green checks, in the container when the
config has one, and writes its end line; it returns the session, a line that parks the run, and the
verdict."""

import json
import os
import shutil
import subprocess
import uuid

from driver import box, livecheck, once, runlog, stream
from driver import settings as driver_settings
from driver.preflight import image_claude

DESCRIPTION = (
    "Reviews one pull request the driver's step opened, reads only, and ends with a REVIEW line."
)
TOOLS = ["Read", "Grep", "Glob", "Bash"]
NAMES = (
    ("head", "HEAD"),
    ("refs", "the refs"),
    ("stash_top", "the stash"),
    ("status", "`git status`"),
)
BLOCKER = "found: blocker — "
ADVICE = "found: advice — "


def agents(state, home, inside=False):
    state = os.path.abspath(state)
    os.makedirs(state, exist_ok=True)
    with open(os.path.join(home, "rules", "reviewer.md"), "rb") as f:
        prompt = f.read().decode("utf-8")
    body = {"reviewer": {"description": DESCRIPTION, "prompt": prompt, "tools": TOOLS}}
    path = os.path.join(state, "agents.json")
    with open(path, "wb") as f:
        f.write(json.dumps(body, indent=2).encode("utf-8"))
    return "/state/agents.json" if inside else path


def _read(project, git, *args):
    # cwd, not -C: the arguments start with the subcommand. A git that cannot run, or fails, is None.
    try:
        done = subprocess.run(
            [*git, *args],
            cwd=project,
            capture_output=True,
            check=False,
            stdin=subprocess.DEVNULL,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except OSError:
        return None
    if done.returncode != 0:
        return None
    return done.stdout.decode("utf-8", errors="replace")


def snapshot(project, git=("git",)):
    # Read-only git only. The refs and the stash's top come from one listing; the stash's line is
    # split off so that a new stash moves stash_top and not refs.
    parts = [
        _read(project, git, "rev-parse", "HEAD"),
        _read(project, git, "rev-parse", "--symbolic-full-name", "HEAD"),
    ]
    head = None if None in parts else "\n".join(part.strip() for part in parts)
    listed = _read(project, git, "for-each-ref", "--format=%(refname) %(objectname)")
    if listed is None:
        refs = stash_top = None
    else:
        lines = listed.splitlines()
        tops = [line for line in lines if line.startswith("refs/stash ")]
        stash_top = tops[0] if tops else ""
        refs = "\n".join(line for line in lines if not line.startswith("refs/stash "))
    status = _read(project, git, "status", "--porcelain=v1", "--untracked-files=all")
    return {"head": head, "refs": refs, "stash_top": stash_top, "status": status}


def changed(before, after):
    for key, name in NAMES:
        if before[key] != after[key]:
            return name
    return None


def verdict(text):
    # The found lines and the blockers, only when the REVIEW line (the last non-empty one) agrees
    # with them; anything else is None, and the driver does not post it as a verdict.
    lines = text.splitlines()
    found = [line for line in lines if line.startswith((BLOCKER, ADVICE))]
    blockers = [line for line in found if line.startswith(BLOCKER)]
    filled = [line.strip() for line in lines if line.strip()]
    last = filled[-1] if filled else None
    if (last == "REVIEW: blocker" and blockers) or (last == "REVIEW: none" and not blockers):
        return found, blockers
    return None


def body(head, session, found):
    # The comment on the pull request: what was found, then the REVIEW line the blockers decide.
    lines = [f"review of `{head}` (session `{session}`):"]
    lines += found or ["nothing found"]
    blocked = any(line.startswith(BLOCKER) for line in found)
    lines.append("REVIEW: blocker" if blocked else "REVIEW: none")
    return "\n".join(lines)


def run(args, home, project, number, record, config, head):
    # The reviewer is a session of its own: a new uuid, the agent from agents(), and the read-only
    # settings. Returns (session, line, code, found): a line parks the run, and found is None when
    # the reply gave no verdict.
    session = str(uuid.uuid4())
    boxed = "container_image" in config
    reviewer = {**record, "session": session}
    if boxed:
        reviewer["container"] = f"driver-{session}"
    agents_path = agents(args.state, home, inside=boxed)
    settings_path = driver_settings.review(args.state, home, inside=boxed)
    if boxed:
        version = livecheck.version(*image_claude(args.docker, config["container_image"]))
    else:
        version = livecheck.version(shutil.which(args.claude))
    runlog.start(
        args.state,
        record["step"],
        "review",
        session,
        version,
        issue=record["issue"],
        container=reviewer.get("container"),
    )
    argv = once.command(
        args,
        home,
        config,
        settings_path,
        session,
        extra=("--agents", agents_path, "--agent", "reviewer"),
    )
    # The reviewer's brief is its agent's prompt; the step's rules file is not sent to it.
    at = argv.index("--append-system-prompt-file")
    del argv[at : at + 2]
    if boxed:
        argv[argv.index("--settings") + 1] = "/state/review-container-settings.json"
        argv = box.command(
            args.docker,
            config["container_image"],
            config["container_secrets"],
            home,
            args.state,
            project,
            reviewer["container"],
            argv,
        )
    prompt = (
        f"Review pull request #{number} at commit {head}, for the step: {record['step']}.\n"
        "Read it as your brief says, change nothing, and end with the REVIEW line.\n"
    )
    done = once.run_session(argv, prompt, args, project, record["issue"], reviewer)
    if done is None:
        return session, "halt: the reviewer's session was stopped", 1, None
    if done is once.PAST:
        return (session, *once.past_bound(args, session), None)
    stdout, _ = done
    stopped = once.halted_after(args, session)
    if stopped:
        return session, stopped, 1, None
    out = stdout.decode("utf-8", errors="replace")
    data = stream.result(out)
    found = None
    replied = data is not None and data.get("is_error") is not True
    if replied and isinstance(data.get("result"), str):
        found = verdict(data["result"])
    if found is None:
        outcome = f"park: the reviewer gave no verdict on #{number} (session `{session}`)"
    else:
        outcome = f"review: #{number}, {len(found[1])} blockers"
    once.write_end(args.state, session, outcome, out)
    return session, None, 0, found
