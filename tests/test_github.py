"""evidence_line(), step_prs(), checks(), failed_lines() and pr_state() read gh's answers: a run's
state, the open pull requests of a step's branches, a pull request's checks, the log of a failed
job, a pull request's state, and a gh that fails. Each test runs a fake gh beside a scratch project,
as PreflightTest does for claude, and reads back the arguments it was called with."""

import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SHA = "1dc0f03" + "a" * 33
JOB = "https://github.com/me/project/actions/runs/11/job/22"

# The fake program: it records its arguments in calls.jsonl beside it, then answers `run list`,
# `pr list`, `issue list`, and the issue writes (`issue create`, `issue comment`, `issue close`,
# `label create`) from fake.json (`issue_code` fails every issue and label call), and exits 99 on
# anything else. A call with `--body-file -` also appends its stdin to bodies.jsonl beside it. A
# fake.json with `sleep_on` (an `issue` subcommand) and `sleep` makes that call sleep first, for
# the timeout test. `pr checks`, `pr view`, `run view` and `run list` with `run_steps` answer from the
# lists `checks`, `views`, `logs` and `run_steps` in fake.json, each entry `{"code": n, "out": ...}`
# (a string printed as it is, anything else as JSON), one per call, the last repeated.
FAKE = """import json
import sys
import time
from pathlib import Path

folder = Path(__file__).resolve().parent
args = sys.argv[1:]
with (folder / "calls.jsonl").open("ab") as calls:
    calls.write(json.dumps(args).encode("utf-8") + b"\\n")
spec = json.loads((folder / "fake.json").read_text(encoding="utf-8"))


def step(name):
    # One answer per call, the last repeated, so that a test can walk a state through its changes.
    answers = spec[name]
    answer = answers.pop(0) if len(answers) > 1 else answers[0]
    (folder / "fake.json").write_bytes(json.dumps(spec).encode("utf-8"))
    out = answer["out"]
    text = out if isinstance(out, str) else json.dumps(out)
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.exit(answer["code"])


if "--body-file" in args and args[args.index("--body-file") + 1] == "-":
    # Read before any exit below, so that a failed call does not leave its stdin unread.
    body = sys.stdin.buffer.read().decode("utf-8")
    with (folder / "bodies.jsonl").open("ab") as bodies:
        bodies.write(json.dumps({"args": args, "body": body}).encode("utf-8") + b"\\n")
if args[0] == "issue" and spec.get("sleep_on") == args[1]:
    time.sleep(spec.get("sleep", 0))
if spec["code"] != 0:
    sys.exit(spec["code"])
if args[0] in ("issue", "label") and spec.get("issue_code", 0) != 0:
    sys.exit(spec["issue_code"])
if args[:2] == ["run", "list"]:
    if spec["run_steps"]:
        step("run_steps")
    print(json.dumps(spec["runs"]))
    sys.exit(0)
if args[:2] == ["pr", "list"]:
    prs = spec["prs"]
    if "--author" in args and args[args.index("--author") + 1] == "@me":
        prs = [pr for pr in prs if pr.get("author") == "me"]
    print(json.dumps([{k: v for k, v in pr.items() if k != "author"} for pr in prs]))
    sys.exit(0)
if args[:2] == ["issue", "list"]:
    issues = spec["issues"]
    state = args[args.index("--state") + 1]
    issues = [issue for issue in issues if issue.get("state") == state]
    if "--label" in args:
        label = args[args.index("--label") + 1]
        issues = [issue for issue in issues if label in issue.get("labels", [])]
    if "--author" in args and args[args.index("--author") + 1] == "@me":
        issues = [issue for issue in issues if issue.get("author") == "me"]
    fields = args[args.index("--json") + 1].split(",")
    listed = []
    for issue in issues:
        row = {}
        for field in fields:
            if field == "labels":
                row[field] = [{"name": n} for n in issue.get("labels", [])]
            else:
                row[field] = issue.get(field)
        listed.append(row)
    print(json.dumps(listed))
    sys.exit(0)
if args[:2] == ["label", "create"]:
    sys.exit(0)
if args[:2] == ["issue", "create"]:
    number = max([issue["number"] for issue in spec["issues"]], default=0) + 1
    labels = [args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "--label"]
    title = args[args.index("--title") + 1]
    spec["issues"].append(
        {"number": number, "title": title, "labels": labels, "state": "open", "author": "me"}
    )
    (folder / "fake.json").write_bytes(json.dumps(spec).encode("utf-8"))
    print(f"https://github.com/me/project/issues/{number}")
    sys.exit(0)
if args[:2] in (["issue", "comment"], ["issue", "close"]):
    if args[2] not in [str(issue["number"]) for issue in spec["issues"]]:
        sys.exit(1)
    if args[1] == "close":
        for issue in spec["issues"]:
            if str(issue["number"]) == args[2]:
                issue["state"] = "closed"
        (folder / "fake.json").write_bytes(json.dumps(spec).encode("utf-8"))
        sys.exit(0)
    print(f"https://github.com/me/project/issues/{args[2]}#issuecomment-1")
    sys.exit(0)
if args[:2] == ["pr", "checks"]:
    step("checks")
if args[:2] == ["pr", "view"]:
    step("views")
if args[:2] == ["run", "view"]:
    step("logs")
sys.exit(99)
"""


