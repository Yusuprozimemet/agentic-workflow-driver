# Day 16 — Back one level on an escape: the level in force, `raise`, level 3's entry, and a reviewer that looks for regressions

**Phase:** 3 · **Depends on:** Day 15 · **Expected PRs:** 6 (the spec change, Tracks A, B, C, D, the close)

## Goal
After a close, the driver reads the project's escapes from its `spec-drift.py --out` JSON. On
an escape it runs one level lower from the next step, and it does the same after a failed
evidence run. It writes the change in the switch log and keeps it until the maintainer runs
`run-steps.py raise`. `driver.json` accepts level 3, and `on` at level 3 starts only when
`status` counts two phases in a row at level 2 with no escape, no merge by hand and no step at
level 1. The driver's reviewer reads the callers of what a pull request changes, and its brief
is measured on its ten known cases against a bar (`plan.md`, Levels, "Back one level"; Phase 3's
Day 16; P53, P54, N40, N41; H15.1, H15.2).

## In scope

Decided by the maintainer on 2026-11-23, where `plan.md` and the hand-offs leave it open:
- The lowered level is kept in the switch log, and `driver.json` stays the maintainer's: the
  level in force is the lower of `driver.json`'s `level` and the level of the switch log's
  newest `level` line. The maintainer lifts it with a new switch, `run-steps.py raise`.
- An escape is P54 as written: a Defect line found at `close`, by the `dashboard`, in a
  `Day NN review` or by the `evidence replay`, whatever its `made:`, plus a failed evidence run
  the driver waited on. No plan change.
- `driver.json` accepts level 3 now (H15.1). `on` at level 3 refuses unless `status` counts
  the entry. Until Day 17 it runs as level 2, and an escape lowers it to 2.

Decided by the maintainer on 2026-11-25, on the spec-auditor's findings:
- The escapes of a close are read at the next step's start, `on`'s first step included, not
  only after a merge the driver waited on: a close that is the night's last step, or one merged
  by hand, is read by the next `on`. The switch log records each Day read, so none is read twice.
- Track D's new tests live in `tests/`, where CI's "Track tests seen red" lists them and every
  pull request runs them.
- Between Track A's merge and Track C's, a level in force of 3 runs as level 1: no level 3 run
  without its entry check (P53). Track C makes it run as level 2 once the count is met.
- Track A stays one pull request, with an `Oversized:` line.
- The reviewer's new brief must meet a bar on `scripts/agent-cases.py`'s ten cases:
  agentic-workflow-driver#214 and agentic-workflow-driver#250 each `blocker` with a blocker line naming the fault in at least 2 of 3
  runs, and bearing#153 and bearing#154 each `none` in at least 2 of 3.

Chosen by the writer, for the spec-auditor and the maintainer to read:
- The switch log is read to decide from here on, which `driver/switchlog.py`'s docstring denies
  today (`switchlog.py:3-4`). Only its `level` lines are read, and only when `driver.json`'s level
  is 2 or 3: at level 1 nothing is read (C16.6).
- `on` reads the level in force once, at its start. A `raise` during a run takes effect at the
  next `on`. A lowering made during the run takes effect at the next step.
- A start line records the level in force and the step's phase only at level 2 or 3, so that
  level 1's start lines, which frozen tests read, keep their keys.

**The level in force (Track A; P54, H15.1, H15.2).**
- `config.is_level` takes 1, 2 or 3. The line becomes `cannot start: <path>'s level must be
  1, 2 or 3` (C16.1, `Replaces: C13.1`).
- A `level` line in the switch log reads
  `{"event": "level", "level": <n>, "from": <m>, "escapes": [<ids>]}` (a lowering on escapes),
  `{"event": "level", "level": <n>, "from": <m>, "evidence": "<sha>"}` (a lowering on a failed
  evidence run) or `{"event": "level", "level": <n>, "by": "maintainer"}` (a raise), `at` aside.
- `switchlog.in_force(state, level)` returns `(level in force, newest level line or None, reason)`,
  where reason is `switchlog.read`'s.
- When the level in force is below `driver.json`'s, `on` prints one line on stdout before
  anything else it prints for the level, and `status`'s second line is the same text:
  `level: <n>, lowered from <m> on an escape: <id>, <id>; run-steps.py raise lifts it`, or, for
  a lowering on a failed evidence run,
  `level: <n>, lowered from <m> on a failed evidence run of <sha7>; run-steps.py raise lifts it`.
  `<m>` is the line's `from`.
- With no `level` line, or after a raise, `status` prints `level: <n>` as Day 15 does (C15.10
  stands unedited), and `on` prints no level line.
- A switch log that cannot be read, at level 2 or 3: `on` refuses with
  `cannot start: the level cannot be read: <reason>` (exit 2, no session), and `status`'s second
  line is `level: unknown: <reason>` (exit 2).
- `run-steps.py raise` (a new choice, with `--config` and `--state` as `on` takes them) writes
  the raise line with `driver.json`'s level and prints `level: raised to <n>, driver.json's`
  (exit 0) when the level in force is below it. Otherwise it writes nothing and prints
  `raise: the level is already <n>, driver.json's` (exit 1). With `--project` it refuses with
  `cannot raise: raise reads the level from driver.json; give --config, not --project` (exit 2).
- `level_2_refusals`, the level 2 merge and the waived checks go by the level in force, not
  `driver.json`'s, and apply when it is 2. A level in force of 3 runs as level 1 until Track C
  (`loop.py`'s three `config.get("level") == 2` tests become a test of the level in force `== 2`).
  Until Track C, then, Track B lowers only from a level in force of 2: a level 3 run as level 1
  lowered to 2 would merge without level 2's start checks. Track C extends the lowering to 3, so
  C16.15's lowering halves stay red at Track C's start.
- `tests/test_level_config.py`'s `BAD` message and `test_level_values` (C13.1's test, which
  expects 3 refused) are edited to C16.1's, and Day 13's break "C13.1: a level of 2.0 or True
  taken", whose find Track A rewrites, is retired in `specs/breaks/day-13.json`
  (`break.py --retire`) and C16.1's break recorded in its place.

