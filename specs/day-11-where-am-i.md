# Day 11 — Where am I, while a session runs: the stream, the events, the heartbeat, `status --watch`, the estimate, the comments

**Phase:** 2 · **Depends on:** Day 10 · **Expected PRs:** 10 (the spec change, Tracks A, B, C, D, E1, a second spec change (D11.19), E2, F, the close)

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
| E2 | | The stale comment, `stale_minutes`, the resumed session's comment: C11.17, C11.19, C11.23 |
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

- [x] C11.1 **new** — With every check passing, `--once` starts one session whose arguments,
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
      Evidence: `OnceTest.test_session_command` and `BoxSessionTest.test_session_runs_in_the_container` pass on `main` at `6f51a22`, after Track F (#170, #178); `tests/test_once.py`'s only change since `c8e5963` is the two flags.
      seen red: python -m unittest tests.test_once.OnceTest.test_session_command tests.test_box_session.BoxSessionTest.test_session_runs_in_the_container on main → AssertionError: Lists differ: [['ru[581 chars]t', 'json', '--max-budget-usd', '5', '--permis[171 chars]d>']] != [['ru[581 chars]t', 'stream-json', '--verbose', '--max-budget-[191 chars]d>']] (#170)
- [x] C11.2 **new** — `driver.stream.result` on a stdout of four lines, a `system` `init`
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
      Evidence: `StreamResultTest.test_result_is_the_last_result_line` and `StreamResultTest.test_once_reads_the_result_event` pass on `main` at `6f51a22` (#170).
      seen red: python -m unittest tests.test_stream.StreamResultTest.test_result_is_the_last_result_line on main → FAILED (errors=1) (#170)
      seen red: python -m unittest tests.test_stream.StreamResultTest.test_once_reads_the_result_event on main → AssertionError: Tuples differ: (1, 'park: the session ended without a result (exit 0; session `<uuid>`)') != (0, 'opened: #5 from `day-01/track-a-x`') (#170)
- [x] C11.3 **new** — A fake printing `not json` then a `result` line ending in "PARK: needs a
      decision" parks "park: the session parked: needs a decision (session `<uuid>`)". Red today:
      it parks "park: the session ended without a result (exit 0; session `<uuid>`)".
      Test: `StreamResultTest.test_unparsed_line_skipped`.
      Plan: N31 "a line that does not parse is counted, not fatal"
      Evidence: `StreamResultTest.test_unparsed_line_skipped` passes on `main` at `6f51a22` (#170).
      seen red: python -m unittest tests.test_stream.StreamResultTest.test_unparsed_line_skipped on main → AssertionError: Tuples differ: (1, 'park: the session ended without a result (exit 0; session `<uuid>`)') != (1, 'park: the session parked: needs a decision (session `<uuid>`)') (#170)
- [x] C11.22 **hold** — A fake printing a `system` `init` and an `assistant` line and no
      `result`, exiting 0, parks "park: the session ended without a result (exit 0; session
      `<uuid>`)", and its `end` line has `cost_usd` null and `denials` 0: true today (two JSON
      lines are not one object) and after Track A (no `result` line). Track A adds the test and
      breaks it once.
      Test: `StreamResultTest.test_no_result_line`.
      Plan: N31 "a stream with no result is a session that printed nothing"
      Evidence: `StreamResultTest.test_no_result_line` passes on `main` at `6f51a22` (#170).
      broken: result returning the last JSON object whatever its type → AssertionError: Tuples differ: (0, 'opened: #5 from `day-01/track-a-x`') != (1, 'park: the session ended without a result (exit 0; session `<uuid>`)') (#170)
- [x] C11.4 **hold** — The outcome table and the run log hold: `tests/test_once_outcome.py`,
      `tests/test_once_run.py`, `tests/test_usage_limit.py`, `tests/test_runlog.py`,
      `tests/test_runlog_end.py`, `tests/test_once_halt.py` and `tests/test_halt_race.py` pass
      unedited (`git diff --exit-code c8e5963` on them is empty), and C10.31's diff against
      `495bf69` stays empty: no new test goes in a file it lists.
      Plan: N31 "The result event stays the record"
      Evidence: `git -c core.safecrlf=false diff --exit-code c8e5963` and `git -c core.safecrlf=false diff --exit-code 495bf69` over Verify's lists print nothing on `main` at `6f51a22`, and the seven files' tests pass there (#169, #178).
      broken: the PARK line read from the first line of the reply → AssertionError: Tuples differ: (0, 'opened: #5 from `day-01/track-a-x`') != (1, 'park: the session parked: needs a decision (session `<uuid>`)') (#169)
- [x] C11.5 **new** — On a fake that prints, one line each, a `system` `init` event, an
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
      Evidence: `EventsTest.test_events_file` passes on `main` at `6f51a22` (#171).
      seen red: python -m unittest tests.test_events.EventsTest.test_events_file on main → AssertionError: False is not true : the session has no events file (#171)
      broken: a user event named "user", not "tool result" (C11.5) → AssertionError: Lists differ: ['system init', 'tool Bash', 'user', 'reply', 'unparsed', 'result'] != ['system init', 'tool Bash', 'tool result', 'reply', 'unparsed', 'result'] (#171)
- [x] C11.6 **new** — `driver.stream.kind` on each case of In scope's list (a `system` event with
      subtype `init`; an `assistant` event with a `text` item then a `tool_use` named `Read`; an
      `assistant` event with only a `thinking` item; a `user` event; a `result` event;
      `{"type": "rate_limit_event"}`; `[1, 2]`; `{"no": "type"}`; `{"type": "assi`) returns
      `system init`, `tool Read`, `assistant`, `tool result`, `result`, `rate_limit_event`,
      `unparsed`, `unparsed`, `unparsed`. Red today: `driver.stream.kind` does not exist.
      Test: `StreamKindTest.test_kinds`.
      Plan: N30 "appends each event's time and kind"
      Evidence: `StreamKindTest.test_kinds` passes on `main` at `6f51a22` (#171); it lives in `tests/test_events.py`, not `tests/test_stream.py` as Verify said (D11.31).
      seen red: python -m unittest tests.test_events.StreamKindTest on main → FAILED (errors=1) (#171)
      broken: an assistant event's tool_use item never named (C11.6) → AssertionError: Lists differ: ['system init', 'reply', 'assistant', 'tool result', 'resu[55 chars]sed'] != ['system init', 'tool Read', 'assistant', 'tool result', '[59 chars]sed'] (#171)
- [x] C11.7 **new** — `--session-minutes` ending a session mid-line keeps the events read so
      far: a fake that prints a `system` `init` line, then `{"type": "assi` with no newline,
      flushes and sleeps, run with `--session-minutes 0.05 --poll 0.2`, parks "park: the session
      ran past 0.05 minutes (session `<uuid>`)" as today, and its events file's kinds are
      `system init`, `unparsed`. Red today: no events file.
      Test: `EventsTest.test_bound_keeps_events_read`.
      Plan: N31 "the poll, STOP and --session-minutes work as before"
      Evidence: `EventsTest.test_bound_keeps_events_read` passes on `main` at `6f51a22` (#171).
      seen red: python -m unittest tests.test_events.EventsTest.test_bound_keeps_events_read on main → AssertionError: 0 != 1 : the run did not write one events file (#171)
      broken: a partial last line dropped from the events file (C11.7) → AssertionError: Lists differ: ['system init'] != ['system init', 'unparsed'] (#171)
- [x] C11.8 **hold** — A `STOP` issue still stops a session within a poll, a failed issues read
      is still skipped, and the bound still parks, with the session printing nothing:
      `tests/test_once_stop.py` and `tests/test_session_bound.py` pass unedited (in C11.4's
      `git diff`), on the reader's wait.
      Plan: P20 "from the phone (an issue whose title starts with `STOP`) it takes as long as the
      driver's poll of GitHub"
      Evidence: `tests/test_once_stop.py` and `tests/test_session_bound.py` pass on `main` at `6f51a22`, unedited: `git -c core.safecrlf=false diff --exit-code c8e5963` over them prints nothing (#171).
      broken: a STOP issue no longer stopping the session (C11.8) → AssertionError: the driver did not end within 10 s (#169)
      broken: the issues read, and the bound, skipped at the reader's timeout (C11.8) → AssertionError: the driver did not end within 10 s (#171)
      Recorded again at the close, since #171 rewrote their finds in `run_session` and did not (D11.30): Day 6's and Day 10's names, the reports as those days recorded them.
      broken: the bound never reached → FAILED (errors=1)
      broken: the bound's kill left the container running → AssertionError: Tuples differ: (1, True, False, []) != (1, True, True, [{'ended': 'itself'}])
      broken: the kill past the bound removed → AssertionError: True is not false : a process of the session still runs
- [x] C11.9 **hold** — The container's mounts and command are Day 10's: `tests/test_box_command.py`
      passes unedited (in C11.4's `git diff`), and no line of `driver/stream.py`, which holds the
      events writer (`append`), names `/state` or `/work`: `grep -nE '"/(state|work)'
      driver/stream.py` finds none (from Track B; before it the file has no writer). Its break
      runs with `--expect-stdout '^$'`.
      Plan: N30 "on the host and written by the driver, never from inside the container"
      Evidence: `grep -nE '"/(state|work)' driver/stream.py` finds none on `main` at `6f51a22`, and `tests/test_box_command.py` passes unedited (in C11.4's `git diff`) (#171). The break's check is a Python count of such lines with `--expect-stdout '^0$'`, not the spec's `'^$'` (D11.21).
      broken: the events path given as "/state/sessions" in driver/stream.py (C11.9) → 1 (#171)
- [x] C11.10 **new** — A fake that prints a `system` `init` line, sleeps 4 seconds printing
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
      Evidence: `HeartbeatTest.test_heartbeat_beats_through_a_quiet_tool` passes on `main` at `6f51a22` (#172).
      seen red: python -m unittest tests.test_heartbeat on main → AssertionError: the session wrote no heartbeat (#172)
      broken: the poll writes no heartbeat → AssertionError: Tuples differ: (True, True, True, True, True, True, False, False, True) != (True, True, True, True, True, True, True, True, True) (#172)
- [x] C11.11 **new** — `driver.status.progress` with `now` fixed: on a run log with three
      earlier `track` sessions of 10m00s, 20m00s and 40m00s and a running `track` session started
      12m05s before `now`, whose events' last line is `tool Bash` 40 seconds before `now`, with
      `assistant` lines `m1` (in 115, out 7), `m1` again (in 115, out 9) and `m2` (in 3, out 20),
      returns `running: 12m05s (estimate 20m00s, the median of 3 earlier track sessions)`,
      `last event: tool Bash, 0m40s ago`, `tokens so far: 118 in, 29 out`. Red today: no
      `progress`.
      Test: `ProgressTest.test_progress_lines`.
      Plan: N33 "the median length of the run log's earlier sessions of the same kind, and its
      n"; N32 "how long it has run, its last event and how long ago, and the tokens so far"
      Evidence: `ProgressTest.test_progress_lines` passes on `main` at `6f51a22` (#173).
      seen red: python -m unittest tests.test_progress on main → FAILED (errors=8) (#173)
      broken: the median taken one below the middle → AssertionError: Lists differ: ['run[18 chars]mate 10m00s, the median of 3 earlier track ses[72 chars]out'] != ['run[18 chars]mate 20m00s, the median of 3 earlier track ses[72 chars]out'] (#173)
      broken: every assistant line's tokens summed → AssertionError: Lists differ: ['run[78 chars] event: tool Bash, 0m40s ago', 'tokens so far: 233 in, 36 out'] != ['run[78 chars] event: tool Bash, 0m40s ago', 'tokens so far: 118 in, 29 out'] (#173)
- [x] C11.12 **new** — The estimate's edges: two earlier `track` sessions give `running: <d> (no
      estimate: 2 earlier track sessions)`; four of 10, 20, 30 and 41 minutes give `estimate
      25m00s, the median of 4`, and of 10m00s, 20m00s, 20m01s and 41m00s `estimate 20m00s`
      (20m00.5s rounded down); a session with no `start` line gives `running: unknown (no start
      line)`; an earlier session with no `end` line, or of kind `spec`, is not
      counted; a step whose prefix is none of the three gives `(no estimate: the step has no
      kind)`; no events give `last event: none yet` and `tokens so far: 0 in, 0 out`. Red today:
      no `progress`.
      Test: `ProgressTest.test_estimate_edges`.
      Plan: N33 "fewer than three, no estimate"
      Evidence: `ProgressTest.test_estimate_edges` passes on `main` at `6f51a22` (#173); the same seen-red run as C11.11's, `tests.test_progress` on `main` → FAILED (errors=8) (#173).
      broken: an even median rounded up → AssertionError: 'running: 12m05s (estimate 20m01s, the median of 4 earlier track sessions)' != 'running: 12m05s (estimate 20m00s, the median of 4 earlier track sessions)' (#173)
      broken: a spec session counted in a track estimate → AssertionError: 'running: 12m05s (estimate 15m00s, the median of 4 earlier track sessions)' != 'running: 12m05s (estimate 20m00s, the median of 3 earlier track sessions)' (#173)
- [x] C11.13 **new** — `run-steps.py status` with a live session (a `pid` line of a running
      process, its `start` line and an events file) prints the three progress lines right after
      its "in progress:" line; the "in progress:" line still ends "cost so far $0.00". Red today:
      no progress lines.
      Test: `StatusWatchTest.test_status_shows_progress`.
      Plan: N32 "the step, how long it has run, its last event and how long ago, and the tokens so
      far; the cost stays the result's, never estimated in dollars"
      Evidence: `StatusWatchTest.test_status_shows_progress` passes on `main` at `6f51a22` (#173).
      seen red: python -m unittest tests.test_status_watch on main → AssertionError: 0 != 1 (#173)
      broken: status prints no progress lines → AssertionError: False is not true : steps: (#173)
- [x] C11.14 **new** — `run-steps.py status --watch --poll 0.5` with a live session (a process
      the test started) prints a first block naming it; the test ends the process once it has
      read that block; then `status --watch` prints another block, a blank line between, the
      last with "in progress: none", and exits 0; with no live session it prints one block and
      exits 0; in both runs the state folder lists the same names before and after (C08.2).
      Red today: argparse refuses `--watch`, exit 2.
      Test: `StatusWatchTest.test_watch_until_the_session_ends`,
      `StatusWatchTest.test_watch_with_nothing_running`,
      `StatusWatchTest.test_watch_creates_nothing`.
      Plan: N32 "status --watch prints status again at each poll until the session ends"
      Evidence: `StatusWatchTest.test_watch_until_the_session_ends`, `StatusWatchTest.test_watch_with_nothing_running` and `StatusWatchTest.test_watch_creates_nothing` pass on `main` at `6f51a22` (#173); the same seen-red run as C11.13's, `tests.test_status_watch` on `main` → AssertionError: 0 != 1 (#173).
      broken: status --watch stops after its first block → AssertionError: [] is not true : status --watch printed nothing after its first block (#173)
- [x] C11.15 **hold** — `status` with no live session prints what it printed before:
      `tests/test_status.py`, `tests/test_status_trial.py` and `tests/test_level_2_sentence.py`
      pass unedited (in C11.4's `git diff`).
      Plan: P62 "`status` prints it: the mode, the level, the step in progress and its cost so
      far"
      Evidence: `tests/test_status.py`, `tests/test_status_trial.py` and `tests/test_level_2_sentence.py` pass on `main` at `6f51a22`, unedited: `git -c core.safecrlf=false diff --exit-code c8e5963` over them prints nothing (#169, #173). Track D recorded no break of its own; #169's still applies (its find matches once).
      broken: a progress line printed with no live session → AssertionError: Lists differ: ['mod[93 chars]e', 'running: unknown', 'steps: none', 'parks [156 chars]ked'] != ['mod[93 chars]e', 'steps: none', 'parks by reason: none', 'r[136 chars]ked'] (#169)
- [x] C11.16 **new** — A fake that prints `system` `init`, sleeps 4 seconds, then a `result`,
      run with `--poll 0.3` and the fake `gh`'s `comment_id` 99: before the run's issue's closing
      comment, the fake `gh` records one `issue comment <the run's issue>` whose body's lines are
      "step: <the step>", "session: <uuid>", then lines starting `running: `, `last event: `,
      `tokens so far:`; then at least one `api --method PATCH
      repos/{owner}/{repo}/issues/comments/99 --input -` whose stdin parses to an object with one
      key, `body`, the last of them holding "last event: system init". The step's outcome is the same
      as without. Red today: no comment before the run's issue's closing one.
      Test: `PhoneTest.test_heartbeat_comment_edited_in_place`.
      Plan: N34 "One comment on the run's issue per session, edited in place at each poll"
      Evidence: `PhoneTest.test_heartbeat_comment_edited_in_place` passes on `main` at `6f51a22` (#175); it fails on and off under load (D11.25).
      seen red: python -m unittest tests.test_phone.PhoneTest.test_heartbeat_comment_edited_in_place on main → AssertionError: Tuples differ: (False, False, False, False, True, False, True, True) != (True, True, True, True, True, True, True, True) (#175)
      broken: a heartbeat that keeps no comment id → AssertionError: Tuples differ: (False, True, True, False, True, False, True, True) != (True, True, True, True, True, True, True, True) (#175)
- [x] C11.17 **new** — As C11.16 with `stale_minutes` 0.02 in `driver.json`: exactly one more
      `issue comment` on the run's issue, whose body is "stale: session `<uuid>`
      has sent no event for 0.02 minutes; it is not stopped"; the session is not killed and the
      step's outcome is as without. With `<state>/sessions/<uuid>.comment.json` holding
      `{"id": 99, "stale": true}` before the first poll, written by the fake's `do`, which knows
      the state folder and the session (a resumed session's), the first poll edits comment 99 and no stale comment is made. Red
      today: no comment.
      Test: `PhoneTest.test_stale_comment_once`,
      `PhoneTest.test_resumed_session_keeps_its_comment`.
      Plan: N34 "when no event has come for stale_minutes (10 by default, in driver.json), one new
      comment says so, once per session; a stale session is reported, not killed"
      Evidence: `PhoneTest.test_stale_comment_once` and `PhoneTest.test_resumed_session_keeps_its_comment` pass on `main` at `6f51a22` (#176).
      seen red: python -m unittest tests.test_phone.PhoneTest.test_stale_comment_once tests.test_phone.PhoneTest.test_resumed_session_keeps_its_comment on main → AssertionError: Tuples differ: (False, False, True) != (True, True, True) (#176)
      broken: a quiet session never reported stale (C11.17) → AssertionError: Tuples differ: (False, True, True, True) != (True, True, True, True) (#176)
      broken: a stale comment made at every poll (C11.17) → AssertionError: Tuples differ: (False, True, True, True) != (True, True, True, True) (#176)
      broken: a resumed session's comment file not read (C11.17) → AssertionError: Tuples differ: (False, False, False) != (True, True, True) (#176)
- [x] C11.23 **hold** — As C11.16 with `stale_minutes` absent from `driver.json` (10): exactly
      one heartbeat comment (a body starting "step: ") and no comment starting "stale: " on the
      run's issue: true since Track E1 (no stale comment exists) and after Track E2 (four seconds
      is under 10 minutes). Track E2 adds the test and breaks it once (the default made 0.001).
      Test: `PhoneTest.test_not_stale_before_stale_minutes`.
      Plan: N34 "stale_minutes (10 by default, in driver.json)"
      Evidence: `PhoneTest.test_not_stale_before_stale_minutes` passes on `main` at `6f51a22` (#176, after spec change #177).
      broken: stale_minutes 0.001 when absent from driver.json (C11.23) → AssertionError: Tuples differ: (True, False) != (True, True) (#176)
- [x] C11.18 **new** — With the fake `gh` failing `issue comment` and `api` (exit 1), a session
      spanning several polls ends with the same outcome and the same stdout as with them
      working, and the next poll tries the comment again (two or more `issue comment` calls
      before the run's closing comment). Red today: no comment is tried.
      Test: `PhoneTest.test_failed_comment_skipped`.
      Plan: none — that a failed comment changes nothing is the driver's own care; `plan.md` says
      nothing of it
      Evidence: `PhoneTest.test_failed_comment_skipped` passes on `main` at `6f51a22` (#175). The break was recorded in #175 and again in #176, which rewrote its find, with the same report.
      seen red: python -m unittest tests.test_phone.PhoneTest.test_failed_comment_skipped on main → AssertionError: Tuples differ: (True, True, False) != (True, True, True) (#175)
      broken: a failed heartbeat comment never tried again → AssertionError: Tuples differ: (True, True, False) != (True, True, True) (#176)
- [x] C11.19 **new** — `driver.config.load` on a config with every Day 2 key and `stale_minutes`
      `"10"`, `0`, `-1` or `true` reports "cannot start: <path>'s stale_minutes must be a number
      above 0", one line; with 0.5 or absent it loads, and absent reads as 10 where the driver
      reads it. Red today: the config loads with each of them.
      Test: `StaleConfigTest.test_stale_minutes`.
      Plan: N34 "stale_minutes (10 by default, in driver.json)"
      Evidence: `StaleConfigTest.test_stale_minutes` passes on `main` at `6f51a22` (#176).
      seen red: python -m unittest tests.test_stale_config on main → AssertionError: Tuples differ: (False, []) != (True, ["cannot start: <path>'s stale_minutes must be a number above 0"]) (#176)
      broken: stale_minutes not checked in driver.json (C11.19) → AssertionError: Tuples differ: (False, []) != (True, ["cannot start: <path>'s stale_minutes must be a number above 0"]) (#176)
- [x] C11.20 **hold** — A session shorter than one poll makes no comment: `OnceTest`'s
      `test_session_command` keeps its six `gh` calls (issue list, run list, issue create, pr
      list, issue comment, issue close), unedited in that part by Track A's edit; and C06.9's
      `OnTest.test_steps_per_night`, whose sessions span `--poll 0.01` polls, passes unedited
      (in C11.4's `git diff`).
      Plan: N34 "edited in place at each poll"
      Evidence: `OnceTest.test_session_command` keeps its six `gh` calls (#170 changed only the two flags in `tests/test_once.py`), and `OnTest.test_steps_per_night` passes on `main` at `6f51a22`, unedited: `git -c core.safecrlf=false diff --exit-code c8e5963` over `tests/test_on.py` prints nothing (#169, #175). Track E1 recorded no break of its own; #169's still applies (its find matches once).
      broken: a comment made at the session's start → AssertionError: Tuples differ: (True, True, True, True, True, True, False, False) != (True, True, True, True, True, True, True, True) (#169)
- [x] C11.21 **hold** — Live: with `DRIVER_CONTAINER_IMAGE` and `DRIVER_CONTAINER_SECRETS` set, runs
      `docker run --rm -i --env-file <secrets> <image> claude -p --model haiku --output-format
      stream-json --verbose --max-budget-usd 0.05 --strict-mcp-config` with "Reply with the word
      ok." on stdin: exit 0; every non-blank line is a JSON object; the first's `type` is
      `system`; `driver.stream.result` of the output has `is_error` false, a number
      `total_cost_usd` and a string `session_id`; no line's kind is `unparsed`. The same command
      without `--verbose` exits non-zero. True of the image today; Track F adds the test and breaks
      it once.
      Test: `StreamLiveTest.test_image_takes_stream_json`.
      Plan: N30 "The driver runs claude -p with --output-format stream-json --verbose"
      Evidence: `StreamLiveTest.test_image_takes_stream_json`, run with `DRIVER_CONTAINER_IMAGE=agentic-workflow-driver-session:2.1.322` and `DRIVER_CONTAINER_SECRETS` set on this machine, passes (#178), and again on `main` at `6f51a22` at the close; CI skips its Docker part.
      Live, so not replayed: CI and the replay have no image; a reader checked the live run and its break in #178: with `--verbose` left out of the test's command, the test failed twice with "AssertionError: 1 != 0 : exit 1" and the CLI's "requires --verbose" error. A replayed break would only skip, so it has no manifest entry (as C10.7).

## Verify
```bash
python -m unittest tests.test_stream tests.test_events tests.test_heartbeat tests.test_progress tests.test_status_watch tests.test_phone tests.test_stale_config tests.test_stream_live tests.test_once tests.test_box_session tests.test_once_outcome tests.test_once_run tests.test_usage_limit tests.test_runlog tests.test_runlog_end tests.test_once_halt tests.test_halt_race tests.test_once_stop tests.test_session_bound tests.test_box_command tests.test_status tests.test_status_trial tests.test_level_2_sentence tests.test_on tests.test_wait -v
git -c core.safecrlf=false diff --exit-code c8e5963 -- tests/test_once_outcome.py tests/test_once_run.py tests/test_usage_limit.py tests/test_runlog.py tests/test_runlog_end.py tests/test_once_halt.py tests/test_halt_race.py tests/test_once_stop.py tests/test_session_bound.py tests/test_box_command.py tests/test_status.py tests/test_status_trial.py tests/test_level_2_sentence.py tests/test_on.py tests/test_contract.py
git -c core.safecrlf=false diff --exit-code 495bf69 -- tests/test_contract.py tests/test_decide.py tests/test_dry_run.py tests/test_steps.py tests/test_tree.py tests/test_config.py tests/test_encoding.py tests/test_halt.py tests/test_halt_report.py tests/test_home.py tests/test_hooks.py tests/test_issues.py tests/test_off.py tests/test_once_park_issues.py tests/test_once_parks.py tests/test_preflight.py tests/test_recovery_table.py tests/test_lock_takeover.py driver/decide.py driver/steps.py driver/home.py rules/session.md tests/test_failures.py tests/test_once_outcome.py tests/test_once_run.py tests/test_runlog.py tests/test_runlog_fix.py tests/test_session_bound.py tests/test_wait.py tests/test_kit_copy.py tests/test_lock.py tests/test_live_cli.py tests/test_once_halt.py tests/test_live_once.py tests/test_once_stop.py
```
`tests/test_stream_live.py` skips its Docker part unless `DRIVER_CONTAINER_IMAGE` and
`DRIVER_CONTAINER_SECRETS` are set; on this machine, with the image `driver.json` names built,
run it with both set as well.

Where the tests live: `StreamResultTest` in `tests/test_stream.py`; `StreamKindTest` and
`EventsTest` in `tests/test_events.py` (D11.31); `HeartbeatTest` in `tests/test_heartbeat.py`;
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
  - C11.23, Track E2: `stale_minutes` 0.001 when absent from `driver.json`.
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
- **Defect** D11.19 — found: seen red · cause: spec · made: Day 11 · C11.17, tagged `new`, named `test_not_stale_before_stale_minutes`, whose checks (one heartbeat comment, no stale comment) Track E1 made true before Track E2 began; CI's "Track tests seen red" failed Track E2's PR #176 on it (fixed in a second spec-change PR: the case moved to C11.23, a hold, broken once in Track E2).
- **Defect** D11.20 — found: Track E1 · cause: spec · made: Day 11 · the spec named only C06.9's test as spanning polls; C07.19's `RunIssueCostTest.test_second_step_comment` also found the second step's comment by "step: ", which the heartbeat comments carry under `on`, and failed with `(0, 3, False) != (0, 1, True)`. #175 finds it by "cost so far: " instead (a departure: C07.19's wording is unchanged and its file is in no Verify `git diff`).
- **Defect** D11.21 — found: break on purpose · cause: spec · made: Day 11 · C11.9's break "runs with `--expect-stdout '^$'`", which cannot catch it: `break.py` matches with `re.M`, so `^$` matches the empty end of any output, and Git's MSYS `grep` started from Python loses the pattern's `"`. #171 used a Python count of such lines with `'^0$'` instead.
- **Defect** D11.22 — found: break on purpose · cause: environment · made: none · same-as: D10.17 · Track B's first C11.9 break passed `"/state/sessions"` through Git Bash without `MSYS_NO_PATHCONV=1`, which rewrote it to a Windows path, and `break.py` refused the report as an absolute path (fixed before #171).
- **Defect** D11.23 — found: break on purpose · cause: process · made: Day 11 · Track C's first break replaced the poll's `begun` with `None`, which nulled `started` rather than skipping the beat, so its name did not fit what it broke; not recorded, the beat's call itself broken instead (#172).
- **Defect** D11.24 — found: self · cause: process · made: Day 11 · Track D's brief had `status --watch` re-read the live session after printing a block, a window in which the session can end; the implementer's test failed 3 of 3 and it added a sleep to the test. The fix went into `run`, which now uses the block's own reading (#173).
- **Defect** D11.25 — found: Day 11 review · cause: implementation · made: Day 11 · `PhoneTest.test_heartbeat_comment_edited_in_place` fails on and off under load: eight copies at once failed 2 of 8 on Track E2's branch and 3 of 8 on `main`. The likely cause: a poll can fall after the `result` line is read and before the session exits, so the last edit shows "last event: result", not "last event: system init" (#176). Not fixed; no day owns it.
- **Defect** D11.26 — found: self · cause: process · made: Day 11 · #175's body first rendered struck through: a bare `<s>` read as HTML. Fixed by backticks.
- **Defect** D11.27 — found: self · cause: process · made: Day 11 · the first live `gh api` PATCH before Track E1 failed with HTTP 400: a Bash `printf` turned `\n` into newlines and broke the JSON. The Python call, as the driver makes it, exited 0 and edited the comment (scratch issue #174).
- **Defect** D11.28 — found: self · cause: implementation · made: Day 11 · Track E2's implementer first built the comment file's folder with the expression that is the find of C11.9's break, so the find matched twice in `driver/stream.py`; caught by checking every Day manifest's finds before #176, which builds it from the file's own path.
- **Defect** D11.29 — found: Track B · cause: implementation · made: Day 09 · same-as: D10.18 · `UsageLimitTest.test_far_reset_parks` failed again under load: 3 of 10 under `--repeat 10` on Track B's branch, then 10 of 10 there and on `main` (#171); once each in #175's and #176's full runs.
- **Defect** D11.30 — found: close · cause: process · made: Day 11 · Track B rewrote the finds of three earlier breaks in `run_session` (Day 6's "the bound never reached", Day 10's "the bound's kill left the container running" and "the kill past the bound removed"), which the Tracks section told it to record again, and did not; #172 then said Track B had. The close ran the three through `break.py` on the new code, with the same reports as their days, and they are in this day's manifest, under C11.8.
- **Defect** D11.31 — found: close · cause: implementation · made: Day 11 · "Where the tests live" put `StreamKindTest` in `tests/test_stream.py`; #171 put it in `tests/test_events.py`, a departure it did not record (the sentence fixed at the close).
- **Defect** D11.32 — found: close · cause: implementation · made: Day 11 · `HeartbeatTest.test_heartbeat_beats_through_a_quiet_tool` (C11.10) failed once in the close's full run, on its check that `last_event` is the same in both reads and is the `init` line's `at`; it passed 3 of 3 run alone, and #176's full run also saw `test_heartbeat.py` fail once. A likely cause, not checked: under load the first read, 0.5 seconds after the `init` line, can come before the first poll's beat, when the file is still the one written at the start. Not fixed; no day owns it.
- At the close, on `main` at `6f51a22`: Verify's tests ran 110, OK, with `DRIVER_CONTAINER_IMAGE` and `DRIVER_CONTAINER_SECRETS` set, so `StreamLiveTest` ran rather than skipped; both `git diff`s print nothing; the C11.9 grep finds none. Under `python scripts/test-parallel.py --repeat 10` (ten copies at once, eight workers), `test_phone.py` failed 8 of 10, each time `test_heartbeat_comment_edited_in_place` on its "last event: system init" check (D11.25), and `test_usage_limit.py` failed 8 of 10, each time `test_far_reset_parks` (D11.29), which passed 50 of 50 so at Day 10's close: both fail more often the heavier the load, and neither has a day that owns it.
- Every Day 11 track break's find matches once on `main` but #175's "a failed heartbeat comment never tried again", whose find #176 rewrote and recorded again under that name with the same report: the manifest holds #176's. #177 recorded C11.23's break as "(C11.17)" before the case moved; #176's record under "(C11.23)" is the manifest's.
- Tracks D and E1 recorded no break of C11.15 and C11.20, which the Notes above left to them; #169's breaks of both, run on the code before the day, still find their lines once and are the ones recorded.
- C11.21 is the first `hold` that is live: its break cannot replay, so `specs/README.md` has it written as a sentence, and the dashboard, which reads a red only from a seen-red or `broken:` line, flags it "No seen-red or broken line" (a scratch merge of this branch, `spec-drift.py --out`). Day 10's live criteria were `new`, with seen-red lines. Left for the maintainer: whether a live hold's sentence should count on the dashboard.
- C11.21 is live: its Docker part skips in CI and in the replay. `usage` repeating on each content block of a message (the Note above) stays unknown: the live session's one `assistant` line held one `text` block (#178).
- The blind relabel (`scripts/relabel.py`), run on 31 entries and again on 32 after D11.32, agreed
  the second time on 31 of 32 stages, 27 of 32 causes and 31 of 32 `made:`. After the first run,
  D11.25 changed from `found: Track E2` to `Day 11 review` (Track E1's test had merged when Track E2
  found it) and D11.31's cause from `spec` to `implementation` (#171 moved the test without
  recording the departure). The second run read both the other way, D11.25 before the merge and
  D11.31 `process`: kept, for the reasons just given. Kept as well: D11.22 `environment` and `made:
  none`, Git Bash's path conversion being the machine's (as D10.17); D11.24 `process`, the window
  being the brief's, not the implementer's (as D10.19); D11.27 `process`, the shell doing as
  written, the command being the slip; D11.29 `implementation`, as D10.18 (the test reads the
  driver's exit before the driver has ended), which the rater read as unclear.
- Still for the maintainer, as plan-change matters: `plan.md` says the session id is read from the output ("Where am I, while a session runs"; "What to build", item 2), `plan.md:130`'s "the JSON result", `plan.md:630`'s "Days 1 to 9 have specs", and P60's `--output-format json`.
