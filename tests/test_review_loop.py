"""The reviewer in `on` (driver/once.py, driver/review.py): C12.11's review key in driver.json, and
C12.12 to C12.19, C12.22 and C12.23 on the run. The reviewer is the case's second claude call, after the
step's, from tests/fake_review.py; in the container it is the second docker run, from tests/fake_docker.py.
A report holds no head, no state folder and no session uuid: the placeholders stand in for them."""

import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests import test_box_preflight as preflight
from tests import test_box_session as box_session
from tests.fake_review import fake_review
from tests.test_dry_run import drift_of
from tests.test_github import read_bodies
from tests.test_merge_wait import run as run_answer
from tests.test_merge_wait import view
from tests.test_on import GREEN, RED, OnCase
from tests.test_once import DASHED, STEP_PR

# Forty hex characters, as a commit hash is: the head the pull request and the project report.
HEAD = "c0ffee" * 6 + "c0ff"
# The reviewer's session in the container; the step's is box_session.U.
R = "00000000-0000-4000-8000-000000000020"
REVIEW_ONLY = "found: advice — a word\nREVIEW: none"
BLOCKER_ONLY = "found: blocker — no test\nREVIEW: blocker"
NONE_ONLY = "REVIEW: none"
NIGHT = "on: 1 steps, the night's count"
# The reviewer's do: a commit in the project, and a file nothing commits.
COMMIT = (
    "import subprocess\n"
    "subprocess.run(['git', '-c', 'user.name=x', '-c', 'user.email=x@x', 'commit', '--allow-empty', "
    "'-m', 'x'], check=True, capture_output=True)\n"
)
UNTRACKED = "from pathlib import Path\nPath('untracked.txt').write_bytes(b'x')\n"
# The fake git of test_snapshot_git_fails: status fails, every other call is the real git's.
GIT_SCRIPT = """import subprocess
import sys

if sys.argv[1:2] == ["status"]:
    sys.exit(1)
done = subprocess.run([{real}, *sys.argv[1:]], capture_output=True, check=False)
sys.stdout.buffer.write(done.stdout)
sys.stderr.buffer.write(done.stderr)
sys.exit(done.returncode)
"""


def value_of(args, flag):
    # The word after flag; None when flag is absent or is the last word, so a check fails, not raises.
    if flag not in args or args.index(flag) + 1 >= len(args):
        return None
    return args[args.index(flag) + 1]


def rewrite(path, **changes):
    # A JSON file read as bytes, changed and written as bytes: text mode would add a carriage return.
    spec = json.loads(path.read_bytes())
    spec.update(changes)
    path.write_bytes(json.dumps(spec).encode("utf-8"))


def without_at(record):
    return {key: value for key, value in record.items() if key != "at"}


# Shared by the two classes below; not a TestCase, so that importing it collects no tests.
def same(test, found, expected):
    """assertEqual that names what differs in short, fixed words: the fields of a tuple by place,
    the keys of a dict, so a break's report replays the same on every machine (break.py refuses
    unittest's shortened [N chars]; #211, S21)."""
    if found == expected:
        return
    if isinstance(found, dict) and isinstance(expected, dict):
        bad = sorted(str(k) for k in set(found) | set(expected) if found.get(k) != expected.get(k))
    elif isinstance(found, (tuple, list)) and isinstance(expected, (tuple, list)):
        bad = [str(i) for i, (a, b) in enumerate(zip(found, expected)) if a != b]
        if len(found) != len(expected):
            bad.append(f"length {len(found)} for {len(expected)}")
    else:
        bad = ["the value"]
    test.fail("differs: " + ", ".join(bad or ["the type"]))


