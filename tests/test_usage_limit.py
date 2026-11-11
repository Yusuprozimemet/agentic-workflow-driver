"""--once and the usage limit (Day 9, C09.1 to C09.5): a session whose transcript's last assistant
record is the limit waits for the reset and is resumed once; a reset further than --limit-hours
parks; the halt file stops the wait. The driver runs as a subprocess, with the fake claude of
tests/test_once.py, which writes the session's transcript under CLAUDE_CONFIG_DIR, and the fake gh
of tests/test_github.py."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_dry_run import drift_of, make_project
from tests.test_github import fake_gh, read_calls
from tests.test_once import DASHED, driver_copy, fake_claude, write_config

OPEN_PR = {"number": 5, "headRefName": "day-01/track-a-x", "url": "u", "author": "me"}
OPENED = "opened: #5 from `day-01/track-a-x`"
PROMPT = (
    "The usage limit has reset. Carry on with this step as before, open its one pull request, "
    "and stop.\n"
)
WAITING = "limit: the usage limit was reached; waiting until "
HALT = "halt: the halt file was set during the wait for the usage limit (session `<uuid>`)"
AGAIN = "park: the usage limit was reached (session `<uuid>`)"
UNKNOWN = "park: the session ended in an error: `unknown` (session `<uuid>`)"
TEXT = "You've hit your session limit · resets 9:10pm (Europe/Amsterdam)"
LIMITED = {"type": "result", "is_error": True, "result": TEXT}
DONE = {"type": "result", "is_error": False, "result": "done"}
PLAIN = {"type": "assistant", "message": {"content": []}}
# The fake session takes its entry from runs.json by the number of starts so far, records the start
# in starts.jsonl, appends the entry's records to the session's transcript and prints its result.
# A resumed session appends to the same transcript, as the CLI does.
DO = """import time
runs = json.loads((folder / "runs.json").read_bytes())
starts = folder / "starts.jsonl"
entry = runs[len(starts.read_bytes().splitlines()) if starts.exists() else 0]
sid = args[args.index("--resume" if "--resume" in args else "--session-id") + 1]
start = {"at": time.time(), "args": args, "stdin": data.decode("utf-8")}
with starts.open("ab") as log:
    log.write(json.dumps(start).encode("utf-8") + b"\\n")
if entry.get("records"):
    transcript = Path(os.environ["CLAUDE_CONFIG_DIR"]) / "projects" / "p" / f"{sid}.jsonl"
    transcript.parent.mkdir(parents=True, exist_ok=True)
    with transcript.open("ab") as log:
        for record in entry["records"]:
            log.write(json.dumps(record).encode("utf-8") + b"\\n")
