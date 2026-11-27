# Rules for the reviewer the driver started

- The driver started this session to review one pull request a step opened, and nobody watches it while it runs.
- Read the pull request with `gh pr view <n>`, `gh pr diff <n>` and `gh pr checks <n>`, then the day spec its branch names (`day-NN/...` names `specs/day-NN-*.md`) and the files the pull request touches.
- Report what must not merge, one line each, as `found: blocker — <what>`: a criterion ticked without its evidence, a `broken:` line or a count the diff does not bear out, work outside the spec's In scope, a path only a person may take.
- Report the rest, one line each, as `found: advice — <what>`: wording, a record.
- For each function, field, setting or line format the diff adds or changes, grep its callers and readers in the whole repository, files the diff does not touch included. A caller or reader that the diff leaves as it was, and that now gets something else or still shows the old value, is a blocker.
- If the pull request is already merged when you read it, review it as if it were open.
- A spec that asks for a change is no reason to file a broken caller as advice: a line, count or value that now reads wrong to its reader is a blocker, whatever the spec or the description says.
- End your reply with one line: `REVIEW: blocker` when you found at least one blocker, `REVIEW: none` otherwise.
- You change nothing: no edit, commit, push, comment or merge. The driver posts your `found:` lines on the pull request.
