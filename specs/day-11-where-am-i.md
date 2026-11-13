# Day 11 — Where am I, while a session runs: the stream, the events, the heartbeat, `status --watch`, the estimate, the comments

**Phase:** 2 · **Depends on:** Day 10 · **Expected PRs:** 9 (the spec change, Tracks A, B, C, D, E1, E2, F, the close)

## Goal
While a session runs, the maintainer can tell a session at work from one that hangs, on the PC
and on the phone: the driver reads the session's `stream-json` events line by line on the host,
keeps `<state>/heartbeat.json` and `<state>/sessions/<session>.events.jsonl`, `status` (and
`status --watch`) shows how long the session has run beside the median of earlier sessions of
its kind, its last event and the tokens so far, and the run's issue carries one comment edited at
each poll and one new comment when the session goes quiet for `stale_minutes`; the `result`
event stays the record of cost, session and refusals (`plan.md`, "Where am I, while a session
runs").

## In scope

- **The stream (Track A).** The session's command (`driver.once.begin`) carries
  `--output-format stream-json --verbose` in place of `--output-format json`, every other
  argument and their order unchanged, on the PC and inside the container's command alike:
  `--verbose` right after `stream-json`, so `--session-id <uuid>` stays last (the fake `docker`
  matches a session's run by that tail, `tests/fake_docker.py:38`). A resumed session
  (`loop.resume`, `once.usage_limit`) is the same list with `--resume`, as today.
  `driver/preflight.py`'s `FLAGS` is not changed (C04.3 counts its "lists no" lines, and
  `tests/test_preflight.py`'s fake `HELP` is pinned by C10.31): only Track F checks `--verbose`.
  A new module `driver/stream.py` holds `result(text)`: the last line of the session's stdout
  that parses as a JSON object whose `type` is `"result"`, or `None`. `once.outcome` and
  `once.write_end` read the session's `result` through it in place of `once.parsed`, so the
  outcome table (`is_error`, `subtype`, `result`), `total_cost_usd` and `permission_denials` are
  read from the `result` event as they are from the JSON object today. The session id stays the
  driver's own `--session-id` uuid, never read from the output, as today. `outcome` stays the
  place the result is judged (`tests/test_halt_race.py` patches it). A stdout with no `result` line is what a session that
  printed nothing is today: "park: the session ended without a result (exit <n>; session
  `<s>`)". The tests' fake `claude` prints its one result object on one line, which is a stream
  of one `result` event: the outcome tests pass unedited.
- **The events (Track B).** `once.run_session` writes the prompt to the session's stdin and
  closes it, then reads its stdout line by line on a reader thread (an error writing the prompt to a
  session that has already exited, `BrokenPipeError` or `OSError`, is ignored, as
  `communicate` ignores it today); the main thread waits on the
  reader with the poll as its timeout (`min(--poll, the time left to --session-minutes)`), and at
  each timeout reads the project's issues and the bound as it does now: a `STOP` issue stops the
  session within a poll, and the bound kills its tree. The prompt is written to stdin and stdin
  closed before the wait, no longer through `communicate(data)`; stderr stays inherited, not
  piped. The reader is a daemon thread and the only reader of the pipe: `kill_session`'s
  `proc.communicate(timeout=10)` after the kill becomes a join of the reader with a 10-second
  timeout, and a process that escaped the kill and holds the pipe leaves the reader behind, not
  the driver. `run_session` keeps its name, its arguments and its returns, `(stdout bytes, return
  code)`, `PAST` or `None` (`tests/test_session_bound.py` patches it and reads `PAST`), and its
  three callers (`once.one_session`, `once.usage_limit`, `loop.resume`) are unchanged. What
  Track C and E add to its poll reads `args` attributes a test's `SimpleNamespace` may lack
  with a default (`getattr(args, "stale_minutes", 10)`). For each line read,
  the reader calls `driver.stream.append(state, session, line)`, which appends one line to
  `<state>/sessions/<session>.events.jsonl` (the folder made if missing), written as bytes by the driver on the host, never from inside the container:
  `{"at": <lock.STAMP of the read>, "kind": <kind>}`, plus, for an `assistant` event,
  `"message": <message.id>`, `"in": <input_tokens + cache_creation_input_tokens +
  cache_read_input_tokens>` and `"out": <output_tokens>` from its `message.usage` (a missing
  count is 0). The kind, from `driver.stream.kind(line)`: `system <subtype>` for a `system`
  event (`system` when it has no string `subtype`); for an `assistant` event, `tool <name>` of its first `tool_use` content item, else
  `reply` when it holds a `text` item, else `assistant`; `tool result` for a `user` event;
  `result` for a `result` event; the `type` itself for any other object with a string `type`;
  `unparsed` for a line that is not a JSON object, or an object with no string `type`, a partial
  last line read at the end included. A blank line is skipped. An `unparsed` line is counted in the events file, never
  fatal. A resumed session appends to the same file. The events go only there: the run log
  (`<state>/run.jsonl`) gets no new line and no new key ("The run log keeps one line per event"
  in `plan.md` means its own events: start, pid, end, park).
- **The heartbeat (Track C).** When the session starts and at each poll, the driver rewrites
  `<state>/heartbeat.json`, one JSON object written as bytes, overwritten, never appended:
  `{"session", "step", "started", "poll", "last_event"}`, the times in `lock.STAMP`, `started`
  the run log's `start` line's `at` (`null` for a session with no `start` line, as Day 6's
  `WaitTest` resumes one), `last_event` the newest events-file line's `at` or `null`.
  It is written before the poll's issues read, so a failed read still beats. Each write goes to a
  temporary file in `<state>` and `os.replace`s the heartbeat; a write that fails (on Windows a
  `PermissionError` while a reader holds the file) is skipped, as a failed issues read is. It is
  left in place when the session ends, a `halt` or a crash included: nothing judges liveness by
  it (`status` reads the run log's `pid` lines).
- **The progress lines and `status --watch` (Track D).** `driver.status.progress(records,
  session, events, now)` returns three lines for a running session:
  - `running: <d> (estimate <d>, the median of <n> earlier <kind> sessions)`, or
    `running: <d> (no estimate: <n> earlier <kind> sessions)` when n < 3, or
    `running: <d> (no estimate: the step has no kind)`, or `running: unknown (no start line)`
    for a session with no `start` line. `<d>` is `<m>m<ss>s` (`75m03s`; minutes
    not wrapped into hours). The session's kind is its `start` line's `prefix`: ending `/spec` is
    `spec`, holding `/track-` is `track`, ending `/close-the-day` is `close`. The earlier
    sessions are the other sessions of the run log of the same kind with a `start` and an `end`
    line; each one's length is its first `end`'s `at` minus its `start`'s `at`; the median of an
    even n is the mean of the middle two, rounded down to the second.
  - `last event: <kind>, <d> ago` (`0m40s ago`), or `last event: none yet`.
  - `tokens so far: <in> in, <out> out`: over the distinct `message` values of the events-file
    lines that carry `message`, the last `in` and `out` seen for each, summed. No dollars: the cost stays
    the `result`'s, and "cost so far" stays the run log's `end` lines' sum.

  `status` prints them as three lines of their own right after its "in progress:" line when a
  session is live (Day 7's `runlog.live_session`), reading
  `<state>/sessions/<session>.events.jsonl`; the "in progress:" line and every other line stay
  as they are (C10.25, C08.10), and with none live nothing is added. `status` still creates
  nothing (C08.2): a missing events file reads as no events, and no folder or file is made.
  `run-steps.py status --watch [--poll <s>]` prints `status` again every `--poll` seconds, a
  blank line between, until a print finds no live session by `runlog.live_session`, then exits
  with that last print's code; with none live at the start it prints once. `status.run` takes
  the poll as a keyword, `status.run(project, gh, state, watch=None)`, so today's callers are
  unchanged.
- **On the phone (Tracks E1 and E2).** At each poll that read the project's issues and found no `STOP`,
  the driver comments on the run's issue: the first time `gh issue comment <n> --body-file -`,
  keeping the comment's id from the URL it prints (`#issuecomment-<id>`); after that
  `gh api --method PATCH repos/{owner}/{repo}/issues/comments/<id> --input -` with
  `{"body": <the body>}` on stdin; each call with `issues._write`'s timeout of 10 seconds, so a
  hanging `gh` cannot hold up the `STOP` read or the bound. The body: "step: <step>", "session:
  <s>", the run's issue's own wording (`issues.open_run`), then the three progress lines; so
  `OnTest.test_steps_per_night` (C06.9), whose `--poll 0.01` sessions span polls and whose
  first comment must hold "step: ", passes unedited. An edit does not notify. When the time since the last event (or since the session's
  start, with none) reaches `stale_minutes`, one new comment on the run's issue: "stale: session
  `<s>` has sent no event for <stale_minutes:g> minutes; it is not stopped", once per session. A
  stale session is reported, not killed. The comment is edited by its id, never with `gh issue
  comment --edit-last`, which after the stale comment would edit that one. The id and whether
  the stale comment was made are kept in `<state>/sessions/<session>.comment.json`, so a
  resumed session (a fix, the usage limit) edits the same comment and makes no second stale
  comment. A comment or edit that fails is skipped and the next poll
  tries again; it prints nothing and changes no outcome. A session that ends before its first poll
  makes no comment. `driver.json` takes an optional `stale_minutes`, a number above 0, 10 when
  absent; `driver.config.load` reports "cannot start: <path>'s stale_minutes must be a number
  above 0" otherwise; where `--once` and `on` load the config, they set `args.stale_minutes =
  config.get("stale_minutes", 10)`, and the poll reads `getattr(args, "stale_minutes", 10)`.
  The tests' fake `gh` (`tests/test_github.py`, Track E1) gains a `comment_id` (default 1) for
  the URL `issue comment` prints, an `api` answer that records its `--input -` stdin in
  `bodies.jsonl` and exits 0 (today it exits 99), and a `comment_code` that fails `issue comment`
  and `api` only, the issues read left working.
- **The image's Claude Code (Track F).** A live test, skipped unless `DRIVER_CONTAINER_IMAGE`
  and `DRIVER_CONTAINER_SECRETS` are set, runs one tiny session in the image with
  `--output-format stream-json --verbose` and reads it with `driver.stream`. It is a hold: the
  image takes the flags today (the spec-auditor ran the refusal without `--verbose` in it), and
  Track A creates `driver.stream`.

## Out of scope

- A page in a browser: later, read-only, from the same files (`plan.md`, "Where am I, while a
  session runs").
- Estimating the cost in dollars, from the events or anything else: only the `result` carries it.
- Reading a transcript for progress: nothing here reads one (Day 9's usage-limit read stays).
- The reviewer — Day 12. The level 2 merge, and `live-check` in the image (H10.1) — Day 13. The
  usage limit met by a headless session (H09.2) and the container's sessions in the record
  (H10.2) — Day 14.
- Killing a stale session: `--session-minutes` and the `STOP` issue decide that, as now.
- Removing old events files or the heartbeat: they stay in `<state>`, uncommitted.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | `--output-format stream-json --verbose`; `driver.stream.result`; the outcome read from the `result` event: C11.1–C11.4, C11.22 |
| B | | The reader thread; `driver.stream.kind`; the events file; STOP and the bound through the new wait: C11.5–C11.9 |
| C | | `<state>/heartbeat.json` at the start and at each poll: C11.10 |
| D | | `driver.status.progress`, the estimate, `status`'s lines and `status --watch`: C11.11–C11.15 |
| E1 | | The heartbeat comment edited in place; the fake `gh`'s switches: C11.16, C11.18, C11.20 |
| E2 | | The stale comment, `stale_minutes`, the resumed session's comment: C11.17, C11.19 |
| F | | Live: the image's Claude Code takes `stream-json --verbose`: C11.21 |

In order: A, B, C, D, E1, E2, F. B rewrites `run_session`, which A leaves alone; C and E1 add
to B's poll; E1's body is D's lines; E2 adds to E1. F last, on the image `driver.json` names.

Breaks recorded on earlier days whose finds a track rewrites are recorded again in that track's
PR under the same `<what>`, with a `manifest:` line: B — Day 4's "the prompt not written to the
session's stdin" (`prompt.encode("utf-8")`), Day 5's "the poll's STOP match never matches",
Day 6's "the bound never reached", Day 10's "run_session writes no pid line", "the bound's kill
left the container running" and "the kill past the bound removed", all in `run_session`; A —
Day 4's "the PARK line not read" and "denials always 0", in `outcome` and `write_end`, when their
finds move; D — Day 7's four in `status.run` (`issues.open_issues(project, gh)`, `return 2 if
gh_reason`, the stderr print, `reason = reason or later`) and Day 8's one there, if `--watch`
moves them, each find left matching once. A track checks the day manifests in `specs/breaks/` for its files before it opens
its PR.

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").

- [ ] C11.1 **new** — With every check passing, `--once` starts one session whose arguments,
      after the program, are C05.8's (C04.9's) with `--output-format stream-json
      --verbose` in place of `--output-format json`, in that place, and nothing else changed,
      `--session-id <uuid>` still last; everything else C05.8 checks (the uuid of the `start` line, the prompt's two lines on stdin with the en dash as
      `\xe2\x80\x93`, the `.cmd` on Windows, the real path as cwd, the lock and settings during
      the session, `rules/session.md`'s words, its six `gh` calls) holds by the same tests.
      With the container keys, the `docker run`'s inner list (C10.15) carries the same two flags.
      Red today: the fake records `--output-format json`; `test_session_command` and
      `test_session_runs_in_the_container`, edited to expect the new flags, fail on the lists.
      Test: `OnceTest.test_session_command`, `BoxSessionTest.test_session_runs_in_the_container`.
      Replaces: C05.8 — was: the session started with C04.9's arguments, `--output-format json`
      among them, around the run's issue and `run.json`.
      Replaces: C10.15 — was: the container's inner `claude -p` carried today's flags,
      `--output-format json` among them.
      Plan: N30 "The driver runs claude -p with --output-format stream-json --verbose"
- [ ] C11.2 **new** — `driver.stream.result` on a stdout of four lines, a `system` `init`
      event, an `assistant` event with `usage` `{"output_tokens": 900}`, a line `not json` and a
      `result` event with `total_cost_usd` 0.42 and two `permission_denials`, returns that
      `result` event, and on the same lines with a `result` of `total_cost_usd` 0.10 put before
      the `assistant` one returns the last, 0.42; `--once` on a fake printing those lines, then opening a pull request,
      prints "opened: #5 from `day-01/track-a-x`" and writes an `end` line with `cost_usd` 0.42
      and `denials` 2, whatever the `assistant` event said. Red today: `driver.stream` does not
      exist; `--once` parks "park: the session ended without a result (exit 0; session
      `<uuid>`)", since the four lines are not one JSON object.
      Test: `StreamResultTest.test_result_is_the_last_result_line`,
      `StreamResultTest.test_once_reads_the_result_event`.
      Plan: N31 "The result event stays the record"
- [ ] C11.3 **new** — A fake printing `not json` then a `result` line ending in "PARK: needs a
      decision" parks "park: the session parked: needs a decision (session `<uuid>`)". Red today:
      it parks "park: the session ended without a result (exit 0; session `<uuid>`)".
      Test: `StreamResultTest.test_unparsed_line_skipped`.
      Plan: N31 "a line that does not parse is counted, not fatal"
- [ ] C11.22 **hold** — A fake printing a `system` `init` and an `assistant` line and no
      `result`, exiting 0, parks "park: the session ended without a result (exit 0; session
      `<uuid>`)", and its `end` line has `cost_usd` null and `denials` 0: true today (two JSON
      lines are not one object) and after Track A (no `result` line). Track A adds the test and
      breaks it once.
      Test: `StreamResultTest.test_no_result_line`.
      Plan: N31 "a stream with no result is a session that printed nothing"
- [ ] C11.4 **hold** — The outcome table and the run log hold: `tests/test_once_outcome.py`,
      `tests/test_once_run.py`, `tests/test_usage_limit.py`, `tests/test_runlog.py`,
      `tests/test_runlog_end.py`, `tests/test_once_halt.py` and `tests/test_halt_race.py` pass
      unedited (`git diff --exit-code c8e5963` on them is empty), and C10.31's diff against
      `495bf69` stays empty: no new test goes in a file it lists.
      Plan: N31 "The result event stays the record"
- [ ] C11.5 **new** — On a fake that prints, one line each, a `system` `init` event, an
      `assistant` event whose content is a `tool_use` named `Bash` (`message.id` `m1`, `usage`
      input 10, cache creation 5, cache read 100, output 7), a `user` event, an `assistant` event
      with a `text` item (`m2`, input 3, output 20), a line `not json`, a blank line and a
      `result` event, `<state>/sessions/<uuid>.events.jsonl` holds six lines whose kinds are
      `system init`, `tool Bash`, `tool result`, `reply`, `unparsed`, `result`; every `at` parses
      with `lock.STAMP`; the `tool Bash` line has `"message": "m1", "in": 115, "out": 7`. Red
      today: no `sessions` folder.
      Test: `EventsTest.test_events_file`.
      Plan: N30 "reads its output line by line on a reader thread, and appends each event's time
      and kind to <state>/sessions/<session>.events.jsonl"
- [ ] C11.6 **new** — `driver.stream.kind` on each case of In scope's list (a `system` event with
      subtype `init`; an `assistant` event with a `text` item then a `tool_use` named `Read`; an
      `assistant` event with only a `thinking` item; a `user` event; a `result` event;
      `{"type": "rate_limit_event"}`; `[1, 2]`; `{"no": "type"}`; `{"type": "assi`) returns
      `system init`, `tool Read`, `assistant`, `tool result`, `result`, `rate_limit_event`,
      `unparsed`, `unparsed`, `unparsed`. Red today: `driver.stream.kind` does not exist.
      Test: `StreamKindTest.test_kinds`.
      Plan: N30 "appends each event's time and kind"
- [ ] C11.7 **new** — `--session-minutes` ending a session mid-line keeps the events read so
      far: a fake that prints a `system` `init` line, then `{"type": "assi` with no newline,
      flushes and sleeps, run with `--session-minutes 0.05 --poll 0.2`, parks "park: the session
      ran past 0.05 minutes (session `<uuid>`)" as today, and its events file's kinds are
      `system init`, `unparsed`. Red today: no events file.
      Test: `EventsTest.test_bound_keeps_events_read`.
      Plan: N31 "the poll, STOP and --session-minutes work as before"
- [ ] C11.8 **hold** — A `STOP` issue still stops a session within a poll, a failed issues read
      is still skipped, and the bound still parks, with the session printing nothing:
      `tests/test_once_stop.py` and `tests/test_session_bound.py` pass unedited (in C11.4's
      `git diff`), on the reader's wait.
      Plan: P20 "from the phone (an issue whose title starts with `STOP`) it takes as long as the
      driver's poll of GitHub"
- [ ] C11.9 **hold** — The container's mounts and command are Day 10's: `tests/test_box_command.py`
      passes unedited (in C11.4's `git diff`), and no line of `driver/stream.py`, which holds the
      events writer (`append`), names `/state` or `/work`: `grep -nE '"/(state|work)'
      driver/stream.py` finds none (from Track B; before it the file has no writer). Its break
      runs with `--expect-stdout '^$'`.
      Plan: N30 "on the host and written by the driver, never from inside the container"
- [ ] C11.10 **new** — A fake that prints a `system` `init` line, sleeps 4 seconds printing
      nothing (a long tool), then prints a `result`, run with `--poll 0.3`, reads
      `<state>/heartbeat.json` 0.5 and 2.5 seconds after the events file first holds the `init`
      line, each read retried for up to a second when it fails (on Windows the driver's
      `os.replace` and the test's read can meet): both are one JSON object with exactly
      the keys `session`, `step`, `started`, `poll`, `last_event`; `session` is the run log's
      uuid; the second `poll` is later than the first; `last_event` is the same in both, the
      `init` line's `at`; after the step the file is still there. Red today: no heartbeat file.
      Test: `HeartbeatTest.test_heartbeat_beats_through_a_quiet_tool`.
      Plan: N29 "At each poll the driver rewrites <state>/heartbeat.json with the session, its
      step, when it started, the time of the poll and the time of the session's last event"
- [ ] C11.11 **new** — `driver.status.progress` with `now` fixed: on a run log with three
      earlier `track` sessions of 10m00s, 20m00s and 40m00s and a running `track` session started
      12m05s before `now`, whose events' last line is `tool Bash` 40 seconds before `now`, with
      `assistant` lines `m1` (in 115, out 7), `m1` again (in 115, out 9) and `m2` (in 3, out 20),
      returns `running: 12m05s (estimate 20m00s, the median of 3 earlier track sessions)`,
      `last event: tool Bash, 0m40s ago`, `tokens so far: 118 in, 29 out`. Red today: no
      `progress`.
      Test: `ProgressTest.test_progress_lines`.
      Plan: N33 "the median length of the run log's earlier sessions of the same kind, and its
      n"; N32 "how long it has run, its last event and how long ago, and the tokens so far"
- [ ] C11.12 **new** — The estimate's edges: two earlier `track` sessions give `running: <d> (no
      estimate: 2 earlier track sessions)`; four of 10, 20, 30 and 41 minutes give `estimate
      25m00s, the median of 4`, and of 10m00s, 20m00s, 20m01s and 41m00s `estimate 20m00s`
      (20m00.5s rounded down); a session with no `start` line gives `running: unknown (no start
      line)`; an earlier session with no `end` line, or of kind `spec`, is not
      counted; a step whose prefix is none of the three gives `(no estimate: the step has no
      kind)`; no events give `last event: none yet` and `tokens so far: 0 in, 0 out`. Red today:
      no `progress`.
      Test: `ProgressTest.test_estimate_edges`.
      Plan: N33 "fewer than three, no estimate"
- [ ] C11.13 **new** — `run-steps.py status` with a live session (a `pid` line of a running
      process, its `start` line and an events file) prints the three progress lines right after
      its "in progress:" line; the "in progress:" line still ends "cost so far $0.00". Red today:
      no progress lines.
      Test: `StatusWatchTest.test_status_shows_progress`.
      Plan: N32 "the step, how long it has run, its last event and how long ago, and the tokens so
      far; the cost stays the result's, never estimated in dollars"
- [ ] C11.14 **new** — `run-steps.py status --watch --poll 0.5` with a live session (a process
      the test started) prints a first block naming it; the test ends the process once it has
      read that block; then `status --watch` prints another block, a blank line between, the
      last with "in progress: none", and exits 0; with no live session it prints one block and
      exits 0; in both runs the state folder lists the same names before and after (C08.2).
      Red today: argparse refuses `--watch`, exit 2.
      Test: `StatusWatchTest.test_watch_until_the_session_ends`,
      `StatusWatchTest.test_watch_with_nothing_running`,
      `StatusWatchTest.test_watch_creates_nothing`.
      Plan: N32 "status --watch prints status again at each poll until the session ends"
- [ ] C11.15 **hold** — `status` with no live session prints what it printed before:
      `tests/test_status.py`, `tests/test_status_trial.py` and `tests/test_level_2_sentence.py`
      pass unedited (in C11.4's `git diff`).
      Plan: P62 "`status` prints it: the mode, the level, the step in progress and its cost so
      far"
- [ ] C11.16 **new** — A fake that prints `system` `init`, sleeps 4 seconds, then a `result`,
      run with `--poll 0.3` and the fake `gh`'s `comment_id` 99: before the run's issue's closing
      comment, the fake `gh` records one `issue comment <the run's issue>` whose body's lines are
      "step: <the step>", "session: <uuid>", then lines starting `running: `, `last event: `,
      `tokens so far:`; then at least one `api --method PATCH
      repos/{owner}/{repo}/issues/comments/99 --input -` whose stdin parses to an object with one
      key, `body`, the last of them holding "last event: system init". The step's outcome is the same
      as without. Red today: no comment before the run's issue's closing one.
      Test: `PhoneTest.test_heartbeat_comment_edited_in_place`.
      Plan: N34 "One comment on the run's issue per session, edited in place at each poll"
- [ ] C11.17 **new** — As C11.16 with `stale_minutes` 0.02 in `driver.json`: exactly one more
      `issue comment` on the run's issue, whose body is "stale: session `<uuid>`
      has sent no event for 0.02 minutes; it is not stopped"; the session is not killed and the
      step's outcome is as without. With `stale_minutes` absent (10): the heartbeat comment and
      no stale comment. With `<state>/sessions/<uuid>.comment.json` holding
      `{"id": 99, "stale": true}` before the first poll, written by the fake's `do`, which knows
      the state folder and the session (a resumed session's), the first poll edits comment 99 and no stale comment is made. Red
      today: no comment.
      Test: `PhoneTest.test_stale_comment_once`, `PhoneTest.test_not_stale_before_stale_minutes`,
      `PhoneTest.test_resumed_session_keeps_its_comment`.
      Plan: N34 "when no event has come for stale_minutes (10 by default, in driver.json), one new
      comment says so, once per session; a stale session is reported, not killed"
- [ ] C11.18 **new** — With the fake `gh` failing `issue comment` and `api` (exit 1), a session
      spanning several polls ends with the same outcome and the same stdout as with them
      working, and the next poll tries the comment again (two or more `issue comment` calls
      before the run's closing comment). Red today: no comment is tried.
      Test: `PhoneTest.test_failed_comment_skipped`.
      Plan: none — that a failed comment changes nothing is the driver's own care; `plan.md` says
      nothing of it
- [ ] C11.19 **new** — `driver.config.load` on a config with every Day 2 key and `stale_minutes`
      `"10"`, `0`, `-1` or `true` reports "cannot start: <path>'s stale_minutes must be a number
      above 0", one line; with 0.5 or absent it loads, and absent reads as 10 where the driver
      reads it. Red today: the config loads with each of them.
      Test: `StaleConfigTest.test_stale_minutes`.
      Plan: N34 "stale_minutes (10 by default, in driver.json)"
- [ ] C11.20 **hold** — A session shorter than one poll makes no comment: `OnceTest`'s
      `test_session_command` keeps its six `gh` calls (issue list, run list, issue create, pr
      list, issue comment, issue close), unedited in that part by Track A's edit; and C06.9's
      `OnTest.test_steps_per_night`, whose sessions span `--poll 0.01` polls, passes unedited
      (in C11.4's `git diff`).
      Plan: N34 "edited in place at each poll"
- [ ] C11.21 **hold** — Live: with `DRIVER_CONTAINER_IMAGE` and `DRIVER_CONTAINER_SECRETS` set, runs
      `docker run --rm -i --env-file <secrets> <image> claude -p --model haiku --output-format
      stream-json --verbose --max-budget-usd 0.05 --strict-mcp-config` with "Reply with the word
      ok." on stdin: exit 0; every non-blank line is a JSON object; the first's `type` is
      `system`; `driver.stream.result` of the output has `is_error` false, a number
      `total_cost_usd` and a string `session_id`; no line's kind is `unparsed`. The same command
      without `--verbose` exits non-zero. True of the image today; Track F adds the test and breaks
      it once.
      Test: `StreamLiveTest.test_image_takes_stream_json`.
      Plan: N30 "The driver runs claude -p with --output-format stream-json --verbose"

## Verify
```bash
python -m unittest tests.test_stream tests.test_events tests.test_heartbeat tests.test_progress tests.test_status_watch tests.test_phone tests.test_stale_config tests.test_stream_live tests.test_once tests.test_box_session tests.test_once_outcome tests.test_once_run tests.test_usage_limit tests.test_runlog tests.test_runlog_end tests.test_once_halt tests.test_halt_race tests.test_once_stop tests.test_session_bound tests.test_box_command tests.test_status tests.test_status_trial tests.test_level_2_sentence tests.test_on tests.test_wait -v
git -c core.safecrlf=false diff --exit-code c8e5963 -- tests/test_once_outcome.py tests/test_once_run.py tests/test_usage_limit.py tests/test_runlog.py tests/test_runlog_end.py tests/test_once_halt.py tests/test_halt_race.py tests/test_once_stop.py tests/test_session_bound.py tests/test_box_command.py tests/test_status.py tests/test_status_trial.py tests/test_level_2_sentence.py tests/test_on.py tests/test_contract.py
git -c core.safecrlf=false diff --exit-code 495bf69 -- tests/test_contract.py tests/test_decide.py tests/test_dry_run.py tests/test_steps.py tests/test_tree.py tests/test_config.py tests/test_encoding.py tests/test_halt.py tests/test_halt_report.py tests/test_home.py tests/test_hooks.py tests/test_issues.py tests/test_off.py tests/test_once_park_issues.py tests/test_once_parks.py tests/test_preflight.py tests/test_recovery_table.py tests/test_lock_takeover.py driver/decide.py driver/steps.py driver/home.py rules/session.md tests/test_failures.py tests/test_once_outcome.py tests/test_once_run.py tests/test_runlog.py tests/test_runlog_fix.py tests/test_session_bound.py tests/test_wait.py tests/test_kit_copy.py tests/test_lock.py tests/test_live_cli.py tests/test_once_halt.py tests/test_live_once.py tests/test_once_stop.py
```
`tests/test_stream_live.py` skips its Docker part unless `DRIVER_CONTAINER_IMAGE` and
`DRIVER_CONTAINER_SECRETS` are set; on this machine, with the image `driver.json` names built,
run it with both set as well.

Where the tests live: `StreamResultTest` and `StreamKindTest` in `tests/test_stream.py`;
`EventsTest` in `tests/test_events.py`; `HeartbeatTest` in `tests/test_heartbeat.py`;
`ProgressTest` in `tests/test_progress.py`; `StatusWatchTest` in `tests/test_status_watch.py`;
`PhoneTest` in `tests/test_phone.py`; `StaleConfigTest` in `tests/test_stale_config.py`;
`StreamLiveTest` in `tests/test_stream_live.py`. The fake sessions print their lines through
`fake_claude`'s `do` in `tests/test_once.py`, which is not edited beyond C11.1's flags; the
fake `gh` in `tests/test_github.py` gains Track E1's switches.

## Notes
- Picks up no hand-off: H10.1 goes to Day 13, H09.2 and H10.2 to Day 14 (`plan.md`, "Course
  corrections", 2026-11-13). Where Days 9 and 10 name "Day 11", they mean the reviewer, now Day 12.
- `specs/plan/promises.json`'s P60 still quotes `--output-format json`; from this day the command
  carries `stream-json --verbose` (`plan.md`, "What to build", item 2, says so). P60 is Day 4's
  and C11.1 replaces C04.9's flag; whether P60's text changes is a plan-change matter.
- `stream-json` repeats an `assistant` message's `usage` on each of its content blocks, as far as
  is known: the tokens are summed per distinct `message.id`, the last seen, not per line
  (C11.11). Track F's live run shows whether it holds; if the counts differ, a spec change.
- From the Phase 2 plan-auditor (2026-11-13, `main` at `c8e5963`): the command's criterion in
  force is C05.8, not C04.9; C10.31 pins `tests/test_preflight.py`, `tests/test_config.py`,
  `tests/test_once_stop.py`, `tests/test_session_bound.py` and others, so new tests go in new
  files and `FLAGS` stays; `run_session`'s names and returns are patched by tests; the reader
  replaces `kill_session`'s drain; `--verbose` before `--session-id`; the run log gets no events;
  `status`'s lines stay and it creates nothing; the heartbeat is replaced atomically and left in
  place; the comment is edited by id. `plan.md` claims the session id is read from the output
  ("Where am I, while a session runs"; "What to build", item 2): the driver never reads it, so
  this spec does not claim it; the wording is a plan-change matter, with `plan.md:130`'s "the
  JSON result" and `plan.md:630`'s "Days 1 to 9 have specs".
- Nothing this day writes to the project or its GitHub beyond the run's issue, and nothing reads
  a transcript for progress (`plan.md`, no commitment ID): C11.16's `gh` calls are the only new
  ones.
- `UsageLimitTest.test_far_reset_parks` failed on and off on Day 10 (D10.18) and runs through
  `run_session`: Track B runs `python scripts/test-parallel.py --repeat 10 tests/test_usage_limit.py`.
- H10.1, H09.2 and H10.2 are listed by the dashboard for Days 12 and 13: Day 12's spec cites
  H10.1 and passes it to Day 13, Day 13's cites H09.2 and H10.2 and passes them to Day 14.
- Breaks on the holds. Run in the spec-change PR, on today's code, since their checks exist
  already: C11.4 ("the PARK line read from the first line of the reply"), C11.8 ("a STOP issue
  no longer stopping the session (C11.8)"), C11.15 ("a progress line printed with no live
  session"), C11.20 ("a comment made at the session's start"). Left to the track that adds
  the check or the code it breaks:
  - C11.8, Track B: the issues read, and the bound, skipped at the reader's timeout.
  - C11.9, Track B: the events path given as `"/state/sessions"` in `driver/stream.py`.
  - C11.15, Track D: the progress lines printed with no live session.
  - C11.20, Track E1: the heartbeat comment made at the session's start.
  - C11.22, Track A: `result` returning the last JSON object whatever its `type`.
  - C11.21, Track F: `--verbose` left out of the test's command.
- H09.2's text (Day 9) asks for the session's "`--output-format json` result": from this day
  there is none; Day 14 reads it as the `result` event.
- Day 8's "a comment reader is Phase 2's, if the maintainer wants one" has no day: this day writes
  comments and reads none.
- A hold test whose `gh` call list changes because a session now spans a poll and comments is a
  stop-and-ask, not an edit: the comment is made only at a poll that read the issues and found no
  `STOP`.
- **Assumed** — `claude -p` refuses `stream-json` without `--verbose`: `echo x | claude -p
  --output-format stream-json --max-budget-usd 0.01` → "Error: When using --print,
  --output-format=stream-json requires --verbose", exit 1, on 2.1.322 (the PC's, 2026-11-13).
- **Assumed** — the `stream-json` `result` event carries the keys the `json` object did (`type`,
  `subtype`, `is_error`, `result`, `total_cost_usd`, `permission_denials`), one JSON object per
  line, each line flushed as its event happens, `docker run -i` included: not run (it costs a
  session): the main session runs one tiny live session on the PC's 2.1.322 before Track A and
  records what it printed in Track A's PR; Track F checks it in the image. Whether `usage`
  repeats on each content block of a message: Track F's PR reports it, no assertion.
- **Assumed** — `gh api` fills `{owner}/{repo}` from the repository of the current directory,
  and the driver runs `gh` with the project as cwd: `gh help api` → the placeholders "{owner},
  {repo}, and {branch} will get replaced with values from the repository of the current
  directory", gh 2.93.0 (the spec-auditor, 2026-11-13).
- **Assumed** — `gh issue comment <n> --body-file -` prints the new comment's URL ending
  `#issuecomment-<id>`, and `gh api --method PATCH repos/{owner}/{repo}/issues/comments/<id>
  --input -` with `{"body": ...}` edits it in place without a notification: not run (both write):
  the main session runs them on a scratch issue of this repository before Track E, gh 2.93.0.
- **Defect** D11.1 — found: auditor · cause: spec · made: Day 11 · C11.1 replaced C04.9, which C05.8 had already replaced, and named no `Replaces:` for C10.15, which pins the container's inner flags (the Phase 2 plan-auditor; fixed in this PR).
- **Defect** D11.2 — found: auditor · cause: spec · made: Day 11 · In scope said the session id is read from the `result` event; the driver never reads it, it uses its own `--session-id` uuid (the Phase 2 plan-auditor; fixed in this PR).
- **Defect** D11.3 — found: auditor · cause: spec · made: Day 11 · C11.7 expected "ran past 1.2 minutes" for `--session-minutes 0.02`; `past_bound` prints the minutes as given, "0.02" (fixed in this PR, now 0.05 minutes).
- **Defect** D11.4 — found: auditor · cause: spec · made: Day 11 · C11.11 expected `40s ago` where In scope's own `<m>m<ss>s` gives `0m40s ago` (fixed in this PR).
- **Defect** D11.5 — found: auditor · cause: spec · made: Day 11 · the heartbeat comment's body "session `<s>`: <step>" would have been `OnTest.test_steps_per_night`'s first comment and failed its "step: " check (C06.9); the body now opens with the run's issue's "step: " and "session: " lines (fixed in this PR).
- **Defect** D11.6 — found: auditor · cause: spec · made: Day 11 · the fake `gh` prints comment id 1 always, exits 99 on `api` without reading its stdin, and has no switch that fails only comments; the spec listed no edit to it (fixed in this PR: Track E1's switches).
- **Defect** D11.7 — found: auditor · cause: spec · made: Day 11 · C11.4's planned break "`result` returning the first `result` line" could be caught by no test, every fake printing one `result` line (fixed in this PR: dropped; C11.2 gets two `result` lines).
- **Defect** D11.8 — found: auditor · cause: spec · made: Day 11 · C11.9's grep read `driver/stream.py`, but the events writer was put in `run_session`, so the grep could not see the break it named (fixed in this PR: `driver.stream.append`).
- **Defect** D11.9 — found: auditor · cause: spec · made: Day 11 · C11.21 was tagged `new` with "Red today: `driver.stream` cannot be imported", false at Track F's start, and the image already takes the flags (fixed in this PR: a hold).
- **Defect** D11.10 — found: auditor · cause: spec · made: Day 11 · C11.3's first half (no `result` line parks) passes on today's code, so it was not `new` (fixed in this PR: split into C11.22, a hold).
- **Defect** D11.11 — found: auditor · cause: spec · made: Day 11 · `test_not_stale_before_stale_minutes` and `test_watch_creates_nothing` pass on today's code as described (fixed in this PR: the first requires the heartbeat comment, the second moved to C11.14 with exit 0).
- **Defect** D11.12 — found: auditor · cause: spec · made: Day 11 · C11.10's read times had no origin, and the driver takes about 1.7 s on this PC to start a session (fixed in this PR: counted from the `init` line in the events file, reads retried).
- **Defect** D11.13 — found: auditor · cause: spec · made: Day 11 · C11.18's "two or more `issue comment` calls" counted the run's closing comment, so one try met it (fixed in this PR).
- **Defect** D11.14 — found: auditor · cause: spec · made: Day 11 · nothing said what the heartbeat and `running:` give for a session with no `start` line, which Day 6's `WaitTest` resumes at `--poll 0.01` (fixed in this PR).
- **Defect** D11.15 — found: auditor · cause: spec · made: Day 11 · C11.6 expected `{"no": "type"}` to be `unparsed`, which In scope's kind rules did not say (fixed in this PR).
- **Defect** D11.16 — found: auditor · cause: spec · made: Day 11 · C11.17's resumed case wrote `<uuid>.comment.json` "before the run", which a subprocess test cannot, the uuid being made by the driver (fixed in this PR: the fake's `do` writes it).
- **Defect** D11.17 — found: auditor · cause: spec · made: Day 11 · In scope cited C07.17 and C07.18, both already replaced (by C08.10 and C10.24/C10.25, and C08.2) (fixed in this PR).
- **Defect** D11.18 — found: auditor · cause: spec · made: Day 11 · C11.18's `Plan:` line quoted N34's "a stale session is reported, not killed", which C11.17 checks, not a failed comment (fixed in this PR: `Plan: none`).
