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
- The reviewer's new brief must meet a bar on `scripts/agent-cases.py`'s ten cases:
  driver#214 and driver#250 each `blocker` with a blocker line naming the fault in at least 2 of 3
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
- `level_2_refusals` and the level 2 merge go by the level in force, not `driver.json`'s.

**The escape (Track B; P54, N41).**
- After the driver waits a merged pull request through its evidence run, and the step it merged
  was a close (`classify(step).prefix` ends in `/close-the-day`), the loop reads the new `--out`
  JSON (`kit_lines`, as today). The closed Day's escapes are its `days[]` entry's `defects`
  whose `found`, lowered and stripped, is `close`, `dashboard`, `evidence replay` or matches
  `day \d+ review`.
- When there is at least one and the level in force is 2 or 3, the driver appends the lowering
  line with `level` one less, `from` the level in force and `escapes` their `id`s in the JSON's
  order. It prints `level: lowered to <n> from <m> on an escape: <id>, <id>`, and runs the next
  step at the new level. At level 1 nothing is written or printed (C16.11).
- A failed evidence run after a merge (`wait_evidence`'s `ended` line) at level 2 or 3 appends the
  lowering line with `evidence` the commit, then prints
  `level: lowered to <n> from <m> on a failed evidence run of <sha7>` before the park line it
  prints today.
- A closed Day's Defect line with no `found` ends the run with
  `cannot read the project: spec-drift.py's JSON has no days[<i>].defects[<j>].found` (exit 2).
  At the start of a run at level 2 or 3, `level_2_refusals` refuses with
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
  `park: the end of Phase (.+?): Day \d+ starts Phase`. Its span runs from after the previous
  phase-end park (or the log's first record) to it. A span counts when:
  - it holds at least one step start;
  - every step start in it has `level` 2 or 3 and `phase` equal to the ended phase;
  - every `merged` line in it has `by` `"driver"`;
  - no switch log `level` line with `from` has an `at` inside the span (after the previous park's
    `at`, up to this park's).
  The count stops at the first span that does not count.
- `status`, with a config read whose level is 2 or 3, prints after its `level 2:` line:
  `level 3: <k> of 2 phases in a row at level 2 with no escape, no merge by hand and no step at level 1`.
  At level 1 and with `--project` it prints no such line.
- `on` with the level in force 3 adds, after level 2's refusal lines, when `k` < 2:
  `cannot start: level 3 needs 2 of 2 phases in a row at level 2 with no escape, no merge by hand and no step at level 1; status counts <k>`.
  With `k` ≥ 2 it runs as level 2 does today.

**The reviewer (Track D; Plan: none).**
- `rules/reviewer.md` gains three rules:
  - For each function, field or line format the diff changes, grep its callers and readers. A
    caller or reader that the diff leaves as it was, and that now gets something else, is a
    blocker.
  - The pull request may already be merged when you read it. Review it as if it were open.
  - A spec that asks for a change is no reason to file a broken caller as advice.
- `scripts/agent-cases.py --record`, for a review agent, keeps under `recorded.cases` one entry
  per case, in the cases' order: `{"case": "<repo's last part>#<pr>", "said": [<each run's verdict:
  "blocker", "none" or "unreadable">], "named": <the runs whose blocker lines match the case's
  names>}`, beside today's worst counts.
- `scripts/test_reviewer_bar.py` reads `specs/agent-cases/reviewer.json`. It checks that
  `recorded.brief` is the first 7 characters of `git hash-object rules/reviewer.md`, and that the
  bar above holds on `recorded.cases`.
- Track D records the count on the new brief with `agent-cases.py reviewer --record` (3 runs) and
  pastes its lines in the PR (CI's "A changed brief shows its case count").

## Out of scope
- Starting the next phase at level 3 on the plan-auditor's verdict, and the verdict line — Day 17
  (P53's first half, N42, H15.3).
- Bearing's `spec-drift.py` writing `found` on each Defect line: it writes `id`, `problem` and
  `same_as` only (`bearing/scripts/spec-drift.py`, `defect_lines`), so level 2 refuses bearing
  until its kit does — the maintainer, before Day 18 (H16.1, to be written at the close).
- A `raise` from the phone — Phase 4.
- Reading escapes of the driver's own repository: N41 says they do not move the project's level.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | C16.1–C16.6 |
| B | | C16.7–C16.11 |
| C | | C16.12–C16.15 |
| D | | C16.16–C16.18 |

B uses Track A's level in force and lowering line, and C uses both, so A, B and C run in that
order. D stands alone and may run at any point. No Track 0: each hold's break needs its track's
code. C16.19 holds today's code and is proved in this spec-change PR, whose `Replaces:` lifts
Day 15's freeze on the files the tracks edit.

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
      The test prints `<state>` for the folder. Red today: `on` starts and `status` prints `level: 2`.
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
      - the step is `day-23/close-the-day`'s, and the driver merges its pull request;
      - after the merge, the fake project's `--out` JSON gives Day 23 the Defect lines D23.1
        (found `track-reviewer`), D23.4 (found `close`) and D23.5 (found `Day 22 review`);
      - the next step is Day 24's spec.

      Then `on`:
      - prints `level: lowered to 1 from 2 on an escape: D23.4, D23.5`;
      - appends `{"event": "level", "level": 1, "from": 2, "escapes": ["D23.4", "D23.5"]}`;
      - starts the next step and does not merge its pull request (one `gh pr merge` in the run).

      Red today: no line, and two merges.
      Test: `EscapeTest.test_close_escape_lowers`.
      Its break, in Track B: `day \d+ review` dropped from the found pattern.
      Plan: P54 "a Defect line found at `close`, by the `dashboard` or in a `Day NN review`"; N41 "read from its `spec-drift.py --out` JSON as the next step is"
- [ ] C16.8 **hold** — The same run with Day 23's Defect lines found `track-reviewer`, `auditor`,
      `seen red`, `break on purpose`, `review`, `Track A`, `self` and `rehearsal` writes no
      `level` line, prints no `level: lowered` line and merges both pull requests. True today:
      nothing lowers.
      Test: `EscapeTest.test_no_escape_no_change`.
      Its break, in Track B: `review` added to the escapes' found values.
      Plan: P54 "a Defect line found at `close`, by the `dashboard` or in a `Day NN review`"
- [ ] C16.9 **new** — At level 2, a driver merge whose evidence run ends `failure`
      (`wait_evidence`'s set-up in `tests/test_level_2_merge.py`):
      - prints `level: lowered to 1 from 2 on a failed evidence run of <sha7>` before the park
        line it prints today;
      - appends `{"event": "level", "level": 1, "from": 2, "evidence": "<sha>"}`;
      - the next `on` prints
        `level: 1, lowered from 2 on a failed evidence run of <sha7>; run-steps.py raise lifts it`.
      Red today: the park line only.
      Test: `EscapeTest.test_failed_evidence_lowers`.
      Its break, in Track B: the lowering skipped when the line holds " ended `".
      Plan: P54 "or a failed evidence replay after a merge"
- [ ] C16.10 **new** — When a Defect line of the closed Day has no `found`, C16.7's run ends after
      the close with
      `cannot read the project: spec-drift.py's JSON has no days[<i>].defects[<j>].found` (exit 2)
      and starts no next step. When a run at level 2 starts with such a line in any Day, `on`
      exits 2 with
      `cannot start: level 2 needs each Defect line's found in spec-drift.py's JSON: days[<i>].defects[<j>] has none`
      and starts no session. Red today: both runs go on.
      Test: `EscapeTest.test_defect_without_found`.
      Its break, in Track B: a missing `found` read as `""`.
      Plan: N41 "read from its `spec-drift.py --out` JSON as the next step is"
- [ ] C16.11 **hold** — C16.7's run at level 1 (`driver.json` with no `level`) writes no switch log
      `level` line and prints no `level:` line: there is no level 0. True today.
      Test: `EscapeTest.test_level_one_escape_changes_nothing`.
      Its break, in Track B: the lowering's level-1 guard removed (the brief names the find).
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
      - 0 when a switch log lowering line's `at` falls in the newer span.
      With `level` 1 and with `--project` it prints no `level 3:` line. Red today: no such line.
      Test: `StatusLevel3Test.test_counts`, `StatusLevel3Test.test_no_line_at_level_one`.
      Its break, in Track C: the `by` test removed from `level_3_run`.
      Plan: N40 "counted by `status`"; P53 "it is entered only after two phases in a row at level 2 with no escape, no merge by hand and no step at level 1"
- [ ] C16.14 **new** — `on` with `level` 3 and the level 2 conditions holding:
      - when the run log counts 1, it exits 2 with
        `cannot start: level 3 needs 2 of 2 phases in a row at level 2 with no escape, no merge by hand and no step at level 1; status counts 1`
        and starts no session;
      - when it counts 2, it starts, its start line carries `"level": 3`, and it merges the pull
        request as level 2 does.

      Red today: `config.problems` refuses level 3.
      Test: `Level3StartTest.test_needs_two_phases`, `Level3StartTest.test_runs_as_level_2`.
      Its break, in Track C: the count compared with 1 in place of 2.
      Plan: P53 "it is entered only after two phases in a row at level 2"
- [ ] C16.15 **new** — C16.7's run with `level` 3 and the entry counted:
      - prints `level: lowered to 2 from 3 on an escape: D23.4, D23.5`;
      - appends the lowering line with `"level": 2, "from": 3`;
      - merges the next step's pull request (two `gh pr merge`);
      - the next `on` prints `level: 2, lowered from 3 on an escape: D23.4, D23.5; run-steps.py raise lifts it`.

      Red today: level 3 is refused.
      Test: `EscapeTest.test_level_three_lowers_to_two`.
      Its break, in Track C: the new level set to 1 in place of one less.
      Plan: P54 "The driver goes back one level on an escape"
- [ ] C16.16 **new** — `agent-cases.py reviewer --record` on `ReviewRunTest`'s fake runner keeps
      `recorded.cases`, one entry per case in order, each with `case`, `said` and `named` as In
      scope says. Its `verdict`, `named`, `runs` and `brief` are as today. Red today: `recorded`
      has no `cases`.
      Test: `ReviewRunTest.test_record_keeps_each_case`.
      Its break, in Track D: `cases` left out of the recorded dict.
      Plan: none — measuring the reviewer's brief is tooling for the maintainer's choice of 2026-11-22, not a commitment of plan.md.
- [ ] C16.17 **new** — `rules/reviewer.md` holds "callers", "already merged" and "as if it were
      open", and still holds C12.2's six phrases. Red today: it holds none of the three.
      Test: `ReviewAgentsTest.test_brief_reads_the_callers`, `ReviewAgentsTest.test_brief_names_the_reply`.
      Its break, in Track D: "already merged" taken out of the brief.
      Plan: none — what the reviewer looks for is detail of Day 12's reviewer; P63 covers only what it may not do.
- [ ] C16.18 **new** — `specs/agent-cases/reviewer.json`'s `recorded.brief` is the first 7
      characters of `git hash-object rules/reviewer.md`. Its `recorded.cases` give:
      - `agentic-workflow-driver#214` and `agentic-workflow-driver#250` `blocker`, named in at
        least 2 of 3 runs;
      - `bearing#153` and `bearing#154` `none` in at least 2 of 3.

      The test reports, in fixed words, the first case that falls short. Red today: `recorded`
      has no `cases` ("no per-case record").
      Test: `ReviewerBarTest.test_brief_meets_the_bar`.
      Its break, in Track D: #214's `named` lowered to 1 in `reviewer.json` (the brief names the
      find).
      Plan: none — the bar is the maintainer's choice of 2026-11-23 for the brief; plan.md names none.
