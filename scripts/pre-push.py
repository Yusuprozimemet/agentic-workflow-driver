"""Run every pull-request check that has a local command, one line per check; exit 1 on any failure.

    python scripts/pre-push.py [--base main] [--title "Day 13 track A: ..."] [--body pr-body.md] [--skip-tests]

Each line is `ok`, `FAIL` or `skip`, then the check's name as CI shows it, then why for a FAIL or
a skip. A FAIL's whole output is kept in .claude/state/pre-push/ (gitignored) and its path printed.
The checks run from the branch's merge base with --base, on the commit at HEAD: commit first.

Three need what only a pull request has: the title (`--title`, for the names check), the body
(`--body`, for the template and an `Oversized:` line), and Linux for "A track's breaks replay",
which CI replays on the merge commit and this script only names: rehearse it with
`break-lines.py` and `break.py`, as CLAUDE.md says.

Why: of the checks that failed on a first push, "Frozen files stay unedited" had a local command
that "Before pushing" did not name (#212 S23, #213 B12). This list is every check CI runs, so a
check added to CI and not here fails `test_pre_push.py`.

"Tests" does one thing CI does not: the test files the branch changes run 5 times each inside the
whole run (`test-parallel.py --repeat 5 --of`), the suite being the load. Nine of Days 9 to 12's
late defects were a test that fails on and off under load, each met in a later track's full run;
alone, one passed 25 of 25 (D12.34). The scripts' own tests (scripts/test_*.py) are not repeated.
"""

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEPT = os.path.join(ROOT, ".claude", "state", "pre-push")
PY = sys.executable
LIMIT = 400
REPEAT = 5  # under load D12.36 failed 3 of 5 and D12.39 4 of 10
SECTIONS = ("## User story", "## What I built", "## Why this approach", "## Contract impact", "## How to run",
            "## Self-check")
# spec-drift-tests.yml runs the scripts' tests only when the change touches one of these.
DRIFT_PATHS = re.compile(r"^(scripts/[^/]+\.py$|\.claude/agents/.*\.md$|\.claude/settings\.json$|"
                         r"spec-drift\.config\.json$|docs/dashboard/(dashboard\.js|index\.html|dashboard\.css)$|"
                         r"kit/(compare-page\.py|page/.*)$|\.github/workflows/(spec-drift-tests|pr-checks)\.yml$)")
EXCLUDED = (":(exclude)**/uv.lock", ":(exclude)**/package-lock.json", ":(exclude)**/poetry.lock",
            ":(exclude)**/*.lock", ":(exclude)**/target/**", ":(exclude)**/dbt_packages/**",
            ":(exclude)**/node_modules/**")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def changed_lines(base):
    total = 0
    for line in git("diff", "--numstat", f"{base}...HEAD", "--", ".", *EXCLUDED).splitlines():
        added, deleted = line.split("\t")[:2]
        total += sum(int(n) for n in (added, deleted) if n != "-")
    return total


def has(path):
    """CI's hashFiles() conditions: a project with no services/ or no kit/ skips those steps."""
    return os.path.exists(os.path.join(ROOT, path))


def changed_tests(files):
    """The changed files test-parallel.py runs: tests/test*.py itself, still there."""
    return sorted(f[len("tests/"):] for f in files if re.fullmatch(r"tests/test[^/]*\.py", f) and has(f))


