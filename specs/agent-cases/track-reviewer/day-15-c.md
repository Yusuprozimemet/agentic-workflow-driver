# Day 15 Track C brief: status's level and a running review's own line (C15.10–C15.13)

Spec: `specs/day-15-the-gate-by-name.md`, "In scope" (the two Track C bullets) and C15.10 to C15.13.
Work on branch `day-15/track-c-review-progress` (already checked out). Never commit or push.

## Order

1. Write the three new test files below, nothing else.
2. Run seen-red on them (command at the end) and stop if any test is not red for the reason given.
3. Only then change the code.
4. Run the targeted tests (command at the end) and report each file's "Ran N tests" and "OK".

## The code (four files, nothing else)

### `driver/runlog.py`

`start` gains a keyword `pr=None`. When given, `record["pr"] = pr` goes after `"claude"` and before
the issue, so a start line with a pr reads `... "claude": ..., "pr": 12, "issue": ...`. Put it as
its own `if pr is not None:` block just after the dict literal, before the issue's comment and
block. The line `record["issue"] = issue` stays exactly as it is, and occurs once.

### `driver/review.py`

In `run`, the `runlog.start(` call (around line 134) gains `pr=number,` (the function's `number`
parameter). No other change.

### `driver/status.py`

- `run(project, gh, state, watch=None)` becomes `run(project, gh, state, watch=None, level=1)` and
  passes `level` to both `_report` calls. `_report(project, gh, state, seen=None)` becomes
  `_report(project, gh, state, seen=None, level=1)`, and its line `lines = [mode, "level: 1", _halt(state)]`
  becomes `lines = [mode, f"level: {level}", _halt(state)]`.
- `_kind(prefix)`: after the `isinstance` check, `if prefix == "review": return "review"`. Update
  its comment: a prefix that is none of the four has none.
- `_step(records, session)`: for the newest start line of the session, when its `prefix` is
  `"review"`, return `f"review of #{pr}"` when the start line has a `pr` that is not `None`, else
  `_review_of(records, session)`; any other prefix returns `record.get("step")` as today. Write the
  test of the prefix as `record.get("prefix") != "review"` (or another form), NOT as
  `start.get("prefix") == "review"`: that exact text must keep occurring once in the file.
  Update the comment.
- Nothing else in the file changes. These texts are earlier Days' break finds and must each
  still occur exactly once, unchanged (check with `grep -c -F`):
  `if start.get("prefix") == "review"`, `return "review of an unknown pull request"`,
  `if session is not None:`, `        if session:` (eight spaces),
  `if other not in ends or _kind(start.get("prefix")) != kind:`,
  `lines.append(_in_progress(state, live, records, session))`, `lines.append(_level_2(records))`.

### `run-steps.py`

In `main`, `status` gets the config's level only when a config was read. Before the line
`if args.project is None:` add `status_extra = {}`; inside that block, after
`args.project = config["project"]`, add `status_extra["level"] = config.get("level", 1)`. The
`status.run(` call adds `**status_extra` as its last argument. `if args.project is None:` stays
exactly as it is and occurs once.

## The tests (three new files; no existing test file is edited)

