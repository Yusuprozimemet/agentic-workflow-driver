# <Change title>

## What changes
<One behaviour, before and after.>

## Why
<Why this change is needed.>

## Acceptance criteria
Tick each box in this PR once its evidence is in the PR body; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [ ] S-<slug>.1 **new** — <checkable behaviour>. Test: `ExampleTest.test_new_behavior`.
      Red today: <what fails on the base>.
- [ ] S-<slug>.2 **hold** — <behaviour that stays true>. Test: `ExampleTest.test_hold`.
      broken: <what was broken> → <what the check reported>

## Verify
```bash
<command anyone can run>
```

## Notes
- <risks, gotchas, decisions deferred>
- **Defect** — found: <auditor | review | break on purpose | self | close | dashboard |
  Day NN review> · cause: <spec | implementation | process | environment> · made: none ·
  <one problem: what was wrong, and the PR that fixed it>.