def checks(a, base, branch, files):
    """(CI's name, commands to run in order, or a str: why it is skipped or failed without a run)."""
    body = open(a.body, encoding="utf-8").read() if a.body else None
    again = changed_tests(files)
    size = changed_lines(base)
    oversized = body is not None and re.search(r"(?mi)^\s*Oversized:\s*\S", body)
    md = [f for f in files if f.endswith(".md") and os.path.exists(os.path.join(ROOT, f))]
    scripts_tests = sorted(f"scripts/{n}" for n in os.listdir(os.path.join(ROOT, "scripts"))
                           if n.startswith("test_") and n.endswith(".py"))
    return [
        ("Style check", [["ruff", "check", "."], ["ruff", "format", "--check", "."]]),
        ("Tests", "skip: --skip-tests" if a.skip_tests else
         [[PY, "scripts/test-parallel.py"] + (["--repeat", str(REPEAT), "--of", *again] if again else [])]),
        ("Description uses the template",
         "skip: pass --body <file>" if body is None else
         [] if all(s.lower() in body.lower() for s in SECTIONS) else
         "FAIL: missing " + ", ".join(s for s in SECTIONS if s.lower() not in body.lower())),
        ("Diff stays reviewable", [] if size <= LIMIT or oversized else
         f"FAIL: {size} changed lines, over {LIMIT}" + ("" if body else "; with an Oversized: line in "
                                                                       "the body (--body) it is a warning")),
        ("Frozen files stay unedited", [[PY, "scripts/invariants.py", base, "HEAD"]]),
        ("Every service is wired into compose and Prometheus",
         [[PY, "scripts/test_service_wiring.py"]] + ([[PY, "scripts/service-wiring.py"]] if has("services") else [])),
        ('"Replaces: lines name real earlier criteria"',
         [[PY, "scripts/test_behaviour_index.py"], [PY, "scripts/behaviour-index.py"]]),
        ("A changed brief shows its case count", "skip: pass --body <file>" if body is None else
         [[PY, "scripts/test_case_count.py"], [PY, "scripts/case-count.py", base, "HEAD", "--body", a.body]]),
        ('"Plan links quote the plan\'s words"', [[PY, "scripts/test_plan_links.py"], [PY, "scripts/plan-links.py"]]),
        ("Branch, title, commits and Jira keys agree",
         "skip: pass --title" if not a.title else [[PY, "scripts/pr-names.py", base, "HEAD"]]),
        ("Track tests seen red", [[PY, "scripts/track-red.py", "--branch", branch, "--runner", "unittest",
                                   "--base", base]]),
        ("Criteria keep their wording", [[PY, "scripts/criteria-wording.py", "--branch", branch, "--base", base,
                                          "--head", "HEAD"]]),
        ("Drift and gap move when they should", [[PY, t] for t in scripts_tests]
         if any(DRIFT_PATHS.match(f) for f in files) else []),
        ("Token counts on Windows", "skip: in the line above" if any(DRIFT_PATHS.match(f) for f in files) else []),
        ("The starter names no project", [[PY, "kit/starter-check.py"]] if has("kit/starter-check.py") else []),
        ("A closed day's evidence replays", [[PY, "scripts/close-evidence.py", "--rehearse", branch, "--base", base,
                                              "--head", "HEAD"]]),
        ("A track's breaks replay", "skip: needs Linux, CI replays it on the merge commit; rehearse with "
                                    "break-lines.py and break.py"),
        ("Links in the Markdown touched", [[PY, "scripts/check-links.py", f] for f in md]),
    ]


def run(commands, env):
    """(exit status, the output of the commands, run until one fails)."""
    out = []
    for command in commands:
        proc = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        out.append(f"$ {' '.join(command)}\n{proc.stdout}{proc.stderr}")
        if proc.returncode:
            return proc.returncode, "\n".join(out)
    return 0, "\n".join(out)


def last_line(output):
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else "no output"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="main")
    ap.add_argument("--title", help="the PR title, for the names check")
    ap.add_argument("--body", help="a file with the PR body, for the template and the size checks")
    ap.add_argument("--skip-tests", action="store_true", help="leave the whole tests/ run out")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    branch = git("branch", "--show-current")
    base = git("merge-base", a.base, "HEAD")
    if not base:
        print(f"pre-push.py: no merge base with {a.base}", file=sys.stderr)
        return 2
    files = git("diff", "--name-only", f"{base}...HEAD").splitlines()
    env = dict(os.environ, PR_BRANCH=branch, PR_TITLE=a.title or "", PYTHONDONTWRITEBYTECODE="1")
    if a.body:
        env["PR_BODY"] = open(a.body, encoding="utf-8").read()
    failed = 0
    for name, what in checks(a, base, branch, files):
        if isinstance(what, str):
            state, why = what.split(": ", 1)
            failed += state == "FAIL"
            print(f"{state:<4} {name}: {why}")
            continue
        code, output = run(what, env)
        if not code:
            again = changed_tests(files) if name == "Tests" else []
            print(f"ok   {name}" + ("" if what else ": nothing to run")
                  + (f": {', '.join(again)} run {REPEAT} times in it" if again else ""))
            continue
        failed += 1
        os.makedirs(KEPT, exist_ok=True)
        path = os.path.join(KEPT, re.sub(r"\W+", "-", name).strip("-").lower() + ".txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"FAIL {name}: {last_line(output)} (kept: {os.path.relpath(path, ROOT)})")
    print(f"pre-push: {failed} check(s) failed" if failed else "pre-push: every local check passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
