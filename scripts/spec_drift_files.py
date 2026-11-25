"""The dashboard's file map, "Where does each file belong?": every tracked file as one dot, hung under the
station of the workflow it serves, its area its line count.

A folder places itself and a script is placed by a table, both in docs/dashboard/file-stations.json, which
is read on every build beside the file list: a new file under a placed folder appears by itself, and a file
the table does not place is drawn in the ring "on no station", never dropped. The picture's geometry is
worked out here, so the page only draws: a dot's radius is 0.36 x sqrt(lines), at least 1.8; within a group
the longest file comes first, in rows centred under the group's column.

One thing on the picture is no station: the improve loop, which runs only when the maintainer asks. The table
marks its files' group "loop", and a line goes back from that group's column to the column of every brief that
has known cases (specs/agent-cases/<agent>.json, which names the brief), read from git on every build: a new
case set gets its arrow by itself.
"""

import json
import math
import os
import re

TABLE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "docs", "dashboard", "file-stations.json"
)
TABLE_NAME = "docs/dashboard/file-stations.json"
SCRIPTS = "scripts/"

# Where a group may hang: the seven stations and the five checks between them, by x on the picture.
# `w` is the widest a row of dots may be there; `at` is what a reader is told.
COLUMNS = {
    "s1": dict(x=76, zone="doc", at="station 1, the goal"),
    "plan-auditor": dict(x=159, zone="doc", at="the plan-auditor's check, after station 1"),
    "s2": dict(x=242, zone="doc", at="station 2, a Day's spec"),
    "spec-auditor": dict(x=328, zone="doc", at="the spec-auditor's check, after station 2"),
    "s3": dict(x=414, zone="doc", at="station 3, a promise"),
    "s4": dict(x=552, zone="try", at="station 4, a test that fails first"),
    "implementer": dict(x=640, zone="try", at="the implementer, between stations 4 and 5"),
    "s5": dict(x=728, zone="try", at="station 5, the code, then a planted bug"),
    "ci": dict(x=836, zone="try", at="CI's checks, after station 5", w=88),
    "s6": dict(x=1016, zone="after", at="station 6, the Day closes"),
    "defect-rater": dict(x=1099, zone="after", at="the defect-rater's check, after station 6"),
    "s7": dict(x=1182, zone="after", at="station 7, the re-check"),
}
ZONES = (
    ("doc", "written down first", "in the nucleus"),
    ("try", "tried on the code", "in the cytoplasm"),
    ("after", "checked afterwards", "out of the cell"),
)
KINDS = (
    ("spec", "written text"),
    ("code", "the app's code"),
    ("test", "a test of the app"),
    ("tool", "tooling and docs"),
    ("tooltest", "a test of the tooling"),
)
RING_AT = "on no station"
CASES = "specs/agent-cases/"
UNPLACED = f"Not in the table yet: {TABLE_NAME} names no station for it."

WIDTH, GAP, FIRST_Y, LABEL_PAD, GROUP_GAP, RING_GAP = 92.0, 1.6, 242.0, 6.0, 20.0, 28.0
NUC_TOP, CELL_TOP, VIEW_TOP = 130.0, 112.0, 100.0
LOOP_Y, LOOP_TOP = (
    92.0,
    74.0,
)  # the improve loop's line, over the cell, and where the picture then opens


def radius(lines):
    return max(1.8, 0.36 * math.sqrt(lines))


def fits(pattern, path):
    """A folder ("tests/") takes everything under it; otherwise * is any run of characters inside one name."""
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return re.fullmatch("[^/]*".join(map(re.escape, pattern.split("*"))), path) is not None


def script_names(stem):
    """The names a script may go by in the table: its own, and for a test the script it tests, tried whole
    and then with its last words dropped (test_spec_drift_plan: spec_drift_plan, spec_drift, spec)."""
    yield [stem]
    if stem.startswith("test_"):
        words = stem[5:].split("_")
        for n in range(len(words), 0, -1):
            name = "_".join(words[:n])
            yield [name, name.replace("_", "-")]


def place(path, groups):
    """The index of the group that takes the file, or None: the ring then."""
    for i, g in enumerate(groups):
        if any(fits(p, path) for p in g.get("paths", ())):
            return i
    if path.startswith(SCRIPTS) and "/" not in path[len(SCRIPTS) :]:
        stem = path[len(SCRIPTS) :].rsplit(".", 1)[0]
        for names in script_names(stem):
            for i, g in enumerate(groups):
                if any(fits(p, name) for p in g.get("scripts", ()) for name in names):
                    return i
    return None


def kind_of(path, group):
    name = path.rsplit("/", 1)[-1]
    if path.startswith(SCRIPTS) and name.startswith("test_"):
        return "tooltest"
    return (group or {}).get("kind", "tool")


