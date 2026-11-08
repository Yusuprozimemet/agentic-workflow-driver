"""--once's outcome (step 12): the line and the exit code the session's stdout gives, the run log's end
line, and the driver's repository checked again after the session. Each case runs from its own copy
of the driver, with the fake claude and the fake gh of tests/test_once.py and tests/test_github.py."""

import concurrent.futures
import importlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import drift_of, git, make_project
from tests.test_github import fake_gh
from tests.test_once import DASHED, driver_copy, fake_claude, halt_line, once, write_config

OPEN_PR = {"number": 5, "headRefName": "day-01/track-a-x", "url": "u", "author": "me"}
OTHER_PR = {"number": 6, "headRefName": "day-01/track-a-y", "url": "u", "author": "me"}
OPENED = "opened: #5 from `day-01/track-a-x`"
# The fake gh's code is read on each call: a session that sets it to 4 makes the step's pr list fail.
GH_DOWN = (
    'gh_file = folder.parent / "gh" / "fake.json"; '
    'gh_spec = json.loads(gh_file.read_bytes()); gh_spec["code"] = 4; '
    'gh_file.write_bytes(json.dumps(gh_spec).encode("utf-8"))'
)


class OutcomeTest(unittest.TestCase):
    def setUp(self):
        # Imported here, as in test_once: where driver/ is missing, each test fails alone.
        importlib.import_module("driver.once")
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def copy_of(self):
        # A copy of the driver with its own temp folder, so a test may change it.
        return driver_copy(tempfile.mkdtemp(dir=self.root))

    def run_case(self, result=None, do="", prs=(OPEN_PR,), copy=None):
        folder = Path(tempfile.mkdtemp(dir=self.root))
        project = make_project(folder, drift_of(DASHED))
        state = folder / "state"
        claude_dir, gh_dir = folder / "claude", folder / "gh"
        claude_dir.mkdir()
        gh_dir.mkdir()
        claude = fake_claude(claude_dir, do=do, result=result)
        gh_runs = [{"status": "completed", "conclusion": "success"}]
        gh = fake_gh(gh_dir, runs=gh_runs, prs=list(prs))
        config = write_config(folder, project)
        flags = ["--config", str(config), "--state", str(state), "--claude", claude, "--gh", gh]
        code, out, err = once(copy, *flags)
        records = []
        if (state / "run.jsonl").exists():
            lines = (state / "run.jsonl").read_text(encoding="utf-8").splitlines()
            records = [json.loads(line) for line in lines]
        starts = [record for record in records if record["event"] == "start"]
        # The uuid differs on every run; a report that names it could not be replayed.
        for record in starts:
            out = out.replace(record["session"], "<uuid>")
            err = err.replace(record["session"], "<uuid>")
        return {
            "code": code,
            "out": out,
            "err": err,
            "flags": flags,
            "state": state,
            "records": records,
            "starts": starts,
        }

    def test_outcomes(self):
        copy = self.copy_of()
        error = {"type": "result", "is_error": True, "result": "x"}
        parked = {
            "type": "result",
            "is_error": False,
            "result": "Worked.\n\nPARK: needs a decision\n\n",
        }
        # The row: the run_case arguments, the line with the session's id, the exit code, the stream.
        rows = [
            (
                "not_json",
                {"do": 'print("oops"); sys.exit(3)'},
                "park: the session ended without a result (exit 3; session `{session}`)",
                1,
                "stdout",
            ),
            (
                "error_with_subtype",
                {"result": {**error, "subtype": "error_max_budget_usd"}},
                "park: the session ended in an error: `error_max_budget_usd` (session `{session}`)",
                1,
                "stdout",
            ),
            (
                "error_without_subtype",
                {"result": error},
                "park: the session ended in an error: `unknown` (session `{session}`)",
                1,
                "stdout",
            ),
            (
                "parked",
                {"result": parked},
                "park: the session parked: needs a decision (session `{session}`)",
                1,
                "stdout",
            ),
            ("one_pr", {}, OPENED, 0, "stdout"),
            (
                "no_pr",
                {"prs": ()},
                "park: the session ended with no pull request and no PARK line (session `{session}`)",
                1,
                "stdout",
            ),
            (
                "two_prs",
                {"prs": (OPEN_PR, OTHER_PR)},
                "park: the step has more than one pull request: #5, #6",
                1,
                "stdout",
            ),
            (
                "gh_fails",
                {"do": GH_DOWN},
                "cannot read the project: gh pr list exited 4",
                2,
                "stderr",
            ),
        ]
        # Each case has its own folders; only the read-only driver copy is shared, so the
        # cases run at once and are checked in order.
        with concurrent.futures.ThreadPoolExecutor(len(rows)) as pool:
            futures = [pool.submit(self.run_case, copy=copy, **row[1]) for row in rows]
        for (name, _, line, code, stream), future in zip(rows, futures):
            with self.subTest(case=name):
                result = future.result()
                streams = (("stdout", result["out"]), ("stderr", result["err"]))
                printed = [n for n, text in streams if text]
                text = (result["err"] or result["out"]).strip()
                self.assertEqual(
                    (result["code"], printed, text),
                    (code, [stream], line.format(session="<uuid>")),
                )

    def test_park_wins_over_a_pr(self):
        # The step has one open pull request, and the session still ends with a PARK line.
        result = self.run_case(
            copy=self.copy_of(),
            result={
                "type": "result",
                "is_error": False,
                "result": "Opened.\nPARK: needs a decision",
            },
        )
        expected = "park: the session parked: needs a decision (session `<uuid>`)"
        self.assertEqual((result["code"], result["out"].strip()), (1, expected))

    def test_end_line(self):
        result = self.run_case(
            copy=self.copy_of(),
            result={
                "type": "result",
                "is_error": False,
                "result": "done",
                "total_cost_usd": 0.42,
                "permission_denials": [{}, {}],
            },
        )
        end = result["records"][-1]
        session = result["starts"][0]["session"]
        self.assertEqual(
            (
                end["event"],
                end["session"] == session,
                end["outcome"],
                end["cost_usd"],
                end["denials"],
            ),
            ("end", True, OPENED, 0.42, 2),
        )

    def test_driver_changed_during_step(self):
        copy = self.copy_of()
        do = f"(Path({str(copy)!r}) / 'notes.txt').write_bytes(b'')"
        result = self.run_case(copy=copy, do=do)
        halt = result["state"] / "halt"
        reason = "the driver's repository has changes: `notes.txt`"
        self.assertEqual(
            (
                result["code"],
                result["out"].splitlines(),
                result["err"],
                halt.exists() and halt.read_bytes().startswith(b"halted at "),
            ),
            (1, [OPENED, f"halt: set during the step; {reason}"], "", True),
        )
        again = once(copy, *result["flags"])
        self.assertEqual((again[0], again[2].strip()), (2, halt_line(result["state"])))

    def test_driver_moved_during_step(self):
        copy = self.copy_of()
        before = git(copy, "rev-parse", "HEAD").stdout.strip()
        # The identity is given on the command line: the session's environment may have none. The
        # commit's own report is captured: it would otherwise land in the session's stdout.
        do = (
            "import subprocess; subprocess.run(['git', '-c', 'user.name=t', '-c', "
            "'user.email=t@t', '-C', "
            f"{str(copy)!r}, 'commit', '--allow-empty', '-m', 'x'], check=True, "
            "capture_output=True)"
        )
        result = self.run_case(copy=copy, do=do)
        after = git(copy, "rev-parse", "HEAD").stdout.strip()
        halt = result["state"] / "halt"
        # The shas differ on every run; a report that names them could not be replayed.
        out = result["out"].replace(before[:7], "<a>").replace(after[:7], "<b>")
        reason = "the driver's repository moved from `<a>` to `<b>`"
        self.assertEqual(
            (
                result["code"],
                out.splitlines(),
                halt.exists(),
            ),
            (1, [OPENED, f"halt: set during the step; {reason}"], True),
        )
        again = once(copy, *result["flags"])
        self.assertEqual((again[0], again[2].strip()), (2, halt_line(result["state"])))

    def test_close_files_do_not_halt(self):
        copy = self.copy_of()
        do = f"(Path({str(copy)!r}) / 'evidence.json').write_bytes(b'')"
        result = self.run_case(copy=copy, do=do)
        self.assertEqual(
            (result["code"], result["out"].splitlines(), result["err"]),
            (0, [OPENED], ""),
        )
        self.assertFalse((result["state"] / "halt").exists())