**The escape (Track B; P54, N41).**
- Only when `driver.json`'s level is 2 or 3: before each step, the run's first included, the
  loop reads the `--out` JSON (`kit_lines`, as today) and takes its finished `days[]` entries:
  those whose `status` is `done` or `closed` (`spec_drift_specs.py:297` gives `closed` to a Day
  closed with a box unticked, as this repository's Day 8). Newer, newest and oldest go by
  position in the JSON's `order`, as `steps.phase_end` reads it, never by the Day's number (the
  kit lets Days run out of number order, `spec_drift_specs.out_of_order`); a finished Day not
  in `order` is not read. When the switch log has an `escapes` line, every finished Day after
  the latest-placed Day such a line names is read, in `order`, so two Days finished between
  reads both count; when it has none (the first read), only the last-placed finished Day is. Each Day read has its escapes: its `defects` whose `found`, lowered and
  stripped, is `close`, `dashboard` or `evidence replay`, or fullmatches `day \d+ review`. For
  each, the driver appends `{"event": "escapes", "day": <n>, "found": [<ids>]}` (`at` aside;
  `found` may be empty), after the run's `on` line when the run writes one, so a Day is read
  once, whether its close was the night's last step, merged by the driver or merged by hand. At
  `driver.json`'s level 1 nothing is read or written (C16.11).
- When the Days read hold at least one escape and the level in force is 2 or 3 (2 only, until
  Track C), the driver appends, after the last `escapes` line, one lowering line with `level` one
  less, `from` the level in force and `escapes` their `id`s in the Days read's order, then each
  Day's `defects[]` order. It prints
  `level: lowered to <n> from <m> on an escape: <id>, <id>`, and runs that step at the new level.
- A failed evidence run after a merge (`wait_evidence`'s `ended` line), when the level in force
  is 2 or 3 (2 only, until Track C), appends the lowering line with `evidence` the commit, then
  prints
  `level: lowered to <n> from <m> on a failed evidence run of <sha7>` before the park line it
  prints today.
- At `driver.json`'s level 2 or 3, a Day read whose Defect line has no `found` (the key absent
  or `null`: the kit writes `null` for a missing tag) ends the run with
  `cannot read the project: spec-drift.py's JSON has no days[<i>].defects[<j>].found` (exit 2).
  At level 1 the JSON is not read for escapes and the run goes on. At the start of a run at
  level 2 or 3, `level_2_refusals` refuses with
  `cannot start: level 2 needs each Defect line's found in spec-drift.py's JSON: days[<i>].defects[<j>] has none`,
  the first such line only, after the protection's line.
- Escapes are read from the project's JSON only: nothing reads the driver's own repository's
  specs (N41).

**Level 3's entry (Track C; P53, N40).**
- At level 2 or 3, `runlog.start` writes `"level": <the level in force>` and `"phase": <the step's
  Day's phase in the --out JSON's days[]>` after `"claude"`. A review's start line (`review.py`)
  has neither.
- `status.level_3_run(records, switches)` counts phases back from the run log's newest phase-end
  park. A phase-end park is a `park` record whose `line` matches
  `park: the end of Phase (.+?): Day \d+ starts Phase`; a phase-end park whose `line` equals the
  previous phase-end park's (written again when its issue could not be opened: `once.py:528-530`
  writes no second park while the issue is open) is the same park and is skipped. Its span runs from after the previous phase-end park (or the log's first record)
  to it. A step start is a `start` record whose `prefix` is not `review`. A span counts when:
  - it holds at least one step start;
  - every step start in it has `level` 2 or 3 and `phase` whose `str()` equals the ended
    phase's captured text (the JSON's phase is an int, the park's a string);
  - every `merged` line in it has `by` `"driver"`;
  - no switch log `level` line with `from` has an `at` inside the span: after the previous
    park's `at`, and at or before this park's (stamps are to the second).
  The count stops at the first span that does not count.
- `status`, with a config read whose level is 2 or 3, prints after its `level 2:` line:
  `level 3: <k> of 2 phases in a row at level 2 with no escape, no merge by hand and no step at level 1`.
  At level 1 and with `--project` it prints no such line.
- `on` with the level in force 3 adds, after level 2's refusal lines, when `k` < 2:
  `cannot start: level 3 needs 2 of 2 phases in a row at level 2 with no escape, no merge by hand and no step at level 1; status counts <k>`.
  With `k` ≥ 2 it runs as level 2 does today: Track C turns Track A's `== 2` tests of the level
  in force into `>= 2`, only once the count is in place.
- Track C also turns Track B's two 2-only lowering guards (on an escape, on a failed evidence
  run) into 2 or 3, so a level 3 run lowers to 2 (C16.15, both halves).

**The reviewer (Track D; Plan: none).**
- `rules/reviewer.md` gains three rules:
  - For each function, field or line format the diff changes, grep its callers and readers. A
    caller or reader that the diff leaves as it was, and that now gets something else, is a
    blocker.
  - The pull request may already be merged when you read it. Review it as if it were open.
  - A spec that asks for a change is no reason to file a broken caller as advice.
