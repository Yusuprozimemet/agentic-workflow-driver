"""After the maintainer says "merged", the session finishes step 5 and stops: new work waits for a new session.

    python scripts/step-guard.py prompt    # UserPromptSubmit: on "merged", set the marker, remind the turn
    python scripts/step-guard.py pre       # PreToolUse: exit 2 with the reason for new work while it is set
    python scripts/step-guard.py start     # SessionStart: a new session, /clear or /compact clears it

CLAUDE.md's step 5 says that after every "merged" the session checks the evidence, reports the
next step, suggests a new session, and stops. In bearing it was read past twice on Day 01: after #7's
"merged" the session went on into the close (D01.23), and after #8's it launched the end-of-phase
plan-auditors in the same context (D01.24). A rule the model can skip was skipped; this one it
cannot. Built in bearing's #9 and copied here.

"merged" is a short prompt (six words at most) holding the word, with no question mark and no
"not": "merged", "Merged #8.", "#8 merged". A longer message that mentions a merge is not one. On
it, the marker `.claude/state/step-guard.json` records the session's id, and the turn is told the
rule. While the marker names this session, these are refused:

- every subagent (Agent, Task): an auditor or implementer starts the next step;
- an Edit, Write or NotebookEdit of a file inside the repository (the scratchpad stays open);
- in Bash or PowerShell: creating a branch, `git commit`, `git push`, `git merge`, `git rebase`,
  `git cherry-pick`, `git stash`, `gh pr create|merge|edit|comment|review|close|ready` and
  `gh issue create`.

Step 5 itself still runs: `git pull`, `git switch main`, `gh run list|view|download`,
`scripts/evidence.py` and `scripts/spec-drift.py`. SessionStart clears the marker on a new session,
`/clear` or `/compact` (not on resume, which is the same context); a new session has another id,
so a marker it never cleared does not apply to it either.

The settings' command finds this script through CLAUDE_PROJECT_DIR, read in Python, and exits 0
without it (see auditor-guard.py).
"""
import json
import os
import re
import sys

try:
    from refusal_log import record
except ImportError:  # a copy of this script without refusal_log.py still refuses, unlogged
    def record(*args, **kwargs):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.path.dirname(HERE)
MARKER = os.path.join(ROOT, ".claude", "state", "step-guard.json")

REMINDER = (
    'step-guard: the maintainer said "merged". Do step 5 only: for a closing PR, check its '
    "evidence run (gh run list --workflow evidence.yml --commit <sha>, gh run view <id> "
    "--exit-status); on fresh main run python scripts/spec-drift.py and report the next step it "
    "prints. Then tell the maintainer to start a new session (or /compact) for that next step, "
    "with a one-line prompt to start it, and stop. Step 6 (the end-of-phase audit) is a next "
    "step too. Subagents, edits in the repository, branches, commits, pushes and PRs are "
    "refused in this session until then."
)

COMMAND_TOOLS = ("Bash", "PowerShell")
EDIT_TOOLS = ("Edit", "Write", "NotebookEdit", "MultiEdit")
AGENT_TOOLS = ("Agent", "Task")

NEW_WORK = re.compile(
    r"\bgit\s+(?:-c\s+\S+\s+)*(?:"
    r"(?:switch|checkout)\s+(?:.*\s)?-[cCbB]\b|branch\s+(?!-(?:-list|-show-current|a|r|v|vv)\b)[\w./-]+"
    r"|commit\b|push\b|merge\b|rebase\b|cherry-pick\b|stash\b)"
    r"|\bgh\s+pr\s+(?:create|merge|edit|comment|review|close|ready)\b"
    r"|\bgh\s+issue\s+create\b"
)


def is_merged(prompt):
    """True when the prompt is the maintainer's short "merged", not a message about a merge."""
    text = (prompt or "").strip().lower()
    words = re.findall(r"[\w#]+", text)
    return (0 < len(words) <= 6 and "merged" in words and "?" not in text
            and not {"not", "isn't", "unmerged"} & set(words))


def marked(session_id, path=MARKER):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("session_id") == session_id
    except (OSError, ValueError, AttributeError):
        return False


def inside(path, root=ROOT):
    try:
        full = os.path.normcase(os.path.realpath(path))
        base = os.path.normcase(os.path.realpath(root))
        return os.path.commonpath([full, base]) == base
    except ValueError:
        return False


def refusal(data, path=MARKER, root=ROOT):
    """The reason to refuse this tool call, or None to let it run."""
    if not marked(data.get("session_id"), path):
        return None
    tool = data.get("tool_name")
    args = data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {}
    what = None
    if tool in AGENT_TOOLS:
        what = f"a subagent ({args.get('subagent_type') or 'general-purpose'})"
    elif tool in EDIT_TOOLS:
        target = args.get("file_path") or args.get("notebook_path") or ""
        if target and inside(target, root):
            what = f"an edit of {target}"
    elif tool in COMMAND_TOOLS:
        found = NEW_WORK.search(args.get("command") or "")
        if found:
            what = f"`{found.group(0).strip()}`"
    if what is None:
        return None
    return (f'step-guard: refused {what}. The maintainer said "merged" in this session, so new '
            "work waits for a new session. Finish step 5 (evidence check, spec-drift.py, report "
            "the next step), tell the maintainer to start a new session (or /compact) with a "
            "one-line prompt for the next step, and stop.")


def set_marker(session_id, path=MARKER):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"session_id": session_id}, f)


def clear_marker(path=MARKER):
    try:
        os.remove(path)
    except OSError:
        pass


def main(argv):
    mode = argv[1] if len(argv) > 1 else ""
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(data, dict):
        return 0
    if mode == "prompt":
        if is_merged(data.get("prompt")):
            set_marker(data.get("session_id"))
            print(REMINDER)
        return 0
    if mode == "start":
        if data.get("source") != "resume":
            clear_marker()
        return 0
    if mode == "pre":
        reason = refusal(data)
        if reason:
            record("step-guard", data, reason, ROOT)
            print(reason, file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
