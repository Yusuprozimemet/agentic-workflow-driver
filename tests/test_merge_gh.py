"""C13.3, C13.4 and C15.4: protection() says whether main requires a pull request and the kit's
nine checks, by name, from a source with no bypass, and merge() runs one `gh pr merge` on the
head it names and says when gh refuses. Each test runs the fake gh of tests/test_github.py beside a scratch project, and reads
back the arguments it was called with."""

import importlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_github import fake_gh, read_calls

SHA = "1dc0f03" + "a" * 33
# The kit's nine checks by job name, a literal: this file must import on main, where driver.github
# has no KIT_CHECKS yet.
KIT = (
    "Description uses the template",
    "Diff stays reviewable",
    "Branch, title, commits and Jira keys agree",
    "Frozen files stay unedited",
    "Dashboard metric tests gate",
    "Criteria keep their wording",
    "A closed day's evidence replays",
    "Track tests seen red",
    "A track's breaks replay",
)
CLASSIC = "repos/{owner}/{repo}/branches/main/protection"
RULES = "repos/{owner}/{repo}/rules/branches/main"
RULESET_7 = "repos/{owner}/{repo}/rulesets/7"
NOT_PROTECTED = {"code": 1, "out": "", "err": "gh: Branch not protected (HTTP 404)\n"}
REVIEWS = {"required_approving_review_count": 0}
CHECKS = {
    "contexts": [*KIT, "tests"],
    "checks": [{"context": name, "app_id": 1} for name in (*KIT, "tests")],
}
RULES_7 = [
    {"type": "pull_request", "ruleset_id": 7, "parameters": {}},
    {
        "type": "required_status_checks",
        "ruleset_id": 7,
        "parameters": {"required_status_checks": [{"context": name} for name in (*KIT, "tests")]},
    },
]


def ok(out):
    return {"code": 0, "out": out}


NO_RULES = ok([])


class GhCase(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top, as in GitHubTest: where driver/github.py lacks the
        # function, each test fails alone with AttributeError.
        self.github = importlib.import_module("driver.github")

    def scratch(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        return folder


class ProtectionTest(GhCase):
    def test_classic(self):
        folder = self.scratch()
        gh = fake_gh(
            folder,
            api={
                CLASSIC: ok(
                    {
                        "required_pull_request_reviews": REVIEWS,
                        "required_status_checks": CHECKS,
                        "enforce_admins": {"enabled": True},
                    }
                ),
                RULES: NO_RULES,
            },
        )
        self.assertIsNone(self.github.protection(str(folder), gh))

    def test_ruleset(self):
        folder = self.scratch()
        gh = fake_gh(
            folder,
            api={
                CLASSIC: NOT_PROTECTED,
                RULES: ok(RULES_7),
                RULESET_7: ok({"id": 7, "bypass_actors": []}),
            },
        )
        self.assertIsNone(self.github.protection(str(folder), gh))
        # Ruleset 7 is named by two rules and read once.
        self.assertEqual(read_calls(folder), [["api", CLASSIC], ["api", RULES], ["api", RULESET_7]])

    def test_bypass(self):
        folder = self.scratch()
        gh = fake_gh(
            folder,
            api={
                CLASSIC: ok(
                    {
                        "required_pull_request_reviews": REVIEWS,
                        "required_status_checks": CHECKS,
                        "enforce_admins": {"enabled": False},
                    }
                ),
                RULES: NO_RULES,
            },
        )
        reason = self.github.protection(str(folder), gh)
        # Compared up to the first name: a break that skips the bypass line reports the names it
        # misses instead, and its words differ at once.
        self.assertIsNotNone(reason)
        self.assertEqual(reason.split(' "')[0], "main allows a bypass")

    def test_checks_bypassable(self):
        folder = self.scratch()
        gh = fake_gh(
            folder,
            api={
                CLASSIC: ok(
                    {"required_status_checks": CHECKS, "enforce_admins": {"enabled": False}}
                ),
                RULES: ok([RULES_7[0]]),
                RULESET_7: ok({"id": 7, "bypass_actors": []}),
            },
        )
        self.assertEqual(self.github.protection(str(folder), gh), "main allows a bypass")

    def test_no_pull_request(self):
        folder = self.scratch()
        gh = fake_gh(folder, api={CLASSIC: NOT_PROTECTED, RULES: NO_RULES})
        self.assertEqual(
            self.github.protection(str(folder), gh), "main does not require a pull request"
        )

    def test_no_checks(self):
        folder = self.scratch()
        gh = fake_gh(
            folder,
            api={
                CLASSIC: ok(
                    {"required_pull_request_reviews": REVIEWS, "enforce_admins": {"enabled": True}}
                ),
                RULES: NO_RULES,
            },
        )
        self.assertEqual(
            self.github.protection(str(folder), gh), "main does not require its checks"
        )

    def test_hidden_bypass(self):
        folder = self.scratch()
        gh = fake_gh(
            folder,
            api={
                CLASSIC: NOT_PROTECTED,
                RULES: ok(RULES_7),
                RULESET_7: ok({"id": 7}),
            },
        )
        self.assertEqual(
            self.github.protection(str(folder), gh),
            "cannot read main's ruleset 7: bypass_actors not shown (needs admin)",
        )

    def test_gh_fails(self):
        folder = self.scratch()
        gh = fake_gh(
            folder,
            api={
                CLASSIC: ok(
                    {
                        "required_pull_request_reviews": REVIEWS,
                        "required_status_checks": CHECKS,
                        "enforce_admins": {"enabled": True},
                    }
                ),
                RULES: {"code": 1, "out": "", "err": "gh: Server Error (HTTP 500)\n"},
            },
        )
        self.assertEqual(self.github.protection(str(folder), gh), "gh api exited 1")

    def test_ruleset_bypass(self):
        # Beyond C13.3's cases (the track-reviewer's finding): a ruleset that names a bypass
        # actor requires nothing that counts.
        folder = self.scratch()
        gh = fake_gh(
            folder,
            api={
                CLASSIC: NOT_PROTECTED,
                RULES: ok(RULES_7),
                RULESET_7: ok({"id": 7, "bypass_actors": [{"actor_id": 5}]}),
            },
        )
        self.assertEqual(self.github.protection(str(folder), gh), "main allows a bypass")

    def test_classic_fails(self):
        # Beyond C13.3's cases: only a 404 on the classic call means "not protected"; any other
        # failure is a reason.
        folder = self.scratch()
        gh = fake_gh(
            folder,
            api={
                CLASSIC: {"code": 1, "out": "", "err": "gh: Forbidden (HTTP 403)\n"},
                RULES: ok(RULES_7),
                RULESET_7: ok({"id": 7, "bypass_actors": []}),
            },
        )
        self.assertEqual(self.github.protection(str(folder), gh), "gh api exited 1")


class MergeCallTest(GhCase):
    def test_merge_call(self):
        folder = self.scratch()
        gh = fake_gh(folder)
        self.assertIsNone(self.github.merge(str(folder), gh, 12, SHA))
        # The head is named by its place, so that a report holds no commit hash.
        calls = [["<head>" if arg == SHA else arg for arg in call] for call in read_calls(folder)]
        self.assertEqual(calls, [["pr", "merge", "12", "--merge", "--match-head-commit", "<head>"]])

    def test_merge_fails(self):
        folder = self.scratch()
        gh = fake_gh(folder, merge_code=1)
        self.assertEqual(self.github.merge(str(folder), gh, 12, SHA), "gh pr merge exited 1")
