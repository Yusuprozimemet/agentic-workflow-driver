"""Every refusal a guard makes, one JSON line each, so the dashboard can count them.

    python scripts/refusal_log.py     # print the counts per date and guard from this machine's log

step-guard.py, read-guard.py and auditor-guard.py call record() each time they refuse (exit 2). The
log is .claude/state/refusals.jsonl in the project, gitignored: it holds local paths and session ids.
token-usage.py, run by scripts/publish-counts.py, writes counts() into refusals.json, which goes to the
dashboard-data branch; the dashboard's graph 8, "What did it cost?", shows it. Only what the counts need goes there:
date, guard and number. A refusal is the rule working, but many of one kind say the rule is read past
or is in the way: the counts are there to tell which.

record() never raises: a guard that fails to log still refuses. GUARD_REFUSAL_LOG names another log
file, so the guards' tests do not write into the repository's own.
"""
import collections
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def log_path(root=None):
    root = root or os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(HERE)
    return os.environ.get("GUARD_REFUSAL_LOG") or os.path.join(root, ".claude", "state", "refusals.jsonl")


def record(guard, data, reason, root=None):
    """Append one refusal to the log; any error is swallowed."""
    try:
        data = data if isinstance(data, dict) else {}
        entry = {"time": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                 "guard": guard, "session": data.get("session_id"),
                 "agent": data.get("agent_type") or "main", "tool": data.get("tool_name"),
                 "reason": (reason or "").splitlines()[0][:300] if reason else ""}
        path = log_path(root)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:  # noqa: BLE001 - logging must never change what the guard decides
        pass


def counts(path=None):
    """[{date, guard, refused}] from the log, by date then guard; [] without a log."""
    found = collections.Counter()
    try:
        with open(path or log_path(), encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    found[(entry["time"][:10], entry["guard"])] += 1
                except (ValueError, KeyError, TypeError):
                    continue  # a line cut short by a crash is skipped, not fatal
    except OSError:
        return []
    return [dict(date=d, guard=g, refused=n) for (d, g), n in sorted(found.items())]


def merge(kept, new):
    """Counts from this machine's log beside those already committed: the larger of each is kept,
    so a close run on another machine, or after the log was deleted, loses nothing."""
    best = {(r["date"], r["guard"]): r["refused"] for r in kept}
    for r in new:
        key = (r["date"], r["guard"])
        best[key] = max(best.get(key, 0), r["refused"])
    return [dict(date=d, guard=g, refused=n) for (d, g), n in sorted(best.items())]


def main():
    rows = counts()
    if not rows:
        print(f"no refusals logged in {log_path()}")
        return 0
    for r in rows:
        print(f"{r['date']}  {r['guard']:<14} {r['refused']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
