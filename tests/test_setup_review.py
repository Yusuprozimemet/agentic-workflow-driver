"""scripts/setup-check.py asks for no required review: one maintainer cannot approve their own
pull request, so CI's required checks and the auditors are the merge gate (#211, N2 and N3).
From a fake gh, with no network."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "me/project"
PROTECTION = "repos/me/project/branches/main/protection"
RULES = "repos/me/project/rules/branches/main"


def load_setup_check():
    spec = importlib.util.spec_from_file_location(
        "setup_check", ROOT / "scripts" / "setup-check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


setup_check = load_setup_check()


def protection(**extra):
    contexts = list(setup_check.REQUIRED) + ["tests"]
    body = {"required_status_checks": {"contexts": contexts}, "enforce_admins": {"enabled": True}}
    body.update(extra)
    answers = {PROTECTION: (200, body), RULES: (200, [])}
    return lambda path: answers.get(path, (500, ["(HTTP 500)"]))


class NoReviewTest(unittest.TestCase):
    def test_no_review_rule_passes(self):
        lines = setup_check.protection_lines(REPO, protection())
        self.assertEqual([line for line in lines if line[0] != "ok"], [])
        self.assertEqual(len(lines), len(setup_check.REQUIRED) + 2)

    def test_a_review_rule_changes_nothing(self):
        without = setup_check.protection_lines(REPO, protection())
        with_review = setup_check.protection_lines(
            REPO, protection(required_pull_request_reviews={"required_approving_review_count": 0})
        )
        self.assertEqual(with_review, without)


if __name__ == "__main__":
    unittest.main()
