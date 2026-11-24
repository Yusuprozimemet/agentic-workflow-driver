"""Does an agent still answer its known cases as it did before its brief was edited?

    python scripts/agent-cases.py defect-rater              # 3 runs, compared with the recorded count
    python scripts/agent-cases.py defect-rater --record     # and keep this count as the recorded one
    python scripts/agent-cases.py reviewer                  # the driver's reviewer, rules/reviewer.md

Nothing else runs an agent on a case whose answer is known: the tests read a brief's shape, and an
edit that makes the agent miss what it caught shows up as a defect on a later Day, or never. The
cases are in specs/agent-cases/<agent>.json, each pinned at a commit, so a later edit changes
nothing here. For the defect-rater a case is a closed Day's spec, and the known answer the tags
it closed with, every disagreement decided; scripts/relabel.py hides them and counts. For the
reviewer (`"kind": "review"`) a case is a merged pull request, checked out at its head commit,
and the known answer its verdict: `blocker` for a fault found only after it merged, with a
pattern a blocker line naming that fault matches, or `none` for one nothing was found in later.
For the track-reviewer (`"kind": "track"`) a case is a brief's first draft, kept in
specs/agent-cases/track-reviewer/ (briefs are never committed) and read against `main` as it stood
when it was written, or a merged track's diff and body; the known answer each fault found after
it, with a pattern a line under "Findings" naming it matches (`"escape": true` where nobody caught
it on that draft and it was tagged by hand), or none for a clean case.
For the spec-auditor (`"kind": "audit"`) a case is a Day's spec as the auditor first read it, or
as a recheck read the fixes, checked out at that commit with `main` at its base, given the prompt
the main session gave it then; `"beside"` puts another repository the spec reads as `../<name>`
at its commit of that time. The known answer each fault taken from that report, or found later in
text it read (`"escape": true`); a clean case is one whose report held no "must fix" or "should
fix", and "note" lines leave it clean.

An agent's answer differs from run to run, so this is a measurement, not a gate: it prints the
worst of its runs beside the recorded count and exits 0. A reply it cannot read counts as 0, as
the driver parks on a verdict it cannot read; left out, two unreadable runs of three scored as
well as three good ones. Exit 1 means no reply could be read at all. Each run is its own `claude
-p` session, which reads the brief as it is on disk: an edited brief is measured before the
session that edited it could use it. The defect-rater's recorded count was partly shaped by the
rater (a close may take its label), so read a fall, not the level. A pull request that edits a
brief with cases shows this count on its body (scripts/case-count.py, CI).
"""

import argparse
import importlib.util
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("relabel", os.path.join(HERE, "relabel.py"))
relabel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relabel)
sys.path.insert(0, ROOT)
from driver import review  # noqa: E402  the verdict the driver reads, and its reviewer's agent
from driver import settings as driver_settings  # noqa: E402

AXES = ("stage", "cause", "made")
REVIEW_AXES = ("verdict", "named")
TRACK_AXES = ("named", "clean")
WORDS = {"named": "name the known fault", "clean": "say none on a clean case"}
COUNT = re.compile(r"^(stage|cause|made): (\d+) of (\d+) agree")
PROMPT = (
    "Review pull request #{pr} at commit {at}.\n"
    "Read it as your brief says, change nothing, and end with the REVIEW line.\n"
)
TRACK_PROMPTS = {
    "brief": (
        "brief — Day {day} Track {track} ({spec}). The brief is at {file}. This directory is the"
        " repository, `main` at {at}, as it stood when the brief was written.\n"
        "Report as your brief says; change nothing.\n"
    ),
    "diff": (
        "diff — Day {day} Track {track} ({spec}), pull request #{pr}. This directory is the"
        " repository: the track's commits are HEAD ({at}) on `main` ({base}), read with"
        " `git diff main...HEAD`. The PR body's draft is at {body}. \n"
        "Report as your brief says; change nothing.\n"
    ),
}
AUDIT_PROMPT = (
    "{prompt}\n\nThis directory is the repository: the spec's commit is HEAD ({at}), on `main`"
    " ({base}).{beside} Report in your brief's Report form, its Findings section included;"
    " change nothing.\n"
)
AUDIT_END = (
    "Hand-offs to this day|Tracks walked|Who else reads|Assumed of the outside|Plan lines"
    "|Suggested track order|Not checked"
)


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


