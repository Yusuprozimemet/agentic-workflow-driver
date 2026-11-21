# Rules for a session the driver started

- This session was started by the driver, and nobody watches it while it runs.
- When the step needs the maintainer, open no pull request, and end the last reply with one line: `PARK: <the reason, in one sentence>`.
- After you open the step's pull request, end the last reply without a `PARK:` line, even where the project's CLAUDE.md says to stop and wait for "merged": the driver waits for the merge itself.
- You never merge a pull request, and you never push to `main`.
- Before running the project's tests, install the project as its CI does (its workflows in `.github/workflows/`).
- A lesson for CLAUDE.md goes in the day's Notes as a `Hand-off` line to the maintainer; do not edit CLAUDE.md.
