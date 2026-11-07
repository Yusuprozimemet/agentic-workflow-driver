"""--once's park issues (C05.7): each line --once prints as a park is an open issue, titled with the
line and holding the line in its body; a second run waits on an open one and parks again once it
is closed; a park whose issue cannot be opened says so on stderr and still exits 1. Each case is a
copy of the driver with the fake gh and the fake claude of tests/test_once.py and
tests/test_github.py."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import drift_of, make_project
from tests.test_github import fake_gh, read_bodies, read_calls
from tests.test_once import DASHED, STEP_PR, driver_copy, fake_claude, once, open_run, write_config
from tests.test_once_outcome import OTHER_PR

CLOSE = "Close this issue to let the driver go on."
SUCCESS = [{"status": "completed", "conclusion": "success"}]
FAILED = [{"status": "completed", "conclusion": "failure"}]
ERROR = {"type": "result", "is_error": True, "result": "x"}
PARKED = {"type": "result", "is_error": False, "result": "Worked.\n\nPARK: needs a decision\n\n"}
PARK_STEM = "park: the session parked: needs a decision"
LABEL_LINE = "cannot open the park's issue: gh label create exited 1"
# The session makes the fake gh's issue and label calls fail, from its own folder's gh/fake.json.
GH_FAILS = (
    'gh_file = folder.parent / "gh" / "fake.json"; '
    'gh_spec = json.loads(gh_file.read_bytes()); gh_spec["issue_code"] = 1; '
    'gh_file.write_bytes(json.dumps(gh_spec).encode("utf-8"))'
)


def dirty_tree(project, state):
    # An untracked file: the tree is not clean, so decide parks before any session starts.
    (project / "stray.txt").write_bytes(b"x\n")


def build(folder, drift=None, prs=(STEP_PR,), runs=SUCCESS, result=None, do="", setup=None):
    # The project, the fake claude and the fake gh in folder, and the config; returns the flags.
    project = make_project(folder, drift)
    state = folder / "state"
    claude_dir, gh_dir = folder / "claude", folder / "gh"
    claude_dir.mkdir()
    gh_dir.mkdir()
    claude = fake_claude(claude_dir, do=do, result=result)
    gh = fake_gh(gh_dir, runs=list(runs), prs=list(prs))
    config = write_config(folder, project)
    if setup is not None:
        setup(project, state)
    return ["--config", str(config), "--state", str(state), "--claude", claude, "--gh", gh]


def gh_issues(folder):
    # The issues the fake gh holds after the run: the ones it created, and the ones it was given.
    spec = json.loads((folder / "gh" / "fake.json").read_bytes())
    return spec["issues"]


def gh_calls(folder, verb):
    # The fake gh's calls that start with the given subcommand pair, e.g. ["issue", "create"].
    if not (folder / "gh" / "calls.jsonl").exists():
        return []
    return [call for call in read_calls(folder / "gh") if call[:2] == verb]


def created_bodies(folder):
    # The bodies sent to `issue create`, read from bodies.jsonl beside the fake gh.
    if not (folder / "gh" / "bodies.jsonl").exists():
        return []
    bodies = read_bodies(folder / "gh")
    return [record["body"] for record in bodies if record["args"][:2] == ["issue", "create"]]


class OnceParkIssuesTest(unittest.TestCase):
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

    def test_each_park_is_an_issue(self):
        # The eight parks: a dirty tree, the evidence run's failure, an open run-log line, and the
        # session's five parks. The session's cases start a session, so they use DASHED's step.
        cases = [
            ("dirty_tree", {"setup": dirty_tree}),
            ("evidence_failure", {"runs": FAILED}),
            ("open_run_log", {"setup": open_run, "drift": drift_of()}),
            ("not_json", {"do": 'print("oops"); sys.exit(3)'}),
            ("error", {"result": ERROR}),
            ("parked", {"result": PARKED}),
            ("no_pr", {"prs": ()}),
            ("two_prs", {"prs": (STEP_PR, OTHER_PR)}),
        ]
        for name, kwargs in cases:
            with self.subTest(name):
                kwargs.setdefault("drift", drift_of(DASHED))
                folder = self.folder_of(name)
                flags = build(folder, **kwargs)
                code, out, err = once(self.copy, *flags)
                line = out.strip()
                bodies = created_bodies(folder)
                self.assertEqual(
                    (
                        line.startswith("park: "),
                        [(i["title"], i["state"], i["labels"]) for i in gh_issues(folder)],
                        out.splitlines(),
                        len(bodies),
                        all(line in body and CLOSE in body for body in bodies),
                        err,
                        code,
                    ),
                    (True, [(line, "open", ["parked"])], [line], 1, True, "", 1),
                )

    def test_open_park_waits(self):
        folder = self.folder_of("open_waits")
        flags = build(folder, drift=drift_of(DASHED), setup=dirty_tree)
        first = once(self.copy, *flags)
        made = len(gh_calls(folder, ["issue", "create"]))
        second = once(self.copy, *flags)
        self.assertEqual(
            (
                first[0],
                made,
                len(gh_calls(folder, ["issue", "create"])) - made,
                second[1].strip(),
                second[2],
                second[0],
            ),
            (1, 1, 0, "wait: parked #1", "", 0),
        )

    def test_closed_park_parks_again(self):
        folder = self.folder_of("closed_again")
        flags = build(folder, drift=drift_of(DASHED), setup=dirty_tree)
        first = once(self.copy, *flags)
        line = first[1].strip()
        # The maintainer closes the park's issue; the fake gh keeps it, with its state changed.
        spec_file = folder / "gh" / "fake.json"
        spec = json.loads(spec_file.read_bytes())
        for issue in spec["issues"]:
            issue["state"] = "closed"
        spec_file.write_bytes(json.dumps(spec).encode("utf-8"))
        second = once(self.copy, *flags)
        self.assertEqual(
            (
                len(gh_calls(folder, ["issue", "comment"])),
                [(i["number"], i["state"], i["title"]) for i in gh_issues(folder)],
                second[0],
                second[1].strip() == line,
            ),
            (0, [(1, "closed", line), (2, "open", line)], 1, True),
        )

    def test_park_issue_fails(self):
        folder = self.folder_of("issue_fails")
        flags = build(folder, drift=drift_of(DASHED), result=PARKED, do=GH_FAILS)
        code, out, err = once(self.copy, *flags)
        stem = out.strip().split(" (session ")[0]
        self.assertEqual(
            (stem, len(out.splitlines()), err.splitlines()[:1], code, gh_issues(folder)),
            (PARK_STEM, 1, [LABEL_LINE], 1, []),
        )
