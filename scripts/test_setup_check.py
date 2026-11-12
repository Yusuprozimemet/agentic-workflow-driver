"""scripts/setup-check.py reports each setup item a copied kit needs, from a fake gh.

The fake answers `gh api` paths as GitHub does: 404 for an unprotected branch or an unset
variable, `[]` for a branch no ruleset covers. The last tests tie the script's lists to what
they copy: the workflows' job names, the README's protection rule, and track-red.py's runners.

    python scripts/test_setup_check.py
"""
import importlib.util
import json
import os
import re
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


setup_check = load("setup_check", "setup-check.py")
REPO = "me/project"
PROJECT_TESTS = "Tests pass"


def fake(**answers):
    """A gh_api answering a set-up repository, with each keyword replacing one path's answer."""
    paths = {
        "protection": (200, {"required_status_checks": {"contexts": list(setup_check.REQUIRED) + [PROJECT_TESTS]},
                             "required_pull_request_reviews": {}, "enforce_admins": {"enabled": True}}),
        "rules": (200, []),
        "ruleset": (200, {"id": 7, "bypass_actors": []}),
        "variable": (200, {"name": "TRACK_RED_RUNNER", "value": "pytest"}),
        "shared": (200, {"total_count": 0, "variables": []}),
        "pages": (200, {"build_type": "workflow", "html_url": "https://me.github.io/project/"}),
    }
    paths.update(answers)
    keys = {f"repos/{REPO}/branches/main/protection": "protection", f"repos/{REPO}/rules/branches/main": "rules",
            f"repos/{REPO}/rulesets/7": "ruleset",
            f"repos/{REPO}/actions/variables/TRACK_RED_RUNNER": "variable",
            f"repos/{REPO}/actions/organization-variables": "shared", f"repos/{REPO}/pages": "pages"}
    return lambda path: paths[keys[path]]


def failed(lines):
    return [text for state, text in lines if state == "FAIL"]


class ProtectionTest(unittest.TestCase):
    def test_a_set_up_repository_passes_every_item(self):
        lines = setup_check.report(REPO, fake(), files=[])
        self.assertEqual(failed(lines), [])
        self.assertIn(("ok", 'main requires "A closed day\'s evidence replays"'), lines)
        self.assertIn(("ok", f'main requires the project\'s tests: "{PROJECT_TESTS}"'), lines)

    def test_an_unprotected_main_fails_each_required_check_by_name(self):
        lines = setup_check.protection_lines(REPO, fake(protection=(404, ["gh: Branch not protected (HTTP 404)"])))
        self.assertEqual(len(failed(lines)), len(setup_check.REQUIRED) + 3)
        self.assertIn('main requires "A closed day\'s evidence replays": not required', failed(lines))
        self.assertIn("main: a pull request before merging: not required", failed(lines))

    def test_one_missing_check_fails_that_line_alone(self):
        contexts = [c for c in setup_check.REQUIRED if c != "Track tests seen red"] + [PROJECT_TESTS]
        lines = setup_check.protection_lines(REPO, fake(protection=(200, {
            "required_status_checks": {"contexts": contexts}, "required_pull_request_reviews": {},
            "enforce_admins": {"enabled": True}})))
        self.assertEqual(failed(lines), ['main requires "Track tests seen red": not required'])

    def test_a_ruleset_protects_main_as_well_as_classic_protection(self):
        rules = [{"type": "pull_request", "ruleset_id": 7, "parameters": {}},
                 {"type": "required_status_checks", "parameters": {"required_status_checks": [
                     {"context": c} for c in setup_check.REQUIRED + (PROJECT_TESTS,)]}}]
        lines = setup_check.protection_lines(REPO, fake(protection=(404, ["(HTTP 404)"]), rules=(200, rules)))
        self.assertEqual(failed(lines), [])

    def test_checks_named_in_the_checks_list_count(self):
        checks = [{"context": c, "app_id": 15368} for c in setup_check.REQUIRED + (PROJECT_TESTS,)]
        lines = setup_check.protection_lines(REPO, fake(protection=(
            200, {"required_status_checks": {"contexts": [], "checks": checks}, "required_pull_request_reviews": {},
                  "enforce_admins": {"enabled": True}})))
        self.assertEqual(failed(lines), [])

    def test_the_kit_checks_alone_leave_the_project_tests_unrequired(self):
        contexts = list(setup_check.REQUIRED + setup_check.OPTIONAL)
        lines = setup_check.protection_lines(REPO, fake(protection=(
            200, {"required_status_checks": {"contexts": contexts}, "required_pull_request_reviews": {},
                  "enforce_admins": {"enabled": True}})))
        self.assertEqual(failed(lines), ["main requires the project's tests: no required check beyond the kit's"])

    def test_a_setting_that_cannot_be_read_fails_and_says_why(self):
        lines = setup_check.protection_lines(REPO, fake(protection=(403, ["gh: Must have admin rights (HTTP 403)"])))
        self.assertEqual(lines, [("FAIL", "branch protection on main: cannot read: no permission (needs admin)")])
        self.assertEqual(setup_check.unreadable("x", 0, "gh is not installed"), [("FAIL", "x: cannot read: gh is not installed")])


