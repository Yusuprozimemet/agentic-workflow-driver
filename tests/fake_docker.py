"""A fake `docker` for the container tests: it answers `version`, `image inspect`, `inspect`, `kill`
and `run` from the answers given to fake_docker, and records each call's arguments. No test but the
ones for C10.7, C10.14 and C10.30 needs a real Docker; the rest run this fake, as the other tests
run their fake claude and gh."""

import json
import os
import sys
from pathlib import Path

# The fake program: it records its arguments in calls.jsonl beside it, then answers from fake.json
# beside it. A missing key prints nothing and exits 0; a `run` with no matching tail does the same;
# a `run` entry with `answers` gives its answers in turn: the n-th run with its tail gets the n-th.
# An answer may hold `files`, a dict of absolute host path -> text: the fake writes each (parents
# created, as bytes) before it prints, as a session writes its transcript into the mounted state.
# A run may hold `until_kill`, a container name: after its files the fake waits until docker is
# asked `kill <name>`, then writes {"ended": "itself"} to ended.jsonl beside it; it gives up after
# 30 s, with exit 1 and no line. Any other first argument exits 99.
FAKE = """import json
import sys
import time
from pathlib import Path

folder = Path(__file__).resolve().parent
args = sys.argv[1:]
with (folder / "calls.jsonl").open("ab") as calls:
    calls.write(json.dumps({"args": args}).encode("utf-8") + b"\\n")
spec = json.loads((folder / "fake.json").read_text(encoding="utf-8"))
if args[:1] == ["version"]:
    answer = spec["version"]
elif args[:2] == ["image", "inspect"]:
    answer = spec["image"]
elif args[:1] == ["inspect"]:
    answer = spec["inspect"]
elif args[:1] == ["kill"]:
    answer = spec["kill"]
elif args[:1] == ["run"]:
    run = next((run for run in spec["run"] if args[-len(run["tail"]) :] == run["tail"]), {})
    if "answers" in run:
        # The n-th run with this tail, this one included, gets answers[n - 1]; the last repeats.
        tail = run["tail"]
        recorded = (folder / "calls.jsonl").read_text(encoding="utf-8").splitlines()
        seen = sum(json.loads(line)["args"][-len(tail) :] == tail for line in recorded)
        answer = run["answers"][min(seen, len(run["answers"])) - 1]
    else:
        answer = run
else:
    sys.exit(99)
for path, text in answer.get("files", {}).items():
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(text.encode("utf-8"))
if "until_kill" in answer:
    # The container runs until its kill is recorded; a kill that never comes fails the run in 30 s.
    kill = ["kill", answer["until_kill"]]
    deadline = time.monotonic() + 30
    while True:
        recorded = (folder / "calls.jsonl").read_text(encoding="utf-8").splitlines()
        if any(json.loads(line)["args"] == kill for line in recorded):
            break
        if time.monotonic() >= deadline:
            sys.exit(1)
        time.sleep(0.05)
    with (folder / "ended.jsonl").open("ab") as ended:
        ended.write(json.dumps({"ended": "itself"}).encode("utf-8") + b"\\n")
sys.stdout.write(answer.get("stdout", ""))
sys.stderr.write(answer.get("stderr", ""))
sys.exit(answer.get("code", 0))
"""


def fake_docker(folder, version=None, image=None, inspect=None, kill=None, run=None):
    # Each answer is a dict of stdout, stderr and code. A version given none answers 29.4.3, as a
    # Docker that runs does; the others answer nothing and exit 0 unless the test says otherwise.
    spec = {
        "version": {"stdout": "29.4.3\n"} if version is None else version,
        "image": image or {},
        "inspect": inspect or {},
        "kill": kill or {},
        "run": run or [],
    }
    # Files are written as bytes: on Windows, text mode would add a carriage return to each line.
    (folder / "fake.json").write_bytes(json.dumps(spec).encode("utf-8"))
    (folder / "fake.py").write_bytes(FAKE.encode("utf-8"))
    if os.name == "nt":
        program = folder / "docker.cmd"
        program.write_bytes(f'@"{sys.executable}" "%~dp0fake.py" %*\r\n'.encode())
    else:
        program = folder / "docker"
        program.write_bytes(f"#!{sys.executable}\n{FAKE}".encode())
        program.chmod(0o755)
    return str(program)


def docker_calls(folder):
    # The argument lists the fake recorded, in order; none when it never ran.
    path = Path(folder) / "calls.jsonl"
    if not path.exists():
        return []
    return [json.loads(line)["args"] for line in path.read_text(encoding="utf-8").splitlines()]


def docker_ended(folder):
    # The lines the runs that ended by a kill wrote, one per run; none when no run ended so.
    path = Path(folder) / "ended.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
