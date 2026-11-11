"""The live check: `on` starts a session only on a Claude Code whose version is in
<state>/live-checked.txt. `run-steps.py live-check` writes that record, and only after the driver's
own tests (tests/test_live_cli.py) pass on the installed CLI with no skip. This module imports only
the standard library and driver.preflight, so that driver/once.py can import it."""

import os
import shutil
import subprocess
import sys

from driver.preflight import CLI, cli_lines

NAME = "live-checked.txt"


def version(*command):
    # The first line of `<command> --version`, stripped; "" when it prints none.
    probe = subprocess.run([*command, "--version"], check=False, **CLI)
    lines = probe.stdout.splitlines()
    return lines[0].strip() if lines else ""


def refusal(state, program, command=None):
    # None when the installed version is listed in the record, else the line `on` refuses with. A
    # record that cannot be read lists nothing. A command given reads the version in its place.
    try:
        with open(os.path.join(state, NAME), "rb") as record:
            data = record.read()
    except OSError:
        data = b""
    listed = [line.strip() for line in data.decode("utf-8", errors="replace").splitlines()]
    line = version(*command) if command is not None else version(shutil.which(program))
    if line in listed:
        return None
    return f"cannot start: Claude Code `{line}` has not passed the live check; run run-steps.py live-check"


def run(args, home):
    lines = cli_lines(args.claude)
    if lines:
        for line in lines:
            print(line, file=sys.stderr)
        return 2
    program = shutil.which(args.claude)
    # The tests skip unless DRIVER_LIVE_CLI names the program they check.
    env = {**os.environ, "DRIVER_LIVE_CLI": program}
    done = subprocess.run(
        [shutil.which(args.python) or args.python, "-m", "unittest", "tests.test_live_cli"],
        cwd=home,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    print(done.stdout, end="")
    # unittest's last line is "OK" only when nothing failed and nothing was skipped; a skip reads
    # "OK (skipped=2)" and proves nothing, so it records nothing.
    last = next((line.strip() for line in reversed(done.stdout.splitlines()) if line.strip()), "")
    if last == "OK" and done.returncode == 0:
        installed = version(program)
        os.makedirs(args.state, exist_ok=True)
        with open(os.path.join(args.state, NAME), "ab") as record:
            record.write(f"{installed}\n".encode())
        print(f"live-check: passed on `{installed}`")
        return 0
    print(f"live-check: nothing recorded: the run ended `{last}`")
    return 1
