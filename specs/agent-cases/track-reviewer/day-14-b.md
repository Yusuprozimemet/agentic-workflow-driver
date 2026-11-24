# Day 14 Track B brief: the reviewer's row and `_reviewer` in `driver/status.py` (C14.5, C14.6)

Spec: `specs/day-14-the-level-2-record.md`, "In scope", the bullet "The reviewer's session in
`status`", and criteria C14.5, C14.6, C14.7. Branch `day-14/track-b-reviewer-row` (already
checked out). Do not commit.

Files you may edit: `driver/status.py` and `tests/test_status_review.py`. Nothing else.
`tests/test_status.py` and `tests/test_status_trial.py` stay unedited (C14.7); import from them.

## Order

1. Write the three tests first (below), in `tests/test_status_review.py`, class `StatusReviewTest`.
2. Run, before any code:
   `python scripts/seen-red.py --expect "Step A' != 'review of|has no attribute '_reviewer'" -- python -m unittest tests.test_status_review -v`
   It must exit 0 and print `seen red:` lines. If it exits 1, stop and report its output; do not
   write the code.
3. Then the code in `driver/status.py`.

## The tests (in `tests/test_status_review.py`)

Keep the existing `test_no_reviewer_line_without_review` and the class's `setUp`, `status`,
`write_log` unchanged. Add at module level:

- `import json` is not needed; add `from driver import status` after the `tests.` imports
  (`ROOT` is already on `sys.path` there).
- `T2 = "2026-11-08T11:00:00Z"`, `T3 = "2026-11-08T12:00:00Z"`.
- `def review_start(session, at):` returns `start(session, "Step A", at)` with its `"prefix"` set
  to `"review"` (copy the dict, then set the key).
- `def verdict(session, pr):` returns
  `{"event": "review", "at": T1, "pr": pr, "session": session, "head": "abc1234", "blockers": 1}`.
- `def row_of(stdout, number):` the line `number` rows after the `steps:` line
  (`lines = stdout.splitlines(); return lines[lines.index("steps:") + number]`).
- `def label(row, at):` the text between `"  {at} "` and the first `":"` after it:
  `row[len(f"  {at} "):].split(":")[0]`.

The log `LOG`, used by tests 1 and 3:
`[start("s1", "Step A", T1), end("s1", "opened: #20", 0.25, 0), review_start("r1", T2), verdict("r1", 7), end("r1", "review: #7, 1 blockers", 0.4, 0)]`

1. `test_review_row`: write `LOG`, run `self.status()`, assert `returncode == 0` (message
   `done.stderr`). `row = row_of(done.stdout, 2)`. First
   `self.assertEqual(label(row, T2), "review of #7")` (short, so the red report is short), then
   `self.assertEqual(row, f"  {T2} review of #7: review: #7, 1 blockers, $0.40, refusals 0, session `r1`")`.
   (The second line's backticks are literal characters in the string.)
   Red today: `AssertionError: 'Step A' != 'review of #7'`.
2. `test_review_row_without_review_line`: log
   `[start("s1", "Step A", T1), end("s1", "opened: #20", 0.25, 0), review_start("r1", T2), end("r1", "crashed", 0.1, 0)]`
   (no `review` line). `row = row_of(done.stdout, 2)`; assert
   `label(row, T2) == "review of an unknown pull request"`, then
   `row == f"  {T2} review of an unknown pull request: crashed, $0.10, refusals 0, session `r1`"`.
   Red today: `AssertionError: 'Step A' != 'review of an unknown pull request'`.
3. `test_reviewer_cost_line`: `records = LOG + [review_start("r2", T3), verdict("r2", 8), end("r2", "review: #8, 0 blockers", 0.3, 0)]`.
   First, before running `status`:
   `self.assertEqual(status._reviewer(records), "reviewer: 2 sessions, $0.70, in the cost above")`
   (red today: `AttributeError: module 'driver.status' has no attribute '_reviewer'`).
   Then write `records` as the log, run `self.status()`, assert `returncode == 0`, and with
   `lines = done.stdout.splitlines()` and `following = after_cost(lines)`:
   - the cost line, `[l for l in lines if l.startswith("cost: ")][0]`, starts with `"cost: $0.95,"`
     (0.25 + 0.4 + 0.3: the total still counts both reviews);
   - `following[0] == "reviewer: 2 sessions, $0.70, in the cost above"`;
   - `following[1].split(":")[0] == "level 2"`.

Also `self.assertIsNone(status._reviewer([start("s1", "Step A", T1), end("s1", "opened: #20", 0.25, 0)]))`
at the end of test 3 (no review `start` line, `None`).

Update the module docstring's first sentence only if it now reads false; add one sentence saying
the file also holds Track B's row and reviewer line.

## The code (in `driver/status.py`)

1. In `_steps`, the label of a row: today `start.get('step')`. When `start.get("prefix") == "review"`,
   the label is `_review_of(records, session)` instead. Rest of the row unchanged.
2. New `_review_of(records, session)`: the `pr` of the last record with `event == "review"` and
   that `session`; returns `f"review of #{pr}"`, or `"review of an unknown pull request"` when there
   is none.
3. New `_reviewer(records)`: the sessions of the `start` records whose `prefix` is `"review"`;
   `None` when there are none; otherwise
   `f"reviewer: {k} sessions, ${x:.2f}, in the cost above"`, `k` the number of those start lines,
   `x` the sum of `_number(r.get("cost_usd"))` over the `end` records whose `session` is one of
   them. One comment line above each new function saying what it returns (house style: see
   `_parks`, `_refused`).
4. In `_report`, between `lines.append(_cost(records))` and `lines.append(_level_2(records))`:
   ```
   reviewer = _reviewer(records)
   if reviewer:
       lines.append(reviewer)
   ```
   `lines.append(_level_2(records))` must still occur exactly once in the file (C14.7's break
   finds it). Do not touch `_cost`, `_in_progress`, `_kind` or `_running`.
5. Update the module docstring: "...and the tools the driver refused, the reviewer's sessions and
   the Level 2 count." (keep the rest).

## Run

- `python -m unittest tests.test_status_review -v` → Ran 4 tests, OK.
- `python -m unittest tests.test_status tests.test_status_trial tests.test_status_watch` → OK
  (unedited, C14.7).
- `ruff check . && ruff format --check .`

Report: the seen-red output (before the code), `git diff --stat`, and the green runs'
"Ran N tests" lines.
