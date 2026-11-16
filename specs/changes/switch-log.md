# The driver records its switches

## What changes
The driver writes each switch a person pulls, or a STOP from the phone sets, to a file of its own,
`<state>/switches.jsonl`: one JSON object per line, fsynced as the run log's are. `on` writes
`{"event": "on", "at": …}` once its run has passed its checks; the loop writes
`{"event": "off", "at": …, "issue": <n>}` when it ends because the run's issue was closed; every halt
writes `{"event": "halt", "at": …, "why": …}`, with `"session": <uuid>` when it killed a session
(a STOP during a session, or `run-steps.py halt` while one lives); `clear` writes
`{"event": "clear", "at": …}` when it removes a halt. `scripts/driver-runs.py` reads the file: a
session a halt names is not counted as crashed, and its document carries the lines as `switches`.

Before: none of these was written anywhere. A session a STOP killed has no `end` line, so the
count, and the page's lane "Can it run without a person?", showed it as a crash (bearing's
session `8bef3bb2`, 10 Nov 23:47Z, the trial's own STOP #92).

The run log (`<state>/run.jsonl`) does not change: after a halt it still holds `start`, `pid` and
no `end`, so the next run still parks on that session for a person (C04.12, C05.11). The driver
never reads `switches.jsonl` to decide anything; it is a record for the count.

## Why
#211 N7 asked for the cause of 11 Nov's crash: it was the trial's phone STOP, not a fault. #212 S11:
Day 14's record must name every merge, park and refusal (N25), and the run log has no on, off or
halt events. Writing them into `run.jsonl` would break two held criteria, C04.12 and C05.11, whose
frozen tests require the log after a halt to be exactly `start`, `pid`; the maintainer chose a file
of its own over a `Replaces:` in Day 13.

## Acceptance criteria
Tick each box in this PR once its evidence is in the PR body; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [ ] S-switch-log.1 **new** — A STOP during a session (`OnceStopTest`'s set-up: STOP issue #9 added
      once the fake session's pids are written) leaves `<state>/switches.jsonl` with exactly one
      line: event "halt", why "STOP issue #9", session the run log's `start` line's session, and an
      `at` stamp. The run log still holds `start`, `pid` only.
      Test: `SwitchLogTest.test_stop_during_session_names_the_session`.
      Red today: `switches.jsonl` is not written, a FileNotFoundError.
      Plan: N25 "every merge the driver made, every park and every refusal"
- [ ] S-switch-log.2 **new** — `run-steps.py halt --state <dir>` with no driver running writes one
      halt line, why "run-steps.py halt" and no `session` key; `clear` then writes one clear line;
      a second `clear`, with no halt set, writes nothing.
      Test: `SwitchLogTest.test_halt_and_clear_commands`.
      Red today: `switches.jsonl` is not written, a FileNotFoundError.
      Plan: P58 "has the switches `on`, `off`, `status`, `halt`, `clear`"
- [ ] S-switch-log.3 **new** — `on`, whose run's issue #1 is closed after the first merge
      (`OnTest.test_off_between_steps`'s set-up), leaves the events "on", then "off" with issue 1,
      in that order and nothing else.
      Test: `SwitchLogOnTest.test_on_then_off`.
      Red today: `switches.jsonl` is not written, a FileNotFoundError.
      Plan: P58 "has the switches `on`, `off`, `status`, `halt`, `clear`"
- [ ] S-switch-log.4 **new** — `scripts/driver-runs.py` on a run log whose session has no `end`
      line and no live process, beside a switch log whose halt names that session, counts it
      `crashed: false` and the step's `crashes` 0; the same run log with no switch log still counts
      it crashed; the document written with `--out` carries the switch log's lines as `switches`
      (an empty list when there is no file).
      Test: `SwitchCountTest.test_a_halted_session_did_not_crash`,
      `SwitchCountTest.test_the_document_carries_the_switches`.
      Red today: `count` takes no fourth argument, a TypeError, and the document has no
      `switches`, "None != [...]".
      Plan: N25 "every merge the driver made, every park and every refusal"

## Verify
```bash
python -m unittest tests.test_switch_log tests.test_switch_count
```

## Notes
- The page does not draw the switches yet: drawing `on`, `off`, `halt` and `clear` on the lane
  "Can it run without a person?" is a `dashboard/` PR, left in #213. Until it lands, the page only
  stops calling a halted session a crash.
- `off` is written by the loop when it sees the run's issue closed, not by `run-steps.py off`: the
  issue can be closed from the phone too, and `tests/test_off.py` runs `off` with no `--state`, so a
  write there would land in this machine's own state folder.
- **Defect** — found: self · cause: spec · made: none · the first design wrote an `end` line for
  a halted session into `run.jsonl`; the next run would then start the step afresh instead of
  parking, and C04.12 and C05.11 forbid any new line there. Changed to a file of its own before
  any code.
