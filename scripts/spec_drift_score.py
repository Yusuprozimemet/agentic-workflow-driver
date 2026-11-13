"""spec-drift.py's quality score: one number out of 100 for the whole project, each Day and each ability.

The recipe, decided by the maintainer on 2026-11-13 and kept here so the page only draws it:

- Each count is a share, n of m, read from data the page already draws (no reader's opinion, no weights).
- A part is the plain average of its counts: on the plan, spec and code agree, proven, mistakes caught,
  within the yardsticks. A count with nothing to count (m = 0) is left out; a part with no count is left out.
- The score is the geometric mean of the parts, so one weak part pulls it down more than an average would.
- A defect found at the close, in review, by the dashboard or in the evidence replay counts as caught late:
  the code had already merged.
- Cost and replies per merged pull request score yardstick / spent for each Day, at most 100, averaged.
- Only finished Days count (done, closed or cut): a Day in progress has no score yet.
- An ability has three parts: on the plan, proven, and its pull requests' checks. Defects and costs belong
  to a Day, not an ability.
"""

import math
import re

LATE = re.compile(r"^(close|dashboard|review|evidence replay|Day \d+ review)$")
HOLDS = ("holds", "holds, never broken")
FINISHED = ("done", "closed", "cut")
# Each part's key, name and the graph that explains it (the page links the part to it).
PARTS = (("plan", "On the plan", "g12"), ("agree", "Spec and code agree", "g6"), ("proof", "Proven", "g4"),
         ("check", "Mistakes caught", "g7"), ("cost", "Within the yardsticks", "g2"))
YARDSTICKS = (("cost", "Cost of a merged pull request"), ("replies", "Replies for a merged pull request"))


def count(name, n, m, note=""):
    return dict(name=name, n=n, m=m, pct=round(100.0 * n / m, 1), note=note) if m else None


def against(name, spent, base):
    """Yardstick / spent for each Day that measured it, at most 1, averaged: a count with no n of m."""
    spent = [v for v in spent if v]
    if not spent or not base:
        return None
    pct = sum(min(1.0, base / v) for v in spent) / len(spent) * 100
    return dict(name=name, n=None, m=None, pct=round(pct, 1),
                note=f"{sum(spent) / len(spent):g} spent against a yardstick of {base:g}"
                     + (f", mean of {len(spent)} Days" if len(spent) > 1 else ""))


def combine(parts):
    """The parts that have a count, each the average of its counts, and their geometric mean; None with none."""
    out = []
    for key, name, graph, counts in parts:
        counts = [c for c in counts if c]
        if counts:
            out.append(dict(key=key, name=name, graph=graph, counts=counts,
                            pct=round(sum(c["pct"] for c in counts) / len(counts), 1)))
    if not out:
        return None
    score = math.exp(sum(math.log(max(p["pct"], 0.01)) for p in out) / len(out))
    return dict(score=round(score, 1), low=min(out, key=lambda p: p["pct"])["key"], parts=out)


class Inputs:
    """What the recipe reads from spec-drift's data, indexed once."""

    def __init__(self, data):
        self.data = data
        # Only finished Days: a Day in progress has criteria not yet proven, and would score as if they failed.
        self.days = sorted(d["day"] for d in data.get("days") or [] if d.get("status") in FINISHED)
        self.index = [c for c in data.get("criteria_index") or [] if c.get("day") in self.days]
        last = {}
        for c in (data.get("replay") or {}).get("cells") or []:
            if c.get("criterion") not in last or c.get("n", 0) >= last[c["criterion"]].get("n", 0):
                last[c.get("criterion")] = c
        self.state = {k: v.get("state") for k, v in last.items()}
        plan = data.get("plan") or {}
        self.links = plan.get("links") or {}
        self.commitments = plan.get("commitments") or []
        self.repeats = {r.get("id") for r in (data.get("defect_recurrence") or {}).get("recurrences") or []}
        rows = (data.get("yardsticks") or {}).get("rows") or []
        self.yard = {r["key"]: r for r in rows if r.get("key") in dict(YARDSTICKS)}
        self.closes = {r["day"]: r for r in data.get("rows") or [] if r.get("day") and r.get("kind") == "close"}

    def on_plan(self, crit):
        """Criteria that name a commitment, or guard what exists (a `hold` with Plan: none), of those with a line."""
        lined = [c for c in crit if c["id"] in self.links]
        return count("Criteria that name a commitment, or guard what exists", sum(
            1 for c in lined if self.links[c["id"]] or c.get("tag") == "hold"), len(lined),
            "the rest are new work with Plan: none")

    def proof(self, crit):
        ids = [c["id"] for c in crit]
        return [count("Still holds at the last re-check", sum(self.state.get(i) in HOLDS for i in ids), len(ids)),
                count("Test seen to fail when the code is broken on purpose",
                      sum(self.state.get(i) == "holds" for i in ids), len(ids)),
                count("Test seen red before the code was written",
                      sum(1 for c in crit if (c.get("seen_red") or {}).get("state")), len(ids))]

    def checks(self, prs):
        return count("Pull requests whose checks passed on every push", sum(not v.get("failed") for v in prs), len(prs))