Each file starts with a docstring saying what it holds and which criteria, the `ROOT`/`sys.path`
lines as `tests/test_status_review.py` has them, and ends with
`if __name__ == "__main__": unittest.main()` only if the other test files do (check
`tests/test_status_review.py`'s end and do the same).

No assertion may compare a string over 80 characters or a list with `assertEqual`: unittest then
prints "[N chars]", which `seen-red.py` and `break.py` refuse. Compare single short lines.

### `tests/test_status_level.py` — `StatusLevelTest.test_config_level` (C15.10)

In `setUp`: a temp root (`tempfile.mkdtemp()`, `addCleanup(shutil.rmtree, ..., ignore_errors=True)`),
a `project` folder, a `state` folder path, and a `gh` folder for `fake_gh` (from
`tests.test_github`), as `StatusReviewTest.setUp` does.

A helper `status_with(config)` writes `config` as JSON bytes to `<root>/driver.json`
(`Path.write_bytes(json.dumps(config).encode("utf-8"))`) and runs
`[sys.executable, str(ROOT / "run-steps.py"), "status", "--config", <that path>, "--state", <state>, "--gh", <fake_gh(folder, issues=[])>]`
with `check=False, capture_output=True, text=True, encoding="utf-8", timeout=60`.

The base config: `{"project": <project>, "human_only": [], "budget_usd": 5, "steps_per_night": 1}`.

`test_config_level`: with the base plus `"level": 2`, `assertEqual(lines[1], "level: 2")` where
`lines = done.stdout.splitlines()`; then with the base alone (no `level`),
`assertEqual(lines[1], "level: 1")`. Before each `assertEqual` on `lines[1]`, assert
`done.returncode` is 0 with `assertEqual(done.returncode, 0, done.stderr)` — if the config is
refused, that names why.

Red today: `AssertionError: 'level: 1' != 'level: 2'`.

### `tests/test_review_start.py` — `ReviewStartTest.test_start_names_the_pr` (C15.11)

`from tests.test_review_loop import REVIEW_ONLY, ReviewCase` (import only those two names, so
`ReviewLoopTest` is not collected again here).

`class ReviewStartTest(ReviewCase, unittest.TestCase)`, with the same two class attributes
`ReviewLoopTest` has (`run_steps = preflight.BoxPreflightTest.run_steps`,
`hidden = preflight.BoxPreflightTest.hidden`, `from tests import test_box_preflight as preflight`),
in case `on` needs them.

`test_start_names_the_pr`: `self.review("start-pr", [{"text": REVIEW_ONLY, "cost": 0.25}])`,
`self.on()`, then from `self.run_log()` take
`prs = [r.get("pr", "no pr key") for r in log if r.get("event") == "start" and r.get("prefix") == "review"]`
and `self.assertEqual(prs, [12])`.

Red today: `AssertionError: Lists differ: ['no pr key'] != [12]` (the message's first line; the
rest of unittest's list diff follows).

### `tests/test_review_progress.py` — `ReviewProgressTest` (C15.12, C15.13)

Imports: `from driver import lock, status` and from `tests.test_status`: `T1, encode`; from
`tests.test_github`: `fake_gh`. Use `datetime` for times.

Constants: `TRACK_STEP = "Day 15 Track C"` (a track's step, as `review.run` passes it, so the
step's sentence never reads "review of #12"), `TRACK = "day-15/track-c"`.

Helpers (module functions):
- `start_line(session, prefix, at, pr=None)`: `{"event": "start", "at": at, "step": TRACK_STEP, "prefix": prefix, "session": session, "claude": "claude"}`, plus `"pr": pr` when `pr` is not `None`.
- `end_line(session, at)`: `{"event": "end", "at": at, "session": session, "outcome": "review: #12, 0 blockers", "cost_usd": 0, "denials": 0}`.
- `earlier_reviews()`: three ended review sessions `e0`, `e1`, `e2`, of 600, 1200 and 2400 s: session
  `e<i>` starts at `T1 + i hours` and ends that many seconds later; stamps written with
  `lock.STAMP`, parsed from `T1` with `lock.stamp_time`.
- `verdict_line(session, pr)`: `{"event": "review", "at": T1, "pr": pr, "session": session, "head": "abc1234", "blockers": 0}`.

`setUp` as `StatusReviewTest.setUp` (root, project, state, gh folder). Methods:
- `live_pid()`: as `StatusTest.live_pid` in `tests/test_status.py` (a child sleeping 120 s,
  `addCleanup(child.wait)` then `addCleanup(child.kill)`).
- `live_log(records)`: writes `records` plus, last, a pid line for session `r1`:
  `{"event": "pid", "at": <now stamp>, "session": "r1", "pid": self.live_pid(), "started": <now stamp>}`
  where `<now stamp>` is `lock.now().strftime(lock.STAMP)`, as bytes with `encode`, to
  `<state>/run.jsonl`.
- `status()`: runs `run-steps.py status --project <project> --state <state> --gh <fake_gh(folder, issues=[])>`
  as `StatusReviewTest.status` does, returns the `CompletedProcess`.
- `line(done, prefix)`: the first stdout line starting with `prefix`, or `"no line " + prefix`.

The live review session is `start_line("r1", "review", <now stamp>, pr=...)`.

Tests (each asserts the `in progress:` line first, then the `running:` line's part after its
first `" ("`, with `assertEqual`; first assert `done.returncode == 0` with
`assertEqual(done.returncode, 0, done.stderr)`):

- `test_live_review_line`: log = live review start with `pr=12`. Expect
  `in progress: review of #12 (session `r1`), cost so far $0.00` and running part
  `no estimate: 0 earlier review sessions)`.
- `test_review_estimate`: log = `earlier_reviews()` + live review start with `pr=12`. Expect the
  same `in progress:` line and running part `estimate 20m00s, the median of 3 earlier review sessions)`.
- `test_no_pr_on_the_start`: log = live review start with no `pr`, no review line. Expect
  `in progress: review of an unknown pull request (session `r1`), cost so far $0.00` (over 80
  characters: compare it as `assertEqual(line.split(" (session")[0], "in progress: review of an unknown pull request")` and
  `assertEqual(line.split(" (session")[1], " `r1`), cost so far $0.00")`, two short compares).
- `test_pr_from_review_line`: log = live review start with no `pr`, then `verdict_line("r1", 12)`.
  Expect `in progress: review of #12 (session `r1`), cost so far $0.00`.
- `test_track_counts_no_review` (C15.13, no subprocess): `records = earlier_reviews() + [start_line("run", TRACK, <stamp 725 s before now>)]`,
  `now = lock.now()`, `running = status.progress(records, "run", [], now)[0]`;
  `assertEqual(running.split(" (", 1)[1], "no estimate: 0 earlier track sessions)")`.
  This one passes today (a hold): do not expect it red.

Red today: for the first four, `in progress: Day 15 Track C (session `r1`), cost so far $0.00`
against the review line (the step's sentence); for `test_no_pr_on_the_start` its first compare,
`'in progress: Day 15 Track C' != 'in progress: review of an unknown pull request'`.

## Commands

Seen red, before any code (Git Bash, from the repository root):

```
python scripts/seen-red.py --expect "level: 1' != 'level: 2'|\['no pr key'\] != \[12\]|in progress: Day 15 Track C" -- python -m unittest tests.test_status_level tests.test_review_start tests.test_review_progress.ReviewProgressTest.test_live_review_line tests.test_review_progress.ReviewProgressTest.test_review_estimate tests.test_review_progress.ReviewProgressTest.test_no_pr_on_the_start tests.test_review_progress.ReviewProgressTest.test_pr_from_review_line
```

and `python -m unittest tests.test_review_progress.ReviewProgressTest.test_track_counts_no_review`
passes before the code.

Targeted tests after the code:

```
python -m unittest tests.test_status_level tests.test_review_start tests.test_review_progress tests.test_progress tests.test_status tests.test_status_review tests.test_status_trial tests.test_status_watch tests.test_review_loop tests.test_runlog
```

(if `tests/test_runlog.py` does not exist, leave it out and say so). Then
`ruff check . && ruff format --check .` (run `ruff format` on the three new files and the four
code files only, if it fails on them).

Report: each file changed with its line counts (`git diff --numstat` and `wc -l` on new files),
the seen-red output's last lines, and each test command's "Ran N tests" and "OK"/"FAILED" line.
