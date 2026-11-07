# Day 05 — Parks: the `parked` issue, the run's issue, the phone's `STOP`, `off`, and a halt's report

**Phase:** 1 · **Depends on:** Day 4 · **Expected PRs:** 10

## Goal
Every park `--once` prints opens a `parked` issue on the project, or comments on the open one with
the same title; an open `parked` issue makes the next `--once` wait, and closing it is the
maintainer's "go on", which also answers a phase's end and a step that failed twice. Each step runs
under the run's issue, which `off` closes from the PC and the maintainer can close from the phone.
An open `STOP` issue from the maintainer's account halts the driver at its start and, within one
poll, during a session; a halt, from the PC or the phone, writes what was in progress on the run's
issue.

## In scope
- **The issues** (`driver/issues.py`), each `gh` call through the program `--gh` names, in the
  project's folder, as `driver/github.py`'s `_gh` runs it (`shutil.which`, `GH_PROMPT_DISABLED=1`,
  its output read as UTF-8 with `errors="replace"`). Every body goes on the call's stdin with
  `--body-file -`, never in an argument: through npm's or the tests' `gh.cmd`, `cmd.exe` drops a
  newline and every argument after it (D04.2). The body is written as UTF-8 bytes with `\n` line
  endings: text mode would turn each into `\r\n` on Windows only. A call that exits non-zero, or a
  read that prints no JSON list, gives the reason "gh issue `<subcommand>` exited `<n>`" (`gh label
  create exited <n>` for the label), and nothing is guessed.
  - `open_issues(project, gh)` runs `gh issue list --state open --author @me --limit 100 --json
    number,title,labels` and returns `(issues, None)`, each `{"number", "title", "labels": [<name>,
    ...]}`, by number; or `([], <reason>)`. Only the maintainer's account counts (`plan.md`, "The
    switches": "only an issue from the maintainer's account counts"; at level 1 the driver's `gh`
    login is the maintainer's).
  - `closed_parks(project, gh)` runs `gh issue list --state closed --author @me --label parked
    --limit 100 --json number,title` and returns `(titles, None)`, a set; or `(set(), <reason>)`.
  - `park(project, gh, line, body, issues)`: the title is `line` cut to 200 characters. When
    `issues` (an `open_issues` result) holds one labelled `parked` with that title, it runs `gh
    issue comment <n> --body-file -` with "parked again at `<ISO 8601, UTC>`" (`plan.md`,
    "Recovery", rule 6: one park per reason). Otherwise `gh label create parked --color D93F0B
    --description "The driver parked; close to let it go on" --force` (it exits 0 whether or not the
    label exists), then `gh issue create --title <title> --label parked --body-file -` with `body`.
    Returns `(<n>, None)`, `<n>` read from the last line `gh issue create` prints (its URL, ending
    `/issues/<n>`; a last line that does not end so is the reason "gh issue create printed no issue
    URL"), or `(None, <reason>)`.
  - `open_run(project, gh, step, session, issues)`: the run's issue. When `issues` holds one whose
    title starts "Driver run" (the lowest number), it comments on it; otherwise `gh issue create
    --title "Driver run <ISO 8601, UTC>" --body-file -`, no label. The body, both ways: "step:
    `<sentence>`", "session: `<uuid>`", a blank line, and "Close this issue to turn the driver off
    after this step." Returns `(<n>, None)` or `(None, <reason>)`.
  - `close(project, gh, number, comment, timeout=None)`: `gh issue comment <n> --body-file -`, then
    `gh issue close <n>`; returns `None` or the first reason. A call that passes `timeout` seconds
    is killed and gives "gh issue `<subcommand>` timed out". `close()` relies on `gh issue close`
    exiting 0 on an issue already closed, so that a run's issue closed from the phone closes again
    without an error (unverified, see Notes).
  - `report(project, record)`: the text a halt writes. `record` is `<state>/run.json`'s object. The
    lines: "halted at `<ISO 8601, UTC>`", "step: `<record's step>`", "session: `<record's session>`",
    "branch: `<git symbolic-ref -q --short HEAD>`" (or "branch: detached HEAD"), "last commit:
    `<git rev-parse --verify -q HEAD, 7 characters>`" (or "last commit: none"), and "uncommitted
    changes: `<n>` paths" from `git status --porcelain` (or "uncommitted changes: none"). Its git
    commands are those three, all in "Recovery", rule 7 (`plan.md`, "The switches", a halt's step 4;
    H03.2).
- **`decide()` answers a phase's end** (H01.1). `decide(drift, facts, answered=frozenset())`:
  when `phase_end` gives a reason `r` and "park: `<r>`" is in `answered`, it does not park on it and
  goes on to the branch check, as for a step in the same phase. Still pure; the dry run passes
  nothing, so it parks at every phase's end as before (H05.2).
- **The run log's failures** (H04.1). `runlog.failures(state, prefix)` returns the sessions, in the
  log's order, whose `start` line has `prefix` and whose `end` line's `outcome` starts "park:"; a log
  it cannot read gives `(None, <the reason open_session gives>)`, otherwise `(sessions, None)`.
- **`--once`, at the start** (`driver/once.py`; `plan.md`, "Recovery", the table's rows 1 and 3).
  Day 4's steps 1-6 stay; right after step 4 takes the lock, a `<state>/run.json` left by an
  earlier run is removed, so that a halt before this run writes its own reads none. Then:
  - 6a. `open_issues`. A reason: "cannot read the project: `<reason>`" on stderr, exit 2. An issue
    whose title starts "STOP" (the lowest number): `<state>/halt` is written, "halted at `<ISO
    8601>`: STOP issue #`<n>`", and "cannot start: halted: the STOP issue #`<n>` is open; close it,
    then run-steps.py clear" goes to stderr, exit 2. Issues labelled `parked`: "wait: parked
    #`<a>`, #`<b>`" on stdout, by number, exit 0.
  - 7. As Day 4, but when `decide()` parks with "park: the end of Phase ", `closed_parks` is read
    and `decide()` asked again with its titles as `answered`. A reason from `closed_parks` is
    "cannot read the project: `<reason>`", exit 2.
  - 8, 9. As Day 4.
  - 9a. `runlog.failures(state, prefix)`: two or more give "park: the step failed twice: sessions
    `<a>` and `<b>`", the last two, unless `closed_parks` (read here if step 7 did not) holds that
    title. A reason from `failures` parks as step 9's does; a reason from `closed_parks` is "cannot
    read the project: `<reason>`", exit 2, as in step 7.
- **Every park is an issue** (H04.1). Each line `--once` prints with exit 1 that starts "park:"
  (decide's parks, the evidence run, the run log, step 9a, and every park of the session's outcome)
  is passed to `park()` with the body: the whole line, a blank line, "step: `<sentence>`", "session:
  `<uuid>`" (or "session: none" before a session), "at: `<ISO 8601>`", a blank line, and "Close this
  issue to let the driver go on." What `--once` prints is unchanged: the issue's number is not
  printed. A reason from `park()` adds "cannot open the park's issue: `<reason>`" on stderr; the exit
  stays 1. A "wait:" line, an exit 2 and a halt open no issue.
- **The run's issue around the session** (`plan.md`, "The switches": off from the phone, "Where am
  I"). Step 10 becomes: a new `uuid4`; `open_run(...)` (a reason: "cannot read the project:
  `<reason>`", exit 2, no session); `<state>/run.json`, written as UTF-8 bytes, `{"project": <the
  project's real path>, "gh": <the gh program's full path>, "issue": <n>, "step": <sentence>,
  "session": <uuid>}`; then the settings and the run log's `start` line, as Day 4. Step 12, after
  the outcome and its `end` line: when the outcome's exit is 2, no further `gh` call is made (`gh`
  is what failed) and the run's issue stays open. Otherwise, in this order: the park's issue, when
  the outcome parked; the driver's repository checked as Day 4 (its "halt: set during the step"
  line and halt file unchanged); then `close(...)` on the run's issue with a comment of the
  outcome's line, then "parked: #`<n>`" on its own line when a park's issue was opened or
  commented, then, when the check set the halt file, the halt's line and `report(...)` (`plan.md`,
  a halt's step 4). These lines are the comment's, never stdout's. A reason from `close` adds
  "cannot close the run's issue #`<n>`: `<reason>`" on stderr, exit unchanged. Then
  `<state>/run.json` is removed.
- **The phone's `STOP` during a session.** `--once` gains `--poll <seconds>` (default 30, a float:
  `plan.md`, "From the phone it takes as long as the driver's poll of GitHub, 30 seconds by
  default"). The session runs under `subprocess.Popen`; `communicate(input=<the prompt>,
  timeout=<poll>)` writes the prompt and closes stdin, and after each `TimeoutExpired` it is called
  again with no input (passing the input again raises `ValueError`). So the first poll comes one
  `--poll` after the session starts, never before it, and a session that ends within one `--poll`
  is not polled. Each poll reads `open_issues`; a read with a reason is skipped. An issue whose
  title starts "STOP" (decided 2026-11-07, the maintainer: the report is written before the kill,
  and nothing about the report can prevent the stop):
  1. `<state>/halt` is written ("halted at `<ISO 8601>`: STOP issue #`<n>`"), so every tool call
     of the session is refused from here on;
  2. "halt: the STOP issue #`<n>` is open; the session is stopped" is printed to stdout with
     `flush=True`;
  3. the report: `close(...)` on the run's issue with `report(...)`, each `gh` call with
     `timeout=10`, inside a `try` that catches any exception; "halt: reported on #`<n>`", or "halt:
     no report on #`<n>`: `<reason or the exception's name>`", printed with `flush=True`, and
     stdout and stderr flushed;
  4. the kill, in a `finally` after step 3, so that a report that fails, raises or hangs past its
     timeouts still ends in it: on Windows, `taskkill /PID <the session's pid> /T /F`, then
     `<state>/run.json` removed, exit 1, the lock released; on POSIX, `os.killpg(os.getpgid(0),
     signal.SIGKILL)`, which ends `--once` with its session (Day 4's step 1 made the group its
     own): the exit is `-9`, the lock and `run.json` stay, and `clear` and the next `--once`
     remove them.
  Either way the run log keeps the `start` line with no `end`, as a PC halt leaves it, and no
  park's issue is opened.
- **A halt's report from the PC** (H03.2). `run-steps.py halt`, after it killed a live driver's
  tree, reads `<state>/run.json`: missing, nothing more is printed; not a JSON object with the five
  keys, "halt: no report: `<state>/run.json` cannot be read"; otherwise `close(...)` on its issue,
  through its `gh`, in its project, with `report(...)`, and "halt: reported on #`<n>`" or "halt: no
  report on #`<n>`: `<reason>`". The second line never changes halt's exit. With no live driver,
  halt prints its Day 3 line only.
- **`python run-steps.py off [--config <file>] [--project <path>] [--gh <program>]`**
  (`driver/switches.py`). The project as `preflight` finds it, a config with a problem exits 2 with
  its lines. `open_issues`; a reason: "cannot read the project: `<reason>`" on stderr, exit 2. No
  issue whose title starts "Driver run": "off: no run is going", exit 0. Each one, by number:
  `close(...)` with "off from the PC at `<ISO 8601>`", and "off: closed the run's issue #`<n>`; the
  current step finishes, nothing new starts", exit 0; a reason, "cannot read the project:
  `<reason>`", exit 2. `off` reads and writes no file in the state folder.
- **The fake `gh`** (`tests/test_github.py`, the one edit to it). `FAKE` also answers, from
  `fake.json`'s `issues` (each `{"number", "title", "labels", "state", "author"}`, read with
  `.get`), `issue list` (filtered by `--state`, `--label` and `--author @me` → `author` `me`;
  `labels` printed as `[{"name": ...}]`), `issue create` (the next number after the highest,
  appended to `fake.json`, its URL printed as the last line), `issue comment <n>` (exit 1 for no
  such issue), `issue close <n>` (sets `state` `closed`; exit 0 when already closed) and `label
  create`. Only a call with `--body-file -` reads stdin, and appends `{"args": ..., "body":
  <stdin>}` to `bodies.jsonl` beside it; `calls.jsonl` stays one argument list per line.
  `fake.json`'s `issue_code` (`.get`, 0 when absent), when non-zero, is the exit of every `issue`
  and `label` call. `fake_gh(folder, runs=None, prs=None, code=0, issues=None, issue_code=0)`.
- **The edits to `tests/test_once.py`**, all in `test_session_command`'s `gh` calls: Track C1
  makes them `issue list`, `run list`, `pr list`, two before the session (its step 6a); Track D
  makes them `issue list`, `run list`, `issue create`, `pr list`, `issue comment`, `issue close`,
  three before the session (C05.8, which replaces C04.9 and restates the rest of it).
- Tests in `tests/test_issues.py`, `tests/test_issue_writes.py`, `tests/test_failures.py`,
  `tests/test_once_parks.py`, `tests/test_once_park_issues.py`, `tests/test_once_run.py`,
  `tests/test_halt_report.py`, `tests/test_off.py` and `tests/test_once_stop.py`, and the edits
  above. No other earlier test file is edited.

## Out of scope
- The loop: `on` keeping one run's issue across steps and reading it between steps, so that `off`
  and the phone's close end the run after the current step; `STOP` polled while the driver waits
  on checks and on the merge — Day 6 (H05.1). On Day 5 a run is one `--once` (decided 2026-11-07,
  the maintainer), and its issue is closed at its end.
- A red check after two fixes; a pull request that touches `plan.md`, a human-only file or carries
  `Oversized:`; the usage limit waited out and retried — Day 6.
- `status`, the run's issue showing the cost so far, parks counted by reason, and the dry run
  reading the issues (it still parks at an answered phase's end) — Day 7 (H05.2). A park on
  uncommitted changes or an unfinished branch naming the paths, the branch, the last commit and the
  session id in its issue (`plan.md`, "Recovery", the table's rows 5 and 6) — Day 7 (H05.4); Day 5's
  issue holds Day 4's line, which counts the paths.
- A `STOP` and a park answered from the phone on real GitHub — Day 8, the trial (H05.3). Day 5's
  tests use the fake `gh`.
- Closing a `STOP` issue: the maintainer's, before `clear`. The driver never closes one, and `clear`
  reads no GitHub: a `STOP` left open halts the next `--once` again.
- A permission refusal as a park of its own: a session stopped by one opens no pull request and
  parks as "no pull request and no PARK line"; the run log's `denials` count it (Day 4).
- Any change to `driver/steps.py`, `driver/lock.py`, `driver/settings.py`, `driver/home.py`,
  `driver/preflight.py`, the hooks, `rules/session.md`, `clear`, and the lines of `--dry-run`,
  `preflight` and Day 3's `halt`.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A1 | | C05.1: `open_issues`, `closed_parks`, the fake `gh`'s `issue list` and `issue_code`; C05.12's diff break |
| A2 | | C05.2, C05.3: `park`, `open_run`, `close`, the fake's writes and `bodies.jsonl` |
| B | | C05.4, C05.5: `decide()`'s `answered`, `runlog.failures` |
| C1 | | C05.6: `--once`'s start checks (6a, 7, 9a), the first edit to `test_session_command` |
| C2 | | C05.7: `--once`'s parks as issues; C05.12's print break |
| D | | C05.8: the run's issue and `run.json` around the session, the second edit to `test_session_command` |
| E | | C05.9, C05.10: `report`, a halt's report from the PC, `off` |
| F | | C05.11: `--poll` and the phone's `STOP` during a session |

C1 needs A1 and B; C2 needs A2 and C1; D needs C2; E needs A2 and D's `run.json`; F needs D and E.
A1, A2 and B do not depend on each other; A2 branches after A1, both editing the fake. Estimated
changed lines, from Day 4's #24 (282) and #25 (395): A1 200, A2 280, B 150, C1 300, C2 250, D 300,
E 370, F 280. C05.12 is held by every track. A track over 400 is split by a spec change (D03.12).

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [ ] C05.1 **new** — With the fake `gh`, `open_issues` returns the open issues by `me` only, by
      number, each with its labels' names, from a file that also holds a closed one and one by
      `someone`; `closed_parks` returns the titles of the closed `parked` issues by `me` only; the
      recorded calls are exactly the two `issue list` calls of In scope; with `issue_code` 1 each
      gives "gh issue list exited 1".
      Red today: `driver/issues.py` does not exist; `ImportError` in `setUp`.
      Test: `IssuesTest.test_open_issues`, `IssuesTest.test_closed_parks`,
      `IssuesTest.test_reads_fail`.
- [ ] C05.2 **new** — `park` with no open `parked` issue of that title records `label create
      parked ... --force`, then `issue create --title <line> --label parked --body-file -`, with
      the body in `bodies.jsonl` holding no `\r`, and returns the new number; with an open `parked`
      issue of that title it records only `issue comment <n> --body-file -`, the body starting
      "parked again at "; a line of 250 characters gives a title of its first 200; with
      `issue_code` 1, `(None, "gh label create exited 1")`.
      Red today: `driver/issues.py` has no `park`; `AttributeError` (after A1), `ImportError`
      (before it).
      Test: `IssueWritesTest.test_park_opens`, `IssueWritesTest.test_park_comments`,
      `IssueWritesTest.test_park_title_cut`, `IssueWritesTest.test_park_fails`.
- [ ] C05.3 **new** — `open_run` with no open "Driver run" issue creates one titled "Driver run "
      and a stamp, unlabelled, its body holding "step: ", the sentence, "session: " and the uuid;
      with one open, it comments on it and creates none. `close` records `issue comment <n>
      --body-file -` then `issue close <n>`, and returns `None` on an issue the fake holds as
      closed already; on a number the fake does not hold, "gh issue comment exited 1"; with a fake
      that sleeps 5 s on `issue comment` and `timeout=1`, "gh issue comment timed out" within 3 s.
      Red today: as C05.2.
      Test: `IssueWritesTest.test_open_run_creates`, `IssueWritesTest.test_open_run_reuses`,
      `IssueWritesTest.test_close`, `IssueWritesTest.test_close_times_out`.
- [ ] C05.4 **new** — `decide()` on a spec step that opens Phase 1, with `answered` holding "park:
      the end of Phase 0: Day 03 starts Phase 1", gives "start: " and the sentence; with that
      answer and a branch of the step on the remote, the branch's park; with `answered` holding
      another phase's line, the phase's park; called without `answered`, the phase's park, as Day
      1's tests hold.
      Red today: `decide()` takes no `answered`; `TypeError` on each call that passes it.
      Test: `AnsweredTest.test_answered_phase_end_starts`,
      `AnsweredTest.test_answered_still_checks_branches`, `AnsweredTest.test_other_answer`.
- [ ] C05.5 **new** — `runlog.failures` on a log of four sessions of one prefix (ended "opened:
      #5 ...", "park: ...", "park: ...", and one with no end) and one park of another prefix
      returns the two parked sessions of the prefix, in order; no log gives `([], None)`; a torn
      last line gives `(None, "the run log cannot be read at line <n>")`.
      Red today: `runlog` has no `failures`; `AttributeError`.
      Test: `FailuresTest.test_failures`, `FailuresTest.test_no_log`, `FailuresTest.test_torn_log`.
- [ ] C05.6 **new** — `--once` from a copy of the driver with the fake `gh` and the fake `claude`,
      each case starting no session (the fake records only `--version` and `--help`) unless it
      says so: an open "STOP now" by `me` gives the STOP line on stderr, exit 2, and
      `<state>/halt` holding "STOP issue #`<n>`"; a "STOP" by `someone` is not read (the step
      starts); open `parked` issues #3 and #5 give "wait: parked #3, #5", exit 0; a next step that
      opens Phase 1 gives the phase's park, exit 1, and with a closed `parked` issue of that title
      it starts the session; a run log with two parked sessions of the step's prefix gives "park:
      the step failed twice: sessions `<a>` and `<b>`", exit 1, and with a closed `parked` issue of
      that title it starts the session; `issue_code` 1 gives "cannot read the project: gh issue
      list exited 1", exit 2; a stale `<state>/run.json` is gone after any case that took the
      lock.
      Red today: `--once` reads no issue: the STOP and parked cases start a session and print
      "opened: ...", the phase's case with its answer still parks, the failed-twice case starts a
      session, the gh case starts one, and `run.json` stays.
      Test: `OnceParksTest.test_stop_at_start`, `OnceParksTest.test_stop_from_another_author`,
      `OnceParksTest.test_wait_on_parked`, `OnceParksTest.test_phase_end_answered`,
      `OnceParksTest.test_failed_twice`, `OnceParksTest.test_issues_unreadable`,
      `OnceParksTest.test_stale_run_json_removed`.
- [ ] C05.7 **new** — Each park `--once` prints (a dirty tree, the evidence run `failure`, an open
      run-log line, and the session's five parks: no JSON result, an error, `PARK:`, no pull
      request and no `PARK:`, more than one pull request) leaves one open `parked` issue in the
      fake whose title is the printed line, whose body (in `bodies.jsonl`) holds the line and
      "Close this issue to let the driver go on."; `--once`'s stdout is that line alone, stderr
      empty, exit 1. Run twice on the dirty tree with the first issue left open, the second run
      waits ("wait: parked #`<n>`") and opens none; with the issue's state set to closed between
      them, the second run comments on no closed issue and opens a second. With `issue_code` 1 set
      by the session (as Day 4's `GH_DOWN`, for the `issue` and `label` calls only), a session's
      `PARK:` gives its line on stdout and, on stderr, "cannot open the park's issue: gh label
      create exited 1" as its first line (after Track D a second follows, "cannot close the run's
      issue #`<n>`: gh issue comment exited 1"), exit 1.
      Red today: no `issue` call is made; the fake holds no issue after any case.
      Test: `OnceParkIssuesTest.test_each_park_is_an_issue`,
      `OnceParkIssuesTest.test_open_park_waits`, `OnceParkIssuesTest.test_closed_park_parks_again`,
      `OnceParkIssuesTest.test_park_issue_fails`.
- [ ] C05.8 **new** — With every check passing, `--once` starts one session: the fake records
      exactly the arguments of Day 4's step 11 after the program, with the uuid that the run
      log's `start` line holds, and on its stdin the two lines of the prompt, in UTF-8, the
      sentence's en dash as `\xe2\x80\x93`; on Windows the fake is a `.cmd`, as npm's `claude`
      is; its cwd is the project's real path when the test passed another path to it; `<state>/lock`
      and `<state>/settings.json` existed while it ran; a `settings.json` holding `not json` before
      the run is valid JSON with the halt hook during it; `rules/session.md` holds "nobody
      watches", "PARK: <", "never merge" and "Hand-off"; after the session the lock is gone (all
      as C04.9). The fake `gh` records, in order, `issue list`, `run list`, `issue create` (the
      run's issue), `pr list`, `issue comment`, `issue close`, and the fake `claude` saw three
      `gh` calls before it ran. During the session `<state>/run.json` held the five keys, its
      `issue` the created number, its `session` the run log's uuid; after it, `run.json` is gone
      and the run's issue is closed, its comment the line `--once` printed. An open "Driver run"
      issue is commented on and closed, and none created. A session's `PARK:` closes the run's
      issue with a comment of the park's line and "parked: #`<n>`", and stdout holds the park's
      line alone. A session that commits in the driver's copy (Day 4's `driver_moved` case)
      closes the run's issue with a comment holding "halt: set during the step" and "branch: ".
      Day 4's `gh_fails` outcome (`GH_DOWN`) makes no call after `pr list` and leaves the run's
      issue open.
      Replaces: C04.9 — was: the session started with Day 4's arguments, prompt, cwd, lock,
      settings and rules, and "The fake `gh` recorded one `run list` before the session."
      Red today: no `issue` call and no `run.json`; `test_session_command`, as edited, fails on its
      `gh` calls.
      Test: `OnceTest.test_session_command`, `OnceTest.test_session_cwd_is_real_path`,
      `OnceTest.test_lock_and_settings_during_session`, `OnceTest.test_rules_file`,
      `OnceRunTest.test_run_json_during_session`, `OnceRunTest.test_run_issue_closed`,
      `OnceRunTest.test_run_issue_reused`, `OnceRunTest.test_park_on_run_issue`,
      `OnceRunTest.test_halt_during_step_reported`, `OnceRunTest.test_no_call_after_gh_fails`.
- [ ] C05.9 **new** — `run-steps.py halt --state <state>` with a lock naming a live stand-in (as
      Day 3's test) and a `run.json` naming the fake `gh`, a scratch project on `day-05/track-a-x`
      with one commit and one untracked file, issue 4, a step and a session: stdout is the Day 3
      kill line, then "halt: reported on #4", exit 0; the fake's issue 4 is closed, and its comment
      holds "step: ", "session: ", "branch: day-05/track-a-x", "last commit: " and the commit's 7
      characters, and "uncommitted changes: 1 paths". A `run.json` that is not JSON gives "halt: no
      report: `<state>/run.json` cannot be read"; with `issue_code` 1, "halt: no report on #4: gh
      issue comment exited 1", exit 0 both. A project on a detached HEAD with a clean tree gives
      "branch: detached HEAD" and "uncommitted changes: none".
      Red today: halt prints the kill line only, and the fake records no call.
      Test: `HaltReportTest.test_report`, `HaltReportTest.test_unreadable_run_json`,
      `HaltReportTest.test_report_fails`, `HaltReportTest.test_detached_clean`.
- [ ] C05.10 **new** — `run-steps.py off --project <p> --gh <fake>`: with open "Driver run" issues
      #2 and #4 by `me`, both closed in the fake, each with an "off from the PC at " comment, and
      two lines "off: closed the run's issue #2; ..." and "... #4; ...", exit 0; with none, "off:
      no run is going", exit 0, and no `issue comment`; with `issue_code` 1, "cannot read the
      project: gh issue list exited 1" on stderr, exit 2; with no `--project` and no config, the
      config's line, exit 2.
      Red today: argparse refuses `off`: "invalid choice: 'off'", exit 2.
      Test: `OffTest.test_off_closes_runs`, `OffTest.test_off_no_run`, `OffTest.test_off_gh_fails`,
      `OffTest.test_off_no_config`.
- [ ] C05.11 **new** — `--once --poll 0.5` on a fake session that starts a child and both sleep,
      writing their pids: once the pids are written, the test adds an open "STOP" issue #9 by `me`
      to the fake. Within 10 s `<state>/halt` holds "STOP issue #9", the fake and its child are
      gone, stdout's first line is "halt: the STOP issue #9 is open; the session is stopped" and
      its second "halt: reported on #`<n>`", the run's issue is closed with a comment holding
      "halted at " and "step: ", and the run log has the `start` line and no `end`; the exit is 1
      on Windows and `-9` on POSIX, where both lines must still reach the pipe. Then `--once`
      refuses with the halt file's line, and the fake records no new session. With the run's issue
      removed from the fake when the STOP issue is added (so `issue comment` on it exits 1, and the
      poll's `issue list` still reads the STOP), the session's tree is still gone within 10 s and
      stdout's second line is "halt: no report on #`<n>`: gh issue comment exited 1". A poll whose read
      fails (`issue_code` 1 set by the session for 2 s, then 0) is skipped, and the session ends as
      its file says.
      Red today: `--once` has no `--poll` (argparse exits 2), and with it, no poll is read: the
      session runs to its end.
      Test: `OnceStopTest.test_stop_during_session`, `OnceStopTest.test_refuses_after_stop`,
      `OnceStopTest.test_stop_when_report_fails`, `OnceStopTest.test_failed_poll_skipped`.
- [ ] C05.12 **hold** — Earlier days' tests pass with their files unedited, but for the fake `gh`
      in `tests/test_github.py` and `test_session_command`'s `gh` calls in `tests/test_once.py`:
      `git -c core.safecrlf=false diff --exit-code 93c94de -- tests/test_contract.py
      tests/test_decide.py tests/test_dry_run.py tests/test_steps.py tests/test_kit_copy.py
      tests/test_config.py tests/test_lock.py tests/test_hooks.py tests/test_halt.py
      tests/test_live_cli.py tests/test_encoding.py tests/test_runlog.py tests/test_home.py
      tests/test_preflight.py tests/test_once_outcome.py tests/test_once_halt.py
      tests/test_live_once.py` prints nothing, and `python -m unittest discover -s tests` passes
      with them in it.
      To break once, in Track A1: one listed test file edited → the diff exits 1. In Track C2:
      `--once` prints the park's issue number after its line → `OnceTest.test_refusals` fails on
      its `every_day_done`, `evidence_failed` and `open_run_log` cases.

## Verify
```bash
python -m unittest discover -s tests
git -c core.safecrlf=false diff --exit-code 93c94de -- tests/test_contract.py tests/test_decide.py tests/test_dry_run.py tests/test_steps.py tests/test_kit_copy.py tests/test_config.py tests/test_lock.py tests/test_hooks.py tests/test_halt.py tests/test_live_cli.py tests/test_encoding.py tests/test_runlog.py tests/test_home.py tests/test_preflight.py tests/test_once_outcome.py tests/test_once_halt.py tests/test_live_once.py
```

## Notes
- Picks up H01.1 (a phase's end answered), H03.2 (a halt's report on the run's issue) and H04.1
  (each park an issue, a step failed twice from the run log's `end` lines). Phase 1 audit, finding
  9: "answered" is a closed `parked` issue by the maintainer's account whose title is the park's
  line. Only two parks are answered that way, a phase's end and a step failed twice: every other
  park is read again from git and GitHub, so closing its issue is the "go on" and the driver parks
  again if nothing changed (`plan.md`, "Recovery", after the table).
- Decided by the maintainer, 2026-11-07, in the spec-change PR:
  1. A run is one `--once`: it opens (or reuses) the run's issue and closes it at its end. Day 6's
     `on` keeps it open across steps (H05.1).
  3. The phone's `STOP` writes and flushes its report before the kill, on both systems, and a
     report that fails, raises or hangs past its timeouts cannot prevent the kill. On POSIX
     `--once` leads the process group its session runs in, so the kill ends `--once` too and
     nothing could write the report after it; the halt file is written first, so the session's
     tool calls are refused while the report is written. A departure from `plan.md`'s order (a
     halt's steps 2 and 4), recorded here.
- Also decided by the maintainer, 2026-11-07, in the spec-change PR, as recommended:
  2. The run's issue is found by its title, "Driver run …", by the maintainer's account, with no
     label; a `parked` issue by its label. Removing the driver leaves both as history (`plan.md`,
     "Removing it").
  4. `--once` does not print a park's issue number: Day 4's tests hold its stdout to one line. The
     run's issue's closing comment names it ("parked: #n").
  5. `clear` stays local: it does not close a `STOP` issue, and a `STOP` left open halts again.
- Known limit (spec-auditor finding 9): within `--once`, `park()`'s comment path never runs: step
  6a waits on any open `parked` issue before a park's line is reached. Only C05.2's unit test
  covers it; Day 6's loop is where it can matter.
- Unverified: `gh issue create` printing its URL last, and `gh issue close` exiting 0 on a closed
  issue (gh 2.93.0 holds "is already closed"). Both write: the auditor could not run them, and a
  scratch repository was refused by the session's permission classifier. Checked before A2 merges.
- **Hand-off** H05.1 → Day 6: `on` opens one run's issue and keeps it across steps; between steps
  the loop reads it, and a closed one (`off`, or the phone) ends the run; `STOP` is polled while
  the loop waits on checks and on the merge, not only during a session.
- **Hand-off** H05.2 → Day 7: `status` shows the run's issue, the open parks and parks counted by
  reason from the run log; the dry run reads no issue, so it parks at a phase's end the maintainer
  has answered.
- **Hand-off** H05.3 → Day 8: a `STOP` opened and a park closed from the phone, on the trial's
  project on GitHub, each timed.
- **Hand-off** H05.4 → Day 7: the park on uncommitted changes or on an unfinished branch names, in
  its issue, the paths, the branch, the last commit and the session id (`plan.md`, "Recovery", the
  table's rows 5 and 6); Day 5's issue holds the line, which counts the paths.
