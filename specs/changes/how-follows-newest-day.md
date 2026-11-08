# "How this works" follows the newest finished day

## What changes
The dashboard's "How this works" panel follows one real promise, picked by `how_excerpts` in
`scripts/spec-drift.py`. Before: a promise with no re-check on record could not be picked, so the
panel skipped the whole of the newest day and showed C05.2. After: the re-check is not among the
steps the picker requires (`HOW_NEEDED`), the panel follows C06.1, and step 7 says "not re-checked
yet" for a promise with none.

## Why
A day's promises have no re-check until the replay reaches them, so the panel lagged at least one
finished day behind, which is the opposite of what it is for.

## Acceptance criteria
Tick each box in this PR once its evidence is in the PR body; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [x] S-how-follows-newest-day.1 **new** — A promise whole at every other step is picked though the
      replay history holds no row for it, and its re-check excerpt is an empty record, not a gap.
      Test: `PickTest.test_a_promise_with_no_recheck_is_still_picked`.
      Red today: the older day's promise is picked, "C97.1" where "C98.1" is expected.
      broken: no rows give a gap, not an empty record → FAILED (errors=1)
- [x] S-how-follows-newest-day.2 **new** — Step 7 says "not re-checked yet" for an empty record, the
      check and its state for a record with rows, and "Missing from this build" for a gap.
      Test: `PageTest.test_step_seven_says_when_there_is_no_recheck`.
      Red today: the page has no `howRecheck`, so the test cannot find the function.
      broken: step 7 says nothing when there is no re-check → AssertionError: 'not re-checked yet' not found in '<figure class="how-ex"><figcaption>C1.1</figcaption><pre></pre></figure>
'
- [x] S-how-follows-newest-day.3 **new** — A replay history that has gone leaves the pick alone and
      shows as missing, never as "not re-checked yet".
      Test: `PickTest.test_a_replay_file_gone_shows_as_missing_not_as_no_recheck`.
      Red today: no promise is picked, a KeyError on "text".
      broken: a replay history gone reads as no re-check → AssertionError: 'text' unexpectedly found in {'source': 'docs/dashboard/replay-history.json', 'text': {'pr': None, 'checks': []}}
      broken: the picker requires a re-check again → FAILED (errors=1)
- [x] S-how-follows-newest-day.4 **hold** — A promise missing any other step of its record is still
      skipped. Test: `PickTest.test_a_promise_missing_a_step_is_skipped`.
      broken: a promise with no planted bug is picked → AssertionError: 'C98.1' != 'C98.2'

## Verify
```bash
python -m unittest tests.test_how_this_works tests.test_how_this_works_page
```

## Notes
- Only this panel's pick changes; the promise tables and the re-check tally read the replay history
  as before.
- **Defect** — found: self · cause: process · made: none · the branch was first created as
  `tooling/how-follows-newest-day`, the wrong rung's name for a short spec, and renamed to
  `change/how-follows-newest-day` before any commit.
- **Defect** — found: break on purpose · cause: implementation · made: none · putting `recheck` back in
  `HOW_NEEDED` passed criterion 1's test, because a promise with no rows now gets an empty record that
  counts as present; only a replay file gone tells the two apart, so that break is run against
  criterion 3's test.
