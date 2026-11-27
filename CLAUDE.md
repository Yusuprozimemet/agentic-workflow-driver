# Working in this repository

This repository builds `run-steps.py`, a driver that runs the kit's day loop on another project,
one `claude -p` session per step, parks for the maintainer when a step needs a person, one day
spec at a time, and records what each day turned up. Three layers have to agree:
[`plan.md`](plan.md) is the goal and changes rarely; the day specs in [`specs/`](specs/) are the
steps; the code is where the steps land. The spec rules are in
[`specs/README.md`](specs/README.md) and the template in [`specs/_template.md`](specs/_template.md).
This file is the principles, the working order and the lessons the rules do not state;
[`docs/procedure.md`](docs/procedure.md) holds the detail of each step, read when the step comes
up, and [`docs/workflow.md`](docs/workflow.md) draws it.

**Source of truth, when they disagree:** the code on `main` for what the system does; the merged
spec for what a day promised; `plan.md` for the goal. The dashboard and memory only record
the others: correct them, never the other way round.

## Five principles

Every rule below is one of these applied. Where no rule speaks, act on them.

1. **See a check fail before trusting it.** A test that passes before and after a change proves
   nothing. A new test is seen red on `main` before its code, and a check is broken on purpose
   once (`seen-red.py`, `break.py`). Four `new` tests were already green on `main` when their
   track's code was written, for nothing (D09.26, D10.12, D10.13, D11.19); hand-run breaks
   half-applied or never started the build. The checking agents are held to it too: an agent with
   cases has a count (`agent-cases.py`), and on the worst of three runs the merge reviewer gives
   the right verdict on 2 of its 10 cases and names 0 of 8 known faults, the spec-auditor names 30
   of 44 and the track-reviewer 9 of 21. A check that has not been measured is a hope.
2. **The writer is not the only checker.** The session that writes a spec or a brief has read
   past its own errors more than once, so a fresh context reads it: the spec-auditor the spec and
   its fixes (D10.12, D12.25), the track-reviewer the brief and the diff (D09.22, D09.23, D11.24,
   D12.33), CI and the reviewer the PR, and once a phase a model from outside the repository a
   few merged PRs ([`docs/outside-review.md`](docs/outside-review.md)). The counts above say none
   of them is enough alone.
