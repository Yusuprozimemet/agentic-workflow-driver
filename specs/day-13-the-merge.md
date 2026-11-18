# Day 13 — The level 2 merge: the switch and its three conditions, the path check, the driver's own repository, `gh pr merge --match-head-commit`

**Phase:** 2 · **Depends on:** Day 12 · **Expected PRs:** 10 (the spec change, Tracks 0, A, B, C, D, E1, E2, F, the close)

## Goal
With `"level": 2` in `driver.json`, `on` refuses to start unless the reviewer is on and Levels'
three conditions hold (`status` counts 15 of 15 from container sessions, the sessions run in the
container, the project's `main` requires a pull request with no bypass). Once a pull request's
checks are green and the reviewer found no blocker on its head, the driver runs the path check,
reads the count again, checks its own repository, and merges with
`gh pr merge <n> --merge --match-head-commit <the head the reviewer saw>`. When the count has
fallen, that pull request waits for the maintainer's merge as at level 1. The driver also never
drives its own repository, and the session installs the project as CI does before its tests
(`plan.md`, "What to build", item 8; "Levels"; "Phase 2"; "Course corrections", 2026-11-16).

## In scope

Decided by the maintainer on 2026-11-18, where `plan.md` leaves it open: a `level` key in
`driver.json` switches the merge on; `on` refuses to start at level 2 unless the three conditions
hold and `review` is true; before each merge the count is read again, and below 15 the pull
request waits for the maintainer's merge, with a run log line that says why. The count also ends
on the reviewer's "still has a blocker … after two fixes" park (H12.2), and not on a failed
evidence run or on any other park. The session's install is a line in the driver's rules (N10).
No `live-check` runs in the image (H10.1, H12.1): C10.9's version check stays the image's check,
and Day 12's live test already ran the reviewer in the image (C12.21).

- **The switch (Track A).** `driver.json` takes an optional `level`, `1` or `2`, `1` when absent;
  `driver.config.problems` reports "cannot start: <path>'s level must be 1 or 2" for any other
  value, `true` and `2.0` included. `driver.json` is the maintainer's, gitignored: no PR sets the
  key. `--once` reads it and does nothing with it: only `on` merges.
- **Never its own repository (Track A).** `once.run`, which `--once` and `on` share, refuses
  "cannot start: `<project>` is the driver's own repository", exit 2, before the lock is taken,
  when the project's resolved path is the driver's folder or `git ls-remote --get-url origin`
  gives the same URL in both. That command prints "origin" and exits 0 when there is no origin:
  "origin" counts as no URL, and two folders with no origin are not the same repository. Nothing
  of the project is read: no `gh` call, no session.
- **What GitHub says (Track B).** `driver.github.protection(project, gh)` returns `None` when
  `main` requires a pull request with no bypass, and the reason otherwise. It reads
  `gh api repos/{owner}/{repo}/branches/main/protection` (exit 1 with "(HTTP 404)" on stderr is
  "no classic protection", as `setup-check.py`'s `gh_api` reads it; any other failure is a
  reason),
  `gh api repos/{owner}/{repo}/rules/branches/main`, and for each distinct `ruleset_id` of a rule
  of type `pull_request` or `required_status_checks`
  `gh api repos/{owner}/{repo}/rulesets/<that id>`, much as `scripts/setup-check.py`'s
  `protection_lines` and `bypass_line` read them; `{owner}/{repo}` is passed as it is, and `gh`
  fills it from the project's remote. Two things must be required: a pull request (the classic
  protection's `required_pull_request_reviews`, or a rule of type `pull_request`) and the checks
  (the classic protection's `required_status_checks` naming one context or check, or a rule of
  type `required_status_checks`). Each counts only from a source with no bypass: the classic
  protection with `enforce_admins.enabled`, or a ruleset whose `bypass_actors` is `[]`. The
  reviewed head is merged on GitHub's refusal of a head whose required checks are not green
  (Notes). Reasons, the first that applies: a failed call first, "gh api exited <code>" (the
  classic 404 aside); then "main does not require a pull request", then "main does not require
  its checks", when no source requires it; then "cannot read main's ruleset <id>: bypass_actors not
  shown (needs admin)" when a ruleset read without the field is the only source left; then "main
  allows a bypass" when every source of one of the two allows a bypass. `driver.github.merge(project, gh, n, sha)` runs
  `gh pr merge <n> --merge --match-head-commit <sha>` and returns `None` on exit 0, else "gh pr
  merge exited <code>". `--merge`, since the projects merge with a merge commit; no
  `--delete-branch` (P48: no branch is deleted).
- **The count (Track C).** `status.level_2_run` also stops counting at a `park` whose line holds
  "the reviewer still has a blocker on" and "after two fixes". `status`'s printed line is unchanged.
- **The start (Track D).** With `level` 2, `on` checks after the live check, before
  `once.settle`, the switch log's `on` line and the run's issue, and refuses with one line per condition that fails, in this order, exit 2:
  - "cannot start: level 2 needs "review": true in <path>"
  - "cannot start: level 2 needs the sessions in the container: <path> has no container_image"
  - "cannot start: level 2 needs 15 of 15 pull requests in a row merged without a change asked;
    status counts <k>"
  - "cannot start: level 2 needs main to require a pull request and its checks with no bypass:
    <the reason>" (the checks are this spec's addition to N15's condition, Notes)

  `<path>` is the config's path, `<k>` `status.level_2_run` over `runlog.read`'s records (a run
  log that cannot be read counts 0). The protection is read only when the first three hold. With
  all four holding, the run starts as at level 1.
- **The merge (Track E).** `loop.wait_merge` takes a keyword `level2`, `None` by default (the
  frozen tests call it without), and `steps` passes `(home, started)` when `level` is 2. With it,
  at the first read whose state is `OPEN` and whose path check passes, in this order:
  1. the count: `status.level_2_run` below 15 prints "level 2: #<n> waits for the maintainer:
     <k> of 15 in a row", appends `{"event": "level", "at": …, "pr": <n>, "line": <that line>}` to
     the run log, and the wait goes on as at level 1; nothing below is done for that pull request;
  2. the driver's own repository: `driver_home.check(home, started)` giving a reason returns
     "halt: <the reason>; #<n> not merged", 1, and `steps`' `finish` writes the halt file, as
     after a step today;
  3. the head: the head of the newest `review` line for `<n>` in the run log, with `blockers` 0.
     None, or a head `pr_state` reads now that is not it, parks "park: #<n> moved after the
     review", 1, with `pr` and `head` as the gated parks (Track E2; in Track E1, with no clean
     `review` line no merge is asked and the wait goes on as at level 1, and a head that differs
     is not checked);
  4. `github.merge` with that head. In Track E1 its result is not read: once asked, the `merged`
     line has `"by": "driver"`. Track E2: on a reason, `pr_state` is read once more: `MERGED`
     goes on as below, without `by` (someone else merged it); otherwise it parks "park: the merge
     of #<n> failed: <the reason>", 1.

  The merge is asked once per pull request: a later `OPEN` read, GitHub not yet showing the
  merge, does not ask again.

  After the merge the wait reads `pr_state` as today: `MERGED` writes the run log's `merged` line
  with `"by": "driver"` after `changed`, and main is pulled and the evidence run waited on, as
  after the maintainer's merge. Whether it merged is read from GitHub, not from the merge's exit.
