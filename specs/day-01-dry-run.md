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
- Tests under `tests/`, run with `python -m unittest discover -s tests`.

The sentences, as `next_step()` returns them in the kit at `393dda6`:

| The sentence | Kind | Branch prefix, or the park's reason |
|---|---|---|
| "Waiting on #7 Day 02 track A: counts" | wait | |
| "Every day is done." | park | "every day is done" |
| "No day specs yet: fill in plan.md, then write the first day's spec (specs/README.md)." | park | "there are no day specs" |
| "Day 05: write its day spec (plan.md lists it, specs/ has none)", and the same with a quoted plan item in the brackets | park | "Day 05 has no spec, and the kit names no branch for writing one" |
| "Day 04 is done: stop and evaluate before going on (plan.md)" | park | "a stopping point after Day 04" |
| "Day 03: read the spec against the code, then the spec-change PR" | step | `day-03/spec-` |
| "Day 03 Track B: C03.2–C03.3" (any text after the colon) | step | `day-03/track-b-` |
| "Day 03 Track C: announced in #9, no branch names it" | park | "Track C of Day 03 was announced in #9 and has no branch" |
| "Day 03: the closing PR" | step | `day-03/close-the-day` |
| anything else | park | "the next step is not one this driver knows" |

The line the dry run prints is one of "wait: #12, #13" (the numbers of `now.open_prs`),
"start: " followed by the sentence, or "park: " followed by the reason.

## Out of scope
- Starting a session, the driver's settings, the halt — Days 3 and 4.
- The run log, the lock, a live process of an earlier session — Days 4 and 7.
- Parks as issues, and whether a phase's end was already answered — Day 5.
- Bringing a clean tree on another branch to `main` — Day 6.
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
- [ ] C01.1 **new** — `classify()` gives every sentence in the table of "In scope" its kind, its
      day, its track and its branch prefix or reason, and every sentence the repository's own
      `scripts/spec-drift.py` `next_step()` can return is one of them. A track's letter is
      lowered in the prefix (Track B: `day-03/track-b-`; Track 0: `day-03/track-0-`). The
      "announced in" sentence is a park, not a track's step.
      Red today: the tests error, there is no `driver` package.
      Test: `ClassifyTest.test_each_sentence_of_the_table`,
      `ContractTest.test_every_sentence_next_step_returns_is_known`.
- [ ] C01.2 **new** — A sentence that is not in the table parks with "the next step is not one
      this driver knows": "Day 3: the closing PR" (one digit), "day 03: the closing PR", "Day 03:
      the closing PR today", "Day 03 Track : x" and the empty string. Only a track's sentence
      takes free text, after its colon.
      Red today: the tests error, there is no `driver` package.
      Test: `ClassifyTest.test_near_misses_are_unknown`.
- [ ] C01.3 **new** — A phase's end parks. With `order` 1, 2, 3, Days 1 and 2 in Phase 0 and
      finished, Day 3 in Phase 1, the spec step of Day 3 gives "the end of Phase 0: Day 03 starts
      Phase 1". The spec step of Day 2, the spec step of the first day of `order`, and a track's
      step or the close of Day 3 give no phase's end. When Day 3 or the day before it in `order`
      has no phase, the spec step of Day 3 gives "Day 03 or the day before it names no phase".
      Red today: the tests error, there is no `driver` package.
      Test: `PhaseEndTest.test_first_step_of_a_new_phase_parks`,
      `PhaseEndTest.test_same_phase_first_day_and_later_steps_do_not`,
      `PhaseEndTest.test_missing_phase_parks`.
