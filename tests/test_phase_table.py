"""The phase-end table (pipeline plan step 5): per phase, and per Day inside one, the Defect lines'
counts, the gates that found nothing, the cost and the hooks' refusals, from what spec-drift.py's
--out JSON already holds. "Escapes" keeps the README's rule (made: another Day); "after the close"
is a separate count (found: evidence replay, dashboard or Day NN review, made: not none), with its
unsplit part beside it, since before Day 12 evidence replay named the rehearsal too."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import spec_drift_metrics as metrics
import spec_drift_specs as specs


def defects(day, rows):
    text = "".join(
        f"- **Defect** D{day:02d}.{n} — found: {f} · cause: spec · made: {m} · x.\n"
        for n, (f, m) in enumerate(rows, 1)
    )
    return specs.defect_lines(text, day)


DAYS = [
    {
        "day": 1,
        "phase": 0,
        "criteria": {"total": 2},
        "defects": defects(
            1, [("auditor", "Day 01"), ("evidence replay", "Day 01"), ("Day 01 review", "none")]
        ),
    },
    {"day": 2, "phase": 0, "criteria": {"total": 3}, "defects": []},
    {
        "day": 3,
        "phase": 1,
        "criteria": {"total": 4},
        "relabel": {"stage": [5, 6], "cause": [4, 6], "made": [6, 6]},
        "defects": defects(
            3,
            [
                ("auditor", "Day 03"),
                ("Track A", "Day 01"),
                ("dashboard", "Day 02"),
                ("break on purpose", "Day 03"),
            ],
        ),
    },
    {
        "day": 12,
        "phase": 2,
        "criteria": {"total": 0},
        "defects": defects(12, [("rehearsal", "Day 12"), ("evidence replay", "Day 12")]),
    },
]
PRS = [
    {"number": 1, "day": 1, "opened": "2026-11-01T09:00:00Z"},
    {"number": 2, "day": 3, "opened": "2026-11-03T09:00:00Z"},
    {"number": 3, "day": None, "opened": "2026-10-20T09:00:00Z"},
    {"number": 4, "day": 12, "opened": "2026-11-10T09:00:00Z"},
]
TOKENS = [
    {"date": "2026-11-01", "day": 1, "cost": 1.0},
    {"date": "2026-11-02", "day": None, "cost": 2.0},
    {"date": "2026-11-02", "day": 2, "cost": 0.5},
    {"date": "2026-11-03", "day": 3, "cost": 4.0},
    {"date": "2026-11-05", "day": None, "cost": 8.0},
    {"date": "2026-10-30", "day": None, "cost": 16.0},
    {"date": "2026-11-11", "day": None, "cost": 0.5},
    {"date": "2026-11-11", "day": 12, "cost": 0.25},
]
REFUSALS = [
    {"date": "2026-11-02", "guard": "read-guard", "refused": 3},
    {"date": "2026-11-04", "guard": "read-guard", "refused": 1},
    {"date": "2026-11-04", "guard": "step-guard", "refused": 2},
    {"date": "2026-11-12", "guard": "auditor-guard", "refused": 5},
]

TABLE = """\
| | Phase 0 (Day 1) | Phase 1 (Day 3) | Phase 2 (Day 12) |
|---|---|---|---|
| Criteria | 2 | 4 | 0 |
| Defects (per criterion) | 3 (1.5) | 4 (1.0) | 2 (-) |
| Caught late | 2 | 3 | 2 |
| Escapes (made on another Day) | 0 | 2 | 0 |
| Found after the close (unsplit) | 1 (1) | 1 (0) | 1 (0) |
| Found by auditor | 1 | 1 | 0 |
| Found by break on purpose | 0 | 1 | 0 |
| Found by work | 0 | 1 | 0 |
| Found by rehearsal | 0 | 0 | 1 |
| Found by evidence replay | 0 | 0 | 1 |
| Found by unsplit | 1 | 0 | 0 |
| Found by dashboard | 0 | 1 | 0 |
| Found by Day review | 1 | 0 | 0 |
| Gates that found nothing | seen red, break on purpose, close | seen red, close, evidence replay | auditor, seen red, break on purpose, close |
| Cost, its Days | $1.50 | $4.00 | $0.25 |
| Cost, the rest of its dates | $2.00 | $8.00 | $0.50 |
| Refusals in its dates | read-guard 3 | read-guard 1, step-guard 2 | auditor-guard 5 |