- **The rules and two leftovers (Track F).** `rules/session.md` gains one line, after "You never
  merge…": "- Before running the project's tests, install the project as its CI does (its
  workflows in `.github/workflows/`)." `review_pass`'s second `git` failure, after the reviewer,
  reads "cannot read the project: git failed after the review of #<n>" (D12.38, H12.5).

## Out of scope

- A failed evidence run after a merge taking the driver back a level (P54): the maintainer chose
  on 2026-11-18 that it does not end the count. It stays a park, as today.
- `status` printing "level: 2": it prints "level: 1" and the count, and does not read
  `driver.json` — Day 14's record, if the maintainer wants it.
- The protection read again before each merge: the maintainer chose the count; the protection is
  read once, at the start.
- A live `gh pr merge` on a real pull request: the Day 14 trial is its first run (Notes, Assumed).
- The usage limit met by a headless session (H09.2), the container's sessions in the record
  (H10.2), the reviewer's session as its own kind in `status` (H12.3) — Day 14.
- H12.4's parts with no criterion: the plan-auditor's report on a phase's park, the last phase's
  three auditors, the "the audit found nothing" park (P25, P37) — Phase 3, level 3. P51's token
  scope with the container — the maintainer, at Day 14's stop.
- Whether a park opens an issue the maintainer closes (#241's question on the dashboard's "ways
  back") — the maintainer.

## Tracks

| Track | Owner | Work |
|---|---|---|
| 0 | | The holds' tests, which pass before and after: C13.17, C13.19, C13.20 |
| A | | `level` in `driver.config`; the own-repository refusal in `once.run`: C13.1, C13.2 |
| B | | `github.protection`, `github.merge`, the fake `gh`'s `api` answers and `pr merge`; C07.1's test: C13.3–C13.5, C13.18 |
| C | | `status.level_2_run` ends on the reviewer's blocker park: C13.6 |
| D | | The level 2 start in `loop.steps`: C13.7 |
| E1 | | The merge in `loop.wait_merge`; `runlog.merged`'s `by`; `runlog.level`: C13.8–C13.11 |
| E2 | | The head check and a failed merge: C13.12, C13.13 |
| F | | `rules/session.md`'s line; the frozen list; `review_pass`'s second line: C13.14–C13.16 |

D needs A, B and C; E1 needs D; E2 needs E1. They run in this order. E is split in two because
Day 12's Track E1, of the same kind, measured 704 changed lines.

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [ ] C13.1 **new** — `driver.config.problems` gives no line for a config without `level` or with
      `level` 1 or 2, and "cannot start: <path>'s level must be 1 or 2" for `3`, `"2"`, `true`
      and `2.0`. Red today: `problems` gives no line for any of the four.
      Test: `LevelConfigTest.test_level_values`.
      Plan: N15 "the level 2 merge is switched on in a run, and refuses otherwise"
- [ ] C13.2 **new** — `--once` with `--project` the driver's folder, and `--once` on a scratch
      project whose `origin` URL the test sets to the one it gives the driver's folder, each print
      "cannot start: `<project>` is the driver's own repository" to stderr, exit 2, and leave the
      fake `gh`'s `calls.jsonl` empty, the fake `claude` uncalled and no lock in the state folder.
      Red today: the own-repository line is not printed (the run refuses on another line, or reads
      the project).
      Test: `OwnRepositoryTest.test_same_folder`, `OwnRepositoryTest.test_same_origin`.
      Plan: P08 "the driver never drives its own repository"
- [ ] C13.3 **new** — `github.protection` on a fake `gh` gives `None` for a classic protection with
      `required_pull_request_reviews` and `enforce_admins` `{"enabled": true}`; `None` for a classic
      404 (exit 1, "gh: Branch not protected (HTTP 404)" on stderr) with ruleset 7's
      `pull_request` and `required_status_checks` rules and its `bypass_actors` `[]`; "main allows
      a bypass" with a classic protection holding `required_pull_request_reviews` and
      `enforce_admins` false, and no rule; "main allows a bypass" with the pull
      request from ruleset 7 (`bypass_actors` `[]`) and the checks only from a classic protection
      with `enforce_admins` false; "main does not require a pull request" with neither; "main does
      not require its checks" for a classic protection with `required_pull_request_reviews`,
      `enforce_admins` enabled and no `required_status_checks`, and no rule; "cannot read main's
      ruleset 7: bypass_actors not shown (needs admin)" for ruleset 7's rules, a body without the
      field, and no classic protection; "gh api exited 1" for a full classic protection and the
      rules call exiting 1. Every case but `test_no_pull_request` and `test_no_checks` has its
      checks required. The calls name `repos/{owner}/{repo}/...` as written. Red today: `github`
      has no `protection`.
      Test: `ProtectionTest.test_classic`, `ProtectionTest.test_ruleset`,
      `ProtectionTest.test_bypass`, `ProtectionTest.test_checks_bypassable`,
      `ProtectionTest.test_no_pull_request`, `ProtectionTest.test_no_checks`,
      `ProtectionTest.test_hidden_bypass`, `ProtectionTest.test_gh_fails`.
      Plan: N15 "main requires a pull request with no bypass"
- [ ] C13.4 **new** — `github.merge(<project>, <fake gh>, 12, <sha>)` returns `None`, and the fake
      `gh` records `["pr", "merge", "12", "--merge", "--match-head-commit", <sha>]`; with the fake's
      `merge_code` 1 it returns "gh pr merge exited 1". Red today: `github` has no `merge`, and the
      fake `gh` exits 99 on `pr merge`.
      Test: `MergeCallTest.test_merge_call`, `MergeCallTest.test_merge_fails`.
      Plan: P64 "then `gh pr merge --match-head-commit <sha>` on the commit the checks and the reviewer saw"
- [ ] C13.5 **new** — Over `run-steps.py` and `driver/*.py`, parsed as C07.1 parses them, exactly
      one list or tuple holds `"pr"` with `"merge"` after it, in `driver/github.py`, and the same
      list holds `"--match-head-commit"`; a second such list, or one without
      `"--match-head-commit"`, fails. Red today: the test finds no merge list.
      Test: `RecoveryRulesTest.test_one_merge_on_a_head`.
      Plan: N24 "carries Replaces: C07.1"
- [ ] C13.6 **new** — `status.level_2_run` over five container merges, a `park` "park: the reviewer
      still has a blocker on #9 after two fixes", then two container merges, gives 2. Red today: 7.
      Test: `LevelTwoBlockerTest.test_blocker_park_ends_the_count`.
      Plan: N15 "only when status reports 15 of 15"
- [ ] C13.7 **new** — `on` with `level` 2 refuses with C13's four lines as their conditions fail:
      `review` absent; no container keys; a run log counting 14; the fake protection giving "main
      allows a bypass" (a classic protection requiring the pull request and the checks, with
      `enforce_admins` false, and no rule). Each case exits 2, starts no session and creates no issue; the first three
      make no `api` call. With all four holding, the fake `gh` records the
      `repos/{owner}/{repo}/branches/main/protection` and `repos/{owner}/{repo}/rules/branches/main`
      calls before the session, and `on` starts its session as at level 1. Red today: `on` starts
      a session in each case, and makes no `api` call.
      Test: `LevelStartTest.test_needs_review`, `LevelStartTest.test_needs_container`,
      `LevelStartTest.test_needs_the_count`, `LevelStartTest.test_needs_protection`,
      `LevelStartTest.test_starts_when_all_hold`.
      Plan: N15 "the level 2 merge is switched on in a run, and refuses otherwise"; N37 "At level 2 the driver's merge stands on the same gate, with the reviewer's verdict in place of the go-ahead"