class ReviewCase(OnCase):
    def review(self, name, replies, views=None, comment_code=0, steps=1, **build):
        # The case's project and fake claude; fake_review writes the program at the path build gave, so
        # the --claude flag already names it. build takes checks and drift for a test that needs them.
        self.build(name, steps=steps, **build)
        program = fake_review(self.folder / "claude", replies)
        assert program in self.flags, "the --claude flag does not name the fake's program"
        self.reviewed(views=views, comment_code=comment_code)

    def reviewed(self, views=None, comment_code=0):
        # The step opens #12; the pull request is read as the views say, and review is on in driver.json.
        rewrite(
            self.folder / "gh" / "fake.json",
            prs=[{**STEP_PR, "number": 12}],
            views=views or [view("OPEN", head=HEAD), view("MERGED", head=HEAD)],
            comment_code=comment_code,
        )
        rewrite(self.folder / "driver.json", review=True)

    def run_log(self):
        # The run log's records, none when the driver wrote none.
        path = self.state / "run.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_bytes().splitlines()]

    def reviewer_ids(self):
        # The --session-id of each session that ran the reviewer, in the order they ran.
        return [
            value_of(call["args"], "--session-id")
            for call in self.sessions()
            if value_of(call["args"], "--agent") == "reviewer"
        ]

    def uuids(self):
        # The step's session uuid and the reviewer's, as the sessions give them; "" when there is none.
        steps = [
            value_of(call["args"], "--session-id")
            for call in self.sessions()
            if value_of(call["args"], "--agent") is None
        ]
        reviewers = self.reviewer_ids()
        return (steps[:1] + [""])[0], (reviewers[:1] + [""])[0]

    def hold(self, text, step="", reviewer=""):
        # The placeholders a report holds: the state folder as the driver spells it or as realpath does,
        # the head, and the two uuids. An empty uuid is not replaced: "" matches between every letter.
        for form in sorted({str(self.state), os.path.realpath(self.state)}, key=len, reverse=True):
            text = text.replace(form, "<state>")
        text = text.replace(HEAD, "<head>")
        if reviewer:
            text = text.replace(reviewer, "<uuid>")
        if step:
            text = text.replace(step, "<step-uuid>")
        return text

    def placed(self, record, step, reviewer):
        # A run log record with its strings held and its at left out, which varies from run to run.
        return {
            key: self.hold(value, step, reviewer) if isinstance(value, str) else value
            for key, value in without_at(record).items()
        }

    def pr_bodies(self):
        # The bodies the fake gh was given for `pr comment`; none when it was given none.
        if not (self.folder / "gh" / "bodies.jsonl").exists():
            return []
        bodies = read_bodies(self.folder / "gh")
        return [record["body"] for record in bodies if record["args"][:2] == ["pr", "comment"]]


