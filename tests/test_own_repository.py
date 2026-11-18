"""Day 13, C13.2 and C13.20: --once refuses the driver's own repository (Track A) and goes on as today
for any other. The project's origin and the driver copy's origin are set per case."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import drift_of, git
from tests.test_once import DASHED, OPENED, driver_copy, once
from tests.test_once_park_issues import build
from tests.test_review_loop import same


class OwnRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def case(self, name):
        # One case's folder: the driver copy, and the project with its remote.git beside it. Each test
        # has its own copy, since the tests set the copy's origin.
        folder = Path(self.root) / name
        folder.mkdir()
        copy = driver_copy(folder)
        flags = build(folder, drift=drift_of(DASHED))
        return folder, copy, flags

    def test_other_origin(self):
        # The driver copy's origin is another repository's, so --once goes on and opens the step's pull request.
        _folder, copy, flags = self.case("other")
        git(copy, "remote", "add", "origin", "https://example.invalid/driver.git")
        code, out, err = once(copy, *flags)
        same(self, (code, out.splitlines(), err.splitlines()), (0, [OPENED], []))

    def test_no_origin(self):
        # With no origin on either side, `git ls-remote --get-url origin` prints "origin" in both; that word
        # is no URL, so the two are not one repository: the run reads the project, which parks on its origin.
        folder, copy, flags = self.case("none")
        git(folder / "project", "remote", "remove", "origin")
        code, out, err = once(copy, *flags)
        same(
            self,
            (code, out.splitlines(), err.splitlines()),
            (1, ["park: the project has no origin/main"], []),
        )

    def assert_refused(self, folder, copy, code, out, err, project_text):
        # The refusal names the project as given. Nothing ran: no gh or claude call, and no state folder,
        # so no lock was taken. The three checks are one tuple, so a failure names which one differs.
        same(
            self,
            (code, out.splitlines(), err.replace(project_text, "<project>").splitlines()),
            (2, [], ["cannot start: `<project>` is the driver's own repository"]),
        )
        gh_calls = folder / "gh" / "calls.jsonl"
        claude_calls = folder / "claude" / "calls.jsonl"
        same(
            self,
            (
                not gh_calls.exists() or gh_calls.read_bytes() == b"",
                not claude_calls.exists(),
                not (folder / "state").exists(),
            ),
            (True, True, True),
        )

    def test_same_folder(self):
        # The project is the driver's own folder, so the run refuses before the lock and before any call.
        folder, copy, flags = self.case("same")
        code, out, err = once(copy, *flags, "--project", str(copy))
        self.assert_refused(folder, copy, code, out, err, str(copy))

    def test_same_origin(self):
        # The driver copy's origin is the project's, so the two are one repository, whatever the folders.
        folder, copy, flags = self.case("origin")
        url = (
            subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=folder / "project",
                capture_output=True,
                check=True,
            )
            .stdout.decode()
            .strip()
        )
        git(copy, "remote", "add", "origin", url)
        code, out, err = once(copy, *flags)
        self.assert_refused(folder, copy, code, out, err, str((folder / "project").resolve()))
