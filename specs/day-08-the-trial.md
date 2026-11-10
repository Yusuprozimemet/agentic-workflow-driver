# Day 08 — The trial's record: one day at level 1 in a project, what parked, what was refused, what it cost

**Phase:** 1 · **Depends on:** Day 7 · **Expected PRs:** 7 (8 with Track F)

## Goal
The driver runs one whole day of another project at level 1, the maintainer only merging and
answering parks, and that day closes with its evidence replay green. This repository holds the
record: every park and every permission refusal by name, the cost and the replies per merged pull
request beside the baseline ($1.86, 34.4), and the count Level 2 is entered on. Before the trial,
the run log keeps what the record needs: which tools were refused, one `merged` or `closed` line for
every pull request a park named, and whether the maintainer changed one before merging it.

## Before this day (the maintainer's)
The trial cannot start until these are done. Each is recorded in the record's Set-up (C08.12).

- **The trial's project** (`plan.md`, "Decisions for the maintainer", still open): one with a filled
  `plan.md` that is neither the kit nor this repository, whose next day has its spec written (the
  driver parks on "write its day spec", `plan.md`, "When the driver parks"). The day is that
  project's next one; the driver starts from its first step.
- **Required checks on the trial's `main`**: `checks` asks `gh pr checks --required`, so with none
  every step parks after `--wait-minutes` ("park: no required checks on #n after 30 minutes").
- **`driver.json`**: `project`, `human_only` (as `plan.md`, "Who does what"), `budget_usd` and
  `steps_per_night` (the open "Budget" decision).
- **The token**: fine-grained, the trial's repository only, as `plan.md`'s "The token".
- **The CLI**: updated to the version the VS Code extension runs, and the live check passed on it
  (`plan.md`, "Unverified", last item); `on` refuses an unchecked version (Day 6).