- `scripts/agent-cases.py --record`, for a review agent, keeps under `recorded.cases` one entry
  per case, in the cases' order: `{"case": "<repo's last part>#<pr>", "said": [<each run's verdict:
  "blocker", "none" or "unreadable">], "named": <how many runs' blocker lines match the case's
  names, a number>}`, beside today's worst counts. `scripts/improve-loop.py`'s "recorded on
  today's brief" line leaves `cases` out, as it leaves out `brief` and `runs` (`improve-loop.py:80`).
- `tests/test_reviewer_bar.py` reads `specs/agent-cases/reviewer.json`. It checks that
  `recorded.brief` is the first 7 characters of `git hash-object rules/reviewer.md`, and that the
  bar above holds on `recorded.cases`. It is in `tests/` so that every pull request runs it, one
  that edits only `rules/reviewer.md` included.
- Track D records the count on the new brief with `agent-cases.py reviewer --record` (3 runs) and
  pastes its lines in the PR (CI's "A changed brief shows its case count"). It adds
  `{"pr": <its number>, "stops": ["D12.38", "D14.68"]}` to `specs/fixes.json`: the new rules are
  aimed at those two defects (agentic-workflow-driver#214, agentic-workflow-driver#250).

## Out of scope
- Starting the next phase at level 3 on the plan-auditor's verdict, and the verdict line — Day 17
  (P53's first half, N42, H15.3).
- Bearing's `spec-drift.py` writing `found` on each Defect line: at bearing `7f8ec5d` it writes
  `id`, `problem` and `same_as` only (`scripts/spec-drift.py`, `defect_lines`), though all 221 of
  its Defect lines carry `found:` in their text. The kit's `spec-drift.py` writes it at `70fe106`
  (`found=fields.get("found")`), so level 2 refuses bearing until bearing takes the kit's
  `spec-drift.py` — the maintainer, before Day 18 (H16.1, to be written at the close).
- A `raise` from the phone — Phase 4.
- Reading escapes of the driver's own repository: N41 says they do not move the project's level.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | C16.1–C16.6 |
| B | | C16.7–C16.11, C16.20 |
| C | | C16.12–C16.15 |
| D | | C16.16–C16.18 |

B uses Track A's level in force and lowering line, and C uses both, so A, B and C run in that
order. D stands alone and may run at any point. No Track 0: each hold's break needs its track's
code. C16.19 holds today's code and is proved in this spec-change PR, whose `Replaces:` lifts
Day 15's freeze on the files the tracks edit; the PR retires Day 15's freeze break too.
Track A carries six criteria and an `Oversized:` line (the maintainer's choice, 2026-11-25).

Every `new` criterion names its break, and each track records it with `break.py --record`
(D15.33). As on Day 15, no red or break report may hold "[N chars]". Tests of `on`'s and
`raise`'s results compare through `same` (`tests/test_review_loop.py`), field by position, and
switch log lines are compared as dicts with `at` removed, through `same`.

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").

- [ ] C16.1 **new** — `config.problems` gives no line for `level` 3. For `level` 0, 4, 3.0,
      `True` and `"3"` it gives exactly `cannot start: <path>'s level must be 1, 2 or 3`. For 1,
      2 and absent it gives none, as before. Red today: 3 gives
      "level must be 1 or 2".
      Test: `LevelConfigTest.test_level_three`.
      Its break, in Track A: `is_level`'s tuple put back to `(1, 2)`.
      Replaces: C13.1 — was: `driver.config.problems` gives no line for a config without `level` or with `level` 1 or 2, and "cannot start: <path>'s level must be 1 or 2" for any other value.
      Plan: P53 "it is entered only after two phases in a row at level 2"
- [ ] C16.2 **new** — On a state whose switch log's newest `level` line is
      `{"level": 1, "from": 2, "escapes": ["D23.4"]}`, with `driver.json`'s level 2,
      `run-steps.py raise --config <c> --state <s>` prints `level: raised to 2, driver.json's`
      and exits 0. The switch log's new last line is `{"event": "level", "level": 2, "by": "maintainer"}`
      (`at` aside). A second `raise` prints `raise: the level is already 2, driver.json's`, exits 1
      and appends nothing, and so does a `raise` with no switch log. `raise --project <p>` exits 2
      with `cannot raise: raise reads the level from driver.json; give --config, not --project`.
      Red today: `raise` is not a choice (argparse exits 2, "invalid choice").
      Test: `RaiseTest.test_raise_then_already`, `RaiseTest.test_raise_needs_the_config`.
      Its break, in Track A: the "already" test made `<` in place of `<=` (the brief names the find).
      Plan: P54 "The driver goes back one level on an escape"