def finish(lines, runs, totals, recorded, axes):
    """The worst of the runs per axis, each run's count, and the recorded count beside them."""
    worst = {a: min(r[a] for r in runs) for a in axes}
    for a in axes:
        each = ", ".join(str(r[a]) for r in runs)
        word = WORDS.get(a, "agree")
        lines.append(f"{a}: {worst[a]} of {totals[a]} {word} at worst ({each})")
    if recorded:
        was = ", ".join(f"{a} {recorded[a]}" for a in axes)
        lines.append(
            f"recorded: {was} (brief {recorded.get('brief', '?')}, {recorded.get('runs', '?')} runs)"
        )
        lower = [f"{a} {worst[a]} < {recorded[a]}" for a in axes if worst[a] < recorded[a]]
        lines.append(
            "lower than recorded: " + ", ".join(lower) if lower else "not lower than recorded"
        )
    return lines, dict(worst, runs=len(runs))


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
            lines.append(f"run {n}: counted as 0 ({e})")
            runs.append(None)
    counted = [r for r in runs if r]
    if not counted:
        return lines + ["no run counted"], None
    totals = {a: counted[0][a][1] for a in AXES}
    runs = [{a: r[a][0] for a in AXES} if r else dict.fromkeys(AXES, 0) for r in runs]
    return finish(lines, runs, totals, recorded, AXES)


def review_report(cases, replies, recorded):
    """As report(), for the reviewer: replies[r][c] is run r's reply on case c. Per run, the cases
    whose verdict agrees with the known one, and the blocker cases whose blocker lines name the
    known fault; an unreadable reply agrees with nothing."""
    said = [[] for _ in cases]
    runs = []
    for run in replies:
        count = dict.fromkeys(REVIEW_AXES, 0)
        for i, (case, reply) in enumerate(zip(cases, run)):
            got = review.verdict(reply)
            if got is None:
                said[i].append("unreadable")
                continue
            blockers = got[1]
            said[i].append("blocker" if blockers else "none")
            count["verdict"] += said[i][-1] == case["expect"]
            count["named"] += case["expect"] == "blocker" and any(
                re.search(case["names"], line, re.I) for line in blockers
            )
        runs.append(count)
    lines = [
        f"{re.split(r'[/\\]', c['repo'])[-1]}#{c['pr']} expects {c['expect']}: {', '.join(s)}"
        for c, s in zip(cases, said)
    ]
    if all(s == "unreadable" for each in said for s in each):
        return lines + ["no run counted"], None
    totals = {
        "verdict": len(cases),
        "named": sum(c["expect"] == "blocker" for c in cases),
    }
    return finish(lines, runs, totals, recorded, REVIEW_AXES)


def findings(reply):
    """The text under the track-reviewer's "Findings:" up to "Held:" or "Not checked:"; None when
    the reply has no such section."""
    m = re.search(r"(?mi)^\W*Findings:(.*?)(?=^\W*(Held|Not checked):|\Z)", reply, re.S)
    return m.group(1) if m else None


def track_calm(text):
    return re.match(r"\s*(none|0)\b", text, re.I) is not None


def audit_findings(reply):
    """The spec-auditor's "Findings" section, up to the next section of its Report; None without
    one. "Checks run" comes before it: a check's line is not a finding."""
    m = re.search(rf"(?mi)^\W*Findings\b:?(.*?)(?=^\W*({AUDIT_END})|\Z)", reply, re.S)
    return m.group(1) if m else None


