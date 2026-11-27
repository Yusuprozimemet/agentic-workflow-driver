"""scripts/agent-cases.py runs an agent on cases whose answer is known and counts what it got.

No test starts a model: the runner is a small Python file that prints a reply. The last class
builds a scratch repository, since a case is a spec at a commit.

    python scripts/test_agent_cases.py
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("agent_cases", os.path.join(HERE, "agent-cases.py"))
agent_cases = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_cases)

NOTES = """## Notes
- **Defect** — found: auditor · cause: spec · made: Day 44 · C44.2 counted 9 files; there are 11.
- **Defect** — found: review · cause: implementation · made: Day 44 · a dead branch.
- **Defect** — found: the close · cause: process · made: Day 43 · a box ticked without evidence.
"""
RIGHT = [
    {"id": "D44-1", "stage": "before_code", "cause": "spec", "made": "this"},
    {"id": "D44-2", "stage": "before_merge", "cause": "implementation", "made": "this"},
    {"id": "D44-3", "stage": "escape", "cause": "process", "made": "earlier"},
]
ONE_CAUSE_OFF = [RIGHT[0], dict(RIGHT[1], cause="spec"), RIGHT[2]]


def key():
    d = tempfile.mkdtemp()
    path = os.path.join(d, "day-44-example.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(NOTES)
    return agent_cases.relabel.entries(path)


class LabelsTest(unittest.TestCase):
    def test_the_array_is_read_from_a_fenced_reply(self):
        reply = "Here are the labels:\n```json\n" + json.dumps(RIGHT) + "\n```\n"
        self.assertEqual(RIGHT, agent_cases.labels(reply))

    def test_a_reply_with_no_array_is_none(self):
        self.assertIsNone(agent_cases.labels("I could not read the file."))
        self.assertIsNone(agent_cases.labels("[1, 2]"))


class ReportTest(unittest.TestCase):
    def test_the_worst_run_is_the_count_and_each_run_is_shown(self):
        lines, worst = agent_cases.report(
            key(), [json.dumps(RIGHT), json.dumps(ONE_CAUSE_OFF)], None
        )
        self.assertEqual(
            [
                "stage: 3 of 3 agree at worst (3, 3)",
                "cause: 2 of 3 agree at worst (3, 2)",
                "made: 3 of 3 agree at worst (3, 3)",
            ],
            lines,
        )
        self.assertEqual({"stage": 3, "cause": 2, "made": 3, "runs": 2}, worst)

    def test_a_fall_below_the_recorded_count_is_named(self):
        recorded = {"stage": 3, "cause": 3, "made": 3, "runs": 3, "brief": "abc1234"}
        lines, _ = agent_cases.report(key(), [json.dumps(ONE_CAUSE_OFF)], recorded)
        self.assertEqual(
            [
                "recorded: stage 3, cause 3, made 3 (brief abc1234, 3 runs)",
                "lower than recorded: cause 2 < 3",
            ],
            lines[-2:],
        )
        lines, _ = agent_cases.report(key(), [json.dumps(RIGHT)], recorded)
        self.assertEqual("not lower than recorded", lines[-1])

    def test_a_run_with_no_array_or_a_missing_entry_counts_as_zero(self):
        # Left out, two unreadable runs of three scored as well as three good ones.
        lines, worst = agent_cases.report(
            key(), ["no", json.dumps(RIGHT[:2]), json.dumps(RIGHT)], None
        )
        # One line at a time: a whole list's diff is shortened ("[N chars]"), which break.py refuses.
        for want, got in zip(
            [
                "run 1: counted as 0 (no JSON array in the reply)",
                "run 2: counted as 0 (no label for D44-3)",
                "stage: 0 of 3 agree at worst (0, 0, 3)",
            ],
            lines,
        ):
            self.assertEqual(want, got)
        self.assertEqual({"stage": 0, "cause": 0, "made": 0, "runs": 3}, worst)
        self.assertEqual(
            (["run 1: counted as 0 (no JSON array in the reply)", "no run counted"], None),
            agent_cases.report(key(), ["no"], None),
        )


class RunTest(unittest.TestCase):
    """A scratch repository: the spec committed, then its Notes edited in the working tree."""

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        for path, text in [
            ("specs/day-44-example.md", NOTES),
            (".claude/agents/rater.md", "brief\n"),
            (
                "reply.py",
                "import sys\nsys.stdin.read()\nprint(open(sys.argv[1], encoding='utf-8').read())\n",
            ),
        ]:
            os.makedirs(os.path.dirname(os.path.join(self.repo, path)), exist_ok=True)
            with open(os.path.join(self.repo, path), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        git = [
            "git",
            "-C",
            self.repo,
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "-c",
            "core.autocrlf=false",
        ]
        subprocess.run(git + ["init", "-q"], check=True)
        subprocess.run(git + ["add", "."], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "a spec"], check=True)
        at = (
            subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, check=True)
            .stdout.decode()
            .strip()
        )
        with open(os.path.join(self.repo, "specs/day-44-example.md"), "w", encoding="utf-8") as f:
            f.write("## Notes\n")
        self.cases = os.path.join(self.repo, "specs", "agent-cases", "rater.json")
        os.makedirs(os.path.dirname(self.cases))
        with open(self.cases, "w", encoding="utf-8") as f:
            json.dump({"cases": [{"spec": "specs/day-44-example.md", "at": at}]}, f)

    def saved(self):
        with open(self.cases, encoding="utf-8") as f:
            return json.load(f)

    def run_it(self, reply, *argv):
        with open(os.path.join(self.repo, "reply.txt"), "w", encoding="utf-8") as f:
            f.write(reply)
        runner = [
            sys.executable,
            os.path.join(self.repo, "reply.py"),
            os.path.join(self.repo, "reply.txt"),
        ]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = agent_cases.main(["rater", "--runs", "2", *argv], repo=self.repo, runner=runner)
        return code, out.getvalue().splitlines()

    def test_the_case_is_the_spec_at_its_commit_and_record_keeps_the_count(self):
        code, lines = self.run_it(json.dumps(ONE_CAUSE_OFF), "--record")
        self.assertEqual(0, code)
        self.assertRegex(lines[0], r"^rater: 3 entries from 1 specs, 2 runs, brief [0-9a-f]{7}$")
        self.assertEqual("cause: 2 of 3 agree at worst (2, 2)", lines[2])
        recorded = self.saved()["recorded"]
        self.assertEqual(
            {"stage": 3, "cause": 2, "made": 3, "runs": 2},
            {k: v for k, v in recorded.items() if k != "brief"},
        )
        code, lines = self.run_it(json.dumps(RIGHT))
        self.assertEqual("not lower than recorded", lines[-1])

    def test_no_run_counted_exits_1_and_records_nothing(self):
        code, lines = self.run_it("the file was not there", "--record")
        self.assertEqual(1, code)
        self.assertEqual("no run counted", lines[-1])
        self.assertNotIn("recorded", self.saved())

    def test_a_draft_is_counted_in_its_briefs_place_and_never_recorded(self):
        draft = os.path.join(self.repo, "draft.md")
        with open(draft, "w", encoding="utf-8", newline="\n") as f:
            f.write("---\nname: rater\ntools: Read\nmodel: m\n---\ndraft\n")
        sha = subprocess.run(["git", "hash-object", draft], capture_output=True, check=True)
        code, lines = self.run_it(json.dumps(RIGHT), "--brief", draft)
        self.assertEqual((0, "brief " + sha.stdout.decode()[:7]), (code, lines[0][-13:]))
        agents = os.path.join(self.repo, ".claude/state/agent-cases/rater/agents.json")
        with open(agents, encoding="utf-8") as f:
            got = json.load(f)["rater"]
        want = {"description": "", "prompt": "draft\n", "tools": ["Read"], "model": "m"}
        self.assertEqual(want, got)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_it(json.dumps(RIGHT), "--brief", draft, "--record")
        self.assertNotIn("recorded", self.saved())


FAULT = {"repo": "o/bearing", "pr": 7, "at": "abc", "expect": "blocker", "names": "manifest"}
CLEAN = {"repo": "o/bearing", "pr": 8, "at": "def", "expect": "none"}
NAMED = "found: blocker — two broken: lines have no manifest entry\nREVIEW: blocker"
OTHER = "found: blocker — a word\nREVIEW: blocker"
NONE = "found: advice — wording\nREVIEW: none"


class ReviewReportTest(unittest.TestCase):
    def test_each_case_is_shown_and_the_worst_run_is_the_count(self):
        lines, worst = agent_cases.review_report(
            [FAULT, CLEAN], [[NAMED, NONE], [OTHER, NAMED], ["no verdict", NONE]], None
        )
        want = [
            "bearing#7 expects blocker: blocker, blocker, unreadable",
            "bearing#8 expects none: none, blocker, none",
            "verdict: 1 of 2 agree at worst (2, 1, 1)",
            "named: 0 of 1 name the known fault at worst (1, 0, 0)",
        ]
        self.assertEqual(len(want), len(lines))
        for w, got in zip(want, lines):
            self.assertEqual(w, got)
        cases = [
            {"case": "bearing#7", "said": ["blocker", "blocker", "unreadable"], "named": 1},
            {"case": "bearing#8", "said": ["none", "blocker", "none"], "named": 0},
        ]
        self.assertEqual({"verdict": 1, "named": 0, "runs": 3, "cases": cases}, worst)

    def test_a_fall_below_the_recorded_count_is_named(self):
        recorded = {"verdict": 2, "named": 1, "runs": 3, "brief": "abc1234"}
        lines, _ = agent_cases.review_report([FAULT, CLEAN], [[OTHER, NONE]], recorded)
        self.assertEqual(
            [
                "recorded: verdict 2, named 1 (brief abc1234, 3 runs)",
                "lower than recorded: named 0 < 1",
            ],
            lines[-2:],
        )

    def test_no_reply_read_is_no_run_counted(self):
        lines, worst = agent_cases.review_report([FAULT], [["x"], [""]], None)
        self.assertEqual(
            ["bearing#7 expects blocker: unreadable, unreadable", "no run counted"], lines
        )
        self.assertIsNone(worst)


class ReviewRunTest(unittest.TestCase):
    """A scratch repository as the case's: its note at the case's commit is what the runner reads."""

    def setUp(self):
        self.origin, self.repo = tempfile.mkdtemp(), tempfile.mkdtemp()
        git = [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "-c",
            "core.autocrlf=false",
        ]
        write = lambda root, path, text: (  # noqa: E731
            os.makedirs(os.path.dirname(os.path.join(root, path)) or root, exist_ok=True),
            open(os.path.join(root, path), "w", encoding="utf-8", newline="\n").write(text),
        )
        write(self.origin, "note.txt", "no manifest entry")
        subprocess.run(git + ["-C", self.origin, "init", "-q"], check=True)
        subprocess.run(git + ["-C", self.origin, "add", "."], check=True)
        subprocess.run(git + ["-C", self.origin, "commit", "-q", "-m", "a"], check=True)
        at = (
            subprocess.run(
                ["git", "-C", self.origin, "rev-parse", "HEAD"], capture_output=True, check=True
            )
            .stdout.decode()
            .strip()
        )
        write(self.origin, "note.txt", "a word")
        subprocess.run(git + ["-C", self.origin, "commit", "-q", "-am", "b"], check=True)
        write(
            self.repo,
            "reply.py",
            "import re, sys\nsys.stdout.reconfigure(encoding='utf-8')\nn = re.search(r'#(\\d+)', sys.stdin.read()).group(1)\n"
            "note = open('note.txt', encoding='utf-8').read()\n"
            "print('found: blocker — ' + note + '\\nREVIEW: blocker' if n == '7' else 'REVIEW: none')\n",
        )
        write(self.repo, "rules/reviewer.md", "brief\n")
        subprocess.run(git + ["-C", self.repo, "init", "-q"], check=True)
        self.cases = os.path.join(self.repo, "specs", "agent-cases", "reviewer.json")
        cases = [dict(FAULT, repo=self.origin, at=at), dict(CLEAN, repo=self.origin, at=at)]
        write(
            self.repo,
            "specs/agent-cases/reviewer.json",
            json.dumps({"kind": "review", "brief": "rules/reviewer.md", "cases": cases}),
        )

    def test_each_case_runs_in_its_checkout_at_its_commit_and_record_keeps_the_count(self):
        runner = [sys.executable, os.path.join(self.repo, "reply.py")]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = agent_cases.main(["reviewer", "--runs", "2", "--record"], self.repo, runner)
        lines = out.getvalue().splitlines()
        self.assertEqual(0, code)
        self.assertRegex(lines[0], r"^reviewer: 2 cases, 2 runs, brief [0-9a-f]{7}$")
        self.assertEqual("verdict: 2 of 2 agree at worst (2, 2)", lines[3])
        self.assertEqual("named: 1 of 1 name the known fault at worst (1, 1)", lines[4])
        replies = os.path.join(self.repo, ".claude", "state", "agent-cases", "reviewer", "replies")
        self.assertEqual(4, len(os.listdir(replies)))
        with open(self.cases, encoding="utf-8") as f:
            recorded = json.load(f)["recorded"]
        self.assertEqual(
            {"verdict": 2, "named": 1, "runs": 2},
            {k: recorded[k] for k in ("verdict", "named", "runs")},
        )


BRIEF = {
    "moment": "brief",
    "day": "44",
    "track": "A",
    "known": [{"id": "D44.1", "names": "heartbeat"}, {"id": "D44.2", "names": r"\[\d+ chars\]"}],
}
QUIET = {"moment": "diff", "day": "44", "track": "B", "known": []}
HEAD = "track-reviewer: Day 44 track A, brief\n\n"
BOTH = HEAD + "Findings: 2\n- the heartbeat adds calls\n- prints [40 chars]\n\nHeld: 1\n"
ONE = (
    HEAD
    + "Findings: 1\n- the heartbeat adds calls\n\nHeld: 2. [40 chars] seen\nNot checked: none\n"
)
CALM = HEAD + "Findings: none\n\nHeld: 1-6\n"
SOME = HEAD + "Findings: 1\n- a comment is long\n"


class TrackReportTest(unittest.TestCase):
    def test_each_case_is_shown_and_a_known_fault_counts_only_under_findings(self):
        lines, worst = agent_cases.track_report(
            [BRIEF, QUIET], [[BOTH, CALM], [ONE, SOME], ["no report", CALM]], None
        )
        want = [
            "Day 44 A brief, 2 known: 2, 1, unreadable",
            "Day 44 B diff, clean: none, findings, none",
            "named: 0 of 2 name the known fault at worst (2, 1, 0)",
            "clean: 0 of 1 say none on a clean case at worst (1, 0, 1)",
        ]
        self.assertEqual(len(want), len(lines))
        for w, got in zip(want, lines):
            self.assertEqual(w, got)
        self.assertEqual({"named": 0, "clean": 0, "runs": 3}, worst)

    def test_a_fault_no_run_named_is_listed(self):
        lines, _ = agent_cases.track_report([BRIEF], [[ONE], [ONE]], None)
        self.assertEqual("never named: D44.2", lines[1])

    def test_no_report_read_is_no_run_counted(self):
        lines, worst = agent_cases.track_report([BRIEF], [["x"]], None)
        self.assertEqual("no run counted", lines[-1])
        self.assertIsNone(worst)


class TrackRunTest(unittest.TestCase):
    """A scratch repository as the case's: `main` is where the brief was written, or the diff's base,
    and the reply reads what the session would."""

    def setUp(self):
        self.origin, self.repo = tempfile.mkdtemp(), tempfile.mkdtemp()
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
        run = lambda *a: subprocess.run(git + ["-C", *a], check=True, capture_output=True)  # noqa: E731
        sha = lambda: run(self.origin, "rev-parse", "HEAD").stdout.decode().strip()  # noqa: E731

        def write(root, path, text):
            os.makedirs(os.path.dirname(os.path.join(root, path)) or root, exist_ok=True)
            with open(os.path.join(root, path), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)

        run(self.origin, "init", "-q")
        write(self.origin, "code.py", "one\n")
        run(self.origin, "add", ".")
        run(self.origin, "commit", "-q", "-m", "a")
        base = sha()
        write(self.origin, "code.py", "the heartbeat\n")
        run(self.origin, "commit", "-q", "-am", "b")
        head = sha()
        write(
            self.repo, ".claude/agents/track-reviewer.md", "---\nname: track-reviewer\n---\nbrief\n"
        )
        write(self.repo, "briefs/a.md", "a brief that says [40 chars]\n")
        write(
            self.repo,
            "reply.py",
            "import re, subprocess, sys\nsys.stdout.reconfigure(encoding='utf-8')\n"
            "p = sys.stdin.read()\n"
            "g = lambda *a: subprocess.run(['git', *a], capture_output=True).stdout.decode().strip()\n"
            "said = [g('show', 'main:code.py'), g('remote')]\n"
            "if p.startswith('brief'):\n"
            "    said.append(open(re.search(r'is at (\\S+)\\. ', p).group(1)).read())\n"
            "else:\n"
            "    said.append(open(re.search(r'draft is at (\\S+)\\. ', p).group(1)).read())\n"
            "print('Findings: 1\\n- ' + ' | '.join(said))\n",
        )
        run(self.repo, "init", "-q")
        brief = dict(BRIEF, spec="s.md", pr=7, at=base, file="briefs/a.md")
        diff = dict(QUIET, spec="s.md", pr=7, base=base, at=head, body="the heartbeat body")
        # main is the base, the clone has no remote to read later commits from, the body is a file
        diff["known"] = [{"id": "D44.3", "names": r"(?m)^- one \|  \| the heartbeat body$"}]
        self.cases = os.path.join(self.repo, "specs", "agent-cases", "track-reviewer.json")
        write(
            self.repo,
            "specs/agent-cases/track-reviewer.json",
            json.dumps({"kind": "track", "repo": self.origin, "cases": [brief, diff]}),
        )

    def test_each_case_reads_its_brief_or_diff_against_main_and_record_keeps_the_count(self):
        runner = [sys.executable, os.path.join(self.repo, "reply.py")]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = agent_cases.main(
                ["track-reviewer", "--runs", "2", "--record"], self.repo, runner
            )
        lines = out.getvalue().splitlines()
        self.assertEqual(0, code, lines)
        self.assertRegex(lines[0], r"^track-reviewer: 2 cases, 2 runs, brief [0-9a-f]{7}$")
        self.assertEqual("Day 44 A brief, 2 known: 1, 1", lines[1])
        self.assertEqual("Day 44 B diff, 1 known: 1, 1", lines[2])
        self.assertEqual("never named: D44.1", lines[3])
        self.assertEqual("named: 2 of 3 name the known fault at worst (2, 2)", lines[4])
        state = os.path.join(self.repo, ".claude", "state", "agent-cases", "track-reviewer")
        self.assertEqual(4, len(os.listdir(os.path.join(state, "replies"))))
        with open(os.path.join(state, "agents.json"), encoding="utf-8") as f:
            self.assertEqual("brief\n", json.load(f)["track-reviewer"]["prompt"])
        with open(self.cases, encoding="utf-8") as f:
            self.assertEqual(2, json.load(f)["recorded"]["named"])


AUDIT = {
    "moment": "audit",
    "day": "44",
    "pr": 9,
    "known": [{"id": "D44.4", "names": "heartbeat"}, {"id": "D44.5", "names": "P54"}],
}
RECHECK = {"moment": "recheck", "day": "44", "pr": 9, "known": []}
AUDIT_HEAD = "Verdict: 2 findings\n\nChecks run\n- C44.1: P54 → hold: green\n\n"
AUDITED = (
    AUDIT_HEAD
    + "Findings\n1. [must fix] the heartbeat adds calls\n\nHand-offs to this day\n- P54\n"
)
NOTE = AUDIT_HEAD + "Findings\n1. [note] a branch exists\n\nNot checked, and why: none\n"
FIX = AUDIT_HEAD + "Findings\n1. [should fix] C44.2 can pass\n\nPlan lines\n- none\n"


class AuditReportTest(unittest.TestCase):
    def test_a_finding_counts_only_under_findings_and_a_note_leaves_a_case_clean(self):
        lines, worst = agent_cases.track_report(
            [AUDIT, RECHECK],
            [[AUDITED, NOTE], [NOTE, FIX]],
            None,
            agent_cases.audit_findings,
            agent_cases.audit_calm,
        )
        want = [
            "Day 44 #9 audit, 2 known: 1, 0",
            "Day 44 #9 recheck, clean: none, findings",
            "never named: D44.5",
            "named: 0 of 2 name the known fault at worst (1, 0)",
            "clean: 0 of 1 say none on a clean case at worst (1, 0)",
        ]
        self.assertEqual(len(want), len(lines))
        for w, got in zip(want, lines):
            self.assertEqual(w, got)
        self.assertEqual({"named": 0, "clean": 0, "runs": 2}, worst)

    def test_a_report_with_no_findings_section_is_unreadable(self):
        lines, worst = agent_cases.track_report(
            [AUDIT], [[AUDIT_HEAD]], None, agent_cases.audit_findings, agent_cases.audit_calm
        )
        self.assertEqual("no run counted", lines[-1])
        self.assertIsNone(worst)


class AuditRunTest(unittest.TestCase):
    """The case's repository at the draft, `main` at its base, no remote, and the repository beside
    it at its own commit, where the spec's `../<name>` reads it."""

    def setUp(self):
        self.origin, self.beside, self.repo = (
            tempfile.mkdtemp(),
            tempfile.mkdtemp(),
            tempfile.mkdtemp(),
        )
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
        run = lambda *a: subprocess.run(git + ["-C", *a], check=True, capture_output=True)  # noqa: E731
        sha = lambda r: run(r, "rev-parse", "HEAD").stdout.decode().strip()  # noqa: E731

        def write(root, path, text):
            os.makedirs(os.path.dirname(os.path.join(root, path)) or root, exist_ok=True)
            with open(os.path.join(root, path), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)

        for r, first, then in ((self.origin, "one", "the draft"), (self.beside, "then", "later")):
            run(r, "init", "-q")
            write(r, "f.txt", first + "\n")
            run(r, "add", ".")
            run(r, "commit", "-q", "-m", "a")
            write(r, "f.txt", then + "\n")
            run(r, "commit", "-q", "-am", "b")
        base = run(self.origin, "rev-parse", "HEAD~1").stdout.decode().strip()
        then = run(self.beside, "rev-parse", "HEAD~1").stdout.decode().strip()
        write(self.repo, ".claude/agents/spec-auditor.md", "---\nname: spec-auditor\n---\naudit\n")
        write(
            self.repo,
            "reply.py",
            "import os, subprocess, sys\nsys.stdout.reconfigure(encoding='utf-8')\n"
            "p = sys.stdin.read().replace('\\n', ' ')\n"
            "g = lambda *a: subprocess.run(['git', *a], capture_output=True).stdout.decode().strip()\n"
            "there = open('../there/f.txt').read().strip() if os.path.exists('../there') else ''\n"
            "said = [g('show', 'main:f.txt'), open('f.txt').read().strip(), g('remote'), there, p]\n"
            "print('Verdict: 1\\n\\nFindings\\n1. [note] ' + ' | '.join(said))\n",
        )
        run(self.repo, "init", "-q")
        case = dict(AUDIT, at=sha(self.origin), base=base, prompt="Audit Day 44.")
        case["beside"] = [{"repo": self.beside, "at": then, "as": "there"}]
        # main is the base, HEAD the draft, no remote, ../there at its commit, the prompt as given
        case["known"] = [
            {"id": "D44.6", "names": r"\] one \| the draft \|  \| then \| Audit Day 44\. .*Report"}
        ]
        self.cases = os.path.join(self.repo, "specs", "agent-cases", "spec-auditor.json")
        write(
            self.repo,
            "specs/agent-cases/spec-auditor.json",
            json.dumps(
                {
                    "kind": "audit",
                    "repo": self.origin,
                    "cases": [case, dict(RECHECK, at=base, base=base, prompt="x")],
                }
            ),
        )

    def test_each_case_is_read_at_its_draft_beside_its_repository_and_record_keeps_the_count(self):
        runner = [sys.executable, os.path.join(self.repo, "reply.py")]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = agent_cases.main(["spec-auditor", "--runs", "2", "--record"], self.repo, runner)
        lines = out.getvalue().splitlines()
        self.assertEqual(0, code, lines)
        self.assertRegex(lines[0], r"^spec-auditor: 2 cases, 2 runs, brief [0-9a-f]{7}$")
        self.assertEqual("Day 44 #9 audit, 1 known: 1, 1", lines[1])
        self.assertEqual("Day 44 #9 recheck, clean: none, none", lines[2])
        self.assertEqual("named: 1 of 1 name the known fault at worst (1, 1)", lines[3])
        state = os.path.join(self.repo, ".claude", "state", "agent-cases", "spec-auditor")
        # every case's checkout has the repository's name: each reply is kept all the same
        self.assertEqual(4, len(os.listdir(os.path.join(state, "replies"))))
        with open(os.path.join(state, "agents.json"), encoding="utf-8") as f:
            self.assertEqual("audit\n", json.load(f)["spec-auditor"]["prompt"])
        with open(self.cases, encoding="utf-8") as f:
            recorded = json.load(f)["recorded"]
        self.assertEqual({"named": 1, "clean": 1}, {k: recorded[k] for k in ("named", "clean")})


if __name__ == "__main__":
    unittest.main()
