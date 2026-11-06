"""run-steps.py --dry-run checks the kit before it reads the remote: each missing piece is one line on
stderr, and an origin that cannot be read is not the same as a main that is missing. Each test
builds a project and a bare remote in a temporary folder, as DryRunTest does."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import drift_of, dry_run, git, make_project, without


class PreflightTest(unittest.TestCase):
    def project(self, drift=None):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        return make_project(tmp.name, drift)

    def test_every_missing_piece_is_a_line(self):
        drift = without(drift_of(), "order")
        del drift["days"][0]["status"]
        project = self.project(drift)
        git(project, "rm", "scripts/pr-names.py")
        git(project, "rm", ".github/workflows/evidence.yml")
        git(project, "commit", "-m", "remove the kit's pieces")
        git(project, "push", "origin", "main")
        self.assertEqual(
            dry_run(project),
            (
                2,
                "",
                (
                    "cannot read the project: scripts/pr-names.py is missing\n"
                    "cannot read the project: .github/workflows/evidence.yml is missing\n"
                    "cannot read the project: spec-drift.py's JSON has no order\n"
                    "cannot read the project: spec-drift.py's JSON has no days[0].status\n"
                ),
            ),
        )

    def test_one_missing_file_refuses(self):
        project = self.project()
        git(project, "rm", "scripts/pr-names.py")
        git(project, "commit", "-m", "remove pr-names")
        # Pushed, so main is origin/main: without the check, the dry run would start the step.
        git(project, "push", "origin", "main")
        self.assertEqual(
            dry_run(project),
            (2, "", "cannot read the project: scripts/pr-names.py is missing\n"),
        )

    def test_unreachable_origin_is_not_a_missing_main(self):
        with self.subTest("origin does not exist"):
            project = self.project()
            missing = project.parent / "no-such-remote"
            git(project, "remote", "set-url", "origin", str(missing))
            # The code is the one git itself exits with for this remote, not a constant.
            code = subprocess.run(
                ["git", "ls-remote", str(missing)], check=False, cwd=project, capture_output=True
            ).returncode
            self.assertNotEqual(code, 0)
            self.assertEqual(
                dry_run(project),
                (
                    2,
                    "",
                    f"cannot read the project: origin could not be read (git ls-remote exited {code})\n",
                ),
            )
        with self.subTest("origin is empty"):
            project = self.project()
            git(project.parent, "init", "--bare", "-b", "main", "empty.git")
            git(project, "remote", "set-url", "origin", str(project.parent / "empty.git"))
            code, out, _ = dry_run(project)
            self.assertEqual((code, out), (1, "park: the project has no origin/main\n"))
        with self.subTest("no remote named origin"):
            project = self.project()
            git(project, "remote", "remove", "origin")
            code, out, _ = dry_run(project)
            self.assertEqual((code, out), (1, "park: the project has no origin/main\n"))

    def test_null_phase_still_parks(self):
        drift = {
            "now": {
                "next_step": "Day 02: read the spec against the code, then the spec-change PR",
                "open_prs": [],
            },
            "order": [1, 2],
            "days": [
                {"day": 1, "phase": 0, "status": "done"},
                {"day": 2, "phase": None, "status": "active"},
            ],
            "meta": {"caveats": []},
        }
        code, out, _ = dry_run(self.project(drift))
        self.assertEqual((code, out), (1, "park: Day 02 or the day before it names no phase\n"))


if __name__ == "__main__":
    unittest.main()
