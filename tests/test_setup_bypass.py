"""The bypass line of scripts/setup-check.py: no one may bypass the rules on `main`, by classic
protection's enforce_admins or by a ruleset whose bypass_actors is empty. Checks C10.27 (classic
enforce_admins) and C10.28 (ruleset bypass_actors) from a fake gh, with no network."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "me/project"
PROTECTION = "repos/me/project/branches/main/protection"
RULES = "repos/me/project/rules/branches/main"
RULESET = "repos/me/project/rulesets/7"
OK = ("ok", "main: no one may bypass the rules")
FAIL = (
    "FAIL",
    'main: administrators may bypass the rules; turn on "Do not allow bypassing the above settings"',
)


def load_setup_check():
    spec = importlib.util.spec_from_file_location(
        "setup_check", ROOT / "scripts" / "setup-check.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


setup_check = load_setup_check()


def fake(answers):
    """A gh answering each path from answers; a path not in it answers 500, so the test fails by its line."""
    return lambda path: answers.get(path, (500, ["(HTTP 500)"]))


class BypassTest(unittest.TestCase):
    def check(self, answers, expected):
        lines = setup_check.protection_lines(REPO, fake(answers))
        self.assertEqual(len(lines), len(setup_check.REQUIRED) + 3)
        self.assertTrue(lines[0][1].startswith("main: a pull request before merging"))
        self.assertEqual(lines[1], expected)

    def test_classic_enforce_admins(self):
        off = {"required_pull_request_reviews": {}, "enforce_admins": {"enabled": False}}
        on = {"required_pull_request_reviews": {}, "enforce_admins": {"enabled": True}}
        cases = {
            "enforce_admins off": ({PROTECTION: (200, off), RULES: (200, [])}, FAIL),
            "enforce_admins on": ({PROTECTION: (200, on), RULES: (200, [])}, OK),
            "classic protection missing": (
                {PROTECTION: (404, ["gh: Branch not protected (HTTP 404)"]), RULES: (200, [])},
                FAIL,
            ),
        }
        for name, (answers, expected) in cases.items():
            with self.subTest(name):
                self.check(answers, expected)

    def test_ruleset_bypass_actors(self):
        rules = (200, [{"type": "pull_request", "ruleset_id": 7, "parameters": {}}])
        actor = {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}
        cases = {
            "no bypass actors": ((200, {"id": 7, "bypass_actors": []}), OK),
            "a bypass actor": ((200, {"id": 7, "bypass_actors": [actor]}), FAIL),
            "bypass_actors not shown": (
                (200, {"id": 7}),
                ("FAIL", "main's ruleset 7: cannot read: bypass_actors not shown (needs admin)"),
            ),
            "ruleset unreadable": (
                (403, ["gh: Must have admin rights (HTTP 403)"]),
                ("FAIL", "main's ruleset 7: cannot read: no permission (needs admin)"),
            ),
        }
        for name, (ruleset, expected) in cases.items():
            with self.subTest(name):
                self.check(
                    {PROTECTION: (404, ["(HTTP 404)"]), RULES: rules, RULESET: ruleset}, expected
                )


if __name__ == "__main__":
    unittest.main()
