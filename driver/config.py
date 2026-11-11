"""The driver's config, the JSON file run-steps.py reads for the project when --project is not given.
load() checks the whole file and returns every problem as one line, so a person fixes them in one
pass. The optional container_image and container_secrets come as a pair, and a session's container
needs both. Plain stdlib: the file is read as UTF-8 bytes, and a problem is never raised."""

import json
import os
from pathlib import Path


def is_path(value):
    return isinstance(value, str) and value != ""


def is_paths(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def is_budget(value):
    # bool is an int in Python, but a true budget is not a number: reject it by type first.
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def is_steps(value):
    # A float such as 2.0 is rejected: the driver counts steps, and a count is a whole number.
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def is_abs_path(value):
    return isinstance(value, str) and os.path.isabs(value)


def problems(path, config):
    # One line per key, in this order. A key that is absent is reported as missing, not as the
    # wrong type, so each line says what to add or what to change.
    rules = [
        ("project", is_path, f"cannot start: {path}'s project must be a path"),
        ("human_only", is_paths, f"cannot start: {path}'s human_only must be a list of paths"),
        ("budget_usd", is_budget, f"cannot start: {path}'s budget_usd must be a number above 0"),
        (
            "steps_per_night",
            is_steps,
            f"cannot start: {path}'s steps_per_night must be an integer of 1 or more",
        ),
    ]
    lines = []
    for key, ok, message in rules:
        if key not in config:
            lines.append(f"cannot start: {path} has no {key}")
        elif not ok(config[key]):
            lines.append(message)
    # The container keys are optional and come as a pair; each one present is checked for its type.
    image = "container_image" in config
    secrets = "container_secrets" in config
    if image and not secrets:
        lines.append(f"cannot start: {path} has container_image but no container_secrets")
    if secrets and not image:
        lines.append(f"cannot start: {path} has container_secrets but no container_image")
    if image and not is_path(config["container_image"]):
        lines.append(f"cannot start: {path}'s container_image must be an image name")
    if secrets and not is_abs_path(config["container_secrets"]):
        lines.append(f"cannot start: {path}'s container_secrets must be an absolute path")
    return lines


def load(path: Path) -> tuple[dict | None, list[str]]:
    # The path is printed as it was given, not resolved, so the person sees the name they typed.
    try:
        config = json.loads(path.read_bytes())
    except FileNotFoundError:
        return None, [f"cannot start: no --project, and no config at {path}"]
    except (OSError, ValueError):
        return None, [f"cannot start: {path} is not a JSON object"]
    if not isinstance(config, dict):
        return None, [f"cannot start: {path} is not a JSON object"]
    lines = problems(path, config)
    if lines:
        return None, lines
    # A relative project is relative to the config's own folder, so the config works from any cwd.
    project = (path.parent / config["project"]).resolve()
    return {**config, "project": project}, []
