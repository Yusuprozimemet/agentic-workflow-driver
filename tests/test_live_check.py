"""The live check (C06.10): `on` starts a session only on a Claude Code version that
<state>/live-checked.txt lists, --once does not read that file, and `run-steps.py live-check` records
the version only after a run that ends "OK" with no skip. The test runner is a fake passed by
--python, so no real unittest runs and no session starts. Each case is a copy of the driver, as in
tests/test_on.py."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_github import read_calls
from tests.test_on import OnCase
from tests.test_once import claude_program

VERSION = "2.1.400 (Claude Code)"
REFUSED = f"cannot start: Claude Code `{VERSION}` has not passed the live check; run run-steps.py live-check"
# The fake runner answers from fake.json beside it, and records each call in calls.jsonl.
FAKE_RUNNER = """import json
import os
import sys
from pathlib import Path

folder = Path(__file__).resolve().parent
spec = json.loads((folder / "fake.json").read_text(encoding="utf-8"))
record = {"args": sys.argv[1:], "live": os.environ.get("DRIVER_LIVE_CLI"), "cwd": os.getcwd()}
with (folder / "calls.jsonl").open("ab") as calls:
    calls.write(json.dumps(record).encode("utf-8") + b"\\n")
sys.stderr.write(spec["output"])
sys.exit(spec["code"])
"""


def fake_runner(folder, output, code):
    # Files are written as bytes: on Windows, text mode would add a carriage return to each line.
    spec = {"output": output, "code": code}
    (folder / "fake.json").write_bytes(json.dumps(spec).encode("utf-8"))
    (folder / "fake.py").write_bytes(FAKE_RUNNER.encode("utf-8"))
    if os.name == "nt":
        program = folder / "runner.cmd"
        program.write_bytes(f'@"{sys.executable}" "%~dp0fake.py" %*\r\n'.encode())
    else:
        program = folder / "runner"
        program.write_bytes(f"#!{sys.executable}\n{FAKE_RUNNER}".encode())
        program.chmod(0o755)
    return str(program)


def same_path(one, other):
    # realpath expands Windows short names, and normcase folds the case, as the paths differ in both.
    return os.path.normcase(os.path.realpath(one)) == os.path.normcase(os.path.realpath(other))


class LiveCheckTest(OnCase, unittest.TestCase):
    def case(self, name, listed):
        # One step, a fake claude that prints VERSION, and the record as `listed` (None: no record).
        self.build(name, steps=1)
        spec_file = self.folder / "claude" / "fake.json"
        spec = json.loads(spec_file.read_bytes())
        spec["version"] = VERSION
        spec_file.write_bytes(json.dumps(spec).encode("utf-8"))
        record = self.state / "live-checked.txt"
        if listed is None:
            record.unlink()
        else:
            record.write_bytes(listed)

    def live_check(self, output, code):
        # run-steps.py live-check on this case's copy, with a runner that prints output and exits code.
        runner = self.folder / "runner"
        runner.mkdir()
        python = fake_runner(runner, output, code)
        return subprocess.run(
            [
                sys.executable,
                str(self.copy / "run-steps.py"),
                "live-check",
                "--state",
                str(self.state),
                "--claude",
                str(claude_program(self.folder / "claude")),
                "--python",
                python,
            ],
            capture_output=True,
            check=False,
            timeout=120,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def test_on_refuses_an_unchecked_version(self):
        # C06.10: a version the record does not list refuses before any session, with no lock left; a
        # listed version goes on; --once does not read the record at all.
        for name, listed in (("missing", None), ("other", b"2.1.170 (Claude Code)\n")):
            with self.subTest(case=name):
                self.case(name, listed)
                code, out, err = self.on()
                lock_left = os.path.exists(self.lock.path(str(self.state)))
                self.assertEqual(
                    (code, out, err.splitlines(), self.sessions(), lock_left),
                    (2, "", [REFUSED], [], False),
                )
        with self.subTest(case="listed"):
            self.case("listed", f"2.1.170 (Claude Code)\n{VERSION}\n".encode())
            code, out, _ = self.on()
            self.assertEqual(
                (code, out.splitlines()[-1], len(self.sessions())),
                (0, "on: 1 steps, the night's count", 1),
            )
        with self.subTest(case="once"):
            self.case("once", None)
            done = subprocess.run(
                [sys.executable, str(self.copy / "run-steps.py"), "--once", *self.flags],
                capture_output=True,
                check=False,
                timeout=120,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assertEqual((done.returncode, len(self.sessions())), (0, 1))

    def test_live_check_records_only_a_clean_pass(self):
        # C06.10: the record gets the version only after a run that ends "OK" with no skip.
        for name, output, code, want_code, want_record in (
            ("clean", "Ran 2 tests in 1s\n\nOK\n", 0, 0, f"{VERSION}\n".encode()),
            ("skip", "Ran 2 tests in 0s\n\nOK (skipped=2)\n", 0, 1, None),
            ("failure", "Ran 2 tests in 1s\n\nFAILED (failures=1)\n", 1, 1, None),
            ("ok_but_exit_1", "OK\n", 1, 1, None),
        ):
            with self.subTest(case=name):
                self.case(name, None)
                done = self.live_check(output, code)
                record = self.state / "live-checked.txt"
                kept = record.read_bytes() if record.exists() else None
                self.assertEqual((done.returncode, kept), (want_code, want_record))
                if name == "clean":
                    call = read_calls(self.folder / "runner")[0]
                    claude = str(claude_program(self.folder / "claude"))
                    self.assertEqual(
                        (
                            call["args"],
                            same_path(call["live"], claude),
                            same_path(call["cwd"], self.copy),
                        ),
                        (["-m", "unittest", "tests.test_live_cli"], True, True),
                    )
        with self.subTest(case="appends"):
            self.case("appends", b"2.1.170 (Claude Code)\n")
            done = self.live_check("OK\n", 0)
            record = (self.state / "live-checked.txt").read_bytes()
            self.assertEqual(
                (done.returncode, record),
                (0, b"2.1.170 (Claude Code)\n" + f"{VERSION}\n".encode()),
            )
