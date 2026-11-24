"""Does a pull request that edits a brief with known cases show the cases' count on that brief?

    python scripts/case-count.py BASE HEAD --body <file with the PR body>

A brief has cases when specs/agent-cases/<agent>.json names it (`"brief"`, by default
.claude/agents/<agent>.md). When the diff BASE...HEAD changes such a brief, the body must hold
the first line `scripts/agent-cases.py <agent>` printed for the brief as HEAD has it,
"<agent>: ... brief <its 7-character blob hash>", and a count line after it ("... at worst
(...)"). CI cannot start an agent, so it checks that the count was run on this brief and pasted,
not what it said: a fall stays the maintainer's to accept (`--record`). Before this check the
count was a line in CLAUDE.md's table that nothing enforced. Exit 1 names each brief without it.

The same pull request must leave that agent's cases as they were: its cases file may change only
in `recorded` (a count kept with --record), and nothing under specs/agent-cases/<agent>/ may
change. A brief's proposer never edits its cases, or the count could be raised by writing the
cases to fit the brief. A first case set, where the base has no cases file, is not an edit.
"""

import argparse
import json
import re
import subprocess
import sys


def git(*args):
    done = subprocess.run(["git", *args], capture_output=True, check=True)
    return done.stdout.decode("utf-8")


def briefs(head):
    """{brief path: agent} for every cases file at `head`."""
    out = {}
    for path in git("ls-tree", "--name-only", f"{head}:specs/agent-cases").split():
        if path.endswith(".json"):
            data = json.loads(git("show", f"{head}:specs/agent-cases/{path}"))
            agent = data.get("agent", path[: -len(".json")])
            out[data.get("brief", f".claude/agents/{agent}.md")] = agent
    return out


def missing(changed, cased, hashes, body):
    """The messages for each changed brief whose count is not in the body."""
    msgs = []
    for path in sorted(set(changed) & set(cased)):
        agent, h = cased[path], hashes[path]
        header = re.search(rf"(?m)^{re.escape(agent)}: .*\bbrief {h}\s*$", body)
        if not header or not re.search(
            r"(?m)^\w+: \d+ of \d+ .* at worst \(", body[header.end() :]
        ):
            msgs.append(
                f"{path} changed: paste what `python scripts/agent-cases.py {agent}` prints on it"
                f" (its first line ends 'brief {h}')"
            )
    return msgs


def unrecorded(data):
    return {k: v for k, v in data.items() if k != "recorded"}


def cases_moved(changed, cased, sets):
    """The messages for each changed brief whose cases changed beside it. `sets` maps an agent to
    its cases file (before, after), each parsed or None. Only `recorded` may change: a count taken
    on the new brief. A first case set (before None) is not an edit of known cases."""
    msgs = []
    for path in sorted(set(changed) & set(cased)):
        agent = cased[path]
        before, after = sets.get(agent, (None, None))
        moved = []
        if before is not None and unrecorded(before) != unrecorded(after or {}):
            moved.append(f"specs/agent-cases/{agent}.json")
        moved += [p for p in changed if p.startswith(f"specs/agent-cases/{agent}/")]
        if moved:
            msgs.append(
                f"{', '.join(moved)}: its cases changed in the PR that edits {path}: a brief's"
                " proposer never edits its cases, so move the case change to its own PR"
            )
    return msgs


def case_set(ref, agent):
    try:
        return json.loads(git("show", f"{ref}:specs/agent-cases/{agent}.json"))
    except subprocess.CalledProcessError:
        return None


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("base")
    ap.add_argument("head")
    ap.add_argument("--body", required=True)
    a = ap.parse_args(argv)
    with open(a.body, encoding="utf-8") as f:
        body = f.read().replace("\r\n", "\n")
    try:
        cased = briefs(a.head)
    except subprocess.CalledProcessError:
        cased = {}
    changed = git("diff", "--name-only", f"{a.base}...{a.head}").split()
    there = [p for p in changed if p in cased]
    hashes = {p: git("rev-parse", f"{a.head}:{p}").strip()[:7] for p in there}
    msgs = missing(there, cased, hashes, body)
    base = git("merge-base", a.base, a.head).strip()
    sets = {cased[p]: (case_set(base, cased[p]), case_set(a.head, cased[p])) for p in there}
    msgs += cases_moved(changed, cased, sets)
    for m in msgs:
        print(m)
    if not msgs:
        print(f"ok: {len(there)} changed brief(s) with cases, each count shown, cases unedited")
    return 1 if msgs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
