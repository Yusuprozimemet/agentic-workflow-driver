# Day 12 — The reviewer: its brief, its read-only settings, the before-and-after comparison, its verdict on the PR, a blocker's fix

**Phase:** 2 · **Depends on:** Day 11 · **Expected PRs:** 11 (the spec change, a second spec change for C12.23, Tracks A, B, C, D, E0, E1, E2, F, the close)

## Goal
Once a pull request's required checks are green, the driver starts a reviewer session, new and
never the step's, from a brief in the driver's own repository (`--agents`, `--agent reviewer`),
with settings that refuse it a git command that changes a repository and a `gh` command that is
not a read; it compares HEAD, the refs, the stash and `git status` before and after the session
and parks on a difference; it posts the reviewer's `found:` lines as one comment on the pull
request; and a blocker resumes the step's session to fix it, within the same two fixes a red
check has, before the merge wait goes on (`plan.md`, "What to build", item 7; "Sessions and
tokens"; "When the driver parks").

## In scope

Decided by the maintainer on 2026-11-15, where `plan.md` leaves it open: the reviewer runs at
every level, once the checks are green (at level 1 the maintainer still merges, and reads its
comment first); its findings go in one comment on the pull request; a blocker's fix and a red
check's fix share the two fixes a pull request has.

- **The switch (Track E1).** `driver.json` takes an optional `review`, `true` or `false`, `false`
  when absent; `driver.config.problems` reports "cannot start: <path>'s review must be true or
  false" for any other value. Absent, the driver does what it does today: the tests' own
  `driver.json` files hold no `review`, so their `gh` and `claude` call lists do not change.
  `driver.json` is the maintainer's, gitignored (`.gitignore:30`): no PR sets the key; the
  maintainer adds `"review": true` to it after Track E2 merges.
- **The brief (Track A).** `rules/reviewer.md`, in the driver's repository, mounted read-only in
  the container with `rules/` as today (`/driver/rules`). It tells the reviewer to read the pull
  request (`gh pr view`, `gh pr diff`, `gh pr checks`), the day spec its branch names and the
  files it touches, and to report, one line each, `found: blocker — <what>` for what must not
  merge (a criterion ticked without its evidence, a `broken:` line or count the diff does not
  bear out, work outside the spec's In scope, a human-only path) and `found: advice — <what>`
  for the rest (wording, a record); its reply's last line is `REVIEW: blocker` when it found at
  least one blocker and `REVIEW: none` otherwise. It changes nothing: no edit, commit, push,
  comment or merge. A new module `driver/review.py` holds `agents(state, home, inside=False)`:
  it writes `<state>/agents.json` afresh, one key `reviewer` whose value has `description` (a
  non-empty string), `prompt` (`rules/reviewer.md`'s text, read as UTF-8) and `tools`
  (`["Read", "Grep", "Glob", "Bash"]`), as bytes, and returns its path; `inside` changes only
  the path returned, `/state/agents.json`. The file goes in `<state>`, not as an argument:
  cmd.exe drops a newline and what follows it (`once.begin`'s comment).
- **The read-only hook (Track B).** `hooks/readonly.py <refusals folder>` reads Claude Code's
  PreToolUse JSON on stdin, as `hooks/guard.py` does. For `Bash` and `PowerShell` it splits the
  command at `&&`, `||`, `;`, `|`, a single `&` and newlines (one more than `guard.py`'s
  `SEGMENT_RE`, which is not changed), and reads each segment's words with `shlex`, skipping
  leading `(`, `&` (PowerShell's call operator), `env` and `NAME=value` words; a segment whose
  first word left is `git` (after any `-C <path>`, `-c <key=value>` or `--no-pager`) passes only
  when its subcommand is one of `status`, `diff`, `log`, `show`,
  `rev-parse`, `ls-files`, `ls-tree`, `cat-file`, `for-each-ref`, `show-ref`, `merge-base`,
  `rev-list`, `blame`, `grep`, `describe`; a segment whose first word is `gh` passes only for
  `pr view`, `pr diff`, `pr checks`, `pr list`, `pr status`, `issue view`, `issue list`,
  `run view`, `run list`, `repo view`, and `api` with no `-X`/`--method` other than `GET` and
  none of `-f`, `-F`, `--field`, `--raw-field`, `--input` (`gh help api`: parameters make it a
  `POST`; `--input` is refused as a body to send, whatever its method). Any other `git` or `gh` segment exits 2 with "refused by the driver: the reviewer only
  reads" on stderr, and a call it cannot read exits 2 with "refused by the driver: the read-only
  hook could not read the tool call"; each refusal is appended to `<refusals folder>/hooks.jsonl`
  through `hook_log`, as `guard.py`'s are. Everything else exits 0 and prints nothing.
  `hooks/guard.py` is not changed.
- **The reviewer's settings (Track A).** `driver.settings.review(state, home, inside=False)`
  writes `<state>/review-settings.json`: the halt hook (`"*"`) and the guard hook (`GUARDED`) as
  `write` makes them, then `readonly.py` with the matcher `"Bash|PowerShell"` and the refusals
  folder, through `entry`. With `inside=True` it writes `<state>/review-container-settings.json`,
  whose readonly command is `python "/driver/hooks/readonly.py" "/state/refusals"`, typed out as
  `write`'s inside commands are. `settings.write` and its two files are not changed.
- **The comparison (Track C).** `review.snapshot(project, git=("git",))` returns a dict of four
  strings read with git commands on P48's list (`for-each-ref` is new to the driver's code, not
  to the list): `head` from `git rev-parse HEAD` and `git rev-parse --symbolic-full-name HEAD`,
  joined by a newline (so a switch to another branch at the same commit is seen), `refs` from
  `git for-each-ref --format=%(refname) %(objectname)` with the `refs/stash` line taken out,
  `stash_top` that line or `""`, and `status` from `git status --porcelain=v1
  --untracked-files=all`; a git command that fails gives its key `None`. (The key is not
  `"stash"`: C07.1's `RecoveryRulesTest.test_no_command_that_can_lose_work` reads that string in
  `driver/*.py` as a command that can lose work.) `review.changed(before, after)` returns the
  first key whose values differ, in the order `head`, `refs`, `stash_top`, `status`, named as
  "HEAD", "the refs", "the stash", "`git status`", or `None`.
- **The verdict and the comment (Track D).** `review.verdict(text)` reads the reviewer's `result`
  text: `(found, blockers)`, where `found` is every line starting `found: blocker — ` or
  `found: advice — `, in order, and `blockers` those starting `found: blocker — `, when the last
  non-empty line is `REVIEW: blocker` and there is at least one blocker, or `REVIEW: none` and
  there is none; `None` otherwise (no verdict line, or one that disagrees with the lines).
  `review.body(head, session, found)` returns "review of `<head>` (session `<session>`):", then
  the `found` lines, or "nothing found" when there are none, then the verdict line, joined by
  newlines. `driver.issues.pr_comment(project, gh, number, body)` runs `gh pr comment <number>
  --body-file -` with the body on stdin, through `_write`, and returns `None` or the reason it
  failed. The tests' fake `gh` (`tests/test_github.py`) answers `pr comment` by printing
  `https://github.com/me/project/pull/<n>#issuecomment-<comment_id>`, and its `comment_code`
  fails `pr comment` as it fails `issue comment`.
- **The split first (Track E0).** A refactor only, held by the tests in force: `once.begin`'s
  command list is built by a new `once.command(args, home, config, settings, session, extra=())`
  that `begin` calls, `extra` going before `--session-id`; `loop.resume`'s run is moved into a
  new `loop.fix(args, project, number, record, command, prompt, used)`, which `resume` calls with
  its prompt unchanged. `resume`'s and `begin`'s signatures, returns and outputs do not change
  (`tests/test_halt_race.py`, `tests/test_session_bound.py` and `tests/test_runlog_recovery.py`
  call `resume` as it is). No criterion of this day is E0's; it records again the breaks whose
  finds it moves (Tracks, below).
- **The reviewer in the loop (Track E1).** With `review` true, `loop.wait_reviewed(args, home,
  project, number, record, command, config)` takes `wait_pr`'s place in `loop.steps`, and
  `wait_found` gains the keyword arguments `home=None, config=None` (its callers' positions
  unchanged) and calls `wait_reviewed` when `config` holds `review` true. `wait_reviewed` runs
  `wait_pr`; on green it reads the pull request through `github.pr_state`, polled as
  `wait_merge` polls it (through `loop.poll`; a read with no `headRefOid` is a failed read,
  waited out within `--wait-minutes`). A pull request read `MERGED` or `CLOSED` there is not
  reviewed: `wait_reviewed` returns `(None, 0)` and `wait_merge` reads it as today. Otherwise
  it takes the snapshot (a key `None` returns "cannot read the project: git failed before the
  review of #<n>", 2), and runs `review.run`: a new uuid, `review.agents`,
  `driver_settings.review`, a run log start line through `runlog.start` with the step's
  sentence, the prefix `review`, the uuid, the Claude Code version read as `once.begin` reads
  it, the run's issue and, in the container, `driver-<uuid>`; and one session through
  `once.run_session`, whose command is `once.command`'s with `--settings` naming the reviewer's
  settings, no `--append-system-prompt-file` and its path, and `extra` `--agents
  <agents.json> --agent reviewer`; in the container, the same inside `box.command`, named
  `driver-<uuid>`, with the `/state/` paths. Its prompt, on stdin: "Review pull request #<n> at
  commit <head>, for the step: <sentence>.\nRead it as your brief says, change nothing, and end
  with the REVIEW line.\n". Then, in this order:
  - the session's STOP, past-the-bound and halt endings return as a step session's do
    (`once.run_session`'s `None` and `PAST`, `once.halted_after`);
  - the `result` read through `driver.stream.result` and `review.verdict`, and the end line
    written through `once.write_end` with the outcome "review: #<n>, <k> blockers" (or the
    park line below), so the session's cost is in the run log whatever follows;
  - the snapshot again: a difference returns "park: the reviewer changed <what> in the project
    on #<n> (session `<uuid>`)", 1, with no comment; a key `None` returns the "cannot read the
    project" line above;
  - no `result`, `is_error`, or `review.verdict` `None` returns "park: the reviewer gave no
    verdict on #<n> (session `<uuid>`)", 1;
  - the comment, through `issues.pr_comment`; a failure prints "review: no comment on #<n>:
    <reason>" and goes on;
  - a run log line `{"event": "review", "at": ..., "pr": <n>, "session": <uuid>, "head": <head>,
    "blockers": <count>}` (`runlog.review`);
  - no blocker: `wait_reviewed` returns `(None, 0)`, and `wait_merge` follows as today.
- **A blocker (Track E2).** A blocker on a pull request with no session of this run (`command`
  `None`) returns "park: the reviewer has a blocker on #<n>: <the first blocker line, without
  `found: blocker — `>", 1. Otherwise, with `runlog.fixes` at 2 already, "park: the reviewer
  still has a blocker on #<n> after two fixes", 1; else `loop.fix` resumes the step's session,
  with `runlog.fix` first and the prompt "The reviewer found a blocker on #<n>:\n<the blocker
  lines>\nFix this step's pull request, push, and stop.\n", and `wait_reviewed` starts again
  with `wait_pr` on the pull request the fix names. The red checks' fix prompt and their "still
  red after two fixes" park are not changed; both read the same `runlog.fixes`.
- **Live (Track F).** A live test, skipped unless `DRIVER_LIVE_REVIEW` is set, runs `claude -p`
  on the PC's Claude Code in a scratch git repository with `--agents` naming a file of one agent,
  `probe`, whose prompt says to reply with the word ORCHID and nothing else, and `--agent probe`:
  the `result` is ORCHID. A second run, with `driver.settings.review`'s file and the prompt "Run
  `git commit --allow-empty -m x` with Bash, then reply DONE", leaves HEAD unchanged and adds a
  readonly refusal to the scratch refusals folder. With `DRIVER_CONTAINER_IMAGE` and
  `DRIVER_CONTAINER_SECRETS` set, the first run is made in the image too, through `box.command`.

## Out of scope

- The level 2 merge, `gh pr merge --match-head-commit <sha>` on the head the reviewer saw — Day 13.
  This day records that head in the run log's `review` line, for Day 13 to read.
- Whether the level 2 merge needs `live-check` run in the image (H10.1) — Day 13 (H12.1).
- The usage limit met by a headless session (H09.2) and the container's sessions in the record
  (H10.2) — Day 14.
- Counting the reviewer's `found:` lines on the dashboard beside the other gates: the run log
  holds them; drawing them is the record's, Day 14.
- Whether the Level 2 count (`status.level_2_run`, H08.4) ends on the new "the reviewer still has
  a blocker on #<n> after two fixes" park as it ends on "still red after two fixes" — Day 13
  (H12.2).
- `status` showing the reviewer's session as its own kind: it shows it as one more `steps:` row
  with the step's sentence, and "(no estimate: the step has no kind)" while it runs — Day 14's
  record, if the maintainer wants it (H12.3).
- Reading the reviewer's transcript: only its `result` is read.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | `rules/reviewer.md`; `review.agents`; `settings.review`: C12.1–C12.3 |
| B | | `hooks/readonly.py`: C12.4, C12.5 |
| C | | `review.snapshot`, `review.changed`: C12.6, C12.7 |
| D | | `review.verdict`, `review.body`, `issues.pr_comment`, the fake `gh`'s `pr comment`: C12.8–C12.10 |
| E0 | | Refactor only: `once.command` out of `once.begin`, `loop.fix` out of `loop.resume`; no criterion |
| E1 | | The `review` switch; `review.run`; `loop.wait_reviewed`: C12.11, C12.12, C12.16–C12.19, C12.22, C12.23 |
| E2 | | The blocker's fix within the shared two: C12.13–C12.15, C12.20 |
| F | | Live: `--agents` and `--agent` from a file, the read-only settings refusing a commit: C12.21 |

In order: A, B, C, D, E0, E1, E2, F. E0 splits what E1 and E2 build on, so that neither passes
400 changed lines (Day 6's Tracks D and E, on `wait_pr` and the merge wait, were 377 and 396);
E1 puts A to D together; E2 adds the fix; F last, on the PC and the image.

Breaks recorded on earlier days whose finds a track rewrites are recorded again in that track's
PR under the same `<what>`, with a `manifest:` line, and a track's new code must not make an
earlier find occur twice (`break.py` then refuses, "occurs 2 times"). Each of these occurs once
today (`grep -cF`) and is at risk: A — Day 9's `entry(GUARDED, "guard.py",
os.path.abspath(home), refusals)` in `driver/settings.py`; E0 — Day 4's `settings_path =
driver_settings.write(args.state, home)`, Day 10's `version = livecheck.version(path)` and
`record["container"],` in `driver/once.py`, and in `driver/loop.py` the `--resume` list
comprehension, `    if done is once.PAST:` and `    halted = once.halted_after(args, session)`
(Day 9); E1 and E2 — `if used >= 2:` (Days 6 and 12), `if command is None:`, `return None,
reason` and `record["pr"] = number` in `driver/loop.py`. Before each track's code, grep every
Day manifest's finds (`specs/breaks/day-*.json`) in the files its diff touches, and list in its
PR the ones it moves.

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").

- [x] C12.1 **new** — `driver.review.agents(<scratch state>, <the repository's root>)` returns
      `<scratch state>/agents.json`; the file parses to an object with one key, `reviewer`, whose
      value has exactly the keys `description` (a non-empty string), `prompt` (equal to
      `rules/reviewer.md` read as UTF-8) and `tools` (`["Read", "Grep", "Glob", "Bash"]`); a
      second call over a file holding `{}` writes the same bytes again; with `inside=True` it
      returns `/state/agents.json`. Red today: `driver.review` does not exist.
      Test: `ReviewAgentsTest.test_agents_file`.
      Plan: P63 "The reviewer's brief is in the driver's repository and reaches the session with
      `--agents` and `--agent`"
      Evidence: `ReviewAgentsTest.test_agents_file` passes on `main` at `3774c34` (#204).
      seen red: python -m unittest tests.test_review_agents on main → FAILED (errors=4) (#204)
      broken: C12.1 the reviewer given Edit → AssertionError: Lists differ: ['Read', 'Grep', 'Glob', 'Bash', 'Edit'] != ['Read', 'Grep', 'Glob', 'Bash'] (#204)
- [x] C12.2 **new** — `rules/reviewer.md` holds each of "found: blocker — ", "found: advice — ",
      "REVIEW: blocker", "REVIEW: none", "gh pr diff" and "change nothing". Red today: no such
      file.
      Test: `ReviewAgentsTest.test_brief_names_the_reply`.
      Plan: P63 "The reviewer's brief is in the driver's repository"
      Evidence: `ReviewAgentsTest.test_brief_names_the_reply` passes on `main` at `3774c34` (#204).
      seen red: python -m unittest tests.test_review_agents on main → FAILED (errors=4) (#204)
      broken: C12.2 the brief's none line renamed → AssertionError: False is not true : the brief lacks 'REVIEW: none' (#204)
- [x] C12.3 **new** — `driver.settings.review(<scratch state>, <root>)` writes
      `<scratch state>/review-settings.json`, whose PreToolUse list is three entries: the matcher
      `"*"` with `halt.py`, `GUARDED` with `guard.py`, then `"Bash|PowerShell"` with a command
      naming `sys.executable`, `<root>/hooks/readonly.py` and `<scratch state>/refusals`, each
      quoted; with `inside=True`, `<scratch state>/review-container-settings.json`, whose third
      command is `python "/driver/hooks/readonly.py" "/state/refusals"`. `settings.write`'s two
      files are as they are on `5bb5fa1` (`SettingsTest.test_settings_name_both_hooks` and
      `BoxCommandTest.test_container_settings` pass unedited). Red today: `settings` has no
      `review`.
      Test: `ReviewSettingsTest.test_review_settings`, `ReviewSettingsTest.test_inside`.
      Plan: P63 "the driver's settings refuse it a git command that changes a repository and a
      `gh` command that is not a read"
      Evidence: `ReviewSettingsTest.test_review_settings` and `ReviewSettingsTest.test_inside` pass on `main` at `3774c34` (#204); `SettingsTest.test_settings_name_both_hooks` and `BoxCommandTest.test_container_settings` pass there, their files unedited: Verify's `git diff`s over `495bf69` and `c8e5963` print nothing.
      seen red: python -m unittest tests.test_review_agents on main → FAILED (errors=4) (#204)
      broken: C12.3 the read-only hook matched on Bash alone → AssertionError: Lists differ: ['*', 'Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit', 'Bash'] != ['*', 'Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit', 'Bash|PowerShell'] (#204)
- [x] C12.4 **new** — `python hooks/readonly.py <scratch refusals>` with a `Bash` PreToolUse call
      exits 2 with "refused by the driver: the reviewer only reads" on stderr, and appends one
      line to `<scratch refusals>/hooks.jsonl`, for each of: `git commit -m x`, `git push`,
      `git checkout -b x`, `git switch main`, `git stash`, `git fetch`, `git -C . reset --hard`,
      `ls && git add .`, `gh pr merge 3`, `gh pr comment 3 --body x`, `gh pr review 3 --approve`,
      `gh issue close 3`, `gh api -X POST repos/o/r/issues`, `gh api repos/o/r/issues -f
      title=x`, `gh api --input body.json repos/o/r/issues`, `GIT_X=1 git commit -m x`, `env git
      commit -m x`, `(git commit -m x)`, `ls & git commit -m x`, and the `PowerShell` call `& git
      commit -m x`; and with stdin `not json` exits 2
      with "refused by the driver: the read-only hook could not read the tool call". Red today:
      no such file.
      Test: `ReadonlyHookTest.test_refuses`.
      Plan: P63 "the driver's settings refuse it a git command that changes a repository and a
      `gh` command that is not a read"
      Evidence: `ReadonlyHookTest.test_refuses` passes on `main` at `3774c34` (#205).
      seen red: python -m unittest tests.test_readonly_hook on main → AssertionError: False is not true (#205)
      broken: readonly.py no longer splits at a single & → AssertionError: 20 != 21 (#205)
      broken: readonly.py lets gh api --input through → AssertionError: 20 != 21 (#205)
- [x] C12.5 **new** — The same hook exits 0 and prints nothing for: `git status`, `git diff
      main...HEAD`, `git --no-pager diff`, `git log --oneline -5`, `git show HEAD:plan.md`, `git
      -C . rev-parse HEAD`,
      `git ls-files`, `gh pr view 3 --json files`, `gh pr diff 3`, `gh pr checks 3`, `gh api
      repos/o/r/pulls/3`, `gh api -X GET repos/o/r/pulls/3/files`, `grep -n x plan.md`, `python
      -m unittest`, and a `Read` call; `hooks.jsonl` is not created. Red today: no such file.
      Test: `ReadonlyHookTest.test_passes`.
      Plan: P63 "refuse it a git command that changes a repository"
      Evidence: `ReadonlyHookTest.test_passes` passes on `main` at `3774c34` (#205).
      seen red: python -m unittest tests.test_readonly_hook on main → AssertionError: False is not true (#205)
      broken: readonly.py no longer skips git --no-pager → AssertionError: True is not false (#205)
- [x] C12.6 **new** — In a scratch repository with one commit, `review.changed(before, after)`
      with `before` and `after` taken by `review.snapshot` around each of these gives: a new
      commit → "HEAD"; `git branch x` → "the refs"; a tracked file changed, then `git stash` →
      "the stash"; a new untracked file → "`git status`"; `git switch -c y` (same commit) →
      "HEAD"; nothing → `None`. Red at Track C's start: `driver.review` has no `snapshot`
      (AttributeError; Track A creates the module).
      Test: `ReviewSnapshotTest.test_changes_named`.
      Plan: P63 "the driver compares HEAD, the refs, the stash and `git status` before and after
      it and parks on a difference"
      Evidence: `ReviewSnapshotTest.test_changes_named` passes on `main` at `3774c34` (#207).
      seen red: python -m unittest tests.test_review_snapshot on main → FAILED (errors=8) (#207)
      broken: C12.6 the stash's line left in the refs → AssertionError: 'the refs' != 'the stash' (#207)
      broken: C12.6 HEAD read without its branch name → AssertionError: 'the refs' != 'HEAD' (#207)
- [x] C12.7 **new** — `review.snapshot` runs only `git rev-parse`, `git for-each-ref` and `git
      status` (a fake `git` records its calls), and a fake `git` that exits 1 gives each key
      `None`. Red at Track C's start: `driver.review` has no `snapshot` (AttributeError).
      Test: `ReviewSnapshotTest.test_reads_only`.
      Plan: P48 "The driver's git commands are only `status`, `rev-parse`, `for-each-ref`"
      Evidence: `ReviewSnapshotTest.test_reads_only` passes on `main` at `3774c34` (#207).
      seen red: python -m unittest tests.test_review_snapshot on main → FAILED (errors=8) (#207)
      broken: C12.7 a failing git read as its output → AssertionError: {'head': '\n', 'refs': '', 'stash_top': '', 'status': ''} != {'head': None, 'refs': None, 'stash_top': None, 'status': None} (#207)
      broken: C12.7 the status read with git diff → AssertionError: Lists differ: ['diff'] != [] (#207)
- [x] C12.8 **new** — `review.verdict` gives: "found: blocker — a\nfound: advice — b\nREVIEW:
      blocker" → (["found: blocker — a", "found: advice — b"], ["found: blocker — a"]); "found:
      advice — b\n\nREVIEW: none\n" → (["found: advice — b"], []); "REVIEW: none" → ([], []);
      "found: blocker — a\nREVIEW: none" → `None`; "REVIEW: blocker" → `None`; "found: advice —
      b" → `None`; "" → `None`; "REVIEW: none\nmore" → `None`. Red at Track D's start:
      `driver.review` has no `verdict` (AttributeError).
      Test: `ReviewVerdictTest.test_verdicts`.
      Plan: P31 "the reviewer still has a blocker"
      Evidence: `ReviewVerdictTest.test_verdicts` passes on `main` at `3774c34` (#208).
      seen red: python -m unittest tests.test_review_verdict on main → FAILED (errors=10) (#208)
      broken: C12.8 a REVIEW line that disagrees taken as a verdict → AssertionError: ([], []) != None (#208)
- [x] C12.9 **new** — `review.body("abc1234", "s1", ["found: advice — b"])` is "review of
      `abc1234` (session `s1`):\nfound: advice — b\nREVIEW: none"; with a blocker line among
      them, the last line is "REVIEW: blocker"; with `[]`, "review of `abc1234` (session
      `s1`):\nnothing found\nREVIEW: none". Red at Track D's start: `driver.review` has no
      `body` (AttributeError).
      Test: `ReviewVerdictTest.test_body`.
      Plan: none — the comment's wording; the maintainer chose the comment on 2026-11-15, and
      `plan.md` names the `found:` lines, not where they go.
      Evidence: `ReviewVerdictTest.test_body` passes on `main` at `3774c34` (#208).
      seen red: python -m unittest tests.test_review_verdict on main → FAILED (errors=10) (#208)
      broken: C12.9 no nothing found line → AssertionError: Lists differ: ['REVIEW: none'] != ['nothing found', 'REVIEW: none'] (#208)
- [x] C12.10 **new** — `issues.pr_comment(<project>, <fake gh>, 12, "x\ny")` returns `None`; the
      fake `gh` records `["pr", "comment", "12", "--body-file", "-"]` and "x\ny" in
      `bodies.jsonl`; with `comment_code` 1 it returns a reason that is not `None`. Red today:
      `issues` has no `pr_comment`, and the fake `gh` exits 99 on `pr comment`.
      Test: `ReviewCommentTest.test_pr_comment`.
      Plan: none — where the findings go, the maintainer's choice of 2026-11-15.
      Evidence: `ReviewCommentTest.test_pr_comment` passes on `main` at `3774c34` (#208); live, `gh pr comment 208 --body-file -` printed the comment's URL and exited 0 (gh 2.93.0, #208).
      seen red: python -m unittest tests.test_review_verdict on main → FAILED (errors=10) (#208)
      broken: C12.10 the comment sent to the issue, not the pull request → AssertionError: 'gh pr comment exited 1' is not None (#208)
- [x] C12.11 **new** — `driver.config.load` on a `driver.json` with `"review": "yes"` returns
      `None` and the line "cannot start: <path>'s review must be true or false"; with `true`,
      `false` or no `review`, it loads. Red today: `"yes"` loads.
      Test: `ReviewConfigTest.test_review_key`.
      Plan: none — a switch, so that the tests' own `driver.json` files keep their call lists.
      Evidence: `ReviewConfigTest.test_review_key` passes on `main` at `3774c34` (#214).
      seen red: python -m unittest tests.test_review_loop.ReviewConfigTest tests.test_review_loop.ReviewLoopTest.test_reviewed_then_merge_wait tests.test_review_loop.ReviewLoopTest.test_change_parks tests.test_review_loop.ReviewLoopTest.test_no_verdict_parks tests.test_review_loop.ReviewLoopTest.test_comment_failure_goes_on tests.test_review_loop.ReviewLoopTest.test_snapshot_git_fails tests.test_review_loop.ReviewBoxTest on main → AssertionError: Tuples differ: (0, 1, ['driver-<uuid>'], ['driver-<uuid>'], [18 chars]alse) != (0, 2, ['driver-<uuid>'], ['driver-<uuid>'], [132 chars]True) (#214)
      broken: a review that is not a boolean loaded (C12.11) → AssertionError: differs: yes (#224)
- [x] C12.12 **new** — `on` with `"review": true`, a fake `claude` whose step session opens
      #12 and whose `--agent reviewer` session replies "found: advice — a word\nREVIEW: none",
      green checks, and a merge read as `MERGED`: the fake `claude` is started twice; the second
      command holds `--agents <state>/agents.json --agent reviewer --session-id <uuid>` as its
      last six arguments, `--settings <state>/review-settings.json`, no
      `--append-system-prompt-file`, a uuid other than the step's, and the prompt "Review pull
      request #12 at commit <head>, for the step: <step>." as its stdin's first line; the fake
      `gh` records one `pr comment 12 --body-file -` with the body "review of `<head>` (session
      `<uuid>`):\nfound: advice — a word\nREVIEW: none"; the run log holds, for the reviewer's
      uuid, a start line with the prefix `review` and the run's issue, an end line whose
      `cost_usd` is the reviewer's `result`'s `total_cost_usd` and whose outcome is "review: #12,
      0 blockers", and `{"event": "review", "pr":
      12, "session": <uuid>, "head": <head>, "blockers": 0}` with its `at`; and the run goes on
      to the merge wait and the evidence wait as without the reviewer. Red today: one session.
      Test: `ReviewLoopTest.test_reviewed_then_merge_wait`.
      Plan: P22 "The reviewer is a new session with a fresh context, read-only, and never the
      step's session"; P55 "with the reviewer session counted in"
      Evidence: `ReviewLoopTest.test_reviewed_then_merge_wait` passes on `main` at `3774c34` (#214); its reviewer's `fix` and merge waits as E2 left them (#218).
      seen red: python -m unittest tests.test_review_loop.ReviewConfigTest tests.test_review_loop.ReviewLoopTest.test_reviewed_then_merge_wait tests.test_review_loop.ReviewLoopTest.test_change_parks tests.test_review_loop.ReviewLoopTest.test_no_verdict_parks tests.test_review_loop.ReviewLoopTest.test_comment_failure_goes_on tests.test_review_loop.ReviewLoopTest.test_snapshot_git_fails tests.test_review_loop.ReviewBoxTest on main → AssertionError: Tuples differ: (0, 1, ['driver-<uuid>'], ['driver-<uuid>'], [18 chars]alse) != (0, 2, ['driver-<uuid>'], ['driver-<uuid>'], [132 chars]True) (#214)
      broken: the reviewer started without --agent reviewer (C12.12) → AssertionError: differs: 0, 1, 3, 6 (#224)
- [x] C12.13 **new** — As C12.12 with the reviewer replying "found: blocker — no test\nREVIEW:
      blocker" the first time and "REVIEW: none" the second: the step's session is resumed once,
      `--resume <the step's uuid>`, with the prompt "The reviewer found a blocker on
      #12:\nfound: blocker — no test\nFix this step's pull request, push, and stop.\n"; the run
      log holds one `fix` line with `n` 1 before it; the checks are read again, a second
      reviewer session runs with a new uuid, and the run goes on to the merge wait. Red today:
      no reviewer.
      Test: `ReviewLoopTest.test_blocker_resumes_the_step`.
      Plan: P23 "A fix after a red check or a reviewer's blocker resumes the step's own session"
      Evidence: `ReviewLoopTest.test_blocker_resumes_the_step` passes on `main` at `3774c34` (#218).
      seen red: python -m unittest tests.test_review_loop.ReviewLoopTest.test_blocker_resumes_the_step on main → AssertionError: Tuples differ: (0, [[49 chars]ewer'], '', False, '', 1, False, [], [], False[30 chars]alse) != (0, [[49 chars]ewer', 'resume', 'reviewer'], '<step-uuid>', F[212 chars]True) (#218)
      broken: a blocker not fixed (C12.13) → AssertionError: Tuples differ: (0, [[49 chars]ewer'], '', False, '', 1, False, [], [], False[30 chars]alse) != (0, [[49 chars]ewer', 'resume', 'reviewer'], '<step-uuid>', F[212 chars]True) (#218)
- [x] C12.14 **new** — As C12.13 with the reviewer always replying a blocker: two fixes, then
      `on` prints "park: the reviewer still has a blocker on #12 after two fixes" and exits 1;
      and with the checks red once first (one fix spent on them), the blocker gets one fix, then
      the same park. Red today: no reviewer.
      Test: `ReviewLoopTest.test_blocker_park_after_two_fixes`,
      `ReviewLoopTest.test_fixes_shared_with_red_checks`.
      Plan: P31 "The driver parks when a required check is still red, or the reviewer still has
      a blocker, after two fixes"
      Evidence: `ReviewLoopTest.test_blocker_park_after_two_fixes` and `ReviewLoopTest.test_fixes_shared_with_red_checks` pass on `main` at `3774c34` (#218).
      seen red: python -m unittest tests.test_review_loop.ReviewLoopTest.test_blocker_park_after_two_fixes on main → AssertionError: Tuples differ: (0, ["on: 1 steps, the night's count"], 2,[135 chars]se}]) != (1, ['park: the reviewer still has a block[41 chars], []) (#218)
      seen red: python -m unittest tests.test_review_loop.ReviewLoopTest.test_fixes_shared_with_red_checks on main → AssertionError: Tuples differ: (0, ["on: 1 steps, the night's count"], [1], [True], 3, 1) != (1, ['park: the reviewer still has a block[51 chars]5, 2) (#218)
      broken: a third fix for a blocker (C12.14) → AssertionError: Tuples differ: (0, ["on: 1 steps, the night's count"], [1[23 chars]6, 2) != (1, ['park: the reviewer still has a block[51 chars]5, 2) (#218)
- [x] C12.15 **new** — A pull request found open at a start (`wait: #12`, no session of this run)
      with green checks and a reviewer replying "found: blocker — no test\nREVIEW: blocker":
      `on` prints "park: the reviewer has a blocker on #12: no test", exits 1, and resumes no
      session. Red today: the merge wait starts.
      Test: `ReviewLoopTest.test_found_pr_blocker_parks`.
      Plan: P31 "the reviewer still has a blocker"
      Evidence: `ReviewLoopTest.test_found_pr_blocker_parks` passes on `main` at `3774c34` (#218).
      seen red: python -m unittest tests.test_review_loop.ReviewLoopTest.test_found_pr_blocker_parks on main → AssertionError: Tuples differ: (0, True, ["off: the run's issue #1 is clo[46 chars] [1]) != (1, True, ['park: the reviewer has a block[41 chars] [1]) (#218)
      broken: a found pull request's blocker resumed (C12.15) → AssertionError: Tuples differ: (1, True, ['review: #12, 1 blockers'], ['reviewer'], 0, 1, [1]) != (1, True, ['park: the reviewer has a blocker on #12: [30 chars] [1]) (#218)
- [x] C12.16 **new** — A reviewer session that commits in the project (the fake runs `git commit
      --allow-empty -m x` there): `on` prints "park: the reviewer changed HEAD in the project on
      #12 (session `<uuid>`)" and exits 1; no `pr comment` is recorded; the run log holds the
      reviewer's end line and no `review` or `merged` line. One that writes an untracked file:
      the same with "`git status`". Red today: no reviewer.
      Test: `ReviewLoopTest.test_change_parks`.
      Plan: P63 "parks on a difference"
      Evidence: `ReviewLoopTest.test_change_parks` passes on `main` at `3774c34` (#214).
      seen red: python -m unittest tests.test_review_loop.ReviewConfigTest tests.test_review_loop.ReviewLoopTest.test_reviewed_then_merge_wait tests.test_review_loop.ReviewLoopTest.test_change_parks tests.test_review_loop.ReviewLoopTest.test_no_verdict_parks tests.test_review_loop.ReviewLoopTest.test_comment_failure_goes_on tests.test_review_loop.ReviewLoopTest.test_snapshot_git_fails tests.test_review_loop.ReviewBoxTest on main → AssertionError: Tuples differ: (0, 1, ['driver-<uuid>'], ['driver-<uuid>'], [18 chars]alse) != (0, 2, ['driver-<uuid>'], ['driver-<uuid>'], [132 chars]True) (#214)
      broken: a change in the project not parked (C12.16) → AssertionError: Tuples differ: (0, False, [['pr', 'comment', '12', '--bod[38 chars]True) != (1, True, [], [], True) (#214)
- [x] C12.17 **new** — A reviewer replying "looks fine": `on` prints "park: the reviewer gave no
      verdict on #12 (session `<uuid>`)" and exits 1, with a `pr comment` recorded for none; a
      reviewer session that ends with `is_error` true parks with the same line. Red today: no
      reviewer.
      Test: `ReviewLoopTest.test_no_verdict_parks`.
      Plan: none — a reply the driver cannot read parks, as a step session's does; `plan.md`
      names the reviewer's "blocker or none", not what an unreadable reply does.
      Evidence: `ReviewLoopTest.test_no_verdict_parks` passes on `main` at `3774c34` (#214).
      seen red: python -m unittest tests.test_review_loop.ReviewConfigTest tests.test_review_loop.ReviewLoopTest.test_reviewed_then_merge_wait tests.test_review_loop.ReviewLoopTest.test_change_parks tests.test_review_loop.ReviewLoopTest.test_no_verdict_parks tests.test_review_loop.ReviewLoopTest.test_comment_failure_goes_on tests.test_review_loop.ReviewLoopTest.test_snapshot_git_fails tests.test_review_loop.ReviewBoxTest on main → AssertionError: Tuples differ: (0, 1, ['driver-<uuid>'], ['driver-<uuid>'], [18 chars]alse) != (0, 2, ['driver-<uuid>'], ['driver-<uuid>'], [132 chars]True) (#214)
      broken: an errored reviewer read for its verdict (C12.17) → AssertionError: Tuples differ: (0, False, [['pr', 'comment', '12', '--body-file', '-']]) != (1, True, []) (#214)
- [x] C12.18 **new** — As C12.12 with `comment_code` 1: `on` prints "review: no comment on #12:
      " followed by a reason, writes the `review` line, and goes on to the merge wait. Red today:
      no reviewer.
      Test: `ReviewLoopTest.test_comment_failure_goes_on`.
      Plan: none — a failed comment does not stop the run; the run log keeps the verdict.
      Evidence: `ReviewLoopTest.test_comment_failure_goes_on` passes on `main` at `3774c34` (#214).
      seen red: python -m unittest tests.test_review_loop.ReviewConfigTest tests.test_review_loop.ReviewLoopTest.test_reviewed_then_merge_wait tests.test_review_loop.ReviewLoopTest.test_change_parks tests.test_review_loop.ReviewLoopTest.test_no_verdict_parks tests.test_review_loop.ReviewLoopTest.test_comment_failure_goes_on tests.test_review_loop.ReviewLoopTest.test_snapshot_git_fails tests.test_review_loop.ReviewBoxTest on main → AssertionError: Tuples differ: (0, 1, ['driver-<uuid>'], ['driver-<uuid>'], [18 chars]alse) != (0, 2, ['driver-<uuid>'], ['driver-<uuid>'], [132 chars]True) (#214)
      broken: no line for a failed review comment (C12.18) → AssertionError: differs: 0 (#224)
- [x] C12.19 **new** — As C12.12 with `container_image` and `container_secrets` in `driver.json`
      and the fake `docker`: the reviewer's `docker run` is named `driver-<uuid>` and its inner
      command holds `--settings /state/review-container-settings.json` and `--agents
      /state/agents.json --agent reviewer --session-id <uuid>`; `<state>/agents.json` and
      `<state>/review-container-settings.json` exist when it starts. Red today: no reviewer.
      Test: `ReviewBoxTest.test_reviewer_in_the_container`.
      Plan: P22 "never the step's session"
      Evidence: `ReviewBoxTest.test_reviewer_in_the_container` passes on `main` at `3774c34` (#214).
      seen red: python -m unittest tests.test_review_loop.ReviewConfigTest tests.test_review_loop.ReviewLoopTest.test_reviewed_then_merge_wait tests.test_review_loop.ReviewLoopTest.test_change_parks tests.test_review_loop.ReviewLoopTest.test_no_verdict_parks tests.test_review_loop.ReviewLoopTest.test_comment_failure_goes_on tests.test_review_loop.ReviewLoopTest.test_snapshot_git_fails tests.test_review_loop.ReviewBoxTest on main → AssertionError: Tuples differ: (0, 1, ['driver-<uuid>'], ['driver-<uuid>'], [18 chars]alse) != (0, 2, ['driver-<uuid>'], ['driver-<uuid>'], [132 chars]True) (#214)
      broken: the reviewer's container settings left at the step's (C12.19) → AssertionError: differs: 4 (#224)
- [x] C12.20 **hold** — Without `review` in `driver.json`, nothing changes: `tests/test_on.py`,
      `tests/test_merge_wait.py`, `tests/test_gated_merge.py`, `tests/test_wait.py` and
      `tests/test_runlog_fix.py` are unedited since `5bb5fa1` and pass, and C12.24's
      diff stays empty: no new test goes in a file they list.
      Test: `OnTest.test_merge_waits_on_the_fixed_pr`, `OnTest.test_wait_line_after_fix`,
      `MergeWaitTest.test_merged_pulled_evidence_waited`, `WaitTest.test_red_after_two_fixes_parks`.
      Plan: P23 "with the failing check's lines, filtered and capped, twice at most"
      Evidence: `OnTest.test_merge_waits_on_the_fixed_pr`, `OnTest.test_wait_line_after_fix`, `MergeWaitTest.test_merged_pulled_evidence_waited` and `WaitTest.test_red_after_two_fixes_parks` pass on `main` at `3774c34`; Verify's three `git diff`s print nothing there (#203, #214, #218). The last five lines are earlier Days' breaks whose finds Track E0 moved into `once.command` and `loop.fix`, recorded again under their own names (#209).
      broken: a third fix allowed for red checks (C12.20) → AssertionError: 3 != 2 (#203)
      broken: the reviewer run when review is absent (C12.20) → AssertionError: Tuples differ: (0, ['13', '13'], "on: 1 steps, the night's count") != (0, ['13'], "on: 1 steps, the night's count") (#214)
      broken: the settings not written before the session → AssertionError: Tuples differ: (True, True, False, False, True) != (True, True, True, True, True) (#209)
      broken: resume does not read PAST → FAILED (errors=1) (#209)
      broken: the halt check after a fix's resume → AssertionError: Tuples differ: ('opened: #7', 0, ['pid', 'end']) != ('halt: the halt file was set while the ses[33 chars]id']) (#209)
      broken: docker asked without the container keys → AssertionError: Tuples differ: (0, True, [['--version']]) != (0, True, []) (#209)
      broken: the session's container not named for its session → AssertionError: Tuples differ: (0, True, [], ['driver-probe-<uuid>', 'driver-other-<uuid>']) != (0, True, [], ['driver-probe-<uuid>', 'driver-<uuid>']) (#209)
- [x] C12.21 **hold** — Live, with `DRIVER_LIVE_REVIEW` set: on the PC's Claude Code, `claude -p
      --agents <a file defining probe> --agent probe` replies ORCHID; with
      `driver.settings.review`'s file, a session asked to run `git commit --allow-empty -m x`
      leaves the scratch repository's HEAD as it was and adds a line with "the reviewer only
      reads" to the scratch `hooks.jsonl`; with the image's two variables set, the first run in
      the image replies ORCHID too. True at Track F's start, not today: the flags are there
      (`claude --help`, Notes), and Tracks A and B add the settings and the hook it runs. It
      cannot be broken where it is replayed: it skips without `DRIVER_LIVE_REVIEW`, so its
      record is `broken: none → <why>`, as C11.21's is (D11.33); Track F's PR reports its run
      with `--agent probe` left out.
      Test: `ReviewLiveTest.test_agent_from_file`, `ReviewLiveTest.test_commit_refused`.
      Plan: P63 "reaches the session with `--agents` and `--agent`"
      Evidence: `ReviewLiveTest.test_agent_from_file` and `ReviewLiveTest.test_commit_refused` pass on this machine on `main` at `3774c34`, Claude Code 2.1.322, with `DRIVER_LIVE_REVIEW`, `DRIVER_CONTAINER_IMAGE` and `DRIVER_CONTAINER_SECRETS` set (#220, and again at the close).
      broken: none → live: it skips without DRIVER_LIVE_REVIEW, so CI and the replay never run it (D11.33, as C11.21) (#220)

- [x] C12.22 **new** — As C12.12 with a fake `git` that exits 1 on `status` before the review:
      `on` prints "cannot read the project: git failed before the review of #12", exits 2, and
      starts no reviewer session. Red today: no reviewer.
      Test: `ReviewLoopTest.test_snapshot_git_fails`.
      Plan: P63 "the driver compares HEAD, the refs, the stash and `git status` before and after
      it"
      Evidence: `ReviewLoopTest.test_snapshot_git_fails` passes on `main` at `3774c34` (#214).
      seen red: python -m unittest tests.test_review_loop.ReviewConfigTest tests.test_review_loop.ReviewLoopTest.test_reviewed_then_merge_wait tests.test_review_loop.ReviewLoopTest.test_change_parks tests.test_review_loop.ReviewLoopTest.test_no_verdict_parks tests.test_review_loop.ReviewLoopTest.test_comment_failure_goes_on tests.test_review_loop.ReviewLoopTest.test_snapshot_git_fails tests.test_review_loop.ReviewBoxTest on main → AssertionError: Tuples differ: (0, 1, ['driver-<uuid>'], ['driver-<uuid>'], [18 chars]alse) != (0, 2, ['driver-<uuid>'], ['driver-<uuid>'], [132 chars]True) (#214)
      broken: no git check before the review (C12.22) → AssertionError: differs: 2, 3 (#224)
- [x] C12.23 **hold** — As C12.12 with the pull request read `MERGED` at `wait_reviewed`'s first
      `pr view` (the maintainer merged it as the checks went green): no reviewer session starts,
      no `pr comment` is recorded, and the run goes on as `wait_merge` reads a merged pull
      request today. True today: no reviewer runs at all. Broken in Track E1 by reading a merged
      pull request as an open one.
      Test: `ReviewLoopTest.test_merged_before_review`.
      Plan: none — what a pull request merged before its review gets; `plan.md` says the
      reviewer runs before the merge, not what happens when the maintainer merges first.
      Evidence: `ReviewLoopTest.test_merged_before_review` passes on `main` at `3774c34` (#214, its hold settled by #215).
      broken: a merged pull request reviewed (C12.23) → AssertionError: Tuples differ: (0, [[30 chars]t"], 2, 1, [['pr', 'comment', '12', '--body-fi[28 chars]ed']) != (0, [[30 chars]t"], 1, 0, [], ['merged']) (#214)

- [x] C12.24 **hold** — The files C11.4 and C10.31 froze stay unchanged since `5d4f1b5`, all
      but `tests/test_usage_limit.py` and `tests/test_issues.py`, which a later spec change of
      #211's PR B edits: the C09.3 and C09.4 fix, and the 3 s bound of the issue close's time-out
      test, which failed 4 of 10 runs under load (D12.39). From that change's `83cf2f2`, those
      two stay unchanged too. Verify's `5d4f1b5` and `83cf2f2` diffs print nothing, and the
      outcome table's and the run log's tests pass unedited.
      Plan: N31 "The result event stays the record"
      Evidence: `git -c core.safecrlf=false diff --exit-code 5d4f1b5` over Verify's list prints nothing on this branch and at Day 12's close (#224); over `tests/test_usage_limit.py` and `tests/test_issues.py`, `git -c core.safecrlf=false diff --exit-code 83cf2f2` prints nothing (#225).
      broken: a byte added to driver/decide.py (C12.24) → import re (#224)
      broken: the issue close's comment sent with no time-out (D12.39) → AssertionError: None != 'gh issue comment timed out' (#225)
      broken: a reset past --limit-hours waited for, not parked (C09.3) → AssertionError: Tuples differ: (True, True, None, 1, ['limit']) != (True, True, 1, 1, ['park']) (#225)
      broken: the halt file not read during the wait (C09.4) → AssertionError: Tuples differ: (True, False, None, ['limit'], 1) != (True, True, 1, ['halt'], 1) (#225)
      Replaces: C11.4 — was: seven run log and outcome test files pass unedited since Day 11's spec, `tests/test_usage_limit.py` among them, and C10.31's diff stays empty.
      Replaces: C10.31 — was: the files Days 8 to 10 do not change are unchanged since Day 10's spec, over a list that holds `tests/test_issues.py`.

## Verify
```bash
python -m unittest tests.test_review_agents tests.test_readonly_hook tests.test_review_snapshot tests.test_review_verdict tests.test_review_loop tests.test_review_live tests.test_on tests.test_merge_wait tests.test_gated_merge tests.test_wait tests.test_runlog_fix tests.test_halt tests.test_box_command tests.test_recovery_holds -v
git -c core.safecrlf=false diff --exit-code 5bb5fa1 -- tests/test_on.py tests/test_merge_wait.py tests/test_gated_merge.py tests/test_wait.py tests/test_runlog_fix.py
git -c core.safecrlf=false diff --exit-code c8e5963 -- tests/test_once_outcome.py tests/test_once_run.py tests/test_runlog.py tests/test_runlog_end.py tests/test_once_halt.py tests/test_halt_race.py tests/test_once_stop.py tests/test_session_bound.py tests/test_box_command.py tests/test_status.py tests/test_status_trial.py tests/test_level_2_sentence.py tests/test_contract.py
git -c core.safecrlf=false diff --exit-code 495bf69 -- tests/test_contract.py tests/test_decide.py tests/test_dry_run.py tests/test_steps.py tests/test_tree.py tests/test_config.py tests/test_encoding.py tests/test_halt.py tests/test_halt_report.py tests/test_home.py tests/test_hooks.py tests/test_off.py tests/test_once_park_issues.py tests/test_once_parks.py tests/test_preflight.py tests/test_recovery_table.py tests/test_lock_takeover.py driver/decide.py driver/steps.py driver/home.py rules/session.md tests/test_failures.py tests/test_once_outcome.py tests/test_once_run.py tests/test_runlog.py tests/test_runlog_fix.py tests/test_session_bound.py tests/test_wait.py tests/test_kit_copy.py tests/test_lock.py tests/test_live_cli.py tests/test_once_halt.py tests/test_live_once.py tests/test_once_stop.py
git -c core.safecrlf=false diff --exit-code 5d4f1b5 -- tests/test_once_outcome.py tests/test_once_run.py tests/test_runlog.py tests/test_runlog_end.py tests/test_once_halt.py tests/test_halt_race.py tests/test_once_stop.py tests/test_session_bound.py tests/test_box_command.py tests/test_status.py tests/test_status_trial.py tests/test_level_2_sentence.py tests/test_on.py tests/test_contract.py tests/test_decide.py tests/test_dry_run.py tests/test_steps.py tests/test_tree.py tests/test_config.py tests/test_encoding.py tests/test_halt.py tests/test_halt_report.py tests/test_home.py tests/test_hooks.py tests/test_off.py tests/test_once_park_issues.py tests/test_once_parks.py tests/test_preflight.py tests/test_recovery_table.py tests/test_lock_takeover.py driver/decide.py driver/steps.py driver/home.py rules/session.md tests/test_failures.py tests/test_runlog_fix.py tests/test_wait.py tests/test_kit_copy.py tests/test_lock.py tests/test_live_cli.py tests/test_live_once.py
git -c core.safecrlf=false diff --exit-code 83cf2f2 -- tests/test_usage_limit.py tests/test_issues.py
```
`tests/test_review_live.py` skips unless `DRIVER_LIVE_REVIEW` is set, and its image run unless
`DRIVER_CONTAINER_IMAGE` and `DRIVER_CONTAINER_SECRETS` are set too; on this machine, run it with
all three set as well.

Where the tests live: `ReviewAgentsTest` and `ReviewSettingsTest` in
`tests/test_review_agents.py`; `ReadonlyHookTest` in `tests/test_readonly_hook.py`;
`ReviewSnapshotTest` in `tests/test_review_snapshot.py`; `ReviewVerdictTest` and
`ReviewCommentTest` in `tests/test_review_verdict.py`; `ReviewConfigTest`, `ReviewLoopTest` and
`ReviewBoxTest` in `tests/test_review_loop.py`; `ReviewLiveTest` in `tests/test_review_live.py`.
The loop's fake `claude` is a new file, `tests/fake_review.py`: it answers a session whose
arguments hold `--agent reviewer` from a list of replies in its JSON, one per call, the last
repeated, and any other session as `fake_claude` in `tests/test_once.py` does, which is not
edited. The fake `gh` in `tests/test_github.py` gains Track D's `pr comment`.

## Notes
- Picks up H10.1 (Day 10: whether the level 2 merge needs `live-check` run in the image) and
  passes it to Day 13, the merge, as H12.1: this day merges nothing (`plan.md`, "Course
  corrections", 2026-11-13). H09.2 and H10.2 are Day 13's to cite and pass to Day 14, as Day
  11's Notes say. H08.4 (the Level 2 count reads "still red after two fixes") meets this day's
  new park: H12.2.
- The reviewer runs at level 1 too (the maintainer's choice): it costs one more session per pull
  request and up to two fixes. P55's baseline ($1.86 and 34.4 replies per merged pull request)
  counts it from this day: its start line carries the run's issue, so `runlog.issue_cost` counts
  it, and Day 14's record reads the run log's `review` start and end lines.
- `review` is a switch in `driver.json`, not a level: absent is off, so that no hold test's call
  list changes. `driver.json` is gitignored: the maintainer sets `"review": true` in the driver's
  own copy after Track E2 merges (a `maintainer action:`), and a project whose `driver.json`
  leaves it out gets no reviewer.
- A blocker's fix runs through `loop.fix`, as a red check's does through `resume`, so it inherits
  H09.3 (a resumed session that meets the usage limit parks with no wait): the maintainer's.
- The head the reviewer is given is read after the checks went green. A commit pushed between
  the green and that read is reviewed, and its checks are not read again; Day 13's
  `--match-head-commit` on the `review` line's head is where that is closed (P64).
- The stash is compared by its top entry, `refs/stash` in `for-each-ref`: a `git stash drop` of
  an entry below the top changes no ref and is not seen. The hook refuses `git stash` in every
  form, so only a command the hook does not read could do it. Known limit.
- The read-only hook reads the command, as `guard.py` does (its Known limit): `bash -c "git
  commit"`, `sh -c`, `xargs git`, a script or an alias that runs git is not read, and `python -c`
  that writes a file gets through (`CLAUDE.md`, "The auditors", says the same of
  `auditor-guard.py`). The before-and-after comparison is what catches those, for what git shows.
- `--agents` with `--print` takes "the path to a file that holds one" (`claude --help`, 2.1.322):
  the driver passes the file, not the JSON, so no newline goes through cmd.exe.
- `gh pr comment` on the step's pull request is a new kind of write to the project's GitHub;
  until this day the driver wrote the run's issue, the park issues and the `parked` label. The
  maintainer chose it on 2026-11-15.
- **Assumed** — `claude -p` takes `--agents <file>` and `--agent <name>`: `claude --help` → "--agents
  <json-or-file>  JSON object defining custom agents, or with --print the path to a file that
  holds one", and "--agent <agent>  Agent for the current session", 2.1.322 (the PC's,
  2026-11-15). That a session so started follows the file's prompt and tools, on 2.1.322: not run
  (it costs a session); the main session runs Track F's first case once before Track E1 and
  records its reply in the PR of the track then open. `plan.md` ("What is not known") says it
  was checked only on 2.1.170.
- **Assumed** — `gh pr comment <n> --body-file -` reads the body from stdin: `gh pr comment
  --help` → "-F, --body-file file   Read body text from file (use "-" to read from standard
  input)", gh 2.93.0 (the main session, 2026-11-15; the auditor's guard refuses the command).
  That it prints the comment's URL and exits 0: not run (it writes): the main session runs it on
  a scratch pull request of this repository before Track D.
- **Assumed** — `gh api` with `-f` or `-F` sends a `POST` unless `-X` says otherwise: `gh api
  --help` → "The default HTTP request method is `GET` normally and `POST` if any parameters
  were added", gh 2.93.0 (2026-11-15). The help does not say `--input` alone sends a `POST`; the
  hook refuses `--input` as a body to send, whatever the method.
- **Assumed** — a PreToolUse hook from `--settings` fires in a session started with `--agent`:
  `plan.md` ("Where the driver lives") → "a session started with `--agent` gave its hooks the
  agent's name", on 2.1.170 only; `live-check` (`tests/test_live_cli.py`) runs no `--agent`.
  Track F's second case is the check on 2.1.322.
- **Assumed** — the project's own hooks and Claude Code write nothing `git status` shows and move
  no ref while a session runs: in bearing at `2e3dd70`, `.claude/tool-output/` and
  `.claude/state/` are ignored (its `.gitignore:10`, `:28`), its status is empty, and no hook of
  its pushes or fetches (the spec-auditor, 2026-11-15). Not checked: whether the image's Claude
  Code writes under `/work`; Track F's image run reports `git status` after it.
- Breaks on the holds. C12.20, in this spec-change PR, on today's code, since its tests exist:
  "a third fix allowed for red checks (C12.20)", `if used >= 2:` made `if used >= 3:` in
  `driver/loop.py`.
  It is caught by `WaitTest.test_red_after_two_fixes_parks` (the three other named tests pass
  with it in). Left to the track that adds the check or the code it breaks:
  - C12.20, Track E1: the reviewer run when `review` is absent.
  - C12.23, Track E1: a merged pull request reviewed (the MERGED read taken as open).
  - C12.21, Track F: `broken: none` (it skips where it is replayed); the PR reports the run with
    `--agent probe` left out.
- **Defect** D12.1 — found: auditor · cause: spec · made: Day 12 · the switch was to be set in the repository's `driver.json`, which is gitignored and untracked, so C12.11's clause could fail in CI (fixed in this PR: the maintainer sets it).
- **Defect** D12.2 — found: auditor · cause: spec · made: Day 12 · the snapshot's key `stash` is a string C07.1's `RecoveryRulesTest.test_no_command_that_can_lose_work` reads as a command that can lose work (fixed in this PR: `stash_top`).
- **Defect** D12.3 — found: auditor · cause: spec · made: Day 12 · C12.12 counted `--agents <path> --agent reviewer --session-id <uuid>` as five arguments; they are six (fixed in this PR).
- **Defect** D12.4 — found: auditor · cause: spec · made: Day 12 · C12.20's named tests all pass with its own break in; only `WaitTest.test_red_after_two_fixes_parks` sees it (fixed in this PR).
- **Defect** D12.5 — found: auditor · cause: spec · made: Day 12 · C12.6 to C12.9's Red today said `driver.review` does not exist, which Track A creates before them (fixed in this PR: Red at their track's start).
- **Defect** D12.6 — found: auditor · cause: spec · made: Day 12 · C12.21, a live hold, had a break that cannot replay where the test skips, and claimed true today for files Tracks A and B add (fixed in this PR).
- **Defect** D12.7 — found: auditor · cause: spec · made: Day 12 · Track E held the switch, the reviewer's run, the loop and the blocker's fix, past 400 changed lines (fixed in this PR: E0, E1, E2).
- **Defect** D12.8 — found: auditor · cause: spec · made: Day 12 · the "changed" park returned before the reviewer's end line, so its cost was lost (fixed in this PR: the end line first).
- **Defect** D12.9 — found: auditor · cause: spec · made: Day 12 · the reviewer's run log start and end values (issue, container, version, outcome) had no stated source (fixed in this PR).
- **Defect** D12.10 — found: auditor · cause: spec · made: Day 12 · nothing said what the head read does with a pull request already `MERGED` or `CLOSED`, or with no head (fixed in this PR, C12.22).
- **Defect** D12.11 — found: auditor · cause: spec · made: Day 12 · a git command failing in both snapshots gave `None` twice, which compared equal and passed (fixed in this PR, C12.22).
- **Defect** D12.12 — found: auditor · cause: spec · made: Day 12 · the Level 2 count (H08.4) ends only on "still red after two fixes", and the spec did not say whether the blocker's park ends it (fixed in this PR: H12.2).
- **Defect** D12.13 — found: auditor · cause: spec · made: Day 12 · Out of scope said a pull request the maintainer opened is not reviewed, while `github.mine` waits on them and C12.15 reviews one (fixed in this PR).
- **Defect** D12.14 — found: auditor · cause: spec · made: Day 12 · the breaks paragraph named only rewritten finds in `driver/loop.py`, not the finds in `settings.py`, `once.py` and `loop.py` that new code would make occur twice (fixed in this PR).
- **Defect** D12.15 — found: auditor · cause: spec · made: Day 12 · `wait_found` lacks `home` and `config`, and frozen tests call `loop.resume` as it is; the spec said neither (fixed in this PR: E0, `loop.fix`).
- **Defect** D12.16 — found: auditor · cause: spec · made: Day 12 · an Assumed line said `live-check` repeated the `--agent` hook check on 2.1.322, which runs no `--agent`, and read `--input` into `gh api`'s help (fixed in this PR).
- **Defect** D12.17 — found: auditor · cause: spec · made: Day 12 · C12.3's "byte for byte as on `5bb5fa1`" named no test that checks it (fixed in this PR).
- **Defect** D12.18 — found: auditor · cause: spec · made: Day 12 · C12.16's "the merge wait never starts" had no evidence a test can see (fixed in this PR: no `review` or `merged` line).
- **Defect** D12.19 — found: auditor · cause: spec · made: Day 12 · "git commands the driver already uses" was wrong: no driver code runs `for-each-ref` today (fixed in this PR).
- **Defect** D12.20 — found: auditor · cause: spec · made: Day 12 · the Notes said the driver wrote only to the run's issue; it also writes park issues and the `parked` label (fixed in this PR).
- **Defect** D12.21 — found: auditor · cause: spec · made: Day 12 · the read-only hook let through a single `&`, `NAME=value git`, `env git`, `(git`, PowerShell's `& git`, refused `git --no-pager diff`, and the snapshot missed a branch switch at the same commit (fixed in this PR).
- **Defect** D12.22 — found: auditor · cause: spec · made: Day 12 · four `Plan:` lines claimed more than their criteria show: C12.17's P31, C12.5's P22, C12.12's P64 (fixed in this PR); C12.12's P55 now asserts the cost.
- **Defect** D12.23 — found: auditor · cause: spec · made: Day 12 · the spec did not say `status` shows the reviewer as one more step row with no estimate (fixed in this PR: Out of scope, H12.3).
- **Defect** D12.24 — found: auditor · cause: spec · made: Day 12 · the Notes said H09.2 and H10.2 go to Day 14 "as Day 11's Notes say"; Day 11 says Day 13 cites them and passes them on (fixed in this PR).
- **Defect** D12.25 — found: seen red · cause: spec · made: Day 12 · C12.22 tagged `new` a first half, a merged pull request starting no reviewer, that is true on `main`, where no reviewer runs at all; "Track tests seen red" failed Track E1's PR (#214) on `ReviewLoopTest.test_merged_before_review` (fixed in a second spec change: that half is C12.23, a `hold`).
- **Defect** D12.26 — found: break on purpose · cause: implementation · made: Day 12 · C12.9's fixed head `abc1234` reads to `break.py` as a commit hash, so Track D's first C12.9 break was refused; `test_body` now compares the empty body's lines after the header first, so a failure there prints no head (#208).
- **Defect** D12.27 — found: Track E0 · cause: process · made: Day 12 · Day 6's "the resume keeps --session-id" was refused by `break.py` (its report holds the test's fixed uuid), and the main session edited `tests/test_wait.py` to fix the message, a file C10.31 and C11.4 freeze; CI's "Frozen files stay unedited" failed. Reverted; the entry is not recorded again, its find moved into `loop.fix` byte for byte (#209).
- **Defect** D12.28 — found: Track E0 · cause: process · made: Day 06 · three Day 6 records held no report, and their `broken:` lines (C06.4, C06.9, C06.10) no longer matched what their tests print; CI's "A track's breaks replay" found them on the first PR since to touch `driver/loop.py`. Their reports were taken from CI's `linux-reports` artifact and the three spec lines changed (#209).
- **Defect** D12.29 — found: self · cause: implementation · made: none · `break.py --take-reports` rewrote all 73 lines of the manifest in another indentation; the two-space format was restored by hand (#209).
- **Defect** D12.30 — found: self · cause: environment · made: none · the wrapper Track E0's recordings first ran through crashed printing an arrow to the cp1252 console; re-run with `PYTHONIOENCODING=utf-8`, which replaced the entries (#209).
- **Defect** D12.31 — found: break on purpose · cause: process · made: Day 12 · the first C12.20 break, the reviewer run when `review` is absent, was run against `OnTest.test_wait_line_after_fix`, which passed with it in: `OnCase` reads the pull request as `MERGED` by default, so the reviewer is skipped there. `OnTest.test_merge_waits_on_the_fixed_pr`, which counts the `pr view` calls, sees it (#214).
- **Defect** D12.32 — found: break on purpose · cause: implementation · made: Day 12 · the first break of a merged pull request reviewed (C12.23) was refused by `break.py`: its report held the reviewer's uuid. The two tests now compare the count of reviewer sessions (#214).
- **Defect** D12.33 — found: Track E2 · cause: process · made: Day 12 · the brief's fake `gh` views for three of Track E2's tests were OPEN only, so on `main` the merge wait never ended and the tests timed out, an error and not a red; each view list now ends in MERGED (#218).
- **Defect** D12.34 — found: Track B · cause: implementation · made: Day 09 · same-as: D11.29 · `UsageLimitTest.test_far_reset_parks` failed in Track B's full run, in a file the track does not touch, then 25 of 25 alone under `--repeat 5` (#205).
- **Defect** D12.35 — found: Track C · cause: implementation · made: Day 11 · same-as: D11.25 · `PhoneTest.test_heartbeat_comment_edited_in_place` failed in Track C's full run and 4 of 5 under `--repeat 5`, then 3 of 3 on `main` and on the branch (#207); again in Track E2's full run (#218) and in Track F's first CI run, whose re-run passed (#220).
- **Defect** D12.36 — found: Track E1 · cause: implementation · made: Day 11 · same-as: D11.32 · `HeartbeatTest.test_heartbeat_beats_through_a_quiet_tool` failed once in Track E1's full run and 3 of 5 on `main`'s code under `--repeat 5` (#214), and 3 of 3 under `--repeat 3` straight after Track E2's full run (#218).
- **Defect** D12.37 — found: Day 12 review · cause: process · made: Day 12 · five `new` criteria, C12.11, C12.12, C12.18, C12.19 and C12.22, closed with a seen-red line and no break: their tests' reports held unittest's shortened `[N chars]`, which `break.py` refuses, and the close let them through (#212, S21). Their tests now report in short fixed words and their breaks are recorded, pinned at `e0f8f52`, since the close's tests print the long reports (#224).
- **Defect** D12.38 — found: Day 12 review · cause: implementation · made: Day 12 · `driver/loop.py` reports a failed `git` after the review as "git failed before the review of #<n>", the same line as the check before it; nothing tests the second. Left to Day 13 (H12.5).
- **Defect** D12.39 — found: Day 12 review · cause: implementation · made: Day 05 · `IssueWritesTest.test_close_times_out` took 3.25 s against its 3 s bound and failed 4 of 10 runs under load; the fix goes in the second spec change of #211's PR B, with C09.3 and C09.4's, since C12.24 must land first to lift the freeze on `tests/test_issues.py` (#224). Fixed there: the fake `gh` sleeps 30 s, not 5, and the bound is 15 s; 10 of 10 under load, beside `tests/test_usage_limit.py` (the C09.3 and C09.4 fix, 10 of 10) and `tests/test_once_stop.py` (10 of 10) run at once (#225).
- **Defect** D12.40 — found: Day 12 review · cause: process · made: Day 12 · the restored C09.3 and C09.4 tests compared whole tuples with a line in them, so their breaks reported "[43 chars]", which `break.py` refuses since #223, and no longer matched Day 09's lines: each test now compares first words, then the line, and both breaks are recorded again under C12.24. And C12.24's `83cf2f2` Verify line fails when `evidence.py` replays Day 12 at its close commit `51f8450`, where the two files are older: a freeze re-pinned after a close fails that replay by construction, and only a local replay of Day 12 runs it again (#225).
- **Hand-off** H12.1 → Day 13: H10.1's question, whether the level 2 merge needs `live-check` run
  in the image, is the merge's call: this day runs the reviewer in the image (C12.19, C12.21)
  but merges nothing.
- **Hand-off** H12.2 → Day 13: whether `status.level_2_run` ends on "the reviewer still has a
  blocker on #<n> after two fixes" as it ends on "still red after two fixes" (H08.4).
- **Hand-off** H12.3 → Day 14: `status` shows the reviewer's session as a step row with the
  step's sentence and no estimate; whether the record wants it as its own kind.
- **Hand-off** H12.4 → Day 13: Day 05's P25 and P37, linked here to the criteria that hold their
  parks (C01.3, C05.4; C04.10, C08.16), leave two parts with no criterion: the plan-auditor's
  report the phase's park carries, and the last phase's three auditors; and a park that names
  "the audit found nothing" when no spec-change PR opens. And Day 08's P51, linked to C02.1 and
  C01.3: its token scope (contents, pull requests and issues) has no check, and may no longer be
  wanted with the container (#211, PR D). P08 and N10 stay in `specs/plan/overdue.json`, settled
  by Day 13 (#224).
- **Hand-off** H12.5 → Day 13: D12.38's line for a `git` that fails after the review, and a test
  of it.
- The Notes' five **Assumed** lines, as the tracks found them: `--agents <file>` with `--agent probe` replied ORCHID on 2.1.322 before Track E1 (#214) and in Track F's live test (#220); `gh pr comment 208 --body-file -` printed the comment's URL and exited 0, gh 2.93.0 (#208); the read-only hook from `--settings` fired in a session started with `--agent` and refused its commit, HEAD unmoved (#220); the image's Claude Code left nothing under `/work` that `git status --porcelain --ignored` shows (#220). `gh api --input` alone is refused whatever its method, as the line says; nothing ran it.
- At the close, on `main` at `3774c34`: Verify's tests ran 96, OK, none skipped, with `DRIVER_LIVE_REVIEW`, `DRIVER_CONTAINER_IMAGE` and `DRIVER_CONTAINER_SECRETS` set, so `ReviewLiveTest` ran on the PC and in the image; Verify's three `git diff`s print nothing. Full suite (`python scripts/test-parallel.py`): 449 tests, two failures, the load flakes D12.35 and D12.36 (`test_heartbeat_comment_edited_in_place`, `test_heartbeat_beats_through_a_quiet_tool`); each file passed run alone straight after (5 tests OK, 1 test OK).
- The manifest is the tracks' own records (`break.py --record` on each `day-12/` branch): 26 entries, and `python scripts/break-lines.py --spec specs/day-12-the-reviewer.md` finds the spec's 26 `broken:` lines agree with it. The five Track E0 recorded again, under C12.20, are Days 4, 6, 9 and 10's, whose own manifests keep them too; Day 6's "the resume keeps --session-id" was not recorded again (D12.27): its find moved byte for byte and Day 6's entry still replays.
- Five `new` criteria closed with a seen-red line and no break of their own: C12.11, C12.12, C12.18, C12.19 and C12.22 (Track E1's four breaks sit under C12.16, C12.17, C12.20 and C12.23). Their breaks came after the close (D12.37), pinned at `e0f8f52`; with C12.24's, added after the close too, the manifest has 32 entries and the spec 32 `broken:` lines (#224).
- Maintainer action, still open: `"review": true` in the driver's own `driver.json` (gitignored), as the Notes above say; until then the driver runs no reviewer.
- The blind relabel (`scripts/relabel.py`) ran on 36 entries; the last whole run agreed on 33 of 36 stages, 31 of 36 causes and 32 of 36 `made:`. After the first run, D12.26's cause changed from `spec` to `implementation`: the fix went into the test, not the spec. Kept: D12.34 to D12.36 as escapes, `implementation`, `made:` Day 09 and Day 11, as D11.29, D11.25 and D11.32 (the rater, reading no `same-as:`, saw no origin and read the machine's load); D12.29 `implementation`, `break.py` being this repository's own script; D12.33 `process`, the views being my brief's, as D11.24; D12.30 `made: none`, the console's codepage being the machine's, as D11.22.