def fake_gh(
    folder,
    runs=None,
    prs=None,
    code=0,
    issues=None,
    issue_code=0,
    checks=None,
    views=None,
    logs=None,
    run_steps=None,
):
    spec = {
        "runs": runs or [],
        "prs": prs or [],
        "code": code,
        "issues": issues or [],
        "issue_code": issue_code,
        "checks": checks or [],
        "views": views or [],
        "logs": logs or [],
        "run_steps": run_steps or [],
    }
    # Files are written as bytes: on Windows, text mode would add a carriage return to each line.
    (folder / "fake.json").write_bytes(json.dumps(spec).encode("utf-8"))
    (folder / "fake.py").write_bytes(FAKE.encode("utf-8"))
    if os.name == "nt":
        program = folder / "gh.cmd"
        program.write_bytes(f'@"{sys.executable}" "%~dp0fake.py" %*\r\n'.encode())
    else:
        program = folder / "gh"
        program.write_bytes(f"#!{sys.executable}\n{FAKE}".encode())
        program.chmod(0o755)
    return str(program)


def read_calls(folder):
    return [
        json.loads(line)
        for line in (folder / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def read_bodies(folder):
    # Read as bytes, as the fake wrote them: a carriage return the caller sent is escaped in the
    # JSON, so the raw file holds none, and the decoded body shows whether one was sent.
    return [
        json.loads(line)
        for line in (folder / "bodies.jsonl").read_bytes().decode("utf-8").splitlines()
    ]


class GitHubTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top, as in test_home: where driver/github.py is missing, each
        # test fails alone with ImportError.
        self.github = importlib.import_module("driver.github")

    def scratch(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        return folder

    def test_evidence_states(self):
        cases = [
            ([{"status": "completed", "conclusion": "success"}], None),
            ([], "park: no evidence run on `1dc0f03` yet"),
            (
                [{"status": "in_progress", "conclusion": ""}],
                "park: the evidence run on `1dc0f03` has not finished (`in_progress`)",
            ),
            (
                [{"status": "completed", "conclusion": "failure"}],
                "park: the evidence run on `1dc0f03` ended `failure`",
            ),
        ]
        for runs, want in cases:
            with self.subTest(runs=runs):
                folder = self.scratch()
                gh = fake_gh(folder, runs=runs)
                line = self.github.evidence_line(str(folder), gh, SHA)
                self.assertEqual(line, want)
                self.assertEqual(
                    read_calls(folder),
                    [
                        [
                            "run",
                            "list",
                            "--workflow",
                            "evidence.yml",
                            "--commit",
                            SHA,
                            "--limit",
                            "1",
                            "--json",
                            "status,conclusion",
                        ]
                    ],
                )

    def test_evidence_gh_fails(self):
        folder = self.scratch()
        gh = fake_gh(folder, code=1)
        self.assertEqual(
            self.github.evidence_line(str(folder), gh, SHA),
            "cannot read the project: gh run list exited 1",
        )

    def test_step_prs_by_branch_and_author(self):
        folder = self.scratch()
        prs = [
            {
                "number": 1,
                "headRefName": "day-04/track-a-x",
                "url": "https://example/pr/1",
                "author": "me",
            },
            {
                "number": 2,
                "headRefName": "day-04/track-a-y",
                "url": "https://example/pr/2",
                "author": "someone",
            },
            {
                "number": 3,
                "headRefName": "day-04/track-b-z",
                "url": "https://example/pr/3",
                "author": "me",
            },
            {
                "number": 4,
                "headRefName": "day-14/track-a-x",
                "url": "https://example/pr/4",
                "author": "me",
            },
        ]
        gh = fake_gh(folder, prs=prs)
        result = self.github.step_prs(str(folder), gh, "Day 04 Track A: the kit's output read")
        self.assertEqual(
            result,
            (
                [{"number": 1, "headRefName": "day-04/track-a-x", "url": "https://example/pr/1"}],
                None,
            ),
        )
        calls = read_calls(folder)
        self.assertEqual(len(calls), 1)
        args = calls[0]
        self.assertEqual(args[args.index("--author") + 1], "@me")
        self.assertEqual(args[args.index("--state") + 1], "open")
        self.assertEqual(
            args,
            [
                "pr",
                "list",
                "--state",
                "open",
                "--author",
                "@me",
                "--limit",
                "100",
                "--json",
                "number,headRefName,url",
            ],
        )

    def test_step_prs_gh_fails(self):
        folder = self.scratch()
        gh = fake_gh(folder, code=1)
        self.assertEqual(
            self.github.step_prs(str(folder), gh, "Day 04 Track A: the kit's output read"),
            ([], "cannot read the project: gh pr list exited 1"),
        )

    def test_checks(self):
        def row(name, bucket):
            return {"name": name, "bucket": bucket, "link": JOB}

        # Each case: the rows gh answers with (or "" for a failed call), gh's exit code, then the
        # state, the names of the failed checks and the reason the caller gets.
        cases = [
            ([row("tests", "pending"), row("lint", "pass")], 8, "pending", [], None),
            (
                [
                    row("tests", "fail"),
                    row("build", "cancel"),
                    row("lint", "pending"),
                    row("docs", "pass"),
                ],
                8,
                "red",
                ["tests", "build"],
                None,
            ),
            ([row("lint", "pass"), row("docs", "skipping")], 0, "green", [], None),
            ([], 0, "none", [], None),
            ("", 1, None, [], "gh pr checks exited 1"),
        ]
        for out, code, state, names, reason in cases:
            with self.subTest(out=out, code=code):
                folder = self.scratch()
                gh = fake_gh(folder, checks=[{"code": code, "out": out}])
                got_state, failed, got_reason = self.github.checks(str(folder), gh, 12)
                self.assertEqual(got_state, state)
                self.assertEqual([c["name"] for c in failed], names)
                self.assertEqual(got_reason, reason)
                if state == "red":
                    self.assertEqual(failed[0]["link"], JOB)
                self.assertEqual(
                    read_calls(folder),
                    [["pr", "checks", "12", "--required", "--json", "name,bucket,link"]],
                )

        # The answers walk the state: pending, then passed, and the last answer repeats.
        folder = self.scratch()
        gh = fake_gh(
            folder,
            checks=[
                {"code": 8, "out": [row("tests", "pending")]},
                {"code": 0, "out": [row("tests", "pass")]},
            ],
        )
        states = [self.github.checks(str(folder), gh, 12)[0] for _ in range(3)]
        self.assertEqual(states, ["pending", "green", "green"])

    def test_failed_lines(self):
        # A job's log keeps its last 40 lines; a link that is not a job is named by its link.
        folder = self.scratch()
        gh = fake_gh(
            folder,
            logs=[
                {"code": 0, "out": "\n".join(f"line {i}" for i in range(50)) + "\n"},
                {"code": 0, "out": "lint – one\nlint two\n"},
            ],
        )
        links = [
            {"name": "tests", "link": JOB},
            {"name": "lint", "link": "https://github.com/me/project/actions/runs/33/job/44"},
            {"name": "vercel", "link": "https://vercel.com/x"},
        ]
        self.assertEqual(
            self.github.failed_lines(str(folder), gh, links),
            "\n".join(
                [f"line {i}" for i in range(10, 50)]
                + ["lint – one", "lint two", "vercel https://vercel.com/x"]
            ),
        )
        self.assertEqual(
            read_calls(folder),
            [
                ["run", "view", "--job", "22", "--log-failed"],
                ["run", "view", "--job", "44", "--log-failed"],
            ],
        )

        # The log is cut to its last 6000 characters.
        folder = self.scratch()
        lines = [f"{i:03d}" + "x" * 297 for i in range(40)]
        gh = fake_gh(folder, logs=[{"code": 0, "out": "\n".join(lines) + "\n"}])
        result = self.github.failed_lines(str(folder), gh, [{"name": "tests", "link": JOB}])
        self.assertEqual(result, "\n".join(lines)[-6000:])
        self.assertEqual(len(result), 6000)

        # A failed log call is named by the check's link, not an error.
        folder = self.scratch()
        gh = fake_gh(folder, logs=[{"code": 1, "out": ""}])
        self.assertEqual(
            self.github.failed_lines(str(folder), gh, [{"name": "tests", "link": JOB}]),
            f"tests {JOB}",
        )

    def test_pr_state(self):
        sha = SHA
        cases = [
            (
                {
                    "state": "MERGED",
                    "mergeCommit": {"oid": sha},
                    "files": [{"path": "plan.md", "additions": 1}, {"path": "driver/loop.py"}],
                    "body": "Oversized: yes\n",
                },
                0,
                ("MERGED", sha, ["plan.md", "driver/loop.py"], "Oversized: yes\n", None),
            ),
            (
                {"state": "OPEN", "mergeCommit": None, "files": [], "body": None},
                0,
                ("OPEN", None, [], "", None),
            ),
            ("", 1, (None, None, [], "", "gh pr view exited 1")),
        ]
        for out, code, expected in cases:
            with self.subTest(out=out, code=code):
                folder = self.scratch()
                gh = fake_gh(folder, views=[{"code": code, "out": out}])
                self.assertEqual(self.github.pr_state(str(folder), gh, 12), expected)
                self.assertEqual(
                    read_calls(folder),
                    [["pr", "view", "12", "--json", "state,mergeCommit,files,body"]],
                )
