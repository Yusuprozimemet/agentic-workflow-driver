"""--once from a copy of the driver, with a fake claude and the fake gh; later tracks import these
helpers. A refusal is one line on its stream; the lock is released unless a live driver holds it."""

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import START, drift_of, git, make_project
from tests.test_github import fake_gh, read_calls
from tests.test_preflight import HELP

SESSION = "00000000-0000-4000-8000-000000000000"
LIVE_LOCK = "cannot start: the driver is already running (pid "
# The fake claude answers --version and --help from fake.json beside it, and records every call in
# calls.jsonl. A session call runs the spec's `do`, then prints its `result` with the session id.
FAKE = """import json
import os
import sys
from pathlib import Path

folder = Path(__file__).resolve().parent
spec = json.loads((folder / "fake.json").read_text(encoding="utf-8"))
args = sys.argv[1:]
probe = args in (["--version"], ["--help"])
data = b"" if probe else sys.stdin.buffer.read()
state = Path(args[args.index("--settings") + 1]).parent if "--settings" in args else None
record = {
    "args": args,
    "stdin": data.hex(),
    "cwd": os.getcwd(),
    "lock": state is not None and (state / "lock").exists(),
    "settings": state is not None and (state / "settings.json").exists(),
}
with (folder / "calls.jsonl").open("ab") as calls:
    calls.write(json.dumps(record).encode("utf-8") + b"\\n")
if probe:
    print(spec["version"] if args == ["--version"] else spec["help"], end="")
    sys.exit(0)
if spec["do"]:
    exec(spec["do"])
session = args[args.index("--session-id") + 1] if "--session-id" in args else None
print(json.dumps({**spec["result"], "session_id": session}))
"""


def claude_program(folder):
    return folder / ("claude.cmd" if os.name == "nt" else "claude")


def fake_claude(folder, help=HELP, do="", result=None):
    spec = {
        "version": "2.1.170 (Claude Code)",
        "help": help,
        "do": do,
        "result": result or {"type": "result", "is_error": False, "result": "done"},
    }
    # Files are written as bytes: on Windows, text mode would add a carriage return to each line.
    (folder / "fake.json").write_bytes(json.dumps(spec).encode("utf-8"))
    (folder / "fake.py").write_bytes(FAKE.encode("utf-8"))
    program = claude_program(folder)
    if os.name == "nt":
        program.write_bytes(f'@"{sys.executable}" "%~dp0fake.py" %*\r\n'.encode())
    else:
        program.write_bytes(f"#!{sys.executable}\n{FAKE}".encode())
        program.chmod(0o755)
    return str(program)


def driver_copy(root):
    # The copy is committed, so the driver's checks see a clean tree, as in the driver's own folder.
    copy = Path(root) / "driver-copy"
    copy.mkdir()
    for name in ("run-steps.py", ".gitignore", "driver", "hooks", "rules"):
        source = ROOT / name
        if source.is_dir():
            shutil.copytree(source, copy / name, ignore=shutil.ignore_patterns("__pycache__"))
        elif source.exists():
            shutil.copy(source, copy / name)
    git(copy, "init", "-b", "main")
    git(copy, "config", "core.autocrlf", "false")
    git(copy, "add", "-A")
    git(copy, "commit", "-m", "copy")
    return copy


def write_config(folder, project, drop=()):
    config = {"project": str(project), "human_only": [], "budget_usd": 5, "steps_per_night": 1}
    path = Path(folder) / "driver.json"
    path.write_bytes(json.dumps({k: v for k, v in config.items() if k not in drop}).encode("utf-8"))
    return path


