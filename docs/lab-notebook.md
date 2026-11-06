# Lab notebook

## Results to date

### Day 01 — the dry run names the next action and starts nothing

Closed 2026-11-06 ([spec](../specs/day-01-dry-run.md)). Five PRs merged: the spec change (#1),
one tooling PR for hand-off H01.7 (#2), and Tracks A, B and C (#3, #4, #5).

- **Delivered:** `python run-steps.py --dry-run --project <path>` reads the kit's next-step
  sentence, the project's tree, branches and remote, and prints one action, `start`, `wait` or
  `park`, with exit codes 0, 0 and 1, or exits 2 when the project cannot be read. Its tests run
  it on a fixture project and record every command it runs: only reads, and nothing in the
  project changes.
- **Every `new` check was seen red.** All 7 criteria were `new`, and CI's "Track tests seen red"
  showed each of their 15 tests failing on the code before its track.
- **Breaks:** 6, across C01.3, C01.5, C01.6 and C01.7, although the spec expected none for an
  all-`new` day. Five of them replay. The sixth's report held a commit hash that changes on
  every run, and the close's rehearsal caught it (D01.17). C01.1, C01.2 and C01.4 rest on
  seen-red alone.
- **Defects:** 17. The spec-auditor and plan-auditor found 14 in the spec before any code
  (D01.1–D01.14, all `cause: spec`). Of the other 3, Track A found a spec gap (D01.16), and the
  close's evidence rehearsal found a break whose report could not be replayed (D01.17). The
  third was a test of the kit's own tooling that read the wrong file (D01.15). It was made
  before any day (`made: none`), so it is an escape from the repository's start, not from a
  day. No escapes from Day 01.
- **Hand-offs:** 9 in all. H01.7 landed in #2. Of the 8 open, Day 2 takes H01.3 and H01.9,
  Day 4 takes H01.5, H01.6 and H01.8, Day 5 takes H01.1, Day 6 takes H01.2, and H01.4 goes to
  the maintainer.

## What is being measured

| Question | Evidence it will be judged on | Day 01 |
| --- | --- | --- |
| Cost per merged PR, main sessions, beside the kit's baseline of $1.86 (`plan.md`, "What it is judged against") | `docs/dashboard/token-usage.json` | $5.51 over 5 merged PRs on 2026-11-06, $1.10 each ($2.45 attributed to Day 1 by branch, $3.06 on `main`). The implementer added $0.07. The close's own session is counted only up to its `token-usage.py` run |
| Replies per merged PR, main sessions, beside 34.4 | `docs/dashboard/token-usage.json` | 118 replies over 5 PRs, 23.6 each |
| Escapes per day | the Notes' Defect lines with `made:` an earlier day | 0 from a day; 1 from the repository's start (D01.15) |
| Parks by reason | the driver's run log | none yet: the driver does not run steps until Phase 1 |
| Hook refusals | `docs/dashboard/refusals.json` | 1, read-guard, 2026-11-06 |
| What each gate cost | `docs/dashboard/gates.json` | Day 1: seen red, 5 runs for $0.36; break on purpose, 8 runs for $0.39 |

## Retrospective