def audit_calm(text):
    """No finding the main session must or should fix: a note is advice."""
    return re.search(r"must fix|should fix", text, re.I) is None


def label(case):
    if "track" in case:
        return f"Day {case['day']} {case['track']} {case['moment']}"
    return f"Day {case['day']} #{case['pr']} {case['moment']}"


def track_report(cases, replies, recorded, read=findings, calm_on=track_calm):
    """As review_report(), for the track-reviewer and the spec-auditor: per run, the known faults
    its findings name, and the clean cases (none known) it reports no finding on. A finding counts
    only under "Findings": the same words under "Held" were seen and let pass."""
    said = [[] for _ in cases]
    named = set()
    runs = []
    for run in replies:
        count = dict.fromkeys(TRACK_AXES, 0)
        for i, (case, reply) in enumerate(zip(cases, run)):
            text = read(reply)
            if text is None:
                said[i].append("unreadable")
                continue
            if not case["known"]:
                calm = calm_on(text)
                said[i].append("none" if calm else "findings")
                count["clean"] += calm
                continue
            hits = [k["id"] for k in case["known"] if re.search(k["names"], text, re.I)]
            named.update(hits)
            said[i].append(str(len(hits)))
            count["named"] += len(hits)
        runs.append(count)
    lines = []
    for c, s in zip(cases, said):
        what = f"{len(c['known'])} known" if c["known"] else "clean"
        lines.append(f"{label(c)}, {what}: {', '.join(s)}")
    if all(s == "unreadable" for each in said for s in each):
        return lines + ["no run counted"], None
    missed = [k["id"] for c in cases for k in c["known"] if k["id"] not in named]
    if missed:
        lines.append("never named: " + ", ".join(missed))
    totals = {
        "named": sum(len(c["known"]) for c in cases),
        "clean": sum(not c["known"] for c in cases),
    }
    return finish(lines, runs, totals, recorded, TRACK_AXES)


def _writable(func, path, _):
    os.chmod(path, stat.S_IWRITE)  # git's pack files are read-only on Windows
    func(path)


def checkout(case, out, tag="", dest=None):
    """A clone of the case's repository (a local path, or owner/name on GitHub) at its commit, at
    `dest` or in `out`; `tag` keeps two cases on one pull request apart."""
    repo = case["repo"]
    name = os.path.basename(repo.rstrip("/\\")) if os.path.isdir(repo) else repo.replace("/", "-")
    base = os.path.join(out, "clones", name)
    if not os.path.isdir(base):
        source = repo if os.path.isdir(repo) else f"https://github.com/{repo}.git"
        os.makedirs(os.path.dirname(base), exist_ok=True)
        git(out, "clone", "--quiet", "--no-checkout", source, base)
    if "pr" in case:
        # A squash-merged pull request's head may be reachable only from GitHub's pull ref.
        pull = f"+pull/{case['pr']}/head:refs/cases/{case['pr']}"
        subprocess.run(["git", "-C", base, "fetch", "--quiet", "origin", pull], capture_output=True)
    path = dest or os.path.join(out, f"{name}-{case.get('pr')}{tag}")
    if os.path.isdir(path):
        shutil.rmtree(path, onerror=_writable)
    git(out, "clone", "--quiet", "--shared", "--no-checkout", base, path)
    git(path, "-c", "advice.detachedHead=false", "checkout", "--quiet", "--detach", case["at"])
    return path


def ask(runner, prompt, cwd, env=None):
    cmd = [shutil.which(runner[0]) or runner[0], *runner[1:]]
    done = subprocess.run(
        cmd,
        input=prompt.encode("utf-8"),
        capture_output=True,
        cwd=cwd,
        env=env,
        timeout=1800,
        check=False,
    )
    return done.stdout.decode("utf-8", "replace").replace("\r\n", "\n")


