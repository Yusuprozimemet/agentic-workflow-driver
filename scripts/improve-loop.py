"""A proposed brief for one agent with known cases, measured before it reaches a pull request.

    python scripts/improve-loop.py defect-rater            # 3 runs per count
    python scripts/improve-loop.py reviewer --runs 1

The brief-improver agent (.claude/agents/brief-improver.md) reads the agent's brief, its cases and
the misses of its last count, and returns a draft and up to 3 passages it would delete. It never
measures its draft: this script does, with scripts/agent-cases.py. "Before" is the recorded count
when it was recorded on today's brief, else a count of today's brief; "after" is the draft's
count; each deletion is the draft with that passage removed, counted alone, and is proposed only
when no axis falls below the draft's. Deletions are not counted together.

Everything goes to .claude/state/improve-loop/<agent>/: draft.md, proposed.md (the draft less the
proposed deletions), report.md (counts, deletions, the diff) and each count's replies. Nothing in
the repository changes and nothing is recorded: the maintainer reads report.md, and an approved
draft goes in a `tooling/brief-<agent>` pull request, whose count is run and recorded there.
Exit 1 when the draft cannot be read from the reply or a count reads no run. Costs: up to 5
counts of every case, each `--runs` times.
"""

import argparse
import difflib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("agent_cases", os.path.join(HERE, "agent-cases.py"))
cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cases)

DRAFT = re.compile(r"^DRAFT\n(.*?\n)END DRAFT$", re.M | re.S)
PROMPT = (
    "Draft a better brief for the {agent}. Its brief is {brief}; its known cases are in {file}"
    "{folder}. {misses}\nReply as your brief says; change nothing.\n"
)


def parse(reply):
    """(draft, deletions) from the brief-improver's reply; draft None when there is none."""
    reply = reply.replace("\r\n", "\n")
    m = DRAFT.search(reply)
    if not m:
        return None, []
    rest = reply[reply.find("DELETIONS:", m.end()) :]
    try:
        got = json.loads(rest[rest.find("[") : rest.rfind("]") + 1])
    except ValueError:
        got = []
    ok = [d for d in got if isinstance(d, dict) and isinstance(d.get("passage"), str)]
    return m.group(1), ok[:3]


def fell(worst, than):
    return [f"{a} {worst[a]} < {than[a]}" for a in than if a != "runs" and worst[a] < than[a]]


def main(argv, repo=ROOT, drafter=None, runner=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("agent")
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args(argv)
    agent, runs = args.agent, args.runs
    with open(os.path.join(repo, "specs", "agent-cases", agent + ".json"), encoding="utf-8") as f:
        data = json.load(f)
    brief = os.path.join(repo, data.get("brief", f".claude/agents/{agent}.md"))
    out = os.path.join(repo, ".claude", "state", "improve-loop", agent)
    if os.path.isdir(out):
        shutil.rmtree(out, onerror=cases._writable)
    os.makedirs(out)
    sha = cases.git(repo, "hash-object", brief).strip()[:7]
    recorded = data.get("recorded") or {}
    last = os.path.join(repo, ".claude", "state", "agent-cases", agent, "count.txt")
    if recorded.get("brief") == sha:
        was = ", ".join(f"{a} {v}" for a, v in recorded.items() if a not in ("brief", "runs"))
        before = [f"recorded on today's brief {sha}: {was} ({recorded.get('runs')} runs)"]
        try:
            with open(last, encoding="utf-8") as f:
                last = last if f.readline().strip().endswith(sha) else None
        except OSError:
            last = None
    else:
        head, lines, worst = cases.count(
            agent, runs, None, os.path.join(out, "before"), repo, runner
        )
        if worst is None:
            print("\n".join([head, *lines]))
            return 1
        before, last = [head, *lines], os.path.join(out, "before", "count.txt")
    misses = (
        f"The last count of this brief is {last}."
        if last
        else "No count of this brief was kept: work from the cases' known answers."
    )
    folder = os.path.join(repo, "specs", "agent-cases", agent)
    prompt = PROMPT.format(
        agent=agent,
        brief=brief,
        file=folder + ".json",
        folder=f" and {folder}/" if os.path.isdir(folder) else "",
        misses=misses,
    )
    drafter = drafter or ["claude", "-p", "--agent", "brief-improver"]
    reply = subprocess.run(
        [shutil.which(drafter[0]) or drafter[0], *drafter[1:]],
        input=prompt.encode("utf-8"),
        capture_output=True,
        cwd=repo,
        timeout=1800,
        check=False,
    ).stdout.decode("utf-8", "replace")
    with open(os.path.join(out, "reply.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(reply)
    draft, deletions = parse(reply)
    if draft is None:
        print(f"no draft between DRAFT and END DRAFT in {os.path.join(out, 'reply.txt')}")
        return 1

    def measure(name, text):
        path = os.path.join(out, name + ".md")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return cases.count(agent, runs, path, os.path.join(out, name), repo, runner)

    head, lines, after = measure("draft", draft)
    if after is None:
        print("\n".join([head, *lines]))
        return 1
    report = ["# Improve loop: " + agent, "", "## Before", "", *before, "", "## After, the draft"]
    report += ["", head, *lines, "", "## Deletions", ""]
    proposed = draft
    for n, d in enumerate(deletions, 1):
        where = f"{n}. {d['passage'].strip().splitlines()[0][:80]!r} ({d.get('why', '')})"
        if draft.count(d["passage"]) != 1:
            report.append(f"{where}: not counted, not exactly once in the draft")
            continue
        _, _, worst = measure(f"deletion-{n}", draft.replace(d["passage"], "", 1))
        lower = ["no run counted"] if worst is None else fell(worst, after)
        report.append(f"{where}: " + ("not proposed, " + ", ".join(lower) if lower else "proposed"))
        if not lower:
            proposed = proposed.replace(d["passage"], "", 1)
    if not deletions:
        report.append("none named")
    with open(os.path.join(out, "proposed.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(proposed)
    with open(brief, encoding="utf-8") as f:
        diff = difflib.unified_diff(
            f.read().splitlines(), proposed.splitlines(), "brief", "proposed", lineterm=""
        )
    report += ["", "## Diff, the brief to proposed.md", "", "```diff", *diff, "```", ""]
    with open(os.path.join(out, "report.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(report))
    print("\n".join([*before, head, *lines]))
    print(f"report: {os.path.join(out, 'report.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