def scope(I, days):
    """The score of some Days: all of them for the whole project, one for a Day."""
    ds, whole = set(days), len(set(days)) == len(I.days)
    crit = [c for c in I.index if c.get("day") in ds]
    defects = [x for d in I.data.get("days") or [] if d["day"] in ds for x in d.get("defects") or []]
    prs = [v for v in I.data.get("verification") or [] if v.get("day") in ds]
    relabel = [d["relabel"] for d in I.data.get("days") or [] if d["day"] in ds and d.get("relabel")]
    handed = [x for x in (I.data.get("look_ahead") or {}).get("hand_offs") or []
              if x.get("how") in ("picked", "lapsed") and any(f"Day {n:02d}" in (x.get("source") or "") for n in ds)]
    plan = [I.on_plan(crit)]
    if whole and I.commitments:
        closed = max(I.days)
        named = {p for ids in I.links.values() for p in ids}
        due = [p["id"] for p in I.commitments if not p.get("rule") and p.get("owner_day") is not None
               and p["owner_day"] <= closed]
        plan.insert(0, count("Commitments due by a closed Day that a criterion names",
                             sum(p in named for p in due), len(due)))
    row = (I.data.get("rows") or [{}])[-1] if whole else I.closes.get(max(ds))
    agree = row and isinstance(row.get("spec_names"), int) and count(
        "Names the specs give that are in the code", row.get("names_in_code") or 0, row["spec_names"])
    yard = [against(name, [v.get("value") for v in (I.yard.get(key) or {}).get("values") or [] if v.get("day") in ds],
                    (I.yard.get(key) or {}).get("baseline")) for key, name in YARDSTICKS]
    graph = dict((k, g) for k, _, g in PARTS)
    return combine([
        ("plan", "On the plan", graph["plan"], plan),
        ("agree", "Spec and code agree", graph["agree"], [agree or None]),
        ("proof", "Proven", graph["proof"], I.proof(crit)),
        ("check", "Mistakes caught", graph["check"], [
            count("Defects found before the close", sum(not LATE.match(x.get("found") or "") for x in defects),
                  len(defects)),
            count("Defects that do not repeat an earlier one", sum(x.get("id") not in I.repeats for x in defects),
                  len(defects)),
            I.checks(prs),
            count("Hand-offs to a later Day that were picked up", sum(x["how"] == "picked" for x in handed), len(handed),
                  "hand-offs since closed; open ones left out"),
            count("Defect tags a blind reader gave the same", sum(v[0] for r in relabel for v in r.values()),
                  sum(v[1] for r in relabel for v in r.values()))]),
        ("cost", "Within the yardsticks", graph["cost"], yard),
    ])


def ability(I, key):
    crit = [c for c in I.index if key in (c.get("abilities") or [])]
    stories = (I.data.get("user_stories") or {}).get("stories") or []
    numbers = {int(s["number"]) for s in stories if s.get("ability") == key}
    prs = [v for v in I.data.get("verification") or [] if v.get("number") in numbers and v.get("day") in I.days]
    return combine([("plan", "On the plan", "g12", [I.on_plan(crit)]),
                    ("proof", "Proven", "g5", I.proof(crit)),
                    ("check", "Checks passed", "g7", [I.checks(prs)])])


def quality_score(data):
    """The score of the finished Days together, of each and of each ability; None before a Day finishes."""
    I = Inputs(data)
    if not I.days:
        return None
    abilities = (data.get("user_stories") or {}).get("abilities") or []
    return dict(all=scope(I, I.days), days={str(d): scope(I, [d]) for d in I.days},
                abilities={a["key"]: ability(I, a["key"]) for a in abilities if a.get("key")})
