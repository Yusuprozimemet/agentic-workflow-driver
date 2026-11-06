# Day 03 — The stop before the start: `halt` stops a driver, and its settings refuse what a session may not do

**Phase:** 1 · **Depends on:** Day 2, and the plan change of #11 · **Expected PRs:** 7

## Goal
Before any session is started, the driver has its stop: a config that names the project, a lock
that names the driver's process, a settings file of its own whose hooks refuse every tool call
while the halt file exists, and refuse a merge, a push to `main` and an edit to the driver's
folder at all times, and `python run-steps.py halt` and `clear`, shown on a stand-in process; and
a test on the installed CLI that `--settings` hooks are still added to the project's.

## In scope
- **The state folder.** The halt file, the lock and the settings file live in one folder, by
  default `state/` in the driver's repository, ignored by git (`.gitignore`). Every command that
  touches them takes `--state <dir>` instead, so that no test writes into the repository's own
  `state/`. Nothing in the folder is committed.
- **The config** (`driver/config.py`), a JSON file, by default `driver.json` in the driver's
  repository, ignored by git; `--config <file>` instead. Four keys, all required: `project` (a
  path), `human_only` (a list of paths, possibly empty), `budget_usd` (a number above 0),
  `steps_per_night` (an integer of 1 or more). `--dry-run` and `preflight` take the project from
  `--project` when it is given, as today, and from the config's `project` when it is not. The
  config is read only when `--project` is not given; when it is read, it is checked whole, one
  stderr line per problem, exit 2, nothing on stdout:

  | Problem | The line |
  |---|---|
  | the file is missing | "cannot start: no --project, and no config at `<path as given>`" |
  | not JSON, or not an object | "cannot start: `<path>` is not a JSON object" |
  | a key missing | "cannot start: `<path>` has no budget_usd", one line per key, in the order above |
  | a key of the wrong type or range | "cannot start: `<path>`'s budget_usd must be a number above 0", and so on per key |

  Nothing else reads the budget, the human-only list or the steps per night this day: Days 4 and
  6 do.
- **The lock** (`driver/lock.py`): `take(state)` creates `<state>/lock` with `os.O_CREAT |
  os.O_EXCL` and writes `{"pid": <this process>, "started": "<ISO 8601, UTC>"}`; `read(state)`
  returns the pid and the start, or nothing; `release(state)` removes the lock only when it names
  this process. `take` refuses, with one line and no change to the file:
  - while the lock's process lives: "cannot start: the driver is already running (pid 1234,
    since 2026-11-07T21:00:00Z)";
  - when its process is gone: "cannot start: a lock names pid 1234, which is gone;
    `run-steps.py clear` removes it". Taking a stale lock over by the table of "Recovery" is
    Day 7's (H03.3).
  Whether a pid lives: on POSIX `os.kill(pid, 0)`; on Windows `OpenProcess` and
  `GetExitCodeProcess` through `ctypes` (`STILL_ACTIVE`, 259). **Never `os.kill(pid, 0)` on
  Windows**: there signal 0 is `CTRL_C_EVENT`, so it sends Ctrl+C to a console process group,
  and it reports a process that has exited as alive (Notes). A pid that lives is the lock's only
  when its process started no later than the lock's `started` (2 s of slack): Windows reuses
  pids, and a process that started after the lock was written is not the driver, so it counts
  as gone. The start: on Windows `GetProcessTimes`; on POSIX `ps -o etime= -p <pid>` taken from
  now. A lock file that is empty or not a JSON object with both keys is "a lock that cannot be
  read": `take` refuses with "cannot start: `<state>/lock` cannot be read; `run-steps.py clear`
  removes it". Nothing calls `take` this day but the tests; `--once` takes the lock on Day 4
  (H03.1).
