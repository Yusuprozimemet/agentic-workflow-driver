# Day 09 — Phase 1's leftovers: the usage limit waited out, refusals logged by the hooks, the halt race, the level 2 sentence tied

**Phase:** 2 · **Depends on:** Day 8 · **Expected PRs:** 7 (the spec change, Tracks A, B1, B2, C, D, the close; one more if Track A splits)

## Goal
A session stopped by the usage limit waits for the reset and is resumed once, and parks only if
the limit stops it again; a refusal by the driver's own hooks is written down by the hook, so a
session killed before its `end` line still has its refusals counted by `status` and by
`scripts/driver-runs.py`; a halt that ends a session before it ends the driver leaves no `end`
line and no park; and a test breaks when `driver/loop.py`'s "still red after two fixes" sentence
and the level 2 count in `driver/status.py` stop agreeing.

## In scope

- **The usage limit (C08.15, H08.1).** The trial did not meet it, so its shape comes from this
  machine's interactive transcripts (Notes, Assumed): the CLI writes an `assistant` record with
  `"apiError": "usage_limit_reached"` and `apiErrorParams.rate_limit_info.resetsAt`, an epoch in
  seconds, and then other records (`last-prompt`, `cost-state`). After a session's process
  returns, and after the halt check (C09.13), the driver reads the session's transcript: the file
  named `<session>.jsonl` under `<config>/projects/*/`, `<config>` being `CLAUDE_CONFIG_DIR` when
  it is set and `~/.claude` when not. Only the transcript's last record whose `type` is
  `assistant` counts. When it is the limit, before Day 4's outcome table is read:

  | When | The driver prints | Then |
  |---|---|---|
  | the reset is at most `--limit-hours` away (default 6) | `limit: the usage limit was reached; waiting until <YYYY-MM-DD HH:MM> (session `<id>`)` | writes the session's `end` line with that outcome, waits until `resetsAt` and one more `--poll`, then runs the same command with `--resume` in place of `--session-id`, and reads the resumed session's outcome as any other |
  | the reset is further away | `park: the usage limit resets at <YYYY-MM-DD HH:MM>, more than <n> hours away (session `<id>`)` | parks as any park, with no wait |
  | the resumed session's last `assistant` record is the limit again | `park: the usage limit was reached (session `<id>`)` | parks as any park |
  | the halt file exists at a poll during the wait | `halt: the halt file was set during the wait for the usage limit (session `<id>`)` | no resume, no further `end` line, exit 1 |

  The resumed session's prompt, on stdin, is "The usage limit has reset. Carry on with this step
  as before, open its one pull request, and stop." The time printed is local, from `resetsAt`.
