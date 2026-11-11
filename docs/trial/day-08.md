# Day 08's trial: one day of `bearing` at level 1

The driver ran `bearing`'s Day 13 with the maintainer only merging and answering parks. The run
log is [`run.jsonl`](run.jsonl), `state/run.jsonl` copied byte for byte after the last step. It was
read before it was committed: the one refused input is a file path, no secret, and no line was
changed. Times are UTC unless they say local.

## Set-up

- **Project:** `bearing` (`../bearing`), Phase 5, Day 13, spec `specs/day-13-loose-ends.md`, at
  `0472de4` at the start.
- **Dates:** first `start` line 2026-11-10T23:16:41Z, last line 2026-11-11T00:33:55Z (00:16 to
  01:33 local on 2026-11-11). Two runs, with issues #89 and #95.
- **CLI:** Claude Code 2.1.322 on every `start` line, updated from 2.1.170 by `npm install -g` on
  2026-11-11 local, the newest extension folder's version; `state/live-checked.txt` holds
  "2.1.322 (Claude Code)".
- **`gh`:** 2.93.0.
- **`driver.json`:** `project` `../bearing`, `human_only` the ten paths of `plan.md`'s "Who does
  what" (`plan.md`, `CLAUDE.md`, `AGENTS.md`, `.github/`, `.claude/`, `scripts/`,
  `specs/README.md`, `specs/_template.md`, `specs/_short-template.md`, `spec-drift.config.json`),
  `budget_usd` 10, `steps_per_night` 6. The two numbers were Claude's suggestion, accepted by the
  maintainer.
- **Required checks on `bearing`'s `main`**, eight, from the protection API: Description uses the
  template, Diff stays reviewable, Branch, title, commits and Jira keys agree, Frozen files stay
  unedited, Dashboard metric tests gate, Criteria keep their wording, Tests, Track tests seen red.

Each "Before this day" item:

| Item | Done | How |
|---|---|---|
| The trial's project | 2026-11-10 | `bearing`, plan change #87 (merged 21:25:42Z), spec change #88 (`0472de4`) |
| Required checks | 2026-11-11 local | the eight above; listed, not changed |
| `driver.json` | 2026-11-11 local | above |
| The token | 2026-11-11 local | fine-grained, `bearing` only: Actions read; Contents, Issues, Pull requests read and write; Metadata read. Loaded by hand as `GH_TOKEN`: the driver does not read `.env` |
| The CLI | 2026-11-11 local | updated, and `live-check` passed on it (3 tests). The denied-call session of #118 (merged 2026-11-10T15:36:12Z) ran on 2.1.170, not the updated CLI as the spec asks; the trial's own refusal, on 2.1.322, was written with its tool and input (Refusals) |
| H03.8 | 2026-11-10 | ignore lines for `evidence.json` and `evidence-rehearsal.json`, in `bearing`'s #87 |
| H05.5 | 2026-11-10 | on the scratch repository `wordtally`, pasted in #120 (merged 16:16:41Z): the URL last, and exit 0 from a second close |
| The run log | 2026-11-11 local | no `state/` folder before the trial; all 19 lines are the trial's |
| H07.1 | 2026-11-10 | corrected by #121 (merged 16:41:07Z) |

## Steps

`status`'s block on the copy, unchanged:

```
steps:
  2026-11-10T23:16:41Z Day 13 Track A: C13.1–C13.3, C13.8–C13.9: `bearing/cli.py`, `tests/test_stderr.py`: opened: #90 from `day-13/track-a-stderr-utf8`, $0.90, refusals 1, session `a6f2d88b-f440-421b-8d1a-863e2e925f2c`
  2026-11-10T23:35:00Z Day 13 Track B: C13.4–C13.6: `bearing/cli.py`, `tests/test_ingest_limit.py`: opened: #91 from `day-13/track-b-limit-warning`, $0.73, refusals 0, session `0106d415-fedd-4137-a29a-7cd97104e66b`
  2026-11-10T23:47:55Z Day 13: the closing PR: no end, $0.00, refusals 0, session `8bef3bb2-7739-40b8-875e-4552641818d1`
  2026-11-11T00:00:59Z Day 13: the closing PR: opened: #96 from `day-13/close-the-day`, $1.16, refusals 0, session `66eeef24-3658-4b65-96c0-47beff5fb4e2`
```

The `wait` lines' pull requests: #90, #91, #96. Each was merged with `"changed": false`.

## Parks

- 2026-11-10T23:56:17Z `park: the run log names session `8bef3bb2-7739-40b8-875e-4552641818d1` for this step, with no end` · issue #94 · closed from the phone · createdAt 2026-11-10T23:56:19Z · closedAt 2026-11-10T23:59:14Z · next `start` 2026-11-11T00:00:59Z. The session was killed by the `STOP` below.
- 2026-11-11T00:33:55Z `park: every day is done` · issue #97 · closed by the maintainer, the device not recorded · createdAt 2026-11-11T00:33:57Z · closedAt 2026-11-11T00:35:07Z · no next `start`: the trial was over.

The `STOP` wrote no `park` line: it halted the run (The phone).

## Refusals

`status`'s lines on the copy, unchanged:

```
refusals: 1
  1 Read: {"file_path": "C:\\Users\\HackYourFuture\\yusup\\bearing\\tests\\test_timeline_cli.py"}
```