- **The halt hook** (`hooks/halt.py <halt file>`): exits 2 with one stderr line, "halted: `<halt
  file>` exists; run-steps.py clear removes it", while the file exists; exits 0 and prints nothing
  when it does not; exits 2 with "halted: the halt hook was given no halt file" when called with
  no argument. It reads nothing from the environment: `CLAUDE_PROJECT_DIR` is the project's
  folder in a session the driver starts (`plan.md`, "Where the driver lives"). It does not read
  stdin.
- **The guard hook** (`hooks/guard.py <driver folder>`): reads the PreToolUse JSON on stdin and
  exits 2 with one stderr line naming the rule, or 0 and nothing:

  | Tool and input | Refused when | The line starts |
  |---|---|---|
  | `Bash`, `PowerShell`: `tool_input.command` | it holds `gh pr merge` as words | "refused by the driver: a session never merges" |
  | the same | a `git push` in it names `main` as a destination among its own arguments, read up to the next `&&`, `\|\|`, `;`, `\|` or newline: the word `main`, or a refspec ending `:main` or `:refs/heads/main` | "refused by the driver: a session never pushes to main" |
  | the same | it names the driver's folder, compared case-insensitively on Windows, with either slash, and in Git Bash's `/c/...` form of a drive path | "refused by the driver: the driver's folder is not a session's" |
  | `Edit`, `Write`, `MultiEdit`, `NotebookEdit`: `tool_input.file_path` or `notebook_path` | the path, resolved, is the driver's folder or under it | the same |
  | any | stdin is not a JSON object | "refused by the driver: the guard could not read the tool call" |

  Passed, among others: `git push -u origin day-03/track-a-config`, `git push origin
  maintenance`, `git push -u origin day-03/x && gh pr create --base main`, `gh pr create ...`,
  `gh pr view 12`, `gh pr checks 12 --watch`, an edit in the project, a command that names a
  folder whose name only starts like the driver's (`agentic-workflow-driver-old`). A bare `git
  push` on `main` names no destination and passes, and a path relative to the project
  (`../agentic-workflow-driver/state/halt`) is not resolved: the hook reads the command, not
  git's configuration or the shell's working directory (Notes).
- **The settings file** (`driver/settings.py`): `write(state, home)` writes
  `<state>/settings.json`, the driver's whole contribution to a session's hooks:
  `PreToolUse`, matcher `*`, the halt hook with `<state>/halt`; `PreToolUse`, matcher
  `Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit`, the guard hook with `home`. Each command
  names `sys.executable`, the hook's script and its argument by absolute path, each quoted, so a
  path with a space works. It writes the file afresh each time and returns its path.
- **`python run-steps.py halt [--state <dir>]`**, in this order: creates `<state>` when it is
  missing (a fresh clone has no `state/`); writes `<state>/halt` (its text:
  "halted at <ISO 8601, UTC>"); then, when the lock names a process that lives, kills that
  process's whole tree; prints one line; exits 0, or 1 when a kill failed. It deletes nothing and
  needs no project and no config.
  - The tree: on Windows `taskkill /PID <pid> /T /F`; on POSIX `os.killpg(pid, SIGKILL)` when the
    process leads its own group (`os.getpgid(pid) == pid`), otherwise `os.kill(pid, SIGKILL)`
    and the line says only that process was killed. `--once` makes the driver lead its own group
    on POSIX (Day 4, H03.1).
  - The lines: "halt: set; killed pid 1234 and the processes it started", "halt: set; killed pid
    1234 only: it does not lead its process group", "halt: set; no driver is running", "halt:
    set; could not kill pid 1234: <the reason>", and, with exit 1, "halt: set; `<state>/lock`
    cannot be read, so nothing was killed".
- **`python run-steps.py clear [--state <dir>]`**: while the lock names a process that lives,
  removes nothing, prints "clear: pid 1234 still runs; halt again, or stop it by hand", exits 1.
  Otherwise removes the halt file and a lock whose process is gone or that cannot be read, prints "clear: the halt is
  removed; the driver is off" (or "clear: no halt is set" when there was none) and exits 0. It
  never starts anything: turning the driver on again is `on`, Day 6.
- **The live check** (`tests/test_live_cli.py`, `LiveCliTest`), picks up H02.1 and audit
  finding 4: skipped, with the reason "DRIVER_LIVE_CLI is not set", unless `DRIVER_LIVE_CLI`
  names the Claude Code program. Each test makes a scratch git project whose own
  `.claude/settings.json` has a `PreToolUse` hook on `Bash` that appends a line to a marker file,
  and a scratch state folder with the driver's settings written by `driver/settings.py`. It runs
  `<program> -p <prompt> --model <DRIVER_LIVE_MODEL, default haiku> --output-format json
  --max-budget-usd 0.50 --strict-mcp-config --permission-mode auto --settings
  <state>/settings.json --allowedTools Bash` in the project, with a timeout of 300 s.
  `--permission-mode auto` is passed so the run does not depend on the maintainer's
  `~/.claude/settings.json`, as Day 4's sessions will not. CI has no login and no budget, so it
  skips there; the evidence is the maintainer's run by hand (Notes).
- Tests in `tests/test_config.py`, `tests/test_lock.py`, `tests/test_hooks.py`,
  `tests/test_halt.py` and `tests/test_live_cli.py`. Day 1's and Day 2's test files are not
  edited. Each new test file imports `driver.config`, `driver.lock` or `driver.settings` in
  `setUp` (`importlib`), not at module level, as `tests/test_steps.py` does: CI's "Track tests
  seen red" counts a module that does not load on `main` as not run, not as red.
  `LiveCliTest.setUp` imports `driver.settings` before it calls `skipTest`, so on `main` each
  live test errors (red) and on the track's head it is skipped (passes) where
  `DRIVER_LIVE_CLI` is unset.
- The config's `project`, when relative, is resolved against the config file's folder.
  `.gitignore` gains `/state/` and `/driver.json`, anchored to the repository's root.

## Out of scope
- Starting a session, the run log, `--session-id` in a real step, `--permission-mode auto`
  (#11), and a halt during a real step — Day 4 (H03.1).
- `--once` and `on` refusing while the halt file is set — Day 4 and Day 6 (H03.1, H03.4).
- The check of the driver's own repository before each step — Day 4 (H03.5).
- Writing what was in progress to the run's issue (a halt's step 4) and the phone's `STOP` —
  Day 5 (H03.2).
- Taking over a lock whose process is gone, by the table of "Recovery" — Day 7 (H03.3).
- The en dash `spec-drift.py` prints, read as strict UTF-8, and the dry run's stdout codepage
  (H02.4, H01.8) — Day 4 (H03.6).
- `--permission-mode` in the preflight's flag check — Day 4 (H03.7).
- The kit's ignoring of `evidence-rehearsal.json` and `evidence.json` after a close — a kit
  `tooling/` PR, the maintainer's (Phase 1 audit, finding 7; H03.8).
- Refusing a Claude Code version the live check has not passed on — Day 4 (H03.9).
- Any change to `driver/decide.py`, `driver/steps.py` or the preflight's lines.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | C03.1: the config, `--config`, `.gitignore` |
| B | | C03.2: the lock |
| C | | C03.3, C03.4: the halt hook and the guard hook |
| D | | C03.5–C03.7: the settings file, `--state`, `halt` and `clear` |
| E | | C03.8: the live check |

D needs B's lock and C's hooks; E needs D's settings file: each branches from `main` after the
one before it merged. A, B and C do not depend on each other. C03.9 is held by every track. A
track that would pass 400 changed lines is split by a spec change first, not on its branch:
CI's "Track tests seen red" knows only the rows of this table.

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [ ] C03.1 **new** — With no `--project`, `python run-steps.py --dry-run --config <file>` takes
      the project from the config and prints the same action as with `--project` (exit 0, 1 as
      Day 1). With a config that is not JSON it prints "cannot start: `<file>` is not a JSON
      object" on stderr, nothing on stdout, and exits 2; with `{"project": "<path>"}` alone it
      prints exactly three lines, for `human_only`, `budget_usd` and `steps_per_night`, in that
      order; with `"budget_usd": 0` the line "cannot start: `<file>`'s budget_usd must be a number
      above 0"; with no `--project` and no config at the path, "cannot start: no --project, and no
      config at `<file>`". `preflight --config <file>` takes the project the same way. A
      relative `project` is read from the config file's folder. `git check-ignore -q driver.json
      && git check-ignore -q state/halt` exits 0 in this repository.
      Red today: argparse exits 2 on every run with `--config`: "invalid choice: '<file>'" for
      `--dry-run --config <file>` (the unknown option's value is read as the command), "the
      following arguments are required: --project" for `preflight --config <file>`; each `git
      check-ignore -q` exits 1.
      Test: `ConfigTest.test_project_from_config`, `ConfigTest.test_preflight_from_config`,
      `ConfigTest.test_relative_project`, `ConfigTest.test_every_problem_is_a_line`,
      `ConfigTest.test_missing_config`, `ConfigTest.test_state_and_config_are_ignored`.
- [ ] C03.2 **new** — `driver.lock.take(state)` writes `{"pid": <os.getpid()>, "started": <ISO
      8601>}` to `<state>/lock` and returns no line; a second `take` while that process lives
      returns "cannot start: the driver is already running (pid <n>, since <started>)" and
      leaves the file's bytes as they were; with a lock naming a process that has exited (the
      pid of a child the test started and waited for), it returns "cannot start: a lock names
      pid <n>, which is gone; `run-steps.py clear` removes it". `release` leaves a lock that
      names another pid. A lock naming a live child but with a `started` an hour before the
      child began counts as gone (a reused pid). An empty lock file, or one that is not JSON,
      returns "cannot start: `<state>/lock` cannot be read; `run-steps.py clear` removes it".
      Asking whether a live child lives leaves it running (the test then ends it itself and
      reads its exit code).
      Red today: `driver/lock.py` does not exist; the tests' `setUp` import raises
      `ImportError`, so each test errors.
      Test: `LockTest.test_take_writes_pid_and_start`, `LockTest.test_live_lock_refuses`,
      `LockTest.test_stale_lock_refuses`, `LockTest.test_reused_pid_is_gone`,
      `LockTest.test_unreadable_lock_refuses`, `LockTest.test_release_keeps_anothers_lock`,
      `LockTest.test_asking_does_not_kill`.
- [ ] C03.3 **new** — `python hooks/halt.py <file>` exits 2 with "halted: <file> exists;
      run-steps.py clear removes it" on stderr while the file exists, and 0 with nothing on
      stdout or stderr when it does not, whatever `CLAUDE_PROJECT_DIR` is (unset, or another
      folder) and whatever the working directory; with no argument it exits 2 with "halted: the
      halt hook was given no halt file".
      Red today: `hooks/halt.py` does not exist; Python exits 2 with "can't open file".
      Test: `HaltHookTest.test_refuses_while_halt_file_exists`,
      `HaltHookTest.test_passes_without_halt_file`, `HaltHookTest.test_no_argument_refuses`.
- [ ] C03.4 **new** — `hooks/guard.py <driver folder>` refuses, exit 2 and the line of In
      scope's table, each of: `gh pr merge 12 --squash`; `git push origin main`; `git push
      origin HEAD:main`; `git push origin HEAD:refs/heads/main`; `git switch x && git push
      origin main`; a `Bash` command naming the driver's folder in either slash form, in the
      `/c/...` form when the folder is on a drive (and, on Windows, another case); a `Write`
      whose `file_path` is `<driver folder>/state/halt`; stdin `not json`. It passes, exit 0 and
      no output: `git push -u origin day-03/track-a-config`, `git push origin maintenance`, `git
      push -u origin day-03/x && gh pr create --base main`, `git push origin x; git switch main`,
      `gh pr view 12`, `gh pr checks 12 --watch`, a `Write` in a scratch project, a `Bash`
      command naming `<driver folder>-old`.
      Red today: `hooks/guard.py` does not exist; every case exits 2 with "can't open file", so
      the passing cases fail.
      Test: `GuardHookTest.test_refuses`, `GuardHookTest.test_passes`.
- [ ] C03.5 **new** — `driver.settings.write(state, home)` writes `<state>/settings.json`, a JSON
      object whose only key is `hooks`, with the two `PreToolUse` entries of In scope. Each
      entry's command, run through the shell (`shell=True`, as Claude Code runs a hook) from a
      folder that is not the driver's, with `CLAUDE_PROJECT_DIR` set to that folder, and with a
      space in the state folder's path: the halt command exits 2 while `<state>/halt` exists and
      0 when it does not; the guard command, given `git push origin main` on stdin, exits 2.
      Red today: `driver/settings.py` does not exist; `ImportError`.
      Test: `SettingsTest.test_settings_name_both_hooks`,
      `SettingsTest.test_commands_run_from_anywhere`.
- [ ] C03.6 **new** — A stand-in driver (a Python process the test starts in its own process
      group, which starts a child, both sleeping and both writing their pid to a file) whose pid
      is in `<state>/lock`: `python run-steps.py halt --state <state>` prints "halt: set; killed
      pid <n> and the processes it started" and exits 0; within 5 s both processes are gone;
      `<state>/halt` exists; and the halt command of `<state>/settings.json` written by
      `driver.settings.write` then exits 2. With no lock, or a lock whose process is gone, it
      prints "halt: set; no driver is running", writes the halt file and exits 0. A second
      `halt` leaves the halt file in place and exits 0. With a `--state` folder that does not
      exist, it creates it and writes the halt file. With an empty lock file it prints "halt:
      set; `<state>/lock` cannot be read, so nothing was killed" and exits 1.
      Red today: `run-steps.py` accepts only `preflight` as a command: argparse exits 2 with
      "invalid choice: 'halt'".
      Test: `HaltTest.test_halt_kills_the_tree`, `HaltTest.test_halt_with_no_driver`,
      `HaltTest.test_halt_twice`, `HaltTest.test_halt_creates_state`,
      `HaltTest.test_halt_unreadable_lock`.
- [ ] C03.7 **new** — `python run-steps.py clear --state <state>` after a halt with no live
      process removes `<state>/halt` and a lock whose process is gone, prints "clear: the halt is
      removed; the driver is off" and exits 0; with no halt file it prints "clear: no halt is set"
      and exits 0; while the lock names a live process (the test's own child) it prints "clear:
      pid <n> still runs; halt again, or stop it by hand", exits 1, and both files are still
      there.
      Red today: argparse exits 2 with "invalid choice: 'clear'".
      Test: `ClearTest.test_clear_removes_halt_and_stale_lock`, `ClearTest.test_clear_no_halt`,
      `ClearTest.test_clear_refuses_while_driver_lives`.
- [ ] C03.8 **hold** — With `DRIVER_LIVE_CLI` naming the installed Claude Code (2.1.170 or newer),
      on the maintainer's PC:
      (a) with no halt file, the prompt "Run this exact command with the Bash tool: echo driver >
      out.txt" leaves `out.txt` in the scratch project and a line in the project hook's marker
      file: the driver's hooks ran beside the project's, not in their place;
      (b) with `<state>/halt` set, the same prompt leaves no `out.txt`, the project hook's
      marker file got a line (a Bash call was attempted, and the project's hook ran beside the
      driver's halt hook, which refused it), and the JSON's `is_error` is false: the
      session ran, and its tool call was refused, not skipped;
      (c) `--append-system-prompt-file <rules>`, whose rules say "End every reply with the line
      PARK: live check", with `-p "Say hello."` and `--session-id <a new uuid4>`: the JSON's
      `result`, stripped of whitespace, ends with "PARK: live check" and its `session_id` is
      that uuid; then `-p "Run this exact command with the Bash tool: echo resumed >
      out2.txt" --resume <that uuid>` exits 0, its JSON's `session_id` is the same uuid,
      `out2.txt` exists and the marker file got another line: hooks hold on a resumed session.
      Without `DRIVER_LIVE_CLI`, all three are skipped with "DRIVER_LIVE_CLI is not set".
      True today: Tracks C and D (#15, #16) put the hooks and the settings file on `main`, so
      on `main`'s code the three tests load and skip without `DRIVER_LIVE_CLI`, and pass with
      it; Track E adds only the test file. Its teeth are shown by a break run by
      hand, on the maintainer's PC: the halt command in the written settings made to exit 0 →
      (b) fails, `out.txt` exists. CI cannot replay it (no login, no budget): the Track E PR and
      the close record it as a sentence, not a `broken:` line (`specs/README.md`, "Evidence at
      the close").
      Test: `LiveCliTest.test_settings_hooks_are_added`, `LiveCliTest.test_halt_refuses_a_tool_call`,
      `LiveCliTest.test_rules_file_and_resume`.
- [ ] C03.9 **hold** — Day 1's and Day 2's tests pass with their files unedited: `git diff
      --exit-code 0efd4d2 -- tests/test_contract.py tests/test_decide.py tests/test_dry_run.py
      tests/test_preflight.py tests/test_steps.py tests/test_kit_copy.py` prints nothing, and
      `python -m unittest discover -s tests` passes with them in it.
      To break once: the config read even when `--project` is given (no `driver.json` exists
      where the tests run, so the run refuses with "cannot start: no --project, and no config")
      → a `DryRunTest` fails; and one test file edited → the diff exits 1.

## Verify
```bash
python -m unittest discover -s tests
git -c core.safecrlf=false diff --exit-code 0efd4d2 -- tests/test_contract.py tests/test_decide.py tests/test_dry_run.py tests/test_preflight.py tests/test_steps.py tests/test_kit_copy.py
```

## Notes
- Written 2026-11-06 from the Phase 1 plan-auditor's findings 1-4 (`main` at `0efd4d2`), after
  the plan change of #11 gave Day 3 the config, the lock and the live check. The spec-auditor
  ran on the draft (`main` at `8d5b177`) and reported 17 findings; the spec-change PR fixed
  them, or names them here as known limits (D03.6 to D03.12).
- **Where the settings go** (finding 3): a file the driver writes into its ignored state folder,
  not JSON passed in `--settings`'s argument. On Windows, `claude` may be a `.cmd` shim, and JSON
  in an argument passes through `cmd.exe`'s quoting; a file passes a path. The file is written
  afresh before each session (Day 4), so a session that edited it changes only its own run, and
  the guard hook refuses that edit anyway.
- **The guard reads the command, not what a program does**, as `auditor-guard.py` does: a bare
  `git push` while on `main`, or a script that merges, gets through. GitHub's protection of
  `main` is what stops a push there at level 2 ("What this does not stop"); at level 1 the
  maintainer merges. A path relative to the project's folder that reaches the driver's
  (`../agentic-workflow-driver/...`) gets through the Bash rule the same way: the hook does not
  know the shell's working directory. Known limits, not criteria.
- **`os.kill(pid, 0)` on Windows is not a liveness check.** Signal 0 is `signal.CTRL_C_EVENT`,
  so Python sends Ctrl+C to a console process group (`GenerateConsoleCtrlEvent`) rather than
  asking; on a process that has exited and been waited for, it raises nothing, so it reads as
  alive. (The draft said it calls `TerminateProcess`; the spec-auditor's run on Python 3.12.10
  showed a child left alive, and only `os.kill(child, 15)` ended it.) `LockTest.test_stale_lock_refuses`
  is the test that catches a check written the POSIX way.
- **Which shell runs a hook.** C03.5 runs each command with `shell=True` (cmd.exe on Windows);
  Claude Code on Windows may run hooks through Git Bash. Unverified here: C03.8 (a) and (b) are
  the check that the commands run as Claude Code runs them.
- **Not tested:** "halt: set; killed pid 1234 only: it does not lead its process group" (POSIX
  only, and `--once` leads its group from Day 4) and "halt: set; could not kill pid 1234"
  (a kill that fails needs a process the test cannot own). C03.6 allows 5 s for the tree to go,
  where `plan.md` ("The switches") says a halt takes effect within a second: the slack is for a
  loaded CI machine, not the behaviour.
- **A skip passes unseen.** After this day every run without `DRIVER_LIVE_CLI` prints "OK
  (skipped=3)", so a Claude Code update that drops `--settings` hooks fails no run until the
  maintainer runs the live check by hand. `plan.md`'s item 1 ("an update ... fails a test and
  not a run") is met only for a run by hand; H03.9 gives Day 4 the rest.
- C03.8 costs a few cents per run on Haiku. `DRIVER_LIVE_MODEL` changes the model. Run it by
  hand after every Claude Code update: `DRIVER_LIVE_CLI=claude python -m unittest
  tests.test_live_cli`.
- `specs/README.md`'s "Map to plan.md" said "Day 1 specified" for Days 1-2, both closed, and
  "titles" for Days 3-8: this spec's spec-change PR fixes both rows. `plan.md`'s "Phases"
  ("Days 1 and 2 have specs ... The days after them are titles") goes stale too; that sentence is
  `plan.md`'s, left to the maintainer.
- **Defect** D03.1 — found: auditor · cause: spec · made: none · `plan.md`'s Phase 1 titles left
  the config, the lock, the driver's self-check and the run's issue to no day, and `--project`
  is required, though "The switches" say the config names the project. Fixed by #11's titles.
- **Defect** D03.2 — found: auditor · cause: spec · made: none · `plan.md`'s halt test ("a test
  starts a step, halts, and checks the process is gone") could not run on Day 3: no session
  exists until Day 4, and the pid to kill comes from a lock no day owned. Fixed by #11: a
  stand-in process on Day 3 (C03.6), a real step on Day 4 (H03.1).
- **Defect** D03.3 — found: auditor · cause: spec · made: none · `plan.md` passed the driver's
  hooks with `--settings` from its own folder, but in a driver-started session
  `CLAUDE_PROJECT_DIR` is the project, so hooks written as the kit's are (a path under that
  variable) would not be found. Fixed by #11 (absolute paths) and C03.5.
- **Defect** D03.4 — found: auditor · cause: spec · made: none · `plan.md`'s session command
  passed no `--permission-mode`, so `auto` came only from the maintainer's
  `~/.claude/settings.json`. Fixed by #11; the session and its preflight check are Day 4's.
- **Defect** D03.5 — found: self · cause: process · made: none · #11's first description
  headed its first section "What was built", not the template's "What I built", and listed its
  own self-check items in place of the template's: "Description uses the template" failed. The
  body was rewritten from `.github/pull_request_template.md`, and the check passed.
- **Defect** D03.6 — found: auditor · cause: spec · made: Day 03 · C03.1's `git check-ignore -q
  driver.json state/halt` could never exit 0: git refuses `-q` with two paths ("fatal: --quiet
  is only valid with a single pathname", exit 128). Now one `check-ignore -q` per path.
- **Defect** D03.7 — found: auditor · cause: spec · made: Day 03 · C03.8 (b), "leaves no
  `out.txt`", passed whenever the session never ran Bash: a lost login, a declined prompt or a
  CLI error passed it too. Now (b) needs the marker line and `is_error` false.
- **Defect** D03.8 — found: auditor · cause: spec · made: Day 03 · the draft said "Red today:
  ImportError" without saying where the import happens; a module-level import counts as "a test
  module did not load" in CI's "Track tests seen red", and a class-level skip passes on `main`
  too, so Track E would have failed CI. Now every new test file imports in `setUp`.
- **Defect** D03.9 — found: auditor · cause: spec · made: Day 03 · the draft said Windows'
  `os.kill(pid, 0)` calls `TerminateProcess` and kills the process; it sends Ctrl+C to a console
  group and reports an exited process as alive (Notes).
- **Defect** D03.10 — found: auditor · cause: spec · made: Day 03 · the guard's push rule read
  the whole command, so `git push -u origin x && gh pr create --base main` would have been
  refused and parked a step; and its folder rule missed Git Bash's `/c/...` form. Now it reads
  the push's own arguments and matches the `/c/...` form.
- **Defect** D03.11 — found: auditor · cause: spec · made: Day 03 · `halt` trusted the lock's
  pid: after a crash, a reused Windows pid would have had an unrelated process tree killed, and
  `halt` did not say it creates a missing state folder. Now a process that started after the
  lock is gone, and `halt` creates the folder.
- **Defect** D03.12 — found: auditor · cause: spec · made: Day 03 · the draft offered a "track
  B2" if B grew past 400 lines, but CI's "Track tests seen red" fails a track that is not a row
  of the Tracks table; and three deferrals (the en dash and codepage, `--permission-mode` in
  the preflight, the evidence files) had no Hand-off ID. Now five tracks, and H03.6 to H03.8.
- **Defect** D03.13 — found: self · cause: spec · made: Day 03 · the live check allowed
  `"Bash(echo:*)"`, which under `--permission-mode auto` on Claude Code 2.1.170 does not cover
  `echo driver > out.txt`: the call was denied ("permission_denials" in the JSON, `is_error`
  false), so (a) and (c)'s resume failed, and (b) passed for the wrong reason, since no `out.txt`
  appeared halt or not. Seen in Track E's first live run; by hand, `"Bash(echo driver >
  out.txt)"` and `"Bash(echo *)"` were denied too, and only `Bash` wrote the file. Now `Bash`:
  the project is a scratch one, and the driver's guard hook still sees every call.
