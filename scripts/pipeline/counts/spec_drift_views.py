"""spec-drift.py's newer views: one function per section of the page, each counted here and written under its own
key of spec-drift.json, so that `docs/dashboard/dashboard.js` only lays them out and counts nothing of its own.
`scripts/demo-data.py` calls the same functions on its made-up data.

The page used to work out each criterion's state in the browser (`promises()` in dashboard.js); it is worked
out here now, in `criterion_states`, and the browser reads it.

A criterion is *in force* while no later criterion's `Replaces:` line names it (its `replaced_by` is empty):
`scripts/plan-links.py`, graph 12 and the gene count the same set.

The views live in one module each beside this one (spec_drift_view_<key>.py, the key of spec-drift.json each
writes), with the helpers more than one uses in spec_drift_view_common.py. This module only imports them,
so that spec-drift.py, demo-data.py and the tests keep importing every view from one name.
"""

from spec_drift_view_common import (  # noqa: F401
    REPLAY_GROUP, FINISHED, FAILED_GROUPS, _cells, _quote, _finished, _round, _plain, _placed, _stamp, _order,
    _runs, _MONTHS, _offset, _ms, _lower_median, _n, _list,
)
from spec_drift_view_criterion_states import (  # noqa: F401
    _stops, criterion_states,
)
from spec_drift_view_gene import (  # noqa: F401
    GENE_CLASSES, _class, gene,
)
from spec_drift_view_merge_graph import (  # noqa: F401
    MERGE_ST, HELD, _day_name, _merge_events, _flap, _merge_view, _merge_crit, uncited_merges, merge_graph,
)
from spec_drift_view_where_ring import (  # noqa: F401
    where_ring,
)
from spec_drift_view_reading import (  # noqa: F401
    reading,
)
from spec_drift_view_gel import (  # noqa: F401
    LOWER_BETTER, _parks_from_runs, _slope, gel,
)
from spec_drift_view_protein import (  # noqa: F401
    RECHECKED, RUN_USE, _tally, _per_day, protein,
)
from spec_drift_view_proofreading import (  # noqa: F401
    PRF_FROM, PRF_GATES, PRF_LAYERS, PRF_CAUSES, PRF_GUARDS, _tag, gate_of, _when, _prf_missing, _prf_defects,
    _prf_late, _prf_hooks, _prf_ci, _prf_reader, proofreading,
)
from spec_drift_view_budget import (  # noqa: F401
    BUDGET_UNIT, BUDGET_OFF, BUDGET_KINDS, BUDGET_WHO, BUDGET_PARTS, _BUDGET_PART, _TOKEN_USAGE, _token_usage, _who,
    _part, _priced, _lr, _budget_missing, _budget_col, _guard_order, budget,
)
from spec_drift_view_rings import (  # noqa: F401
    RING_KINDS, _share, _ring, rings,
)
from spec_drift_view_actogram import (  # noqa: F401
    ACT_LANES, ACT_RUNS, ACT_PR_KINDS, _WEEKDAYS, _act_lane, _r1, _covered, _union, _twice, _act_missing, actogram,
)
from spec_drift_view_reflex import (  # noqa: F401
    RFX_END, RFX_BY, RFX_GO, _rfx_missing, _rfx_label, _said, _ago, reflex,
)
from spec_drift_view_needs_attention import (  # noqa: F401
    NEEDS_GROUPS, NEEDS_COUNTED, NEEDS_WHY, NEEDS_GRAPHS, NEEDS_CHIPS, NEEDS_UNREAD, needs_attention,
)
from spec_drift_view_learning import (  # noqa: F401
    _day_of_id, LRN_WAIT, LRN_GATED, learning,
)
from spec_drift_view_one_day import (  # noqa: F401
    ONE_DAY_FROM, ONE_DAY_SPLIT, ONE_DAY_ROLES, ONE_DAY_AT, ONE_DAY_FOUND, _one_day_subs, _one_day_track,
    _one_day_place, one_day, one_day_line,
)
from spec_drift_view_rewrites import (  # noqa: F401
    _rewrites_line, rewrites, rewrites_line,
)
