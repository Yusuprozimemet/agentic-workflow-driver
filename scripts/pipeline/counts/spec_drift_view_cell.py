"""The cell: what the front page's cell draws beside one Day that the other keys do not hold (`cell`). Each checking
agent's challenge test from its case set, and the check each fix is drawn beside, from a table chosen by hand.
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

import json

# The case sets the cell draws a challenge test for, by the station its agent stands at, in the cell's order
CELL_AGENTS = (("sa", "spec-auditor"), ("chap", "track-reviewer"), ("ci", "reviewer"), ("rater", "defect-rater"))
# Who found a defect, for the stations whose agent is counted as finding it
CELL_FOUND = dict(sa=("auditor",), chap=("track-reviewer",), ci=("CI", "driver reviewer"))
# The checks a fix can be drawn beside, and the table that places each one
FIX_AT = ("sa", "test", "chap", "ko", "spec", "ci")
FIX_STATIONS = "docs/dashboard/fix-stations.json"


def cell_cards(d, texts):
    """{station: card} from {agent: the text of specs/agent-cases/<agent>.json, or None}. A card is its agent, its
    number of cases and the runs it was counted over (the worst of them is recorded), and what it was counted on:
    the known faults named over all its cases (as spec_drift_metrics.case_counts counts them) at sa and chap; the
    right verdicts over the cases and the faults named over the cases that expect a blocker at ci; the three labels
    at rater, whose totals the case set does not record, beside the real Days' agreement. `found` is the defects of
    the Days that the station's agent is recorded as finding. An agent whose set is missing, is not JSON, or has no
    recorded count is left out."""
    found = [x.get("found") for day in (d.get("one_day") or {}).get("days") or [] for x in day.get("defects") or []]
    out = {}
    for station, agent in CELL_AGENTS:
        try:
            data = json.loads(texts.get(agent) or "null")
        except ValueError:
            continue
        rec = data.get("recorded") if isinstance(data, dict) else None
        if not rec:
            continue
        cases = data.get("cases") or []
        card = dict(agent=agent, cases=len(cases), runs=rec.get("runs"))
        if station in ("sa", "chap"):
            card.update(n=rec.get("named"), of=sum(len(c.get("known") or []) for c in cases))
        elif station == "ci":
            card.update(n=rec.get("verdict"), of=len(cases), named=rec.get("named"),
                        named_of=sum(1 for c in cases if c.get("expect") == "blocker"))
        else:
            card.update(cause=rec.get("cause"), stage=rec.get("stage"), made=rec.get("made"),
                        real=(d.get("defect_counts") or {}).get("rater") or {})
        if station in CELL_FOUND:
            card["found"] = sum(1 for f in found if f in CELL_FOUND[station])
        out[station] = card
    return out


def fix_stations(text, prs):
    """({str(pr): station}, problems) from the table's text and the fixes' numbers: a fix the table places at one of
    FIX_AT stands there; a fix it does not place, an entry that names no fix and a station not in FIX_AT are each
    one problem, and so is a table that cannot be read, which places nothing."""
    try:
        table = (json.loads(text or "null") or {}).get("stations")
        if not isinstance(table, dict):
            raise ValueError
    except (ValueError, AttributeError):
        return {}, [f"{FIX_STATIONS} cannot be read, so the cell draws no fix at a check"]
    stations, problems = {}, []
    for pr in prs:
        at = table.get(str(pr))
        if at is None:
            problems.append(f"fix #{pr} has no station in {FIX_STATIONS}, so the cell draws it at no check")
        elif at not in FIX_AT:
            problems.append(f"{FIX_STATIONS} puts fix #{pr} at {at!r}, which is none of {', '.join(FIX_AT)}")
        else:
            stations[str(pr)] = at
    named = {str(pr) for pr in prs}
    problems += [f"{FIX_STATIONS} places #{k}, which is no fix in specs/fixes.json" for k in table if k not in named]
    return stations, problems


def cell(d, texts, stations_text):
    """The cell's key: the challenge tests (cell_cards), each fix's station (fix_stations, over the fixes the learning
    view counts) with what could not be placed, and the defects on record, which the cell's sentences count against."""
    prs = [f["pr"] for f in (d.get("learning") or {}).get("fixes") or []]
    fix_station, problems = fix_stations(stations_text, prs)
    return dict(cards=cell_cards(d, texts), fix_station=fix_station, problems=problems,
                total=(d.get("defect_recurrence") or {}).get("defects") or 0)
