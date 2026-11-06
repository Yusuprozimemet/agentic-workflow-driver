# Day 01 — The dry run names the next action and starts nothing

**Phase:** 0 · **Depends on:** the repository set up from the kit · **Expected PRs:** 5

## Goal
`python run-steps.py --dry-run --project <path>` prints the one action the driver would take on
that project (start a step, wait, or park with its reason) and starts nothing.

## In scope
- `driver/steps.py`: what the project's `scripts/spec-drift.py --out` wrote, read as data. The
  kind of each next-step sentence, and a phase's end from `order` and each day's `phase`.
- `driver/decide.py`: the action, from that and from facts about the project's tree and
  branches. Pure: the facts come in as data.
- `run-steps.py --dry-run --project <path>`: gathers the facts with reads only, prints one line.
- Tests under `tests/`, run with `python -m unittest discover -s tests`. Track A adds
  `tests/__init__.py`: `scripts/track-red.py` lists tests with `discover("tests", top_level_dir=".")`,
  which needs `tests/` importable. The contract test lives in `tests/test_contract.py`.
- The closing PR names `393dda6` in `README.md` as a kit commit the contract test passed on
  (`plan.md`, "How it is kept"), and adds `tests/test_contract.py` to `frozen` in
  `spec-drift.config.json`.

The sentences, as `next_step()` returns them in the kit at `393dda6`:

| The sentence | Kind | Branch prefix, or the park's reason |
|---|---|---|
| "Waiting on #7 Day 02 track A: counts" | wait | |
| "Every day is done." | park | "every day is done" |
| "No day specs yet: fill in plan.md, then write the first day's spec (specs/README.md)." | park | "there are no day specs" |
| "Day 05: write its day spec (plan.md lists it, specs/ has none)", and the same with a quoted plan item in the brackets | park | "Day 05 has no spec: writing it is the maintainer's" |
| "Day 04 is done: stop and evaluate before going on (plan.md)" | park | "a stopping point after Day 04" |
| "Day 03: read the spec against the code, then the spec-change PR" | step | `day-03/spec` |
| "Day 03 Track B: C03.2–C03.3" (any text after the colon and its space, none included) | step | `day-03/track-b` |
| "Day 03 Track A1: w" (a track's name is letters and digits) | step | `day-03/track-a1` |
| "Day 03 Track C: announced in #9, no branch names it" | park | "Track C of Day 03 was announced in #9 and has no branch" |
| "Day 03: the closing PR" | step | `day-03/close-the-day` |
| anything else | park | "the next step is not one this driver knows" |

The line the dry run prints is one of "wait: #12, #13" (the numbers of `now.open_prs`),
"start: " followed by the sentence, or "park: " followed by the reason.

## Out of scope
- Starting a session, the driver's settings, the halt — Days 3 and 4.
- The run log, the lock, a live process of an earlier session — Days 4 and 7.
- Parks as issues, and whether a phase's end was already answered — Day 5.
- Bringing a clean tree on another branch to `main`, and the evidence run after a close — Day 6;
  the start table of `plan.md`'s "Recovery" — Day 7.
- The preflight of a project's kit and of the installed CLI — Day 2.
- Any `gh` call of the driver's own: Day 1 reads GitHub only through the project's
  `spec-drift.py`.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | C01.1–C01.3: the next step's sentence and a phase's end |
| B | | C01.4–C01.5: the action from the project's state |
| C | | C01.6–C01.7: the `--dry-run` command |

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [x] C01.1 **new** — `classify()` gives every sentence in the table of "In scope" its kind, its
      day, its track and its branch prefix or reason. A track's name is lowered in the prefix
      (Track B: `day-03/track-b`; Track A1: `day-03/track-a1`; Track 0: `day-03/track-0`). The
      "announced in" sentence is a park, not a track's step; "Day 03 Track B: " (nothing after
      the colon, as the kit returns for an empty Work cell) is Track B's step. Every sentence the
      repository's own `scripts/spec-drift.py` `next_step()` can return is one of the table's:
      the contract test calls `next_step()` for each, and also counts the `return` statements
      in `next_step()` (9 at `393dda6`, read with `ast`), so a sentence the kit adds fails it.
      Red today: each test raises ModuleNotFoundError for `driver` inside the test. The tests
      import `driver` in the test or in `setUp`, never at the top of the module:
      `scripts/track-red.py` counts a module that does not load as not run, not as red.
      Test: `ClassifyTest.test_each_sentence_of_the_table`,
      `ContractTest.test_every_sentence_next_step_returns_is_known`.
      Evidence: `ClassifyTest.test_each_sentence_of_the_table` and
      `ContractTest.test_every_sentence_next_step_returns_is_known` (#3);
      `python -m unittest discover -s tests` (#3).
      seen red first on `41d6563`'s code: each test FAILED (errors=1), on the head OK (#3).
- [x] C01.2 **new** — A sentence that is not in the table parks with "the next step is not one
      this driver knows": "Day 3: the closing PR" (one digit), "day 03: the closing PR", "Day 03:
      the closing PR today", "Re: Day 03: the closing PR", "Day 03 Track : x" and the empty
      string. The whole sentence must match; only a track's sentence takes free text, after its
      colon.
      Red today: each test raises ModuleNotFoundError for `driver` inside the test.
      Test: `ClassifyTest.test_near_misses_are_unknown`.
      Evidence: `ClassifyTest.test_near_misses_are_unknown` (#3);
      `python -m unittest discover -s tests` (#3).
      seen red first on `41d6563`'s code: FAILED (errors=1), on the head OK (#3).
- [x] C01.3 **new** — A phase's end parks, judged against the day before in `order`. With
      `order` 1, 2, 3, Days 1 and 2 in Phase 0 and finished, Day 3 in Phase 1, the spec step of
      Day 3 gives "the end of Phase 0: Day 03 starts Phase 1". With `order` 1, 3, 2, Day 1 in
      Phase 0 and Days 2 and 3 in Phase 1, the spec step of Day 3 parks and the spec step of
      Day 2 does not. With Days 1, 2, 3 in Phases 0, 1, 1 and `order` 1, 2, 3, the spec step of
      Day 3 does not park. The spec step of the first day of `order`, and a track's step or the
      close of a phase's first day, give no phase's end. When the day or the day before it in
      `order` has no phase, its spec step gives "Day 03 or the day before it names no phase".
      Phase 0 is a phase: `phase` is an integer, and 0 is not missing.
      Red today: each test raises ModuleNotFoundError for `driver` inside the test.
      Test: `PhaseEndTest.test_first_step_of_a_new_phase_parks`,
      `PhaseEndTest.test_same_phase_first_day_and_later_steps_do_not`,
      `PhaseEndTest.test_missing_phase_parks`.
      Evidence: `PhaseEndTest.test_first_step_of_a_new_phase_parks`,
      `PhaseEndTest.test_same_phase_first_day_and_later_steps_do_not` and
      `PhaseEndTest.test_missing_phase_parks` (#3); `python -m unittest discover -s tests` (#3).
      seen red first on `41d6563`'s code: each test FAILED (errors=1), on the head OK (#3).
      broken: phase_end treats Phase 0 as missing → AssertionError: 'Day 03 or the day before it names no phase' is not None (#3)
- [x] C01.4 **new** — `decide()` returns the first of these that applies, and its line:
      open pull requests 12 and 13, "wait: #12, #13", whatever the tree is;
      a wait sentence with no open pull request, "park: the next step waits on no open pull
      request";
      two paths in `git status --porcelain`, "park: the project's tree is not clean (2 paths)";
      a detached HEAD, "park: the project is on a detached HEAD, not on main";
      a clean tree on `day-03/track-b-counts`, "park: the project is on day-03/track-b-counts,
      not on main";
      no `main` on the remote, "park: the project has no origin/main";
      `main` and the remote's `main` at different commits, behind or ahead, "park: main is not
      origin/main";
      a park from C01.1 to C01.3, "park: " and its reason; a branch of the step (C01.5);
      otherwise "start: " and the sentence.
      Red today: each test raises ModuleNotFoundError for `driver` inside the test.
      Test: `DecideTest.test_first_reason_wins`.
      Evidence: `DecideTest.test_first_reason_wins` (#4);
      `python -m unittest discover -s tests` (#4).
      seen red first on `437886d`'s code: FAILED (errors=1), on the head OK (#4).
- [x] C01.5 **new** — A step with a branch of its own already there never starts. A branch of
      the step is one whose name is the step's prefix, or the prefix followed by `-` or by a
      track name's letters and digits (the kit reads `track-b1-x` and `track-bb-x` as parts of
      Track B). For the step "Day 03 Track B: C03.2–C03.3", a local branch `day-03/track-b-old`,
      the same name on the remote only, `day-03/track-b`, `day-03/track-bb-x` or
      `day-03/track-b1-x` gives "park: a branch of this step exists: day-03/track-b-old" (or the
      name found). For the step "Day 03: read the spec against the code, then the spec-change
      PR", `day-03/spec` and `day-03/spec-x` park. The branches `day-13/track-b-x`,
      `day-03/track-a-x` and `day-03/spec-x` (for the Track B step) do not: the step starts.
      Red today: each test raises ModuleNotFoundError for `driver` inside the test.
      Test: `DecideTest.test_a_branch_of_the_step_parks`,
      `DecideTest.test_near_miss_branches_start`.
      Evidence: `DecideTest.test_a_branch_of_the_step_parks` and
      `DecideTest.test_near_miss_branches_start` (#4); `python -m unittest discover -s tests` (#4).
      seen red first on `437886d`'s code: each test FAILED (errors=1), on the head OK (#4).
      broken: a track's branch takes no letters or digits after its prefix → AssertionError: 'start' != 'park' (#4)
- [x] C01.6 **new** — `python run-steps.py --dry-run --project <path>` prints exactly one line
      on stdout, the action, and exits 0 for "start" and "wait" and 1 for "park". When the
      project cannot be read it prints nothing on stdout, one line on stderr that names what is
      missing, and exits 2: no `scripts/spec-drift.py` (the line names that path), the script
      fails, its JSON lacks `now.next_step`, `now.open_prs`, `order` or `days` (the line names
      the field), or GitHub was not read: `meta.caveats` holds the kit's "No GitHub remote"
      sentence while `git ls-remote --get-url origin` names `github.com` (the line says GitHub
      could not be read). Without that last check an expired `gh` login makes `spec-drift.py`
      exit 0 with no pull requests, and the dry run would start a step it should wait on.
      Red today: there is no `run-steps.py`; Python's own error also exits 2 with one stderr
      line, so the test asserts the line names the missing path or field, which it does not.
      Test: `DryRunTest.test_prints_one_action_and_its_exit_code`,
      `DryRunTest.test_unreadable_project_exits_2`, `DryRunTest.test_github_unread_exits_2`.
      Evidence: `DryRunTest.test_prints_one_action_and_its_exit_code`,
      `DryRunTest.test_unreadable_project_exits_2` and `DryRunTest.test_github_unread_exits_2`
      (#5); `python -m unittest discover -s tests` (#5).
      seen red first on `e1f09cf`'s code: FAILED (failures=3), (failures=6) and (failures=1),
      on the head OK (#5).
      broken: the GitHub-read check never fires → AssertionError: Tuples differ: (1, 'park: the project has no origin/main\n') != (2, '') (#5)
- [x] C01.7 **new** — The dry run reads the remote live, starts nothing and writes nothing in the
      project. It reads the remote's `main` with `git ls-remote origin refs/heads/main` and the
      remote's branches with `git ls-remote --heads origin`, never the remote-tracking refs a
      `fetch` would update: on a fixture whose bare remote moved ahead from a second clone with
      no fetch, it prints "park: main is not origin/main"; with a local commit not pushed, the
      same; with no remote, "park: the project has no origin/main". The only commands it runs,
      as the test records them with their arguments, are the project's `scripts/spec-drift.py`
      with `--out` and `--cache` outside the project, and `git` with `status --porcelain`,
      `rev-parse`, `symbolic-ref -q --short HEAD`, `for-each-ref` or `ls-remote`. Each test
      first asserts that the dry run printed an action and exited 0 or 1, and the recorded
      commands include `spec-drift.py` and `git status`. On a fixture project,
      `git status --porcelain --ignored` and `git for-each-ref` print the same before and after
      it.
      Red today: there is no `run-steps.py`, so no action is printed and no command recorded.
      Test: `DryRunTest.test_origin_main_is_read_live`, `DryRunTest.test_runs_only_reads`,
      `DryRunTest.test_project_is_unchanged`.
      Evidence: `DryRunTest.test_origin_main_is_read_live`, `DryRunTest.test_runs_only_reads`
      and `DryRunTest.test_project_is_unchanged` (#5);
      `python -m unittest discover -s tests` (#5).
      seen red first on `e1f09cf`'s code: FAILED (failures=3), (errors=1) and (failures=1), on
      the head OK (#5).
      broken: origin/main read from the remote-tracking ref, not ls-remote → AssertionError: Tuples differ: (0, 'start: Day 01: read the spec against the code, then the spec-change PR\n') != (1, 'park: main is not origin/main\n') (#5)
      broken: spec-drift.py's output written inside the project (test_runs_only_reads) → AssertionError: False is not true : not a read: ['C:\\Users\\HackYourFuture\\AppData\\Local\\Programs\\Python\\Python312\\python.exe', '<tmp>\\project\\scripts\\spec-drift.py', '--out', '<tmp>\\project\\spec-drift.json', '--cache', '<tmp>\\cache.json'] (#5)
      The same break also failed `DryRunTest.test_project_is_unchanged` in #5, with "?? spec-drift.json" in
      the status. It cannot be replayed: the report holds the fixture's commit hash, which changes
      on every run (D01.17).

## Verify
```bash
python -m unittest discover -s tests
```

## Notes
- Written 2026-11-06 in the kit, before this repository existed, and read against this
  repository's code by the spec-auditor and the plan-auditor the same day: the spec-change PR
  `day-01/spec-audit-fixes` fixed what they found.
- `ContractTest` loads `scripts/spec-drift.py`, which imports `numpy` at the top. `tests.yml`
  installs it; the required check "Track tests seen red" installs nothing, so Track A's
  `ContractTest` would not load there (H01.7).
- The fixture project is built by the tests in a temporary folder: a git repository, a bare one
  as its remote, a second clone to move the remote, and a `scripts/spec-drift.py` that writes
  the JSON a test gives it. Write its files as bytes: on Windows, text mode adds a carriage
  return.
- By default `spec-drift.py` keeps its cache and its output in the project's folder, both
  ignored by git. C01.7 has the dry run pass both paths outside the project.
- Every criterion is `new`: nothing exists to hold. The track PRs record `broken: none` with the
  reason, and each shows its tests red on `main`'s code.
- Track C, with the fixture and its bare remote, is the one likely to come near 400 lines.
- **Defect** D01.1 — found: auditor · cause: spec · made: Day 01 · "Red today: the tests error"
  was the red `scripts/track-red.py` rejects: a module that does not load is not run. Fixed in
  this spec change (C01.1–C01.5).
- **Defect** D01.2 — found: auditor · cause: spec · made: Day 01 · `tests/` had no
  `__init__.py`, so `track-red.py` would find none of the named tests. Fixed in this spec change
  (In scope).
- **Defect** D01.3 — found: auditor · cause: spec · made: Day 01 · C01.6's exit-2 test passed
  with no `run-steps.py`: Python's own error has the same shape. Fixed in this spec change.
- **Defect** D01.4 — found: auditor · cause: spec · made: Day 01 · C01.7's tests passed with
  nothing run: nothing changes and no command is recorded. Fixed in this spec change.
- **Defect** D01.5 — found: auditor · cause: spec · made: Day 01 · the remote's `main` and
  branches were not said to be read live; a stale tracking ref after a merge on GitHub gave
  "start" on a merged step. Fixed in this spec change (C01.7).
- **Defect** D01.6 — found: auditor · cause: spec · made: Day 01 · an expired `gh` login lets
  `spec-drift.py` exit 0 with no pull requests, and the dry run would start. Fixed in this spec
  change (C01.6).
- **Defect** D01.7 — found: auditor · cause: spec · made: Day 01 · `day-03/track-bb-x` was a
  branch that starts, while the kit reads it as part of Track B. Fixed in this spec change
  (C01.5).
- **Defect** D01.8 — found: auditor · cause: spec · made: Day 01 · a track's "letter" missed
  the names the kit allows, such as A1. Fixed in this spec change (C01.1).
- **Defect** D01.9 — found: auditor · cause: spec · made: Day 01 · the contract test could not
  fail when the kit adds a sentence. Fixed in this spec change (C01.1).
- **Defect** D01.10 — found: auditor · cause: spec · made: Day 01 · the near-misses missed
  leading text, the empty-work track sentence and a wait with no pull request. Fixed in this
  spec change (C01.1, C01.2, C01.4).
- **Defect** D01.11 — found: auditor · cause: spec · made: Day 01 · the phase-end cases could
  not tell the day before in `order` from day N−1 or the first day. Fixed in this spec change
  (C01.3).
- **Defect** D01.12 — found: auditor · cause: spec · made: Day 01 · a detached HEAD had no line.
  Fixed in this spec change (C01.4).
- **Defect** D01.13 — found: auditor · cause: spec · made: Day 01 · the allowed commands went by
  name, so `git symbolic-ref HEAD <ref>`, which writes, got through. Fixed in this spec change
  (C01.7).
- **Defect** D01.14 — found: auditor · cause: spec · made: Day 01 · "needs numpy, as the kit's
  CI already does" was not true of the check that runs `new` tests; the plan-auditor found it
  before any code. Recorded here and in H01.7.
- **Hand-off** H01.1 → Day 5: whether a phase's end was already answered by the maintainer.
  Until then the dry run parks at every phase's end, each time it is asked.
- **Hand-off** H01.2 → Day 6: a clean tree on another branch is brought to `main` (the plan's
  "Recovery"). Day 1 parks on it, on purpose (the maintainer, 2026-11-06): the dry run moves no
  branch. Day 6 changes that part of C01.4 with a `Replaces:` line, in the order of the plan's
  start table: a branch of the step parks before any switch.
- **Hand-off** H01.3 → Day 2: the fields C01.6 checks, and the GitHub-read check, become the
  preflight at `on`.
- **Hand-off** H01.4 → the maintainer: the step "write its day spec" is a manual hand-off for
  now (the maintainer, 2026-11-06). The kit names no branch for it; the driver parks on it and
  the maintainer writes the spec by hand.
- **Hand-off** H01.5 → Day 4: after a closing PR merges, `next_step()` names the next day's step
  while the evidence run is unchecked. `--once` must not start a step after a close before the
  evidence run is checked: Day 4 checks it, or parks after every close until Day 6 does.
- **Hand-off** H01.6 → Day 4: a run-log line for a step with no branch and no pull request means
  a session may exist (`plan.md`, "Recovery", rules 1 and 4). The dry run reads no log; Day 4's
  `--once` parks on such a line with its session id.
- **Hand-off** H01.7 → a `tooling/` PR before Track A: the "Track tests seen red" job in
  `.github/workflows/pr-checks.yml` installs nothing, so `ContractTest` cannot load there. It
  installs `requirements.txt` as `tests.yml` does.
- Closed 2026-11-06. H01.7 landed in #2 (`tooling/seen-red-installs-requirements`), before
  Track A; Tracks A, B and C landed in #3, #4 and #5, in the table's order. Every `new` test was
  seen red on the code before its track, by `scripts/track-red.py` in CI's "Track tests seen
  red" job, one line per test and criterion.
- The Notes above expected `broken: none` in every track: with nothing to hold there was nothing
  to break. Each track broke its code once or more anyway, on a rule its tests should guard: six
  breaks, under C01.3, C01.5, C01.6 and C01.7, five of them in `specs/breaks/day-01.json`
  (D01.17 says why not the sixth). C01.1, C01.2 and
  C01.4 rest on their seen-red lines alone.
- #2 also ran a break, on `docs/kit.md`, under no Day 01 criterion: it stays in that PR and out
  of the day's manifest.
- Track C's implementer draft came to 406 changed lines; the review cut repeated keyword
  arguments to 384 (#5).
- **Defect** D01.15 — found: Day 01 review · cause: environment · made: none ·
  `scripts/test_setup_check.py` read the protection rule from `README.md` after the rule moved to
  `docs/kit.md` when the repository was started from the kit, and errored on `main`; the job
  that runs it skips a PR that changes no workflow or script, so #1 never ran it. Fixed in #2.
- **Defect** D01.16 — found: Track A · cause: spec · made: Day 01 · C01.3 did not say what a
  spec step gives when its day is not in `order` or the day before it is not among `days`. #3
  parks it with "Day NN or the day before it names no phase", as the plan's rule to park rather
  than guess asks, and says so in its description.
- **Defect** D01.17 — found: evidence replay · cause: process · made: Day 01 · #5's break of
  `DryRunTest.test_project_is_unchanged` recorded a report that holds the fixture's commit hash.
  The fixture commits at the current time, so the hash changed and the close's rehearsal failed
  the line. It is written as a sentence under C01.7 instead, and the other break of the same code
  still replays.
- **Hand-off** H01.8 → Day 4: on Windows the dry run's stdout uses the locale's codepage, so a
  sentence with an en dash ("Day 03 Track B: C03.2–C03.3") may reach a parent reading UTF-8
  mangled. The tests use ASCII sentences. #5 named Day 3; `plan.md` has sessions start from
  this line on Day 4.
- **Hand-off** H01.9 → Day 2: when `git ls-remote` fails for any reason, a network error
  included, the dry run says "park: the project has no origin/main". Parking is the safe side;
  the reason may be wrong. The preflight can tell an unreachable remote from a missing `main`.