- [ ] C16.19 **hold** — These files stay unchanged since `cd78909`:
      `driver/__init__.py`, `driver/box.py`, `driver/decide.py`, `driver/github.py`,
      `driver/home.py`, `driver/issues.py`, `driver/livecheck.py`, `driver/lock.py`,
      `driver/preflight.py`, `driver/review.py`, `driver/settings.py`, `driver/steps.py`,
      `driver/stream.py`, `driver/tree.py`, `hooks`, `docker`, `tests/test_once.py`,
      `tests/test_box_session.py`, `tests/test_status.py`, `tests/test_status_trial.py`,
      `tests/test_trial_record.py`, `tests/test_trial_ten.py`, `docs/trial/day-08.md`,
      `docs/trial/day-10.md`, `docs/trial/run.jsonl` and `scripts/test_token_usage.py`. Verify's
      `cd78909` diff prints nothing, and `tests/test_status.py`, `tests/test_status_trial.py` and
      `scripts/test_token_usage.py` pass unedited. True today.
      Test: Verify's `git diff`, `tests/test_status.py`.
      Its break, in this spec-change PR: a driver file outside the edited ones changed (find
      `decides its next step` in `driver/__init__.py`).
      Replaces: C15.16 — was: the files C14.1, C14.4 and C14.7 froze at `3f31818` stay unchanged since `11206ea`, all but the six Day 15's tracks edit, and `scripts/test_token_usage.py` with them.
      Plan: none — the freeze keeps Days 7 to 15's code out of this Day's diff; it serves no Day 16 commitment.