- [ ] C01.4 **new** — `decide()` returns the first of these that applies, and its line:
      open pull requests 12 and 13, "wait: #12, #13", whatever the tree is;
      two paths in `git status --porcelain`, "park: the project's tree is not clean (2 paths)";
      a clean tree on `day-03/track-b-counts`, "park: the project is on day-03/track-b-counts,
      not on main"; `main` and the remote's `main` at different commits, "park: main is not
      origin/main"; a park from C01.1 to C01.3, "park: " and its reason; a branch of the step
      (C01.5); otherwise "start: " and the sentence.
      Red today: the tests error, there is no `driver` package.
      Test: `DecideTest.test_first_reason_wins`.
- [ ] C01.5 **new** — A step with a branch of its own already there never starts. For the step
      "Day 03 Track B: C03.2–C03.3", a local branch `day-03/track-b-old`, the same name on the
      remote only, or `day-03/track-b` gives "park: a branch of this step exists:
      day-03/track-b-old" (or the name found). The branches `day-03/track-bb-x`,
      `day-13/track-b-x`, `day-03/track-a-x` and `day-03/spec-x` do not: the step starts.
      Red today: the tests error, there is no `driver` package.
      Test: `DecideTest.test_a_branch_of_the_step_parks`,
      `DecideTest.test_near_miss_branches_start`.
- [ ] C01.6 **new** — `python run-steps.py --dry-run --project <path>` prints exactly one line
      on stdout, the action, and exits 0 for "start" and "wait" and 1 for "park". When the
      project cannot be read (no `scripts/spec-drift.py`, the script fails, or its JSON lacks
      `now.next_step`, `now.open_prs`, `order` or `days`) it prints nothing on stdout, one line
      on stderr that names what is missing, and exits 2.
      Red today: the command fails, there is no `run-steps.py`.
      Test: `DryRunTest.test_prints_one_action_and_its_exit_code`,
      `DryRunTest.test_unreadable_project_exits_2`.
- [ ] C01.7 **new** — The dry run starts nothing and writes nothing in the project. The only
      commands it runs are the project's `scripts/spec-drift.py` with `--out` and `--cache`
      outside the project, and `git` with `status`, `rev-parse`, `symbolic-ref`, `for-each-ref`
      or `ls-remote`. On a fixture project, `git status --porcelain --ignored` and
      `git for-each-ref` print the same before and after it.
      Red today: the command fails, there is no `run-steps.py`.
      Test: `DryRunTest.test_runs_only_reads`, `DryRunTest.test_project_is_unchanged`.

## Verify
```bash
python -m unittest discover -s tests
```

## Notes
- Provisional: written 2026-11-06 from the plan, before the repository exists. Its sentences and
  JSON fields were read from the kit at `393dda6`; the spec-auditor reads them against the
  repository's own copy first.
- `ContractTest` loads `scripts/spec-drift.py`, which imports `numpy`: the test needs it, as the
  kit's CI already does.
- The fixture project is built by the tests in a temporary folder: a git repository, a bare one
  as its remote, and a `scripts/spec-drift.py` that writes the JSON a test gives it. Write its
  files as bytes: on Windows, text mode adds a carriage return.
- By default `spec-drift.py` keeps its cache and its output in the project's folder, both
  ignored by git. C01.7 has the dry run pass both paths outside the project.
- Every criterion is `new`: nothing exists to hold. The track PRs record `broken: none` with the
  reason, and each shows its tests red on `main`'s code.
- **Hand-off** H01.1 → Day 5: whether a phase's end was already answered by the maintainer.
  Until then the dry run parks at every phase's end, each time it is asked.
- **Hand-off** H01.2 → Day 6: a clean tree on another branch is brought to `main` (the plan's
  "Recovery"). Day 1 parks on it, on purpose (the maintainer, 2026-11-06): the dry run moves no
  branch. Day 6 changes that part of C01.4 with a `Replaces:` line.
- **Hand-off** H01.3 → Day 2: the fields C01.6 checks become the preflight at `on`.
- **Hand-off** H01.4 → the maintainer: the step "write its day spec" is a manual hand-off for
  now (the maintainer, 2026-11-06). The kit names no branch for it; the driver parks on it and
  the maintainer writes the spec by hand.
