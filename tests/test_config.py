"""run-steps.py takes the project from the driver's config when --project is not given. These tests
run it on configs, and check the lines it prints for a config with problems: one line per problem,
nothing on stdout. config.load() is checked directly too. Each test builds a project and a bare
remote in a temporary folder, as DryRunTest does, and the preflight test runs against a fake Claude
Code, as CliPreflightTest does."""

import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import SCRIPT, START, make_project
from tests.test_preflight import fake_cli


def good(project):
    return {"project": str(project), "human_only": [], "budget_usd": 5, "steps_per_night": 3}


class ConfigTest(unittest.TestCase):
    def setUp(self):
        # Imported here, not at the top: where driver/ is missing, each test fails alone, and
        # scripts/track-red.py counts a module that does not load as not run, not as red.
        self.config = importlib.import_module("driver.config")

    def folder(self):
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def drive(self, *args, cwd=None):
        cmd = [sys.executable, str(SCRIPT), *args]
        done = subprocess.run(
            cmd, check=False, capture_output=True, text=True, encoding="utf-8", cwd=cwd
        )
        return done.returncode, done.stdout, done.stderr

    def write(self, path, obj):
        # Written as bytes: on Windows, text mode would add a carriage return to each line.
        raw = obj if isinstance(obj, bytes) else json.dumps(obj).encode("utf-8")
        path.write_bytes(raw)
        return path

    def test_project_from_config(self):
        tmp = self.folder()
        project = make_project(tmp)
        config = self.write(tmp / "driver.json", good(project))
        code, out, err = self.drive("--dry-run", "--config", str(config))
        self.assertEqual((code, out), (0, f"start: {START}\n"))
        self.assertEqual((code, out, err), self.drive("--dry-run", "--project", str(project)))

    def test_preflight_from_config(self):
        tmp = self.folder()
        project = make_project(tmp)
        config = self.write(tmp / "driver.json", good(project))
        claude = fake_cli(self.folder())
        code, out, err = self.drive("preflight", "--config", str(config), "--claude", claude)
        self.assertEqual((code, out), (0, "preflight: ok\n"))
        self.assertEqual(
            (code, out, err), self.drive("preflight", "--project", str(project), "--claude", claude)
        )

    def test_relative_project(self):
        tmp = self.folder()
        make_project(tmp)
        (tmp / "conf").mkdir()
        # The project is "../project" from the config's folder; the run's cwd is elsewhere, so a
        # project read from the cwd would not be found.
        config = self.write(tmp / "conf" / "driver.json", good("../project"))
        code, out, _ = self.drive("--dry-run", "--config", str(config), cwd=self.folder())
        self.assertEqual((code, out), (0, f"start: {START}\n"))

    def test_every_problem_is_a_line(self):
        tmp = self.folder()
        project = make_project(tmp)
        file = tmp / "driver.json"
        for raw in (b"not json", b"[1, 2]"):
            self.write(file, raw)
            self.assertEqual(
                self.drive("--dry-run", "--config", str(file)),
                (2, "", f"cannot start: {file} is not a JSON object\n"),
            )
        self.write(file, {"project": str(project)})
        self.assertEqual(
            self.drive("--dry-run", "--config", str(file)),
            (
                2,
                "",
                (
                    f"cannot start: {file} has no human_only\n"
                    f"cannot start: {file} has no budget_usd\n"
                    f"cannot start: {file} has no steps_per_night\n"
                ),
            ),
        )
        self.write(file, {**good(project), "budget_usd": 0})
        self.assertEqual(
            self.drive("--dry-run", "--config", str(file)),
            (2, "", f"cannot start: {file}'s budget_usd must be a number above 0\n"),
        )
        bad = {"project": 3, "human_only": "a", "budget_usd": True, "steps_per_night": 0}
        config, lines = self.config.load(self.write(file, bad))
        self.assertIsNone(config)
        self.assertEqual(
            lines,
            [
                f"cannot start: {file}'s project must be a path",
                f"cannot start: {file}'s human_only must be a list of paths",
                f"cannot start: {file}'s budget_usd must be a number above 0",
                f"cannot start: {file}'s steps_per_night must be an integer of 1 or more",
            ],
        )

    def test_missing_config(self):
        missing = self.folder() / "nope.json"
        self.assertEqual(
            self.drive("--dry-run", "--config", str(missing)),
            (2, "", f"cannot start: no --project, and no config at {missing}\n"),
        )

    def test_state_and_config_are_ignored(self):
        # One check-ignore per path: git refuses -q with two paths, and the check would never pass.
        for name in ("driver.json", "state/halt"):
            done = subprocess.run(
                ["git", "check-ignore", "-q", name],
                cwd=ROOT,
                check=False,
                capture_output=True,
            )
            self.assertEqual(done.returncode, 0, name)