## Verify
```bash
python -m unittest tests.test_level_config tests.test_raise tests.test_level_in_force tests.test_status_level tests.test_escape tests.test_level_3 tests.test_review_agents tests.test_status tests.test_status_trial
python -m unittest discover -s scripts -p "test_agent_cases.py"
python -m unittest discover -s scripts -p "test_reviewer_bar.py"
git -c core.safecrlf=false diff --exit-code cd78909 -- driver/__init__.py driver/box.py driver/decide.py driver/github.py driver/home.py driver/issues.py driver/livecheck.py driver/lock.py driver/preflight.py driver/review.py driver/settings.py driver/steps.py driver/stream.py driver/tree.py hooks docker tests/test_once.py tests/test_box_session.py tests/test_status.py tests/test_status_trial.py tests/test_trial_record.py tests/test_trial_ten.py docs/trial/day-08.md docs/trial/day-10.md docs/trial/run.jsonl scripts/test_token_usage.py
```

## Notes
- Draft written 2026-11-23 on `cd78909`; not yet audited. The spec-auditor reads it next, and its
  fixes go in this PR before it opens, with a recheck (D10.12, D12.25).
- For the auditor to check:
  - that no test frozen or in force compares a level 2 start line's keys exactly (C16.12 adds two);
  - that a phase-end park is written to the run log on `on`'s path (`once.finish` and `park_issue`);
  - that `tests/test_status.py`'s one `--config` run has no `level` 2, so it gets no `level 3:` line;
  - that C16.7's fake can give a second `--out` JSON after the merge.
- Bearing cannot reach level 2 after this Day until its `spec-drift.py` writes `found` (C16.10;
  Out of scope). This repository's `spec-drift.py` writes it.
- Track D's measurement costs 30 reviewer sessions per run of `agent-cases.py` (10 cases, 3 runs);
  the brief may need more than one. The bar makes the count a gate for this brief: the next edit
  to `rules/reviewer.md` fails `ReviewerBarTest` until a new `--record` meets it.
- **Assumed** — the `--out` JSON gives each Defect line `found` and `id` on this repository's
  `spec-drift.py`: `python -c` over `spec-drift.json`'s `days[].defects` → keys include `found`
  and `id` (2026-11-23); bearing's give `id`, `problem` and `same_as` only.