- **Defect** D03.14 — found: Track E · cause: spec · made: Day 03 · C03.8 was tagged `new` with
  "Red today: the `setUp` import of `driver.settings` fails", but Tracks C and D land that
  module before Track E, so on `main`'s code the tests skip, and CI's "Track tests seen red"
  failed #18 three times, "reports OK (skipped=1) on 5887c0b". The behaviour is true before
  Track E, which adds only its test: now `hold`, broken once by hand as before.
- **Defect** D03.15 — found: Track E · cause: environment · made: Day 03 · with `Bash` allowed,
  the live check was still denied the write: `tempfile.mkdtemp()` gave the 8.3 short path
  `C:\Users\HACKYO~1\...` as the session's cwd, and Claude Code 2.1.170 asked before writing
  there, which `-p` turns into a denial. With the long path, all three passed. The test now
  takes `os.path.realpath` of its scratch root. D03.13 was half the cause: in a long-path
  project, `"Bash(echo:*)"` was still denied.
- **Hand-off** H03.1 → Day 4: `--once` takes the lock and releases it, leads its own process
  group on POSIX, refuses while the halt file is set, writes the settings file before each
  session, and passes it; a test starts a real step, halts, and checks the session's tree is
  gone and its next tool call refused (`plan.md`, "What to build", item 3).
