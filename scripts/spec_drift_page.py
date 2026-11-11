"""spec-drift.py's page: the data the dashboard draws, and the one-file page it builds."""

import ast
import functools
import importlib.util
import json
import os
import re
import subprocess
import tempfile

from spec_drift_common import (
    BREAK_NONE,
    CITED_PR,
    COMMAND,
    FINISHED,
    PAGE,
    PLACEHOLDERS,
)
from spec_drift_git import (
    own_day,
    run,
)
from spec_drift_specs import (
    broke,
    criterion_evidence,
    evidence,
    evidence_test_names,
    moves,
    replacement_lines,
    section,
    test_state,
    track_criteria,
)
from spec_drift_data import (
    replay_row_state,
)


def deployment():
    """The live checks of the one deployment (the project's own), or None if nothing was deployed."""
    path = os.path.join(PAGE, "deployment.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def criterion_index(days, reports, handoffs, snaps, blobs, order=()):
    """Join recorded evidence without treating an unavailable source as a negative result."""
    names = {t for d in days for c in d["evidence"] for t in evidence_test_names(c["block"])}
    states = test_state(names, snaps[-1]["sha"], blobs, {old: new for _, old, new in moves(snaps)})
    report_days = {d["day"]: d for d in reports.get("days", [])}
    rows, attention = [], []
    def flag(row, reason, detail):
        attention.append(dict(id=row["id"], reason=reason, detail=detail, day=row["day"]))

    for day in days:
        report = report_days.get(day["day"], {})
        for check in report.get("checks", []):
            if check.get("criterion") is None and check["status"] in ("failed", "error"):
                flag(dict(id=f"Day {day['day']:02d}", day=day["day"]), "replay_" + check["status"],
                     check.get("diagnostic") or check.get("label") or "")
        for c in day["evidence"]:
            if not c["id"]:
                continue
            block = c["block"]
            evidence_text = criterion_evidence(block)
            tests = evidence_test_names(block)
            # An Evidence line that points at "the command above" cites the claim's own command.
            claim_text = re.split(r"(?im)^\s*Evidence:", block, maxsplit=1)[0]
            command = re.search(COMMAND, evidence_text) or (
                re.search(r"\bcommands? above\b", evidence_text, re.I) and re.search(COMMAND, claim_text))
            measured = c["ticked"] and day.get("evidence_format", True)
            # A ticked box a reader judged has its Not proven: line as proof (specs/README.md), and cites its PR there.
            reader = re.search(r"(?m)^\s+Not proven:\s*(.*(?:\n(?!\s*(?:broken:|Replaces:|Evidence:))\s+[^\n]+)*)", block)
            cited = bool(CITED_PR.search(evidence_text) and (tests or command)
                         or reader and CITED_PR.search(reader.group(1))) if measured else None
            red_lines = [line.strip() for line in block.splitlines()
                         if broke(line) or re.search(r"\bseen[- ]red\b", line, re.I)]
            red = bool(red_lines) if measured else None
            # `broken: none → <why>`: a check that cannot be broken from the repository, and why.
            none = [why.strip() for what, why in BREAK_NONE.findall(block) if what.lower() == "none"]
            found = all(states[t] != "missing" for t in tests) if tests else None
            state = report.get("state", reports["state"] if reports["state"] != "loaded" else "not checked")
            checks = [x for x in report.get("checks", []) if x.get("criterion") == c["id"]]
            replay = dict(state=state, status=[x["status"] for x in checks] or None,
                          why=report.get("why", []) + ([reports["diagnostic"]] if reports.get("diagnostic") else [])
                          + [x["diagnostic"] for x in checks if x.get("diagnostic")], checks=checks)
            track = next((name for name, work in day.get("track_work", {}).items()
                          if c["id"] in track_criteria(work)), None)
            if track is None and len(day.get("tracks", [])) == 1:
                track = day["tracks"][0]
            claim = re.split(r"\n\s*(?:Evidence|Test|broken|Replaces):", block, maxsplit=1, flags=re.I)[0]
            claim = re.sub(r"^- \[[ x]\]\s*\S+\s*(?:\*\*(?:new|hold)\*\*\s*[—-]\s*)?", "", claim)
            row = dict(id=c["id"], day=day["day"], phase=day.get("phase"), tag=c["kind"], claim=" ".join(claim.split()),
                       ticked=bool(c["ticked"]),
                       spec=day["file"] + "#acceptance-criteria", track=track,
                       prs=sorted({int(n) for n in CITED_PR.findall(evidence_text)}), tests=tests,
                       cited=cited, test_found=found, seen_red=dict(state=red, lines=red_lines, none=none), replay=replay,
                       replaces=[i for _, ids in replacement_lines(block) for i in ids], replaced_by=[])
            rows.append(row)
            for check in checks:
                if check["status"] in ("failed", "error"):
                    flag(row, "replay_" + check["status"], check.get("diagnostic") or check.get("label") or "")
            if state == 'stale':
                flag(row, "replay_stale", "; ".join(replay["why"]))
            if cited is False:
                flag(row, "evidence_missing", "No evidence and PR cited together")
            if day["status"] in FINISHED and state in ("absent", "invalid", "not checked"):
                flag(row, "evidence_missing", "Replay report: " + state)
            if red is False and none:
                flag(row, "not_breakable", "; ".join(none))
            elif red is False:
                flag(row, "not_seen_red", "No seen-red or broken line")
            if found is False:
                flag(row, "test_not_found", ", ".join(t for t in tests if states[t] == "missing"))
            # The "Tests on main" column's orange: a test CI can skip is noted here, not a fault. That
            # column reads the states evidence_history gives the names in the whole block, not only the
            # Evidence line's; before it runs, `tests` is still the list of names.
            day_states = c["tests"] if isinstance(c.get("tests"), dict) else {}
            skips = list(dict.fromkeys([t for t in tests if states[t] == "skippable"]
                                       + [t for t, s in day_states.items() if s == "skippable"]))
            if skips:
                flag(row, "test_skippable", ", ".join(skips))
            for h in handoffs:
                if not h["picked"] and re.search(rf"\b{re.escape(c['id'])}\b", h["text"]):
                    flag(row, "handoff_unclaimed", h["text"])
    by_id = {r["id"]: r for r in rows}
    for row in rows:
        for target in row["replaces"]:
            if target in by_id:
                by_id[target]["replaced_by"].append(row["id"])
    severity = ("replay_failed", "replay_error", "replay_stale", "evidence_missing",
                "not_seen_red", "test_not_found", "handoff_unclaimed", "not_breakable", "test_skippable")
    attention.sort(key=lambda a: (severity.index(a["reason"]), a["day"], a["id"]))
    for item in attention:
        del item["day"]
    # handoff_unclaimed above needs a hand-off to name a criterion; hand-offs name their own ID and
    # a day, and the day they go to has no criteria yet. So each open one is listed, after the rest:
    # those for the next day to run, then those no later day picks up.
    finished = {d["day"] for d in days if d["status"] in FINISHED}
    upcoming = next((d for d in order if d not in finished and d not in PLACEHOLDERS), None)
    for reason, to in ((("handoff_next", upcoming),) if upcoming else ()) + (("handoff_unpicked", None),):
        for h in handoffs:
            if not h["picked"] and h.get("to") == to:
                text = " ".join(re.sub(r"^\s*-\s*", "", h["text"]).split())
                attention.append(dict(id=h.get("id") or h["source"], reason=reason,
                                      detail=(f"Day {to:02d}: " if to is not None else "") + text))
    return rows, attention


def first_sentence(text, limit=200):
    """A claim's first sentence for a reader, its backticks gone: the fallback for a promise with no plain
    sentence. It ends at a full stop before a capital, a quote or the end, so `run-steps.py --once` stays whole."""
    text = " ".join(text.replace("`", "").split())
    match = re.match(r"(.+?[.!?])(?=\s+[A-Z\"]|\s*$)", text)
    sentence = match.group(1) if match else text
    return sentence if len(sentence) <= limit else sentence[:limit].rsplit(" ", 1)[0] + "…"


def attach_plain(index, path=None):
    """Each criterion's plain sentence from docs/dashboard/plain-promises.json, or the first sentence of
    its claim: a new day with no entry, or a file that cannot be read, must not break the page."""
    path = path or os.path.join(PAGE, "plain-promises.json")
    try:
        with open(path, encoding="utf-8") as f:
            written = json.load(f)
    except (OSError, ValueError):
        written = {}
    if not isinstance(written, dict):
        written = {}
    for row in index:
        text = written.get(row["id"])
        ok = isinstance(text, str) and text.strip()
        row["plain"] = text.strip() if ok else first_sentence(row["claim"])
        row["plain_source"] = "written" if ok else "first sentence"


ABILITIES = (
    dict(key="rehearse", name="Shows what it would do", role="rung"),
    dict(key="stop", name="Can be stopped, from anywhere", role="rung"),
    dict(key="loop", name="Works through the night", role="rung"),
    dict(key="park", name="Asks only when it must", role="rung"),
    dict(key="recover", name="Picks itself up after a crash", role="rung"),
    dict(key="see", name="Shows the world what still works", role="rail"),
    dict(key="record", name="Proves every claim", role="rail"),
)
STORY_TEMPLATE = re.compile(r"As an? \[type of user\],? I want \[goal or capability\],? so that \[benefit or outcome\]\.?")


def story_section(body):
    """The "## User story" section of a PR body, HTML comments gone, or "" when there is none."""
    # The comments are the template's advice; the section ends at the next "## " heading.
    lines = re.sub(r"<!--.*?-->", "", body or "", flags=re.S).splitlines()
    start = next((i for i, line in enumerate(lines) if re.match(r"##\s*User story\s*$", line)), None)
    if start is None:
        return ""
    rest = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        rest.append(line)
    return " ".join(" ".join(rest).split())


def story_ability(section):
    """The Ability: line's key, or None: `Ability: <key>` with the key one of ABILITIES, in any case and with its
    square brackets optional. The unfilled template, "[one of ...]", names no key, so it is None."""
    match = re.search(r"Ability:\s*\[?\s*(\w+)", section, re.I)
    key = match.group(1).lower() if match else None
    return key if key in [a["key"] for a in ABILITIES] else None


def story_sentence(section):
    """The story's own words: the section with the Ability: line removed; "" when that is only the template's
    placeholders, so a PR that left the template as it was has no story."""
    text = " ".join(re.sub(r"Ability:\s*(\[[^\]]*\]|\S+)", "", section, flags=re.I).split())
    return "" if not text or STORY_TEMPLATE.fullmatch(text) else text


def story_reader(sentence):
    """Who the story is written for, from its "As ..." clause: "away" when they are not at a desk, "reader" when
    they only read the dashboard, else "desk". "away" wins when both match; with no clause it is "desk"."""
    match = re.match(r"\s*As\s+(.*?)(?:,\s*|\s+)I want\b", sentence, re.I)
    if not match:
        return "desk"
    clause = match.group(1).lower()
    if any(w in clause for w in ("phone", "away", "overnight", "asleep", "night", "leaves", "leave", "running",
                                 "runs the driver")):
        return "away"
    if any(w in clause for w in ("dashboard", "page", "reading", "reads", "reader", "looking", "visiting",
                                 "opening", "someone")):
        return "reader"
    return "desk"


def user_stories(prs, path=None):
    """Every merged pull request's user story with its ability, for the dashboard: the PR body's own section and
    Ability: line first, docs/dashboard/user-stories.json for the ones written before the template asked, and a
    problem line for each PR that has neither. The page must not break on a missing or unreadable file."""
    source = path or "docs/dashboard/user-stories.json"
    path = path or os.path.join(PAGE, "user-stories.json")
    try:
        with open(path, encoding="utf-8") as f:
            written = json.load(f)
    except (OSError, ValueError):
        written = {}
    if not isinstance(written, dict):
        written = {}
    keys = [a["key"] for a in ABILITIES]
    rows, problems = [], []
    for p in sorted((p for p in prs if p["state"] == "MERGED"), key=lambda p: p["number"]):
        number = p["number"]
        section = story_section(p.get("body"))
        sentence = story_sentence(section)
        ability = story_ability(section)
        entry = written.get(str(number))
        entry = entry if isinstance(entry, dict) else {}
        kept = entry.get("story")
        kept = kept.strip() if isinstance(kept, str) else ""
        story, story_source = (sentence, "pr") if sentence else (kept, "written" if kept else "missing")
        if ability:
            ability_source = "pr"
        elif entry.get("ability") in keys:
            ability, ability_source = entry["ability"], "written"
        else:
            ability_source = "missing"
        if story_source == "missing":
            problems.append(f"#{number} has no user story")
        if ability_source == "missing":
            problems.append(f"#{number} names no ability: add an Ability: line or an entry in "
                            "docs/dashboard/user-stories.json")
        named = dict(headRefName=p.get("headRefName") or "", title=p.get("title") or "")
        rows.append(dict(number=number, title=p["title"], url=p["url"], branch=p.get("headRefName") or "",
                         day=own_day(named),
                         date=(p.get("mergedAt") or "")[:10] or None, ability=ability,
                         ability_source=ability_source, story=story, story_source=story_source,
                         reader=story_reader(story)))
    return dict(abilities=[dict(a) for a in ABILITIES], stories=rows, problems=problems, source=source)


def attach_abilities(index, stories):
    """Each promise's abilities: the ones its pull requests grew, the most-grown first and a tie going to the one
    whose pull request is cited first. A promise is kept by the pull requests that grew it, so one that cites none
    yet, or none with an ability, gets []."""
    ability = {s["number"]: s["ability"] for s in stories}
    for row in index:
        keys = [ability[n] for n in row["prs"] if ability.get(n)]
        # sorted() is stable, so keys that are equally common keep the order they were cited in.
        row["abilities"] = sorted(dict.fromkeys(keys), key=lambda k: -keys.count(k))


# What runs each test file, first match wins: tests.yml runs tests/ on every push and pull request, where
# the live modules skip without DRIVER_LIVE_CLI; spec-drift-tests.yml runs scripts/test_*.py.
TEST_GROUPS = (
    ("live", r"^tests/test_live_", "Live runs against real Claude",
     "By hand only: skipped in CI, which has no login or budget"),
    ("gap", r"^tests/test_dashboard_gap\.py$", "The dashboard's gap numbers", "Every push and pull request"),
    ("driver", r"^tests/test_[^/]*\.py$", "Driver behaviour", "Every push and pull request"),
    ("tooling", r"^scripts/test_[^/]*\.py$", "Project tooling",
     "Only on pull requests that touch a script or a file they read (spec-drift-tests.yml)"),
)


def count_tests(source):
    """The test methods of a module's classes, as unittest finds them; a module that does not parse is None."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    return sum(isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.name.startswith("test")
               for c in ast.walk(tree) if isinstance(c, ast.ClassDef) for f in c.body)


def test_inventory(paths, read):
    """The tests on main by what runs them: each file counted once, in the first of TEST_GROUPS that
    names it. `read` gives a path's text; a module that does not parse is named, not counted."""
    groups = {key: dict(key=key, label=label, when=when, files=0, tests=0) for key, _, label, when in TEST_GROUPS}
    unreadable = []
    for path in sorted(paths):
        key = next((k for k, pattern, _, _ in TEST_GROUPS if re.search(pattern, path)), None)
        if key is None:
            continue
        count = count_tests(read(path))
        if count is None:
            unreadable.append(path)
            continue
        groups[key]["files"] += 1
        groups[key]["tests"] += count
    # In the order a reader meets them: what the driver does first.
    ordered = [groups[k] for k in ("driver", "live", "gap", "tooling")]
    return dict(groups=ordered, total=sum(g["tests"] for g in ordered), unreadable=unreadable)


INFRA_TRIES = 5


def infra_summary(run_id):
    """One infra workflow run's summary (scripts/infra-summary.py), or None if its artifact does not download."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            run("gh", "run", "download", str(run_id), "-n", "infra-summary", "-D", tmp)
            with open(os.path.join(tmp, "infra-summary.json"), encoding="utf-8") as f:
                return json.load(f)
        except (subprocess.CalledProcessError, OSError, ValueError):
            return None


def infra(workflow):
    """The infra workflow's runs on main, and the summary of the newest completed run whose artifact
    downloads (artifacts expire, so an old run may have none). With no workflow, none: gh is not asked."""
    if not workflow:
        return dict(runs=[], latest=None)
    try:
        listed = json.loads(run("gh", "run", "list", "--workflow", workflow, "--branch", "main",
                                "--event", "push", "--limit", "30",
                                "--json", "databaseId,headSha,conclusion,createdAt,url"))
    except subprocess.CalledProcessError:
        return dict(runs=[], latest=None)
    runs = [dict(sha=r["headSha"][:7], conclusion=r["conclusion"], date=r["createdAt"][:10], url=r["url"])
            for r in listed]
    latest, tries = None, 0
    for i, r in enumerate(listed):
        if not r["conclusion"]:
            continue  # still running
        if tries == INFRA_TRIES:
            break
        tries += 1
        summary = infra_summary(r["databaseId"])
        if summary is not None:
            latest = dict(runs[i], summary=summary)
            break
    return dict(runs=runs, latest=latest)


# The "How this works" panel follows one real promise, picked by how_excerpts, through its day's
# files and these.
HOW_TEMPLATE = "specs/_template.md"
HOW_REPLAY = "docs/dashboard/replay-history.json"
HOW_PLAN = "plan.md"
HOW_PLAN_PARTS = ("Short answer", "Who does what", "When the driver parks", "Phases", "Stopping points")
# A promise is followed only if every one of these is on record: its track, PR, seen-red line and
# planted bugs among them. Its re-check is not: the newest day has none until the replay reaches it.
HOW_NEEDED = ("crumbs", "day_goal", "day_out_of_scope", "day_tracks", "day_criteria", "claim", "red_today", "test",
              "evidence", "seen_red", "tick", "bugs", "plan_phase")
HOW_NO_PROMISE = "every finished promise is missing a step of its record"


def how_specs(days):
    """The finished days' spec files, newest day first: what the panel may pick a promise from."""
    return [d["file"] for d in sorted(days, key=lambda d: d["day"], reverse=True) if d["status"] in FINISHED]


def how_excerpts(read, specs):
    """The panel's excerpts for the first promise in `specs` (newest day first) tagged new, ticked and
    on record at every step, under "promise" {id, day, spec, breaks}. Each is {source, text} from the
    real files through `read(path)` ("" for no file), or {source, missing: why}: a file or passage that
    has gone shows as gone, never filled in. A file every promise shares going does not end the pick."""
    read = functools.cache(read)
    for path in specs:
        day = int(re.search(r"day-(\d+)", path).group(1))
        for cid in re.findall(r"^- \[x\] (C\d+\.\d+) \*\*new\*\*", read(path), re.M):
            promise = dict(id=cid, day=day, spec=path, breaks=f"specs/breaks/day-{day:02d}.json")
            got = how_excerpts_of(read, promise)
            if all("text" in got[k] for k in HOW_NEEDED if k != "plan_phase" or read(HOW_PLAN)):
                return dict(got, promise=dict(source=path, text=promise))
    return dict(how_excerpts_of(read, None), promise=dict(source="specs/", missing=HOW_NO_PROMISE))


def how_excerpts_of(read, promise):
    """The excerpts for one promise, or with None only those every promise shares."""
    cid = promise["id"] if promise else ""
    spec_path, breaks_path = (promise["spec"], promise["breaks"]) if promise else ("specs/", "specs/breaks/")
    files = {p: read(p) for p in (HOW_TEMPLATE, HOW_REPLAY, HOW_PLAN) + ((spec_path, breaks_path) if promise else ())}
    spec, template, plan = files.get(spec_path, ""), files[HOW_TEMPLATE], files[HOW_PLAN]

    def flat(text):
        return re.sub(r"\s+", " ", text).strip()

    def passage(text, pattern):
        m = re.search(pattern, text, re.M | re.S)
        return m.group(1).rstrip() if m else None

    def section(heading):
        return passage(spec, rf"^## {heading}\n(.*?)(?=^## |\Z)")

    block = passage(spec, rf"^(- \[[ x]\] {re.escape(cid)} .*?)(?=^- \[|^## |\Z)")

    def field(pattern):
        return flat(passage(block, pattern))

    def evidence():
        return field(r"^\s*Evidence: (.*?)(?=^\s*seen red|^\s*broken:|\Z)")

    def crumbs():
        track = passage(section("Tracks"), rf"^\| (\w\d?) \|[^\n]*{re.escape(cid)}\b")
        pr = passage(evidence(), r"\(#(\d+)\)")
        phase = passage(spec, r"\*\*Phase:\*\* (\d+)")
        return track and pr and phase and [HOW_PLAN, f"Phase {phase}", f"Day {promise['day']}", f"Track {track} (PR #{pr})", f"Promise {cid}"]

    def criteria_count():
        day = cid.split(".")[0]
        count = len(re.findall(rf"^- \[[ x]\] {day}\.\d+ ", spec, re.M))
        return f"{count} on this day" if count else None

    def tracks():
        letters = re.findall(r"^\| (\w\d?) \|", section("Tracks"), re.M)
        return "Tracks " + ", ".join(letters) if letters else None

    def bugs():
        manifest = json.loads(files[breaks_path])
        out = []
        for what, said in re.findall(r"broken: (.+?) → (.+?) \(#\d+\)", block):
            entry = next(b for b in manifest if b["what"] == what)
            out.append(dict(what=what, file=entry["file"], find=entry["find"], replace=entry["replace"], reported=said))
        return out

    def recheck():
        rows = [r for r in json.loads(files[HOW_REPLAY])["rows"] if r["criterion"] == cid]
        if promise and not rows:
            return dict(pr=None, checks=[])  # read, and none on record: not the same as a file gone
        newest = max(r["n"] for r in rows)
        rows = [r for r in rows if r["n"] == newest]
        return dict(pr=rows[0].get("pr"), checks=[dict(check=r["check"], state=replay_row_state(r)) for r in rows])

    def plan_parts():
        headings = re.findall(r"^## (.+)$", plan, re.M)
        return list(HOW_PLAN_PARTS) if all(p in headings for p in HOW_PLAN_PARTS) else None

    def plan_phase():
        phase = passage(spec, r"\*\*Phase:\*\* (\d+)")
        heading = passage(plan, rf"^(### Phase {phase}\b.*?)(?=^- Day )")
        scheduled = passage(plan, rf"^(- Day {promise['day']}:.*?)(?=^\S|\Z)")
        return heading and scheduled and f"{heading}\n{scheduled}"

    wanted = dict(
        crumbs=(spec_path, crumbs),
        day_goal=(spec_path, lambda: flat(section("Goal"))),
        day_out_of_scope=(spec_path, lambda: flat(passage(section("Out of scope"), r"^- (.*?)(?=^- |\Z)"))),
        day_tracks=(spec_path, tracks),
        day_criteria=(spec_path, criteria_count),
        claim=(spec_path, lambda: field(r"\*\*(?:new|hold)\*\* — (.*?)^\s*Red today:")),
        red_today=(spec_path, lambda: field(r"^\s*Red today: (.*?)^\s*Test:")),
        test=(spec_path, lambda: field(r"^\s*Test: (.*?)^\s*Evidence:")),
        evidence=(spec_path, evidence),
        seen_red=(spec_path, lambda: field(r"^\s*(seen red\b.*?)$")),
        tick=(spec_path, lambda: passage(block, r"^(- \[[ x]\] \S+ \*\*\w+\*\*)")),
        form=(HOW_TEMPLATE, lambda: passage(template, r"^(- \[ \] CNN\.1 .*?)(?=^- \[ \] CNN\.2)")),
        template_parts=(HOW_TEMPLATE, lambda: re.findall(r"^## (.+)$", template, re.M)),
        bugs=(breaks_path, bugs),
        recheck=(HOW_REPLAY, recheck),
        plan_phase=(HOW_PLAN, plan_phase),
        plan_parts=(HOW_PLAN, plan_parts),
    )
    out = {}
    for key, (source, get) in wanted.items():
        try:
            value = get()
        except (ValueError, KeyError, TypeError, IndexError, AttributeError, StopIteration):
            value = None
        why = (HOW_NO_PROMISE if not promise and key in HOW_NEEDED + ("recheck",) else
               "the file is missing or empty" if not files[source] else "the passage is no longer there")
        out[key] = dict(source=source, text=value) if value else dict(source=source, missing=why)
    return out


def fill(page, data, name):
    # PR titles and spec text are written by anyone: no "<" may reach the HTML parser from the data
    # line. "</script>" would end it early; "<!--" then "<script" (a spec quoting HTML, Day 12) keeps
    # the real end tag from closing it, and the page never ran. JSON reads "<" back as "<".
    data = data.replace("<", "\\u003c")
    page, n = re.subn(r"^window\.SPEC_DRIFT = .*;$", lambda _: f"window.SPEC_DRIFT = {data};", page, flags=re.M)
    if n != 1:
        raise SystemExit(f"{name}: expected one window.SPEC_DRIFT line, found {n}")
    return page


def build(data):
    """docs/dashboard/ as a single page: the stylesheet and script inlined, the data filled in."""
    def read(name):
        with open(os.path.join(PAGE, name), encoding="utf-8") as f:
            return f.read()
    page = read("index.html")
    for tag, name, wrap in (('<link rel="stylesheet" href="dashboard.css">', "dashboard.css", "style"),
                            ('<script src="dashboard.js"></script>', "dashboard.js", "script")):
        if page.count(tag) != 1:
            raise SystemExit(f"index.html: expected one {tag}")
        page = page.replace(tag, f"<{wrap}>\n{read(name)}</{wrap}>")
    return fill(page, data, "index.html")


def page_data(real, spec_days):
    """What --build writes: the real data, or with no day specs yet, demo-data.py's example data marked
    "demo": true, which the page shows under a banner. --out never uses this."""
    if spec_days:
        return real
    spec = importlib.util.spec_from_file_location("demo_data", os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo-data.py"))
    demo_data = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo_data)
    return dict(demo_data.demo(), demo=True)
