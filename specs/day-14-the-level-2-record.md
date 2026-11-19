# Day 14 — The level 2 trial's record: the count run at level 1, one day at level 2, what the driver merged, what parked, what it cost

**Phase:** 2 · **Depends on:** Day 13 · **Expected PRs:** 8 (the spec change, Tracks 0, A, B, C1, C2, D, the close)

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

Overdue: P54 waits — the maintainer chose on 2026-11-19 that Day 14's stop settles it, after this Day's close (`specs/plan/overdue.json`, `settled_by` 15).

## Before this day (the maintainer's)
Track D cannot start until these are done. Each goes in the record's Set-up (C14.13).

- **The count run** (decided 2026-11-19). At 3f31818, `status` reads "level 2: 0 of 15 pull
  requests in a row merged without a change asked". Only container sessions count, and the
  container has run one step (bearing #101, still open). Before the count run, add days to
  bearing's plan, since it ends at its Day 14, and write their specs: the driver parks on "write
  its day spec". Then run bearing with `"level": 1` (or no `level`) and the container keys until
  `status` reads 15 of 15. That is about four bearing days.
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
  `scripts/test_token_usage_container.py`, so `scripts/test_token_usage.py` stays unedited
  (C14.1). `scripts/publish-counts.py` is not changed: the dashboard counts this repository's
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
- **The record (Track D; N25, P55, N11, N27, N28, H09.2, H13.1, H13.2).** `docs/trial/day-14.md`
  and four copies, lines as written, from the start line above: `docs/trial/run-14.jsonl`
  (`state/run.jsonl`), `docs/trial/switches-14.jsonl` (`state/switches.jsonl`, S-switch-log),
  `docs/trial/refusals-14.jsonl` (`state/refusals/hooks.jsonl`, which `status` adds as late
  refusals) and `docs/trial/install-14.jsonl`. The last holds, from one level 2 step session's
  transcript, that session's id, then the `input` of its first `Bash` tool_use that installs
  the project and of its first that runs the tests, in that order. The record has these
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
- `plan.md`'s "Unverified" items the record answers (H10.2: `token-usage.py` counting the
  container's transcripts; "No merge has used the token"): the plan-change PR after the close
  edits them, not this Day.

## Tracks

| Track | Owner | Work |
|---|---|---|
| 0 | | The hold test for `status` with no reviewer: C14.7 |
| A | | `--container` in `scripts/token-usage.py`: C14.2, C14.3 |
| B | | The reviewer's row and `_reviewer` in `driver/status.py`: C14.5, C14.6 |
| C1 | | The page's half of the picker removed: C14.16 |
| C2 | | The build's half of the picker removed: C14.8 |
| D | | After the maintainer's runs, and after A and B merge: the record, its copies and its test: C14.10–C14.15, C14.17, C14.18 |

C14.1, C14.4 and C14.9 hold today's code and are proved in the spec-change PR (their breaks in
`specs/breaks/day-14.json`). Track 0 lands
first. Tracks A to C2 do not depend on each other or on the count run, and are built while the
count run goes. Track D uses Track A's `--container` and Track B's `_reviewer`, and waits for
the level 2 day's close and its evidence run. Track C's two halves were split (about 530 lines
together, most of it the two test files): C1 is about 110 lines; C2 is about 420, all deletions
(`tests/test_how_this_works.py`'s 277 lines, `spec_drift_page.py`'s 136, `spec-drift.py`'s 4,
and the imports ruff then flags as unused), and its PR carries an `Oversized:` line saying so.
Test files, new and edited:
- 0 and B: `StatusReviewTest` in `tests/test_status_review.py` (new; `tests/test_status.py` and
  `tests/test_status_trial.py` stay unedited).
- A: `ContainerTest` in `scripts/test_token_usage_container.py` (new).
- C1: `tests/test_how_this_works_page.py` deleted. C2: `tests/test_how_this_works.py` deleted.
- D: `tests/test_trial_fourteen.py` (`TrialFourteenTest`).

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [ ] C14.1 **hold** — The driver's code other than `driver/status.py`, its hooks, rules and
      image, `scripts/test_token_usage.py`, the earlier trial records and their tests are
      unchanged since `3f31818`: Verify's `git diff` prints nothing.
      Plan: none — keeps the Day to the record and its two tools; no commitment is about it.
      broken: a driver file other than status.py edited → +"""The driver: reads a project's state and decides its step (plan.md)."""
