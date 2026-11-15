"""The reviewer: a session the driver starts once a pull request's checks are green, new and never the
step's, from the brief rules/reviewer.md. agents() writes <state>/agents.json, the file --agents reads,
afresh: one agent, reviewer, whose prompt is the brief. The file goes in <state>, not on the command
line: cmd.exe drops a newline and what follows it."""

import json
import os

DESCRIPTION = (
    "Reviews one pull request the driver's step opened, reads only, and ends with a REVIEW line."
)
TOOLS = ["Read", "Grep", "Glob", "Bash"]


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
