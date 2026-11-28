"""Helpers more than one view uses: the replay's groups, a Day's state, rounding, plain words, times.
spec_drift_views.py imports it for spec-drift.py, demo-data.py and the tests."""

import datetime
import re


# Each replay state, as the group a reader sees it in: dashboard-reconcile.py's recount keeps the same groups, and
# tests/test_dashboard_views.py holds the two to each other.
REPLAY_GROUP = {
    "code broken": "broken",
    "test weakened": "repair",
    "break no longer applies": "repair",
    "not runnable": "skipped",
    "not applicable on this platform": "skipped",
    "live only": "skipped",
    "holds, never broken": "unproven",
    "holds": "proven",
    "not yet in force": None,
}


# A Day the page treats as over: its criteria are no longer being built.
FINISHED = ("done", "closed", "cut")


FAILED_GROUPS = ("broken", "repair")


def _cells(replay):
    """Each criterion's replay cells, oldest first."""
    out = {}
    for cell in sorted((replay or {}).get("cells") or [], key=lambda c: c.get("n", 0)):
        out.setdefault(cell.get("criterion"), []).append(cell)
    return out


def _quote(c, text=""):
    """One quote of the plan as the gene draws it: the criterion that makes it, and the words it quotes."""
    return dict(id=c["id"], day=c.get("day"), tag=c.get("tag"), state=c.get("state"), back=bool(c.get("back")),
                gone=bool(c.get("replaced_by")), quote=text)


def _finished(day):
    return bool(day) and day.get("status") in FINISHED


def _round(x):
    """As the page's Math.round: a half goes up."""
    return None if x is None else int(x + 0.5)


def _plain(s):
    return str(s or "").replace("`", "")


def _placed(d):
    """The Day each merge belongs to, as the page places it (dashboard.js, PLACED): the Day its branch names; for a
    merge no Day owns, the furthest Day begun when it merged, and whether that Day was open or closed by then. A code
    merge or a close no Day owns is counted as other work."""
    order = d.get("order") or []
    rank = lambda day: order.index(day) if day in order else day  # noqa: E731
    top, shut, out = None, set(), []
    for r in d.get("rows") or []:
        own = r.get("own_day") if r.get("pr") and r.get("own_day") is not None else None
        if own is not None and (top is None or rank(own) > rank(top)):
            top = own
        kind = r.get("kind") if r.get("kind") in ("origin", "spec", "code", "close", "other") else "other"
        if r.get("pr") and own is None and kind in ("code", "close"):
            kind = "other"
        if not r.get("pr"):
            whose = "before Day 1"
        elif own is not None:
            whose = f"Day {own}"
        elif top is None:
            whose = "outside any Day, merged before Day 1 began"
        else:
            whose = f"outside any Day, merged {f'after Day {top} closed' if top in shut else f'while Day {top} was open'}"
        if own is not None and r.get("kind") == "close":
            shut.add(own)
        # `at` and `area` as the page's PLACED has them: the Day a merge is placed at (its own, or the furthest Day
        # begun; None before Day 1, the page's 0), and whether it is a pull request no Day owns.
        out.append(dict(own=own, kind=kind, whose=whose, at=own if own is not None else top,
                        area=bool(r.get("pr")) and own is None))
    return out


def _stamp(d):
    now = d.get("now") or {}
    return dict(head=(now.get("head") or "")[:7], last_pr=now.get("last_pr"), generated=now.get("generated") or "")


def _order(cid):
    """A criterion's place in the order built: its Day, then its number."""
    return tuple(
        int(x) for x in "".join(ch if ch.isdigit() else " " for ch in str(cid)).split()
    ) or (0,)


def _runs(steps):
    """The run log's steps, read by RUN_USE: a step may be in more than one (a crash that parked)."""
    return dict(
        loop=[s.get("pr") for s in steps if s.get("ended") == "merged" and not s.get("parks")],
        park=[
            dict(pr=s.get("pr"), day=s.get("day"), by=p.get("by"), line=_plain(p.get("line")))
            for s in steps
            for p in s.get("parks") or []
        ],
        stop=[s.get("pr") for s in steps if s.get("ended") == "stopped"],
        recover=[
            dict(
                pr=s.get("pr"),
                crashes=s.get("crashes"),
                sessions=len(s.get("sessions") or []),
                ended=s.get("ended"),
            )
            for s in steps
            if (s.get("crashes") or 0) > 0
        ],
        open=[s.get("pr") for s in steps if s.get("ended") == "open"],
    )


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _offset(stamp):
    """The minutes east of UTC a time is stamped with (graph 10's offsetOf); none or Z is 0."""
    m = re.search(r"(Z|[+-]\d\d:\d\d)$", stamp or "")
    if not m or m.group(1) == "Z":
        return 0
    return (-1 if m.group(1)[0] == "-" else 1) * (int(m.group(1)[1:3]) * 60 + int(m.group(1)[4:6]))


def _ms(stamp):
    """Milliseconds since the epoch, as Date.parse gives them; a time with no offset is taken as UTC."""
    t = datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return t.timestamp() * 1000


def _lower_median(values):
    v = sorted(values)
    return v[(len(v) - 1) // 2] if v else None


def _n(k, one, many=None):
    return f"{k} {one if k == 1 else many or one + 's'}"


def _list(items):
    items = list(items)
    return " and ".join(items) if len(items) < 3 else f"{', '.join(items[:-1])} and {items[-1]}"
