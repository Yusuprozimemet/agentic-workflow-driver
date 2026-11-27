# The tooling

`scripts/` holds this repository's commands: each one a body of its own, run by hand, by a hook or
by CI. The specs, the workflows and the docs name them by path, so their names and places do not
move; this page only sorts them by what they are for. Their tests are in `scripts/tests/`, run one
file at a time (`python scripts/tests/test_<name>.py`). Three tests stay beside the scripts on
purpose: `test_token_usage.py`, frozen by C16.19 (a hold in force); `test_setup_check.py`, which
Day 10's break record runs by this path (C10.29); and `test_dashboard_page.py`, which Day 14's break
record runs by this module name (C14.9).

## The dashboard's data: sources

| File | What it does |
|---|---|
| `spec_drift_common.py` | What every part of spec-drift.py reads: the patterns, the project file's values, and where the page and its data live. |
| `spec_drift_git.py` | spec-drift.py's reading of git and GitHub: commands, merges, branches, PRs, runs and parked issues. |
| `spec_drift_specs.py` | spec-drift.py's reading of plan.md and the day specs: steps, tracks, criteria, evidence and removals. |
| `spec_drift_handoffs.py` | spec-drift.py's reading of hand-offs: what one day defers to a later one, and what lies ahead. |
| `spec_drift_data.py` | spec-drift.py's reading of what git and GitHub cannot give: the dashboard-data branch and the evidence report. |
| `spec_drift_files.py` | The dashboard's file map: every tracked file as one dot, hung under the station of the workflow it serves. |
| `spec_drift_plan.py` | spec-drift.py's plan graph: what `plan.md` commits to, and which criteria say they serve each commitment. |

## The dashboard's data: counts

| File | What it does |
|---|---|
| `spec_drift_metrics.py` | spec-drift.py's measures: the clock, the chance bands, the names in code, boundaries and yardsticks. |
| `spec_drift_score.py` | spec-drift.py's quality score: one number out of 100 for the whole project, each Day and each ability. |
| `spec_drift_views.py` | spec-drift.py's newer views: one function per section of the page, each written under its own key of spec-drift.json. |

## The dashboard's data: build

| File | What it does |
|---|---|
| `spec-drift.py` | Measure how the spec and the code move against each other, merge by merge. |
| `spec_drift_page.py` | spec-drift.py's page: the data the dashboard draws, and the one-file page it builds. |
| `demo-data.py` | Made-up data in the shape spec-drift.py writes for the dashboard, for a project called sample-shop. |
| `dashboard-reconcile.py` | Hold each new section of the dashboard to the graph it is drawn beside, one line per section. |

## Counts from outside git

| File | What it does |
|---|---|
| `replay-history.py` | Whether each in-force criterion still holds at each merge on main: its breaks re-run on that merge's code. |
| `driver-runs.py` | Count the driver's run log into docs/dashboard/driver-runs.json, for the dashboard. |
| `publish-counts.py` | Publishes this machine's count of the sessions without a pull request. |
| `token-usage.py` | Count the Claude Code tokens spent on this repository, per date, migration day, model and agent. |
| `infra-summary.py` | Summarises one infra-ci run for the dashboard: the criteria that ran and failed, the steps, and an hour's cost. |
| `refusal_log.py` | Every refusal a guard makes, one JSON line each, so the dashboard can count them. |

## Gates on a pull request

| File | What it does |
|---|---|
| `pre-push.py` | Run every pull-request check that has a local command, one line per check; exit 1 on any failure. |
| `pr-names.py` | A pull request's branch, title, commit subjects and Jira keys agree with each other. |
| `invariants.py` | Fail a pull request that edits what the project must not change, and name each file. |
| `plan-links.py` | Check the plan's commitments and the links from criteria to them. |
| `criteria-wording.py` | Keep accepted day criteria unchanged outside `day-NN/spec-<slug>` PRs. |
| `case-count.py` | Does a pull request that edits a brief with known cases show the cases' count on that brief? |
| `check-links.py` | Check that every relative link in the given Markdown files points at a file that exists. |
| `service-wiring.py` | Every service under services/ is wired into compose and Prometheus the way the first one was. |
| `behaviour-index.py` | List the ticked criteria that still describe the behaviour in force. |
| `brief-check.py` | Check the paths and names a brief gives the implementer against the tree, before it is sent. |
| `test-parallel.py` | Run tests/ one file per process, in parallel; print failures and the counts. |
| `setup-check.py` | Is a copied kit set up? One line per item, from GitHub's settings and the files. |

## Seen red and breaks on purpose

| File | What it does |
|---|---|
| `seen-red.py` | Run the branch's tests on the code as it was before the day, and print the `seen red:` line. |
| `track-red.py` | Run each test a track's `new` criteria name, on the code before the track and on the track. |
| `break.py` | Break the code on purpose once, run the check, put the code back, and print the `broken:` line. |
| `break-lines.py` | Print a branch's break lines from its break record, or check a spec's `broken:` lines against it. |
| `track-breaks.py` | Replay a track PR's breaks, and the day's earlier tracks', on the PR's code, before the close does. |

## The close

| File | What it does |
|---|---|
| `close-evidence.py` | Replay a closed day, or a short spec landed, on main; with --rehearse, a closing branch before it merges. |
| `evidence.py` | Each ticked criterion's evidence holds up at the commit its day's close merged. |
| `close-views.py` | A closing PR's defect views, printed from one record: the Defect lines in the day spec's Notes. |
| `relabel.py` | A second, blind reading of a day's Defect lines, and how far it agrees with the tags they carry. |
| `phase-table.py` | The phase-end table: what the maintainer reads at a phase's stop, beside the plan-auditor's report. |

## Guards on a session

| File | What it does |
|---|---|
| `auditor-guard.py` | The auditors only read: a hook in the project settings (.claude/settings.json) makes it so. |
| `read-guard.py` | A Read of a whole large file is sent back once to read the part it needs. |
| `cap-output.py` | A long Bash result keeps its first and last 3,000 characters in the context; the rest is saved. |
| `step-guard.py` | After the maintainer says "merged", the session finishes step 5 and stops: new work waits for a new session. |
| `session-size.py` | Warn when a session's context passes 150k tokens, and again at each further 50k; never block. |

## Agents with cases

| File | What it does |
|---|---|
| `agent-cases.py` | Does an agent still answer its known cases as it did before its brief was edited? |
| `improve-loop.py` | A proposed brief for one agent with known cases, measured before it reaches a pull request. |