- **Hand-off** H03.2 → Day 5: a halt's step 4, what was in progress written to the run's issue.
- **Hand-off** H03.3 → Day 7: a lock whose process is gone taken over by the table of
  "Recovery"; until then `take` refuses it and `clear` removes it.
- **Hand-off** H03.4 → Day 6: `on` refuses while the halt file is set.
- **Hand-off** H03.5 → Day 4: the check of the driver's own repository (clean, at the commit it
  started from) must not count `state/` or `driver.json`, which git ignores, nor
  `evidence-rehearsal.json` and `evidence.json`, which a close leaves untracked in this
  repository too (`git status` shows `?? evidence-rehearsal.json` on 2026-11-06).
- **Hand-off** H03.6 → Day 4: the en dash `spec-drift.py` prints, read as strict UTF-8, and the
  dry run's stdout codepage (H02.4, H01.8): a real step reads that output, so Day 4's spec
  decides how.
- **Hand-off** H03.7 → Day 4: `--permission-mode` in the preflight's flag check
  (`driver/preflight.py`'s `FLAGS`); Day 4's spec carries a `Replaces: C02.5` line for it.
- **Hand-off** H03.8 → the maintainer: the kit's ignore list gains `evidence-rehearsal.json`
  and `evidence.json` (Phase 1 audit, finding 7), a kit `tooling/` PR.
- **Hand-off** H03.9 → Day 4: a skip of the live check passes unseen (H02.1's question). The
  live check records the Claude Code version it passed on, and the preflight refuses a version
  it has not, or Day 4's spec names why not.
- **Hand-off** H03.10 → Day 4: `--once` starts `claude -p` with the project as cwd; it passes
  `os.path.realpath` of the project, or a short Windows path denies every write (D03.15).