def reviews(data, runs, out, runner):
    """Each run's replies, one per case, from the driver's reviewer agent in the case's checkout.
    The project's own settings are not loaded (`--setting-sources user`): an old commit's
    session hooks would push counts from the scratch clone."""
    cases = data["cases"]
    paths = [checkout(case, out) for case in cases]
    if runner is None:
        runner = [
            "claude",
            "-p",
            "--model",
            "opus",
            "--permission-mode",
            "auto",
            "--strict-mcp-config",
            "--setting-sources",
            "user",
            "--settings",
            driver_settings.review(out, ROOT),
            "--max-budget-usd",
            "5",
            "--agents",
            review.agents(out, ROOT),
            "--agent",
            "reviewer",
        ]

    def one(job):
        case, path = cases[job % len(cases)], paths[job % len(cases)]
        env = None if os.path.isdir(case["repo"]) else {**os.environ, "GH_REPO": case["repo"]}
        return ask(runner, PROMPT.format(**case), path, env)

    return pooled(one, runs, paths, out)


def pooled(one, runs, paths, out):
    """one(job) for every run of every case, six at a time, each reply kept beside the count."""
    n = len(paths)
    jobs = range(runs * n)
    with ThreadPoolExecutor(min(6, len(jobs))) as pool:
        got = list(pool.map(one, jobs))
    # Each reply is kept, so a count can be read back to what the agent said.
    os.makedirs(os.path.join(out, "replies"), exist_ok=True)
    for job, reply in zip(jobs, got):
        # the path under `out`: an audit's checkouts share the repository's name
        name = os.path.relpath(paths[job % n], out).replace(os.sep, "-")
        with open(
            os.path.join(out, "replies", f"{name}-run{job // n + 1}.txt"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(reply)
    return [got[r * n : (r + 1) * n] for r in range(runs)]


def track_agents(repo, out, name="track-reviewer"):
    """The agent's brief as this repository has it, for --agents: a case's checkout holds the
    brief of its own commit, which `--agent` would read instead."""
    with open(os.path.join(repo, ".claude", "agents", name + ".md"), encoding="utf-8") as f:
        text = f.read()
    head, _, body = text.partition("\n---\n")
    meta = dict(
        line.split(": ", 1) for line in head.splitlines() if ": " in line and line[0] != "-"
    )
    tools = [t.strip() for t in meta.get("tools", "Read, Grep, Glob, Bash").split(",")]
    agent = {"description": meta.get("description", ""), "prompt": body, "tools": tools}
    path = os.path.join(out, "agents.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({name: agent}, f, indent=2)
    return path


def pr_body(case, repo):
    """The pull request's body as it merged: the draft the track-reviewer was given is not kept."""
    if "body" in case:
        return case["body"]
    done = subprocess.run(
        ["gh", "pr", "view", str(case["pr"]), "--repo", repo, "--json", "body", "-q", ".body"],
        capture_output=True,
        check=True,
    )
    return done.stdout.decode("utf-8")


def tracks(data, runs, out, runner, repo):
    """Each run's replies from the track-reviewer, one per case, in the case's checkout with `main`
    where the brief was written or at the diff's base, and no remote to read later commits from.
    The project's own settings are not loaded, as for the reviewer."""
    cases = [dict(c, repo=data["repo"]) for c in data["cases"]]
    paths, prompts = [], []
    for case in cases:
        path = checkout(case, out, "-" + case["moment"])
        git(path, "branch", "--quiet", "--force", "main", case.get("base", case["at"]))
        git(path, "remote", "remove", "origin")
        fields = dict(case)
        if case["moment"] == "brief":
            fields["file"] = os.path.join(out, "briefs", os.path.basename(case["file"]))
            os.makedirs(os.path.dirname(fields["file"]), exist_ok=True)
            shutil.copyfile(os.path.join(repo, case["file"]), fields["file"])
        else:
            fields["body"] = os.path.join(out, "bodies", f"{case['pr']}.md")
            os.makedirs(os.path.dirname(fields["body"]), exist_ok=True)
            with open(fields["body"], "w", encoding="utf-8", newline="\n") as f:
                f.write(pr_body(case, data["repo"]))
        paths.append(path)
        prompts.append(TRACK_PROMPTS[case["moment"]].format(**fields))
    if runner is None:
        runner = [
            "claude",
            "-p",
            "--permission-mode",
            "auto",
            "--strict-mcp-config",
            "--setting-sources",
            "user",
            "--max-budget-usd",
            "5",
            "--agents",
            track_agents(repo, out),
            "--agent",
            "track-reviewer",
        ]
    else:
        track_agents(repo, out)
    n = len(cases)
    return pooled(lambda job: ask(runner, prompts[job % n], paths[job % n]), runs, paths, out)


def audits(data, runs, out, runner, repo):
    """Each run's replies from the spec-auditor, one per case: the repository at the spec's commit
    in a folder of its own, `main` at the base, no remote, and each repository the case puts
    beside it at its commit. The project's own settings are not loaded, as for the reviewer."""
    cases = [dict(c, repo=data["repo"]) for c in data["cases"]]
    paths, prompts = [], []
    for case in cases:
        here = os.path.join(out, "cases", f"{case['day']}-{case['at'][:7]}")
        name = os.path.basename(case["repo"].rstrip("/\\"))
        path = checkout(case, out, dest=os.path.join(here, name))
        git(path, "branch", "--quiet", "--force", "main", case["base"])
        git(path, "remote", "remove", "origin")
        beside = ""
        for other in case.get("beside", []):
            there = checkout(other, out, dest=os.path.join(here, other["as"]))
            git(there, "remote", "remove", "origin")
            beside += f" `../{other['as']}` is {other['as']} as it stood then."
        paths.append(path)
        prompts.append(AUDIT_PROMPT.format(**dict(case, beside=beside)))
    agents = track_agents(repo, out, "spec-auditor")
    if runner is None:
        runner = [
            "claude",
            "-p",
            "--permission-mode",
            "auto",
            "--strict-mcp-config",
            "--setting-sources",
            "user",
            "--max-budget-usd",
            "5",
            "--agents",
            agents,
            "--agent",
            "spec-auditor",
        ]
    n = len(cases)
    return pooled(lambda job: ask(runner, prompts[job % n], paths[job % n]), runs, paths, out)


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
    os.makedirs(out, exist_ok=True)
    runner = runner or (shlex.split(args.runner) if args.runner else None)
    path = data.get("brief", f".claude/agents/{args.agent}.md")
    brief = git(repo, "hash-object", path).strip()[:7]
    if data.get("kind") == "review":
        print(f"{args.agent}: {len(data['cases'])} cases, {args.runs} runs, brief {brief}")
        replies = reviews(data, args.runs, out, runner)
        lines, worst = review_report(data["cases"], replies, data.get("recorded"))
    elif data.get("kind") == "track":
        print(f"{args.agent}: {len(data['cases'])} cases, {args.runs} runs, brief {brief}")
        replies = tracks(data, args.runs, out, runner, repo)
        lines, worst = track_report(data["cases"], replies, data.get("recorded"))
    elif data.get("kind") == "audit":
        print(f"{args.agent}: {len(data['cases'])} cases, {args.runs} runs, brief {brief}")
        replies = audits(data, args.runs, out, runner, repo)
        lines, worst = track_report(
            data["cases"], replies, data.get("recorded"), audit_findings, audit_calm
        )
    else:
        key = prepare(repo, data["cases"], out)
        blind = os.path.join(out, "blind.md").replace("\\", "/")
        with open(blind, encoding="utf-8") as f:
            n = len(f.read().splitlines())
        prompt = f"Label the entries in {blind}. It has {n} lines: read it with limit {n}."
        runner = runner or ["claude", "-p", "--agent", args.agent]
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
