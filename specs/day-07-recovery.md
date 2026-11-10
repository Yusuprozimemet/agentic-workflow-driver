# Day 07 — Recovery: every start reads the table; `status` and the run log's report

**Phase:** 1 · **Depends on:** Day 6 · **Expected PRs:** 11

## Goal
Every start, `--once` and `on` alike, reads the table of `plan.md`'s "Recovery" from the top and
does what the first row that applies says: a live session is waited for, a stale lock is taken over,
and a park on unfinished work names its paths, branch, last commit and session. `python run-steps.py
status` prints where the driver is, one line per step, parks by reason, and the cost per merged PR.

## In scope

**The table.** `once.ready()`, used by `--once` and by `on`, reads the rows in this order; the
first that applies ends the read.

| Row (`plan.md`) | It does | Today |
|---|---|---|
| 1. the halt file, or an open `STOP` issue | `ready()` gives the halted line, exit 2 | the file is read only on entry to `run()`, so a wait inside `on` would not see it |
| 2. a live process of a session the log names | "wait: session `<id>` is still running (pid <n>)", exit 0, nothing started | no row: the log's open session parks, after the decision |
| 3. an open `parked` issue of its own | "wait: parked #n" (C05.6) | as it is |
| 4. an open pull request from the maintainer's account | Day 1's "wait: #n"; the tree is not touched | `to_main` runs first and can switch the branch; the kit lists the repository owner's pull requests, which are not `@me`'s when the `gh` login is another account |
| 5. uncommitted changes | parks, its issue naming the paths, branch, last commit and session | the issue holds the line, the step, a session of "none" and the time; no branch, commit or paths |
| 6. a branch of the next step, no pull request | parks the same way | as row 5 |
| 7. a clean tree on another branch | `to_main` (C06.1) | as it is |
| 8. a clean tree on `main`, no branch of the step | the evidence run, the log's checks, then the session | as it is |

**The run log** (`driver/runlog.py`).
- A `pid` line, `{"event": "pid", "at", "session", "pid", "started"}`, appended and fsynced by
  `once.run_session` right after `Popen`, for a first session and for a resume alike. `started` is
  the `lock.STAMP` time read after `Popen`, so that `lock.lives(pid, started)` answers for it as it
  does for the lock: a reused pid counts as gone.
- `live_session(state)` returns `(session, pid, None)` for the newest session whose last `pid` line
  has no later `end` line for that session and whose process lives; `(None, None, None)` when there
  is none or no log; `(None, None, reason)` when the log cannot be read. It covers every session in
  the log, not only the next step's.
- The log is unreadable at a line, as at a torn one ("the run log cannot be read at line <n>"),
  when a `start` line's `session` is missing or not a string (H04.4), or a `pid` line fails what
  `lock.read` asks of a lock: `pid` an int, not a bool, `0 < pid < 2**31`; `started` a string that
  parses with `lock.STAMP`.
- `last_session(state, prefix)` gives the newest session started for the prefix, else `None`, also
  on an unreadable log. `start(...)` gains `issue=None`; when given, the line carries the issue's
  number.
- A `park` line, `{"event": "park", "at", "step", "line"}`, written by `once.park_issue`, and a
  `merged` line, `{"event": "merged", "at", "pr"}`, written by `loop.wait_merge` on "MERGED". The
  log counts every park, before a session and after one.

**A crash's session** (H04.3). A `start` with no `end` whose process is gone stays Day 4's "park:
the run log names session `<id>` for this step, with no end". A closed `parked` issue of exactly
that title answers it, as a phase's end is answered (`plan.md`: "the maintainer's go on"). A branch
of the step still parks first (row 6), so a new session starts only when nothing of the first is
left. Nothing is resumed (rule 4).

**The wait on a live session in `on`.** Row 2 gives `ready()` a new kind, "running". `on` prints
its line once, sleeps `--poll` seconds and reads the kit's JSON and the table again, so that row 1
stops it and the row below takes over when the process ends. `--once` prints the line and exits 0.

**The lock** (`driver/lock.py`, H03.3). A start that finds a lock whose process is gone creates
`<state>/lock.takeover` with `O_EXCL`, reads the lock again, replaces it by `os.replace` with its
own, which also holds `"took_over": <the old pid>`, and removes the guard, so that of two starts
one takes it. `take` still returns `None` for a lock it holds; `lock.took_over(state)` returns that
pid, or `None`. `run` prints "lock: taken over from pid <n>, which is gone" on stdout, and nothing
starts until the table has been read through. A `lock.takeover` that exists refuses (C07.6's line);
`clear` removes it, with the stale lock. An unreadable lock still refuses (C03.2's line).

**A lost or torn log** (`plan.md`, "Recovery": "A lost or torn log makes it park, not guess"). A
start that took over a lock and finds no `run.jsonl` parks at row 2: "park: the run log is missing,
and a lock shows a driver ran (pid <n>)". The next start has no stale lock and goes on through the
table. A torn log parks at row 2 too, with Day 4's "park: <reason>", because a log that cannot be
read cannot say no session lives; an open `parked` issue of exactly that title waits instead, row
3's "wait: parked #n" with no comment added. Closing it answers nothing: the next start parks
again while the log stays torn.

**`halt` and a session a crash left** (`driver/switches.py`). `plan.md`'s halt "kills the running
session", and a session whose driver crashed is in no lock's tree. `halt` reads `live_session`
first, then does the lock's kill as today, then, when that session still lives, kills it and its
descendants: `taskkill /T` on Windows, on POSIX the pid and `once.descendants(pid)`, since it leads
no group. It prints "halt: set; killed session `<id>` (pid <n>) and the processes it started" in
place of "halt: set; no driver is running", and runs `_report` when the lock's branch has not. A
process already gone prints no line. A failed kill prints "halt: set; could not kill session `<id>`
(pid <n>): <reason>" and, like a log it cannot read ("halt: the run log cannot be read at line <n>;
no session was looked for"), does not change the exit code: the halt file stands.

**Row 4's author** (`plan.md`, "What to build": "It acts only on pull requests the maintainer's
account opened"). When the kit's `open_prs` is not empty, `ready()` calls `github.mine(project,
gh)`, which runs `gh pr list --state open --author @me --limit 100 --json number`, and passes
`decide()` (unchanged) only those. A failed read gives "cannot read the project: gh pr list exited
<n>", exit 2. `to_main` runs only when none of the maintainer's is open. With only another account's
open, the kit's sentence waits and `decide()` gives Day 1's "park: the next step waits on no open
pull request".

**A park's body** (H05.4). Every issue `park_issue` opens holds, in order: the line, a blank line,
"step: <sentence>", "session: <id or none>", "branch: <name or detached HEAD>", "last commit: <7
characters or none>", "uncommitted paths:" followed by each line of `git status --porcelain`, at
most 50 and then "and <k> more" (or the one line "uncommitted paths: none"), Day 5's "at: <stamp>",
a blank line, and "Close this issue to let the driver go on.". The session is the one the park
names; `None` or the string "none" (`loop.py`'s between-steps record) falls back to
`last_session(state, prefix)` for the step.

**`status`** (H05.2; `plan.md`, "The switches" and "What to build", item 5). `python run-steps.py
status [--config] [--project] [--state] [--gh]` reads the state folder and the project's open
issues, takes no lock and writes nothing. On stdout, in this order:

```
mode: on (pid 1234, since 2026-11-08T10:00:00Z)
level: 1
halt: none
run's issue: #12
open parks: #14, #15
in progress: Day 07 Track A: the run log (session `<id>`), cost so far $0.40
steps:
  2026-11-08T10:00:00Z Day 07 Track A: the run log: opened: #20 from `day-07/track-a-x`, $1.20, refusals 0, session `<id>`
  2026-11-08T11:00:00Z Day 07 Track B: the lock: no end, $0.00, refusals 0, session `<id>`
parks by reason:
  2 park: the session ended with no pull request and no PARK line (session `…`)
refusals: 3
cost: $3.40, merged pull requests 2, $1.70 each (baseline $1.86)
```

- `mode`: the line above when the lock's process lives; else "mode: off", "mode: off (a lock names
  pid <n>, which is gone)" or "mode: off (the lock cannot be read)". `halt`: "halt: none" or "halt:
  set: <the halt file's text>". `level` is 1 until level 2 exists.
- `run's issue`: the lowest open "Driver run" issue, or "none"; `open parks`: the open `parked`
  issues, or "none".
- `in progress`: the step and session `live_session` names; else, while the lock's process lives,
  `run.json`'s step and session (during `on`'s waits); else "in progress: none". Its cost is the sum
  of that session's `end` costs, a `null` counting 0.
- `steps`: one line per `start` line: its time, step, its last `end` outcome or "no end", the sum of
  its costs and refusals, its session. No `start` lines: "steps: none".
