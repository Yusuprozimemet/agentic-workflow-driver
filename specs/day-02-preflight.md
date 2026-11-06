# Day 02 — The preflight names every piece of the kit and the CLI the driver misses

**Phase:** 0 · **Depends on:** Day 1 · **Expected PRs:** 4

## Goal
`python run-steps.py preflight --project <path>` names, one line each, every piece of the
project's kit and of the installed Claude Code CLI that the driver needs and does not find, and
`--dry-run` refuses on the same kit lines; an unreachable remote is no longer read as a missing
`main`.

## In scope
- `driver/preflight.py`: the kit's checks and the CLI's, each returning the lines of what is
  missing, none when nothing is. What `plan.md`'s "What the driver needs from the kit" names
  for the preflight: `scripts/spec-drift.py` and the fields of its `--out` JSON,
  `scripts/pr-names.py`, `.github/workflows/evidence.yml`. Picks up H01.3: the fields C01.6
  checks and the GitHub-read check move here, and are reported all at once instead of the first
  only.
- The remote read: `git ls-remote` that fails is "origin could not be read", not "no
  origin/main". Picks up H01.9. A project with no remote named `origin` (`git ls-remote
  --get-url origin` prints "origin" itself) is not that case: it still parks "the project has
  no origin/main", as C01.7 says. When the GitHub check's line is printed, the remote is not
  read again. Every git command the driver runs has `GIT_TERMINAL_PROMPT=0` in its environment,
  so an unattended run never waits on a login prompt.
- The CLI: `claude --version` and `claude --help`, nothing else. The program is `--claude
  <program>`, by default `claude` found on `PATH` (`shutil.which`). The flags it must list are
  the ones `plan.md`'s "What to build", item 2, passes to `claude -p`, and `--resume` from the
  same item.
- `run-steps.py preflight --project <path> [--claude <program>]`: the kit's checks, then the
  CLI's. `--dry-run` runs the kit's checks only: it starts no session, so it needs no CLI.
- Tests in `tests/test_preflight.py`. Track A also edits the fixture of `tests/test_dry_run.py`,
  and only the fixture: `make_project` writes an empty `scripts/pr-names.py` and
  `.github/workflows/evidence.yml`, and `drift_of` gives its day `"status": "active"`. No
  assertion changes: with the two rules of the remote read above, the no-remote case of
  `DryRunTest.test_origin_main_is_read_live` still parks and `DryRunTest.test_github_unread_exits_2`
  still gets one line. No test reads a remote on github.com.

The lines, in the order they are printed. Each starts as shown; `<...>` is filled in:

| What is missing | The line |
|---|---|
| `scripts/spec-drift.py` | "cannot read the project: `<its path, under --project as given>` is missing" (as on Day 1) |
| `scripts/pr-names.py` | "cannot read the project: scripts/pr-names.py is missing" |
| `.github/workflows/evidence.yml` | "cannot read the project: .github/workflows/evidence.yml is missing" |
| `spec-drift.py` exits non-zero, or writes no JSON | as on Day 1: "cannot read the project: scripts/spec-drift.py exited 3", "... wrote no JSON" |
| `now.next_step`, `now.open_prs`, `order` or `days` in the JSON | "cannot read the project: spec-drift.py's JSON has no order", one line per field |
| `day`, `phase` or `status` in an entry of `days` | "cannot read the project: spec-drift.py's JSON has no days[0].status", the index from 0, one line per key |
| GitHub not read (C01.6's check, unchanged) | "cannot read the project: GitHub could not be read (...)" (as on Day 1) |
| `git ls-remote origin` exits non-zero, `origin` configured, no GitHub line above | "cannot read the project: origin could not be read (git ls-remote exited 128)" |
| the CLI program | "cannot run a session: claude is not found", the program as given |
| a version at the start of `--version`'s output | "cannot run a session: claude --version printed no version" |
| Claude Code 2.1.170 or newer | "cannot run a session: Claude Code 2.1.99 is older than 2.1.170, the oldest the driver was checked on" |
| a flag in `--help` | "cannot run a session: claude --help lists no --settings", one line per flag |

A key that is present with the value `null` is not missing: C01.3 parks on a day with no
phase, and that stays a park, not a refusal. When `spec-drift.py` is missing or fails, its
field lines are not printed; every other check still runs. When the CLI is not found, its
version and flag lines are not printed.

## Out of scope
- The live check that hooks from `--settings` are added to the project's on the installed CLI
  (`plan.md`, "What to build", item 1): it starts a paid session and needs a login, which CI has
  neither of. Day 3, where the driver's settings file and its halt hook first exist (H02.1).
- Running this preflight before a session starts: `--once` on Day 4 (H02.2), `on` on Day 6
  (H02.3), and `on`'s refusal while a manual branch is unmerged or a halt is set.
- Whether the project's `gh` login can see pull requests beyond what `spec-drift.py`'s caveat
  says: Day 1's GitHub-read check stays as it is.
- Adapting to an older kit: the preflight only names what is missing (`plan.md`, "How it is
  kept").
- Any change to `driver/decide.py` or `driver/steps.py`.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | C02.1–C02.3, C02.7: the kit's checks, in `--dry-run` |
| B | | C02.4–C02.6: the CLI's checks and the `preflight` command |

Track B builds on Track A's `driver/preflight.py`, so it branches from `main` after Track A
merged.

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [ ] C02.1 **new** — `python run-steps.py --dry-run --project <path>` prints exactly one line
      on stdout, the action, and exits 0 for "start" and "wait" and 1 for "park". When the
      project lacks a piece of the table of "In scope" above its CLI rows, it prints nothing on
      stdout, one line on stderr for each piece missing, in the table's order, and exits 2. A
      project with no `scripts/pr-names.py` and no `.github/workflows/evidence.yml`, whose JSON
      has no `order` and whose first day has no `status`, gives exactly these four lines:
      "cannot read the project: scripts/pr-names.py is missing", "cannot read the project:
      .github/workflows/evidence.yml is missing", "cannot read the project: spec-drift.py's JSON
      has no order", "cannot read the project: spec-drift.py's JSON has no days[0].status". A
      project lacking only `scripts/pr-names.py` gives its one line and exits 2. Day 1's
      `DryRunTest.test_prints_one_action_and_its_exit_code`,
      `DryRunTest.test_unreadable_project_exits_2` and `DryRunTest.test_github_unread_exits_2`
      still pass, their assertions unedited.
      Red today: the four-piece project gives one line, "cannot read the project:
      spec-drift.py's JSON has no order"; the project lacking only `scripts/pr-names.py` prints
      "start: " and its step and exits 0.
      Test: `PreflightTest.test_every_missing_piece_is_a_line`,
      `PreflightTest.test_one_missing_file_refuses`.
      Replaces: C01.6 — was: "When the project cannot be read it prints nothing on stdout, one
      line on stderr that names what is missing, and exits 2", for a missing
      `scripts/spec-drift.py`, a failing script, a missing `now.next_step`, `now.open_prs`,
      `order` or `days`, or GitHub not read.
- [ ] C02.2 **new** — When `git ls-remote origin` exits non-zero, the dry run prints nothing on
      stdout, "cannot read the project: origin could not be read (git ls-remote exited <its
      code>)" on stderr, and exits 2. With `origin` set to a path that does not exist, the code
      is the one git exits with there (128 with git 2.x), and the test reads it from git, not a
      constant. A remote that is read and has no `main`, and a project with no remote named
      `origin`, still give "park: the project has no origin/main" and exit 1 (C01.4, C01.7).
      Red today: the remote that does not exist gives "park: the project has no origin/main"
      and exit 1.
      Test: `PreflightTest.test_unreachable_origin_is_not_a_missing_main`.
- [ ] C02.3 **hold** — The dry run, preflight included, runs only reads and writes nothing in the
      project: Day 1's `DryRunTest.test_runs_only_reads` and
      `DryRunTest.test_project_is_unchanged` pass with their assertions unedited, and the dry
      run runs no `claude`.
      The break's check runs only `tests.test_dry_run.DryRunTest.test_runs_only_reads`: the
      same break also fails `DryRunTest.test_project_is_unchanged`, whose report holds a commit
      hash and does not replay (D01.17). Expected report: "not a read: ['git', 'fetch',
      'origin']".
      broken: the preflight reads the remote with `git fetch origin` instead of
      `git ls-remote` → <what `DryRunTest.test_runs_only_reads` reported>
- [ ] C02.4 **new** — `python run-steps.py preflight --project <path> --claude <program>` prints
      "preflight: ok" on stdout and exits 0 when nothing in the table of "In scope" is missing.
      Otherwise it prints nothing on stdout, one line on stderr for each piece missing, the
      kit's lines first and then the CLI's, in the table's order, and exits 2. The CLI's version
      is the `<major>.<minor>.<patch>` at the start of `<program> --version`'s output, compared
      number by number: "2.1.170 (Claude Code)" and "2.10.0 (Claude Code)" give no line,
      "2.1.99 (Claude Code)" gives "cannot run a session: Claude Code 2.1.99 is older than
      2.1.170, the oldest the driver was checked on", "Claude Code" and a `--version` that exits
      1 give "cannot run a session: <program> --version printed no version". A `--claude` that
      names no file gives "cannot run a session: <program> is not found" and no version or flag
      line. A project lacking `scripts/pr-names.py`, with a CLI at 2.1.99, gives the kit's line
      and then the version's.
      Red today: `run-steps.py` has no `preflight`; argparse exits 2 with its usage on stderr.
      Test: `CliPreflightTest.test_ok`, `CliPreflightTest.test_versions`,
      `CliPreflightTest.test_not_found`, `CliPreflightTest.test_kit_lines_come_first`.
- [ ] C02.5 **new** — `<program> --help` lists each of `--print`, `--model`, `--output-format`,
      `--max-budget-usd`, `--strict-mcp-config`, `--settings`, `--append-system-prompt-file`,
      `--session-id` and `--resume`, or the preflight prints "cannot run a session: <program>
      --help lists no <flag>" for each one it does not. A flag is listed when the help text has
      it followed by a character that is not a letter, a digit or `-`, or at the end of the
      text. A flag ending in `-file` is also listed when the help text has the flag without
      `-file` followed by `[-file]`: Claude Code 2.1.170 lists `--append-system-prompt-file`
      only as "--append-system-prompt[-file]". Near misses each give their flag's line: a help
      with `--settings-file` and no `--settings`, one with `--append-system-prompt` and no
      `[-file]` after it, and one with `--printer` and no `--print`.
      Red today: `run-steps.py` has no `preflight`.
      Test: `CliPreflightTest.test_every_flag_is_listed`, `CliPreflightTest.test_near_miss_flags`.
- [ ] C02.6 **new** — The preflight runs only reads and starts no session: the commands it runs
      are the dry run's reads (C01.7), the project's `scripts/spec-drift.py`, and
      `<program> --version` and `<program> --help`, each with no other argument. It writes
      nothing in the project. The test records every command as `DryRunTest.test_runs_only_reads`
      does and fails on any other, a `<program> -p` among them.
      Red today: `run-steps.py` has no `preflight`.
      Test: `CliPreflightTest.test_runs_only_reads`.
- [ ] C02.7 **hold** — A day whose `phase` is `null` gives no preflight line: the key is there.
      With `order` 1, 2, Day 1 in Phase 0 and Day 2's `phase` `null`, the spec step of Day 2
      gives exit 1 and "park: Day 02 or the day before it names no phase", as C01.3 says. Day 2
      and not Day 1: the first day of `order` gives no phase's end, so a null phase there starts.
      Test: `PreflightTest.test_null_phase_still_parks`.
      broken: the preflight counts a `null` value as missing → <what the test reported>

## Verify
```bash
python -m unittest discover -s tests
```

## Notes
- The tests' CLI is a fake program each test writes into its temporary folder: on Windows a
  `claude.cmd` that runs a Python script with `sys.executable`, elsewhere an executable Python
  script whose first line names `sys.executable`. The script prints the `--version` and `--help`
  text the test gives it. No test runs the installed `claude`; CI has none.
- Track B's PR also runs `python run-steps.py preflight --project <a kit project>` against the
  CLI installed on the maintainer's PC (2.1.170 on 2026-11-06) and records what it printed: the
  check of C02.5's `[-file]` rule against the real help text, which no CI run makes.
- Why `preflight` is a command of its own and not part of `--dry-run`: the dry run starts no
  session, so requiring the CLI there would refuse a dry run that needs none, and Day 1's dry-run
  tests would all need a fake CLI.
- C02.2 changes what the dry run prints for an unreachable remote without a `Replaces:` line:
  `decide()` is unchanged and still parks on no `main` (C01.4), and a project with no `origin`
  still parks as C01.7 says; what changes is that the facts never reach `decide()` when a
  configured remote cannot be read. C02.1 replaces C01.6, whose list of exit-2 causes this
  extends.
- C02.5 proves that the help text names each flag, not that the CLI accepts it: in 2.1.170,
  `--append-system-prompt-file` appears only inside `--bare`'s description, and the option line
  is `--append-system-prompt <prompt>`. Only a session shows a flag is accepted (H02.1).
- C02.3 and C02.6 see only the commands run through `subprocess.run`, which the tests patch. A
  `claude` started with `Popen`, or with `run` imported by name, escapes the record; the `git`
  calls cannot, since the test asserts `git status` was recorded. Track B's brief says to run
  every command through `subprocess.run`.
- **Defect** D02.1 — found: spec-change PR · cause: process · made: Day 02 · drafting this spec,
  the main session checked whether the CLI accepts `--append-system-prompt-file` by running
  `claude -p` on it: a live session, which the budget cap ended after $0.11. The spec keeps the
  preflight to `--version` and `--help`, which start nothing.
- **Defect** D02.2 — found: Day 02 review · cause: process · made: Day 01 · Day 01's In scope
  said its closing PR adds `tests/test_contract.py` to `frozen` in `spec-drift.config.json`;
  `frozen` on `main` is still empty, so CI guards no contract test.
- **Defect** D02.3 — found: Day 02 review · cause: process · made: Day 01 · Day 01's In scope
  said its closing PR names `393dda6` in `README.md` as a kit commit the contract test passed
  on; `README.md` still says "none yet (Day 1 adds `ContractTest`)".
- **Hand-off** H02.1 → Day 3: the live check that `--settings` hooks are added to the
  project's on the installed CLI (`plan.md`, "What to build", item 1). It needs a session, so a
  test that skips without `claude` and a login, and Day 3's spec decides how a skip is kept from
  passing unseen.
- **Defect** D02.4 — found: auditor · cause: spec · made: Day 02 · C02.2 read every failing
  `git ls-remote` as an unreachable remote, so a project with no `origin` refused instead of
  parking as C01.7 says, and `DryRunTest.test_origin_main_is_read_live` turned red. Fixed in
  this spec change (In scope, C02.2).
- **Defect** D02.5 — found: auditor · cause: spec · made: Day 02 · the remote was read even
  after the GitHub check's line, so `DryRunTest.test_github_unread_exits_2` got two lines and
  ran `git ls-remote` against github.com. Fixed in this spec change (In scope).
- **Defect** D02.6 — found: auditor · cause: spec · made: Day 02 · C02.1, a `new` criterion,
  named `PreflightTest.test_null_phase_still_parks`, which passes on today's code, so "Track
  tests seen red" would fail Track A. Moved to the `hold` C02.7, on Day 2 of `order`.
- **Defect** D02.7 — found: auditor · cause: spec · made: Day 02 · In scope said the fixture
  edits needed no assertion change, which was false while D02.4 and D02.5 stood. Fixed in this
  spec change, with them.
- **Defect** D02.8 — found: auditor · cause: spec · made: Day 02 · C02.3's break fails two
  tests, one whose report holds a commit hash and does not replay (D01.17). Its check now names
  the one test and the expected report.
- **Defect** D02.9 — found: auditor · cause: spec · made: Day 02 · H02.2 sent the preflight only
  to `on` on Day 6, but Day 4's `--once` starts a session first. Split into H02.2 and H02.3.
- **Hand-off** H02.2 → Day 4: `--once` runs this preflight before it starts a session and
  refuses with its lines.
- **Hand-off** H02.3 → Day 6: `on` runs this preflight first and refuses with its lines
  (`plan.md`, "How it is kept").
- D02.2 and D02.3 are fixed in this day's spec-change PR (the maintainer, 2026-11-06), so that
  `frozen` guards `tests/test_contract.py` before either track: `spec-drift.config.json` gets
  `tests/test_contract.py` in `frozen`, and `README.md` names `393dda6` as a kit commit the
  contract test passed on.
- The `preflight` command stays separate from `--dry-run`, and the live `--settings` check goes
  to Day 3 (H02.1), as this spec proposed (the maintainer, 2026-11-06).
