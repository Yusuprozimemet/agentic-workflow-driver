"""Day 15's kit checks by name (C15.1 to C15.5): protection() requires the kit's nine checks by job
name from a source with no bypass, names the ones missing, lets a waived name pass, counts a ruleset's
names, and reads the same nine from scripts/setup-check.py. Each test runs the fake gh of
tests/test_github.py beside a scratch project, as tests/test_merge_gh.py does."""

import importlib.util
import re
import subprocess

from tests.test_github import fake_gh
from tests.test_merge_gh import (
    CLASSIC,
    KIT,
    NO_RULES,
    NOT_PROTECTED,
    REVIEWS,
    ROOT,
    RULES,
    RULES_7,
    RULESET_7,
    GhCase,
    ok,
)


def classic(contexts, checks=(), admins=True, pr=True):
    # Classic protection with the given required contexts and checks; pr=False leaves out the pull
    # request reviews, and admins is what enforce_admins says.
    body = {
        "required_status_checks": {
            "contexts": list(contexts),
            "checks": [{"context": name, "app_id": 1} for name in checks],
        },
        "enforce_admins": {"enabled": admins},
    }
    if pr:
        body["required_pull_request_reviews"] = REVIEWS
    return ok(body)


class KitChecksTest(GhCase):
    def missing(self, reason, names):
        # The reason's own words, in order, then the names in quotes: a break's report names what it
        # reached in short, fixed words (the spec's rule on long reports).
        self.assertIsNotNone(reason)
        self.assertEqual(reason.split(' "')[0], "main does not require")
        found = re.findall(r'"([^"]*)"', reason)
        self.assertEqual(len(found), len(names))
        self.assertEqual(found, list(names))
        self.assertEqual(reason, "main does not require " + ", ".join(f'"{n}"' for n in names))

    def test_only_the_projects_tests(self):
        # C15.1: the project's own tests are not one of the kit's nine, so the nine are all missing.
        folder = self.scratch()
        gh = fake_gh(folder, api={CLASSIC: classic(["tests"], ["tests"]), RULES: NO_RULES})
        reason = self.github.protection(str(folder), gh)
        self.missing(reason, KIT)

    def test_one_missing(self):
        # C15.1: eight of the nine named as contexts, the ninth absent, so only it is named.
        folder = self.scratch()
        gh = fake_gh(
            folder,
            api={CLASSIC: classic([*KIT[:8], "tests"]), RULES: NO_RULES},
        )
        reason = self.github.protection(str(folder), gh)
        self.missing(reason, ["A track's breaks replay"])

    def test_waived(self):
        # C15.2: a waived name is not missing; a waiver for a name that is required changes nothing.
        folder = self.scratch()
        gh = fake_gh(
            folder,
            api={CLASSIC: classic([*KIT[:8], "tests"]), RULES: NO_RULES},
        )
        self.assertIsNone(
            self.github.protection(str(folder), gh, waived=("A track's breaks replay",))
        )
        self.missing(
            self.github.protection(str(folder), gh, waived=("Track tests seen red",)),
            ["A track's breaks replay"],
        )

    def test_bypassable_check(self):
        # C15.3: the classic protection names the check but lets admins bypass it, and the ruleset
        # names the other eight. A name counts only from a source with no bypass.
        folder = self.scratch()
        gh = fake_gh(
            folder,
            api={
                CLASSIC: classic(["Frozen files stay unedited"], admins=False, pr=False),
                RULES: ok(
                    [
                        {"type": "pull_request", "ruleset_id": 7, "parameters": {}},
                        {
                            "type": "required_status_checks",
                            "ruleset_id": 7,
                            "parameters": {
                                "required_status_checks": [
                                    {"context": name}
                                    for name in KIT
                                    if name != "Frozen files stay unedited"
                                ]
                            },
                        },
                    ]
                ),
                RULESET_7: ok({"id": 7, "bypass_actors": []}),
            },
        )
        reason = self.github.protection(str(folder), gh)
        self.missing(reason, ["Frozen files stay unedited"])

    def test_ruleset_names(self):
        # C15.4 (hold): a ruleset's required checks count by their names, as the nine do in RULES_7.
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

    def test_classic_forms(self):
        # C15.4 (hold): the nine split between the classic contexts and checks count the same.
        folder = self.scratch()
        gh = fake_gh(
            folder,
            api={CLASSIC: classic(KIT[:5], KIT[5:]), RULES: NO_RULES},
        )
        self.assertIsNone(self.github.protection(str(folder), gh))

    def test_the_kits_nine(self):
        # C15.5: driver/github.py holds the kit's nine as scripts/setup-check.py does, and no file
        # under driver/ names the setup-check script, so the driver does not depend on it.
        spec = importlib.util.spec_from_file_location(
            "setup_check", ROOT / "scripts" / "setup-check.py"
        )
        setup_check = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup_check)
        kit = self.github.KIT_CHECKS
        self.assertEqual(kit, setup_check.REQUIRED)
        done = subprocess.run(
            ["git", "grep", "-n", "-e", "setup-check", "-e", "setup_check", "--", "driver"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, 1, done.stdout)