- [ ] C13.8 **new** — `wait_merge` with `level2`, a run log counting 15 and a `review` line for #12
      with `blockers` 0 on the head the fake's views give, the views `OPEN`, `OPEN`, `MERGED`: the
      fake `gh` records exactly one `pr merge`, with `--match-head-commit` and that head, after the
      first `pr view`; the run log's `merged` line has `"by": "driver"`; main is pulled and the
      evidence run waited on as today. And `on` with `level` 2 and every condition holding: its
      `calls.jsonl` holds one `pr merge` of its step's pull request with the head of the run log's
      `review` line, and the run ends "on: 1 steps, the night's count". Red today: `wait_merge`
      takes no `level2`, and the fake records no `pr merge`.
      Test: `LevelMergeTest.test_merges_the_reviewed_head`, `LevelMergeTest.test_on_merges`.
      Plan: P64 "The level 2 merge is the path check against the human-only list"; P24 "A merge is done by the maintainer or (level 2) the driver, never by a step session"; N09 "where it polls and at level 2 merges"
- [ ] C13.9 **new** — With `level2`, the path check comes first: a pull request touching `plan.md`,
      a human-only path, or carrying `Oversized:`, parks with today's gated line and its `pr` and
      `head`, and the fake `gh` records no `pr merge`. Red today: `wait_merge` takes no `level2`.
      Test: `LevelMergeTest.test_path_check_first`.
      Plan: P27 "Kit and gate changes are human-only files that only the maintainer merges"; P30 "The driver parks when the pull request touches plan.md or a human-only file"
