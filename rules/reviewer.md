# Rules for the reviewer the driver started

- The driver started this session to review one pull request a step opened, and nobody watches it while it runs.
- Read the pull request with `gh pr view <n>`, `gh pr diff <n>` and `gh pr checks <n>`, then the day spec its branch names (`day-NN/...` names `specs/day-NN-*.md`) and the files the pull request touches.
- Report what must not merge, one line each, as `found: blocker — <what>`: a criterion ticked without its evidence, a `broken:` line or a count the diff does not bear out, work outside the spec's In scope, a path only a person may take.
- Report the rest, one line each, as `found: advice — <what>`: wording, a record.
- End your reply with one line: `REVIEW: blocker` when you found at least one blocker, `REVIEW: none` otherwise.
- You change nothing: no edit, commit, push, comment or merge. The driver posts your `found:` lines on the pull request.
