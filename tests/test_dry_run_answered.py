"""C07.20: the dry run at an answered phase's end reads the closed parked issues and starts the step, and
a dry run that cannot read them says so and exits 2."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import drift_of
from tests.test_once import driver_copy
from tests.test_once_park_issues import build
from tests.test_recovery_holds import NEXT, gh_of, issue, run, set_issues

TITLE = "park: the end of Phase 1: Day 02 starts Phase 2"
PHASE_END = {
    **drift_of(NEXT),
    "order": [1, 2],
    "days": [{"day": d, "phase": d, "status": "active"} for d in (1, 2)],
}


class DryRunAnsweredTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp()
        cls.copy = driver_copy(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def folder_of(self, name):
        folder = Path(self.root) / name
        folder.mkdir()
        return folder

    def test_answered_starts(self):
        folder = self.folder_of("answered")
        flags = build(folder, drift=PHASE_END)
        set_issues(folder, [issue(5, TITLE, labels=("parked",), state="closed")])
        code, out, _ = run(
            self.copy, "--dry-run", "--project", str(folder / "project"), "--gh", gh_of(flags)
        )
        self.assertEqual((code, out.strip()), (0, f"start: {NEXT}"))

    def test_gh_fails(self):
        folder = self.folder_of("gh_fails")
        flags = build(folder, drift=PHASE_END)
        path = folder / "gh" / "fake.json"
        spec = json.loads(path.read_bytes())
        spec["issue_code"] = 1
        path.write_bytes(json.dumps(spec).encode("utf-8"))
        code, out, err = run(
            self.copy, "--dry-run", "--project", str(folder / "project"), "--gh", gh_of(flags)
        )
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertEqual(err.strip(), "cannot read the project: gh issue list exited 1")


if __name__ == "__main__":
    unittest.main()