- [ ] C13.10 **new** — With a run log counting 14, `wait_merge` with `level2` prints "level 2: #12
      waits for the maintainer: 14 of 15 in a row", appends one `level` line with that line, records
      no `pr merge`, and returns `(None, 0, {})` once the views say `MERGED`; the `merged` line has
      no `by`. Red today: `wait_merge` takes no `level2`.
      Test: `LevelMergeTest.test_count_fallen_waits`.
      Plan: N15 "only when status reports 15 of 15"
- [ ] C13.11 **new** — With `level2` and a file left in the driver's folder (or its HEAD moved from
      `started`), `wait_merge` returns "halt: the driver's repository has changes: `x.txt`; #12 not
      merged", 1 (or "halt: the driver's repository moved from `<head>` to `<head>`; #12 not
      merged", 1, the two short heads put back as `<head>` by the test), and the fake records no
      `pr merge`. Red today: `wait_merge` takes no `level2`.
      Both tests give a run log counting 15, so step 1 passes.
      Test: `LevelMergeTest.test_driver_changed_no_merge`, `LevelMergeTest.test_driver_moved_no_merge`.
      Plan: P10 "at level 2 before each merge, the driver checks that its own repository is clean and at the commit it started from, and halts on a difference"; N24 "includes the check of the driver's own repository before each merge"
