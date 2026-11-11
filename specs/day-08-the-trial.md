# Day 08 — The trial's record: one day at level 1 in a project, what parked, what was refused, what it cost

**Phase:** 1 · **Depends on:** Day 7 · **Expected PRs:** 8 (9 with Track F, one more if Track C2 splits)

## Goal
The driver runs one whole day of another project at level 1, the maintainer only merging and
answering parks, and that day closes with its evidence replay green. This repository holds the
record: every park and every permission refusal by name, the cost and the replies per merged pull
request beside the baseline ($1.86, 34.4), and the count Level 2 is entered on. Before the trial,
the run log keeps what the record needs: which tools were refused, one `merged` or `closed` line for
every pull request the driver waited on, and whether the maintainer changed one before merging it.

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
  from a second `gh issue close`, each pasted unchanged into Track B's PR. The `gh pr checks` part,
  and Day 6's two reads left for it, are settled by reads (Notes, Assumed).
- **The run log**: the trial starts from an empty `state/run.jsonl` (no `state/` folder), so the
  copy holds the trial's lines only.
- **H07.1**: whether `specs/breaks/day-05.json` is corrected. Day 8 does not touch it.

## In scope

**A run log the readers can trust** (H07.3; `driver/runlog.py`). `_bad` also refuses an `end` line
whose `session` is not a string, or whose `refused` is present and not a list of objects with a
string `tool` and `input`; a `merged`, `closed` or `wait` line whose `pr` is not an int (a bool is
not one), and a `park` line whose `pr` is present and not one; and a `park` or `merged` line whose
`head` is present and not a string (a head is written only when known, never as `null`). The log is
then "the run log cannot be read at line <n>", as for a `start` line (H04.4). Today `failures()` and
`issue_cost()` raise `TypeError` on a list `session`, and `open_session()` and `last_session()` read
past it.

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

**One `merged` or `closed` line for every pull request the driver waited on** (H07.2, D07.30;
`driver/loop.py`, `driver/once.py`, `driver/github.py`, `driver/runlog.py`).
- `pr_state` asks `--json state,mergeCommit,files,body,headRefOid` and returns the head as a sixth
  value, `None` when `gh` gives none; one call, as today.
- `loop.wait_pr` appends `{"event": "wait", "at", "pr"}` before its first read, and again each time
  a resumed fix opens a new pull request and the wait moves to it (`loop.py`'s `number = ...` after
  `resume`). Every wait on a pull request, found at a start or opened by the step's session, goes
  through it, so the log names that pull request however the wait ends: a park, a halt, a `STOP`,
  Ctrl-C, a crash.
- The three parks of `gated` are written with `"pr": <n>`, and `"head"` when `pr_state` gave one:
  `wait_merge` returns that head with its park line, and `once.finish` and `once.park_issue` take
  `pr` and `head` as keyword arguments with defaults (`tests/test_park_body.py` calls it with seven
  positional ones). No other park line carries `pr`; its pull request's `wait` line names it.
- Every start that takes the lock (`--once`, `on`), after `driver_home.check`, the preflight, the
  lock and, in `on`, `livecheck.refusal`, and before the table, reads the run log. A log that is missing or cannot be read is passed
  over and left to the table (rows 2 and 3, C07.7, C07.21). Otherwise, for each `pr` named by a
  `wait` or `park` line with no `merged` or `closed` line for it, once per `pr`: `pr_state` "MERGED"
  appends `{"event": "merged", "at", "pr", "head": <the head now, when known>, "changed": <bool, or
  null>}`, `changed` comparing with the newest `park` line's `head` for that `pr`, `null` when there
  is none or either head is unknown; "CLOSED" appends `{"event": "closed", "at", "pr"}`; "OPEN"
  appends nothing. A failed read refuses: "cannot read the project: gh pr view exited <n>", exit 2,
  nothing started. The dry run never reaches this read (`run-steps.py` returns before `once.run`).
- `loop.wait_merge` keeps the head of its first successful read after the green, and on "MERGED"
  writes the same `merged` line, `changed` comparing the head at the merge with that one, `null`
  when either is unknown. A commit the maintainer pushed after the green is the change.
- Day 8's tests compare a run-log line's `event`, `pr`, `head` and `changed` only, with heads "aaa"
  and "bbb", so no `at` time or commit hash reaches a break's report. `MergeWaitHeadTest` lives in
  `tests/test_runlog_report.py`, which already imports `tests/test_merge_wait.py`'s helpers.

