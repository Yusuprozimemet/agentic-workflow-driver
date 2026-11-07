"""The driver reads and writes the project's issues through gh: the parks, the run's issue, the
phone's STOP (Day 5). Each call is one gh call, a failed one is a reason, never a guess."""

from driver.github import _gh


def open_issues(project, gh):
    # Only the maintainer's account counts: an issue anyone else opens is not a switch (plan.md,
    # "The switches").
    code, issues = _gh(
        project,
        gh,
        [
            "issue",
            "list",
            "--state",
            "open",
            "--author",
            "@me",
            "--limit",
            "100",
            "--json",
            "number,title,labels",
        ],
    )
    if code != 0 or issues is None:
        return [], f"gh issue list exited {code}"
    listed = [
        {
            "number": issue["number"],
            "title": issue["title"],
            "labels": [label["name"] for label in issue["labels"]],
        }
        for issue in issues
    ]
    return sorted(listed, key=lambda issue: issue["number"]), None


def closed_parks(project, gh):
    # A closed park is an answered one: the maintainer approved a phase's end, or a step failed
    # twice and was looked at. Only those count as answers, so an open park still parks the run.
    code, issues = _gh(
        project,
        gh,
        [
            "issue",
            "list",
            "--state",
            "closed",
            "--author",
            "@me",
            "--label",
            "parked",
            "--limit",
            "100",
            "--json",
            "number,title",
        ],
    )
    if code != 0 or issues is None:
        return set(), f"gh issue list exited {code}"
    return {issue["title"] for issue in issues}, None
