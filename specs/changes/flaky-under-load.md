# Four heartbeat, park and halt tests hold under load

## What changes
Before: three tests failed on and off when the machine was busy, and passed when run alone
(D10.18, D11.25, D11.29, D11.32, D12.34 to D12.36; #211, N1):
`PhoneTest.test_heartbeat_comment_edited_in_place` (C11.16),
`HeartbeatTest.test_heartbeat_beats_through_a_quiet_tool` (C11.10) and
`UsageLimitTest.test_far_reset_parks` (C09.3); a fourth, `UsageLimitTest.test_halt_during_wait`
(C09.4), failed the same way once they held (Notes). After: each runs with its fake `gh` slowed on
purpose, as a busy machine slows it, and with its fake claude timed to the driver's polls, and
passes every time. The driver does not change: in each failure it did what its criterion says,
and the test had bet on the clock.

## Why
The local full run was red for a reason nobody read, so a real failure could hide behind it, and
CI saw one of them once (#220). The causes, seen on `main` at `51f8450` on 2026-11-15:

- C11.16: a poll's issue read can be in progress when the session's `result` line arrives. The
  heartbeat built after that read says "last event: result", which is true, and the test wanted
  "last event: system init" in the last edit. Under `scripts/test-parallel.py --repeat 10`,
  `test_phone.py` failed 3 of 10, each time on that check; a probe printed one run's last body as
  "last event: result, 0m02s ago". The branch played no part: D11.25's guess was right.
- C11.10: a poll that runs the fake `gh` took longer than the test's fixed 0.5 and 2.5 seconds,
  so its reads saw the file written at the run's start, `last_event` null: 9 of 10 with the full
  suite running beside it, and in a probe 10 of 10, 6 of them in both reads. D11.32's guess.
- C09.3: the test counted the 10 seconds from the driver's start, through its start-up and the
  fake `gh` calls before and after the park line. The park line was printed and the exit code was
  still `None` at the bound: 8 of 10 with the full suite running beside it.

## Acceptance criteria
Tick each box in this PR once its evidence is in the PR body; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [x] S-flaky-under-load.1 **hold** — C11.16 under load: with the fake `gh`'s `issue list`
      sleeping 1 second and the fake claude printing its `result` as the third poll's issue read
      starts, the run posts one heartbeat comment, then at least one PATCH whose stdin is an object
      with the one key `body`; the last PATCH made before the `result` line was read (the last
      whose body does not hold "last event: result") holds "last event: system init"; the step's
      outcome is that of the run at `--poll 30`. A PATCH after the `result` line holds "last event:
      result" and is no failure.
      Test: `PhoneTest.test_heartbeat_comment_edited_in_place`.
      broken: a heartbeat that keeps no comment id → AssertionError: Tuples differ: (False, True, True, False, True, False, True, True) != (True, True, True, True, True, True, True, True)
- [x] S-flaky-under-load.2 **hold** — C11.10 under load: with the fake `gh`'s `issue list`
      sleeping 2 seconds and the fake claude printing its `init` line as a poll's issue read starts,
      then quiet until the test lets it go, the test reads `<state>/heartbeat.json` once its
      `last_event` is the `init` line's `at` and again once its `poll` is later, each wait at most
      30 seconds; both reads pass C11.10's checks, and the file is there after the step.
      Test: `HeartbeatTest.test_heartbeat_beats_through_a_quiet_tool`.
      broken: the poll writes no heartbeat → AssertionError: Tuples differ: (True, True, True, True, True, True, False, False, True) != (True, True, True, True, True, True, True, True, True)
- [x] S-flaky-under-load.3 **hold** — C09.3 under load: with the fake `gh`'s `issue create`
      sleeping 6 seconds, the run log's `end` line comes at most 10 seconds after its `pid` line,
      the driver prints the park line alone, exits 1 within 60 seconds and starts the fake once;
      with `--limit-hours 40` it waits instead and is stopped by the halt file.
      Test: `UsageLimitTest.test_far_reset_parks`.
      broken: a park that waits 15 seconds before its line → AssertionError: Tuples differ: (True, False, 1, 1, ['park: the usage limit rese[53 chars]`)']) != (True, True, 1, 1, ['park: the usage limit reset[52 chars]`)'])
- [x] S-flaky-under-load.4 **hold** — C09.4 under load: with the fake `gh`'s `issue close`
      sleeping 6 seconds, the halt file written during a 60-second wait makes the driver print
      "halt: the halt file was set during the wait for the usage limit (session `<id>`)" at most
      5 seconds after it, as C09.4 says, then exit 1 within 60 seconds, starting the fake once;
      the run log's events for the session are `start`, `pid`, `end`.
      Test: `UsageLimitTest.test_halt_during_wait`.
      broken: a halt line 8 seconds after the halt file → AssertionError: Tuples differ: (True, False, 1, ['halt: the halt file was set d[54 chars]], 1) != (True, True, 1, ['halt: the halt file was set du[53 chars]], 1)

## Verify
```bash
python -m unittest tests.test_phone tests.test_heartbeat tests.test_usage_limit
python scripts/test-parallel.py --repeat 10 test_phone.py
python scripts/test-parallel.py --repeat 10 test_heartbeat.py
python scripts/test-parallel.py --repeat 10 test_usage_limit.py
```

## Notes
- Departures from the criteria as written, for the maintainer: C11.16's "the last of them" is
  read as the last PATCH before the `result` line; C11.10's reads at "0.5 and 2.5 seconds" after
  the `init` line become waits for the first beat that names it and for the poll after it; C09.3's
  "within 10 seconds" is counted from the session's start (the run log's `pid` line) to its `end`
  line, written as the park line is printed. The driver's behaviour is the same, so nothing is
  replaced; a day that rewrites those criteria can take these readings.
- The rung: the change is in `tests/` only, which the ladder's area row could also take; #211's N1
  asked for a short spec, and its criteria are `hold`, since the code on `main` already does what
  they say. A `new` criterion would fail CI's "Track tests seen red": the code before is the code
  after. The seen-red record is the first commit, the slowed fakes with the old checks.
- The sleeps make each test longer: run alone, about 18, 12, 19 and 10 seconds. `test_phone.py`
  and `test_usage_limit.py` are among the suite's slowest files; the runner's floor is still
  `test_on.py`.
- C09.4 needs no departure: its criterion bounds the halt line, and the test had bounded the exit,
  which comes after the run's issue is closed.
- **Defect** — found: self · cause: implementation · made: none · `UsageLimitTest.test_halt_during_wait`
  (C09.4) failed 8 of 10 beside the full suite once the other three held: its 5 seconds were
  counted to the driver's exit, not to the halt line. `scripts/test-parallel.py` prints a file's
  first failure in full, so on `main` `test_far_reset_parks` hid it; the eight kept failure files
  named it. Fixed here as S-flaky-under-load.4 (this PR).
- **Defect** — found: self · cause: process · made: none · the first `--repeat 10` runs were given
  `tests/test_phone.py` and printed nothing, matching no file: `scripts/test-parallel.py` takes a
  name under `tests/`, as `CLAUDE.md` writes it. Re-run with the bare names (this PR).
