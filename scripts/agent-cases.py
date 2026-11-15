"""Does an agent still answer its known cases as it did before its brief was edited?

    python scripts/agent-cases.py defect-rater              # 3 runs, compared with the recorded count
    python scripts/agent-cases.py defect-rater --record     # and keep this count as the recorded one

Nothing else runs an agent on a case whose answer is known: the tests read a brief's shape, and an
edit that makes the agent miss what it caught shows up as a defect on a later Day, or never. The
cases are in specs/agent-cases/<agent>.json: closed Days' specs, each pinned at a commit, so a
later edit to their Notes changes nothing here. For the defect-rater the known answer is the
tags those Days closed with, every disagreement decided; scripts/relabel.py hides them and counts.

An agent's answer differs from run to run, so this is a measurement, not a gate: it prints the
worst of its runs beside the recorded count and exits 0. Exit 1 means no run could be counted.
Each run is its own `claude -p --agent <agent>` session, which reads the brief as it is on disk:
an edited brief is measured before the session that edited it could use it. The recorded count
was partly shaped by the rater (a close may take its label), so read a fall, not the level.
"""

import argparse
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("relabel", os.path.join(HERE, "relabel.py"))
relabel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relabel)

AXES = ("stage", "cause", "made")
COUNT = re.compile(r"^(stage|cause|made): (\d+) of (\d+) agree")


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo, *args], capture_output=True, check=True
    ).stdout.decode("utf-8")


def prepare(repo, cases, out):
    """blind.md and key.json in `out`, from each case's spec as it stood at its commit."""
    os.makedirs(out, exist_ok=True)
    paths = []
    for case in cases:
        path = os.path.join(out, os.path.basename(case["spec"]))
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(git(repo, "show", f"{case['at']}:{case['spec']}"))
        paths.append(path)
    return relabel.blind(paths, out)


def labels(reply):
    """The JSON array in the agent's reply, fenced or not; None when there is none."""
    try:
        got = json.loads(reply[reply.find("[") : reply.rfind("]") + 1])
    except ValueError:
        return None
    return (
        got
        if isinstance(got, list) and all(isinstance(r, dict) and "id" in r for r in got)
        else None
    )


def report(key, replies, recorded):
    """The lines to print, and the worst count per axis (None when no run could be counted)."""
    lines, runs = [], []
    for n, reply in enumerate(replies, 1):
        got = labels(reply)
        try:
            if got is None:
                raise SystemExit("no JSON array in the reply")
            found = [COUNT.match(line) for line in relabel.compare(key, got)]
            runs.append({m.group(1): (int(m.group(2)), int(m.group(3))) for m in found if m})
        except SystemExit as e:
            lines.append(f"run {n}: not counted ({e})")
    if not runs:
        return lines + ["no run counted"], None
    worst = {a: min(r[a][0] for r in runs) for a in AXES}
    for a in AXES:
        each = ", ".join(str(r[a][0]) for r in runs)
        lines.append(f"{a}: {worst[a]} of {runs[0][a][1]} agree at worst ({each})")
    if recorded:
        was = ", ".join(f"{a} {recorded[a]}" for a in AXES)
        lines.append(
            f"recorded: {was} (brief {recorded.get('brief', '?')}, {recorded.get('runs', '?')} runs)"
        )
        lower = [f"{a} {worst[a]} < {recorded[a]}" for a in AXES if worst[a] < recorded[a]]
        lines.append(
            "lower than recorded: " + ", ".join(lower) if lower else "not lower than recorded"
        )
    return lines, dict(worst, runs=len(runs))


def ask(runner, prompt, repo):
    cmd = [shutil.which(runner[0]) or runner[0], *runner[1:]]
    done = subprocess.run(
        cmd, input=prompt.encode("utf-8"), capture_output=True, cwd=repo, timeout=1800, check=False
    )
    return done.stdout.decode("utf-8", "replace")


def main(argv, repo=ROOT, runner=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("agent")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--record", action="store_true", help="keep this count as the recorded one")
    ap.add_argument(
        "--runner",
        help="the command that takes the prompt on stdin (default: claude -p --agent <agent>)",
    )
    args = ap.parse_args(argv)
    cases_file = os.path.join(repo, "specs", "agent-cases", args.agent + ".json")
    with open(cases_file, encoding="utf-8") as f:
        data = json.load(f)
    out = os.path.join(repo, ".claude", "state", "agent-cases", args.agent)
    key = prepare(repo, data["cases"], out)
    blind = os.path.join(out, "blind.md").replace("\\", "/")
    with open(blind, encoding="utf-8") as f:
        n = len(f.read().splitlines())
    prompt = f"Label the entries in {blind}. It has {n} lines: read it with limit {n}."
    runner = runner or (
        shlex.split(args.runner) if args.runner else ["claude", "-p", "--agent", args.agent]
    )
    brief = git(repo, "hash-object", f".claude/agents/{args.agent}.md").strip()[:7]
    print(
        f"{args.agent}: {len(key)} entries from {len(data['cases'])} specs, {args.runs} runs, brief {brief}"
    )
    with ThreadPoolExecutor(args.runs) as pool:
        replies = list(pool.map(lambda _: ask(runner, prompt, repo), range(args.runs)))
    lines, worst = report(key, replies, data.get("recorded"))
    print("\n".join(lines))
    if worst is None:
        return 1
    if args.record:
        data["recorded"] = dict(worst, brief=brief)
        with open(cases_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(data, indent=1) + "\n")
        print(f"recorded in specs/agent-cases/{args.agent}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