- **The hooks log their refusals (H08.2).** `hooks/guard.py <driver folder> [<refusals folder>]`
  and `hooks/halt.py <halt file> [<refusals folder>]`: given the second argument, a refusal
  appends one JSON line to `<refusals folder>/hooks.jsonl` (the folder made if missing) with the
  keys `at` (UTC, `%Y-%m-%dT%H:%M:%SZ`, the run log's format; the hooks import nothing from
  `driver/`), `session` (stdin's `session_id`, or null), `hook` (`guard` or `halt`), `tool`
  (stdin's `tool_name`, or null) and `input` (`json.dumps` of stdin's `tool_input` cut to 200
  characters, as `driver.once.refusal` writes it on an `end` line, or null), and `line` (the
  refusal's stderr line). The halt hook reads stdin for these fields only, and only when stdin is
  not a terminal, for at most 2 seconds; with nothing read, the fields are null. What it decides
  still depends on the halt file alone. A write that fails changes nothing else: the same exit 2
  and the same one stderr line. A passing call writes nothing. `driver.settings.write(state,
  home)` gives both hooks `<state>/refusals`: a folder of its own, so that Day 10 can let the
  second account write it and nothing else of the driver's (H09.1).
- **The refusals counted (H08.2, the plan-auditor's finding 5).** `status`'s "refusals: n", its
  by-tool lines and each step's "refusals n", and `scripts/driver-runs.py`'s `denials` per
  session, add the hook log's lines of a session that are later than the session's last `end`
  line, or all of them when it has none. A session's refusals up to its last `end` line are
  counted from its `end` lines alone, as today: a hook's exit-2 refusal reaches
  `permission_denials` (`plan.md`, "Unverified"), so counting its log line too would count it
  twice. A resumed session killed after a fix or after the usage limit has an earlier `end` line,
  so "later than the last" is what counts its refusals. A hook line in the same second as the
  `end` line is taken as counted by it.
- **The halt race (H08.3).** `run-steps.py halt` writes `<state>/halt` before it kills anything
  (`driver/switches.py`, `halt`). When the session's process ends first and the driver reads its
  output before its own kill lands, `one_session` writes an `end` line and may open a park issue
  (D08.76). After a session's process returns, after a fix's resumed session returns
  (`driver/loop.py`, `resume`), and after the usage limit's resumed session returns, the driver
  checks the halt file before anything else: present, it prints `halt: the halt file was set
  while the session ran (session `<id>`)`, writes no `end` line, opens no park issue, and exits 1
  (`loop.resume` returns that line with code 1).
- **The level 2 sentence (H08.4).** A test drives `driver.loop.wait_pr` with the fakes
  `tests/test_wait.py` uses until it returns the red-after-two-fixes park line, passes that line
  to `driver.once.park_issue` as `once.finish` does, reads the `park` line `park_issue` wrote to
  the run log, and feeds it to `driver.status.level_2_run`. No code change: the test is what was
  missing.

## Out of scope

- The second Windows account, and the hooks' log folder writable by it while the rest of the
  driver's folder is not — Day 10 (H09.1).
- The usage limit met by a fix's resumed session (`driver/loop.py`, `resume`): it parks as Day 4's
  table says, with no wait — the maintainer (H09.3).
- A STOP issue during the wait for the usage limit: the wait does not poll issues; a halt kills
  the driver as at any time, and the halt file is checked at each poll — the maintainer (H09.3).
- What state a `--max-budget-usd` stop leaves the branch in (`plan.md`, "Unverified") — not met;
  no day owns it until a run meets it.
- The reviewer — Day 11. The level 2 merge and `Replaces: C07.1` — Day 12. The bypass line of
  `setup-check.py` — Day 10.
- Whether the breaks of C04.7, C04.8 and C07.5 still apply (`plan.md`, "Course correction after
  Phase 1", "Not settled here") — a spec-change matter for the maintainer, checked against
  `replay-history.json`; PR #139 re-recorded nine Day 04 and Day 07 breaks.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | The usage limit's wait, resume and parks: C09.1–C09.5 |
| B1 | | The hooks log their refusals; the settings pass the folder: C09.6–C09.10 |
| B2 | | `status` and `driver-runs.py` count a killed session's hook refusals: C09.11, C09.12 |
| C | | The halt file checked after a session returns: C09.13 |
| D | | The level 2 count tied to `loop.py`'s park sentence: C09.14 |

B2 depends on B1's log format and lands after it. C lands after A: its check comes before A's
transcript read, and covers A's resume. Track A may split along the wait (C09.1, C09.4, C09.5)
and the parks (C09.2, C09.3) if its diff passes 400 lines.

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [ ] C09.1 **new** — `run-steps.py --once --poll 1` on a fake session whose first run writes a
      transcript under `CLAUDE_CONFIG_DIR` with an `assistant` record carrying `"apiError":
      "usage_limit_reached"` and `resetsAt` two seconds ahead, followed by a `last-prompt` and a
      `cost-state` record, prints `{"type": "result", "is_error": true, "result": "You've hit your
      session limit · resets 9:10pm (Europe/Amsterdam)"}` and exits 1, and whose second run opens
      a pull request: prints a line starting "limit: the usage limit was reached; waiting until "
      and ending "(session `<id>`)", then "opened: #n from `<branch>`", and exits 0. The fake is
      started twice, the second time no earlier than `resetsAt`, with `--resume <id>` and no
      `--session-id`, and with In scope's resumed prompt on stdin; the run log's events for the
      session are `start`, `pid`, `end`, `pid`, `end`.
      Red today: the driver prints "park: the session ended in an error: `unknown` (session
      `…`)" and starts the fake once.
      Test: `UsageLimitTest.test_waits_and_resumes`.
- [ ] C09.2 **new** — As C09.1, but the resumed run's last `assistant` record is the limit again:
      the driver prints "park: the usage limit was reached (session `<id>`)", opens a park issue
      as for any park, exits 1, and starts the fake exactly twice.
      Red today: as C09.1, after one start.
      Test: `UsageLimitTest.test_second_limit_parks`.
- [ ] C09.3 **new** — As C09.1, but `resetsAt` 30 hours ahead: the driver prints "park: the usage
      limit resets at <YYYY-MM-DD HH:MM>, more than 6 hours away (session `<id>`)" within 10
      seconds, exits 1, and starts the fake once; with `--limit-hours 40` it waits instead (the
      test stops it with the halt file, C09.4).
      Red today: the Day 4 error line; and `--limit-hours` is refused by the argument parser,
      exit 2 (its wording differs between `--limit-hours 40` and `--limit-hours=40`, so the test
      reads the exit code only).
      Test: `UsageLimitTest.test_far_reset_parks`.
- [ ] C09.4 **new** — As C09.1, with `resetsAt` 60 seconds ahead: the test writes `<state>/halt`
      during the wait; the driver prints "halt: the halt file was set during the wait for the
      usage limit (session `<id>`)" within 5 seconds of it, exits 1, starts the fake once, and
      the run log's events for the session are `start`, `pid`, `end`.
      Red today: the Day 4 error line, and no wait.
      Test: `UsageLimitTest.test_halt_during_wait`.
- [ ] C09.5 **hold** — A session whose transcript is missing, or whose last `assistant` record
      carries no `apiError` (a limit record followed by a later `assistant` record included),
      keeps Day 4's outcome lines: the tests of `tests/test_once_outcome.py` pass unedited, and a
      fake with an `is_error` result and such a transcript prints "park: the session ended in an
      error: `<subtype>` (session `…`)".
      Test: `UsageLimitTest.test_earlier_limit_is_not_the_last`, and `tests/test_once_outcome.py`.
- [ ] C09.6 **new** — `hooks/guard.py <driver folder> <refusals folder>`, given on stdin a
      `Bash` call of `git push origin main` with `"session_id": "s1"`: exits 2 with C03.4's
      line, and `<refusals folder>/hooks.jsonl` (the folder created) holds one line whose keys
      are `at`, `session`, `hook`, `tool`, `input` and `line`, with `"s1"`, `"guard"`, `"Bash"`,
      `{"command": "git push origin main"}` as a string, and that line. Given `gh pr view 12`, it
      exits 0, prints nothing and creates no file.
      Red today: the guard ignores its second argument; no file is created.
      Test: `HookLogTest.test_guard_logs_refusal`, `HookLogTest.test_guard_pass_writes_nothing`.
- [ ] C09.7 **new** — `hooks/halt.py <halt file> <refusals folder>` while the halt file exists,
      given a `Write` call with `"session_id": "s2"`: exits 2 with C03.3's line and logs one line
      with `"s2"`, `"halt"`, `"Write"` and the call's `tool_input` as `json.dumps` writes it;
      given stdin `not json`, it still exits 2 with the same stderr and logs a line whose
      `session`, `tool` and `input` are null; with no halt file, it exits 0, prints nothing and
      creates no file. The test's failure messages print `<halt>` in place of the halt file's
      path, so a break's report can replay.
      Red today: the halt hook ignores its second argument; no file is created.
      Test: `HookLogTest.test_halt_logs_refusal`, `HookLogTest.test_halt_unreadable_stdin_logs_nulls`.
- [ ] C09.8 **hold** — When the log cannot be written (the refusals folder's path is an existing
      file), each hook still exits 2 and its stderr is its one refusal line, nothing more. True
      today because the hooks ignore the argument; broken on B1's code by taking away the
      write's guard.
      Test: `HookLogTest.test_unwritable_log_still_refuses`.
- [ ] C09.9 **new** — `driver.settings.write(state, home)` gives both hook commands
      `<state>/refusals` as their last argument: run through the shell as C03.5 runs them, the
      guard command given `git push origin main` with `"session_id": "s1"` exits 2 and leaves one
      line in `<state>/refusals/hooks.jsonl` with `"session": "s1"`; the halt command, with
      `<state>/halt` present, leaves a second line with `"hook": "halt"`.
      Red today: no `<state>/refusals/hooks.jsonl` is written.
      Test: `HookLogTest.test_settings_commands_log`.
- [ ] C09.10 **hold** — C03.3, C03.4 and C03.5 hold: `python -m unittest tests.test_hooks
      tests.test_halt` passes with both files unedited, so a hook given one argument behaves as
      Day 3 wrote it, and the halt command run with an inherited stdin does not hang. The breaks
      are recorded on B1's code, since B1 rewrites the lines a break on today's code would use.
- [ ] C09.11 **new** — `run-steps.py status` on a run log built by the test, with session `a`
      ended by an `end` line of `"denials": 1` and no `refused` list, session `b` with `start`
      and `pid` only, and session `c` ended by an `end` line of `"denials": 0`, then a `fix` and
      a `pid` line; and a `<state>/refusals/hooks.jsonl` of guard lines, each refusing `git push
      origin main`: two for `b`, one for `a` and one for `c` dated before their `end` lines, and
      one for `c` dated after its `end` line. It prints "refusals: 4" (1 + 2 + 1), its by-tool
      lines are the one "  3 Bash: {"command": "git push origin main"}", `b`'s step line reads
      "refusals 2" and `c`'s "refusals 1". The lines dated before an `end` line are not counted
      again.
      Red today: it prints "refusals: 1", and `b`'s step line "refusals 0".
      Test: `HookRefusalCountTest.test_status_counts_killed_session`.
- [ ] C09.12 **new** — `scripts/driver-runs.py` on the same run log and hook log gives session
      `a`'s run `"denials": 1`, `b`'s `"denials": 2` and `c`'s `"denials": 1`.
      Red today: `b`'s run has `"denials": 0` and `c`'s `"denials": 0`.
      Test: `HookRefusalCountTest.test_driver_runs_counts_killed_session`.
- [ ] C09.13 **new** — A fake session that writes `<state>/halt` and then exits 0 with a result,
      having opened a pull request: `run-steps.py --once` prints "halt: the halt file was set
      while the session ran (session `<id>`)", exits 1, opens no park issue (the fake `gh` saw no
      `issue create` after the run's own), and the run log's events for the session are `start`,
      `pid`. `driver.loop.resume`, called with the fakes of `tests/test_runlog_fix.py` on a fake
      whose resumed run writes the halt file, returns that line with code 1, and the run log's
      events after its `fix` line are `pid` alone. As C09.1, with the resumed run writing the
      halt file: the same line, exit 1, and events `start`, `pid`, `end`, `pid`.
      Red today: the driver prints "opened: #n from `…`" and writes an `end` line.
      Test: `HaltRaceTest.test_halt_file_after_session`, `HaltRaceTest.test_halt_file_after_resume`,
      `HaltRaceTest.test_halt_file_after_limit_resume`.
- [ ] C09.14 **hold** — The level 2 count stops at `driver/loop.py`'s own park line: with checks
      red after two fixes, `loop.wait_pr` returns its park line and `once.park_issue` writes it to
      the run log as a `park` line; `driver.status.level_2_run` over two `merged` lines with
      `"changed": false` and then that line gives 0, and over that line and then the two `merged`
      lines gives 2.
      Test: `Level2SentenceTest.test_loop_park_stops_the_count`.

## Verify
```bash
python -m unittest tests.test_usage_limit tests.test_hook_log tests.test_hook_refusal_count tests.test_halt_race tests.test_level_2_sentence tests.test_once_outcome tests.test_hooks tests.test_halt -v
```

## Notes
- Picks up H08.1 and C08.15 (C09.1–C09.5), H08.2 (C09.6–C09.12), H08.3 (C09.13) and H08.4
  (C09.14). C08.15's lines are kept: its park sentence is C09.2's, its test names C09.1's and
  C09.2's. C08.15 stays unticked in Day 8's file, which is never edited.
- No `Replaces:` line: Day 4's outcome rows (C04.10's table) still decide every session whose
  last `assistant` record is not the limit (C09.5), and a hook given one argument behaves as Day
  3's criteria say (C09.10).
- The plan-auditor (Phase 2, 2026-11-11, `main` at `f35826e`) found five things; this spec takes
  them as follows. 1: the log goes to `<state>/refusals`, a folder Day 10 can open to the second
  account alone (H09.1), and a failed write still refuses (C09.8). 2: the usage limit's source is
  named (Assumed, below), and the real headless shape goes to the level 2 trial (H09.2). 3: H08.3
  is a criterion on the driver (C09.13), not a retry in the tests. 4: Day 10's. 5: both readers
  are covered (C09.11, C09.12).
- The flaky tests of D08.76 and D08.81: at the close, `python scripts/test-parallel.py --repeat 10
  test_once_halt.py` and the same for `test_once_stop.py` (file names, not paths: the runner
  globs them under `tests/`), with the counts in the Notes. A failure left is a Defect and a
  hand-off; `test_once_stop.py`'s cause was never found, and the STOP path is not the halt path.
- **Assumed** — the usage limit's record, read from this machine's transcripts:
  `grep -h '"apiError":"usage_limit_reached"' -r --include=*.jsonl ~/.claude/projects` → five
  records, CLI 2.1.295 to 2.1.312, each an `assistant` record with
  `apiErrorParams.rate_limit_info.resetsAt` (epoch seconds), `rateLimitType` `five_hour` or
  `seven_day`, `"error": "rate_limit"` and a text such as "You've hit your session limit · resets
  9:10pm (Europe/Amsterdam)", "You've hit your 5-hour limit · resets 2:50am" or "You've hit your
  weekly limit · resets …". In none is it the file's last line: `last-prompt` and `cost-state`
  records follow. In the one transcript that ended at the limit it is the last `assistant`
  record; in the other four the person carried on after the reset. All five are `"entrypoint":
  "claude-vscode"`; none is headless, and none is on 2.1.322. That `claude -p` writes the same
  record, and what its `--output-format json` result then holds: not run, since no headless
  session has met the limit; the level 2 trial records it (H09.2).
- **Assumed** — a PreToolUse hook's stdin carries `session_id`, `tool_name` and `tool_input`:
  `scripts/refusal_log.py` and `scripts/read-guard.py` read them, and this repository's
  `.claude/state/refusals.jsonl` holds 84 records, 84 with a session and 82 with a tool, from
  interactive sessions. A headless session on 2.1.322: not run; Track B1's PR runs it.
- **Assumed** — the hook's `session_id` is the driver's `--session-id`, on `--resume` too and in
  a subagent; a resumed session writes to the same `<session>.jsonl`; `claude -p --resume <id>`
  continues a session that ended on the limit. Shown so far: `claude --help` says
  `--fork-session` creates a new session ID, so a plain resume keeps it; in
  `.claude/state/refusals.jsonl`, a main session's and its subagents' hook calls share one
  session ID (interactive). Not run headless, and `--resume` after a limit never (`plan.md`,
  "Unverified"). The fakes stand in.
- **H08.5, answered by the maintainer on 2026-11-11** (picks up H08.5): `claude -p "Run this
  exact command with the Bash tool: echo driver > out.txt" --model haiku --output-format json
  --permission-mode auto --allowedTools "Bash(echo:*)" --max-budget-usd 0.5` on 2.1.322 →
  `"permission_denials": []`, `"is_error": false`, and `out.txt` held "driver" (run in this
  repository's root by mistake; the file was removed before any commit). So `auto` mode let the
  write through, as #118 saw on 2.1.170, where D03.13 saw it denied on 2.1.170.
  `tests/test_live_cli.py` cannot tell: it passes `--allowedTools Bash`. Nothing in Day 9 rests
  on `auto` mode refusing a call: what the driver must refuse, its own hooks refuse, and they
  log it (C09.6–C09.9).
- **Defect** D09.1 — found: spec-change PR · cause: environment · made: none · `auto` mode with
  `--allowedTools "Bash(echo:*)"` denied `echo driver > out.txt` once (D03.13, 2.1.170) and let it
  through twice (#118 on 2.1.170, this PR on 2.1.322): the same call does not get the same answer,
  so a refusal by `auto` mode is not something a criterion can rest on. Day 3's choice of `Bash`
  for the live check stands.
- The result of a headless session carries `"api_error_status"` (null in the H08.5 run) beside
  `is_error`; whether a usage limit sets it is not known (H09.2). The driver reads the transcript,
  not this field.
- A crash during the wait leaves the session with an `end` line whose outcome starts "limit:":
  the next start reads the step as Day 7's table does (a branch with no pull request), and starts
  a new session. Recorded, not changed.
- **Hand-off** H09.1 → Day 10: `<state>/refusals` must be writable by the second Windows account
  while `on` checks the rest of the driver's folder is not; and the transcripts the usage limit
  is read from sit in that account's `~/.claude` (or its `CLAUDE_CONFIG_DIR`), not the driver's.
- **Hand-off** H09.2 → Day 13: the record says whether a headless session met the usage limit,
  and if it did, quotes its transcript record and its `--output-format json` result, so the
  Assumed line above is checked or corrected.
- **Hand-off** H09.3 → the maintainer: a fix's resumed session that meets the usage limit parks
  with no wait, and a STOP issue is not read during the wait. Neither is needed for level 2 to
  run, and no Phase 2 day owns them; the maintainer decides whether one should.
