# Day 13 Track D brief: the level 2 start in `loop.steps` (C13.7)

Spec: `specs/day-13-the-merge.md`, "The start (Track D)" in In scope, and C13.7. Branch
`day-13/track-d-level-2-start`, already made from fresh `main`. Do not commit.

## Order of work

1. Write the tests first (below), in the new file `tests/test_level_2_start.py`.
2. Run them on `main`'s code, before any code change:
   `python scripts/seen-red.py --expect "AssertionError" -- python -m unittest tests.test_level_2_start -v`
   Red today: `on` starts a session in each case and makes no `api` call. Every one of the five
   tests must fail on an assertion (not an error in setup). If any passes, or errors, stop and
   report; write no code.
3. Then the code in `driver/loop.py`. Run `python scripts/test-parallel.py "test_level_2_*.py"`
   and `python scripts/test-parallel.py "test_on*.py"`, and report the counts.

## The code: `driver/loop.py`

In `steps`, right after the live check's refusal (`line = livecheck.refusal(...)`, `if line:
return once.refuse([line])`) and before `reason = once.settle(args, project)`, add:

```python
    if config.get("level") == 2:
        lines = level_2_refusals(args, project, config)
        if lines:
            return once.refuse(lines)
```

and a new module-level function `level_2_refusals(args, project, config)` in `driver/loop.py`
that returns a list of lines, empty when all four conditions hold. `<path>` is `args.config` as
given. In this order, one line per failed condition:

1. `config.get("review") is not True` →
   `cannot start: level 2 needs "review": true in <path>`
2. `"container_image" not in config` →
   `cannot start: level 2 needs the sessions in the container: <path> has no container_image`
3. `records, _ = runlog.read(args.state)`; `k = status.level_2_run(records)` when `records` is
   not None, else 0 (a missing or unreadable run log counts 0). When `k < status.LEVEL_2_RUN` →
   `cannot start: level 2 needs 15 of 15 pull requests in a row merged without a change asked; status counts <k>`
   (write the 15s from `status.LEVEL_2_RUN`).
4. Only when 1 to 3 gave no line: `reason = github.protection(project, args.gh)`; when it is not
   None → `cannot start: level 2 needs main to require a pull request and its checks with no bypass: <reason>`

Add `status` to the `from driver import ...` line in `driver/loop.py` (check `driver/status.py`
does not import `driver.loop`; it imports `issues`, `lock`, `runlog`). Nothing else changes; at
level 1 or with no `level` the code path is untouched.

## The tests: `tests/test_level_2_start.py`, class `LevelStartTest`

Model it on `tests/test_level_2_merge.py`'s `LevelMergeTest` (same base `ReviewCase` from
`tests/test_review_loop.py`, the same assigned helpers `box`, `hidden`, `plain`, `named`,
`names` from `tests/test_box_session.py`'s `BoxSessionTest` and `run_steps` from
`tests/test_box_preflight.py`'s `BoxPreflightTest`). Use `container_merges(first, k)` from
`tests/test_level_2_blocker.py` to seed `run.jsonl` (written as bytes, one JSON per line, as
`test_level_2_merge.py` does), `rewrite` from `tests/test_review_loop.py` to change
`driver.json` and `gh/fake.json`. The fake `gh` (`tests/test_github.py`) answers an `api` call
from the `api` map in `gh/fake.json`, keyed by the path argument; an unmatched `api` exits 0 with
nothing.

Fixtures (as `tests/test_merge_gh.py` has them):

```python
CLASSIC = "repos/{owner}/{repo}/branches/main/protection"
RULES = "repos/{owner}/{repo}/rules/branches/main"
def protected(admins):  # classic protection requiring the pull request and the checks
    return {"code": 0, "out": {
        "required_pull_request_reviews": {"required_approving_review_count": 0},
        "required_status_checks": {"contexts": ["tests"], "checks": [{"context": "tests", "app_id": 1}]},
        "enforce_admins": {"enabled": admins}}}
NO_RULES = {"code": 0, "out": []}
```

Each refusal test asserts, with the config path replaced by `<path>` in stderr (replace both
`str(path)` and `os.path.realpath(path)`; the reports must hold no absolute path):
- exit code 2;
- stderr's lines equal exactly the one expected line;
- no session started: the run log (`run.jsonl`) has no record with `"event": "start"` beyond the
  seeded ones (compare the count of start records before and after);
- no issue created: the fake `gh`'s calls hold no `["issue", "create", ...]`;
- the first three: no `api` call among the fake `gh`'s calls.

Cases (all with `"level": 2`):

- `test_needs_review`: container keys (via `box`), run log of 15 (`container_merges(101, 15)`),
  `review` absent from `driver.json`. Line:
  `cannot start: level 2 needs "review": true in <path>`
- `test_needs_container`: no container keys (plain `self.build(...)`, not `box`; set
  `self.secrets` to a path in the case folder so `hidden` works), `review` true, run log of 15.
  Line: `cannot start: level 2 needs the sessions in the container: <path> has no container_image`
- `test_needs_the_count`: container keys, `review` true, run log of 14
  (`container_merges(101, 14)`). Line:
  `cannot start: level 2 needs 15 of 15 pull requests in a row merged without a change asked; status counts 14`
- `test_needs_protection`: container keys, `review` true, run log of 15, `api` map
  `{CLASSIC: protected(False), RULES: NO_RULES}`. Line:
  `cannot start: level 2 needs main to require a pull request and its checks with no bypass: main allows a bypass`
  (this case does make the two `api` calls; assert them: `[["api", CLASSIC], ["api", RULES]]`).
- `test_starts_when_all_hold`: container keys, `review` true, run log of 15, `api` map
  `{CLASSIC: protected(True), RULES: NO_RULES}`, the session's fake claude/docker answers as
  `test_level_1_never_merges` gives them. Assert: the fake `gh`'s calls hold `["api", CLASSIC]`
  then `["api", RULES]`, both before the first `["issue", "create", ...]` call; the run log has a
  new `"event": "start"` record (a session started). Exit code and later lines as at level 1 need
  not be asserted beyond that.

For the review-on cases, use `self.reviewed(...)` as `test_level_1_never_merges` does, then
`rewrite(self.folder / "driver.json", level=2)`; for `test_needs_review`, remove `review` from
`driver.json` after `reviewed` (read, `pop("review")`, write back as `rewrite` does).

Compare with `same(self, found, expected)` (one tuple per test) as `test_level_2_merge.py` does,
so a failure prints the whole tuple.

## Report back

The five tests' red output (from seen-red.py) before the code, the diff's `--stat`, and the two
test-parallel runs' counts and OK lines. Do not commit.
