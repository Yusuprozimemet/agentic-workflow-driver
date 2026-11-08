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
- [x] C06.1 **new** — In a scratch git project with a bare remote, a clean tree on
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
      Evidence: `TreeTest.test_brought_to_main`, `TreeTest.test_refusals_park`, `TreeTest.test_dry_run_moves_nothing` (#62).
      seen red: python -m unittest tests.test_tree on main → FAILED (errors=3) (#62)
      broken: to_main no longer stops on a dirty tree → AssertionError: Tuples differ: (True, None) != (False, None) (#62)
      broken: to_main no longer stops on a detached HEAD → AssertionError: Tuples differ: (True, None) != (False, None) (#62)
      broken: to_main no longer stops on a branch of the step → AssertionError: Tuples differ: (True, None) != (False, None) (#62)
      broken: the merge is no longer fast-forward only → AssertionError: Lists differ: [['fetch', 'origin'], ['merge', 'origin/main']] != [['fetch', 'origin'], ['merge', '--ff-only', 'origin/main']] (#62)
      broken: to_main switches even when already on main → AssertionError: Lists differ: [['fetch', 'origin'], ['switch', 'main'], ['merge', '--ff-only', 'origin/main']] != [['fetch', 'origin'], ['merge', '--ff-only', 'origin/main']] (#62)
      broken: once does not read the facts again after the move → AssertionError: 1 != 0 : (#62)
      broken: once does not call to_main → AssertionError: 1 != 0 : (#62)
      broken: the facts read switches the project to main → AssertionError: Tuples differ: (1, 'park: main is not origin/main\n') != (1, 'park: the project is on day-05/close-the-day, not on main\n') (#62)
- [x] C06.2 **new** — With the fake `gh`: `checks` gives "pending" for a pending check and a
      passing one (exit 8), "red" with the names of a "fail" and a "cancel" check, "green" for
      "pass" and "skipping", "none" for an empty list, and "gh pr checks exited 1" for exit 1;
      `failed_lines` returns the last 40 lines of each failed job's `--log-failed`, cut to its
      last 6,000 characters; `pr_state` returns the state, merge sha, paths and body; the
      recorded calls are exactly In scope's.
      Red today: `AttributeError: module 'driver.github' has no attribute 'checks'`.
      Test: `GitHubTest.test_checks`, `GitHubTest.test_failed_lines`, `GitHubTest.test_pr_state`.
      Evidence: `GitHubTest.test_checks`, `GitHubTest.test_failed_lines`, `GitHubTest.test_pr_state` (#64).
      seen red: python -m unittest tests.test_github.GitHubTest.test_checks tests.test_github.GitHubTest.test_failed_lines tests.test_github.GitHubTest.test_pr_state on main → FAILED (errors=10) (#64)
      broken: checks treats exit 8 as a failed call → AssertionError: Lists differ: [None, 'green', 'green'] != ['pending', 'green', 'green'] (#64)
      broken: checks does not count a cancelled check as red → AssertionError: Lists differ: ['tests'] != ['tests', 'build'] (#64)
      broken: a pending check beats a failed one → AssertionError: 'pending' != 'red' (#64)
      broken: failed_lines keeps 41 lines of a log → AssertionError: 'line 9\nline 10\nline 11\nline 12\nline 13\nli[367 chars]om/x' != 'line 10\nline 11\nline 12\nline 13\nline 14\nl[359 chars]om/x' (#64)
      broken: failed_lines keeps 6,001 characters → AssertionError: 'xxxx[272 chars]xxxxxx\n021xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx[5694 chars]xxxx' != 'xxxx[272 chars]xxxxx\n021xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx[5693 chars]xxxx' (#64)
      broken: pr_state reads the wrong merge commit field → AssertionError: Tuples differ: ('MERGED', None, ['plan.md', 'driver/loop.py'], 'Ove[16 chars]None) != ('MERGED', '1dc0f03aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa[54 chars]None) (#64)
- [x] C06.3 **new** — `fix` appends one fsynced line; `fixes` counts a session's `fix` lines
      only, 0 for a session with none, and 2 for a log with a torn line.
      Red today: `AttributeError: module 'driver.runlog' has no attribute 'fix'`.
      Test: `RunlogFixTest.test_fixes_counted`, `RunlogFixTest.test_torn_log_counts_both`.
      Evidence: `RunlogFixTest.test_fixes_counted`, `RunlogFixTest.test_torn_log_counts_both` (#66).
      seen red: python -m unittest tests.test_runlog_fix.RunlogFixTest.test_fixes_counted tests.test_runlog_fix.RunlogFixTest.test_torn_log_counts_both on main → FAILED (errors=5) (#66)
      broken: fixes counts every session's fix lines → AssertionError: 2 != 1 (#66)
      broken: fixes counts a session's start and end lines too → AssertionError: 3 != 1 (#66)
      broken: a fix line leaves out n → AssertionError: Items in the second set but not the first: (#66)
      broken: the run log's lines are not fsynced → AssertionError: 0 != 1 (#66)
      broken: a missing log counts as both fixes used → AssertionError: 2 != 0 (#66)
      broken: an unreadable log counts as one fix used → AssertionError: 1 != 2 (#66)
      broken: a log that cannot be opened raises → FAILED (errors=1) (#66)
- [x] C06.4 **new** — The wait on a pull request this run opened: checks red, red, green, with
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
      Evidence: `WaitTest.test_red_resumed_twice_then_green`, `WaitTest.test_red_after_two_fixes_parks`, `WaitTest.test_red_without_session_parks`, `WaitTest.test_no_checks_parks`, `WaitTest.test_two_open_prs_park` (#67). Against the fake `gh` only: H06.3.
      seen red: python -m unittest tests.test_wait on main → FAILED (errors=10) (#67)
      broken: the resume keeps --session-id → AssertionError: '--resume' not found in ['-p', '--settings', '<tmp>/state/settings.json', '--session-id', '00000000-0000-4000-8000-000000000000'] (#67)
      broken: the fix line is not written → AssertionError: Tuples differ: ('park: the session ended without a result[57 chars]', 1) != (None, 0) (#67)
      broken: the failing lines left out of the prompt → AssertionError: 'boom' not found in "The required checks failed on #12: tests.\nFix this step's pull request, push, and stop.\n" (#67)
      broken: a third fix allowed → AssertionError: 3 != 2 (#67)
      broken: a pull request with no session is resumed → FAILED (errors=1) (#67)
      broken: the park names a fixed number of minutes → AssertionError: Tuples differ: ('park: no required checks on #12 after 30 minutes', 1) != ('park: no required checks on #12 after 0.01 minutes', 1) (#67)
      broken: two open pull requests are waited on → AssertionError: Tuples differ: (None, 0) != ('park: more than one open pull request: #3, #5', 1) (#67)
- [x] C06.5 **new** — During the checks wait: a halt file written by the
      test ends the run within one poll, exit 1, nothing more started; an open `STOP` issue
      writes the halt file and the report on the run's issue, exit 1; the run's issue closed
      gives "off: the run's issue #7 is closed; nothing new starts", exit 0, and the PR is not
      closed (no `pr close` call recorded).
      Red today: `driver/loop.py` does not exist.
      Test: `WaitTest.test_halt_during_wait`, `WaitTest.test_stop_during_wait`,
      `WaitTest.test_off_during_wait`.
      Evidence: `WaitTest.test_halt_during_wait`, `WaitTest.test_stop_during_wait`, `WaitTest.test_off_during_wait` (#67).
      seen red: python -m unittest tests.test_wait on main → FAILED (errors=10) (#67)
      broken: the halt file is not read → AssertionError: the wait did not end on what the first sleep changed (#67)
      broken: a STOP issue writes no halt file → FAILED (errors=1) (#67)
      broken: a closed run's issue is not read → AssertionError: the wait did not end on what the first sleep changed (#67)
      broken: the checks are read while the issues cannot be → AssertionError: Tuples differ: (None, 0) != ('cannot read the project: gh issue list exited 1', 2) (#67)
- [x] C06.6 **new** — `gated` gives, first that applies, "park: #12 touches plan.md",
      "park: #12 touches a human-only path: `docs/kit.md`" (entry `docs/`), the same for an
      entry equal to the path, and "park: #12 carries Oversized:"; nothing for a PR that touches
      `driver/once.py` with `human_only` ["docs/"], or whose body only quotes the word in the
      middle of a line.
      Red today: `driver/loop.py` does not exist.
      Test: `GateTest.test_parks`, `GateTest.test_passes`.
      Evidence: `GateTest.test_parks`, `GateTest.test_passes`, `MergeWaitTest.test_gated_pr_parks` (#70).
      seen red: python -m unittest tests.test_merge_wait on main → FAILED (errors=22) (#70)
      broken: plan.md is not checked → AssertionError: 'park: #12 touches a human-only path: `docs/kit.md`' != 'park: #12 touches plan.md' (#70)
      broken: any path holding plan.md parks → AssertionError: 'park: #12 touches plan.md' is not None (#70)
      broken: an entry with no slash matches what is under it → AssertionError: 'park: #12 touches a human-only path: `docs/kit.md`' is not None (#70)
      broken: an entry ending in a slash matches nothing under it → AssertionError: 'park: #12 carries Oversized:' != 'park: #12 touches a human-only path: `docs/kit.md`' (#70)
      broken: Oversized: anywhere in a line parks → AssertionError: 'park: #12 carries Oversized:' is not None (#70)
      broken: the wait skips the path check → AssertionError: Tuples differ: ('park: #12 was closed without a merge', 1) != ('park: #12 touches a human-only path: `docs/kit.md`', 1) (#70)
      broken: the wait drops the config's human_only → AssertionError: Tuples differ: ('park: #12 was closed without a merge', 1) != ('park: #12 touches a human-only path: `docs/kit.md`', 1) (#70)
- [x] C06.7 **new** — The merge wait: "OPEN" twice, then "MERGED", pulls `main` (C06.1's three
      git commands), then waits through an evidence run "in_progress" to "success" and returns
      to the next step; "CLOSED" gives "park: #12 was closed without a merge"; an evidence run
      that ends "failure" parks at once with Day 4's line, and one still "in_progress" past
      `--wait-minutes 0.01` parks with Day 4's line and "after 0.01 minutes". The fake `gh`'s
      `run list` steps through its answers as `pr view`'s do.
      Red today: `driver/loop.py` does not exist.
      Test: `MergeWaitTest.test_merged_pulled_evidence_waited`,
      `MergeWaitTest.test_closed_parks`, `MergeWaitTest.test_evidence_failed_parks`,
      `MergeWaitTest.test_evidence_unfinished_parks`.
      Evidence: `MergeWaitTest.test_merged_pulled_evidence_waited`, `MergeWaitTest.test_closed_parks`, `MergeWaitTest.test_evidence_failed_parks`, `MergeWaitTest.test_evidence_unfinished_parks` (#70).
      seen red: python -m unittest tests.test_merge_wait on main → FAILED (errors=22) (#70)
      broken: a closed pull request counts as merged → AssertionError: Tuples differ: (None, 0) != ('park: #12 was closed without a merge', 1) (#70)
      broken: the merged step's own branch keeps main from being pulled → AssertionError: Lists differ: [] != [['fetch', 'origin'], ['switch', 'main'], ['merge', '--ff-only', 'origin/main']] (#70)
      broken: main is not pulled after the merge → AssertionError: Lists differ: [] != [['fetch', 'origin'], ['switch', 'main'], ['merge', '--ff-only', 'origin/main']] (#70)
      broken: the evidence is read for another commit → AssertionError: False is not true : another commit read (#70)
      broken: a failed evidence run counts as green → AssertionError: Tuples differ: (None, 0) != ('park: the evidence run on `<head>` ended `failure`', 1) (#70)
      broken: an unfinished evidence run is not waited out → AssertionError: Tuples differ: ('park: the evidence run on `<head>` has n[44 chars]', 1) != (None, 0) (#70)
      broken: the evidence park names a fixed number of minutes → AssertionError: Tuples differ: ('par[25 chars]head>` has not finished (`in_progress`) after 30 minutes', 1) != ('par[25 chars]head>` has not finished (`in_progress`) after 0.01 minutes', 1) (#70)
      broken: no origin/main is passed to the evidence read → FAILED (errors=1) (#70)
      broken: a failed pull request read ends the wait at once → AssertionError: 1 not greater than 1 (#70)
      broken: a failed evidence read ends the wait at once → AssertionError: 1 not greater than 1 (#70)
- [x] C06.8 **new** — `on` refuses with `--once`'s lines and exit 2, before any session and
      with no lock left behind, when the halt file exists ("cannot start: halted: …"), on a
      failed preflight, and on a missing config key; it takes the lock once for the whole run
      and releases it at the end.
      Red today: `run-steps.py: error: argument command: invalid choice: 'on'`.
      Test: `OnTest.test_refusals`, `OnTest.test_one_lock_for_the_run`.
      Evidence: `OnTest.test_refusals`, `OnTest.test_one_lock_for_the_run` (#73).
      seen red: python -m unittest tests.test_on on main → AssertionError: Tuples differ (#73)
      Not replayable, so a sentence and not in the manifest: on goes on after a failed preflight was broken in #73 and `OnTest.test_refusals` failed, but unittest cuts the report inside the scratch directory's random name (D06.25).
      broken: the lock is not released at the end → AssertionError: Tuples differ: (0, 1, 0, [True, True], True) != (0, 1, 1, [True, True], False) (#73)
- [x] C06.9 **new** — With `steps_per_night` 2 and the fake `gh` merging each PR: `on` starts two
      sessions, opens one run's issue and comments on it for the second step, closes it with
      "on: 2 steps, the night's count", prints that line and exits 0; a resume within a step
      does not count as a step. With the run's issue closed after the first merge, the second
      session never starts and the line is C06.5's.
      Red today: as C06.8.
      Test: `OnTest.test_steps_per_night`, `OnTest.test_off_between_steps`.
      Evidence: `OnTest.test_steps_per_night`, `OnTest.test_off_between_steps` (#73), and the next step re-read after a merge, `OnTest.test_next_step_read_after_merge` (#74).
      seen red: python -m unittest tests.test_on on main → AssertionError: Tuples differ (#73)
      broken: the night runs one step past its count → AssertionError: Tuples differ: (0, "on: 3 steps, the night's count", 3, 1, 1, ['1[50 chars]alse) != (0, "on: 2 steps, the night's count", 2, 1, 1, ['1[50 chars]alse) (#73)
      broken: a resume counts as a step → AssertionError: Tuples differ: (0, "on: 1 steps, the night's count", 1, 1, 1, ['1[51 chars]alse) != (0, "on: 2 steps, the night's count", 2, 1, 1, ['1[50 chars]alse) (#73)
      broken: the switches are not read between steps → AssertionError: Tuples differ: (0, "on: 2 steps, the night's count", 2, 2, [], [['issue', 'close', '2']]) != (0, "off: the run's issue #1 is closed; nothing new starts", 1, 1, [], []) (#73)
      broken: the fix's pull request is not the one waited on → AssertionError: Tuples differ: (0, ['5'], "on: 1 steps, the night's count") != (0, ['13'], "on: 1 steps, the night's count") (#73)
      broken: on does not re-read the next step after a merge → AssertionError: Tuples differ: (0, [[21 chars]ack A: C01.1–C01.3', 'Next step: Day 01 Track A: C01.1–C01.3']) != (0, [[21 chars]ack A: C01.1–C01.3', 'Next step: Day 01 Track A: C01.4']) (#74)
- [x] C06.10 **new** — With `--claude` a fake printing `2.1.400 (Claude Code)`: `on` refuses with
      "cannot start: Claude Code `2.1.400 (Claude Code)` has not passed the live check; run
      run-steps.py live-check" when `<state>/live-checked.txt` is missing or lists another
      version, and goes on when it lists that line; `live-check` appends the line after a run
      that ends "OK", and not after one with a skip or a failure (a fake test runner passed by
      `--python`); `--once` does not read the file.
      Red today: as C06.8.
      Test: `LiveCheckTest.test_on_refuses_an_unchecked_version`,
      `LiveCheckTest.test_live_check_records_only_a_clean_pass`.
      Evidence: `LiveCheckTest.test_on_refuses_an_unchecked_version`, `LiveCheckTest.test_live_check_records_only_a_clean_pass` (#74).
      seen red: python -m unittest tests.test_live_check on main → AssertionError: Tuples differ (#74)
      broken: on skips the version check → AssertionError: Tuples differ: (0, "opened: #5 from `day-01/track-a-x`\no[707 chars]alse) != (2, '', ['cannot start: Claude Code `2.1.4[85 chars]alse) (#74)
      broken: live-check counts OK (skipped=2) as a pass → AssertionError: Tuples differ: (0, b'2.1.400 (Claude Code)\n') != (1, None) (#74)
      broken: live-check ignores the exit code → AssertionError: Tuples differ: (0, b'2.1.400 (Claude Code)\n') != (1, None) (#74)
      broken: live-check names another program to the tests → AssertionError: Tuples differ: (['-m', 'unittest', 'tests.test_live_cli'], False, True) != (['-m', 'unittest', 'tests.test_live_cli'], True, True) (#74)
      broken: --once reads the live-check record → AssertionError: Tuples differ: (2, 0) != (0, 1) (#74)
- [x] C06.11 **new** — With `--session-minutes 0.01` and a fake `claude` that sleeps, `--once`
      kills the session's tree, prints "park: the session ran past 0.01 minutes (session `<id>`)",
      writes the `end` line with it, opens its `parked` issue and exits 1.
      Red today: "run-steps.py: error: argument command: invalid choice: '0.01' (choose from
      preflight, halt, clear, off, on, live-check)": the value is read as the positional command
      (D06.20).
      Test: `SessionBoundTest.test_session_past_its_bound_parks`.
      Evidence: `SessionBoundTest.test_session_past_its_bound_parks`, and a resumed session's bound in `SessionBoundTest.test_resumed_session_past_its_bound_parks` (#75).
      seen red: python -m unittest tests.test_session_bound.SessionBoundTest.test_session_past_its_bound_parks tests.test_session_bound.SessionBoundTest.test_resumed_session_past_its_bound_parks on main → AssertionError: 2 != 1 (#75)
      broken: the kill past the bound removed → AssertionError: True is not false : a process of the session still runs (#75)
      broken: the bound never reached → FAILED (errors=1) (#75)
      Not replayable, so a sentence and not in the manifest: `past_bound` writing no end line was broken in #75 and the test failed, but its report holds the session's random id (D06.27).
      broken: resume does not read PAST → FAILED (errors=1) (#75)
- [x] C06.12 **hold** — Earlier days' tests pass with their files unedited, but for the fake
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
      Evidence: the commands above, on `main` at `337f6b9` after #75: the diff printed nothing, and `python -m unittest discover -s tests` ran 212 tests, "OK (skipped=4)"; each track PR ran the same (#62 to #75). F1 (#72) had no criterion of its own: its five breaks are here because they show the earlier days' tests catching a wrong split.
      broken: one listed earlier test file edited → tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True) (#62)
      broken: an exit-2 line goes to stdout → AssertionError: Tuples differ: ('', 'cannot start: halted: the STOP issue [56 chars]e, 0) != ('cannot start: halted: the STOP issue #4 i[54 chars]e, 0) (#72)
      broken: a park with no session opens no issue → AssertionError: Tuples differ: (True, [], ['park: the run log names session `000[75 chars]', 1) != (True, [('park: the run log names session `000000[196 chars]', 1) (#72)
      broken: a session's park opens no issue → AssertionError: Tuples differ: (True, [], ['park: the step has more than one pul[31 chars]', 1) != (True, [('park: the step has more than one pull r[108 chars]', 1) (#72)
      broken: a STOP issue at the start exits 0 → AssertionError: Tuples differ: ('', 'cannot start: halted: the STOP issue [56 chars]e, 0) != ('cannot start: halted: the STOP issue #4 i[54 chars]e, 0) (#72)
      broken: the run's issue is left open at the step's end → AssertionError: Tuples differ: (1, True, [], 'open', [], 'opened: #5 from `day-01/track-a-x`', 0) != (1, True, [], 'closed', ['opened: #5 from `day-01/track-[43 chars]', 0) (#72)
- [x] C06.13 **new** — During the merge wait and the evidence wait, as C06.5 during the checks
      wait: a halt file ends the run within one poll, exit 1; an open `STOP` issue writes the
      halt file and the report on the run's issue, exit 1; the run's issue closed gives "off:
      the run's issue #7 is closed; nothing new starts", exit 0, and no `pr close` call is
      recorded.
      Red today: `driver/loop.py` does not exist.
      Test: `MergeWaitTest.test_halt_during_merge_wait`, `MergeWaitTest.test_stop_during_evidence_wait`,
      `MergeWaitTest.test_off_during_merge_wait`.
      Evidence: `MergeWaitTest.test_halt_during_merge_wait`, `MergeWaitTest.test_stop_during_evidence_wait`, `MergeWaitTest.test_off_during_merge_wait` (#70).
      seen red: python -m unittest tests.test_merge_wait on main → FAILED (errors=22) (#70)
      broken: the pull request is read while the issues cannot be → AssertionError: Tuples differ: (None, 0) != ('cannot read the project: gh issue list exited 1', 2) (#70)
      broken: the merge wait reads no halt file → AssertionError: the wait did not end on what the first sleep changed (#70)
      broken: the evidence wait reads no STOP issue → AssertionError: the wait did not end on what the first sleep changed (#70)
      broken: the merge wait reads no closed run's issue → AssertionError: the wait did not end on what the first sleep changed (#70)

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
- **Defect** D06.6 — found: seen red · cause: implementation · made: Day 06 ·
  `TreeTest.test_dry_run_moves_nothing` passed on `main`'s code, so CI failed #62's first push.
  It now also runs `to_main` on the same project, a control that the dry run had work to skip.
- **Defect** D06.7 — found: self · cause: process · made: Day 06 · the command creating #64's
  branch failed on a bad `git rev-parse`, so the implementer started while the checkout was on
  `main`. The branch was created at the same commit before any edit; nothing landed on `main`.
- **Defect** D06.8 — found: Track B · cause: spec · made: Day 06 · In scope says `checks` returns
  failed checks' names, but `failed_lines` needs their links too, and a second `gh` call breaks
  "the recorded calls are exactly In scope's". On red the list holds name and link (#64).
- **Defect** D06.9 — found: self · cause: process · made: Day 06 · #66 branched from a local
  `main` three commits behind `origin/main` (#65's). `git fetch` showed it before anything was
  committed; the branch was fast-forwarded onto f274965 before the tests and the breaks.
- **Defect** D06.10 — found: Track C · cause: spec · made: Day 06 · C06.3's Red today quotes
  "no attribute 'fix'"; the test calls `fixes` first, so what it reported was "no attribute
  'fixes'". Same cause, one word different (#66). The quote is left as it was.
- **Defect** D06.11 — found: self · cause: implementation · made: Day 06 · #67's brief gave the
  red fixture exit 1, which `checks` reads as a failed call. The implementer stopped and reported
  it rather than patching; `gh`'s source shows exit 0, and the fixture now says so.
- **Defect** D06.12 — found: self · cause: implementation · made: Day 06 · `test_*_during_wait`
  could have polled for ever on a regression, and the first runs against D06.11's fixture sat in
  the 30-minute bound. `on_sleep` now fails after five sleeps (#67).
- **Defect** D06.13 — found: Track D · cause: spec · made: Day 06 · from `gh`'s source at v2.93.0,
  read but not run: with no required checks, `gh pr checks --required --json` exits 1 before any
  JSON, so `checks` never gives "none" and the wait ends as "cannot read the project", exit 2, not
  C06.4's park. C06.2 and C06.4 pass on the fake's `[]`. Not fixed: the maintainer's call, H06.3.
- **Defect** D06.14 — found: Track D · cause: spec · made: Day 06 · the same source: with `--json`,
  `gh` returns right after the rows, so pending and red both exit 0. C06.2's "exit 8" for pending
  does not hold there. `checks` accepts both, so nothing breaks (#67).
- **Defect** D06.15 — found: Track E · cause: spec · made: Day 06 · In scope gives
  `gated(paths, body, human_only)`, but C06.6's lines name the pull request, so it takes `number`
  as a fourth parameter (#70).
- **Defect** D06.16 — found: Track E · cause: spec · made: Day 06 · C06.6's, C06.7's and C06.13's
  Red today say "`driver/loop.py` does not exist". Track D created it, so the red was `gated` and
  `wait_merge` missing from it (`AttributeError`, #70). The quotes are left as they were.
- **Defect** D06.17 — found: break on purpose · cause: implementation · made: Day 06 · the first
  break of the path check hung for ten minutes: that test's pull request stayed OPEN and the merge
  wait has no bound, as a real regression would have hung CI. Its view list now ends in CLOSED (#70).
- **Defect** D06.18 — found: break on purpose · cause: process · made: Day 06 · same-as: D05.9 ·
  four of Track E's breaks reported the scratch commit's sha, which differs on every run, so the
  close's replay would have failed them. The test now prints `<head>` and they were rerun (#70).
- **Defect** D06.19 — found: break on purpose · cause: implementation · made: Day 06 · the
  failed-read tests first passed with a break that ended the wait at once; each now requires a
  second read (#70).
- **Defect** D06.20 — found: Track H · cause: spec · made: Day 06 · same-as: D06.16 · C06.11's Red
  today quoted argparse's choices as `preflight, halt, clear, off`; #73 and #74 added `on` and
  `live-check` before Track H ran, and #75 recorded the departure. Same failure. Corrected at this
  close, confirmed by running `run-steps.py --session-minutes 0.01 --once` at #74's merge (33b93b8).
- **Defect** D06.21 — found: close · cause: spec · made: Day 06 · same-as: D06.16 · C06.10's Red
  today says "as C06.8", an `on` that argparse refuses. #73 had added `on` before Track G, so its
  red was an assertion (`Tuples differ`, #74). The line is left as it was.
- **Defect** D06.22 — found: close · cause: process · made: Day 06 · Track D's 11 `manifest:` lines
  (#67) name this machine's absolute `python.exe`: run on CI's Linux they would not start. The
  close's manifest gives `python` for each.
- **Defect** D06.23 — found: evidence replay · cause: process · made: Day 06 · the report of
  #67's break "the resume keeps --session-id" holds a Windows path separator, so Linux's replay
  differed. The line now records the report CI's Linux run gives.
- **Defect** D06.24 — found: evidence replay · cause: process · made: Day 06 · two of #72's breaks
  counted a carriage return in unittest's cut ("[58 chars]" on Windows, "[56 chars]" on Linux).
  The lines now record Linux's reports.
- **Defect** D06.25 — found: evidence replay · cause: process · made: Day 06 · same-as: D06.18 ·
  #73's break "on goes on after a failed preflight" reported a line that unittest cuts inside the
  scratch directory's random name, so no two runs print it alike. It stays a sentence under C06.8,
  not in the manifest.
- **Defect** D06.26 — found: evidence replay · cause: process · made: Day 06 · two of #74's breaks
  held Windows-only text: a carriage return, and an en dash the console turned into a replacement
  character. The lines now record Linux's reports.
- **Defect** D06.27 — found: evidence replay · cause: process · made: Day 06 · same-as: D06.18 ·
  #75's break "past_bound writes no end line" reported the session's random id. It stays a
  sentence under C06.11, not in the manifest.
- **Defect** D06.28 — found: evidence replay · cause: process · made: Day 06 · same-as: D06.3 · #70
  added a second `{args.wait_minutes:g} minutes` to `driver/loop.py`, so #67's break of it matched
  twice and `break.py` refused it. The manifest now gives a find unique at the close.
- **Defect** D06.29 — found: evidence replay · cause: process · made: Day 06 · same-as: D06.3 · #73
  added two more `if line is None:` to `driver/loop.py`, so #70's break of it matched three times.
  The manifest now breaks the line above it, with the same effect and the same report.
- The close replayed its breaks on Linux in Docker before writing the lines: 66 of 75 matched at
  first. Five `broken:` lines now record CI's reports, and a rehearsal on Windows fails those five.
- The blind relabel (`scripts/relabel.py`, the defect-rater): stage 24 of 29 agree, cause 24 of
  29, made 28 of 29, every tag kept. D06.2 (low): #51's own replay caught a bug in the repository's
  own script. D06.4: `found:` names the gate, the auditor. D06.21: this close noticed it, after #74
  merged. D06.25, D06.27, rater unclear: the close's rehearsal, which their text does not say.
  D06.11 (low): the wrong exit code became a test fixture. D06.23, D06.24, D06.26, rater
  `environment`: kept `process`, as D05.10: the defect is recording a report CI cannot reproduce.
- Departures: Track H's kill is not STOP's, though In scope says "as a `STOP` kills it": on POSIX
  a STOP kills `--once`'s own group, so the driver could not park. `kill_session` sends SIGKILL to
  the session and its descendants from one `ps` snapshot (#75). #70 adds five tests to the spec's.
- Unverified at the close: a `STOP` during `on` closes the run's issue twice, read from the code,
  harmless if `gh issue close` exits 0 on a closed issue, which H05.5 still holds (#73). A break of
  the descendant walk in `kill_session` was not run anywhere (#75).
- **Hand-off** H06.1 → Day 8: how a headless session reports the usage limit, recorded from the
  trial; the wait and retry follow it (Day 5's Out of scope gave it to Day 6).
- **Hand-off** H06.2 → Day 7 | Day 8: the count of pull requests in a row merged at level 1
  without a change asked, Level 2's entry condition; nothing in Phase 1 counts it yet.
- **Hand-off** H06.3 → Day 7 | Day 8: `checks` against the real `gh` with no required checks
  (D06.13): `_gh` must read stderr and C06.2 change, on the scratch repository with H05.5.
