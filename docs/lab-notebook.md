# Lab notebook

## Results to date

### Day 01 — the dry run names the next action and starts nothing

Closed 2026-11-06 ([spec](../specs/day-01-dry-run.md)). Five PRs merged: the spec change (#1),
one tooling PR for hand-off H01.7 (#2), and Tracks A, B and C (#3, #4, #5).

- **Delivered:** `python run-steps.py --dry-run --project <path>` reads the kit's next-step
  sentence, the project's tree, branches and remote, and prints one action, `start`, `wait` or
  `park`, with exit codes 0, 0 and 1, or exits 2 when the project cannot be read. Its tests run
  it on a fixture project and record every command it runs: only reads, and nothing in the
  project changes.
- **Every `new` check was seen red.** All 7 criteria were `new`, and CI's "Track tests seen red"
  showed each of their 15 tests failing on the code before its track.
- **Breaks:** 6, across C01.3, C01.5, C01.6 and C01.7, although the spec expected none for an
  all-`new` day. Four of them replay. The close's rehearsals caught the other two (D01.17,
  D01.18). One report held a commit hash that changes on every run. The other held a Windows
  interpreter path that CI's Linux run cannot match, and the local rehearsal passed it. C01.1,
  C01.2 and C01.4 rest on seen-red alone.
- **Defects:** 18. The spec-auditor and plan-auditor found 14 in the spec before any code
  (D01.1–D01.14, all `cause: spec`). Of the other 4, Track A found a spec gap (D01.16), and the
  close's evidence rehearsals found two breaks whose reports could not be replayed (D01.17,
  D01.18). The fourth was a test of the kit's own tooling that read the wrong file (D01.15). It was made
  before any day (`made: none`), so it is an escape from the repository's start, not from a
  day. No escapes from Day 01.
- **Hand-offs:** 9 in all. H01.7 landed in #2. Of the 8 open, Day 2 takes H01.3 and H01.9,
  Day 4 takes H01.5, H01.6 and H01.8, Day 5 takes H01.1, Day 6 takes H01.2, and H01.4 goes to
  the maintainer.

### Day 02 — the preflight names every piece of the kit and the CLI the driver misses