def once(copy, *args):
    done = subprocess.run(
        [sys.executable, str(copy / "run-steps.py"), "--once", *args],
        capture_output=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return done.returncode, done.stdout.decode("utf-8"), done.stderr.decode("utf-8")


def write_lock(state, pid):
    lock = importlib.import_module("driver.lock")
    state.mkdir(parents=True, exist_ok=True)
    started = lock.now().strftime(lock.STAMP)
    body = json.dumps({"pid": pid, "started": started})
    Path(lock.path(str(state))).write_bytes(body.encode("utf-8"))


def halt_line(state):
    halt = os.path.join(str(state), "halt")
    return f"cannot start: halted: `{halt}` exists; run-steps.py clear removes it"


def without_session_id():
    line = "  --session-id <uuid>  Use a specific session ID for the conversation\n"
    assert line in HELP, "HELP no longer lists --session-id on the line this test removes"
    return HELP.replace(line, "")


def equals(line):
    return lambda text: text == line


def starts(prefix):
    return lambda text: text.startswith(prefix)


def evidence_failed(text):
    return text.startswith("park: the evidence run on `") and text.endswith("` ended `failure`")


def halted(project, state):
    state.mkdir(parents=True)
    (state / "halt").write_bytes(b"halted")


def open_run(project, state):
    # A start with no end line: the run log names the session as still open for the step.
    record = {
        "event": "start",
        "at": "2026-11-07T00:00:00Z",
        "step": START,
        "prefix": "day-01/spec",
        "session": SESSION,
        "claude": "2.1.170 (Claude Code)",
    }
    state.mkdir(parents=True)
    (state / "run.jsonl").write_bytes((json.dumps(record) + "\n").encode("utf-8"))


class OnceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Imported here, as in test_halt: where driver/ is missing, each test fails alone.
        cls.lock = importlib.import_module("driver.lock")
        cls.root = tempfile.mkdtemp()
        cls.copy = driver_copy(cls.root)
        # The live_lock case's lock names this process, which lives until tearDownClass.
        cls.sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])

        def lock_held(project, state):
            write_lock(state, cls.sleeper.pid)

        def notes(project, state):
            (cls.copy / "notes.txt").write_bytes(b"")

        def no_pr_names(project, state):
            (project / "scripts" / "pr-names.py").unlink()

        root = Path(cls.root)
        halt = halt_line(root / "halted" / "state")
        budget = f"cannot start: {root / 'no_budget' / 'driver.json'} has no budget_usd"
        claude = claude_program(root / "no_session_id" / "claude")
        changed = "cannot start: the driver's repository has changes: `notes.txt`"
        pr_names = "cannot read the project: scripts/pr-names.py is missing"
        session = f"cannot run a session: {claude} --help lists no --session-id"
        ended = f"park: the run log names session `{SESSION}` for this step, with no end"
        done = drift_of("Every day is done.")
        waiting = drift_of(open_prs=(7,))
        failed = [{"status": "completed", "conclusion": "failure"}]
        # The table: case, run_case arguments, exit code, the stream that holds the line, its test.
        table = [
            ("halted", {"setup": halted}, 2, "stderr", equals(halt)),
            ("no_budget", {"drop": ("budget_usd",)}, 2, "stderr", equals(budget)),
            ("live_lock", {"setup": lock_held}, 2, "stderr", starts(LIVE_LOCK)),
            ("driver_changed", {"setup": notes}, 2, "stderr", equals(changed)),
            ("no_pr_names", {"setup": no_pr_names}, 2, "stderr", equals(pr_names)),
            ("no_session_id", {"help": without_session_id()}, 2, "stderr", equals(session)),
            ("every_day_done", {"drift": done}, 1, "stdout", equals("park: every day is done")),
            ("waits", {"drift": waiting}, 0, "stdout", equals("wait: #7")),
            ("evidence_failed", {"runs": failed}, 1, "stdout", evidence_failed),
            ("open_run_log", {"setup": open_run}, 1, "stdout", equals(ended)),
            ("passes", {}, 0, "stdout", equals(f"would start: {START}")),
        ]
        cls.wants = {}
        cls.results = {}
        for name, kwargs, code, stream, match in table:
            cls.results[name] = cls.run_case(name, **kwargs)
            cls.wants[name] = (code, stream, match)

    @classmethod
    def tearDownClass(cls):
        cls.sleeper.kill()
        cls.sleeper.wait(timeout=10)
        shutil.rmtree(cls.root, ignore_errors=True)

    @classmethod
    def run_case(cls, name, drift=None, setup=None, help=HELP, runs=None, drop=()):
        folder = Path(cls.root) / name
        folder.mkdir()
        project = make_project(folder, drift)
        state = folder / "state"
        claude_dir, gh_dir = folder / "claude", folder / "gh"
        claude_dir.mkdir()
        gh_dir.mkdir()
        claude = fake_claude(claude_dir, help=help)
        gh = fake_gh(gh_dir, runs=runs or [{"status": "completed", "conclusion": "success"}])
        config = write_config(folder, project, drop)
        if setup is not None:
            setup(project, state)
        flags = ["--config", str(config), "--state", str(state), "--claude", claude, "--gh", gh]
        code, out, err = once(cls.copy, *flags)
        (cls.copy / "notes.txt").unlink(missing_ok=True)
        calls = read_calls(claude_dir) if (claude_dir / "calls.jsonl").exists() else []
        return {
            "code": code,
            "out": out,
            "err": err,
            "lock": os.path.exists(cls.lock.path(str(state))),
            "settings": (state / "settings.json").exists(),
            "runlog": (state / "run.jsonl").exists(),
            # Only --version and --help may have run: no case here starts a session.
            "calls_ok": all(call["args"] in (["--version"], ["--help"]) for call in calls),
        }

    def assert_case(self, name):
        result = self.results[name]
        code, stream, match = self.wants[name]
        printed = [n for n, text in (("stdout", result["out"]), ("stderr", result["err"])) if text]
        text = (result["err"] or result["out"]).strip()
        with self.subTest(case=name):
            self.assertEqual(
                (result["code"], printed, match(text), result["calls_ok"]),
                (code, [stream], True, True),
            )

    def test_refusals(self):
        # The first ten cases of the table are refusals; passes is the eleventh.
        for name in list(self.wants)[:10]:
            self.assert_case(name)

    def test_halt_comes_first(self):
        # Its own case folder: the halt file is set and the config has no budget_usd.
        result = self.run_case("halt_first", setup=halted, drop=("budget_usd",))
        state = Path(self.root) / "halt_first" / "state"
        self.assertEqual(
            (result["code"], result["err"].strip() == halt_line(state), result["out"] == ""),
            (2, True, True),
        )

    def test_lock_released_on_refusal(self):
        # Cases 4 to 11 of the table, from driver_changed to passes, leave the lock released.
        locks = [self.results[name]["lock"] for name in list(self.results)[3:]]
        self.assertEqual((locks, self.results["live_lock"]["lock"]), ([False] * 8, True))
        self.assert_case("passes")
        passes = self.results["passes"]
        self.assertEqual((passes["settings"], passes["runlog"]), (False, False))

    def test_once_goes_alone(self):
        for args in (("--dry-run",), ("halt",)):
            code, out, err = once(self.copy, *args)
            self.assertEqual((code, err.strip(), out), (2, "run-steps.py: --once goes alone", ""))

    def test_usage_line(self):
        project = Path(self.root) / "passes" / "project"
        done = subprocess.run(
            [sys.executable, str(self.copy / "run-steps.py"), "--project", str(project)],
            capture_output=True,
            check=False,
            text=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(
            (done.returncode, done.stderr.strip(), done.stdout),
            (2, "run-steps.py: give --dry-run, --once or a command", ""),
        )
