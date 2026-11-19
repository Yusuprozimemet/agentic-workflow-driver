# Day 14 — The level 2 trial's record: the count run at level 1, one day at level 2, what the driver merged, what parked, what it cost

**Phase:** 2 · **Depends on:** Day 13 · **Expected PRs:** 6 (the spec change, Tracks A, B, C, D, the close)

## Goal
The driver merges pull requests in another project without the maintainer, and this repository
holds the record. The trial's project runs at level 1, in the container, until `status` reads
15 of 15. Then it runs one whole day at level 2, and that day closes with its evidence replay
green. The record names every merge the driver made, every park and every refusal, and what the
reviewer found. It gives the cost beside the baseline ($1.86, 34.4) and beside the level 1 count
run (`plan.md`, Phase 2's Day 14 and its Done when). The step sessions' transcripts are counted
from the container's folder, and `status` shows the reviewer's sessions as their own kind. Day 14
is a stopping point: the plan-auditor reads the whole plan after its close (`plan.md`, "Stopping
points").

## Before this day (the maintainer's)
Track D cannot start until these are done. Each goes in the record's Set-up (C14.13).

- **The count run** (decided 2026-11-19). At 3f31818, `status` reads "level 2: 0 of 15 pull
  requests in a row merged without a change asked". Only container sessions count, and the
  container has run one step (bearing #101). Before the count run, add days to bearing's plan,
  since it ends at its Day 14, and write their specs: the driver parks on "write its day spec".
  Then run bearing with `"level": 1` (or no `level`) and the container keys until `status` reads
  15 of 15. That is about four bearing days. A merge where the maintainer asks for a change, a
  close, or a "still red" or "still has a blocker" park after two fixes starts the count again
  (C13.6, C08.10).
- **`main`'s protection on bearing**, checked with `python scripts/setup-check.py --repo
  Yusuprozimemet/bearing` before the level 2 day. `on` refuses to start at level 2 without it
  (C13.7). At Track D of Day 13 the one failure left was "A track's breaks replay", which bearing
  does not have (#213).
- **The red-check probe** (H13.2), on the scratch repository `Yusuprozimemet/merge-probe`, before
  the level 2 day. Try `gh pr merge <n> --merge --match-head-commit <the right sha>` on a pull
  request whose required check is red. Write down what gh printed, its exit code and the
  settings that were on.
- **The level 2 day**: `"level": 2` and `"review": true` in `driver.json`, then `on`, for one
  whole bearing day, its closing PR included. Load `GH_TOKEN` by hand before each run (#213).
- **The run log is kept.** The count reads `state/run.jsonl` as a whole. The record's copy holds
  its lines from the count run's first `start` on.

## In scope

Decided by the maintainer on 2026-11-19, where `plan.md` and the hand-offs leave it open:
- The count run comes first, as above.
- P54 (back one level on an escape) is not built: `specs/plan/overdue.json` moves its
  `settled_by` from 14 to 15, because Day 14's stop settles it and the stop comes after Day 14's
  close. This PR makes that change.
- The reviewer's session is its own kind in `status` (H12.3).

- **The container's transcripts (Track A; N12, H10.2).** `scripts/token-usage.py` gains
  `--container DIR`. DIR is the driver's `<state>/claude/projects`. With `--compare` or
  `--tools`, the `*.jsonl` files under its `-work` folder are read as well as the repository's
  (`transcripts()` as today). A main session's file is one whose path holds no `subagents` folder,
  as `agent()` says today. With neither flag, it is refused with exit 2, "--container needs
  --compare or --tools: token-usage.json counts this repository only", and nothing is written. A
  DIR with no `-work` folder adds no files. `scripts/publish-counts.py` is not changed: the
  dashboard counts this repository's sessions, and the driver's cost reaches it from the run log
  (`driver-runs.json`).
- **The reviewer's session in `status` (Track B; H12.3, P55).** A `start` line whose `prefix` is
  `"review"` prints, in the `steps:` block, `review of #<n>` where today the step's sentence
  stands. `<n>` is the `pr` of that session's `review` line, and "review of an unknown pull
  request" when there is none (a session that crashed or gave no verdict). The rest of the row is
  unchanged: the outcome, `$<cost>`, refusals and the session. Under the `cost:` line, when the
  log holds at least one review `start` line, `status` prints
  `reviewer: <k> sessions, $<x>, in the cost above`, where `<x>` is the sum of those sessions'
  `end` lines' `cost_usd`. The `cost:` line itself is unchanged and already counts them. With no
  review `start` line, the block is exactly as today.
- **The leftover picker goes (Track C).** #259 removed the "How this works" views and kept the
  picker that fed them, `how_excerpts` (`scripts/spec_drift_page.py`), its data in the build
  (`spec-drift.py`'s `how_this_works` key) and `howRecheck` with its helpers in
  `docs/dashboard/dashboard.js`. The page draws none of it. That PR could not retire the short
  spec's criteria, so this Day does (C14.8, four `Replaces:` lines). Their tests
  (`tests/test_how_this_works.py`, `tests/test_how_this_works_page.py`) are deleted with the code.
  Their recorded breaks in `specs/breaks/how-follows-newest-day.json` are retired with
  `break.py --retire`, as Day 13 retired C12.24's.
- **The record (Track D; N25, P55, N11, N27, N28, H09.2, H13.1, H13.2).** `docs/trial/day-14.md`
  and the run log's copy `docs/trial/run-14.jsonl` (lines as written, from the count run's first
  `start` on). The record has these sections, in this order: Set-up, The count run, The level 2
  day, Merges, Parks, Refusals, The reviewer, Cost, The usage limit, The install, The first merge,
  Unverified, Evidence. Its test is `tests/test_trial_fourteen.py` (`TrialFourteenTest`). It reads
  only the record and the copy, so CI can run it.

## Out of scope

- P54, back one level on an escape: Day 14's stop (`overdue.json`, `settled_by` 15).
- The Telegram remote (#212, S8) and P51's token scope with the container: Day 14's stop.
- `status` printing "level: 2". It still prints "level: 1" and does not read `driver.json`. The
  record quotes `driver.json` instead. Not asked for.
- `publish-counts.py` reading the container's folder: the dashboard counts this repository.
- H09.3, a resumed fix that meets the usage limit and a STOP during the wait: no Phase 2 day owns
  them (the maintainer).
- The plan-auditor's reading at the stop: step 6 of `CLAUDE.md`'s day order, in a new session
  after the close, never inside it.
- Pipeline step 6, whether the post-merge evidence replay stays (#212, S12): the maintainer's, after
  this close or Day 13's.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | `--container` in `scripts/token-usage.py`: C14.2–C14.4 |
| B | | The reviewer's row and line in `driver/status.py`: C14.5–C14.7 |
| C | | The leftover picker removed: C14.8, C14.9 |
| D | | After the maintainer's runs: the record, its copy and its test: C14.10–C14.15 |

C14.1 is proved in the spec-change PR. Tracks A to C do not depend on each other or on the
count run, and are built while the count run goes. Track D waits for the level 2 day's close and
its evidence run. Test files, new and edited:
- A: `ContainerTest` in `scripts/test_token_usage.py`.
- B: `StatusReviewTest` in `tests/test_status_review.py` (new; `tests/test_status.py` and
  `tests/test_status_trial.py` stay unedited, C14.7).
- C: `tests/test_how_this_works.py` and `tests/test_how_this_works_page.py` deleted.
- D: `tests/test_trial_fourteen.py` (`TrialFourteenTest`).

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [ ] C14.1 **hold** — The driver's code other than `driver/status.py`, its hooks, rules and
      image, and the earlier trial records' tests are unchanged since `3f31818`: Verify's
      `git diff` prints nothing.
      Plan: none — keeps the Day to the record and its two tools; no commitment is about it.
- [ ] C14.2 **new** — `python scripts/token-usage.py --compare --container <dir> --transcripts
      <empty> --repo <r>` reads the main sessions under `<dir>/-work/`. A test builds `<dir>/-work/`
      with one main session (two assistant replies with usage, dated after `--split`) and one
      under `-work/<id>/subagents/`. The "after" side then counts 2 replies and the subagent's
      none. A `<dir>` with no `-work` folder counts 0.
      Red today: argparse refuses the flag, "unrecognized arguments: --container", exit 2.
      Test: `ContainerTest.test_container_main_sessions_counted`, `ContainerTest.test_no_work_folder_adds_nothing`.
      Plan: N12 "token-usage.py is pointed there"
- [ ] C14.3 **new** — `--container` with neither `--compare` nor `--tools` exits 2, its stderr
      holds "--container needs --compare or --tools", and `--out` is not written.
      Red today: stderr says "unrecognized arguments: --container", not the sentence.
      Test: `ContainerTest.test_container_without_compare_or_tools_is_refused`.
      Plan: N12 "read from the container's Claude Code folder"
- [ ] C14.4 **hold** — Without `--container`, the folders read and the figures are as today:
      `RepoTest` and the rest of `scripts/test_token_usage.py` pass with their cases unedited.
      Plan: N12 "token-usage.py is pointed there"
- [ ] C14.5 **new** — On a log with a step session `s1` and a review session `r1` (`start` with
      prefix "review", a `review` line with `"pr": 7`, an `end` with outcome "review: #7, 1
      blockers" and `cost_usd` 0.4), the `steps:` block's second row is exactly
      `  <r1's at> review of #7: review: #7, 1 blockers, $0.40, refusals 0, session `r1``. A
      review session with no `review` line prints "review of an unknown pull request".
      Red today: the row prints the step's sentence where "review of #7" is expected.
      Test: `StatusReviewTest.test_review_row`, `StatusReviewTest.test_review_row_without_review_line`.
      Plan: P55 "with the reviewer session counted in"
- [ ] C14.6 **new** — On the same log with a second review session (`cost_usd` 0.3), the line
      right after `cost:` is exactly `reviewer: 2 sessions, $0.70, in the cost above`, and the
      `cost:` line's total still includes both.
      Red today: the line after `cost:` is the `level 2:` line.
      Test: `StatusReviewTest.test_reviewer_cost_line`.
      Plan: P55 "with the reviewer session counted in"
- [ ] C14.7 **hold** — A log with no review `start` line prints the `status` block exactly as
      before: `tests/test_status.py` and `tests/test_status_trial.py` pass, unedited since
      `3f31818` (Verify).
      Plan: none — Days 7 and 8's `status` output is kept; it serves no Day 14 commitment.
- [ ] C14.8 **new** — The picker is gone: `git grep -n -e how_excerpts -e howRecheck -e
      how_this_works -- scripts docs/dashboard tests` prints nothing, and the build's
      `spec-drift.json` has no `how_this_works` key.
      Red today: the grep finds lines in `scripts/spec_drift_page.py`, `scripts/spec-drift.py`,
      `docs/dashboard/dashboard.js` and both test files.
      Test: Verify's `git grep` (`--expect-stdout '\A\Z'` at the break); `DashboardFilesTest` builds the page.
      Replaces: S-how-follows-newest-day.1 — was: a promise whole at every other step is picked though the replay history holds no row for it.
      Replaces: S-how-follows-newest-day.2 — was: step 7 says "not re-checked yet" for an empty record.
      Replaces: S-how-follows-newest-day.3 — was: a replay history that has gone leaves the pick alone and shows as missing.
      Replaces: S-how-follows-newest-day.4 — was: a promise missing any other step of its record is still skipped.
      Plan: none — the maintainer's choice in #259 ("views go, picker stays") left code that nothing draws.
- [ ] C14.9 **hold** — The page still builds and draws its graphs: `tests/test_dashboard_files.py`
      and `tests/test_dashboard_page.py` pass.
      Plan: none — the dashboard's views are not commitments of `plan.md`.
- [ ] C14.10 **new** — The trial ran at level 2. `docs/trial/run-14.jsonl` reads without a reason.
      Every `start` line has an `end` line, or a later park "the run log names session `<id>` for
      this step, with no end" names its session. Every `merged` and `closed` line's `pr` is named
      by an earlier `wait` line. At least one `merged` line has `"by": "driver"`, and every such
      line comes after a `review` line for its `pr` with `"blockers": 0`.
      Red today: `docs/trial/run-14.jsonl` does not exist.
      Test: `TrialFourteenTest.test_run_log_is_a_level_2_trial`.
      Plan: N25 "and the record names every merge the driver made, every park and every refusal"
- [ ] C14.11 **new** — The record names every merge the driver made (Merges: each `"by":
      "driver"` line's pull request, time and head), every park (Parks: its time and line), and
      every refusal (Refusals: each `refused` entry's tool and input from the copy, and the
      `refusals.json` rows on the `dashboard-data` branch for the trial's dates, quoted). The
      sections come in the order In scope gives.
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_every_driver_merge_named`, `TrialFourteenTest.test_every_park_named`,
      `TrialFourteenTest.test_every_refusal_named`, `TrialFourteenTest.test_sections_in_order`.
      Plan: N25 "and the record names every merge the driver made, every park and every refusal"; N28 "this repository's refusals.json on the dashboard-data branch"
- [ ] C14.12 **new** — The Cost section holds `status`'s `cost:` and `reviewer:` lines as `status`
      gives them on the copy (the test runs `status` on it). It also holds, from
      `token-usage.py --compare --repo ../bearing --container <state>/claude/projects --split
      <the level 2 day's first local date>`, the "cost per merged pull request" and "replies per
      merged pull request" lines of the side before the split (the count run, level 1) and of
      the side after it (level 2), each with "(baseline $1.86)" and "(baseline 34.4)".
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_cost_lines_are_status`, `TrialFourteenTest.test_cost_beside_level_1_and_baseline`.
      Plan: P55 "34.4 replies per merged pull request"; N25 "with cost beside the baseline and level 1"
- [ ] C14.13 **new** — The Set-up names the project `bearing`, `budget_usd` 10, `steps_per_night`
      6, the ten `human_only` paths, the level of each run, the image, the driver's `main` commit,
      and the commit of bearing's copy of the kit's `scripts/spec-drift.py` (40 hex characters
      each).
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_set_up`.
      Plan: N27 "with budget_usd 10 per step, steps_per_night 6 and a ten-path human-only list"; N11 "trial's record names the commit of its project's copy"
- [ ] C14.14 **new** — The level 2 day closed with its evidence replay green. The Evidence section
      names bearing's closing PR, its merge commit (40 hex characters), an evidence run id and
      "conclusion: success". The copy holds a `merged` line for that pull request.
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_evidence_section`.
      Plan: N25 "closed with its evidence replay green"
- [ ] C14.15 **new** — The hand-offs are answered in the record. The usage limit (H09.2): "met"
      with the transcript record and the `result` quoted, or "not met". The install (H13.1): from
      one level 2 session's transcript, its install command and its first test command, quoted
      in that order. The first merge (H13.2): the first `"by": "driver"` line's pull request and
      head, and the red-check probe's command, output and exit code.
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_hand_off_sections`.
      Plan: N10 "installs the project as CI does before running its tests"

## Verify
```bash
python -m unittest tests.test_status_review tests.test_status tests.test_status_trial tests.test_dashboard_files tests.test_dashboard_page tests.test_trial_fourteen tests.test_trial_record tests.test_trial_ten -v
python -m unittest scripts.test_token_usage -v
git -c core.safecrlf=false diff --exit-code 3f31818 -- driver/__init__.py driver/box.py driver/config.py driver/decide.py driver/github.py driver/home.py driver/issues.py driver/livecheck.py driver/lock.py driver/loop.py driver/once.py driver/preflight.py driver/review.py driver/runlog.py driver/settings.py driver/steps.py driver/stream.py driver/switches.py driver/switchlog.py driver/tree.py run-steps.py hooks rules docker tests/test_status.py tests/test_status_trial.py tests/test_trial_record.py tests/test_trial_ten.py
git grep -n -e how_excerpts -e howRecheck -e how_this_works -- scripts docs/dashboard tests
```

## Notes
- The count run is bearing's work at level 1. It changes nothing here. Its PRs are bearing's, and
  the count is `status`'s on the PC's `state/run.jsonl`. If the count falls back during the run,
  the record says why, from the run log's line.
- The level 2 day is the driver's first live `gh pr merge` on a real pull request. A refused merge
  parks, as Day 13 built it (C13.13). The record names it under Parks and in The first merge.
- **Assumed** — GitHub refuses `gh pr merge --match-head-commit` on a head whose required check is
  red, as it refuses a wrong sha (merge-probe, 2026-11-18, gh 2.93.0) | not run: the maintainer,
  on merge-probe, before the level 2 day (H13.2).
- **Assumed** — the container's Claude Code writes each session's transcript to
  `<state>/claude/projects/-work/<session>.jsonl`: `ls state/claude/projects/-work` →
  `2d6771a4-63cb-4a41-b0ef-3da00a7fc3fb.jsonl`, the Day 10 step's session (2.1.322).
- C14.8's grep must find nothing in comments either: no comment names the removed functions.
- The short spec's breaks are retired, not re-recorded: their finds name code this Day deletes.
