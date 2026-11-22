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
  (`tests`) are neither needed nor refused.
- **`waived_checks` (Track B; N38, N39).** An optional key of `driver.json`: a list of distinct
  names, each one of `KIT_CHECKS`. Absent is `[]`. Anything else is one line from
  `config.problems`: `cannot start: <path>'s waived_checks must be a list of the kit's check names,
  each once`. At level 2, `level_2_refusals` passes it to `protection`; once the four conditions
  hold, `on` prints on stdout, before the session, one line per waived name in the config's order,
  `level 2: waived check "<name>"`, and the switch log's `on` line becomes
  `{"event": "on", "waived_checks": [<the names>]}`. With none waived, or at level 1, the `on`
  line stays `{"event": "on"}` (S-switch-log.3), and level 1 prints no waived line and reads no
  protection.
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
  lines (`live_lines`). A track's estimate still counts no review (C15.13).

## Out of scope
- `level` 3 in `driver.json` (`config.is_level`, C13.1) — Day 16's spec (H15.1).
- Keeping a lowered level after an escape, and which level `status` then prints — Day 16 (H15.2).
- The plan-auditor's verdict line and its place ("first" or "last") — Day 17 (H15.3).
- Whether the fine-grained token can read `main`'s protection — the maintainer (H15.4).
- Running `setup-check.py` from the driver: `plan.md` says the driver reads the names itself.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | C15.1–C15.5 |
| B | | C15.6–C15.9, C15.14 |
| C | | C15.10–C15.13 |

B uses Track A's `KIT_CHECKS` and `waived`, so it follows A. C stands alone and may run before B.
No Track 0: each hold's break needs its track's code, so each hold's test lands with its track.

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [ ] C15.1 **new** — `github.protection` on the fake `gh`, for C13.3's `test_classic` set-up with
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
- [ ] C15.2 **new** — `protection(..., waived=("A track's breaks replay",))` on the set-up of
      C15.1's second case gives `None`; with `waived` naming "Track tests seen red" instead, it
      gives `main does not require "A track's breaks replay"`. Red today: `protection` takes no
      `waived`, a TypeError.
      Test: `KitChecksTest.test_waived`.
      Plan: N38 "unless `waived_checks` in `driver.json` names it"
- [ ] C15.3 **new** — A kit check only a source with a bypass requires is missing: ruleset 7
      (`bypass_actors` `[]`) requires the pull request and eight of the nine, and a classic
      protection with `enforce_admins` false requires the ninth, "Frozen files stay unedited":
      `protection` gives `main does not require "Frozen files stay unedited"`. Red today: `None`.
      Test: `KitChecksTest.test_bypassable_check`.
      Plan: N38 "requires each of the kit's nine checks by name"