def rows_of(radii, width):
    """The radii, already longest first, cut into rows no wider than the column."""
    rows, row, used = [], [], 0.0
    for r in radii:
        add = 2 * r + (GAP if row else 0)
        if row and used + add > width:
            rows.append(row)
            row, used, add = [], 0.0, 2 * r
        row.append(r)
        used += add
    return rows + [row] if row else rows


def hang(sizes, x, y, width):
    """Dots in centred rows under a label at y: [(cx, cy, r)] in the order given, and the bottom."""
    dots, top = [], y + LABEL_PAD
    for row in rows_of(sizes, width):
        left = x - (sum(2 * r for r in row) + GAP * (len(row) - 1)) / 2
        for r in row:
            dots.append((left + r, top + row[0], r))
            left += 2 * r + GAP
        top += 2 * row[0] + GAP
    return dots, (top - GAP if dots else y)


def ring(sizes, x, y):
    """Dots on a circle under a label at y, the first at the top: the dots, and the circle (cy, r, bottom)."""
    around = max(14.0, sum(2 * r + GAP for r in sizes) / (2 * math.pi))
    cy = y + 20 + around
    turn = 2 * math.pi / max(1, len(sizes))
    dots = [
        (x + around * math.sin(k * turn), cy - around * math.cos(k * turn), r)
        for k, r in enumerate(sizes)
    ]
    return dots, dict(cy=round(cy, 1), r=round(around + 13, 1), bottom=cy + around + 31)