spec["result"] = entry["result"]
"""


def limit_record(reset):
    info = {"resetsAt": reset, "rateLimitType": "five_hour"}
    return {
        "type": "assistant",
        "apiError": "usage_limit_reached",
        "error": "rate_limit",
        "apiErrorParams": {"rate_limit_info": info},
        "message": {"content": [{"type": "text", "text": TEXT}]},
    }


def limit_records(reset):
    # The CLI's transcript at the limit: the limit record, then two records that are not assistant.
    return [limit_record(reset), {"type": "last-prompt"}, {"type": "cost-state"}]


def jsonl(path):
    # One JSON object per line; a line still being written is skipped, as the log is read live.
    records = []
    for line in path.read_bytes().decode("utf-8").splitlines() if path.exists() else []:
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    return records


def session_of(folder):
    records = jsonl(folder / "state" / "run.jsonl")
    return next((r["session"] for r in records if r.get("event") == "start"), None)


def events(folder):
    # The run log's events for the case's one session, in order.
    session = session_of(folder)
    records = jsonl(folder / "state" / "run.jsonl")
    return [r.get("event") for r in records if r.get("session") == session]


def starts_of(folder):
    return jsonl(folder / "claude" / "starts.jsonl")


def stop(proc):
    # A driver the test left running is killed, so that no case outlives its test.
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=60)


class UsageLimitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp()
        cls.copy = driver_copy(cls.root)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, True)

    def start(self, runs, flags=()):
        # One case in its own folder: the fake claude with its runs, the fake gh, and the driver.
        folder = Path(tempfile.mkdtemp(dir=self.root))
        project = make_project(folder, drift_of(DASHED))
        (folder / "claude").mkdir()
        (folder / "gh").mkdir()
        # Written as bytes: on Windows, text mode would add a carriage return to each line.
        (folder / "claude" / "runs.json").write_bytes(json.dumps(runs).encode("utf-8"))
        claude = fake_claude(folder / "claude", do=DO)
        gh = fake_gh(
            folder / "gh", runs=[{"status": "completed", "conclusion": "success"}], prs=[OPEN_PR]
        )
        config = write_config(folder, project)
        command = [
            sys.executable,
            str(self.copy / "run-steps.py"),
            "--once",
            "--config",
            str(config),
        ]
        command += ["--state", str(folder / "state"), "--claude", claude, "--gh", gh, "--poll", "1"]
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        env["CLAUDE_CONFIG_DIR"] = str(folder / "config")
        proc = subprocess.Popen(
            [*command, *flags], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
        )
        self.addCleanup(stop, proc)
        return folder, proc

    def finish(self, folder, proc, bound=60):
        # The driver's code (None when killed at the bound) and its stdout lines, the uuid replaced.
        try:
            out, _ = proc.communicate(timeout=bound)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            out, code = proc.communicate(timeout=60)[0], None
        text = out.decode("utf-8")
        session = session_of(folder)
        return code, (text.replace(session, "<uuid>") if session else text).splitlines()

    def halt_after_end(self, folder):
        # Writes the halt file once the run log holds the session's first end line (30 s at most).
        until = time.monotonic() + 30
        while "end" not in events(folder) and time.monotonic() < until:
            time.sleep(0.1)
        (folder / "state" / "halt").write_bytes(b"halted by the test\n")
        return "end" in events(folder)

    def test_waits_and_resumes(self):
        # C09.1: the session hits a limit two seconds ahead and is resumed after it.
        reset = int(time.time()) + 2
        # The resumed session writes a later assistant record, as the CLI would on carrying on.
        runs = [{"records": limit_records(reset), "result": LIMITED}]
        folder, proc = self.start(runs + [{"records": [PLAIN], "result": DONE}])
        code, lines = self.finish(folder, proc)
        starts = starts_of(folder)
        resumed = starts[1] if len(starts) > 1 else {"args": [], "at": 0, "stdin": ""}
        args, session = resumed["args"], session_of(folder)
        self.assertEqual((code, len(starts), lines[-1:]), (0, 2, [OPENED]))
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith(WAITING) and lines[0].endswith("(session `<uuid>`)"))
        self.assertEqual(args[args.index("--resume") + 1 :][:1], [session])
        self.assertNotIn("--session-id", args)
        self.assertEqual((resumed["at"] >= reset, resumed["stdin"]), (True, PROMPT))
        self.assertEqual(events(folder), ["start", "pid", "end", "pid", "end"])

    def test_second_limit_parks(self):
        # C09.2: the resumed session's last assistant record is the limit again: the step parks.
        reset = int(time.time()) + 2
        runs = [{"records": limit_records(r), "result": LIMITED} for r in (reset, reset + 1)]
        folder, proc = self.start(runs)
        code, lines = self.finish(folder, proc)
        # The run's own issue is created too; the park's is the create call not titled "Driver run".
        creates = [c for c in read_calls(folder / "gh") if c[:2] == ["issue", "create"]]
        parks = [c for c in creates if not any("Driver run" in arg for arg in c)]
        self.assertEqual((code, len(starts_of(folder)), lines[-1:], len(parks)), (1, 2, [AGAIN], 1))

    def test_far_reset_parks(self):
        # C09.3: a reset 30 hours ahead parks at once; with --limit-hours 40 it is waited for.
        reset = int(time.time()) + 30 * 3600
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(reset))
        far = f"park: the usage limit resets at {when}, more than 6 hours away (session `<uuid>`)"
        runs = [{"records": limit_records(reset), "result": LIMITED}]
        folder, proc = self.start(runs)
        code, lines = self.finish(folder, proc, bound=10)
        self.assertEqual((code, len(starts_of(folder)), lines), (1, 1, [far]))
        folder, proc = self.start(runs, flags=["--limit-hours", "40"])
        ended = self.halt_after_end(folder)
        code, lines = self.finish(folder, proc, bound=10)
        self.assertEqual((ended, code, lines[-1:], len(starts_of(folder))), (True, 1, [HALT], 1))

    def test_halt_during_wait(self):
        # C09.4: the halt file written during a 60-second wait stops the driver within 5 seconds.
        folder, proc = self.start(
            [{"records": limit_records(int(time.time()) + 60), "result": LIMITED}]
        )
        ended = self.halt_after_end(folder)
        code, lines = self.finish(folder, proc, bound=5)
        self.assertEqual((ended, code, lines[-1:], len(starts_of(folder))), (True, 1, [HALT], 1))
        self.assertEqual(events(folder), ["start", "pid", "end"])

    def test_earlier_limit_is_not_the_last(self):
        # C09.5: no transcript, or a limit followed by a later assistant record, is no usage limit.
        later = [limit_record(int(time.time()) + 3600), {"type": "last-prompt"}, PLAIN]
        cases = {
            "no transcript": [{"result": LIMITED}],
            "later assistant": [{"records": later, "result": LIMITED}],
        }
        for name, runs in cases.items():
            with self.subTest(case=name):
                folder, proc = self.start(runs)
                code, lines = self.finish(folder, proc)
                self.assertEqual((code, lines, len(starts_of(folder))), (1, [UNKNOWN], 1))
