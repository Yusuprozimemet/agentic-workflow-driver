"""The driver checks its own repository before and after a step (plan.md, "What the separate folder
protects"): changes left behind, or a HEAD that moved, park the driver. The close files are left
out because a close leaves them untracked (H03.8 is the kit's fix). Plain stdlib."""

import subprocess

CLOSE_FILES = ("evidence-rehearsal.json", "evidence.json")


def check(home, started=None):
    # Returns (head, reason): HEAD now, and why the driver must park, or None.
    status = git(home, "status", "--porcelain")
    rev = git(home, "rev-parse", "HEAD")
    if status is None or rev is None:
        return None, f"the driver's folder `{home}` is not a git repository"
    head = rev.strip()
    changes = []
    for line in status.splitlines():
        if not line:
            continue
        # Porcelain paths are relative to the repository root, so only a root file matches.
        if line[:2] == "??" and line[3:] in CLOSE_FILES:
            continue
        changes.append(line[3:])
    if changes:
        named = ", ".join(f"`{p}`" for p in changes)
        return head, f"the driver's repository has changes: {named}"
    # Changes are named first: a step that both moved HEAD and left files is reported as the files.
    if started is not None and head != started:
        return head, f"the driver's repository moved from `{started[:7]}` to `{head[:7]}`"
    return head, None


def git(home, *args):
    # None when git cannot be run or exits non-zero; the caller reads that as not a repository.
    try:
        result = subprocess.run(["git", *args], cwd=home, capture_output=True, check=False)
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace")