- `parks by reason` counts the `park` lines, grouped after each backticked span becomes `` `…` ``,
  each `#<n>` becomes "#n" and "(<n> paths)" becomes "(n paths)", most frequent first, then by text.
  None: "parks by reason: none".
- `refusals` sums the `end` lines' `denials`. `cost` sums their `cost_usd`; with no `merged` line:
  "cost: $3.40, merged pull requests 0 (baseline $1.86)". The baseline is `plan.md`'s, "What it is
  judged against".
- A log that cannot be read: "in progress: unknown" and, on stdout in place of `steps` through
  `cost`, "run log: the run log cannot be read at line <n>", exit 2. A `gh` that fails: "run's
  issue: unknown", "open parks: unknown", the rest printed, then "cannot read the project: gh issue
  list exited <n>" on stderr, exit 2. Otherwise exit 0. A config with a problem exits 2 with its lines.

**The run's issue shows the cost** (Day 5's Out of scope, H05.2). `issues.open_run` gains
`state=None`; given it, its body and comment add "cost so far: $<x.xx>", the sum of the `end` costs
of the sessions whose `start` line carries that issue's number, $0.00 on a new issue.

**The dry run and an answered phase's end** (H05.2). When `decide()` names a phase's end, the dry
run reads `issues.closed_parks` and decides again, as `--once` does (C07.20). No other dry run reads
an issue.

## Out of scope
- The count of 15 pull requests in a row merged at level 1 without a change asked — Day 8's record
  (H06.2): "without a change asked" needs review data the run log does not hold.
- `checks` against the real `gh` with no required checks (H06.3, D06.13), with H05.5's two `gh`
  commands — Day 8, on the trial's repository, the maintainer's scratch run first.
- Replies per merged pull request beside the 34.4 baseline, and the usage limit (H06.1) — Day 8.
- Any change to `driver/decide.py`, `driver/steps.py`, `driver/settings.py`, `driver/home.py`,
  `driver/preflight.py`, `driver/config.py`, `hooks/` and `rules/session.md`.

## Tracks

| Track | Owner | Work |
|---|---|---|
| 0 | | The tests that pass before and after: C07.1, C07.2, C07.14, C07.21 |
| A | | The run log: `pid`, `live_session`, the validated lines: C07.3–C07.5 |
| B | | The lock taken over, the lost log: C07.6, C07.7 |
| C | | Rows 1 and 2, `on`'s wait, a crash's session answered, `halt`: C07.8–C07.11 |
| D | | Rows 3 to 8, the author: C07.12, C07.13 |
| E | | A park's body: C07.15 |
| F | | The log's `park` and `merged` lines, the run's issue's cost: C07.16, C07.19 |
| G | | `status`: C07.17, C07.18 |
| H | | The dry run on an answered phase's end: C07.20 |

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").

