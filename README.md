# agentic-workflow-driver

A driver for projects set up from the
[agentic workflow kit](https://github.com/Yusuprozimemet/agentic-workflow-kit): `run-steps.py`
runs a project's day loop, one `claude -p` session per step, and parks for the maintainer when a
step needs a person. The maintainer writes the project's `plan.md` and answers the parks.

Nothing is built yet. [plan.md](plan.md) is the goal; the day specs in [specs/](specs/) are the
steps; [CLAUDE.md](CLAUDE.md) is the working order. This repository is itself run by hand, one day
spec at a time, as the kit describes ([docs/kit.md](docs/kit.md)); the driver never drives it.

- Set up from the kit at `393dda6` (2026-11-06).
- Kit commits the driver's contract test has passed on: none yet (Day 1 adds `ContractTest`).

Run the tests with `python -m unittest discover -s tests` (they need `numpy`:
`python -m pip install -r requirements.txt`), and the style check with
`ruff check . && ruff format --check .`.

## Findings

None yet. Each closing PR adds what its day found; the details are in
[docs/lab-notebook.md](docs/lab-notebook.md).
