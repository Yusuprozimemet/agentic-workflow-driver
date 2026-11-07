"""evidence_line() and step_prs() read gh's answers: a run's state, the open pull requests of a step's
branches, and a gh that fails. Each test runs a fake gh beside a scratch project, as PreflightTest
does for claude, and reads back the arguments it was called with."""

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

# The fake program: it records its arguments in calls.jsonl beside it, then answers `run list`,
# `pr list` and `issue list` from fake.json (`issue_code` fails every issue and label call), and
# exits 99 on anything else.
FAKE = """import json
import sys
from pathlib import Path

folder = Path(__file__).resolve().parent
args = sys.argv[1:]
with (folder / "calls.jsonl").open("ab") as calls:
    calls.write(json.dumps(args).encode("utf-8") + b"\\n")
spec = json.loads((folder / "fake.json").read_text(encoding="utf-8"))
if spec["code"] != 0:
    sys.exit(spec["code"])
if args[0] in ("issue", "label") and spec.get("issue_code", 0) != 0:
    sys.exit(spec["issue_code"])
if args[:2] == ["run", "list"]:
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
sys.exit(99)
"""


def fake_gh(folder, runs=None, prs=None, code=0, issues=None, issue_code=0):
    spec = {
        "runs": runs or [],
        "prs": prs or [],
        "code": code,
        "issues": issues or [],
        "issue_code": issue_code,
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
