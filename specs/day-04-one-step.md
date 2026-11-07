# Day 04 — One step: `--once` checks, writes the run log, starts one session and finds its pull request

**Phase:** 1 · **Depends on:** Day 3 · **Expected PRs:** 9

## Goal
`python run-steps.py --once` does one step of a project: it refuses while halted, takes the lock,
checks the driver's own repository, runs the preflight, decides as the dry run does, checks the
evidence run on `origin/main`, writes the run log's line, starts one `claude -p` session with the
driver's settings and rules, and ends with the step's pull request, found on GitHub by branch and
author, or a park with its reason. A halt during that step kills the session's tree, shown on a
stand-in and, by hand, on a real session.

## In scope
- **Reading the kit's output** (H03.6, picks up H01.8 and H02.4, fixes D02.11). `run_drift` in
  `driver/preflight.py` decodes `scripts/spec-drift.py`'s output with `errors="replace"`: the
  output is not read for anything, and the JSON comes from its file. `run-steps.py` writes its
  stdout and stderr as UTF-8 when they are not a console (`sys.stdout.reconfigure(encoding=
  "utf-8")` when `not sys.stdout.isatty()`, the same for stderr), whatever the locale and
  `PYTHONIOENCODING` say: a parent that reads the dry run's line, as `--once`'s callers and the
  tests do, reads UTF-8. A console keeps its own encoding. The reconfigure runs in
  `run-steps.py`'s `if __name__ == "__main__":` block, before `main()`, never inside `main()`:
  `test_dry_run` and `test_preflight` call `main()` in-process under `redirect_stdout`, and a
  `StringIO` has no `reconfigure` (D04.3). The line ending stays the platform's.
- **`--permission-mode` in the preflight** (H03.7): `FLAGS` in `driver/preflight.py` gains
  `--permission-mode`, after `--max-budget-usd`. `tests/test_preflight.py`'s fake help text and
  its list of flags gain it; nothing else in that file changes.
- **The run log** (`driver/runlog.py`), `<state>/run.jsonl`, one JSON object per line, written
  as UTF-8 bytes ending in `\n`, appended, flushed and `os.fsync`ed before the call returns
  (`plan.md`, "Recovery", rule 1):
  - `start(state, step, prefix, session, claude)` appends `{"event": "start", "at": "<ISO 8601,
    UTC>", "step": <the sentence>, "prefix": <the step's branch prefix>, "session": <uuid>,
    "claude": <the first line of the CLI's --version>}`;
  - `end(state, session, outcome, cost_usd, denials)` appends `{"event": "end", "at": ...,
    "session": ..., "outcome": <the line --once printed>, "cost_usd": <number or null>,
    "denials": <int>}`;
  - `open_session(state, prefix)` returns `(session, None)` for the last `start` line with that
    prefix whose session has no `end` line, `(None, None)` when there is none or no log, and
    `(None, "the run log cannot be read at line <n>")` for a line that is not a JSON object (a
    torn last line after a crash included): a torn log parks, it is never guessed past.
