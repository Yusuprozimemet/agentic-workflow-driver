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

## What is being measured

| Question | Evidence it will be judged on | Day 01 | Day 02 | Day 03 | Day 04 |
| --- | --- | --- | --- | --- | --- |
| Cost per merged PR, main sessions, beside the kit's baseline of $1.86 (`plan.md`, "What it is judged against") | `docs/dashboard/token-usage.json` | $5.51 over 5 merged PRs on 2026-11-06, $1.10 each ($2.45 attributed to Day 1 by branch, $3.06 on `main`). The implementer added $0.07. The close's own session is counted only up to its `token-usage.py` run | $7.97 over 3 merged PRs since Day 01's count, $2.66 each. It includes the tail of Day 01's close after its count, and this close only up to its `token-usage.py` run. The implementer added $0.05; the spec-auditor $1.51 | $15.07 over 9 merged PRs since Day 02's count (#11 to #19), $1.67 each. It includes the tail of Day 02's close after its count, and this close only up to its `token-usage.py` run. The implementer added $0.11; the spec-auditor $2.04; the plan-auditor $1.45 | $21.59 over 10 merged PRs since Day 03's count (#20 to #29), $2.16 each. It includes the tail of Day 03's close after its count, and this close only up to its `token-usage.py` run. The implementer added $0.61; the spec-auditor $2.20 |
| Replies per merged PR, main sessions, beside 34.4 | `docs/dashboard/token-usage.json` | 118 replies over 5 PRs, 23.6 each | 140 replies over 3 PRs, 46.7 each | 281 replies over 9 PRs, 31.2 each | 363 replies over 10 PRs, 36.3 each |
| Escapes per day | the Notes' Defect lines with `made:` an earlier day | 0 from a day; 1 from the repository's start (D01.15) | 3 from Day 01 (D02.2, D02.3, D02.11) | 0 from a day; 5 `made: none` (D03.1–D03.4 in `plan.md`, D03.5 in #11's description) | 0 from a day; 1 `made: none` (D04.14, the maintainer's machine) |
| Parks by reason | the driver's run log | none yet: the driver does not run steps until Phase 1 | none yet | none yet | none yet: `--once` has run only on fake projects and one live scratch project |
| Hook refusals | `docs/dashboard/refusals.json` | 1, read-guard, 2026-11-06 | 2 more, read-guard, 2026-11-06 (3 in all) | 1 more, read-guard, 2026-11-06 (4 in all) | 8 more, 2026-11-07: 7 read-guard, 1 auditor-guard (12 in all) |
| What each gate cost | `docs/dashboard/gates.json` | Day 1: seen red, 5 runs for $0.36; break on purpose, 8 runs for $0.39 | Day 2: seen red, 5 runs for $0.36; break on purpose, 1 run for $0.12 | Day 3: seen red, 8 runs for $0.60; break on purpose, 16 runs for $0.93; evidence replay, 4 runs for $0.17 | Day 4: seen red, 18 runs for $1.50; break on purpose, 18 runs for $1.21; hooks, 7 runs for $0.02; the spec-auditor, 1 run for $2.20 |

## Retrospective