- [ ] C16.3 **new** — `on` with `driver.json`'s level 2, the four level 2 conditions holding
      (`LevelStartTest`'s set-up) and that switch log:
      - prints `level: 1, lowered from 2 on an escape: D23.4; run-steps.py raise lifts it` before
        the session;
      - makes no `branches/main/protection` call;
      - starts the session;
      - waits for the merge as level 1 does (no `gh pr merge`).
      After a raise line it runs as level 2 (C15.17's set-up). Red today: it reads the protection
      and merges at level 2.
      Test: `LevelInForceTest.test_lowered_runs_at_one`.
      Its break, in Track A: `level_2_refusals` given `driver.json`'s level in place of the level
      in force.
      Plan: P54 "The driver goes back one level on an escape"
- [ ] C16.4 **new** — `run-steps.py status --config <c>` with `level` 2 and that switch log prints
      `level: 1, lowered from 2 on an escape: D23.4; run-steps.py raise lifts it` as its second
      line. After a raise line it prints `level: 2`. With
      `{"level": 1, "from": 2, "evidence": "0123456789abcdef0123456789abcdef01234567"}` it prints
      `level: 1, lowered from 2 on a failed evidence run of 0123456; run-steps.py raise lifts it`.
      With `driver.json`'s level 3 and the line `{"level": 1, "from": 2, "escapes": ["D23.4"]}`
      it prints `level: 1, lowered from 2 on an escape: D23.4; run-steps.py raise lifts it`.
      Red today: it prints `level: 2`.
      Test: `StatusLevelTest.test_lowered_level`.
      Its break, in Track A: the lowered line's `from` read from `driver.json` in place of the
      switch log line.
      Plan: P54 "The driver goes back one level on an escape"
- [ ] C16.5 **new** — With `level` 2 and a switch log whose second line is `{`:
      - `on` exits 2 with `cannot start: the level cannot be read: <state>/switches.jsonl: line 2 cannot be read`
        and starts no session;
      - `status --config` prints `level: unknown: <state>/switches.jsonl: line 2 cannot be read`
        as its second line and exits 2.
      The test prints `<state>` for the folder and `/` for the path's separator (on Windows
      `os.path.join` gives `\`). Red today: `on` starts and `status` prints `level: 2`.
      Test: `LevelInForceTest.test_unreadable_switch_log`.
      Its break, in Track A: `in_force`'s reason dropped.
      Plan: P54 "The driver goes back one level on an escape"
- [ ] C16.6 **hold** — At `driver.json`'s level 1, a switch log with a lowering line and one with
      an unreadable line both change nothing: `on` prints no `level:` line and starts as at
      level 1, and `status --config` prints `level: 1`. True today: nothing reads the switch log.
      Test: `LevelInForceTest.test_level_one_reads_no_switches`.
      Its break, in Track A: the switch log read at level 1 too (the brief names the find).
      Plan: none — level 1 has no lower level; this keeps level 1's start unchanged.
- [ ] C16.7 **new** — `on` at level 2, set up as follows:
      - before the close, the fake project's `--out` JSON has `order` [23, 24] and `days[]`
        Day 23 `active` and Day 24 `planned`, both of one phase, so no Day is finished and the
        first step reads nothing (not `tests/test_dry_run.py`'s `drift_of`, whose `order` [1]
        parks Day 24's spec, `steps.py:95-96`);
      - the step is `day-23/close-the-day`'s, and the driver merges its pull request;
      - after the merge, the JSON gives Day 23 the Defect lines D23.1
        (found `track-reviewer`), D23.4 (found `close`), D23.5 (found `Day 22 review`), D23.6
        (found `dashboard`) and D23.7 (found `Evidence replay `), and its `status` `done`;
      - the next step is Day 24's spec.

      Then `on`:
      - prints `level: lowered to 1 from 2 on an escape: D23.4, D23.5, D23.6, D23.7`;
      - appends, after its `on` line,
        `{"event": "escapes", "day": 23, "found": ["D23.4", "D23.5", "D23.6", "D23.7"]}`,
        then `{"event": "level", "level": 1, "from": 2, "escapes": ["D23.4", "D23.5", "D23.6", "D23.7"]}`;
      - starts the next step and does not merge its pull request (one `gh pr merge` in the run).

      The same run with Day 23's `status` `closed` (a box left unticked) lowers the same way.
      Red today: no line, and two merges.
      Test: `EscapeTest.test_close_escape_lowers`.
      Its break, in Track B: `day \d+ review` dropped from the found pattern.
      Plan: P54 "a Defect line found at `close`, by the `dashboard` or in a `Day NN review`"; N41 "read from its `spec-drift.py --out` JSON as the next step is"
- [ ] C16.8 **hold** — The same run with Day 23's Defect lines found `track-reviewer`, `auditor`,
      `seen red`, `break on purpose`, `review`, `Day 22 review of D23`, `spec-change PR`,
      `Track A`, `self`, `rehearsal`, `CI` and `driver reviewer` (`specs/README.md`'s found values
      since #300 to #302) writes no `level` line, prints no `level: lowered` line and
      merges both pull requests. True today: nothing lowers.
      Test: `EscapeTest.test_no_escape_no_change`.
      Its break, in Track B: `review` added to the escapes' found values.
      Plan: P54 "a Defect line found at `close`, by the `dashboard` or in a `Day NN review`"
- [ ] C16.9 **new** — At level 2, a driver merge whose evidence run ends `failure`
      (`tests/test_merge_wait.py`'s `test_evidence_failed_parks` set-up, with
      `tests/test_level_2_merge.py`'s `LevelMergeTest` level 2 set-up):
      - prints `level: lowered to 1 from 2 on a failed evidence run of <sha7>` before the park
        line it prints today;
      - appends `{"event": "level", "level": 1, "from": 2, "evidence": "<sha>"}`;
      - the next `on` prints
        `level: 1, lowered from 2 on a failed evidence run of <sha7>; run-steps.py raise lifts it`.

      With `driver.json`'s level 2 and a level in force of 1 (C16.3's switch log), a merge by
      hand whose evidence run ends `failure` appends no `level` line and prints only the park
      line: there is no level 0. Red today: the park line only, in the first case.
      Test: `EscapeTest.test_failed_evidence_lowers`.
      Its break, in Track B: the lowering skipped when the line holds " ended `".
      Plan: P54 "or a failed evidence replay after a merge"
- [ ] C16.10 **new** — When a Defect line of the closed Day has no `found` key, and again when its
      `found` is `null`, C16.7's run ends after the close with
      `cannot read the project: spec-drift.py's JSON has no days[<i>].defects[<j>].found` (exit 2)
      and starts no next step. When a run at level 2 starts with such a line in any Day, `on`
      exits 2 with
      `cannot start: level 2 needs each Defect line's found in spec-drift.py's JSON: days[<i>].defects[<j>] has none`
      and starts no session. Red today: both runs go on.
      Test: `EscapeTest.test_defect_without_found`.
      Its break, in Track B: a missing `found` read as `""`.
      Plan: N41 "read from its `spec-drift.py --out` JSON as the next step is"
- [ ] C16.11 **hold** — C16.7's run at level 1 (`driver.json` with no `level`) writes no `escapes`
      or `level` line to the switch log (its `on` line is written, as today) and prints no `level:` line, and so does the same run with Day 23's Defect lines
      without `found` (bearing's JSON): the run goes on to the next step. True today.
      Test: `EscapeTest.test_level_one_escape_changes_nothing`.
      Its break, in Track B: the read's guard (only when `driver.json`'s level is 2 or 3) removed,
      so the JSON is read at level 1 and the run without `found` ends (the brief names the find).
      Plan: P54 "The driver goes back one level on an escape"
- [ ] C16.12 **new** — At level 2, the step's start line carries `"level": 2` and `"phase"`: the
      Day's `phase` in the fake `--out` JSON. After the C16.7 lowering, the next step's start line
      has neither key, and neither does a review's start line. At level 1, start lines are as
      today. Red today: no `level` key.
      Test: `StartLevelTest.test_start_records_level_and_phase`.
      Its break, in Track C: `level` left out of `runlog.start`'s record.
      Plan: N40 "no step at level 1, counted by `status`"
- [ ] C16.13 **new** — `run-steps.py status --config <c>` with `level` 2 prints
      `level 3: <k> of 2 phases in a row at level 2 with no escape, no merge by hand and no step at level 1`
      after its `level 2:` line. On fixture run logs, each with two phase-end parks
      (`park: the end of Phase 3: Day 24 starts Phase 4`, then Phase 4's), `k` is:
      - 2 when every step start is at level 2 with its phase and every merge is the driver's;
      - 1 when a step start in the older span has no `level`;
      - 0 when a merged line in the newer span has no `by`;
      - 0 when a switch log lowering line's `at` falls in the newer span;
      - 2 when every span also holds review start lines without `level`, and when the newer
        phase-end park is written twice in a row.
      Then, on the first fixture, with `level` 1 and with `--project` it prints no `level 3:` line.
      Red today: no such line.
      Test: `StatusLevel3Test.test_counts`.
      Its break, in Track C: the `by` test removed from `level_3_run`.
      Plan: N40 "counted by `status`"; P53 "it is entered only after two phases in a row at level 2 with no escape, no merge by hand and no step at level 1"
- [ ] C16.14 **new** — `on` with `level` 3 and the level 2 conditions holding:
      - when the run log counts 1, it exits 2 with
        `cannot start: level 3 needs 2 of 2 phases in a row at level 2 with no escape, no merge by hand and no step at level 1; status counts 1`
        and starts no session;
      - when it counts 2, it starts, its start line carries `"level": 3`, and it merges the pull
        request as level 2 does.

      Red today (at Track C's start, on Tracks A and B's code): level 3 runs as level 1, so it
      starts a session with no count and does not merge.
      Test: `Level3StartTest.test_needs_two_phases`, `Level3StartTest.test_runs_as_level_2`.
      Its break, in Track C: the count compared with 1 in place of 2.
      Plan: P53 "it is entered only after two phases in a row at level 2"
- [ ] C16.15 **new** — C16.7's run with `level` 3 and the entry counted:
      - merges the close's pull request;
      - prints `level: lowered to 2 from 3 on an escape: D23.4, D23.5, D23.6, D23.7`;
      - appends the lowering line with `"level": 2, "from": 3`;
      - merges the next step's pull request (two `gh pr merge`);
      - the next `on` prints `level: 2, lowered from 3 on an escape: D23.4, D23.5, D23.6, D23.7; run-steps.py raise lifts it`.

      And C16.9's set-up with `level` 3 and the entry counted prints
      `level: lowered to 2 from 3 on a failed evidence run of <sha7>` before the park line and
      appends `{"event": "level", "level": 2, "from": 3, "evidence": "<sha>"}`.

      Red today (at Track C's start): level 3 runs as level 1, so the driver does not merge the
      close (one `gh pr merge`), and Track B lowers from 2 only, so no lowering line is written.
      Test: `EscapeTest.test_level_three_lowers_to_two`.
      Its break, in Track C: level 3 run as level 1 again (Track C's `>= 2` put back to `== 2` in
      the merge's test; the brief names the find).
      Plan: P54 "The driver goes back one level on an escape"
- [ ] C16.16 **new** — `agent-cases.py reviewer --record`, on a fake runner built as
      `scripts/test_agent_cases.py`'s `ReviewRunTest` builds it, keeps `recorded.cases`, one entry
      per case in order, each with `case`, `said` and `named` (a number) as In scope says. Its
      `verdict`, `named`, `runs` and `brief` are as today. The test gives its case repositories
      fixed names (`driver`, `bearing`), never a temporary folder's, so its report replays.
      Red today: `recorded` has no `cases`.
      Test: `tests/test_reviewer_record.py`, `ReviewerRecordTest.test_record_keeps_each_case`.
      Its break, in Track D: `cases` left out of the recorded dict.
      Plan: none — measuring the reviewer's brief is tooling for the maintainer's choice of 2026-11-22, not a commitment of plan.md.
- [ ] C16.17 **new** — `rules/reviewer.md` holds "callers", "already merged" and "as if it were
      open". Red today: it holds none of the three. C12.2's six phrases stay C12.2's.
      Test: `ReviewAgentsTest.test_brief_reads_the_callers`.
      Its break, in Track D: "already merged" taken out of the brief.
      Plan: none — what the reviewer looks for is detail of Day 12's reviewer; P63 covers only what it may not do.
- [ ] C16.18 **new** — `specs/agent-cases/reviewer.json`'s `recorded.brief` is the first 7
      characters of `git hash-object rules/reviewer.md`. Its `recorded.cases` give:
      - `agentic-workflow-driver#214` and `agentic-workflow-driver#250` `blocker`, named in at
        least 2 of 3 runs;
      - `bearing#153` and `bearing#154` `none` in at least 2 of 3.

      The test reports, in fixed words, the first case that falls short. Red today: `recorded`
      has no `cases` ("no per-case record").
      Test: `tests/test_reviewer_bar.py`, `ReviewerBarTest.test_brief_meets_the_bar`.
      Its break, in Track D: #214's `named` lowered to 1 in `reviewer.json` (the brief names the
      find).
      Plan: none — the bar is the maintainer's choice of 2026-11-23 for the brief; plan.md names none.
- [ ] C16.19 **hold** — These files stay unchanged since `97688d5`:
      `driver/__init__.py`, `driver/box.py`, `driver/decide.py`, `driver/github.py`,
      `driver/home.py`, `driver/issues.py`, `driver/livecheck.py`, `driver/lock.py`,
      `driver/preflight.py`, `driver/review.py`, `driver/settings.py`, `driver/steps.py`,
      `driver/stream.py`, `driver/tree.py`, `hooks`, `docker`, `tests/test_once.py`,
      `tests/test_box_session.py`, `tests/test_status.py`, `tests/test_status_trial.py`,
      `tests/test_trial_record.py`, `tests/test_trial_ten.py`, `docs/trial/day-08.md`,
      `docs/trial/day-10.md`, `docs/trial/run.jsonl` and `scripts/test_token_usage.py`. Verify's
      `97688d5` diff prints nothing, and `tests/test_status.py`, `tests/test_status_trial.py` and
      `scripts/test_token_usage.py` pass unedited. True today.
      Test: Verify's `git diff`, `tests/test_status.py`.
      Its break, in this spec-change PR: a driver file outside the edited ones changed (find
      `decides its next step` in `driver/__init__.py`).
      Replaces: C15.16 — was: the files C14.1, C14.4 and C14.7 froze at `3f31818` stay unchanged since `11206ea`, all but the six Day 15's tracks edit, and `scripts/test_token_usage.py` with them.
      Plan: none — the freeze keeps Days 7 to 15's code out of this Day's diff; it serves no Day 16 commitment.
- [ ] C16.20 **new** — A close the driver did not read when it merged is read by the next `on`:
      - C16.7's set-up with `steps_per_night` 1: the run ends after the close's merge and writes
        no `escapes` line; the next `on` prints
        `level: lowered to 1 from 2 on an escape: D23.4, D23.5, D23.6, D23.7` before its session,
        appends C16.7's two lines and does not merge;
      - the same with the close merged by hand before an `on`: the test writes into the run log,
        before that `on`, the close's `merged` line with no `by` and `changed: false`, and an
        `end` whose outcome is `opened: #<n>` from a container session, so that
        `status.level_2_run` (`status.py:449-452`) still counts it and level 2 starts (`on` runs
        `level_2_refusals` before `once.settle`, `loop.py:436-440`); that `on` lowers the same way;
      - a further `on` appends no second `escapes` line for Day 23;
      - with `order` [22, 23, 24, 25], a switch log whose `escapes` line names Day 22, and Days
        23 and 24 both `done` in the JSON, Day 23's escapes D23.4 and Day 24's D24.2 (found
        `close`), the next `on` appends `escapes` lines for Day 23 then Day 24 and one lowering
        line with `"escapes": ["D23.4", "D24.2"]`;
      - with `order` [22, 24, 23, 25], a switch log whose `escapes` line names Day 24, and Day 23
        then `done` with D23.4 (found `close`), the next `on` reads Day 23 (it is placed after
        Day 24) and lowers on D23.4.

      Red today: no line, and the `on` after the close merges its step.
      Test: `EscapeTest.test_close_read_at_next_on`.
      Its break, in Track B: the switch log's `escapes` lines not looked at, so Day 23 is read
      again (the brief names the find).
      Plan: P54 "The driver goes back one level on an escape"

## Verify
```bash
python -m unittest tests.test_level_config tests.test_raise tests.test_level_in_force tests.test_status_level tests.test_escape tests.test_level_3 tests.test_review_agents tests.test_reviewer_record tests.test_reviewer_bar tests.test_status tests.test_status_trial
python -m unittest discover -s scripts -p "test_agent_cases.py"
python -m unittest discover -s scripts -p "test_improve_loop.py"
git -c core.safecrlf=false diff --exit-code 97688d5 -- driver/__init__.py driver/box.py driver/decide.py driver/github.py driver/home.py driver/issues.py driver/livecheck.py driver/lock.py driver/preflight.py driver/review.py driver/settings.py driver/steps.py driver/stream.py driver/tree.py hooks docker tests/test_once.py tests/test_box_session.py tests/test_status.py tests/test_status_trial.py tests/test_trial_record.py tests/test_trial_ten.py docs/trial/day-08.md docs/trial/day-10.md docs/trial/run.jsonl scripts/test_token_usage.py
```

## Notes
- Base: `main` at `97688d5`. Drafted 2026-11-23 on `cd78909`, parked while self-improving items
  3 to 7 merged (#288 to #299) and the dashboard's honest rates (#300 to #303), rebased
  2026-11-26. None of C16.19's files changed between the two commits, and its base moved to `97688d5`, the commit this PR merges onto.
- The spec-auditor read the draft on 2026-11-25 and made 21 findings, all taken (D16.1 to D16.21).
  The maintainer settled four of them (In scope, "Decided by the maintainer on 2026-11-25").
- The driver's escape (found at close, by the dashboard, in a Day NN review or by the evidence
  replay, P54) is not `specs/README.md`'s escape (a Defect `made:` on an earlier Day, whatever
  its `found:`), nor the JSON's and the dashboard's "Escapes per day". It was the maintainer's
  choice of 2026-11-23: the two counts are not one.
- The first `on` at level 2 or 3 after Track B reads the newest finished Day, which no `escapes`
  line names yet, so a project whose last close had an escape starts one level lower.
- Earlier Days' breaks whose finds the tracks rewrite, each re-recorded or retired in the track
  that rewrites it (`specs/README.md`, "Evidence at the close"):
  - Track A, `driver/loop.py`: `    if config.get("level") == 2:` and
    `level2=(home, started) if config.get("level") == 2 else None` (Day 13);
    `    waived = config.get("waived_checks", []) if config.get("level") == 2 else []` (C15.9);
  - Track A, `driver/config.py`: "C13.1: a level of 2.0 or True taken" (Day 13), retired;
  - Track A, `run-steps.py`, beside the new `raise`: `status_extra["level"] = config.get("level", 1)`
    (C15.10) and `if args.project is None:` (Days 7 and 8);
  - Track C, `driver/runlog.py`: `record["issue"] = issue` (Day 7's "start dropping the issue
    it is given") and `"issue"] = issue` (Day 8's "start writing a null issue");
  - Track C, `driver/status.py`: `lines.append(_level_2(records))` (Day 14, and C15.16's
    "a line put before the level 2 line");
  - Track C, `driver/loop.py`: its `>= 2` rewrites the finds Track A re-recorded with `== 2`
    (Day 13's two, C15.9's) and Track A's own C16.3 break; Track C re-records them;
  - Track C, the two lowering guards: any Track B break whose find holds one (C16.9's, if its
    find holds the guard) is re-recorded by Track C.
- This PR retires Day 15's "a driver file outside the six edited (C15.16)" in
  `specs/breaks/day-15.json`, pinned at `8c94ed9`. Its diff against `11206ea` covers
  `driver/switchlog.py`, `driver/once.py`, `driver/switches.py` and `rules/reviewer.md`, which
  Tracks A, C and D edit (as D15.11 found of C14.1's).
- Track D's measurement costs 30 reviewer sessions per run of `agent-cases.py` (10 cases, 3 runs);
  the brief may need more than one. The bar is measured on the same cases the new rules were
  written from, so passing it shows little beyond them. `ReviewerBarTest` sits in `tests/`, so
  the next edit to `rules/reviewer.md` fails it until a new `--record` meets the bar.
- **Assumed** — the `--out` JSON gives each Defect line `found` and `id` on this repository's
  `spec-drift.py`: `python -c` over `spec-drift.json`'s `days[].defects` → keys `catchable`,
  `found`, `id`, `cause`, `made`, `same_as`, `problem` (2026-11-25). Bearing at `7f8ec5d` gives
  `id`, `problem` and `same_as` only; the kit at `70fe106` writes `found`, `null` when absent.
- **Defect** D16.1 — found: auditor · cause: spec · made: Day 16 · escapes were read only at the loop's top after a merge the driver waited on, so a close that was the night's last step, or one merged by hand (run-14 has `merged 153 None` at level 2), was never read, against P54 and N40 (fixed in this PR: read before each step, with a switch log `escapes` record, C16.20).
- **Defect** D16.2 — found: auditor · cause: spec · made: Day 16 · the missing-`found` stop had no level condition, so at level 1 it would end every run after a close on bearing (fixed in this PR: read only at `driver.json`'s level 2 or 3, C16.11).
- **Defect** D16.3 — found: auditor · cause: spec · made: Day 16 · "no `found`" left out `null`, which the kit writes for a missing tag (fixed in this PR: C16.10).
- **Defect** D16.4 — found: auditor · cause: spec · made: Day 16 · Track D's new tests sat in `scripts/`, which `track-red.py` does not list, so CI's "Track tests seen red" would fail (fixed in this PR: moved to `tests/`, the maintainer's choice).
- **Defect** D16.5 — found: auditor · cause: spec · made: Day 16 · C16.17 named `test_brief_names_the_reply`, C12.2's test, already green on `main` (fixed in this PR: dropped).
- **Defect** D16.6 — found: auditor · cause: spec · made: Day 16 · `StatusLevel3Test.test_no_line_at_level_one` passed whole on `main` under a `new` criterion (fixed in this PR: folded into `test_counts`, C16.13).
- **Defect** D16.7 — found: auditor · cause: spec · made: Day 16 · C16.15 could pass whole at Track C's start, and its break was in Track B's code (fixed in this PR: level 3 runs as level 1 until Track C, red and break restated).
- **Defect** D16.8 — found: auditor · cause: spec · made: Day 16 · the spec did not say how Track A runs a level in force of 3, so level 3 could run with no entry check between Tracks A and C, against P53, and C16.14's red was stale (fixed in this PR: as level 1 until Track C, the maintainer's choice).
- **Defect** D16.9 — found: auditor · cause: spec · made: Day 16 · same-as: D15.11 · Day 15's C15.16 freeze break diffs files the tracks edit, so the breaks replay would fail without the break (fixed in this PR: retired, pinned at `8c94ed9`).
- **Defect** D16.10 — found: auditor · cause: spec · made: Day 16 · same-as: D15.10 · C13.1's test expects 3 refused and Track A rewrites its break's find; the spec listed neither (fixed in this PR: Track A edits the test and retires the break).
- **Defect** D16.11 — found: auditor · cause: spec · made: Day 16 · C16.4's break could not bite: in every case `driver.json`'s level equalled `from` (fixed in this PR: a level 3 case).
- **Defect** D16.12 — found: auditor · cause: spec · made: Day 16 · C16.9 named a failed-evidence set-up in `tests/test_level_2_merge.py`, which has none (fixed in this PR: `tests/test_merge_wait.py`'s).
- **Defect** D16.13 — found: auditor · cause: spec · made: Day 16 · the level 3 count left review starts, the phase's type, the span's edge and a repeated park undefined (fixed in this PR: In scope, C16.13).
- **Defect** D16.14 — found: auditor · cause: spec · made: Day 16 · no criterion gave `dashboard` or `evidence replay`, so dropping either failed nothing; `spec-change PR` was missing from the non-escapes, and the review pattern did not say fullmatch (fixed in this PR: C16.7, C16.8).
- **Defect** D16.15 — found: auditor · cause: spec · made: Day 16 · C16.5's path held `/`, which `os.path.join` does not give on Windows (fixed in this PR).
- **Defect** D16.16 — found: auditor · cause: spec · made: Day 16 · the per-case record's `case` would hold a temporary folder's name, which cannot replay, and `named` read as a list in In scope but a count in C16.18 (fixed in this PR: fixed names, a number).
- **Defect** D16.17 — found: auditor · cause: spec · made: Day 16 · the Notes said the bar gates later edits of the brief, but CI's scripts tests skip a PR that edits only `rules/reviewer.md` (fixed in this PR: the test in `tests/`).
- **Defect** D16.18 — found: auditor · cause: spec · made: Day 16 · `improve-loop.py:80` prints every `recorded` key but `brief` and `runs`, so it would dump `cases`; the spec did not list it (fixed in this PR: Track D's In scope).
- **Defect** D16.19 — found: auditor · cause: spec · made: Day 16 · earlier Days' breaks whose finds the tracks rewrite were not listed (fixed in this PR: Notes).
- **Defect** D16.20 — found: auditor · cause: spec · made: Day 16 · Track D, aimed at D12.38 and D14.68, added no `specs/fixes.json` row (fixed in this PR: Track D's In scope).
- **Defect** D16.21 — found: auditor · cause: spec · made: Day 16 · the bearing claims named no commit, and "until its kit does" was out of date: the kit writes `found` at `70fe106` (fixed in this PR: Out of scope, Assumed).
- The spec-auditor's recheck of the 21 fixes (2026-11-26) made 10 findings, all taken (D16.22 to D16.31).
- **Defect** D16.22 — found: auditor · cause: spec · made: Day 16 · the escape read took only Days with `status` `done`, so a Day closed with a box unticked, which `spec_drift_specs.py:297` gives `closed`, was never read (fixed in this PR: `done` or `closed`, a `closed` case in C16.7).
- **Defect** D16.23 — found: auditor · cause: spec · made: Day 16 · C16.11's break removed a level-1 guard on the lowering, which cannot bite because nothing is read at level 1 (fixed in this PR: the read's guard is the break).
- **Defect** D16.24 — found: auditor · cause: spec · made: Day 16 · only the newest finished Day was read, so of two Days finished between reads the older was lost (fixed in this PR: every finished Day newer than the newest one an `escapes` line names, newest only on the first read, a case in C16.20).
- **Defect** D16.25 — found: auditor · cause: spec · made: Day 16 · C16.7 and C16.20 left the starting JSON open, so the first step could write an `escapes` line for another Day, and the hand-merge case's `merged` line would make `level_2_run` refuse `on` first (fixed in this PR: no finished Day at the start, `changed: false` and a container-opened pull request).
- **Defect** D16.26 — found: auditor · cause: spec · made: Day 16 · between Tracks A and C a level 3 run as level 1 would be lowered to 2 and merge without level 2's start checks (fixed in this PR: Track B lowers only from 2, Track C extends it to 3, C16.15's red restated).
- **Defect** D16.27 — found: auditor · cause: spec · made: Day 16 · the failed-evidence lowering said "at level 2 or 3" of `driver.json`, so a level in force of 1 would write level 0 (fixed in this PR: the level in force, a case in C16.9 that writes nothing).
- **Defect** D16.28 — found: auditor · cause: spec · made: Day 16 · C16.8's non-escapes left out `CI` and `driver reviewer`, found values since #300 to #302 (fixed in this PR).
- **Defect** D16.29 — found: auditor · cause: spec · made: Day 16 · the Notes' list of rewritten finds left out Track C's `>= 2` over Track A's re-recorded and own breaks, and Day 8's "start writing a null issue" (fixed in this PR: Notes).
- **Defect** D16.30 — found: auditor · cause: spec · made: Day 16 · the spec did not say where the `escapes` line goes, and `tests/test_level_2_start.py`'s `first_switch` reads line 0 as the `on` line (fixed in this PR: after the `on` line).
- **Defect** D16.31 — found: auditor · cause: spec · made: Day 16 · a repeated phase-end park was said to come from `on` run twice, which `once.py:528-530` does not do while the issue is open, and two references read `driver#214` (fixed in this PR: the reason restated, `agentic-workflow-driver#214`).
- The spec-auditor's second recheck (2026-11-26, of d885ed6) made 5 findings, all taken (D16.32 to D16.36).
- **Defect** D16.32 — found: auditor · cause: spec · made: Day 16 · C16.7's starting JSON was `drift_of`'s, whose `order` [1] parks Day 24's spec (`steps.py:95-96`) and gives Day 23 no phase for Track C (fixed in this PR: `order` [23, 24], Day 23 `active`, Day 24 `planned`).
- **Defect** D16.33 — found: auditor · cause: spec · made: Day 16 · "newer" and "newest" were not defined, so read by number a Day run out of order would lose its escapes, D16.24 again (fixed in this PR: by position in `order`, an out-of-order case in C16.20).
- **Defect** D16.34 — found: auditor · cause: spec · made: Day 16 · Track C's In scope did not say it lifts Track B's two 2-only lowering guards, and no criterion had a level 3 failed evidence run (fixed in this PR: Track C's In scope, a case in C16.15, Notes).
- **Defect** D16.35 — found: auditor · cause: spec · made: Day 16 · C16.20's hand-merge case said a fake gives `changed`, which the driver computes, and left open who writes the line before `level_2_refusals` reads it (fixed in this PR: the test writes it before the `on`).
- **Defect** D16.36 — found: auditor · cause: spec · made: Day 16 · C16.11 said "writes no switch log line", false at every level since `on` writes its `on` line (fixed in this PR: no `escapes` or `level` line).