**The count Level 2 is entered on** (H06.2; `plan.md`, "Levels": "15 PRs in a row merged at level 1
without the maintainer asking for a change"). The run log cannot see a request made in chat; what it
can see is read as a change asked: a `merged` line whose `changed` is not `false`, a `closed` line, a
park "still red after two fixes". `status` prints, after the `cost` line,
`level 2: <k> of 15 pull requests in a row merged without a change asked`, where `k` counts the
`merged` lines with `"changed": false` from the newest back to the first change asked, or to a
`merged` line with no `changed` (written before Day 8), which also ends it. No `merged` line: `k` is
0.

**The trial** (no pull request here). The maintainer runs `on` on the trial's project until its
day's closing PR has merged and its evidence run is green, merging each pull request and answering
each park as it comes. The driver checks that run; if the closing PR is gated, the next start parks
before the table reads the evidence run (`decide` returns first, `once.py`), and the maintainer
checks it with `gh run view <id> --json conclusion`; the record says which. A park ends the run
(C05.6: "wait: parked #n", exit 0, though `plan.md`'s Recovery row 3 says the driver waits); the
maintainer closes the issue and runs `on` again. Level 0 stays open for a park that needs a
conversation. Once each, from the phone (H05.3): open a `STOP` issue while the driver waits on a
pull request (a `STOP` during a session leaves a `start` line with no `end`, which parks the next
start and needs VS Code), copying the halt file's text before `run-steps.py clear` deletes it; and
close a park's issue. Nothing in this repository changes while it runs.

**The record** (`docs/trial/`).
- `docs/trial/run.jsonl`: the trial's `state/run.jsonl`, copied byte for byte after the last step,
  then read before it is committed: a refused input can hold a secret. A secret is replaced with
  `<secret>` in the copy and in the record, and the record names the lines changed, or says none was.
- `docs/trial/day-08.md`, with these sections, in this order:
  - **Set-up**: the project and its commit at the start, the dates it ran, the CLI and `gh`
    versions, `driver.json`, the required checks, and each "Before this day" item, with its date.
  - **Steps**: `status`'s `steps:` block on the copy, unchanged, and each `wait` line's pull request.
  - **Parks**: one line per `park` line in the copy, in order: its time, its line, its issue, how it
    was answered (closed from the phone, closed after work in VS Code, a `STOP`), the issue's
    `createdAt` and `closedAt` from `gh issue view`, and the next `start` line's `at`.
  - **Refusals**: `status`'s refusal lines on the copy, unchanged, and what each step was doing;
    then the trial project's `.claude/state/refusals.jsonl` lines inside the trial's dates.
  - **Cost**: `status`'s `cost` and `level 2` lines on the copy, unchanged (the sessions'
    `total_cost_usd`); then `cost per merged pull request: $<x.xx> (baseline $1.86)`, the list-price
    dollars of the later side of `token-usage.py --compare --repo <the project> --split <the trial's
    first date>` over its pull requests (the baseline's own measure), and `replies per merged pull
    request: <y.y> (baseline 34.4)` from the same line. That side also counts interactive sessions:
    the record names them, the transcripts whose file name is no `start` line's session.
  - **The phone** (H05.3): `STOP: opened <stamp>, halted <stamp>, <s> s`, the issue's `createdAt`
    and the copied halt file's "halted at"; `park closed: <stamp>, started again <stamp>, <s> s`,
    the issue's `closedAt` and the next `start` line's `at`.
  - **The usage limit** (H06.1): the session's JSON fields when it was met, unchanged, or "not met".
  - **Unverified**: for each item of `plan.md`'s "Unverified" the trial touched, what it showed;
    for "resuming is cheaper than a new session for a fix", each resumed fix's cost by
    `token-usage.py` beside its step's first session, and that the new-session way was not run
    unless the maintainer ran one.
  - **Evidence**: `closing PR: #<n>`, `merge commit: <40 hex>`, `evidence run: <id>`,
    `conclusion: success`, from the trial repository's `gh run view <id> --json conclusion`.
- `tests/test_trial_record.py` reads both files inside its tests, not at import.

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
| C1 | | `pr_state`'s head; the `wait` line; gated parks with their pull request; `wait_merge`'s `merged` line: C08.8, C08.16, C08.17 |
| C2 | | `merged` and `closed` at a start, in `--once` and `on`: C08.7, C08.9 |
| D | | `status`: the refusals by tool, the Level 2 count: C08.2, C08.10 |
| E | | After the maintainer's trial, on the project: the record and its test: C08.11–C08.14 |
| F | | The usage limit, only if the trial met it: C08.15 |

C08.1 is proved in the spec-change PR. Day 7's comparable tracks measured 245 to 398 lines, so
Track C is split before it starts. The test files, new ones and the earlier ones each track edits:
- A: `tests/test_runlog_end.py` (`RunlogEndTest`), `tests/test_refused.py` (`RefusedTest`), and the
  fake `claude` in `tests/test_once.py` if it needs `permission_denials`.
- B: `tests/test_checks_none.py` (`ChecksNoneTest`); `FAKE`'s `err` key in `tests/test_github.py`.
- C1: `MergeWaitHeadTest` in `tests/test_runlog_report.py`, with its `test_merged_line`;
  `tests/test_merge_wait.py`'s `view` and `wait()` for the head; `tests/test_github.py`'s
  `test_pr_state`; `OnTest.test_wait_line_after_fix` in `tests/test_on.py`.
- C2: `tests/test_gated_merge.py` (`GatedMergeTest`); its `--once` cases rewrite `fake.json` after the
  frozen `tests/test_once_park_issues.py` `build()`, as it takes no `views`.
- D: `tests/test_status_trial.py` (`StatusTrialTest`); `tests/test_status.py`'s four cases (C08.2).
- E: `tests/test_trial_record.py`. F: `tests/test_usage_limit.py`.
C2 is near 400 lines (eight cases: C08.7's seven, C08.9's one); if it passes, its `on` case goes to a
C3.

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").

- [x] C08.1 **hold** — The files Day 8 does not change are unchanged since `f9f43fd`: Verify's diff
      prints nothing. Its list is C07.2's and C06.12's with `tests/test_merge_wait.py` and
      `tests/test_on.py` taken out (Tracks C1 and C2 edit them), and Day 8's own frozen files added.
      broken: a byte added to driver/decide.py → import re (#111)
      Replaces: C07.2 — was: earlier days' tests pass and Verify's diff is empty against `4a2c53f`, over a list that holds `tests/test_merge_wait.py` and `tests/test_on.py`.
      Replaces: C06.12 — was: earlier days' tests pass with their files unedited against `6f9e72c`, over a list that holds `tests/test_lock.py`, `tests/test_once_halt.py` and `tests/test_once_stop.py`, which Day 7 edited.
      Evidence: `git -c core.safecrlf=false diff --exit-code f9f43fd` over Verify's list printed nothing on `main` at `3c0952d`, after #129.
- [x] C08.2 **hold** — Day 7's `status` block still prints exactly for a log with no `refused`, no
      `changed` and no `closed` line: the nine `StatusTest` cases pass, `test_full_report`,
      `test_no_parks` and `test_gh_down` only gaining the `level 2` line, and `test_no_merged`
      reading its `cost` line as the last but one (C08.10). C07.18 holds as written: `status`
      changes nothing, a torn log, a `gh` failing and a config with a problem print and exit as it
      says; Track D re-records its breaks, whose reports the `level 2` line changes.
      Test: `StatusTest.test_full_report`, `StatusTest.test_mode_forms`, `StatusTest.test_no_merged`,
      `StatusTest.test_no_parks`, `StatusTest.test_in_progress`, `StatusTest.test_writes_nothing`,
      `StatusTest.test_torn_log`, `StatusTest.test_gh_down`, `StatusTest.test_bad_config`.
      Replaces: C07.18 — was: the same, with break reports that ended at the `cost` line.
      Evidence: `StatusTest.test_full_report`, `StatusTest.test_mode_forms`, `StatusTest.test_no_merged`, `StatusTest.test_no_parks`, `StatusTest.test_in_progress`, `StatusTest.test_writes_nothing`, `StatusTest.test_torn_log`, `StatusTest.test_gh_down`, `StatusTest.test_bad_config` (#126).
      broken: status drops the refusals line → AssertionError: Lists differ: ['mod[627 chars]f', 'cost: $1.20, merged pull requests 2, $0.6[93 chars]ked'] != ['mod[627 chars]f', 'refusals: 3', 'cost: $1.20, merged pull r[108 chars]ked'] (#126)
      broken: status skipping the config → AssertionError: "mode: off\nlevel: 1\nhalt: none\nrun's i[219 chars]ed\n" != '' (#126)
      broken: a log that cannot be read passing as empty → AssertionError: Lists differ: ['in progress: none', 'steps: none', 'parks by reason: n[144 chars]ked'] != ['in progress: unknown', 'run log: the run log cannot be read at line 2'] (#126)
- [x] C08.3 **new** — An `end` line whose `session` is `["s1"]` or whose `refused` is `"x"`, a
      `refused` is `[{"tool": 5, "input": "{}"}]`, a `merged` line whose `pr` is `true` or `"3"`, a
      `closed` or `wait` line whose `pr` is `"3"`, a `park` line whose `pr` is `true`, or a `park` or
      `merged` line whose `head` is `5`, makes `runlog.read`, `failures`
      and `open_session` give "the run log cannot be read at line <n>", `last_session` give `None`,
      and `status` print "run log: the run log cannot be read at line <n>", exit 2.
      Red today: `failures` and `issue_cost` raise `TypeError: unhashable type: 'list'`;
      `open_session` gives `('s1', None)`; the other lines are read as fine.
      Test: `RunlogEndTest.test_end_session_not_string`, `RunlogEndTest.test_merged_pr_not_int`,
      `RunlogEndTest.test_wait_pr_not_int`, `RunlogEndTest.test_closed_pr_not_int`, `RunlogEndTest.test_park_pr_not_int`,
      `RunlogEndTest.test_head_not_string`, `RunlogEndTest.test_refused_not_list`.
      Evidence: `RunlogEndTest.test_end_session_not_string`, `RunlogEndTest.test_merged_pr_not_int`, `RunlogEndTest.test_wait_pr_not_int`, `RunlogEndTest.test_closed_pr_not_int`, `RunlogEndTest.test_park_pr_not_int`, `RunlogEndTest.test_head_not_string`, `RunlogEndTest.test_refused_not_list` (#118).
      seen red: python -m unittest tests.test_runlog_end tests.test_refused on main → AssertionError: Tuples differ: ([{'event': 'start', 'at': '2026-11-08T10:[146 chars]None) != (None, 'the run log cannot be read at line 2') (#118)
      broken: an end line's session not checked → AssertionError: Tuples differ: ([{'event': 'start', 'at': '2026-11-08T10:[198 chars]None) != (None, 'the run log cannot be read at line 2') (#118)
      broken: a refused that is not a list read as fine → AssertionError: Tuples differ: ([{'event': 'start', 'at': '2026-11-08T10:[212 chars]None) != (None, 'the run log cannot be read at line 2') (#118)
      broken: a bool passing as a pull request's number → AssertionError: Tuples differ: ([{'event': 'start', 'at': '2026-11-08T10:[184 chars]None) != (None, 'the run log cannot be read at line 2') (#118)
- [x] C08.4 **new** — A session whose result holds three `permission_denials`
      (`{"tool_name": "Bash", "tool_input": {"command": "git push --force"}}`, one with neither key,
      and `"x"`) writes an `end` line with `"denials": 3` and `"refused": [{"tool": "Bash", "input":
      "{\"command\": \"git push --force\"}"}, {"tool": "unknown", "input": "{}"}, {"tool":
      "unknown", "input": "{}"}]`; a `tool_name` of `null` is "unknown"; an input of 500
      characters is cut to 200; a session with none writes no `refused` key.
      Red today: `KeyError: 'refused'`.
      Test: `RefusedTest.test_end_names_refused_tools`, `RefusedTest.test_malformed_denials`,
      `RefusedTest.test_input_cut`.
      Evidence: `RefusedTest.test_end_names_refused_tools`, `RefusedTest.test_malformed_denials`, `RefusedTest.test_input_cut` (#118).
      seen red: python -m unittest tests.test_refused on main → FAILED (errors=3) (#118)
      broken: a refused input not cut to 200 characters → AssertionError: '{"co[191 chars]aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa[270 chars]aa"}' != '{"co[191 chars]aaaaa' (#118)
- [x] C08.5 **new** — With a fake `gh` that exits 1 and writes "no required checks reported on the
      'day-01/track-a-x' branch" (or "no checks reported on the 'day-01/track-a-x' branch") to
      stderr, `checks` gives `("none", [], None)`, and the wait on that pull request parks "park: no
      required checks on #7 after 0.01 minutes", exit 1.
      Red today: `checks` gives `(None, [], "gh pr checks exited 1")`, and the wait ends "cannot
      read the project: gh pr checks exited 1", exit 2.
      Test: `ChecksNoneTest.test_no_required_checks`, `ChecksNoneTest.test_no_checks`,
      `ChecksNoneTest.test_wait_parks`.
      Replaces: C06.2 — was: every exit 1 of `gh pr checks` gives "gh pr checks exited 1", and `pr_state` asks `state,mergeCommit,files,body` and returns five values.
      Evidence: `ChecksNoneTest.test_no_required_checks`, `ChecksNoneTest.test_no_checks`, `ChecksNoneTest.test_wait_parks` (#120).
      seen red: python -m unittest tests.test_checks_none on main → AssertionError: Tuples differ: ('cannot read the project: gh pr checks exited 1', 2) != ('park: no required checks on #7 after 0.01 minutes', 1) (#120)
      broken: checks does not read gh's no required checks line → AssertionError: Tuples differ: (None, [], 'gh pr checks exited 1') != ('none', [], None) (#120)
      broken: an exit 1 with gh's no checks line is a failed read again → AssertionError: Tuples differ: ('cannot read the project: gh pr checks exited 1', 2) != ('park: no required checks on #7 after 0.01 minutes', 1) (#120)
- [x] C08.6 **hold** — An exit 1 of `gh pr checks` with any other stderr, or none, still gives
      "gh pr checks exited 1", and the rest of C06.2's `checks` and `failed_lines` hold: "pending"
      on exit 8, "red" with the failed checks' names, "green", "none" for an empty list, and the
      last 40 lines of each failed job's log, cut to its last 6,000 characters.
      Test: `ChecksNoneTest.test_other_exit_1`, `GitHubTest.test_checks`,
      `GitHubTest.test_failed_lines`.
      broken: failed_lines keeps 41 lines of a log → AssertionError: 'line 9\nline 10\nline 11\nline 12\nline 13\nli[367 chars]om/x' != 'line 10\nline 11\nline 12\nline 13\nline 14\nl[359 chars]om/x' (#111)
      Evidence: `ChecksNoneTest.test_other_exit_1`, `GitHubTest.test_checks`, `GitHubTest.test_failed_lines` (#120).
      broken: any stderr holding checks reported gives none → AssertionError: Tuples differ: ('none', [], None) != (None, [], 'gh pr checks exited 1') (#120)
- [x] C08.7 **new** — After a gated park of #7 with head "aaa", at the next `--once`, and at the
      next `on`, with the fake saying "MERGED" and the same head and listing no open pull request,
      the log gains a `merged` line with `"pr": 7`, `"head": "aaa"`, `"changed": false` before the
      run's first new `start` line, and a second
      start adds no second line. Two park lines for #7 give one `merged` line, compared with the
      newer's head. A new head at the merge gives `"changed": true`; a `wait` line for #7 and no
      park, then "MERGED", gives `"changed": null`; "CLOSED" gives a `closed` line with `"pr": 7`;
      a failing `gh pr view` prints "cannot read the project: gh pr view exited 1", exit 2, and
      starts no session; a torn log still parks as C07.21 says.
      Red today, at Track C2's start: the `park` and `wait` lines name #7 (Track C1), but no start
      writes a `merged` or `closed` line (D07.30).
      Test: `GatedMergeTest.test_merged_after_park`, `GatedMergeTest.test_on_writes_merged_at_start`,
      `GatedMergeTest.test_two_parks_one_line`, `GatedMergeTest.test_changed`,
      `GatedMergeTest.test_wait_only_null`, `GatedMergeTest.test_closed`,
      `GatedMergeTest.test_gh_fails`.
      Replaces: C07.16 — was: a `park` line is `{"event", "at", "step", "line"}` and a `merged` line `{"event", "at", "pr"}`.
      Evidence: `GatedMergeTest.test_merged_after_park`, `GatedMergeTest.test_on_writes_merged_at_start`, `GatedMergeTest.test_two_parks_one_line`, `GatedMergeTest.test_changed`, `GatedMergeTest.test_wait_only_null`, `GatedMergeTest.test_closed`, `GatedMergeTest.test_gh_fails` (#124); the torn log, `tests/test_recovery_holds.py`, which passes unedited.
      seen red: python -m unittest tests.test_gated_merge on main → AssertionError: Lists differ: [] != [('merged', 7, 'aaa', None)] (#124)
      broken: the start-time read asks again for a pull request with a `merged` line → AssertionError: Lists differ: [('merged', 7, 'aaa', False), ('merged', 7, 'aaa', False)] != [('merged', 7, 'aaa', False)] (#124)
- [x] C08.8 **new** — `wait_pr` on #7 writes a `wait` line with `"pr": 7` before its first read. A
      resumed fix that opens #13 in that wait writes a `wait` line with `"pr": 13`. A gated park of
      #7 writes `"pr": 7` and `"head": "aaa"`. In `wait_merge`, a head of "aaa" at its
      first successful read after the green and "bbb" when it merges writes a `merged` line with
      `"head": "bbb"`, `"changed": true`; the same head writes `"changed": false`; no head at
      either read writes no `head` key and `"changed": null`. `pr_state` makes one `gh pr view`
      call per read, asking `state,mergeCommit,files,body,headRefOid`, and returns six values.
      Red today: no `wait` line, a park line with no `pr`, a `merged` line of `{"event", "at", "pr"}`
      only; `GitHubTest.test_pr_state` and `RunLogReportTest.test_merged_line` as Track C1 edits
      them fail on today's code.
      Test: `MergeWaitHeadTest.test_wait_line`, `MergeWaitHeadTest.test_gated_park_carries_pr_head`,
      `MergeWaitHeadTest.test_changed`, `MergeWaitHeadTest.test_unchanged`,
      `MergeWaitHeadTest.test_no_head`, `OnTest.test_wait_line_after_fix`,
      `RunLogReportTest.test_merged_line`,
      `GitHubTest.test_pr_state`.
      Evidence: `MergeWaitHeadTest.test_wait_line`, `MergeWaitHeadTest.test_gated_park_carries_pr_head`, `MergeWaitHeadTest.test_changed`, `MergeWaitHeadTest.test_unchanged`, `MergeWaitHeadTest.test_no_head`, `OnTest.test_wait_line_after_fix`, `RunLogReportTest.test_merged_line`, `GitHubTest.test_pr_state` (#123).
      seen red: python -m unittest tests.test_runlog_report.MergeWaitHeadTest.test_wait_line tests.test_runlog_report.MergeWaitHeadTest.test_gated_park_carries_pr_head tests.test_runlog_report.MergeWaitHeadTest.test_changed tests.test_runlog_report.MergeWaitHeadTest.test_unchanged tests.test_runlog_report.MergeWaitHeadTest.test_no_head tests.test_on.OnTest.test_wait_line_after_fix tests.test_runlog_report.RunLogReportTest.test_merged_line tests.test_github.GitHubTest.test_pr_state on main → AssertionError: Tuples differ: (None, None, [], '', 'gh pr view exited 1') != (None, None, [], '', 'gh pr view exited 1', None) (#123)
      broken: runlog.wait writing no line → AssertionError: Tuples differ: ((None, 0), []) != ((None, 0), [7]) (#123)
      broken: wait_merge comparing two unknown heads → AssertionError: Lists differ: [(False, True, False)] != [(False, True, None)] (#123)
      broken: wait_merge comparing the heads the wrong way round → AssertionError: Lists differ: [(12, 'bbb', False)] != [(12, 'bbb', True)] (#123)
      broken: a gated park dropping its head → AssertionError: Tuples differ: (1, 'park: #7 touches plan.md', [(7, None)]) != (1, 'park: #7 touches plan.md', [(7, 'aaa')]) (#123)
      broken: wait_pr writing no wait line for the fix's pull request → AssertionError: Tuples differ: (0, [5]) != (0, [5, 13]) (#123)
      broken: pr_state not asking for the head → AssertionError: Lists differ: [['pr', 'view', '12', '--json', 'state,mergeCommit,files,body']] != [['pr', 'view', '12', '--json', 'state,mergeCommit,files,body,headRefOid']] (#123)
- [x] C08.9 **hold** — An open pull request a `wait` or `park` line named adds no line at a start.
      Test: `GatedMergeTest.test_open_adds_nothing`.
      Evidence: `GatedMergeTest.test_open_adds_nothing` (#124).
      broken: the start-time read appends `merged` for "OPEN" → AssertionError: Lists differ: ['merged', 'start'] != ['start'] (#124)
- [x] C08.10 **new** — `status` on a log built by the test prints, under "refusals: 3", the lines
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
      Evidence: `StatusTrialTest.test_refused_lines`, `StatusTrialTest.test_level_2_count`, `StatusTrialTest.test_count_ends` (#126).
      seen red: python -m unittest tests.test_status_trial on main → AssertionError: Lists differ: ['refusals: 3', 'cost: $0.20, merged pull requests 0 (baseline $1.86)'] != ['refusals: 3', '  2 Bash: {"command": "git push --force"}', '  1 Edit: {}'] (#126)
- [x] C08.11 **new** — The trial ran: `docs/trial/run.jsonl` reads without a reason; every `start`
      line has an `end` line, or a later `park` line "the run log names session `<id>` for this
      step, with no end" names its session; every `merged` and `closed` line's `pr` is named by an
      earlier `wait` line; and the record's Steps names each `wait` line's pull request.
      Red today: `docs/trial/run.jsonl` does not exist.
      Test: `TrialRecordTest.test_run_log_is_a_trial`.
      Evidence: `TrialRecordTest.test_run_log_is_a_trial` (#129).
      seen red: python -m unittest tests.test_trial_record on main → AssertionError: None is not true : run log is empty (#129)
      broken: the wait line of the closing pull request names another one → AssertionError: False is not true : wait pull request missing from Steps (#129)
- [x] C08.12 **new** — The record names every park and every permission refusal, and its `cost`
      line is the one `status` gives on the copy of the run log.
      Red today: `docs/trial/day-08.md` does not exist.
      Test: `TrialRecordTest.test_every_park_named`, `TrialRecordTest.test_every_refusal_named`,
      `TrialRecordTest.test_cost_line_is_status`.
      Evidence: `TrialRecordTest.test_every_park_named`, `TrialRecordTest.test_every_refusal_named`, `TrialRecordTest.test_cost_line_is_status`, `TrialRecordTest.test_sections_in_order` (#129).
      seen red: python -m unittest tests.test_trial_record on main → AssertionError: None is not true : run log is empty (#129)
      broken: the record gives the last park another time → AssertionError: False is not true : park time missing from Parks (#129)
      broken: the record names another refused tool → AssertionError: False is not true : refused tool line missing from Refusals (#129)
      broken: the record's cost line differs from status → AssertionError: False is not true : cost line missing from Cost (#129)
      broken: a section of the record is renamed → AssertionError: Lists differ: ['Set[15 chars]'Parked', 'Refusals', 'Cost', 'The phone', 'Th[36 chars]nce'] != ['Set[15 chars]'Parks', 'Refusals', 'Cost', 'The phone', 'The[35 chars]nce'] (#129)
- [x] C08.13 **new** — The trial's day closed with its evidence replay green: the record's Evidence
      section names the closing PR, a merge commit of 40 hex characters, an evidence run id and
      "conclusion: success", and the copy holds a `merged` line for that pull request.
      Red today: `docs/trial/day-08.md` does not exist.
      Test: `TrialRecordTest.test_evidence_section`.
      Evidence: `TrialRecordTest.test_evidence_section` (#129): `bearing`'s closing PR #96, evidence run 42932015269, conclusion success.
      seen red: python -m unittest tests.test_trial_record on main → AssertionError: None is not true : run log is empty (#129)
      broken: the record's evidence run did not succeed → AssertionError: False is not true : conclusion line missing (#129)
- [x] C08.14 **new** — A `STOP` opened from the phone halted the driver, and a park closed from the
      phone was followed by the next start, each with its two times and the seconds between in the
      record's The phone section (H05.3).
      Red today: `docs/trial/day-08.md` does not exist.
      Test: `TrialRecordTest.test_phone_lines`.
      Evidence: `TrialRecordTest.test_phone_lines` (#129): 30 s from the `STOP` to the halt, 105 s from the park's close to the next start.
      seen red: python -m unittest tests.test_trial_record on main → AssertionError: None is not true : run log is empty (#129)
      broken: the phone's seconds do not match its stamps → AssertionError: 30 != 31 : seconds differ (#129)
- [ ] C08.15 **new** — If the trial met the usage limit: a fake session ending with the fields the
      record quotes waits until its reset and resumes the same session once; a second one parks
      "park: the usage limit was reached (session `<id>`)". If it did not, this box stays unticked
      with "Not proven: the trial did not meet the limit", and H06.1 goes on to the maintainer.
      Red today: such a session parks with a Day 4 line ("the session ended in an error: …" or
      another), with no wait.
      Test: `UsageLimitTest.test_waits_and_resumes`, `UsageLimitTest.test_second_limit_parks`.
      Not proven: the trial did not meet the limit
- [x] C08.16 **hold** — The rest of C07.16 holds: a park before a session and one after it each
      write one `park` line, its `line` the printed line and its `step` the sentence; `start(...,
      issue=12)` carries `"issue": 12`, and without it the line's keys are C04.4's.
      Test: `RunLogReportTest.test_park_lines`, `RunLogReportTest.test_issue_on_start`.
      broken: park_issue writing no park line → AssertionError: Tuples differ: (1, True, 0) != (1, True, 1) (#111)
      broken: start writing a null issue → AssertionError: Tuples differ: ('issue', None, ['event', 'at', 'step', 'prefix', 'session', 'claude']) != ('issue', 12, ['event', 'at', 'step', 'prefix', 'session', 'claude']) (#111)
      Evidence: `RunLogReportTest.test_park_lines`, `RunLogReportTest.test_issue_on_start` (#123).
- [x] C08.17 **hold** — A park other than the three of `gated` carries no `pr` key, even one that
      ends a wait on #7 in the same step ("park: #7 was closed without a merge", "park: the checks
      on #7 are red"), where `record["pr"]` is set.
      Test: `MergeWaitHeadTest.test_park_without_pr`.
      Evidence: `MergeWaitHeadTest.test_park_without_pr` (#123).
      broken: a park line takes the wait's pr → AssertionError: Tuples differ: (1, '[17 chars]on #7 are red: tests', [['event', 'at', 'step', 'line', 'pr']]) != (1, '[17 chars]on #7 are red: tests', [['event', 'at', 'step', 'line']]) (#123)

## Verify
```bash
python -m unittest discover -s tests
git -c core.safecrlf=false diff --exit-code f9f43fd -- tests/test_contract.py tests/test_decide.py tests/test_dry_run.py tests/test_steps.py tests/test_tree.py tests/test_config.py tests/test_encoding.py tests/test_halt.py tests/test_halt_report.py tests/test_home.py tests/test_hooks.py tests/test_issues.py tests/test_off.py tests/test_once_park_issues.py tests/test_once_parks.py tests/test_preflight.py tests/test_recovery_table.py tests/test_lock_takeover.py driver/decide.py driver/steps.py driver/settings.py driver/home.py driver/preflight.py driver/config.py hooks rules/session.md tests/test_failures.py tests/test_once_outcome.py tests/test_once_run.py tests/test_runlog.py tests/test_runlog_fix.py tests/test_session_bound.py tests/test_wait.py tests/test_kit_copy.py tests/test_lock.py tests/test_live_cli.py tests/test_once_halt.py tests/test_live_once.py tests/test_once_stop.py
```

## Notes
- Picks up H05.3 (C08.14), H06.1 (C08.15), H06.2 (C08.8, C08.10), H06.3 (C08.5), H07.2 (C08.7) and
  H07.3 (C08.3). H07.1 and the rest of "Before this day" are the maintainer's. Day 6's two reads
  left "for the scratch repository with H05.5" are Assumed lines below; `plan.md`'s "The trial
  counts both ways" is the record's Unverified section.
- "Without the maintainer asking for a change" is read as what the run log can see: a commit after
  the green, a pull request closed unmerged, a red after two fixes, or a merge with no head to
  compare (`changed` `null`: no gated park, or a wait ended before its merge). A request made in
  chat, or a PR comment, does not reset the count, so it can be too high; the rest errs too strict.
  A gated park the maintainer merges unchanged does not reset it: Level 2 would not merge those,
  and the maintainer changed nothing. GitHub's "Update branch", or a rebase, changes the head and so
  counts as a change asked.
- "park: more than one open pull request: #3, #5" waits on neither and writes no `wait` line; a
  pull request the driver opened has its own `wait` line from its step. `--once` does not wait
  (Day 6), so it writes none; the trial runs `on`.
- C06.2 is replaced once, by C08.5; its `checks` and `failed_lines` parts are restated in C08.6 and
  its `pr_state` in C08.8. C07.16 is replaced by C08.7; its park and issue parts are restated in
  C08.16 and its `merged` line in C08.8.
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
- Spec-auditor a third time, 2026-11-10, on 86c7b66: 17 findings (D08.41 to D08.57), all taken up;
  four came from the second round's fixes. The Red today claims held, but for C08.7's at C2's start.
- Spec-auditor a fourth time, 2026-11-10, on 4478125: 9 findings (D08.58 to D08.66), all taken up.
  The Red today claims held. Found on the way, not Day 8's: three of Day 6's recorded breaks no
  longer replay on today's `main` ("the fix line is not written" reports otherwise; "on does not
  re-read the next step after a merge" finds its text twice in `driver/loop.py`; "the resume keeps
  --session-id" holds a uuid, which break.py now refuses). The maintainer's, as H07.1 is.
- **Assumed** — `gh pr checks --required` on a pull request with no checks, and with checks none of
  them required, exits 1, empty stdout, and writes "no checks reported on the '<b>' branch" /
  "no required checks reported on the '<b>' branch": `gh pr checks 1 --repo octocat/Hello-World
  --required --json name,bucket,link` and `gh pr checks 3912 --repo pallets/click --required --json
  name,bucket` → those lines, gh 2.93.0.
- **Assumed** — `gh pr checks --json` on pending checks exits 0, not 8 (`checks` takes both): three
  python/cpython pull requests with pending checks → exit 0, gh 2.93.0.
- **Assumed** — `git merge --ff-only origin/main` on a diverged branch exits 128: a scratch clone
  with a local commit and a new remote one → "fatal: Not possible to fast-forward, aborting.", exit
  128, git 2.54.0.windows.1.
- **Assumed** — `headRefOid` on a merged pull request is its last head: `gh pr view 113 --json
  headRefOid` → `101d29b7…`, the last commit of `gh api repos/Yusuprozimemet/agentic-workflow-driver/pulls/113/commits`;
  for squash merges, astral-sh/ruff #30258 and #30235 the same; gh 2.93.0.
- **Assumed** — `gh issue view --json createdAt,closedAt` gives both as UTC stamps ending "Z":
  `gh issue view 1 --repo octocat/Hello-World --json createdAt,closedAt` → both, gh 2.93.0.
- **Assumed** — `gh run view <id> --exit-status` prints no conclusion; `--json conclusion` does:
  `gh run view 42805769752 --exit-status` → exit 0, "✓ main Evidence replay · 42805769752";
  `--json conclusion` → `{"conclusion":"success"}`, gh 2.93.0.
- **Assumed** — a `permission_denials` entry is `{"tool_name", "tool_use_id", "tool_input"}`: read
  from Claude Code 2.1.170's bundle (`tool_name:k.string(),tool_use_id:k.string(),tool_input:k.record(...)`)
  | not run: the maintainer, on the updated CLI, before Track A ("Before this day", The CLI).
- **Assumed** — a hook's exit-2 refusal appears in `permission_denials` | not run: the trial; the
  record's Unverified section.
- **Assumed** — the kit's guards write `.claude/state/refusals.jsonl` in a headless session | not
  run: the trial; the record's Refusals section.
- **Assumed** — `gh issue create` prints the URL last; a second `gh issue close` exits 0 | not run
  (writes): the maintainer, before Track B (H05.5).
- **Assumed** — `token-usage.py` counts the driver's headless transcripts: they exist, named by the
  `--session-id` (`"entrypoint":"sdk-cli"`, which `token-usage.py` does not read) | not run: the count, the trial.
- **Assumed** — `--resume <id>` resumes a session after a usage limit | not run: Track F, if it opens.
- Two blind passes: the first, of 81 entries, moved D08.19 and D08.60 from `spec` to `process`, each a fault in a break's record. The last whole pass, of 82 after D08.82, is the one the closing PR quotes: stage 76, cause 78, made 78 agree, and the rater unclear on cause 3, made 2, stage 5. All its disagreements are kept. D08.10, D08.21, D08.60, D08.65 and D08.78's stage: the rater says the line does not say where it was found, and the tags come from the spec-change PR and #118. D08.16: no close step owns the map, so `none`. D08.17: the rule came after the spec was written, so `process`, `none`. D08.21's cause: the auditor found a spec gap. D08.76 and D08.81: the field allows no "unclear"; each test file was added by the day named, and the lines say the cause was not found.
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
- **Defect** D08.19 — found: auditor · cause: process · made: Day 08 · C08.1's `broken:` line ended "(spec-change PR)", which the replay does not strip, and had no `manifest:` line; now break.py's lines as printed, ending "(#111)".
- **Defect** D08.20 — found: auditor · cause: spec · made: Day 08 · `_bad` did not check a park line's `pr`, so `"pr": true` would refuse every later start until the log was edited by hand; now refused, with a C08.3 case.
- **Defect** D08.21 — found: auditor · cause: spec · made: Day 08 · the start-time read in `on`, the path the trial uses, had no test; `GatedMergeTest.test_on_writes_merged_at_start` added.
- **Defect** D08.22 — found: auditor · cause: spec · made: Day 08 · a wait that ended with no park (a halt, a `STOP`, a failed read) wrote no line, so a pull request merged after it was never counted; first a `left` line, then (D08.45) a `wait` line written when a wait begins.
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
- **Defect** D08.41 — found: auditor · cause: spec · made: Day 08 · C06.2 was replaced by both C08.5 and C08.8, which `behaviour-index.py` fails once both are ticked, and `failed_lines` went out of force; now one `Replaces:`, with C06.2's other parts restated in C08.6 and C08.8.
- **Defect** D08.42 — found: auditor · cause: spec · made: Day 08 · `_bad` refused a non-string `head` while an unknown head would have been written as `null`, making the log unreadable after any merge with no head; a head is now written only when known.
- **Defect** D08.43 — found: auditor · cause: spec · made: Day 08 · `test_park_without_pr` under the `new` C08.8 passes on C1's base, which the required "Track tests seen red" fails; now the `hold` C08.17.
- **Defect** D08.44 — found: auditor · cause: spec · made: Day 08 · C08.7's Red today was stale at C2's start, and C1's park `pr` and `head` had no test of C1's own; Red today restated, and the gated park's `pr` and `head` moved to C08.8.
- **Defect** D08.45 — found: auditor · cause: spec · made: Day 08 · the `left` line was not written when `run-steps.py halt` kills the driver, on Ctrl-C or on a crash; replaced by a `wait` line written when a wait begins.
- **Defect** D08.46 — found: auditor · cause: spec · made: Day 08 · a park ending a wait without naming its pull request carried no `pr`, so a merge after it went uncounted and the count erred lenient; the `wait` line now names it.
- **Defect** D08.47 — found: auditor · cause: spec · made: Day 08 · C08.11's rewrite failed a trial that recovered a killed session or found a pull request open at a start; it now allows the no-end park and reads `wait` lines.
- **Defect** D08.48 — found: auditor · cause: spec · made: Day 08 · In scope had inputs with no criterion: a `left` or `closed` line's `pr`, a non-string `head`, the "more than one open pull request" park, a `STOP` in the evidence wait; now C08.3 cases, a Note, or gone with the `left` line.
- **Defect** D08.49 — found: auditor · cause: spec · made: Day 08 · C08.8's `STOP` in `on` could not be built (the fake opens no issue; `OnCase` in `test_merge_wait.py` would import in a circle); now `wait_pr`'s `wait` line, tested in `tests/test_runlog_report.py`.
- **Defect** D08.50 — found: auditor · cause: spec · made: Day 08 · C08.9's dry-run half had no break and cannot fail, since the dry run never reaches the read; dropped, the reason in In scope.
- **Defect** D08.51 — found: auditor · cause: spec · made: Day 08 · `Replaces: C07.16` retired `test_park_lines` and `test_issue_on_start` with nothing restating them; now the `hold` C08.16, both broken here.
- **Defect** D08.52 — found: auditor · cause: spec · made: Day 08 · the four-key comparison was given to `GatedMergeTest` only, though `MergeWaitHeadTest` compares log lines too; now Day 8's tests.
- **Defect** D08.53 — found: auditor · cause: spec · made: Day 08 · C08.2's `Test:` named the class `StatusTest`, which the evidence does not count; now its nine tests.
- **Defect** D08.54 — found: auditor · cause: spec · made: Day 08 · Track C2 is near 400 lines; a C3 for its `on` case is named if it passes.
- **Defect** D08.55 — found: auditor · cause: spec · made: Day 08 · a gated closing PR parks the next start before the driver reads its evidence run, so "the driver has checked its evidence run" could never happen; the maintainer checks it then.
- **Defect** D08.56 — found: auditor · cause: spec · made: Day 08 · the cost per merged pull request is not printed by `token-usage.py` and the interactive sessions had no rule; both now said.
- **Defect** D08.57 — found: auditor · cause: spec · made: Day 08 · the kit's guards logging in a headless session, Day 6's two reads left for H05.5, and `plan.md`'s "counts both ways" were carried by nothing; Assumed lines and the record's Unverified section now carry them.
- **Defect** D08.58 — found: auditor · cause: spec · made: Day 08 · Tracks C1 and C2 edit `tests/test_merge_wait.py` and `tests/test_on.py`, which C07.2 holds unedited, with no `Replaces:`, and C06.12 was already false after Day 7; C08.1 now replaces both over their merged list, and each track's test files are named.
- **Defect** D08.59 — found: auditor · cause: spec · made: Day 08 · a resumed fix moves `wait_pr` to a new pull request with no `wait` line, so its merge was named by nothing and C08.11 would fail a real trial; a `wait` line is now written for the new number, with a C08.8 case.
- **Defect** D08.60 — found: auditor · cause: process · made: Day 08 · C08.16's second break had Day 7's name for a different mutation, so its report did not replay with Day 7's; renamed "start writing a null issue".
- **Defect** D08.61 — found: auditor · cause: spec · made: Day 08 · the `level 2` line changes two of C07.18's recorded break reports; C08.2 now replaces C07.18 and Track D re-records them.
- **Defect** D08.62 — found: auditor · cause: spec · made: Day 08 · C08.17's example park could not catch the leak its break names (a new step's record has no `pr`); now a park that ends a wait in the same step.
- **Defect** D08.63 — found: auditor · cause: spec · made: Day 08 · `_bad`'s `closed` line, `merged` head and malformed `refused` entries had no C08.3 case, though D08.48 said they did; added.
- **Defect** D08.64 — found: auditor · cause: spec · made: Day 08 · C08.7's `on` case could pass at C2's start, `wait_merge` writing the line itself; the fake now lists #7 as not open, and the line must come before the run's first new `start`.
- **Defect** D08.65 — found: auditor · cause: spec · made: Day 08 · an Assumed line said headless transcripts carry `entrypoint` "claude-vscode"; they carry "sdk-cli".
- **Defect** D08.66 — found: auditor · cause: spec · made: Day 08 · C2's case count, Expected PRs with a C3, and the start-time read's place beside `livecheck.refusal` were unstated or wrong; said.
- Track F did not open: the record's "The usage limit" reads "not met", so C08.15 stays unticked and H06.1 goes on to the maintainer as H08.1. The day took the 8 pull requests it expected: #111, #118, #120, #123, #124, #126, #129 and this close.
- At the close the suite is 340 tests (301 before the day), "OK (skipped=4)". The first of this close's two runs of `python scripts/test-parallel.py` failed once in `tests/test_once_stop.py`, "FAILED (failures=1)" of its 4, and its report was not kept (D08.81); the second passed. The file passed 5 of 5 alone, `OnceHaltTest.test_halt_during_once` 4 of 4 alone, and CI's serial run passed at `3c0952d`.
- C08.6's break differs from the name the spec gave it: the spec said every exit 1 taken as "none", the break run was the narrower "any stderr holding checks reported gives none" (#120). The same test, `ChecksNoneTest.test_other_exit_1`, catches it.
- C08.14's `STOP` landed during the closing session, not during a wait on a pull request as the spec asked; the record says so. The criterion's words hold: it was opened from the phone and halted the driver in 30 s.
- C08.11 to C08.14 read the committed record. What they cannot check is that the record is true of the trial: that the `STOP` and the park were closed from the phone is the maintainer's word, and how #97 was closed is not recorded.
- What the trial settled of the Assumed lines above. A hook's exit-2 refusal does appear in `permission_denials`, and from a subagent (one case, `bearing`'s `read-guard.py`). The kit's guards do not write `.claude/state/refusals.jsonl` on `bearing` at `c214b09` (D08.79). `token-usage.py` does count the headless transcripts, all four sessions. `gh issue create` prints the URL last and a second `gh issue close` exits 0 (#120, wordtally#57). `--resume <id>` after a usage limit was not run: Track F did not open.
- The `permission_denials` shape was read on 2.1.170 from a deny rule (#118) and on 2.1.322 from a hook (the trial's one refusal). `auto` mode refused nothing in the trial's three finished sessions.
- The trial's 3 of 15 toward Level 2 is one small day, three pull requests, and can be too high (the Note on "without the maintainer asking" above). Two costs are recorded and not reconciled: $0.93 per merged pull request by the sessions' own figures, $1.07 by list price, against the baseline's $1.86.
- **Defect** D08.67 — found: review · cause: implementation · made: Day 08 · the implementer's `RefusedTest` read the line with `.get`, so its red was `None != [...]`, not the spec's `KeyError: 'refused'`; changed to index the key before the red was recorded (#118).
- **Defect** D08.68 — found: break on purpose · cause: process · made: Day 08 · a two-line `--find` did not match the CRLF tree and `break.py` refused it, "occurs 0 times"; redone on one line (#118).
- **Defect** D08.69 — found: break on purpose · cause: process · made: Day 08 · a `--find` occurred twice in `driver/runlog.py` and `break.py` refused it; redone with a line that occurs once (#118).
- **Defect** D08.70 — found: self · cause: implementation · made: Day 08 · the implementer's first `tests/test_checks_none.py` failed the style check on two percent-format lines, UP031; fixed before it reported (#120).
- **Defect** D08.71 — found: self · cause: process · made: Day 08 · the suite on `main` was not counted before Track B's change, so its PR could give 315 only as the branch's count (#120).
- **Defect** D08.72 — found: break on purpose · cause: process · made: Day 08 · same-as: D08.68 · five more multi-line finds refused on the CRLF tree; re-run on single lines, which an LF checkout also replays (#123).
- **Defect** D08.73 — found: break on purpose · cause: process · made: Day 08 · a break in a branch `MergeWaitHeadTest.test_no_head` never reaches could not fail it, and `break.py` exited 1; replaced by "wait_merge comparing two unknown heads" (#123).
- **Defect** D08.74 — found: Track C1 · cause: process · made: Day 08 · the brief said a drift with #7 open makes `on` wait on #7, but the fake still served #5; the implementer rewrote the fake's number after the build (#123).
- **Defect** D08.75 — found: Track C1 · cause: spec · made: Day 08 · the spec had `wait_merge` return the head with its park line, but a bare head cannot tell a gated park with no known head, which must carry `pr`, from a park that must not (C08.17); it returns the gated park's keys instead (#123).
- **Defect** D08.76 — found: Track C1 · cause: implementation · made: Day 04 · `OnceHaltTest.test_halt_during_once` fails on and off, the log holding an `end` line it does not expect: 2 runs of 3 on the branch and 1 of 4 on `main` (#123). Tagged for the test's timing; the cause was not found, so a race in the driver is not ruled out (H08.3).
- **Defect** D08.77 — found: Track D · cause: process · made: Day 08 · the brief named `tests/test_github.py` for the log helpers, which live in `tests/test_status.py`; the implementer said so and imported from there (#126).
- **Defect** D08.78 — found: Track A · cause: process · made: Day 08 · the denied-call session ran on 2.1.170, not the updated CLI "Before this day" asks for; the trial's own refusal on 2.1.322 was written with its tool and input (#118, #129).
- **Defect** D08.79 — found: Track E · cause: spec · made: Day 08 · the Assumed line that the kit's guards write `.claude/state/refusals.jsonl` does not hold on `bearing`: at `c214b09` they print their refusals and log them nowhere, and the file does not exist (#129).
- **Defect** D08.80 — found: Track E · cause: spec · made: Day 08 · the spec expected the park after a `STOP`-killed session to need VS Code; it was closed from the phone, and the next start ran the step in a new session (#129).
- **Defect** D08.81 — found: close · cause: implementation · made: Day 05 · a whole-suite run at the close failed once in `tests/test_once_stop.py` and the next passed; the report was not kept, so the test and the cause are not known (H08.3).
- **Defect** D08.82 — found: evidence replay · cause: process · made: Day 08 · C08.16's break "park_issue writing no park line" was recorded on #111 with a find that Track C1 then changed, when `runlog.park` took two more arguments, so the close's rehearsal refused it, "occurs 0 times"; re-run on today's line, with the same report.
- **Hand-off** H08.1 → the maintainer: H06.1, how a headless session reports the usage limit. The trial did not meet it, so `once.outcome` still parks such a session with a Day 4 line and no wait, and `--resume` after a limit has not been run.
- **Hand-off** H08.2 → the maintainer: neither `hooks/guard.py` nor `bearing`'s guards log a refusal, so a guard's refusal that does not reach `permission_denials` is seen nowhere (D08.79). The Note above leaves this to the stop's plan-auditor.
- **Hand-off** H08.3 → the maintainer: `OnceHaltTest.test_halt_during_once` and a test in `tests/test_once_stop.py` fail on and off under load (D08.76, D08.81). `OnceStopTest` and `OnceHaltTest` expect `["start", "pid"]`, so a killed session's `end` line may be a race in the driver and not only in the tests; no day owns it.
- **Hand-off** H08.4 → the maintainer: the Level 2 count reads a park as a change asked by the words "still red after two fixes", the text `driver/loop.py` writes; a change to that sentence would stop the count seeing it, and no test ties the two files together (#126). Before Level 2 is entered on the count.
- **Hand-off** H08.5 → the maintainer: under `--permission-mode auto --allowedTools "Bash(echo:*)"` on 2.1.170 a session was not denied `echo driver > out.txt` (#118), which D03.13 records as denied under the same mode and version. Not looked into.
