"""Run tests/ one file per process, in parallel; print failures and the counts.

The same tests as `python -m unittest discover -s tests`, each file run by
exactly that command restricted to it (`-p <file>`), so imports and paths do
not change. Most of the suite's time is spent starting processes (the driver,
git, the fake gh), which parallelises well. Each file's time is kept in
.claude/state/test-times.json (gitignored) and the slowest start first.
Finer splits were slower: test_once.py's setUpClass then runs once per test,
and test_once_halt.py, which misses its 5-second stop under load, runs alone.
CI keeps the serial command.

A failing file's whole output is kept in .claude/state/test-failures/ (gitignored), and its
path printed: two flaky failures (D07.27, D08.81) were seen once, not kept, and their cause is
still unknown. --repeat N runs each file N times and says how often each failed.

    python scripts/test-parallel.py            # all tests, one worker per CPU
    python scripts/test-parallel.py -j 4 test_once_*.py
    python scripts/test-parallel.py --repeat 10 test_once_halt.py
"""

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
TIMES = ROOT / ".claude" / "state" / "test-times.json"
FAILURES = ROOT / ".claude" / "state" / "test-failures"
# Timing-sensitive: the driver must stop within 5 seconds of a halt, which a
# loaded machine misses. Run alone, after the others.
SOLO = {"test_once_halt.py"}


def run(name):
    start = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", name],
        check=False,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = proc.stdout + proc.stderr
    ran = re.search(r"^Ran (\d+) tests?", out, re.MULTILINE)
    skipped = re.search(r"skipped=(\d+)", out)
    return {
        "name": name,
        "code": proc.returncode,
        "ran": int(ran.group(1)) if ran else 0,
        "skipped": int(skipped.group(1)) if skipped else 0,
        "seconds": time.monotonic() - start,
        "output": out,
    }


def keep(result, stamp):
    """Write a failing run's whole output to FAILURES; its path, or None when it cannot be written."""
    path = FAILURES / f"{stamp}-{result['name'].removesuffix('.py')}-{result['round']}.txt"
    try:
        FAILURES.mkdir(parents=True, exist_ok=True)
        path.write_text(result["output"], encoding="utf-8")
    except OSError:
        return None
    return path


def load_times():
    try:
        return json.loads(TIMES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pattern", nargs="?", default="test*.py")
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 4)
    parser.add_argument("--repeat", type=int, default=1, metavar="N", help="run each file N times")
    args = parser.parse_args(argv)

    jobs = sorted(p.name for p in TESTS.glob(args.pattern))
    if not jobs:
        print("no test files match", file=sys.stderr)
        return 2
    times = load_times()
    # Slowest first, so a long file does not start last and leave workers idle.
    jobs.sort(key=lambda name: -times.get(name, 1.0))

    start = time.monotonic()
    rounds = range(max(args.repeat, 1))
    shared = [(name, n) for n in rounds for name in jobs if name not in SOLO]
    with concurrent.futures.ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(lambda job: dict(run(job[0]), round=job[1]), shared))
    results += [dict(run(name), round=n) for n in rounds for name in jobs if name in SOLO]
    elapsed = time.monotonic() - start

    times.update({r["name"]: round(r["seconds"], 2) for r in results})
    try:
        TIMES.parent.mkdir(parents=True, exist_ok=True)
        TIMES.write_text(json.dumps(times, indent=1, sort_keys=True), encoding="utf-8")
    except OSError:
        pass

    failed = [r for r in results if r["code"] != 0 or r["ran"] == 0]
    stamp, shown = time.strftime("%Y%m%dT%H%M%S"), set()
    for r in failed:
        if r["name"] not in shown:  # with --repeat, each file's first failure in full
            shown.add(r["name"])
            print(f"===== {r['name']} (exit {r['code']}) =====")
            print(r["output"].rstrip())
        path = keep(r, stamp)
        print(f"kept: {path}" if path else f"kept: nothing, {FAILURES} cannot be written")
    ran = sum(r["ran"] for r in results)
    skipped = sum(r["skipped"] for r in results)
    slowest = max(results, key=lambda r: r["seconds"])
    print(
        f"Ran {ran} tests in {elapsed:.1f}s "
        f"({args.jobs} workers; slowest {slowest['name']} {slowest['seconds']:.1f}s)"
    )
    for name in sorted({r["name"] for r in failed}) if args.repeat > 1 else ():
        print(f"{name} failed {sum(r['name'] == name for r in failed)} of {args.repeat}")
    if failed:
        print(f"FAILED ({len(failed)}: {', '.join(sorted({r['name'] for r in failed}))})")
        return 1
    print(f"OK (skipped={skipped})" if skipped else "OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