def load_table(path=TABLE):
    """The table's groups, or a sentence saying why there are none."""
    try:
        with open(path, encoding="utf-8") as f:
            groups = json.load(f)["groups"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        return (
            None,
            f"`{TABLE_NAME}` could not be read ({type(e).__name__}), so no file has a station.",
        )
    bad = sorted({str(g.get("at")) for g in groups if g.get("at") not in COLUMNS})
    if bad:
        return (
            None,
            f"`{TABLE_NAME}` hangs a group at {', '.join(bad)}, which the picture does not have.",
        )
    return groups, None


def tracked(head, run):
    """{path: lines} for every file tracked at head: git's list, and one git grep for the counts. A file with
    no line, or one git calls binary, counts 0 and is still drawn."""
    counts = dict.fromkeys(
        p for p in run("git", "ls-tree", "-r", "--name-only", head).splitlines() if p
    )
    try:
        counted = run("git", "grep", "-c", "-I", "", head)
    except Exception:  # noqa: BLE001  git grep exits 1 when nothing has a line
        counted = ""
    for line in counted.splitlines():
        path, _, n = line.partition(":")[2].rpartition(":")
        if path in counts and n.isdigit():
            counts[path] = int(n)
    return {p: n or 0 for p, n in counts.items()}


def case_briefs(counts, head, run):
    """{agent: its brief} for every case set tracked at head: the brief the set names, .claude/agents/<agent>.md
    when it names none (as scripts/agent-cases.py reads it). A set that cannot be read names no brief."""
    out = {}
    for path in sorted(counts):
        agent = path[len(CASES) : -len(".json")]
        if not (path.startswith(CASES) and path.endswith(".json")) or "/" in agent:
            continue
        try:
            out[agent] = json.loads(run("git", "show", f"{head}:{path}")).get(
                "brief", f".claude/agents/{agent}.md"
            )
        except Exception:  # noqa: BLE001  one torn case set costs its own arrow, not the picture
            continue
    return out


def loop_of(groups, members, briefs, home):
    """The improve loop's line: from the column its files hang at, back to each column where a brief with known
    cases hangs, left to right. None when the table marks no group "loop", it holds no file, or no such brief
    is placed. `home` is {path: the group's index, or None in the ring}."""
    start = next((g for i, g in enumerate(groups) if g.get("loop") and members[i]), None)
    to = {}
    for agent, brief in sorted((briefs or {}).items()):
        if home.get(brief) is not None and not groups[home[brief]].get("ring"):
            to.setdefault(groups[home[brief]]["at"], []).append(agent)
    if not start or not to:
        return None
    return dict(
        label=start["label"],
        x=COLUMNS[start["at"]]["x"],
        y=LOOP_Y,
        at=COLUMNS[start["at"]]["at"],
        to=[
            dict(col=k, x=COLUMNS[k]["x"], at=COLUMNS[k]["at"], agents=to[k])
            for k in COLUMNS
            if k in to
        ],
    )


def file_map(counts, groups, head=None, why=None, briefs=None):
    """The page's model: every file once, in `files`, and each group's dots where they are drawn; `briefs` is
    {agent: brief} for the agents with known cases, which the improve loop's line lands on."""
    if groups is None or not counts:
        return dict(
            empty=why or "The file list could not be read from git, so there is no file to draw."
        )
    groups = [dict(g) for g in groups]
    if not any(g.get("ring") for g in groups):
        groups.append(
            dict(at="defect-rater", ring=True, label="unplaced", kind="tool", what=UNPLACED)
        )
    ring_i = next(i for i, g in enumerate(groups) if g.get("ring"))
    kinds = [k for k, _ in KINDS]
    files, members, home = [], [[] for _ in groups], {}
    for path in sorted(counts):
        i = home[path] = place(path, groups)
        lost = i is None
        kind = kind_of(path, None if lost else groups[i])
        members[ring_i if lost else i].append(len(files))
        files.append([path, counts[path], kinds.index(kind), ring_i if lost else i, int(lost)])
    out, bottoms, plasmid = [], dict.fromkeys(COLUMNS, None), None
    order = sorted(
        range(len(groups)), key=lambda i: (bool(groups[i].get("ring")), i)
    )  # a ring hangs under its column
    drawn = {}
    for i in order:
        g, col = groups[i], COLUMNS[groups[i]["at"]]
        if not members[i]:
            continue
        mine = sorted(members[i], key=lambda j: (-files[j][1], files[j][0]))
        sizes, below = [radius(files[j][1]) for j in mine], bottoms[g["at"]]
        if g.get("ring"):
            y = FIRST_Y if below is None else below + RING_GAP
            dots, plasmid = ring(sizes, col["x"], y)
            plasmid.update(x=col["x"])
            bottom = plasmid.pop("bottom")
        else:
            y = FIRST_Y if below is None else below + GROUP_GAP
            dots, bottom = hang(sizes, col["x"], y, col.get("w", WIDTH))
        bottoms[g["at"]] = bottom
        drawn[i] = dict(
            label=g["label"],
            what=g["what"],
            at=RING_AT if g.get("ring") else col["at"],
            zone=col["zone"],
            ring=bool(g.get("ring")),
            x=col["x"],
            y=round(y, 1),
            files=len(mine),
            folder=g["label"]
            in g.get("paths", ()),  # a folder that places itself, under its own name
            lines=sum(files[j][1] for j in mine),
            dots=[
                [j, round(cx, 1), round(cy, 1), round(r, 1)] for j, (cx, cy, r) in zip(mine, dots)
            ],
        )
    index = {i: n for n, i in enumerate(sorted(drawn))}
    out = [drawn[i] for i in sorted(drawn)]
    for f in files:
        f[3] = index[f[3]]

    def lowest(zone):
        return max(
            [b for k, b in bottoms.items() if b is not None and COLUMNS[k]["zone"] == zone],
            default=FIRST_Y,
        )

    loop = loop_of(groups, members, briefs, home)
    top = LOOP_TOP if loop else VIEW_TOP
    nuc = lowest("doc") + 17
    cyto = max(lowest("try"), nuc + 17 + 4) + 19
    after = lowest("after") + 22
    geo = dict(
        nuc_label=round(nuc, 1),
        nuc_h=round(nuc + 17 - NUC_TOP, 1),
        cyto_label=round(cyto, 1),
        cell_h=round(cyto + 17 - CELL_TOP, 1),
        after_label=round(after, 1),
        top=top,
        height=round(max(after + 18.3, cyto + 17 + 12) - top, 1),
        plasmid=plasmid,
    )
    zones = [
        dict(
            key=k,
            name=name,
            where=where,
            files=sum(g["files"] for g in out if g["zone"] == k),
            lines=sum(g["lines"] for g in out if g["zone"] == k),
        )
        for k, name, where in ZONES
    ]
    return dict(
        head=head,
        files=files,
        lines=sum(counts.values()),
        groups=out,
        geo=geo,
        zones=zones,
        loop=loop,
        kinds=[
            dict(key=k, name=name, n=sum(f[2] == n for f in files))
            for n, (k, name) in enumerate(KINDS)
        ],
        unplaced=[f[0] for f in files if f[4]],
        unplaced_what=UNPLACED,
        table=TABLE_NAME,
        scripts=sum(
            f[0].startswith(SCRIPTS) and not f[0].rsplit("/", 1)[-1].startswith("test_")
            for f in files
        ),
    )


def build_file_map(head, run):
    """What spec-drift.py puts in the page's data."""
    groups, why = load_table()
    try:
        counts = tracked(head, run)
    except Exception as e:  # noqa: BLE001  the page says so; the rest of the build goes on
        return dict(
            empty=f"The file list could not be read from git ({type(e).__name__}), so there is no file to draw."
        )
    return file_map(counts, groups, head, why, case_briefs(counts, head, run))
