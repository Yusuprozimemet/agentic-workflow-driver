# Day 06 — The loop: `on`, the checks waited on, a fix resumed twice at most, the merge waited for, `main` pulled

**Phase:** 1 · **Depends on:** Day 5 · **Expected PRs:** 11

## Goal
`python run-steps.py on` runs steps one after another under one run's issue, at most
`steps_per_night` of them. Each step's pull request is waited on: a red required check resumes
the step's own session with the failing lines, twice at most, and then parks. A green PR that
touches `plan.md` or a human-only path, or carries `Oversized:`, parks. Otherwise the loop waits
for the maintainer's merge, pulls `main` and waits for the evidence run on it. Then it takes the
next step. A halt, an open `STOP` issue and a closed run's issue are read during every wait, not
only during a session. `on` refuses while halted, on a failed preflight, and on a Claude Code
version the live check has not passed on.

## Before this day (the maintainer's)
- **H05.5**: run #35's two `gh` commands on a scratch repository (the URL last from
  `gh issue create`, exit 0 from a second `gh issue close`). Day 6 is the first day that relies
  on `park` and `close` across steps. If either differs, that is a spec change to this spec
  (plan-auditor, Phase 1 Days 6–8, finding 4).
- **H03.8**: the kit's ignore list gains `evidence-rehearsal.json` and `evidence.json`. Until it
  lands, every kit close leaves the project's tree not clean, so `on` parks after every close
  (C01.4's "park: the project's tree is not clean (1 paths)"). Day 6's tests do not depend on
  it; the trial (Day 8) does (plan-auditor finding 3).

## In scope
- **A clean tree brought to `main`** (H01.2; `plan.md`, "Recovery", the start table's last two
  rows), in `driver/tree.py`, `to_main(project, facts, step)`, called by `--once` and by `on`
  before `decide()`. It acts only when the tree is clean, `origin/main` exists, and no branch of
  the step exists, locally or on the remote. Then, when the project is on another branch or
  `main` is not `origin/main`, it runs `git fetch origin`, `git switch main` (only when on
  another branch) and `git merge --ff-only origin/main`, and reads the facts again. The git
  command is a parameter, `to_main(..., git=("git",))`, so a test passes a recorder that logs
  its arguments and runs the real git; the driver's callers pass nothing. A command
  that exits non-zero gives "park: cannot bring the project to main: git `<subcommand>` exited
  `<n>`". These are the only git commands that change the project (rule 7: no `reset`, `stash`,
  `clean`, checkout of a path). `decide()` is unchanged, and so is the dry run, which moves no
  branch (Day 1, decided 2026-11-06). A dirty tree, a detached HEAD, and a branch of the step
  still park from `decide()` with C01.4's lines, before any switch.
- **The pull request's state** (`driver/github.py`), each through `_gh`:
  - `checks(project, gh, number)` runs `gh pr checks <n> --required --json name,bucket,link` and
    returns `("pending" | "green" | "red" | "none", [names of failed checks], None)` or a reason.
    `bucket` "fail" or "cancel" is red; any "pending" with no red is pending; no check at all is
    "none"; otherwise green. `gh pr checks` exits 8 while checks are pending: that is read from
    the JSON, not treated as a failed call.
  - `failed_lines(project, gh, links)`: for each failed check whose link is an Actions job
    (`/actions/runs/<run>/job/<job>`), `gh run view --job <job> --log-failed`; the last 40 lines
    of each, the whole cut to its last 6,000 characters. A check with no Actions link gives its
    name and link only.
  - `pr_state(project, gh, number)` runs `gh pr view <n> --json state,mergeCommit,files,body`
    and returns the state, the merge commit's sha, the paths and the body. The body is read only
    for an `Oversized:` line and never goes into a prompt (`plan.md`, "What to build", item 2).
- **The run log's fixes** (`driver/runlog.py`): `fix(state, session, pr, n)` appends
  `{"event": "fix", "at", "session", "pr", "n"}` before a resume, fsynced as the other lines;
  `fixes(state, session)` returns how many `fix` lines the session has, or 2 when the log cannot
  be read (`plan.md`, "Recovery", rule 4: "when the log cannot say, both count as used").
