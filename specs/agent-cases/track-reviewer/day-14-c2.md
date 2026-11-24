# Brief: Day 14 Track C2, the build's half of the picker removed (C14.8)

Branch `day-14/track-c2-build-picker` (already checked out, from fresh `main` at 2e24e86). Do not commit.
Spec: `specs/day-14-the-level-2-record.md`, C14.8 and "In scope", "The leftover picker goes".

## Step 1: the test first (stop if it is not red for this reason)

In `tests/test_picker_gone.py` (made by Track C1), add to `PickerGoneTest` a method
`test_build_half_gone`, built as `test_page_half_gone` is:

- a module-level `BUILD_NAMES` list beside `PAGE_NAMES`, the ten names spelled in parts so the
  grep does not find this file: `"how_" + part` for `excerpts`, `excerpts_of`, `specs`,
  `this_works`, and `"HOW_" + part` for `TEMPLATE`, `REPLAY`, `PLAN`, `PLAN_PARTS`, `NEEDED`,
  `NO_PROMISE`;
- `code, files = grep_files(BUILD_NAMES, ["scripts", "tests"])`, then
  `self.assertEqual(files, [])`, then `self.assertEqual(code, 1)` (that order: the list first).
- In the module docstring, change "(Day 14, C14.16)" to "(Day 14, C14.8 and C14.16)" and say
  the build's half too; keep it short and keep the line width under 120.

Then run, from the repository root:

```
python scripts/seen-red.py --expect "Lists differ" -- python -m unittest tests.test_picker_gone.PickerGoneTest.test_build_half_gone
```

Expected Red (C14.8's Red today): `AssertionError: Lists differ: ['scripts/spec-drift.py', 'scripts/spec_drift_page.py', 'tests/test_how_this_works.py'] != []`.
If it is not red for that reason, stop and report.

## Step 2: the code

1. `scripts/spec_drift_page.py`: delete the whole block from the comment line
   "# One real promise, picked by how_excerpts, ..." (line 398) through the `return out` that
   ends `how_excerpts_of` (line 527), keeping two blank lines before `def fill(`. That is the
   comment, the six `HOW_*` constants, `how_specs`, `how_excerpts` and `how_excerpts_of` with
   its inner functions. Nothing outside the block calls them (checked by `git grep`).
2. `scripts/spec-drift.py`, lines 281-284: delete the `if args.build:` block whose body is the
   comment "The re-check rows are on the data branch...", the `how_read = lambda ...` line and
   `real["how_this_works"] = how_excerpts(...)`. Leave the next line
   (`payload = page_data(real, spec_days) if args.build else real`) as it is.
3. Delete `tests/test_how_this_works.py` (`git rm` is fine; do not commit).
4. Run `ruff check scripts/spec_drift_page.py scripts/spec-drift.py tests/test_picker_gone.py`.
   Remove the imports (in `spec_drift_page.py`'s `from ... import (...)` lists, or `import`
   lines) that ruff then flags as unused, and only those. A name may still be needed by
   `spec-drift.py` through `from spec_drift_page import *`: before removing an import, check
   with `git grep -n -w <name> -- scripts/spec-drift.py` whether spec-drift.py also star-imports
   the module it comes from (it star-imports `spec_drift_common`, `spec_drift_git`,
   `spec_drift_specs`, `spec_drift_data` directly), so it does not lose the name.
   Then `ruff format --check` on the same files.

## Step 3: checks

- `python -m unittest tests.test_picker_gone -v`: 2 tests, OK.
- `git grep -n -w -e how_excerpts -e how_excerpts_of -e how_specs -e how_this_works -e HOW_TEMPLATE -e HOW_REPLAY -e HOW_PLAN -e HOW_PLAN_PARTS -e HOW_NEEDED -e HOW_NO_PROMISE -- scripts tests`
  prints nothing.
- `python scripts/test-parallel.py "test_spec_drift*.py"` and
  `python -m unittest discover -s scripts -p "test_*.py"`: report the counts and any failure.

Report: the seen-red line, the lines removed per file (`git diff --numstat`), the imports removed,
and the test counts.