- [ ] C15.4 **hold** — C13.3's ten `ProtectionTest` cases, their checks the nine and `tests`
      (`CHECKS` in `tests/test_merge_gh.py` and the rules' `parameters`), give C13.3's answers;
      the nine required only as ruleset 7's rule `parameters.required_status_checks[].context`
      (classic 404) give `None`, as do the nine split between classic `contexts` (five) and
      `checks[].context` (four). True today: `protection` reads no names.
      Test: `ProtectionTest`, `KitChecksTest.test_ruleset_names`, `KitChecksTest.test_classic_forms`.
      Its break, in Track A: the names read from `contexts` alone.
      Plan: N15 "main requires a pull request with no bypass"
- [ ] C15.5 **new** — `github.KIT_CHECKS` equals `scripts/setup-check.py`'s `REQUIRED`, loaded
      by path, item for item. Red today: `github` has no `KIT_CHECKS`, an AttributeError.
      Test: `KitChecksTest.test_the_kits_nine`.
      Plan: N38 "the driver reads them itself and does not run setup-check.py"
- [ ] C15.6 **new** — `config.problems` gives `cannot start: <path>'s waived_checks must be a
      list of the kit's check names, each once` for `"A track's breaks replay"` (a string),
      `["nope"]` and `["Track tests seen red", "Track tests seen red"]`; and no line for `[]`,
      for the nine, and with the key absent. Red today: no line for the three bad values.
      Test: `WaivedConfigTest.test_not_a_list`, `WaivedConfigTest.test_unknown_name`,
      `WaivedConfigTest.test_twice` (`tests/test_waived_config.py`).
      Plan: N38 "unless `waived_checks` in `driver.json` names it"
- [ ] C15.7 **new** — `on` with `level` 2, the other three conditions holding, and the fake
      classic protection requiring the pull request and `tests` with `enforce_admins` true, exits 2
      with `cannot start: level 2 needs main to require a pull request and its checks with no
      bypass: main does not require "Description uses the template", …` (the nine, as C15.1),
      starts no session and creates no issue. With the nine required, it starts its session as
      C13.7's `test_starts_when_all_hold` does, whose `protected` fixture
      (`tests/test_level_2_start.py:40`) now names the nine and `tests`. Red today: the session
      starts.
      Test: `LevelStartTest.test_needs_the_kits_checks`, `LevelStartTest.test_starts_when_all_hold`.
      Replaces: C13.7 — was: `on` at level 2 started once `main` required a pull request and any check with no bypass.
      Plan: N15 "the level 2 merge is switched on in a run, and refuses otherwise"; N38 "requires each of the kit's nine checks by name"
- [ ] C15.8 **new** — `on` with `level` 2, `waived_checks` `["A track's breaks replay", "A closed
      day's evidence replays"]` and the fake requiring the other seven and `tests`, starts its
      session; its stdout holds `level 2: waived check "A track's breaks replay"` then `level 2:
      waived check "A closed day's evidence replays"`, before the session's start, and the switch
      log's first line is `{"event": "on", "waived_checks": ["A track's breaks replay", "A closed
      day's evidence replays"]}`. Red today: no waived line, and the `on` line is `{"event": "on"}`.
      Test: `LevelStartTest.test_waived_printed_and_logged`.
      Plan: N39 "`on` prints each check `waived_checks` names and the switch log's `on` line names them"
- [ ] C15.9 **hold** — At level 1, `waived_checks` `["A track's breaks replay"]` changes nothing:
      `on` makes no `api` call, prints no `level 2: waived` line, and its switch log's `on` line is
      `{"event": "on"}`. True today: `on` reads no `waived_checks`.
      Test: `LevelStartTest.test_level_1_ignores_waived`.
      Its break, in Track B: the waived lines printed at any level.
      Plan: none — level 1 is unchanged by this Day; the hold keeps the waiver to level 2.
- [ ] C15.10 **new** — `run-steps.py status --config <c>`, `<c>` naming the fake project with
      `level` 2, prints `level: 2` as its second line; with `level` absent, `level: 1`. Red today:
      `level: 1` for both.
      Test: `StatusLevelTest.test_config_level` (`tests/test_status_level.py`).
      Plan: P62 "the mode, the level"
- [ ] C15.11 **new** — After a review on the fake `claude` (`tests/test_review_loop.py`'s set-up)
      of #12, the run log's `start` line with `prefix` "review" holds `"pr": 12`. Red today: no
      `pr` key.
      Test: `ReviewStartTest.test_start_names_the_pr` (`tests/test_review_start.py`).
      Plan: P62 "the step in progress and its cost so far"
- [ ] C15.12 **new** — `status` on a log whose live session (a child the test starts) has a
      `start` line with `prefix` "review" and `pr` 12 prints `in progress: review of #12 (session
      `r1`), cost so far $0.00` and a `running:` line ending `(no estimate: 0 earlier review
      sessions)`; with three earlier ended reviews of 600, 1200 and 2400 s, ending `(estimate
      20m00s, the median of 3 earlier review sessions)`; with no `pr` key and no `review` line,
      `in progress: review of an unknown pull request (session `r1`), cost so far $0.00`. Red
      today: the step's sentence, and `(no estimate: the step has no kind)`.
      Test: `ReviewProgressTest.test_live_review_line`, `ReviewProgressTest.test_review_estimate`,
      `ReviewProgressTest.test_no_pr_on_the_start` (`tests/test_review_progress.py`).
      Plan: P62 "the step in progress and its cost so far"
- [ ] C15.13 **hold** — A running track session with three earlier ended review sessions and no
      earlier track session reads `(no estimate: 0 earlier track sessions)`, and
      `tests/test_progress.py`'s cases pass unedited. True today: a review has no kind.
      Test: `ReviewProgressTest.test_track_counts_no_review`, `ProgressTest`.
      Its break, in Track C: the earlier lengths read of every kind.
      Plan: P62 "the step in progress and its cost so far"
- [ ] C15.14 **hold** — C13.8 holds with C13.7's fixture changed: `LevelMergeTest`
      (`tests/test_level_2_merge.py`, which imports `protected` from `tests/test_level_2_start.py`)
      passes unedited, and Day 13's break "level 2 started without reading the protection", whose
      find `reason = github.protection(project, args.gh)` Track B rewrites, is re-recorded in
      `specs/breaks/day-15.json` under this criterion and retired in `specs/breaks/day-13.json` in Track
      B's PR.
      Test: `LevelMergeTest`.
      Its break, in Track B: the protection not read at level 2.
      Plan: N15 "the level 2 merge is switched on in a run, and refuses otherwise"

## Verify
```bash
python -m unittest tests.test_merge_gh tests.test_kit_checks tests.test_waived_config tests.test_level_2_start tests.test_level_2_merge tests.test_status tests.test_status_level tests.test_review_start tests.test_progress tests.test_review_progress tests.test_switch_log
python scripts/invariants.py 11206ea HEAD
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
  `driver/github.py`: Track A keeps that line, or re-records the break under C15.1.
- Bearing lacks "A closed day's evidence replays" and "A track's breaks replay" (Day 14, "Before
  this day"): its `driver.json` names both in `waived_checks` before its next level 2 run
  (#213's breaks replay, now a waiver).
- **Assumed** — GitHub returns a classic protection's required checks as names:
  `gh api "repos/{owner}/{repo}/branches/main/protection" --jq '.required_status_checks | {contexts: (.contexts|length), checks: .checks[0]}'`
  → `{"checks":{"app_id":null,"context":"Description uses the template"},"contexts":10}` (gh
  2.93.0, this repository, 2026-11-22). The ruleset form,
  `parameters.required_status_checks[].context`, is read as `setup-check.py:113` reads it; not
  run here, since this repository has no `required_status_checks` rule (the same call on
  `rules/branches/main` printed nothing).
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
