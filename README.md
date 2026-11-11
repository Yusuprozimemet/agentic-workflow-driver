# agentic-workflow-driver

A driver for projects set up from the
[agentic workflow kit](https://github.com/Yusuprozimemet/agentic-workflow-kit): `run-steps.py`
runs a project's day loop, one `claude -p` session per step, and parks for the maintainer when a
step needs a person. The maintainer writes the project's `plan.md` and answers the parks.

Nothing is built yet. [plan.md](plan.md) is the goal; the day specs in [specs/](specs/) are the
steps; [CLAUDE.md](CLAUDE.md) is the working order. This repository is itself run by hand, one day
spec at a time, as the kit describes ([docs/kit.md](docs/kit.md)); the driver never drives it.

- Set up from the kit at `393dda6` (2026-11-06).
- Kit commits the driver's contract test has passed on: `393dda6` (Day 1, #3).

Run the tests with `python scripts/test-parallel.py`, one test file per process (they need
`numpy`: `python -m pip install -r requirements.txt`); CI runs the same tests serially with
`python -m unittest discover -s tests`. The style check is
`ruff check . && ruff format --check .`.

## Findings

Each closing PR adds what its day found; the details are in
[docs/lab-notebook.md](docs/lab-notebook.md).

- **Day 01:** the auditors found 14 of the day's 18 defects in the spec, before any code. Every
  `new` test was seen red, and nothing the day made escaped it. The close's evidence rehearsals
  caught two recorded breaks that could not replay: one report held a hash that changes on
  every run, the other a Windows path. Only CI's Linux rehearsal caught the second.
- **Day 08:** the driver ran one day of another project at level 1, three pull requests merged
  unchanged, two parks, one refusal, and that day's evidence replay green. The spec-auditor found 66 of the
  day's 82 defects before any code. The trial did not meet the usage limit, so that part stays not proven.