- [ ] C14.2 **new** — `transcripts(<empty>, <r>, container=<d>)` yields the files under
      `<d>/-work/`, a main session and one under `-work/<id>/subagents/`, and not a main session
      put directly in `<d>`. `compare()` over its main sessions, with two replies dated
      2026-11-20 and splits `(2026-11-02,)`, counts 2 replies on the "after" side.
      Red today: `transcripts()` takes no `container`, a TypeError.
      Test: `ContainerTest.test_work_folder_read`, `ContainerTest.test_compare_counts_container_replies`.
      Plan: N12 "token-usage.py is pointed there"
- [ ] C14.3 **new** — `--container` with neither `--compare` nor `--tools` exits 2, and its stderr
      holds "--container needs --compare or --tools". (Exit 2 and no `--out` written are true
      today too, through argparse.)
      Red today: stderr says "unrecognized arguments: --container", not the sentence.
      Test: `ContainerTest.test_container_without_compare_or_tools_is_refused`.
      Plan: none — a refusal of a misuse; N12 is C14.2's.
- [ ] C14.4 **hold** — Without `--container`, the folders read and the figures are as today:
      `scripts/test_token_usage.py` passes, unedited since `3f31818` (C14.1).
      Plan: N12 "token-usage.py is pointed there"
      broken: the split day put on the earlier side → AssertionError: Lists differ: [50000, 60000] != [50000]
