"""decide() gives the one line a dry run prints: the action the driver would take on the next step of
the project, or the reason it would park. Pure: no I/O, standard library only."""

import re
from dataclasses import dataclass

from driver.steps import Step, classify, phase_end


@dataclass(frozen=True)
class Facts:
    dirty: tuple[str, ...] = ()  # paths from `git status --porcelain`
    branch: str | None = "main"  # current branch; None on a detached HEAD
    main: str | None = None  # sha of local main
    origin_main: str | None = None  # sha of the remote's main; None when the remote has none
    branches: tuple[str, ...] = ()  # local branch names
    remote_branches: tuple[str, ...] = ()  # the remote's branch names, without "origin/"


@dataclass(frozen=True)
class Action:
    kind: str  # "start", "wait" or "park"
    line: str  # the line the dry run prints


def _park(reason: str) -> Action:
    return Action("park", f"park: {reason}")


def _is_branch_of(step: Step, name: str) -> bool:
    # A track's branches may carry letters and digits after its prefix, so that a track's own
    # sub-parts are still the track's. A day's spec or close takes only a "-" after its prefix.
    tail = r"[a-z0-9]*" if step.track is not None else ""
    return re.fullmatch(re.escape(step.prefix) + tail + r"(-.*)?", name) is not None


def decide(drift: dict, facts: Facts) -> Action:
    sentence = drift["now"]["next_step"]
    open_prs = drift["now"]["open_prs"]
    step = classify(sentence)
    if open_prs:
        numbers = ", ".join(f"#{pr['number']}" for pr in open_prs)
        return Action("wait", f"wait: {numbers}")
    if step.kind == "wait":
        return _park("the next step waits on no open pull request")
    if facts.dirty:
        return _park(f"the project's tree is not clean ({len(facts.dirty)} paths)")
    if facts.branch is None:
        return _park("the project is on a detached HEAD, not on main")
    if facts.branch != "main":
        return _park(f"the project is on {facts.branch}, not on main")
    if facts.origin_main is None:
        return _park("the project has no origin/main")
    if facts.main != facts.origin_main:
        return _park("main is not origin/main")
    if step.kind == "park":
        return _park(step.reason)
    reason = phase_end(step, drift["order"], drift["days"])
    if reason:
        return _park(reason)
    if step.kind == "step":
        # Local branches first, then the remote's.
        for name in (*facts.branches, *facts.remote_branches):
            if _is_branch_of(step, name):
                return _park(f"a branch of this step exists: {name}")
    return Action("start", f"start: {sentence}")
