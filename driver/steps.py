"""What `spec-drift.py --out` wrote, read as data: the kind of each next-step sentence (the sentences
`next_step()` returns in the kit at 393dda6) and a phase's end from the run order. Pure: no I/O,
standard library only."""

import re
from dataclasses import dataclass

UNKNOWN = "the next step is not one this driver knows"

# The kit formats a day as {:02d}: two digits, or more past 99. "Day 3" is not the kit's sentence.
NN = r"(\d{2}|[1-9]\d{2,})"
# A track's name as the kit writes it: letters and digits, such as B, A1 or 0.
TRACK = r"([A-Za-z0-9]+)"


@dataclass(frozen=True)
class Step:
    kind: str  # "step", "wait" or "park"
    day: int | None = None
    track: str | None = None  # as written in the sentence, e.g. "B", "A1", "0"
    prefix: str | None = None  # branch prefix, for a step
    reason: str | None = None  # for a park


# Each pattern must match the whole sentence, and they are checked in this order. A sentence in no
# row is a park, never a guess: a step guessed from a near miss could start the wrong work
# (plan.md, "What the driver needs from the kit"). The announced-track row comes before the track
# row, which takes any text after its colon.
RULES = [
    (r"Waiting on #\d+ .*", lambda m: Step("wait")),
    (r"Every day is done\.", lambda m: Step("park", reason="every day is done")),
    (
        r"No day specs yet: fill in plan\.md, then write the first day's spec \(specs/README\.md\)\.",
        lambda m: Step("park", reason="there are no day specs"),
    ),
    (
        rf'Day {NN}: write its day spec \((?:plan\.md lists it, specs/ has none|plan\.md: ".*")\)',
        lambda m: Step(
            "park",
            day=int(m.group(1)),
            reason=f"Day {m.group(1)} has no spec: writing it is the maintainer's",
        ),
    ),
    (
        rf"Day {NN} is done: stop and evaluate before going on \(plan\.md\)",
        lambda m: Step(
            "park", day=int(m.group(1)), reason=f"a stopping point after Day {m.group(1)}"
        ),
    ),
    (
        rf"Day {NN}: read the spec against the code, then the spec-change PR",
        lambda m: Step("step", day=int(m.group(1)), prefix=f"day-{m.group(1)}/spec"),
    ),
    (
        rf"Day {NN} Track {TRACK}: announced in #(\d+), no branch names it",
        lambda m: Step(
            "park",
            day=int(m.group(1)),
            track=m.group(2),
            reason=f"Track {m.group(2)} of Day {m.group(1)} was announced in #{m.group(3)} and has no branch",
        ),
    ),
    (
        rf"Day {NN} Track {TRACK}: .*",
        lambda m: Step(
            "step",
            day=int(m.group(1)),
            track=m.group(2),
            prefix=f"day-{m.group(1)}/track-{m.group(2).lower()}",
        ),
    ),
    (
        rf"Day {NN}: the closing PR",
        lambda m: Step("step", day=int(m.group(1)), prefix=f"day-{m.group(1)}/close-the-day"),
    ),
]


def classify(sentence: str) -> Step:
    for pattern, make in RULES:
        m = re.fullmatch(pattern, sentence)
        if m:
            return make(m)
    return Step("park", reason=UNKNOWN)


def phase_end(step: Step, order: list, days: list[dict]) -> str | None:
    """A park reason when the spec step opens a new phase, else None. Only a day's spec step can
    open a phase: a track's step and a close never do."""
    if step.kind != "step" or step.track is not None or not step.prefix.endswith("/spec"):
        return None
    if order and step.day == order[0]:
        return None
    phases = {d["day"]: d.get("phase") for d in days}
    if step.day not in order:
        return f"Day {step.day:02d} or the day before it names no phase"
    before = order[order.index(step.day) - 1]
    phase, before_phase = phases.get(step.day), phases.get(before)
    # Phase 0 is a phase, so test for None, never for a false value.
    if phase is None or before_phase is None:
        return f"Day {step.day:02d} or the day before it names no phase"
    if phase == before_phase:
        return None
    return f"the end of Phase {before_phase}: Day {step.day:02d} starts Phase {phase}"
