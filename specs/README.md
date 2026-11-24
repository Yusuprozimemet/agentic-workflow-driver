# Specs

Spec-driven development. **No code without a spec. No spec without checkable acceptance criteria.**

## Workflow

1. Read the day spec against the code, and run every acceptance check on the code as it is.
   Fix what that turns up in a spec-change PR before any track starts.
2. Branch per track: `day-04/track-b-saved-jobs-tests`.
3. Build only what **In scope** lists.
4. Copy the acceptance criteria into the PR description and tick them.
5. The day is done when every box is ticked and **Verify** passes on `main`.

## Before the audit: the writer's self-check

The auditors caught about the same number of spec defects every Day (Days 9 to 12: 20, 10, 18,
24), each fixed one by one and never given back to the writer (#212, S4). These are the kinds that
recurred among those 72, counted from the Defect lines on 2026-11-16, most frequent first. Before
asking for the spec-auditor, go through the spec once per line and fix what it finds; say in the
spec-change PR which lines found something, so the next count can tell whether the auditor's
catches fall.

- [ ] **Cases left unsaid (13; D09.12, D11.14, D12.10, D12.21).** For each new behaviour, list its
      edge inputs (none, already done, resumed, failing twice, a second reader) and name the
      criterion or Out of scope line that covers each.
- [ ] **Claims about today's code (11; D09.17, D11.2, D12.1, D12.19).** For each statement of what
      the code does, uses or calls today, grep for it and cite the file and line.
- [ ] **The outside assumed (7; D09.6, D09.18, D10.11, D12.16).** For every behaviour of `claude`,
      `gh`, `git`, argparse or Docker the spec relies on, quote it from a run or its source in an
      `Assumed` line.
- [ ] **Tag or Red today wrong (7; D10.6, D11.9, D11.10, D12.5).** Run each `new` criterion's
      test against `main` as its track will start it, and paste what it reports as Red today.
      Take each test apart: one whose results are all true there, a "no ..." half above all,
      is a `hold` of its own (the spec-auditor's check 8), in a fix written after the audit too.
- [ ] **A check that cannot fail (7; D11.7, D11.13, D12.4, D12.18).** For each criterion, say which
      test fails under its named break, and why it cannot pass with the break in. A criterion
      whose commitment is about behaviour is checked by running the behaviour, not by finding its
      sentence in a document (#212, S4).
- [ ] **Collisions (7; D10.4, D11.5, D12.2, D12.14).** Grep the tests, fakes, frozen files and break
      manifests for every name, key, line prefix and find the change adds or edits.
- [ ] **Output with no source (6; D09.3, D11.3, D11.4, D12.9).** For each value a criterion's
      output names, name the function and line that produces it.
- [ ] **Wrong cross-references (6; D10.3, D11.1, D11.18, D12.24).** Run `behaviour-index.py` and
      `plan-links.py`, and re-read each cited criterion, hand-off or Note at its source.
- [ ] **What reading cannot settle.** A Day whose behaviour needs Docker, a real `claude -p` or
      GitHub (Day 10: the spec-auditor caught 42%, four spec-change PRs) plans those live checks
      into Track 0, so the environment's surprises show up first.

## Reviewing a track's diff

The main session's review of the implementer's diff caught 7 defects in 12 Days; 48 others whose
cause was the code were caught later, by a break (16), the implementer itself (9), a test seen red
(3), the close or an escape (#212, S5; counted 2026-11-16). Ask these of every track's diff
before running the breaks, most frequent first, and record what the review catches as
`found: review`. From Day 13 the **track-reviewer** agent answers them first, from a fresh
context, and checks each claim of the PR against the diff; what it catches is
`found: track-reviewer`, and `found: review` stays the main session's own reading after it:

- [ ] **Timing (10; D10.18, D11.29, D12.35, D12.39).** Does a new or touched test depend on a poll,
      a sleep, an exit code read too early or a wall-clock bound? It passes 10 of 10 under
      `test-parallel.py --repeat 10` in a full run. `pre-push.py` runs each changed test file 5
      times inside the whole run (`--repeat 5 --of <files>`); 10 is still the review's own run.
- [ ] **Red for another reason (9; D05.7, D07.29, D10.14, D10.22).** On `main`'s code, does each new
      test fail by an assertion, for the reason the spec gives, and not by an error in setup?
- [ ] **A branch no test sees (8; D05.3, D06.6, D07.28, D12.38).** For each branch the diff adds,
      which assertion fails if it is deleted or short-circuited?
- [ ] **A report that differs between runs (7; D04.10, D05.8, D10.15, D12.32).** Could any failure
      message hold a uuid, pid, hash, absolute path, path separator or set order? `seen-red.py`
      refuses the first four, and "[N chars]", in the lines `main`'s code fails by; a break may
      reach another assertion, so read the rest.
- [ ] **Collisions (3; D09.25, D09.28, D11.28).** Are changed signatures, new module names and
      edited expressions grepped against their callers and every Day's break finds?
      `brief-check.py` names the callers a brief misses.

## Kinds that came back

Each kind below came back at least once: 32 Defect lines carry `same-as:`, and the work itself
(`found: self`, `review` or `Track <X>`) caught 74, outside any gate (#212, S13 and S14; counted
2026-11-16). The gate named is what now catches the kind before a person has to notice it. A
kind marked "none" needs its own gate if it comes back again.

| Kind | Lines | Last | Gate now |
|---|---|---|---|
| A break's report differs between runs or machines (pid, uuid, time, hash, "[N chars]") | D03.17, D04.6 and 9 more, D12.26, D12.32, D12.37, D12.40 | Day 12 | `break.py` refuses the report; `seen-red.py` refuses the same in the red, at the track's start, before the code |
| A report holds Windows-only text | D06.23, D07.40, D08.83 | Day 08 | "A track's breaks replay", on Linux |
| Git Bash rewrote a `/path` argument | D05.5, D10.17, D11.22 | Day 11 | `break.py` refuses it (this rung's PR) |
| A multi-line find on a CRLF tree | D08.68, D08.72 | Day 08 | `break.py` writes it in the file's endings |
| A test fails on and off under load | D07.27, D08.76, D10.18, D11.25, D11.29, D11.32, D12.34–36, D12.39 | Day 12 | `pre-push.py`, "Tests": the test files a branch changes run 5 times inside the whole run; "Timing" above |
| A Red today the code no longer gives, or a test of a `new` criterion that passes at its track's start | D03.14, D06.10, D06.16, D06.20, D06.21, D09.26, D10.12, D10.13, D11.19, D12.25 | Day 12 | the spec-auditor's check 8, one line for each test, and its recheck of what the spec change rewrote; `seen-red.py --expect` at the track's start |
| A test the spec does not list reads what the Day changes | D07.25, D11.20 | Day 11 | the spec-auditor's check 14 |
| Red by an error, not an assertion | D07.29, D07.32, D08.67, D10.14, D12.33 | Day 12 | `seen-red.py --expect`; "Red for another reason" above |
| A PR over 400 changed lines | D06.5, D07.15, D07.17, D07.20, D07.33 | Day 07 | `pre-push.py`, "Diff stays reviewable" |
| A brief names a name's wrong home or misses a caller | D07.24, D08.77, D09.28 | Day 09 | `brief-check.py`; the track-reviewer, on the brief |
| A brief's fake or expected count is wrong | D08.74, D09.22, D09.23, D11.24 | Day 11 | the track-reviewer, on the brief, before the implementer starts |
| A branch no test sees | D07.21, D07.28 | Day 07 | "A branch no test sees" above |
| A new name collides with an old one | D09.25, D11.28 | Day 11 | `brief-check.py` callers; "Collisions" above |
| Evidence worded so the replay cannot read it | D10.26, D11.33 | Day 11 | `close-evidence.py --rehearse` |
| A branch started from a stale `main` | D06.7, D06.9 | Day 06 | none |
| Output crashed on the cp1252 console | D02.11, D12.30 | Day 12 | none |

A repeat's text names what failed, its cause and the Day that made it, as a line without
`same-as:` would: `relabel.py` gives the blind rater only "It repeats a defect recorded on Day
NN", and Day 12's three repeats that named neither (D12.34 to D12.36) made 9 of its 12
disagreements (#212, S22).

## Size of change

Take the lowest rung that qualifies, and say which in the PR.

| Rung | Branch | Qualifies | Keeps |
|---|---|---|---|
| area branch | `<area>/<slug>` | no product behaviour changes: kit tooling, docs, dashboard, CI, plan; a fix that changes only tests (a flaky test made steady), which has no `new` criterion for a short spec to hold (#222) | the branch and title rules, the diff limit, a seen-red test and a `broken:` line when the PR has a check |
| short spec | `change/<slug>` | one product behaviour, one PR, no contract test, frozen file or `Replaces:` | `S-<slug>.N` criteria tagged `new` or `hold`, seen red, breaks, `Defect` lines in its Notes, the behaviour index, the replay |
| day spec | `day-NN/...` | plan work, and anything the rows above exclude | the auditors, tracks, the close, the blind relabel, the replay |

The areas are those `scripts/pr-names.py` accepts (`workflow`, `tooling`, `dashboard`, `docs`,
`specs`, `plan`, `ci`), plus any the project file lists. A docs-only area PR with no check
records `broken: none`.

## Short specs

For one small behaviour change outside the days that fits one PR and touches no contract test
or frozen file, use a short spec. Do not use one for work covered by a day's criteria or for a
change needing a `Replaces:` line. Use the day workflow for those.

On `change/<slug>` (lowercase letters, numbers and single hyphens), write
`specs/changes/<slug>.md` using [`_short-template.md`](_short-template.md). Its criteria use
`S-<slug>.N` IDs, `new` or `hold` tags and `Test:` fields, as in a day spec. Spec and code
land together: no separate spec-change or closing PR. Put the `seen red:` line and the
`broken:` lines in the PR. Run `python scripts/track-red.py --branch change/<slug> --runner
<runner>` (the project's: `unittest`, `pytest`, `maven` or `npm`) to check each new criterion's
test against base code and the head; CI runs it when `TRACK_RED_RUNNER` names the runner, and
fails a `new` criterion when unset. Hold checks must also
be broken on purpose as in the day rules below, and the PR commits their break manifest as
`specs/breaks/<slug>.json` ([Evidence at the close](#evidence-at-the-close)): after the merge,
the Evidence replay replays the short spec at the merge of `change/<slug>`.
Before opening the PR, read the saved spec as UTF-8 and inspect its punctuation, including
any `?` where a dash or arrow was intended.
Tick each criterion in the same PR once its seen-red or broken evidence is in the PR body.
Record each defect found along the way in the spec's Notes, one `Defect` line each, as the day
rules below say; `made:` is `none`, since the work is outside any day.
Ticked short-spec criteria join the behaviour index; a later day replaces one with
`Replaces: S-<slug>.N`.

## Rules

- **The spec is the contract.** Found work outside it? Add a line to that day's *Notes*
  and raise it. Do not widen the PR — CI rejects diffs over 400 lines.
- **Criteria must be checkable by someone who did not write the code.**
  "Auth works" is not a criterion. "`POST /api/auth/login` returns 200 with a
  `Set-Cookie` containing `HttpOnly` and `SameSite=Lax`" is.
- **Every criterion is `new` or `hold`, and every check has been seen to fail.** A check that
  cannot fail proves nothing, and in jobmatch-microservices, Phases 0 and 1 had three kinds of
  them: a CI gate that never ran the integration tests (Day 02), a verify command that ran no
  tests (Day 08), and greps for TODO markers that did not exist, so the criterion ticked itself
  (Days 08 and 09).
  - `new` is behaviour that does not exist yet. The check must fail on today's code, and the
    spec says how ("the grep finds two"). A `new` check that passes before the work is wrong.
    The track PR that adds its test runs it on the code before the day (the code change
    stashed, CLAUDE.md "The implementer") and says what it reported, "FAILED (failures=2)";
    the closing PR copies it into the Evidence as "seen red first on `<sha>`'s code". In
    wordtally, Days 4 and 5 recorded their breaks but not this, and each close had to run it.
    `scripts/seen-red.py` does that run for tests under `tests/` (CLAUDE.md "The implementer").
    Give every `new` criterion a `Test:` field with backticked test names immediately after
    the colon, for example Test: `ExampleTest.test_new_behavior`. Replace the template's
    example with a real test. Separate multiple names with commas or "and". `Evidence:`
    records the result; it does not replace `Test:`. Name the criterion IDs in the owning
    track's Work cell (for example `C01.1` or `C01.1–C01.3`); with one track, it owns all criteria.
  - `hold` must stay true through the change: contract tests passing unedited, a statement
    count. It passes before and after, so passing says nothing. Break the code on purpose once,
    watch the check fail, record what it reported, and revert. In jobmatch-microservices, Day
    08 did this with a per-posting loop: the query-count test failed with 2, 21 and 25
    statements.
  - The proof goes in the PR that first runs the check: the spec-change PR if the check exists
    already, the track's PR if a track adds it (a Track 0). The closing PR links it when it
    ticks the box.
  - The record is one line of its own: `broken: <what was broken> → <what the check reported>`,
    or `broken: none → <why>` in a PR that broke nothing. The PR that ran the break carries it
    in its description; the closing PR copies it under the criterion it ticks. `spec-drift.py`
    reads no other wording as a break. `scripts/break.py` runs one break and
    prints the line.
  - A ticked criterion carries its evidence under it, each piece with the PR it landed in; a
    copied `broken:` line ends with the PR that ran it:

    ```
    - [x] C01.2 **hold** — <the criterion>
      Evidence: `CliTest.test_counts` (#4); `python -m unittest discover -s tests` (#4).
      broken: the total left out → AssertionError: 2 != 3 (#4)
    ```
  - A grep is broken both ways: once with the thing it looks for put back (it must find it),
    once with a near miss it must not match (a longer name, a fully qualified form, a comment).
    In jobmatch-microservices, two of the paper's escapes were greps that matched too much or
    too little (D22-017, D23-028).
  - A check that diffs against a base names a fixed SHA, `main` before the day, never `main`:
    once the track merges, `main` is the change, the diff is empty, and the check ticks itself.
    In wordtally, Days 2 and 3 both wrote `main` first.
  - A check of JSON output compares the parsed object, not the string: on Windows a path in it
    has its backslashes escaped (wordtally, Day 5).
  - A check whose break bites on one system only (a carriage return on Windows) says so, and
    that a local run there guards it, not CI: CI's Linux run passes either way. In wordtally,
    Days 2 and 4 had one each.
  - A break's report must be one any run prints again, on Windows and on Linux: no pid, session
    id, commit hash, time, temporary name, absolute path or path separator. The test prints a
    fixed word in its place (`<uuid>`, `<head>`). Here, up to Day 7, 21 Defect lines were
    reports that did not replay, 12 of them the same problem come back (D03.17 to D07.40).
    `scripts/break.py` runs the check twice with the break in and refuses a report that differs
    between the runs, or that holds a pid, a uuid, a commit hash or an absolute path, a
    fixture's fixed one included: it cannot tell that from a real one.
  - Red today is the failure at the start of the criterion's track, on `main` with the tracks
    before it merged, not on the day the spec was written: an earlier track that adds the
    module or the argparse choice changes it (D06.16, D06.20). A behaviour an earlier track
    already makes true is a `hold` (D03.14).
  - What the spec takes `gh`, `git`, the `claude` CLI or the operating system to do is an
    `Assumed` line in its Notes, with the command that shows it and what it printed, or who
    runs it and before which track when the auditor cannot (a command that writes). Read from
    source and never run, three such claims were wrong or unchecked on Days 5 and 6 (D05.12,
    D06.13, D06.14).
  - The closing PR copies breaks; it does not run the first one. A criterion whose only
    `broken:` lines the close itself ran was a check no track had shown can fail: record it as a
    `Defect` (`found: close`). In jobmatch-microservices, four of the paper's six spec escapes
    were these. After the merge,
    the dashboard says so on each one's tile, in "Can we trust it?".
- **A contract test's timing is part of what it expects.** A contract test (`ContractTest`, from Day 1) is frozen in its expected values and in when it expects them. One that asserted
  an effect at once and now waits for it, or waits longer than it did, expects something else,
  even with every value unedited. In jobmatch-microservices, Day 25 did this to
  `AccountDeletionIT`: the saved jobs came to go by the `user.deleted` event,
  the test came to poll apps_db for 10 s, and deletion became eventually consistent through the
  public API, a `savedCount` that counts a deleted user's saves for a few seconds. The edit was
  approved, but read as values only, and no test asserted that count until #441 (paper, §4.1).
  So a new or longer wait, poll bound or timeout in a contract test is a departure: the
  spec-change PR names it before the work, with the bound and what the API shows until it
  passes; the maintainer approves it; and a test outside the contract tests
  pins that public effect within the bound, as, in jobmatch-microservices,
  `SavedCountAfterDeletionIT` does. A wait raised to quiet a flaky test is
  the same change.
- **Tracks and days run in order.** Branch each track from fresh `main` after the previous
  track merged; never stack branches. Track 0 lands first. Dependencies may change the table's
  order; explain that in the PR. Day N assumes N-1 is merged.
- **Record every defect in the day's *Notes* when it is found**, one `Defect` line each, with
  an ID and three fields:
  - the ID, after `**Defect**`: `D<NN>.<n>`, the day's defects numbered from 1 in the order they
    are written (`- **Defect** D28.1 — found: …`). A short spec's Defect lines take none.
  - `found:` where, exactly one of `auditor`, `spec-change PR` (before any code);
    `track-reviewer` (the agent's reading of a track's brief or diff, from Day 13), `review`,
    `seen red` (a new test that passed on `main`'s code), `break on purpose`, `self`, `Track <X>`
    (before merge); `close`, `rehearsal` (the close's rehearsal failed, before its merge),
    `evidence replay` (the replay after its merge failed), `dashboard`, `Day <NN> review` (after
    the track merged: an escape). The list is closed: `spec-drift.py` prints any other value as
    "not on the list". It reads `self` and `Track <X>` as one stage, the work, and
    before Day 12, when `evidence replay` named both replays, reads that value as "unsplit". It
    counts, per Day, the Defect lines per criterion, the late ones (any stage after the two
    before any code) and the escapes, and the blind rater's agreement per tag
    (`defect_counts`). The dashboard sets the defects each gate found (`auditor`, `seen red`,
    `break on purpose`, `evidence replay` with `rehearsal`, and the hooks' refusals) beside the
    tokens it cost (`gates.json`).
  - `cause:` exactly one of `spec` (wrong, missing a case, or not meetable as written),
    `implementation` (the spec was right, the code did not do it), `process` (the workflow and
    the record around the code: branch names, Jira keys, a break run wrong, a track announced
    and never opened) or `environment` (tooling, CI, the machine, a library).
  - `made:` the day whose work holds the defect, merged or not (`Day 21`, or `none` for work outside any
    day). When it is not this day, the defect is an escape from that day, whatever `found:` says.
  - `catchable:` the earliest layer that could have caught it, one of the `found:` values above,
    after `made:`: the same value as `found:` when no earlier layer could have (`found: close ·
    … · catchable: auditor` says the spec-auditor could have counted it). From Day 16 on, every
    Defect line has one; earlier Days' lines have none and are not given it. `spec-drift.py`
    counts, per Day, the lines an earlier layer could have caught, and reports a value off the
    list; `relabel.py` strips it with the tags.
  - `same-as:`, only when the defect repeats one an earlier Defect line records: that line's ID
    (`same-as: D21.2`), after `made:` and before the text. `scripts/spec-drift.py` counts it as
    a recurrence, ringed in the dashboard's graph of defects, and reports an ID it cannot place
    (malformed, unknown, used twice, or not earlier); `scripts/relabel.py` strips it with the
    tags, so the blind rater does not read the earlier defect's.

  A pull request made to stop a kind of defect coming back (a gate, a rule, a brief's
  checklist) adds its own row to [`fixes.json`](fixes.json), `{"pr": N, "stops": [IDs]}`,
  with the IDs of the Defect lines it names. `spec-drift.py` reports a row it cannot place,
  and counts, per fix, the times its problems (their `same-as:` chains) happened before the
  first Day whose spec merged after it, and from that Day on.

  Two tags are easy to get wrong; in wordtally, Days 1 and 3 got both wrong and Day 2 the
  first, and the blind rater's pass corrected each:
  - A defect caught in the spec-change PR, before any code, is `found: spec-change PR`, even
    when the session that wrote the spec caught it itself: a break run with the wrong `bash`
    and run again before the PR opened. `self` is for the implementer or the main session
    catching its own code before merge.
  - A defect in the implementer's draft, caught by its own test run before it reported, is
    `made: Day NN`, this day, not `none`: the draft is the day's work, merged or not.

  One line per problem: the same kind of problem in two PRs is two lines, a review of seven
  drafts is as many lines as it finds problems, and an auditor's three findings are three lines
  (wordtally, Day 2, wrote them as one). In jobmatch-microservices, the paper had to
  decide all three of these after the data (its §5.3); deciding them on the day is cheaper. A
  track whose code the main session rewrote beyond review fixes gets a `Rewrite` line. In
  jobmatch-microservices, these are the counts `docs/paper/success-criteria.md` judges H1–H3 by; its
  amendment maps `process` and the `found:` values above.

  The Defect lines are the one record; the close's views of them are printed, not written:
  `python scripts/close-views.py specs/day-NN-slug.md` prints the Defects bullet of the Day's
  entry in `docs/lab-notebook.md`, its "Escapes per day" cell and the closing PR's "## Defects"
  section, counted as `spec-drift.py` counts them. Paste them unchanged; a tag changes in the
  Notes, and the script runs again. Written by hand, Day 12's entry counts 4 escapes and its
  Notes hold 5 (D12.39).

  At a phase's last close, a reader who wrote none of it labels the defects of every Day of the
  phase again, blind ([`scripts/relabel.py`](../scripts/relabel.py), the `defect-rater` agent):
  the tagger has also written the work, and in jobmatch-microservices, on Days 21–28 a blind
  rater disagreed with 11 of 82 causes and 16 stages, mostly defects made on one day and found on
  another. Once a phase, not at every close: the rater reads a phase's Days in one run, and the
  defects made on one Day and found on another sit in the same file. `relabel.py compare` prints
  one block per Day, headed `Day NN:`, and the closing PR pastes them unchanged: the dashboard
  counts each Day from its own block. The closing PR lists each disagreement and decides it: the
  tag kept, with the reason, or changed in that Day's Notes. A tag is never changed without a
  line in the PR. Days up to 15 were relabelled at their own close.
- **IDs.** Each criterion starts with its ID, `C28.3` for Day
  28's third, and keeps it when others are added or dropped. Each item a day leaves for later is
  a `Hand-off` line in its Notes with an ID, `H28.1`, and the day or the maintainer it goes to.
  The receiving spec picks it up by citing the ID; naming the day does not. `spec-drift.py`
  lists what no later day picks up, and any track a PR announces ("E1c, next") that no branch
  ever names.
- **When a criterion changes behaviour in force, name what it replaces.** Put
  `Replaces: C12.3 — was: <the old behaviour, quoted or in one sentence>` inside the new
  criterion's block, in the spec-change PR like any criterion wording. A reviewer then sees the
  old and the new behaviour, and `python scripts/behaviour-index.py` retires the old criterion
  once the new one is ticked; a `Replaces:` line without an ID or `— was:` fails it. Never edit
  the replaced criterion's file.
- **From Day 11, each criterion names what of `plan.md` it serves.** `specs/plan/promises.json`
  lists the plan's commitments (P01 to P69, N01 on), each with a quote that stands in
  `plan.md`. Under each criterion, before its `Evidence:`, put one `Plan:` line:
  `Plan: P27 "words quoted from P27"; N03 "words quoted from N03"`, each ID followed by words
  copied literally from that commitment's `text` (or its `change`), or `Plan: none — <why>`
  when it serves none. It may wrap onto indented lines. `python scripts/plan-links.py` (CI:
  "Plan links quote the plan's words") fails a criterion of Day 11 or later with no `Plan:`
  line, two of them, one in neither form, an unknown ID or a quote it cannot find. Days 1 to
  10 are linked in `specs/plan/links-days-01-10.json` instead; their specs are not edited. A
  `Plan:` line is criterion wording: write and change it in the spec-change PR. The dashboard's
  plan graph will draw from these lines.
- **Overdue commitments come before additions.** A commitment is overdue for a Day when its
  `owner_day` in `specs/plan/promises.json` is earlier than that Day and no criterion of an
  earlier Day names it (in a `Plan:` line or `specs/plan/links-days-01-10.json`). A Day's spec
  takes the overdue commitments before any commitment added since (the `N` IDs), or says why
  not in one line under its Goal: `Overdue: P25, P37 wait — <why>`. Day 11 spent 21 of its 23
  criteria on additions while eight commitments came due uncovered (#211, N6).
- **At most 24 criteria a Day.** A plan change that would give a Day more is split over two
  Days, and the first Day's spec names the second and what it takes. Days 1 to 12 had 7 to 23,
  except Day 10's 32, where a plan change landed at once (#212, S3).
- Changing a spec is normal. Change it in a PR *before* the work, not after.
  Criterion wording, tags and IDs change only in a spec-change PR on `day-NN/spec-<slug>`.
  CI's "Criteria keep their wording" job enforces this against the branch's merge base on
  every other PR, including tracks, closing PRs and tooling PRs.
- **Every spec-auditor finding ends one way, one line each, in the spec-change PR.** List each
  finding of the day's spec-auditor report, a hand-off it marked MISSING included, under
  "Why this approach" as `<N>: <the finding's one line> → <ending>`, with exactly one ending:
  - `fixed`: this spec-change PR changes the spec (or names the PR that already did);
  - `known limit: <reason>`: the spec stays as it is, and its Notes record the limit;
  - `maintainer action: <what>`: outside the repository, on the maintainer's own accounts;
  - `rejected: <reason>`: the maintainer's call, with their reason.

  These are the four endings jobmatch-microservices gave its end-of-phase audit findings. A
  report with no findings is one line, `Auditor findings: none`. Nothing counts the endings
  yet: the dashboard waits until there are spec-change PRs to count.
- Specs written before the `new`/`hold` rule get their criteria tagged in that day's
  spec-change PR, when the spec is read against the code.

## Evidence at the close

The closing PR ticks criteria with evidence and copies the earlier PRs' breaks. Commit a break
manifest at `specs/breaks/day-NN.json`: a JSON list with one object per recorded mutation.
Each object has `what` (the text between "broken:" and the last arrow), `file` (a path from the
repository root), `find`, `replace` and `command` (an argument list run from that root):

```json
[{"what":"the total left out","file":"app.py","find":"return total","replace":"return 0","command":["python","-m","unittest","tests.test_app.CliTest.test_counts"]}]
```

Use the actual arguments from the earlier break, not this illustrative mutation: `break.py`
prints them as `manifest: {...}` above its `broken:` line, and a track PR records that line
beside the `broken:` line, so the close copies each entry instead of rebuilding it from the
merged code. Copy it from the raw body (`gh pr view <n> --json body`), not the rendered page,
which drops a level of backslashes, and check that each entry parses. A break run with `--cwd`, or on a file outside the directory it ran from, prints
`manifest: none` with the reason: run it from the repository root. `break.py --record` writes
the entry into the manifest itself (`specs/breaks/day-NN.json` on a `day-NN/` branch,
`specs/breaks/<slug>.json` on `change/<slug>`, or the path given), with two more keys the
replay ignores: `report`, the `broken:` line's report, and `blob`, the `git hash-object` of the
file before the break. A second run with the same `what` replaces its entry. From Day 12 a
track records each break so and commits the manifest with its code: `python scripts/break-lines.py`
prints the `manifest:` and `broken:` lines of the entries the branch added, to paste into the PR
body unretyped, and CI's "A track's breaks replay" runs the recorded entries in place of a body
line of the same `what`. At the close, `python scripts/break-lines.py --spec specs/day-NN-slug.md`
fails a spec `broken:` line with no entry, a name recorded twice, or a report other than the
recorded one, and prints each recorded entry the spec does not cite as the line to put under its
criterion; it runs nothing, which the rehearsal does. Optional
`at` names the historical commit when the close no longer contains the text to edit;
`passes: true` marks a near miss that must pass with the mutation in; `expect_stdout` holds
the regex the break gave `break.py --expect-stdout`, for a check judged by what it prints
(`grep -c`): without it, the replay goes by the exit code and that check passes with the
break in. On Windows, `bash` in
the command means Git's Bash. See [`scripts/evidence.py`](../scripts/evidence.py) for the format.
Write `[]` when there are no mutations to replay, and retain the reasons for inapplicable checks.
Give each break a `what` of its own: the replay finds an entry by it, and fails a name recorded
twice. The `broken:` line's report may end in a PR number in brackets, "(#12)", and nothing
else: the replay strips only that, so "(close, D10.19)" makes the line differ. A break that
cannot replay (on another repository, or replaced by a later one) is written as a sentence
that says why, not as a `broken:` line.

**CI's Linux report is the one the record keeps.** When "A track's breaks replay" says a recorded
entry `differs`, it saves Linux's report as the run's `linux-reports` artifact:
`gh run download <run-id> -n linux-reports`, then `python scripts/break.py --take-reports
linux-reports.json` writes each into its entry, and `break-lines.py` prints the lines again. Its
output names both commands. Never retype a report into the record.

**A later PR re-records or retires an earlier Day's break.** CI checks every closed Day's in-force
break on every PR, and fails one whose find no longer occurs exactly once ("no longer applies";
its line names both commands). The fix lands in the PR that moved the code:

- **Re-record** when the break still makes sense on the new code: `break.py --record
  specs/breaks/day-NN.json` under the same `--what` and command, with a find that occurs once both
  here and at Day NN's close (the Day's replay runs the entry there; break.py refuses a find the
  close lacks). The entry replaces the old one. If its report differs from the Day's `broken:`
  line, change that line in the Day's spec too, and say so in the PR.
- **Retire** when no find fits both: `break.py --retire specs/breaks/day-NN.json --what "<what>"`
  pins the entry with `at`, the commit where HEAD left `main` (or `--at <commit>`), after checking
  its find occurs once there. It runs nothing. The Day's replay runs it there, and track-breaks
  reports it "pinned". The re-check after a merge still shows it as "break no longer applies":
  this code has no break proving the test, and the dashboard says so. A later re-record replaces it.

Either way, `python scripts/break-lines.py --spec specs/day-NN-slug.md` checks the Day's spec
against the record, and the PR says which breaks it re-recorded or retired, and why. A break
under a criterion a later Day replaced (`Replaces:`) is not checked, and needs neither.

A box the close leaves unticked needs its reason under it, indented like the criterion's other
lines: `Not proven: <why>`. The replay reports each unticked criterion as "not proven" and passes
it only when that line is in the spec at the closing commit; a line added to the spec since does
not count. For each ticked criterion it names what proved it: a test, a command, a break, or a
reader. One with none of the first three fails unless its `Not proven:` line says why a reader
judged it instead (`Not proven: a reader compared the page with the design`).

The dashboard counts a ticked criterion's Evidence only when it cites a PR (`#n`) **and** names
a test, a backticked `git`, `python`, `diff`, `grep` or `bash` command, or "the command above"
(or "the commands above") when the criterion's own text holds such a command. "The command
exited 0" names none, and a project's own CLI is not read: write "the commands above" and keep
the command in the claim. It reads a red only from a line holding "seen red" or a `broken:`
line: "Red:" is not read. Anything else is flagged "No evidence and PR cited together" or "No
seen-red or broken line" (bearing D12.11 to D12.13, three criteria worded so in one close).

Verify is replayed by CI after the close, in a scratch worktree of this repository. A command
that needs something CI cannot reach (another repository, a local checkout, a browser) fails
there: put it in a Note and run it by hand, and leave Verify to commands that run from the
repository alone (bearing D12.10: four such lines failed the replay).

After the closing PR's "merged", CI runs the Evidence replay workflow automatically. Check the
run for that merge commit with `gh run list --workflow evidence.yml --commit <sha>`, then
`gh run view <run-id> --exit-status`. Require a completed successful run before the next step;
a failed, missing, pending or cancelled run blocks advancement. Inspect the checks and retain
the evidence artifact. For a local run on fresh `main`, use
`python scripts/evidence.py specs/day-NN-slug.md --ref main --json evidence.json`.
Retain the report and inspect each result: named tests are checked for existence under `tests/`,
Verify commands are executed, and recorded breaks are replayed at historical commits.
Replay finds a **merged closing commit**; the post-merge gate cannot block its own closing PR's
merge. What can is the rehearsal: on a pull request the same check, "A closed day's evidence
replays", replays a closing branch (`day-NN/close-the-day`, `change/<slug>`) as its merge would
be, and passes any other branch with "not a closing branch"; required in branch protection, it
blocks a close whose evidence does not replay. Run it before opening the PR, on the committed
branch: `python scripts/close-evidence.py --rehearse day-NN/close-the-day`. A rehearsal does not
replace the replay after the merge: `main` can move in between, and a squash merge is found by its
title, which a rehearsal never sees. The workflow's manual dispatch accepts an optional
day number to replay a previously closed day on `main`. A short spec replays the same way at its
`change/<slug>` merge (or the squash that added it), its breaks in `specs/breaks/<slug>.json`:
`python scripts/evidence.py specs/changes/<slug>.md --ref main`.

Keep three evidence states separate: **missing** means required evidence or its report is absent;
**stale** means a saved report's spec, break inputs or closing commit no longer match;
**failed** means replay ran and a check did not hold. None permits advancement. Execution errors
also block advancement; an explicit inapplicable result needs its reason. A historical replay
does not replace the project's tests on current code.

## Layout

```
specs/
  README.md        this file
  _template.md     start a new day from this
  day-NN-slug.md   one file per day
```

## Map to plan.md

| Days | Phase | Outcome | Status |
|---|---|---|---|
| 1-2 | 0 — The dry run | the driver names the next action on a project and starts nothing | Days 1-2 closed |
| 3-8 | 1 — Level 1 | one day of a project runs with the maintainer only merging and answering parks | Days 3-8 closed |
| 9- | 2-3 — Level 2, Level 3 | merges without the maintainer; phases chain | after the stop at Day 8 |

## Provisional specs

Day 1 was written on 2026-11-06 in the kit, before this repository existed: the spec-auditor read it against this repository's code before its spec-change PR.

## Stopping points

- Day 2 ends Phase 0: the dry run and the preflight, which start nothing.
- Day 8 ends Phase 1 and is a stopping point: the level 1 trial's record.
