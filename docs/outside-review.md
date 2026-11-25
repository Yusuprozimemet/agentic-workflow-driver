# The outside review, once a phase

Every check in this repository was written by sessions that share its habits: the same
`CLAUDE.md`, the same spec rules, the same model family. The spec-auditor, the track-reviewer
and the merge reviewer each read from a fresh context, but none of them reads from outside the
repository's way of seeing, and their case counts say each misses most known faults alone
(`CLAUDE.md`, "Five principles"). Once a phase, a model from outside reads a few of the phase's
merged PRs as a stranger would.

It is advice, like the auditors': it gates nothing, and what becomes a PR is the maintainer's call.

## When

At step 6, after a phase's last closing PR has merged and step 5 is done, in the same session as
the plan-auditor's run on the phase (`CLAUDE.md`, "A day, in order"). The session picks the PRs
and writes the prompt; the maintainer gives it to the model by hand.

## Which PRs

Three, picked at random from the phase's Days' merged PRs (branches `day-NN/` for each Day the
phase holds), with the merge commit of the phase's last close as the seed, so that a second
session picks the same three. With `<NN|NN|NN>` the phase's Days and `<sha>` that merge commit:

```
gh pr list --state merged --limit 500 --json number,headRefName --jq ".[] | select(.headRefName | test(\"^day-(<NN|NN|NN>)/\")) | .number" > prs.txt
python -c "import random,sys; n=sorted(int(x) for x in open('prs.txt')); random.seed(sys.argv[1]); print(*sorted(random.sample(n, 3)))" <sha>
```

The session does not swap a pick for a PR it thinks better: a choice is where its habits come
back in.

## What the model gets

For each PR: its body (`gh pr view <n> --json title,body`), its diff (`gh pr diff <n>`), and the
spec criteria it names. Not this file's history, not the auditors' reports, not the dashboard:
the stranger reads what a reviewer at the merge had.

## The prompt

Give the model this text, with the three PRs pasted below it:

> You are reviewing three pull requests that already merged into a repository you have never
> seen. Its maintainer merges on CI and on reports by AI agents; no person reads every line.
> For each pull request:
>
> 1. Does the code do what the description says it does? Name any claim the diff does not bear
>    out.
> 2. Name up to three faults a careful reviewer would have blocked the merge on: a bug, a test
>    that cannot fail, a number that does not match, a change the description does not mention.
>    For each, the file and line, and what goes wrong.
> 3. Name one rule, step or section of the description that looks like ceremony: it costs the
>    author time and would not catch anything here.
> 4. Say: accept, doubt or reject, and why, in one sentence.
>
> Say "none" where you find none. Do not guess what the repository's other files say.

## What happens to the answer

The session that runs step 6 puts the model's answer beside the plan-auditor's report, as it
came, with the model's name and the three PR numbers. The maintainer reads it. A fault they
accept goes into the next phase's first Day's Notes as a Defect line,
`found: Day <NN> review`, with `<NN>` the Day whose PR it was: it is an escape from that Day,
since it passed every gate. A rule they agree is ceremony goes into the same Notes as a
hand-off, for a `docs/` PR after that Day closes.
