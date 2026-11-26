# Procedure in detail

[`CLAUDE.md`](../CLAUDE.md) holds the principles and the working order, and every session reads
it. This page holds the detail of the steps it names, read when the step comes up: the close's
commands, the checks before pushing, the breaks, the hooks, and where the counts live. The spec
rules stay in [`specs/README.md`](../specs/README.md).

## The close, step by step

The closing PR, `day-NN/close-the-day` (`CLAUDE.md`, "A day, in order", step 3):

- Tick each criterion with its evidence (test or command, and the PR it landed in), add Notes to
  the spec, and update the Day entry and measurement table in
  [`docs/lab-notebook.md`](lab-notebook.md) (the README keeps only its Findings).
- Its defect counts and the PR's "## Defects" section are printed from the Notes by
  `python scripts/close-views.py specs/day-NN-slug.md`: paste them unchanged. Each Defect line
  carries `catchable:`, the earliest layer that could have caught it, and from Day 16 may say
  the step it was caught at, `at:`, which these views do not print (`specs/README.md`).
- The close commits no counts: the session hooks push them to the `dashboard-data` branch
  ("Where the counts live", below). For the notebook's figures, run
  `python scripts/publish-counts.py` and read them from that branch
  (`git show origin/dashboard-data:docs/dashboard/token-usage.json`).