Closed 2026-11-06 ([spec](../specs/day-02-preflight.md)). Three PRs merged: the spec change
(#7) and Tracks A and B (#8, #9).

- **Delivered:** `--dry-run` now prints one stderr line for each piece of the kit a project
  lacks, in the spec's order, and exits 2; an `origin` that `git ls-remote` cannot read is a
  refusal, not a missing `main`. `python run-steps.py preflight --project <path>` adds the
  CLI's checks: version 2.1.170 or newer and nine flags in `--help`, running only `--version`
  and `--help`. On the maintainer's CLI, 2.1.170, it printed "preflight: ok".
- **Every `new` check was seen red.** 5 of the 7 criteria were `new`; their 10 tests failed on
  the code before their track (3 in #8, 7 in #9).
- **Breaks:** 2, one for each `hold` criterion (C02.3, C02.7), both in the manifest. Day 01's
  lesson held: C02.3's check names one test, and its report holds no hash or path.
- **Defects:** 11. The spec-auditor found 6 before any code (D02.4–D02.9), and the session
  drafting the spec made one more (D02.1, a live `claude -p` for $0.11). Review found one test
  red for the wrong reason (D02.10). Three are escapes from Day 01: its closing PR left two
  promised edits undone (D02.2, D02.3, fixed in #7), and `run_drift` decodes
  `scripts/spec-drift.py`'s output as strict UTF-8, which an en dash in the Windows codepage
  breaks (D02.11, found by #9's live run, not fixed).
- **Hand-offs:** 4. H02.1 → Day 3, H02.2 → Day 4, H02.3 → Day 6, and H02.4, D02.11's fix, to
  the maintainer.

### Day 03 — the stop: config, lock, halt, clear and the hooks a session cannot pass

Closed 2026-11-07 ([spec](../specs/day-03-the-stop.md)). Nine PRs merged: the plan change
(#11), three spec changes (#12, #17, #19) and Tracks A to E (#13, #14, #15, #16, #18).

- **Delivered:** `driver.json` names the project when `--project` is not given, and each problem
  with it is one line. `driver.lock` writes the driver's pid and start time, and refuses a second
  start. A lock whose process is gone, or whose pid started after the lock, counts as stale.
  Two hooks: `hooks/halt.py` refuses every tool call while the halt file exists, and
  `hooks/guard.py` refuses a merge, a push to `main` and any touch of the driver's folder.
  `driver.settings` writes both hooks into `<state>/settings.json`. `run-steps.py halt` kills the
  driver's process tree and sets the halt, and `clear` removes it unless the driver still runs.
  A live check (C03.8) showed on Claude Code 2.1.170 that the hooks run beside the project's
  own hooks, refuse while the halt is set, and hold on a resumed session.
- **Every `new` check was seen red.** 7 of the 9 criteria were `new`; their 28 tests failed on
  `main`'s code before their track (6 in #13, 7 in #14, 5 in #15, 10 in #16). C03.8 began as
  `new`, but Tracks C and D had already landed its behaviour, so CI's "Track tests seen red"
  failed #18 until #19 made it `hold` (D03.14).
- **Breaks:** 26 recorded, 14 of them in the manifest: 13 from the tracks, and one the close ran
  itself, because no track owned C03.9's diff break (D03.16). Eleven track breaks reported a pid, a
  lock time, this repository's path or a Windows temp path, which no replay can print again: the
  close's rehearsals, local and on CI's Linux, failed them, and they stay as sentences (D03.17), so
  Day 01's lesson did not hold. C03.8's break
  was run by hand on the maintainer's PC and cannot replay in CI.
- **Defects:** 17. The auditors found 11 before any code: four `plan.md` gaps found by the
  plan-auditor and fixed by #11 (D03.1–D03.4), and seven spec errors found by the spec-auditor
  (D03.6–D03.12). The session found 2 itself (D03.5, D03.13), Track E found 2 (D03.14, and
  D03.15: an 8.3 short temp path made Claude Code deny the write), the close found 1
  (D03.16), and its rehearsal 1 (D03.17). None is an escape from an earlier day.
- **Hand-offs:** 10. H03.1, H03.5, H03.6, H03.7, H03.9 and H03.10 → Day 4, H03.2 → Day 5,
  H03.4 → Day 6, H03.3 → Day 7, and H03.8 to the maintainer.

### Day 04 — one step: `--once` checks, writes the run log, starts one session and finds its pull request

Closed 2026-11-07 ([spec](../specs/day-04-one-step.md)). Eight PRs merged for the day: the spec
change (#21) and Tracks A to G (#22, #23, #24, #25, #26, #28, #29); #27, a `tooling/` branch,
merged between E and F.

- **Delivered:** `python run-steps.py --once` runs one step. It refuses, in order, on the halt
  file, a live lock, a change or move in the driver's own repository, a failed preflight (which
  now lists `--permission-mode`), a next step that parks or waits, an evidence run on `main` that
  has not passed, and a run-log `start` with no `end`. Then it writes the settings, a `start`
  line in `<state>/run.jsonl`, and starts one `claude -p` session in the project's real path, the
  prompt on stdin and the rules file beside it. From the session's JSON and the step's open PRs
  it prints one line (opened, parked, failed), writes the `end` line with the cost and the
  denials, and sets the halt if the session changed the driver's repository. The kit's output is
  read with bad bytes replaced, and the driver writes UTF-8 to a pipe. A halt during `--once`
  kills the session's tree, on a stand-in and, live on Claude Code 2.1.170, a real session.
- **Every `new` check was seen red.** 11 of the 14 criteria were `new`; their 32 tests failed on
  `main`'s code before their track (4 in #22, 9 in #23, 4 in #24, 5 in #25, 4 in #26, 6 in #28).
  C04.12 to C04.14 are `hold`.
- **Breaks:** 26 recorded: 25 by the tracks and C04.12's setpgid break, which no machine of the
  maintainer's could run (D04.14) and the close ran on Linux in Docker. Every entry was replayed
  twice there before the close, the way CI's replay compares them: 18 are in the manifest, two
  of them re-recorded because a later track changed the test (D04.11). Six cannot replay: four
  report a uuid or a sha again, as on Day 3 (D04.6, same as D03.17), and two bite on Windows
  only (D04.7, D04.9). C04.13's named break could never fail its test (D04.13); Track G's
  "/T" break, run by hand, replaced it.
- **Defects:** 15. The spec-auditor found 5 before any code (D04.1–D04.5). The tracks found 5:
  Track B 1 (D04.6), the breaks on purpose 2 (D04.8, D04.10), Track G 2 (D04.13, D04.14). The
  close found 5 (D04.7, D04.9, D04.11, D04.12, D04.15), four of them only by replaying the
  breaks on Linux. None is an escape from an earlier day.
- **Hand-offs:** 4. H04.1 → Day 5, H04.2 → Day 6, H04.3 and H04.4 → Day 7.

### Day 05 — parks: the `parked` issue, the run's issue, the phone's `STOP`, `off`, and a halt's report

Closed 2026-11-07 ([spec](../specs/day-05-parks.md)). Eleven PRs merged for the day: two spec
changes (#32, #40), a specs-map branch (#33) and Tracks A1 to F (#34, #35, #36, #37, #38, #39,
#41, #42).

- **Delivered:** the project's GitHub issues are now the driver's line to the maintainer. Every
  park `--once` prints opens a `parked` issue titled with its line, or waits while one is open;
  closing it is the "go on", and for a phase's end or a step failed twice (read from the run
  log) it is the answer that lets the step start. Each `--once` opens or reuses a "Driver run"
  issue, writes `<state>/run.json` around the session, and closes the issue with the outcome's
  line. An open `STOP` issue by the maintainer's account refuses at the start, and `--poll`
  reads it during a session: the halt file is written, the report posted, then the session's
  tree killed. `halt` from the PC reports the step, session, branch, last commit and
  uncommitted paths on the run's issue; `off` closes the run's issues.
- **Every `new` check was seen red.** 11 of the 12 criteria were `new`; their 47 tests failed on
  `main`'s code before their track (3 in #34, 8 in #35, 6 in #36, 7 in #37, 4 in #38, 7 in #39,
  8 in #41, 4 in #42). Three tests C05.8 first named could not be (D05.1): #40 dropped them.
  C05.12 is `hold`.
- **Breaks:** 15 recorded by the tracks, every one replayed twice on Linux in Docker before the
  close. 14 matched and are in the manifest. One bites on Windows only and held a duration
  (D05.10, same as D04.7). Day 4's lesson held: five breaks whose reports would not have replayed
  (an error, a set, a pid) were caught and redone in their own tracks (D05.4, D05.7–D05.9).
  The Docker run itself first failed the STOP test with no break: nothing reaped the killed
  processes (D05.11).
- **Defects:** 12. CI's "Track tests seen red" found 2 (D05.1, D05.3), the tracks' breaks on
  purpose 5 (D05.4, D05.5, D05.7–D05.9), review 1 (D05.6), Track D 1 (D05.2), the close 3
  (D05.10–D05.12). Two are `made: none` (D05.5, Git Bash; D05.11, Docker). None is an escape
  from an earlier day. Two `gh` behaviours the spec said would be checked before #35 merged
  still are not (D05.12).
- **Hand-offs:** 5. Picked up H01.1, H03.2 and H04.1. H05.1 → Day 6, H05.2 and H05.4 → Day 7,
  H05.3 → Day 8, H05.5 to the maintainer.

### Day 06 — the loop: `on`, the checks waited on, a fix resumed twice at most, the merge waited for, `main` pulled

Closed 2026-11-08 ([spec](../specs/day-06-the-loop.md)). Eleven PRs merged for the day: two spec
changes (#61, #71) and Tracks A to H (#62, #64, #66, #67, #70, #72, #73, #74, #75; F is split).

- **Delivered:** `on` runs the day loop across steps under one lock and one run's issue: the tree
  brought to `main`, required checks waited on, a red PR resumed twice at most, the path check, the
  merge and evidence waited for. `STOP`, the halt file and a closed run's issue are read during
  every wait. `live-check` records passed versions, and `--session-minutes` bounds a session.
- **Every `new` check was seen red.** 12 of the 13 criteria were `new`, each failing on `main`'s
  code before its track. #62's first push had one test that passed there, and CI's "Track tests
  seen red" failed it (D06.6). C06.12 is `hold`.
- **Breaks:** 75 recorded by the tracks; the close's first Linux replay matched 66. Five reports held
  Windows-only text and now record CI's, two finds were made unique, two reports held a random
  name and stay sentences. The manifest holds 73.
- **Defects:** 29. The evidence replay found 7 (D06.23–D06.29), the tracks 7, the main session
  or implementer 6, breaks on purpose 3, the close 2, the dashboard 2, seen red 1, and the
  auditors 1. Two are escapes (D06.1 from Day 04, D06.3 from Day 05), two `made: none` (D06.2, D06.4).
- **Not proven against the real `gh`:** from its source, not a run, `--required --json` exits 1
  with no required checks, so C06.4's park there is reached only by the fake (D06.13, H06.3).
- **Hand-offs:** 3. Picked up H01.2, H01.5, H02.3, H03.4, H04.2 and H05.1. H06.1 → Day 8, H06.2
  and H06.3 → Day 7 or Day 8.

### Day 07 — recovery: every start reads the table; `status` and the run log's report

Closed 2026-11-10 ([spec](../specs/day-07-recovery.md)). Ten PRs merged for the day: the spec
change (#79), Track 0 (#85) and Tracks A to H (#88, #89, #95, #100, #101, #104, #106, #107).

- **Delivered:** every start reads "Recovery"'s table in order. A live session is waited on, a
  stale lock is taken over by one start of several, a lost or torn log parks, a crash's session is
  answered by closing its park, and `halt` kills a session with no driver. Only the maintainer's
  own pull requests hold a step. A park's issue names the session, branch, commit and paths; the
  log counts parks and merges; `status` prints the run and its cost and writes nothing.
- **Every `new` check was seen red.** 17 of the 21 criteria were `new`, each failing on `main`'s
  code before its track; the four `hold` criteria landed in Track 0 and were broken there, but for
  two reads that did not exist yet (Tracks D and H). The suite is 301 tests, 233 before the day.
- **Breaks:** 91 recorded by the tracks. Replayed on Linux before the close, 59 matched. 23 report
  a pid, a time or a random session id and stay sentences (D07.34 to D07.38), a quarter of the
  day's breaks: C07.9 keeps none that replays. Three record Linux's report, three replay at their
  track's merge because later tracks changed the code, three near misses record "OK". The
  manifest holds 68.
- **Defects:** 41. The spec-auditor found 15 before any code, the evidence replay 7, breaks on
  purpose 6, the tracks 5, the main session or implementer 5, review 2, the close 1. None is an
  escape from an earlier day. Two tracks went over 400 lines at first and were trimmed (D07.17,
  D07.20); Track G merged at 579 with an `Oversized:` line (D07.33).
- **Not proven beyond the fake `gh` and one machine at a time:** the POSIX list of a session's
  descendants runs only on CI and `taskkill` only on Windows, and one failure of
  `tests/test_issues.py` was not kept (D07.27).
- **Hand-offs:** 3. Picked up H03.3, H04.3, H04.4, H05.2 and H05.4; H06.2 and H06.3 go to Day 8.
  H07.1 → the maintainer (C05.7's and C05.8's breaks no longer apply to `main`), H07.2 and H07.3
  → Day 8.

### Day 08 — the trial: one day of `bearing` at level 1, what parked, what was refused, what it cost

- **What it does now:** the driver ran `bearing`'s Day 13 with the maintainer only merging and answering
  parks, and that day closed with its evidence replay green (run 42932015269). The run log names the tools
  refused, every pull request waited on, and whether one changed before its merge; `status` prints the
  refusals by tool and the count Level 2 is entered on. The record is [`docs/trial/day-08.md`](trial/day-08.md).
- **The trial:** three pull requests merged unchanged (#90, #91, #96), two parks, one refusal (a hook's, from
  a subagent), and 3 of 15 toward Level 2. $2.78 by the sessions' own figures, $0.93 per merged pull request;
  $1.07 and 14.0 replies by list price, beside the baseline's $1.86 and 34.4. One small day of three pull
  requests, so a small sample, and the two dollar figures are not reconciled. From the phone, a `STOP` halted
  the driver in 30 s, and a closed park was followed by the next start in 105 s.
- **Not proven:** C08.15. The trial did not meet the usage limit, so Track F did not open (H08.1). C08.11 to
  C08.14 read the committed record, not the trial's repository.
- **Every `new` check was seen red.** 16 of the 17 criteria are ticked, 10 `new` and 6 `hold`. The suite is
  340 tests, 301 before the day.
- **Breaks:** 30 recorded, all in the manifest. The close's rehearsal refused one, recorded before Track C1
  changed its line, and it was re-run with the same report (D08.82). CI's Linux replay differed from Windows on
  another, whose report the spec now holds as Linux prints it (D08.83).
- **Defects:** 85. The spec-auditor found 66 before any code, in four rounds, breaks on purpose 4, the tracks
  7, self 4, review 1, the close 1, the evidence replay 2. Causes: spec 63, process 18, implementation 4.
  Two escapes, D08.76 from Day 04 and D08.81 from Day 05, both tests that fail on and off with the cause not
  found.
- **Hand-offs:** 5, all to the maintainer. Picked up H05.3, H06.2, H06.3, H07.2 and H07.3; H06.1 goes on as
  H08.1. Day 8 is a stopping point: nothing of Phase 2 is specified until the stop's plan-auditor has read the
  whole plan.

### Day 09 — Phase 1's leftovers: the usage limit waited out, refusals logged by the hooks, the halt race, the level 2 sentence tied

- **What it does now:** a session stopped by the usage limit is waited out and resumed once, and parks if the
  limit stops it again or resets more than `--limit-hours` away; the halt file is read during the wait. The
  driver's own hooks write each refusal to `<state>/refusals/hooks.jsonl`, and `status` and
  `scripts/driver-runs.py` count the ones a killed session never reported. A halt that lands after the session
  ended writes no `end` line and opens no park. A test ties `driver/loop.py`'s park sentence to the level 2
  count.
- **Not run for real:** the usage limit. Its shape comes from five interactive transcripts; no headless session
  has met it, and the fakes stand in for the resume (H09.2, Day 13). The hooks' log was checked headless once
  on 2.1.322: the hook's `session_id` is the driver's `--session-id`, and its refusal reaches
  `permission_denials` (#142).
- **Every `new` check was seen red.** 14 of 14 criteria are ticked, 11 `new` and 3 `hold`. The suite is
  358 tests, 341 before the day.
- **Breaks:** 23 recorded, all in the manifest, each copied from its track PR's `manifest:` line.
- **Flaky tests (D08.76, D08.81):** `test_once_halt.py` and `test_once_stop.py` each passed 10 runs of 10 at
  the close. `test_once_stop.py`'s cause is still not found.
- **Defects:** 32. The auditors found 19 before any code, which the spec-change PR fixed but did not write down;
  the close wrote them (D09.21). The spec-change PR 1, breaks on purpose 4, the tracks 3, seen red 1, self 1,
  review 1, the close 1. Causes: spec 21, implementation 5, process 4, environment 2. No escapes.
- **Hand-offs:** 3: H09.1 to Day 10 (the refusals folder writable by the second account), H09.2 to Day 13 (a
  headless usage limit recorded), H09.3 to the maintainer (a fix's resume meeting the limit, and `STOP` during
  the wait). Picked up H08.1 to H08.5.

### Day 10 — The session's container: the image, sessions started and killed in it, its reach checked before each session, the count from it, the bypass line

- **What it does now:** with `container_image` and `container_secrets` in its config, the driver runs each
  session as `docker run` of `docker/Dockerfile`'s image, with six `--mount`s and nothing else of the PC's:
  the project read-write, the driver's hooks and rules read-only, the state folder read-only but for the
  refusals and Claude Code's own folders. Before each session it checks Docker, the image, the secrets file
  and the image's Claude Code, then runs `hooks/probe.py` in the container and refuses to start if a folder
  it must not write is writable, or one it must write is not. `docker kill` ends a session past its bound,
  on STOP and on `halt`; Recovery waits on a container still running. `status` counts level 2 from
  container sessions only, so the Day 8 trial's 3 now count 0. `setup-check.py` says whether anyone may
  bypass `main`'s rules. Without the two keys nothing changes, and no Docker runs.
- **Run for real:** one step of bearing's Day 14, from the container, opened bearing #101, its head commit
  authored by the image's `GIT_NAME`, the PC's checkout left clean (`docs/trial/day-10.md`, #159).
- **Every `new` check was seen red.** 32 of 32 criteria are ticked, 23 `new` and 9 `hold`. Two `new`
  criteria were tagged wrong and changed to `hold` when "Track tests seen red" failed their tracks (#154,
  #156). The suite is 390 tests (6 skipped: the live tests without an image), 358 before the day.
- **Breaks:** 42 in the manifest, 41 copied from the PRs' `manifest:` lines and one made at the close:
  C10.29, a `hold`, had not been broken (D10.21). The live breaks of C10.7 and C10.14 are written as
  sentences: CI has no image.
- **Flaky test:** `UsageLimitTest.test_far_reset_parks` failed once each in five tracks' full runs
  (D10.18, an escape from Day 09); 50 of 50 under `--repeat 10` at the close.
- **Defects:** 26. The auditors 10, the dashboard 1, seen red 3, breaks on purpose 5, review 1, the tracks
  2, self 2, the close 1, the close's rehearsal 1. Causes: spec 15, implementation 6, process 4, environment 1. Escapes: 2 from
  Day 09 (D10.1, D10.18).
- **Hand-offs:** 2: H10.1 to Day 12 (`live-check` run in the image), H10.2 to Day 13 (the container's
  transcripts counted). Picked up H09.1 and D09.21's bypass line.

### Day 11 — Where am I, while a session runs: the stream, the events, the heartbeat, `status --watch`, the estimate, the comments

- **What it does now:** the driver runs `claude -p` with `--output-format stream-json --verbose` and reads
  the session's stdout line by line on a reader thread. Each event's time and kind go to
  `<state>/sessions/<session>.events.jsonl`, and the outcome is read from the last `result` event; a line that
  does not parse is counted, not fatal. At the start and at each poll the driver rewrites
  `<state>/heartbeat.json`. `status` prints a live session's running time, with an estimate when three or
  more earlier sessions of its kind ended (their median), its last event and how long ago, and its tokens
  so far; `status --watch` prints again at each poll until the session ends. On the run's issue, one comment
  per session is edited in place at each poll, and one more says so when no event has come for
  `stale_minutes` (10 by default): a stale session is reported, not killed. A failed comment changes nothing.
- **Run for real:** two tiny live sessions, no step: one on the PC before Track A (#170) and one in the image
  (#178). Each printed `system init`, a reply, a `rate_limit_event` and a `result` line; without `--verbose`
  the CLI refuses. Two `gh` writes were tried on a scratch issue before Track E1 (#174, closed).
- **Every `new` check was seen red.** 23 of 23 criteria are ticked, 15 `new` and 8 `hold`. One `new`
  criterion named a test Track E1 had already made pass; "Track tests seen red" failed Track E2 on it, and
  spec change #177 moved that case to a `hold`, C11.23 (D11.19). The suite is 413 tests (7 skipped: the live
  tests without an image or a CLI), 390 before the day.
- **Breaks:** 27 in the manifest. 24 are copied from the PRs' `manifest:` lines; #175's is left out, since
  #176 rewrote its find and recorded it again. Three were made at the close: Day 6's and Day 10's bound
  breaks, whose finds Track B rewrote without recording them again (D11.30). C11.21's live break is written
  `broken: none`, with why: CI has no image.
- **Flaky tests:** `UsageLimitTest.test_far_reset_parks` again (D11.29, an escape from Day 09) and Track E1's
  `PhoneTest.test_heartbeat_comment_edited_in_place` (D11.25), both under load: at the close, under
  `--repeat 10` (ten copies at once), each failed 8 of 10, where Day 10's close saw `test_far_reset_parks`
  pass 50 of 50. Track C's `HeartbeatTest.test_heartbeat_beats_through_a_quiet_tool` failed once in the
  close's full run (D11.32).
- **Defects:** 33. The auditors 18, seen red 1, breaks on purpose 3, self 4, the tracks 2, a later track's
  review 1, the close 3, the close's rehearsal 1. Causes: spec 21, implementation 5, process 6, environment 1.
  Escapes: 1 from Day 09
  (D11.29).
- **Hand-offs:** none made, none picked up: H10.1, H09.2 and H10.2 went to Days 13 and 14 by #168. Left to
  the maintainer: `plan.md`'s and P60's wording of the session's output (the spec's Notes), and D11.25.

### Day 12 — The reviewer: its brief, its read-only settings, the before-and-after comparison, its verdict on the PR, a blocker's fix

- **What it does now:** with `"review": true` in `driver.json`, once a step's pull request has green
  checks the driver starts a second `claude -p` session, never the step's: `--agents <state>/agents.json
  --agent reviewer`, the brief `rules/reviewer.md`, with its own settings, in which `hooks/readonly.py`
  refuses a git command that changes a repository and a `gh` command that is not a read. Before and after
  it, the driver reads HEAD, the refs, the stash's top and `git status`; any difference parks the run. The
  reviewer's `found:` lines and its `REVIEW: blocker` or `REVIEW: none` go in one comment on the pull
  request, and a `review` line in the run log. A blocker resumes the step's own session, within the two
  fixes a red check also spends; a blocker left after both parks, and so does a reply the driver cannot
  read. Without `review`, nothing changes. It runs in the image too, as `driver-<uuid>`.
- **Run for real:** a `--agents` file with `--agent probe` replied ORCHID on the PC's 2.1.322 before Track
  E1 (#214); `gh pr comment --body-file -` was tried on #208. Track F's live test ran on the PC and in the
  image (#220) and again at the close: the agent from a file replies ORCHID, a commit asked for is refused by
  the read-only hook and leaves HEAD as it was, and the image's run leaves `git status` clean. `review` is
  still not set in the driver's own `driver.json` (a maintainer action).
- **Every `new` check was seen red.** 23 of 23 criteria are ticked, 20 `new` and 3 `hold`. One `new`
  criterion's first half passed on `main`, where no reviewer runs at all; "Track tests seen red" failed
  Track E1 on it, and spec change #215 made that half C12.23, a `hold` (D12.25). The suite is 449 tests,
  413 at Day 11's close.
- **Breaks:** 26 in the manifest, all recorded by the tracks (`break.py --record`); `break-lines.py`
  finds the spec's 26 `broken:` lines agree with it. Five are earlier Days' breaks whose finds Track E0
  moved into `once.command` and `loop.fix`, recorded again under their names. C12.21's live break is
  `broken: none`, with why: it skips where it is replayed.
- **Flaky tests:** the three Day 11 left, again under load, none fixed: `test_far_reset_parks` (D12.34),
  `test_heartbeat_comment_edited_in_place` (D12.35, in three PRs and once in CI) and
  `test_heartbeat_beats_through_a_quiet_tool` (D12.36).
- **Defects:** 36. The auditor 24, seen red 1, breaks on purpose 3, self 2, the tracks 6. Causes: spec 25,
  implementation 6, process 4, environment 1. Escapes: 4, from Day 06 (D12.28), Day 09 (D12.34) and Day
  11 (D12.35, D12.36).
- **Hand-offs:** picked up H10.1 and passed it to Day 13 as H12.1; made H12.2 (Day 13: does the Level 2
  count end on the reviewer's park) and H12.3 (Day 14: the reviewer as its own kind in `status`).
- **While the Day was open,** five area PRs merged (#206, #210, #216, #217, #219); the last of them is
  the rule that such a PR opens only to unblock the Day's next step.

### Day 13 — The level 2 merge: the switch and its three conditions, the path check, the driver's own repository, `gh pr merge --match-head-commit`

- **What it does now:** with `"level": 2` in `driver.json` (any other value than 1 or 2 is refused), `on`
  starts only when `review` is on, the container keys are set, the run log counts 15 container merges in a
  row, and `main` requires a pull request and its checks with no bypass (`github.protection`, read once at
  the start from the classic protection and the rules). At each merge, after the path check (a pull request
  touching `plan.md`, a human-only file or saying `Oversized:` still parks), the driver reads the count again
  (below 15 the pull request waits for the maintainer, with a `level` line saying why), checks its own folder
  is clean and at the commit it started from (else it halts), and merges with `gh pr merge --merge
  --match-head-commit` on the head the reviewer saw with no blocker; a moved head, or no clean review,
  parks. A failed merge is read again from GitHub: merged after all goes on, else it parks. The run log's
  `merged` line says `"by": "driver"`. The count now ends on the reviewer's "still has a blocker … after two
  fixes" park. `--once` refuses the driver's own repository, by folder or by `origin` URL. The session
  rules gain one line: install the project as its CI does before running its tests. At level 1 nothing
  changes.
- **Run for real:** the maintainer's probe before Track E1, on a scratch repository: `--match-head-commit`
  with a wrong sha is refused ("Head branch was modified"), with the head's sha it merges (#255).
  `setup-check.py` on bearing before Track D: no bypass and the evidence check turned on by the maintainer;
  "A track's breaks replay" is the only check left, which bearing has no workflow for (#254). The driver
  has not merged a real pull request yet, and a merge on a red required check is not probed: the Day 14
  trial (H13.2).
- **Every `new` check was seen red.** 20 of 20 criteria are ticked, 17 `new` and 3 `hold`. Five of
  Track E1's seen-red lines were a retyped summary and were re-run at the close, one per test, on E1's base.
  The suite is 606 tests, 449 at Day 12's close.
- **Breaks:** 32 in the manifest: 26 recorded by the tracks, and six for C13.1 to C13.5 at the close,
  after its rehearsal failed the five for having none (D13.68); `break-lines.py` finds the spec's 32
  `broken:` lines agree with it. Track A's docstring edit moved Day
  08's C08.2 report on Linux, retaken (D13.36); Track C re-recorded Day 09's status break; Track F pinned
  C12.24's `driver/decide.py` break at `78f430d`.
- **The track-reviewer's first Day:** it read every brief and every diff, and found 30 of the 68 defects,
  before the implementer started or before the PR: wrong expected counts, seen-red `--expect` lines that
  could not match, breaks that reached the wrong check, and six cases no criterion named (D13.38,
  D13.43, D13.48, D13.54, D13.55, D13.62). It cost $12.58, two thirds of the main sessions' $18.76.
- **Defects:** 68. The auditor 28, the track-reviewer 30, review 3, the tracks 4, the spec-change PR 1,
  the close 1, the rehearsal 1. Causes: spec 34, process 30, implementation 4. Escapes: 2, from Day 05 (D13.66, the
  `OnceStopTest` load flake) and Day 08 (D13.36).
- **Hand-offs:** answered H12.1 (no `live-check` in the image), H12.2 (the count ends on the reviewer's
  park after two fixes) and H12.5 (C13.16); passed H09.2, H10.2 and H12.3 to Day 14; made H13.1 (the
  install seen in a trial session) and H13.2 (the first real level 2 merge).
- **While the Day was open,** one area PR merged (#251, the dashboard's gene bands), which unblocked no
  step: against the rule, recorded here.

### Day 14 — The level 2 trial's record: the count run to 15 of 15, one bearing day at level 2, the reviewer's row and cost, `--container`, the picker removed

- **What it does now:** `token-usage.py --container <d>` reads the driver container's transcripts
  (`<d>/-work/` and its subagents) for `--compare` and `--tools`, and refuses without one of them.
  `status` names a review session's row "review of #n" and gives the reviewer's cost on its own
  line after `cost:`, inside the total. The session rules gain a line: a step that opened its pull
  request ends without `PARK:`, whatever the project's `CLAUDE.md` says. The dashboard's leftover
  picker is gone, page and build halves; the file map keeps `howBlob`. The trial's record is
  `docs/trial/day-14.md`, with copies of the run log, the switch log, the hook log and one
  session's install, and a test that reads only them.
- **Run for real:** the count run on bearing, level 1, in the container, on 2026-11-21. It stood
  at 1 of 15 when two step sessions opened their pull request and then parked, as bearing's
  `CLAUDE.md` says after any pull request (D14.34); Track E's line ended that, and the count
  reached 15 of 15 at bearing #151. The level 2 day was bearing's Day 22 from its Track A: two step
  sessions, two reviews with 0 blockers. The maintainer merged #153 by hand a second after its
  review; the driver merged #154, the day's close, on the head the reviewer saw, and its evidence
  run 44965577837 concluded `success`; then it parked at the end of bearing's Phase 14. The
  red-check probe: GitHub refused `--match-head-commit` with the right sha on a red required check
  (exit 1). From the run log: the count run alone $23.92 over 15 merges, $1.59 each; level 2 alone
  $2.77 over 2, $1.38 each, against the baseline's $1.86; the reviewer 2 sessions, $0.61.
  `--compare` on the container's sessions: 15.9 replies per merged pull request before
  2026-11-22, 26.5 on it, against 34.4. No session met the usage limit; bearing's Day 22 had no
  escape.
- **Every `new` check was seen red.** 19 of 19 criteria are ticked, 15 `new` and 4 `hold`.
  C14.2's two tests were re-run at the close on #264's merge, since #265's line was the module's.
- **Breaks:** 24 in the manifest, all recorded by the spec-change PRs and the tracks;
  `break-lines.py` finds the spec's 24 `broken:` lines agree with it. Track E retired Day 13's
  install-line break, whose test it replaced.
- **Five spec changes after the first.** Four (#264, #267, #270, #272) came each before the track
  it unblocked: a test CI's seen-red check could not see (twice), the park after a pull request
  the count run met, and the install and the level 2 day as they ran. The fifth (#275) came after
  the closing PR was open: CI's rehearsal of the close failed C14.4 on Linux, where the max-path
  test's folder came to 250 characters in the rehearsal's short worktree, not past 260; the local
  rehearsal, on longer paths, had passed (D14.70). The test now pads its folder past 260 wherever
  the checkout is, and the closing PR was rebased on it.
- **Defects:** 70. The auditor 34, the track-reviewer 25, review 2, the tracks 4, self 1, break on
  purpose 1, the rehearsal 2, a review of the trial 1. Causes: spec 42, process 23, implementation 4, environment 1.
  Escapes: 2, from Day 04 (D14.34, the park after a pull request) and Day 13 (D14.68, `status`'s
  "level: 1").
- **Hand-offs:** answered H09.2 (not met), H10.2 (C14.2), H12.3 (C14.5, C14.6), H13.1 (the install
  seen in a level 2 session) and H13.2 (the first merge, the probe); made H14.1 to H14.3, all to
  the maintainer.
- **While the Day was open,** no area PR merged.

## Phase reads

**Read at the end of Phase 0.** Phase 0 set out to show that the driver can read a project and
name its next action without starting anything (`plan.md`, "Phase 0"). Days 1 and 2 closed on
2026-11-06, in ten merged PRs (#1 to #10). `--dry-run` prints one action, `start`, `wait` or
`park`, from the kit's next-step sentence and the project's git state. Its tests record every
command it runs, and every one is a read. `preflight` names each piece of the kit a project
lacks, and checks the CLI's version and nine flags. The plan-auditor, run on `main` after #10,
found the Done-when met.

The auditors did most of the finding. 20 of the phase's 29 defects were found in the specs
before any code, and 21 of the 29 have `cause: spec`. All 14 criteria were ticked. The 12 `new`
ones had their 25 tests seen red, and the 2 `hold` ones were each broken once. Of the 8 breaks
recorded, 6 replay. The other two printed a commit hash and a Windows path, and only the close's
rehearsals caught them. Three defects made on Day 1 escaped into Day 2: two edits Day 1's close
promised and left undone, and a strict UTF-8 read of the kit's output that an en dash breaks on
Windows (D02.2, D02.3, D02.11). The 8 merged PRs the two closes counted cost $13.48, $1.69 each
beside the kit's $1.86, with 32.3 replies each beside 34.4.

Still open: the tests ran the dry run on fixture projects. The one live run (#9) found D02.11,
which the fixtures missed because their script prints nothing; Day 4 fixed it. Of Phase 0's 13
hand-offs, two wait for Day 6: H01.2, a clean branch brought to `main`, and H02.3, `on` running
the preflight first. H01.4 stays with the maintainer: writing a day spec is a park, not a step
the driver starts.

What Phase 1 had to know: its day titles were too thin to write specs from. No day owned the
lock, the config, the driver's check of its own repository, or the run's issue. `auto` came only
from the maintainer's own settings. Plan change #11 and Days 3 to 5 took these up. A fixture that
prints nothing cannot catch an encoding fault, and a break whose report holds a hash or a path
cannot replay.

## What is being measured

| Question | Evidence it will be judged on | Day 01 | Day 02 | Day 03 | Day 04 | Day 05 | Day 06 | Day 07 | Day 08 | Day 09 | Day 10 | Day 11 | Day 12 | Day 13 | Day 14 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Cost per merged PR, main sessions, beside the kit's baseline of $1.86 (`plan.md`, "What it is judged against") | `docs/dashboard/token-usage.json` | $5.51 over 5 merged PRs on 2026-11-06, $1.10 each ($2.45 attributed to Day 1 by branch, $3.06 on `main`). The implementer added $0.07. The close's own session is counted only up to its `token-usage.py` run | $7.97 over 3 merged PRs since Day 01's count, $2.66 each. It includes the tail of Day 01's close after its count, and this close only up to its `token-usage.py` run. The implementer added $0.05; the spec-auditor $1.51 | $15.07 over 9 merged PRs since Day 02's count (#11 to #19), $1.67 each. It includes the tail of Day 02's close after its count, and this close only up to its `token-usage.py` run. The implementer added $0.11; the spec-auditor $2.04; the plan-auditor $1.45 | $21.59 over 10 merged PRs since Day 03's count (#20 to #29), $2.16 each. It includes the tail of Day 03's close after its count, and this close only up to its `token-usage.py` run. The implementer added $0.61; the spec-auditor $2.20 | $25.45 over 13 merged PRs since Day 04's count (#30 to #42), $1.96 each. It includes the tail of Day 04's close after its count, and this close only up to its `token-usage.py` run. The implementer added $0.26; the spec-auditor $3.04; the defect-rater $0.20 (Day 04's and this close's) | $83.42 over 32 merged PRs since Day 05's count (#44 to #75, 11 of them Day 06's), $2.61 each. It includes the tail of Day 05's close after its count, and this close only up to its `token-usage.py` run. The implementer added $1.20; the plan-auditor $1.55; the spec-auditor $0.95; the defect-rater $0.06 | $43.67 over 10 merged PRs, Day 07's own (#79 to #107), $4.37 each: the sessions on the day's own branches, which is how the file gives a Day its cost since #109. Not comparable with the columns before by subtraction: #105 and #108 changed what is counted, and the 22 other PRs merged since Day 06's close are left out. This close is counted only up to its `token-usage.py` run. The implementer added $0.96; the defect-rater $0.07; the spec-auditor's run is not given to a Day in the file | $22.47 over 7 merged PRs, Day 08's own (#111 to #129), $3.21 each, counted as Day 07's is. This close is counted only up to its `token-usage.py` run. The spec-auditor added $9.97; the implementer $0.27; the defect-rater $0.68. The trial's own: $1.07 per merged PR, `bearing`'s three (`docs/trial/day-08.md`) | $7.66 over 6 merged PRs (#140 to #145), $1.28 each: the sessions started on a Day 09 branch, main $7.43 and the implementer $0.23. The spec-change session and its auditors (plan-auditor $7.53, spec-auditor $2.28) started on `main` and sit in 2026-11-11's rows with no Day. This close is counted only up to its `publish-counts.py` run | $22.07 over 12 merged PRs, Day 10's own (#148 to #159), $1.84 each, counted as Day 07's is. This close is counted only up to its `publish-counts.py` run. The spec-auditor added $3.23; the implementer $0.81. The trial's own: $0.56 for bearing #101's one session, the `end` line's `cost_usd` (`docs/trial/day-10.md`) | $13.46 over 9 merged PRs, Day 11's own (#169 to #178), $1.50 each, counted as Day 07's is. This close is counted only up to its `publish-counts.py` run. The implementer added $0.28. The spec-change session and its auditors (plan-auditor $3.51, spec-auditor $5.18) started on `main` and sit in 2026-11-13's rows with no Day | $22.39 over 10 merged PRs, Day 12's own (#203 to #220), $2.24 each, counted as Day 07's is. This close is counted only up to its `publish-counts.py` run. The implementer added $0.65. The spec-auditor ($3.86) and an instrument-auditor run the maintainer asked for ($3.43) carry Day 12 | $18.76 over 9 merged PRs, Day 13's own (#248 to #257 but #251), $2.08 each, the rows the count tags Day 13. This close is counted only up to its `publish-counts.py` run. The track-reviewer added $12.58 in its first Day, the spec-auditor $5.78, the implementer $0.24 | $28.73 over 13 merged PRs, Day 14's own (#262 to #273, and #275), $2.21 each, the rows the count tags Day 14. This close is counted only up to its last `publish-counts.py` run, after its rebase on #275. The spec-auditor added $17.09, the track-reviewer $8.94, the defect-rater $0.36, the implementer $0.14. The trial's own sessions ran on bearing, in the container: $26.68 over 17 merges in its run log (the record's Cost) |
| Replies per merged PR, main sessions, beside 34.4 | `docs/dashboard/token-usage.json` | 118 replies over 5 PRs, 23.6 each | 140 replies over 3 PRs, 46.7 each | 281 replies over 9 PRs, 31.2 each | 363 replies over 10 PRs, 36.3 each | 432 replies over 13 PRs, 33.2 each | 1,311 replies over 32 PRs, 41.0 each | 414 replies over 10 PRs, Day 07's own, 41.4 each, counted as the cost is | 252 replies over 7 PRs, Day 08's own, 36.0 each. The trial's own: 14.0 | 151 replies over 6 PRs, Day 09's own, 25.2 each | 412 replies over 12 PRs, Day 10's own, 34.3 each | 257 replies over 9 PRs, Day 11's own, 28.6 each | 444 replies over 10 PRs, Day 12's own, 44.4 each | 349 replies over 9 PRs, Day 13's own, 38.8 each | 481 replies over 13 PRs, Day 14's own, 37.0 each; the trial's container sessions 15.9 before 2026-11-22 and 26.5 on it |
| Escapes per day | the Notes' Defect lines with `made:` an earlier day | 0 from a day; 1 from the repository's start (D01.15) | 3 from Day 01 (D02.2, D02.3, D02.11) | 0 from a day; 5 `made: none` (D03.1–D03.4 in `plan.md`, D03.5 in #11's description) | 0 from a day; 1 `made: none` (D04.14, the maintainer's machine) | 0 from a day; 2 `made: none` (D05.5, Git Bash; D05.11, Docker) | 2 (D06.1 from Day 04, D06.3 from Day 05); 2 `made: none` (D06.2, D06.4) | 0: all 41 are `made: Day 07` | 2: D08.76 from Day 04, D08.81 from Day 05; 81 of the 85 are `made: Day 08`, 2 `made: none` | 0: 30 of the 32 are `made: Day 09`, 2 `made: none` (D09.1, D09.32) | 2 from Day 09 (D10.1, D10.18); 23 of the 26 are `made: Day 10`, 1 `made: none` (D10.17) | 1 from Day 09 (D11.29); 31 of the 33 are `made: Day 11`, 1 `made: none` (D11.22) | 4: 1 from Day 06 (D12.28), 1 from Day 09 (D12.34), 2 from Day 11 (D12.35, D12.36); 30 of the 36 are `made: Day 12`, 2 `made: none` (D12.29, D12.30) | 2: 1 from Day 05 (D13.66), 1 from Day 08 (D13.36); 66 of the 68 are `made: Day 13` | 2: 1 from Day 04 (D14.34), 1 from Day 13 (D14.68); D14.56 is `made: none`; 67 of the 70 are `made: Day 14`. bearing's level 2 day: 0 |
| Parks by reason | the driver's run log | none yet: the driver does not run steps until Phase 1 | none yet | none yet | none yet: `--once` has run only on fake projects and one live scratch project | none yet: `--once` has run only on fake projects | none yet: `on` has run only on fake projects | none yet: `on` and `status` have run only on fake projects | 2, in the trial: "the run log names session … with no end" after the `STOP`, and "every day is done" | none: the driver ran on no project during Day 9, only on the tests' fakes | 1, "every day is done", on bearing before its Day 14 was added; then one step in the container, which opened bearing #101 (#159) | none: the driver ran on no project during Day 11, only on the tests' fakes and two live sessions with no step | none: the driver ran on no project during Day 12, only on the tests' fakes and the live reviewer tests, with no step | none: the driver ran on no project during Day 13, only on the tests' fakes; `driver-runs.json` counts level 2 at 0 of 15 | 9, in the trial: 4 phase ends (bearing's Phases 11 to 14), 2 "the session parked" after its pull request (D14.34), 2 "the session ended with no pull request and no PARK line" (its pull request merged by hand first), 1 "the project's tree is not clean" |
| Hook refusals | `docs/dashboard/refusals.json` | 1, read-guard, 2026-11-06 | 2 more, read-guard, 2026-11-06 (3 in all) | 1 more, read-guard, 2026-11-06 (4 in all) | 8 more, 2026-11-07: 7 read-guard, 1 auditor-guard (12 in all) | 8 more, 2026-11-07: 5 read-guard, 3 auditor-guard (20 in all) | 13 more, 2026-11-07 to 2026-11-08: 11 read-guard, 1 auditor-guard, 1 step-guard (33 in all) | 27 more, 2026-11-08 to 2026-11-10: 23 read-guard, 4 step-guard (60 in all) | 14 more, up to 2026-11-11 (74 in all) | 15 more, up to 2026-11-11 (89 in all) | 9 more, up to 2026-11-12 (98 in all) | 15 more, up to 2026-11-13 (113 in all) | 13 more, up to 2026-11-15 (126 in all): 2 read-guard on 2026-11-14, 8 auditor-guard and 3 read-guard on 2026-11-15 | 34 more, up to 2026-11-18 (160 in all): from 2026-11-16, 20 read-guard, 5 auditor-guard and 4 step-guard, and 5 earlier that Day 12's count had not reached | 10 more, up to 2026-11-22 (170 in all): from 2026-11-19, 5 auditor-guard and 3 read-guard, and 2 earlier that Day 13's count had not reached. In the trial's container, 2: the reviewer's read-only hook on a `git fetch` |
| What each gate cost | `docs/dashboard/gates.json` | Day 1: seen red, 5 runs for $0.36; break on purpose, 8 runs for $0.39 | Day 2: seen red, 5 runs for $0.36; break on purpose, 1 run for $0.12 | Day 3: seen red, 8 runs for $0.60; break on purpose, 16 runs for $0.93; evidence replay, 4 runs for $0.17 | Day 4: seen red, 18 runs for $1.50; break on purpose, 18 runs for $1.21; hooks, 7 runs for $0.02; the spec-auditor, 1 run for $2.20 | Day 5: seen red, 15 runs for $0.86; break on purpose, 19 runs for $1.26; evidence replay, 4 runs for $0.87; hooks, 4 runs for $0.01; the spec-auditor, 1 run for $3.04 | Day 6: seen red, 11 runs for $2.07; break on purpose, 10 runs for $1.23; evidence replay, 5 runs for $0.70; hooks, 6 runs for $0.01 | Day 7: seen red, 26 runs for $3.11; break on purpose, 28 runs for $4.67; evidence replay, 10 runs for $0.96; hooks, 13 runs for $0.78 | Day 8: auditors, 2 runs for $9.97; seen red, 11 runs for $1.25; break on purpose, 19 runs for $2.32; evidence replay, 3 runs for $0.69; hooks, 7 runs for $0.10 | Day 9: seen red, 11 runs for $0.93; break on purpose, 12 runs for $0.84; hooks, 5 runs for $0.01; the auditors' runs carry no Day (2026-11-11, 5 runs for $9.81, with the Phase 1 end audit) | Day 10: seen red, 29 runs for $1.69; break on purpose, 40 runs for $3.57; the spec-auditor, 1 run for $3.23; hooks, 7 runs for $0.10 | Day 11: seen red, 15 runs for $0.97; break on purpose, 24 runs for $1.51; hooks, 6 runs for $0.01; the auditors' runs carry no Day (2026-11-13: the plan-auditor $3.51, the spec-auditor $5.18) | Day 12: seen red, 13 runs for $0.87; break on purpose, 43 runs for $3.59; evidence replay, 2 runs for $0.19; hooks, 3 runs for $0.00; the auditors, 2 runs for $7.29 | Day 13: seen red, 41 runs for $1.94; break on purpose, 30 runs for $2.27; hooks, 3 runs for $0.04; the auditors, 4 runs for $5.78 | Day 14: seen red, 49 runs for $2.82; break on purpose, 47 runs for $3.75; evidence replay, 6 runs for $0.65; hooks, 3 runs for $0.17; the auditors, 11 runs for $17.09 |

## Retrospective