- [ ] C13.12 **new** — With `level2` and the views' head not the `review` line's (or no `review`
      line for #12, or one with `blockers` 1), `wait_merge` parks "park: #12 moved after the
      review", 1, with `pr` 12 and the head read, and records no `pr merge`; the views end
      `MERGED`, so a wait that does not park ends. Red at Track E2's start: Track E1 records a `pr
      merge` with the `review` line's head when the views' head differs, and waits to `MERGED`
      with no park when there is no clean `review` line.
      `test_no_clean_review_parks` holds both the no-line and the `blockers` 1 cases.
      Test: `LevelMergeTest.test_head_moved_parks`, `LevelMergeTest.test_no_clean_review_parks`.
      Plan: P64 "then `gh pr merge --match-head-commit <sha>` on the commit the checks and the reviewer saw"
- [ ] C13.13 **new** — With `level2` and the fake's `merge_code` 1, the views `OPEN`, `OPEN`,
      `CLOSED`, `wait_merge` parks "park: the merge of #12 failed: gh pr merge exited 1", 1, and
      writes no `merged` line; with the view after the failed merge `MERGED`, it does not park, and
      the `merged` line has no `by`. Red at Track E2's start: Track E1 reads no result, so the
      first ends "park: #12 was closed without a merge" and the second's `merged` line has `"by":
      "driver"`.
      Test: `LevelMergeTest.test_merge_fails_parks`, `LevelMergeTest.test_merge_fails_but_merged`.
      Plan: P64 "whether a PR merged is read from GitHub, not from the log"
- [ ] C13.14 **new** — `rules/session.md` is its text at `5d4f1b5` with one line added after the
      line that begins "- You never merge": "- Before running the project's tests, install the
      project as its CI does (its workflows in `.github/workflows/`)." (line endings aside). Red
      today: the file is its text at `5d4f1b5`.
      Test: `SessionRulesTest.test_install_line`.
      Plan: N10 "the session installs the project as CI does before running its tests"
- [ ] C13.15 **hold** — The files C12.24 keeps stay unchanged, all but `rules/session.md`, which
      changes only by C13.14's line: Verify's `5d4f1b5` and `83cf2f2` diffs print nothing.
      Replaces: C12.24 — was: `rules/session.md` among the files unchanged since `5d4f1b5`.
      Plan: N31 "The result event stays the record"
- [ ] C13.16 **new** — When `git` fails in the snapshot after the reviewer's session (and not
      before it), `review_pass` returns "cannot read the project: git failed after the review of
      #12", 2. Red today: the line says "before the review".
      Test: `ReviewAfterTest.test_git_fails_after_the_review`.
      Plan: none — the wording of one line (D12.38); the park it ends in is C12.17's.
- [ ] C13.17 **hold** — Without `level`, or with `level` 1, nothing changes: C12.20 holds (its
      files unedited since `5bb5fa1` and passing), and `on` with `"level": 1`, `review` true, the
      container keys, a run log counting 15 and a clean `review` line for its step's pull request
      records no `pr merge` and waits for the views' `MERGED`.
      Test: `LevelMergeTest.test_level_1_never_merges`, `OnTest.test_merge_waits_on_the_fixed_pr`,
      `MergeWaitTest.test_merged_pulled_evidence_waited`.
      Plan: N15 "the level 2 merge is switched on in a run, and refuses otherwise"
- [ ] C13.18 **hold** — C07.1's three rules hold with the merge in: no string constant can lose
      work, no shell, and no list holds `"pr"` with `create`, `close`, `edit` or `review` after it;
      `"pr"` with `merge` is left to C13.5.
      Test: `RecoveryRulesTest.test_no_pull_request_opened_or_closed`,
      `RecoveryRulesTest.test_no_command_that_can_lose_work`, `RecoveryRulesTest.test_no_shell`.
      Replaces: C07.1 — was: no list held `"pr"` with `merge` after it.
      Plan: P46 "The driver opens no pull request and closes none"; P48 "never `reset`, a checkout of a path, `clean`, `stash`, `branch -D`, a forced push or the deletion of a branch"
- [ ] C13.19 **hold** — `status.level_2_run` over five container merges, the park "park: the
      reviewer has a blocker on #9: x", then two container merges, gives 7: only the park after
      two fixes ends the count (the maintainer's choice).
      Test: `LevelTwoBlockerTest.test_other_blocker_park_passes`.
      Plan: N15 "only when status reports 15 of 15"
- [ ] C13.20 **hold** — `--once` on a project whose `origin` URL differs from the driver folder's,
      and on one with no origin beside a driver folder with none, goes on past the
      own-repository check as today.
      Test: `OwnRepositoryTest.test_other_origin`, `OwnRepositoryTest.test_no_origin`.
      Plan: P08 "the driver never drives its own repository"

## Verify
```bash
python -m unittest tests.test_level_config tests.test_own_repository tests.test_merge_gh tests.test_recovery_holds tests.test_level_2_blocker tests.test_level_2_start tests.test_level_2_merge tests.test_session_rules tests.test_review_after tests.test_review_loop tests.test_on tests.test_merge_wait tests.test_gated_merge tests.test_wait tests.test_runlog_fix tests.test_status tests.test_level_2_sentence tests.test_level_2_container -v
git -c core.safecrlf=false diff --exit-code 5bb5fa1 -- tests/test_on.py tests/test_merge_wait.py tests/test_gated_merge.py tests/test_wait.py tests/test_runlog_fix.py
git -c core.safecrlf=false diff --exit-code 5d4f1b5 -- tests/test_once_outcome.py tests/test_once_run.py tests/test_runlog.py tests/test_runlog_end.py tests/test_once_halt.py tests/test_halt_race.py tests/test_once_stop.py tests/test_session_bound.py tests/test_box_command.py tests/test_status.py tests/test_status_trial.py tests/test_level_2_sentence.py tests/test_on.py tests/test_contract.py tests/test_decide.py tests/test_dry_run.py tests/test_steps.py tests/test_tree.py tests/test_config.py tests/test_encoding.py tests/test_halt.py tests/test_halt_report.py tests/test_home.py tests/test_hooks.py tests/test_off.py tests/test_once_park_issues.py tests/test_once_parks.py tests/test_preflight.py tests/test_recovery_table.py tests/test_lock_takeover.py driver/decide.py driver/steps.py driver/home.py tests/test_failures.py tests/test_runlog_fix.py tests/test_wait.py tests/test_kit_copy.py tests/test_lock.py tests/test_live_cli.py tests/test_live_once.py
git -c core.safecrlf=false diff --exit-code 83cf2f2 -- tests/test_usage_limit.py tests/test_issues.py
```

Where the tests live: `LevelConfigTest` in `tests/test_level_config.py` (`tests/test_config.py`
is frozen); `OwnRepositoryTest` in `tests/test_own_repository.py`; `ProtectionTest` and
`MergeCallTest` in `tests/test_merge_gh.py`; `RecoveryRulesTest` in `tests/test_recovery_holds.py`,
edited; `LevelTwoBlockerTest` in `tests/test_level_2_blocker.py` (`tests/test_status.py` and
`tests/test_level_2_sentence.py` are frozen); `LevelStartTest` in `tests/test_level_2_start.py`;
`LevelMergeTest` in `tests/test_level_2_merge.py` (`tests/test_merge_wait.py` and
`tests/test_gated_merge.py` are frozen); `SessionRulesTest` in `tests/test_session_rules.py`;
`ReviewAfterTest` in `tests/test_review_after.py`. The fake `gh` in `tests/test_github.py` gains
`pr merge` (answered with `merge_code`, 0 when not given) and, for an `api` call with no
`--input`, answers from `api`, a map from the path to `{"code": n, "out": ..., "err": ...}`
(`err` written to stderr), exiting 0 with no output for a path it does not hold, as today. A
level 2 test sets no `comment_code`, which fails every `api` call.

## Notes
- Track 0 lands the holds' tests first: C13.17's `test_level_1_never_merges` (an `on` run;
  today's `config.problems` passes the unknown `level`), C13.19's and C13.20's. C13.18's tests
  exist. Breaks, each recorded in the track whose code it breaks: C13.17's, `steps` passing
  `(home, started)` at level 1 (Track E1); C13.18's, a `"pr", "close"` list (Track B, beside
  C13.5); C13.19's, the count ended on any blocker park (Track 0 on today's line, again in Track
  C, which rewrites it); C13.20's, "origin" read as a URL (`test_no_origin`) and any two origins
  read as one (`test_other_origin`) (Track A).
- The protection's required checks are this spec's addition to Levels' "main requires a pull
  request with no bypass": without them, the reviewed head could merge with checks never run,
  against P64's "on the commit the checks and the reviewer saw" (the recheck's finding).
- The tests report fixed words where a report would hold a head or a path: a break's report with a
  hash, a uuid or an absolute path is refused by `break.py` (D12.37, D12.40). C13.2's
  `<project>`, C13.7's config `<path>`, C13.11's folder and moved heads, and C13.12's head are compared with
  `<project>`, `<path>`, `<home>` and `<head>` put in their place, or asserted as booleans.
- Earlier breaks this day rewrites, re-recorded in the track that moves them: Day 07's find
  `runlog.merged(args.state, number` (Track E1, if a second call is added); Day 09's find
  `"still red after two fixes" in line` (Track C); Track D's breaks in `steps` (Track E1).
- Day 12's Notes (day-12, the gap between the green checks and the reviewer's read) leave that
  gap to Day 13. The driver does not read the checks again on the reviewed head: `on` at level 2
  requires that `main` requires its checks (C13.3), and GitHub refuses a merge of a head whose
  required checks are not green (Assumed, below).
- C13.14 checks the sentence only; that a session installs the project before its tests is first
  seen in the Day 14 trial's sessions (H13.1).
- This spec change also writes the `Plan:` lines that `specs/plan/overdue.json` held for Day 13:
  C12.10 gains N35; C11.1 gains P04, P60 and N14; C07.20 gains P07 and C08.5 gains N13 in
  `specs/plan/links-days-01-10.json`. P08 and N10 are C13.2's and C13.14's. `overdue.json` now
  holds only P54, `settled_by` 14: owned by Day 13 in `promises.json`, not built by the
  maintainer's choice (Out of scope).
- **Assumed** — `gh api` fills `{owner}/{repo}` from the project's remote: `gh api
  'repos/{owner}/{repo}/branches/main/protection' --jq '{admins: .enforce_admins.enabled, pr:
  (.required_pull_request_reviews != null)}'` in this repository → `{"admins":false,"pr":false}`
  (gh 2.93.0). This repository's `main` has classic protection with 10 required checks, no pull
  request required and admins able to bypass; `rulesets` and `rules/branches/main` give `[]`
  (the recheck's run): this repository would be refused level 2, which it never runs (C13.2).
- **Assumed** — an unprotected branch: `gh api 'repos/{owner}/{repo}/branches/dashboard-data/protection'`
  → exit 1, "gh: Branch not protected (HTTP 404)" on stderr (gh 2.93.0, the recheck's run).
- **Assumed** — `git ls-remote --get-url origin` with no origin prints "origin" and exits 0,
  outside a repository too (git 2.54.0.windows.1, the spec-auditor's run).
- **Assumed** — `gh pr merge <n> --merge --match-head-commit <sha>` merges when the head is
  `<sha>` and exits non-zero without merging when it is not, and a merge of a head whose required
  checks are not green is refused | not run: the maintainer, before Track E1, on a throwaway pull
  request in a scratch repository with a required check, once with the right sha and once with a
  wrong one, with "Do not allow bypassing" on, since the maintainer is an admin there (record the
  setting it ran with); nothing in this repository is merged by a script.
- **Assumed** — bearing's `main` requires a pull request with no bypass | not run: the
  maintainer, before Track D, with `scripts/setup-check.py` on bearing (Course correction after
  Phase 1); `on` at level 2 reads it (C13.7).
- **Hand-off** H13.1 → Day 14: N10's install seen in a trial session's transcript, before its
  tests.
- **Defect** D13.1 — found: auditor · cause: spec · made: Day 13 · C13.9 was tagged `hold`, but its test passes `level2`, a TypeError on `main` (fixed in this PR: `new`).
- **Defect** D13.2 — found: auditor · cause: spec · made: Day 13 · C13.5 named three tests that pass today beside its one red test (fixed in this PR: split into C13.5 and the hold C13.18, which carries `Replaces: C07.1`).
- **Defect** D13.3 — found: auditor · cause: spec · made: Day 13 · C13.6's second test passes today (fixed in this PR: the hold C13.19).
- **Defect** D13.4 — found: auditor · cause: spec · made: Day 13 · C13.2's `test_other_origin` passed today, and `test_same_origin` could not work: `ls-remote --get-url` echoes "origin" with no origin, and the test copy has none (fixed in this PR: the hold C13.20, and the URL set by the test).
- **Defect** D13.5 — found: auditor · cause: spec · made: Day 13 · C13.7's `test_starts_when_all_hold` passed today (fixed in this PR: it asserts the `api` calls).
- **Defect** D13.6 — found: auditor · cause: spec · made: Day 13 · a 404 exits 1 as any failure does, and the fake's `api` had no stderr (fixed in this PR: "(HTTP 404)" read from stderr, `err` in the fake).
- **Defect** D13.7 — found: auditor · cause: spec · made: Day 13 · the `gh pr merge` Assumed line named only the Day 14 trial, after every track (fixed in this PR: the maintainer's probe before Track E1).
- **Defect** D13.8 — found: auditor · cause: spec · made: Day 13 · the Notes said `overdue.json` is emptied; it holds P54 (fixed in this PR).
- **Defect** D13.9 — found: auditor · cause: spec · made: Day 13 · no result for a ruleset read without `bypass_actors` (fixed in this PR).
- **Defect** D13.10 — found: auditor · cause: spec · made: Day 13 · C13.13 parked on the merge's exit, against P64's "read from GitHub" (fixed in this PR: `pr_state` read after a failed merge).
- **Defect** D13.11 — found: auditor · cause: spec · made: Day 13 · the merge asked once, and `test_on_merges`'s `pr merge`, had no test; `wait_found`'s merge was claimed untested (fixed in this PR: C13.8 says both; the `wait_found` claim removed).
- **Defect** D13.12 — found: auditor · cause: spec · made: Day 13 · C13.2's and C13.7's lines hold absolute paths, which `break.py` refuses (fixed in this PR: Notes).
- **Defect** D13.13 — found: auditor · cause: spec · made: Day 13 · the level 2 start's place against `once.settle` and the switch log's `on` was unsaid (fixed in this PR).
- **Defect** D13.14 — found: auditor · cause: spec · made: Day 13 · Day 12's Notes leave the gap between the green checks and the reviewed head to Day 13, which did not answer it (fixed in this PR: Notes and Assumed).
- **Defect** D13.15 — found: auditor · cause: spec · made: Day 13 · C13.14 proves the sentence, not the install (fixed in this PR: H13.1).
- **Defect** D13.16 — found: auditor · cause: spec · made: Day 13 · no Track 0 for the holds, and Track E would pass 400 lines (fixed in this PR: Track 0, E1 and E2).
- **Defect** D13.17 — found: auditor · cause: spec · made: Day 13 · earlier breaks the day rewrites were not named (fixed in this PR: Notes).
- **Defect** D13.18 — found: auditor · cause: spec · made: Day 13 · C13.17's `Plan: P56` was wrong (fixed in this PR: N15), and its break would have crashed before an assertion (fixed in this PR: another break).
- **Defect** D13.19 — found: auditor · cause: spec · made: Day 13 · recheck: C13.17's break in `steps` reached no test, all of which called `wait_merge` directly or counted 0 (fixed in this PR: `test_level_1_never_merges` runs `on` counting 15).
- **Defect** D13.20 — found: auditor · cause: spec · made: Day 13 · recheck: what Track E1 does on a failed merge or with no clean `review` line was unsaid, so C13.12's and C13.13's tests could pass or hang at Track E2's start (fixed in this PR: E1's behaviour and Red-at-E2 lines, the views ending `CLOSED` or `MERGED`).
- **Defect** D13.21 — found: auditor · cause: spec · made: Day 13 · recheck: the answer to Day 12's gap rested on `main` requiring its checks, which `protection` did not read, and the Assumed line misread this repository (fixed in this PR: the checks required, C13.3's `test_no_checks`).
- **Defect** D13.22 — found: auditor · cause: spec · made: Day 13 · recheck: C13.11's moved-HEAD case gave the changes line, and holds hashes (fixed in this PR).
- **Defect** D13.23 — found: auditor · cause: spec · made: Day 13 · recheck: the holds' breaks named no track that can run them, and `test_other_origin` had none (fixed in this PR).
- **Defect** D13.25 — found: auditor · cause: spec · made: Day 13 · second recheck: with the checks' reason added, three C13.3 cases expected another reason than the order gives, and `test_gh_fails` gave no classic answer (fixed in this PR: the order, and every case's checks named).
- **Defect** D13.26 — found: auditor · cause: spec · made: Day 13 · second recheck: checks required only by a classic protection that admins bypass passed `protection`, so an admin token could merge with red checks (fixed in this PR: each requirement only from a no-bypass source, `test_checks_bypassable`; the probe with bypassing off).
- **Defect** D13.27 — found: auditor · cause: spec · made: Day 13 · second recheck: the fourth start line named only N15's condition while refusing on the checks (fixed in this PR: its own wording).
- **Defect** D13.28 — found: auditor · cause: spec · made: Day 13 · third recheck: a ruleset holding only the checks' rule was never read; `test_no_pull_request` could expect either of two reasons; `test_bypass` and C13.7's protection case did not name what their fakes require (fixed in this PR).
- **Defect** D13.24 — found: auditor · cause: spec · made: Day 13 · recheck: the 404 was probed on a missing branch, not an unprotected one (fixed in this PR).