- **The driver's own repository** (`driver/home.py`, H03.5). `check(home, started=None)` returns
  `(head, reason)`: `head` is `git rev-parse HEAD` in `home`, and `reason` is `None` or one of
  - "the driver's folder `<home>` is not a git repository";
  - "the driver's repository has changes: `<path>`, `<path>`", the paths of `git status
    --porcelain` in its order (an untracked folder shows as `sub/`), with untracked
    `evidence-rehearsal.json` and `evidence.json` at
    the repository's root left out (a close leaves them; H03.8 is the kit's fix). `state/` and
    `driver.json` never show: git ignores them (Day 3);
  - with `started` given and HEAD elsewhere: "the driver's repository moved from `<started, 7
    characters>` to `<head, 7 characters>`".
  Changes come before a move. Its git commands are `status --porcelain` and `rev-parse HEAD`.
- **The GitHub reads** (`driver/github.py`), each through the program `--gh` names (default
  `gh`, found with `shutil.which` as the preflight finds `claude`, so a `.cmd` is found on
  Windows), in the project's folder, with `GH_PROMPT_DISABLED=1`:
  - `evidence_line(project, gh, sha)` (H01.5) runs `gh run list --workflow evidence.yml --commit
    <sha> --limit 1 --json status,conclusion`, `<sha>` the full 40 characters (`gh` matches no
    abbreviation: `--commit 1dc0f03` lists no run), and returns `None` for a run with status
    `completed` and conclusion `success`; otherwise "park: no evidence run on `<sha7>` yet",
    "park: the evidence run on `<sha7>` has not finished (`<status>`)", "park: the evidence run
    on `<sha7>` ended `<conclusion>`", or, when `gh` exits non-zero or prints no JSON list,
    "cannot read the project: gh run list exited `<n>`".
  - `step_prs(project, gh, step)` runs `gh pr list --state open --author @me --limit 100 --json
    number,headRefName,url` and returns `(prs, None)`, the PRs whose `headRefName` is a branch of
    the step by `driver.decide`'s `_is_branch_of`, by number; or `([], "cannot read the project:
    gh pr list exited <n>")`. The author filter is the driver's own, not `spec-drift.py`'s
    (`plan.md`, "What the driver needs from the kit"; Phase 1 audit, finding 8). No PR title or
    body is read.
- **The session's rules** (`rules/session.md`, committed), passed with
  `--append-system-prompt-file` (`plan.md`, "What to build", item 3). It says, each as its own
  line: the session was started by the driver and nobody watches it; when the step needs the
  maintainer (a "Stop and ask" of the project's `CLAUDE.md`, a decision that is theirs, a
  criterion that cannot be met), open no pull request and end the last reply with one line,
  `PARK: <the reason, in one sentence>`; never merge and never push to `main`; a lesson for
  `CLAUDE.md` goes in the day's Notes as a `Hand-off` line to the maintainer, and `CLAUDE.md` is
  not edited. Each of the four holds its own words: "nobody watches", "PARK: <", "never merge"
  and "Hand-off" (C04.9).
- **`python run-steps.py --once [--config <file>] [--project <path>] [--state <dir>] [--claude
  <program>] [--gh <program>] [--model <name>]`** (`driver/once.py`; picks up H02.2, H03.1,
  H03.10, H01.6). `--model` defaults to `opus`, the main session's model (`plan.md`, "What to
  build", item 2). `--once` with `--dry-run` or a command exits 2 with "run-steps.py: --once
  goes alone". With neither `--dry-run`, `--once` nor a command, the line "run-steps.py: only
  --dry-run and preflight exist yet" becomes "run-steps.py: give --dry-run, --once or a
  command". In this order, and the first that applies ends the run:
  1. On POSIX, it makes itself the leader of its own process group (`os.setpgid(0, 0)`), so that
     `halt` kills the session with it (Day 3, "The tree").
  2. The halt file `<state>/halt` exists: "cannot start: halted: `<state>/halt` exists;
     run-steps.py clear removes it", exit 2.
  3. The config is read whole, always, since `--once` needs `budget_usd`; `--project`, when
     given, takes the place of its `project`. Its lines as Day 3's, exit 2.
  4. `driver.lock.take(state)`; its refusal line, exit 2. From here the lock is released on every
     way out but a kill.
  5. `driver.home.check(home)`; "cannot start: `<reason>`", exit 2. The HEAD it returns is the
     commit the driver started from.
  6. The preflight, `kit_lines` and `cli_lines`: its lines, exit 2.
  7. The dry run's facts and `decide()`. Anything but `start` prints the dry run's line and exits
     as the dry run does: 0 for `wait`, 1 for `park`.
  8. `evidence_line` for `origin/main`'s sha from the facts: its line, exit 1 for a park, 2 for
     "cannot read the project".
  9. `open_session(state, prefix)`: a session gives "park: the run log names session `<uuid>`
     for this step, with no end", a reason gives "park: `<reason>`"; exit 1.
  Before Track E (#26), a step that passed step 9 printed "would start: `<the sentence>`" and exited 0,
  with the lock released, no settings written and no run-log line.
  10. `driver.settings.write(state, home)` (afresh), a new `uuid4`, then `runlog.start(...)`.
  11. The session, with the project's real path as cwd (`os.path.realpath`; H03.10, D03.15):
      `<claude> -p --model <model> --output-format json --max-budget-usd <budget_usd>
      --permission-mode auto --strict-mcp-config --settings <state>/settings.json
      --append-system-prompt-file <home>/rules/session.md --session-id <uuid>`, `<claude>`
      found with `shutil.which`, every path absolute, `<budget_usd>` as `str()` of the config's
      number. No argument holds the prompt: it goes to the session's stdin as UTF-8 bytes, and
      stdin is then closed (`-p` with no prompt reads stdin). An argument to npm's `claude.cmd`
      passes through `cmd.exe`, which drops a newline and every argument after it (D04.2). The
      prompt is two lines: "Next step: `<the sentence>`" and "Do this one step as CLAUDE.md
      says, open its one pull request, and stop." The session's stdout is read as UTF-8 with
      `errors="replace"`.
  12. The outcome (Track F), its run log `end` line, and the driver's repository checked again.
  Before Track F (#28), step 12 was "ended: session `<uuid>`" and exit 0, with no end line.
- **The outcome** (Track F). From the session's stdout, the first rule that applies:

  | The session | The line | Exit |
  |---|---|---|
  | stdout is not a JSON object | "park: the session ended without a result (exit `<n>`; session `<uuid>`)" | 1 |
  | `is_error` is true | "park: the session ended in an error: `<subtype>` (session `<uuid>`)", `unknown` when there is no subtype | 1 |
  | the last non-blank line of `result`, stripped, starts `PARK:` | "park: the session parked: `<the rest, stripped>` (session `<uuid>`)" | 1 |
  | `step_prs` finds one | "opened: #`<n>` from `<headRefName>`" | 0 |
  | it finds none | "park: the session ended with no pull request and no PARK line (session `<uuid>`)" | 1 |
  | it finds more than one | "park: the step has more than one pull request: #`<a>`, #`<b>`" | 1 |
  | `step_prs` gives a reason | "cannot read the project: gh pr list exited `<n>`" | 2 |

  The `end` line records that line, `total_cost_usd` (null when absent) and the number of
  `permission_denials` (0 when absent): the run log counts refusals, the driver never changes the
  permission mode (`plan.md`, "When the driver parks"). Then `driver.home.check(home, started)`:
  a reason writes `<state>/halt` ("halted at `<ISO 8601>`: `<reason>`") and prints a second
  line, "halt: set during the step; `<reason>`", exit 1 (`plan.md`, "What the separate folder
  protects": the guard reads commands, the check finds what got past it).
- **The tests' fakes.** A fake `gh` (Track C, in `tests/test_github.py`): it answers `run list`
  and `pr list` from a `fake.json` beside it, appends each call's arguments to `calls.jsonl`
  beside it, and exits 99 on anything else; for `pr list` with `--author @me` it returns only the
  PRs whose `author` in its file is `me`. A fake `claude` and a copy of the driver (Track D, in
  `tests/test_once.py`): the fake answers `--version` and `--help` as Day 2's does, and a
  session by recording its arguments, its stdin's bytes, its cwd, whether `<state>/lock` and
  `<state>/settings.json`
  exist, then doing what its file says (sleep, start a child, write a file, commit in a
  folder) and printing its file's JSON with `session_id` set to its `--session-id`. The copy is
  `run-steps.py`, `driver/`, `hooks/`, `rules/` and `.gitignore` committed into a scratch git
  repository: every `--once` test runs the copy, so the self-check reads a repository the test
  owns, and a work in progress in this one never fails it. Later tracks import these helpers
  from those files; each new test file imports a new `driver` module in `setUp` (`importlib`),
  as Day 3's do (D03.8).
- Tests in `tests/test_encoding.py`, `tests/test_runlog.py`, `tests/test_home.py`,
  `tests/test_github.py`, `tests/test_once.py`, `tests/test_once_outcome.py`,
  `tests/test_once_halt.py`, `tests/test_live_once.py`, and the two edits to
  `tests/test_preflight.py` above. No other earlier test file is edited.

## Out of scope
- The run's issue, the `parked` issue, when a park counts as answered, the phone's `STOP`, `off`,
  and "the same step failed twice" from the run log's `end` lines — Day 5 (H01.1, H03.2, H04.1).
- `on`, the loop, `gh pr checks --watch`, a fix resumed on a red check, the merge waited for,
  `main` pulled, a clean tree brought to `main` (H01.2), `steps_per_night`, `human_only`, `on`
  refusing while halted (H03.4), the preflight before `on` (H02.3) — Day 6.
- Refusing a Claude Code version the live check has not passed on — Day 6 (H03.9 → H04.2).
- A stale lock taken over, a run-log session whose process still lives, and `status` — Day 7
  (H03.3, H04.3).
- The kit's ignore list for `evidence-rehearsal.json` and `evidence.json` — the maintainer
  (H03.8). Until it lands, a project with those files untracked has a tree that is not clean,
  and `--once` parks on it as the dry run does.
- Any change to `driver/decide.py`, `driver/steps.py`, `driver/lock.py`, `driver/settings.py`,
  the hooks, or the lines of `--dry-run`, `preflight`, `halt` and `clear`. `read_facts` may move
  from `run-steps.py` into a `driver` module unchanged.

## Tracks

| Track | Owner | Work |
|---|---|---|
| A | | C04.1–C04.3: the kit's output read, UTF-8 stdout, `--permission-mode` in the preflight; C04.14's two breaks |
| B | | C04.4, C04.5: the run log and the driver's own repository |
| C | | C04.6, C04.7: the evidence run and the step's PRs, the fake `gh` |
| D | | C04.8: `--once`'s steps 1-9, the copy of the driver, the fake `claude` |
| E | | C04.9: steps 10-11, the session started, the rules file |
| F | | C04.10, C04.11: the outcome, the `end` line, the check after the step |
| G | | C04.12, C04.13: a halt during `--once`, on a stand-in and live |

D needs A's flag, B and C; E needs D; F needs E; G needs F. A, B and C do not depend on each
other. C04.14 is held by every track, and each track that edits no earlier test file runs its
diff; Track A's row names it so that one track owns its breaks (D03.16). A track
that would pass 400 changed lines is split by a spec change first, not on its branch: CI's
"Track tests seen red" knows only this table's rows (D03.12).

## Acceptance criteria
Tick each box in the closing PR once its evidence is in it; under a box left unticked, write
`Not proven: <why>` (`specs/README.md`, "Evidence at the close").
- [x] C04.1 **new** — With a project whose `scripts/spec-drift.py` writes its JSON and then the
      bytes "next: Day 02 Track B: C02.4", 0x96, "C02.6" and a newline to its stdout (the en
      dash in Windows-1252), `python run-steps.py --dry-run --project <path>` exits 0, prints
      the start line on stdout, and prints nothing on stderr; `preflight` with a fake CLI prints
      "preflight: ok" and nothing on stderr.
      Red today: the strict UTF-8 decode raises `UnicodeDecodeError`, and a traceback reaches
      stderr (D02.11), on any system: the fixture writes the byte itself.
      Test: `EncodingTest.test_drift_output_not_utf8`, `EncodingTest.test_preflight_output_not_utf8`.
      Evidence: `EncodingTest.test_drift_output_not_utf8`, `EncodingTest.test_preflight_output_not_utf8` (#22).
      seen red: python -m unittest tests.test_encoding.EncodingTest.test_drift_output_not_utf8 on main → AssertionError: b'Exception in thread Thread-1 (_readerthre[706 chars]\r\n' != b'' (#22)
      seen red: python -m unittest tests.test_encoding.EncodingTest.test_preflight_output_not_utf8 on main → AssertionError: b'Exception in thread Thread-1 (_readerthre[706 chars]\r\n' != b'' (#22)
- [x] C04.2 **new** — `python run-steps.py --dry-run --project <path>` on a project whose next
      step is "Day 01 Track A: C01.1–C01.3", run with `PYTHONIOENCODING=cp1252` and no
      `PYTHONUTF8`, writes to its stdout pipe the bytes of "start: Day 01 Track A: C01.1–C01.3"
      in UTF-8 (`\xe2\x80\x93` for the dash) and `os.linesep` (`\r\n` on Windows).
      Red today: stdout follows `PYTHONIOENCODING` and writes byte 0x96.
      Test: `EncodingTest.test_stdout_is_utf8_in_a_pipe`.
      Evidence: `EncodingTest.test_stdout_is_utf8_in_a_pipe` (#22).
      seen red: python -m unittest tests.test_encoding.EncodingTest.test_stdout_is_utf8_in_a_pipe on main → AssertionError: b'start: Day 01 Track A: C01.1\x96C01.3\r\n' != b'start: Day 01 Track A: C01.1\xe2\x80\x93C01.3\r\n' (#22)
- [x] C04.3 **new** — The preflight's flag check lists `--permission-mode`: a help text without
      it gives "cannot run a session: `<program>` --help lists no --permission-mode", in the
      order of `FLAGS` (after `--max-budget-usd`), and the fake help with it gives "preflight:
      ok".
      Replaces: C02.5 — was: the preflight checks `--print`, `--model`, `--output-format`,
      `--max-budget-usd`, `--strict-mcp-config`, `--settings`, `--append-system-prompt-file`,
      `--session-id` and `--resume`, and no `--permission-mode`.
      Red today: the "no flag" subtest expects ten lines and gets nine.
      Test: `CliPreflightTest.test_every_flag_is_listed`.
      Evidence: `CliPreflightTest.test_every_flag_is_listed` (#22).
      seen red: python -m unittest tests.test_encoding tests.test_preflight.CliPreflightTest.test_every_flag_is_listed on main → AssertionError: Tuples differ: (2, '[579 chars]no --strict-mcp-config\ncannot run a session: [460 chars]e\n') != (2, '[579 chars]no --permission-mode\ncannot run a session: C:[584 chars]e\n') (#22)
- [x] C04.4 **new** — `driver.runlog`: after `start(...)` returns, a second process reads
      `<state>/run.jsonl` and finds the line, parsed, with the six keys of In scope; `end(...)`
      appends its line after it; the file's bytes hold no `\r`. `open_session` returns the
      session of a `start` with no `end`, `(None, None)` once its `end` is written, `(None,
      None)` for another prefix and for no log, and `(None, "the run log cannot be read at line
      2")` when line 2 is `{"event": "sta` with no newline.
      Red today: `driver/runlog.py` does not exist; each test errors at its `setUp` import.
      Test: `RunLogTest.test_start_line_is_on_disk`, `RunLogTest.test_end_line`,
      `RunLogTest.test_open_session`, `RunLogTest.test_torn_log`.
      Evidence: `RunLogTest.test_start_line_is_on_disk`, `RunLogTest.test_end_line`, `RunLogTest.test_open_session`, `RunLogTest.test_torn_log` (#23).
      seen red: python -m unittest tests.test_runlog.RunLogTest.test_start_line_is_on_disk on main → FAILED (errors=1) (#23)
      seen red: python -m unittest tests.test_runlog.RunLogTest.test_end_line on main → FAILED (errors=1) (#23)
      seen red: python -m unittest tests.test_runlog.RunLogTest.test_open_session on main → FAILED (errors=1) (#23)
      seen red: python -m unittest tests.test_runlog.RunLogTest.test_torn_log on main → FAILED (errors=1) (#23)
      Not replayed, its report holds a session uuid that differs on every run (D04.6): "open_session
      drops the last line whether or not it ends in a newline" failed
      `RunLogTest.test_torn_log`, and "open_session ignores end lines" failed
      `RunLogTest.test_open_session` (#23).
      Not replayed in CI, it bites on Windows only (D04.7): "the run log writes the platform line
      ending" failed `RunLogTest.test_end_line` with a carriage return found in the line; on
      Linux `os.linesep` is a bare newline and the break passes, so a local Windows run guards
      it, not CI (#23).
- [x] C04.5 **new** — `driver.home.check` on a scratch repository: clean gives `(<HEAD>, None)`;
      an edited tracked file and an untracked `notes.txt` give "the driver's repository has
      changes: " and both paths; untracked `evidence-rehearsal.json` and `evidence.json` at the
      root give no reason, and `sub/evidence.json`, in a `sub/` that holds a committed file,
      gives "the driver's repository has changes: `sub/evidence.json`"; a commit after
      `started` gives "the
      driver's repository moved from `<a>` to `<b>`" with the two 7-character shas; a folder
      that is not a repository gives "the driver's folder `<home>` is not a git repository".
      Red today: `driver/home.py` does not exist; `ImportError` in `setUp`.
      Test: `HomeTest.test_clean`, `HomeTest.test_changes_named`,
      `HomeTest.test_ignored_close_files`, `HomeTest.test_moved`,
      `HomeTest.test_not_a_repository`.
      Evidence: `HomeTest.test_clean`, `HomeTest.test_changes_named`, `HomeTest.test_ignored_close_files`, `HomeTest.test_moved`, `HomeTest.test_not_a_repository` (#23).
      seen red: python -m unittest tests.test_home.HomeTest.test_clean on main → FAILED (errors=1) (#23)
      seen red: python -m unittest tests.test_home.HomeTest.test_changes_named on main → FAILED (errors=1) (#23)
      seen red: python -m unittest tests.test_home.HomeTest.test_ignored_close_files on main → FAILED (errors=1) (#23)
      seen red: python -m unittest tests.test_home.HomeTest.test_moved on main → FAILED (errors=1) (#23)
      seen red: python -m unittest tests.test_home.HomeTest.test_not_a_repository on main → FAILED (errors=1) (#23)
      Not replayed, its report holds commit shas that differ on every run (D04.6):
      "home.check leaves out the close files in any folder, not only the root" failed
      `HomeTest.test_ignored_close_files`, and "home.check names a move before changes" failed
      `HomeTest.test_moved` (#23).
- [x] C04.6 **new** — `driver.github.evidence_line` with the fake `gh`: a run `completed` and
      `success` gives `None`; no run, a run `in_progress`, and a run `completed` and `failure`
      give the three park lines of In scope; a fake that exits 1 gives "cannot read the project:
      gh run list exited 1". The fake's recorded call is exactly the `run list` of In scope,
      with the 40-character sha given.
      Red today: `driver/github.py` does not exist; `ImportError` in `setUp`.
      Test: `GitHubTest.test_evidence_states`, `GitHubTest.test_evidence_gh_fails`.
      Evidence: `GitHubTest.test_evidence_states`, `GitHubTest.test_evidence_gh_fails` (#24).
      seen red: python -m unittest tests.test_github.GitHubTest.test_evidence_states on main → FAILED (errors=1) (#24)
      seen red: python -m unittest tests.test_github.GitHubTest.test_evidence_gh_fails on main → FAILED (errors=1) (#24)
      broken: evidence_line passes gh the 7-character sha → AssertionError: Lists differ: [['ru[57 chars]c0f03', '--limit', '1', '--json', 'status,conclusion']] != [['ru[57 chars]c0f03aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', '--li[37 chars]on']] (#24)
      broken: evidence_line takes any completed run as passed → AssertionError: None != 'park: the evidence run on `1dc0f03` ended `failure`' (#24)
- [x] C04.7 **new** — `driver.github.step_prs` for the step "Day 04 Track A: …" with the fake
      `gh` holding PRs on `day-04/track-a-x` by `me`, `day-04/track-a-y` by `someone`,
      `day-04/track-b-z` by `me` and `day-14/track-a-x` by `me`, returns only the first; the
      recorded call has `--author @me` and `--state open`; a fake that exits 1 gives `([],
      "cannot read the project: gh pr list exited 1")`.
      Red today: `ImportError` in `setUp`, as C04.6.
      Test: `GitHubTest.test_step_prs_by_branch_and_author`, `GitHubTest.test_step_prs_gh_fails`.
      Evidence: `GitHubTest.test_step_prs_by_branch_and_author`, `GitHubTest.test_step_prs_gh_fails` (#24).
      seen red: python -m unittest tests.test_github.GitHubTest.test_step_prs_by_branch_and_author on main → FAILED (errors=1) (#24)
      seen red: python -m unittest tests.test_github.GitHubTest.test_step_prs_gh_fails on main → FAILED (errors=1) (#24)
      broken: step_prs asks for another author than @me → AssertionError: Tuples differ: ([{'n[71 chars]r/1'}, {'number': 2, 'headRefName': 'day-04/tr[43 chars]None) != ([{'n[71 chars]r/1'}], None) (#24)
      broken: step_prs keeps every open PR of the author → AssertionError: Tuples differ: ([{'n[71 chars]r/1'}, {'number': 3, 'headRefName': 'day-04/tr[124 chars]None) != ([{'n[71 chars]r/1'}], None) (#24)
- [x] C04.8 **new** — `python run-steps.py --once` from a copy of the driver starts no session
      (the fake `claude` records no call but `--version` and `--help`) and prints, on the
      stream and with the exit of In scope, each of: the halt file set; a config missing
      `budget_usd`; a lock naming a live process (the test's child); an untracked file in the
      driver's copy; a project with no `scripts/pr-names.py`; a fake `claude` whose help lists
      no `--session-id`; a next step that parks ("Every day is done.", exit 1) and one that
      waits (an open PR, exit 0); an evidence run `completed` and `failure`; a run log with an
      open `start` line for the step's prefix. The first two of these set together give only
      the halt's line. After each refusal from step 5 on, `<state>/lock` is gone; after the
      refusal on the live process's lock, that lock is still there. `--once --dry-run` and
      `--once halt` each give "run-steps.py: --once goes alone", exit 2; no `--dry-run`,
      `--once` or command gives "run-steps.py: give --dry-run, --once or a command", exit 2.
      With every check passing, it prints "would start: " and the sentence, exit 0, and the
      lock is gone.
      Red today: argparse exits 2 with "unrecognized arguments: --once" on every case; with no
      flag the line is "only --dry-run and preflight exist yet".
      Test: `OnceTest.test_refusals`, `OnceTest.test_halt_comes_first`,
      `OnceTest.test_lock_released_on_refusal`, `OnceTest.test_once_goes_alone`,
      `OnceTest.test_usage_line`.
      Evidence: `OnceTest.test_refusals`, `OnceTest.test_halt_comes_first`, `OnceTest.test_lock_released_on_refusal`, `OnceTest.test_once_goes_alone`, `OnceTest.test_usage_line` (#25).
      seen red: python -m unittest tests.test_once.OnceTest.test_refusals on main → AssertionError: Tuples differ: (2, ['stderr'], False, True) != (1, ['stdout'], True, True) (#25)
      seen red: python -m unittest tests.test_once.OnceTest.test_halt_comes_first on main → AssertionError: Tuples differ: (2, False, True) != (2, True, True) (#25)
      seen red: python -m unittest tests.test_once.OnceTest.test_lock_released_on_refusal on main → AssertionError: Tuples differ: (2, ['stderr'], False, True) != (0, ['stdout'], True, True) (#25)
      seen red: python -m unittest tests.test_once.OnceTest.test_once_goes_alone on main → AssertionError: Tuples differ: (2, 'usage: run-steps.py [-h] [--dry-run] [--p[194 chars], '') != (2, 'run-steps.py: --once goes alone', '') (#25)
      seen red: python -m unittest tests.test_once.OnceTest.test_usage_line on main → AssertionError: Tuples differ: (2, 'run-steps.py: only --dry-run and preflight exist yet', '') != (2, 'run-steps.py: give --dry-run, --once or a command', '') (#25)
      broken: --once never releases its lock → AssertionError: Tuples differ: ([True, True, True, True, True, True, True, True], True) != ([False, False, False, False, False, False, False, False], True) (#25)
      broken: --once skips the halt file → AssertionError: Tuples differ: (2, False, True) != (2, True, True) (#25)
      Re-recorded at the close (D04.11): Track E (#26) changed the tuple `OnceTest.test_refusals`
      compares, so the next two breaks, recorded in #25 as "(0, ['stdout'], False, True) != (1,
      ['stdout'], True, True)", report what they give on today's code, the same on Linux and
      Windows:
      broken: --once reads the run log for another prefix → AssertionError: Tuples differ: (1, ['stdout'], False, 1) != (1, ['stdout'], True, 0)
      broken: --once skips the evidence run → AssertionError: Tuples differ: (1, ['stdout'], False, 1) != (1, ['stdout'], True, 0)
- [x] C04.9 **new** — With every check passing, `--once` starts one session: the fake records
      exactly the arguments of In scope's step 11 after the program, with the uuid that the run
      log's `start` line holds, and on its stdin the two lines of the prompt, in UTF-8, the
      sentence's en dash as `\xe2\x80\x93`; on Windows the fake is a `.cmd`, as npm's `claude`
      is; its cwd is the project's real path when the test passed another
      path to it (a symlink on POSIX, the 8.3 short path on Windows); `<state>/lock` and
      `<state>/settings.json` existed while it ran; a `settings.json` holding `not json` before
      the run is valid JSON with the halt hook during it; `rules/session.md` holds "nobody
      watches", "PARK: <", "never merge" and "Hand-off". After the session the lock is
      gone. The fake `gh` recorded one `run list` before the session.
      Red today: on Track D's code `--once` prints "would start: " and the sentence and starts
      no session; the fake records only `--version` and `--help`.
      Test: `OnceTest.test_session_command`, `OnceTest.test_session_cwd_is_real_path`,
      `OnceTest.test_lock_and_settings_during_session`, `OnceTest.test_rules_file`.
      Evidence: `OnceTest.test_session_command`, `OnceTest.test_session_cwd_is_real_path`, `OnceTest.test_lock_and_settings_during_session`, `OnceTest.test_rules_file` (#26).
      seen red: python -m unittest tests.test_once.OnceTest.test_session_command on main → AssertionError: Tuples differ: (False, False, False, False, True, False, True, False) != (True, True, True, True, True, True, True, True) (#26)
      seen red: python -m unittest tests.test_once.OnceTest.test_session_cwd_is_real_path on main → AssertionError: Tuples differ: (True, False) != (True, True) (#26)
      seen red: python -m unittest tests.test_once.OnceTest.test_lock_and_settings_during_session on main → AssertionError: Tuples differ: (False, False, False, False, True) != (True, True, True, True, True) (#26)
      seen red: python -m unittest tests.test_once.OnceTest.test_rules_file on main → FAILED (errors=1) (#26)
      broken: the prompt not written to the session's stdin → AssertionError: Tuples differ: (True, True, False, False, True, True, True, True) != (True, True, True, True, True, True, True, True) (#26)
      broken: the settings not written before the session → AssertionError: Tuples differ: (True, True, False, False, True) != (True, True, True, True, True) (#26)
      broken: the rules file without "nobody watches" → AssertionError: Tuples differ: (False, False) != (True, True) (#26)
      Not replayed in CI, it bites on Windows only (D04.9): "the session's cwd the path as given,
      not its real path" failed `OnceTest.test_session_cwd_is_real_path` with "(True, False) !=
      (True, True)" on Windows, where the 8.3 short path stays the child's cwd; on Linux the
      child's cwd reads as the resolved path whatever it is given, and the break passes (#26).
- [x] C04.10 **new** — Each row of In scope's outcome table, from the fake's JSON and the fake
      `gh`'s PRs, prints its line and exits with its code; a `result` that ends "PARK: needs a
      decision" with an open PR of the step still parks; and the run log's `end` line holds the
      printed line, the fake's `total_cost_usd`, and `denials` 2 for two `permission_denials`.
      Red today: on Track E's code `--once` prints "ended: session `<uuid>`" and exits 0, and
      writes no `end` line.
      Test: `OutcomeTest.test_outcomes`, `OutcomeTest.test_park_wins_over_a_pr`,
      `OutcomeTest.test_end_line`.
      Evidence: `OutcomeTest.test_outcomes`, `OutcomeTest.test_park_wins_over_a_pr`, `OutcomeTest.test_end_line` (#28).
      seen red: python -m unittest tests.test_once_outcome.OutcomeTest.test_outcomes on main → AssertionError: Tuples differ: (0, ['stdout'], 'ended: session `<uuid>`') != (2, ['stderr'], 'cannot read the project: gh pr list exited 4') (#28)
      seen red: python -m unittest tests.test_once_outcome.OutcomeTest.test_park_wins_over_a_pr on main → AssertionError: Tuples differ: (0, 'ended: session `<uuid>`') != (1, 'park: the session parked: needs a decision (session `<uuid>`)') (#28)
      seen red: python -m unittest tests.test_once_outcome.OutcomeTest.test_end_line on main → FAILED (errors=1) (#28)
      broken: the PARK line not read → AssertionError: Tuples differ: (0, 'opened: #5 from `day-01/track-a-x`') != (1, 'park: the session parked: needs a decision (session `<uuid>`)') (#28)
      broken: denials always 0 → AssertionError: Tuples differ: ('end', True, 'opened: #5 from `day-01/track-a-x`', 0.42, 0) != ('end', True, 'opened: #5 from `day-01/track-a-x`', 0.42, 2) (#28)
- [x] C04.11 **new** — A fake session that writes `notes.txt` into the driver's copy, and one
      that commits there, each end with the outcome line, then "halt: set during the step; "
      and the reason of C04.5, exit 1, and `<state>/halt` exists; a following `--once` refuses
      with the halt's line. A session that writes `evidence.json` at the copy's root does not
      halt.
      Red today: on Track E's code no check runs after the session; no halt file appears.
      Test: `OutcomeTest.test_driver_changed_during_step`,
      `OutcomeTest.test_driver_moved_during_step`, `OutcomeTest.test_close_files_do_not_halt`.
      Evidence: `OutcomeTest.test_driver_changed_during_step`, `OutcomeTest.test_driver_moved_during_step`, `OutcomeTest.test_close_files_do_not_halt` (#28).
      seen red: python -m unittest tests.test_once_outcome.OutcomeTest.test_driver_changed_during_step on main → AssertionError: Tuples differ: (0, ['ended: session `<uuid>`'], '', False) != (1, ['opened: #5 from `day-01/track-a-x`',[85 chars]True) (#28)
      seen red: python -m unittest tests.test_once_outcome.OutcomeTest.test_driver_moved_during_step on main → AssertionError: Tuples differ: (0, ['ended: session `<uuid>`'], False) != (1, ['opened: #5 from `day-01/track-a-x`',[82 chars]True) (#28)
      seen red: python -m unittest tests.test_once_outcome.OutcomeTest.test_close_files_do_not_halt on main → AssertionError: Tuples differ: (0, ['ended: session `<uuid>`'], '') != (0, ['opened: #5 from `day-01/track-a-x`'], '') (#28)
      broken: no check after the step → AssertionError: Tuples differ: (0, ['opened: #5 from `day-01/track-a-x`'], '', False) != (1, ['opened: #5 from `day-01/track-a-x`',[85 chars]True) (#28)
      broken: the check after the step without the starting HEAD → AssertionError: Tuples differ: (0, ['opened: #5 from `day-01/track-a-x`'], False) != (1, ['opened: #5 from `day-01/track-a-x`',[82 chars]True) (#28)
- [x] C04.12 **hold** — A stand-in step: `--once` on a fake session that starts a child and
      both sleep, both writing their pid to a file. Once the pids are written,
      `python run-steps.py halt --state <state>` prints a line starting "halt: set; killed pid "
      and exits 0; within 5 s the driver, the fake and its child are gone; the run log has the
      `start` line and no `end` line; the lock is still there. Then `--once` refuses with the
      halt's line and the fake records no new session; `clear` exits 0 and removes the halt
      file and the lock. Tagged hold though `--once` does not exist today: it is true once
      Track F merges (the lock from D, the group from D's step 1), Track G adds the test and owns
      no `new` claim, and CI's "Track tests seen red" passes a track that owns none.
      To break once: `--once` takes no lock (halt prints "no driver is running", the tree lives);
      on POSIX only, no `os.setpgid` (halt prints "killed pid N only: …", which still starts
      "halt: set; killed pid ", so the child alive after 5 s is what fails; a local Windows run
      does not see this break, CI's Linux run does). The tests assert so that no pid or path is
      in the report (D03.17).
      Test: `OnceHaltTest.test_halt_during_once`, `OnceHaltTest.test_once_refuses_after_halt`.
      Evidence: `OnceHaltTest.test_halt_during_once`, `OnceHaltTest.test_once_refuses_after_halt` (#29).
      broken: --once takes no lock → AssertionError: 'halt: set; no driver i' != 'halt: set; killed pid ' (#29)
      The POSIX break was run by the close, not by Track G (D04.14): on Linux, in a
      `python:3.12-slim` container, `scripts/break.py` replaced "os.setpgid(0, 0)" with "pass"
      in `driver/once.py`; on Windows it changes nothing and passes, so CI's Linux replay
      guards it. The first process seen alive is the fake, not its child (D04.15):
      broken: --once leaves the driver in the caller's process group → AssertionError: True is not false : the fake still runs
- [x] C04.13 **hold** — With `DRIVER_LIVE_CLI` naming the installed Claude Code, on the
      maintainer's PC (`plan.md`, "What to build", item 3, "a real step"): a scratch project
      whose `CLAUDE.md` says to run, first, "echo started > started.txt && sleep 20 && echo late
      > late.txt" with the Bash tool, whose `.claude/settings.json` allows `Bash` and has a
      marker hook on Bash, and whose fixture `spec-drift.py` names a track step; `--once
      --model <DRIVER_LIVE_MODEL, default haiku> --gh <fake>` starts the session; once
      `started.txt` exists, `halt` kills the driver; after 30 s there is no `late.txt` (the
      session's tree is gone). Then `<program> -p "Run this exact command with the Bash tool: echo
      resumed > out2.txt" --resume <the run log's uuid> --output-format json --permission-mode
      auto --strict-mcp-config --settings <state>/settings.json` leaves no `out2.txt`, the
      marker file got a line, and `is_error` is false: the session's next tool call was
      refused. Without `DRIVER_LIVE_CLI`, skipped with "DRIVER_LIVE_CLI is not set".
      Tagged hold as C04.12: true once Track F merges; Track G adds the test. Broken by hand,
      on the maintainer's PC, as C03.8 was: `--once` passes no `--settings` → `out2.txt`
      exists. CI cannot replay it (no login, no budget): a sentence and `broken: none →`.
      Test: `LiveOnceTest.test_halt_during_a_real_step`.
      Evidence: `LiveOnceTest.test_halt_during_a_real_step` passed live with
      `DRIVER_LIVE_CLI=claude` on the maintainer's PC (Windows, Claude Code 2.1.170, haiku):
      1 test in 44.9 s, OK (#29).
      seen red by hand on the maintainer's PC, not replayable (no login or budget in CI):
      `scripts/break.py` dropped "/T" from `halt`'s `taskkill` call in `driver/switches.py`, so
      `halt` killed the driver only, and the run reported "AssertionError: True is not false :
      the session's tree lived on": `late.txt` was written (#29).
      broken: none → C04.13 is a live check; CI skips it without DRIVER_LIVE_CLI, and its break was run by hand (#29)
- [x] C04.14 **hold** — Earlier days' tests pass with their files unedited, but for
      `tests/test_preflight.py`'s fake help text and flag list (C04.3): `git -c
      core.safecrlf=false diff --exit-code 1dc0f03 -- tests/test_contract.py
      tests/test_decide.py tests/test_dry_run.py tests/test_steps.py tests/test_kit_copy.py
      tests/test_config.py tests/test_lock.py tests/test_hooks.py tests/test_halt.py
      tests/test_live_cli.py` prints nothing, and `python -m unittest discover -s tests` passes
      with them in it ("OK (skipped=4)" at the close: Day 3's three live tests and
      `LiveOnceTest`).
      Replaces: C03.9 — was: Day 1's and Day 2's tests pass with their files unedited,
      `tests/test_preflight.py` among them: the diff against 0efd4d2 prints nothing.
      To break once, in Track A: one listed test file edited → the diff exits 1; and `run_drift`
      writes its `--out` file inside the project → `DryRunTest.test_project_is_unchanged` fails.
      The second's report holds commit shas that differ on every run, so it is recorded as a
      sentence and `broken: none →` with that reason, not replayed (D03.17, D04.4).
      Evidence: the commands above: `git -c core.safecrlf=false diff --exit-code 1dc0f03 -- ...`
      prints nothing and `python -m unittest discover -s tests` gives "Ran 92 tests", "OK
      (skipped=4)" on this branch, after #29; #22 to #29 each report the same diff empty.
      broken: tests/test_decide.py edited → ROOT = Path(__file__).resolve().parent.parent (#22)
      Not replayed, its report holds commit shas that differ on every run (D04.4): `run_drift`
      writing its `--out` inside the project failed `DryRunTest.test_project_is_unchanged` with
      "?? spec-drift.json" in git status (#22).

## Verify
```bash
python -m unittest discover -s tests
git -c core.safecrlf=false diff --exit-code 1dc0f03 -- tests/test_contract.py tests/test_decide.py tests/test_dry_run.py tests/test_steps.py tests/test_kit_copy.py tests/test_config.py tests/test_lock.py tests/test_hooks.py tests/test_halt.py tests/test_live_cli.py
```

## Notes
- Written 2026-11-07 on `main` at `1dc0f03`, after Day 3's close (#20), from `plan.md`'s Day 4
  title and the hand-offs to Day 4: H01.5, H01.6, H01.8, H02.2, H03.1, H03.5, H03.6, H03.7,
  H03.9, H03.10. H02.4 (the maintainer's) is taken here, beside H01.8, as it offered. The
  spec-auditor's 10 findings on the draft are fixed: D04.1 to D04.5, and five of wording (the full
  sha, `sub/`, `os.linesep`, why C04.12-13 are hold, five unchecked behaviours now in C04.8-9).
- **The evidence run is checked on every start, not only after a close** (H01.5). The kit's
  `evidence.yml` runs on every push to `main` and passes a commit that is no close, so the run on
  `origin/main`'s head says what CLAUDE.md's step 5 asks without the driver telling a close from
  another merge (by a merge's subject or a squash's title, both the kit's wording). The cost: a
  `--once` in the minute after any merge parks on "has not finished". Day 6's loop waits instead.
  The maintainer may prefer the check after a close only; the spec-change PR is where to say so.
- **H03.9 goes to Day 6, not here** (H04.2). `--once` is run by the maintainer at the PC, who
  sees its result; `on` runs unattended, which is where a Claude Code update must not pass
  unseen. Where the record of a passed live check lives (a committed list means a driver PR per
  Claude Code release, several a week; a file in `state/` means the live test writes into the
  repository's own state folder, which Day 3 ruled out) is Day 6's decision. Day 4 records the
  version of each session in its `start` line, so the trial's record says which versions ran.
- **A run-log `start` with no `end` parks with no way past it but by hand** (H01.6): the
  maintainer looks at the session and removes the line, or not; Day 7 decides it (H04.3).
- **The project's tree.** `--once` parks on a project tree that is not clean, as the dry run does,
  so until H03.8 lands every kit close is followed by a park (`evidence-rehearsal.json`).
- **No timeout on the session.** `--max-budget-usd` bounds its cost and `halt` stops a hang;
  Day 6's loop, which runs unattended, decides a bound.
- **The order of the checks:** the halt first (it costs nothing and must win), the lock before
  any read of the project, the driver's own repository before the preflight runs the project's
  script, and the evidence run and the run log only for a step that would start.
- **Breaks that replay** (D03.17): each brief says to assert on booleans or fixed strings where
  a value holds a pid, a sha, a uuid or a temp path, so a break reports the same in CI on Linux.
- Estimated size: A ~80 lines, B ~250, C ~220, D ~300, E ~200, F ~250, G ~250.
- **Defect** D04.1 — found: auditor · cause: spec · made: Day 04 · C04.7 expected
  `day-04/track-ab` to be no branch of Track A, but by `_is_branch_of` (C01.5) it is one: the
  test could never pass. Now `day-14/track-a-x`.
- **Defect** D04.2 — found: auditor · cause: spec · made: Day 04 · step 11 put the two-line
  prompt in an argument; through npm's `claude.cmd` the newline dropped every argument after it,
  so the session would have run with no `--settings`, `--permission-mode` or
  `--max-budget-usd`. The prompt now goes on stdin; `claude` and `gh` are found by `shutil.which`.
- **Defect** D04.3 — found: auditor · cause: spec · made: Day 04 · C04.2 did not say where the
  reconfigure goes; in `main()` it errors in two tests whose files C04.14 keeps unedited.
- **Defect** D04.4 — found: auditor · cause: spec · made: Day 04 · C04.14's `run_drift` break
  reports shas that change each run, so it could not replay (as D03.17), and no track's row
  named C04.14 (as D03.16). Now a sentence, and Track A's row.
- **Defect** D04.5 — found: auditor · cause: spec · made: Day 04 · Track D held steps 1-11, two
  fakes and fourteen cases at ~380 lines; Day 3's `halt` and `clear` alone were 344 (#16). Split
  into D and E here, not by a spec change mid-day.
- **Hand-off** H04.1 → Day 5: each park `--once` prints (a session's `PARK:`, neither a PR nor
  `PARK:`, an error, more than one PR, the evidence run, an open run-log line) becomes a
  `parked` issue, and "the same step failed twice" is read from the run log's `end` lines.
- **Hand-off** H04.2 → Day 6: `on` refuses a Claude Code version the live check has not passed
  on (H03.9), and decides where that record lives.
- **Hand-off** H04.3 → Day 7: a run-log `start` with no `end` is read by the table of
  "Recovery": a live process of that session waits, a gone one parks; Day 4 parks on both.
- The close (2026-11-07): the tracks merged in the table's order, A to G (#22, #23, #24, #25,
  #26, #28, #29), after the spec change #21; #27 was a `tooling/` branch between E and F. The
  tracks recorded 25 `broken:` lines: 23 with a `manifest:` entry and two `broken: none` (#22,
  #29). Each entry, parsed from the raw bodies, and the close's one break (C04.12's setpgid,
  D04.14) were run through `scripts/break.py` twice on Linux, in a `python:3.12-slim` container
  on a clone of `main` at `cfdb450`, and each report compared by the replay's own `normal()`
  with the recorded one: 16 matched both times, as CI's Linux replay will compare them. Of the
  other eight, six cannot replay and are sentences, not in the manifest (D04.6, D04.7, D04.9),
  and two are re-recorded from today's code (D04.11). `specs/breaks/day-04.json` holds 18
  entries: 15 as recorded, the two re-recorded, and the close's. A local
  `python scripts/close-evidence.py --rehearse day-04/close-the-day` on Windows fails one check,
  C04.12's setpgid break ("The check passed with the break in"), and passes every other; CI's
  rehearsal and replay, on Linux, are the ones that see that break.
- Left for the close by the tracks. The backticks of In scope: #25 and #28 read them as literal
  around identifiers, branch names, paths, uuids and shas, and none around numbers, a whole
  substituted reason or the PARK text; the close keeps that reading, which the tests pin. #25's
  fifth break, the "--once goes alone" check dropped, failed `OnceTest.test_once_goes_alone` with
  a temp path in its report, so it is neither a `broken:` line nor in the manifest. In scope's
  "Until Track E" and "Until Track F" sentences are now in the past (#28 asked).
- Hook refusals since Day 03's count (`docs/dashboard/refusals.json`): 7 read-guard and 1
  auditor-guard, all on 2026-11-07. Seven whole-file Reads refused in a day say the 8,000-byte
  rule is still read past: a Read of a spec or a test file starts from `grep -n`.
- **Defect** D04.6 — found: Track B · cause: process · made: Day 04 · same-as: D03.17 · four of
  Track B's five breaks (#23) report a session uuid or commit shas, which differ on every run,
  though this spec's Notes ("Breaks that replay") asked each brief for booleans or fixed strings;
  #23 said so itself and left it to the close. Now sentences, not in the manifest.
- **Defect** D04.7 — found: close · cause: spec · made: Day 04 · C04.4's claim that the run log's
  bytes hold no carriage return bites on Windows only: on Linux the break that writes
  `os.linesep` passes, and the spec did not say so (`specs/README.md`: a check whose break bites
  on one system only says so). The close's Linux replay found it.
- **Defect** D04.8 — found: break on purpose · cause: implementation · made: Day 04 · Track E's
  test case (#26), as its brief wrote it, put the 8.3 short path in the config's `project`, which
  `driver/config.py` already resolves, so the break that drops `realpath` from step 11 passed;
  Track E's break on purpose caught it before #26 merged, and the case now passes the path with
  `--project`.
- **Defect** D04.9 — found: close · cause: spec · made: Day 04 · C04.9's "a symlink on POSIX" case
  cannot fail: a POSIX child's cwd reads as the resolved path whatever path it was started in,
  so on Linux the break that passes the path as given passes; only Windows' 8.3 case sees it.
  The spec did not say so (as D04.7). The close's Linux replay found it.
- **Defect** D04.10 — found: break on purpose · cause: implementation · made: Day 04 · same-as:
  D03.17 · the implementer's first Track F tests (#28) compared the session's real uuid, so
  their seen-red and break reports held it; the main session's first round of breaks caught it,
  and the tests now put "<uuid>", "<a>" and "<b>" in its place.
- **Defect** D04.11 — found: close · cause: process · made: Day 04 · two of Track D's breaks (#25)
  no longer report what #25 recorded: Track E (#26) changed the tuple `OnceTest.test_refusals`
  compares, and nothing re-ran D's breaks. Both are still caught; the close re-records them.
- **Defect** D04.12 — found: close · cause: process · made: Day 04 · #24's body wrote its four
  `broken:` lines as "broken: broken: …": copied as they stand, none would have matched its
  manifest entry by name. The spec holds each once.
- **Defect** D04.13 — found: Track G · cause: spec · made: Day 04 · C04.13's named break,
  `--once` passing no `--settings`, cannot fail `LiveOnceTest.test_halt_during_a_real_step`: the
  resume the criterion names passes `--settings <state>/settings.json` itself, and `halt` kills
  the tree before the flag matters (#29). Track G ran the "/T" break instead, which the test
  catches, and the close ticks C04.13 on it. A departure: C04.13's text still names the other
  break, since a close keeps the criteria's wording ("Criteria keep their wording"); a
  spec-change PR rewords it if the maintainer wants.
- **Defect** D04.14 — found: Track G · cause: environment · made: none · C04.12's POSIX break
  could not run on the maintainer's PC, whose WSL has no `python3` (#29). The close ran it on
  Linux in a Docker container.
- **Defect** D04.15 — found: close · cause: spec · made: Day 04 · C04.12 said the setpgid break
  fails on the child alive after 5 s; it fails first on the fake ("the fake still runs"): `halt`
  kills only the driver's pid, and the test checks the fake before its child. The close's run of
  the break showed it.
- The blind relabel (`scripts/relabel.py`, the defect-rater): stage 7 of 15 agree, cause 13 of
  15, made 14 of 15. Each stage disagreement but D04.5's is the rater's "unclear": the text did
  not say when it was found. D04.1 to D04.5 keep `found: auditor` (the first Note: the
  spec-auditor's findings, fixed in #21 before any code), and D04.8, D04.9 and D04.15 now say
  when. D04.2 keeps `cause: spec` against the rater's `environment` (low): npm's `claude.cmd` is
  what it met, but the spec's step 11 is what was wrong and changed. D04.8's cause is now
  `implementation`, the rater's: the spec was right and the test case was not, though its brief
  wrote it so. D04.14's `made:` is now `none`, the rater's: a machine with no `python3` is no
  day's work.
- **Hand-off** H04.4 → Day 7: a run-log `start` line that parses but has no `session` key is not
  read as unreadable (#23); the table of "Recovery" that H04.3 brings decides it.