class RunnerAndPagesTest(unittest.TestCase):
    def test_runner_set_to_a_known_runner_passes(self):
        self.assertEqual(setup_check.runner_line(REPO, fake()), [("ok", "TRACK_RED_RUNNER: `pytest`")])

    def test_runner_unset_fails(self):
        lines = setup_check.runner_line(REPO, fake(variable=(404, ["(HTTP 404)"])))
        self.assertEqual(failed(lines), ["TRACK_RED_RUNNER: not set; set it to one of unittest, pytest, maven, npm, or a command holding {test}"])

    def test_an_organization_variable_counts(self):
        shared = (200, {"variables": [{"name": "TRACK_RED_RUNNER", "value": "maven"}]})
        lines = setup_check.runner_line(REPO, fake(variable=(404, ["(HTTP 404)"]), shared=shared))
        self.assertEqual(lines, [("ok", "TRACK_RED_RUNNER: `maven`")])

    def test_an_unknown_runner_fails(self):
        lines = setup_check.runner_line(REPO, fake(variable=(200, {"value": "gradle"})))
        self.assertEqual(failed(lines), ["TRACK_RED_RUNNER: `gradle` is not one of unittest, pytest, maven, npm, or a command holding {test}"])

    def test_a_command_holding_test_passes(self):
        lines = setup_check.runner_line(REPO, fake(variable=(200, {"value": "./gradlew test --tests {test}"})))
        self.assertEqual(lines, [("ok", "TRACK_RED_RUNNER: `./gradlew test --tests {test}`")])

    def test_pages_off_or_from_a_branch_fails(self):
        self.assertEqual(len(failed(setup_check.pages_line(REPO, fake(pages=(404, ["(HTTP 404)"]))))), 1)
        lines = setup_check.pages_line(REPO, fake(pages=(200, {"build_type": "legacy"})))
        self.assertEqual(failed(lines), ['GitHub Pages: built from a branch (legacy); set source "GitHub Actions"'])


class PlaceholderTest(unittest.TestCase):
    def test_each_file_with_a_placeholder_left_is_one_line_naming_its_lines(self):
        with tempfile.TemporaryDirectory() as root:
            files = {"CLAUDE.md": "a\n<!-- PROJECT: build -->\nb <!-- PROJECT: test -->\n",
                     "README.md": "Fill every `<!-- PROJECT: … -->`.\n", "done.md": "filled\n"}
            for name, text in files.items():
                with open(os.path.join(root, name), "w", encoding="utf-8", newline="") as f:
                    f.write(text)
            lines = setup_check.placeholder_lines(root, sorted(files))
            self.assertEqual(lines, [("FAIL", "<!-- PROJECT left in CLAUDE.md, lines 2, 3")])
            self.assertEqual(setup_check.placeholder_lines(root, ["done.md", "README.md"]),
                             [("ok", "no <!-- PROJECT placeholder left in the Markdown files")])

    def test_kit_keeps_its_placeholders_in_one_ok_line(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ("CLAUDE.md", "plan.md", "done.md"):
                with open(os.path.join(root, name), "w", encoding="utf-8", newline="") as f:
                    f.write("filled\n" if name == "done.md" else "<!-- PROJECT: goal -->\n")
            lines = setup_check.placeholder_lines(root, ["CLAUDE.md", "done.md", "plan.md"], kit=True)
            self.assertEqual(lines, [("ok", "--kit: 2 Markdown files keep their <!-- PROJECT placeholders, as the kit's should")])
            self.assertEqual(len(failed(setup_check.placeholder_lines(root, ["CLAUDE.md", "plan.md"]))), 2)

    def test_kit_flag_reaches_the_placeholder_item(self):
        seen = []
        with mock.patch.object(setup_check, "gh_api", fake()), \
                mock.patch.object(setup_check, "placeholder_lines", lambda *a: seen.append(a[-1]) or [("ok", "x")]), \
                mock.patch("sys.stdout"):
            setup_check.main(["--repo", REPO, "--kit"])
            setup_check.main(["--repo", REPO])
        self.assertEqual(seen, [True, False])

    def test_kit_folder_is_not_read(self):
        self.assertFalse([p for p in setup_check.tracked_markdown() if p.startswith("kit/")])


class MainTest(unittest.TestCase):
    def test_exit_1_on_any_failure_and_0_when_all_set_up(self):
        with mock.patch.object(setup_check, "gh_api", fake()), \
                mock.patch.object(setup_check, "placeholder_lines", lambda *a: [("ok", "none left")]), \
                mock.patch("sys.stdout"):
            self.assertEqual(setup_check.main(["--repo", REPO]), 0)
        with mock.patch.object(setup_check, "gh_api", fake(pages=(404, ["(HTTP 404)"]))), \
                mock.patch.object(setup_check, "placeholder_lines", lambda *a: [("ok", "none left")]), \
                mock.patch("sys.stdout"):
            self.assertEqual(setup_check.main(["--repo", REPO]), 1)


class CopiedListsTest(unittest.TestCase):
    def test_every_named_check_is_a_job_in_the_workflows(self):
        names = set()
        workflows = os.path.join(ROOT, ".github", "workflows")
        for file in os.listdir(workflows):
            with open(os.path.join(workflows, file), encoding="utf-8") as f:
                names |= {m.strip().strip('"') for m in re.findall(r"^    name: (.+)$", f.read(), re.M)}
        self.assertEqual(set(setup_check.REQUIRED + setup_check.OPTIONAL) - names, set())

    def test_the_kit_rule_requires_the_same_checks(self):
        with open(os.path.join(ROOT, "docs", "kit.md"), encoding="utf-8") as f:
            rule = re.search(r"```json\s*\n\s*(\{\"required_status_checks\".*?)```", f.read(), re.S).group(1)
        contexts = json.loads(rule)["required_status_checks"]["contexts"]
        self.assertEqual(contexts, list(setup_check.REQUIRED) + ["<the project's tests>"])

    def test_the_runners_are_track_reds(self):
        track_red = load("track_red", "track-red.py")
        self.assertEqual(setup_check.RUNNERS, tuple(track_red.RUNNERS))
        self.assertEqual((setup_check.TEMPLATE, setup_check.SUPPORTED), (track_red.TEMPLATE, track_red.SUPPORTED))


if __name__ == "__main__":
    unittest.main()
