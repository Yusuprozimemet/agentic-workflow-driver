"""scripts/case-count.py: a pull request that edits a brief with cases shows their count on it.

python scripts/test_case_count.py
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("case_count", os.path.join(HERE, "case-count.py"))
case_count = importlib.util.module_from_spec(spec)
spec.loader.exec_module(case_count)

CASED = {"rules/reviewer.md": "reviewer"}
SHOWN = (
    "## How to run\nreviewer: 8 cases, 3 runs, brief abc1234\n"
    "bearing#65 expects blocker: blocker, blocker, none\n"
    "verdict: 7 of 8 agree at worst (8, 7, 8)\n"
)


class MissingTest(unittest.TestCase):
    def test_a_changed_brief_with_its_count_on_this_brief_passes(self):
        self.assertEqual(
            [],
            case_count.missing(
                ["rules/reviewer.md"], CASED, {"rules/reviewer.md": "abc1234"}, SHOWN
            ),
        )

    def test_no_count_or_a_count_on_another_brief_fails(self):
        bodies = {
            "no count": "## How to run\nnothing\n",
            "another brief": SHOWN.replace("abc1234", "fff0000"),
            "no count line": SHOWN.split("bearing")[0],
        }
        for name, body in bodies.items():
            got = case_count.missing(
                ["rules/reviewer.md"], CASED, {"rules/reviewer.md": "abc1234"}, body
            )
            self.assertEqual(1, len(got), f"{name}: not refused")
            self.assertEqual(
                "rules/reviewer.md changed: paste what `python scripts/agent-cases.py reviewer`"
                " prints on it (its first line ends 'brief abc1234')",
                got[0],
            )

    def test_a_brief_with_no_cases_needs_nothing(self):
        self.assertEqual([], case_count.missing(["rules/session.md"], CASED, {}, ""))


CASES = {"agent": "reviewer", "brief": "rules/reviewer.md", "cases": [{"pr": 1}]}


class CasesStayTest(unittest.TestCase):
    """A brief's proposer never edits its cases in the same pull request."""

    def moved(self, after, changed=("rules/reviewer.md",), before=CASES):
        return case_count.cases_moved(list(changed), CASED, {"reviewer": (before, after)})

    def test_only_the_recorded_count_may_change_beside_the_brief(self):
        self.assertEqual([], self.moved(CASES))
        self.assertEqual([], self.moved(dict(CASES, recorded={"verdict": 3})))

    def test_a_case_added_or_rewritten_beside_its_brief_fails(self):
        for name, after in {
            "added": dict(CASES, cases=[{"pr": 1}, {"pr": 2}]),
            "rewritten": dict(CASES, cases=[{"pr": 9}]),
        }.items():
            got = self.moved(after)
            self.assertEqual(["specs/agent-cases/reviewer.json"], [m.split(":")[0] for m in got])
            self.assertEqual(
                [
                    (
                        "specs/agent-cases/reviewer.json: its cases changed in the PR that edits"
                        " rules/reviewer.md: a brief's proposer never edits its cases, so move"
                        " the case change to its own PR"
                    )
                ],
                got,
                name,
            )

    def test_a_case_file_in_the_agents_folder_counts_as_its_cases(self):
        got = self.moved(CASES, ("rules/reviewer.md", "specs/agent-cases/reviewer/day-1.md"))
        self.assertEqual(1, len(got))
        self.assertIn("specs/agent-cases/reviewer/day-1.md", got[0])

    def test_cases_alone_or_a_first_case_set_pass(self):
        self.assertEqual([], self.moved(dict(CASES, cases=[]), changed=()))
        self.assertEqual([], self.moved(CASES, before=None))


class RunTest(unittest.TestCase):
    """A scratch repository: main, then a branch that edits the brief."""

    def test_the_brief_changed_on_the_branch_needs_its_count(self):
        repo = tempfile.mkdtemp()
        git = [
            "git",
            "-C",
            repo,
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "-c",
            "core.autocrlf=false",
        ]

        def write(path, text):
            os.makedirs(os.path.dirname(os.path.join(repo, path)), exist_ok=True)
            with open(os.path.join(repo, path), "w", encoding="utf-8", newline="\n") as f:
                f.write(text)

        write("rules/reviewer.md", "brief\n")
        write(
            "specs/agent-cases/reviewer.json",
            json.dumps({"agent": "reviewer", "brief": "rules/reviewer.md"}),
        )
        subprocess.run(git + ["init", "-q", "-b", "main"], check=True)
        subprocess.run(git + ["add", "."], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "a"], check=True)
        write("rules/reviewer.md", "brief, edited\n")
        subprocess.run(git + ["commit", "-q", "-am", "b"], check=True)
        h = subprocess.run(
            git + ["rev-parse", "HEAD:rules/reviewer.md"], capture_output=True, check=True
        )
        body = os.path.join(repo, "body.md")
        cwd = os.getcwd()
        os.chdir(repo)
        try:
            for text, code in (
                ("nothing\n", 1),
                (SHOWN.replace("abc1234", h.stdout.decode()[:7]), 0),
            ):
                write("body.md", text)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(code, case_count.main(["HEAD~1", "HEAD", "--body", body]))
        finally:
            os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
