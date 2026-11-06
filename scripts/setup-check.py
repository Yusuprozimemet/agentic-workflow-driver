"""Is a copied kit set up? One line per item, from GitHub's settings and the files.

    python scripts/setup-check.py [--repo owner/name]    # default: the repository gh sees here
    python scripts/setup-check.py --kit                  # the kit itself: its placeholders stay

The items are the README's "Starting a project from it": on `main`, a pull request before merging
and each check in REQUIRED required by name (classic branch protection or a ruleset, either
counts), and one more required check, the project's own tests; the repository variable
TRACK_RED_RUNNER set to a runner track-red.py knows, or a command holding `{test}`; GitHub Pages built by GitHub Actions; and no
`<!-- PROJECT` placeholder left in a tracked Markdown file outside kit/ (in backticks, a placeholder
is named, not left). The `PROJECT:` comments in code are notes that stay, and are not counted.
The kit's own repository keeps every placeholder on purpose, for the copy to fill: `--kit` reads
the other items as for a copy and reports the placeholders as kept, one `ok` line, so that the
kit's exit code says what its settings lack, not that it is a kit.

Each line starts `ok` or `FAIL`. A setting gh cannot read (not logged in, no admin rights: the
branch protection and variable reads need them) is a FAIL that says so: a check that could not
look is not a pass. Exits 1 if any line failed. It reads only: it never changes a setting.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The kit's checks a copy requires on `main`, by job name (README, "On GitHub").
REQUIRED = (
    "Description uses the template",
    "Diff stays reviewable",
    "Branch, title, commits and Jira keys agree",
    "Frozen files stay unedited",
    "Dashboard metric tests gate",
    "Criteria keep their wording",
    "A closed day's evidence replays",
    "Track tests seen red",
)
# Kit checks that are not required, so not the project's tests either.
OPTIONAL = ("Every service is wired into compose and Prometheus",)
RUNNERS = ("unittest", "pytest", "maven", "npm")  # track-red.py's RUNNERS
TEMPLATE = "{test}"  # track-red.py's TEMPLATE: a value holding it is the project's own command
SUPPORTED = f"{', '.join(RUNNERS)}, or a command holding {TEMPLATE}"
PLACEHOLDER = "<!-- PROJECT"
CODE_SPAN = re.compile(r"`[^`]*`")
HTTP_STATUS = re.compile(r"\(HTTP (\d{3})\)")


def gh_api(path):
    """(status, parsed body) of `gh api <path>`; status 0 when gh could not be run."""
    try:
        run = subprocess.run(["gh", "api", path], capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        return 0, "gh is not installed"
    if run.returncode == 0:
        return 200, json.loads(run.stdout or "null")
    status = HTTP_STATUS.search(run.stderr)
    return (int(status.group(1)) if status else 0), run.stderr.strip().splitlines()[-1:] or ["no output"]


def unreadable(what, status, body):
    reason = {401: "gh is not logged in", 403: "no permission (needs admin)"}.get(status)
    if reason is None:
        reason = f"HTTP {status}" if status else (body if isinstance(body, str) else " ".join(body))
    return [("FAIL", f"{what}: cannot read: {reason}")]


def protection_lines(repo, gh):
    """Pull request before merging and the required checks on `main`, from both kinds of rule."""
    what = "branch protection on main"
    status, classic = gh(f"repos/{repo}/branches/main/protection")
    if status == 404:  # "Branch not protected": rulesets may still protect it
        classic = {}
    elif status != 200:
        return unreadable(what, status, classic)
    status, rules = gh(f"repos/{repo}/rules/branches/main")
    if status != 200:
        return unreadable(what + " (rulesets)", status, rules)
    checks = (classic.get("required_status_checks") or {})
    required = set(checks.get("contexts") or []) | {c["context"] for c in checks.get("checks") or []}
    pull_request = "required_pull_request_reviews" in classic
    for rule in rules or []:
        if rule.get("type") == "pull_request":
            pull_request = True
        if rule.get("type") == "required_status_checks":
            required |= {c["context"] for c in rule["parameters"]["required_status_checks"]}
    lines = [("ok" if pull_request else "FAIL", "main: a pull request before merging"
              + ("" if pull_request else ": not required"))]
    for name in REQUIRED:
        lines.append(("ok", f'main requires "{name}"') if name in required
                     else ("FAIL", f'main requires "{name}": not required'))
    others = sorted(required - set(REQUIRED) - set(OPTIONAL))
    lines.append(("ok", "main requires the project's tests: " + ", ".join(f'"{o}"' for o in others)) if others
                 else ("FAIL", "main requires the project's tests: no required check beyond the kit's"))
    return lines


def runner_line(repo, gh):
    what = "TRACK_RED_RUNNER"
    status, body = gh(f"repos/{repo}/actions/variables/{what}")
    if status == 404:  # an organization variable shared with the repository counts too
        status, shared = gh(f"repos/{repo}/actions/organization-variables")
        found = [v for v in (shared or {}).get("variables", []) if v["name"] == what] if status == 200 else []
        if not found:
            return [("FAIL", f"{what}: not set; set it to one of {SUPPORTED}")]
        body, status = found[0], 200
    if status != 200:
        return unreadable(what, status, body)
    value = body.get("value", "")
    if value not in RUNNERS and TEMPLATE not in value:
        return [("FAIL", f"{what}: `{value}` is not one of {SUPPORTED}")]
    return [("ok", f"{what}: `{value}`")]


def pages_line(repo, gh):
    status, body = gh(f"repos/{repo}/pages")
    if status == 404:
        return [("FAIL", 'GitHub Pages: not enabled; enable it with source "GitHub Actions"')]
    if status != 200:
        return unreadable("GitHub Pages", status, body)
    if body.get("build_type") != "workflow":
        return [("FAIL", f'GitHub Pages: built from a branch ({body.get("build_type")}); set source "GitHub Actions"')]
    return [("ok", f"GitHub Pages: built by GitHub Actions, {body.get('html_url')}")]


def tracked_markdown(root=ROOT):
    out = subprocess.run(["git", "ls-files", "-z", "--", "*.md"], cwd=root, capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p and not p.startswith("kit/")]


def placeholder_lines(root=ROOT, files=None, kit=False):
    """One FAIL per file with a placeholder left, naming its lines; one ok when none is. With kit,
    one ok that counts the files keeping theirs."""
    lines = []
    for name in files if files is not None else tracked_markdown(root):
        text = (Path(root) / name).read_text(encoding="utf-8", errors="replace")
        hits = [n for n, line in enumerate(text.splitlines(), 1) if PLACEHOLDER in CODE_SPAN.sub("", line)]
        if hits:
            lines.append(("FAIL", f"{PLACEHOLDER} left in {name}, line{'s' if len(hits) > 1 else ''} "
                          + ", ".join(map(str, hits))))
    if kit:
        return [("ok", f"--kit: {len(lines)} Markdown files keep their {PLACEHOLDER} placeholders, as the kit's should")]
    return lines or [("ok", f"no {PLACEHOLDER} placeholder left in the Markdown files")]


def report(repo, gh=gh_api, root=ROOT, files=None, kit=False):
    return (protection_lines(repo, gh) + runner_line(repo, gh) + pages_line(repo, gh)
            + placeholder_lines(root, files, kit))


def current_repo():
    run = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                         cwd=ROOT, capture_output=True, text=True)
    return run.stdout.strip() if run.returncode == 0 else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", help="owner/name; default: the repository gh sees here")
    parser.add_argument("--kit", action="store_true", help="the kit itself: its placeholders stay")
    args = parser.parse_args(argv)
    repo = args.repo or current_repo()
    if not repo:
        print("setup-check.py: no repository: pass --repo owner/name, or log gh in", file=sys.stderr)
        return 2
    lines = report(repo, gh_api, kit=args.kit)
    for state, text in lines:
        print(f"{state:<4} {text}")
    failed = sum(state == "FAIL" for state, _ in lines)
    print(f"{failed} of {len(lines)} items need setup" if failed else f"all {len(lines)} items set up")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
