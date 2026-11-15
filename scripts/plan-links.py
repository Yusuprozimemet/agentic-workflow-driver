"""Check the plan's commitments and the links from criteria to them.

    python scripts/plan-links.py [--root DIR]

`specs/plan/promises.json` lists what `plan.md` commits to: P01 to P69 from the plan as
approved on 2026-11-06 (commit 2d64383), N01 onwards added by later plan changes. Each entry
carries a short quote that must stand literally in today's `plan.md`, so a plan change that
drops the words fails here and the entry is brought up to date with it.

`specs/plan/links-days-01-10.json` holds, for every criterion of Days 1 to 10, the
commitments it serves, each with words quoted literally from that commitment's text (or from
its `change`, the note a commitment the plan has since changed carries). They are the links two
fresh readers both made on 2026-11-13, a reader's "..." cut to its longest piece; the ten
closed specs are not edited.

From Day 11 on, each criterion of a day spec says it in its own `Plan:` line instead
(`specs/README.md`, "Rules"): `Plan: P27 "words from P27"; N03 "words from N03"`, or
`Plan: none` (optionally `Plan: none — <why>`). A criterion with no `Plan:` line, two of them,
or one in neither form fails, and its quotes are checked as the backfill's are.

A commitment is overdue when its `owner_day` is at or before the current Day (the highest Day
with a spec in `specs/`) and no criterion names it: that fails too, since a commitment no
criterion names has no test that can fail (#211, N5). `specs/plan/overdue.json` records the ones
known and not yet settled, each with the Day that settles it (`settled_by`) and why; an entry
holds only while the current Day is before that Day, so the spec of that Day goes red unless it,
or a spec change before it, names the commitment. An entry for a commitment that is named, not
due, or unknown fails, so the file only ever lists what is still open.

A Day from 11 on where more than a third of the criteria say `Plan: none` is printed as a
warning, not a failure: a sign that the plan needs a change (#212, S18).

Whitespace (line wrapping in `plan.md`) is not compared. Prints one line per problem and
exits 1, or one summary line and exits 0.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROMISE_ID = re.compile(r"[PN]\d\d")
CRITERION = re.compile(r"^- \[[ x]\] (C\d+\.\d+)\b(.*?)(?=^- |^#|\Z)", re.M | re.S)
PLAN_FIELD = re.compile(r"^[ \t]+Plan:(.*(?:\n[ \t]+(?![A-Za-z][\w -]*:)\S.*)*)", re.M)
PLAN_LINK = re.compile(r'([PN]\d\d) "([^"]+)"')
PLAN_NONE = re.compile(r"none(?: — .+)?")
DAY_FILE = re.compile(r"day-(\d+)-[^/\\]+\.md")
FIELDS = {"id", "short", "section", "owner_day", "rule_about_people", "quote", "text"}
BACKFILL_DAYS = range(1, 11)
PLAN_LINES_FROM = 11
OVERDUE = os.path.join("specs", "plan", "overdue.json")
NONE_SHARE = 1 / 3


def flat(text):
    return re.sub(r"\s+", " ", text).strip()


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def spec_criteria(specs_dir):
    """Each day spec's criteria, by Day: (id, the criterion's lines)."""
    days = {}
    for name in sorted(os.listdir(specs_dir)):
        m = DAY_FILE.fullmatch(name)
        if m:
            days.setdefault(int(m.group(1)), []).extend(CRITERION.findall(read(os.path.join(specs_dir, name))))
    return days


def link_problems(cid, pid, quote, texts, seen):
    if pid not in texts:
        return [f"{cid}: no such commitment {pid}"]
    problems = [f"{cid}: {pid} linked twice"] if pid in seen else []
    seen.add(pid)
    if not quote or quote not in texts[pid]:
        problems.append(f'{cid}: quote not in {pid}: "{quote}"')
    return problems


def plan_line(cid, block, texts):
    """The problems with one criterion's `Plan:` line, and the commitments it names."""
    fields = PLAN_FIELD.findall(block)
    if not fields:
        return [f"{cid}: no Plan: line (the commitments it serves, or Plan: none)"], []
    if len(fields) > 1:
        return [f"{cid}: more than one Plan: line"], []
    value = flat(fields[0])
    if PLAN_NONE.fullmatch(value):
        return [], []
    linked = PLAN_LINK.findall(value)
    if not linked or not re.fullmatch(r"[\s,;]*", PLAN_LINK.sub("", value)):
        return [f'{cid}: a Plan: line is none, or ids each with a quote: "{value}"'], []
    problems, seen = [], set()
    for pid, quote in linked:
        problems += link_problems(cid, pid, flat(quote), texts, seen)
    return problems, [pid for pid, _ in linked]


