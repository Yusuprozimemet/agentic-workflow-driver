# Day 14 — The level 2 trial's record: the count run at level 1, one day at level 2, what the driver merged, what parked, what it cost

**Phase:** 2 · **Depends on:** Day 13 · **Expected PRs:** 9 (the spec change, Tracks 0, A, B, C1, C2, E, D, the close)

## Goal
The driver merges pull requests in another project without the maintainer, and this repository
holds the record. The trial's project runs at level 1, in the container, until `status` reads
15 of 15. Then it runs one whole day at level 2 (as it ran, from that day's Track A on:
"Before this day"), and that day closes with its evidence replay
green. The record names every merge the driver made, every park and every refusal, and what the
reviewer found. It gives the cost beside the baseline ($1.86, 34.4) and beside the level 1 count
run (`plan.md`, Phase 2's Day 14 and its Done when). The step sessions' transcripts are counted
from the container's folder, and `status` shows the reviewer's sessions as their own kind. Day 14
is a stopping point: the plan-auditor reads the whole plan after its close (`plan.md`, "Stopping
points").

Overdue: P54 waits — the maintainer chose on 2026-11-19 that Day 14's stop settles it, after this Day's close (`specs/plan/overdue.json`, `settled_by` 15).

## Before this day (the maintainer's)
Track D cannot start until these are done. Each goes in the record's Set-up (C14.13).

- **The count run** (decided 2026-11-19). At 3f31818, `status` reads "level 2: 0 of 15 pull
  requests in a row merged without a change asked". Only container sessions count, and the
  container has run one step (bearing #101, still open). Before the count run, add days to
  bearing's plan, since it ends at its Day 14, and write their specs: the driver parks on "write
  its day spec". Then run bearing with `"level": 1` (or no `level`) and the container keys until
  `status` reads 15 of 15. That is about four bearing days. The count run started on
  2026-11-21 and stopped at 1 of 15: two step sessions opened their pull request and then
  ended with a `PARK:` line (#108, #116), so the driver never counted them (D14.34). It resumes
  after Track E merges.
- **What sets the count back to 0** (C13.6, C08.10, `status.level_2_run`): a merge where the
  maintainer asked for a change, a close, a "still red" or "still has a blocker" park after two
  fixes, and a merge of a pull request no container session opened. The driver waits on any
  open pull request and writes its `merged` line, so a bearing plan or spec PR merged while `on`
  runs sets the count back to 0: merge those with the driver off.
- **`main`'s protection on bearing**, checked with `python scripts/setup-check.py --repo
  Yusuprozimemet/bearing` before the level 2 day. `on` refuses to start at level 2 without it
  (C13.7). At Day 13's Track D the one failure left was "A track's breaks replay", which bearing
  does not have (#213).
- **The red-check probe** (H13.2), on the scratch repository `Yusuprozimemet/merge-probe`, before
  the level 2 day. Try `gh pr merge <n> --merge --match-head-commit <the right sha>` on a pull
  request whose required check is red. Write down what gh printed, its exit code and the
  settings that were on.
- **The level 2 day**: `"level": 2` and `"review": true` in `driver.json`, then `on`, for one
  whole bearing day, its closing PR included. Load `GH_TOKEN` by hand before each run (#213).
  As it ran (the maintainer chose on 2026-11-22 to record it so): the count's 15th merge was
  the spec PR of bearing's Day 22 (#151), at level 1, so level 2 covers that day's Track A
  (#153) and its close (#154), not its spec step. The maintainer merged #153 by hand, a second
  after its review; #154 is the driver's one merge. The record's The level 2 day says so
  (C14.11). "By hand" is the maintainer's word, here and for #123 and #139 (C14.12): GitHub
  gives one login for every merge, and the run log shows only that the driver did not ask it.
- **The run log is kept.** The count reads `state/run.jsonl` as a whole. The record's copies
  start at the first line after `2026-11-12T23:21:05Z` (the Day 10 step's `end`, line 22 of
  `state/run.jsonl` at 3f31818). So #101's `wait` and `merged` lines, which the next `on` writes,
  are in the copy. Its opener's `end` line is not, and the record says so.

## In scope

Decided by the maintainer on 2026-11-19, where `plan.md` and the hand-offs leave it open:
- The count run comes first, as above.
- P54 (back one level on an escape) is not built: `specs/plan/overdue.json` moves its
  `settled_by` from 14 to 15 (this PR).
- The reviewer's session is its own kind in `status`'s rows and cost (H12.3).

- **The container's transcripts (Track A; N12, H10.2).** `transcripts(root, repo=None,
  container=None)` in `scripts/token-usage.py` also yields every `*.jsonl` under
  `<container>/-work/`, and nothing else of `<container>`. `main()` gains `--container DIR`
  (the driver's `<state>/claude/projects`) and passes it with `--compare` or `--tools`. A main
  session is told from a subagent by `agent()`, as today. With neither flag, `--container` is
  refused with exit 2, "--container needs --compare or --tools: token-usage.json counts this
  repository only", and nothing is written. `ContainerTest` lives in a new file,
  `tests/test_token_usage_container.py` (under `tests/`, where CI's "Track tests seen red" finds it), so `scripts/test_token_usage.py` changes only in
  C14.4's four lines (D14.70). `scripts/publish-counts.py` is not changed: the dashboard counts this repository's
  sessions, and the driver's cost reaches it from the run log (`driver-runs.json`).
- **The reviewer's session in `status` (Track B; H12.3, P55).** A `start` line whose `prefix` is
  `"review"` prints, in the `steps:` block, `review of #<n>` where today the step's sentence
  stands. `<n>` is the `pr` of that session's `review` line, and "review of an unknown pull
  request" when there is none (a session that crashed, was halted or gave no verdict). The rest
  of the row is unchanged. A new `status._reviewer(records)` returns
  `reviewer: <k> sessions, $<x>, in the cost above` when the log holds at least one review
  `start` line, `<x>` the sum of those sessions' `end` lines' `cost_usd`, and `None` otherwise.
  `status` prints it right after the `cost:` line. The `cost:` line is unchanged and already
  counts them. With no review `start` line, the block is exactly as today (C14.7).
- **The leftover picker goes (Tracks C1, C2).** #259 removed the "How this works" views and kept
  the picker that fed them. C1 removes the page's half: `howRecheck`, `howHas`, `howMissing` and
  `howExcerpt` in `docs/dashboard/dashboard.js`, and `tests/test_how_this_works_page.py`.
  `howBlob` stays: the file map uses it, and `scripts/test_dashboard_page.py` reads it. C2
  removes the build's half: `how_excerpts`, `how_excerpts_of`, `how_specs` and the `HOW_*`
  constants in `scripts/spec_drift_page.py`, the `how_this_works` key `spec-drift.py --build`
  puts in the page, and `tests/test_how_this_works.py`. The short spec's criteria are replaced
  (C14.8, C14.16). Their recorded breaks in `specs/breaks/how-follows-newest-day.json` are left
  as they are: breaks under a replaced criterion need neither replay nor retirement
  (`specs/README.md`, "Evidence at the close"), and `track-breaks.py` reads only `day-NN.json`.
- **A step that opened its pull request ends without `PARK:` (Track E; P29, D14.34).** bearing's
  `CLAUDE.md` says to stop after opening any pull request and wait for "merged", and the step
  sessions of #108 and #116 wrote that as a `PARK:` line, which wins over a pull request in
  `driver/once.py`'s `outcome()`. `rules/session.md` gains one line saying the driver waits for
  the merge itself (C14.19). `outcome()` is not changed: a `PARK:` after a pull request still
  parks, as P29 and the Day 4 rule say.
- **The record (Track D; N25, P55, N11, N27, N28, H09.2, H13.1, H13.2).** `docs/trial/day-14.md`
  and four copies, lines as written, from the start line above: `docs/trial/run-14.jsonl`
  (`state/run.jsonl`), `docs/trial/switches-14.jsonl` (`state/switches.jsonl`, S-switch-log),
  `docs/trial/refusals-14.jsonl` (`state/refusals/hooks.jsonl`, which `status` adds as late
  refusals) and `docs/trial/install-14.jsonl`. The last holds, from one level 2 step session's
  transcript, that session's id, then the `input` of its first `Bash` tool_use that installs
  the project and of its first that runs the tests, in that order, each as its `assistant`
  record gives it. The copies end where the level 2 day ended: `run-14.jsonl` at line 133 of
  `state/run.jsonl`, the park "park: the end of Phase 14: Day 23 starts Phase 15", and
  `switches-14.jsonl` at line 15 of `state/switches.jsonl`, the `on` at 2026-11-21T23:42:48Z;
  a line written later is not copied. (These transcripts hold most tool_use blocks a second time, the install's
  among them, in an `api-request-blob` record whose command starts `cd /work && `); one
  tool_use may be both
  (C14.15). The record has these
  sections, in this order: Set-up, The count run, The level 2 day, Merges, Parks, Refusals, The
  reviewer, Cost, The usage limit, The install, The first merge, Unverified, Evidence. Its test
  is `tests/test_trial_fourteen.py` (`TrialFourteenTest`). It reads only the record and the
  copies, and calls `status`'s functions with no `gh`, so CI can run it. The copies are data:
  Track D's PR may pass 400 lines, with an `Oversized:` line naming them.

## Out of scope

- P54, back one level on an escape: Day 14's stop (`overdue.json`, `settled_by` 15).
- The Telegram remote (#212, S8) and P51's token scope with the container: Day 14's stop.
- A live reviewer's `in progress:` line and its estimate: `_kind("review")` stays `None`, so a
  running reviewer still shows the step's sentence and "no estimate" (H14.1).
- `status` printing "level: 2". It still prints "level: 1" and does not read `driver.json`. The
  record quotes `driver.json` instead. Not asked for.
- `publish-counts.py` reading the container's folder: the dashboard counts this repository.
- H09.3, a resumed fix that meets the usage limit and a STOP during the wait: no Phase 2 day owns
  them (the maintainer).
- The plan-auditor's reading at the stop: step 6 of `CLAUDE.md`'s day order, in a new session
  after the close, never inside it.
- Pipeline step 6, whether the post-merge evidence replay stays (#212, S12): the maintainer's.
- `plan.md`'s "Unverified" items the record answers ("No merge has used the token", the usage
  limit of H09.2, and the reviewer started with `--agents` and `--agent` in the container): the
  plan-change PR after the close edits them, not this Day (H10.2).

## Tracks

| Track | Owner | Work |
|---|---|---|
| 0 | | The hold test for `status` with no reviewer: C14.7 |
| A | | `--container` in `scripts/token-usage.py`: C14.2, C14.3 |
| B | | The reviewer's row and `_reviewer` in `driver/status.py`: C14.5, C14.6 |
| C1 | | The page's half of the picker removed: C14.16 |
| C2 | | The build's half of the picker removed: C14.8 |
| E | | The session rules' line for a step that opened its pull request: C14.19 |
| D | | After the maintainer's runs, and after A and B merge: the record, its copies and its test: C14.10–C14.15, C14.17, C14.18 |

C14.1, C14.4 and C14.9 hold today's code and are proved in the spec-change PR (their breaks in
`specs/breaks/day-14.json`). Track 0 lands
first. Tracks A to C2 do not depend on the count run, and are built while the count run goes;
of them, only C2 depends on another: it adds to `tests/test_picker_gone.py`, which C1 creates, so
C1 lands first. Track E depends on no other track; the count run resumes only after it merges,
since the record's sessions must run with its line. Track D uses Track A's `--container` and Track B's `_reviewer`, and waits for
the level 2 day's close and its evidence run. Track C's two halves were split (about 530 lines
together, most of it the two test files): C1 is about 110 lines; C2 is about 420, all deletions
(`tests/test_how_this_works.py`'s 277 lines, `spec_drift_page.py`'s 136, `spec-drift.py`'s 4,
and the imports ruff then flags as unused), and its PR carries an `Oversized:` line saying so.
Test files, new and edited:
- 0 and B: `StatusReviewTest` in `tests/test_status_review.py` (new; `tests/test_status.py` and
  `tests/test_status_trial.py` stay unedited).
- A: `ContainerTest` in `tests/test_token_usage_container.py` (new).
- The close's spec change (D14.70): `LongPathTest.test_transcript_past_max_path_is_counted` in
  `scripts/test_token_usage.py`, its folder padded past 260 characters.
- C1: `tests/test_how_this_works_page.py` deleted; `PickerGoneTest` in `tests/test_picker_gone.py`
  (new, `test_page_half_gone`). C2: `tests/test_how_this_works.py` deleted; `test_build_half_gone`
  added to `PickerGoneTest`.
- E: `SessionRulesTest.test_after_pr_line` in `tests/test_session_rules.py`, in place of
  `test_install_line` (C13.14, replaced).
- D: `tests/test_trial_fourteen.py` (`TrialFourteenTest`).

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [x] C14.1 **hold** — The driver's code other than `driver/status.py`, its hooks, the
      reviewer's rules (`rules/reviewer.md`; `rules/session.md` is C14.19's) and image,
      `tests/test_once.py`, `tests/test_box_session.py`, the earlier trial records and their
      tests are unchanged since `3f31818`: Verify's `git diff` prints nothing.
      (`scripts/test_token_usage.py` is C14.4's.)
      Plan: none — keeps the Day to the record and its two tools; no commitment is about it.
      Evidence: Verify's `git diff` from `3f31818` prints nothing on `main` at `c7d4377`, after every Day 14 PR; its break recorded in #262, and again in #275 without `scripts/test_token_usage.py`.
      broken: a driver file other than status.py edited → +"""The driver: reads a project's state and decides its step (plan.md)."""
- [x] C14.2 **new** — `transcripts(<empty>, <r>, container=<d>)` yields the files under
      `<d>/-work/`, a main session and one under `-work/<id>/subagents/`, and not a main session
      put directly in `<d>`. `compare()` over its main sessions, with two replies dated
      2026-11-20 and splits `(2026-11-02,)`, counts 2 replies on the "after" side.
      Red today: `transcripts()` takes no `container`, a TypeError.
      Test: `ContainerTest.test_work_folder_read`, `ContainerTest.test_compare_counts_container_replies`.
      Plan: N12 "token-usage.py is pointed there"
      Evidence: `ContainerTest.test_work_folder_read` and `ContainerTest.test_compare_counts_container_replies` pass on `main` at `66782b6` (#265).
      seen red: python -m unittest tests.test_token_usage_container.ContainerTest.test_work_folder_read on 091a6ef → FAILED (errors=1) (#265, re-run at the close on #264's merge)
      seen red: python -m unittest tests.test_token_usage_container.ContainerTest.test_compare_counts_container_replies on 091a6ef → FAILED (errors=1) (#265, re-run at the close on #264's merge)
      broken: the container's -work folder left out of its glob → AssertionError: False is not true : read: -other/s2.jsonl, -work/s1.jsonl, -work/s1/subagents/agent-a1.jsonl, stray.jsonl
      broken: the container's transcripts never read → AssertionError: 0 != 2
- [x] C14.3 **new** — `--container` with neither `--compare` nor `--tools` exits 2, and its stderr
      holds "--container needs --compare or --tools". (Exit 2 and no `--out` written are true
      today too, through argparse.)
      Red today: stderr says "unrecognized arguments: --container", not the sentence.
      Test: `ContainerTest.test_container_without_compare_or_tools_is_refused`.
      Plan: none — a refusal of a misuse; N12 is C14.2's.
      Evidence: `ContainerTest.test_container_without_compare_or_tools_is_refused` passes on `main` at `66782b6` (#265).
      seen red: python -m unittest tests.test_token_usage_container -v on main → AssertionError: False is not true : stderr lacks the sentence: unrecognized arguments (#265)
      broken: --container's refusal without --compare or --tools taken out → AssertionError: 1 != 2
- [x] C14.4 **hold** — Without `--container`, the folders read and the figures are as today:
      `scripts/test_token_usage.py` passes. Since `3f31818` it changes in four lines only, in
      `test_transcript_past_max_path_is_counted`, whose folder is padded past 260 characters
      wherever the checkout is (D14.70): Verify's `git diff -U0` of the file counts 6 lines
      that start `-` or `+`, the two file headers and the four.
      Plan: N12 "token-usage.py is pointed there"
      Evidence: `scripts/test_token_usage.py` passes on `main` at `c7d4377`, and Verify's `git diff -U0` count from `3f31818` prints 6 there, the max-path test's four lines and the two file headers (#275); its breaks recorded in #262 and #275.
      broken: the split day put on the earlier side → AssertionError: Lists differ: [50000, 60000] != [50000]
      broken: a line added outside the max-path test → 9
- [x] C14.5 **new** — On a log with a step session `s1` and a review session `r1` (`start` with
      prefix "review", a `review` line with `"pr": 7`, an `end` with outcome "review: #7, 1
      blockers" and `cost_usd` 0.4), the `steps:` block's second row is exactly
      `  <r1's at> review of #7: review: #7, 1 blockers, $0.40, refusals 0, session `r1``. A
      review session with no `review` line prints "review of an unknown pull request".
      Red today: the row prints the step's sentence where "review of #7" is expected.
      Test: `StatusReviewTest.test_review_row`, `StatusReviewTest.test_review_row_without_review_line`.
      Plan: P62 "The run log has one line per step and `status` prints it"
      Evidence: `StatusReviewTest.test_review_row` and `StatusReviewTest.test_review_row_without_review_line` pass on `main` at `66782b6` (#266).
      seen red: python -m unittest tests.test_status_review.StatusReviewTest.test_review_row on main → AssertionError: 'Step A' != 'review of #7' (#266)
      seen red: python -m unittest tests.test_status_review.StatusReviewTest.test_review_row_without_review_line on main → AssertionError: 'Step A' != 'review of an unknown pull request' (#266)
      broken: the review row labelled by its step → AssertionError: 'Step A' != 'review of #7'
      broken: the review row with no verdict naming no pull request → AssertionError: 'review of #None' != 'review of an unknown pull request'
- [x] C14.6 **new** — On the same log with a second review session (`cost_usd` 0.3),
      `status._reviewer(records)` is `reviewer: 2 sessions, $0.70, in the cost above`, and it is
      the line right after `cost:` in the block, whose total still includes both.
      Red today: `status` has no `_reviewer`, an AttributeError.
      Test: `StatusReviewTest.test_reviewer_cost_line`.
      Plan: P55 "with the reviewer session counted in"
      Evidence: `StatusReviewTest.test_reviewer_cost_line` passes on `main` at `66782b6` (#266).
      seen red: python -m unittest tests.test_status_review.StatusReviewTest.test_reviewer_cost_line on main → FAILED (errors=1) (#266)
      broken: the reviewer's cost summed over the other sessions → AssertionError: 'reviewer: 2 sessions, $0.25, in the cost above' != 'reviewer: 2 sessions, $0.70, in the cost above'
      broken: the reviewer line left out of the block → AssertionError: 'level 2: 0 of 15 pull requests in a row merged without a change asked' != 'reviewer: 2 sessions, $0.70, in the cost above'
- [x] C14.7 **hold** — A log with no review `start` line prints the `status` block as before: the
      line after `cost:` is the `level 2:` line, and `tests/test_status.py` and
      `tests/test_status_trial.py` pass, unedited since `3f31818` (C14.1).
      Test: `StatusReviewTest.test_no_reviewer_line_without_review` (Track 0). Its break, in Track
      0's PR: a line put before the `level 2:` line, find `lines.append(_level_2(records))` in
      `driver/status.py`, which Track B leaves occurring once (it adds `_reviewer`'s line before it).
      Plan: none — Days 7 and 8's `status` output is kept; it serves no Day 14 commitment.
      Evidence: `StatusReviewTest.test_no_reviewer_line_without_review` passes on `main` at `66782b6` (#263), and after Track B (#266); `tests/test_status.py` and `tests/test_status_trial.py` pass, unedited since `3f31818` (C14.1's diff).
      broken: a line put before the level 2 line → AssertionError: 'x' != 'level 2'
- [x] C14.8 **new** — The build's half of the picker is gone: `git grep -n -w -e how_excerpts -e
      how_excerpts_of -e how_specs -e how_this_works -e HOW_TEMPLATE -e HOW_REPLAY -e HOW_PLAN -e
      HOW_PLAN_PARTS -e HOW_NEEDED -e HOW_NO_PROMISE -- scripts tests` prints nothing.
      Red today: the grep finds lines in `scripts/spec_drift_page.py`, `scripts/spec-drift.py`
      and `tests/test_how_this_works.py`.
      Test: `PickerGoneTest.test_build_half_gone`, which runs the grep with `-l` for `-n` from
      the repository's root (found from the test's `__file__`) and asserts its exit code is 1
      and the list of files it prints is empty; the test spells the names in parts, so the grep
      does not find the test. The track's break runs this test, not the bare grep.
      Replaces: S-how-follows-newest-day.1 — was: a promise whole at every other step is picked though the replay history holds no row for it.
      Replaces: S-how-follows-newest-day.3 — was: a replay history that has gone leaves the pick alone and shows as missing.
      Replaces: S-how-follows-newest-day.4 — was: a promise missing any other step of its record is still skipped.
      Plan: none — the maintainer's choice in #259 ("views go, picker stays") left code that nothing draws.
      Evidence: `PickerGoneTest.test_build_half_gone` passes on `main` at `66782b6` (#269); Verify's first `git grep` prints nothing.
      seen red: python -m unittest tests.test_picker_gone.PickerGoneTest.test_build_half_gone on main → AssertionError: 3 != 0 : ['scripts/spec-drift.py', 'scripts/spec_drift_page.py', 'tests/test_how_this_works.py'] (#269)
      broken: a picker name put back in the build's page module → AssertionError: 1 != 0 : ['scripts/spec_drift_page.py']
- [x] C14.9 **hold** — The page still builds and draws its graphs, the file map with `howBlob`
      included: `scripts/test_dashboard_page.py` and `tests/test_dashboard_files.py` pass.
      Plan: none — the dashboard's views are not commitments of `plan.md`.
      Evidence: `scripts/test_dashboard_page.py` and `tests/test_dashboard_files.py` pass on `main` at `66782b6`, after both picker tracks (#268, #269); its break recorded in #262.
      broken: the helper the file map links by removed with the picker → AssertionError: Tuples differ: ('howBlob is not defined', []) != (None, [])
- [x] C14.10 **new** — The trial ran at level 2. The test builds a temporary state folder from the
      copies (`run-14.jsonl` as `run.jsonl`, `switches-14.jsonl` as `switches.jsonl`,
      `refusals-14.jsonl` as `refusals/hooks.jsonl`; an empty `refusals-14.jsonl` when the hook log
      had no line, which gives no late refusal) and calls `runlog.read`, `runlog.late_refusals`
      and `status`'s functions on that folder, never on `docs/trial`, which holds Day 8's
      `run.jsonl`. `runlog.read` gives no reason on it. Every `start` line has an `end` line, or a later park "the run log names session `<id>` for
      this step, with no end", or a `halt` line of `docs/trial/switches-14.jsonl` names its
      session. Every `merged` and `closed` line's `pr` is named by an earlier `wait` line. At
      least one `merged` line has `"by": "driver"`, and every such line comes after a `review`
      line for its `pr` with `"blockers": 0`.
      Red today: `docs/trial/run-14.jsonl` does not exist.
      Test: `TrialFourteenTest.test_run_log_is_a_level_2_trial`.
      Plan: N25 "and the record names every merge the driver made, every park and every refusal"
      Evidence: `TrialFourteenTest.test_run_log_is_a_level_2_trial` passes on `main` at `66782b6` (#273).
      seen red: python -m unittest tests.test_trial_fourteen.TrialFourteenTest.test_run_log_is_a_level_2_trial on main → AssertionError: docs/trial/run-14.jsonl does not exist (#273)
      broken: a driver merge after a review with a blocker → AssertionError: a driver merge has no review with blockers 0
- [x] C14.11 **new** — The record names every merge the driver made (Merges: each `"by":
      "driver"` line's pull request, time and head), every park (Parks: its time and line, and
      `status`'s "parks by reason" lines on the copy), and every refusal (Refusals: each `refused`
      entry's tool and input, each line of `docs/trial/refusals-14.jsonl`, and the
      `refusals.json` rows on the `dashboard-data` branch for the trial's dates, quoted). The
      sections come in the order In scope gives. The level 2 day names each merge the driver
      did not make: for each `merged` line of the copy at or after the Set-up's "level 2 from:"
      with no `by`, a line `merged by hand: #<n>` (#153), which
      `test_every_driver_merge_named` checks too.
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_every_driver_merge_named`, `TrialFourteenTest.test_every_park_named`,
      `TrialFourteenTest.test_every_refusal_named`, `TrialFourteenTest.test_sections_in_order`.
      Plan: N25 "and the record names every merge the driver made, every park and every refusal"; N28 "this repository's refusals.json on the dashboard-data branch"; P55 "parks by reason"
      Evidence: `TrialFourteenTest.test_every_driver_merge_named`, `TrialFourteenTest.test_every_park_named`, `TrialFourteenTest.test_every_refusal_named` and `TrialFourteenTest.test_sections_in_order` pass on `main` at `66782b6` (#273).
      seen red: python -m unittest tests.test_trial_fourteen on main → AssertionError: docs/trial/day-14.md does not exist (#273)
      broken: the hand merge left out of the record → AssertionError: The level 2 day does not name the merges made by hand
- [x] C14.12 **new** — The Cost section holds `status`'s `cost:` line and `_reviewer`'s line as
      they come out on the copy (the test calls them). It also holds the two sides of
      `token-usage.py --compare --transcripts <an empty folder> --repo ../bearing --container
      <state>/claude/projects --split <the level 2 day's first local date>`, quoted: "between"
      (the Day 10 step's one session and the count run, level 1) and "after" (the level 2 day's
      local date). For each
      side it gives the cost per merged pull request (the side's cost divided by its pull
      requests, worked by hand as Day 8's record did) beside "(baseline $1.86)", and the replies
      per merged pull request the side prints beside "(baseline 34.4)". `../bearing`'s `main` is
      pulled first (`merged_prs` reads the local `main`), and the record names the merged pull
      requests on each side that no container session opened (the plan and spec PRs merged by
      hand). Level 2 started at 00:42 local on 2026-11-22, the local date on which the count
      run's last session ran and its last two pull requests merged (#148, #151), so the "after"
      side holds level 1 replies and pull requests too: the record names those sessions and pull
      requests. So the section also holds two lines worked from the copy, which the test works
      out too: `count run alone: ` and `level 2 alone: `, each followed by what `status._cost`
      returns, after its "cost: ", on the copy's lines before the Set-up's "level 2 from:" time
      and on those at or after it (`level 2 alone: $<x>, merged pull requests <k>, $<y> each
      (baseline $1.86)`). The first counts four sessions whose pull request has no `merged`
      line: #108 and #116, whose sessions ended with a `PARK:` line, and #123 and #139
      (sessions 57665251 and 1efd23a0), merged by hand before their session ended, so the
      driver wrote "the session ended with no pull request and no PARK line". Its 15 merges
      include #101, whose opener's cost is before the copy. The record says all of this; no
      test can catch a name left out. It also says that the run log's dollars (the sessions'
      own `cost_usd`, the result's `total_cost_usd`) and `--compare`'s (list prices of the main sessions'
      replies) are two measures and are not subtracted, and that session 43f05fb7 (#148's
      opener) runs over local midnight, so its replies are on both sides.
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_cost_lines_are_status`, `TrialFourteenTest.test_cost_beside_level_1_and_baseline`.
      Plan: P55 "34.4 replies per merged pull request"; N25 "with cost beside the baseline and level 1"
      Evidence: `TrialFourteenTest.test_cost_lines_are_status` and `TrialFourteenTest.test_cost_beside_level_1_and_baseline` pass on `main` at `66782b6` (#273).
      seen red: python -m unittest tests.test_trial_fourteen on main → AssertionError: docs/trial/day-14.md does not exist (#273)
      broken: the record's cost line not status's → AssertionError: Cost lacks status's cost line
- [x] C14.13 **new** — The Set-up names the project `bearing`, `budget_usd` 10, `steps_per_night`
      6, the ten `human_only` paths, the level of each run, the image, the driver's `main` commit,
      the commit of bearing's copy of the kit's `scripts/spec-drift.py`, "bearing at the level 2
      day: <commit>" (40 hex characters each), and "level 2 from: <time>" in the run log's UTC
      form, which C14.11, C14.12 and C14.15 read: the `at` of the last `on` line of
      `switches-14.jsonl`, which the test asserts.
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_set_up`.
      Plan: N27 "with budget_usd 10 per step, steps_per_night 6 and a ten-path human-only list"; N11 "trial's record names the commit of its project's copy"
      Evidence: `TrialFourteenTest.test_set_up` passes on `main` at `66782b6` (#273).
      seen red: python -m unittest tests.test_trial_fourteen on main → AssertionError: docs/trial/day-14.md does not exist (#273)
      broken: level 2 from: not the last on line → AssertionError: level 2 from is not the last on line
- [x] C14.14 **new** — The level 2 day closed with its evidence replay green. The Evidence section
      names bearing's closing PR, its merge commit (40 hex characters), an evidence run id and
      "conclusion: success". The copy holds a `merged` line for that pull request. It also gives
      "escapes: <n>" for the level 2 day (`plan.md`, "Back one level"): each Defect line of
      bearing's spec for that day found at `close`, by the `dashboard` or in a review of the day
      (bearing writes `found: review`), and each evidence run after one of its merges whose
      conclusion is `failure`, quoted one per line, and <n> their count. The test checks only
      that <n> is the number of lines quoted: bearing's spec is not copied, so a Defect line
      left out is not caught here, and the record says so.
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_evidence_section`, `TrialFourteenTest.test_escapes_counted`.
      Plan: N25 "closed with its evidence replay green"; P55 "escapes per day"
      Evidence: `TrialFourteenTest.test_evidence_section` and `TrialFourteenTest.test_escapes_counted` pass on `main` at `66782b6` (#273).
      seen red: python -m unittest tests.test_trial_fourteen on main → AssertionError: docs/trial/day-14.md does not exist (#273)
      broken: the escapes count not the lines quoted → AssertionError: escapes does not count the lines quoted under it
      broken: the closing PR not the level 2 day's last merge → AssertionError: the closing PR is not the level 2 day's last merge
- [x] C14.15 **new** — The hand-offs are answered from the copies. The usage limit (H09.2): the
      section says "met", with the transcript record and the `result` quoted, when any line of
      `run-14.jsonl` holds "usage limit", and "not met" only when none does. The install (H13.1):
      `docs/trial/install-14.jsonl` holds three lines: a session id that starts a level 2 step
      in the copy (Day 22 Track A's, `76bd4a7f-98fc-4049-800f-4c791d2adc90`, which the test
      asserts), then the `input` of that session's first `Bash` tool_use that installs as
      bearing's CI does, `pip install -e ".[dev]"`
      (`.github/workflows/evidence.yml`, line 30 at 714412f; The install quotes that line at the
      Set-up's "bearing at the level 2 day: <40 hex>"), matched by the regex
      `pip install (?:-q )?-e ['"]?\.\[dev\]['"]?` so neither the quoting nor the `-q` the
      session chose matters, then the `input` of its first that runs the tests: one whose
      `command` holds the word "pytest" (bearing's CI runs `pytest -q`,
      `.github/workflows/tests.yml`). In Day 22 Track A's session one tool_use is both: the test
      asserts that lines 2 and 3 are the same `input`, and that the regex's match starts before
      the first "pytest" in its `command`. The install quotes the command.
      A level 2 step is a `start` line of the copy at or after the Set-up's "level 2 from: <time>"
      whose `prefix` is not "review": the run log writes no level. That time is the last `on`
      line of `switches-14.jsonl`, at 2026-11-21T23:42:48Z, the first after `driver.json`'s
      last write (23:37:15Z). The `on` at
      23:36:32Z started no session, and whether it ran at level 2 is not known (the maintainer,
      2026-11-22).
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_usage_limit_follows_the_copy`, `TrialFourteenTest.test_install_before_tests`.
      Plan: N10 "installs the project as CI does before running its tests"
      Evidence: `TrialFourteenTest.test_usage_limit_follows_the_copy` and `TrialFourteenTest.test_install_before_tests` pass on `main` at `66782b6` (#273).
      seen red: python -m unittest tests.test_trial_fourteen on main → AssertionError: docs/trial/day-14.md does not exist (#273)
      broken: the install's session not a level 2 step → AssertionError: the install's session is not a level 2 step
- [x] C14.16 **new** — The page's half of the picker is gone: `git grep -n -w -e howRecheck -e
      howHas -e howMissing -e howExcerpt -- docs/dashboard scripts tests` prints nothing, and
      `howBlob` is still defined in `docs/dashboard/dashboard.js` (C14.9).
      Red today: the grep finds lines in `docs/dashboard/dashboard.js` and
      `tests/test_how_this_works_page.py`.
      Test: `PickerGoneTest.test_page_half_gone`, built as C14.8's test is, for this grep: `-l`,
      run from the root, exit code 1 and no files asserted, the names spelled in parts, and the
      track's break run on this test.
      Replaces: S-how-follows-newest-day.2 — was: step 7 says "not re-checked yet" for an empty record.
      Plan: none — the same leftover as C14.8, on the page.
      Evidence: `PickerGoneTest.test_page_half_gone` passes on `main` at `66782b6` (#268); Verify's second `git grep` prints nothing, and `howBlob` is still defined in `docs/dashboard/dashboard.js`.
      seen red: python -m unittest tests.test_picker_gone.PickerGoneTest.test_page_half_gone on main → AssertionError: Lists differ: ['docs/dashboard/dashboard.js', 'tests/test_how_this_works_page.py'] != [] (#268)
      broken: a picker helper put back beside howBlob → AssertionError: Lists differ: ['docs/dashboard/dashboard.js'] != []
- [x] C14.17 **new** — The reviewer section names each `review` line of the copy: its pull
      request, its head and its blocker count, and the reviewer's PR comment's URL, taken from
      `gh pr view <n> --repo Yusuprozimemet/bearing --json comments` (the run log writes none):
      `https://github.com/Yusuprozimemet/bearing/pull/<n>#issuecomment-<digits>`, the comment whose
      body starts "review of `<head>` (session `<session>`)" with that line's head and session
      (`driver/review.py`), or "no comment" with the reason. A failed comment shows only on
      `on`'s output ("review: no comment on #<n>: <why>"): the maintainer saves that output on
      the level 2 day, and the record quotes the line.
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_every_review_named`.
      Plan: N35 "The reviewer's findings go in one comment on the pull request"
      Evidence: `TrialFourteenTest.test_every_review_named` passes on `main` at `66782b6` (#273).
      seen red: python -m unittest tests.test_trial_fourteen on main → AssertionError: docs/trial/day-14.md does not exist (#273)
      broken: a review's comment URL on another pull request → AssertionError: The reviewer does not name the review of #154
- [x] C14.18 **new** — The first merge (H13.2) names the first `"by": "driver"` line's pull
      request and head, and quotes the red-check probe's command, output and exit code.
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_first_merge`.
      Plan: P64 "on the commit the checks and the reviewer saw"
      Evidence: `TrialFourteenTest.test_first_merge` passes on `main` at `66782b6` (#273).
      seen red: python -m unittest tests.test_trial_fourteen on main → AssertionError: docs/trial/day-14.md does not exist (#273)
      broken: the probe's output cut from the first merge → AssertionError: gh's output after the command is empty
- [x] C14.19 **new** — `rules/session.md` is its text at `5d4f1b5` with C13.14's install line
      after the line that begins "- You never merge", and one more line right after the line
      that holds "PARK: <": "- After you open the step's pull request, end the last reply
      without a `PARK:` line, even where the project's CLAUDE.md says to stop and wait for
      "merged": the driver waits for the merge itself." (line endings aside). Nothing else in
      the file changes, and `OnceTest.test_rules_file` still passes unedited (C14.1). Track E
      retires Day 13's recorded break on `test_install_line` ("the session rules without the
      install line", `specs/breaks/day-13.json`) with `break.py --retire`, since CI's "A track's
      breaks replay" runs it on any PR that edits `rules/session.md`, and records C14.19's own.
      The retire edits `specs/breaks/day-13.json`, so Track E's CI replays every Day 13 break
      still in force; one that no longer replays is re-recorded or pinned in that PR.
      Red today: the file has 7 lines and not the new one.
      Test: `SessionRulesTest.test_after_pr_line` (it takes `test_install_line`'s place).
      Replaces: C13.14 — was: `rules/session.md` is its text at `5d4f1b5` with the install line only.
      Evidence: `SessionRulesTest.test_after_pr_line` and `OnceTest.test_rules_file` pass on `main` at `66782b6` (#271).
      seen red: python -m unittest tests.test_session_rules.SessionRulesTest.test_after_pr_line on main → AssertionError: Tuples differ: (7, [4, 5, 6]) != (8, []) (#271)
      broken: the session rules without the after-PR line → AssertionError: Tuples differ: (8, [4]) != (8, [])
      Plan: P29 "how a session hands over a step it could not finish or would not decide"

## Verify
```bash
python -m unittest tests.test_status_review tests.test_status tests.test_status_trial tests.test_dashboard_files tests.test_trial_fourteen tests.test_trial_record tests.test_trial_ten tests.test_token_usage_container tests.test_picker_gone tests.test_session_rules tests.test_once -v
python -m unittest scripts.test_token_usage scripts.test_dashboard_page -v
git -c core.safecrlf=false diff -U0 3f31818 -- scripts/test_token_usage.py | grep -c '^[-+]'  # 6
git -c core.safecrlf=false diff --exit-code 3f31818 -- driver/__init__.py driver/box.py driver/config.py driver/decide.py driver/github.py driver/home.py driver/issues.py driver/livecheck.py driver/lock.py driver/loop.py driver/once.py driver/preflight.py driver/review.py driver/runlog.py driver/settings.py driver/steps.py driver/stream.py driver/switches.py driver/switchlog.py driver/tree.py run-steps.py hooks rules/reviewer.md docker tests/test_once.py tests/test_box_session.py tests/test_status.py tests/test_status_trial.py tests/test_trial_record.py tests/test_trial_ten.py docs/trial/day-08.md docs/trial/day-10.md docs/trial/run.jsonl
git grep -n -w -e how_excerpts -e how_excerpts_of -e how_specs -e how_this_works -e HOW_TEMPLATE -e HOW_REPLAY -e HOW_PLAN -e HOW_PLAN_PARTS -e HOW_NEEDED -e HOW_NO_PROMISE -- scripts tests  # nothing, exit 1
git grep -n -w -e howRecheck -e howHas -e howMissing -e howExcerpt -- docs/dashboard scripts tests  # nothing, exit 1
```

## Notes
- The count run is bearing's work at level 1. It changes nothing here. Its PRs are bearing's, and
  the count is `status`'s on the PC's `state/run.jsonl`. If the count falls back during the run,
  the record says why, from the run log's line.
- The level 2 day is the driver's first live `gh pr merge` on a real pull request. A refused merge
  parks, as Day 13 built it (C13.13). The record names it under Parks and in The first merge.
- **Assumed** — GitHub refuses `gh pr merge --match-head-commit` on a head whose required check is
  red, as it refuses a wrong sha (merge-probe, 2026-11-18, gh 2.93.0) | run by the maintainer on
  merge-probe before the level 2 day, gh 2.93.0, the required check "test" red on the head:
  `gh pr merge 1 --merge --match-head-commit ec3d79f…` → "X Pull request
  Yusuprozimemet/merge-probe#1 is not mergeable: the base branch policy prohibits the merge.",
  exit 1, the pull request left open (`docs/trial/day-14.md`, The first merge; H13.2).
- **Assumed** — the container's Claude Code writes each session's transcript to
  `<state>/claude/projects/-work/<session>.jsonl`, its subagents under `<session>/subagents/`:
  `find state/claude/projects/-work` → `2d6771a4-63cb-4a41-b0ef-3da00a7fc3fb.jsonl` and
  `2d6771a4-…/subagents/agent-aa71599a54a3f2719.jsonl` with its `.meta.json` (2.1.322).
- **Assumed** — a reviewer started with `--agents <file> --agent reviewer` in the container leaves
  its transcript as a main session under `-work`, not under `subagents/`, so C14.12 counts it |
  run on 2026-11-22, before Track D: `find state/claude/projects/-work` → the two reviewer
  sessions' files, `d26d9fcb-….jsonl` and `3a64c23d-….jsonl`, beside the step sessions', with
  no folder of their own (2.1.322), and `--compare`'s "after" side counts them among its 6
  sessions.
- C14.8's and C14.16's greps find comments too: no comment names the removed names.
- **Defect** D14.1 — found: auditor · cause: spec · made: Day 14 · Verify and C14.9 named `tests.test_dashboard_page`; the file is `scripts/test_dashboard_page.py` (fixed in this PR).
- **Defect** D14.2 — found: auditor · cause: spec · made: Day 14 · C14.8 named a test class that does not exist, and its "no `how_this_works` key in `spec-drift.json`" half was true today: the key is put only in the `--build` page (fixed in this PR).
- **Defect** D14.3 — found: auditor · cause: spec · made: Day 14 · C14.12 called the side before the split the count run, but `--split` with HOOKS_DAY gives three sides and `--repo` alone reads the PC's bearing sessions; and it named "cost per merged pull request" and "baseline" lines no code prints (fixed in this PR: container only, the "between" side, the figures worked by hand).
- **Defect** D14.4 — found: auditor · cause: spec · made: Day 14 · Track C measured about 520 changed lines with no split and no `Oversized:` line (fixed in this PR: C1 and C2).
- **Defect** D14.5 — found: auditor · cause: spec · made: Day 14 · C14.7's named tests report shortened diffs that `break.py` refuses ("[75 chars]"), so the hold had no recordable break (fixed in this PR: a Track 0 test with a short report).
- **Defect** D14.6 — found: auditor · cause: spec · made: Day 14 · C14.10's rule failed on a reviewer stopped by a halt, which writes no `end` and no park names; the switch log S-switch-log promised to Day 14's record was not copied (fixed in this PR: `switches-14.jsonl`).
- **Defect** D14.7 — found: auditor · cause: spec · made: Day 14 · C14.15 passed on "not met" for any record and on the install's wording alone (fixed in this PR: "met" follows the copy, the install's commands copied and checked in order).
- **Defect** D14.8 — found: auditor · cause: spec · made: Day 14 · the count run's resets left out a merge no container session opened, which a bearing plan or spec PR merged while `on` runs is (fixed in this PR).
- **Defect** D14.9 — found: auditor · cause: spec · made: Day 14 · the copy "from the count run's first start" left out #101's `wait` and `merged` lines, written before that start (fixed in this PR).
- **Defect** D14.10 — found: auditor · cause: spec · made: Day 14 · "every refusal" left out the late refusals `status` reads from `<state>/refusals/hooks.jsonl` (fixed in this PR: `refusals-14.jsonl`).
- **Defect** D14.11 — found: auditor · cause: spec · made: Day 14 · The reviewer section, "what the reviewer found" in `plan.md`, had no criterion (fixed in this PR: C14.17).
- **Defect** D14.12 — found: auditor · cause: spec · made: Day 14 · H12.3 was taken for the rows and the cost only, unsaid: the live `in progress:` line still names the step (fixed in this PR: Out of scope, H14.1).
- **Defect** D14.13 — found: auditor · cause: spec · made: Day 14 · Track D's test needed a reviewer-line function In scope did not name (fixed in this PR: `status._reviewer`).
- **Defect** D14.14 — found: auditor · cause: spec · made: Day 14 · the grep let nine of the picker's names stay, and `howBlob`, which the file map uses, was not protected (fixed in this PR).
- **Defect** D14.15 — found: auditor · cause: spec · made: Day 14 · retiring the short spec's breaks with `break.py --retire` refuses at HEAD, and breaks under a replaced criterion need no retirement (fixed in this PR: left as they are).
- **Defect** D14.16 — found: auditor · cause: spec · made: Day 14 · C14.2's command had no `--split` and needed a real `--repo`, and its no-`-work` test was red only through argparse (fixed in this PR: `transcripts()` and `compare()` called directly).
- **Defect** D14.17 — found: auditor · cause: spec · made: Day 14 · Track D's copies would pass 400 lines with nothing said (fixed in this PR: an `Oversized:` line allowed).
- **Defect** D14.18 — found: auditor · cause: spec · made: Day 14 · P54 is overdue and the spec had no `Overdue:` line; C14.4 and C14.9 were not said to be proved in this PR; C14.4's cases could be edited unseen; C14.1 did not cover the earlier records; the reviewer's transcript place was assumed unsaid (fixed in this PR).
- **Defect** D14.19 — found: auditor · cause: spec · made: Day 14 · the recheck: D14.4's split left Track C2 at about 420 lines, all deletions, with nothing said (fixed in this PR: an `Oversized:` line for C2).
- **Defect** D14.20 — found: auditor · cause: spec · made: Day 14 · the recheck: C14.10's test, calling `runlog.read` on `docs/trial` as `tests/test_trial_record.py` does, would read Day 8's `run.jsonl`, and half of it passed today (fixed in this PR: a temporary state folder built from the copies).
- **Defect** D14.21 — found: auditor · cause: spec · made: Day 14 · the recheck: C14.8's grep let `HOW_PLAN_PARTS` stay, which In scope removes (fixed in this PR).
- **Defect** D14.22 — found: auditor · cause: spec · made: Day 14 · the recheck: C14.15's "a level 2 step" could not be told from the copies, which write no level, and "pip install" took any install, not the one bearing's CI runs (fixed in this PR: the Set-up's "level 2 from:" time, bearing's `pip install -e ".[dev]"`).
- **Defect** D14.23 — found: auditor · cause: spec · made: Day 14 · the recheck: P55's "escapes per day" had no criterion (fixed in this PR: C14.14's escapes count).
- **Defect** D14.24 — found: auditor · cause: spec · made: Day 14 · the recheck: C14.12's `--split` by local date could put a level 1 session on the "after" side, `merged_prs` reads `../bearing`'s local `main`, and the hand-merged PRs were counted unsaid (fixed in this PR).
- **Defect** D14.25 — found: auditor · cause: spec · made: Day 14 · the recheck: C14.17's comment URL had no source in the copies and no result for a failed comment, and its review half's `Plan:` N25 does not hold "what the reviewer found" (fixed in this PR: the URL from `gh pr view`, C14.17 split into C14.17 and C14.18).
- **Defect** D14.28 — found: auditor · cause: spec · made: Day 14 · the second recheck: D14.25's fix gave C14.17 `Plan: none`, though N35 is that comment, and C14.18 N25, though its one merge on the checked commit is P64's (fixed in this PR).
- **Defect** D14.29 — found: auditor · cause: spec · made: Day 14 · the second recheck: D14.22's fix read "level 2 from:" and a bearing commit from a Set-up whose test checks neither, and matched the install as one literal string the session's quoting could miss (fixed in this PR: both in C14.13, a regex).
- **Defect** D14.30 — found: auditor · cause: spec · made: Day 14 · the second recheck: C14.17 did not say which comment answers which `review` line or who keeps a failed comment's line; the Out of scope line gave an item `plan.md`'s Unverified list does not hold; the escapes count took cancelled runs and a "Day NN review" bearing never writes, and did not say its test cannot catch a Defect line left out (fixed in this PR).
- **Defect** D14.26 — found: auditor · cause: spec · made: Day 14 · the recheck: C14.1 was said proved in this PR with no `broken:` line, and C14.7 named no break Track B leaves applying (fixed in this PR: C14.1's break recorded, C14.7's find named).
- **Defect** D14.27 — found: auditor · cause: spec · made: Day 14 · the recheck: the reviewer-transcript Assumed line named no one who checks it, and H10.2's "Unverified" items in `plan.md` were left with no owner (fixed in this PR: the main session before Track D; the plan-change PR after the close).
- **Defect** D14.31 — found: track-reviewer · cause: spec · made: Day 14 · Track A's `ContainerTest` was put in `scripts/`, but CI's required "Track tests seen red" lists test ids from `tests/` only (`scripts/track-red.py`, `LIST_TESTS`) and `scripts/seen-red.py` reads only `tests/`, so C14.2's and C14.3's tests would match no test there and the track could not merge (fixed in a spec-change PR before Track A: the file is `tests/test_token_usage_container.py`).
- **Defect** D14.32 — found: Track C1 · cause: spec · made: Day 14 · C14.8's and C14.16's `Test:` was Verify's `git grep`, but CI's required "Track tests seen red" fails a `new` criterion whose `Test:` names no test in backticks (`scripts/track-red.py`), so neither picker track could merge; the auditors' three runs and D14.31's fix, the same check's other half, did not catch it (fixed in a spec-change PR after Track C1's code: `PickerGoneTest` in `tests/test_picker_gone.py`).
- **Defect** D14.33 — found: auditor · cause: spec · made: Day 14 · the recheck of D14.32's fix: C2 now adds to a file C1 creates though the spec said the tracks do not depend on each other; a test asserting only an empty list passes when `git grep` fails outside a repository (exit 128, nothing printed); C14.16's "the same" did not carry the spelling in parts; and C1's break ran the bare grep, so it never showed the named test failing (fixed in this PR: C1 lands first, exit code 1 asserted, each test spelled out, each break on its test).
- **Defect** D14.34 — found: self · cause: spec · made: Day 4 · the count run's first two step sessions on bearing (Day 14's close, #108; Day 15 Track A, #116) opened their pull request and then ended with a `PARK:` line, as bearing's `CLAUDE.md` says after any pull request, and `outcome()` lets a `PARK:` win over a pull request; `rules/session.md` said when to park but not to end without one after a pull request, so the driver counted neither and the count stayed at 1 of 15 (fixed in this PR and Track E: C14.19).
- C13.15, still in force, says `rules/session.md` "changes only by C13.14's line": from Track E
  it reads "by C13.14's and C14.19's lines". No `Replaces: C13.15`, since `invariants.py` lifts a
  replaced hold's freeze when the spec merges, and C13.15's diffs name no `rules/` path.
- Assumed: a step session follows `rules/session.md`'s new line over the project's `CLAUDE.md`
  (the `claude` CLI appends the rules to the system prompt; no test can show the model obeys).
  The count run after Track E checks it: the `outcome` of its first step's `end` line in
  `state/run.jsonl` (`python run-steps.py status` shows it) starts "opened: #" (`driver/once.py`),
  not "park: the session parked: " followed by the session's own words, which for #108 and #116
  named the open pull request; the record's Parks section says which | checked by the count run on
  `10b3d9d`: no step session after it ended with a `PARK:` line after opening its pull request.
  The first (57665251, Day 15's close) ended "park: the session ended with no pull request and
  no PARK line", since its #123 was merged by hand before its end; the next ended "opened: #127
  from `day-16/track-a-silent-successes`" (`docs/trial/run-14.jsonl`).
- **Defect** D14.35 — found: auditor · cause: spec · made: Day 14 · the recheck of D14.34's fix: Track E would delete the test Day 13's recorded break for C13.14 runs, so CI's breaks replay would fail it; C13.15's wording would go false unsaid; whether a session obeys the line was not marked Assumed; and "unedited" for `tests/test_once.py` had no check (fixed in this PR: the retire, the two Notes lines, both test files in C14.1's diff).
- **Defect** D14.36 — found: Track D · cause: spec · made: Day 14 · C14.15's regex took `pip install -e` with nothing between, but both level 2 step sessions ran `python -m pip install -q -e ".[dev]"`, and Day 22 Track A's ran it and `python -m pytest -q` in one Bash command, so "an install command, then a test command" named two commands where the transcript holds one; the transcript also holds each tool_use twice, which the copy's rule did not say (fixed in a spec-change PR before Track D: the `-q`, the order inside one command, the `assistant` record).
- **Defect** D14.37 — found: Track D · cause: spec · made: Day 14 · C14.12 took the level 2 day to start on a later local date than the count run's last session; it started 15 minutes after the count's 15th merge, on the same local date, so the "after" side mixes two level 1 pull requests with the two of level 2 and gives no level 2 figure of its own; and "the first `on` of the level 2 day" did not say which of two `on` lines it is (fixed in a spec-change PR before Track D: two lines from the copy by `status._cost`, the `on` named).
- **Defect** D14.38 — found: auditor · cause: spec · made: Day 14 · the recheck of D14.36's and D14.37's fixes: `count run alone:` named two of the four sessions whose pull request has no `merged` line (#123 and #139 were left out) and not #101's opener; "level 2 from:" took any `on` line; "The level 2 day says so" had no check and the Goal still read "one whole day"; the Cost section set two measures side by side unsaid; the install's order was checked only for the session it did not name; a level 2 step took the reviewer's `start` lines; "every tool_use" was most; "16 minutes" was 15; and the reviewer-transcript Assumed line still read "not run" (fixed in this PR).
- **Defect** D14.39 — found: auditor · cause: spec · made: Day 14 · the second recheck: "the last `on` line" holds only until the next `on`, since the copies had a first line and no last; with "when they differ" gone, a later test command as line 3 passed with no order checked; the Assumed line lost its "→" and version; "the CLI's total" was more than `driver/once.py` shows; and "by hand" was written as if the data showed it (fixed in this PR; these last fixes were read by no auditor).
- **Defect** D14.70 — found: rehearsal · cause: spec · made: Day 14 · C14.4's hold, `scripts/test_token_usage.py` passes, failed CI's rehearsal of the close on Linux: `test_transcript_past_max_path_is_counted` builds a folder whose length is the temporary root's and the checkout's name plus 212, and in the rehearsal's short `/tmp/rehearsal-…` worktree it came to 250, not past 260 ("AssertionError: 250 not greater than 260"); on this PC the paths are longer, so the local rehearsal passed; C14.1 froze the file (fixed in a spec-change PR before the close: the folder padded past 260 wherever the checkout is, C14.4 allows those four lines, C14.1's diff and break leave the file out).
- **Hand-off** H14.1 → the maintainer: a live reviewer's `in progress:` line names the step's sentence with "no estimate", since `_kind("review")` is `None`; giving the reviewer an estimate of its own is not asked for.
- The close. The count run reached "level 2: 15 of 15" at bearing #151; the level 2 day was
  bearing's Day 22, from its Track A: two step sessions and two reviews, 0 blockers each. The
  maintainer merged #153 by hand a second after its review, so the driver's one merge is #154,
  the day's closing PR, on the head the reviewer saw; its evidence run 44965577837 concluded
  `success` (`docs/trial/day-14.md`). H09.2 is answered "not met": no session met the usage
  limit. H10.2 by C14.2, H12.3 by C14.5 and C14.6 (with H14.1), H13.1 by The install, H13.2 by
  The first merge.
- Known limits, with no test: the `refusals.json` rows are quoted but not copied, so
  `test_every_refusal_named` needs one row for a trial date, not every row (#273); Track 0's break
  reaches only `test_no_reviewer_line_without_review`'s first assertion, and its last (no line
  starts "reviewer") has none of its own (#263, found by the track-reviewer on the diff; C14.6's
  breaks cover the reviewer line).
- **Defect** D14.40 — found: track-reviewer · cause: process · made: Day 14 · Track A's C14.3 test reported, on `main`, argparse's whole usage text and a temporary path that differs by OS, which no recorded red can hold (fixed in #265: a short fixed sentence).
- **Defect** D14.41 — found: break on purpose · cause: process · made: Day 14 · Track A's `-work` test reported its list diff shortened to "[40 chars]", which `break.py` refuses (fixed in #265: the test names the whole list).
- **Defect** D14.42 — found: track-reviewer · cause: process · made: Day 14 · Track B's brief ran one `seen-red.py --expect` with an alternation, so one test's red would have passed all three and its one line named one red (fixed before the implementer ran: once per test).
- **Defect** D14.43 — found: track-reviewer · cause: process · made: Day 14 · Track B's brief redefined `T2` and `T3`, which `tests/test_status.py` already has (fixed before the implementer ran: imported).
- **Defect** D14.44 — found: review · cause: implementation · made: Day 14 · Track B's length guard before the reviewer line's check made that break report "1 not greater than or equal to 2" (fixed in #266: removed; the break reports the `level 2:` line in the reviewer's place).
- **Defect** D14.45 — found: review · cause: implementation · made: Day 14 · Track B's module docstring's new clause ran past the file's width (fixed in #266).
- **Defect** D14.46 — found: track-reviewer · cause: process · made: Day 14 · Track B's PR body said `seen-red.py` reports only `AssertionError` lines; it falls back through `break.py`'s list of failure lines (fixed in #266).
- **Defect** D14.47 — found: track-reviewer · cause: process · made: Day 14 · Track C1's first build's break report held a line number (`dashboard.js:873`), which moves with any edit above it (fixed in #268: `git grep -l`).
- **Defect** D14.48 — found: track-reviewer · cause: implementation · made: Day 14 · Track C1's test's `subprocess.run` had no `check=False`, which `ruff check` refuses (PLW1510) (fixed in #268).
- **Defect** D14.49 — found: track-reviewer · cause: process · made: Day 14 · Track C1's PR body did not say the replaced criterion's break no longer applies (fixed in #268).
- **Defect** D14.50 — found: track-reviewer · cause: process · made: Day 14 · Track C2's brief gave an expected red unittest shortens to "[40 chars]", which `seen-red.py` refuses (fixed before the implementer ran: `len(files)` asserted, the list as its message).
- **Defect** D14.51 — found: track-reviewer · cause: process · made: Day 14 · Track C2's brief said to remove the imports ruff flags, which would have removed older unused imports in `scripts/` that ruff flagged on `main` already (fixed before the implementer ran).
- **Defect** D14.52 — found: track-reviewer · cause: process · made: Day 14 · Track C2's brief invited `ruff format` on `scripts/`, whose `--check` already fails on `main` (fixed before the implementer ran).
- **Defect** D14.53 — found: track-reviewer · cause: process · made: Day 14 · Track C2's PR body's oversized count left out the break record's 3 lines (fixed in #269).
- **Defect** D14.54 — found: track-reviewer · cause: process · made: Day 14 · Track C2's PR body left out one replaced criterion, `S-how-follows-newest-day.4` (fixed in #269).
- **Defect** D14.55 — found: track-reviewer · cause: process · made: Day 14 · Track C2's PR body said the old picker breaks stop applying in it, though their finds were gone before it (fixed in #269).
- **Defect** D14.56 — found: Track C2 · cause: environment · made: none · Track C2's `pre-push.py` full run failed 7 driver test files with a build running beside it; each passed alone, and the run passed again without the build (not fixed: load, as N1's).
- **Defect** D14.57 — found: track-reviewer · cause: process · made: Day 14 · Track E's brief named the two inserts into the held text without their order; the after-PR line first would have moved the "never merge" anchor and put the install line before it (fixed before the implementer ran).
- **Defect** D14.58 — found: track-reviewer · cause: process · made: Day 14 · Track D's brief read the red in the wrong order and gave a loose `--expect` (fixed before the implementer ran).
- **Defect** D14.59 — found: track-reviewer · cause: process · made: Day 14 · Track D's brief gave failure messages holding uuids, hashes or lists, which `break.py` refuses (fixed before the implementer ran: `longMessage = False`, fixed words).
- **Defect** D14.60 — found: track-reviewer · cause: process · made: Day 14 · Track D's brief's check of the probe's output in The first merge could not fail (fixed before the implementer ran).
- **Defect** D14.61 — found: track-reviewer · cause: process · made: Day 14 · Track D's brief read the copies without allowing for `\r` on a CRLF checkout (fixed before the implementer ran).
- **Defect** D14.62 — found: track-reviewer · cause: process · made: Day 14 · Track D's brief called `runlog.late_refusals` and left its result unchecked (fixed before the implementer ran).
- **Defect** D14.63 — found: track-reviewer · cause: process · made: Day 14 · Track D's PR body said the record's Unverified section lists every fact not tested; it lists five (fixed in #273).
- **Defect** D14.64 — found: track-reviewer · cause: process · made: Day 14 · Track D's `test_evidence_section` took any merged pull request of the copy as the close, so #153 passed (fixed in #273: the level 2 day's last merge, with a break).
- **Defect** D14.65 — found: track-reviewer · cause: process · made: Day 14 · Track D's install break stopped at the literal session id and never reached the level 2 step check (fixed in #273: re-recorded on `run-14.jsonl`).
- **Defect** D14.66 — found: track-reviewer · cause: process · made: Day 14 · Track D's seen-red lines showed no red for C14.10 (fixed in #273: its line added).
- **Defect** D14.67 — found: track-reviewer · cause: implementation · made: Day 14 · Track D's test gave two read failures one message (fixed in #273).
- **Defect** D14.68 — found: Day 14 review · cause: spec · made: Day 13 · `status` prints "level: 1" whatever `driver.json`'s level (`driver/status.py`, `_report`, a line from Day 7): on the level 2 day it read "level: 1"; Day 13 added level 2 and no criterion named the line (not fixed: H14.2).
- **Defect** D14.69 — found: rehearsal · cause: spec · made: Day 14 · Verify's two `git grep` lines exit 1 when they find nothing, which is their pass, and the replay reads a bare line by its exit code, so `close-evidence.py --rehearse` failed both (fixed in the close: each ends `  # nothing, exit 1`, which `scripts/evidence.py` reads as what the line must print and exit).
- **Hand-off** H14.2 → the maintainer: `status` names the level `driver.json` gives, not "level: 1" (D14.68).
- **Hand-off** H14.3 → the maintainer: `on` at level 2 reads `main`'s protection only, so `setup-check.py`'s two failed checks on bearing ("A closed day's evidence replays", "A track's breaks replay", which bearing does not have) did not stop it; whether level 2 should need them is not asked by any criterion.