3. **Decide the scope before building.** Take the lowest rung of the
   [size-of-change ladder](specs/README.md#size-of-change), run the gates that decide what a
   change may touch, and ask the maintainer once, early, for what is theirs to decide. The N1 fix
   found two such rules after building and lost about 25 minutes (#212, S23); on 14 Nov 21 area
   PRs merged and no Day moved (#212, S15).
4. **Output in the main session is paid for on every reply.** Every reply re-reads the whole
   conversation: in jobmatch-microservices 61% of the main sessions' context tokens up to Day 17
   were read after a session had passed 300k, and 29% over the whole project
   (`python scripts/token-usage.py --compare`). One session per step, small outputs, few replies.
5. **Record departures.** A criterion that cannot be met as written, a premise that looks wrong,
   a mistake of your own: say so in the PR and the Day's Notes, never deviate silently. The
   corrections are part of what this repository measures.

## Starting

A person or an agent new to this repository: read `plan.md`, then run
`python scripts/behaviour-index.py` to see what the system does now, then `specs/README.md`; run
`python scripts/spec-drift.py --out spec-drift.json` (it needs `numpy` and the `gh` CLI; or open
the dashboard) for the current day and next step; then ask for it, for example "start Day 12".
Nothing merges without the maintainer, and nothing starts after a phase ends until they say so.

**The merge gate is CI and the auditors; the maintainer's merge is a go-ahead.** CI's required
checks and the auditors' reports are what a PR must pass; the maintainer's "merged" says go
ahead, not that every line was reviewed by a person. Of the first 213 PRs, the median went from
open to merged in 4 minutes, CI included (#211, N3). So a PR body says what CI and the auditors
did not check, where a reader should look.

## A day, in order

Not every change is a day: take the lowest rung of the [size-of-change ladder](specs/README.md#size-of-change)
that qualifies (area branch, short spec, day spec) and say which in the PR.

**Run the gates before planning, not before pushing:** the ones that decide the rung and the
files a change may touch (`python scripts/invariants.py main HEAD` for frozen files, the rung's
own rules, `python scripts/plan-links.py`), and ask the maintainer once, early, for everything
that is theirs to decide (principle 3).

**While a Day is open** (its spec PR merged, its closing PR not yet), an area PR (`tooling/`,
`dashboard/`, `docs/` and the rest) opens only when it fixes what blocks the Day's next step: a
failing check, or a tool the step needs that is broken. Say in the PR what it unblocks.
Anything else waits for the close and goes into its Notes as a hand-off (`plan.md`, "Course
correction after Phase 2").

1. **Audit before writing anything.** On the first day of a phase, run the **plan-auditor**
   agent on the phase first: do the specs still add up to what `plan.md` wants from it, and
   does the code still match their premises? Then, every day, run the **spec-auditor** agent on
   the day: every check run on the code as it is, every `hold` tried to break, every claim
   counted. Both only report. Fix what they find in a **spec-change PR** first (a **plan-change
   PR** when the code shows `plan.md` itself is wrong, which should be rare):
   `day-NN/spec-<slug>`, titled `Day NN spec change: <what was wrong>`. Before opening it, send
   the spec-auditor again, with the word "recheck" and the criteria the fixes added, split,
   retagged or rewrote: a fix is spec text no auditor has read (D10.12, D12.25). Every criterion is tagged
   `new` (fails today; the spec says how) or `hold` (true today; broken on purpose once), and
   from Day 11 carries a `Plan:` line, the commitments of `plan.md` it serves or `Plan: none`
   (`specs/README.md`, "Rules"; `python scripts/plan-links.py` checks them).
2. **One PR per track**, each branched from fresh `main` after the previous one merged. Never
   stack branches. `day-NN/track-<letter>-<slug>`, titled `Day NN track X: <what it does>`. A
   Track 0 holds the tests that must pass before and after the change, and lands first.
3. **A closing PR:** `day-NN/close-the-day`. Tick each criterion with its evidence, add Notes
   to the spec, update the lab notebook, paste what `close-views.py` prints, commit the break
   manifest, and at a phase's last close relabel the phase's defects blind: the commands are in
   [The close, step by step](docs/procedure.md#the-close-step-by-step). Rehearse the replay
   before opening it (`close-evidence.py --rehearse`); after it merges, run `evidence.py` on
   fresh `main` and keep missing, stale and failed evidence apart, resolving each before
   advancing.
4. **After opening any PR, stop and wait for the maintainer to say "merged".** Do not start the
   next step, and do not start a new phase, until told.
5. **After a closing PR's "merged", check evidence before advancing:** run
   `gh run list --workflow evidence.yml --commit <sha>` for its merge commit, then
   `gh run view <run-id> --exit-status`. Require a completed successful run; a failed, missing,
   pending or cancelled run blocks the next step. Retain its evidence artifact.
   **After every "merged",** on fresh `main`, run `python scripts/spec-drift.py` and report the
   next step it prints (the merge rebuilds the
   [public dashboard](https://yusuprozimemet.github.io/agentic-workflow-driver/) by itself).
   **Then stop.** Tell the maintainer to start a new session (or `/compact`) for the next step,
   with a one-line prompt for it, and do nothing more in this one, after every kind of PR. A hook
   enforces it (`scripts/step-guard.py`): after a short "merged" it refuses subagents, edits,
   branches, commits, pushes and PRs until a new session, `/clear` or `/compact`. In bearing, the
   rule alone was read past twice in a row (bearing D01.23, D01.24).
6. **When a phase's last closing PR has merged,** in a new session after step 5, on fresh
   `main`: run the plan-auditor on the phase that just ended and on the next (at the end of
   Phase 3, the three end-of-phase auditors too); they read what merged, never the closing PR.
   Beside their report, give the maintainer the phase-end table
   (`python scripts/phase-table.py spec-drift.json --phase N`; it flags nothing, and its "after
   the close" is not an escape) and the outside review's prompt
   ([`docs/outside-review.md`](docs/outside-review.md)), for a model outside this repository.
   Report, and stop.

Tracks may run in a different order from the spec's table when one depends on another; say so in
the PR.

## One session per step

A step starts in a fresh session (principle 4): after step 5, the maintainer starts a new session
or `/compact`s, and `scripts/step-guard.py` refuses new work until they do. Nothing is lost: the
spec, `spec-drift.json`, this file and memory carry what the next step needs.
`python scripts/token-usage.py --simulate` prints what fresher sessions or capped tool results
would have saved on this machine's transcripts. Keep the main session's output small:

- Test runs and CI logs: filter to the failures and the counts (`grep`, `tail`), or have a
  subagent read them and return the summary. Never print a whole log or report.
- Replies are the cost, more than their size: batch independent calls into one reply, and
  checks into one shell command that prints one line per item. Wait for CI in the background
  (`run_in_background`) with `gh pr checks <n> --watch > <file>`, then print only the final
  `gh pr checks <n>`: never watch it in the foreground.
- Read the part of a file you need (`offset`/`limit`, `grep -n`), not the whole file, unless the
  step changes all of it. Diffs: `--stat` first, then the files that matter. Hooks refuse a
  whole Read of a file over 8,000 bytes and cut long Bash output
  ([The hooks](docs/procedure.md#the-hooks)).

## The auditors

`.claude/agents/plan-auditor.md` and `.claude/agents/spec-auditor.md`. Separate agents with their
own brief and a fresh context, so the session that implements is not the only one checking its
own specs (principle 2).

| When | Run | What it answers |
|---|---|---|
| first day of a phase, before anything else | plan-auditor | Do this phase's specs still deliver what `plan.md` wants, on today's code? |
| every day, before the spec-change PR | spec-auditor | Is every claim and check in this day's spec true, and can each check fail? |
| a phase's last closing PR has merged, on fresh `main` | plan-auditor | What did the phase change that the next one must know? |
| a stopping point `plan.md` names, before going on | plan-auditor, on the whole plan | Is `plan.md` still the right plan, and what has piled up that no day owns? |
| the closing PR of Phase 3 (level 3: phases chain) has merged, on fresh `main` | security-ops-auditor, agentic-engineering-auditor, architecture-auditor | Can the workflow take more autonomy safely; what does it show about agents; do its gates hold? |
| a phase's last close, after the Notes are written | defect-rater, on `relabel.py`'s blind file of the phase's Days | Does a reader who did not write the phase tag its defects the same way? |
| a phase's last closing PR has merged, beside the plan-auditor | a model outside this repository, given [`docs/outside-review.md`](docs/outside-review.md) by the maintainer | Would a reader with none of this repository's habits accept a few of the phase's merged PRs? |
| any time, by hand | either | "use the plan-auditor on Phase 3" |
| a PR edits a brief that has cases (`specs/agent-cases/`: the defect-rater, the track-reviewer, the spec-auditor, and the driver's reviewer in `rules/reviewer.md`) | `python scripts/agent-cases.py <agent>` | Does the agent still answer its known cases as it did? A count, not a gate: paste its lines in the PR, `--record` when the maintainer accepts it, and change cases only in a PR of their own ([Agents with cases](docs/procedure.md#agents-with-cases)). |
| only when the maintainer asks to improve an agent with cases | `python scripts/improve-loop.py <agent>`, which starts the **brief-improver** | Would a drafted brief, or one with an unused passage cut, answer more of the agent's known cases? Advice ([Agents with cases](docs/procedure.md#agents-with-cases)). |
| only when the maintainer asks for it by name | instrument-auditor | Is each view of the live page, those behind a button or a closed section included, true when recounted from git and GitHub, and what does it say needs fixing? "On the tooling": do the tooling scripts still enforce their rules? |

The instrument-auditor is manual only: no step of a day, no close, no phase end and no driver run
starts it, and a session does not start it on its own initiative. Its report is advice.

The plan-auditor and spec-auditor both check hand-offs: what earlier days' Notes and test
comments defer to a later day. Nothing else carries them forward, and that is where most gaps
have come from. The three end-of-phase auditors run on Opus, each from a fresh context, and read
none of the others' reports: their disagreement is part of the result.

"Read-only" is enforced as far as a hook can (`scripts/auditor-guard.py`): a command guard, not a
sandbox ([The hooks](docs/procedure.md#the-hooks)).

Their findings are advice to the maintainer. What becomes a PR is the maintainer's call.

## The implementer

`.claude/agents/implementer.md`, on Opus (`claude-opus-5-5`), the maintainer's choice from
26 Nov 2026 (on Haiku, `claude-haiku-5-5`, before). For each
track, the main session writes the brief (files, changes, tests, the spec's exact expected
outputs), sends it, and then does what the implementer does not: reviews the diff, runs the full
checks in "Before pushing", breaks the code on purpose, commits, and writes the PR. Specs,
audits, spec-change PRs and closing PRs stay with the main session. The implementer never
commits or pushes.

Before sending a brief, run `python scripts/brief-check.py <brief file>` (a backticked name in
another file than the line names, D07.24, D08.77), then give the brief's file to the
**track-reviewer** with the word "brief": it greps the callers of what the brief changes, walks
each fake's states and works out each expected count. Fix the brief first, and record each
finding you take as a Defect line, `found: track-reviewer`.

New tests are seen red at the track's start, before any code: the implementer writes them, runs
`python scripts/seen-red.py --expect <the spec's Red today> -- <the test command>`, and stops if
they are not red for that reason (#212 S6; [Seen red](docs/procedure.md#seen-red)). A `new` test
already green on `main` is a spec defect, a hold or a test that checks the wrong thing. Run it
again yourself before the PR. Before the breaks, send the track-reviewer again, with the word
"diff" and the PR body's draft: it answers
[Reviewing a track's diff](specs/README.md#reviewing-a-tracks-diff) and checks each claim of the
PR against the diff (D11.30, D11.31). Then read the diff yourself: what it found is
`found: track-reviewer`, what you find after it `found: review`. It is not the driver's reviewer
(`rules/reviewer.md`), which reads the pull request once it is open. From Day 16, a real fault a
required check showed on the open pull request is `found: CI`, and a finding of the driver's
reviewer you take is `found: driver reviewer`.

Re-count any number the implementer reports (lines, tests, entries in a file) before it goes in
a PR: in wordtally, Day 4's report said a list held 40 words; it held 45.

## Before pushing

Run `python scripts/pre-push.py --title "<PR title>" --body <body file>` on the committed branch:
one line per PR check with a local command, exit 1 on any failure. Its "Style check" is the
check-only `ruff check . && ruff format --check .`, and its "Tests" is the track's one full run of
`tests/` (while working, run only the files the change touches): read the "Ran N tests" on its
`ok` line, and that N is the count the change should give. Run it in the background
(`run_in_background`, output to a file, then print the file's tail), never in the foreground: a
full run takes about 7 minutes and the shell stops at 10. A rerun after only the title or the
body changed takes `--skip-tests`; after a code change, the full run again. Break each check once with
`scripts/break.py` and copy the `broken:` line and `manifest:` it prints into the PR's raw body.
The diff stays under 400 changed lines, or carries an `Oversized:` line. What each step is for,
and the traps in each, are in [Before pushing](docs/procedure.md#before-pushing) and
[Breaks on purpose](docs/procedure.md#breaks-on-purpose).

## Stop and ask, do not patch

- The work seems to need an edit to `ContractTest` (Day 1) to make it pass, or to the sentences
  the driver accepts from the kit: the kit and the driver disagree, which `plan.md` ("What the
  driver needs from the kit") settles, not a patch.
  That is the signal the spec's premise is wrong.
- A criterion cannot be met as written. Record the departure; do not deviate silently.

## Where things live

- **State:** no database. The driver decides from git and GitHub; its run log, lock and halt
  file sit in its own folder, uncommitted (`plan.md`, "Recovery").
- **Measurement:** `python scripts/spec-drift.py --out spec-drift.json` rebuilds the dashboard's
  data from git and GitHub; every merge to `main` republishes the page. What git and GitHub cannot
  give it lives on the `dashboard-data` branch, filled by hooks and CI, never committed to `main`
  ([Where the counts live](docs/procedure.md#where-the-counts-live)).
- **Refusals:** the guards log every refusal to `.claude/state/refusals.jsonl`, counted on the
  dashboard. Many of one kind mean a rule is read past or in the way: say so in the day's Notes.

## Pitfalls this repository has already hit

- A small out-of-day behaviour change still needs a seen-red test: use [Short specs](specs/README.md#short-specs) when it qualifies.
- Claude Code refuses `rm -rf`, so a spec or brief that ends a command with it stops the
  session (a scratch virtualenv in the kit's workflow comparison). Leave a scratch directory in
  the session's scratchpad, remove it with `python -c "import shutil; shutil.rmtree('<dir>')"`,
  or let the build's `clean` delete old reports.
- The dashboard's dollars are API list prices, not a bill, and its sessions are this repository's
  only. On the page, "Day" is the plan's step and "date" the calendar's: keep the capital.
- `scripts/spec-drift.py` reads `main` by name: on a branch it shows `main`. To see a branch's
  effect, merge it into a scratch clone ([The dashboard script](docs/procedure.md#the-dashboard-script)).

What a session learns goes here, not into the next session's prompt: every session reads this
file. A lesson that only one step needs goes in `docs/procedure.md`, under that step.

On Windows, in Git Bash and PowerShell:

- The working tree may be CRLF (`core.autocrlf`): check `git ls-files --eol`, and expect git to
  rewrite a file it touches (a `git stash pop` does). Exact-string edits from a script fail on
  CRLF: use the Edit tool, or normalise and write the ending back. A test that writes a file
  writes bytes: text mode adds a carriage return and changes every count. `git show <sha>:<file>`
  prints LF: diffed against the CRLF tree, every line differs, so use `diff --strip-trailing-cr`.
- Windows PowerShell `Set-Content` and `Add-Content` can write in the system ANSI codepage,
  turning em dashes and arrows into `?`: write Markdown with `-Encoding utf8` or the Write tool,
  and read the saved file back as UTF-8 before committing.
- A path in JSON has its backslashes escaped: compare the parsed object, not the string.
- Long heredocs break in Git Bash, and PowerShell has none. Write commit messages and PR bodies
  to a scratch file (`git commit -F`, `gh pr create --body-file`); give the maintainer one-line
  commands, with any JSON in a file (`gh api --input <file>`).
- The Write tool will not overwrite a file this session has not read, even one a shell made.
- `bash` may be WSL's, which never starts a check: name Git Bash by its full path
  (`"C:/Program Files/Git/bin/bash.exe" -c "..."`).

## Commits and pull requests

- Commit messages: a subject that says what changed, then why, and what was seen failing.
- PR descriptions follow `.github/pull_request_template.md`: a user story in plain words a
  non-technical reader follows (as a…, I want…, so that…), what was built, why this approach
  (including what was broken on purpose and what it reported), contract impact, how to run, and
  the self-check. Spec-change PRs tick the `new`/`hold` line.
- Record mistakes, including your own, in the PR and the day's Notes (principle 5).