- At a phase's last close only, relabel the defects of the phase's Days blind (each Day the phase
  has not relabelled at its own close; Phase 3: Days 16 to 18):
  `python scripts/relabel.py blind specs/day-16-*.md specs/day-17-*.md specs/day-18-*.md --out <dir>`,
  give `<dir>/blind.md` to the **defect-rater** agent, save its JSON as `<dir>/labels.json`, run
  `python scripts/relabel.py compare <dir>`, and paste its lines unchanged in the PR (the
  dashboard counts each Day's `Day NN:` block in the last whole run there) with a decision on each
  disagreement: the tag kept, and why, or changed in that Day's Notes.
- Commit the break manifest `specs/breaks/day-NN.json` with the actual mutation arguments, the
  `manifest:` lines the track PRs recorded (format and example in
  [Evidence at the close](../specs/README.md#evidence-at-the-close)); from Day 12 the tracks
  recorded it already, and `python scripts/break-lines.py --spec specs/day-NN-slug.md` checks the
  spec's `broken:` lines against it and prints the ones it lacks.
- Before opening the PR, commit the close and run
  `python scripts/close-evidence.py --rehearse day-NN/close-the-day` ("Breaks on purpose", below).
- After the PR merges, on fresh `main`, run
  `python scripts/evidence.py specs/day-NN-slug.md --ref main --json evidence.json` and retain
  the report for local runs. CI replays automatically after the merge; step 5 checks its run.
  Replay finds a **merged closing commit**; squash-merged closing PRs count too. Keep **missing**
  evidence/report, **stale** inputs or closing commit, and **failed** replay checks separate;
  resolve each before advancing. Execution errors also block advancement; review reasons for
  inapplicable checks.

## Seen red

Every track PR shows its new tests failing first (`specs/README.md`). When the tests live under
`tests/`, `python scripts/seen-red.py --expect <regex> -- <the test command>` runs the branch's
`tests/` on `main`'s code in a scratch worktree and prints the `seen red: ... → <what it reported>`
line for the PR; exit 1 means they pass there, or fail for another reason than `--expect`, the
spec's Red today (D08.67), or a failure line holds what `break.py` refuses in a break's report (a
uuid, a pid, a commit hash, an absolute path, "[N chars]"): the test is rewritten then, before the
code, not at the break (D12.37, D12.40). A red that passes is not a break's report proved fit: a
break may reach another assertion. Otherwise, without a Track 0 or an extra commit, stash the code
change (`git stash push -- <the code's directory>`), run the new tests on `main`'s code, compare
with what the spec says fails today, `git stash pop`, and put what they reported in the PR. CI's
"Track tests seen red" re-runs each `new` criterion's test this way when the repository variable
`TRACK_RED_RUNNER` names the project's runner (`docs/kit.md`, setup); unset, it fails a track that
owns a `new` criterion and passes the rest.

## Before pushing

- `python scripts/pre-push.py --title "<PR title>" --body <body file>` on the committed branch
  prints one line per PR check with a local command (`invariants.py main HEAD`, "Frozen files stay
  unedited", among them), exit 1 on any failure; "A track's breaks replay" needs Linux and only
  says so. Its "Tests" line runs the test files the branch changes 5 times each inside the whole
  run (`test-parallel.py --repeat 5 --of <files>`), which CI does not: a test that fails on and off
  under load is met in the PR that wrote it, not in a later track's full run (D12.34 passed 25 of
  25 alone). The scripts' own tests (`scripts/test_*.py`) are not repeated.
- The style check is check-only, `ruff check . && ruff format --check .`: it must fail on
  unformatted code and never rewrite files.
- While working, run only the test files the change touches
  (`python scripts/test-parallel.py "test_setup*.py"`, a glob under `tests/`), and name them in an
  implementer's brief; the full run goes once, before pushing. Waiting on commands was 55% of the
  main session's busy time over 6 to 15 Nov, most of it whole-suite runs (#212, S1).
- `python scripts/test-parallel.py` from the repository root runs the whole of `tests/`, one file
  per process, slowest first, the failures printed whole. It is the same tests as
  `python -m unittest discover -s tests`, which CI (`tests.yml`) runs serially with `-v`, and which
  the specs' Verify blocks replay; on this machine the serial run takes 2 to 8 minutes and the
  runner about half (337 s against 164 s, back to back), since the suite's time is spent starting
  processes (#60); the runner's floor is its slowest file, `test_on.py`. Run the serial command
  only to reproduce CI. Nothing is built first; the tests need `numpy` (`ContractTest` loads
  `scripts/spec-drift.py`). CI runs the style check and the serial command, nothing the local
  commands do not. A failing file's output is kept in `.claude/state/test-failures/` and its path
  printed: a failure seen once is not lost (D07.27, D08.81). For a file that fails on and off,
  `--repeat 10 <file>` says how often, and `--repeat 10 --of <file>` says it with the whole suite
  as the load.
- There is no test report directory: read unittest's "Ran N tests" and "OK" lines, and that N is
  the count the change should give, not the exit code.
- `PR_BRANCH=<branch> PR_TITLE="<title>" python scripts/pr-names.py main HEAD`,
  `git diff --numstat main...HEAD`, and `python scripts/check-links.py` on each Markdown file
  touched. Re-read the PR body's counts and `broken:` lines. Never force-push without the
  maintainer's OK.
- The PR diff must stay under **400 changed lines** (CI: "Diff stays reviewable"). If it does not,
  split the PR along a line where each part stands alone. An `Oversized:` line in the description
  turns the failure into a warning. `main` is protected, so the check must pass before a merge.
- A grep criterion cannot tell a comment from code: do not name, in a comment, the thing the day's
  grep checks is gone.

## Breaks on purpose

A test that passes before and after a change proves nothing until it has been seen to fail. Break
the code on purpose, run it, record what it reported, revert. The break never merges. Record it in
one line, `broken: <what> → <what it reported>` (`specs/README.md`): the dashboard reads no other
wording.

- `scripts/break.py` does one break this way and prints the line: one exact replacement, the
  file's bytes put back, the command run without a shell, a build only with `clean`, the check run
  twice with the break in. It refuses a report that differs between the two runs or holds a pid, a
  uuid, a commit hash or an absolute path: have the test print a fixed word there (`<uuid>`,
  `<head>`), in a fixture too. Hand-run breaks have half-applied, skipped the compile, never
  started the build, and lost unstaged work.
- Above the `broken:` line it prints `manifest: {...}`, the break's entry for the close's break
  manifest: put it in the PR beside its `broken:` line. Paste it as printed into the body file and
  check it with `gh pr view <n> --json body`: retyped or passed through a shell string, it loses a
  level of backslashes (`\s` for `\\s`) and no longer parses or matches (bearing D01.21). GitHub's
  rendered page drops one too: copy from the raw body.
- CI's "A track's breaks replay" (`scripts/track-breaks.py`) replays them, and the day's earlier
  tracks', on Linux on the PR's merge commit, and runs again when the body is edited: a report
  recorded on Windows, or a find this track rewrote, fails there and not at the close. Record the
  break again in this PR's body, under the same `<what>`, with CI's report.
- On a `day-NN/` branch, run it with `break.py --record` instead, commit `specs/breaks/day-NN.json`
  with the code, and paste what `python scripts/break-lines.py` prints: CI replays the record, and
  a re-run replaces its entry. When CI's report differs from the recorded one, take it with
  `break.py --take-reports` (CI's output names the artifact). When CI says an earlier Day's break
  "no longer applies", re-record or retire it in this PR, as its line says
  ([Evidence at the close](../specs/README.md#evidence-at-the-close)).
- Name the exact test, and check that the run failed: an error in the setup proves nothing. Clear
  the language's caches first (Python: `PYTHONDONTWRITEBYTECODE=1`, no `__pycache__`).
- Run the break, then copy its `broken:` line from what `scripts/break.py` printed. A line written
  before the run differed from the report.
- On Windows, `bash` may be WSL's, which never starts the check ("execvpe(/bin/bash) failed"):
  name Git Bash by its full path (`"C:/Program Files/Git/bin/bash.exe" -c "..."`). `break.py`
  refuses such a run rather than record it. Git Bash needs `MSYS_NO_PATHCONV=1` for a find that
  holds a `/path`.
- A check judged by what it prints, not its exit code (`grep -c` exits 1 at 0, a count): pass
  `--expect-stdout <regex>`, its output without the break; break.py refuses if it does not match,
  or if it matches any output (`^$` under `re.M` does, D11.21): for "prints nothing", `\A\Z`.
- On a CRLF tree, a `git diff --exit-code` check prints git's CRLF warning, and `break.py` reports
  that warning as the check's line: run `git -c core.safecrlf=false diff ...`.
- Replaying each manifest entry through `break.py` does not check the spec's `broken:` lines
  against the manifest. In bearing, the Day 10 close did only that, and the replay after its merge
  failed four lines (bearing D10.20): two breaks shared a name, two lines had no entry, one ended
  in "(close, D10.19)". The rules are in
  [Evidence at the close](../specs/README.md#evidence-at-the-close). Before opening the closing PR,
  commit the close and run `python scripts/close-evidence.py --rehearse day-NN/close-the-day`: it
  replays the branch as its merge into `main` would, moves no ref, and writes
  `evidence-rehearsal.json`. CI runs the same on the PR ("A closed day's evidence replays"). On
  bearing's Day 10 branch as it stood before its merge, it fails those lines. It is not the replay
  after the merge, which step 5 still checks: `main` can move in between. It does not run the
  dashboard either: on a scratch clone where the branch is merged with
  `--no-ff -m "Merge pull request #0 from me/day-NN/close-the-day"`, run `spec-drift.py --out`: a
  "No evidence and PR cited together" flag on the day's criteria means the Evidence is worded so
  the dashboard does not count it (bearing D12.11 to D12.13, fixed by a spec change after the
  close).

## The dashboard script

- `scripts/spec-drift.py` reads `main` by name: on a branch it shows `main`. To see a branch's
  effect, clone into a scratch directory, merge the branch with `--no-ff`, and run there. Pass
  `--cache <scratch>/c.json` by hand; `--build` and `--out` do not go together. Its output holds an
  en dash: grep it with `grep -a`.
- `--out spec-drift.json` rebuilds the dashboard's data from git and GitHub; `--build` writes the
  page (`docs/dashboard/`) with it, and until the first day spec exists it shows example data under
  a banner; `--out` never does. Every merge to `main` republishes it to
  [GitHub Pages](https://yusuprozimemet.github.io/agentic-workflow-driver/).
- In a spec, put in backticks only identifiers, paths and commands; quote literal output. The gap
  reads backticked snake_case and camelCase names as code.
- CI runs `scripts/behaviour-index.py` to check `Replaces:` lines.
- A project started from the kit inherits the kit's `docs/dashboard/token-usage.json`, and
  `token-usage.py` never lowers a row: the kit's six dates stayed on graph 8 as $151.56 of
  "set-up" until they were deleted by hand. The counts now live on the `dashboard-data` branch:
  a project started from the kit must not copy that branch.

## Agents with cases

The defect-rater, the track-reviewer, the spec-auditor and the driver's reviewer
(`rules/reviewer.md`) have known cases in `specs/agent-cases/`.

- A PR that edits one of their briefs runs `python scripts/agent-cases.py <agent>` and pastes its
  lines. CI's "A changed brief shows its case count" checks they were run on the brief the PR ends
  with, and that the agent's cases did not change beside it: only `recorded` may. Run it with
  `--record` when the maintainer accepts the new count. A case change goes in its own PR, so a
  brief is never measured on cases written to fit it.
- `python scripts/improve-loop.py <agent>`, only when the maintainer asks, starts the
  **brief-improver**: it returns a drafted brief, and the script counts it, before and after, and
  each cut of an unused passage alone, into `.claude/state/improve-loop/<agent>/report.md`. An
  approved draft goes in a `tooling/brief-<agent>` PR, counted and recorded there with
  `agent-cases.py`.

## Where the counts live

What git and GitHub cannot give the page has one route, the `dashboard-data` branch, filled by
machines and never committed to `main` (the seven files are gitignored there). A SessionStart and
a SessionEnd hook run `scripts/publish-counts.py --detach`: it counts in the background from the
last count on the branch, pushes the five count files (`token-usage.json`, `refusals.json`,
`gates.json`, `sessions.json`, `counted.json`) and the driver's count (`driver-runs.json`, from the
run log beside `run-steps.py`) to that branch (no working tree or branch here moves) and asks for
the page's rebuild. A count with nothing new is not pushed, and a push that lost a race with
another session's is built again on it. After every merge to `main`,
`.github/workflows/recheck.yml` re-checks the merges with no Linux row
(`scripts/replay-history.py`) and pushes `replay-history.json` to the same branch. `spec-drift.py`
fetches the branch and reads the seven there, in CI and in a local run alike; with the branch or
one of its files missing, the page says so in a banner and draws none of it. What the publisher
printed is in `.claude/state/publish-counts.log`: read it when the page's session lanes stand
still.

## The hooks

- **Whole-file Reads:** a PreToolUse hook (`scripts/read-guard.py`) refuses a Read with no
  `offset`, `limit` or `pages` of a file over 8,000 bytes, and names its size and line count. Find
  the part with `grep -n` and read that range; to read all of it on purpose, give the `limit` it
  names. Edit works after a ranged Read. Images, PDFs and notebooks pass.
- **Long Bash output:** a PostToolUse hook (`scripts/cap-output.py`) cuts stdout over 8,000
  characters to its head and tail; the full output is in `.claude/tool-output/` (gitignored).
  Claude Code merges stderr into stdout, so a failing command's error comes back at the end of
  stdout with stderr `''`: it is cut, and the tail (last 3,000 characters) keeps it; the stderr
  guard only catches a separate stderr. An interrupted command is left whole, as is output of
  30,000 characters or more, which Claude Code saves itself.
- **Refusals:** step-guard, read-guard and auditor-guard each append every refusal to
  `.claude/state/refusals.jsonl` (gitignored; `scripts/refusal_log.py`). `token-usage.py` counts it
  into `refusals.json` on the `dashboard-data` branch, shown under the dashboard's graph 8 ("What
  did it cost?") and as a row of graph 2. Many of one kind mean a rule is read past or in the way:
  say so in the day's Notes.
- **Read-only auditors:** `.claude/settings.json` runs `scripts/auditor-guard.py` on every Bash
  command and every subagent's stop. For the six auditors with Bash, and the track-reviewer, it
  blocks a git command that changes a repository (but `git -C <absolute path> fetch` into another
  repository, a scratch clone, passes) and a `gh` command that is not a read, and at the auditor's
  stop it compares HEAD, the refs, the stash and `git status` with what they were and sends the
  auditor back once if they changed; the main session and other agents pass. It is not a sandbox:
  it reads the command, not what a program does (`python -c` that writes a file gets through), and
  the stop sees only what git shows in this repository.
- The hooks sit in the project settings, not the agents' frontmatter: the VS Code extension's
  Claude Code (2.1.312) ignored frontmatter hooks. VS Code Copilot reads the same settings, ignores
  the matcher and sets no `CLAUDE_PROJECT_DIR`; the hook command reads that variable in Python and
  passes without it, since a missing script exits 2 and denied every Copilot tool call (seen in PR
  #58). An edit to `.claude/` takes effect in the next session, not this one.
