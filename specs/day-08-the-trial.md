# Day 08 — The trial's record: one day at level 1 in a project, what parked, what was refused, what it cost

**Phase:** 1 · **Depends on:** Day 7 · **Expected PRs:** 8 (9 with Track F)

## Goal
The driver runs one whole day of another project at level 1, the maintainer only merging and
answering parks, and that day closes with its evidence replay green. This repository holds the
record: every park and every permission refusal by name, the cost and the replies per merged pull
request beside the baseline ($1.86, 34.4), and the count Level 2 is entered on. Before the trial,
the run log keeps what the record needs: which tools were refused, one `merged` or `closed` line for
every pull request a park or a left wait named, and whether the maintainer changed one before merging it.

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
  (`plan.md`, "Unverified", last item); `on` refuses an unchecked version (Day 6). **Before Track
  A**, on that CLI: one `claude -p` session with one denied tool call, its `permission_denials`
  pasted unchanged into Track A's PR; a shape other than C08.4's is a spec change first.
- **H03.8**: the kit's ignore list gains `evidence-rehearsal.json` and `evidence.json`, or the trial
  parks after every close (C01.4's "park: the project's tree is not clean (1 paths)").
- **H05.5**, on a scratch repository, before Track B: the URL last from `gh issue create`, and exit 0
  from a second `gh issue close`, each pasted unchanged into Track B's PR. The `gh pr checks` part is
  settled by reads (Notes, Assumed).
- **The run log**: the trial starts from an empty `state/run.jsonl` (no `state/` folder), so the
  copy holds the trial's lines only.
- **H07.1**: whether `specs/breaks/day-05.json` is corrected. Day 8 does not touch it.

## In scope

**A run log the readers can trust** (H07.3; `driver/runlog.py`). `_bad` also refuses an `end` line
whose `session` is not a string, or whose `refused` is present and not a list of objects with a
string `tool` and `input`; a `merged`, `closed`, `park` or `left` line whose `pr` (required on the
first two) is not an int (a bool is not one); and a `park`, `left` or `merged` line whose `head` is
present and not a string. The log is then "the run log cannot be read at line <n>", as for a `start`
line (H04.4). Today `failures()` and `issue_cost()` raise `TypeError` on a list `session`, and
`open_session()` and `last_session()` read past it.

**What was refused** (`plan.md`, Phase 1's Done when: "the record names every permission
refusal"). `runlog.end` gains `refused=None` and writes the key only when given, as `start` writes
`issue`. `once` gives it when the session's `permission_denials` is a non-empty list: one
`{"tool": <tool_name>, "input": <json.dumps(tool_input)[:200]>}` per denial, a missing or non-string
`tool_name` "unknown", a missing `tool_input` `{}`, an entry that is not an object
`{"tool": "unknown", "input": "{}"}`. `denials` stays the count. `status` prints, under
"refusals: <n>", one line per tool and input, most frequent first, then by text:
`  <k> <tool>: <input>`. An `end` line with no `refused` adds to the count and to no line. Whether a
hook's refusal (exit 2) appears in `permission_denials` is not known (`plan.md`, "Unverified"), and
the driver's `hooks/guard.py` logs its refusals nowhere (`hooks/` is out of scope): the record also
reads the trial project's own refusal log, and its Unverified section says which refusals it saw
in `permission_denials`.

**No checks on the real `gh`** (H06.3, D06.13; `driver/github.py`). `_gh` gains `stderr=False`;
given it, it returns the stderr as a third value. `checks` asks for it, and an exit 1 whose stderr
matches `^no (required )?checks reported on the '.*' branch` gives `("none", [], None)`. Any other
exit 1 is still "gh pr checks exited 1". The wait then reaches C06.4's park, "park: no required
checks on #<n> after <m> minutes", as it does on the fake's `[]`. No other caller of `_gh` changes.
The shared fake `gh` (`FAKE` in `tests/test_github.py`) gains an `err` key per answer, written to
stderr; answers without it write none.

**One `merged` or `closed` line for every pull request a park or a left wait named** (H07.2,
D07.30; `driver/loop.py`, `driver/once.py`, `driver/github.py`, `driver/runlog.py`).
- `pr_state` asks `--json state,mergeCommit,files,body,headRefOid` and returns the head as a sixth
  value; one call, as today.
- A park line whose line names one pull request (`loop.py`'s "no required checks on #n", "the checks
  on #n are red", "still red after two fixes", the three of `gated`, "was closed without a merge")
  is written with `"pr": <n>`; the three of `gated` also with `"head": <the head pr_state gave>`.
  `wait_merge` returns that head with its park line, and `once.finish` and `once.park_issue` take
  `pr` and `head` as keyword arguments with defaults (`tests/test_park_body.py` calls it with seven
  positional ones). A park that names no pull request, or more than one, has no `pr` key, even after
  a wait in the same run: the record's `pr` is that wait's only.
- A wait in `on` that ends any way other than a merge or a park (a halt, a `STOP`, the run's issue
  closed, a failed read) appends `{"event": "left", "at", "pr", "line"}`, with `"head"` when
  `wait_merge` had read one.
- Every start that takes the lock (`--once`, `on`), after `driver_home.check`, the preflight and the
  lock and before the table, reads the run log. A log that is missing or cannot be read is passed
  over and left to the table (rows 2 and 3, C07.7, C07.21). Otherwise, for each `pr` named by a
  `park` or `left` line with no `merged` or `closed` line for it, once per `pr`: `pr_state` "MERGED"
  appends `{"event": "merged", "at", "pr", "head": <the head now>, "changed": <bool, or null>}`,
  `changed` comparing with the newest such line's `head` for that `pr`, `null` when either head is
  unknown; "CLOSED" appends `{"event": "closed", "at", "pr"}`; "OPEN" appends nothing. A failed read
  refuses: "cannot read the project: gh pr view exited <n>", exit 2, nothing started. The dry run
  writes nothing and reads none of this.
- `loop.wait_merge` keeps the head of its first successful read after the green, and on "MERGED"
  writes the same `merged` line, `changed` comparing the head at the merge with that one, `null`
  when either is unknown. A commit the maintainer pushed after the green is the change.

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
open a `STOP` issue while the driver waits on a pull request (a `STOP` during a session leaves a
`start` line with no `end`, which parks the next start and needs VS Code), copying the halt file's
text before `run-steps.py clear` deletes it; and close a park's issue. Nothing in this repository
changes while it runs.

**The record** (`docs/trial/`).
- `docs/trial/run.jsonl`: the trial's `state/run.jsonl`, copied byte for byte after the last step,
  then read before it is committed: a refused input can hold a secret. A secret is replaced with
  `<secret>` in the copy and in the record, and the record names the lines changed, or says none was.
- `docs/trial/day-08.md`, with these sections, in this order:
  - **Set-up**: the project and its commit at the start, the dates it ran, the CLI and `gh`
    versions, `driver.json`, the required checks, and each "Before this day" item, with its date.
  - **Steps**: `status`'s `steps:` block on the copy, unchanged, and each step's pull request.
  - **Parks**: one line per `park` line in the copy, in order: its time, its line, its issue, how it
    was answered (closed from the phone, closed after work in VS Code, a `STOP`), the issue's
    `createdAt` and `closedAt` from `gh issue view`, and the next `start` line's `at`.
  - **Refusals**: `status`'s refusal lines on the copy, unchanged, and what each step was doing;
    then the trial project's `.claude/state/refusals.jsonl` lines inside the trial's dates.
  - **Cost**: `status`'s `cost` and `level 2` lines on the copy, unchanged (the sessions'
    `total_cost_usd`); then `cost per merged pull request: $<x.xx> (baseline $1.86)` and
    `replies per merged pull request: <y.y> (baseline 34.4)`, both from the later side of
    `token-usage.py --compare --repo <the project> --split <the trial's first date>` (its list-price
    dollars over its pull requests, the baseline's own measure), which also counts any interactive
    session in those dates; the record says how many there were.
  - **The phone** (H05.3): `STOP: opened <stamp>, halted <stamp>, <s> s`, the issue's `createdAt`
    and the copied halt file's "halted at"; `park closed: <stamp>, started again <stamp>, <s> s`,
    the issue's `closedAt` and the next `start` line's `at`.
  - **The usage limit** (H06.1): the session's JSON fields when it was met, unchanged, or "not met".
  - **Unverified**: for each item of `plan.md`'s "Unverified" the trial touched, what it showed.
  - **Evidence**: `closing PR: #<n>`, `merge commit: <40 hex>`, `evidence run: <id>`,
    `conclusion: success`, from the trial repository's `gh run view <id> --json conclusion`.
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
- A refusal log for `hooks/guard.py`: the stop's plan-auditor, if the trial shows its refusals are
  missing from `permission_denials`.
- The plan-auditor on the whole plan: the stop's own step, after Day 8's close merges.
- Any change to `driver/decide.py`, `driver/steps.py`, `driver/settings.py`, `driver/home.py`,
  `driver/preflight.py`, `driver/config.py`, `hooks/` and `rules/session.md`.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | The run log's lines checked, the refused tools: C08.3, C08.4 |
| B | | No checks on the real `gh`, the fake's stderr: C08.5, C08.6 |
| C1 | | `pr_state`'s head; park and `left` lines with their pull request; `wait_merge`'s `merged` line: C08.8 |
| C2 | | `merged` and `closed` at a start, in `--once` and `on`: C08.7, C08.9 |
| D | | `status`: the refusals by tool, the Level 2 count: C08.2, C08.10 |
| E | | After the maintainer's trial, on the project: the record and its test: C08.11–C08.14 |
| F | | The usage limit, only if the trial met it: C08.15 |

C08.1 is proved in the spec-change PR. Day 7's comparable tracks measured 245 to 398 lines, so
Track C is split before it starts. C1 edits `tests/test_merge_wait.py`, `tests/test_github.py` and
`tests/test_runlog_report.py`; C2 `tests/test_on.py` and the `--once` cases, which rewrite
`fake.json` after the frozen `tests/test_once_park_issues.py` `build()`, as it takes no `views`.

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").

- [ ] C08.1 **hold** — The files Day 8 does not change are unchanged since `f9f43fd`: Verify's diff
      prints nothing.
      broken: a byte added to driver/decide.py → import re (#111)
- [ ] C08.2 **hold** — Day 7's `status` block still prints exactly for a log with no `refused`, no
      `changed` and no `closed` line: the nine `StatusTest` cases pass, `test_full_report`,
      `test_no_parks` and `test_gh_down` only gaining the `level 2` line, and `test_no_merged`
      reading its `cost` line as the last but one (C08.10).
      Test: `StatusTest` (all nine).
      broken: <`status` drops the `refusals` line> → <what it reported>
- [ ] C08.3 **new** — An `end` line whose `session` is `["s1"]` or whose `refused` is `"x"`, a
      `merged` line whose `pr` is `true` or `"3"`, or a `park` line whose `pr` is `true`, makes
      `runlog.read`, `failures` and `open_session` give "the run log cannot be read at line <n>",
      `last_session` give `None`, and `status` print "run log: the run log cannot be read at line
      <n>", exit 2.
      Red today: `failures` and `issue_cost` raise `TypeError: unhashable type: 'list'`;
      `open_session` gives `('s1', None)`; the other lines are read as fine.
      Test: `RunlogEndTest.test_end_session_not_string`, `RunlogEndTest.test_merged_pr_not_int`,
      `RunlogEndTest.test_park_pr_not_int`, `RunlogEndTest.test_refused_not_list`.
- [ ] C08.4 **new** — A session whose result holds three `permission_denials`
      (`{"tool_name": "Bash", "tool_input": {"command": "git push --force"}}`, one with neither key,
      and `"x"`) writes an `end` line with `"denials": 3` and `"refused": [{"tool": "Bash", "input":
      "{\"command\": \"git push --force\"}"}, {"tool": "unknown", "input": "{}"}, {"tool":
      "unknown", "input": "{}"}]`; a `tool_name` of `null` is "unknown"; an input of 500
      characters is cut to 200; a session with none writes no `refused` key.
      Red today: `KeyError: 'refused'`.
      Test: `RefusedTest.test_end_names_refused_tools`, `RefusedTest.test_malformed_denials`,
      `RefusedTest.test_input_cut`.
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
      carrying `"pr": 7` and the head the fake gives; at the next `--once`, and at the next `on`,
      with the fake saying "MERGED" and the same head, the log gains a `merged` line with
      `"pr": 7`, `"head": "aaa"`, `"changed": false` before the table is read, and a second start
      adds no second line. Two park lines for #7 give one `merged` line, compared with the newer's
      head. A new head at the merge gives `"changed": true`; a park "the checks on #7 are red" then
      "MERGED" gives `"changed": null`; a `left` line for #7 then "MERGED" gives a `merged` line;
      "CLOSED" gives a `closed` line with `"pr": 7`; a failing `gh pr view` prints "cannot read
      the project: gh pr view exited 1", exit 2, and starts no session; a torn log still parks as C07.21 says. The tests
      compare each line's `event`, `pr`, `head` and `changed` only, with heads "aaa" and "bbb".
      Red today: the `park` line has no `pr`, and no start writes a `merged` or `closed` line (D07.30).
      Test: `GatedMergeTest.test_merged_after_park`, `GatedMergeTest.test_on_writes_merged_at_start`,
      `GatedMergeTest.test_two_parks_one_line`, `GatedMergeTest.test_changed`,
      `GatedMergeTest.test_red_park_null`, `GatedMergeTest.test_left_wait_merged`,
      `GatedMergeTest.test_closed`, `GatedMergeTest.test_gh_fails`.
      Replaces: C07.16 — was: a `park` line is `{"event", "at", "step", "line"}` and a `merged`
      line `{"event", "at", "pr"}`.
- [ ] C08.8 **new** — In `on`, a pull request whose head is "aaa" at its first successful read
      after the green and "bbb" when it merges writes a `merged` line with `"head": "bbb"`,
      `"changed": true`; the same head writes `"changed": false`; no head at either read writes
      `"changed": null`. A `STOP` during that wait writes a `left` line with `"pr": 7` and
      `"head": "aaa"`; a park after that run's merged step that names no pull request has no `pr`
      key. `pr_state` makes one `gh pr view` call per read, asking
      `state,mergeCommit,files,body,headRefOid`.
      Red today: the `merged` line is `{"event", "at", "pr"}` only, a left wait writes no line, and
      `GitHubTest.test_pr_state` as Track C1 edits it fails on today's `pr_state`, which asks no head.
      Test: `MergeWaitHeadTest.test_changed`, `MergeWaitHeadTest.test_unchanged`,
      `MergeWaitHeadTest.test_no_head`, `MergeWaitHeadTest.test_stop_writes_left`,
      `MergeWaitHeadTest.test_park_without_pr`, `GitHubTest.test_pr_state`.
      Replaces: C06.2 — was: `pr_state` asks `state,mergeCommit,files,body` and returns five values.
- [ ] C08.9 **hold** — An open pull request a park named adds no line at a start, and `--dry-run`
      on a log with a gated park writes nothing and calls no `gh pr view`.
      Test: `GatedMergeTest.test_open_adds_nothing`, `GatedMergeTest.test_dry_run_writes_nothing`.
      broken: <the start-time read appends `merged` for "OPEN"> → <what it reported>
- [ ] C08.10 **new** — `status` on a log built by the test prints, under "refusals: 3", the lines
      "  2 Bash: {"command": "git push --force"}" and "  1 Edit: {}" (as printed, no backslashes),
      and after the `cost` line "level 2: 2 of 15 pull requests in a row merged without a change
      asked" for, oldest first, `merged` (changed false), a park "still red after two fixes",
      `merged` (false), `merged` (false). A `closed` line, a `merged` line with `changed` `null` or
      with no `changed` ends the count there; no `merged` line gives "level 2: 0 of 15 pull requests
      in a row merged without a change asked".
      Red today: no line after `cost`, and no line under `refusals`.
      Test: `StatusTrialTest.test_refused_lines`, `StatusTrialTest.test_level_2_count`,
      `StatusTrialTest.test_count_ends`.
      Replaces: C07.17 — was: the block ended at the `cost` line, and `refusals` was one line.
- [ ] C08.11 **new** — The trial ran: `docs/trial/run.jsonl` reads without a reason, every `start`
      line in it has an `end` line, every `merged` line names a pull request the record's Steps
      names, and the Steps' pull requests that merged each have one.
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
  those, and the maintainer changed nothing. GitHub's "Update branch", or a rebase, changes the head
  and so counts as a change asked: too strict, not too lenient.
- C06.2 is replaced twice, once for `checks` (C08.5) and once for `pr_state` (C08.8): one criterion
  held both.
- `refused`'s input is cut to 200 characters so a long `Write` does not put a file into the log.
- C08.11 to C08.14 are proved by the trial; what CI replays of them is `TrialRecordTest`, which reads
  the committed record, not the trial's repository.
- If the driver's own guard refusals do not appear in `permission_denials`, "every permission
  refusal" in the record means every one the run log and the kit's guards saw; the record's
  Unverified section says so, and the stop's plan-auditor weighs a log for `hooks/guard.py`.
- Day 8 is a stopping point (`plan.md`, "Stopping points"): after its close merges, the plan-auditor
  reads the whole plan, and nothing of Phase 2 is specified until a "Course correction after Phase
  1" lifts the stop.
- Spec-auditor, 2026-11-10, on `main` at `f9f43fd`, on the draft: 16 findings, all taken up (see the
  spec-change PR). The Red today claims held.
- Spec-auditor again, 2026-11-10, with #112's brief, on this branch with `main` at `cf58647` merged
  in: 24 findings (D08.17 to D08.40), all taken up. The Red today claims held.
- **Assumed** — `gh pr checks --required` on a pull request with no checks, and with checks none of
  them required, exits 1, empty stdout, and writes "no checks reported on the '<b>' branch" /
  "no required checks reported on the '<b>' branch": `gh pr checks 1 --repo octocat/Hello-World
  --required --json name,bucket,link` and `gh pr checks 3912 --repo pallets/click --required --json
  name,bucket` → those lines, gh 2.93.0.
- **Assumed** — `headRefOid` on a merged pull request is its last head: `gh pr view 113 --json
  headRefOid` → `101d29b7…`, the last commit of `gh api repos/Yusuprozimemet/agentic-workflow-driver/pulls/113/commits`,
  gh 2.93.0; a merge commit, not a squash.
- **Assumed** — `gh issue view --json createdAt,closedAt` gives both as UTC stamps ending "Z":
  `gh issue view 1 --repo octocat/Hello-World --json createdAt,closedAt` → both, gh 2.93.0.
- **Assumed** — `gh run view <id> --exit-status` prints no conclusion; `--json conclusion` does:
  `gh run view 42805769752 --exit-status` → exit 0, "✓ main Evidence replay · 42805769752", gh 2.93.0.
- **Assumed** — a `permission_denials` entry is `{"tool_name", "tool_input"}` | not run: the
  maintainer, before Track A ("Before this day", The CLI).
- **Assumed** — a hook's exit-2 refusal appears in `permission_denials` | not run: the trial; the
  record's Unverified section.
- **Assumed** — `gh issue create` prints the URL last; a second `gh issue close` exits 0 | not run
  (writes): the maintainer, before Track B (H05.5).
- **Assumed** — `token-usage.py` counts the driver's headless transcripts | not run: the trial.
- **Assumed** — `--resume <id>` resumes a session after a usage limit | not run: Track F, if it opens.
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
- **Defect** D08.17 — found: auditor · cause: process · made: none · the spec had no `Assumed` line, which #112 made a rule after it was written; added, the `permission_denials` shape given to the maintainer before Track A.
- **Defect** D08.18 — found: auditor · cause: spec · made: Day 08 · H05.5's `gh pr checks` part was set as a scratch-repository task, but it is a read: the auditor ran it, it matches C08.5's pattern, and it is now an `Assumed` line.
- **Defect** D08.19 — found: auditor · cause: spec · made: Day 08 · C08.1's `broken:` line ended "(spec-change PR)", which the replay does not strip, and had no `manifest:` line; now break.py's lines as printed, ending "(#111)".
- **Defect** D08.20 — found: auditor · cause: spec · made: Day 08 · `_bad` did not check a park line's `pr`, so `"pr": true` would refuse every later start until the log was edited by hand; now refused, with a C08.3 case.
- **Defect** D08.21 — found: auditor · cause: spec · made: Day 08 · the start-time read in `on`, the path the trial uses, had no test; `GatedMergeTest.test_on_writes_merged_at_start` added.
- **Defect** D08.22 — found: auditor · cause: spec · made: Day 08 · a wait that ended with no park (a halt, a `STOP`, a failed read) wrote no line, so a pull request merged after it was never counted; now a `left` line, read at a start as a park is.
- **Defect** D08.23 — found: auditor · cause: spec · made: Day 08 · the record was to name every permission refusal, but `hooks/guard.py` logs its refusals nowhere; the gap is now stated, and the record's Unverified section answers it.
- **Defect** D08.24 — found: auditor · cause: spec · made: Day 08 · C08.5 needs a fake `gh` that writes stderr, and the shared fake writes none; the `err` key is now Track B's.
- **Defect** D08.25 — found: auditor · cause: spec · made: Day 08 · Track C's list left out `park_issue`'s positional caller in `tests/test_park_body.py` and the frozen `build()` that takes no `views`; the new arguments are now keyword ones and the fake's rewrite is named.
- **Defect** D08.26 — found: auditor · cause: spec · made: Day 08 · Track C would pass 400 lines (Day 7's like tracks measured 245 to 398); split into C1 and C2, Expected PRs 8.
- **Defect** D08.27 — found: auditor · cause: spec · made: Day 08 · the gated park's head had no route to the park line, `driver/runlog.py` was not in Track C's files, and a wait's `pr` would have leaked onto later parks; now stated, with a case for a park naming no pull request.
- **Defect** D08.28 — found: auditor · cause: spec · made: Day 08 · with no head at either read, `None == None` would have written `"changed": false` and counted toward Level 2; now `null`, and "first read" is the first successful one.
- **Defect** D08.29 — found: auditor · cause: spec · made: Day 08 · the run log's copy was "byte for byte" and "read for secrets" with no rule for a secret found; now replaced with `<secret>` and named.
- **Defect** D08.30 — found: auditor · cause: spec · made: Day 08 · the phone's `STOP` time came from the halt file, which `run-steps.py clear` deletes before `on` can run again; it is now copied first.
- **Defect** D08.31 — found: auditor · cause: spec · made: Day 08 · the cost per merged pull request had no source; now `token-usage.py --compare`'s, the baseline's measure, beside `status`'s.
- **Defect** D08.32 — found: auditor · cause: spec · made: Day 08 · "conclusion: success" was to come from `gh run view --exit-status`, which prints no conclusion; now `--json conclusion`.
- **Defect** D08.33 — found: auditor · cause: spec · made: Day 08 · C08.2 said the nine cases only gain the `level 2` line, but `test_no_merged` reads the last line and must move its index.
- **Defect** D08.34 — found: auditor · cause: spec · made: Day 08 · C08.10 quoted its lines with backslashes that `status` does not print; now as printed.
- **Defect** D08.35 — found: auditor · cause: spec · made: Day 08 · C08.8 named `GitHubTest.test_pr_state`, which passes today, without saying it is red only as Track C1 edits it; now said.
- **Defect** D08.36 — found: auditor · cause: spec · made: Day 08 · C08.3's Red today left out that `issue_cost` also raises on a list `session`, reached from `begin`; added.
- **Defect** D08.37 — found: auditor · cause: spec · made: Day 08 · a denial that is not an object, a `null` `tool_name` and a malformed `refused` would have crashed `write_end` or `status`; each now has a result.
- **Defect** D08.38 — found: auditor · cause: spec · made: Day 08 · whole-line comparisons in `GatedMergeTest` would put an `at` time and a 40-hex head into a break's report, which break.py refuses; the tests now compare four keys, with heads "aaa" and "bbb".
- **Defect** D08.39 — found: auditor · cause: spec · made: Day 08 · the trial's starting run log was not stated, so earlier `--once` lines could count in the copy; it now starts empty.
- **Defect** D08.40 — found: auditor · cause: spec · made: Day 08 · C08.11 held by construction (Steps is read from the same copy; session ids are uuids); it now checks an `end` per `start` and a `merged` line per merged step.