Track A's implementer subagent, reading that test file at 23:17:38Z. `bearing`'s `read-guard.py`
refused it, a whole-file Read of a file over 8,000 bytes: "… is 8,116 bytes, 219 lines. Read the
part you need: find it with grep -n, then Read with offset and limit."

`bearing`'s `.claude/state/refusals.jsonl`: no lines inside the trial's dates, because the file does
not exist. `bearing`'s guards at `c214b09` print their refusals and log them nowhere, so the
spec's Assumed line that the kit's guards write that file does not hold for this project's copy.

## Cost

`status`'s lines on the copy, unchanged (the sessions' `total_cost_usd`):

```
cost: $2.78, merged pull requests 3, $0.93 each (baseline $1.86)
level 2: 3 of 15 pull requests in a row merged without a change asked
```

The list-price measure, from the later side of
`python scripts/token-usage.py --compare --repo ../bearing --split 2026-11-11` ($3.22, 42 replies,
3 merged pull requests):

```
cost per merged pull request: $1.07 (baseline $1.86)
replies per merged pull request: 14.0 (baseline 34.4)
```

- The split is 2026-11-11 because the script splits on the local date, and the trial's first
  local date is that one.
- Interactive sessions on that side: none. Its four sessions are the four `start` lines' sessions.
  The interactive ones nearest the trial, `2c23262f` and `c4207576`, ended by 22:08Z on 2026-11-10
  (23:08 local), before the split.
- The two figures measure different things and are not reconciled here. `status` leaves out the
  killed session, which wrote no `end` line. The list-price side includes it and counts the main
  sessions only, not their subagents.
- The count of 3 of 15 can be too high: the run log cannot see a change asked for in chat or a PR
  comment.
- Three pull requests of one small day, Phase 5's loose ends, are a small sample beside the
  baseline.

## The phone

STOP: opened 2026-11-10T23:49:28Z, halted 2026-11-10T23:49:58Z, 30 s

park closed: 2026-11-10T23:59:14Z, started again 2026-11-11T00:00:59Z, 105 s

The first is issue #92, its time from `createdAt` and the halt file's text, copied before `clear`:
"halted at 2026-11-10T23:49:58Z: STOP issue #92". A second `STOP`, #93, was opened at 23:49:55Z,
before the halt. The spec asked for the `STOP` during a wait on a pull request; it landed during
the closing session instead, `8bef3bb2`, so that session has no `end` line and parked the next
start. The spec expected that park to need VS Code. It did not: #94 was closed from the phone, and
the next start ran the closing step again, in a new session. The second is issue #94.

## The usage limit

not met

## Unverified

For each item of `plan.md`'s "Unverified" the trial touched:

- **Usage limit and a `--max-budget-usd` stop:** neither happened. The dearest session was $1.16 and
  the run came in under `budget_usd` 10.
- **The kit's hooks act in `claude -p` in `auto` mode:** the Read hook did, in a subagent of a
  headless session (Refusals).
- **A hook's exit-2 refusal in `permission_denials`** (the spec's Assumed line): it appears, and from
  a subagent too. The one refusal in the run log is `read-guard.py`'s. Every permission refusal in
  the record is therefore every one in `permission_denials`; a guard's refusal that did not reach
  it would be seen nowhere, since `bearing`'s guards log none and neither does `hooks/guard.py`.
- **A step session ends after one pull request:** the three sessions that ended each opened one
  and stopped.
- **Resuming is cheaper than a new session for a fix:** not shown. No step needed a fix, so the run
  log has no resumed session and there is no cost to set beside a step's first session. The
  new-session way was not run.
- **`taskkill /T /F` ends the session's subagents and commands:** not shown. The killed session's
  transcript stops at 23:49:05Z, 53 s before the halt, and it had started no subagent. The driver's
  report on #89 gave its branch `day-13/close-the-day`, no uncommitted changes and no commits on it.
- **`token-usage.py` counts headless transcripts:** it does, all four sessions, on 2.1.322, as
  `"entrypoint":"sdk-cli"`. Whether a resumed session's transcript counts twice is still unknown.
- **The fine-grained token is enough:** `gh pr checks --required` and `gh run list` worked with
  it, and each session pushed its branch and opened its pull request. Which credential
  `git push` used cannot be read from the log; the git config sends it through
  `gh auth git-credential`. No merge used the token: at level 1 the maintainer merges.
- **`--session-id` with `claude -p`:** it works, each transcript's file name is its `start` line's
  session. `--resume` was not used.
- **`--settings` hooks after the CLI update:** `live-check` passed on 2.1.322. A resumed session was
  not seen.
- **Rules passed with `--append-system-prompt-file`:** the sessions did one step and stopped, as
  those rules say. Nothing here compares them with `CLAUDE.md`.
- **What `auto` mode refuses over a whole step:** nothing in the three sessions that ended, whose
  one refusal was a hook's. The killed session wrote no `end` line, so its refusals are not known.
- **The CLI's version:** updated to 2.1.322 before the trial.

Not touched: Remote Control showing a headless session, the reviewer through `--agents`, the second
Windows account.

## Evidence

The driver checked the run: #96 was not gated, so `wait_merge` waited for the evidence run on the
new `main` before the next read, which parked "every day is done". Then, by hand, from `bearing`:
`gh run view 42932015269 --json conclusion`.

closing PR: #96

merge commit: c214b097f8bc5dd478d7972259237ea799291827

evidence run: 42932015269

conclusion: success
