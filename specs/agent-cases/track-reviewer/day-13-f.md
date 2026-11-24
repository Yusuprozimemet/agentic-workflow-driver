# Day 13 Track F brief: the session rule and review_pass's second line

Spec: `specs/day-13-the-merge.md`, criteria C13.14 and C13.16 (C13.15 is a hold the main session
checks; nothing to write for it). Branch `day-13/track-f-session-rule-and-review-line`, already
checked out. Do not commit or push. Windows: the working tree is CRLF; use the Edit tool for edits.

## Order: tests first, seen red, then the code

### 1. `tests/test_session_rules.py` (new): `SessionRulesTest.test_install_line` (C13.14)

- Read `rules/session.md` at commit `5d4f1b5` with `subprocess.run(["git", "show",
  "5d4f1b5:rules/session.md"], cwd=ROOT, capture_output=True, check=True)` and decode as UTF-8;
  read the working file `ROOT / "rules" / "session.md"` as bytes, decoded UTF-8. `ROOT` is
  `Path(__file__).resolve().parent.parent`.
- Line endings aside: compare `.splitlines()` of each.
- Expected: the `5d4f1b5` lines with this one line inserted right after the one line that starts
  with `- You never merge` (exactly one such line; assert it):
  `- Before running the project's tests, install the project as its CI does (its workflows in `.github/workflows/`).`
  (The backticks around `.github/workflows/` are literal characters in the line.)
- Assert with `self.assertEqual(found_lines, expected_lines)`. Red today: the file is its
  `5d4f1b5` text, so the lists differ (an AssertionError, "Lists differ").

### 2. `tests/test_review_after.py` (new): `ReviewAfterTest.test_git_fails_after_the_review` (C13.16)

Model it on `ReviewLoopTest.test_snapshot_git_fails` in `tests/test_review_loop.py` (lines
385-409); do not edit `tests/test_review_loop.py`.

- `from tests import test_box_preflight as preflight`; `from tests.test_review_loop import
  REVIEW_ONLY, ReviewCase, same`.
- `class ReviewAfterTest(ReviewCase, unittest.TestCase)` with the same two assignments as
  `ReviewLoopTest`: `run_steps = preflight.BoxPreflightTest.run_steps` and
  `hidden = preflight.BoxPreflightTest.hidden`.
- The test: `self.review("git_fails_after", [{"text": REVIEW_ONLY}])`; set
  `self.secrets = self.folder / "secrets.env"` as the model does. Patch `driver.review.snapshot`
  (via `importlib.import_module("driver.review")` and `mock.patch.object(review, "snapshot",
  side_effect=...)`) with a function that calls the original on its first call and returns the
  original's dict with every value `None` on its second (and later) calls: git works before the
  reviewer's session and fails after it.
- Run `code, _, err = self.run_steps("on")`, `step, reviewer = self.uuids()`, then
  `same(self, (code, message in self.hold(err, step, reviewer), len(self.sessions()), len(self.reviewer_ids())), (2, True, 2, 1))`
  with `message = "cannot read the project: git failed after the review of #12"`.
  Two sessions ran (the step's and the reviewer's), one reviewer id.
- Red today: `driver/loop.py` line 186 says "before the review", so the second field is False:
  `same`'s report names it.

### 3. Seen red, before any code

Run, and stop and report if either is not red for this reason:

```
python scripts/seen-red.py --expect "Lists differ|AssertionError" -- python -m unittest tests.test_session_rules tests.test_review_after
```

### 4. The code

- `rules/session.md`: insert the line from 1 right after the line `- You never merge a pull
  request, and you never push to `main`.` Change nothing else in the file.
- `driver/loop.py` line 186 (in `review_pass`, the check of `after`): "before the review" →
  "after the review". Line 179 (the check of `before`) stays "before".

### 5. Targeted tests

```
python scripts/test-parallel.py "test_session_rules.py" "test_review_after.py" "test_review_loop.py" "test_once.py"
```

`OnceTest.test_rules_file` in `tests/test_once.py` must still pass (it needs "never merge" in
exactly one line: the new line does not hold it). Report each command's "Ran N tests" and OK/FAILED
lines, and the full diff stat (`git diff --stat`), not whole logs.
