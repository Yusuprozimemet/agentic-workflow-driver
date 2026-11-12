# Day 10: the first step in the container

C10.30's record: one step of the trial's project, run by `run-steps.py --once` with the container
keys, in the image `docs/container.md` builds. The run log's lines are copied from
`state/run.jsonl` as written; the rest is read from GitHub and the PC after the run.

## Set-up

- **Project:** `bearing` (`../bearing`), Phase 6, Day 14, spec `specs/day-14-description-length.md`,
  at `714412f` (bearing #99) at the start. Day 14 was added for this run: bearing's plan ended at
  Day 13, and `--once` printed "park: every day is done" (plan change bearing #98, spec #99).
- **Driver:** `main` at `af7332a` (#158), with no change in its folder: the first `--once` refused,
  "cannot start: the driver's repository has changes: `tests/test_trial_ten.py`", this track's test
  left uncommitted; it was stashed and the run started again.
- **`driver.json`:** as Day 8's, with `container_image` `agentic-workflow-driver-session:2.1.322` and
  `container_secrets` the secrets file's path. `preflight` printed "preflight: ok".
- **The image:** built as `docs/container.md` says, `CLAUDE_VERSION=2.1.322`,
  `GIT_NAME="Driver session"`.
- **The secrets file:** `CLAUDE_CODE_OAUTH_TOKEN` and `GH_TOKEN`, the fine-grained token for
  `bearing` only: Contents, Issues and Pull requests read and write; Actions and Metadata read; no
  Administration, no Workflows.

## The run

```json
{"event": "start", "at": "2026-11-12T23:14:39Z", "step": "Day 14 Track A: C14.1–C14.3: `bearing/ingest/text.py`, `tests/test_sentences.py`", "prefix": "day-14/track-a", "session": "2d6771a4-63cb-4a41-b0ef-3da00a7fc3fb", "claude": "2.1.322 (Claude Code)", "issue": 100, "container": "driver-2d6771a4-63cb-4a41-b0ef-3da00a7fc3fb"}
{"event": "pid", "at": "2026-11-12T23:14:39Z", "session": "2d6771a4-63cb-4a41-b0ef-3da00a7fc3fb", "pid": 9280, "started": "2026-11-12T23:14:39Z", "container": "driver-2d6771a4-63cb-4a41-b0ef-3da00a7fc3fb"}
{"event": "end", "at": "2026-11-12T23:21:05Z", "session": "2d6771a4-63cb-4a41-b0ef-3da00a7fc3fb", "outcome": "opened: #101 from `day-14/track-a-two-sentences`", "cost_usd": 0.5558345, "denials": 1, "refused": [{"tool": "Read", "input": "{\"file_path\": \"/work/specs/day-14-description-length.md\"}"}]}
```

- **Pull request:** https://github.com/Yusuprozimemet/bearing/pull/101
- **Head commit's author:** `Driver session`
- **The image's `GIT_NAME`:** `Driver session`
- **The PC's `git config user.name`:** `Yusuprozimemet`
- **`git status --short` in `../bearing` after:** empty

The head commit is `2e3dd70` (`gh pr view 101 --json commits`), with a `Co-Authored-By` line for
the model. The session ran 6 min 26 s (23:14:39Z to 23:21:05Z) and cost $0.56 by the `end` line's
`cost_usd`; the run's issue, bearing #100, is closed with the outcome. #101's checks: 15 passed,
2 skipped (`gh pr checks 101`). The push with `GH_TOKEN` and a whole step in the container, `plan.md`'s "Unverified", are
shown by this run.

## What the run showed

- **The dev dependencies:** the image has no `bearing` dependencies; the session ran
  `pip install -e ".[dev]"` itself, as bearing's `CLAUDE.md` says, about 90 s of the 6 min 26 s.
  Every container session pays it again.
- **One refusal that did not refuse:** the `end` line's `denials` is 1 and its `refused` holds a
  Read of the spec, but the transcript has one Read of that file, with `limit` 200, and its result
  is the file's text. Why the CLI counted it as denied is not known; the run log records what the
  CLI reported.
- **The checkout's branch:** after the run, `../bearing` is on `day-14/track-a-two-sentences`, not
  `main`, as after a session on the PC; its status is empty.
- **The cost count:** `scripts/token-usage.py` does not count the container's transcripts
  (`state/claude/projects/-work/`); the cost here is the run log's (H10.2, Day 13).