- **H03.8**: the kit's ignore list gains `evidence-rehearsal.json` and `evidence.json`, or the trial
  parks after every close (C01.4's "park: the project's tree is not clean (1 paths)").
- **H05.5**, on a scratch repository: the URL last from `gh issue create`, exit 0 from a second
  `gh issue close`, and (for C08.5) `gh pr checks <n> --required --json name,bucket,link` on a pull
  request whose one check is not required and on one with no checks at all: each exit code and
  stderr, pasted unchanged into the spec-change PR. If either stderr does not match C08.5's
  pattern, the pattern changes there, before Track B. Also `gh pr view <n> --json headRefOid` on a
  merged pull request gives its last head (C08.7, C08.8).
- **H07.1**: whether `specs/breaks/day-05.json` is corrected. Day 8 does not touch it.

## In scope

**An `end` line the readers can trust** (H07.3; `driver/runlog.py`). `_bad` also refuses an `end`
line whose `session` is not a string, and a `merged` or `closed` line whose `pr` is not an int (a
bool is not one): the log is "the run log cannot be read at line <n>", as for a `start` line
(H04.4). Today `failures()` raises `TypeError` on such an `end` line, and `open_session()` and
`last_session()` read past it.

**What was refused** (`plan.md`, Phase 1's Done when: "the record names every permission
refusal"). `runlog.end` gains `refused=None` and writes the key only when given, as `start` writes
`issue`. `once` gives it when the session's `permission_denials` is a non-empty list: one
`{"tool": <tool_name>, "input": <json.dumps(tool_input)[:200]>}` per denial, a missing `tool_name`
"unknown", a missing `tool_input` `{}`. `denials` stays the count. `status` prints, under
"refusals: <n>", one line per tool and input, most frequent first, then by text:
`  <k> <tool>: <input>`. An `end` line with no `refused` adds to the count and to no line. Whether a
hook's refusal (exit 2) appears in `permission_denials` is not known (`plan.md`, "Unverified"); the
record also reads the trial project's own refusal log.

**No checks on the real `gh`** (H06.3, D06.13; `driver/github.py`). `_gh` gains `stderr=False`;
given it, it returns the stderr as a third value. `checks` asks for it, and an exit 1 whose stderr
matches `^no (required )?checks reported on the '.*' branch` gives `("none", [], None)`. Any other
exit 1 is still "gh pr checks exited 1". The wait then reaches C06.4's park, "park: no required
checks on #<n> after <m> minutes", as it does on the fake's `[]`. No other caller of `_gh` changes.

**One `merged` or `closed` line for every pull request a park named** (H07.2, D07.30;
`driver/loop.py`, `driver/once.py`, `driver/github.py`).
- `pr_state` asks `--json state,mergeCommit,files,body,headRefOid` and returns the head as a sixth
  value; one call, as today.
- Every park line that names a pull request (`loop.py`'s "no required checks on #n", "the checks on
  #n are red", "still red after two fixes", the three of `gated`, "was closed without a merge") is
  written with `"pr": <n>`; the three of `gated` also with `"head": <the head pr_state gave>`.
- Every start that takes the lock (`--once`, `on`), after `driver_home.check`, the preflight and the
  lock and before the table, reads the run log. A log that is missing or cannot be read is passed
  over and left to the table (rows 2 and 3, C07.7, C07.21). Otherwise, for each `pr` named by a
  `park` line with no `merged` or `closed` line for it, once per `pr`: `pr_state` "MERGED" appends
  `{"event": "merged", "at", "pr", "head": <the head now>, "changed": <bool, or null>}`, `changed`
  comparing with the newest park line's `head` for that `pr`, `null` when that line has none;
  "CLOSED" appends `{"event": "closed", "at", "pr"}`; "OPEN" appends nothing. A failed read refuses:
  "cannot read the project: gh pr view exited <n>", exit 2, nothing started. The dry run writes
  nothing and reads none of this.
- `loop.wait_merge` keeps the head of its first read, the one right after the green, and on "MERGED"
  writes the same `merged` line, `changed` comparing the head at the merge with that one. A commit
  the maintainer pushed after the green is the change.

**The count Level 2 is entered on** (H06.2; `plan.md`, "Levels": "15 PRs in a row merged at level 1
without the maintainer asking for a change"). The run log cannot see a request made in chat; what it
can see is read as a change asked: a `merged` line whose `changed` is not `false`, a `closed` line, a
park "still red after two fixes". `status` prints, after the `cost` line,
`level 2: <k> of 15 pull requests in a row merged without a change asked`, where `k` counts the
`merged` lines with `"changed": false` from the newest back to the first change asked, or to a
`merged` line with no `changed` (written before Day 8), which also ends it. No `merged` line: `k` is
0.

**The trial** (no pull request here). The maintainer runs `on` on the trial's project until its
day's closing PR has merged and the driver has checked its evidence run, merging each pull request
and answering each park as it comes. A park ends the run (C05.6: "wait: parked #n", exit 0, though
`plan.md`'s Recovery row 3 says the driver waits); the maintainer closes the issue and runs `on`
again. Level 0 stays open for a park that needs a conversation. Once each, from the phone (H05.3):
open a `STOP` issue while a session runs, and close a park's issue. Nothing in this repository
changes while it runs.

**The record** (`docs/trial/`).
- `docs/trial/run.jsonl`: the trial's `state/run.jsonl`, copied byte for byte after the last step,
  and read before it is committed: a refused input can hold a secret, and the record says it was read.
- `docs/trial/day-08.md`, with these sections, in this order:
  - **Set-up**: the project and its commit at the start, the dates it ran, the CLI and `gh`
    versions, `driver.json`, the required checks, and each "Before this day" item, with its date.
  - **Steps**: `status`'s `steps:` block on the copy, unchanged, and each step's pull request.
  - **Parks**: one line per `park` line in the copy, in order: its time, its line, its issue, how it
    was answered (closed from the phone, closed after work in VS Code, a `STOP`), the issue's
    `createdAt` and `closedAt` from `gh issue view`, and the next `start` line's `at`.
  - **Refusals**: `status`'s refusal lines on the copy, unchanged, and what each step was doing;
    then the trial project's `.claude/state/refusals.jsonl` lines inside the trial's dates.
  - **Cost**: `status`'s `cost` and `level 2` lines on the copy, unchanged; then
    `cost per merged pull request: $<x.xx> (baseline $1.86)` and
    `replies per merged pull request: <y.y> (baseline 34.4)`, the replies from
    `token-usage.py --compare --repo <the project> --split <the trial's first date>`'s later side,
    which also counts any interactive session in those dates; the record says how many there were.
  - **The phone** (H05.3): `STOP: opened <stamp>, halted <stamp>, <s> s`, the issue's `createdAt`
    and the halt file's "halted at"; `park closed: <stamp>, started again <stamp>, <s> s`, the
    issue's `closedAt` and the next `start` line's `at`.
  - **The usage limit** (H06.1): the session's JSON fields when it was met, unchanged, or "not met".
  - **Unverified**: for each item of `plan.md`'s "Unverified" the trial touched, what it showed.
  - **Evidence**: `closing PR: #<n>`, `merge commit: <40 hex>`, `evidence run: <id>`,
    `conclusion: success`, from the trial repository's `gh run view <id> --exit-status`.
- `tests/test_trial_record.py` reads both files.

**The usage limit, if the trial met it** (H06.1; Track F). `once.outcome` names the limit from the
fields the record quotes, and the driver waits until the reset the session reports, then resumes the
same session once (`--resume <id>`); a second limit, or no reset time, parks "park: the usage limit
was reached (session `<id>`)". Its exact fields and lines come in a spec-change PR before Track F.
If the trial did not meet it, Track F does not open.

## Out of scope
- Level 2: the driver's merge, the second Windows account, `main`'s protection, the reviewer — after
  the stop (`plan.md`, "Stopping points"). Day 8 counts toward Level 2 and enters nothing.
- A request for a change made in chat or in a PR comment: the run log cannot see it, so the count
  may be too high; the record says so. A comment reader is Phase 2's, if the maintainer wants one.
- A wait on an open park inside `on` (Recovery row 3's wording against C05.6): the stop's
  plan-auditor, if the trial shows it is wanted.
- What state a `--max-budget-usd` stop leaves a branch in beyond what the trial happens to show.
- Correcting `specs/breaks/day-05.json` (H07.1, the maintainer's).
- The plan-auditor on the whole plan: the stop's own step, after Day 8's close merges.
- Any change to `driver/decide.py`, `driver/steps.py`, `driver/settings.py`, `driver/home.py`,
  `driver/preflight.py`, `driver/config.py`, `hooks/` and `rules/session.md`.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | The run log's `end`, `merged` and `closed` lines checked, the refused tools: C08.3, C08.4 |
| B | | No checks on the real `gh`: C08.5, C08.6 |
| C | | Park lines with their pull request; `merged` and `closed` at a start and after the wait: C08.7–C08.9 |
| D | | `status`: the refusals by tool, the Level 2 count: C08.2, C08.10 |
| E | | After the maintainer's trial, on the project: the record and its test: C08.11–C08.14 |
| F | | The usage limit, only if the trial met it: C08.15 |

C08.1 is proved in the spec-change PR. Track C is the largest (code, and edits to
`tests/test_merge_wait.py`, `tests/test_on.py`, `tests/test_github.py` and
`tests/test_runlog_report.py`); split it at the start-time read if it passes 400 lines.

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").

- [ ] C08.1 **hold** — The files Day 8 does not change are unchanged since `f9f43fd`: Verify's diff
      prints nothing.
      broken: a byte added to driver/decide.py → import re (spec-change PR)
- [ ] C08.2 **hold** — Day 7's `status` block still prints exactly for a log with no `refused`, no
      `changed` and no `closed` line: the nine `StatusTest` cases pass, their expected lists only
      gaining the `level 2` line (C08.10).
      Test: `StatusTest` (all nine).
      broken: <`status` drops the `refusals` line> → <what it reported>
- [ ] C08.3 **new** — An `end` line whose `session` is `["s1"]`, or a `merged` line whose `pr` is
      `true` or `"3"`, makes `runlog.read`, `failures` and `open_session` give "the run log cannot
      be read at line <n>", `last_session` give `None`, and `status` print "run log: the run log
      cannot be read at line <n>", exit 2.
      Red today: `failures` raises `TypeError: unhashable type: 'list'`; `open_session` gives
      `('s1', None)`; a `merged` line with `pr` `true` is read as fine.
      Test: `RunlogEndTest.test_end_session_not_string`, `RunlogEndTest.test_merged_pr_not_int`.
- [ ] C08.4 **new** — A session whose result holds two `permission_denials`
      (`{"tool_name": "Bash", "tool_input": {"command": "git push --force"}}` and one with neither
      key) writes an `end` line with `"denials": 2` and `"refused": [{"tool": "Bash", "input":
      "{\"command\": \"git push --force\"}"}, {"tool": "unknown", "input": "{}"}]`; an input of
      500 characters is cut to 200; a session with none writes no `refused` key.
      Red today: `KeyError: 'refused'`.
      Test: `RefusedTest.test_end_names_refused_tools`, `RefusedTest.test_input_cut`.
- [ ] C08.5 **new** — With a fake `gh` that exits 1 and writes "no required checks reported on the
      'day-01/track-a-x' branch" (or "no checks reported on the 'day-01/track-a-x' branch") to
      stderr, `checks` gives `("none", [], None)`, and the wait on that pull request parks "park: no
      required checks on #7 after 0.01 minutes", exit 1.
      Red today: `checks` gives `(None, [], "gh pr checks exited 1")`, and the wait ends "cannot
      read the project: gh pr checks exited 1", exit 2.
      Test: `ChecksNoneTest.test_no_required_checks`, `ChecksNoneTest.test_no_checks`,
      `ChecksNoneTest.test_wait_parks`.
      Replaces: C06.2 — was: every exit 1 of `gh pr checks` gives "gh pr checks exited 1".
- [ ] C08.6 **hold** — An exit 1 of `gh pr checks` with any other stderr, or none, still gives
      "gh pr checks exited 1".
      Test: `ChecksNoneTest.test_other_exit_1`, `GitHubTest.test_checks`.
      broken: <`checks` takes every exit 1 as "none"> → <what it reported>
- [ ] C08.7 **new** — A green pull request that touches a human-only path parks with a `park` line
      carrying `"pr": 7` and the head the fake gives; at the next `--once`, with the fake saying
      "MERGED" and the same head, the log gains `{"event": "merged", "pr": 7, "head": <it>,
      "changed": false}` before the table is read, and a second start adds no second line. Two
      park lines for #7 give one `merged` line, compared with the newer's head. A new head at the
      merge gives `"changed": true`; a park "the checks on #7 are red" then "MERGED" gives
      `"changed": null`; "CLOSED" gives `{"event": "closed", "pr": 7}`; a failing `gh pr view`
      prints "cannot read the project: gh pr view exited 1", exit 2, and starts no session; a torn
      log still parks as C07.21 says.
      Red today: the `park` line has no `pr`, and no start writes a `merged` or `closed` line (D07.30).
      Test: `GatedMergeTest.test_merged_after_park`, `GatedMergeTest.test_two_parks_one_line`,
      `GatedMergeTest.test_changed`, `GatedMergeTest.test_red_park_null`,
      `GatedMergeTest.test_closed`, `GatedMergeTest.test_gh_fails`.
      Replaces: C07.16 — was: a `park` line is `{"event", "at", "step", "line"}` and a `merged`
      line `{"event", "at", "pr"}`.
- [ ] C08.8 **new** — In `on`, a pull request whose head is `aaa` at its first read after the green
      and `bbb` when it merges writes a `merged` line with `"head": "bbb"`, `"changed": true`; the
      same head writes `"changed": false`. `pr_state` makes one `gh pr view` call per read, asking
      `state,mergeCommit,files,body,headRefOid`.
      Red today: the `merged` line is `{"event", "at", "pr"}` only, and `pr_state` asks no head.
      Test: `MergeWaitHeadTest.test_changed`, `MergeWaitHeadTest.test_unchanged`,
      `GitHubTest.test_pr_state`.
      Replaces: C06.2 — was: `pr_state` asks `state,mergeCommit,files,body` and returns five values.
- [ ] C08.9 **hold** — An open pull request a park named adds no line at a start, and `--dry-run`
      on a log with a gated park writes nothing and calls no `gh pr view`.
      Test: `GatedMergeTest.test_open_adds_nothing`, `GatedMergeTest.test_dry_run_writes_nothing`.
      broken: <the start-time read appends `merged` for "OPEN"> → <what it reported>
- [ ] C08.10 **new** — `status` on a log built by the test prints, under "refusals: 3", the lines
      "  2 Bash: {\"command\": \"git push --force\"}" and "  1 Edit: {}", and after the `cost` line
      "level 2: 2 of 15 pull requests in a row merged without a change asked" for, oldest first,
      `merged` (changed false), a park "still red after two fixes", `merged` (false), `merged`
      (false). A `closed` line, a `merged` line with `changed` `null` or with no `changed` ends the
      count there; no `merged` line gives "level 2: 0 of 15 pull requests in a row merged without a
      change asked".
      Red today: no line after `cost`, and no line under `refusals`.
      Test: `StatusTrialTest.test_refused_lines`, `StatusTrialTest.test_level_2_count`,
      `StatusTrialTest.test_count_ends`.
      Replaces: C07.17 — was: the block ended at the `cost` line, and `refusals` was one line.
- [ ] C08.11 **new** — The trial ran: `docs/trial/run.jsonl` reads without a reason, holds a
      `start` line for each step the record's Steps names, each with its own session, and every
      `start` line's session is one no earlier `start` line used.
      Red today: `docs/trial/run.jsonl` does not exist.
      Test: `TrialRecordTest.test_run_log_is_a_trial`.
- [ ] C08.12 **new** — The record names every park and every permission refusal, and its `cost`
      line is the one `status` gives on the copy of the run log.
      Red today: `docs/trial/day-08.md` does not exist.
      Test: `TrialRecordTest.test_every_park_named`, `TrialRecordTest.test_every_refusal_named`,
      `TrialRecordTest.test_cost_line_is_status`.
- [ ] C08.13 **new** — The trial's day closed with its evidence replay green: the record's Evidence
      section names the closing PR, a merge commit of 40 hex characters, an evidence run id and
      "conclusion: success", and the copy holds a `merged` line for that pull request.
      Red today: `docs/trial/day-08.md` does not exist.
      Test: `TrialRecordTest.test_evidence_section`.
- [ ] C08.14 **new** — A `STOP` opened from the phone halted the driver, and a park closed from the
      phone was followed by the next start, each with its two times and the seconds between in the
      record's The phone section (H05.3).
      Red today: `docs/trial/day-08.md` does not exist.
      Test: `TrialRecordTest.test_phone_lines`.
- [ ] C08.15 **new** — If the trial met the usage limit: a fake session ending with the fields the
      record quotes waits until its reset and resumes the same session once; a second one parks
      "park: the usage limit was reached (session `<id>`)". If it did not, this box stays unticked
      with "Not proven: the trial did not meet the limit", and H06.1 goes on to the maintainer.
      Red today: such a session parks with a Day 4 line ("the session ended in an error: …" or
      another), with no wait.
      Test: `UsageLimitTest.test_waits_and_resumes`, `UsageLimitTest.test_second_limit_parks`.

## Verify
```bash
python -m unittest discover -s tests
git -c core.safecrlf=false diff --exit-code f9f43fd -- tests/test_contract.py tests/test_decide.py tests/test_dry_run.py tests/test_steps.py tests/test_tree.py tests/test_config.py tests/test_encoding.py tests/test_halt.py tests/test_halt_report.py tests/test_home.py tests/test_hooks.py tests/test_issues.py tests/test_off.py tests/test_once_park_issues.py tests/test_once_parks.py tests/test_preflight.py tests/test_recovery_table.py tests/test_lock_takeover.py driver/decide.py driver/steps.py driver/settings.py driver/home.py driver/preflight.py driver/config.py hooks rules/session.md
```

## Notes
- Picks up H05.3 (C08.14), H06.1 (C08.15), H06.2 (C08.8, C08.10), H06.3 (C08.5), H07.2 (C08.7) and
  H07.3 (C08.3). H07.1 and the rest of "Before this day" are the maintainer's.
- "Without the maintainer asking for a change" is read as what the run log can see: a commit after
  the green, a pull request closed unmerged, a red after two fixes, or a merge after a park whose
  head was not kept (`changed` `null`). A request made in chat, or a PR comment, does not reset the
  count. A gated park the maintainer merges unchanged does not reset it: Level 2 would not merge
  those, and the maintainer changed nothing.
- C06.2 is replaced twice, once for `checks` (C08.5) and once for `pr_state` (C08.8): one criterion
  held both.
- `refused`'s input is cut to 200 characters so a long `Write` does not put a file into the log.
- C08.11 to C08.14 are proved by the trial; what CI replays of them is `TrialRecordTest`, which reads
  the committed record, not the trial's repository.
- Day 8 is a stopping point (`plan.md`, "Stopping points"): after its close merges, the plan-auditor
  reads the whole plan, and nothing of Phase 2 is specified until a "Course correction after Phase
  1" lifts the stop.
- Spec-auditor, 2026-11-10, on `main` at `f9f43fd`, on the draft: 16 findings, all taken up (see the
  spec-change PR). The Red today claims held.
- **Defect** D08.1 — found: auditor · cause: spec · made: Day 08 · three `new` criteria sat in a maintainer row of the Tracks table that "Track tests seen red" does not read, two had no `Test:` field and one named a class, not a test; moved to Track E with `TrialRecordTest` cases.
- **Defect** D08.2 — found: auditor · cause: spec · made: Day 08 · C08.11's evidence was a `gh` command the replay does not run, and C08.9 named a command the replay would count but never run; both now proved by tests.
- **Defect** D08.3 — found: auditor · cause: spec · made: Day 08 · the phone's park half timed the driver "going on", but a park ends the run (C05.6) and the driver prints no times; now timed from the issue's `closedAt` and the next `start` line.
- **Defect** D08.4 — found: auditor · cause: spec · made: Day 08 · the `merged` line's new keys changed C07.16 with no `Replaces:`, and a separate `gh pr view` for the head would have shifted the fake's answers in Day 6's tests; now `pr_state` asks the head, with `Replaces:` on C07.16 and C06.2.
- **Defect** D08.5 — found: auditor · cause: spec · made: Day 08 · C08.5 changed C06.2 with no `Replaces:`, and its pattern missed `gh`'s "no checks reported" for a pull request with no checks at all.
- **Defect** D08.6 — found: auditor · cause: spec · made: Day 08 · Track 0 had nothing to land: C08.1's check is Verify's diff, and C08.2's edited tests fail before Track D; Track 0 dropped, C08.2 moved to D.
- **Defect** D08.7 — found: auditor · cause: spec · made: Day 08 · the start-time read did not say what it does with a missing or torn log, which C07.7 and C07.21 pin; now it passes them over to the table.
- **Defect** D08.8 — found: auditor · cause: spec · made: Day 08 · two park lines for one pull request would have written two `merged` lines, counting it twice; now one line per `pr`.
- **Defect** D08.9 — found: auditor · cause: spec · made: Day 08 · only the three gated parks carried their pull request, so one merged by hand after any other park was not counted, and one closed unmerged reset nothing; every park that names one now carries it, and a `closed` line is written.
- **Defect** D08.10 — found: auditor · cause: spec · made: Day 08 · nothing asked for required checks on the trial's `main`, without which every step parks after `--wait-minutes`.
- **Defect** D08.11 — found: auditor · cause: spec · made: Day 08 · the record read refusals only from `permission_denials`, which may not hold a hook's refusal; it now also reads the trial project's refusal log.
- **Defect** D08.12 — found: auditor · cause: spec · made: Day 08 · `token-usage.py --compare --repo` cannot pick out the driver's sessions; now split at the trial's first date, interactive sessions counted and named.
- **Defect** D08.13 — found: auditor · cause: spec · made: Day 08 · three tests named under `new` criteria pass today; moved to the `hold` criteria C08.6 and C08.9.
- **Defect** D08.14 — found: auditor · cause: spec · made: Day 08 · a `refused` key written on every `end` line would break `RunLogTest.test_end_line`, which asserts the line's six keys; now written only when given.
- **Defect** D08.15 — found: auditor · cause: spec · made: Day 08 · the run log's copy goes into the repository with up to 200 characters of each refused input; it is now read before it is committed.
- **Defect** D08.16 — found: auditor · cause: process · made: none · `specs/README.md`'s map still said "Days 7-8 titles" after Day 7 closed; corrected here.