Rater agreement, all Days: stage 5 of 6, cause 4 of 6, made 6 of 6
Found after the close: evidence replay, dashboard or Day NN review, made: not none. Before Day 12 evidence replay named the rehearsal too: its unsplit part is an upper bound.
"""


class PhaseTableTest(unittest.TestCase):
    def test_rows_per_phase_and_per_day(self):
        t = metrics.phase_table(DAYS, PRS, TOKENS, REFUSALS)
        self.assertEqual(
            [
                (
                    r["phase"],
                    r["days"],
                    r["criteria"],
                    r["defects"],
                    r["per_criterion"],
                    r["late"],
                    r["escapes"],
                    r["after_close"],
                    r["after_close_unsplit"],
                    r["silent"],
                    r["cost_days"],
                    r["cost_between"],
                    r["refusals"],
                )
                for r in t["phases"]
            ],
            [
                (
                    0,
                    [1],
                    2,
                    3,
                    1.5,
                    2,
                    0,
                    1,
                    1,
                    ["seen red", "break on purpose", "close"],
                    1.5,
                    2.0,
                    {"read-guard": 3},
                ),
                (
                    1,
                    [3],
                    4,
                    4,
                    1.0,
                    3,
                    2,
                    1,
                    0,
                    ["seen red", "close", "evidence replay"],
                    4.0,
                    8.0,
                    {"read-guard": 1, "step-guard": 2},
                ),
                (
                    2,
                    [12],
                    0,
                    2,
                    None,
                    2,
                    0,
                    1,
                    0,
                    ["auditor", "seen red", "break on purpose", "close"],
                    0.25,
                    0.5,
                    {"auditor-guard": 5},
                ),
            ],
        )
        self.assertEqual(
            [
                (
                    r["day"],
                    r["phase"],
                    r["defects"],
                    r["stages"],
                    r["cost_days"],
                    r["cost_between"],
                    r["refusals"],
                )
                for r in t["days"]
            ],
            [
                (1, 0, 3, {"auditor": 1, "unsplit": 1, "Day review": 1}, 1.0, None, None),
                (
                    3,
                    1,
                    4,
                    {"auditor": 1, "break on purpose": 1, "work": 1, "dashboard": 1},
                    4.0,
                    None,
                    None,
                ),
                (12, 2, 2, {"rehearsal": 1, "evidence replay": 1}, 0.25, None, None),
            ],
        )

    def run_script(self, *args):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spec-drift.json"
            path.write_bytes(
                json.dumps(
                    {"days": DAYS, "clock": {"prs": PRS}, "tokens": TOKENS, "refusals": REFUSALS}
                ).encode("utf-8")
            )
            run = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "phase-table.py"), str(path), *args],
                check=False,
                capture_output=True,
            )
        self.assertEqual(run.returncode, 0, run.stderr.decode("utf-8", "replace"))
        return run.stdout.decode("ascii").replace("\r\n", "\n")

    def test_the_script_prints_one_column_per_phase(self):
        self.assertEqual(self.run_script(), TABLE)

    def test_one_phase_prints_its_days_then_the_phase(self):
        out = self.run_script("--phase", "1").splitlines()
        self.assertEqual(out[0], "| | Day 3 | Phase 1 (Day 3) |")
        self.assertIn("| Cost, the rest of its dates | - | $8.00 |", out)
        self.assertIn("| Refusals in its dates | - | read-guard 1, step-guard 2 |", out)
        self.assertIn("| Found by dashboard | 1 | 1 |", out)
        self.assertNotIn("| Found by rehearsal | 0 | 0 |", out)


if __name__ == "__main__":
    unittest.main()