- [ ] C14.5 **new** — On a log with a step session `s1` and a review session `r1` (`start` with
      prefix "review", a `review` line with `"pr": 7`, an `end` with outcome "review: #7, 1
      blockers" and `cost_usd` 0.4), the `steps:` block's second row is exactly
      `  <r1's at> review of #7: review: #7, 1 blockers, $0.40, refusals 0, session `r1``. A
      review session with no `review` line prints "review of an unknown pull request".
      Red today: the row prints the step's sentence where "review of #7" is expected.
      Test: `StatusReviewTest.test_review_row`, `StatusReviewTest.test_review_row_without_review_line`.
      Plan: none — H12.3's display; the reviewer's cost is C14.6's.
- [ ] C14.6 **new** — On the same log with a second review session (`cost_usd` 0.3),
      `status._reviewer(records)` is `reviewer: 2 sessions, $0.70, in the cost above`, and it is
      the line right after `cost:` in the block, whose total still includes both.
      Red today: `status` has no `_reviewer`, an AttributeError.
      Test: `StatusReviewTest.test_reviewer_cost_line`.
      Plan: P55 "with the reviewer session counted in"
- [ ] C14.7 **hold** — A log with no review `start` line prints the `status` block as before: the
      line after `cost:` is the `level 2:` line, and `tests/test_status.py` and
      `tests/test_status_trial.py` pass, unedited since `3f31818` (C14.1).
      Test: `StatusReviewTest.test_no_reviewer_line_without_review` (Track 0). Its break, in Track
      0's PR: a line put before the `level 2:` line, find `lines.append(_level_2(records))` in
      `driver/status.py`, which Track B leaves occurring once (it adds `_reviewer`'s line before it).
      Plan: none — Days 7 and 8's `status` output is kept; it serves no Day 14 commitment.
- [ ] C14.8 **new** — The build's half of the picker is gone: `git grep -n -w -e how_excerpts -e
      how_excerpts_of -e how_specs -e how_this_works -e HOW_TEMPLATE -e HOW_REPLAY -e HOW_PLAN -e
      HOW_PLAN_PARTS -e HOW_NEEDED -e HOW_NO_PROMISE -- scripts tests` prints nothing.
      Red today: the grep finds lines in `scripts/spec_drift_page.py`, `scripts/spec-drift.py`
      and `tests/test_how_this_works.py`.
      Test: Verify's first `git grep` (`--expect-stdout '\A\Z'` at the break).
      Replaces: S-how-follows-newest-day.1 — was: a promise whole at every other step is picked though the replay history holds no row for it.
      Replaces: S-how-follows-newest-day.3 — was: a replay history that has gone leaves the pick alone and shows as missing.
      Replaces: S-how-follows-newest-day.4 — was: a promise missing any other step of its record is still skipped.
      Plan: none — the maintainer's choice in #259 ("views go, picker stays") left code that nothing draws.
- [ ] C14.9 **hold** — The page still builds and draws its graphs, the file map with `howBlob`
      included: `scripts/test_dashboard_page.py` and `tests/test_dashboard_files.py` pass.
      Plan: none — the dashboard's views are not commitments of `plan.md`.
      broken: the helper the file map links by removed with the picker → AssertionError: Tuples differ: ('howBlob is not defined', []) != (None, [])
- [ ] C14.10 **new** — The trial ran at level 2. The test builds a temporary state folder from the
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
- [ ] C14.11 **new** — The record names every merge the driver made (Merges: each `"by":
      "driver"` line's pull request, time and head), every park (Parks: its time and line, and
      `status`'s "parks by reason" lines on the copy), and every refusal (Refusals: each `refused`
      entry's tool and input, each line of `docs/trial/refusals-14.jsonl`, and the
      `refusals.json` rows on the `dashboard-data` branch for the trial's dates, quoted). The
      sections come in the order In scope gives.
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_every_driver_merge_named`, `TrialFourteenTest.test_every_park_named`,
      `TrialFourteenTest.test_every_refusal_named`, `TrialFourteenTest.test_sections_in_order`.
      Plan: N25 "and the record names every merge the driver made, every park and every refusal"; N28 "this repository's refusals.json on the dashboard-data branch"; P55 "parks by reason"
- [ ] C14.12 **new** — The Cost section holds `status`'s `cost:` line and `_reviewer`'s line as
      they come out on the copy (the test calls them). It also holds the two sides of
      `token-usage.py --compare --transcripts <an empty folder> --repo ../bearing --container
      <state>/claude/projects --split <the level 2 day's first local date>`, quoted: "between"
      (the Day 10 step's one session and the count run, level 1) and "after" (level 2). For each
      side it gives the cost per merged pull request (the side's cost divided by its pull
      requests, worked by hand as Day 8's record did) beside "(baseline $1.86)", and the replies
      per merged pull request the side prints beside "(baseline 34.4)". `../bearing`'s `main` is
      pulled first (`merged_prs` reads the local `main`), and the record names the merged pull
      requests on each side that no container session opened (the plan and spec PRs merged by
      hand). The level 2 day starts on a later local date than the count run's last session, so
      no level 1 session falls on the "after" side; if one does, the record names it.
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
      "conclusion: success". The copy holds a `merged` line for that pull request. It also gives
      "escapes: <n>" for the level 2 day (`plan.md`, "Back one level"): each Defect line of
      bearing's spec for that day found at `close`, by the `dashboard` or in a `Day NN review`,
      and each evidence run after one of its merges whose conclusion is not success, quoted one
      per line, and <n> their count.
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_evidence_section`, `TrialFourteenTest.test_escapes_counted`.
      Plan: N25 "closed with its evidence replay green"; P55 "escapes per day"
- [ ] C14.15 **new** — The hand-offs are answered from the copies. The usage limit (H09.2): the
      section says "met", with the transcript record and the `result` quoted, when any line of
      `run-14.jsonl` holds "usage limit", and "not met" only when none does. The install (H13.1):
      `docs/trial/install-14.jsonl` holds a session id that starts a level 2 step in the copy,
      then an install command holding bearing's CI install, `pip install -e ".[dev]"`
      (`.github/workflows/evidence.yml`, line 30 at 714412f; The install quotes that line at the
      commit the Set-up names), then a test command, in that order, and The install quotes both.
      A level 2 step is a `start` line of the copy at or after the Set-up's "level 2 from: <time>"
      (the first `on` of the level 2 day in `switches-14.jsonl`): the run log writes no level.
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_usage_limit_follows_the_copy`, `TrialFourteenTest.test_install_before_tests`.
      Plan: N10 "installs the project as CI does before running its tests"
- [ ] C14.16 **new** — The page's half of the picker is gone: `git grep -n -w -e howRecheck -e
      howHas -e howMissing -e howExcerpt -- docs/dashboard scripts tests` prints nothing, and
      `howBlob` is still defined in `docs/dashboard/dashboard.js` (C14.9).
      Red today: the grep finds lines in `docs/dashboard/dashboard.js` and
      `tests/test_how_this_works_page.py`.
      Test: Verify's second `git grep` (`--expect-stdout '\A\Z'` at the break).
      Replaces: S-how-follows-newest-day.2 — was: step 7 says "not re-checked yet" for an empty record.
      Plan: none — the same leftover as C14.8, on the page.
- [ ] C14.17 **new** — The reviewer section names each `review` line of the copy: its pull
      request, its head and its blocker count, and the reviewer's PR comment's URL, taken from
      `gh pr view <n> --repo Yusuprozimemet/bearing --json comments` (the run log writes none):
      `https://github.com/Yusuprozimemet/bearing/pull/<n>#issuecomment-<digits>`, or "no comment"
      with the reason, since a failed comment shows only on `on`'s output ("review: no comment
      on #<n>").
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_every_review_named`.
      Plan: none — "what the reviewer found" is `plan.md`'s Day 14 line, held by no commitment.
- [ ] C14.18 **new** — The first merge (H13.2) names the first `"by": "driver"` line's pull
      request and head, and quotes the red-check probe's command, output and exit code.
      Red today: `docs/trial/day-14.md` does not exist.
      Test: `TrialFourteenTest.test_first_merge`.
      Plan: N25 "and the record names every merge the driver made, every park and every refusal"

## Verify
```bash
python -m unittest tests.test_status_review tests.test_status tests.test_status_trial tests.test_dashboard_files tests.test_trial_fourteen tests.test_trial_record tests.test_trial_ten -v
python -m unittest scripts.test_token_usage scripts.test_token_usage_container scripts.test_dashboard_page -v
git -c core.safecrlf=false diff --exit-code 3f31818 -- driver/__init__.py driver/box.py driver/config.py driver/decide.py driver/github.py driver/home.py driver/issues.py driver/livecheck.py driver/lock.py driver/loop.py driver/once.py driver/preflight.py driver/review.py driver/runlog.py driver/settings.py driver/steps.py driver/stream.py driver/switches.py driver/switchlog.py driver/tree.py run-steps.py hooks rules docker scripts/test_token_usage.py tests/test_status.py tests/test_status_trial.py tests/test_trial_record.py tests/test_trial_ten.py docs/trial/day-08.md docs/trial/day-10.md docs/trial/run.jsonl
git grep -n -w -e how_excerpts -e how_excerpts_of -e how_specs -e how_this_works -e HOW_TEMPLATE -e HOW_REPLAY -e HOW_PLAN -e HOW_PLAN_PARTS -e HOW_NEEDED -e HOW_NO_PROMISE -- scripts tests
git grep -n -w -e howRecheck -e howHas -e howMissing -e howExcerpt -- docs/dashboard scripts tests
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
  `<state>/claude/projects/-work/<session>.jsonl`, its subagents under `<session>/subagents/`:
  `find state/claude/projects/-work` → `2d6771a4-63cb-4a41-b0ef-3da00a7fc3fb.jsonl` and
  `2d6771a4-…/subagents/agent-aa71599a54a3f2719.jsonl` with its `.meta.json` (2.1.322).
- **Assumed** — a reviewer started with `--agents <file> --agent reviewer` in the container leaves
  its transcript as a main session under `-work`, not under `subagents/`, so C14.12 counts it |
  not run: no review has run in the container; the main session checks it with `find
  state/claude/projects/-work` after the level 2 day, before Track D.
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
- **Defect** D14.25 — found: auditor · cause: spec · made: Day 14 · the recheck: C14.17's comment URL had no source in the copies and no result for a failed comment, and its review half's `Plan:` N25 does not hold "what the reviewer found" (fixed in this PR: the URL from `gh pr view`, C14.17 split into C14.17, `Plan: none`, and C14.18).
- **Defect** D14.26 — found: auditor · cause: spec · made: Day 14 · the recheck: C14.1 was said proved in this PR with no `broken:` line, and C14.7 named no break Track B leaves applying (fixed in this PR: C14.1's break recorded, C14.7's find named).
- **Defect** D14.27 — found: auditor · cause: spec · made: Day 14 · the recheck: the reviewer-transcript Assumed line named no one who checks it, and H10.2's "Unverified" items in `plan.md` were left with no owner (fixed in this PR: the main session before Track D; the plan-change PR after the close).
- **Hand-off** H14.1 → the maintainer: a live reviewer's `in progress:` line names the step's sentence with "no estimate", since `_kind("review")` is `None`; giving the reviewer an estimate of its own is not asked for.