def overdue(promises, named, today, excepted):
    """The problems of commitments due by Day `today` that no criterion names, and of the
    recorded exceptions; `excepted` maps an id to its overdue.json entry."""
    owner = {e.get("id"): e.get("owner_day") for e in promises}
    problems = []
    for pid, day in owner.items():
        if not PROMISE_ID.fullmatch(str(pid)) or not isinstance(day, int) or day > today or pid in named:
            continue
        until = excepted.get(pid, {}).get("settled_by")
        if isinstance(until, int) and today < until:
            continue
        problems.append(f"{pid}: overdue, due on Day {day}, the current Day is {today}, and no criterion names "
                        f"it: name it in a Plan: line" + (f" (its exception ran out at Day {until})" if until
                        else f", or record it in {OVERDUE.replace(os.sep, '/')} with the Day that settles it"))
    for pid, entry in excepted.items():
        if pid not in owner:
            problems.append(f"{pid}: in {OVERDUE.replace(os.sep, '/')}, but no such commitment")
        elif pid in named:
            problems.append(f"{pid}: named by a criterion now: take it out of {OVERDUE.replace(os.sep, '/')}")
        elif not isinstance(owner[pid], int) or owner[pid] > today:
            problems.append(f"{pid}: in {OVERDUE.replace(os.sep, '/')}, but not due yet")
        elif not isinstance(entry.get("settled_by"), int) or not entry.get("why"):
            problems.append(f"{pid}: an exception gives settled_by, a Day number, and why")
    return problems


def none_shares(root):
    """A warning for each Day from 11 on where more than a third of the criteria say Plan: none."""
    warnings = []
    for day, criteria in sorted(spec_criteria(os.path.join(root, "specs")).items()):
        if day < PLAN_LINES_FROM:
            continue
        values = [flat(f[0]) for _, block in criteria if len(f := PLAN_FIELD.findall(block)) == 1]
        none = sum(bool(PLAN_NONE.fullmatch(v)) for v in values)
        if values and none / len(values) > NONE_SHARE:
            warnings.append(f"warning: Day {day}: {none} of {len(values)} criteria say Plan: none, more than a "
                            "third: the plan may need a change (#212, S18)")
    return warnings


def check(root):
    problems = []
    plan = flat(read(os.path.join(root, "plan.md")))
    promises = json.loads(read(os.path.join(root, "specs", "plan", "promises.json")))
    links = json.loads(read(os.path.join(root, "specs", "plan", "links-days-01-10.json")))
    days = spec_criteria(os.path.join(root, "specs"))

    texts = {}
    for e in promises:
        pid = e.get("id", "?")
        missing = FIELDS - set(e)
        if missing:
            problems.append(f"{pid}: missing {', '.join(sorted(missing))}")
            continue
        if not PROMISE_ID.fullmatch(pid):
            problems.append(f"{pid}: an id is P or N and two digits")
        if pid in texts:
            problems.append(f"{pid}: listed twice")
        texts[pid] = flat(e["text"] + " " + e.get("change", ""))
        owner, rule = e["owner_day"], e["rule_about_people"]
        if rule and owner is not None:
            problems.append(f"{pid}: a rule about people has no owner Day")
        if not rule and not (isinstance(owner, int) and owner >= 1):
            problems.append(f"{pid}: owner_day must be a Day number")
        quote = flat(e["quote"])
        if not quote:
            problems.append(f"{pid}: empty quote")
        elif quote not in plan:
            problems.append(f'{pid}: quote not in plan.md: "{quote}"')

    known = {c for criteria in days.values() for c, _ in criteria}
    named = {link.get("p") for served in links.values() for link in served}
    for cid, served in links.items():
        if cid not in known:
            problems.append(f"{cid}: no such criterion in specs/")
        seen = set()
        for link in served:
            problems += link_problems(cid, link.get("p"), flat(link.get("quote", "")), texts, seen)
    for day in BACKFILL_DAYS:
        for cid, _ in days.get(day, []):
            if cid not in links:
                problems.append(f"{cid}: Day {day} criterion missing from the backfill")
    count, lines = sum(len(v) for v in links.values()), 0
    for day in sorted(d for d in days if d >= PLAN_LINES_FROM):
        for cid, block in days[day]:
            found, made = plan_line(cid, block, texts)
            problems += found
            lines, count, named = lines + 1, count + len(made), named | set(made)
    path = os.path.join(root, OVERDUE)
    excepted = {e.get("id"): e for e in json.loads(read(path))} if os.path.exists(path) else {}
    problems += overdue(promises, named, max(days, default=0), excepted)
    return problems, (f"plan links: {len(texts)} commitments, {len(links)} criteria, "
                      f"{lines} Plan: lines, {count} links, every quote found")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=os.path.dirname(HERE))
    args = ap.parse_args(argv)
    problems, summary = check(args.root)
    for p in none_shares(args.root) + problems:
        print(p)
    if problems:
        print(f"plan links: {len(problems)} problem(s)")
        return 1
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