- [x] C07.1 **hold** — Rules 5 and 7 of "Recovery", read from the code: over `run-steps.py` and
      `driver/*.py`, parsed with `ast` so that a comment or a docstring cannot match, no string
      constant is exactly `reset`, `stash`, `clean`, `restore`, `checkout`, `rebase`, `push`, `rm`,
      `-D`, `-d` or `--delete`; no list or tuple holds `"pr"` with `create`, `close`, `merge`, `edit`
      or `review` anywhere after it; no call passes `shell=True`.
      Test: `RecoveryRulesTest.test_no_command_that_can_lose_work`,
      `RecoveryRulesTest.test_no_pull_request_opened_or_closed`, `RecoveryRulesTest.test_no_shell`.
      Each is broken twice, the thing put back (a `"stash"` in a list; `"pr", "--repo", "r",
      "close"`; `shell=True`) and a near miss it must not match (a comment naming `git stash`;
      `"issue", "close"`; `shell=False`).
      Evidence: `RecoveryRulesTest.test_no_command_that_can_lose_work`, `RecoveryRulesTest.test_no_pull_request_opened_or_closed`, `RecoveryRulesTest.test_no_shell` (#85).
      broken: near miss, a comment naming git stash → OK (#85)
      broken: near miss, an issue close → OK (#85)
      broken: near miss, to_main's git run with shell=False → OK (#85)
      broken: a stash in to_main's git commands → AssertionError: Lists differ: ["driver/tree.py:23 'stash' can lose work"] != [] (#85)
      broken: a pr close with --repo between the words → AssertionError: Lists differ: ['driver/tree.py:23 a pull request is opened or closed'] != [] (#85)
      broken: to_main's git run with shell=True → AssertionError: Lists differ: ['driver/tree.py:29 shell=True'] != [] (#85)
- [x] C07.2 **hold** — Earlier days' tests pass and Verify's diff is empty against `4a2c53f`. The
      only earlier tests edited: `tests/test_lock.py`'s `test_stale_lock_refuses` and
      `test_reused_pid_is_gone` (C07.6, Track B), `tests/test_once.py`'s `waiting` case, whose fake
      `gh` gains #7 by "me" (C07.12, Track D), and the `events == ["start"]` assertions of
      `tests/test_once_halt.py`'s `test_halt_during_once` and `tests/test_once_stop.py`'s
      `test_stop_during_session`, which become `["start", "pid"]` (C07.3, Track A).
      Test: `python -m unittest discover -s tests` and the diff in Verify.
      Broken once, in the spec-change PR: open pull requests no longer winning over a dirty tree.
      Evidence: the commands above, on `main` at `f4a3067` after #109: `python scripts/test-parallel.py`, the same tests as `python -m unittest discover -s tests`, ran 301 tests, "OK (skipped=4)", and the diff in Verify printed nothing; each track PR ran the suite (#85 to #107).
      broken: open pull requests no longer win over a dirty tree → AssertionError: Tuples differ: ('park: the next step waits on no open pull request', 'park') != ('wait: #12, #13', 'wait') (#79)
- [x] C07.3 **new** — After a `--once` on the fake `claude`, the run log's lines for the session are
      `start`, `pid`, `end`, in that order, and the `pid` line holds an int `pid`, a `started` that
      parses with `lock.STAMP`, and the session's uuid. A resume writes a second `pid` line after its
      `fix` line. `runlog.pid` writes one fsynced line, no carriage return.
      Red today: the log has no `pid` line (`start`, `end` only).
      Test: `RunLogPidTest.test_pid_line_between_start_and_end`,
      `RunLogPidTest.test_resume_writes_a_pid_line`, `RunLogPidTest.test_pid_is_fsynced`.
      Evidence: `RunLogPidTest.test_pid_line_between_start_and_end`, `RunLogPidTest.test_resume_writes_a_pid_line`, `RunLogPidTest.test_pid_is_fsynced` (#88).
      seen red: tests.test_runlog_recovery.RunLogPidTest.test_pid_line_between_start_and_end on main → AssertionError: Lists differ: ['start', 'end'] != ['start', 'pid', 'end'] (#88)
      seen red: tests.test_runlog_recovery.RunLogPidTest.test_resume_writes_a_pid_line on main → FAILED (errors=1) (#88)
      seen red: tests.test_runlog_recovery.RunLogPidTest.test_pid_is_fsynced on main → FAILED (errors=1) (#88)
      seen red: tests.test_once_halt.OnceHaltTest.test_halt_during_once tests.test_once_stop on main → AssertionError: Lists differ: ['start'] != ['start', 'pid'] (#88)
      broken: run_session writes no pid line → AssertionError: Lists differ: ['start', 'end'] != ['start', 'pid', 'end'] (#88)
      broken: a log line not fsynced → AssertionError: 0 != 1 (#88)
      Not replayed, its report holds a pid or a time: the pid line names the driver, not the session → AssertionError: Lists differ: [16256] != [22896] (#88)
- [x] C07.4 **new** — `runlog.live_session`, with a child the test starts: `start`, `pid` of the live
      child gives `(session, pid, None)`; an `end` after it gives none; `start`, `pid`, `end`, `fix`,
      `pid` of a live child (a resume) gives that session; a child that has exited gives none; a
      `started` an hour before the child began gives none (a reused pid); a session of another prefix
      is found; no log gives `(None, None, None)`; a torn second line gives `(None, None, "the run
      log cannot be read at line 2")`.
      Red today: `AttributeError: module 'driver.runlog' has no attribute 'live_session'`.
      Test: `LiveSessionTest.test_truth_table`, `LiveSessionTest.test_torn_log`.
      Evidence: `LiveSessionTest.test_truth_table`, `LiveSessionTest.test_torn_log` (#88).
      seen red: tests.test_runlog_recovery.LiveSessionTest.test_truth_table on main → FAILED (errors=10) (#88)
      seen red: tests.test_runlog_recovery.LiveSessionTest.test_torn_log on main → FAILED (errors=1) (#88)
      broken: live_session lets an unreadable log raise → FAILED (errors=1) (#88)
      Not replayed, its report holds a pid or a time: live_session ignores end lines → AssertionError: Tuples differ: ('s1', 23280, None) != (None, None, None) (#88)
      Not replayed, its report holds a pid or a time: live_session reads the log from the top → AssertionError: Tuples differ: ('s1', 19752, None) != (None, None, None) (#88)
      Not replayed, its report holds a pid or a time: live_session takes any named pid as alive → AssertionError: Tuples differ: ('s1', 8600, None) != (None, None, None) (#88)
      Not replayed, its report holds a pid or a time: live_session ignores when the process started → AssertionError: Tuples differ: ('s1', 27304, None) != (None, None, None) (#88)
      Not replayed, its report holds a pid or a time: an earlier pid line answers for a session whose last is gone → AssertionError: Tuples differ: ('s1', 27448, None) != (None, None, None) (#88)
- [x] C07.5 **new** — H04.4: each of a `start` line with no `session` key, one with `session` 7, a
      `pid` line with `pid` "x", `true` or `2147483648`, one with no `started`, and one with `started`
      "x" gives `open_session`, `failures` and `live_session` the reason "the run log cannot be read
      at line <n>", and none raises. `last_session` gives the newest session of the prefix, `None`
      for another prefix, and `None` on a torn log.
      Red today: `open_session` returns `(None, None)` for the `start` line with no `session`.
      Test: `RunLogLinesTest.test_bad_lines_are_unreadable`, `RunLogLinesTest.test_last_session`.
      Evidence: `RunLogLinesTest.test_bad_lines_are_unreadable`, `RunLogLinesTest.test_last_session` (#88).
      seen red: tests.test_runlog_recovery.RunLogLinesTest.test_bad_lines_are_unreadable on main → AssertionError: Tuples differ: ('s1', None) != (None, 'the run log cannot be read at line 2') (#88)
      seen red: tests.test_runlog_recovery.RunLogLinesTest.test_last_session on main → FAILED (errors=1) (#88)
      broken: a start line with no session is read → AssertionError: Tuples differ: (7, None) != (None, 'the run log cannot be read at line 2') (#88)
      broken: a pid line with no session is read → AssertionError: Tuples differ: ('s1', None) != (None, 'the run log cannot be read at line 2') (#88)
      broken: a bool is read as a pid → AssertionError: Tuples differ: ('s1', None) != (None, 'the run log cannot be read at line 2') (#88)
      broken: a pid out of range is read → AssertionError: Tuples differ: ('s1', None) != (None, 'the run log cannot be read at line 2') (#88)
      broken: a pid line's started need not be a string → FAILED (errors=1) (#88)
      broken: a pid line's started need not parse → AssertionError: Tuples differ: ('s1', None) != (None, 'the run log cannot be read at line 2') (#88)
      broken: last_session ignores the prefix → AssertionError: 's2' is not None (#88)
- [x] C07.6 **new** — H03.3: `lock.take` on a lock naming a process that has exited returns `None`,
      the lock then names this process, `lock.took_over` gives the old pid, and `<state>/lock.takeover`
      is gone; a lock taken with no stale one has no `took_over`. A `lock.takeover` already there
      refuses with "cannot start: <state>/lock.takeover exists: another start is taking the lock over;
      run-steps.py clear removes it", the lock's bytes as they were. Eight processes started together
      on one stale lock, each holding what it got until all have reported: exactly one gets `None`.
      `clear` removes a `lock.takeover`. `--once` on a stale lock prints "lock: taken over from pid
      <n>, which is gone" on stdout before its other lines. The rest of C03.2 stands, in
      `tests/test_lock.py`: a live lock and an unreadable one refuse, `release` leaves another pid's
      lock, asking leaves a live child running, and a reused pid counts as gone, so it is taken over.
      Red today: `take` returns "cannot start: a lock names pid <n>, which is gone; run-steps.py clear
      removes it".
      Replaces: C03.2 — was: a lock naming a process that has exited is refused, and `run-steps.py clear` removes it.
      Test: `LockTakeoverTest.test_stale_lock_taken_over`, `LockTakeoverTest.test_guard_refuses`,
      `LockTakeoverTest.test_eight_starts_one_winner`, `LockTakeoverTest.test_clear_removes_guard`,
      `LockTakeoverTest.test_once_prints_the_takeover`.
      Evidence: `LockTakeoverTest.test_stale_lock_taken_over`, `LockTakeoverTest.test_guard_refuses`, `LockTakeoverTest.test_eight_starts_one_winner`, `LockTakeoverTest.test_clear_removes_guard`, `LockTakeoverTest.test_once_prints_the_takeover` (#89).
      seen red: python -m unittest tests.test_lock_takeover.LockTakeoverTest.test_stale_lock_taken_over on main → AssertionError: 'cannot start: a lock names pid 26832, which is gone; run-steps.py clear removes it' is not None (#89)
      seen red: python -m unittest tests.test_lock_takeover.LockTakeoverTest.test_guard_refuses on main → AssertionError: 'cannot start: a lock names pid 23016, which is gone; ru[23 chars]s it' != 'cannot start: C:\\Users\\HACKYO~1\\AppData\\Local\\Temp[101 chars]s it' (#89)
      seen red: python -m unittest tests.test_lock_takeover.LockTakeoverTest.test_read_again_finds_it_taken on main → AssertionError: 'already running (pid 16620, since 2026-11-09T11:51:13Z)' not found in 'cannot start: a lock names pid 26324, which is gone; run-steps.py clear removes it' (#89)
      seen red: python -m unittest tests.test_lock_takeover.LockTakeoverTest.test_replace_refused_retries_then_refuses on main → FAILED (errors=1) (#89)
      seen red: python -m unittest tests.test_lock_takeover.LockTakeoverTest.test_eight_starts_one_winner on main → AssertionError: 0 != 1 (#89)
      seen red: python -m unittest tests.test_lock_takeover.LockTakeoverTest.test_clear_removes_guard on main → FAILED (errors=1) (#89)
      seen red: python -m unittest tests.test_lock_takeover.LockTakeoverTest.test_once_prints_the_takeover on main → AssertionError: 2 != 1 (#89)
      seen red: python -m unittest tests.test_lock.LockTest.test_stale_lock_refuses tests.test_lock.LockTest.test_reused_pid_is_gone on main → AssertionError: 'cannot start: a lock names pid 28392, which is gone; run-steps.py clear removes it' is not None (#89)
      broken: the guard opened without O_EXCL → AssertionError: None != 'cannot start: <tmp>/lock.take[77 chars]s it' (#89)
      broken: one try at the replace → AssertionError: 1 != 20 (#89)
      broken: clear leaves the guard → AssertionError: True is not false (#89)
      Not replayed, its report holds a pid or a time: the new lock without took_over → AssertionError: None != 15512 (#89)
      Not replayed, its report holds a pid or a time: no takeover line → AssertionError: "park: the project's tree is not clean (1 paths)" != 'lock: taken over from pid 18324, which is gone' (#89)
      Not replayed, its report holds a pid or a time: the second read ignored → AssertionError: 'already running (pid 25920, since 2026-11-09T11:48:24Z)' not found in 'None' (#89)
- [x] C07.7 **new** — `--once` on a stale lock with no `run.jsonl` prints "park: the run log is
      missing, and a lock shows a driver ran (pid <n>)", exit 1, starts no session (the fake records
      only `--version` and `--help`) and opens one `parked` issue of that title; with that issue
      closed, the next `--once` has no stale lock and starts the step. A stale lock with a log goes on
      through the table.
      Red today: `--once` refuses on the stale lock, exit 2.
      Test: `LostLogTest.test_stale_lock_and_no_log_parks`, `LostLogTest.test_next_start_goes_on`,
      `LostLogTest.test_stale_lock_with_a_log_goes_on`.
      Evidence: `LostLogTest.test_stale_lock_and_no_log_parks`, `LostLogTest.test_next_start_goes_on`, `LostLogTest.test_stale_lock_with_a_log_goes_on` (#89).
      seen red: python -m unittest tests.test_lock_takeover.LostLogTest.test_stale_lock_and_no_log_parks on main → FAILED (errors=1) (#89)
      seen red: python -m unittest tests.test_lock_takeover.LostLogTest.test_next_start_goes_on on main → FAILED (errors=1) (#89)
      seen red: python -m unittest tests.test_lock_takeover.LostLogTest.test_stale_lock_with_a_log_goes_on on main → FAILED (errors=1) (#89)
      broken: the lock kept after the run → AssertionError: Tuples differ: (True, True, 0) != (False, False, 1) (#89)
      Not replayed, its report holds a random session id: a lost log never parks → AssertionError: Tuples differ: (1, [[55 chars] the session ended with no pull request and no[475 chars]5']]) != (1, [[55 chars] the run log is missing, and a lock shows a dr[21 chars], []) (#89)
      Not replayed, its report holds a pid or a time: a takeover parks even with a log → AssertionError: 'park: the run log is missing, and a lock shows a driver ran (pid 8236)' != "park: the project's tree is not clean (1 paths)" (#89)
- [x] C07.8 **new** — Row 2. `--once` with a log naming a live child prints "wait: session `<id>` is
      still running (pid <n>)", exit 0, starts no session, opens no issue and moves no branch. That
      row wins over an open `parked` issue, an open pull request, a dirty tree and a branch of the
      step, each set with it. A torn log prints "park: the run log cannot be read at line 2", exit 1,
      with an open pull request set and with an open `parked` issue of another title.
      Red today: with a live child and no other row the line is "park: the run log names session
      `<id>` for this step, with no end"; with an open `parked` issue, "wait: parked #n"; with a torn
      log and #7 open, "wait: #7".
      Test: `TableTest.test_live_session_waits`, `TableTest.test_live_session_beats_the_rows_below`,
      `TableTest.test_torn_log_parks_first`.
      Evidence: `TableTest.test_live_session_waits`, `TableTest.test_live_session_beats_the_rows_below`, `TableTest.test_torn_log_parks_first` (#95).
      seen red: python -m unittest tests.test_recovery_table.TableTest.test_live_session_waits on main → AssertionError: Tuples differ: (1, ['park: the run log names session `000[59 chars]nd']) != (0, ['wait: session `00000000-0000-4000-80[42 chars]8)']) (#95)
      seen red: python -m unittest tests.test_recovery_table.TableTest.test_live_session_beats_the_rows_below on main → AssertionError: Tuples differ: (1, ['park: a branch of this step exists: day-01/spec-x']) != (0, ['wait: session `00000000-0000-4000-80[43 chars]2)']) (#95)
      seen red: python -m unittest tests.test_recovery_table.TableTest.test_torn_log_parks_first on main → AssertionError: Tuples differ: (0, 'wait: parked #1') != (1, 'park: the run log cannot be read at line 2') (#95)
      broken: a torn log does not park first → AssertionError: Tuples differ: (0, 'wait: parked #1') != (1, 'park: the run log cannot be read at line 2') (#95)
      Not replayed, its report holds a pid or a time: a live session not waited on → AssertionError: Tuples differ: (1, ['park: the run log names session `000[59 chars]nd']) != (0, ['wait: session `00000000-0000-4000-80[43 chars]2)']) (#95)
- [x] C07.9 **new** — `on --poll 0.2` on a log naming a live child: the test reads the row 2 line from
      `on`'s stdout, and only then lets the child exit (it waits for a file the test creates); `on`
      has printed that line once, prints "park: the run log names session `<id>` for this step, with
      no end", exit 1, and starts no session. A halt file written after that line is read ends the
      run with "cannot start: halted: <halt> exists; run-steps.py clear removes it", exit 2; a `STOP`
      issue added then, with the halted line and the halt file, exit 2; no session in either.
      Red today: `on` parks at once, and never prints the wait.
      Test: `OnWaitsTest.test_waits_then_reads_the_table_again`, `OnWaitsTest.test_halt_file_ends_the_wait`,
      `OnWaitsTest.test_stop_ends_the_wait`.
      Evidence: `OnWaitsTest.test_waits_then_reads_the_table_again`, `OnWaitsTest.test_halt_file_ends_the_wait`, `OnWaitsTest.test_stop_ends_the_wait` (#95).
      seen red: python -m unittest tests.test_recovery_table.OnWaitsTest.test_waits_then_reads_the_table_again on main → AssertionError: 'park: the run log names session `00000000[52 chars] end' != 'wait: session `00000000-0000-4000-8000-00[36 chars]236)' (#95)
      seen red: python -m unittest tests.test_recovery_table.OnWaitsTest.test_halt_file_ends_the_wait on main → AssertionError: 'park: the run log names session `00000000[52 chars] end' != 'wait: session `00000000-0000-4000-8000-00[35 chars]004)' (#95)
      seen red: python -m unittest tests.test_recovery_table.OnWaitsTest.test_stop_ends_the_wait on main → AssertionError: 'park: the run log names session `00000000[52 chars] end' != 'wait: session `00000000-0000-4000-8000-00[35 chars]220)' (#95)
      Not replayed, its report is cut inside a temporary name: the halt file not read in the table → AssertionError: Tuples differ: (1, '') != (2, 'cannot start: halted: `C:\\Users\\HAC[100 chars] it') (#95)
      Not replayed, its report holds a pid or a time: the wait said on every poll → AssertionError: Lists differ: ['wait: session `00000000-0000-4000-8000-00[138 chars]end'] != ['park: the run log names session `00000000[53 chars]end'] (#95)
- [x] C07.10 **new** — H04.3: a `start` with no `end`, its process gone, no branch of the step, and a
      closed `parked` issue titled exactly "park: the run log names session `<id>` for this step, with
      no end": `--once` starts a new session whose uuid is not `<id>`.
      Red today: `ready()` parks on the session and opens a second issue.
      Test: `CrashAnsweredTest.test_closed_park_starts_a_new_session`.
      Evidence: `CrashAnsweredTest.test_closed_park_starts_a_new_session` (#95).
      seen red: python -m unittest tests.test_recovery_table.CrashAnsweredTest.test_closed_park_starts_a_new_session on main → AssertionError: Tuples differ: (1, False) != (0, True) (#95)
      broken: a closed park does not answer a crash → AssertionError: Tuples differ: (1, False) != (0, True) (#95)
- [x] C07.11 **new** — `halt --state <state>` with no lock and a log naming a live child kills it and
      its child (both gone within 10 seconds), prints "halt: set; killed session `<id>` (pid <n>) and
      the processes it started" and not "no driver is running", reports on the run's issue when
      `run.json` is there, exit 0. With a live lock and such a session outside its tree, both are gone
      and the exit is 0. A torn log prints "halt: the run log cannot be read at line <n>; no session
      was looked for", the halt file is there, and the exit is the lock branch's. The rest of C03.6
      stands, in `tests/test_halt.py`.
      Red today: the child still runs and the line is "halt: set; no driver is running".
      Replaces: C03.6 — was: with no lock, or a lock whose process is gone, `halt` prints "halt: set; no driver is running", whatever session a crash left.
      Test: `HaltSessionTest.test_kills_a_session_with_no_driver`,
      `HaltSessionTest.test_lock_and_session`, `HaltSessionTest.test_torn_log`.
      Evidence: `HaltSessionTest.test_kills_a_session_with_no_driver`, `HaltSessionTest.test_lock_and_session`, `HaltSessionTest.test_torn_log` (#95).
      seen red: python -m unittest tests.test_recovery_table.HaltSessionTest.test_kills_a_session_with_no_driver on main → AssertionError: Lists differ: ['halt: set; no driver is running'] != ['halt: set; killed session `00000000-0000-4000-8000-0[74 chars] #4'] (#95)
      seen red: python -m unittest tests.test_recovery_table.HaltSessionTest.test_lock_and_session on main → AssertionError: 'halt: set; killed session `00000000-0000-4000-8000-000000000000` (pid 14592) and the processes it started' not found in ['halt: set; killed pid 24880 and the processes it started', 'halt: reported on #4'] (#95)
      seen red: python -m unittest tests.test_recovery_table.HaltSessionTest.test_torn_log on main → AssertionError: 'halt: the run log cannot be read at line 2; no session was looked for' not found in ['halt: set; C:\\Users\\HACKYO~1\\AppData\\Local\\Temp\\tmprq3c7r7m\\unreadable\\lock cannot be read, so nothing was killed'] (#95)
      seen red: python -m unittest tests.test_recovery_table.HaltSessionTest.test_failed_kill_keeps_the_exit_code on main → FAILED (errors=1) (#95)
      broken: halt says killed and kills nothing → FAILED (errors=1) (#95)
      broken: halt reports twice → AssertionError: Tuples differ: (0, 2) != (0, 1) (#95)
      broken: a torn log not said at halt → AssertionError: 'halt: the run log cannot be read at line 2; no session was looked for' not found in ['halt: set; <tmp>/unreadable/lock cannot be read, so nothing was killed'] (#95)
      broken: a failed kill not said → AssertionError: Lists differ: [] != ['halt: set; could not kill session `00000[46 chars]ied'] (#95)
      Not replayed, its report holds a pid or a time: halt looks for no session → AssertionError: Lists differ: ['halt: set; no driver is running'] != ['halt: set; killed session `00000000-0000-4000-8000-0[74 chars] #4'] (#95)
      Not replayed, its report holds a pid or a time: halt skips the session when a lock lives → AssertionError: 'halt: set; killed session `00000000-0000-4000-8000-000000000000` (pid 25536) and the processes it started' not found in ['halt: set; killed pid 23720 and the processes it started', 'halt: reported on #4'] (#95)
- [x] C07.12 **new** — Row 4's author. With the kit's `open_prs` naming #7, the sentence waiting, and
      the fake holding #7 by "someone": "park: the next step waits on no open pull request", exit 1. A
      fake whose `pr list` exits 1 on that read: "cannot read the project: gh pr list exited 1", exit 2.
      Red today: both print "wait: #7".
      Test: `AuthorTest.test_someone_elses_on_a_waiting_sentence_parks`, `AuthorTest.test_gh_fails`.
      Evidence: `AuthorTest.test_someone_elses_on_a_waiting_sentence_parks`, `AuthorTest.test_gh_fails` (#100).
      seen red: python -m unittest tests.test_recovery_table.AuthorTest.test_someone_elses_on_a_waiting_sentence_parks on main → AssertionError: Tuples differ: (0, 'wait: #7') != (1, 'park: the next step waits on no open pull request') (#100)
      seen red: python -m unittest tests.test_recovery_table.AuthorTest.test_gh_fails on main → AssertionError: Tuples differ: (0, '') != (2, 'cannot read the project: gh pr list exited 1') (#100)
      broken: another account's pull request counts → AssertionError: Tuples differ: (0, 'wait: #7') != (1, 'park: the next step waits on no open pull request') (#100)
      broken: the read not limited to @me → AssertionError: Tuples differ: (0, 'wait: #7') != (1, 'park: the next step waits on no open pull request') (#100)
      broken: a failed read of the author not said → AssertionError: Tuples differ: (1, '') != (2, 'cannot read the project: gh pr list exited 1') (#100)
- [x] C07.13 **new** — A clean tree on `day-07/other` (no branch of the step), `main` one commit
      behind `origin/main` and #7 open by "me": `--once` prints "wait: #7" and the project is still on
      `day-07/other`, `main` where it was.
      Red today: `to_main` has switched the project to `main`.
      Test: `TableTest.test_open_pr_leaves_the_tree`.
      Evidence: `TableTest.test_open_pr_leaves_the_tree` (#100).
      seen red: python -m unittest tests.test_recovery_table.TableTest.test_open_pr_leaves_the_tree on main → AssertionError: 'main' != 'day-07/other' (#100)
      broken: the tree moved with a pull request open → AssertionError: 'main' != 'day-07/other' (#100)
- [x] C07.14 **hold** — The rest of the table, each pair set together, the higher row's outcome
      alone: row 3 over 4 (`parked` open and #7 open: "wait: parked #n"); 4 over 5 (#7 and a dirty
      tree: "wait: #7"); 5 over 6 (a dirty tree and a branch of the step: C01.4's "park: the project's
      tree is not clean (1 paths)"); 6 over 7 (a branch of the step, the project clean on another:
      parks, still on that branch); 7 over 8 (a clean tree on another branch, no branch of the step:
      `to_main`, then the session). #7 is by "me" in the fake.
      Test: `RecoveryHoldTest.test_rows_three_to_eight`.
      Broken once: `ready()` reading the open parks after `decide()`.
      Evidence: `RecoveryHoldTest.test_rows_three_to_eight` (#85).
      broken: ready() reading the open parks after decide() → AssertionError: Tuples differ: (0, 'wait: #7') != (0, 'wait: parked #1') (#85)
- [x] C07.15 **new** — H05.4: with a dirty tree of two paths on `main` and an earlier `start` line of
      the step's prefix, the park's body in `bodies.jsonl` equals In scope's, in its order, naming the
      session, "branch: main", the seven characters and both porcelain lines. A branch of the step:
      "uncommitted paths: none". No session in the log: "session: none" in that same whole body. A
      park with the string session "none" falls back to the log's. 53 dirty paths: 50 lines, then "and
      3 more". A detached HEAD: "branch: detached HEAD".
      Red today: the body has no "branch:" line.
      Test: `ParkBodyTest.test_dirty_tree`, `ParkBodyTest.test_branch_of_the_step`,
      `ParkBodyTest.test_no_session`, `ParkBodyTest.test_none_string_falls_back`,
      `ParkBodyTest.test_capped`, `ParkBodyTest.test_detached_head`.
      Evidence: `ParkBodyTest.test_dirty_tree`, `ParkBodyTest.test_branch_of_the_step`, `ParkBodyTest.test_no_session`, `ParkBodyTest.test_none_string_falls_back`, `ParkBodyTest.test_capped`, `ParkBodyTest.test_detached_head` (#101).
      seen red: python -m unittest tests.test_park_body on main → AssertionError: Tuples differ: (1, "[147 chars]one\nat: STAMP\n\nClose this issue to let the driver go on.\n") != (1, "[147 chars]one\nbranch: main\nlast commit: f195c6d\nuncom[82 chars].\n") (#101)
      broken: park_issue falling back only for None, not the string "none" → AssertionError: Tuples differ: (1, False) != (1, True) (#101)
      broken: park_body listing every porcelain line, no cap of 50 → AssertionError: Tuples differ: (1, "[805 chars]txt\n?? f50.txt\n?? f51.txt\n?? f52.txt\nand 3[60 chars].\n") != (1, "[805 chars]txt\nand 3 more\nat: STAMP\n\nClose this issue[24 chars].\n") (#101)
      broken: park_body writing a bare "uncommitted paths:" on a clean tree → AssertionError: Tuples differ: (1, '[225 chars]aths:\nat: STAMP\n\nClose this issue to let th[21 chars]alse) != (1, '[225 chars]aths: none\nat: STAMP\n\nClose this issue to l[25 chars]True) (#101)
- [x] C07.16 **new** — The log counts: a park before a session and one after it each write one `park`
      line, its `line` the printed line and its `step` the sentence; `wait_merge` on "MERGED" writes a
      `merged` line with the number; `start(..., issue=12)` carries `"issue": 12`, and without it the
      line's keys are C04.4's.
      Red today: the log has no `park` or `merged` line.
      Test: `RunLogReportTest.test_park_lines`, `RunLogReportTest.test_merged_line`,
      `RunLogReportTest.test_issue_on_start`.
      Evidence: `RunLogReportTest.test_park_lines`, `RunLogReportTest.test_merged_line`, `RunLogReportTest.test_issue_on_start` (#104).
      seen red: python -m unittest tests.test_runlog_report on main → AssertionError: Tuples differ: (1, True, 0) != (1, True, 1) (#104)
      broken: park_issue writing no park line → AssertionError: Tuples differ: (1, True, 0) != (1, True, 1) (#104)
      broken: wait_merge writing no merged line on MERGED → AssertionError: Tuples differ: ((None, 0), []) != ((None, 0), [(['event', 'at', 'pr'], 12)]) (#104)
      broken: start dropping the issue it is given → AssertionError: Tuples differ: ('claude', None, ['event', 'at', 'step', 'prefix', 'session', 'claude']) != ('issue', 12, ['event', 'at', 'step', 'prefix', 'session', 'claude']) (#104)
- [x] C07.17 **new** — `run-steps.py status` on a state folder built by the test, with the fake `gh`,
      prints In scope's block exactly: three `start` lines (one with two `end` lines and a `fix`, one
      with no `end`), `park` lines that group after normalising (two sessions, two `#n`, two path
      counts), `merged` lines, `denials` and `cost_usd` (one `null`), exit 0. Each `mode` and `halt`
      form, the cost with no `merged` line, "steps: none", "parks by reason: none", and `in progress`
      from a live child, from `run.json` under a live lock, and "none" are compared too.
      Red today: argparse exits 2, "invalid choice: 'status'".
      Test: `StatusTest.test_full_report`, `StatusTest.test_mode_forms`, `StatusTest.test_no_merged`,
      `StatusTest.test_no_parks`, `StatusTest.test_in_progress`.
      Evidence: `StatusTest.test_full_report`, `StatusTest.test_mode_forms`, `StatusTest.test_no_merged`, `StatusTest.test_no_parks`, `StatusTest.test_in_progress` (#106).
      seen red: python -m unittest tests.test_status on main → AssertionError: 2 != 0 (#106)
      broken: the path count left in a park's reason → AssertionError: Lists differ: ['mod[465 chars]ck', '  2 park: the session ended with no pull[252 chars]86)'] != ['mod[465 chars]ck', "  2 park: the project's tree is not clea[197 chars]86)'] (#106)
      broken: the session left in a park's reason → AssertionError: Lists differ: ['mod[523 chars], '  1 park: a one-off', '  1 park: the sessio[224 chars]86)'] != ['mod[523 chars], '  2 park: the session ended with no pull re[139 chars]86)'] (#106)
      broken: parks ranked by text alone → AssertionError: Lists differ: ['mod[430 chars], '  1 park: a one-off', '  2 park: pull reque[232 chars]86)'] != ['mod[430 chars], '  2 park: pull request #n is stuck', "  2 p[232 chars]86)'] (#106)
      broken: a step showing its first end, not its last → AssertionError: Lists differ: ['mod[158 chars]log: park: tried, $1.20, refusals 1, session `[480 chars]86)'] != ['mod[158 chars]log: opened: #20 from `day-07/track-a-x`, $1.2[504 chars]86)'] (#106)
      broken: the highest run's issue, not the lowest → AssertionError: Lists differ: ['mod[45 chars]ue: #30", 'open parks: #14, #15', 'in progress[617 chars]86)'] != ['mod[45 chars]ue: #12", 'open parks: #14, #15', 'in progress[617 chars]86)'] (#106)
      broken: a null cost not counted as 0 → AssertionError: Lists differ: [] != ['mode: off', 'level: 1', 'halt: none', "r[671 chars]86)'] (#106)
      broken: the cost with no merged line printing as with one → AssertionError: Lists differ: [] != ['mode: off', 'level: 1', 'halt: none', "r[165 chars]86)'] (#106)
      broken: a live session not read → AssertionError: 'in progress: Step A (session `s1`), cost so far $0.40' not found in ['mode: off', 'level: 1', 'halt: none', "run's issue: #12", 'open parks: #14, #15', 'in progress: none', 'steps:', '  2026-11-08T10:00:00Z Step A: opened: #20, $0.40, refusals 0, session `s1`', 'parks by reason: none', 'refusals: 0', 'cost: $0.40, merged pull requests 0 (baseline $1.86)'] (#106)
      broken: the cost line ignoring merged lines → AssertionError: Lists differ: ['mod[650 chars]t: $1.20, merged pull requests 0 (baseline $1.86)'] != ['mod[650 chars]t: $1.20, merged pull requests 2, $0.60 each (baseline $1.86)'] (#106)
      Not replayed, its report holds a pid or a time: a live lock read as gone → AssertionError: Tuples differ: ('mode: off (a lock names pid 22164, which is gone[43 chars]47Z') != ('mode: on (pid 22164, since 2026-11-10T00:10:47Z)[42 chars]47Z') (#106)
      Not replayed, its report holds a pid or a time: a halt file not seen → AssertionError: Tuples differ: ('mod[29 chars]11-10T00:10:49Z)', 'halt: none') != ('mod[29 chars]11-10T00:10:49Z)', 'halt: set: halted at 2026-11-10T00:10:49Z') (#106)
      Not replayed, its report holds a pid or a time: run.json not read under a live lock → AssertionError: 'in progress: Step R (session `s9`), cost so far $0.00' not found in ['mode: on (pid 19040, since 2026-11-10T00:10:53Z)', 'level: 1', 'halt: none', "run's issue: #12", 'open parks: #14, #15', 'in progress: none', 'steps: none', 'parks by reason: none', 'refusals: 0', 'cost: $0.00, merged pull requests 0 (baseline $1.86)'] (#106)
- [x] C07.18 **new** — `status` changes nothing: the state folder's names and bytes are the same after
      it, with a live lock and without one, and the recorded `gh` calls are only `issue list`. A torn
      log prints "in progress: unknown" and "run log: the run log cannot be read at line 2" on stdout,
      exit 2. A `gh` failing prints "unknown" twice and the local lines, "cannot read the project: gh
      issue list exited 1" on stderr, exit 2. A config with a problem exits 2 with its lines.
      Red today: as C07.17.
      Test: `StatusTest.test_writes_nothing`, `StatusTest.test_torn_log`, `StatusTest.test_gh_down`,
      `StatusTest.test_bad_config`.
      Evidence: `StatusTest.test_writes_nothing`, `StatusTest.test_torn_log`, `StatusTest.test_gh_down`, `StatusTest.test_bad_config` (#106).
      seen red: python -m unittest tests.test_status on main → AssertionError: 2 != 0 (#106)
      broken: status making a second kind of gh call → AssertionError: 6 != 3 (#106)
      broken: a gh failure exiting 0 → AssertionError: 0 != 2 (#106)
      broken: the gh failure not said on stderr → AssertionError: '' != 'cannot read the project: gh issue list exited 1' (#106)
      broken: status skipping the config → AssertionError: "mode: off\nlevel: 1\nhalt: none\nrun's i[154 chars]6)\n" != '' (#106)
      broken: a log that cannot be read passing as empty → AssertionError: Lists differ: ['in progress: none', 'steps: none', 'parks by reason: n[71 chars]86)'] != ['in progress: unknown', 'run log: the run log cannot be read at line 2'] (#106)
      Not replayed, its report holds a pid or a time: status writing a file in the state folder → AssertionError: {'loc[262 chars]pid": 4528, "started": "2026-11-10T00:10:54Z"}\n', 'seen': b''} != {'loc[262 chars]pid": 4528, "started": "2026-11-10T00:10:54Z"}\n'} (#106)
- [x] C07.19 **new** — `on` with two steps, on a fake `claude` of the test's own whose reply carries
      `total_cost_usd` 1.5: the run's issue's first body holds "cost so far: $0.00"; the comment for the
      second step holds "cost so far: $1.50". A cost from a `start` line carrying another issue's
      number is not counted.
      Red today: the body has no "cost so far".
      Test: `RunIssueCostTest.test_first_body`, `RunIssueCostTest.test_second_step_comment`,
      `RunIssueCostTest.test_other_issue_not_counted`.
      Evidence: `RunIssueCostTest.test_first_body`, `RunIssueCostTest.test_second_step_comment`, `RunIssueCostTest.test_other_issue_not_counted` (#104).
      seen red: python -m unittest tests.test_runlog_report on main → AssertionError: Tuples differ: (1, True, 0) != (1, True, 1) (#104)
      broken: open_record not giving open_run the state → AssertionError: Tuples differ: (0, 1, False) != (0, 1, True) (#104)
      broken: begin writing no issue on the start line → AssertionError: Tuples differ: (0, 1, False) != (0, 1, True) (#104)
      broken: issue_cost counting every session, whatever its issue → AssertionError: Tuples differ: ((12, None), False) != ((12, None), True) (#104)
      broken: issue_cost matching start lines with no issue on a new issue → AssertionError: 'cost so far: $0.00' not found in 'step: Step\nsession: s5\ncost so far: $4.00\n\nClose this issue to turn the driver off after this step.\n' (#104)
- [x] C07.20 **new** — H05.2: `--dry-run` at a phase's end, with a closed `parked` issue titled "park:
      the end of Phase 1": "start: <sentence>", exit 0. `gh` failing on that read: nothing on stdout,
      "cannot read the project: gh issue list exited 1" on stderr, exit 2. The rest of C01.7 stands:
      `DryRunTest.test_runs_only_reads` and the other dry-run tests pass unedited.
      Red today: the first prints the park; the second prints the park and exits 1.
      Replaces: C01.7 — was: the only commands the dry run runs are the project's `scripts/spec-drift.py` and `git` reads, with no `gh issue list` at a phase's end.
      Test: `DryRunAnsweredTest.test_answered_starts`, `DryRunAnsweredTest.test_gh_fails`.
      Evidence: `DryRunTest.test_runs_only_reads`, `DryRunAnsweredTest.test_answered_starts`, `DryRunAnsweredTest.test_gh_fails` (#107).
      seen red: python -m unittest tests.test_dry_run_answered on main → AssertionError: 1 != 2 (#107)
      broken: the dry run ignores the closed parks → AssertionError: Tuples differ: (1, 'park: the end of Phase 1: Day 02 starts Phase 2') != (0, 'start: Day 02: read the spec against the code, then the spec-change PR') (#107)
      broken: the dry run ignores a failed read of the closed parks → AssertionError: 1 != 2 (#107)
      broken: every parked dry run reads the closed parks → AssertionError: '' != 'park: a branch of this step exists: day-01/spec-x\n' (#107)
- [x] C07.21 **hold** — What the change must not move, each with the fake `gh` and a log written by
      the test: an open `STOP` issue beats a live session, the halted line and the halt file; a torn
      log with an open `parked` issue of exactly its title gives "wait: parked #n", exit 0, and no
      comment; a crash's session with a closed park of its title and a branch of the step gives
      "park: a branch of this step exists: <name>", no session; with that issue open, "wait: parked
      #n"; a closed park naming another session parks on this one; `halt` with no lock and no live
      session says "halt: set; no driver is running"; #7 by "me" gives "wait: #7"; `open_prs` empty
      records no `pr list --state open` call; `--dry-run` at an unanswered phase's end gives the
      phase's park, exit 1; a dry run not at a phase's end records no `gh` issue call.
      Test: `RecoveryHoldTest.test_stop_beats_a_live_session`,
      `RecoveryHoldTest.test_torn_log_with_its_park_open_waits`,
      `RecoveryHoldTest.test_crash_with_a_branch_parks`, `RecoveryHoldTest.test_crash_park_open_waits`,
      `RecoveryHoldTest.test_other_session_does_not_answer`, `RecoveryHoldTest.test_nothing_to_kill`,
      `RecoveryHoldTest.test_mine_waits`, `RecoveryHoldTest.test_no_pr_read_with_none_open`,
      `RecoveryHoldTest.test_unanswered_phase_end_parks`, `RecoveryHoldTest.test_no_issue_read_elsewhere`.
      Each is broken once in Track 0, but for the two reads that do not exist yet, broken by making
      the read always: `test_no_pr_read_with_none_open` in Track D, `test_no_issue_read_elsewhere` in Track H.
      Evidence: `RecoveryHoldTest.test_stop_beats_a_live_session`, `RecoveryHoldTest.test_torn_log_with_its_park_open_waits`, `RecoveryHoldTest.test_crash_with_a_branch_parks`, `RecoveryHoldTest.test_crash_park_open_waits`, `RecoveryHoldTest.test_other_session_does_not_answer`, `RecoveryHoldTest.test_nothing_to_kill`, `RecoveryHoldTest.test_mine_waits`, `RecoveryHoldTest.test_no_pr_read_with_none_open`, `RecoveryHoldTest.test_unanswered_phase_end_parks`, `RecoveryHoldTest.test_no_issue_read_elsewhere` (#85).
      broken: a torn log overriding its own open park → AssertionError: Tuples differ: (1, 'park: the run log cannot be read at line 2') != (0, 'wait: parked #1') (#85)
      broken: a branch of the step no longer parking → AssertionError: Tuples differ: (1, 'park: the run log names session `00000000-0000-[47 chars]end') != (1, 'park: a branch of this step exists: day-01/spec-x') (#85)
      broken: an open park on a crash's session not waiting → AssertionError: Tuples differ: (1, 'park: the run log names session `0000[57 chars]end') != (0, 'wait: parked #1') (#85)
      broken: halt no longer saying no driver is running → AssertionError: Tuples differ: (0, 'halt: set') != (0, 'halt: set; no driver is running') (#85)
      broken: a phase's end no longer parking → AssertionError: Tuples differ: (0, 'start: Day 02: read the spec against the code, then the spec-change PR') != (1, 'park: the end of Phase 0: Day 02 starts Phase 1') (#85)
      broken: a STOP issue ignored when a run log exists → AssertionError: Tuples differ: (1, 'park: the run log names session `0000[61 chars], '') != (2, '', 'cannot start: halted: the STOP is[46 chars]ear') (#85)
      broken: a torn log parks with its own park open → AssertionError: Tuples differ: (1, 'park: the run log cannot be read at line 2') != (0, 'wait: parked #1') (#95)
      broken: the author read with none open → AssertionError: Lists differ: [['pr', 'list', '--state', 'open', '--auth[45 chars]er']] != [] (#100)
      broken: every dry run reads the closed parks → AssertionError: Lists differ: [['issue', 'list', '--state', 'closed', '-[77 chars]le']] != [] (#107)
      Not replayed, its report holds a random session id: any closed park answering a crash's session → AssertionError: Tuples differ: (1, 'park: the session ended with no pull request and no[56 chars]f`)') != (1, 'park: the run log names session `00000000-0000-4000[43 chars]end') (#85)
      Not replayed, its report holds a random session id: an open pull request no longer waiting → AssertionError: Tuples differ: (1, 'park: the session ended with no pull [70 chars]f`)') != (0, 'wait: #7') (#85)
      Not replayed, its report holds a random session id: any closed park answers a crash → AssertionError: Tuples differ: (1, 'park: the session ended with no pull request and no[56 chars]0`)') != (1, 'park: the run log names session `00000000-0000-4000[43 chars]end') (#95)

## Verify
```bash
python -m unittest discover -s tests
git -c core.safecrlf=false diff --exit-code 4a2c53f -- tests/test_contract.py tests/test_decide.py tests/test_dry_run.py tests/test_steps.py tests/test_tree.py tests/test_config.py tests/test_encoding.py tests/test_failures.py tests/test_halt.py tests/test_halt_report.py tests/test_home.py tests/test_hooks.py tests/test_issues.py tests/test_merge_wait.py tests/test_off.py tests/test_on.py tests/test_once_outcome.py tests/test_once_park_issues.py tests/test_once_parks.py tests/test_once_run.py tests/test_preflight.py tests/test_runlog.py tests/test_runlog_fix.py tests/test_session_bound.py tests/test_wait.py driver/decide.py driver/steps.py driver/settings.py driver/home.py driver/preflight.py driver/config.py hooks rules/session.md
```

## Notes
- Picks up H03.3 (C07.6), H04.3 (C07.8–C07.10), H04.4 (C07.5), H05.2 (C07.17–C07.20) and H05.4
  (C07.15). H06.2 and H06.3 name "Day 7 | Day 8"; this spec gives both to Day 8 (Out of scope), and
  H06.1 stays there. H03.8 still stands (the maintainer's, before Day 8); Day 7's tests do not need it.
- "A lock whose process is gone is taken over only after the table" (`plan.md`, rule 2) is read as:
  nothing starts until the table has been read through by the run that took the lock. Taking it
  after reading the table would let two starts read at once. The maintainer confirmed this reading
  on 2026-11-08, with a torn log whose own park is open waiting.
- Known limits. A lost log is seen only where a stale lock says a driver ran; with the whole state
  folder gone, rows 3 to 6 still stand on git and GitHub. `runlog.fixes` counts 0 on a missing log
  (C06.3); during a run the log exists, its `start` line written first. Row 2 in `on` has no bound
  once the driver that set `--session-minutes` has gone: only a halt or the session's end ends it.
- Row 6 with the project on another branch keeps C01.4's title, "park: the project is on <x>, not
  on main", since `decide()` is unchanged; its body names the branch and the session.
- `github.mine` guards a `gh` login that is not the repository owner (Phase 2's second account). The
  dry run has no such filter, so it can say "wait: #7" where `--once` does not.
- The run's issue's "cost so far" is the run's total; `plan.md`'s "its cost so far" for the step is
  `status`'s `in progress`. A `merged` line comes only from `on`: a `--once`-only trial reads
  "merged pull requests 0".
- Spec-auditor, 2026-11-08, on `main` at `4a2c53f`: 15 findings, all taken up. C07.1's `"pr", "merge"` needs a `Replaces:` at level 2.
- **Defect** D07.1 — found: auditor · cause: spec · made: Day 07 · nine named tests under `new` criteria passed today, so "Track tests seen red" would fail their tracks; moved to C07.21.
- **Defect** D07.2 — found: auditor · cause: spec · made: Day 07 · C07.2 named one test that does not change and missed three that do.
- **Defect** D07.3 — found: auditor · cause: spec · made: Day 07 · C07.14, a `hold`, landed with the change it guards; moved to Track 0.
- **Defect** D07.4 — found: auditor · cause: spec · made: Day 07 · C07.11 changed C03.6 with no `Replaces:` line.
- **Defect** D07.5 — found: auditor · cause: spec · made: Day 07 · C07.20 changed C01.7 with no `Replaces:` line.
- **Defect** D07.6 — found: auditor · cause: spec · made: Day 07 · C07.9's two-second child raced the driver's start-up (median 2.02 s to the first table read).
- **Defect** D07.7 — found: auditor · cause: spec · made: Day 07 · a `pid` line's bad `started` would have crashed the driver, validated less strictly than the lock.
- **Defect** D07.8 — found: auditor · cause: spec · made: Day 07 · no interface carried a takeover's old pid from `take` to `run` and `ready()`.
- **Defect** D07.9 — found: auditor · cause: spec · made: Day 07 · row 4's "Today" cell was false for the real kit, and one C07.12 case could happen only with the fake.
- **Defect** D07.10 — found: auditor · cause: spec · made: Day 07 · `halt` with a lock and a session left its order, POSIX descendants, report and exit unsaid.
- **Defect** D07.11 — found: auditor · cause: spec · made: Day 07 · `status`'s output could not be compared exactly, and `in progress` read "none" during `on`'s waits.
- **Defect** D07.12 — found: auditor · cause: spec · made: Day 07 · "the issue holds the line only" was untrue, and today's `at:` line and the string session "none" were unaccounted for.
- **Defect** D07.13 — found: auditor · cause: spec · made: Day 07 · C07.1 passed on `branch -d`, `--delete`, `shell=True` and `"pr"` not next to its verb.
- **Defect** D07.14 — found: auditor · cause: spec · made: Day 07 · a torn log at row 2 overrode row 3 with a repeat park, unstated and untested.
- **Defect** D07.15 — found: auditor · cause: spec · made: Day 07 · Track F held `status` and the log's report, likely over 400 lines; split into F and G.
- **Defect** D07.16 — found: break on purpose · cause: process · made: Day 07 · #85's first break of `test_stop_beats_a_live_session` gave a find that occurs twice in `driver/once.py`; `break.py` refused it, and it was run again on a line that occurs once.
- **Defect** D07.17 — found: self · cause: implementation · made: Day 07 · #89's first version was 431 changed lines, over the limit of 400: the new test file repeated its fixtures. Shared, it is 395 with no case dropped.
- **Defect** D07.18 — found: Track B · cause: spec · made: Day 07 · In scope's takeover leaves out two Windows behaviours: creating the guard can raise `PermissionError` while another start replaces it, and `os.replace` raises it while another start reads the lock. #89 treats the first as "someone else has it" and tries the second 20 times, then refuses with a line the spec does not give.
- **Defect** D07.19 — found: break on purpose · cause: implementation · made: Day 07 · no break of `test_eight_starts_one_winner` fails on every run (the best, 2 runs of 5), so C07.6's race has no `broken:` line; the line that decides it is held by "the guard opened without O_EXCL" (#89).
- **Defect** D07.20 — found: self · cause: implementation · made: Day 07 · same-as: D07.17 · #95's first version was 418 changed lines; its test scaffolding was trimmed to 398 with no case dropped.
- **Defect** D07.21 — found: review · cause: implementation · made: Day 07 · `test_lock_and_session` did not check the report, so a `halt` that reported twice passed; the check was added in review (#95).
- **Defect** D07.22 — found: self · cause: process · made: Day 07 · a first draft of #95's breaks held one that changed nothing; dropped before the run.
- **Defect** D07.23 — found: Track C · cause: spec · made: Day 07 · C07.9 quotes the halted line with no backticks round the path; `run()` already printed it with them, and #95 keeps that one wording for both.
- **Defect** D07.24 — found: self · cause: process · made: Day 07 · #100's brief said `commit_file` is in `tests/test_tree.py`; it is in `tests/test_dry_run.py`, and the implementer imported it from there.
- **Defect** D07.25 — found: Track D · cause: spec · made: Day 07 · same-as: D07.2 · C07.2's list of earlier tests edited leaves out the fake `gh` in `tests/test_github.py`, which gains a `pr_code` key so that `pr list` can fail alone (C07.12, #100). No test case in that file changes, and it is not in Verify's diff.
- **Defect** D07.26 — found: break on purpose · cause: process · made: Day 07 · same-as: D07.16 · #101's first break, on the `branch:` line, matched `report` too and was refused; it was run again on a line only `park_body` has.
- **Defect** D07.27 — found: self · cause: process · made: Day 07 · `tests/test_issues.py` failed once in three runs of the parallel runner on #101's branch and its output was not kept, so which test failed is not known. It passed in the other two runs and four times alone.
- **Defect** D07.28 — found: review · cause: implementation · made: Day 07 · `issue_cost`'s guard for a run with no issue number had no test, so a new issue could have counted lines with no issue; `test_other_issue_not_counted` now covers it (#104).
- **Defect** D07.29 — found: break on purpose · cause: implementation · made: Day 07 · `test_issue_on_start` raised `KeyError` under its break, an error and not a failed assertion; it now reads the key with `.get` (#104).
- **Defect** D07.30 — found: Track F · cause: spec · made: Day 07 · a pull request on a human-only path that the maintainer merges parks at the path check and writes no `merged` line, so `status` counts one merged pull request too few for each (#104, #106). Not fixed: H07.2.
- **Defect** D07.31 — found: break on purpose · cause: process · made: Day 07 · #106's break "the cost line ignoring merged lines" named `test_no_merged`, which has no `merged` line and passed with the break in; it now names `test_full_report`.
- **Defect** D07.32 — found: break on purpose · cause: implementation · made: Day 07 · same-as: D07.29 · `test_torn_log` raised `ValueError` under its break; it now compares the lines (#106).
- **Defect** D07.33 — found: Track G · cause: spec · made: Day 07 · same-as: D07.15 · Track G alone is 579 changed lines (#106), merged with an `Oversized:` line: `status` prints one block and C07.17 and C07.18 compare it whole.
- **Defect** D07.34 — found: evidence replay · cause: process · made: Day 07 · same-as: D06.18 · two of #85's breaks reported a random session id, so no two runs agree. They stay sentences under C07.21, not in the manifest.
- **Defect** D07.35 — found: evidence replay · cause: process · made: Day 07 · same-as: D06.18 · six of #88's breaks reported a pid. They stay sentences under C07.3 and C07.4; C07.4 keeps one break that replays.
- **Defect** D07.36 — found: evidence replay · cause: process · made: Day 07 · same-as: D06.18 · five of #89's breaks reported a pid, a time or a random session id. They stay sentences under C07.6 and C07.7.
- **Defect** D07.37 — found: evidence replay · cause: process · made: Day 07 · same-as: D06.18 · six of #95's breaks reported a pid, a random session id, a cut whose length follows the pid's digits, or a cut inside a temporary name. They stay sentences; C07.9 keeps no break that replays, only its tests and their seen-red lines.
- **Defect** D07.38 — found: evidence replay · cause: process · made: Day 07 · same-as: D06.18 · four of #106's breaks reported a pid or a time. They stay sentences under C07.17 and C07.18.
- **Defect** D07.39 — found: evidence replay · cause: process · made: Day 07 · three breaks report something else on the close's code, since later tracks changed what they break: #85's "a branch of the step no longer parking" and "a STOP issue ignored when a run log exists", and #89's "the lock kept after the run". The manifest replays each at its track's merge (`at`), so two of C07.21's tests and C07.7's only replaying break are shown to fail on that code, not the close's.
- **Defect** D07.40 — found: evidence replay · cause: process · made: Day 07 · same-as: D06.23 · three reports held Windows-only text: a temporary path (#89), a path separator (#95) and a count in unittest's cut (#106, 148 characters on Windows, 154 on Linux). The lines now record Linux's reports, and a rehearsal on Windows fails those three.
- **Defect** D07.41 — found: close · cause: process · made: Day 07 · #85 recorded its three near misses with a report the replay never gives ("passed with the break in, as a near miss must"); the replay reports the check's last line, and the lines now say "OK".
- The close replayed the tracks' 91 breaks before writing the lines, once on Windows and twice on Linux in Docker: 59 matched on Linux at first. The manifest holds 68; 23 stay sentences ("Not replayed"), a quarter of the day's breaks, each for a report that names a process, a time or a random id. Day 3's lock and halt tests had the same; the day's tests of live processes print pids in what they compare.
- #95's first CI runs ("PR checks", "Dashboard metric tests") failed three attempts, none with a failed test job; a run eleven minutes later on the same commit passed. Not explained.
- Departures, each recorded in its PR. #88: a `pid` line whose `session` is not a string is unreadable too, and a log that cannot be opened gives `live_session` "the run log cannot be read: <why>". #89: the start writes its record into the guard and one `os.replace` makes it the lock; two tests the spec does not name. #95: a torn log with no lock also prints "halt: set; no driver is running"; a failed kill with no driver does not; `test_failed_kill_keeps_the_exit_code` is not in the spec. #106: a `pid` line with no `start` prints "no start line", a null outcome prints "None", and a halt file that cannot be opened prints its reason; none of the three has a test.
- Unverified at the close. The POSIX list of a session's descendants runs only on CI and `taskkill` only on Windows, and no break isolates the POSIX list (#95, as Day 6's). On POSIX a session in the lock's tree can count as alive just after the group kill, so `halt` may print its "killed session" line as well (#95). A lock deleted between the failed create and the first read refuses with "cannot be read" (#89). `on` re-reading a kit that starts failing during a wait has no test (#95). What failed in `tests/test_issues.py` (D07.27): its one timing bound is a `close` that must return within 3 s, a possible cause under load, not a confirmed one.
- **Hand-off** H07.1 → the maintainer: C05.7's and C05.8's recorded breaks ("the session's park opens no issue", "run.json kept after the session") stopped applying to `main` when #72 split `driver/once.py`: their finds are no longer there. Their tests pass and Day 05's replay still runs at its own close, but neither criterion has a planted bug that works on today's code. Correcting `specs/breaks/day-05.json` may turn Day 05's replay stale, so it is not changed here.
- **Hand-off** H07.2 → Day 8: the `merged` line for a pull request on a human-only path that the maintainer merged (D07.30), before the trial's cost per pull request is read from `status`.
- **Hand-off** H07.3 → Day 8: an `end` line whose `session` is a list makes `runlog.failures()` raise `TypeError` (#88, run on that branch); it predates Day 7 and no criterion lists `end` lines.