- **The wait on a pull request** (`driver/loop.py`, `wait_pr(...)`), inside `on` only: after a
  step's session printed "opened: #n", and for an open pull request found at a start (the start
  table's fourth row, `decide()`'s "wait: #n"). `--once` does not wait: it still prints
  "opened: #n" and exits 0, and on an open pull request still prints Day 4's "wait: #n" (the
  held `OutcomeTest` cases). When `decide()` names more than one open pull request, `on` waits
  on none: "park: more than one open pull request: #3, #5" (one PR per track, never stacked;
  two open is the maintainer's to sort). Every `--poll` seconds it reads, in this order: the
  halt file; the open issues (a `STOP` issue halts as Day 5's does during a session: halt
  file, report on the run's issue, exit 1; the run's issue closed ends the run, below); then
  the checks.
  - Pending: wait. "none" for longer than `--wait-minutes` (default 30): "park: no required
    checks on #n after `<m>` minutes", `<m>` the value given.
  - Red, on a pull request this run's session opened, with `fixes` below 2: write the `fix`
    line, then resume the session: Day 4's command with `--resume <session>` in place of
    `--session-id <session>`, the prompt on stdin: "The required checks failed on #n: <names>.",
    the failing lines, then "Fix this step's pull request, push, and stop.". The session's
    outcome is read as Day 4's step 12 reads it; "opened: #n" again goes back to the wait, any
    other outcome is its park or refusal, and the run log's `end` line is written as on Day 4.
  - Red after two fixes: "park: the checks on #n are still red after two fixes: <names>".
    Red on a pull request with no session of this run (found at a start): "park: the checks on
    #n are red: <names>" (rule 4: after a crash the driver resumes nothing by itself).
  - Green: the path check, then the merge wait.
- **The path check** (`driver/loop.py`, `gated(paths, body, human_only)`): the first that
  applies, "park: #n touches plan.md"; "park: #n touches a human-only path: `<path>`" (a
  `human_only` entry matches a path equal to it, and an entry ending in `/` every path under
  it, both with `/` separators); "park: #n carries Oversized:" (a body line that starts with
  `Oversized:`). At level 1 the maintainer merges anyway: the park is the signal to read that PR
  closely, and closing it is the "go on" as for any park.
- **The merge waited for**: every `--poll` seconds the same halt and issue reads, then
  `pr_state`. "MERGED": `main` pulled (`to_main`), then the evidence run on the new
  `origin/main` head waited for (Day 4's `evidence_line`): "has not finished" and "no evidence
  run yet" are waited out up to `--wait-minutes`, then park with the same line and "after `<m>`
  minutes"; "ended `<conclusion>`" parks at once (Day 4, Notes: "Day 6's loop waits instead").
  "CLOSED": "park: #n was closed without a merge". No bound on the merge itself: the maintainer
  merges when they choose.
- **`on`** (`run-steps.py on`, `driver/loop.py`, `run(args, home, read_facts)`): `--once`'s
  checks in Day 4's order (halt first, H03.4; the config; the lock, held for the whole run; the
  driver's own repository; the preflight, H02.3), then the version check, then steps:
  - The version check (H04.2): `claude --version`'s first line must be a line of
    `<state>/live-checked.txt`, or "cannot start: Claude Code `<version>` has not passed the
    live check; run run-steps.py live-check", exit 2. `python run-steps.py live-check` runs
    `python -m unittest tests.test_live_cli` with `DRIVER_LIVE_CLI` set (unset, the file skips
    and proves nothing) and the installed CLI and, only when it ends in
    "OK" with no skip, appends the version line. The record lives in the state folder, written
    by the command and never by a test (Day 3 ruled out a test writing there; Day 4, Notes).
    `--once` does not check it: it is run at the PC, where its result is seen.
  - One run's issue for the run (H05.1): opened, or reused, before the first session; each later
    step comments on it (`open_run`'s existing path). Between steps, and in every wait, the
    issue is read: closed (by `off` or from the phone) gives "off: the run's issue #n is closed;
    nothing new starts", exit 0, with the current step's PR left open.
  - After `steps_per_night` sessions started (a resume does not count), the run's issue is closed
    with "on: <k> steps, the night's count", printed too, exit 0.
  - A park, a refusal or a halt ends the run: the park's issue opened as Day 5's, the run's
    issue closed with its line as `--once` closes it. `on` does not wait on its own parks: the
    next `on`, after the maintainer closes the issue, reads the start table from the top.
- **A bound on the session** (Day 4, Notes: "Day 6's loop, which runs unattended, decides a
  bound"): `--session-minutes` (default 120) for `on` and `--once`. Past it the session's tree
  is killed as a `STOP` kills it (Day 5), and the step parks with "park: the session ran past
  `<m>` minutes (session `<id>`)", `<m>` the value given, its `end` line written.
- The fake `gh` in `tests/test_github.py` gains `pr checks`, `pr view` and `run view`, and its
  `run list` (today one static `runs` answer) may be given a list too: each from a list in its
  spec that a test can step through (one answer per call, the last repeated); the
  fake `claude` in `tests/test_once.py` gains `--resume`, recorded as the other arguments are.

## Out of scope
- The reviewer, the merge by the driver, level 2 — Phase 2, not specified until the stop after
  Day 8 is lifted.
- The usage limit waited out and retried — Day 8, the trial, records how a headless session
  reports it first (`plan.md`, "Unverified"); Day 5 (Out of scope) gave it to Day 6, and this
  spec moves it (H06.1). Until then a session stopped by the limit parks as Day 4's outcome
  table says (an error, or no pull request and no `PARK:` line).
- A stale lock taken over, a run-log session whose process still lives, a `start` with no `end`,
  `status` and the run log's report — Day 7 (H03.3, H04.3, H04.4, H05.2). The park on
  uncommitted changes or an unfinished branch naming its paths, branch, commit and session —
  Day 7 (H05.4).
- Counting the 15 pull requests in a row merged at level 1 without a change asked, Level 2's
  entry condition (`plan.md`, "Levels") — Day 7's `status` or Day 8's record (H06.2;
  plan-auditor finding 9).
- `plan.md`'s switch table says `on` is "refused while a manual branch is unmerged"; its
  "Recovery" table says an open pull request from the maintainer's account is waited on. This
  spec follows "Recovery" ("Every start is the same start"), and the departure is recorded in
  the Notes.
- Any change to `driver/decide.py`, `driver/steps.py`, `driver/lock.py`, `driver/settings.py`,
  `driver/home.py`, `driver/preflight.py`, `driver/config.py`, the hooks, `rules/session.md`,
  `halt`, `clear`, `off`, `preflight` and the dry run's lines.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | C06.1: `driver/tree.py`, `to_main`, called from `--once` |
| B | | C06.2: `checks`, `failed_lines`, `pr_state`; the fake `gh`'s `pr checks`, `pr view`, `run view` |
| C | | C06.3: `runlog.fix`, `runlog.fixes` |
| D | | C06.4, C06.5: `wait_pr`'s checks, the resume, the fake `claude`'s `--resume`, the reads during the checks wait |
| E | | C06.6, C06.7, C06.13: the path check, the merge wait, `main` pulled, the evidence waited for, the reads during those waits |
| F1 | | No criterion of its own: `--once`'s `checked` split in `driver/once.py`, so that `on` can reuse its checks, the session's start and its end; `--once`'s lines unchanged, held by C04's and C05's tests |
| F2 | | C06.8, C06.9: `on`, the run's issue across steps, `steps_per_night` |
| G | | C06.10: `live-check` and the version check at `on` |
| H | | C06.11: `--session-minutes` |

A, B and C do not depend on each other; D needs B and C; E needs A, B and D; F2 needs E and F1;
G and H need F2's `on` (H touches `run_session`, which F2 does not). C06.12 is held by every track.
Estimated changed lines, from Day 5's: A 220, B 320, C 120, D 340, E 390, F1 170, F2 400, G 220,
H 200 (F1 and F2 measured, D06.5).
D, E and F2 sit near the limit: their briefs keep each test to the cases named here.
A track over 400 is split by a spec change (D03.12).

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [ ] C06.1 **new** — In a scratch git project with a bare remote, a clean tree on
      `day-05/close-the-day` with `main` one commit behind `origin/main` is brought to `main`
      equal to `origin/main` by `to_main`, and `--once` then starts the step (fake `claude`);
      the git commands `to_main` runs, recorded through its `git` parameter, are exactly
      `fetch origin`, `switch main`, `merge --ff-only origin/main`. A local `main` one commit ahead and one behind gives "park:
      cannot bring the project to main: git merge exited 128"; one only ahead is left as it is
      and gives C01.4's "park: main is not origin/main"; a dirty tree, a detached HEAD and a branch
      of the step give C01.4's lines and run no git command that changes the project. The dry
      run on the first project still prints "park: the project is on day-05/close-the-day, not
      on main".
      Red today: `driver/tree.py` does not exist; `ImportError`.
      Test: `TreeTest.test_brought_to_main`, `TreeTest.test_refusals_park`,
      `TreeTest.test_dry_run_moves_nothing`.
- [ ] C06.2 **new** — With the fake `gh`: `checks` gives "pending" for a pending check and a
      passing one (exit 8), "red" with the names of a "fail" and a "cancel" check, "green" for
      "pass" and "skipping", "none" for an empty list, and "gh pr checks exited 1" for exit 1;
      `failed_lines` returns the last 40 lines of each failed job's `--log-failed`, cut to its
      last 6,000 characters; `pr_state` returns the state, merge sha, paths and body; the
      recorded calls are exactly In scope's.
      Red today: `AttributeError: module 'driver.github' has no attribute 'checks'`.
      Test: `GitHubTest.test_checks`, `GitHubTest.test_failed_lines`, `GitHubTest.test_pr_state`.
- [ ] C06.3 **new** — `fix` appends one fsynced line; `fixes` counts a session's `fix` lines
      only, 0 for a session with none, and 2 for a log with a torn line.
      Red today: `AttributeError: module 'driver.runlog' has no attribute 'fix'`.
      Test: `RunlogFixTest.test_fixes_counted`, `RunlogFixTest.test_torn_log_counts_both`.
- [ ] C06.4 **new** — The wait on a pull request this run opened: checks red, red, green, with
      the fake `claude` opening the same PR each time, resumes the session twice, with
      `--resume <the session's id>`, the prompt starting "The required checks failed on #12:
      tests.", the failing lines in it and no PR title or body; two `fix` lines precede the
      resumes; then it goes on to the path check. Red three times gives "park: the checks on #12
      are still red after two fixes: tests" after two resumes. A red PR found at a start gives
      "park: the checks on #12 are red: tests" and resumes nothing. "none" past
      `--wait-minutes 0.01` gives "park: no required checks on #12 after 0.01 minutes". Two
      open pull requests at a start give "park: more than one open pull request: #3, #5" and
      no `pr checks` call.
      Red today: `driver/loop.py` does not exist.
      Test: `WaitTest.test_red_resumed_twice_then_green`, `WaitTest.test_red_after_two_fixes_parks`,
      `WaitTest.test_red_without_session_parks`, `WaitTest.test_no_checks_parks`,
      `WaitTest.test_two_open_prs_park`.
- [ ] C06.5 **new** — During the checks wait: a halt file written by the
      test ends the run within one poll, exit 1, nothing more started; an open `STOP` issue
      writes the halt file and the report on the run's issue, exit 1; the run's issue closed
      gives "off: the run's issue #7 is closed; nothing new starts", exit 0, and the PR is not
      closed (no `pr close` call recorded).
      Red today: `driver/loop.py` does not exist.
      Test: `WaitTest.test_halt_during_wait`, `WaitTest.test_stop_during_wait`,
      `WaitTest.test_off_during_wait`.
- [ ] C06.6 **new** — `gated` gives, first that applies, "park: #12 touches plan.md",
      "park: #12 touches a human-only path: `docs/kit.md`" (entry `docs/`), the same for an
      entry equal to the path, and "park: #12 carries Oversized:"; nothing for a PR that touches
      `driver/once.py` with `human_only` ["docs/"], or whose body only quotes the word in the
      middle of a line.
      Red today: `driver/loop.py` does not exist.
      Test: `GateTest.test_parks`, `GateTest.test_passes`.
- [ ] C06.7 **new** — The merge wait: "OPEN" twice, then "MERGED", pulls `main` (C06.1's three
      git commands), then waits through an evidence run "in_progress" to "success" and returns
      to the next step; "CLOSED" gives "park: #12 was closed without a merge"; an evidence run
      that ends "failure" parks at once with Day 4's line, and one still "in_progress" past
      `--wait-minutes 0.01` parks with Day 4's line and "after 0.01 minutes". The fake `gh`'s
      `run list` steps through its answers as `pr view`'s do.
      Red today: `driver/loop.py` does not exist.
      Test: `MergeWaitTest.test_merged_pulled_evidence_waited`,
      `MergeWaitTest.test_closed_parks`, `MergeWaitTest.test_evidence_failed_parks`,
      `MergeWaitTest.test_evidence_unfinished_parks`.
- [ ] C06.8 **new** — `on` refuses with `--once`'s lines and exit 2, before any session and
      with no lock left behind, when the halt file exists ("cannot start: halted: …"), on a
      failed preflight, and on a missing config key; it takes the lock once for the whole run
      and releases it at the end.
      Red today: `run-steps.py: error: argument command: invalid choice: 'on'`.
      Test: `OnTest.test_refusals`, `OnTest.test_one_lock_for_the_run`.
- [ ] C06.9 **new** — With `steps_per_night` 2 and the fake `gh` merging each PR: `on` starts two
      sessions, opens one run's issue and comments on it for the second step, closes it with
      "on: 2 steps, the night's count", prints that line and exits 0; a resume within a step
      does not count as a step. With the run's issue closed after the first merge, the second
      session never starts and the line is C06.5's.
      Red today: as C06.8.
      Test: `OnTest.test_steps_per_night`, `OnTest.test_off_between_steps`.
- [ ] C06.10 **new** — With `--claude` a fake printing `2.1.400 (Claude Code)`: `on` refuses with
      "cannot start: Claude Code `2.1.400 (Claude Code)` has not passed the live check; run
      run-steps.py live-check" when `<state>/live-checked.txt` is missing or lists another
      version, and goes on when it lists that line; `live-check` appends the line after a run
      that ends "OK", and not after one with a skip or a failure (a fake test runner passed by
      `--python`); `--once` does not read the file.
      Red today: as C06.8.
      Test: `LiveCheckTest.test_on_refuses_an_unchecked_version`,
      `LiveCheckTest.test_live_check_records_only_a_clean_pass`.
- [ ] C06.11 **new** — With `--session-minutes 0.01` and a fake `claude` that sleeps, `--once`
      kills the session's tree, prints "park: the session ran past 0.01 minutes (session `<id>`)",
      writes the `end` line with it, opens its `parked` issue and exits 1.
      Red today: "run-steps.py: error: argument command: invalid choice: '0.01' (choose from
      preflight, halt, clear, off, on, live-check)": the value is read as the positional command.
      Test: `SessionBoundTest.test_session_past_its_bound_parks`.
- [ ] C06.12 **hold** — Earlier days' tests pass with their files unedited, but for the fake
      `gh` in `tests/test_github.py` and the fake `claude` in `tests/test_once.py`:
      `git -c core.safecrlf=false diff --exit-code 6f9e72c -- tests/test_contract.py
      tests/test_decide.py tests/test_dry_run.py tests/test_steps.py tests/test_kit_copy.py
      tests/test_config.py tests/test_lock.py tests/test_hooks.py tests/test_halt.py
      tests/test_live_cli.py tests/test_encoding.py tests/test_runlog.py tests/test_home.py
      tests/test_preflight.py tests/test_once_outcome.py tests/test_once_halt.py
      tests/test_live_once.py tests/test_failures.py tests/test_halt_report.py
      tests/test_issues.py tests/test_off.py tests/test_once_park_issues.py
      tests/test_once_parks.py tests/test_once_run.py tests/test_once_stop.py` prints nothing,
      and `python -m unittest discover -s tests` passes with them in it. The list holds C04.14's
      and C05.12's: a track that must edit one of their files names this criterion in a
      `Replaces:` line (D06.1, D06.4), and changes this spec first. The base is 6f9e72c, after
      #60 ran `tests/test_once_outcome.py`'s and `tests/test_once_park_issues.py`'s cases in
      parallel with their assertions unchanged.
      Replaces: C04.14 — was: earlier days' tests pass with their files unedited, but for
      `tests/test_preflight.py`'s fake help text and flag list: the diff against 1dc0f03 prints
      nothing.
      Replaces: C05.12 — was: earlier days' tests pass with their files unedited, but for the
      fake `gh` and `test_session_command`'s `gh` calls: the diff against 93c94de prints nothing
      (red on `main` since #60, D06.4).
      To break once, in Track A: one listed test file edited → the diff exits 1.
- [ ] C06.13 **new** — During the merge wait and the evidence wait, as C06.5 during the checks
      wait: a halt file ends the run within one poll, exit 1; an open `STOP` issue writes the
      halt file and the report on the run's issue, exit 1; the run's issue closed gives "off:
      the run's issue #7 is closed; nothing new starts", exit 0, and no `pr close` call is
      recorded.
      Red today: `driver/loop.py` does not exist.
      Test: `MergeWaitTest.test_halt_during_merge_wait`, `MergeWaitTest.test_stop_during_evidence_wait`,
      `MergeWaitTest.test_off_during_merge_wait`.

## Verify
```bash
python -m unittest discover -s tests
git -c core.safecrlf=false diff --exit-code 6f9e72c -- tests/test_contract.py tests/test_decide.py tests/test_dry_run.py tests/test_steps.py tests/test_kit_copy.py tests/test_config.py tests/test_lock.py tests/test_hooks.py tests/test_halt.py tests/test_live_cli.py tests/test_encoding.py tests/test_runlog.py tests/test_home.py tests/test_preflight.py tests/test_once_outcome.py tests/test_once_halt.py tests/test_live_once.py tests/test_failures.py tests/test_halt_report.py tests/test_issues.py tests/test_off.py tests/test_once_park_issues.py tests/test_once_parks.py tests/test_once_run.py tests/test_once_stop.py
```

## Notes
- Picks up H01.2 (a clean tree brought to `main`), H02.3 (the preflight at `on`), H03.4 (`on`
  refuses while halted), H04.2 (the version check and where its record lives), H05.1 (one run's
  issue across steps, `STOP` read during the waits), H01.5 (the evidence run checked on every
  start, C06.7), Day 4's two notes for Day 6 (the evidence run waited for; a bound on the
  session), Day 5's Out of scope (red after two fixes, the path check), and reads the config's
  `steps_per_night` and `human_only`, which `driver/config.py` validates and nothing reads yet.
  Plan-auditor on Phase 1's Days 6–8, 2026-11-07, on `main` at `1226331`: 9 findings, none
  blocking; findings 1–4 shape this spec, 5–7 are D06.1–D06.3 below.
- Second audit, 2026-11-08, on `main` at `6f9e72c` after #44–#60 (dashboard, tooling and docs
  work): the plan-auditor found 4 (#60 broke C05.12; H01.5 not cited; H01.4 and H01.7 unowned;
  C06.7's "after 30 minutes"), and nothing in #44–#60 touched `driver/`, `run-steps.py`,
  `.github/` or `specs/README.md`; the spec-auditor found 7 (#60 again; `--once` not said to
  skip the wait; C06.11's quoted error; the fake's `run list`; C06.5 in the wrong track; no way
  to record `to_main`'s git commands; C06.7 again) and notes (`GitHubTest`, a Day 3 note cited
  that does not exist, several open PRs, `DRIVER_LIVE_CLI`). This spec change takes all of
  them: C06.5 is split, the merge and evidence parts becoming C06.13 in Track E. Both left
  unverified, for the scratch repository with H05.5: `gh pr checks` exiting 8 while pending,
  and `git merge --ff-only` exiting 128 on a diverged `main`.
- H01.7 was done in #2 (Day 01 Notes); nothing to carry. H01.4 stays in force: writing a day
  spec is the maintainer's, and `on` parks at every day's spec step (`driver/steps.py`).
- For the maintainer's review of this spec, each a recommendation:
  1. **The bring-to-`main` lives outside `decide()`.** H01.2 said Day 6 would change C01.4 with
     a `Replaces:` line. Kept in `driver/tree.py` instead, called before `decide()`, so the dry
     run keeps parking on another branch (Day 1's decision that it moves no branch) and C01.4
     stays in force unchanged. No `Replaces: C01.4` is needed. A departure from H01.2's wording,
     not its intent: the start table's order holds (a branch of the step parks before any
     switch).
  2. **`--once` also brings the tree to `main`** ("Recovery", rule 3: every start is the same
     start). No Day 4 or Day 5 test sets up a clean tree on another branch for `--once` (only
     `tests/test_decide.py` and `tests/test_dry_run.py` hold that park), so no earlier test
     changes.
  3. **The checks are polled, not `--watch`ed.** `plan.md` ("What to build", item 2) says
     `gh pr checks <n> --watch`. A blocking `--watch` cannot read `STOP` or the run's issue
     while it waits, which H05.1 asks for, so `checks` reads `--json` every `--poll` seconds.
     Only required checks count (`--required`), as `main`'s protection does.
  4. **The version record is `<state>/live-checked.txt`, written by `run-steps.py live-check`.**
     A committed list would need a driver PR per Claude Code release; a test writing the state
     folder was ruled out on Day 3. The command runs the live tests, which start real sessions
     and cost a little, once per CLI version.
  5. **An open pull request at a start is waited on**, as "Recovery"'s table says, not refused,
     as the switch table's "refused while a manual branch is unmerged" says. If it goes red the
     driver parks; it resumes only a session this run started.
  6. **The path check parks at level 1 too.** The maintainer merges anyway; the park says which
     PR to read closely. Recommend keeping it, so that level 2 inherits a gate already tried.
  7. **The usage limit moves to Day 8** (H06.1): how a headless session reports it is
     unverified, and a criterion written now would guess the wording.
- `park()`'s comment path ("one park per reason") never ran inside `--once` (Day 5, spec-auditor
  finding 9). In `on` it still does not: a park ends the run, and the next start waits on the
  open `parked` issue before any park line is reached. It stays covered by C05.2's unit test only.
- The en dash: the waits print only lines built by the driver; `failed_lines` decodes CI's log
  as UTF-8 with `errors="replace"`, as `_gh` does.
- **Defect** D06.1 — found: dashboard · cause: spec · made: Day 04 · C04.14 restated C03.9's hold
  with `tests/test_preflight.py` exempted but carried no `Replaces: C03.9` line, so C03.9 stayed
  in force and its diff against 0efd4d2 read "code broken" in the replay history at every merge
  from the Day 05 close on (#49). Fixed by the spec change #50. C06.12 names the same risk for
  C04.14 and C05.12.
- **Defect** D06.2 — found: self · cause: implementation · made: none · `scripts/break.py`
  opened `--file` from its own working directory, not from `--cwd`, and did not refuse when the
  two trees differed: replaying C04.8's break with `--cwd <worktree>` from the repository root
  broke the main tree's `driver/once.py` while the tests ran in the worktree, and reported "The
  check passed with the break in" (#51's own replay, discarded). Fixed by #53: with `--cwd`,
  a `--file` outside its tree is refused before anything is read or written. No manifest entry
  uses `cwd`, so no replay was affected.
- **Defect** D06.3 — found: dashboard · cause: process · made: Day 05 · Day 05 (f18d7fa) added a
  second `classify(sentence).prefix)` call to `driver/once.py`, so C04.8's break manifest entry
  matched twice, `break.py` refused it ("occurs 2 times"), and the replay history (#49) showed
  C04.8 as "break no longer applies". Fixed by #51, a find unique at the Day 04 close and on
  `main`. Not on the maintainer's list for these Notes; the plan-auditor named it (finding 7).
- **Defect** D06.4 — found: auditor · cause: process · made: none · same-as: D06.1 · #60 (`tooling/`, bd6dfce)
  edited `tests/test_once_outcome.py` and `tests/test_once_park_issues.py`, files C05.12 holds,
  to run their cases in parallel, with no spec change and no `Replaces:` line, so C05.12 has
  been red on `main` since. The assertions are unchanged. Found by both auditors on 2026-11-08;
  fixed by this spec change (C06.12 re-based on 6f9e72c, `Replaces: C05.12`).
- **Defect** D06.5 — found: self · cause: spec · made: Day 06 · the Tracks table estimated Track F
  at 380 changed lines. That counted `on` and its tests but not the split of `driver/once.py`'s
  `checked`, one function holding `--once`'s checks, the session's start and its end, which `on`
  must reuse. The first implementation measured 578 lines, over the limit of 400. Split by this
  spec change into F1 (the split, 167 lines measured) and F2 (`on`, 398).
- **Hand-off** H06.1 → Day 8: how a headless session reports the usage limit, recorded from the
  trial; the wait and retry follow it (Day 5's Out of scope gave it to Day 6).
- **Hand-off** H06.2 → Day 7 | Day 8: the count of pull requests in a row merged at level 1
  without a change asked, Level 2's entry condition; nothing in Phase 1 counts it yet.
