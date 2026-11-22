# The level 2 trial: bearing, 2026-11-21 and 2026-11-22

The record of Day 14 (`specs/day-14-the-level-2-record.md`). The driver ran bearing at level 1
in the container until `status` read 15 of 15, then for one bearing day at level 2. The run log,
the switch log, the hook log and one session's install calls are copied beside this file, lines
as written: `run-14.jsonl` (lines 23 to 133 of `state/run.jsonl`, from the first line after the
Day 10 step's `end` at 2026-11-12T23:21:05Z to the park that ended the level 2 day),
`switches-14.jsonl` (all 15 lines of `state/switches.jsonl`), `refusals-14.jsonl` (both lines of
`state/refusals/hooks.jsonl`) and `install-14.jsonl`. `tests/test_trial_fourteen.py` reads this
file and the copies, never the state folder.

## Set-up

- project: bearing
- budget_usd: 10
- steps_per_night: 6
- human_only: `plan.md`, `CLAUDE.md`, `AGENTS.md`, `.github/`, `.claude/`, `scripts/`, `specs/README.md`, `specs/_template.md`, `specs/_short-template.md`, `spec-drift.config.json`
- level of the count run: 1
- level of the level 2 day: 2, with `"review": true`
- image: `agentic-workflow-driver-session:2.1.322`, id `sha256:a3a43f744940ec2faf0f14944df33e18c21d9d9a29cbaae95c3a8ea41cf1590b`
- driver's main: 10b3d9d46e12b328c102e0b2e401615501413ac2
- bearing's copy of the kit's scripts/spec-drift.py: 2beefea833105aa680a945c0a4360d683096569a
- bearing at the level 2 day: 456659bd4f6b232fc9da6e8a6e995ab89c23c254
- level 2 from: 2026-11-21T23:42:48Z

`driver.json` named `"project": "../bearing"`, the keys above, `container_image` and
`container_secrets` (a file outside both repositories). The driver's `main` was 10b3d9d from
13:40Z on 2026-11-21 (#271, Track E's line in `rules/session.md`); the count run's first two
sessions (fc600943, 656d9ab8) ran on the `main` before it, without that line, and parked after
opening their pull request (D14.34). The count run's sessions had no `level` in `driver.json`
(level 1). For the level 2 day `driver.json` gained `"level": 2` and `"review": true`, last
written at 23:37:15Z. "level 2 from:" is the `at` of the last `on` line of `switches-14.jsonl`;
the `on` at 23:36:32Z, before that write, started no session, and whether it ran at level 2 is
not known.

Before the level 2 day, `python scripts/setup-check.py --repo Yusuprozimemet/bearing` printed 12
of 14 checks ok. The two that failed, "A closed day's evidence replays" and "A track's breaks
replay", are checks bearing does not have (#213). `on` at level 2 reads `main`'s protection only,
so neither stopped it. `GH_TOKEN` was loaded by hand before each `on`.

## The count run

The count started at 0 of 15 (3f31818) and ran at level 1 on 2026-11-21. bearing's plan had
ended at its Day 14, so the maintainer merged a plan change for Days 15 to 18 (#102) and its
specs (#103 to #106) with the driver off, and later Days 19 to 24 (#118, #121). The run stopped
at 1 of 15 after #101: the sessions of #108 (Day 14's close) and #116 (Day 15 Track A) opened
their pull request and ended with a `PARK:` line, since bearing's `CLAUDE.md` says to stop and
wait for "merged" (D14.34). The maintainer merged both by hand. Track E (#271) added the line
that a step which opened its pull request ends without `PARK:`, and the count resumed. Two
later step sessions ended with no `opened:` line because the maintainer merged their pull
request by hand before the session ended (#123, session 57665251; #139, session 1efd23a0): the
driver wrote "the session ended with no pull request and no PARK line" for each. None of these
four has a `merged` line, so the count did not fall back to 0 for them. The 15th merge in a row
was #151 (bearing Day 22's spec change), at 23:27:27Z: `status` read "level 2: 15 of 15".

## The level 2 day

bearing's Day 22, from its Track A on: the 15th merge of the count was that day's spec step, at
level 1. Two step sessions ran at level 2: 76bd4a7f (Track A, opened #153) and bd6bbdc4 (the
close, opened #154), each followed by a reviewer session (d26d9fcb, 3a64c23d), each with 0
blockers. The maintainer merged #153 by hand at 23:57:09Z, a second after its review; the
driver wrote a `merged` line with no `by`. The driver merged #154 itself. Then it parked on
"the end of Phase 14: Day 23 starts Phase 15", as level 2 does at a phase's end.

- merged by hand: #153

"By hand" is the maintainer's word: GitHub gives the same login for every merge, and the run log
shows only that the driver did not ask for it.

## Merges

Each `merged` line with `"by": "driver"`:

- #154 at 2026-11-22T00:14:05Z, head 6f61333e2401c761fdabcb2a96539e5863b18ac4

GitHub gives #154's merge commit as eaefe7098d6044dc5fa1e5075aa87e988823e32d, merged at
00:13:33Z; the run log's line is written once the driver has read the merge back.

## Parks

Each `park` line of the copy, its time and line:

```text
2026-11-21T10:54:42Z park: the session parked: PR #108 needs the maintainer to review and merge it before the post-merge evidence check and the Phase 6/7 plan-auditor run can start. (session `fc600943-1141-4818-9de5-88d5620c9fa9`)
2026-11-21T12:51:07Z park: the session parked: PR #116 is open and needs the maintainer's review and "merged" before the Day 15 close can start. (session `656d9ab8-ed1d-433a-a85e-5f0c198cf39d`)
2026-11-21T17:15:21Z park: the session ended with no pull request and no PARK line (session `57665251-423f-455f-b20f-40320b774c97`)
2026-11-21T18:10:55Z park: the project's tree is not clean (1 paths)
2026-11-21T19:40:34Z park: the end of Phase 11: Day 20 starts Phase 12
2026-11-21T21:48:03Z park: the session ended with no pull request and no PARK line (session `1efd23a0-0957-41a0-afca-573029b50706`)
2026-11-21T22:19:59Z park: the end of Phase 12: Day 21 starts Phase 13
2026-11-21T23:08:50Z park: the end of Phase 13: Day 22 starts Phase 14
2026-11-22T00:18:44Z park: the end of Phase 14: Day 23 starts Phase 15
```

`status`'s "parks by reason" on the copy:

```text
parks by reason:
  2 park: the session ended with no pull request and no PARK line (session `…`)
  1 park: the end of Phase 11: Day 20 starts Phase 12
  1 park: the end of Phase 12: Day 21 starts Phase 13
  1 park: the end of Phase 13: Day 22 starts Phase 14
  1 park: the end of Phase 14: Day 23 starts Phase 15
  1 park: the project's tree is not clean (n paths)
  1 park: the session parked: PR #n is open and needs the maintainer's review and "merged" before the Day 15 close can start. (session `…`)
  1 park: the session parked: PR #n needs the maintainer to review and merge it before the post-merge evidence check and the Phase 6/7 plan-auditor run can start. (session `…`)
```

## Refusals

Each `refused` entry of the copy's `end` lines, its session, tool and input:

```text
7de1aefc-d93a-485c-b1fa-8d6cf6e3ed4a: Read: {"file_path": "/work/tests/test_direction_cli.py"}
7de1aefc-d93a-485c-b1fa-8d6cf6e3ed4a: Read: {"file_path": "/work/tests/test_timeline_cli.py"}
a7020b2a-dac1-4e34-a2f4-4a7b7b2864a2: Read: {"file_path": "/work/specs/day-18-direction-git-errors.md"}
d2b6f33d-8566-4482-9ea8-b674ddc2890b: Read: {"file_path": "/work/specs/day-19-prs-records.md"}
26aaba52-2585-49be-9679-62c573823f74: Read: {"file_path": "/work/specs/day-21-dates.md"}
d26d9fcb-3c4a-423d-925b-1fb01f041810: Bash: {"command": "cd /work; gh pr diff 153; ls specs/day-22*; git fetch -q origin pull/153/head 2>/dev/null; git log --oneline -1 d316c6c2a2", "description": "Show diff and spec file"}
3a64c23d-da44-4315-b4ad-9640abe5f808: Bash: {"command": "git fetch -q origin pull/154/head 2>/dev/null; gh pr diff 154 | head -c 30000", "description": "Show PR diff"}
```

Each line of `refusals-14.jsonl` (the hook log; `runlog.late_refusals` gives none of them late,
since each reviewer's `end` line counts its refusal):

```text
{"at": "2026-11-21T23:56:26Z", "session": "d26d9fcb-3c4a-423d-925b-1fb01f041810", "hook": "readonly", "tool": "Bash", "input": "{\"command\": \"cd /work; gh pr diff 153; ls specs/day-22*; git fetch -q origin pull/153/head 2>/dev/null; git log --oneline -1 d316c6c2a2\", \"description\": \"Show diff and spec file\"}", "line": "refused by the driver: the reviewer only reads"}
{"at": "2026-11-22T00:12:38Z", "session": "3a64c23d-da44-4315-b4ad-9640abe5f808", "hook": "readonly", "tool": "Bash", "input": "{\"command\": \"git fetch -q origin pull/154/head 2>/dev/null; gh pr diff 154 | head -c 30000\", \"description\": \"Show PR diff\"}", "line": "refused by the driver: the reviewer only reads"}
```

This repository's `refusals.json` on the `dashboard-data` branch, the rows for the trial's dates
(the main sessions' guards here, not the driver's):

```text
{"date": "2026-11-21", "guard": "auditor-guard", "refused": 1}
{"date": "2026-11-22", "guard": "read-guard", "refused": 1}
```

The five Read refusals are the driver's read limit on whole files of over 8,000 bytes; the two
Bash refusals are the reviewer's read-only hook on a `git fetch`.

## The reviewer

Each `review` line of the copy, with the reviewer's comment on the pull request, from
`gh pr view <n> --repo Yusuprozimemet/bearing --json comments`:

- #153, head d316c6c2a2af86d735007384e226302c68d9077d, blockers 0, comment https://github.com/Yusuprozimemet/bearing/pull/153#issuecomment-7071211308
- #154, head 6f61333e2401c761fdabcb2a96539e5863b18ac4, blockers 0, comment https://github.com/Yusuprozimemet/bearing/pull/154#issuecomment-7071402227

Each comment's body starts "review of `<head>` (session `<session>`)" with that line's head and
session. `on`'s output on the level 2 day held no "review: no comment on" line.

## Cost

`status`'s `cost:` line and the reviewer's line, on the copy:

```text
cost: $26.68, merged pull requests 17, $1.57 each (baseline $1.86)
reviewer: 2 sessions, $0.61, in the cost above
```

Worked from the copy's lines before "level 2 from:" and at or after it, by `status._cost`:

```text
count run alone: $23.92, merged pull requests 15, $1.59 each (baseline $1.86)
level 2 alone: $2.77, merged pull requests 2, $1.38 each (baseline $1.86)
```

The count run's figure counts four sessions whose pull request has no `merged` line: #108 and
#116, whose sessions ended with a `PARK:` line, and #123 and #139 (sessions 57665251 and
1efd23a0), merged by hand before their session ended. Its 15 merges include #101, whose
opener (session 2d6771a4, $0.56) ran on 2026-11-12, before the copy.

`python scripts/token-usage.py --compare --transcripts <an empty folder> --repo ../bearing
--container state/claude/projects --split 2026-11-22`, `../bearing`'s `main` pulled first, two
sides quoted:

```text
from 2026-11-02, before 2026-11-22: 508 replies on 2 days, median 51,314 and mean 52,368 context tokens per reply; 0.0% of its context read after a session passed 300k; $17.91 at the list prices checked 2026-11-02 ($0.0353 per reply); 32 pull requests merged on main from 2026-11-13 to 2026-11-21, 15.9 replies per merged pull request
after 2026-11-22: 106 replies on 1 days, median 50,930 and mean 48,283 context tokens per reply; 0.0% of its context read after a session passed 300k; $3.92 at the list prices checked 2026-11-02 ($0.0369 per reply); 4 pull requests merged on main from 2026-11-22 to 2026-11-22, 26.5 replies per merged pull request
```

Worked by hand:

- between: $17.91 / 32 = $0.56 per merged pull request (baseline $1.86); 15.9 replies per merged pull request (baseline 34.4)
- after: $3.92 / 4 = $0.98 per merged pull request (baseline $1.86); 26.5 replies per merged pull request (baseline 34.4)

"between" is the Day 10 step's one session and the count run, level 1. Its 32 merged pull
requests hold 19 no container session's `opened:` line names: the plan and spec pull requests
merged by hand (#99, #102 to #106, #110 to #114, #118, #119, #121, #125) and the four above
(#108, #116, #123, #139). "after" is the local date 2026-11-22: level 2 started at 00:42 local,
on the date the count run's last session ran and its last two pull requests merged (#148, #151),
so its 4 pull requests are #148 and #151 at level 1 and #153 and #154 at level 2, and its
replies include session bd865c00 (#151's opener) and the end of session 43f05fb7 (#148's
opener), which runs over local midnight and has replies on both sides.

The run log's dollars (each session's own `cost_usd`, the result's `total_cost_usd`) and
`--compare`'s (list prices of the main sessions' replies) are two measures: they are not
subtracted from each other.

## The usage limit

- usage limit: not met

No line of `run-14.jsonl` holds "usage limit": no step met it in the count run or on the level 2
day (H09.2).

## The install

`install-14.jsonl` holds session 76bd4a7f's id (Day 22 Track A, a level 2 step), then the
`input` of its first `Bash` tool_use that installs the project as bearing's CI does, then of its
first that runs the tests. They are one tool_use, so lines 2 and 3 are the same:

```text
python -m pip install -q -e ".[dev]" 2>&1 | tail -2; python -m pytest -q 2>&1 | tail -1; git checkout -q -b day-22/track-a-ingest-not-a-repo && echo ok
```

The install comes before the tests in that command. bearing's CI, `.github/workflows/evidence.yml`
line 30 at 456659bd4f6b232fc9da6e8a6e995ab89c23c254 (bearing at the level 2 day):

```text
        run: python -m pip install -e ".[dev]"
```

The session added `-q`; `tests.yml` runs `pytest -q` (H13.1). The transcript holds this tool_use
twice, in its `assistant` record and in an `api-request-blob` record whose command starts
`cd /work && `; the copy is the `assistant` record's.

## The first merge

- first merge: #154, head 6f61333e2401c761fdabcb2a96539e5863b18ac4

The driver's first `gh pr merge` on a real pull request, with `--match-head-commit` on the head
the checks and the reviewer saw. Before the level 2 day, the red-check probe (H13.2) on
`Yusuprozimemet/merge-probe` (public, recreated for the probe), gh 2.93.0, `main` protected with
a pull request required, 0 approvals, the required check "test", `enforce_admins` on, strict off;
pull request #1, its check "test" red, head ec3d79fed49cc9f5a92f64177d79b4c61bac4c78:

```text
$ gh pr merge 1 --merge --match-head-commit ec3d79fed49cc9f5a92f64177d79b4c61bac4c78
X Pull request Yusuprozimemet/merge-probe#1 is not mergeable: the base branch policy prohibits the merge.
To have the pull request merged after all the requirements have been met, add the `--auto` flag.
To use administrator privileges to immediately merge the pull request, add the `--admin` flag.
exit 1
```

The pull request stayed open. GitHub refuses the merge of a red head with the right sha, as it
refused a wrong sha on 2026-11-18.

## Unverified

- "By hand" for #123, #139 and #153 is the maintainer's word (The level 2 day).
- Whether the `on` at 23:36:32Z ran at level 2: it started no session.
- The reviewer's transcripts are counted as main sessions under `-work`: checked by `find` on
  2026-11-22 for the two reviewer sessions, not by a test.
- The escapes count below quotes bearing's spec, which is not copied: a Defect line left out is
  not caught by the test.
- The count run's first two sessions ran on the driver's `main` before 10b3d9d; their commit is
  not in the run log.

## Evidence

- closing PR: #154
- merge commit: eaefe7098d6044dc5fa1e5075aa87e988823e32d
- evidence run: 44965577837
- conclusion: success
- escapes: 0

bearing's Day 22 spec (`specs/day-22-ingest-not-a-repo.md`) has seven Defect lines: D22.1 to
D22.5 found by the auditor, D22.6 and D22.7 by Track A, none at `close`, by the `dashboard` or in
a review. The evidence runs after the day's merges (#151 at 456659bd, #153 at 5bbe4e11, #154 at
eaefe709) all concluded `success`; #153's was run 44964252447. So no line is quoted under
"escapes".
