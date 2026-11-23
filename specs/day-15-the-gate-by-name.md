# Day 15 — The level 2 gate by name: the kit's nine checks, `waived_checks`, and `status`'s level and reviewer lines

**Phase:** 3 · **Depends on:** Day 14 · **Expected PRs:** 5 (the spec change, Tracks A, B, C, the close)

## Goal
`on` at level 2 starts only when `main` requires a pull request, allows no bypass and requires
each of the kit's nine checks by name, less those `waived_checks` in `driver.json` names; `on`
prints each waived check and the switch log's `on` line names them. `status` prints the level
`driver.json` names, and a running review shows its pull request and an estimate of its own
(`plan.md`, Levels, "The kit's checks"; Phase 3's Day 15; H14.1, H14.2, H14.3).

## In scope

Decided by the maintainer on 2026-11-22, where `plan.md` and the hand-offs leave it open:
- `status` with `--project` reads no config, as today (`run-steps.py:150`), and prints "level: 1"
  as it does now; with a config read, it prints the config's `level`, 1 when absent. C07.17 and
  C08.2 stand unedited.
- A running review is its own kind: its `start` line records the pull request, and `status`'s
  `running:` line estimates it from earlier reviews, as a track's is from earlier tracks.
- A start refused for missing checks names all of them in one line, in the kit's order.

- **The kit's checks (Track A; N38, H14.3).** `driver/github.py` gains `KIT_CHECKS`, a tuple of the
  nine names of `plan.md`'s Levels in that order, which is `scripts/setup-check.py`'s `REQUIRED`
  (`setup-check.py:30-40`); C15.5 ties the two. `protection(project, gh, waived=())` reads the
  required names as `setup-check.py:109-113` does: the classic protection's
  `required_status_checks.contexts` and `.checks[].context`, and each `required_status_checks`
  rule's `parameters.required_status_checks[].context`. A name counts only from a source whose
  state is "free" (`github.py:234`, `249-252`). Its reasons keep today's order (`github.py:264-281`):
  no pull request, no checks, a hidden bypass list, a bypass; then, last, the kit's checks not
  required and not in `waived`, as one reason: `main does not require "<name>", "<name>"`, in
  `KIT_CHECKS`'s order. Edge inputs: a waived name `main` does require changes nothing; a name only
  a hidden or bypassable source requires is missing; the project's own checks beyond the nine
  (`tests`) are neither needed nor refused. The shared `protected` fixture
  (`tests/test_level_2_start.py:40`) names the nine and `tests` in this track, since its
  `["tests"]` is refused from here on (C15.14). No file under `driver/` names `setup-check`, in
  code or a comment (C15.5).
- **`waived_checks` (Track B; N38, N39).** An optional key of `driver.json`: a list of distinct
  names, each one of `KIT_CHECKS`. Absent is `[]`. Anything else is one line from
  `config.problems`: `cannot start: <path>'s waived_checks must be a list of the kit's check names,
  each once`. At level 2, `level_2_refusals` passes it to `protection`; once the four conditions
  hold, `on` prints on stdout, before the session, one line per waived name in the config's order,
  `level 2: waived check "<name>"`, and the switch log's `on` line becomes
  `{"event": "on", "waived_checks": [<the names>]}` (`at` aside). With none waived (`[]` or
  absent), or at level 1, the `on` line stays `{"event": "on"}` (S-switch-log.3): `loop.py`
  passes `waived_checks` only when it names a check, since `switchlog.append` leaves out `None`
  and not `[]` (`switchlog.py:22`), and `driver/switchlog.py` stays unedited (C15.16). Level 1
  prints no waived line and reads no protection.
- **`status`'s level (Track C; P62, H14.2).** `status.run` gains `level=1`; `run-steps.py` passes
  the config's `level` (1 when absent) when it read a config, and nothing with `--project`.
  `_report`'s second line is `level: <level>` (today the literal, `status.py:43`).
- **A running review's own line (Track C; P62, H14.1).** `review.run`'s `runlog.start` call
  (`review.py:134`) passes `pr=<number>`, and `runlog.start` writes `"pr"` after `"claude"` when
  given (`runlog.py:25`). `_kind("review")` is "review" (`status.py:230`). `_in_progress` names a
  review session `review of #<pr>`, from its start line's `pr`, else its newest `review` line's
  (`_review_of`, `status.py:328`), else "review of an unknown pull request" (old run logs). So a
  live review reads `in progress: review of #12 (session `<id>`), cost so far $0.00` and
  `running: <t> (no estimate: 0 earlier review sessions)`, and with three earlier ended reviews,
  `(estimate <m>, the median of 3 earlier review sessions)`. The heartbeat comment shows the same
  `running:` line (`live_lines`, `status.py:163-166`); its header stays the start line's `step`
  (`once.py:320-321`), unchanged. A track's estimate still counts no review (C15.13).

## Out of scope
- `level` 3 in `driver.json` (`config.is_level`, C13.1) — Day 16's spec (H15.1).
- Keeping a lowered level after an escape, and which level `status` then prints — Day 16 (H15.2).
- The plan-auditor's verdict line and its place ("first" or "last") — Day 17 (H15.3).
- Whether the fine-grained token can read `main`'s protection — the maintainer (H15.4).
- Running `setup-check.py` from the driver: `plan.md` says the driver reads the names itself.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | C15.1–C15.5, C15.7, C15.14 |
| B | | C15.6, C15.8, C15.9, C15.15, C15.17 |
| C | | C15.10–C15.13 |

B uses Track A's `KIT_CHECKS` and `waived`, so it follows A. C stands alone and may run before B.
No Track 0: each hold's break needs its track's code, so each hold's test lands with its track.
C15.16 holds today's code and is proved in this spec-change PR, whose `Replaces:` lifts Day 14's
freeze on the six driver files the tracks edit.

No red or break report may hold "[N chars]", which `seen-red.py` and `break.py` refuse and which
unittest makes of a long string, list or dict in `assertEqual`. So:
- Tests of `protection`'s reason (C15.1–C15.3) assert, in order: the reason is not `None`
  (`assertIsNotNone`, "unexpectedly None" today), its text before the first ` "`, the number of
  names, then the names as a list. A `None` expected (C15.2's first half, C15.4's
  `test_ruleset_names` and `test_classic_forms`) is asserted with `assertIsNone`, which prints the
  reason whole.
- Tests of `on`'s results and of `config.problems` (C15.6, C15.7, C15.8, C15.17) compare through
  `same` (`tests/test_review_loop.py`), field by position, as `LevelStartTest`'s cases do with
  `refused()`, so the report names the fields that differ ("differs: 0, …"). C15.7's red is
  "differs: 0, 1, 2, 3" (the exit code, the stderr line, the session and the issue); its api
  field compares only the calls before the first issue, as `test_starts_when_all_hold` does, so a
  heartbeat PATCH cannot add a field.

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [x] C15.1 **new** — `github.protection` on the fake `gh`, for C13.3's `test_classic` set-up with
      its checks only `tests` (classic `contexts` `["tests"]`, `checks` `[{"context": "tests"}]`),
      gives `main does not require "Description uses the template", "Diff stays reviewable",
      "Branch, title, commits and Jira keys agree", "Frozen files stay unedited", "Dashboard metric
      tests gate", "Criteria keep their wording", "A closed day's evidence replays", "Track tests
      seen red", "A track's breaks replay"`. With the other eight and `tests` required, "A track's
      breaks replay" left out, it gives `main does not require "A track's breaks replay"`. Red
      today: `None` for both.
      Test: `KitChecksTest.test_only_the_projects_tests`, `KitChecksTest.test_one_missing`
      (`tests/test_kit_checks.py`).
      Replaces: C13.3 — was: `protection` gave `None` when `main` required a pull request and any check, by no name, from a source with no bypass.
      Plan: N38 "requires each of the kit's nine checks by name, unless `waived_checks` in `driver.json` names it"
      Evidence: `KitChecksTest.test_only_the_projects_tests` and `KitChecksTest.test_one_missing` pass on `main` at `9d9be8e` (#281).
      seen red: python -m unittest tests.test_kit_checks.KitChecksTest.test_only_the_projects_tests tests.test_kit_checks.KitChecksTest.test_one_missing tests.test_kit_checks.KitChecksTest.test_bypassable_check on main → AssertionError: unexpectedly None (#281)
- [x] C15.2 **new** — `protection(..., waived=("A track's breaks replay",))` on the set-up of
      C15.1's second case gives `None`; with `waived` naming "Track tests seen red" instead, it
      gives `main does not require "A track's breaks replay"`. Red today: `protection` takes no
      `waived`, a TypeError.
      Test: `KitChecksTest.test_waived`.
      Plan: N38 "unless `waived_checks` in `driver.json` names it"
      Evidence: `KitChecksTest.test_waived` passes on `main` at `9d9be8e` (#281); its red on `main` was the spec's TypeError, which `seen-red.py` prints as unittest's last line.
      seen red: python -m unittest tests.test_kit_checks.KitChecksTest.test_waived on main → FAILED (errors=1) (#281)
- [x] C15.3 **new** — A kit check only a source with a bypass requires is missing: ruleset 7
      (`bypass_actors` `[]`) requires the pull request and eight of the nine, and a classic
      protection with `enforce_admins` false requires the ninth, "Frozen files stay unedited":
      `protection` gives `main does not require "Frozen files stay unedited"`. Red today: `None`.
      Test: `KitChecksTest.test_bypassable_check`.
      Plan: N38 "requires each of the kit's nine checks by name"
      Evidence: `KitChecksTest.test_bypassable_check` passes on `main` at `9d9be8e` (#281).
      seen red: python -m unittest tests.test_kit_checks.KitChecksTest.test_only_the_projects_tests tests.test_kit_checks.KitChecksTest.test_one_missing tests.test_kit_checks.KitChecksTest.test_bypassable_check on main → AssertionError: unexpectedly None (#281)
- [x] C15.4 **hold** — C13.3's ten `ProtectionTest` cases, their checks the nine and `tests`
      (`CHECKS` in `tests/test_merge_gh.py` and the rules' `parameters`), give C13.3's answers;
      the nine required only as ruleset 7's rule `parameters.required_status_checks[].context`
      (classic 404) give `None`, as do the nine split between classic `contexts` (five) and
      `checks[].context` (four). True today: `protection` reads no names.
      Test: `ProtectionTest`, `KitChecksTest.test_ruleset_names`, `KitChecksTest.test_classic_forms`.
      Its break, in Track A: the names read from `contexts` alone. Day 13's break "C13.3: a bypass
      read as protection" (find `    if blocked:`, `ProtectionTest.test_bypass`) reaches the names'
      reason under Track A's code, a report unittest shortens: Track A retires it in
      `specs/breaks/day-13.json` (`break.py --retire`) and records it again under this criterion,
      with `test_bypass` comparing the reason's text before the first ` "`, so its report is
      `AssertionError: 'main does not require' != 'main allows a bypass'`.
      Plan: N15 "main requires a pull request with no bypass"
      Evidence: `ProtectionTest`, `KitChecksTest.test_ruleset_names` and `KitChecksTest.test_classic_forms` pass on `main` at `9d9be8e`; its breaks recorded in #281, Day 13's C13.3 break retired there.
      broken: a bypass read as protection (C15.4) → AssertionError: 'main does not require' != 'main allows a bypass'
      broken: the names read from contexts alone (C15.4) → AssertionError: 'main does not require "Criteria keep their wording", "A closed day\'s evidence replays", "Track tests seen red", "A track\'s breaks replay"' is not None
- [x] C15.5 **new** — `github.KIT_CHECKS` equals `scripts/setup-check.py`'s `REQUIRED`, loaded
      by path, item for item. Red today: `github` has no `KIT_CHECKS`, an AttributeError. After the
      names, the same test asserts that no file under `driver/` names `setup-check` or
      `setup_check` (`git grep` exits 1): a grep for what is absent today, standing in for "does not
      run", and not seen red on its own.
      Test: `KitChecksTest.test_the_kits_nine`.
      Plan: N38 "the driver reads them itself and does not run setup-check.py"
      Evidence: `KitChecksTest.test_the_kits_nine` passes on `main` at `9d9be8e` (#281), and `git grep -l -e setup-check -e setup_check -- driver/` exits 1 there; its red on `main` was the spec's AttributeError. The grep half is not seen red on its own, as the criterion says.
      seen red: python -m unittest tests.test_kit_checks.KitChecksTest.test_the_kits_nine on main → FAILED (errors=1) (#281)
- [x] C15.6 **new** — `config.problems` gives `cannot start: <path>'s waived_checks must be a
      list of the kit's check names, each once` for `"A track's breaks replay"` (a string),
      `["nope"]` and `["Track tests seen red", "Track tests seen red"]`; and no line for `[]`,
      for the nine, and with the key absent. Red today: no line for the three bad values.
      Test: `WaivedConfigTest.test_not_a_list`, `WaivedConfigTest.test_unknown_name`,
      `WaivedConfigTest.test_twice` (`tests/test_waived_config.py`).
      Plan: N38 "unless `waived_checks` in `driver.json` names it"
      Evidence: `WaivedConfigTest.test_not_a_list`, `WaivedConfigTest.test_unknown_name` and `WaivedConfigTest.test_twice` pass on `main` at `9d9be8e` (#282); its break recorded in #282, beyond the spec's breaks, after the diff review.
      seen red: python -m unittest tests.test_waived_config on main → AssertionError: differs: 0 (#282)
      seen red: python -m unittest tests.test_waived_config.WaivedConfigTest.test_not_a_list on main → AssertionError: differs: 0, 2 (#282)
      broken: waived_checks not required to be a list (C15.6) → AssertionError: differs: 2
- [x] C15.7 **new** — `on` with `level` 2, the other three conditions holding, and the fake
      classic protection requiring the pull request and `tests` with `enforce_admins` true, exits 2
      with `cannot start: level 2 needs main to require a pull request and its checks with no
      bypass: main does not require "Description uses the template", …` (the nine, as C15.1),
      starts no session and creates no issue. Red today: the session starts, "differs: 0, 1, 2, 3". (In Track A: once
      `protection` refuses, `level_2_refusals` passes its reason on unchanged.)
      Test: `LevelStartTest.test_needs_the_kits_checks`.
      Replaces: C13.7 — was: `on` at level 2 started once `main` required a pull request and any check with no bypass.
      Plan: N15 "the level 2 merge is switched on in a run, and refuses otherwise"; N38 "requires each of the kit's nine checks by name"
      Evidence: `LevelStartTest.test_needs_the_kits_checks` passes on `main` at `9d9be8e` (#281).
      seen red: python -m unittest tests.test_level_2_start.LevelStartTest.test_needs_the_kits_checks on main → AssertionError: differs: 0, 1, 2, 3 (#281)
- [x] C15.8 **new** — `on` with `level` 2, `waived_checks` `["A track's breaks replay", "A closed
      day's evidence replays"]` and the fake requiring the other seven and `tests`, starts its
      session; its stdout holds `level 2: waived check "A track's breaks replay"` then `level 2:
      waived check "A closed day's evidence replays"`, before the session's start, and the switch
      log's first line is `{"event": "on", "waived_checks": ["A track's breaks replay", "A closed
      day's evidence replays"]}` (`at` aside). Red at Track B's start (after
      Track A): `on` exits 2 with `cannot start: level 2 needs main to require a pull request and
      its checks with no bypass: main does not require "A closed day's evidence replays", "A
      track's breaks replay"`, the waived key unread.
      Test: `LevelStartTest.test_waived_printed_and_logged`.
      Plan: N39 "`on` prints each check `waived_checks` names and the switch log's `on` line names them"
      Evidence: `LevelStartTest.test_waived_printed_and_logged` passes on `main` at `9d9be8e` (#282).
      seen red: python -m unittest tests.test_level_2_start.LevelStartTest.test_waived_printed_and_logged on main → AssertionError: differs: 0, 1, 2, 3 (#282)
- [x] C15.9 **hold** — At level 1, `waived_checks` `["A track's breaks replay"]` changes nothing:
      `on` makes no call to `branches/main/protection` or `rules/branches/main` (the heartbeat's
      `api --method PATCH` calls aside), prints no `level 2: waived` line, and its switch log's `on` line is
      `{"event": "on"}`. True today: `on` reads no `waived_checks`.
      Test: `LevelStartTest.test_level_1_ignores_waived`.
      Its break, in Track B: the waived lines printed at any level.
      Plan: none — level 1 is unchanged by this Day; the hold keeps the waiver to level 2.
      Evidence: `LevelStartTest.test_level_1_ignores_waived` passes on `main` at `9d9be8e`; its break recorded in #282.
      broken: the waived lines printed at any level (C15.9) → AssertionError: differs: 1, 2
- [x] C15.10 **new** — `run-steps.py status --config <c>`, `<c>` naming the fake project with
      `level` 2, prints `level: 2` as its second line; with `level` absent, `level: 1`. Red today:
      `level: 1` for both.
      Test: `StatusLevelTest.test_config_level` (`tests/test_status_level.py`).
      Plan: P62 "the mode, the level"
      Evidence: `StatusLevelTest.test_config_level` passes on `main` at `9d9be8e` (#283).
      seen red: python -m unittest tests.test_status_level.StatusLevelTest.test_config_level on main → AssertionError: 'level: 1' != 'level: 2' (#283)
- [x] C15.11 **new** — After a review on the fake `claude` (`tests/test_review_loop.py`'s set-up)
      of #12, the run log's `start` line with `prefix` "review" holds `"pr": 12`. Red today: no
      `pr` key.
      Test: `ReviewStartTest.test_start_names_the_pr` (`tests/test_review_start.py`).
      Plan: P62 "the step in progress and its cost so far"
      Evidence: `ReviewStartTest.test_start_names_the_pr` passes on `main` at `9d9be8e` (#283).
      seen red: python -m unittest tests.test_review_start.ReviewStartTest.test_start_names_the_pr on main → AssertionError: Lists differ: ['no pr key'] != [12] (#283)
- [x] C15.12 **new** — `status` on a log whose live session (a child the test starts) has a
      `start` line with `prefix` "review" and `pr` 12 prints `in progress: review of #12 (session
      `r1`), cost so far $0.00` and a `running:` line ending `(no estimate: 0 earlier review
      sessions)`; with three earlier ended reviews of 600, 1200 and 2400 s, ending `(estimate
      20m00s, the median of 3 earlier review sessions)`; with no `pr` key and no `review` line,
      `in progress: review of an unknown pull request (session `r1`), cost so far $0.00`; with no
      `pr` key and a `review` line for #12 from that session, `in progress: review of #12`. In each
      fixture the start line's `step` is a track's step, as `review.run` passes it, so the
      step's sentence never reads "review of #12" by itself. Red
      today: the step's sentence, and `(no estimate: the step has no kind)`.
      Test: `ReviewProgressTest.test_live_review_line`, `ReviewProgressTest.test_review_estimate`,
      `ReviewProgressTest.test_no_pr_on_the_start`, `ReviewProgressTest.test_pr_from_review_line`
      (`tests/test_review_progress.py`).
      Plan: P62 "the step in progress and its cost so far"
      Evidence: `ReviewProgressTest.test_live_review_line`, `ReviewProgressTest.test_review_estimate`, `ReviewProgressTest.test_no_pr_on_the_start` and `ReviewProgressTest.test_pr_from_review_line` pass on `main` at `9d9be8e` (#283).
      seen red: python -m unittest tests.test_review_progress.ReviewProgressTest.test_live_review_line on main → AssertionError: 'in progress: Day 15 Track C (session `r1`), cost so far $0.00' != 'in progress: review of #12 (session `r1`), cost so far $0.00' (#283)
      seen red: python -m unittest tests.test_review_progress.ReviewProgressTest.test_review_estimate on main → AssertionError: 'no estimate: the step has no kind)' != 'estimate 20m00s, the median of 3 earlier review sessions)' (#283)
      seen red: python -m unittest tests.test_review_progress.ReviewProgressTest.test_no_pr_on_the_start on main → AssertionError: 'in progress: Day 15 Track C' != 'in progress: review of an unknown pull request' (#283)
      seen red: python -m unittest tests.test_review_progress.ReviewProgressTest.test_pr_from_review_line on main → AssertionError: 'in progress: Day 15 Track C (session `r1`), cost so far $0.00' != 'in progress: review of #12 (session `r1`), cost so far $0.00' (#283)
- [x] C15.13 **hold** — A running track session with three earlier ended review sessions and no
      earlier track session reads `(no estimate: 0 earlier track sessions)`, and
      `tests/test_progress.py`'s cases pass unedited. True today: a review has no kind.
      Test: `ReviewProgressTest.test_track_counts_no_review`, `ProgressTest`.
      Its break, in Track C: the earlier lengths read of every kind.
      Plan: P62 "the step in progress and its cost so far"
      Evidence: `ReviewProgressTest.test_track_counts_no_review` and `ProgressTest` pass on `main` at `9d9be8e`, `tests/test_progress.py` unedited since `11206ea`; its break recorded in #283.
      broken: the earlier lengths read of every kind (C15.13) → AssertionError: 'estimate 20m00s, the median of 3 earlier track sessions)' != 'no estimate: 0 earlier track sessions)'
- [x] C15.14 **hold** — With the `protected` fixture (`tests/test_level_2_start.py:40`) naming the
      nine and `tests`, C13.7's `LevelStartTest.test_starts_when_all_hold` starts its session, and
      `LevelMergeTest` (`tests/test_level_2_merge.py`, which imports `protected`) passes unedited.
      True today: `protection` reads no names. Both fail under Track A's code with the fixture's
      old `["tests"]`, so the fixture changes in Track A's PR.
      Test: `LevelStartTest.test_starts_when_all_hold`, `LevelMergeTest`.
      Its break, in Track A: one of the nine left out of the names `protection` counts as
      required (the brief names the find in Track A's code).
      Plan: N15 "the level 2 merge is switched on in a run, and refuses otherwise"
      Evidence: `LevelStartTest.test_starts_when_all_hold` and `LevelMergeTest` pass on `main` at `9d9be8e` (#281); its break recorded in #281.
      broken: one of the nine not counted as required (C15.14) → AssertionError: differs: 1
- [x] C15.15 **hold** — `on` at level 2 reads `main`'s protection before it starts:
      `LevelStartTest.test_needs_protection` passes. True today. Day 13's break "level 2 started
      without reading the protection", whose find `reason = github.protection(project, args.gh)`
      Track B rewrites, is retired in `specs/breaks/day-13.json` and recorded again under this
      criterion in `specs/breaks/day-15.json`, with the same check, in Track B's PR.
      Test: `LevelStartTest.test_needs_protection`.
      Its break, in Track B: the protection not read at level 2.
      Plan: N15 "the level 2 merge is switched on in a run, and refuses otherwise"
      Evidence: `LevelStartTest.test_needs_protection` passes on `main` at `9d9be8e`; its break recorded in #282, Day 13's retired there.
      broken: the protection not read at level 2 (C15.15) → AssertionError: differs: 0, 1, 2, 3, 4
- [x] C15.16 **hold** — The files C14.1, C14.4 and C14.7 froze at `3f31818` stay unchanged since
      `11206ea`, all but the six the tracks edit (`driver/config.py`, `driver/github.py`,
      `driver/loop.py`, `driver/review.py`, `driver/runlog.py`, `run-steps.py`), and
      `scripts/test_token_usage.py` with them: Verify's `11206ea` diff prints nothing. With it
      `tests/test_status.py`, `tests/test_status_trial.py`, `scripts/test_token_usage.py` and
      `StatusReviewTest.test_no_reviewer_line_without_review` pass unedited. True today.
      Test: Verify's `git diff`, `StatusReviewTest.test_no_reviewer_line_without_review`.
      Its breaks, in this spec-change PR: a driver file outside the six edited (find
      `decides its next step` in `driver/__init__.py`), and C14.7's line put before the `level 2:`
      line (find `lines.append(_level_2(records))` in `driver/status.py`, which Track C leaves
      occurring once).
      broken: a driver file outside the six edited (C15.16) → +"""The driver: reads a project's state and decides its step (plan.md)."""
      broken: a line put before the level 2 line (C15.16) → AssertionError: 'x' != 'level 2'
      Replaces: C14.1 — was: the driver's code other than `driver/status.py`, its hooks, the reviewer's rules and image, two tests, and the trial records are unchanged since `3f31818`.
      Replaces: C14.4 — was: `scripts/test_token_usage.py` passes and changes since `3f31818` in four lines of its max-path test only.
      Replaces: C14.7 — was: a log with no review `start` line prints the `status` block as before, and `tests/test_status.py` and `tests/test_status_trial.py` pass, unedited since `3f31818`.
      Plan: none — the freeze keeps Days 7 to 14's code out of this Day's diff; it serves no Day 15 commitment.
      Evidence: Verify's `git diff` from `11206ea` prints nothing on `main` at `9d9be8e`, after every Day 15 PR, and `StatusReviewTest.test_no_reviewer_line_without_review` passes there; its breaks recorded in #280.
- [x] C15.17 **hold** — With `level` 2, `waived_checks` `[]` and the nine required, `on` starts its
      session, prints no `level 2: waived` line, and the switch log's first line is
      `{"event": "on"}` (`at` aside). True today: `config.problems` ignores the key.
      Test: `LevelStartTest.test_none_waived`.
      Its break, in Track B: `waived_checks` `[]` passed to `switchlog.append` (the brief names the
      find in Track B's code); its report names the `on` line's fields through `same`.
      Plan: N39 "`on` prints each check `waived_checks` names and the switch log's `on` line names them"
      Evidence: `LevelStartTest.test_none_waived` passes on `main` at `9d9be8e`; its break recorded in #282.
      broken: waived_checks [] passed to switchlog.append (C15.17) → AssertionError: differs: waived_checks

## Verify
```bash
python -m unittest tests.test_merge_gh tests.test_kit_checks tests.test_waived_config tests.test_level_2_start tests.test_level_2_merge tests.test_status tests.test_status_trial tests.test_status_review scripts.test_token_usage tests.test_status_level tests.test_review_start tests.test_progress tests.test_review_progress tests.test_switch_log
git -c core.safecrlf=false diff --exit-code 11206ea -- driver/__init__.py driver/box.py driver/decide.py driver/home.py driver/issues.py driver/livecheck.py driver/lock.py driver/once.py driver/preflight.py driver/settings.py driver/steps.py driver/stream.py driver/switches.py driver/switchlog.py driver/tree.py hooks rules/reviewer.md docker tests/test_once.py tests/test_box_session.py tests/test_status.py tests/test_status_trial.py tests/test_trial_record.py tests/test_trial_ten.py docs/trial/day-08.md docs/trial/day-10.md docs/trial/run.jsonl scripts/test_token_usage.py
```

## Notes
- Base: `main` at `11206ea`. The plan-auditor read Phase 3 there before this spec (2026-11-22):
  8 findings, none blocking Day 15; findings 1 to 3 and 8 are settled in In scope, C15.4, C15.5,
  C15.6 and C15.14; 4 to 7 are H15.1 to H15.4.
- `scripts/setup-check.py` collects names from every source whatever its bypass
  (`setup-check.py:108-113`); the driver counts them only from a source with no bypass, as
  `protection` already reads the pull request and the checks (`github.py:262-281`). So
  `setup-check.py` may pass a check `on` refuses; the stricter reading is the merge's.
- Day 13's break "C13.3: a bypass read as protection" finds `    if blocked:` in
  `driver/github.py`; under Track A's code its report changes even with that line kept, so Track
  A retires and re-records it (C15.4).
- Earlier Days' break finds in the code the tracks rewrite, each to stay occurring once (or be
  re-recorded in the track's PR): Track B, `    if config.get("level") == 2:` (`loop.py`, Day 13);
  Track C, in `status.py`, `if start.get("prefix") == "review"` and
  `return "review of an unknown pull request"` (Day 14), `if session is not None:` (Day 7),
  `        if session:` and `if other not in ends or _kind(start.get("prefix")) != kind:` (Day 11,
  and C15.13's break), `lines.append(_in_progress(state, live, records, session))` (Day 11), and
  `lines.append(_level_2(records))` (C15.16); `if args.project is None:` in `run-steps.py` (Days 7
  and 8); `record["issue"] = issue` in `runlog.py` (Days 7 and 8).
- Bearing requires "A closed day's evidence replays" now (bearing at `7f8ec5d`, #157: classic
  `contexts` and `checks` both name it, `enforce_admins` true, `rules/branches/main` `[]`); of
  the nine it lacks only "A track's breaks replay" (#213's breaks replay, now a waiver). The
  maintainer adds `"waived_checks": ["A track's breaks replay"]` to bearing's `driver.json`
  after Track B merges and before bearing's next level 2 run
  (spec-auditor, finding 10).
- **Assumed** — GitHub returns a classic protection's required checks as names:
  `gh api "repos/{owner}/{repo}/branches/main/protection" --jq '.required_status_checks | {contexts: (.contexts|length), checks: .checks[0]}'`
  → `{"checks":{"app_id":null,"context":"Description uses the template"},"contexts":10}` (gh
  2.93.0, this repository, 2026-11-22). The ruleset form,
  `parameters.required_status_checks[].context`, is read as `setup-check.py:113` reads it, and
  stays untried: `gh api "repos/{owner}/{repo}/rules/branches/main"` returns `[]` in this
  repository and in bearing (the spec's first `--jq` on it printed "expected an object but got:
  array ([])" and exited 1). `KitChecksTest.test_ruleset_names` fakes that shape; the first
  project with such a rule tries it, and until then the maintainer accepts it untried.
- **Hand-off** H15.1 → Day 16: `config.is_level` takes only 1 or 2 (`config.py:36`, C13.1); level
  3 needs `driver.json` to accept 3, with `Replaces: C13.1` (plan-auditor, finding 4).
- **Hand-off** H15.2 → Day 16: a level lowered on an escape must be kept and read back, but the
  switch log is never read to decide (`switchlog.py:3-4`); once it is lowered, C15.10's "the
  level `driver.json` names" is not the level in force; and the `--out` JSON's `escapes`
  (`spec_drift_metrics.py:728`) is not the plan's escape (Levels, "Back one level")
  (plan-auditor, finding 5).
- **Hand-off** H15.3 → Day 17: `plan.md` says the plan-auditor's report "ends with one verdict
  line" (What to build, N42) and that the verdict line "comes first" (Phase 3, Day 17); the
  brief has no verdict line yet, and its kit PR has no Day (plan-auditor, finding 6).
- **Hand-off** H15.4 → the maintainer: reading `main`'s protection and a ruleset's
  `bypass_actors` may need Administration read, which the fine-grained token does not hold
  (`plan.md`, "Decisions for the maintainer"); P51's token scope, sent to Day 14's stop by Day
  13, is not in "Course correction after Phase 2" (plan-auditor, finding 7).
- **Defect** D15.1 — found: auditor · cause: spec · made: Day 15 · the tracks edit six files Day 14's Verify freezes at `3f31818`, which `invariants.py` gives to C14.1, C14.4 and C14.7 alike (each names the sha), and the spec had no `Replaces:` for them, so every track would fail "Frozen files stay unedited" (fixed in this PR: C15.16).
- **Defect** D15.2 — found: auditor · cause: spec · made: Day 15 · Track A's `protection` refuses the `protected` fixture's `["tests"]`, failing `test_starts_when_all_hold` and `LevelMergeTest` in Track A's own PR, though the spec edited the fixture in Track B; C15.7's `test_needs_the_kits_checks` would pass whole at Track B's start, and `test_starts_when_all_hold`, tagged `new`, passes on `main` (fixed in this PR: C15.7 and the fixture in Track A, C15.14 a hold of its own).
- **Defect** D15.3 — found: auditor · cause: spec · made: Day 15 · C15.14's break "the protection not read at level 2" did not fail `LevelMergeTest` ("Ran 11 tests … OK" with it in); Day 13 recorded it against `LevelStartTest.test_needs_protection` (fixed in this PR: C15.15 on that test).
- **Defect** D15.4 — found: auditor · cause: spec · made: Day 15 · under Track A's code, Day 13's C13.3 break reaches the names' reason, which unittest shortens to "[N chars]", which `break.py` refuses, and the same held for C15.1–C15.3's red with `assertEqual` on the reason (fixed in this PR: the re-record under C15.4 and the order the tests compare in).
- **Defect** D15.5 — found: auditor · cause: spec · made: Day 15 · C15.8's Red today was not the red at Track B's start (the two unwaived names refused); C15.9's "no `api` call" fails on the heartbeat's PATCH; and C15.8 gave the `on` line without its `at` (found: self) (fixed in this PR).
- **Defect** D15.6 — found: auditor · cause: spec · made: Day 15 · the Notes said bearing lacks "A closed day's evidence replays", which it requires at `7f8ec5d`; the Assumed line's `rules/branches/main` call did not print nothing but exited 1, and the ruleset form was tried nowhere (fixed in this PR).
- **Defect** D15.7 — found: auditor · cause: spec · made: Day 15 · earlier Days' break finds in the code the tracks rewrite were not listed; a review with no `pr` but a `review` line and `waived_checks` `[]` were in scope with no criterion; C15.5 quoted "does not run setup-check.py" and checked only the names (fixed in this PR).
- **Defect** D15.8 — found: auditor · cause: spec · made: Day 15 · the recheck: Verify's `invariants.py 11206ea HEAD` reads the specs as `11206ea` has them, where C14.1's freeze is in force, so it fails once Track A edits `driver/github.py`; two tests added by the first fixes, `test_driver_does_not_run_it` and `test_none_waived`, pass on `main` under `new` criteria, which CI's "Track tests seen red" fails; the rule on long reports covered only `protection`'s reason; two break finds were missing from the Notes; the heartbeat was said to show the `in progress:` line; the bearing waiver had no owner (fixed in this PR: the line dropped, CI's `invariants.py main HEAD` covers each PR; the first test folded into `test_the_kits_nine`, the second a hold, C15.17).
- **Defect** D15.9 — found: auditor · cause: spec · made: Day 15 · the second recheck: C15.7's red, compared through `same`, is "differs: 0, 1, 2, 3" (the stderr line differs too), not the three fields D15.8's fix named; its api field could gain a heartbeat PATCH; and C15.12's fixture could pass by a start line whose `step` read "review of #12" (fixed in this PR, in the auditor's measured wording).
- **Defect** D15.10 — found: track-reviewer · cause: spec · made: Day 15 · Day 13's break "C13.18: a "pr", "close" list in github.merge" reports a line number in `driver/github.py`, which Track A's new lines above `merge` move, so no find gives Day 13's report at its close and on Track A's code; the spec's Notes did not list it (fixed in #281: retired in `specs/breaks/day-13.json`, pinned at `38570d8`).
- **Defect** D15.11 — found: Track A · cause: spec · made: Day 15 · C14.1's break, "a driver file other than status.py edited", stayed in force in `specs/breaks/day-14.json` though C15.16 replaced C14.1; its check diffs the driver against `3f31818`, so it failed without the break once Track A edited `driver/github.py`, and CI's first breaks replay on #281 failed on it; neither the spec nor the track listed it (fixed in #281: retired, pinned at `38570d8`).
- **Defect** D15.12 — found: track-reviewer · cause: process · made: Day 15 · Track A's brief named no find for C15.14's break (fixed before the implementer ran).
- **Defect** D15.13 — found: track-reviewer · cause: process · made: Day 15 · Track A's brief left imports out of the new test file (fixed before the implementer ran).
- **Defect** D15.14 — found: track-reviewer · cause: process · made: Day 15 · Track A's brief was ambiguous on `KIT_CHECKS`'s comment: a comment naming `setup-check.py` would fail C15.5's grep (fixed before the implementer ran).
- **Defect** D15.15 — found: track-reviewer · cause: process · made: Day 15 · Track A's brief gave test lines over ruff's 100 characters (fixed before the implementer ran).
- **Defect** D15.16 — found: track-reviewer · cause: process · made: Day 15 · Track A's brief gave a test count as a difference, not the count (fixed before the implementer ran).
- **Defect** D15.17 — found: track-reviewer · cause: spec · made: Day 15 · no test had two rulesets, so every ruleset's names could be counted for each ruleset unseen (fixed in #281: `KitChecksTest.test_bypassable_ruleset_check`, beyond the spec's named tests, seen red on `main` as "AssertionError: unexpectedly None"; its break, each ruleset's names not its own, reported the same and is in no manifest, since no criterion's `broken:` line owns it).
- **Defect** D15.18 — found: track-reviewer · cause: implementation · made: Day 15 · Track A's `test_bypass` split the reason without first asserting it was not `None`, and its helper kept a fifth, whole-string comparison, long enough for unittest to shorten (fixed in #281).
- **Defect** D15.19 — found: track-reviewer · cause: implementation · made: Day 13 · the `protected` fixture's comment in `tests/test_level_2_start.py` had the admins' bypass the wrong way round, on `main` since Day 13's Track D wrote it (fixed in #281).
- **Defect** D15.20 — found: track-reviewer · cause: process · made: Day 15 · #281's first draft said the retired C13.18 break would show as "break no longer applies"; its find still occurs once, so it holds with another report (fixed in #281).
- **Defect** D15.21 — found: track-reviewer · cause: process · made: Day 15 · Track B's brief compared C15.17's `on` line inside a tuple, so its break would have reported a position, not the line's fields (fixed before the implementer ran).
- **Defect** D15.22 — found: track-reviewer · cause: process · made: Day 15 · Track B's brief placed the waived lines before `once.settle`, which can still refuse (fixed before the implementer ran).
- **Defect** D15.23 — found: track-reviewer · cause: process · made: Day 15 · Track B's brief left the root-path preamble out of `tests/test_waived_config.py` (fixed before the implementer ran).
- **Defect** D15.24 — found: track-reviewer · cause: spec · made: Day 15 · C15.6's bad values never reached `is_waived`'s list test: the string alone is refused by the names test, so deleting `isinstance(value, list)` failed no test (fixed in #282: `{}` in `test_not_a_list`, and the break "waived_checks not required to be a list" recorded beyond the spec's breaks).
- **Defect** D15.25 — found: track-reviewer · cause: spec · made: Day 15 · on #282's diff: C15.15 retires Day 13's "level 2 started without reading the protection", though a find fitting both codes exists (`reason = github.protection(project, args.gh`), so `specs/README.md` would re-record it in place (not fixed: #282 retired it as C15.15 says, and the re-check after a merge shows Day 13's entry as pinned).
- **Defect** D15.26 — found: self · cause: process · made: Day 15 · #282's first draft named `tests.test_kit_checks` in C15.8's seen-red line, retyped instead of pasted (fixed in #282: re-run and pasted).
- **Defect** D15.27 — found: track-reviewer · cause: process · made: Day 15 · Track C's brief ran one `seen-red.py` for six tests, which passes on one match while the other five error (fixed before the implementer ran: one run per test).
- **Defect** D15.28 — found: track-reviewer · cause: process · made: Day 15 · Track C's brief never made the live log's state folder, so the four C15.12 tests would have stopped on FileNotFoundError (fixed before the implementer ran).
- **Defect** D15.29 — found: track-reviewer · cause: process · made: Day 15 · Track C's brief had every C15.12 test assert the `in progress:` line first, so the spec's second red, "(no estimate: the step has no kind)", was seen by none (fixed before the implementer ran: `test_review_estimate` asserts the `running:` line first).
- **Defect** D15.30 — found: track-reviewer · cause: process · made: Day 15 · Track C's brief gave two tests no expected `running:` line (fixed before the implementer ran).
- **Defect** D15.31 — found: Track C · cause: process · made: Day 15 · Track C's brief forbade comparing a list with `assertEqual`, then did so in C15.11's test, which the implementer reported (not fixed: kept, since its report is short and fixed).
- **Defect** D15.32 — found: track-reviewer · cause: implementation · made: Day 15 · Track C's live log stamped the pid line's `started` before the child began, leaving about 1 s of `lock.lives`' 2 s slack under load (fixed in #283: the child started first, as `tests/test_status.py` does, and the file repeated under load).
- **Hand-off** H15.5 → the maintainer: what CI and the auditors did not check in the tracks: a `once.settle` refusal at level 2 with names waived (#282); `status --watch --config <c>`'s level, on its own path (#283); the heartbeat comment's review estimate, tested through `status` and not through `once.py`'s comment (#283); and, during a live review whose start line has `pr` and no `review` line yet, `in progress:` reads "review of #12" while the same session's `steps:` row reads "review of an unknown pull request" (#283).
- The close. Day 15 answers H14.1 (C15.12, C15.13: a running review's own line and estimate),
  H14.2 (C15.10: `status` prints the level `driver.json` gives) and H14.3 (C15.1 to C15.8: the
  kit's nine checks by name, and `waived_checks`). Nothing ran for real: the Day is code and
  fakes. Before bearing's next level 2 run, the maintainer adds `"waived_checks": ["A track's
  breaks replay"]` to its `driver.json` (Notes above). The ruleset form stays untried (Assumed).
  Retired this Day: Day 13's C13.3 (re-recorded under C15.4), C13.18 and "level 2 started
  without reading the protection" (re-recorded under C15.15), and Day 14's C14.1 break.