class ReviewConfigTest(unittest.TestCase):
    def test_review_key(self):
        # C12.11: review must be true or false when it is there; a value that is not gives one line.
        config = importlib.import_module("driver.config")
        base = {"project": "project", "human_only": [], "budget_usd": 5, "steps_per_night": 1}
        cases = (
            ("yes", {"review": "yes"}),
            ("true", {"review": True}),
            ("false", {"review": False}),
            ("absent", {}),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "driver.json"
            found = {}
            for name, extra in cases:
                path.write_bytes(json.dumps({**base, **extra}).encode("utf-8"))
                loaded, lines = config.load(path)
                lines = [line.replace(str(path), "<path>") for line in lines]
                found[name] = (loaded is None, lines)
        same(
            self,
            found,
            {
                "yes": (True, ["cannot start: <path>'s review must be true or false"]),
                "true": (False, []),
                "false": (False, []),
                "absent": (False, []),
            },
        )


class ReviewLoopTest(ReviewCase, unittest.TestCase):
    # The driver run in-process, for the case that patches the snapshot; hidden() reads <secrets>.
    run_steps = preflight.BoxPreflightTest.run_steps
    hidden = preflight.BoxPreflightTest.hidden

    def test_reviewed_then_merge_wait(self):
        # C12.12: the reviewer is a second session with its own uuid, reads the pull request's head, and
        # its verdict is one comment and one review line; the run goes on to the merge.
        self.review("reviewed", [{"text": REVIEW_ONLY, "cost": 0.25}])
        code, out, _ = self.on()
        step, reviewer = self.uuids()
        sessions = self.sessions()
        second = sessions[1] if len(sessions) > 1 else {"args": [], "stdin": ""}
        log = self.run_log()
        step_start = [r for r in log if r.get("event") == "start" and r.get("session") == step]
        review_start = [
            r for r in log if r.get("event") == "start" and r.get("session") == reviewer
        ]
        reviewer_end = [r for r in log if r.get("event") == "end" and r.get("session") == reviewer]
        review_lines = [r for r in log if r.get("event") == "review"]
        order = [r.get("event") for r in log if r.get("event") in ("review", "merged")]
        step_issue = step_start[0].get("issue") if step_start else None
        review_issue = review_start[0].get("issue") if review_start else None
        tail = [self.hold(arg, step, reviewer).replace("\\", "/") for arg in second["args"][-6:]]
        settings = self.hold(value_of(second["args"], "--settings") or "", step, reviewer)
        prompt = bytes.fromhex(second["stdin"]).decode("utf-8").splitlines()[:1]
        same(
            self,
            (
                code,
                self.hold(out, step, reviewer).splitlines()[-1:],
                len(sessions),
                tail,
                settings.replace("\\", "/"),
                "--append-system-prompt-file" in second["args"],
                bool(reviewer) and reviewer != step,
                [self.hold(line, step, reviewer) for line in prompt],
            ),
            (
                0,
                [NIGHT],
                2,
                [
                    "--agents",
                    "<state>/agents.json",
                    "--agent",
                    "reviewer",
                    "--session-id",
                    "<uuid>",
                ],
                "<state>/review-settings.json",
                False,
                True,
                [f"Review pull request #12 at commit <head>, for the step: {DASHED}."],
            ),
        )
        same(
            self,
            (
                self.gh_of("pr", "comment"),
                [self.hold(body, step, reviewer) for body in self.pr_bodies()],
            ),
            (
                [["pr", "comment", "12", "--body-file", "-"]],
                [f"review of `<head>` (session `<uuid>`):\n{REVIEW_ONLY}"],
            ),
        )
        same(
            self,
            (
                [r.get("prefix") for r in review_start],
                isinstance(step_issue, int),
                review_issue == step_issue,
                [r.get("cost_usd") for r in reviewer_end],
                [r.get("outcome") for r in reviewer_end],
                [isinstance(r.get("at"), str) for r in review_lines],
                [self.placed(r, step, reviewer) for r in review_lines],
                order,
                [r.get("pr") for r in log if r.get("event") == "merged"],
            ),
            (
                ["review"],
                True,
                True,
                [0.25],
                ["review: #12, 0 blockers"],
                [True],
                [
                    {
                        "event": "review",
                        "pr": 12,
                        "session": "<uuid>",
                        "head": "<head>",
                        "blockers": 0,
                    }
                ],
                ["review", "merged"],
                [12],
            ),
        )

    def test_change_parks(self):
        # C12.16: a reviewer that changes the project parks before any comment; the reviewer's end line is
        # written, and no review or merged line is.
        cases = (
            (
                "committed",
                COMMIT,
                "park: the reviewer changed HEAD in the project on #12 (session `<uuid>`)",
            ),
            (
                "untracked",
                UNTRACKED,
                "park: the reviewer changed `git status` in the project on #12 (session `<uuid>`)",
            ),
        )
        for name, do, line in cases:
            with self.subTest(case=name):
                self.review(name, [{"text": "REVIEW: none", "do": do}])
                code, out, _ = self.on()
                step, reviewer = self.uuids()
                log = self.run_log()
                self.assertEqual(
                    (
                        code,
                        line in self.hold(out, step, reviewer),
                        self.gh_of("pr", "comment"),
                        [r.get("event") for r in log if r.get("event") in ("review", "merged")],
                        any(r.get("event") == "end" and r.get("session") == reviewer for r in log),
                    ),
                    (1, True, [], [], True),
                )

    def test_no_verdict_parks(self):
        # C12.17: a reply the driver cannot read, or a session that errors, parks with no comment.
        cases = (
            ("looks_fine", {"text": "looks fine"}),
            ("errored", {"text": REVIEW_ONLY, "is_error": True}),
        )
        for name, reply in cases:
            with self.subTest(case=name):
                self.review(name, [reply])
                code, out, _ = self.on()
                step, reviewer = self.uuids()
                line = "park: the reviewer gave no verdict on #12 (session `<uuid>`)"
                self.assertEqual(
                    (code, line in self.hold(out, step, reviewer), self.gh_of("pr", "comment")),
                    (1, True, []),
                )

    def test_comment_failure_goes_on(self):
        # C12.18: a failed comment is a line, and the run goes on: the verdict is in the run log and the
        # merge is waited on.
        self.review("comment_fails", [{"text": REVIEW_ONLY}], comment_code=1)
        _, out, _ = self.on()
        step, reviewer = self.uuids()
        prefix = "review: no comment on #12: "
        lines = self.hold(out, step, reviewer).splitlines()
        reasons = [line[len(prefix) :] for line in lines if line.startswith(prefix)]
        log = self.run_log()
        same(
            self,
            (
                [bool(reason.strip()) for reason in reasons],
                [r.get("event") for r in log if r.get("event") in ("review", "merged")],
                [r.get("pr") for r in log if r.get("event") == "merged"],
            ),
            ([True], ["review", "merged"], [12]),
        )

    def test_merged_before_review(self):
        # C12.23: a pull request merged before its review starts no reviewer session.
        self.review("merged_first", [{"text": REVIEW_ONLY}], views=[view("MERGED", head=HEAD)])
        code, out, _ = self.on()
        step, reviewer = self.uuids()
        log = self.run_log()
        self.assertEqual(
            (
                code,
                self.hold(out, step, reviewer).splitlines()[-1:],
                len(self.sessions()),
                len(self.reviewer_ids()),
                self.gh_of("pr", "comment"),
                [r.get("event") for r in log if r.get("event") in ("review", "merged")],
            ),
            (0, [NIGHT], 1, 0, [], ["merged"]),
        )

    def test_snapshot_git_fails(self):
        # C12.22: a git whose status fails stops the run with code 2, before any reviewer.
        self.review("git_fails", [{"text": REVIEW_ONLY}])
        self.secrets = self.folder / "secrets.env"
        script = self.folder / "git.py"
        real = shutil.which("git") or "git"
        script.write_bytes(GIT_SCRIPT.format(real=repr(real)).encode("utf-8"))
        review = importlib.import_module("driver.review")
        original = review.snapshot

        def through_fake_git(project, git=("git",)):
            return original(project, git=(sys.executable, str(script)))

        with mock.patch.object(review, "snapshot", side_effect=through_fake_git):
            code, _, err = self.run_steps("on")
        step, reviewer = self.uuids()
        message = "cannot read the project: git failed before the review of #12"
        same(
            self,
            (
                code,
                message in self.hold(err, step, reviewer),
                len(self.sessions()),
                len(self.reviewer_ids()),
            ),
            (2, True, 1, 0),
        )

    def test_blocker_resumes_the_step(self):
        # C12.13: a blocker resumes the step's session, which opens its fix; the reviewer runs again on the
        # fixed pull request, and its verdict of none lets the merge be waited on.
        self.review(
            "blocker_fixed",
            [{"text": BLOCKER_ONLY}, {"text": NONE_ONLY}],
            views=[view("OPEN", head=HEAD), view("OPEN", head=HEAD), view("MERGED", head=HEAD)],
        )
        code, out, _ = self.on()
        step, reviewer = self.uuids()
        sessions = self.sessions()
        resumed = sessions[2] if len(sessions) > 2 else {"args": [], "stdin": ""}
        log = self.run_log()
        fix_at = [i for i, r in enumerate(log) if r.get("event") == "fix"]
        review_at = [i for i, r in enumerate(log) if r.get("event") == "review"]
        kinds = [
            "reviewer"
            if "--agent" in call["args"]
            else "resume"
            if "--resume" in call["args"]
            else "step"
            for call in sessions
        ]
        self.assertEqual(
            (
                code,
                self.hold(out, step, reviewer).splitlines()[-1:],
                kinds,
                self.hold(value_of(resumed["args"], "--resume") or "", step, reviewer),
                "--agent" in resumed["args"],
                self.hold(bytes.fromhex(resumed["stdin"]).decode("utf-8"), step, reviewer),
                len(set(self.reviewer_ids())),
                step in self.reviewer_ids(),
                [(r.get("pr"), r.get("n")) for r in log if r.get("event") == "fix"],
                [
                    self.hold(str(r.get("session")), step, reviewer)
                    for r in log
                    if r.get("event") == "fix"
                ],
                bool(fix_at) and len(review_at) > 1 and fix_at[0] < review_at[1],
                [r.get("blockers") for r in log if r.get("event") == "review"],
                [r.get("event") for r in log if r.get("event") in ("review", "fix", "merged")],
                len(self.gh_of("pr", "checks")) > 1,
            ),
            (
                0,
                [NIGHT],
                ["step", "reviewer", "resume", "reviewer"],
                "<step-uuid>",
                False,
                (
                    "The reviewer found a blocker on #12:\nfound: blocker — no test\n"
                    "Fix this step's pull request, push, and stop.\n"
                ),
                2,
                False,
                [(12, 1)],
                ["<step-uuid>"],
                True,
                [1, 0],
                ["review", "fix", "review", "merged"],
                True,
            ),
        )

    def test_blocker_park_after_two_fixes(self):
        # C12.14: a reviewer that still finds a blocker after two fixes parks the run; no merge is waited on.
        self.review(
            "blocker_parks",
            [{"text": BLOCKER_ONLY}],
            views=[
                view("OPEN", head=HEAD),
                view("OPEN", head=HEAD),
                view("OPEN", head=HEAD),
                view("MERGED", head=HEAD),
            ],
        )
        code, out, _ = self.on()
        step, reviewer = self.uuids()
        log = self.run_log()
        self.assertEqual(
            (
                code,
                self.hold(out, step, reviewer).splitlines()[-1:],
                len(self.sessions()),
                [r.get("n") for r in log if r.get("event") == "fix"],
                len([r for r in log if r.get("event") == "review"]),
                [r for r in log if r.get("event") == "merged"],
            ),
            (
                1,
                ["park: the reviewer still has a blocker on #12 after two fixes"],
                6,
                [1, 2],
                3,
                [],
            ),
        )

    def test_fixes_shared_with_red_checks(self):
        # C12.14: the red check and the reviewer's blocker share the two fixes: the first goes to the red
        # check, the second to the blocker, and the blocker after them parks the run.
        self.review(
            "shared",
            [{"text": BLOCKER_ONLY}],
            views=[view("OPEN", head=HEAD), view("OPEN", head=HEAD), view("MERGED", head=HEAD)],
            checks=[RED, GREEN],
        )
        code, out, _ = self.on()
        step, reviewer = self.uuids()
        resumed = [call for call in self.sessions() if "--resume" in call["args"]]
        prompts = [
            self.hold(bytes.fromhex(call["stdin"]).decode("utf-8"), step, reviewer)
            for call in resumed
        ]
        starts = [
            "The required checks failed on #12: tests.",
            "The reviewer found a blocker on #12:",
        ]
        log = self.run_log()
        self.assertEqual(
            (
                code,
                self.hold(out, step, reviewer).splitlines()[-1:],
                [r.get("n") for r in log if r.get("event") == "fix"],
                [prompt.startswith(start) for prompt, start in zip(prompts, starts)],
                len(self.sessions()),
                len([r for r in log if r.get("event") == "review"]),
            ),
            (
                1,
                ["park: the reviewer still has a blocker on #12 after two fixes"],
                [1, 2],
                [True, True],
                5,
                2,
            ),
        )

    def test_found_pr_blocker_parks(self):
        # C12.15: a pull request open at the start, with no session of this run, is reviewed; a blocker
        # parks the run, since there is no step session to resume.
        self.review(
            "found_blocker",
            [{"text": BLOCKER_ONLY}],
            views=[view("OPEN", head=HEAD), view("MERGED", head=HEAD)],
            drift=drift_of(DASHED, open_prs=(12,)),
            # The evidence run closes the run's issue, so that a run that merges #12 ends (with off).
            run_steps=[{**run_answer("completed", "success"), "closes": [1]}],
        )
        code, out, _ = self.on()
        step, reviewer = self.uuids()
        sessions = self.sessions()
        log = self.run_log()
        lines = self.hold(out, step, reviewer).splitlines()
        self.assertEqual(
            (
                code,
                "wait: #12" in lines,
                lines[-1:],
                [value_of(call["args"], "--agent") for call in sessions],
                len([call for call in sessions if "--resume" in call["args"]]),
                len([r for r in log if r.get("event") == "fix"]),
                [r.get("blockers") for r in log if r.get("event") == "review"],
            ),
            (
                1,
                True,
                ["park: the reviewer has a blocker on #12: no test"],
                ["reviewer"],
                0,
                0,
                [1],
            ),
        )


class ReviewBoxTest(ReviewCase, unittest.TestCase):
    # BoxSessionTest's container helpers and BoxPreflightTest's in-process runner, by assignment.
    box = box_session.BoxSessionTest.box
    hidden = box_session.BoxSessionTest.hidden
    plain = box_session.BoxSessionTest.plain
    named = box_session.BoxSessionTest.named
    names = box_session.BoxSessionTest.names
    run_steps = preflight.BoxPreflightTest.run_steps

    def test_reviewer_in_the_container(self):
        # C12.19: the reviewer's docker run has its own name, settings and agent, and the files it reads
        # are in the state folder before it starts.
        reviewer_answer = json.dumps(
            {"type": "result", "is_error": False, "result": "REVIEW: none", "session_id": R}
        )
        self.box(
            "boxed",
            run=[
                {
                    "tail": ["--session-id", box_session.U],
                    "stdout": box_session.result(box_session.U),
                },
                {"tail": ["--session-id", R], "stdout": reviewer_answer},
            ],
            steps=1,
        )
        self.reviewed()

        def uuids():
            # The step's uuid first, then the reviewer's for every later call.
            yield uuid.UUID(box_session.U)
            while True:
                yield uuid.UUID(R)

        with mock.patch("uuid.uuid4", side_effect=uuids().__next__):
            code, _, _ = self.run_steps("on")
        # The image's probe is named too; the step's run and the reviewer's are the two that count here.
        names = [name.replace(R, "<uuid>") for name in self.names() if "-probe-" not in name]
        reviewer_runs = self.named(f"driver-{R}")
        run = [arg.replace(R, "<uuid>") for arg in reviewer_runs[0]] if reviewer_runs else []
        same(
            self,
            (
                code,
                len(names),
                names[:1],
                names[-1:],
                value_of(run, "--settings"),
                run[-6:],
                (self.state / "agents.json").exists(),
                (self.state / "review-container-settings.json").exists(),
            ),
            (
                0,
                2,
                ["driver-<uuid>"],
                ["driver-<uuid>"],
                "/state/review-container-settings.json",
                [
                    "--agents",
                    "/state/agents.json",
                    "--agent",
                    "reviewer",
                    "--session-id",
                    "<uuid>",
                ],
                True,
                True,
            ),
        )
