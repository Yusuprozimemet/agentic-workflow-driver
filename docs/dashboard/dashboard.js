// The dashboard in ten graphs. Each answers one question, folds what used to be several panels into
// its marks, and says the detail in the readout under it. model() reads the data and touches no
// document, so a test can run it; draw() puts what it returns on the page.

const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const shortDate = s => `${+s.slice(8, 10)} ${MONTHS[+s.slice(5, 7) - 1]}`;
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const money = n => "$" + Number(n).toFixed(2);
const SIEVE_CAP = 24;  // the most dots a By Day cell of graph 7 draws; it counts the rest
const comma = n => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
const sum = (list, f) => list.reduce((a, x) => a + (Number(f ? f(x) : x) || 0), 0);
const andList = a => a.length < 3 ? a.join(" and ") : `${a.slice(0, -1).join(", ")} and ${a[a.length - 1]}`;
const finished = d => d.status === "done" || d.status === "closed" || d.status === "cut";
const openFor = m => m >= 60 ? `${(m / 60).toFixed(1)} h` : plural(Math.max(1, Math.round(m)), "minute", "minutes");
const plain = s => String(s == null ? "" : s).replace(/`/g, "");
const lower = s => s.charAt(0).toLowerCase() + s.slice(1);
// Minutes covered by a list of [from, to] intervals, a minute two of them share counted once.
const covered = list => [...list].sort((a, b) => a[0] - b[0]).reduce((acc, [a, b]) => ({ n: acc.n + Math.max(0, b - Math.max(a, acc.end)), end: Math.max(acc.end, b) }), { n: 0, end: -Infinity }).n;
// "Days 1 to 6" for a run of days, "Days 1, 2 and 4" for one with a hole in it.
const daySpan = ds => !ds.length ? "" : ds.length === 1 ? `Day ${ds[0]}`
  : ds[ds.length - 1] - ds[0] === ds.length - 1 ? `Days ${ds[0]} to ${ds[ds.length - 1]}` : `Days ${andList(ds.map(String))}`;

// Every state a promise can be in. The first five are what a re-check can find, and the only ones counted as
// "re-checked". The page says a state by its `word`; `means` is its definition, kept here for the reader of this file.
const STATES = {
  proven: { word: "Proven", means: "its test still passes, and still fails when the bug is put back" },
  unproven: { word: "Passes, not yet proven", means: "its test passes, and has not been seen to fail in the re-check" },
  repair: { word: "Needs repair", means: "its test cannot be trusted to catch a failure" },
  broken: { word: "Broken", means: "the promise no longer holds" },
  skipped: { word: "Not checked here", means: "it needs a real live run or a different computer" },
  replaced: { word: "Replaced", means: "a later promise took its place" },
  building: { word: "Not yet in force", means: "its Day is still being built" },
  open: { word: "Left unticked", means: "its Day closed without ticking it" },
  unchecked: { word: "Not re-checked yet", means: "no re-check has run on it" },
};
const COUNTED = ["proven", "unproven", "repair", "broken", "skipped"];

// Graph 7's pipeline: every gate a Day's work passes, top to bottom, its stages keyed by name. A gate with `pile` holds
// the defects the Notes credit to it (a gate's key in the data's proofreading.gates); `guard` and `ci` name what counts how often it stopped something (a
// hook's refusals, a CI workflow's failed pull requests); `nc` marks a gate nothing counts yet; `inPr` a check counted
// under PR checks. The track loop wraps the writing alone (`loop`); the spec change, each track and the close all pass
// CI and the merge. The hooks run in every stage: HOOKS is drawn beside the pipe. PHASE_END comes after the Day's pipe.
const PIPE = [
  { name: "Before any code", gates: [
    { names: ["plan-auditor", "spec-auditor"], subs: ["first Day of a phase", "every Day"], pile: "auditor",
      does: "On the first Day of a phase, the plan-auditor asks whether the phase's specs still deliver what plan.md wants, on today's code. Every Day, before any code, the spec-auditor runs every check in the spec on the code as it is and tries to break every hold criterion. This tray holds every auditor's catches, those at a phase's end too: the Notes do not say which auditor." },
    { names: ["Spec-change PR"], subs: ["day-NN/spec-slug"], pile: "spec-change PR", does: "The pull request that fixes what the auditors found in the Day's spec, before any track starts; a defect found while writing it is caught here. Like every pull request, it then passes CI and your merge." },
    { names: ["plan-links.py"], nc: true, does: "Every criterion's Plan: line must quote the plan's own words." }] },
  { name: "Writing a track, on this machine", loop: true, gates: [
    { names: ["brief-check.py"], nc: true, does: "Fails when a backticked name in the implementer's brief sits in another file than the line names." },
    { names: ["track-reviewer"], subs: ["the brief, then the diff"], pile: "track-reviewer", does: "An agent with a fresh context reads each track twice: the brief before the implementer starts (the callers of what it changes, each fake's states, each expected count), and the diff before the pull request (the review checklist, and every claim the pull request makes). Counted from Day 13." },
    { names: ["seen-red.py"], pile: "seen red", does: "Runs the branch's new tests on main's code: they must fail, for the reason the spec gives." },
    { names: ["break.py"], pile: "break on purpose", does: "Breaks the code on purpose and runs the check twice with the break in, then puts the bytes back. A test that still passes would not catch a real failure. With --record it writes the break into the Day's record, specs/breaks/day-NN.json." },
    { names: ["break-lines.py"], nc: true, does: "Prints the pull request's manifest: and broken: lines from the Day's break record, so they are copied, never retyped." },
    { names: ["ruff"], nc: true, does: "ruff check and ruff format --check: fails on unformatted code, never rewrites it." },
    { names: ["test-parallel.py"], nc: true, does: "The whole of tests/, one file per process, the failures printed whole." },
    { names: ["pr-names.py"], nc: true, does: "The branch, title and commit names agree with the Day and track." },
    { names: ["check-links.py"], nc: true, does: "Every link in a Markdown file touched resolves." },
    { names: ["Diff review"], subs: ["the main session"], pile: "review", does: "The main session reads the implementer's diff before it runs the checks, breaks the code and commits: a defect it finds there is caught here." },
    { names: ["Noticed in the work"], pile: "work", leak: true, subs: ["no gate: a leak"],
      does: "No gate: a defect someone noticed while working, in a track or the session. A catch by a gate the Notes do not name (the 400-line check, a hook) is counted here too, for now." }] },
  { name: "The close", gates: [
    { names: ["Tick each criterion"], pile: "close", does: "The closing pull request ticks every criterion with its evidence and writes the Day's Notes; a defect found doing it is caught here. Then, like every pull request, it passes CI, where its rehearsal runs, and your merge." },
    { names: ["relabel.py + defect-rater"], relabel: true, does: "A reader who did not write the Day tags its defects blind; each disagreement is decided in the closing pull request." },
    { names: ["break-lines.py --spec"], nc: true, does: "Checks the spec's broken: lines against the Day's break record: every line has its entry, and no two breaks share a name." }] },
  { name: "CI on every pull request", gates: [
    { names: ["Description uses the template"], inPr: true, does: "The pull request's description has the template's sections." },
    { names: ["Diff stays reviewable"], subs: ["400 lines"], inPr: true, does: "No pull request over 400 changed lines; an Oversized: line turns the failure into a warning." },
    { names: ["Frozen files stay unedited"], inPr: true, does: "Files a Day froze are not edited, and the Verify lists of the holds in force do not change." },
    { names: ["Criteria keep their wording"], inPr: true, does: "A merged criterion's words do not change under it." },
    { names: ["Replaces: lines are real"], inPr: true, does: "A Replaces: line names an earlier criterion that exists." },
    { names: ["Plan links quote the plan"], inPr: true, does: "plan-links.py again, in CI." },
    { names: ["Branch, title, commits and Jira keys agree"], inPr: true, does: "pr-names.py again, in CI, with the Jira keys." },
    { names: ["Track tests seen red"], inPr: true, does: "Re-runs each new criterion's test on main's code, when TRACK_RED_RUNNER is set." },
    { names: ["Style check"], inPr: true, does: "ruff again, in CI." },
    { names: ["Compose and Prometheus"], kit: true, subs: ["applies when the project has services"], does: "Every service is wired into compose and Prometheus. It came with the kit and applies when the project has services; this one has none, so there is nothing for it to check here." },
    { names: ["Tests"], ci: "Tests", does: "tests.yml: the whole suite, serially, on Linux." },
    { names: ["Track breaks"], ci: "Track breaks", does: "track-breaks.yml: replays the pull request's broken: lines, and the Day's earlier tracks', on Linux on the merge commit; on every pull request, each closed Day's in-force break must still apply, and runs when the change touches it." },
    { names: ["Dashboard tests"], ci: "Dashboard metric tests", does: "spec-drift-tests.yml: drift and gap move when they should, token counts hold on Windows, the starter names no project." },
    { names: ["close-evidence --rehearse"], ci: "Evidence replay", pile: "rehearsal", subs: ["the closing PR, counted from Day 12"], does: "On the closing pull request only: replays the closing branch as its merge into main would, before the merge, locally and in CI (\"A closed day's evidence replays\"). Until Day 12 the Notes named its catches evidence replay: they sit with the replay after the merge." }] },
  { name: "You", gates: [
    { names: ["Your merge"], merged: true, does: "main is protected: nothing lands without the checks passing and the maintainer's merge, the spec change, each track and the close alike." }] },
  { name: "After the merge", gates: [
    { names: ["Evidence replay"], pile: "evidence replay", subs: ["before Day 12, the rehearsal too"], does: "evidence.yml on the closing merge commit, checked with gh run view --exit-status before the next step." },
    { names: ["Dashboard"], pile: "dashboard", does: "A defect seen on the published page, after the Day closed." },
    { names: ["Day NN review"], pile: "Day review", subs: ["a later Day reads it"], does: "A defect a later Day found in a closed Day's work." },
    { names: ["Re-check history"], nc: true, does: "recheck.yml: after every merge, re-checks the merges with no Linux row." }] },
];
const HOOKS = { name: "Hooks, in every stage", gates: [
  { names: ["step-guard"], guard: "step-guard", does: "After a short \"merged\", refuses subagents, edits, branches, commits, pushes and pull requests until a new session." },
  { names: ["read-guard"], guard: "read-guard", does: "Refuses a whole-file Read of a file over 8,000 bytes, and names its size." },
  { names: ["auditor-guard"], guard: "auditor-guard", does: "Keeps the six auditors with Bash read-only: blocks git writes and gh commands that are not reads, and checks the repository at their stop." },
  { names: ["cap-output"], subs: ["trims, never refuses"], nc: true, does: "Cuts Bash output over 8,000 characters to its head and tail. It trims; it does not refuse." }] };
const PHASE_END = { name: "End of a phase", gates: [
  { names: ["plan-auditor"], subs: ["after a phase's last close"], nc: true, does: "On fresh main after a phase's last closing pull request merged: what did the phase change that the next one must know? Its catches sit in the auditors' tray at the top: the Notes do not say which auditor." },
  { names: ["security-ops-auditor", "agentic-engineering-auditor", "architecture-auditor"], subs: ["after Phase 3's close", "", ""], nc: true,
    does: "Once, after the closing pull request of the last phase plan.md names: can the workflow take more autonomy safely, what does it show about agents, do its gates hold? Each from a fresh context." }] };
const CAUSES = ["spec", "process", "implementation", "environment", "other"];
const KINDS = { origin: "the first commit", spec: "spec", code: "code", close: "a Day's close", other: "other" };
const REASONS = { replay_failed: "Replay failed", replay_error: "Replay error", replay_stale: "Replay stale",
  evidence_missing: "Evidence missing", not_seen_red: "Not seen red", test_not_found: "Test not found", handoff_unclaimed: "Hand-off unclaimed",
  not_breakable: "No break possible from the repository", test_skippable: "Can be skipped in CI (expected)",
  handoff_next: "Hand-off for the next Day", handoff_unpicked: "Hand-off no later Day picks up" };
const YARD_HINT = { escapes: "fewer is better", refusals: "many of one kind mean a rule is in the way", reread: "re-reading is most of the cost",
  gates: "a gate run in the main session is also inside the pull requests' cost above" };

/* ---------- the model: what each graph draws and says, from the data alone ---------- */
function model(DATA) {
  const now = DATA.now || {}, days = [...(DATA.days || [])].sort((a, b) => a.day - b.day), current = now.current_day;
  const named = (DATA.user_stories || {}).abilities || [];
  const safe = fn => { try { return fn(); } catch (e) { return { error: String((e && e.message) || e) }; } };
  const done = days.filter(finished).map(d => d.day);
  const daysSay = (done.length ? `${daySpan(done)} ${done.length === 1 ? "is" : "are"} closed` : "No Day is closed yet")
    + (current != null ? ` and Day ${current} is in progress.` : ".");
  // The dollars, refusals, gate runs and sessions are counted on the maintainer's computer and end at that count
  // (counted.json on the dashboard-data branch); the pull requests come from GitHub and go on. What sets one against the other
  // takes only the pull requests merged by then. With no count on record, nothing is left out and nothing is claimed.
  const countedAt = (DATA.counted || {}).at || null, countedMs = countedAt ? Date.parse(countedAt) : null;
  const countedSay = countedAt ? `${countedAt.slice(11, 16)} on ${shortDate(countedAt)}` : "";
  const TIMES = ((DATA.clock || {}).prs || []).filter(p => p.opened && p.merged);
  // One rule for which Day a pull request belongs to, on every graph: the Day its branch names (`own_day`).
  // A dashboard/ or tooling/ pull request is no Day's work: it is placed by `at`, the furthest Day begun when it merged,
  // and says whether that Day was open or closed by then. A row's `day` is the gap's "Day reached" and is not read here.
  const dayOrder = DATA.order || [], rankOf = d => dayOrder.includes(d) ? dayOrder.indexOf(d) : d;
  let top = 0; const shut = new Set();
  const PLACED = (DATA.rows || []).map(r => {
    const own = r.pr && r.own_day != null ? r.own_day : null;
    if (own != null && (!top || rankOf(own) > rankOf(top))) top = own;
    const kind = r.kind in KINDS ? r.kind : "other";
    const p = { own, at: own != null ? own : top, area: !!r.pr && own == null, kind: r.pr && own == null && (kind === "code" || kind === "close") ? "other" : kind,
      whose: !r.pr ? "before Day 1" : own != null ? `Day ${own}` : !top ? "outside any Day, merged before Day 1 began"
        : `outside any Day, merged ${shut.has(top) ? `after Day ${top} closed` : `while Day ${top} was open`}` };
    if (own != null && kind === "close") shut.add(own);
    return p;
  });

  // The counts and the re-check rows come from the dashboard-data branch alone (spec-drift.py, data_source): with the
  // branch or one of its files missing, the page says what it leaves out, rather than draw nothing and say nothing.
  const DATA_WHAT = { "token-usage.json": "the dollars", "refusals.json": "the hooks' refusals", "gates.json": "the gates' runs and cost",
    "sessions.json": "the sessions' times", "counted.json": "when the sessions were last counted", "driver-runs.json": "the driver's steps",
    "replay-history.json": "the re-checks of finished promises" };
  function dataMissing() {
    const D = DATA.data;
    if (!D) return null;
    const what = names => andList(names.map(n => DATA_WHAT[n] || n));
    // Without the gates' runs and cost, the proofreading stream (spec_drift_views.proofreading) is not drawn at all;
    // without the dollars, the energy budget (spec_drift_views.budget) is not.
    const stream = " The proofreading stream is not drawn.", beads = " The energy budget is not drawn.";
    if (!D.commit) return `The ${D.branch} branch is missing, so this page leaves out ${what(Object.keys(DATA_WHAT))}.${stream}${beads}`;
    if (!(D.absent || []).length) return null;
    return `The ${D.branch} branch has no ${andList(D.absent)}, so this page leaves out ${what(D.absent)}.${D.absent.includes("gates.json") ? stream : ""}`
      + (D.absent.includes("token-usage.json") ? beads : "");
  }
  function head() {
    const g = now.generated || "", when = g.length >= 16 ? `${shortDate(g)} ${g.slice(0, 4)} at ${g.slice(11, 16)}` : g;
    // A Day is a step of the plan and not a calendar day: how many dates the closed Days' own pull requests ran over says so.
    // `worked` is a Day's first and last merge date; a pull request outside any Day that merged between two Days is not its work.
    const closed = days.filter(d => finished(d) && (d.worked || []).length === 2), dates = new Set();
    closed.forEach(d => { for (let t = Date.parse(d.worked[0]); t <= Date.parse(d.worked[1]); t += 86400000) dates.add(t); });
    const took = closed.length ? `${daySpan(closed.map(d => d.day))} took ${plural(dates.size, "date", "dates")}` : "";
    return { project: (DATA.meta || {}).project || "", when, commit: String(now.head || "").slice(0, 7), demo: DATA.demo === true,
      missing: dataMissing(), now: daysSay, next: String(now.next_step || ""), open: (now.open_prs || []).length, took };
  }

  /* The promises: each criterion with the state scripts/spec_drift_views.py (criterion_states) gave it; the page only
     reads it. The model's promises key counts them by state, for the merge graph's line in scripts/dashboard-reconcile.py. */
  function promises() {
    const tiles = (DATA.criteria_index || []).map(c => ({ id: c.id, day: c.day, status: STATES[c.state] ? c.state : "unchecked" }));
    const n = (list, s) => list.filter(t => t.status === s).length, counted = list => list.filter(t => COUNTED.includes(t.status)).length;
    return { tiles, n, counted };
  }

  /* Graph 6: every merge, with the gap it left, how long it was open, and whether a check failed on it */
  function mergeGraph() {
    const R = DATA.rows || [], V = new Map((DATA.verification || []).map(v => [v.number, v]));
    const gaps = R.map(r => r.gap_full).filter(g => g != null);
    const lo = gaps.length ? Math.floor((Math.min(...gaps) - 1) / 5) * 5 : 0, hi = gaps.length ? Math.ceil((Math.max(...gaps) + 1) / 5) * 5 : 90;
    // From the two timestamps, as graph 10 reads them: the hours beside them are rounded, and gave another minute.
    const open = new Map(TIMES.map(p => [p.number, (Date.parse(p.merged) - Date.parse(p.opened)) / 60000]));
    const mins = R.map(r => { const v = V.get(r.pr); return open.has(r.pr) ? open.get(r.pr) : v && v.hours != null ? v.hours * 60 : null; });
    const top = Math.max(120, ...mins.filter(m => m != null)), barAt = m => (6 + Math.log2(Math.max(m, 1)) / Math.log2(top) * 54) / 60;
    let before = null;
    const merges = R.map((r, i) => {
      const placed = PLACED[i], kind = placed.kind, v = V.get(r.pr) || {}, m = mins[i], failed = (v.failed || 0) > 0, g = r.gap_full;
      const moved = g == null || before == null ? null : g - before;
      if (g != null) before = g;
      const says = [g == null ? "The gap was not measured at this merge." : `Spec and code ${g.toFixed(1)}° apart${moved == null ? "" : Math.abs(moved) < 0.05 ? ", unchanged" : `, ${moved > 0 ? "up" : "down"} ${Math.abs(moved).toFixed(1)}° from the merge before`}.`,
        m == null ? "" : `Open for ${openFor(m)} before it merged.`,
        !r.pr ? "" : failed ? `A check failed on it first${(v.failed_in || []).length ? ` (${v.failed_in.join(", ")})` : ""}.` : "No check failed on it."].filter(Boolean).join(" ");
      return { pr: r.pr, kind, day: placed.own || 0, at: placed.at, date: r.date, gap: g, moved, mins: m, failed, y: g == null ? null : (hi - g) / (hi - lo), h: m == null ? 0 : barAt(m),
        t: `${r.pr ? `Pull request #${r.pr}` : "The first commit"} · ${KINDS[kind]} · ${placed.whose}`, b: [r.title, says].filter(Boolean) };
    });
    const bands = [];
    merges.forEach(m => { const b = bands[bands.length - 1]; if (b && b.day === m.at) b.n++; else bands.push({ day: m.at, n: 1 }); });
    const nKind = k => merges.filter(m => m.kind === k).length, withPr = merges.filter(m => m.pr), nFailed = merges.filter(m => m.failed).length;
    const mean = k => { const ms = merges.filter(m => m.kind === k && m.moved != null); return ms.length ? sum(ms, m => m.moved) / ms.length : null; };
    const last = R[R.length - 1] || {}, band = last.gap_chance_band, spec = mean("spec"), code = mean("code");
    const signed = x => `${x > 0 ? "up" : "down"} by ${Math.abs(x).toFixed(1)}°`;
    const b = [last.gap_full != null && band ? (last.gap_full < band[0] ? "The specs and the code share more names than chance would" : last.gap_full > band[1] ? "The specs and the code share fewer names than chance would" : "That is within what chance gives")
        + `: nineteen times in twenty, chance gives ${band[0].toFixed(1)}° to ${band[1].toFixed(1)}°.` : "",
      spec != null && code != null ? `On average a spec merge moved the dot ${signed(spec)} and a code merge ${signed(code)}.` : "",
      withPr.length ? `${nFailed} of ${plural(withPr.length, "pull request", "pull requests")} had a check of any workflow fail before ${withPr.length === 1 ? "it" : "they"} merged.` : ""].filter(Boolean);
    const step = hi - lo > 30 ? 10 : 5, ticks = [];
    for (let t = lo + step; t < hi; t += step) ticks.push({ label: `${t}°`, y: (hi - t) / (hi - lo) });
    return { merges, bands, ticks, barTicks: [[1, "1 min"], [10, "10 min"], [top, top >= 90 ? `${Math.round(top / 60)} h` : `${Math.round(top)} min`]].map(([m, label]) => ({ label, h: barAt(m) })),
      key: [["spec", `Spec merge ${nKind("spec")}`], ["code", `Code merge ${nKind("code")}`], ["close", `A Day's close ${nKind("close")}`],
        ["other", `Other (tooling, dashboard) ${nKind("other")}`], ["failed", `A check failed before the merge ${nFailed}`]],
      say: `One column per merge, ${merges.length} in all, oldest on the left. The dot is the angle between the specs and the code over the names the specs use, in degrees: lower means closer. The bar under it is how long the pull request stayed open. The first column is the first commit, before any pull request.`,
      read: { t: last.gap_full == null ? "No gap is measured yet" : `Now ${last.gap_full.toFixed(1)}° apart` + (last.gap_chance != null ? `, where chance alone would give ${last.gap_chance.toFixed(1)}°` : ""), b: [b.join(" ")].filter(Boolean) },
      table: { head: ["Merge", "Kind", "Day", "Date", "Gap, degrees", "Minutes open", "Checks failed"],
        rows: merges.map(m => [m.pr ? `#${m.pr}` : "start", KINDS[m.kind], m.day || "", m.date || "", m.gap == null ? "" : m.gap.toFixed(1), m.mins == null ? "" : Math.round(m.mins), m.failed ? "yes" : ""]) } };
  }

  /* Graph 7: the sieve. Each defect at the gate that caught it. Its rules are counted in scripts/spec_drift_views.py
     (proofreading), the same fields the proofreading stream reads: the gates, each defect's gate, layer, cause and
     marks, the four phases, and the cost per catch over the Days merged by the count. */
  function sieveGraph() {
    const PR = DATA.proofreading || {}, gateList = PR.gates || [], layerList = PR.layers || [];
    const read7 = new Map((PR.defects || []).map(o => [`${o.day}:${o.i}`, o]));
    const rows = days.map(d => {
      const dots = (d.defects || []).map((x, i) => {
        const o = read7.get(`${d.day}:${i}`), gate = o && gateList.find(g => g.key === o.gate);
        if (!gate) return null;
        const made = typeof o.made === "number" ? o.made : null, cause = o.cause;
        const where = o.escaped ? `Made on Day ${made} and caught on Day ${d.day}` + (made < d.day ? `: it escaped for ${plural(d.day - made, "Day", "Days")}.` : ".")
          : made != null ? `Made and caught on Day ${d.day}.` : o.made === "none" ? "Made outside any Day: in the plan, a tool or a machine."
          : `Caught on Day ${d.day}; its line does not say which Day made it.`;
        // Who noticed a defect caught in the work (`by`): a track, the session itself, or something else.
        return { id: o.id, day: d.day, gate: gate.key, layer: o.layer, cause, escaped: o.escaped, back: o.back, by: o.by,
          t: `${o.id} · ${cause} · caught by: ${lower(gate.name)}`,
          b: [where + (o.back ? ` The same problem as ${o.same_as}, back again.` : "") + (o.noticed ? ` Noticed by: ${o.noticed}.` : "")] };
      }).filter(Boolean);
      const R = d.relabel ? Object.values(d.relabel) : null;
      return { day: d.day, dots, cells: gateList.map(g => dots.filter(o => o.gate === g.key)), differ: R ? sum(R, r => r[1] - r[0]) : null, tags: R ? sum(R, r => r[1]) : null,
        note: R ? `${sum(R, r => r[1] - r[0])} of ${sum(R, r => r[1])}` : finished(d) ? "not read yet" : "read at its close" };
    });
    // The By Day view's note: each read Day's share of tags read differently, and whether it rose or fell since the last read Day (#213, B10).
    let prevPct = null;
    rows.forEach(r => { if (!r.tags) return; const pct = Math.round(100 * r.differ / r.tags);
      r.note += ` · ${pct}%${prevPct == null ? "" : pct > prevPct ? " ↑" : pct < prevPct ? " ↓" : " ="}`; prevPct = pct; });
    const all = rows.flatMap(r => r.dots), at = k => all.filter(o => o.gate === k).length, by = c => all.filter(o => o.cause === c).length;
    // A gate with runs on record (gates.json, on the data branch) says them; with the branch or the file missing, none does.
    const gates = gateList.map(g => ({ key: g.key, name: g.name, n: at(g.key), per: g.per,
      sub: `${at(g.key)} caught` + (g.runs != null ? ` · ${plural(g.runs, "run", "runs")} · ${money(g.cost)}` : g.key === "work" ? " · tracks, the session" : "") }));
    // A gate's dollars end at the count, so they are shared over the catches of the Days whose pull requests were all merged by then.
    const late = PR.late || [];
    const each = gateList.filter(g => g.per != null).map(g => [g.per, g.at]).sort((a, b) => a[0] - b[0]);
    const read = rows.filter(r => r.tags), nEsc = all.filter(o => o.escaped).length, nBack = all.filter(o => o.back).length;
    const b = [by("spec") ? `${by("spec")} ${by("spec") === 1 ? "was" : "were"} in a spec.` : "",
      `${nEsc} escaped from an earlier Day and ${nBack} came back.`,
      read.length ? `A second reader gave ${sum(read, r => r.differ)} of ${sum(read, r => r.tags)} tags differently.` : "",
      each.length ? `Each catch cost about ${andList(each.map(([c, name]) => `${money(c)} at ${name}`))}${late.length ? `, over the catches of the Days in the count: ${daySpan(late)} had a pull request merge after it` : ""}.` : "",
      countedAt && gateList.some(g => g.runs != null) ? `The gates' runs and dollars are counted up to ${countedSay}.` : ""].filter(Boolean);
    // The pipeline: the same dots, at the same gates, with how often the other gates stopped something, over all dates.
    const per = new Map(gateList.filter(g => g.per != null).map(g => [g.key, g.per]));
    const refused = {}, failed = {};
    (DATA.refusals || []).forEach(r => { refused[r.guard] = (refused[r.guard] || 0) + (r.refused || 0); });
    (DATA.verification || []).forEach(v => new Set(v.failed_in || []).forEach(w => { failed[w] = (failed[w] || 0) + 1; }));
    const merged = (DATA.rows || []).filter(r => r.pr).length, hooks = PR.hooks && PR.hooks.cost != null ? PR.hooks : null;
    const runs = keys => { const s = keys.map(k => gateList.find(g => g.key === k)).filter(g => g && g.runs != null);
      return s.length ? `${plural(sum(s, x => x.runs), "run", "runs")} · ${money(sum(s, x => x.cost))}` : ""; };
    const nRefused = sum(Object.values(refused)), prFails = failed["PR checks"] || 0;
    const notes = { "Before any code": runs(["auditor"]) && `auditors: ${runs(["auditor"])}`,
      "Writing a track, on this machine": runs(["seen red", "break on purpose"]) && `seen red and breaks: ${runs(["seen red", "break on purpose"])}`,
      [HOOKS.name]: (DATA.refusals || []).length ? `${plural(nRefused, "refusal", "refusals")}${hooks ? ` · ${money(hooks.cost)}` : ""}` : "",
      "CI on every pull request": (DATA.verification || []).length ? `the PR checks workflow failed on ${plural(prFails, "pull request", "pull requests")}; graph 6 counts any workflow` : "",
      "After the merge": runs(["evidence replay"]) && `replay: ${runs(["evidence replay"])}` };
    const prs = n => plural(n, "pull request", "pull requests");
    const segment = (st, n) => ({ n, name: st.name, loop: !!st.loop, note: notes[st.name] || "", gates: st.gates.map(g => {
      const dots = g.pile ? CAUSES.flatMap(c => all.filter(o => o.gate === g.pile && o.cause === c)) : null;
      const stop = g.guard ? `${refused[g.guard] || 0} refused` : g.ci ? `failed on ${prs(failed[g.ci] || 0)}` : g.merged ? `${prs(merged)} merged`
        : g.relabel && read.length ? `${sum(read, r => r.differ)} of ${sum(read, r => r.tags)} tags read differently` : "";
      const n = k => dots.filter(o => o.by === k).length;
      const caught = dots && `${dots.length} caught` + (per.has(g.pile) && dots.length ? ` · about ${money(per.get(g.pile))} a catch` : "");
      const plain = g.kit ? "nothing to check here" : g.nc ? "not counted yet" : g.inPr ? "in the PR checks' count" : "";
      return { names: g.names, subs: g.subs || [], kind: g.leak ? "leak" : g.kit ? "kit" : g.inPr ? "small" : "valve", dots, stop, plain, caught,
        by: g.pile === "work" && dots.length ? `by: tracks ${n("track")} · self ${n("self")} · other ${n("other")}` : "",
        t: g.names.join(" and "), b: [g.does, [caught, stop, plain].filter(Boolean).join("; ") + "."].filter(s => s !== ".") };
    }) });
    const stages = PIPE.map((st, si) => segment(st, si + 1)), band = segment(HOOKS, null), phaseEnd = segment(PHASE_END, null);
    const phases = layerList.map((L, i) => { const c = all.filter(o => o.layer === i).length; return { name: L.name, n: c, pct: all.length ? Math.round(100 * c / all.length) : 0 }; });
    const pipe = { stages, hooks: band, phase_end: phaseEnd, phases, escaped: nEsc, gates: sum([...stages, band], s => sum(s.gates, g => g.names.length)) };
    return { gates, rows, pipe,
      key: [...CAUSES.filter(c => c !== "other" || by(c)).map(c => ({ cls: `dot ${c}`, text: `${c.charAt(0).toUpperCase() + c.slice(1)} ${by(c)}` })),
        { cls: "dot ring", text: `Ringed: the same problem came back ${nBack}` }, { cls: "dot square", text: `Square: made on an earlier Day ${nEsc}` }],
      say: `Work flows down the pipe, through ${pipe.gates} gates in ${stages.length} stages, with the hooks beside them all; the spec change, each track and the close are each a pull request, and each passes CI and your merge. Each dot is one defect from a Day's Notes, ${all.length} in all, at the gate that caught it: the lower its tray, the later the catch. A grey number is how often a gate stopped something, over all dates. Point at a gate's name for what it checks.`,
      read: { t: !all.length ? "No defect is recorded yet" : at("auditor") ? `${plural(all.length, "defect", "defects")}; the auditors caught ${at("auditor")} of them before any code was written` : `${plural(all.length, "defect", "defects")} in the Days' Notes`,
        b: all.length ? [b.join(" ")] : [] },
      table: { head: ["Day", ...gateList.map(g => g.name), ...CAUSES.map(c => `Cause: ${c}`), "Escaped", "Came back", "Tags read differently", "Tags"],
        rows: rows.map(r => [`Day ${r.day}`, ...r.cells.map(c => c.length), ...CAUSES.map(c => r.dots.filter(o => o.cause === c).length),
          r.dots.filter(o => o.escaped).length, r.dots.filter(o => o.back).length, r.differ == null ? "" : r.differ, r.tags == null ? "" : r.tags]) } };
  }

  /* Graph 2: the plan's yardsticks, each on its own scale, against the kit's baseline where it has one */
  // The parks row on a Day with driver steps and no figure in the lab notebook: the parks over those steps stand in for it.
  // Only the figure is filled in; no average is worked out from it.
  const parksFromRuns = r => {
    const steps = (DATA.driver_runs || {}).steps || null;
    if (r.key !== "parks" || !steps) return r;
    const values = [...(r.values || [])];
    [...new Set(steps.map(s => s.day))].filter(d => d != null).forEach(day => {
      const i = values.findIndex(v => v.day === day);
      if (i >= 0 && values[i].value != null) return;
      const n = sum(steps.filter(s => s.day === day), s => (s.parks || []).length);
      const v = { day, value: n, text: `${plural(n, "park", "parks")}, counted from the driver's run log; the lab notebook has no figure for this Day yet.` };
      if (i >= 0) values[i] = v; else values.push(v);
    });
    return { ...r, values };
  };
  // Which yardsticks are better lower: the maintainer's judgement, kept in scripts/spec_drift_views.py (LOWER_BETTER) and
  // read from the gel's panels, so graph 2 and the gel judge alike.
  const lowerBetter = new Set(((DATA.gel || {}).panels || []).filter(p => p.lower_better).map(p => p.key));
  function yardGraph() {
    const Y = DATA.yardsticks || {}, all = (Y.rows || []).map(parksFromRuns), cols = [...new Set([...days.map(d => d.day), ...(Y.days || [])])].sort((a, b) => a - b);
    const show = (r, v) => r.unit === "$" ? `$${v.toFixed(r.decimals)}` : `${v.toFixed(r.decimals)}${r.unit || ""}`;
    const has = r => (r.values || []).some(v => v.value != null);
    // A row as a bullet: the last Day's bar, every Day's range, the average so far and the kit's tick, on the row's own
    // scale (0 to 1), and the Day by Day trend beside it. Green or amber says whether the last Day beat the average,
    // for the yardsticks where lower is better; refusals have no better direction.
    const bullet = (r, every, lastAvg, fine) => {
      // Only the columns' Days: the driver's run log can name a Day of the project it drove, which this page has no column for.
      const inCols = every.filter(v => cols.includes(v.day)), vals = inCols.length ? inCols : every;
      const last = vals[vals.length - 1], lo = Math.min(...vals.map(v => v.value)), hi = Math.max(...vals.map(v => v.value));
      const top = Math.max(hi, r.baseline || 0, lastAvg ? lastAvg.value : 0) * 1.08 || 1, at = v => v / top;
      const cmp = !lastAvg || !lowerBetter.has(r.key) ? "" : last.value < lastAvg.value ? "better" : last.value > lastAvg.value ? "worse" : "";
      return { lo: at(lo), hi: at(hi), last: at(last.value), avg: lastAvg ? at(lastAvg.value) : null, base: r.baseline != null ? at(r.baseline) : null, cmp,
        spark: cols.map((day, i) => { const v = r.values.find(x => x.day === day); return v && v.value != null ? { day, x: cols.length > 1 ? i / (cols.length - 1) : 0.5, y: at(v.value) } : null; }).filter(Boolean),
        now: show(r, last.value), day: last.day, avgText: lastAvg ? show(fine, lastAvg.value) : "–",
        t: `${r.name}: ${show(r, last.value)} on Day ${last.day}`,
        b: [`Every Day between ${show(r, lo)} and ${show(r, hi)}${lastAvg ? `, average so far ${show(fine, lastAvg.value)}` : ""}${r.baseline != null ? `; the kit with a person driving every step: ${show(r, r.baseline)}` : "; no kit figure to compare"}.`
          + (cmp ? ` The last Day was ${cmp} than the average.` : "")] };
    };
    const rows = all.filter(has).map(r => {
      // The average so far is drawn on the same scale, so the scale must reach it too.
      const vals = r.values.filter(v => v.value != null), avgs = (r.average || []).map((a, i) => ({ a, day: (r.values[i] || {}).day })).filter(x => x.a != null);
      const max = Math.max(...vals.map(v => v.value), ...avgs.map(x => x.a), r.baseline || 0) || 1;
      // An average of whole counts is rarely whole: it keeps one decimal where the day's own figure has none.
      const fine = { ...r, decimals: Math.max(1, r.decimals || 0) };
      const avg = avgs.map(x => ({ day: x.day, value: x.a, text: show(fine, x.a), y: x.a / max })), lastAvg = avg[avg.length - 1];
      const noun = { "pull requests": "pull request", days: "Day" }[r.average_over];
      const cells = cols.map(day => {
        const v = r.values.find(x => x.day === day);
        if (!v || v.value == null) return { day, text: "·", h: 0, over: false, t: `${r.name} · Day ${day}`,
          b: [v && v.text ? v.text : day === current ? `Day ${day} is in progress: it is counted at its close.` : `Not counted for Day ${day}.`] };
        const over = r.baseline != null && v.value > r.baseline;
        return { day, value: v.value, text: show(r, v.value), h: v.value ? Math.max(0.06, v.value / max) : 0.03, over,
          t: `${r.name} · Day ${day}: ${show(r, v.value)}` + (r.baseline != null ? `${over ? ", above" : ", within"} the baseline of ${show(r, r.baseline)}` : ""), b: [v.text || ""] };
      });
      // The cost row's count changed at Day 7 (outside work counted until then): the row says so, and graph 8's columns by Day have the split.
      return { key: r.key, name: r.name, foot: r.key === "cost" ? "Days 1 to 6 count every pull request merged since the last count, outside work included; from Day 7 on, each Day counts its own only. The two halves of the row do not compare; graph 8, with a column for each Day, has the split." : null,
        cells, line: r.baseline != null ? r.baseline / max : null, base: r.baseline != null ? show(r, r.baseline) : "",
        over: cells.filter(c => c.over).length, n: vals.length, last: vals[vals.length - 1],
        note: r.baseline != null ? `kit's baseline: ${show(r, r.baseline)}` : `no baseline${YARD_HINT[r.key] ? `; ${YARD_HINT[r.key]}` : ""}`, show: v => show(r, v),
        avg, avgNote: lastAvg ? `average so far: ${lastAvg.text}${noun ? ` over every ${noun}` : ""}` : "", bullet: bullet(r, vals, lastAvg, fine) };
    });
    const waiting = all.filter(r => !has(r)).map(r => ({ name: r.name, why: (((r.values || []).filter(v => v.text).pop() || {}).text || "nothing is counted yet").replace(/^none(?: yet)?[:,]\s*/i, "") }));
    const based = rows.filter(r => r.line != null);
    return { cols, rows: rows.map(({ show: _, last: __, ...r }) => r), waiting,
      read: { t: !rows.length ? "No yardstick is counted yet" : based.length ? "Above the kit's baseline " + based.map((r, i) => `${i ? "and " : ""}on ${r.over} of ${plural(r.n, "Day", "Days")} for ${r.key}`).join(", ")
          : `${plural(rows.length, "yardstick", "yardsticks")}, counted at each Day's close`,
        b: [based.map(r => `${r.name}: ${r.show(r.last.value)} on Day ${r.last.day}, against ${r.base} with a person driving every step.`).join(" ")
          + ((Y.problems || []).length ? ` ${plural(Y.problems.length, "cell", "cells")} could not be read.` : "")].filter(s => s.trim()) },
      table: { head: ["Yardstick", "Kit's baseline", ...cols.map(d => `Day ${d}`), "Average so far"], rows: rows.map(r => [r.name, r.base, ...r.cells.map(c => c.value == null ? "" : c.text), r.avgNote]) } };
  }

  /* Graph 1: how far to the next stop. One column per merge, then the tracks of the open day that are specified and
     not merged, then the days the plan has no spec for yet, which cannot be drawn. */
  function lookGraph() {
    const L = DATA.look_ahead || {}, R = DATA.rows || [], C = L.columns || [], P = L.pending || null, ledger = L.hand_offs || [];
    const order = DATA.order || [], stop = now.stop_after != null ? now.stop_after : null, last = C[C.length - 1] || {};
    const ceil = (n, step) => Math.max(step, Math.ceil(n / step) * step);
    // The tracks, then the close, in the order the day runs them; each adds its promises to the running total.
    let run = last.built || 0;
    const ahead = P ? [...(P.tracks || []).map(t => ({ label: t.track, ids: t.ids || [], close: false })),
      { label: "close", ids: P.at_close || [], close: true }].map(a => { run += a.ids.length; return { ...a, day: P.day, built: run }; }) : [];
    const pMax = ceil(Math.max(0, ...C.map(c => c.written || 0), ...C.map(c => c.built || 0), ...ahead.map(a => a.built)), 20);
    const hMax = ceil(Math.max(0, ...C.map(c => c.open_numbered || 0)), 6);
    const written = last.written || 0, built = last.built || 0;
    const merges = C.map((c, i) => {
      const r = R[i] || {}, placed = PLACED[i] || {}, kind = placed.kind || "other", day = placed.own || 0, got = c.got || [], open = c.open_numbered || 0;
      const moved = i ? (c.written || 0) - (C[i - 1].written || 0) : 0;
      const says = [moved > 0 ? `Its spec wrote ${plural(moved, "promise", "promises")}.` : moved < 0 ? `Its spec dropped ${plural(-moved, "promise", "promises")}.` : "",
        got.length ? `Built ${got.join(", ")}.` : "Built no promise.", `${c.built || 0} of ${c.written || 0} built after it.`,
        `${plural(open, "hand-off", "hand-offs")} open after it.`].filter(Boolean).join(" ");
      return { pr: c.pr, kind, day, at: placed.at || 0, built: c.built || 0, written: c.written || 0, open, got, yb: 1 - (c.built || 0) / pMax, yw: 1 - (c.written || 0) / pMax, h: open / hMax,
        t: `${c.pr ? `Pull request #${c.pr}` : "The first commit"} · ${KINDS[kind]} · ${placed.whose}`, b: [r.title, says] };
    });
    const aheadOut = ahead.map(a => ({ label: a.label, close: a.close, ids: a.ids, day: a.day, built: a.built, yb: 1 - a.built / pMax,
      t: a.close ? `Day ${P.day}'s close · specified, not merged` : `Day ${P.day} track ${a.label} · specified, not merged`,
      b: [a.close ? "The close ticks each promise with its evidence and leaves the hand-offs for the Days after."
        : a.ids.length ? `Would build ${a.ids.join(", ")}.` : "Builds no promise of its own.", `${a.built} of ${written} built after it.`] }));
    // Days after today with no spec, up to the stop: the plan cannot draw their size, and the hand-offs that wait for them say so.
    const at = order.indexOf(current), have = new Set(days.map(d => d.day));
    const unknown = (at < 0 ? [] : order.slice(at + 1)).filter(d => !have.has(d) && (stop == null || d <= stop)).map(day => {
      const waiting = ledger.filter(x => x.closed == null && x.id && (x.to || []).includes(day)), waits = waiting.length;
      return { day, waits, ids: waiting.map(x => x.id), t: `Day ${day} · no spec yet`,
        b: ["Its size cannot be drawn until its spec is written.", waits ? `${plural(waits, "numbered hand-off waits", "numbered hand-offs wait")} for it (${waiting.map(x => x.id).join(", ")}).` : ""].filter(Boolean) };
    });
    const bands = [];
    merges.forEach(m => { const b = bands[bands.length - 1]; if (b && b.day === m.at) b.n++; else bands.push({ day: m.at, n: 1 }); });
    if (aheadOut.length) { const b = bands[bands.length - 1]; if (b && b.day === P.day) b.n += aheadOut.length; else bands.push({ day: P.day, n: aheadOut.length }); }
    const nKind = k => merges.filter(m => m.kind === k).length;
    const left = aheadOut.length ? aheadOut[aheadOut.length - 1].built - built : 0;
    const parts = [left > 0 ? plural(left, "promise", "promises") : "", ...unknown.map(u => `Day ${u.day}`)].filter(Boolean);
    // Written and not built, and no track or close ahead builds it: a closed Day left it (Day 8's unticked box). The readout names them.
    const gotIds = new Set(C.flatMap(c => c.got || [])), aheadIds = new Set(ahead.flatMap(a => a.ids));
    const closedDays = new Set(days.filter(finished).map(d => d.day));
    const never = (DATA.criteria_index || []).filter(c => c && c.id && closedDays.has(c.day) && !gotIds.has(c.id) && !aheadIds.has(c.id)).map(c => c.id);
    const unbuilt = never.length;
    const tracks = P ? (P.tracks || []) : [];
    const b = [P ? (tracks.length ? `Day ${P.day} has ${plural(tracks.length, "track left", "tracks left")} (${tracks.map(t => `${t.track}: ${(t.ids || []).length}`).join(", ")}) and its close.`
        : `Day ${P.day} has only its close left.`) : "",
      unbuilt ? `${plural(unbuilt, "promise", "promises")} written on a closed Day ${unbuilt === 1 ? "was" : "were"} never built, and nothing ahead builds ${unbuilt === 1 ? "it" : "them"} (${never.join(", ")}).` : "",
      ...unknown.map(u => `Day ${u.day} has no spec, so its size cannot be drawn.` + (u.waits ? ` ${plural(u.waits, "numbered hand-off waits", "numbered hand-offs wait")} for it (${u.ids.join(", ")}).` : "")),
      stop != null ? `After Day ${stop} the plan stops for the maintainer. What comes after is not specified, so the graph ends there and gives no percentage of the whole plan.` : ""].filter(Boolean);
    // The ladder starts at the project's own count when the driver's count holds steps; Level 2 is drawn when its count is in.
    const DR = DATA.driver_runs || {}, steps = DR.steps, L2 = DR.level_2 || {};
    const counted2 = typeof L2.run === "number" && typeof L2.of === "number";
    // Each level card says who holds the wheel: `who` pairs a person ("maintainer" or "driver") with what they do.
    const lv0 = { lv: "Level 0", name: "The maintainer starts each step and merges", who: [["maintainer", "starts"], ["maintainer", "merges"]] };
    const lv1 = { lv: "Level 1", name: "The driver starts each step", who: [["driver", "starts"], ["maintainer", "merges"]] };
    const lv2 = { lv: "Level 2", name: "The driver merges", who: [["driver", "starts"], ["driver", "merges"]], need: "15 pull requests in a row with no change asked." };
    const rung2 = counted2 ? { ...lv2, cls: "", state: `${L2.run} of ${L2.of} in a row`, run: L2.run, of: L2.of } : { ...lv2, cls: "wait", state: "Not counted yet" };
    const rung3 = { lv: "Level 3", name: "Phases chain", who: [["driver", "runs whole phases"]], need: "One whole phase at level 2 with no escape.",
      cls: "wait", state: counted2 ? "Waits on level 2" : "Not counted yet" };
    const ladder = Array.isArray(steps) && steps.length ? [
      { ...lv0, cls: "", state: "Passed at the Day 8 trial" },
      { ...lv1, cls: "now", state: `Where the trial's project is: ${plural(steps.length, "step", "steps")} run` },
      rung2, rung3]
      : [{ ...lv0, cls: "now", state: "Where the project is" }, { ...lv1, cls: "", state: "Enters at the Day 8 trial" }, rung2, rung3];
    const ticks = [], every = pMax > 120 ? 40 : 20;
    for (let t = 0; t <= pMax; t += every) ticks.push({ label: String(t), y: 1 - t / pMax });
    return { merges, ahead: aheadOut, unknown, stop, pMax, hMax, ticks, bands, barTicks: [{ label: String(hMax / 2), h: 0.5 }, { label: String(hMax), h: 1 }],
      key: [["pt spec", `Spec merge ${nKind("spec")}`], ["pt code", `Code merge ${nKind("code")}`], ["pt close", `A Day's close ${nKind("close")}`],
        ["pt other", `Other (tooling, dashboard) ${nKind("other")}`], ["sw built", "Promises built"], ["sw written", "Promises written"],
        ["sw handoff", "Hand-offs open"], ["pt todo", "Specified, not merged"], ["sw unknown", "Not specified yet"]],
      say: `One column per merge, ${merges.length} in all, oldest on the left. The dot is the number of promises built once that merge landed; the dashed line above it is the number written. The bar under it is the numbered hand-offs still open. Right of today, the outlined dots are tracks that are specified and not merged. The first column is the first commit, before any pull request.`,
      ladder,
      read: !C.length ? { t: "Nothing is merged yet", b: [] }
        : { t: `${built} of ${written} promises built` + (parts.length ? ` · ${andList(parts)}${stop != null ? " before the stop" : " still to come"}` : "")
          + (unbuilt ? ` · ${unbuilt} never built` : ""), b },
      table: { head: ["Merge", "Kind", "Day", "Built", "Written", "Hand-offs open"],
        rows: [...merges.map(m => [m.pr ? `#${m.pr}` : "start", KINDS[m.kind], m.day || "", m.built, m.written, m.open]),
          ...aheadOut.map(a => [a.close ? "close" : `track ${a.label}`, "not merged", a.day, a.built, written, ""])] } };
  }

  // What is known and accepted (a test CI may skip, a check no break can reach) is listed apart, folded, and
  // left out of the count, so the number means "look at this" (#213, B20).
  function attention() {
    const group = list => {
      const groups = [];
      list.forEach(a => {
        const label = REASONS[a.reason] || a.reason, detail = a.detail || "";
        const g = groups.find(x => x.label === label && x.detail === detail) || groups[groups.push({ label, detail, ids: [] }) - 1];
        g.ids.push(a.id);
      });
      return groups;
    };
    const all = DATA.attention || [], open = all.filter(a => !a.expected), known = all.filter(a => a.expected);
    return { total: open.length, groups: group(open), expected: known.length, known: group(known) };
  }

  // Graph 10: one date on the clock. The sessions (sessions.json on the dashboard-data branch) are stamped with the offset of the
  // machine that recorded them, so the clock is the maintainer's and not the reader's; GitHub's times are UTC and
  // are moved to that offset. A stretch that crosses 05:00, where a date ends, is clipped to each date it touches.
  const LANES = [["main", "Main session"], ["implementer", "Implementer"], ["auditors", "Auditors"], ["other", "Other subagents"]];
  const laneOf = a => a === "main" || a === "implementer" ? a : /-auditor$|^defect-rater$/.test(a) ? "auditors" : "other";
  const offsetOf = s => { const m = /(Z|[+-]\d\d:\d\d)$/.exec(s || ""); return !m || m[1] === "Z" ? 0 : (m[1][0] === "-" ? -1 : 1) * (+m[1].slice(1, 3) * 60 + +m[1].slice(4, 6)); };
  const hm = m => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(Math.floor(m % 60)).padStart(2, "0")}`;
  const span = m => { const r = Math.round(m); return r >= 60 ? `${Math.floor(r / 60)} h ${r % 60} min` : plural(Math.max(1, r), "minute", "minutes"); };
  // What a session waited on inside a busy stretch (scripts/token-usage.py's RUN_KINDS): its key, its legend and its words in a sentence.
  const RUNS = [["tests", "waiting on tests", "tests"], ["checks", "waiting on GitHub's checks", "GitHub's checks"], ["other", "waiting on another command", "other commands"]];
  function clockGraph() {
    const C = DATA.clock || {}, S = (C.sessions || []).filter(s => s.from && s.to), PRS = (C.prs || []).filter(p => p.opened);
    const none = { head: ["Lane", "What", "From", "To", "Minutes"], rows: [] };
    // The driver's runs: the sessions it started, the merges it saw and its parks. Its times are UTC and are moved to the
    // sessions' clock like the pull requests' are; a park's step is the one whose park names its issue, for its Day.
    const DR = DATA.driver_runs || {}, DSTEPS = DR.steps || null, DPARKS = DR.parks || null, DCOUNT = DR.counted || null;
    const DSESS = (DSTEPS || []).flatMap(s => (s.sessions || []).filter(x => x.start).map(x => ({ x, s })));
    const DMERGES = (DSTEPS || []).filter(s => s.merged), stepOfPark = i => (DSTEPS || []).find(s => (s.parks || []).some(p => p.issue === i.number));
    if (!S.length && !PRS.length && !DSESS.length && !DMERGES.length && !(DPARKS || []).length) return { empty: "no session, pull request or check times are recorded yet. The maintainer's sessions count their transcripts into `sessions.json` on the dashboard-data branch (`scripts/publish-counts.py`); the pull requests' and checks' times come from GitHub.",
      dates: [], at: -1, hours: [], read: { t: "No times are recorded yet.", b: [] }, table: none };
    const counts = new Map();
    S.forEach(s => counts.set(offsetOf(s.from), (counts.get(offsetOf(s.from)) || 0) + 1));
    const zone = S.length ? [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0] : 0;
    const zoneText = zone ? `UTC${zone > 0 ? "+" : "−"}${hm(Math.abs(zone))}` : "UTC";
    // A working date runs from 05:00 to 05:00 local time, so work after midnight stays on the evening it belongs to: a moment's
    // date is the local date of the moment five hours earlier. Minutes on the clock count from the date's 05:00.
    const dateOf = s => new Date(Date.parse(s) + (zone - 300) * 60000).toISOString().slice(0, 10);
    const dayStart = date => Date.parse(`${date}T05:00:00Z`) - zone * 60000;
    const wall = m => hm((m + 300) % 1440);
    // An interval on one date, in minutes from its 05:00, or null when it misses the date.
    const clip = (date, a, b) => { const t0 = dayStart(date), x = (Date.parse(a) - t0) / 60000, y = (Date.parse(b) - t0) / 60000; return y < 0 || x > 1440 || isNaN(x) || isNaN(y) ? null : [Math.max(0, x), Math.min(1440, Math.max(y, x))]; };
    // A pull request not merged yet has no end: its bar runs to the date's end.
    const OPEN_TO = "9999-12-31T23:59:59Z";
    const dates = [...new Set([...S.map(s => dateOf(s.from)), ...PRS.flatMap(p => [p.opened, p.merged || p.closed].filter(Boolean).map(dateOf)),
      ...DSESS.map(({ x }) => dateOf(x.start)), ...DMERGES.map(s => dateOf(s.merged)), ...(DPARKS || []).flatMap(i => [i.opened, i.closed || DCOUNT]).filter(Boolean).map(dateOf)])].sort();
    const laneKeys = LANES.filter(([k]) => k !== "other" || S.some(s => laneOf(s.agent) === "other"));
    const bar = (cls, [a, b], t, b2, day) => ({ x: a / 14.4, w: (b - a) / 14.4, cls, t, b: b2, days: day ? [day] : [], mins: b - a, from: wall(a), to: wall(b) });
    // Bars of one lane that overlap go on sub-rows: the first row free when the bar starts, three rows at most, and the third
    // takes the rest, so every bar stays drawn and hoverable. A wait is drawn on its session's row (stackLane).
    const stack = bars => { const ends = []; [...bars].sort((u, v) => u.x - v.x).forEach(b => { let r = ends.findIndex(e => e <= b.x + 1e-9);
      if (r < 0) r = Math.min(ends.length, 2); ends[r] = r < ends.length ? Math.max(ends[r], b.x + b.w) : b.x + b.w; b.row = r; }); return bars; };
    const stackLane = (bars, waits) => { stack(bars); waits.forEach(w => { const own = bars.find(b => b.src === w.src); w.row = own ? own.row : 0; }); return [...bars, ...waits]; };
    const prKind = p => p.kind in KINDS && p.kind !== "origin" ? p.kind : "other";
    // A pull request's checks: the stretches its workflow runs were running in, so the time between two pushes is in none
    // of them. Data written before the stretches were kept has only the first start and the last end.
    const spansOf = ch => ch.spans && ch.spans.length ? ch.spans : [[ch.start, ch.end, ch.failed]];
    const whole = ([a, b]) => (Date.parse(b) - Date.parse(a)) / 60000, kindOf = r => (RUNS.find(k => k[0] === r[2]) || RUNS[2])[0];
    // A run GitHub cancelled, or one still queued long after the merge, never passed: say so rather than "all passed".
    const runsSay = ch => { const runs = `${plural(ch.runs, "workflow run", "workflow runs")}${ch.pushes ? ` over ${plural(ch.pushes, "push", "pushes")}` : ""}`;
      if (!ch.cancelled && !ch.unfinished) return `${runs}${ch.failed ? `, ${ch.failed} of them failed.` : ", all passed."}`;
      const passed = Math.max(0, ch.runs - (ch.failed || 0) - (ch.cancelled || 0) - (ch.unfinished || 0));
      return `${runs}: ${andList([passed ? `${passed} passed` : "", ch.failed ? `${ch.failed} failed` : "", ch.cancelled ? `${ch.cancelled} cancelled` : "",
        ch.unfinished ? `${ch.unfinished} never finished` : ""].filter(Boolean))}.`; };
    const ACT_BY = new Map(((DATA.actogram || {}).dates || []).map(x => [x.date, x]));
    const out = dates.map(date => {
      const days = new Set(), lanes = [], busy = [], rows = [];
      // The minute of this date the sessions are counted up to: all of it, none of it, or part of it.
      const upTo = countedMs == null ? 1440 : Math.max(0, Math.min(1440, (countedMs - dayStart(date)) / 60000));
      const unseen = upTo <= 0 ? "not counted yet" : upTo < 1440 ? `nothing recorded up to ${wall(upTo)}` : "nothing recorded";
      const add = (name, bars, sub, busyFor) => { lanes.push({ name, sub, bars, busyFor }); bars.forEach(b => { b.days.forEach(d => days.add(d)); rows.push([name, b.what || b.t.split(" · ")[0], b.from, b.to, Math.round(b.mins)]); }); return bars; };
      // The date's figures, counted in Python (scripts/spec_drift_views.py, actogram); without them the sentences that need them are left out.
      const F = ACT_BY.get(date) || null, ran = F ? F.ran : null, who = s => s.agent === "main" ? "Main session" : s.agent;
      let counted = false;  // a stretch written before the waits were counted has no `ran`: the date then says nothing about them
      laneKeys.forEach(([k, name]) => {
        const mine = S.filter(s => laneOf(s.agent) === k).map(s => ({ s, c: clip(date, s.from, s.to) })).filter(x => x.c);
        // What a stretch waited on, for the part of it on this date.
        const part = (s, c) => { const all = (Date.parse(s.to) - Date.parse(s.from)) / 60000; return all > 0 ? (c[1] - c[0]) / all : 1; };
        // A wait of a minute or more has its own times and is cut to the date; only the rest of `ran`, the shorter waits, is shared by the part of the stretch on it.
        const bars = mine.map(({ s, c }) => { const mins = RUNS.map(([kind]) => { const long = (s.runs || []).filter(r => kindOf(r) === kind);
            return sum(long, r => { const x = clip(date, r[0], r[1]); return x ? x[1] - x[0] : 0; }) + Math.max(0, ((s.ran || {})[kind] || 0) / 60 - sum(long, whole)) * part(s, c); }), all = sum(mins);
          return { ...bar("busy", c, `${who(s)} · busy ${wall(c[0])} to ${wall(c[1])}`, [`${plural(s.replies, "reply", "replies")}, with no gap longer than 5 minutes.`
            + (all >= 1 ? ` ${span(all)} of it waiting on commands it ran: ${andList(RUNS.map(([, , word], i) => mins[i] >= 1 ? `${span(mins[i])} on ${word}` : "").filter(Boolean))}.` : "")], s.day), ran: mins, counted: Boolean(s.ran || s.runs), src: s }; });
        const waits = mine.flatMap(({ s }) => (s.runs || []).map(([a, b, kind]) => { const c = clip(date, a, b), run = RUNS.find(r => r[0] === kind) || RUNS[2];
          return c && { ...bar(`run ${run[0]}`, c, `${who(s)} · ${run[1]} ${wall(c[0])} to ${wall(c[1])}`, [`${span(c[1] - c[0])} inside a busy stretch: the session had run a command and was waiting for it to finish.`], s.day), what: `${who(s)}, ${run[1]}`, src: s }; }).filter(Boolean));
        busy.push(...bars);
        counted = counted || bars.some(b => b.counted);
        // A lane's busy minutes (two of its sessions at once counted once) and its waits are counted in Python (actogram).
        const mins = F && bars.length ? F.lanes[k] : null, wait = F && bars.length ? F.waits[k] : null;
        add(name, stackLane(bars, waits), !bars.length ? unseen : mins == null ? "busy"
          : `busy ${span(mins)}${wait >= 1 ? `, ${span(wait)} of it waiting on commands` : ""}`, mins != null ? span(mins) : "");
      });
      // A pull request is drawn from its opening to its merge, to its close without a merge, or to the date's end while it is still open.
      const open = PRS.map(p => { const c = clip(date, p.opened, p.merged || p.closed || OPEN_TO); if (!c) return null; const ch = p.checks, at = wall(c[0]), to = wall(c[1]),
        earlier = c[0] === 0 && Date.parse(p.opened) < dayStart(date) ? ", opened on an earlier date" : "";
        return { ...bar(prKind(p), c, `Pull request #${p.number} · ${p.branch} · ${p.merged ? `open ${at} to ${to}` : p.closed ? `closed without merging ${at} to ${to}` : `still open from ${at}`}`,
          [p.merged ? `Open for ${span(whole([p.opened, p.merged]))} before it merged${earlier}.` : p.closed ? `Open for ${span(whole([p.opened, p.closed]))} before it was closed without merging${earlier}.`
            : `Still open: not merged or closed yet${earlier}.`, ch ? `Its checks were running for ${span(sum(spansOf(ch), whole))}: ${runsSay(ch)}` : "No check is recorded for it."], p.day),
          pr: p.number, state: p.merged ? "merged" : p.closed ? "closed" : "open" }; }).filter(Boolean);
      const stillOpen = open.filter(b => b.state === "open").length, unmerged = open.filter(b => b.state === "closed").length;
      add("Pull request open", stack(open), open.length ? `${plural(open.length, "pull request", "pull requests")}, ${span(sum(open, b => b.mins))} in all${stillOpen ? `, ${stillOpen} still open` : ""}${unmerged ? `, ${unmerged} closed without merging` : ""}` : "none open");
      const checks = PRS.flatMap(p => !p.checks ? [] : spansOf(p.checks).map(([a, b, failed]) => { const c = clip(date, a, b);
        return c && { ...bar(failed ? "failed" : "ok", c, `Checks on pull request #${p.number} · ${wall(c[0])} to ${wall(c[1])}`, [`On this pull request in all: ${runsSay(p.checks)}`], p.day), pr: p.number }; }).filter(Boolean));
      busy.push(...checks);
      const checked = new Set(checks.map(b => b.pr)), red = new Set(checks.filter(b => b.cls === "failed").map(b => b.pr));
      // The date's pull requests with no check run on it are named, so a reader does not take the lane for all of them.
      const unchecked = open.map(b => b.pr).filter(n => !checked.has(n));
      add("Checks running", stack(checks), checks.length ? `on ${plural(checked.size, "pull request", "pull requests")}, running for ${span(covered(checks.map(b => [b.x * 14.4, b.x * 14.4 + b.mins])))}, ${red.size} with a failure${unchecked.length ? `; none on ${unchecked.map(n => `#${n}`).join(", ")}` : ""}` : "none");
      const merged = PRS.filter(p => p.merged && dateOf(p.merged) === date).map(p => ({ p, wait: (Date.parse(p.merged) - Date.parse(p.opened)) / 60000 }));
      const merges = merged.map(({ p, wait }) => { const at = (Date.parse(p.merged) - dayStart(date)) / 60000; return bar("merge", [at, at], `Merged pull request #${p.number} · at ${wall(at)}`, [`The maintainer merged it ${span(wait)} after it opened.`], p.day); });
      add("Maintainer merges", merges, plural(merges.length, "merge", "merges"));
      // The driver's lanes come first and are not busy time: a mark for each session it started, each merge it saw and each
      // crashed session (the run log does not say when it was on or off, so no lane shows that), and its parks as bars.
      const minuteOf = t => (Date.parse(t) - dayStart(date)) / 60000, sessionsOn = DSESS.filter(({ x }) => dateOf(x.start) === date);
      const acts = [...sessionsOn.map(({ x, s }) => bar("act", [minuteOf(x.start), minuteOf(x.start)], `The driver started a session · ${wall(minuteOf(x.start))}`, [s.step], s.day)),
        ...DMERGES.filter(s => dateOf(s.merged) === date).map(s => bar("act", [minuteOf(s.merged), minuteOf(s.merged)], `The driver saw pull request ${s.pr != null ? `#${s.pr}` : "a pull request"} merged · ${wall(minuteOf(s.merged))}`, [s.step], s.day))];
      const crashes = sessionsOn.filter(({ x }) => x.crashed).map(({ x, s }) => bar("crash", [minuteOf(x.start), minuteOf(x.start)], `A session crashed · started ${wall(minuteOf(x.start))}`, ["The run log has no end for it."], s.day));
      const parks = (DPARKS || []).map(i => { const end = i.closed || DCOUNT, c = end ? clip(date, i.opened, end) : null;
        return c && bar("park", c, `Parked · ${wall(c[0])} to ${wall(c[1])}`, [i.closed ? `Waited ${span((Date.parse(i.closed) - Date.parse(i.opened)) / 60000)}: ${i.title}` : `Still waiting at the count: ${i.title}`], (stepOfPark(i) || {}).day); }).filter(Boolean);
      // A date with no driver step and no park has neither lane: the readout says so instead. A missing park list keeps its lane.
      const quiet = DSTEPS && DPARKS && !acts.length && !crashes.length && !parks.length;
      const drv = DSTEPS && !quiet ? [{ name: "Driver", sub: acts.length || crashes.length ? `${plural(acts.length, "act", "acts")}, ${plural(crashes.length, "crashed session", "crashed sessions")}` : unseen, bars: [...acts, ...crashes] },
        { name: "Parked for the maintainer", sub: !DPARKS ? "the parked issues could not be read" : parks.length ? `${plural(parks.length, "park", "parks")}, ${span(sum(parks, b => b.mins))} in all` : "none", bars: stack(parks) }] : [];
      drv.forEach(l => l.bars.forEach(b => { b.days.forEach(d => days.add(d)); rows.push([l.name, b.what || b.t.split(" · ")[0], b.from, b.to, Math.round(b.mins)]); }));
      lanes.unshift(...drv);
      const driverSay = quiet ? "The driver started no step and nothing was parked on this date." : DSTEPS && (sessionsOn.length || parks.length) ? `The driver started ${plural(sessionsOn.length, "session", "sessions")} and waited ${parks.length ? `${span(sum(parks, b => b.mins))} on ${plural(parks.length, "park", "parks")}` : "on no park"}.` : "";
      // What the date says as a whole: the merges and the typical wait, who was busy how long, the longest stretch with nothing running, the longest waits.
      const median = F ? F.median : null, sessionBars = busy.some(b => b.cls === "busy");
      const was = lanes.filter(l => l.busyFor).map((l, i) => `${i ? "the " : "The "}${lower(l.name)} ${i ? "" : "was busy "}for ${l.busyFor}`);
      const waited = !counted || !ran ? "" : sum(ran) < 1 ? "None of that was a wait on a command of a minute or more."
        : `Of that, the sessions waited ${span(sum(ran))} on commands they had run: ${andList(RUNS.map(([, , word], i) => ran[i] >= 1 ? `${span(ran[i])} on ${word}` : "").filter(Boolean))}.${ran[1] >= 1 ? " The wait on GitHub's checks is drawn again under Checks running." : ""}`;
      const idle = busy.map(b => [b.x * 14.4, b.x * 14.4 + b.mins]).sort((a, b) => a[0] - b[0]).reduce((acc, [a, b]) => { if (acc.end != null && a - acc.end > acc.gap && a <= upTo) { acc.gap = a - acc.end; acc.from = acc.end; acc.to = a; } acc.end = acc.end == null ? b : Math.max(acc.end, b); return acc; }, { end: null, gap: 0 });
      const longest = merged.sort((a, b) => b.wait - a.wait).slice(0, 3);
      const read = { t: F ? `${shortDate(date)}: ${plural(F.merged, "pull request", "pull requests")} merged${median != null ? `, half of them open for ${span(median)} or less` : ""}` : shortDate(date),
        b: [days.size ? `Work of ${daySpan([...days].sort((a, b) => a - b))}.` : "", was.length ? `${andList(was)}.` : sessionBars ? "" : upTo <= 0 ? `The sessions of this date are not counted yet: the count ends at ${countedSay}.` : "No session was recorded on this date.", was.length ? waited : "", driverSay,
          upTo > 0 && upTo < 1440 ? `The sessions are counted up to ${wall(upTo)}: after that, only GitHub's pull requests and checks are in.` : "",
          idle.gap >= 60 ? `Nothing ran from ${wall(idle.from)} to ${wall(idle.to)}.` : "", longest.length ? `The longest ${longest.length === 1 ? "wait" : "waits"} for a merge: ${andList(longest.map(m => `#${m.p.number} (${span(m.wait)})`))}.` : "",
          `Times are on the clock of the machine that recorded the sessions (${zoneText}).`].filter(Boolean) };
      const fig = F && { lanes: F.lanes, waits: F.waits, ran: F.ran, merged: F.merged, median: F.median };
      return { date, label: shortDate(date), days: [...days].sort((a, b) => a - b), lanes, read, table: { head: none.head, rows }, fig };
    });
    const at = out.length - 1;
    return { dates: out, at, zone: zoneText, runs: RUNS.map(([k, text]) => [k, text]), hours: [6, 9, 12, 15, 18, 21, 0, 3].map(hh => ({ t: hm(hh * 60), x: ((hh * 60 - 300 + 1440) % 1440) / 14.4 })), read: out[at].read, table: out[at].table, driver: DSTEPS !== null };
  }

  // The plan graph: one stripe per commitment of plan.md (specs/plan/promises.json), one row per Day, a mark where a
  // criterion of that Day names the commitment in its Plan: line (Days 1 to 10: the backfill). Nothing here is a reader's.
  function planGraph() {
    const PL = DATA.plan;
    if (!PL || !(PL.commitments || []).length) return { empty: "this project keeps no `specs/plan/promises.json`, so no criterion can name what the plan commits to.",
      read: { t: "Not measured yet", b: [] }, table: { head: [], rows: [] } };
    // Only criteria in force count: one a later criterion replaced no longer names anything (scripts/plan-links.py reads the same).
    const gone = new Set(PL.replaced || []), links = PL.links || {};
    const crit = (DATA.criteria_index || []).filter(c => c && c.id in links && !gone.has(c.id));
    const closedTo = Math.max(0, ...days.filter(finished).map(d => d.day));
    const kindOf = c => { const l = links[c.id]; return l.some(p => p[0] === "P") ? "first" : l.length ? "added" : c.tag === "hold" ? "guard" : "unplanned"; };
    const KIND = { first: "names a commitment of the plan as approved", added: "names only commitments added later", unplanned: "new work, Plan: none", guard: "safety check, Plan: none" };
    const by = {}; crit.forEach(c => links[c.id].forEach(p => (by[p] = by[p] || []).push(c)));
    const shade = n => n >= 7 ? 4 : n >= 4 ? 3 : n >= 2 ? 2 : n ? 1 : 0;
    const said = c => `${c.id} ${plain(c.plain || c.claim || "")}`;
    const byDay = list => [...new Set(list.map(c => c.day))].sort((a, b) => a - b).map(d => `Day ${d}: ${list.filter(c => c.day === d).map(c => c.id).join(", ")}`);
    const cols = PL.commitments.map(p => {
      const served = by[p.id] || [], n = served.length, due = !p.rule && p.owner_day != null && p.owner_day <= closedTo && !n;
      const state = p.rule ? "a rule about people, which no test can check" : due ? `due by Day ${p.owner_day}, and no criterion names it`
        : n ? plural(n, "criterion names it", "criteria name it") : p.owner_day != null ? `owned by Day ${p.owner_day}, not reached yet` : "no criterion names it";
      return { arm: p.id[0] === "P" ? "p" : "n", key: p.id, section: p.section, shade: shade(n), n, rule: p.rule, due, change: p.change,
        days: [...new Set(served.map(c => c.day))],
        is: { due, none: !n && !p.rule, single: n === 1, changed: !!p.change },
        t: `${p.id} · ${p.short}`, b: [`${p.section} · ${p.change ? `the plan ${p.change === "reworded" ? "reworded" : "later changed"} it` : p.id[0] === "P" ? "as approved" : "added by a later plan change"} · ${state}.`,
          p.text, ...byDay(served), ...served.map(said)] };
    });
    const off = crit.filter(c => !links[c.id].length).sort((a, b) => a.day - b.day || a.id.localeCompare(b.id, "en", { numeric: true }))
      .map(c => ({ arm: "o", key: c.id, kind: kindOf(c), days: [c.day], is: {}, t: `${c.id} · ${KIND[kindOf(c)]}`,
        b: [`Day ${c.day}, tagged ${c.tag}. Its Plan: line names no commitment${kindOf(c) === "guard" ? ": it checks that earlier work still holds" : ": work the plan does not ask for"}.`, plain(c.plain || c.claim || "")] }));
    const all = [...cols, ...off], at = new Map(all.map((c, i) => [c.key, i]));
    const groups = arm => all.reduce((g, c, i) => { if (c.arm !== arm) return g; const last = g[g.length - 1];
      if (last && last.label === c.section) last.to = i; else g.push({ label: c.section, from: i, to: i }); return g; }, []);
    const after = new Set((PL.rewrites || []).map(r => r.after_day));
    const dayList = [...new Set(crit.map(c => c.day))].sort((a, b) => a - b);
    const rows = dayList.map(d => {
      const mine = crit.filter(c => c.day === d), k = s => mine.filter(c => kindOf(c) === s).length;
      const marks = [];
      mine.forEach(c => { const l = links[c.id];
        if (!l.length) marks.push({ i: at.get(c.id), cls: kindOf(c) });
        l.forEach(p => at.has(p) && marks.push({ i: at.get(p), cls: p[0] === "P" ? "first" : "added" })); });
      const counts = { first: k("first"), added: k("added"), unplanned: k("unplanned"), guard: k("guard") };
      return { day: d, n: mine.length, counts, marks, rewrite: after.has(d),
        read: { t: `Day ${d} · ${plural(mine.length, "criterion", "criteria")}`, b: [`${counts.first} name a commitment of the plan as approved, ${counts.added} only commitments added later, ${counts.unplanned} are new work the plan does not ask for, ${counts.guard} are safety checks.`,
          after.has(d) ? "The plan was rewritten after this Day's spec merged: the Days below wrote against the new plan." : ""].filter(Boolean) } };
    });
    const P0 = cols.filter(c => c.arm === "p"), N0 = cols.filter(c => c.arm === "n");
    const filters = [["due", "Should be covered by now, is not"], ["none", "No criterion yet"], ["single", "Held by a single criterion"], ["changed", "Rewritten by the plan later"]]
      .map(([key, label]) => ({ key, label, n: cols.filter(c => c.is[key]).length }));
    const served = list => list.filter(c => c.n).length, quotes = PL.quotes || 0;
    const read = { t: `${served(P0)} of ${P0.length} commitments of the approved plan and ${served(N0)} of ${N0.length} added later are named by a criterion`,
      b: [`${plural(crit.length, "criterion in force", "criteria in force")} over ${plural(dayList.length, "Day", "Days")}; ${plural(off.length, "names", "name")} no commitment${gone.size ? `; ${plural(gone.size, "criterion a later one replaced is", "criteria later ones replaced are")} not counted` : ""}. ${filters[0].n ? `${plural(filters[0].n, "commitment is", "commitments are")} due by a closed Day and named by no criterion in force.` : "Every commitment due by a closed Day is named."}`,
        `${comma(quotes)} quotes, each found word for word in its commitment by \`scripts/plan-links.py\` on every pull request.`,
        (PL.unlined || []).length ? `${plural(PL.unlined.length, "criterion has", "criteria have")} no Plan: line yet and ${PL.unlined.length === 1 ? "is" : "are"} not drawn: ${PL.unlined.join(", ")}.` : ""].filter(Boolean) };
    const ladder = { days: dayList, rows: cols.map(c => ({ key: c.key, name: c.t, cells: dayList.map(d => (by[c.key] || []).filter(x => x.day === d).length), c })) };
    // What the two drawings read, in the by-script mockup's own shapes: the commitments by arm, every criterion with
    // its links and their quotes, the rows a rewrite sits above, and why each unnamed commitment is unnamed.
    const quoteOf = PL.said || {}, cut = s => s.length > 220 ? `${s.slice(0, 219)}…` : s;
    const toP = p => ({ id: p.id, short: p.short, sec: p.section, promise: p.text, status: p.change || "kept", note: p.note || "" });
    const un = {};
    PL.commitments.forEach(p => { if ((by[p.id] || []).length) return;
      const owner = p.owner_day;
      un[p.id] = p.rule ? { kind: "standing", when: "" } : owner != null && owner <= closedTo ? { kind: "due", when: `Day ${owner}` }
        : owner != null ? { kind: "later", when: `Day ${owner}` } : null;
      if (!un[p.id]) delete un[p.id]; });
    const chart = { days: dayList, quotes,
      ref: PL.commitments.filter(p => p.id[0] === "P").map(toP), added: PL.commitments.filter(p => p.id[0] !== "P").map(toP),
      C: crit.map(c => ({ id: c.id, day: c.day, tag: c.tag, what: cut(plain(c.plain || c.claim || "")),
        kind: { first: "ref", added: "later" }[kindOf(c)] || kindOf(c), links: links[c.id].map((p, k) => ({ p, quote: (quoteOf[c.id] || [])[k] || "" })) })),
      rw: [...after].map(a => dayList.findIndex(d => d > a)).filter(i => i > 0).sort((a, b) => a - b), un };
    return { chart, say:`One stripe per commitment of \`plan.md\`, in the plan's order, and one row per Day: a mark means a criterion of that Day names the commitment under it in its Plan: line.`,
      all, arms: [["p", `The plan as approved · ${P0.length}`], ["n", `Added later · ${N0.length}`], ["o", `Criteria no commitment asks for · ${off.length}`]].filter(([a]) => all.some(c => c.arm === a)),
      sections: groups("p"), added_sections: groups("n"), rows, filters, quotes, read, ladder,
      table: { head: ["Commitment", "Section", "Owner Day", "Criteria", "Days", "State"],
        rows: cols.map(c => [c.t, c.section, c.rule ? "rule about people" : PL.commitments[at.get(c.key)].owner_day ?? "", c.n, c.days.sort((a, b) => a - b).join(", "), c.b[0].split(" · ").pop().replace(/\.$/, "")]) } };
  }

  /* The merge graph: counted in scripts/spec_drift_views.py (merge_graph), drawn by mergeDraw as it stands. */
  /* "Where we are" as a ring, and graph 1 read as a gene: counted in scripts/spec_drift_views.py (where_ring, reading);
     the reading carries what dashboard-reconcile.py holds it to, the look-ahead's own ledger and last column. */
  function whrGraph() {
    const W = DATA.where_ring;
    return W && (W.slots || []).length ? W : { empty: (W && W.empty) || "plan.md lists no phase with its Days, so there is no plan to draw as a ring." };
  }
  function rdgGraph() {
    const R = DATA.reading, L = DATA.look_ahead || {}, C = L.columns || [], last = C[C.length - 1] || {};
    if (!R || !(R.m || []).length) return { empty: (R && R.empty) || "nothing is merged yet, so there is no strand to read." };
    return Object.assign({}, R, { ledger: { n: (L.hand_offs || []).length, open: last.open || 0, numbered: last.open_numbered || 0 } });
  }
  /* Graph 2 as a gel, and graphs 3 to 5 as proteins: counted in scripts/spec_drift_views.py (gel, protein). */
  function gelGraph() {
    const G = DATA.gel;
    return G && (G.panels || []).length ? G : { empty: (G && G.empty) || "no yardstick is counted yet, so there is no gel to run." };
  }
  function prtGraph() {
    const P = DATA.protein, Q = (safe(quality) || {}).abilities || {};
    if (!P || !(P.chains || []).length) return { empty: (P && P.empty) || "no criterion is on record yet, so there is no chain to fold." };
    return Object.assign({}, P, { chains: P.chains.map(c => Object.assign({}, c, { parts: c.key in Q ? Q[c.key].parts : null })) });
  }
  /* Graph 7 as proofreading: counted in scripts/spec_drift_views.py (proofreading); `empty` with the data branch or its
     gates.json missing, where the stream is not drawn. */
  function prfGraph() {
    const P = DATA.proofreading;
    return P && (P.gates || []).length ? P : { empty: "no defect is counted yet, so there is no stream to draw." };
  }
  /* Graph 8 as an energy budget and graph 9 as growth rings: counted in scripts/spec_drift_views.py (budget, rings).
     The budget is `empty` with the data branch or its token-usage.json missing, where no bead is drawn. */
  function atpGraph() {
    const B = DATA.budget;
    return B ? B : { empty: "no token counts yet, so there is no bead to draw." };
  }
  function rngGraph() {
    const R = DATA.rings;
    return R && R.drawn ? R : { empty: "no Day has merged work yet, so there is no ring to draw." };
  }
  // The actogram: every date on one clock, counted in Python (actogram); with the sessions missing it draws nothing.
  function actGraph() {
    const A = DATA.actogram;
    if (A && A.missing) return { empty: A.missing };
    return A && (A.dates || []).some(x => x.segs.length) ? A : { empty: "no session is recorded yet, so there is no date to draw." };
  }
  // Graph 11 as reflex arcs, counted in Python (reflex); with the run log or the data branch missing it draws nothing.
  function rfxGraph() {
    const R = DATA.reflex;
    if (!R) return { empty: "the driver's run log is not counted for this project yet, so no step is drawn." };
    if (R.missing) return { empty: R.missing };
    return (R.rows || []).length ? R : { empty: "the driver has started no step yet, so there is no row to draw." };
  }
  function mrgGraph() {
    const G = DATA.merge_graph;
    return G && (G.crit || []).length ? G : { empty: "no criterion is on record yet, so no merge can be drawn against one." };
  }

  /* The gene: the plan read down to proved code. Every figure is counted in scripts/spec_drift_views.py (gene);
     this only words it and hands the drawing its columns, its labels and what the pointer says. */
  function geneGraph() {
    const G = DATA.gene;
    if (!G || !(G.commitments || []).length) return { empty: "this project keeps no `specs/plan/promises.json`, so nothing reads the plan down to the code.",
      read: { t: "Not measured yet", b: [] }, table: { head: [], rows: [] } };
    const C = G.counts || {}, U = G.untranscribed || {}, Q = G.quoting || {}, total = G.commitments.length, ring = G.ring || G.off || [];
    const K = new Map((DATA.criteria_index || []).map(c => [c.id, c])), part = (C.proved || 0) - G.proved_full;
    const CLASS = {
      proved: ["reach proved code", `a criterion in force names them, and a break on purpose proved its test. For ${G.proved_full} of them that is every criterion that names them; for ${part}, only some`],
      unproved: [C.unproved === 1 ? "reaches code never seen to fail" : "reach code never seen to fail", "the criterion holds, but no break was recorded for it"],
      unreplayable: [C.unreplayable === 1 ? "reaches a check nobody can replay" : "reach a check nobody can replay", "every criterion that names it needs a live run or another computer, which the replay cannot give"],
      repair: [C.repair === 1 ? "reaches a test that needs repair" : "reach a test that needs repair", "its recorded break no longer applies, or its test stopped catching it"],
      fails: [C.fails === 1 ? "reaches code that is broken" : "reach code that is broken", "the last replay found a criterion that names it failing"],
      unbuilt: [C.unbuilt === 1 ? "is named, not built yet" : "are named, not built yet", "its criteria are written in a Day still open, or left unticked"],
      spliced: [C.spliced === 1 ? "is spliced out" : "are spliced out", "only replaced criteria name them, so they stop at the spec"],
      // never transcribed, in three: a rule for people (regulatory), a gene whose Day is still ahead (switched off), and overdue
      regulatory: [U.rule === 1 ? "is regulatory" : "are regulatory", "rules for how people work: they steer the work and never become code, so no criterion is expected"],
      switched: [U.later === 1 ? "is switched off for now" : "are switched off for now", "real genes, not due yet: each turns on when its Day writes the checks"],
      overdue: ["should be on by now", U.due ? overdueSub() : `none: every commitment due by Day ${G.closed_to} was transcribed at least once`]};
    function overdueSub() {
      const by = [...new Set(G.commitments.filter(c => c.sub === "due").map(c => c.settled_by))];
      return by.length === 1 && by[0] != null ? `overdue, all recorded as due by Day ${by[0]}` : "overdue: due by a Day that has closed, and no criterion ever named them";
    }
    const N = { ...C, regulatory: U.rule, switched: U.later, overdue: U.due };
    const ALWAYS = ["proved", "unproved", "unreplayable", "spliced", "regulatory", "switched", "overdue"];
    const figs = Object.keys(CLASS).filter(k => ALWAYS.includes(k) || N[k]).map(k => ({ cls: k, n: N[k] || 0, what: CLASS[k][0], sub: CLASS[k][1] }));
    const WORD = { proven: "holds, and a break on purpose proved its test", unproven: "holds; its test was never seen to fail", skipped: "the replay cannot run this check",
      repair: "its test needs repair (the recorded break no longer applies, or the test stopped catching it)", broken: "not holding at the newest replay",
      building: "written, not built yet", open: "left unticked", unchecked: "not re-checked yet", replaced: "replaced" };
    const REST = { unproven: "never seen to fail", skipped: "the replay cannot run", repair: "needing repair", broken: "broken", building: "not built yet", open: "left unticked", unchecked: "not re-checked yet" };
    const says = { unproved: "Reaches code that holds, but no test for it was ever seen to fail.", unreplayable: "Reaches a check the replay cannot run.",
      repair: "Reaches a test that needs repair.", fails: "Reaches code that is not holding at the newest replay.", unbuilt: "Named, and not built yet." };
    const owed = c => c.settled_by != null ? ` Recorded in specs/plan/overdue.json, to be settled by Day ${c.settled_by}.` : "";
    const reach = c => c.cls === "untranscribed" ? { rule: "Regulatory: a rule for how people work. It steers the work and never becomes code, so no criterion is expected.",
        later: c.owner_day != null ? `Switched off until Day ${c.owner_day}: a real gene with no criterion yet. It turns on when that Day writes its checks.`
          : "Switched off: no Day owns it yet, and no criterion names it.",
        due: `Overdue: due by Day ${c.owner_day}, and no criterion names it.${owed(c)}` }[c.sub]
      : c.cls === "spliced" ? `Spliced out: every criterion that named it was replaced, and the replacement does not name it.${owed(c)}`
      : c.cls !== "proved" ? says[c.cls]
      : c.sub === "full" ? "Reaches code that holds, and a break on purpose proved a test for it."
      : `Reaches code that holds. A break on purpose proved ${(c.tally || {}).proven || 0} of the ${c.cells.length} criteria in force that name it; the rest: ${Object.entries(c.tally || {}).filter(([k]) => k !== "proven").map(([k, n]) => `${n} ${REST[k] || k}`).join(", ")}.`;
    const cols = G.commitments.map(c => ({ ...c, reach: reach(c),
      tip: [["t", `${c.id} · ${c.short}`], c.text && ["", c.text],
        ["q", `Section: ${c.section}${c.rule ? " · regulatory" :c.owner_day != null ? ` · due by Day ${c.owner_day}` : ""}`], ["st", reach(c)],
        c.written.length && ["q", `Named in ${plural(c.written.length, "quote", "quotes")} by ${plural(c.criteria, "criterion", "criteria")}, replaced ones included`],
        c.change && ["q", `${c.change === "changed" ? "The plan later rewrote it." : "Reworded only."} ${c.note || ""}`.trim()]].filter(Boolean) }));
    // what the pointer says of one criterion: the same lines wherever the criterion is drawn, and the quote of the commitment under it
    const crit = Object.fromEntries([...cols.flatMap(c => c.written), ...ring].map(q => {
      const c = K.get(q.id) || {}, S = c.seen || {}, prs = c.prs || [];
      return [q.id, { head: `${q.id} · Day ${q.day}${c.track ? ` · track ${c.track}` : ""} · ${q.tag === "hold" ? "safety check" : "new work"}`, text: c.plain || c.claim || "",
        code: q.gone ? `Code: replaced by ${andList(c.replaced_by || [])}; the replay no longer runs it` : `Code: ${WORD[q.state] || q.state}${S.last ? ` (last replayed at #${S.last})` : ""}`,
        more: [!q.gone && `Names ${plural((c.tests || []).length, "test", "tests")}${prs.length ? `. Evidence in ${prs.map(n => `#${n}`).join(", ")}` : ""}. The replay ran it at ${plural(S.merges || 0, "merge", "merges")}.`,
          ...(S.stops || []).map(s => `At #${s.pr} the replay first reported “${s.state}”, ${s.held ? `and it held again by #${s.held}.` : "and it was not seen holding again."}`)].filter(Boolean) }];
    }));
    // the names down the left of the picture, each with its counts
    const code = [[G.proved_full, "proved in full"], [part, "proved in part"], [C.unproved, "never seen to fail"], [C.unreplayable, "cannot be replayed"],
      [C.repair, "needing repair"], [C.fails, "broken"], [C.unbuilt, "not built yet"]].filter(([n]) => n).map(([n, w]) => `${n} ${w}`);
    const rows = { plan: ["The plan", "the gene", [plural(total, "commitment", "commitments")]],
      written: ["Criteria, as written", "the first transcript", [`${plural(G.quotes, "quote", "quotes")} of the plan`, `in ${plural(Q.criteria || 0, "criterion", "criteria")}`]],
      splice: ["Replacement", "splicing", [`${G.named} named at least once,`, `${C.spliced || 0} ${C.spliced === 1 ? "loses" : "lose"} every criterion`]],
      live: ["Criteria in force", "the mature transcript", [plural(G.live, "commitment", "commitments")]],
      tests: ["Tests and replay", "translation", [`${plural(G.live_quotes, "quote", "quotes")} in force,`, `${plural(Q.not_proved || 0, "criterion", "criteria")} not proved,`, `${Q.came_back || 0} stopped once`]],
      code: ["The code", "the protein", code] };
    // under the picture: where the plan stops short of proved code, a line for each kind, with the commitments it lights
    const them = n => n === 1 ? "it" : "them", by = f => [...cols.reduce((g, c) => { const k = f(c); if (k != null) g.set(k, [...(g.get(k) || []), c]); return g; }, new Map())];
    const cls = k => cols.filter(c => c.cls === k), ids = list => andList(list.map(c => c.id)), one = c => `${c.id}, ${c.short}.`;
    const spliced = cls("spliced"), settle = [...new Set(spliced.map(c => c.settled_by))];
    const weak = q => ["building", "open", "broken", "repair", "unchecked"].includes(q.state);
    const back = [...new Set([...cols.flatMap(c => c.cells), ...ring].filter(q => q.back && !q.gone).map(q => q.id))];
    const finds = [
      ...cols.filter(c => c.cls === "untranscribed" && c.sub === "due").map(c => ({ ids: [c.id], b: one(c),
        text: `Due by Day ${c.owner_day}, and no criterion names it. The gene has it; nothing was ever transcribed.${c.settled_by != null ? ` \`specs/plan/overdue.json\` records it, to be settled by Day ${c.settled_by}.` : ""}` })),
      spliced.length && { ids: spliced.map(c => c.id), b: `${ids(spliced)}.`,
        text: `Spliced out. Every criterion that named ${them(spliced.length)} was replaced by a later one, and the later one does not name ${them(spliced.length)}.`
          + (settle.length === 1 && settle[0] != null ? ` \`specs/plan/overdue.json\` records ${them(spliced.length)}, to be settled by Day ${settle[0]}.` : "") + ` Graph 12 lists ${them(spliced.length)} under "should be covered by now".` },
      ...cls("unreplayable").map(c => ({ ids: [c.id], b: one(c), text: `${c.cells.length === 1 ? "Its only criterion in force is" : "Its criteria in force are"} ${andList(c.cells.map(q => q.id))}, which the replay cannot run.` })),
      ...by(c => c.cls === "unproved" ? c.cells.map(q => q.id).join(" ") : null).map(([k, list]) => ({ ids: list.map(c => c.id), b: `${ids(list)}.`,
        text: k.includes(" ") ? `The criteria in force that name ${them(list.length)} (${andList(k.split(" "))}) hold, but none of their tests was ever seen to fail.`
          : `The only criterion in force that names ${them(list.length)}, ${k}, holds, but its test was never seen to fail.` })),
      ...["repair", "fails", "unbuilt"].flatMap(k => cls(k).map(c => ({ ids: [c.id], b: one(c), text: `${says[k]} Its criteria in force: ${andList(c.cells.map(q => q.id))}.` }))),
      ...[...new Set(cols.filter(c => c.cls === "proved").flatMap(c => c.cells.filter(weak).map(q => q.id)))].map(id => {
        const on = cols.filter(c => c.cls === "proved" && c.cells.some(q => q.id === id)), q = on[0].cells.find(z => z.id === id);
        return { ids: on.map(c => c.id), b: `${id}, on ${ids(on)}.`, text: `Day ${q.day}'s criterion: ${WORD[q.state] || q.state}. ${ids(on)} still ${on.length === 1 ? "reaches" : "reach"} proved code through other criteria.` }; }),
      ...ring.filter(q => !q.gone && weak(q)).map(q => ({ ids: [], b: `${q.id}, on the ring.`, text: `Day ${q.day}'s criterion: ${WORD[q.state] || q.state}. It names no commitment, so no band of the plan shows it.` })),
      part && { ids: cols.filter(c => c.sub === "part").map(c => c.id), b: `${plural(part, "commitment is", "commitments are")} proved in part.`,
        text: `${part === 1 ? "It is" : "Each is"} named by a proved criterion and by at least one that is not. ${part === 1 ? "It is the half bead" : "They are the half beads"}: ${cols.filter(c => c.sub === "part").map(c => c.id).join(", ")}.` },
      back.length && { ids: cols.filter(c => c.cells.some(q => q.back)).map(c => c.id), b: `${back.join(", ")}.`,
        text: `The replay once saw ${back.length === 1 ? "this criterion" : "each of these"} stop holding, or its recorded break stop applying, and ${back.length === 1 ? "it" : "each"} came back. ${back.length === 1 ? "It is" : "They are"} in force and ${back.length === 1 ? "holds" : "hold"} now; the edge is ${back.length === 1 ? "its" : "their"} history.` }].filter(Boolean);
    const rules = cols.filter(c => c.sub === "rule"), later = cols.filter(c => c.sub === "later"), gone = G.criteria - G.in_force;
    const expected = [rules.length && [plural(rules.length, "regulatory region", "regulatory regions"), `: ${ids(rules)}. Like promoters and switches in DNA, they never become protein: they are rules for how people work, which no test can check, and they steer the work without appearing in the product.`],
      later.length && [plural(later.length, "switched-off gene", "switched-off genes"), `, real genes that turn on later, when their Day writes the checks: ${later.map(c => c.owner_day != null ? `${c.id} (Day ${c.owner_day})` : `${c.id} (no Day yet)`).join(", ")}.`],
      gone && [`${gone} of the ${G.criteria} criteria ${gone === 1 ? "was" : "were"} replaced`, " by a later one. Their quotes are the hollow dashes. Most of what they named is still named by another criterion."]].filter(Boolean);
    const bends = [["Named is not done.", " A filled bead means a criterion that names the commitment holds and was proved. It does not mean the whole commitment is delivered."],
      spliced.length && [`The ${spliced.length === 1 ? "one" : spliced.length} spliced out ${spliced.length === 1 ? "is" : "are"} a reading of the \`Plan:\` lines.`, " Nobody has checked yet whether the replacing criteria still cover them in substance."],
      ["A criterion can quote several commitments.", ` ${plural(Q.criteria || 0, "criterion makes", "criteria make")} ${plural(G.quotes, "quote", "quotes")}, so one criterion is drawn once under each commitment it names.`],
      G.changed && ["A cell reads one way; this project does not.", ` When the code shows the plan is wrong, the plan is rewritten. Those are the triangles on the gene: ${plural(G.changed, "commitment", "commitments")} so far, over ${plural(G.rewrites, "plan change", "plan changes")}.`],
      ["No time.", " This is a cross-section at one commit. An edged cell says a criterion once stopped; the pointer says at which merge. When a criterion was written is on graph 12."],
      ["Tests and merges are in the pointer, not in the picture.", " A column is a few pixels wide, so a criterion's tests and the merges it cites show when you point at its cell."]].filter(Boolean);
    const read = { t: `${C.proved || 0} of ${total} commitments reach proved code`,
      b: [G.uncovered.length ? `${plural(G.uncovered.length, "commitment is", "commitments are")} due by Day ${G.closed_to} and named by no criterion in force: ${andList(G.uncovered)}. Graph 12's "should be covered by now" lists the same.`
        : `Every commitment due by Day ${G.closed_to} is named by a criterion in force.`,
        `${plural(G.criteria, "criterion", "criteria")} make ${plural(G.quotes, "quote", "quotes")} of the plan; ${G.in_force} of them are in force and make ${G.live_quotes}.`] };
    // the merges no criterion cites: the merge graph's own list (spec_drift_views.uncited_merges), so the two cannot differ
    const uncited = ((DATA.merge_graph || {}).uncited || []).map(u => ({ pr: u.pr, title: plain(u.title), prod: u.prod }));
    return { figs, cols, ring, off: (G.off || []).length, crit, rows, finds, expected, bends, total, stacks: G.stacks || { written: 0, cells: 0 }, read, uncovered: G.uncovered, uncited,
      table: { head: ["Commitment", "Section", "Reaches", "Criteria as written", "In force, and their state"],
        rows: cols.map(c => [`${c.id} · ${c.short}`, c.section, c.cls === "proved" ? `proved code (${c.sub === "full" ? "in full" : "in part"})` : c.cls === "untranscribed" ? `never transcribed (${{ rule: "regulatory", later: "switched off", due: "overdue" }[c.sub] || c.sub})` : c.cls === "spliced" ? "spliced out" : says[c.cls],
          c.written.map(q => q.id).join(", "), c.cells.map(q => `${q.id} ${q.state}${q.back ? ", came back" : ""}`).join("; ")]) } };
  }

  // The driver's steps are not measured until its run log is counted; a driver that has started no step is counted.
  function notMeasured(yard, clock, plan) {
    const I = DATA.infra || {}, steps = (DATA.driver_runs || {}).steps;
    return [!I.latest && !(I.runs || []).length && ["Infrastructure checks", "no run is recorded, so nothing is drawn."],
      !DATA.deployment && ["The live deployment", "no run is recorded, so nothing is drawn."],
      ...((yard.waiting || []).map(w => [w.name, `${w.why}.`])),
      !steps && ["Whether it runs without a person", "the driver's run log is not counted for this project yet. The maintainer's sessions count the run log beside run-steps.py into `driver-runs.json` on the dashboard-data branch (`scripts/publish-counts.py`)."],
      plan.empty && ["Whether the specs follow the plan", plan.empty],
      clock.empty && ["Where a date's time goes, and who waits for whom", clock.empty]].filter(Boolean);
  }

  // The quality score: scripts/spec_drift_score.py computes it from this same data; the page only draws it.
  function quality() {
    const S = DATA.score;
    if (!S || !S.all) return null;
    const view = (x, label) => x && { label, n: Math.round(x.score),
      parts: x.parts.map(p => ({ key: p.key, name: p.name, graph: p.graph, n: Math.round(p.pct), low: p.key === x.low })),
      rows: x.parts.flatMap(p => p.counts.map(c => [p.name, c.name, c.m ? `${c.n} of ${c.m}${c.note ? `, ${c.note}` : ""}` : c.note, Math.round(c.pct)])) };
    return { all: view(S.all, "the finished Days"),
      days: Object.fromEntries(Object.entries(S.days || {}).map(([d, x]) => [d, view(x, `Day ${d}`)])),
      abilities: Object.fromEntries(Object.entries(S.abilities || {}).filter(([, x]) => x)
        .map(([k, x]) => [k, { n: Math.round(x.score), parts: x.parts.map(p => `${p.name.toLowerCase()} ${Math.round(p.pct)}`).join(" · ") }])) };
  }

  const P = safe(promises), g2 = safe(yardGraph), g10 = safe(clockGraph), g12 = safe(planGraph), gene = safe(geneGraph), mrg = safe(mrgGraph);
  return { head: head(), days: days.map(d => ({ day: d.day, title: plain(d.title), closed: finished(d), active: d.day === current })),
    attention: attention(), quality: safe(quality), g6: safe(mergeGraph), g7: safe(sieveGraph), g1: safe(lookGraph), g2, g10, g12, gene, mrg, whr: safe(whrGraph), rdg: safe(rdgGraph), gel: safe(gelGraph), prt: safe(prtGraph), prf: safe(prfGraph), atp: safe(atpGraph), rng: safe(rngGraph), act: safe(actGraph), rfx: safe(rfxGraph),
    promises: P.error ? { counts: [] } : { counts: COUNTED.map(s => [s, P.n(P.tiles, s)]).filter(c => c[1]), total: P.counted(P.tiles),
      states: Object.fromEntries(Object.keys(STATES).map(s => [s, P.n(P.tiles, s)])) },
    caveats: (DATA.meta || {}).caveats || [], notMeasured: notMeasured(g2, g10, g12) };
}

/* ---------- one promise's excerpts, as the build read them ---------- */
const howHas = x => Boolean(x && x.text && !x.missing);
const howMissing = x => h("span", { class: "how-missing" }, `Missing from this build: ${(x && x.source) || "this excerpt"} (${(x && x.missing) || "not in this data"})`);
const howExcerpt = (x, caption) => h("figure", { class: "how-ex" }, h("figcaption", null, caption), howHas(x) ? h("pre", null, x.text) : howMissing(x));
// howRecheck is drawn nowhere on the page. It is kept, with the three helpers above that it calls, for
// S-how-follows-newest-day.2 (specs/changes/how-follows-newest-day.md) until a Day's spec replaces that criterion.
function howRecheck(x, id) {
  if (!howHas(x)) return howExcerpt(x, "The latest re-check");
  if (!x.text.checks.length) return h("figure", { class: "how-ex" }, h("figcaption", null, id), h("pre", null, "not re-checked yet"));
  return h("figure", { class: "how-ex" }, h("figcaption", null, `${id} at its latest re-check${x.text.pr ? `, the merge of PR #${x.text.pr}` : ""}`),
    h("pre", null, x.text.checks.map((c, i) => [i ? "\n" : null, `${c.check} → `, h("span", { class: "put" }, c.state)])));
}
// The repository's files on GitHub, from the URL the build read (meta.repo_url); with none, the page links to none of them.
const howBlob = DATA => { const u = ((DATA || {}).meta || {}).repo_url; return u ? `${u.replace(/\/+$/, "")}/blob/main/` : null; };

/* ---------- the page: the model, drawn ---------- */
// Every string from the data reaches the page as a text node: a PR title or a spec's words are never parsed as HTML.
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  Object.entries(attrs || {}).forEach(([k, v]) => {
    if (v == null || v === false) return;
    if (k === "class") e.className = v; else if (k === "style") e.style.cssText = v; else e.setAttribute(k, v === true ? "" : v);
  });
  kids.flat(Infinity).forEach(c => { if (c != null && c !== false) e.append(c); });
  return e;
}

// A name a spec or a note put in backticks is drawn as code; the rest stays text.
const rich = s => String(s).split("`").map((part, i) => i % 2 ? h("code", null, part) : part);

/* Graph 12's two drawings, ported from the by-script mockup: the plan as one banded bar with a row per Day above
   it, and the ladder of commitments with a lane per Day. Same layout, marks and colours (the --c-* tokens on
   #g12); only the data is the page's. */
const SVG_NS = "http://www.w3.org/2000/svg";
const svgEl = (svg, n, a, txt, parent) => { const e = document.createElementNS(SVG_NS, n); for (const k in a) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; (parent || svg).appendChild(e); return e; };
const tipAt = (tip, fig, ev, w) => {
  const b = fig.getBoundingClientRect(); let px = ev.clientX - b.left + 14; if (px + w + 10 > b.width) px = ev.clientX - b.left - w - 14;
  tip.style.left = Math.max(4, px) + "px"; tip.style.top = (ev.clientY - b.top + 16) + "px";
};
const PC_WORD = { kept: "kept", reworded: "reworded, same commitment", changed: "changed", dropped: "dropped" };
const PC_KNAME = { unplanned: "new work that no commitment asks for", guard: "safety check: keeps earlier work intact, builds nothing" };

function planBar(m, box, tip, panel, forDays, resets) {
  const G = m.chart, C = G.C, UN = G.un;
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "pc-svg"); svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `The plan drawn as one banded bar: ${G.ref.length} commitments of the original plan, then ${G.added.length} added later, then the criteria that name none. One row per Day above it marks the commitments each Day's criteria name.`);
  const el = (n, a, txt, parent) => svgEl(svg, n, a, txt, parent);
  const UKIND = { later: "No criterion yet: the plan gives this to a later Day", standing: "No criterion: a rule about people, which no test can check", due: "Should be covered by now: no criterion checks it" };
  const USW = { later: "empty", standing: "st", due: "due" };
  const KFILL = { unplanned: "var(--c-unpl)", guard: "var(--c-guard)" };
  const PN = {}; G.ref.forEach(p => PN[p.id] = p); G.added.forEach(p => PN[p.id] = p);

  // one slot per band: the first plan's commitments, the added ones, then the criteria that name none
  const slots = [];
  const mk = (arm, p, fill) => {
    const per = {};
    C.forEach(c => c.links.forEach(l => { if (l.p === p.id) (per[c.day] = per[c.day] || []).push({ c, l }); }));
    slots.push({ arm, id: p.id, short: p.short, p, per, fill, n: Object.values(per).flat().length });
  };
  G.ref.forEach(p => mk("ref", p, "var(--c-in)"));
  G.added.forEach(p => mk("add", p, "var(--c-out)"));
  ["unplanned", "guard"].forEach(k => C.filter(c => c.kind === k).forEach(c => slots.push({ arm: "off", id: c.id, short: c.what, c, per: { [c.day]: [{ c }] }, fill: KFILL[k], n: 0 })));

  const X0 = 62, U = 5, CEN = 12, GAP = 20, T0 = 26, RH = 13, CH = 26, RW = G.rw,
    rowY = i => T0 + i * RH + 6 * RW.filter(d => d <= i).length, CY = rowY(G.days.length) + 6;
  const arms = {}; let x = X0, prev = null;
  slots.forEach(s => {
    if (prev && s.arm !== prev) x += prev === "ref" ? CEN : GAP;
    if (!arms[s.arm]) arms[s.arm] = { x0: x, n: 0 };
    s.x = x; x += U; arms[s.arm].x1 = x; arms[s.arm].n++; prev = s.arm;
  });
  const SW = 2.5, W = x + 128, SX = x + 40, maxN = Math.max(1, ...slots.filter(s => s.arm === "ref").map(s => s.n));
  const mid = a => (arms[a].x0 + arms[a].x1) / 2;
  if (arms.ref) el("text", { x: mid("ref"), y: 14, "text-anchor": "middle", class: "strong" }, `The original plan · ${arms.ref.n} commitments`);
  if (arms.add) el("text", { x: mid("add"), y: 14, "text-anchor": "middle", class: "strong" }, `Added later · ${arms.add.n}`);
  if (arms.off) el("text", { x: mid("off"), y: 14, "text-anchor": "middle", class: "strong" }, `Criteria no commitment asks for · ${arms.off.n}`);
  el("text", { x: SX - 18, y: 14, class: "strong" }, "Criteria per Day");
  RW.forEach(d => el("line", { x1: X0, x2: SX + 84, y1: rowY(d) - 3, y2: rowY(d) - 3, stroke: "var(--c-out)", "stroke-width": 1, "stroke-dasharray": "4 3" }));
  el("text", { x: W - 6, y: CY + CH + 20, "text-anchor": "end", class: "strong" }, `Quotes checked · ${comma(G.quotes)}`);
  el("text", { x: W - 6, y: CY + CH + 34, "text-anchor": "end", class: "faint" }, "each one found in its commitment's text");
  el("text", { x: W - 6, y: CY + CH + 47, "text-anchor": "end", class: "faint" }, "checked again on every pull request");

  let sel = null;
  const rowEls = {}, KORD = [["ref", "var(--c-in)"], ["later", "var(--c-out)"], ["unplanned", "var(--c-unpl)"], ["guard", "var(--c-guard)"]];
  G.days.forEach((d, i) => {
    const y = rowY(i), g = el("g", { class: "trk" }); rowEls[d] = g; forDays(g, [d]);
    const hitr = el("rect", { class: "dhit", x: 2, y, width: X0 - 6, height: RH, rx: 3, tabindex: 0, role: "button", "aria-label": `Day ${d}: show only this Day` }, null, g);
    el("text", { class: "dlab", x: X0 - 8, y: y + 10.5, "text-anchor": "end" }, "Day " + d, g);
    Object.values(arms).forEach(a => el("rect", { x: a.x0, y: y + 1, width: a.x1 - a.x0, height: RH - 2, rx: 2, fill: "var(--c-grid)", "fill-opacity": .4 }, null, g));
    slots.forEach(s => {
      const l = s.per[d]; if (!l) return;
      const k = s.arm === "off" ? 1 : l.length;
      const a = { x: s.x + .75, y: y + 2, width: U - 1.5, height: RH - 4, rx: 1.2, fill: s.fill, "fill-opacity": Math.min(.4 + k * .3, 1) };
      if (s.arm === "off" && s.c.kind === "guard") { a.stroke = "var(--muted)"; a["stroke-width"] = .75; }
      el("rect", a, null, g);
    });
    const cs = C.filter(c => c.day === d);
    el("text", { x: SX - 5, y: y + 10.5, "text-anchor": "end", class: "num" }, cs.length, g);
    let sx = SX;
    KORD.forEach(([k, f]) => {
      const n = cs.filter(c => c.kind === k).length; if (!n) return;
      const a = { x: sx, y: y + 3, width: n * SW, height: RH - 6, fill: f }; if (k === "guard") { a.stroke = "var(--muted)"; a["stroke-width"] = .5; }
      el("rect", a, null, g); sx += n * SW;
    });
    const pick = () => { sel = sel && sel.day === d ? null : { day: d }; draw(); };
    hitr.addEventListener("click", pick);
    hitr.addEventListener("keydown", ev => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); pick(); } });
  });

  // the bar itself: two arms pinched together, and the loose piece
  const defs = el("defs", {}), gb = {};
  const pat = (id, rot, col, w, step) => { const q = el("pattern", { id, width: step, height: step, patternUnits: "userSpaceOnUse", patternTransform: `rotate(${rot})` }, null, defs); el("rect", { x: 0, y: 0, width: step, height: w, fill: col }, null, q); };
  pat("g12-due", 45, "var(--c-unpl)", 2, 4.5); pat("g12-st", 0, "var(--muted)", 1, 4);
  Object.keys(arms).forEach(a => {
    const r = { x: arms[a].x0, y: CY, width: arms[a].x1 - arms[a].x0, height: CH, rx: a === "off" ? 7 : 11 };
    el("rect", r, null, el("clipPath", { id: "g12-cp-" + a }, null, defs));
    gb[a] = el("g", { "clip-path": `url(#g12-cp-${a})` });
    el("rect", Object.assign({ fill: "var(--card)" }, r), null, gb[a]);
  });
  slots.forEach(s => {
    let fill = s.fill, op = 1;
    if (s.arm !== "off") {
      s.u = s.n ? null : UN[s.id]; const k = s.u && s.u.kind;
      if (s.arm === "ref") { fill = s.n ? "var(--ink)" : k === "due" ? "url(#g12-due)" : k === "standing" ? "url(#g12-st)" : "var(--card)"; op = s.n ? .14 + .86 * Math.sqrt(s.n / maxN) : 1; }
      else if (k === "due" || k === "standing") fill = `url(#g12-${k === "due" ? "due" : "st"})`;
      else op = s.n ? Math.min(.55 + .2 * s.n, 1) : .13;
      // A commitment no criterion names yet, owned by a later Day: white with a dotted outline, not the empty grey.
      if (k === "later") { fill = "var(--card)"; op = 1; }
    }
    s.band = el("rect", { class: "band", x: s.x, y: CY, width: U, height: CH, fill, "fill-opacity": op, stroke: "var(--card)", "stroke-width": .6 }, null, gb[s.arm]);
    if (s.u && s.u.kind === "later") el("rect", { x: s.x + .5, y: CY + .5, width: U - 1, height: CH - 1, fill: "none", stroke: "var(--muted)", "stroke-width": .7, "stroke-dasharray": "1 1.2" }, null, gb[s.arm]);
    const cx = s.x + U / 2;
    if (s.arm === "ref" && s.p.status === "changed") el("path", { d: `M${cx} ${CY + CH + 2} l-3 5.5 h6 z`, fill: "var(--c-out)" });
    if (s.arm === "ref" && s.p.status === "reworded") el("path", { d: `M${cx} ${CY + CH + 2.5} l-2.6 5 h5.2 z`, fill: "var(--card)", stroke: "var(--c-out)", "stroke-width": 1 });
  });
  Object.keys(arms).forEach(a => el("rect", { x: arms[a].x0, y: CY, width: arms[a].x1 - arms[a].x0, height: CH, rx: a === "off" ? 7 : 11, fill: "none", stroke: "var(--c-line)", "stroke-width": 1 }));
  if (arms.ref && arms.add) {
    const ca = arms.ref.x1 - 1, cb = arms.add.x0 + 1, cm = (ca + cb) / 2, cy = CY + CH / 2;
    el("polygon", { points: `${ca},${CY + 5} ${cm},${cy - 2} ${cb},${CY + 5} ${cb},${CY + CH - 5} ${cm},${cy + 2} ${ca},${CY + CH - 5}`, fill: "var(--muted)" });
  }

  // the plan's sections under each arm: a tick per group, and a horizontal label cut to the group's width with its whole
  // name in a title; a group narrower than 24 px gets its tick only
  const by = CY + CH + 21, ly = by + 12, SECW = 5.8;  // a 10.5 px label's letter, a little over its average; fit() keeps 5 px between labels
  const fit = (name, w) => name.length * SECW <= w - 5 ? name : `${name.slice(0, Math.max(1, Math.floor((w - 5) / SECW) - 1))}…`;
  ["ref", "add"].forEach(arm => {
    const secs = [];
    slots.filter(s => s.arm === arm).forEach(s => { const l = secs[secs.length - 1]; if (l && l.name === s.p.sec) l.x1 = s.x + U; else secs.push({ name: s.p.sec, x0: s.x, x1: s.x + U }); });
    for (let i = secs.length - 1; i > 0; i--) if (secs[i].x1 - secs[i].x0 === U && secs[i - 1].x1 - secs[i - 1].x0 === U) { secs[i - 1].name += " · " + secs[i].name; secs[i - 1].x1 = secs[i].x1; secs.splice(i, 1); }
    secs.forEach(s => {
      const c = (s.x0 + s.x1) / 2, w = s.x1 - s.x0;
      el("line", { x1: s.x0 + 1, x2: s.x1 - 1, y1: by, y2: by, stroke: "var(--muted)", "stroke-width": 1.5 });
      el("line", { x1: c, x2: c, y1: by + 1, y2: ly - 5, stroke: "var(--muted)", "stroke-width": .75 });
      if (w >= 24) el("title", {}, s.name, el("text", { x: s.x0, y: ly, class: "faint", style: "font-size:10.5px" }, fit(s.name, w)));
    });
  });
  const H = Math.ceil(Math.max(ly, CY + CH + 47) + 8);  // the quotes' last line sits inside the box too
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);

  // what needs a look: each chip is a set of bands
  const FILT = [
    ["due", "Should be covered by now, is not", s => s.arm !== "off" && s.u && s.u.kind === "due", "The promise file gives this commitment to a Day that is closed, and no criterion names it."],
    ["none", "No criterion yet", s => s.arm !== "off" && !s.n, "No Plan: line names this commitment."],
    ["thin", "Held by a single criterion", s => s.arm !== "off" && s.n === 1, "One criterion is all that names this commitment."],
    ["changed", "Rewritten by the plan later", s => s.arm === "ref" && s.p.status === "changed", "The plan rewrote this commitment after some Days had already built on the old wording."]];
  const chips = FILT.map(([k, name, f]) => {
    const b = h("button", { type: "button", class: "pc-chip", "aria-pressed": "false" }, `${name} `, h("b", null, String(slots.filter(f).length)));
    b.addEventListener("click", () => { sel = sel && sel.filt === k ? null : { filt: k }; draw(); });
    return b;
  });

  // hover and click, one column per band; the tip and the panel are built as nodes, data put in as text
  const fig = tip.parentElement;
  const selbox = el("rect", { y: T0 - 2, width: U + 2, height: CY + CH - T0 + 4, rx: 2, fill: "none", stroke: "var(--ink)", "stroke-width": 1.5, "pointer-events": "none", visibility: "hidden" });
  const state = s => s.arm === "off" ? `Day ${s.c.day} · ${PC_KNAME[s.c.kind]}`
    : s.n ? `${s.n} ${s.n === 1 ? "criterion names it" : "criteria name it"}`
    : s.u ? UKIND[s.u.kind] + (s.u.when && s.u.kind !== "standing" ? ` (${s.u.when})` : "")
    : s.arm === "add" ? "No criterion names it"
    : "No criterion names it; the promise file gives it no owner Day";
  slots.forEach(s => {
    const r = el("rect", { class: "chit", x: s.x, y: T0 - 2, width: U, height: CY + CH - T0 + 4 });
    r.addEventListener("pointermove", ev => {
      const change = s.arm === "ref" && s.p.status === "changed" ? "The plan changed it later" : s.arm === "ref" && s.p.status === "reworded" ? "The plan reworded it later, same commitment" : null;
      tip.replaceChildren(h("b", null, s.id), ` · ${s.short}`, h("br"), state(s), change ? h("br") : "", change || "");
      tip.hidden = false; tipAt(tip, fig, ev, 300);
    });
    r.addEventListener("pointerleave", () => { tip.hidden = true; });
    r.addEventListener("click", () => { sel = sel && sel.slot === s ? null : { slot: s }; draw(); });
  });

  const lk = l => h("span", null, h("i", null, l.p), PN[l.p] ? PN[l.p].short : "");
  const critRow = c => h("div", { class: "pc-crit" }, h("span", { class: "cid" }, c.id), h("span", { class: "what" }, c.what),
    c.links.length ? h("span", { class: "pr" }, c.links.map(lk)) : null);
  const goTo = (q, ...kids) => { const b = h("button", { type: "button" }, h("i", null, q.id), q.short, ...kids); b.addEventListener("click", () => { sel = { slot: q }; draw(); }); return b; };
  const KL = [["ref", "var(--c-in)", "Name a commitment of the original plan"], ["later", "var(--c-out)", "Name only commitments added later"], ["unplanned", "var(--c-unpl)", "New work no commitment asks for"], ["guard", "var(--c-guard)", "Safety checks"]];
  const sub = (...k) => h("div", { class: "sub" }, ...k), grp = (...k) => h("div", { class: "grp" }, ...k), ptext = (...k) => h("p", { class: "ptext" }, ...k);
  function draw() {
    const d = sel && sel.day, s = sel && sel.slot, fk = sel && sel.filt, F = fk && FILT.find(f => f[0] === fk);
    Object.entries(rowEls).forEach(([k, g]) => { g.style.opacity = d && +k !== d ? .18 : 1; g.classList.toggle("sel", +k === d); });
    slots.forEach(t => { t.band.style.opacity = d && !t.per[d] ? .1 : F && !F[2](t) ? .1 : 1; });
    FILT.forEach((f, i) => chips[i].setAttribute("aria-pressed", String(f[0] === fk)));
    selbox.setAttribute("visibility", s ? "visible" : "hidden"); if (s) selbox.setAttribute("x", s.x - 1);
    const t = [];
    if (F) {
      const l = slots.filter(F[2]);
      t.push(h("h3", null, `${F[1]} · ${l.length}`), sub(`${F[3]} Click one to read it.`), h("div", { class: "pc-plist" }, l.map(q => goTo(q))));
    } else if (d) {
      const cs = C.filter(c => c.day === d), cnt = k => cs.filter(c => c.kind === k).length, on = a => slots.filter(q => q.arm === a && q.per[d]);
      const ls = cs.flatMap(c => c.links);
      t.push(h("h3", null, `Day ${d}: ${cs.length} criteria`), sub(`This Day's Plan: lines make ${ls.length} links to commitments, and every quote is found in its commitment. ${cnt("ref")} criteria serve the original plan, ${cnt("later")} only commitments added later, ${cnt("unplanned")} are new work no commitment asks for, ${cnt("guard")} are safety checks.`));
      [["ref", "Commitments of the original plan"], ["add", "Commitments added later"]].forEach(([a, name]) => {
        const l = on(a); if (!l.length) return;
        t.push(grp(`${name} · ${l.length}`), h("div", { class: "pc-plist" }, l.map(q => goTo(q, h("b", null, String(q.per[d].length))))));
      });
      KL.forEach(([k, f, name]) => { const l = cs.filter(c => c.kind === k); if (!l.length) return; t.push(grp(h("i", { class: "pc-sw", style: `background:${f}` }), `${name} · ${l.length}`), l.map(critRow)); });
    } else if (s && s.arm === "off") {
      const c = s.c;
      t.push(h("h3", null, `${c.id} · Day ${c.day}`), sub(`${PC_KNAME[c.kind]} · tagged ${c.tag}`), ptext(c.what), ptext(h("code", null, "Plan: none")));
    } else if (s) {
      t.push(h("h3", null, `${s.id} · ${s.short}`), sub((s.arm === "ref" ? `${s.p.sec} · the plan today: ${PC_WORD[s.p.status] || s.p.status}` : `Added by a later plan change, under "${s.p.sec}"`) + ` · ${state(s)}`), ptext(s.p.promise));
      if (s.p.note) t.push(ptext(h("b", null, "What changed:"), ` ${s.p.note}`));
      const ds = Object.keys(s.per).map(Number).sort((a, b) => a - b);
      ds.forEach(k => t.push(grp(`Day ${k} · ${s.per[k].length}`), s.per[k].map(q => h("div", { class: "pc-crit" }, h("span", { class: "cid" }, q.c.id), h("span", { class: "what" }, q.c.what),
        q.l.quote ? h("span", { class: "why" }, h("code", null, `Plan: ${s.id} "${q.l.quote}"`), " · the quote is in the commitment") : null))));
      if (!ds.length && s.u) t.push(grp(h("i", { class: `pc-sw ${USW[s.u.kind]}` }), UKIND[s.u.kind] + (s.u.when ? ` · ${s.u.when}` : "")),
        ptext("From two fields of the promise file: the Day the plan gives the commitment to, and a flag for rules about people. The script compares that Day with the Days that are closed."));
      else if (!ds.length) t.push(sub("No Plan: line names this commitment." + (s.arm === "ref" ? " The promise file gives it no owner Day yet, so the script cannot say whether it is late." : "")));
    } else t.push(h("h3", null, rich(m.read.t)), m.read.b.map(b => sub(rich(b))), sub("Click a button above, a stripe, or a Day's name."));
    panel.replaceChildren(...t.flat());
  }
  box.replaceChildren(h("div", { class: "pc-chiprow" }, h("span", { class: "pc-lg" }, "Show only"), chips), legendBar(), h("div", { class: "scroll-x" }, svg));
  resets.push(() => { sel = null; draw(); });
  draw();
}

// The bar's legend, as the mockup has it: four labelled rows, folded under a summary so the chips above stay the first thing read.
function legendBar() {
  const sw = (cls, style) => h("i", { class: `pc-sw ${cls || ""}`, style: style || null });
  const row = (label, items) => h("div", { class: "pc-legend" }, h("span", { class: "pc-lg" }, label), items.map(([k, t]) => h("span", null, k, t)));
  const tri = (fill) => { const s = document.createElementNS(SVG_NS, "svg"); s.setAttribute("class", "pc-glyph"); s.setAttribute("viewBox", "0 0 12 10"); s.setAttribute("width", "12"); s.setAttribute("height", "10");
    svgEl(s, "path", { d: "M6 1.5 L10.5 9 H1.5 Z", fill: fill ? "var(--c-out)" : "none", stroke: "var(--c-out)", "stroke-width": 1.2 }); return s; };
  const dash = () => { const s = document.createElementNS(SVG_NS, "svg"); s.setAttribute("class", "pc-glyph"); s.setAttribute("viewBox", "0 0 24 10"); s.setAttribute("width", "24"); s.setAttribute("height", "10");
    svgEl(s, "line", { x1: 0, x2: 24, y1: 5, y2: 5, stroke: "var(--c-out)", "stroke-dasharray": "4 3" }); return s; };
  return h("details", { class: "pc-key" }, h("summary", null, "Key: what each colour and sign means"),
    row("The long bar", [[h("i", { class: "pc-grad" }), "one stripe per commitment: the darker, the more criteria name it"], [sw("empty"), "no criterion names it (a stripe of the bar)"],
      [sw("later"), "no criterion yet, owned by a later Day"], [sw("st"), "a rule about people, which no test can check"], [sw("due"), "should be covered by now, and is not"]]),
    row("Marks in a row", [[sw("", "background:var(--c-in)"), "a criterion of this Day names a commitment of the original plan"], [sw("", "background:var(--c-out)"), "names one added later"],
      [sw("", "background:var(--c-unpl)"), "new work, Plan: none"], [sw("", "background:var(--c-guard);border:1px solid var(--muted)"), "safety check (Plan: none, a row mark)"]]),
    row("Signs under the bar", [[tri(true), "the plan later rewrote this commitment"], [tri(false), "reworded only, same meaning"]]),
    row("Dashed line", [[dash(), "the plan was rewritten between these two Days"]]));
}

function planLadder(G, box, tip) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "pc-svg"); svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", `The original plan's ${G.ref.length} commitments as a ladder, today's plan and each Day as lanes beside it, and zones underneath for commitments added later and for criteria that name none.`);
  const el = (n, a, txt) => svgEl(svg, n, a, txt);
  const nd = G.days.length, RH = 13, LAD = 158, PLN = 204, D0 = 256, DW = 26, TX = D0 + nd * DW + 24, W = TX + 400;
  const dayX = d => D0 + G.days.indexOf(d) * DW;
  const lanes = [[LAD, 40], [PLN, 40]].concat(G.days.map(d => [dayX(d), DW - 4]));
  const bg = lanes.map(([x, w]) => el("rect", { x, y: 36, width: w, height: 10, rx: 4, fill: "var(--c-grid)", "fill-opacity": .45 }));
  el("text", { x: LAD + 20, y: 28, "text-anchor": "middle", class: "strong" }, "Ladder");
  el("text", { x: PLN + 20, y: 28, "text-anchor": "middle", class: "strong" }, "Today");
  el("text", { x: D0 + (nd / 2) * DW - 2, y: 12, "text-anchor": "middle", class: "faint" }, "Day");
  G.days.forEach(d => el("text", { x: dayX(d) + (DW - 4) / 2, y: 28, "text-anchor": "middle", class: "num strong" }, d));
  const fig = tip.parentElement;
  const hit = (y, hh, lines) => {
    const r = el("rect", { x: 0, y, width: W, height: hh, class: "hit" });
    r.addEventListener("pointermove", ev => { tip.replaceChildren(...lines.flatMap((l, i) => i ? [h("br"), l] : [l]).flat()); tip.hidden = false; tipAt(tip, fig, ev, 340); });
    r.addEventListener("pointerleave", () => { tip.hidden = true; });
  };
  const band = (x, w, y, fill, op) => el("rect", { x: x + 3, y: y - 2.5, width: w - 6, height: 5, rx: 2, fill, "fill-opacity": op == null ? 1 : op });
  const label = (y, id, text) => { el("text", { x: TX, y: y + 4, class: "num faint" }, id); el("text", { x: TX + 46, y: y + 4, style: "font-size:11px" }, text); };
  const served = id => { const per = {}; G.C.forEach(c => { if (c.links.some(l => l.p === id)) (per[c.day] = per[c.day] || []).push(c); }); return per; };

  let y = 50, sec = null;
  G.ref.forEach(p => {
    if (p.sec !== sec) { y += sec === null ? 0 : 9; sec = p.sec; el("text", { x: 150, y: y + 4, "text-anchor": "end", class: "faint", style: "font-size:10px" }, sec.length > 27 ? sec.slice(0, 26) + "…" : sec); }
    band(LAD, 40, y, "var(--ink-2)");
    if (p.status !== "dropped") band(PLN, 40, y, p.status === "changed" ? "var(--c-out)" : "var(--ink-2)", p.status === "reworded" ? .45 : 1);
    const per = served(p.id), ds = Object.keys(per).map(Number).sort((a, b) => a - b);
    ds.forEach(d => band(dayX(d), DW - 4, y, "var(--c-in)", Math.min(.5 + per[d].length * .17, 1)));
    if (!ds.length) el("circle", { cx: D0 + nd * DW + 6, cy: y, r: 3, fill: "var(--card)", stroke: "var(--ink)", "stroke-width": 1.5 });
    label(y, p.id, p.short);
    hit(y - RH / 2, RH, [h("b", null, `${p.id} · ${p.short}`), p.promise, [h("b", null, "Plan today:"), ` ${PC_WORD[p.status] || p.status}${p.note ? ". " + p.note : ""}`],
      ...(ds.length ? ds.map(d => [h("b", null, `Day ${d}:`), ` ${per[d].map(c => c.id).join(", ")}`]) : [h("b", null, "No criterion names it.")])]);
    y += RH;
  });
  const zone = title => { y += 16; el("line", { x1: 0, x2: W, y1: y, y2: y, stroke: "var(--muted)", "stroke-width": 1, "stroke-dasharray": "4 4" }); y += 18; el("text", { x: 4, y, class: "strong" }, title); y += 16; };

  zone("Off the ladder: commitments added by later plan changes");
  el("text", { x: 4, y: y - 2, class: "faint" }, "A band here is a Day with a criterion that names the added commitment.");
  y += 10;
  G.added.forEach(a => {
    band(PLN, 40, y, "var(--c-out)");
    const per = served(a.id), cs = Object.values(per).flat();
    Object.entries(per).forEach(([d, l]) => band(dayX(+d), DW - 4, y, "var(--c-in)", Math.min(.5 + l.length * .17, 1)));
    label(y, a.id, a.short);
    hit(y - RH / 2, RH, [h("b", null, `${a.id} · ${a.short}`), a.promise, `Added under "${a.sec}".`,
      ...(cs.length ? cs.map(c => [h("b", null, c.id), ` (Day ${c.day}): ${c.what}`]) : ["No criterion names it."])]);
    y += RH;
  });

  zone("Off the ladder: criteria that name no commitment");
  G.C.filter(c => !c.links.length).forEach(c => {
    band(dayX(c.day), DW - 4, y, "var(--c-in)", .85);
    label(y, c.id.replace(/^C0?/, "C"), c.what.length > 44 ? c.what.slice(0, 43) + "…" : c.what);
    hit(y - RH / 2, RH, [h("b", null, c.id), c.what, PC_KNAME[c.kind] || ""]);
    y += RH;
  });

  zone("Against the ladder: criteria that contradict a commitment");
  el("text", { x: TX, y: y + 4, style: "font-size:11px" }, "empty by design: no script can tell that a criterion contradicts a commitment"); y += RH;
  y += 8;
  bg.forEach(r => r.setAttribute("height", y - 36));
  svg.setAttribute("viewBox", `0 0 ${W} ${y + 8}`);
  box.replaceChildren(h("div", { class: "scroll-x" }, svg));
}

/* The gene, drawn: the plan as two banded arms, each criterion's quotes under the commitment it names, the splice,
   the commitments still named closed up, a cell per criterion in force, and the code as a row of beads; the criteria
   off the plan as a ring beside it. Layout only: every class, state and count comes from the model. The marks carry
   data-p (a commitment) and data-c (a criterion), which the pointer follows. Colours are in dashboard.css, under #gene. */
const GENE_CELL = { proven: "proved", unproven: "unproved", skipped: "norun", repair: "stale", broken: "broken" };
const GENE_BEAD = { unproved: "unproved", unreplayable: "norun", repair: "stale", fails: "broken", unbuilt: "unbuilt" };
function geneDraw(m, box, tip, forDays) {
  const svg = document.createElementNS(SVG_NS, "svg"), el = (n, a, txt, parent) => svgEl(svg, n, a, txt, parent);
  const cols = m.cols, U = 6.4, P = 7.85, X0 = 150, DASH = 4.4, CELL = 4.6, r1 = n => Math.round(n * 10) / 10;
  // where each band stands: one slot is left between two sections, with a thin line in it, and two where the plan's
  // second arm begins, with no line: the arms are two caps
  const X = [], XL = [], live = cols.map((c, i) => i).filter(i => cols[i].cells.length), at = new Map(live.map((i, k) => [i, k]));
  cols.forEach((c, i) => { const p = cols[i - 1]; X.push(i ? X[i - 1] + P + (c.arm !== p.arm ? 2 * P : c.section !== p.section ? P : 0) : X0); });
  live.forEach((i, k) => { const c = cols[i], p = cols[live[k - 1]]; XL.push(k ? XL[k - 1] + P + (c.arm !== p.arm || c.section !== p.section ? P : 0) : X0); });
  const right = X[X.length - 1] + U, liveRight = live.length ? XL[XL.length - 1] + U : X0, mid = i => X[i] + U / 2;
  const Y = { band: 186, dash: 218 };
  Y.rep = Math.max(300, Y.dash + m.stacks.written * DASH + 16); Y.live = Y.rep + 78; Y.cell = Y.live + 12;
  Y.code = Math.max(Y.live + 86, Y.cell + m.stacks.cells * CELL + 10);
  const ring = m.ring.length, RX = Math.max(right - 40.5, liveRight + 150), RY = Y.live + 50, W = Math.max(ring ? Math.max(right + 111.5, RX + 152) : right + 24, 560);
  const shade = n => n >= 7 ? 4 : n >= 4 ? 3 : n >= 2 ? 2 : 1;
  const kind = q => q.gone ? "replaced" : q.tag === "hold" ? "hold" : "new", cell = q => `${GENE_CELL[q.state] || "unbuilt"}${q.back ? " scar" : ""}`;

  // the plan: each arm's name, its sections above it, and its bands inside a rounded cap
  const arms = ["first", "added"].map(a => [...cols.keys()].filter(i => cols[i].arm === a)).filter(a => a.length);
  let titled = 0;   // where the last arm's name ends, by a rough width: a short arm's name must not run into the next
  arms.forEach((a, k) => {
    const x0 = X[a[0]], x1 = X[a[a.length - 1]] + U, cap = { x: r1(x0 - 3), y: Y.band, width: r1(x1 - x0 + 6), height: 24, rx: 12 };
    const title = cols[a[0]].arm === "first" ? `The original plan · ${plural(a.length, "commitment", "commitments")}` : `Added later · ${a.length}`;
    el("text", { class: "t-arm", x: r1(Math.max(x0, titled)), y: 12 }, title); titled = Math.max(x0, titled) + title.length * 7.4 + 16;
    let from = a[0];
    a.forEach((i, j) => {
      const next = a[j + 1], name = cols[i].section;
      if (next != null && cols[next].section === name) return;
      const s0 = X[from], s1 = X[i] + U, c = (s0 + s1) / 2;
      el("path", { class: "brk", d: `M${r1(s0)} 172 H${r1(s1)} M${r1(c)} 172 V168` });
      el("text", { class: "t-sec", transform: `translate(${r1(c + 2)} 166) rotate(-52)` }, name.length > 38 ? `${name.slice(0, 37)}…` : name);
      from = next;
    });
    el("rect", cap, null, el("clipPath", { id: `gene-cap${k}` }));
    el("rect", { ...cap, class: "cap-bg" });
    const g = el("g", { "clip-path": `url(#gene-cap${k})` });
    // every band the same size, whatever it is: its fill alone says regulatory, switched off, overdue or how often named
    a.forEach((i, j) => {
      const c = cols[i], look = { rule: "rule", later: "notdue", due: "overdue" }[c.sub] || `gs${shade(c.written.length)}`;
      if (j && c.section !== cols[a[j - 1]].section) { const x = Math.round((X[a[j - 1]] + U + X[i]) * 50) / 100;
        el("line", { class: "secdiv", x1: x, x2: x, y1: Y.band, y2: Y.band + 24 }, null, g); }
      el("rect", { class: `b ${look}`, x: r1(X[i]), y: Y.band, width: U, height: 24, "data-p": c.id, "data-id": c.id, tabindex: 0, "aria-label": `${c.id} · ${c.short}: ${c.reach}` }, null, g);
    });
    el("rect", { ...cap, class: "cap" });
  });
  if (arms.length === 2) { const c = r1((X[arms[0][arms[0].length - 1]] + U + X[arms[1][0]]) / 2), y = Y.band;
    el("path", { class: "pinch", d: `M${r1(c - 9.55)} ${y + 5} L${c} ${y + 10} L${r1(c + 9.55)} ${y + 5} V${y + 19} L${c} ${y + 14} L${r1(c - 9.55)} ${y + 19} Z` }); }
  cols.forEach((c, i) => { if (c.change) el("path", { class: `tri ${c.change}`, "data-p": c.id, d: `M${r1(mid(i))} ${Y.band - 3} l4 -6.5 h-8 z` }); });

  // the criteria as written: one dash per quote, under the commitment it quotes; a name under each one that is overdue
  let lastX = -Infinity, step = 0;
  cols.forEach((c, i) => {
    c.written.forEach((q, k) => forDays(el("rect", { class: `rd ${kind(q)}`, "data-p": c.id, "data-c": q.id, x: r1(X[i]), y: r1(Y.dash + k * DASH), width: U, height: 3.2, rx: 1.4 }), [q.day]));
    if (c.sub !== "due") return;
    step = mid(i) - lastX < 70 ? step + 1 : 0; lastX = mid(i);
    el("text", { class: "t-id", "data-p": c.id, x: r1(mid(i)), y: r1(Y.dash + 24.2 + 12 * step), "text-anchor": "middle" }, `${c.id} overdue`);
  });

  // the splice: a box on the strand for each commitment ever named, a line down to where it stands among those still
  // named, and an arc over the ones that only replaced criteria name
  el("path", { class: "strand", d: `M${X0} ${Y.rep} H${r1(right)}` });
  cols.forEach((c, i) => {
    if (!c.written.length) return;
    const on = c.cells.length > 0;
    el("rect", { class: on ? "ex pre" : "ex skip", "data-p": c.id, "data-id": c.id, x: r1(X[i] + (on ? 0 : 0.5)), y: Y.rep - 5, width: on ? U : 5.4, height: 10, rx: 2 });
    if (on) el("path", { class: "fun", "data-p": c.id, d: `M${r1(mid(i))} ${Y.rep + 6} L${r1(XL[at.get(i)] + U / 2)} ${Y.live - 7}` });
  });
  const out = [...cols.keys()].filter(i => cols[i].cls === "spliced");
  out.forEach((i, k) => {
    if (k && X[i] - X[out[k - 1]] < 28) return;   // close enough to share the last one's arc and its name
    let j = k; while (out[j + 1] != null && X[out[j + 1]] - X[out[j]] < 28) j++;
    const a = mid(i) - 5.8, b = mid(out[j]) + 5.8;
    el("path", { class: "arc", d: `M${r1(a)} ${Y.rep - 6} Q${r1((a + b) / 2)} ${Y.rep - 30} ${r1(b)} ${Y.rep - 6}` });
    el("text", { class: "t-id", x: r1((a + b) / 2), y: Y.rep - 22, "text-anchor": "middle" }, out.slice(k, j + 1).map(z => cols[z].id).join(", "));
  });

  // the criteria in force, closed up: each commitment still named, a cell per criterion in force, and its code as a bead
  if (live.length) { el("path", { class: "strand", d: `M${X0} ${Y.live} H${r1(liveRight)}` }); el("path", { class: "bond", d: `M${r1(XL[0] + U / 2)} ${Y.code} H${r1(liveRight - U / 2)}` }); }
  lastX = -Infinity; step = 0;
  live.forEach((i, k) => {
    const c = cols[i], x = r1(XL[k]), cx = r1(XL[k] + U / 2);
    el("rect", { class: "ex mat", "data-p": c.id, "data-id": c.id, x, y: Y.live - 6, width: U, height: 12, rx: 2 });
    c.cells.forEach((q, j) => forDays(el("rect", { class: `tc ${cell(q)}`, "data-p": c.id, "data-c": q.id, x, y: r1(Y.cell + j * CELL), width: U, height: 3.4, rx: 1.4 }), [q.day]));
    el("path", { class: "tick", "data-p": c.id, d: `M${cx} ${r1(Y.cell + c.cells.length * CELL + 0.3)} V${Y.code - 5.5}` });
    el("circle", { class: `bead ${c.cls === "proved" ? (c.sub === "part" ? "part" : "proved") : GENE_BEAD[c.cls] || "unbuilt"}`, "data-p": c.id, "data-id": c.id, cx, cy: Y.code, r: 3.7 });
    if (c.cls === "proved") return;
    step = cx - lastX < 24 ? step + 1 : 0; lastX = cx;
    el("path", { class: "lead", d: `M${cx} ${Y.code + 5.5} V${Y.code + 6 + 11 * step}` });
    el("text", { class: "t-id", "data-p": c.id, x: cx, y: Y.code + 15 + 11 * step, "text-anchor": "middle" }, c.id);
  });

  // each strand's name down the left, with its counts: never closer than a line to the one above
  let floor = 0;
  const label = ([name, bio, lines], y) => { y = Math.max(y, floor);
    el("text", { class: "t-row", x: 0, y }, name); el("text", { class: "t-bio", x: 0, y: y + 13 }, bio.toUpperCase());
    lines.forEach((s, k) => el("text", { class: "t-n", x: 0, y: y + 27 + 13 * k }, s));
    floor = y + 45 + 13 * Math.max(0, lines.length - 1); return floor - 18; };
  label(m.rows.plan, 178); label(m.rows.written, 228); label(m.rows.splice, Y.rep - 2); label(m.rows.live, Y.live - 4); label(m.rows.tests, Y.live + 41);
  const H = Math.max(label(m.rows.code, Y.code + 28) + 32, ring ? RY + 162 : 0);

  // off the plan: a ring, the criteria that name no commitment by Day (outside), and the state of each one in force (inside)
  if (ring) {
    const days = new Set(m.ring.map(q => q.day)).size, u = 2 * Math.PI / (ring + days * 0.5), pad = Math.min(0.012, u * 0.1);
    const pt = (r, a) => `${r1(RX + r * Math.sin(a))} ${r1(RY - r * Math.cos(a))}`;
    const sector = (r, s, a0, a1) => { const big = a1 - a0 > Math.PI ? 1 : 0; return `M${pt(r, a0)} A${r} ${r} 0 ${big} 1 ${pt(r, a1)} L${pt(s, a1)} A${s} ${s} 0 ${big} 0 ${pt(s, a0)} Z`; };
    const name = (day, a0, a1) => el("text", { class: "t-day", x: r1(RX + 74.5 * Math.sin((a0 + a1) / 2)), y: r1(RY - 74.5 * Math.cos((a0 + a1) / 2) + 3), "text-anchor": "middle" }, `D${day}`);
    let a = 0.25 * u, day = null, start = a;
    m.ring.forEach(q => {
      if (q.day !== day) { if (day != null) { name(day, start, a); a += 0.5 * u; } day = q.day; start = a; }
      forDays(el("path", { class: `rd rg ${kind(q)}`, "data-c": q.id, d: sector(63, 52, a + pad, a + u - pad) }), [q.day]);
      if (!q.gone) forDays(el("path", { class: `rk ${cell(q)}`, "data-c": q.id, d: sector(49, 39.5, a + pad, a + u - pad) }), [q.day]);
      a += u;
    });
    name(day, start, a);
    const hollow = ring - m.off;
    [["t-big", 4, String(m.off)], ["t-n", 18, m.off === 1 ? "criterion" : "criteria"], ["t-row", 98, "Off the plan"], ["t-bio", 111, "A PLASMID"],
      ["t-n", 125, "criteria in force that name no commitment"], hollow && ["t-n", 138, `${hollow} more ${hollow === 1 ? "was" : "were"} replaced: the hollow arcs`]]
      .filter(Boolean).forEach(([cls, dy, s]) => el("text", { class: cls, x: r1(RX), y: RY + dy, "text-anchor": "middle" }, s));
    // under the ring, as the mockup has them: a bead for each merge that changed product code and that no criterion cites
    const U2 = m.uncited || [];
    if (U2.length) {
      const say = `${U2.length} ${U2.length === 1 ? "merge" : "merges"} no criterion cites`, x0 = RX - (12 * U2.length + 2 + 5.6 * say.length) / 2 + 4.4;
      U2.forEach((u, i) => el("circle", { class: "free", "data-m": u.pr, cx: r1(x0 + 12 * i), cy: RY + 146, r: 4.4 }));
      el("text", { class: "t-n", x: r1(x0 + 12 * (U2.length - 1) + 14), y: RY + 150 }, say);
    }
  }
  svg.setAttribute("viewBox", `0 0 ${r1(W)} ${r1(H)}`); svg.setAttribute("class", "fig"); svg.id = "gene-fig"; svg.setAttribute("role", "group");
  svg.setAttribute("aria-label", "The plan drawn as a gene, the criteria as its transcript, the code as its protein");
  svg.style.cssText = `min-width:${Math.round(Math.min(1080, W * 0.85))}px;max-width:${Math.round(W * 1.15)}px`;
  box.replaceChildren(svg);

  // the pointer: what a mark is, and every other mark of the same commitment or the same criterion lit
  const byId = new Map(cols.map(c => [c.id, c])), line = (cls, s) => h("div", { class: cls || null }, s);
  const fill = t => {
    const col = byId.get(t.dataset.p), c = m.crit[t.dataset.c], u = t.dataset.m && (m.uncited || []).find(x => String(x.pr) === t.dataset.m);
    if (u) { tip.replaceChildren(line("t", `#${u.pr}`), line("", u.title), line("st", `${plural(u.prod, "line", "lines")} of product code, cited by no criterion`)); return true; }
    if (c) { const q = col && col.written.find(z => z.id === t.dataset.c);
      tip.replaceChildren(line("t", c.head), line("", c.text), line("q", q ? `Names ${col.id} (${col.short})${q.quote ? `: “${q.quote}”` : ""}` : "Plan: none"), line("st", c.code), ...c.more.map(s => line("q", s))); }
    else if (col) tip.replaceChildren(...col.tip.map(([cls, s]) => line(cls, s)));
    return !!(c || col);
  };
  const place = (x, y) => { tip.hidden = false;
    const w = tip.offsetWidth, hgt = tip.offsetHeight, top = y + 18;
    tip.style.left = `${Math.max(8, Math.min(x + 14, innerWidth - w - 8))}px`; tip.style.top = `${top + hgt > innerHeight - 8 ? Math.max(8, y - hgt - 12) : top}px`; };
  const clear = () => { svg.classList.remove("foc", "focc"); svg.querySelectorAll(".lit").forEach(e => e.classList.remove("lit")); };
  const light = (sel, cls) => { clear(); const hit = svg.querySelectorAll(sel); if (!hit.length) return; hit.forEach(e => e.classList.add("lit")); svg.classList.add(cls); };
  const follow = t => t.dataset.c ? light(`[data-c="${t.dataset.c}"]`, "focc") : t.dataset.p ? light(`[data-p="${t.dataset.p}"]`, "foc") : clear();
  const hide = () => { tip.hidden = true; clear(); };
  svg.addEventListener("pointerover", e => { const t = e.target.closest("[data-c],[data-id],[data-m]"); if (t && fill(t)) { place(e.clientX, e.clientY); follow(t); } else hide(); });
  svg.addEventListener("pointermove", e => { if (!tip.hidden) place(e.clientX, e.clientY); });
  svg.addEventListener("pointerleave", hide);
  svg.addEventListener("focusin", e => { const b = e.target.closest(".b"); if (b && fill(b)) { const r = b.getBoundingClientRect(); place(r.left, r.bottom); follow(b); } });
  svg.addEventListener("focusout", hide);
  document.addEventListener("pointerdown", e => { if (!svg.contains(e.target)) tip.hidden = true; });
  return { light: ids => light(ids.map(id => `[data-p="${id}"]`).join(","), "foc"), clear };
}

/* "Where we are" as one turn of a cell's cycle, in the old panel's place: a segment per Day plan.md numbers, read
   clockwise from the top, each phase's arc outside its Days, a gate at each stop and a hand where the work stands.
   Layout only, as the mockup at #228 drew it: every count it prints is in DATA.where_ring, counted by
   scripts/spec_drift_views.py (where_ring). `get` finds an element by its id; `onDay` is the page's Day buttons and
   `press(day)` presses one. Colours are in dashboard.css, under #whr. */
const RING_WORD = { done: "done", open: "closed, boxes open", active: "in progress", ready: "spec written", next: "next, no spec yet",
  planned: "provisional: plan.md names it, no spec yet", cut: "cut" };
function ringDraw(W, get, onDay, press) {
  const NS = "http://www.w3.org/2000/svg", $ = id => get("whr-" + id), fig = $("fig"), tip = $("tip");
  const el = (n, a, txt, parent) => { const e = document.createElementNS(NS, n); for (const k in a) if (a[k] != null) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; (parent || fig).appendChild(e); return e; };
  const h = (tag, cls, txt, parent) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; if (parent) parent.appendChild(e); return e; };
  const n = (k, one, many) => `${k} ${k === 1 ? one : many}`;
  const span = ds => !ds.length ? "" : ds.length === 1 ? `Day ${ds[0]}` : `Days ${ds[0]} to ${ds[ds.length - 1]}`;
  const runs = ds => { const out = []; ds.forEach(d => { const r = out[out.length - 1]; if (r && d === r[1] + 1) r[1] = d; else out.push([d, d]); });
    return andList(out.map(([a, b]) => a === b ? String(a) : `${a} to ${b}`)); };
  const wrap = (s, w) => String(s).split(" ").reduce((ls, word) => { const l = ls[ls.length - 1]; if (l && (l + " " + word).length <= w) ls[ls.length - 1] = l + " " + word; else ls.push(word); return ls; }, []);
  const CX = 280, CY = 168, RO = 138, RI = 100, RP = 146, RL = 119, PAD = 3.6, GAP = 1.2, TRIM = 1.6, VW = 572, VH = 326;
  const S = W.slots, N = Math.max(1, S.length), PITCH = (360 - 2 * PAD + GAP) / N, f = v => v.toFixed(1);
  const pt = (a, r) => [CX + r * Math.sin(a * Math.PI / 180), CY - r * Math.cos(a * Math.PI / 180)];
  const P = (a, r) => pt(a, r).map(f).join(" ");
  const arc = (a0, a1, r) => `M${P(a0, r)} A${r.toFixed(1)} ${r.toFixed(1)} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${P(a1, r)}`;
  const band = (a0, a1) => `${arc(a0, a1, RO)} L${P(a1, RI)} A${RI.toFixed(1)} ${RI.toFixed(1)} 0 ${a1 - a0 > 180 ? 1 : 0} 0 ${P(a0, RI)} Z`;
  const start = i => PAD + PITCH * i, end = i => start(i) + PITCH - GAP, mid = i => start(i) + (PITCH - GAP) / 2;
  const phaseOf = p => W.phases.find(x => x.phase === p) || { name: "", days: [] };
  const phaseName = p => p == null ? "Before the plan's list" : `${p}. ${phaseOf(p).name}`;
  const closed = s => s.state === "done" || s.state === "open";
  const D = {};

  // the words each mark says when pointed at: the pointer box and the mark's label alike
  W.phases.forEach(p => {
    D[p.k] = { t: `Phase ${phaseName(p.phase)}`, l: [p.days.length ? `${span(p.days)}: ${p.closed} of ${p.total} closed`
      : `No Day of it is numbered yet: the plan says only that it starts at Day ${p.from_day}.`,
    p.stop != null ? `The plan stops for the maintainer after Day ${p.stop}: ${p.lifted ? "passed, lifted by a course correction" : "ahead"}.`
      : p.days.length ? "No stop after it: the next phase follows without waiting." : null] };
  });
  S.forEach(s => {
    if (s.state === "stub") { D[s.k] = { t: `From Day ${s.from_day} · not numbered yet`, l: [`Phase ${phaseName(s.phase)}`,
      `The plan names this phase and says it starts at Day ${s.from_day}. It numbers none of its Days yet, so the ring cannot say how long it is.`] }; return; }
    const spec = s.total || s.prs.n;
    D[s.k] = { t: `Day ${s.day} · ${RING_WORD[s.state]}`, q: s.title || s.name, l: [`Phase ${phaseName(s.phase)}`,
      ...(spec ? [`${n(s.total, "promise", "promises")}, ${s.ticked} ticked`, `${n(s.prs.n, "pull request", "pull requests")}: ${s.prs.code} code, ${s.prs.spec} spec, ${s.prs.close} close`,
        s.state === "active" && s.tracks ? `${s.merged} of ${s.tracks} tracks merged` : null,
        s.score != null ? `Score ${s.score} of 100; its lowest part: ${s.low}` : null] : ["No spec yet: no promises, no pull requests, no score"]),
      s.end ? "Ends a phase" : null,
      s.stop ? `A stop follows it: ${s.stop === "passed" ? "passed, lifted by a course correction" : "the work halts here until the maintainer lifts it"}` : null] };
  });
  const toGo = g => S.slice(0, g.slot + 1).filter(s => s.day != null && !closed(s) && s.state !== "cut").map(s => s.day);
  W.gates.forEach(g => {
    D[g.k] = { t: `Stop after Day ${g.day} · ${g.passed ? "passed" : "ahead"}`, l: ["The plan stops here for the maintainer. No phase starts after it until the maintainer says go on.",
      g.passed ? "The maintainer said go on: the stop was lifted by a course correction." : `${n(toGo(g).length, "Day", "Days")} to go before it: ${span(toGo(g))}.`] };
  });
  const [was, next] = W.now.between || [null, null], last = W.last;
  const nowWhere = W.now.day != null ? `The work stands in Day ${W.now.day}, in progress.` : was == null ? `The work stands before Day ${next}.`
    : next == null ? `The work stands after Day ${was}, the last Day the plan numbers.` : `The work stands between Day ${was} and Day ${next}.`;
  const openSay = W.open_prs.length ? `${n(W.open_prs.length, "pull request is", "pull requests are")} open.` : "No pull request is open.";
  D.now = { t: `Now · ${W.now.day != null ? `Day ${W.now.day} in progress` : "between Days"}`, l: [nowWhere, `Next step: ${W.next_step}`,
    last ? `Last merge: #${last.pr}${last.sha ? ` at ${last.sha}` : ""}. ${openSay}` : openSay] };
  const said = k => [D[k].t, D[k].q, ...D[k].l].filter(Boolean).join(". ");

  // the figure
  fig.replaceChildren();
  const where = W.now.day != null ? `Day ${W.now.day} is in progress` : `between ${was == null ? "the start" : `Day ${was}`} and ${next == null ? "the end" : `Day ${next}`}`;
  fig.setAttribute("viewBox", `0 0 ${VW} ${VH}`);
  fig.setAttribute("aria-label", `The plan as a ring read clockwise from the top: ${n(W.numbered, "Day", "Days")} in ${n(W.phases.length, "phase", "phases")}, ${W.closed} closed. Now: ${where}. Next step: ${W.next_step}`);
  el("path", { class: "start", d: `M${CX - 4}.0 ${CY - 125}.0 l0 12 l8 -6 z` });
  el("text", { class: "t-sub", x: CX, y: 13, "text-anchor": "middle" }, "start");
  const groups = [], labels = [];
  const group = (k, extra) => { const g = el("g", Object.assign({ class: "b", tabindex: 0, role: "img", "aria-label": said(k), "data-k": k }, extra || {})); groups.push(g); return g; };
  // the phases: an arc outside their Days, and their name beside it
  W.phases.forEach(p => {
    const at = S.map((s, i) => s.phase === p.phase ? i : -1).filter(i => i >= 0);
    if (!at.length) return;
    const a0 = start(at[0]) + 0.8, a1 = end(at[at.length - 1]) - 0.8, d = arc(a0, a1, RP), m = (a0 + a1) / 2, g = group(p.k);
    el("path", { class: `parc${p.days.length ? "" : " later"}`, d }, null, g);
    el("path", { d, fill: "none", stroke: "transparent", "stroke-width": 14 }, null, g);
    const sub = p.days.length ? span(p.days) : `from Day ${p.from_day}`;
    if (m < 50 || m > 310) labels.push({ top: true, x: m < 180 ? CX + 34 : CX - 34, anchor: m < 180 ? "start" : "end", name: phaseName(p.phase), sub });
    else { const right = m < 180, x = right ? CX + RP + 4.7 : CX - RP - 15.9, lines = wrap(phaseName(p.phase), Math.floor((right ? VW - x - 4 : x - 4) / 6.2));
      labels.push({ x, anchor: right ? "start" : "end", lines: [...lines, sub], y: CY - 170 * Math.cos(m * Math.PI / 180) - 7 * lines.length }); }
  });
  // the Days: one segment each, its number, and its score under it
  S.forEach((s, i) => {
    const first = !i || S[i - 1].phase !== s.phase, lastOf = i === S.length - 1 || S[i + 1].phase !== s.phase;
    const a0 = start(i) + (first ? TRIM : 0), a1 = end(i) - (lastOf ? TRIM : 0), g = group(s.k);
    el("path", { class: `seg s-${s.state}`, d: band(a0, a1) }, null, g);
    if (s.state === "active" && s.tracks) el("path", { class: "prog", d: arc(a0, a0 + (a1 - a0) * Math.max(0.04, s.merged / s.tracks), RO - 3) }, null, g);
    const [x, y] = pt(mid(i), RL), ny = y + 4.5 - (s.score != null ? 5 : 0);
    el("text", { class: `t-n${s.state === "planned" || s.state === "stub" ? " quiet" : ""}${s.state === "cut" ? " struck" : ""}`, x: f(x), y: f(ny) },
      s.day != null ? String(s.day) : `${s.from_day}+`, g);
    if (s.score != null) el("text", { class: "t-sc", x: f(x), y: f(ny + 12) }, String(s.score), g);
    if (s.state === "open") el("rect", { class: "box", x: f(x + 8.5), y: f(ny - 12.5), width: 7, height: 7, rx: 1 }, null, g);
    if (s.day != null) {
      g.addEventListener("click", () => press(s.day));
      g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); press(s.day); } });
    }
  });
  // the stops: a gate across the ring after their Day, open once the maintainer lifted it
  const gateAt = slot => start(slot + 1) - GAP / 2;
  W.gates.forEach(gt => {
    const a = gateAt(gt.slot), g = group(gt.k, { transform: `rotate(${a.toFixed(2)} ${CX} ${CY})` });
    el("rect", { class: "hit", x: f(CX - 8), y: "12.0", width: 16, height: "68.0", rx: 4 }, null, g);
    if (gt.passed) { el("rect", { class: "gate passed", x: f(CX - 3), y: "15.0", width: 6, height: 13, rx: 3 }, null, g); el("rect", { class: "gate passed", x: f(CX - 3), y: "70.0", width: 6, height: 11, rx: 3 }, null, g); }
    else el("rect", { class: "gate ahead", x: f(CX - 3), y: "15.0", width: 6, height: "62.0", rx: 3 }, null, g);
    const [px, py] = pt(a, 155), left = a > 180, below = py > CY, x = left ? px - 58 : px + 58, y = below ? py - 22 : py + 19;
    labels.push({ x, anchor: left ? "end" : "start", gate: true, lines: [gt.passed ? `stop after Day ${gt.day}, passed:` : `stop after Day ${gt.day}:`,
      gt.passed ? "the maintainer said go on" : "the maintainer says go on"], y, lead: [left ? 4 : -4, below ? 10 : -4, px, py] });
  });
  // where the work stands: in the middle of the Day in progress, or before the first Day not finished
  const na = W.now.day != null ? mid(W.now.slot) : gateAt(W.now.slot), ng = group("now", { transform: `rotate(${na.toFixed(2)} ${CX} ${CY})` });
  el("rect", { class: "hit", x: CX - 9, y: "2.0", width: 18, height: "72.0", rx: 4 }, null, ng);
  el("path", { class: "hand", d: `M${CX} 17.0 V70.0` }, null, ng);
  el("path", { class: "pin", d: `M${CX - 6.5} 5.0 h13 l-6.5 11 z` }, null, ng);
  { const [px, py] = pt(na, 172), left = na > 180;
    labels.push({ x: left ? px - 9 : px + 9, anchor: left ? "end" : "start", now: true, lines: ["now", W.now.day != null ? `in Day ${W.now.day}` : "between Days"], y: py }); }
  // the labels at the sides, pushed down until none overlaps another on its side
  const side = labels.filter(l => !l.top).sort((a, b) => a.y - b.y);
  side.forEach((l, i) => side.slice(0, i).forEach(o => {
    if (o.anchor === l.anchor && Math.abs(o.x - l.x) < 120 && l.y < o.y + 14 * o.lines.length + 4) l.y = o.y + 14 * o.lines.length + 4; }));
  labels.forEach(l => {
    if (l.top) { const t = el("text", { class: "t-ph", x: l.x, y: 13, "text-anchor": l.anchor }, l.name); el("tspan", { class: "t-sub" }, ` · ${l.sub}`, t); return; }
    l.y = Math.max(13, Math.min(VH - 14 * l.lines.length, l.y));
    const wide = Math.max(...l.lines.map(s => s.length)) * 6.3;  // kept inside the picture, as the mockup keeps them
    l.x = l.anchor === "start" ? Math.min(l.x, VW - wide - 2) : Math.max(l.x, wide + 2);
    l.lines.forEach((line, j) => el("text", { class: j === l.lines.length - 1 ? "t-sub" : l.now ? "t-now" : l.gate ? "t-gate" : "t-ph", x: f(l.x), y: f(l.y + 14 * j), "text-anchor": l.anchor }, line));
    if (l.lead) el("path", { class: "lead", d: `M${f(l.x + l.lead[0])} ${f(l.y + l.lead[1])} L${f(l.lead[2])} ${f(l.lead[3])}` });
  });
  // the middle: the next step in the page's own words, and how far the next stop is
  const steps = wrap(W.next_step, 23), shown = steps.slice(0, 4);
  if (steps.length > 4) shown[3] = shown[3].replace(/.?$/, "…");
  let y = 109 + 8 * (3 - shown.length);
  el("text", { class: "t-kick", x: CX, y: f(y) }, W.now.day != null ? "IN PROGRESS" : "NEXT STEP");
  shown.forEach((s, j) => el("text", { class: "t-step", x: CX, y: f(y + 19 + 16 * j) }, s));
  y += 19 + 16 * (shown.length - 1) + 14;
  el("path", { class: "rule", d: `M${CX - 52} ${f(y)} H${CX + 52}` });
  const big = W.stop != null ? [n(W.left.length, "Day", "Days"), "left to the next stop,", `after Day ${W.stop}`] : [`${W.closed} of ${W.numbered}`, "Days closed", ""];
  el("text", { class: "t-big", x: CX, y: f(y + 32) }, big[0]);
  el("text", { class: "t-mid", x: CX, y: f(y + 49) }, big[1]);
  if (big[2]) el("text", { class: "t-mid", x: CX, y: f(y + 63) }, big[2]);

  // the figures beside it, and the next step among them
  const fig3 = (num, of, what, sub) => { const d = h("div"); const v = h("div", "num", String(num), d); if (of != null) h("small", "", ` of ${of}`, v); h("div", "what", what, d); h("span", "sub", sub, d); return d; };
  const nx = h("div", "next"); h("p", "kick", `Next step · ${W.now.day != null ? `Day ${W.now.day} in progress` : "between Days"}`, nx); h("p", "step", W.next_step, nx);
  $("figs").replaceChildren(fig3(W.closed, W.numbered, "Days closed", "of the Days the plan numbers"),
    W.stop != null ? fig3(W.left.length, null, `${W.left.length === 1 ? "Day" : "Days"} left to the next stop`, `the plan stops after Day ${W.stop}`)
      : fig3(W.left.length, null, `${W.left.length === 1 ? "Day" : "Days"} not finished`, "the plan names no stop ahead"),
    fig3(W.built, W.written, "promises built", "of the promises written so far"), nx);
  $("key-sc").textContent = W.score != null ? String(W.score) : "";
  const facts = $("facts"), fact = (dt, wide) => { const d = h("div", wide ? "wide" : ""); h("dt", "", dt, d); facts.appendChild(d); return h("dd", "", null, d); };
  facts.replaceChildren();
  if (last) { const dd = fact("Last merge"), b = h("b", "", null, dd);
    if (W.repo_url) { const a = h("a", "", `#${last.pr}`, b); a.setAttribute("href", `${W.repo_url}/pull/${last.pr}`); } else b.textContent = `#${last.pr}`;
    if (last.sha) { dd.append(" at "); h("code", "", last.sha, dd); }
    dd.append(`, ${last.date || ""}`); h("br", "", null, dd); dd.append(last.title); }
  { const dd = fact("Open pull requests"); if (!W.open_prs.length) h("b", "", "None", dd); else W.open_prs.forEach((p, i) => { if (i) h("br", "", null, dd); h("b", "", `#${p.pr}`, dd); dd.append(` ${p.title}`); }); }
  if (W.score != null) { const dd = fact("Score so far"); h("b", "", String(W.score), dd); dd.append(" of 100, the finished Days together"); }
  if (W.stop != null) { const dd = fact("Stop ahead", true); h("b", "", `Day ${W.stop}`, dd);
    dd.append(`${W.stop_name ? `, ${W.stop_name}` : ""}, ${W.left.length ? `${n(W.left.length, "Day", "Days")} to go` : "reached"}. The work halts there until the maintainer lifts it.`); }

  // the key, the lists and the stamp under the picture
  const sw = (cls, parent, extra) => { const s = el("svg", { width: 20, height: 14, viewBox: "0 0 20 14", "aria-hidden": "true" }, null, parent); el("rect", { class: `seg s-${cls}`, x: 1, y: 1, width: 18, height: 12, rx: 2.5 }, null, s);
    if (extra) el("rect", { class: "box", x: 7.5, y: 4.5, width: 5, height: 5, rx: 1, style: "stroke-width:1.2" }, null, s); return s; };
  const lg = $("lg"); lg.replaceChildren();
  const term = (dt, small) => { const t = h("dt", "", dt, lg); h("small", "", small, t); return h("dd", "", null, lg); };
  const item = (dd, mk, text) => { const s = h("span", "", null, dd); mk(s); s.append(text); };
  const inState = st => S.filter(s => s.state === st && s.day != null).map(s => s.day);
  const dayList = ds => ds.length === 1 ? `Day ${ds[0]}` : `Days ${runs(ds)}`;
  const STATES = [["done", "closed, every promise ticked"], ["open", "closed, a box open: closed with a promise not ticked"], ["active", "in progress"], ["ready", "spec written, not closed"],
    ["next", "next, and no spec yet"], ["planned", "no spec yet: plan.md names it, nothing more"], ["cut", "cut"]];
  let dd = term("A Day", "a stretch of the cycle");
  STATES.filter(([st]) => inState(st).length).forEach(([st, w]) => item(dd, s => sw(st, s, st === "open"), `${w} (${dayList(inState(st))})`));
  h("span", "", "The big number is the Day. The small number under it is the Day's score out of 100, the one the page's Day buttons show; a Day not finished has none.", dd);
  const absent = STATES.filter(([st]) => !inState(st).length).map(([, w]) => w.split(":")[0].replace(/, and no spec yet$/, ""));
  if (absent.length) h("span", "", `Not drawn today, since no Day is in that state: ${absent.join(", ")}.`, dd);
  dd = term("A phase", "a stretch of the plan");
  item(dd, s => { const v = el("svg", { width: 22, height: 8, viewBox: "0 0 22 8", "aria-hidden": "true" }, null, s); el("path", { class: "parc", d: "M2 6Q11 0 20 6", style: "stroke-width:3" }, null, v); },
    "the arc outside its Days, with its number and name as plan.md gives them");
  const stubs = S.filter(s => s.state === "stub");
  if (stubs.length) item(dd, s => sw("stub", s), `a phase whose Days are not numbered yet: one dashed segment, marked with the Day it starts from (${stubs.map(s => s.from_day + "+").join(", ")})`);
  if (W.gates.length) {
    dd = term("A stop", "a checkpoint");
    const gs = p => W.gates.filter(g => g.passed === p).map(g => `after Day ${g.day}`).join(", ");
    const gate = (s, p) => { const v = el("svg", { width: 8, height: 18, viewBox: "0 0 8 18", "aria-hidden": "true" }, null, s);
      if (p) { el("rect", { class: "gate passed", x: 1.5, y: 1, width: 5, height: 6, rx: 2.5 }, null, v); el("rect", { class: "gate passed", x: 1.5, y: 11, width: 5, height: 6, rx: 2.5 }, null, v); }
      else el("rect", { class: "gate ahead", x: 1.5, y: 1, width: 5, height: 16, rx: 2.5 }, null, v); };
    if (gs(true)) item(dd, s => gate(s, true), `stop, passed: the maintainer said go on, and the gate stands open (${gs(true)})`);
    if (gs(false)) item(dd, s => gate(s, false), `stop ahead: a bar across the ring, shut until the maintainer says go on (${gs(false)})`);
  }
  dd = term("Now", "where the cell is in its cycle");
  item(dd, s => { const v = el("svg", { width: 12, height: 18, viewBox: "0 0 12 18", "aria-hidden": "true" }, null, s); el("path", { class: "pin", d: "M1 1h10l-5 8z" }, null, v); el("path", { class: "hand", d: "M6 9V17" }, null, v); },
    `the line where the work stands: in the middle of a Day in progress, or before the first Day not finished (today: ${where})`);
  $("stamp").textContent = `Drawn from the page's data at ${W.head}${W.last_pr ? ` (#${W.last_pr})` : ""}, generated ${W.generated}`;

  const li = (ul, cls, b, text) => { const l = h("li", cls, null, ul); h("b", "", b, l); l.append(text); };
  const finds = $("finds"); finds.replaceChildren();
  const whole = W.phases.filter(p => p.total && p.closed === p.total), part = W.phases.filter(p => p.total && p.closed && p.closed < p.total);
  li(finds, "good", `${W.closed} of the ${W.numbered} Days the plan numbers are closed.`,
    (whole.length ? ` Phases closed whole: ${andList(whole.map(p => `${p.phase} (${span(p.days)})`))}.` : "") + part.map(p => ` Phase ${p.phase} has ${p.closed} of its ${p.total} closed.`).join(""));
  W.boxes.forEach(b => li(finds, "fix", `Day ${b.day} is closed with ${n(b.total - b.ticked, "box", "boxes")} open.`,
    ` ${b.ticked} of its ${b.total} promises are ticked; ${b.ids.length === 1 ? `the one not ticked is ${b.ids[0]}` : `not ticked: ${b.ids.join(", ")}`}.${W.built < W.written ? ` It is why the page counts ${W.built} promises built of ${W.written} written.` : ""}`));
  li(finds, "", W.now.day != null ? `Day ${W.now.day} is in progress.` : "No Day is in progress.",
    ` ${nowWhere} Next step: ${W.next_step}.${last ? ` The last merge is #${last.pr}${last.sha ? ` at ${last.sha}` : ""}, and ${W.open_prs.length ? n(W.open_prs.length, "pull request is", "pull requests are") + " open" : "no pull request is open"}.` : ""}`);
  if (W.stop != null) { const unspec = W.left.filter(d => { const s = S.find(x => x.day === d); return s && (s.state === "next" || s.state === "planned"); });
    li(finds, "", `${n(W.left.length, "Day", "Days")} to the next stop, after Day ${W.stop}.`,
      unspec.length ? ` ${dayList(unspec)} ${unspec.length === 1 ? "has" : "have"} no spec yet: ${unspec.length === 1 ? "it is" : "they are"} named only by plan.md.` : ""); }
  W.gates.filter(g => g.passed).forEach(g => { const after = W.phases.find(p => p.days.includes(g.day + 1) || p.from_day === g.day + 1);
    li(finds, "", `The stop after Day ${g.day} was passed.`, ` The plan stopped there for the maintainer, and a course correction lifted it.${after ? ` Phase ${after.phase} started after it.` : ""}`); });
  stubs.forEach(s => li(finds, "", `Phase ${s.phase} has no numbered Day.`, ` The plan says it starts at Day ${s.from_day} and names none of its Days, so the ring shows it as one dashed segment of unknown length.`));
  if (W.lo && W.hi) li(finds, "", `The closed Days score from ${W.lo.n} to ${W.hi.n} out of 100.`, ` The lowest is Day ${W.lo.day}, the highest Day ${W.hi.day}${W.score != null ? `; the finished Days together score ${W.score}` : ""}.`);
  const sized = S.filter(s => s.total), small = sized.reduce((a, s) => !a || s.total < a.total ? s : a, null), large = sized.reduce((a, s) => !a || s.total > a.total ? s : a, null);
  const lifted = W.gates.filter(g => g.passed).map(g => `the stop after Day ${g.day}`);
  const bends = $("bends"); bends.replaceChildren();
  [["A cell's cycle repeats; this plan runs once.", " After division a cell is back at the start. The ring is one turn only: it ends at the top and does not begin again, which is why it is left open there."],
    ["Nobody chooses a cell's phases.", ` The plan's phases and its stops were written by the maintainer in plan.md, and can be rewritten${lifted.length ? `: ${andList(lifted)} was lifted by a course correction` : ""}.`],
    ["A checkpoint tests the cell; a stop waits for a person.", " A cell passes when its own checks find nothing wrong. Here the checks run on every pull request, and the stop is a separate thing: the maintainer's decision to go on."],
    ["Every segment has the same width.", ` A Day is a step of the plan, not a length of time or an amount of work${small && large && small !== large ? `: Day ${small.day} has ${small.total} promises and Day ${large.day} has ${large.total}, and they are drawn alike` : ""}.`],
    ["Closed is not the same as proven.", " A filled segment says the Day is closed. How well its promises hold is the score, and the graphs below."],
    ...(stubs.length ? [["The last phase is drawn as one segment.", " That is a placeholder, not a count: the plan does not yet say how many Days it holds."]] : [])]
    .forEach(([b, t]) => li(bends, "", b, t));

  // the pointer box: what a mark is, built as text
  const show = k => { const d = D[k]; if (!d) return false; tip.replaceChildren(); h("div", "t", d.t, tip); if (d.q) h("div", "q", d.q, tip); d.l.filter(Boolean).forEach(l => h("div", "l", l, tip)); tip.hidden = false; return true; };
  const place = (x, y) => { const w = tip.offsetWidth, ht = tip.offsetHeight; let t = y + 18; if (t + ht > innerHeight - 8) t = Math.max(8, y - ht - 12);
    tip.style.left = Math.max(8, Math.min(x + 14, innerWidth - w - 8)) + "px"; tip.style.top = t + "px"; };
  const mark = e => e.target && e.target.closest ? e.target.closest(".b") : null;
  fig.addEventListener("pointerover", e => { const b = mark(e); if (b && show(b.getAttribute("data-k"))) place(e.clientX, e.clientY); else tip.hidden = true; });
  fig.addEventListener("pointermove", e => { if (!tip.hidden) place(e.clientX, e.clientY); });
  fig.addEventListener("pointerleave", () => { tip.hidden = true; });
  fig.addEventListener("focusin", e => { const b = mark(e); if (b && show(b.getAttribute("data-k"))) { const r = b.getBoundingClientRect(); place(r.left + r.width / 2, r.bottom - 10); } });
  fig.addEventListener("focusout", () => { tip.hidden = true; });
  if (typeof addEventListener === "function") addEventListener("scroll", () => { tip.hidden = true; }, { passive: true });
  // the page's Day buttons light a Day on the ring, and its phase
  // the chosen Day is also said to a screen reader, on its segment (aria-current): dimming the others says nothing to it
  onDay.push(day => groups.forEach(g => { const k = g.getAttribute("data-k"), m = /^d(\d+)$/.exec(k), p = /^p(\d+)$/.exec(k);
    if (m) g.setAttribute("aria-current", day != null && +m[1] === day ? "true" : "false");
    g.classList.toggle("mk-dim", day != null && (m ? +m[1] !== day : p ? !(phaseOf(+p[1]).days || []).includes(day) : false)); }));
  // at phone width the ring scrolls sideways in its card: open it centred on the ring, not on its left labels
  const sc = $("scroll"); if (sc.scrollWidth > sc.clientWidth) sc.scrollLeft = (sc.scrollWidth - sc.clientWidth) / 2;
  return fig;
}

/* What graph 1's reading says of one mark, as the pointer box shows it: a title, the words it quotes, and its lines.
   `k` and `v` are the mark's data-k and data-v. */
const RDG_HOW = { picked: "Picked up", lapsed: "Lapsed", withdrawn: "Withdrawn" };
function rdgTip(R, k, v) {
  const m = R.m, pr = i => m[i] && m[i].pr ? "#" + m[i].pr : "the first commit", n = (x, one, many) => `${x} ${x === 1 ? one : many}`;
  const whose = i => (m[i] || {}).w || "";
  if (k === "m") {
    const x = m[+v]; let o = 0, c = 0; R.h.forEach(h => { if (h.o === +v) o++; if (h.c === +v) c++; });
    return { t: `${x.pr ? "Pull request #" + x.pr : "The first commit"} · ${KINDS[x.k] || x.k} · ${x.w}`,
      l: [x.t, x.g.length ? `Built ${x.g.map(g => g[0]).join(", ")}.` : "Built no promise.", o || c ? `Opened ${n(o, "hand-off", "hand-offs")}, closed ${c}.` : ""] };
  }
  if (k === "iv") {
    const ix = R.strand.filter(s => s.iv)[+v].iv, built = sum(ix, i => m[i].g.length), first = whose(ix[0]);
    const lines = ix.slice(0, 8).map(i => `${m[i].pr ? "#" + m[i].pr : "start"} ${m[i].t}`);
    if (ix.length > 8) lines.push(`and ${ix.length - 8} more`);
    return { t: `Between Days · ${n(ix.length, "merge", "merges")} · ${ix.length > 1 ? `${pr(ix[0])} to ${pr(ix[ix.length - 1])}` : pr(ix[0])}`,
      l: [`${first.charAt(0).toUpperCase()}${first.slice(1)}. They built ${built || "no"} promise${built === 1 ? "" : "s"}.`, ...lines] };
  }
  if (k === "h") {
    const h = R.h[+v];
    return { t: `${h.id || "Unnumbered hand-off"} · ${h.s}`, q: h.x, l: [`Opened at ${pr(h.o)} (${whose(h.o)}).`,
      h.c == null ? `Still open${h.w ? `; it waits for Day ${h.w}` : ""}.` : `${RDG_HOW[h.how] || "Closed"} at ${pr(h.c)} (${whose(h.c)}).`] };
  }
  if (k === "ph") {
    const p = R.phases[+v], ds = p.days;
    return { t: `Phase ${p.phase} · ${p.name}`, l: [ds.length ? `${ds.length === 1 ? `Day ${ds[0]}` : `Days ${ds[0]} to ${ds[ds.length - 1]}`}.` : `From Day ${p.from_day}; none of its Days is numbered yet.`,
      p.stop == null ? "No stop of its own." : p.lifted ? `Its stop, after Day ${p.stop}, was lifted.` : `Its stop, after Day ${p.stop}, is the next one: the maintainer decides there.`] };
  }
  if (k === "gap") { const g = R.gap.find(x => x.id === v); return { t: `${v} · written on Day ${g.d}, never built`, q: g.x, l: ["Its Day closed without it, and nothing ahead builds it."] }; }
  if (k === "ahead") {
    const a = R.ahead.find(x => x.day === +v), named = a.w.filter(x => x !== "unnumbered");
    return { t: `Day ${v} · no spec yet`, l: [a.n ? `The plan calls it: ${a.n}.` : "", "Its size cannot be drawn until its spec is written.",
      a.w.length ? `${n(a.w.length, "open hand-off waits", "open hand-offs wait")} for it; numbered: ${named.join(", ") || "none"}.` : ""] };
  }
  return null;
}

/* Graph 1 read as a gene, in graph 1's place: every merge in order on one strand, a Day's merges as a block, the
   merges between Days as thin stretches, the promises built under each merge, today as the polymerase, the Days with
   no spec ahead and the stop, and the hand-offs as arcs. Layout only, as the mockup at #228 drew it: every count it
   prints is in DATA.reading, counted by scripts/spec_drift_views.py (reading). Every hand-off's arc is drawn, closed or open;
   pointing at one, or at its merge, lights it and fades the others, and a Day chosen fades those not of it. `get` finds an element by its
   id; `onDay` is the page's Day buttons. Colours are in dashboard.css, under #rdg. */
function readingDraw(R, get, onDay) {
  const NS = "http://www.w3.org/2000/svg", $ = id => get("rdg-" + id), fig = $("fig"), tip = $("tip");
  const el = (n, a, txt, parent) => { const e = document.createElementNS(NS, n); for (const k in a) if (a[k] != null) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; (parent || fig).appendChild(e); return e; };
  const h = (tag, cls, txt, parent) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; if (parent) parent.appendChild(e); return e; };
  const n = (x, one, many) => `${x} ${x === 1 ? one : many}`, f = v => +v.toFixed(1);
  const m = R.m, items = R.strand, ivs = items.filter(x => x.iv), nA = R.ahead.length, stop = R.stop;
  const later = R.phases.find(p => p.later), cellsN = items.length - ivs.length;
  // the right of the strand: today, the Days ahead, the stop and a phase not numbered yet, as the mockup spaces them
  const VW = 1240, X0 = 120, right = 7 + 13 + (nA ? 52 * nA - 6 + 12 : 0) + (stop ? 12 : 0) + (later ? 56 : 0) + 6;
  const PC = Math.min(24, (VW - right - X0 - 6 * ivs.length - 0.5 * R.between) / Math.max(1, cellsN)), CW = Math.max(1.2, PC - 0.96);
  const L = [], X = [], CX = {};
  let c = X0 + 0.5;
  items.forEach((x, j) => {
    if (x.iv) { const w = 6 + 0.5 * x.iv.length, x0 = c - 0.5; L.push({ j, iv: x.iv, x: x0, w }); x.iv.forEach((i, k) => { X[i] = x0 + w * (k + 0.5) / x.iv.length; }); c += w; }
    else { L.push({ j, m: x.m, x: c, w: CW }); CX[x.m] = c; X[x.m] = c + CW / 2; c += PC; }
  });
  const SE = c - 0.5, T = SE + 7, TX = T + 13, AE = TX + 52 * nA - 6, termX = nA ? AE + 12 : TX, LX = stop ? termX + 12 : termX;
  const cellEnd = i => CX[i] + CW;
  fig.replaceChildren();

  // the open hand-offs' rows: to the Day they wait for, nearest origin innermost
  const rank = d => { const i = R.ahead.findIndex(a => a.day === d); return i < 0 ? 1e6 + (d || 0) : i; };
  const opens = R.h.map((x, j) => ({ x, j })).filter(o => o.x.c == null).sort((a, b) => rank(a.x.w) - rank(b.x.w) || b.x.o - a.x.o || a.j - b.j);
  const Y0 = 268, rows = opens.map((o, k) => Y0 + 4.6 * k), lastY = rows.length ? rows[rows.length - 1] : 220;
  const VH = f(Math.max(lastY + 26.4, 240));
  fig.setAttribute("viewBox", `0 0 ${VW} ${VH}`);
  const defs = el("defs", {}), pat = el("pattern", { id: "rdg-hatch", width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, null, defs);
  el("rect", { class: "hb", width: 5, height: 5 }, null, pat); el("rect", { class: "hl", width: 1.6, height: 5 }, null, pat);

  // the rows' names on the left
  const how = R.how || {}, closedN = (how.picked || 0) + (how.lapsed || 0) + (how.withdrawn || 0);
  [["t-row", 43, "The plan's phases"], ["t-row", 78, "Merges, in order"], ["t-bio", 90, "THE GENE, AS READ"], ["t-sec", 101, `${R.merges}, ${R.between} between Days`],
    ["t-row", 125, "Promises built"], ["t-bio", 137, "THE TRANSCRIPT"], ["t-sec", 148, `${R.built} of ${R.written} written`],
    ["t-row", 180, "Hand-offs, closed"], ["t-sec", 192, `${closedN}: ${how.picked || 0} picked up,`], ["t-sec", 203, `${how.lapsed || 0} lapsed, ${how.withdrawn || 0} withdrawn`]]
    .forEach(([cls, y, t]) => el("text", { class: cls, x: 0, y }, t));
  if (opens.length) { const y = (rows[0] + lastY) / 2 - 16;
    [["t-row", 0, "Hand-offs, open"], ["t-sec", 12, `${R.open}, of them`], ["t-sec", 23, `${R.numbered} numbered`]].forEach(([cls, dy, t]) => el("text", { class: cls, x: 0, y: f(y + dy) }, t)); }

  // the phases over the strand
  const aheadDays = new Set(R.ahead.map(a => a.day)), marks = [];
  R.phases.forEach((p, v) => {
    if (p.later) return;
    const mine = R.days.filter(d => p.days.includes(d.day)), at = mine.flatMap(d => [d.main, ...d.strays]).flat();
    const hasAhead = p.days.some(d => aheadDays.has(d));
    if (!at.length && !hasAhead) return;
    const x0 = at.length ? Math.min(...at.map(i => CX[i])) - 0.5 : TX - 0.5, x1 = hasAhead ? (stop ? termX : AE) : Math.max(...at.map(cellEnd)) + 0.5;
    const g = el("g", { class: "b ph", tabindex: 0, "data-k": "ph", "data-v": v });
    el("rect", { class: "phase", x: f(x0), y: 32, width: f(x1 - x0), height: 15, rx: 3 }, null, g);
    const full = `Phase ${p.phase} · ${p.name}`;
    el("text", { class: "t-ph", x: f(x0 + 6), y: 43 }, full.length * 5.4 < x1 - x0 - 12 ? full : `Phase ${p.phase}`, g);
  });
  // a bracket over each Day's main span, its number and its promises; a small number over a fragment away from it
  R.days.forEach(d => {
    const x0 = CX[d.main[0]], x1 = cellEnd(d.main[1]), mid = (x0 + x1) / 2;
    el("path", { class: "brk", d: `M${f(x0)} 69 V66 H${f(x1)} V69` });
    el("text", { class: "t-dayn", x: f(mid), y: 62, "text-anchor": "middle" }, x1 - x0 >= 30 ? `Day ${d.day}` : String(d.day));
    if (d.total) el("text", { class: `t-bw${d.ticked < d.total ? " short" : ""}`, x: f(mid), y: 153, "text-anchor": "middle" }, `${d.ticked}/${d.total}`);
    d.strays.forEach(([a, b]) => { el("path", { class: "brk", d: `M${f(CX[a])} 69 V66 H${f(cellEnd(b))} V69` });
      el("text", { class: "t-stray", x: f((CX[a] + cellEnd(b)) / 2), y: 62, "text-anchor": "middle" }, String(d.day)); });
  });
  // the strand: a cell per merge of a Day, a thin stretch for the merges between Days
  el("path", { class: "strand", d: `M${X0} 90 H${f(SE)}` });
  const cells = {}, stretches = [];
  L.forEach(x => {
    if (x.iv) {
      const r = el("rect", { class: "b iv", tabindex: 0, "data-k": "iv", "data-v": stretches.length, x: f(x.x), y: 74, width: f(x.w), height: 32 });
      stretches.push(r); marks.push(r);
      x.iv.forEach(i => { if (m[i].k === "spec") el("rect", { class: "pc", x: f(X[i] - 1), y: 85.5, width: 2, height: 9 }); });
    } else {
      cells[x.m] = el("rect", { class: `b cell k-${m[x.m].k}`, tabindex: 0, "data-k": "m", "data-v": x.m, x: f(x.x), y: 82, width: f(x.w), height: 16, rx: 1 });
      marks.push(cells[x.m]);
    }
  });
  // under each merge, the promises it built
  const qs = [];
  m.forEach((x, i) => x.g.forEach(([id, tag, day], k) => {
    const w = i in CX ? CW - 0.6 : 4, x0 = i in CX ? CX[i] + 0.3 : X[i] - 2;
    const q = el("rect", { class: `q q-${tag === "hold" ? "hold" : "new"}`, "data-q": id, x: f(x0), y: f(103 + 4.4 * k), width: f(w), height: 3, rx: 1.2 }); q.dataset.day = String(day); qs.push(q);
  }));
  R.gap.forEach(g => el("rect", { class: "b q gap", tabindex: 0, "data-k": "gap", "data-v": g.id, x: f(X[g.at] - 3.55), y: f(104 + 4.4 * m[g.at].g.length), width: 7.1, height: 3.4, rx: 1.2 }));
  // the stops: one the maintainer lifted, after its Day; the next, after the Days ahead
  R.lifted.forEach(s => { const x = cellEnd(s.at);
    el("path", { class: "lead", d: `M${f(x + 1.5)} 26 V73` });
    el("rect", { class: "term lifted", x: f(x), y: 74, width: 3, height: 32, rx: 1.5 });
    el("text", { class: "t-top", x: f(x + 1.5), y: 22, "text-anchor": "middle" }, `stop after Day ${s.day}: lifted`); });
  if (stop) {
    el("path", { class: "lead", d: `M${f(termX + 3)} 14 V32` });
    el("rect", { class: "term shut", x: f(termX), y: 73, width: 6, height: 34, rx: 2 });
    el("path", { class: "termcap", d: `M${f(termX - 6)} 73 h18` });
    el("text", { class: "t-top strong", x: VW - 2, y: 10, "text-anchor": "end" }, `the next stop, after Day ${stop.day}: the maintainer decides`);
  }
  L.forEach(x => { if (x.iv && x.iv.length >= 4) el("text", { class: "t-iv", x: f(x.x + x.w / 2), y: 84, "text-anchor": "middle" }, String(x.iv.length)); });
  // today, and the Days the plan lists with no spec yet
  const lastPr = [...m].reverse().find(x => x.pr);
  el("path", { class: "lead today", d: `M${f(T)} 26 V78` });
  el("ellipse", { class: "pol", cx: f(T), cy: 90, rx: 7, ry: 11.5 });
  el("text", { class: "t-top strong", x: f(T + 6), y: 22, "text-anchor": "end" }, `today${lastPr ? ` · after #${lastPr.pr}` : ""}`);
  if (nA || stop) el("path", { class: "strand todo", d: `M${f(T + 7)} 90 H${f(stop ? termX : AE)}` });
  const boxX = {};
  R.ahead.forEach((a, k) => { const x = TX + 52 * k; boxX[a.day] = x + 23;
    const g = el("g", { class: "b", tabindex: 0, "data-k": "ahead", "data-v": a.day });
    el("rect", { class: "todo-day", x: f(x), y: 80, width: 46, height: 20, rx: 2 }, null, g);
    el("text", { class: "t-todo", x: f(x + 23), y: 93.5, "text-anchor": "middle" }, `Day ${a.day}`, g); });
  if (nA) { el("path", { class: "brk", d: `M${f(TX + 0.5)} 69 V66 H${f(AE - 0.5)} V69` });
    el("text", { class: "t-dayn muted", x: f((TX + AE) / 2), y: 62, "text-anchor": "middle" }, "no spec yet"); }
  if (later) {
    el("rect", { class: "phase later", x: f(LX), y: 32, width: 56, height: 15, rx: 3 });
    el("text", { class: "t-ph later", x: f(LX + 6), y: 43 }, `Phase ${later.phase}`);
    el("path", { class: "strand later", d: `M${f(LX)} 90 H${f(LX + 56)}` });
    el("text", { class: "t-sec", x: f(LX + 28), y: 112, "text-anchor": "middle" }, `from Day ${later.from_day},`);
    el("text", { class: "t-sec", x: f(LX + 28), y: 123, "text-anchor": "middle" }, "not specified");
  }
  // the hand-offs: a closed one as an arc under the strand, from where it was opened to where it was closed
  const arcs = [], pairs = {};
  R.h.forEach((x, j) => {
    if (x.c == null) return;
    const key = `${x.o} ${x.c}`, k = pairs[key] = (pairs[key] || 0) + 1, a = X[x.o], b = X[x.c];
    const depth = Math.min(184, 14 + 0.4 * Math.abs(b - a) + 4.4 * (k - 1)), d = `M${f(a)} 164 Q${f((a + b) / 2)} ${f(164 + depth)} ${f(b)} 164`;
    const g = el("g", { class: `b ho ${x.how || "picked"}`, tabindex: 0, "data-k": "h", "data-v": j, "data-o": x.o, "data-c": x.c });
    el("path", { class: "v", d }, null, g); el("path", { class: "hitp", d }, null, g); arcs[j] = g;
  });
  // an open one runs down and along to the Day it waits for, the ones from one merge side by side
  const from = {}, seen = {};
  opens.forEach(o => { from[o.x.o] = (from[o.x.o] || 0) + 1; });
  const waits = {};
  opens.forEach((o, k) => {
    const x = o.x, y = rows[k], i = seen[x.o] = (seen[x.o] == null ? 0 : seen[x.o] + 1), sx = X[x.o] - 1.7 * (from[x.o] - 1) / 2 + 1.7 * i;
    const tx = x.w in boxX ? boxX[x.w] : stop ? termX + 3 : T, d = `M${f(sx)} 164 V${f(y - 5)} Q${f(sx)} ${f(y)} ${f(sx + 5)} ${f(y)} H${f(tx - 2.6)}`;
    const g = el("g", { class: `b ho open${x.id ? " num" : ""}`, tabindex: 0, "data-k": "h", "data-v": o.j, "data-o": x.o });
    el("path", { class: "v", d }, null, g); el("circle", { class: "oend", cx: f(tx), cy: f(y), r: 2.2 }, null, g); el("path", { class: "hitp", d }, null, g);
    arcs[o.j] = g; if (x.w in boxX) (waits[x.w] = waits[x.w] || []).push(y);
  });
  Object.keys(waits).forEach(day => { const ys = waits[day];
    el("path", { class: "guide", d: `M${f(boxX[day])} 101 V${f(ys[0] - 3)}` });
    el("text", { class: "t-n", x: f(boxX[day]), y: f(lastY + 16), "text-anchor": "middle" }, `${ys.length} wait`); });
  fig.setAttribute("aria-label", `Every merge in order, drawn as a gene being read: Days as blocks, the work between Days as thin lines, the promises built under them, today's place, the Days ahead and the stop, and the hand-offs as arcs`);

  // the figures over it, and the key's counts
  const fig4 = (num, of, what, sub) => { const d = h("div"); const v = h("div", "num", String(num), d); if (of != null) h("small", "", ` ${of}`, v); h("div", "what", what, d); h("div", "sub", sub, d); return d; };
  const bk = R.between_kinds || {}, unbuilt = R.written - R.built;
  const neither = nA === 1 ? "it has no spec yet" : nA === 2 ? "neither has a spec yet" : "none has a spec yet";
  $("figs").replaceChildren(
    fig4(R.built, `of ${R.written}`, "promises built", unbuilt > 0 ? `${n(unbuilt, "promise", "promises")} written and never built` : "every promise written is built"),
    fig4(nA, null, stop ? `${nA === 1 ? "Day" : "Days"} left to the stop` : `${nA === 1 ? "Day" : "Days"} the plan lists with no spec`, stop ? `${nA ? neither + "; " : ""}the stop is after Day ${stop.day}` : "the plan names no stop ahead"),
    fig4(R.numbered, `of ${R.open} open`, "numbered hand-offs open", "the rest are notes and test comments that name a Day ahead"),
    fig4(R.between, `of ${R.merges}`, "merges between Days", `${n(R.stretches, "run", "runs")}; ${bk.other || 0} other, ${bk.spec || 0} spec or plan${bk.origin ? ", and the first commit" : ""}`));
  const K = R.kinds || {}, say = (id, t) => { $(id).textContent = t; };
  say("k-between", `(${R.between} in ${n(R.stretches, "stretch", "stretches")})`);
  say("k-pc", `(${bk.spec || 0})`);
  say("k-kinds", `Counted as graph 1 counts them: spec ${K.spec || 0}, code ${K.code || 0}, a Day's close ${K.close || 0}, other ${K.other || 0}${K.origin ? ", and the first commit" : ""}`);
  const d0 = R.days[0]; say("k-bw", d0 ? `${d0.ticked}/${d0.total} under a Day: built of written` : "built of written, under a Day");
  say("k-picked", `(${how.picked || 0})`); say("k-lapsed", `(${how.lapsed || 0})`); say("k-withdrawn", `(${how.withdrawn || 0})`);
  say("k-open", `(${R.open - R.numbered})`); say("k-num", `(${R.numbered})`);
  say("stamp", `Drawn from the page's data at ${R.head}${R.last_pr ? ` (#${R.last_pr})` : ""}, generated ${R.generated} · ${n(R.merges, "merge", "merges")} · the level cards above are graph 1's own`);

  // the lists under it
  const li = (ul, b, text) => { const l = h("li", "", null, ul); h("b", "", b, l); l.append(text); return l; };
  const dayList = ds => andList(ds.map(d => `Day ${d}`));
  const finds = $("finds"); finds.replaceChildren();
  const context = s => `${s.w.replace(/^outside any Day, merged /, "")}${s.next != null ? `, before Day ${s.next}'s ${s.first ? "first" : "next"} merge` : ", up to today"}`;
  li(finds, `${R.between} of the ${R.merges} merges were between Days.`, R.longest.length ? ` The longest ${R.longest.length === 1 ? "stretch" : "stretches"}: ${R.longest.map(s =>
    `${n(s.n, "merge", "merges")}, ${s.n > 1 ? `${s.a ? "#" + s.a : "the first commit"} to #${s.b}` : s.a ? "#" + s.a : "the first commit"} (${context(s)})`).join("; ")}.` : "");
  if (R.cut.length) li(finds, "A Day's work rarely ran in one piece.", ` ${R.cut.map(([d, k]) => `Day ${d} was cut into ${k} fragments`).join(", ")}.${R.unbroken.length ? ` Only ${dayList(R.unbroken)} ran unbroken.` : ""}`);
  if (R.gap.length) li(finds, `${n(R.gap.length, "promise was", "promises were")} written and never built:`,
    ` ${R.gap.map(g => `${g.id}, the hollow dash under Day ${g.d}`).join("; ")}. Nothing ahead builds ${R.gap.length === 1 ? "it" : "them"}.`);
  if (nA) li(finds, `${n(nA, "Day is", "Days are")} left to the ${stop ? "stop" : "end of the plan's list"}, and ${nA === 1 ? "it has no spec" : nA === 2 ? "neither has a spec" : "none has a spec"}.`,
    ` ${R.ahead.map(a => `Day ${a.day}${a.n ? ` is ${a.n}` : ""}, and ${n(a.w.length, "open hand-off waits", "open hand-offs wait")} for it`).join("; ")}. Their size cannot be drawn until their specs are written.`);
  R.lifted.forEach(s => li(finds, `The stop after Day ${s.day} was lifted.`, ` ${n(s.between, "merge", "merges")} went by between it and the next Day's first merge.`));
  const opened = $("opens"); opened.replaceChildren();
  R.opens.forEach(o => { const short = o.x.length > 150 ? o.x.slice(0, 150).replace(/\s+\S*$/, "") + "…" : o.x;
    const l = li(opened, o.id, `${o.to != null ? `, for Day ${o.to}` : ""}, opened at ${o.pr ? "#" + o.pr : "the first commit"}: ${short}`); l.setAttribute("tabindex", "0"); l.dataset.h = String(o.h);
    ["pointerover", "focusin"].forEach(ev => l.addEventListener(ev, () => lightH(o.h))); ["pointerleave", "focusout"].forEach(ev => l.addEventListener(ev, clear)); });
  if (!R.opens.length) h("li", "", "None.", opened);
  const bends = $("bends"); bends.replaceChildren();
  const cutAll = R.days.filter(d => d.frags > 1).length, whole = R.unbroken;
  [["An intron is cut out; this work is not.", " In a cell an intron is removed from the transcript. The merges between Days are tooling, the dashboard and plan changes: they build no promise, and the Days run on them."],
    ["A gene's exons do not interleave.", ` Here ${R.strayed.length ? `${dayList(R.strayed)} ${R.strayed.length === 1 ? "has a fragment" : "have fragments"} away from ${R.strayed.length === 1 ? "its span" : "their spans"}, and ` : ""}${cutAll ? (whole.length ? `every Day but ${andList(whole.map(String))} was cut by merges between Days` : "every Day was cut by merges between Days") : "no Day was cut"}. The picture keeps the true order; the bracket is the Day's main span.`],
    ...(nA ? [["The Days ahead have no width.", ` ${dayList(R.ahead.map(a => a.day))} ${nA === 1 ? "has" : "have"} no spec, so nothing says how many merges or promises they hold. Their boxes are one size and mean nothing by it.`]] : []),
    ["Between Days is squeezed.", ` A cell of a Day is ${PC.toFixed(1)} px wide; a stretch between Days is 6 px and half a pixel for each merge, so its length understates it. The number over it is the count.`],
    ["No dates.", " The strand is in merge order. A long stretch may be one afternoon; graph 10 has the clock."]].forEach(([b, t]) => li(bends, b, t));

  // the pointer box, and what it lights: a hand-off's two merges, or a merge's hand-offs
  const show = (k, v) => { const d = rdgTip(R, k, v); if (!d) return false; tip.replaceChildren(); h("div", "t", d.t, tip); if (d.q) h("div", "q", d.q, tip);
    d.l.filter(Boolean).forEach(l => h("div", "l", l, tip)); tip.hidden = false; return true; };
  const place = (x, y) => { const w = tip.offsetWidth, ht = tip.offsetHeight; let t = y + 18; if (t + ht > innerHeight - 8) t = Math.max(8, y - ht - 12);
    tip.style.left = Math.max(8, Math.min(x + 14, innerWidth - w - 8)) + "px"; tip.style.top = t + "px"; };
  const lit = [];
  function clear() { fig.classList.remove("foc"); lit.splice(0).forEach(e => e.classList.remove("lit")); }
  const light = e => { if (e) { e.classList.add("lit"); lit.push(e); } };
  function lightH(j) { clear(); const x = R.h[+j]; if (!x || !arcs[+j]) return; light(arcs[+j]); [x.o, x.c].forEach(i => light(cells[i])); fig.classList.add("foc"); }
  const focusOn = b => { const k = b.getAttribute("data-k"), v = b.getAttribute("data-v");
    if (k === "h") return lightH(v);
    clear();
    if (k === "m") { const mine = R.h.map((x, j) => x.o === +v || x.c === +v ? arcs[j] : null).filter(Boolean); if (!mine.length) return; mine.forEach(light); light(b); fig.classList.add("foc"); } };
  const mark = e => e.target && e.target.closest ? e.target.closest(".b") : null;
  fig.addEventListener("pointerover", e => { const b = mark(e); if (b && show(b.getAttribute("data-k"), b.getAttribute("data-v"))) { place(e.clientX, e.clientY); focusOn(b); } else { tip.hidden = true; clear(); } });
  fig.addEventListener("pointermove", e => { if (!tip.hidden) place(e.clientX, e.clientY); });
  fig.addEventListener("pointerleave", () => { tip.hidden = true; clear(); });
  fig.addEventListener("focusin", e => { const b = mark(e); if (b && show(b.getAttribute("data-k"), b.getAttribute("data-v"))) { const r = b.getBoundingClientRect(); place(r.left, r.bottom); focusOn(b); } });
  fig.addEventListener("focusout", () => { tip.hidden = true; clear(); });
  if (typeof addEventListener === "function") addEventListener("scroll", () => { tip.hidden = true; }, { passive: true });
  // a Day chosen on the page's buttons: its merges, its promises and its hand-offs stay as they are, the rest fade
  const own = (i, day) => i != null && m[i] && m[i].own === day;
  onDay.push(day => {
    Object.keys(cells).forEach(i => cells[i].classList.toggle("mk-dim", day != null && !own(+i, day)));
    stretches.forEach(r => r.classList.toggle("mk-dim", day != null));
    qs.forEach(q => q.classList.toggle("mk-dim", day != null && q.dataset.day !== String(day)));
    R.h.forEach((x, j) => { if (!arcs[j]) return; const on = day != null && (own(x.o, day) || own(x.c, day));
      arcs[j].classList.toggle("day", on); arcs[j].classList.toggle("mk-dim", day != null && !on); });
  });
  return fig;
}

/* The merge graph, drawn, in graph 6's place: the spec as one long bar, one stripe per criterion, and above it a row
   per Day (or per merge) marking the criteria each merge gave evidence for and the times the replay saw one stop
   holding. Layout only, as the mockup at #228 drew it: every count it prints is in DATA.merge_graph, counted by
   scripts/spec_drift_views.py (merge_graph), for all Days (`all`) and for each Day (`by_day`). `get` finds an element
   by its id; `onDay` is the page's Day buttons. Colours are in dashboard.css, under #mrg. */
function mergeDraw(D, get, onDay) {
  const NS = "http://www.w3.org/2000/svg";
  const crit = D.crit, merges = D.merges, events = D.events;
  const $ = id => get("mrg-" + id);
  const comma = n => n.toLocaleString("en-US");
  const plural = (n, w) => `${comma(n)} ${w}${n === 1 ? "" : "s"}`;
  const criteria = n => n === 1 ? "1 criterion" : `${comma(n)} criteria`;
  const dayName = d => d === 0 ? "Start" : "Day " + d;
  const prI = new Map(merges.map((m, i) => [m.pr, i]));
  const byId = new Map(crit.map(c => [c.id, c]));
  const at = p => merges[prI.get(p)];
  crit.forEach((c, i) => { c.i = i; });
  const loose = merges.filter(m => m.loose);
  const STALE = "break no longer applies";
  // a merge drawn only because the replay looked there: it first noticed a stop, or saw one hold again, at it
  const NOCITE = { stop: "no criterion cites this merge; the replay first noticed the stop here, at a sampled merge",
    held: "no criterion cites this merge; the replay first saw it hold again here, at a sampled merge" };
  // the suspect window of one stop: the merges after the last replay where it held, up to the one where it failed
  const hash = ps => ps.map(p => "#" + p).join(", ");
  const winText = e => e.lo == null ? "It was not holding at its first replay, so there is no window." : `Last held at #${e.lo}. The window up to #${e.pr} holds ${plural(e.wn, "merge")}; ${e.sus.length ? `product code changed in ${e.sus.length}: ${hash(e.sus)}` : "none changed product code"}.`;
  const dayTitle = {}; D.days.forEach(d => { dayTitle[d.day] = d.title; });
  // a later criterion naming an earlier merge: sometimes a hold citing the work it guards, sometimes a number in its own wording
  const early = (m, i) => m.early.includes(i);
  const down = c => c.st === "bad" || c.st === "stale";
  const chain = c => { const out = []; let cur = c; while (cur.rep.length && out.length < 9) { const nx = byId.get(cur.rep[0]); if (!nx) break; out.push(nx); cur = nx; } return out; };
  const stWord = c => c.st === "ok" ? "holds" : c.st === "un" ? "holds, with no break on purpose recorded" : down(c) ? `is not holding ("${c.why}")` : c.lp ? `is not run by the replay ("${c.why}")` : "was never run by the replay";

  // one finding per criterion that ever stopped holding and one per uncited merge, numbered left to right as drawn
  const finds = D.finds.map(f => f.kind === "loose" ? { kind: f.kind, n: f.n, m: at(f.pr) } : { kind: f.kind, n: f.n, c: crit[f.c], ev: events.filter(e => e.c === f.c) });
  const view = () => state.day == null ? D.all : D.by_day[state.day];

  const svg = $("g"), tip = $("tip");
  const el = (n, a, txt, parent) => { const e = document.createElementNS(NS, n); for (const k in a) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; (parent || svg).appendChild(e); return e; };
  const h = (tag, cls, txt, parent) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; if (parent) parent.appendChild(e); return e; };
  // push labels apart along one line until none overlap
  const spread = (xs, s, lo, hi) => {
    const p = xs.slice(); if (!p.length) return p;
    for (let it = 0; it < 200; it++) { let moved = false;
      for (let i = 1; i < p.length; i++) { const d = p[i] - p[i - 1]; if (d < s - .01) { const sh = (s - d) / 2; p[i - 1] -= sh; p[i] += sh; moved = true; } }
      if (p[0] < lo) { p[0] = lo; moved = true; } if (p[p.length - 1] > hi) { p[p.length - 1] = hi; moved = true; }
      if (!moved) break; }
    return p;
  };
  const state = { view: "day", day: null };

  function draw() {
    svg.replaceChildren();
    const zoom = state.day, big = zoom != null, byMerge = big || state.view === "merge", V = view();
    svg.setAttribute("class", big ? "g" : state.view === "merge" ? "g all tight" : "g all");
    const cs = crit.filter(c => !big || c.day === zoom), inC = new Set(cs.map(c => c.i));
    const evs = events.filter(e => inC.has(e.c));
    const ms = V.merges.map(at), ls = V.loose.map(at);
    const fs = finds.filter(f => V.finds[f.kind].includes(f.n));
    // rows, each with the counts merge_graph gave it
    let rows;
    if (byMerge) rows = ms.map(m => ({ day: m.day, label: "#" + m.pr, ms: [m], ran: m.rp ? 1 : 0, drawn: 1, stopped: V.stopped[m.pr] || 0, nocite: m.nocite.length ? 1 : 0 }));
    else { const by = new Map(); ms.forEach(m => { if (!by.has(m.day)) by.set(m.day, []); by.get(m.day).push(m); }); rows = [...by.keys()].sort((a, b) => a - b).map(d => Object.assign({ day: d, label: dayName(d), ms: by.get(d) }, V.rows.find(q => q.day === d))); }
    const X0 = big ? 326 : 160, U = big ? Math.max(22, Math.min(46, Math.floor(640 / cs.length))) : 5, DG = 6, T0 = 50;
    const RH = big ? 16 : byMerge ? 11 : 17, RG = byMerge ? 5 : 0, CH = big ? 30 : 26, UL = big ? 20 : 12, BW = 96, SH = 9, BR = big ? 8.5 : 7.5;
    let y = T0; rows.forEach((r, i) => { if (i && rows[i - 1].day !== r.day) y += RG; r.y = y; r.i = i; y += RH; });
    const CY = y + 8, SY = CY + CH + 4, TY = SY + SH + 2, BY = SY + SH + 21 + BR;
    const stag = big && U < 42, IDY = BY + BR + 15, DLY = big ? IDY + (stag ? 12 : 0) : BY + BR + 16;
    const rowOf = new Map(); rows.forEach(r => r.ms.forEach(m => rowOf.set(m.pr, r.i)));
    // columns
    const cols = {}; let x = X0;
    cs.forEach((c, k) => { if (k && cs[k - 1].day !== c.day) x += DG; c.x = x; (cols[c.day] = cols[c.day] || { x0: x }).x1 = x + U; x += U; });
    const SPX1 = x, FW = 34, fut = big ? [] : D.future; fut.forEach(f => { x += DG; f.x0 = x; x += FW; });
    const LX0 = x + 30, LX1 = LX0 + ls.length * UL, base = ls.length ? LX1 : x, KX = base + 62, SX = base + 138, W = SX + BW + 14, H = DLY + 10;
    ls.forEach((m, k) => { m.lx = LX0 + k * UL; });
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.style.minWidth = Math.min(W, big ? 1000 : 1180) + "px"; svg.style.maxWidth = big ? Math.round(W * 1.08) + "px" : "";
    svg.setAttribute("aria-label", `${criteria(V.criteria)} as one banded bar, in Day order. ${rows.length} rows above it, one per ${byMerge ? "merge" : "Day"}, mark the criteria each one gave evidence for and the ${V.events} times a criterion stopped holding. The numbered list under the graph names each one.`);
    const defs = el("defs", {});
    const pat = el("pattern", { id: "mrg-hatch", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, null, defs);
    el("rect", { width: 6, height: 6, fill: "var(--wash)" }, null, pat); el("line", { x1: 1, y1: 0, x2: 1, y2: 6, stroke: "var(--hot)", "stroke-width": 1.8 }, null, pat);

    // headings
    el("text", { x: (X0 + SPX1) / 2, y: 16, "text-anchor": "middle", class: "strong" }, big ? `${dayName(zoom)} · ${criteria(V.criteria)}` : `The spec · ${criteria(V.criteria)}`);
    if (ls.length) { el("text", { x: (LX0 + LX1) / 2, y: 16, "text-anchor": "middle", class: "strong" }, "No criterion"); el("text", { x: (LX0 + LX1) / 2, y: 31, "text-anchor": "middle", class: "strong" }, `cites it · ${V.finds.loose.length}`); }
    el("text", { x: SX + BW / 2, y: 16, "text-anchor": "middle", class: "strong" }, byMerge ? "Lines per merge" : "Lines per Day");
    el("text", { x: big ? X0 - 24 : X0 - 3, y: T0 - 7, "text-anchor": big ? "middle" : "end", class: "col" }, "Replay ran");
    el("text", { x: KX, y: 16, "text-anchor": "middle", class: "strong" }, "Stopped");
    el("text", { x: KX, y: T0 - 7, "text-anchor": "middle", class: "col" }, "first seen here");
    // Days plan.md lists that have no spec yet: an empty dashed column each, and an empty piece of the bar
    fut.forEach(f => {
      const mid = f.x0 + FW / 2, my = (T0 + y) / 2;
      el("text", { x: mid, y: T0 - 7, "text-anchor": "middle", class: "col" }, dayName(f.day));
      el("text", { x: mid, y: DLY, "text-anchor": "middle", class: "col" }, dayName(f.day));
      el("rect", { x: f.x0 + .5, y: T0 + 1, width: FW - 1, height: y - T0 - 2, rx: 2, fill: "none", stroke: "var(--axis)", "stroke-width": 1, "stroke-dasharray": "3 3" });
      el("text", { x: mid, y: my, dy: 3.5, "text-anchor": "middle", class: "col", transform: `rotate(-90 ${mid} ${my})` }, "not due · no spec yet");
      el("rect", { x: f.x0 + .5, y: CY + .5, width: FW - 1, height: CH - 1, rx: 5, fill: "var(--card)", stroke: "var(--muted)", "stroke-width": 1.2, "stroke-dasharray": "3 3" });
    });
    if (!big) Object.keys(cols).forEach(d => {
      const mid = (cols[d].x0 + cols[d].x1) / 2;
      el("text", { x: mid, y: T0 - 7, "text-anchor": "middle", class: "col" }, dayName(+d));
      el("text", { x: mid, y: DLY, "text-anchor": "middle", class: "col" }, dayName(+d));
    });

    // row tracks (hatched where the replay never ran), the shaded steps, labels, and the bars at the right
    const maxL = Math.max(...rows.map(r => r.ms.reduce((s, m) => s + m.prod + m.test, 0)), 1);
    rows.forEach((r, i) => {
      const track = r.ran ? "var(--wash)" : "url(#mrg-hatch)";
      const st = r.stopped;
      if (st || !byMerge || big) el("text", { x: KX, y: r.y + RH - (byMerge && !big ? 2 : 5), "text-anchor": "middle", class: st ? "num stopn" : "num zero" }, st);
      Object.keys(cols).forEach(d => el("rect", { x: cols[d].x0, y: r.y + 1, width: cols[d].x1 - cols[d].x0, height: RH - 2, rx: 1.5, fill: +d === r.day ? "var(--hot)" : track }));
      if (ls.length) el("rect", { x: LX0, y: r.y + 1, width: LX1 - LX0, height: RH - 2, rx: 1.5, fill: track });
      // a row no criterion cites: a dashed outline over its track, its label in italics; in a Day's row, how many
      if (byMerge && r.nocite) el("rect", { class: "nocite", x: X0 - .5, y: r.y + .5, width: SPX1 - X0 + 1, height: RH - 1, rx: 2, fill: "none", stroke: "var(--ink-2)", "stroke-width": 1.1, "stroke-dasharray": "4 2" });
      if (big) { const m = r.ms[0], t = `#${m.pr}  ${m.title}`; el("text", { x: 6, y: r.y + RH - 4.4, class: r.nocite ? "prz ncl" : "prz" }, t.length > 50 ? t.slice(0, 49) + "…" : t); }
      else if (byMerge) {
        if (!i || rows[i - 1].day !== r.day) el("text", { x: 6, y: r.y + 9, class: "day" }, dayName(r.day));
        el("text", { x: X0 - 40, y: r.y + RH - 2.2, "text-anchor": "end", class: r.nocite ? "pr ncl" : "pr" }, r.label);
      } else {
        el("text", { x: X0 - 54, y: r.y + RH - 4.6, "text-anchor": "end", class: "day" }, r.label);
        if (r.nocite) el("text", { x: 6, y: r.y + RH - 4.8, class: "nc" }, `${r.nocite} uncited`);
      }
      if (byMerge) el("circle", { cx: X0 - 24, cy: r.y + RH / 2, r: big ? 3.2 : 2.4, fill: r.ran ? "var(--ink-2)" : "var(--card)", stroke: "var(--ink-2)", "stroke-width": 1 });
      else el("text", { x: X0 - 24, y: r.y + RH - 5, "text-anchor": "middle", class: "num" }, `${r.ran} of ${r.drawn}`);
      const prod = r.ms.reduce((s, m) => s + m.prod, 0), test = r.ms.reduce((s, m) => s + m.test, 0);
      if (prod + test) {
        el("text", { x: SX - 6, y: r.y + RH - (byMerge && !big ? 2 : 5), "text-anchor": "end", class: "num" }, comma(prod + test));
        const pw = prod / maxL * BW, tw = test / maxL * BW, bh = RH - (byMerge && !big ? 4 : 8), by = r.y + (RH - bh) / 2;
        if (prod) el("rect", { x: SX, y: by, width: Math.max(pw, 1), height: bh, fill: "var(--ink-2)" });
        if (test) el("rect", { x: SX + (prod ? Math.max(pw, 1) + 1 : 0), y: by, width: Math.max(tw, 1), height: bh, fill: "var(--axis)" });
      }
    });

    // the red lines: from the merge where a criterion stopped holding to the one where it held again
    const MW = big ? Math.min(U - 8, 20) : U - 1.6, MO = (U - MW) / 2;
    // the suspect window: the rows after the last replay where the criterion held, above its mark
    const inWin = (e, r) => r.ms.filter(m => m.n > e.lon && m.n < e.n);
    evs.forEach(e => {
      const r0 = rows[rowOf.get(e.pr)]; if (!r0 || e.lon == null) return;
      rows.forEach(r => { if (r.i >= r0.i) return; const w = inWin(e, r); if (!w.length) return;
        el("rect", { x: crit[e.c].x + .3, y: r.y, width: U - .6, height: RH, class: w.some(m => m.prod > 0) ? "whi" : "wlo" }); });
    });
    evs.forEach(e => {
      const r0 = rows[rowOf.get(e.pr)], r1 = e.end != null ? rows[rowOf.get(e.end)] : null; if (!r0) return;
      const y1 = r0.y + RH - 1, y2 = r1 ? r1.y + 1 : CY, cx = crit[e.c].x + U / 2;
      if (y2 > y1) { const a = { x1: cx, y1, x2: cx, y2, stroke: "var(--c-bad)", "stroke-width": big ? 1.6 : 1.2 }; if (e.state === STALE) a["stroke-dasharray"] = "2.5 2.5"; el("line", a); }
    });

    // marks
    rows.forEach(r => {
      const seen = new Set();
      r.ms.forEach(m => m.lands.forEach(i => {
        if (!inC.has(i) || seen.has(i)) return; seen.add(i);
        const a = { x: crit[i].x + MO, y: r.y + 1, width: MW, height: RH - 2, rx: 1, fill: crit[i].tag === "hold" ? "var(--c-guard)" : "var(--c-in)" };
        if (crit[i].tag === "hold") { a.stroke = "var(--muted)"; a["stroke-width"] = .6; }
        if (early(m, i)) a.opacity = .38;
        el("rect", a);
      }));
      r.ms.forEach(m => { if (ls.includes(m)) el("rect", { x: m.lx + 2, y: r.y + 1, width: UL - 4, height: RH - 2, rx: 1, fill: "var(--c-unpl)" }); });
    });
    evs.forEach(e => {
      const r = rows[rowOf.get(e.pr)], stale = e.state === STALE; if (!r) return;
      el("rect", { x: crit[e.c].x + MO + (stale ? .2 : -.4), y: r.y + (stale ? 1.4 : 1), width: MW + (stale ? -.4 : .8), height: RH - (stale ? 2.8 : 2), rx: 1, fill: stale ? "var(--card)" : "var(--c-bad)", stroke: "var(--c-bad)", "stroke-width": stale ? 1.2 : 0 });
    });

    // the bar: one piece per Day, one stripe per criterion; under it the strip of each criterion's last replay state
    const maxT = Math.max(...crit.map(c => c.nt), 1);
    const piece = (id, x0, x1) => { const r = { x: x0, y: CY, width: x1 - x0, height: CH, rx: 5 }; el("rect", r, null, el("clipPath", { id }, null, defs)); const g = el("g", { "clip-path": `url(#${id})` }); el("rect", Object.assign({ fill: "var(--card)" }, r), null, g); return g; };
    const gs = {}; Object.keys(cols).forEach(d => { gs[d] = piece("mrg-cp-d" + d, cols[d].x0, cols[d].x1); });
    cs.forEach((c, k) => {
      el("rect", { x: c.x, y: CY, width: U, height: CH, fill: c.nt ? "var(--ink)" : "var(--card)", "fill-opacity": c.nt ? .14 + .86 * Math.sqrt(c.nt / maxT) : 1, stroke: "var(--card)", "stroke-width": .6 }, null, gs[c.day]);
      const cx = c.x + U / 2, sx = c.x + (big ? 4 : .7), sw = U - (big ? 8 : 1.4), dim = c.rep.length ? .5 : 1;
      if (c.st === "ok") el("rect", { x: sx, y: SY, width: sw, height: SH, rx: .8, fill: "var(--c-ok)", opacity: dim });
      else if (c.st === "un") el("rect", { x: sx + .6, y: SY + .6, width: sw - 1.2, height: SH - 1.2, rx: .8, fill: "var(--card)", stroke: "var(--c-ok)", "stroke-width": 1.2, opacity: dim });
      else if (c.st === "bad") el("rect", { x: sx, y: SY, width: sw, height: SH, rx: .8, fill: "var(--c-bad)" });
      else if (c.st === "stale") el("rect", { x: sx + .6, y: SY + .6, width: sw - 1.2, height: SH - 1.2, rx: .8, fill: "var(--card)", stroke: "var(--c-bad)", "stroke-width": 1.2 });
      else if (c.st === "due") el("rect", { x: sx + .5, y: SY + .5, width: sw - 1, height: SH - 1, rx: .8, fill: "var(--card)", stroke: "var(--muted)", "stroke-width": 1, "stroke-dasharray": "1.8 1.4" });
      else el("rect", { x: sx, y: SY + SH / 2 - .8, width: sw, height: 1.6, fill: "var(--muted)" });
      if (c.rep.length) el("path", { d: `M${cx} ${TY} l-2.8 5.2 h5.6 z`, fill: "var(--ink-2)" });
      if (big) el("text", { x: cx, y: IDY + (stag ? (k % 2) * 12 : 0), "text-anchor": "middle", class: "cid" }, c.id);
    });
    Object.keys(cols).forEach(d => el("rect", { x: cols[d].x0, y: CY, width: cols[d].x1 - cols[d].x0, height: CH, rx: 5, fill: "none", stroke: "var(--c-line)", "stroke-width": 1 }));
    if (ls.length) {
      const g = piece("mrg-cp-loose", LX0, LX1);
      ls.forEach(m => el("rect", { x: m.lx, y: CY, width: UL, height: CH, fill: "var(--c-unpl)", stroke: "var(--card)", "stroke-width": .6 }, null, g));
      el("rect", { x: LX0, y: CY, width: LX1 - LX0, height: CH, rx: 5, fill: "none", stroke: "var(--c-line)", "stroke-width": 1 });
    }

    // the numbers: one badge per finding, in a lane under the bar, pushed apart so none overlap
    const lane = fs.map(f => ({ f, ax: f.c ? f.c.x + U / 2 : f.m.lx + UL / 2 })).sort((a, b) => a.ax - b.ax);
    const bx = spread(lane.map(b => b.ax), 2 * BR + 2, BR + 2, W - BR - 2);
    lane.forEach((b, k) => {
      const f = b.f, col = f.kind === "loose" ? "var(--c-unpl)" : f.kind === "back" ? "var(--muted)" : "var(--c-bad)", solid = f.kind === "fix" || f.kind === "loose";
      el("line", { x1: b.ax, y1: f.c ? TY + (f.c.rep.length ? 6.4 : -1) : CY + CH + 1, x2: bx[k], y2: BY - BR, stroke: "var(--muted)", "stroke-width": .7 });
      el("circle", { cx: bx[k], cy: BY, r: BR, fill: solid ? col : "var(--card)", stroke: col, "stroke-width": 1.4 });
      el("text", { x: bx[k], y: BY + 3.2, "text-anchor": "middle", class: "bn", style: `fill:${f.kind === "fix" ? "var(--card)" : f.kind === "loose" ? "var(--on-unpl)" : "var(--ink)"}` }, f.n);
    });

    // hover: a crosshair over the whole graph, so no mark has to be hit exactly
    const rowHi = el("rect", { x: 0, width: W, height: RH, fill: "var(--ink)", "fill-opacity": .09, "pointer-events": "none", visibility: "hidden" });
    const colHi = el("rect", { y: T0 - 2, width: U, height: SY + SH - T0 + 2, fill: "var(--ink)", "fill-opacity": .13, "pointer-events": "none", visibility: "hidden" });
    const hit = el("rect", { class: "hit", x: 0, y: T0 - 2, width: W, height: H - T0 + 2, fill: "transparent" });
    const line = (cls, txt) => h("div", cls, txt, tip);
    const rel = (color, txt, hollow) => { const d = line("r", ""); const i = document.createElement("i"); if (hollow) { i.style.border = `1.6px solid ${color}`; i.style.boxSizing = "border-box"; } else i.style.background = color; d.append(i, txt); };
    const critLines = c => {
      line("t", `${c.id} · ${dayName(c.day)} · ${c.tag}`); if (c.txt) line("", c.txt);
      line("s", `${c.nt ? "names " + plural(c.nt, "test") : "names no test"} · cites ${c.prs.map(p => "#" + p).join(", ")}${c.rep.length ? " · replaced by " + c.rep.join(", ") : ""}`);
      line("s", c.lp ? `The replay last ran it at #${c.lp}, ${plural(c.nc, "time")} in all: "${c.why}".` : "The replay never ran it.");
    };
    const rowLines0 = r => {
      if (r.ms.length === 1) { const m = r.ms[0]; line("m", `#${m.pr} · ${m.date}`); line("", m.title); line("s", `${comma(m.prod)} product lines, ${comma(m.test)} test lines · gives evidence to ${criteria(m.lands.length)} · ${m.rp ? "the replay ran here" : "the replay never ran here"}`); m.nocite.forEach(k => line("s", NOCITE[k])); }
      else {
        line("t", `${dayName(r.day)}${dayTitle[r.day] ? ": " + dayTitle[r.day] : ""}`); line("s", `${plural(r.drawn, "merge")} drawn · the replay ran at ${r.ran}`);
        r.ms.filter(m => m.nocite.length).forEach(m => m.nocite.forEach(k => line("s", `#${m.pr}: ${NOCITE[k]}`)));
      }
    };
    const rowLines = r => { rowLines0(r); const st = evs.filter(e => rowOf.get(e.pr) === r.i); if (r.stopped) rel("var(--c-bad)", `${criteria(r.stopped)} first seen not holding here: ${st.map(e => crit[e.c].id).join(", ")}.`); };
    const move = ev => {
      const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY; const p = pt.matrixTransform(svg.getScreenCTM().inverse());
      const r = rows.find(q => p.y >= q.y && p.y < q.y + RH);
      const c = p.x >= X0 && p.x < SPX1 ? cs.find(q => p.x >= q.x && p.x < q.x + U) : null, ci = c ? c.i : -1;
      const lm = ls.find(m => p.x >= m.lx && p.x < m.lx + UL);
      const fu = fut.find(f => p.x >= f.x0 && p.x < f.x0 + FW);
      const onBar = p.y >= CY && p.y <= BY + BR;
      tip.replaceChildren();
      rowHi.setAttribute("visibility", r ? "visible" : "hidden"); if (r) rowHi.setAttribute("y", r.y);
      colHi.setAttribute("visibility", c ? "visible" : "hidden"); if (c) colHi.setAttribute("x", c.x);
      if (c) {
        critLines(c);
        if (r) {
          const on = evs.filter(e => e.c === ci && rowOf.get(e.pr) === r.i);
          const within = evs.filter(e => e.c === ci && rowOf.get(e.pr) < r.i && (e.end == null || rowOf.get(e.end) > r.i));
          const lands = r.ms.filter(m => m.lands.includes(ci));
          const win = evs.filter(e => e.c === ci && e.lon != null && rowOf.get(e.pr) > r.i && inWin(e, r).length);
          if (lands.length || on.length || within.length || win.length) line("m", byMerge ? `#${r.ms[0].pr} · ${r.ms[0].title}` : dayName(r.day));
          lands.forEach(m => rel(c.tag === "hold" ? "var(--c-guard)" : "var(--c-in)", early(m, ci) ? `The criterion names #${m.pr}, a merge from before its Day. It may be a number in its wording, not evidence.` : `${byMerge ? "This merge" : "#" + m.pr} is evidence the criterion cites.`));
          on.forEach(e => { rel("var(--c-bad)", `The replay first reports "${e.state}" at #${e.pr}${e.end ? ", and it holds again at #" + e.end : ", and it has not come back"}.`, e.state === STALE); if (e.detail) line("s", `${e.check ? e.check + ": " : ""}${e.detail}`); line("s", winText(e)); });
          win.forEach(e => { const hot = inWin(e, r).filter(m => m.prod > 0); rel("var(--c-bad)", `In the suspect window: it last held at #${e.lo}, and the replay saw "${e.state}" at #${e.pr}.`, true); line("s", hot.length ? `Product code changed here in ${hash(hot.map(m => m.pr))}.` : "No merge here changed product code."); });
          within.forEach(e => rel("var(--c-bad)", `Not holding here: "${e.state}" since #${e.pr}.`, e.state === STALE));
          if (byMerge) r.ms[0].nocite.forEach(k => line("s", NOCITE[k]));
        }
      } else if (lm && (onBar || (r && r.ms.includes(lm)))) { line("m", `#${lm.pr} · ${lm.date}`); line("", lm.title); rel("var(--c-unpl)", `${plural(lm.prod, "product line")} changed, and no criterion cites this merge.`); }
      else if (fu) { line("t", `${dayName(fu.day)}: ${fu.title}`); line("", "Not due. plan.md lists this Day and specs/ has no spec for it, so it has no criteria yet."); line("s", `${plural(fu.ho, "hand-off")} and ${plural(fu.pc, "plan commitment")} name it.`); }
      else if (r) rowLines(r);
      if (!tip.childNodes.length) { tip.hidden = true; return; }
      tip.hidden = false;
      const b = tip.getBoundingClientRect(), vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
      let tx = ev.clientX + 16, ty = ev.clientY + 16;
      if (tx + b.width > vw - 8) tx = Math.max(8, ev.clientX - b.width - 16);
      if (ty + b.height > vh - 8) ty = Math.max(8, ev.clientY - b.height - 16);
      tip.style.left = tx + "px"; tip.style.top = ty + "px";
    };
    const leave = () => { tip.hidden = true; rowHi.setAttribute("visibility", "hidden"); colHi.setAttribute("visibility", "hidden"); };
    hit.addEventListener("pointermove", move); hit.addEventListener("pointerdown", move); hit.addEventListener("pointerleave", leave);

    frame(V, fs, zoom);
    fit();
  }

  // the text of the frame: what a screenshot has to carry without the hover
  function frame(V, fs, zoom) {
    $("frame-h").textContent = zoom == null ? "Merges against criteria" : `${dayName(zoom)}: ${dayTitle[zoom] || ""}`;
    $("stamp").textContent = `the page's data at ${D.head} · after #${D.last_pr} · generated ${D.generated.replace("T", " ")} · the replay ran at ${comma(D.replayed_merges)} merges, #${D.first_replayed_pr} to #${D.newest_pr} · showing ${zoom == null ? "all Days" : dayName(zoom)}`;
    const v = $("verdict"); v.replaceChildren();
    const tile = (sw, num, label, sub) => { const d = h("div", "", null, v), dt = h("dt", "", null, d); if (sw) h("i", sw, null, dt); dt.append(comma(num)); const dd = h("dd", "", label, d); if (sub) h("small", "", sub, dd); };
    V.verdict.forEach(t => tile(t.sw, t.n, t.label, t.sub));

    const box = $("find"); box.replaceChildren();
    const col = () => h("div", "", null, box);
    const group = (parent, title, list, fill) => { h("h3", "", `${title} · ${list.length}`, parent); if (!list.length) { h("p", "none", "None.", parent); return; } const ul = h("ul", "", null, parent); list.forEach(f => { const li = h("li", "", null, ul); h("i", "bd " + (f.kind === "back" ? "" : f.kind), f.n, li); fill(h("div", "", null, li), f); }); };
    const evText = e => `"${e.state}" first seen at #${e.pr}`;
    const a = col();
    group(a, "Not holding, still in force", fs.filter(f => f.kind === "fix"), (d, f) => {
      h("b", "", f.c.id, d); d.append(` · ${f.c.tag} · ${f.ev.map(evText).join("; ")}; the replay last ran it at #${f.c.lp}. No later criterion replaces it.`);
      const e = f.ev[f.ev.length - 1]; if (e.detail) h("small", "", `${e.check ? e.check + ": " : ""}${e.detail}`, d);
    });
    group(a, "Not holding when last run, since replaced", fs.filter(f => f.kind === "retired"), (d, f) => {
      const ch = chain(f.c), end = ch[ch.length - 1];
      h("b", "", f.c.id, d); d.append(` · ${f.c.tag} · ${f.ev.map(evText).join("; ")}; the replay stopped running it after #${f.c.lp}.`);
      h("small", "", `Replaced by ${ch.map(c => c.id).join(" → ")}. ${end.id} ${stWord(end)}${end.lp ? " at #" + end.lp : ""}.`, d);
    });
    const b = col();
    group(b, "Stopped holding and came back", fs.filter(f => f.kind === "back"), (d, f) => {
      h("b", "", f.c.id, d); d.append(` · ${f.ev.map(e => `"${e.state}" #${e.pr} → held again #${e.end}`).join("; ")}`);
    });
    h("h3", "", `Stops grouped by suspect window · ${plural(V.piles.length, "group")}, first seen at ${plural(V.pile_merges, "merge")}`, b);
    if (!V.piles.length) h("p", "none", "None.", b);
    else { const ul = h("ul", "", null, b); V.piles.forEach(g => { const e = events[g.e], li = h("li", "", null, ul); h("i", "bd cnt", g.n, li); const d = h("div", "", null, li); h("b", "", "#" + g.pr, d); d.append(` · ${g.ids.join(", ")}`); h("small", "", winText(e), d); }); }
    const c3 = col();
    group(c3, "Product code no criterion cites", fs.filter(f => f.kind === "loose"), (d, f) => {
      h("b", "", "#" + f.m.pr, d); d.append(` · ${plural(f.m.prod, "product line")} · ${f.m.title}`);
    });
    h("h3", "", `Doubtful citations · ${V.doubt.length}`, c3);
    if (V.doubt.length) { h("p", "", "A criterion names a merge from before its own Day. Often it is a number in the criterion's wording, read as a pull request.", c3); h("p", "mmono", V.doubt.join("  "), c3); }
    else h("p", "none", "None.", c3);

    const notes = $("notes"); notes.replaceChildren();
    const flat = !D.flap.crit_twice && !D.flap.twice;
    [[V.drawn, ` merges drawn; the replay never ran at ${comma(V.dead)} of them (it starts at #${D.first_replayed_pr})`],
     [D.cells, ` replay runs of a criterion at a merge in all: the replay samples, it does not run every criterion at every merge`],
     [D.tests_cited, " tests named by criteria, of " + comma(D.inventory.driver || 0) + " driver tests"],
     [D.flap.crit_twice, ` criteria stopped holding twice: of ${comma(D.flap.series)} single checks the replay followed, ${D.flap.stopped} stopped and ${D.flap.twice} stopped again${flat ? ", so no flapping sign is drawn" : ""}`]]
      .forEach(([k, t]) => { const s = h("span", "", null, notes); h("b", "", comma(k), s); s.append(t); });
  }
  const fit = () => { const sc = $("scroll"); $("narrow").hidden = sc.scrollWidth <= sc.clientWidth + 1; };
  const win = typeof window !== "undefined" && typeof window.addEventListener === "function" ? window : null;
  if (win) win.addEventListener("resize", fit);

  // the table of the same red marks
  const tb = $("ev");
  tb.replaceChildren();
  const td = (tr, cls, txt) => h("td", cls, txt, tr);
  events.slice().sort((a, b) => a.pr - b.pr || a.c - b.c).forEach(e => {
    const tr = document.createElement("tr"), c = crit[e.c], stale = e.state === STALE;
    td(tr, "pr", e.find); td(tr, "id", c.id); td(tr, "", c.txt); td(tr, "pr", e.lo == null ? "never" : "#" + e.lo); td(tr, "pr", "#" + e.pr);
    td(tr, "", e.lo == null ? "not holding at its first replay" : `${plural(e.wn, "merge")}; ${e.sus.length ? "product code changed in " + hash(e.sus) : "none changed product code"}`);
    const s = td(tr, ""), p = h("span", "pill " + (stale ? "stale" : "bad"), null, s); p.append(document.createElement("i"), e.state);
    if (e.detail) h("div", "", e.detail, s);
    td(tr, e.end ? "pr" : "pr open", e.end ? "#" + e.end : "not yet");
    tb.appendChild(tr);
  });
  $("ev-h").textContent = `Where a criterion stopped holding · ${events.length} times, ${D.open_events} still open (the table)`;

  const futureDays = D.future.map(f => dayName(f.day)).join(" and ");
  const cannot = $("cannot"); cannot.replaceChildren();
  [`A red mark means a check the criterion names stopped passing, or its break on purpose stopped applying. Code that leaves the spec where no test looks is not drawn.`,
   `A blue mark links a whole pull request to a criterion, as the criterion's Evidence cites it. Nothing says which of its lines serve the criterion.`,
   `The replay starts at #${D.first_replayed_pr} and runs every criterion at only ${D.all_at.length} merges (${hash(D.all_at)}); at the others it runs the Day's own. So a red mark, and the Stopped count, sit where the replay next looked: ${D.at_all} of the ${events.length} stops were first seen at one of those merges. The count says when a stop was noticed, not which merge caused it.`,
   `The red band is the window the cause lies in. It is as wide as the gap between two looks, ${D.win.min} to ${D.win.max} merges, and the darker rows only say that product code changed there, not that it broke the criterion. Merges are taken in merge order, which is not always number order.`,
   D.flap.crit_twice || D.flap.twice ? `${criteria(D.flap.crit_twice)} stopped holding twice, and ${plural(D.flap.twice, "single check")} stopped again after holding. No flapping sign is drawn yet; one would go beside the criterion's number.`
     : `No criterion, and no single check, stopped holding twice, so there is no flapping sign to draw yet. One would go beside the criterion's number.`,
   D.future.length ? `${futureDays} ${D.future.length === 1 ? "is an empty dashed column: plan.md lists it" : "are empty dashed columns: plan.md lists them"} and no spec exists, so they have no criteria. ${comma(D.nyf)} replay runs reported "not yet in force", a criterion run at a merge from before its own Day had closed; they are not drawn.`
     : `${comma(D.nyf)} replay runs reported "not yet in force", a criterion run at a merge from before its own Day had closed; they are not drawn.`,
   `Once a later criterion replaces one, the replay stops running the old one. Its cell in the strip, and a red line that reaches the bar, show the last state seen, not today's.`,
   `${comma(D.early_n)} faint marks sit above the steps: a later criterion names a merge from before its own Day. Some are real, a hold citing the merge that built what it guards. Some are a number in the criterion's own wording ("wait: #12") that the dashboard reads as a pull request. The real graph would have to tell them apart.`,
   `${comma(D.skipped_total)} merges are not drawn: no criterion cites them and they changed no product code (specs, closes, tooling, the dashboard, docs).`]
    .forEach(t => h("li", "", t, cannot));

  const bm = $("v-merge"), bd = $("v-day"), zs = $("zoom");
  zs.replaceChildren();
  h("option", "", "All Days", zs).value = "";
  D.days.forEach(d => { const t = `${dayName(d.day)}: ${d.title}`; h("option", "", t.length > 58 ? t.slice(0, 57) + "…" : t, zs).value = d.day; });
  const sync = () => { const z = state.day != null; bm.disabled = bd.disabled = z; bm.setAttribute("aria-pressed", z || state.view === "merge"); bd.setAttribute("aria-pressed", !z && state.view === "day"); tip.hidden = true; draw(); };
  // a view can be linked (#mrg-day-10, #mrg-merges); the page's address is only read, never written, so the dashboard's own anchors and scroll stay as they are
  const readHash = () => { const where = typeof location !== "undefined" ? location.hash : ""; const m = /^#mrg-day-(\d+)$/.exec(where), mg = where === "#mrg-merges"; if (!m && !mg) return false; const d = m && +m[1] in dayTitle ? +m[1] : null; state.day = d; state.view = mg ? "merge" : state.view; zs.value = d == null ? "" : d; sync(); return true; };
  bm.addEventListener("click", () => { state.view = "merge"; sync(); });
  bd.addEventListener("click", () => { state.view = "day"; sync(); });
  zs.addEventListener("change", () => { state.day = zs.value === "" ? null : +zs.value; sync(); });
  // the page's Day buttons zoom the graph to that Day, and "All Days" back out
  onDay.push(day => { state.day = day != null && day in dayTitle ? day : null; zs.value = state.day == null ? "" : state.day; sync(); });
  if (win) win.addEventListener("hashchange", readHash);
  if (!readHash()) sync();
}

/* The pointer box of a mockup section: `D` maps a mark's data-k (or what `key(el)` reads) to a title, an optional
   quote and lines, each built as text. Shared by the gel and the proteins. */
function pointerBox(fig, tip, show, key) {
  const place = (x, y) => { const w = tip.offsetWidth, ht = tip.offsetHeight; let t = y + 18; if (t + ht > innerHeight - 8) t = Math.max(8, y - ht - 12);
    tip.style.left = Math.max(8, Math.min(x + 14, innerWidth - w - 8)) + "px"; tip.style.top = t + "px"; };
  const mark = e => e.target && e.target.closest ? e.target.closest(".b") : null;
  fig.addEventListener("pointerover", e => { const b = mark(e); if (b && show(key(b), b)) place(e.clientX, e.clientY); else { tip.hidden = true; show(null); } });
  fig.addEventListener("pointermove", e => { if (!tip.hidden) place(e.clientX, e.clientY); });
  fig.addEventListener("pointerleave", () => { tip.hidden = true; show(null); });
  fig.addEventListener("focusin", e => { const b = mark(e); if (b && show(key(b), b)) { const r = b.getBoundingClientRect(); place(r.left, r.bottom - 10); } });
  fig.addEventListener("focusout", () => { tip.hidden = true; show(null); });
  if (typeof addEventListener === "function") addEventListener("scroll", () => { tip.hidden = true; }, { passive: true });
}
const tipFill = (tip, d) => { tip.replaceChildren(); const div = (c, t) => { const e = document.createElement("div"); e.className = c; e.textContent = t; tip.appendChild(e); };
  div("t", d.t); (d.l || []).filter(Boolean).forEach(l => Array.isArray(l) ? div(l[0], l[1]) : div("l", l)); if (d.q) div("q", d.q); tip.hidden = false; return true; };

/* Graph 2 as a gel, as the mockup at #228 draws it: counted in scripts/spec_drift_views.py (gel); this lays it out and
   words it. `get` finds an element by its id; `onDay` is the page's Day buttons. Colours are in dashboard.css, under #gel. */
// What one of a yardstick's figures is a figure of, as the pointer box says it.
const GEL_NOUN = { cost: ["for each merged pull request"], replies: ["reply for each merged pull request", "replies for each merged pull request"],
  escapes: ["escaped defect", "escaped defects"], parks: ["stop for a person", "stops for a person"], refusals: ["refused call", "refused calls"],
  gates: ["for the gates"], reread: ["token read again for each token written", "tokens read again for each token written"] };
const GEL_SHORT = { cost: "cost", replies: "replies", escapes: "escaped defects", parks: "stops for a person", refusals: "refused calls", gates: "the gates' cost", reread: "re-reading" };
function gelDraw(G, get, onDay) {
  const $ = id => get("gel-" + id), fig = $("fig"), tip = $("tip");
  const el = (n, a, txt, parent) => { const e = document.createElementNS(SVG_NS, n); for (const k in a) if (a[k] != null) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; (parent || fig).appendChild(e); return e; };
  const f = v => (+v).toFixed(1).replace(/\.0$/, "");
  const fmt = (p, v, dec) => p.unit === "$" ? `$${(+v).toFixed(dec == null ? p.decimals : dec)}` : `${(+v).toFixed(dec == null ? p.decimals : dec)}${p.unit || ""}`;
  const avgOf = p => fmt(p, p.average, Math.max(1, p.decimals));
  const noun = (p, v) => { const w = GEL_NOUN[p.key]; return w ? (w.length > 1 && v !== 1 ? w[1] : w[0]) : ""; };
  const said = (p, v, dec) => `${fmt(p, v, dec)}${noun(p, v) ? " " + noun(p, v) : ""}`;
  const nice = v => { const e = Math.pow(10, Math.floor(Math.log10(Math.max(v, 1e-9)))); return [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].map(k => k * e).find(k => k >= v - 1e-9); };
  const wrap = (s, w) => String(s).split(" ").reduce((ls, word) => { const l = ls[ls.length - 1]; if (l && (l + " " + word).length <= w) ls[ls.length - 1] = l + " " + word; else ls.push(word); return ls; }, []);
  const n = (k, one, many) => `${k} ${k === 1 ? one : many}`;
  const P = G.panels, days = G.days, N = days.length, PW = 171.1, D = {}, lastDay = days[days.length - 1];
  const over = p => p.average_over === "days" ? "every Day" : p.average_over === "tokens written" ? "all the tokens written" : p.average_over ? `every ${p.average_over.replace(/s$/, "")}` : "every Day";
  // the line of figures
  const fig3 = (num, small, what, sub) => { const d = h("div", null, h("div", { class: "num" }, String(num), small && h("small", null, small)), h("div", { class: "what" }, what), h("div", { class: "sub" }, sub)); return d; };
  const below = G.below.map(k => GEL_SHORT[k] || k), unjudged = P.filter(p => !p.lower_better).map(p => GEL_SHORT[p.key] || p.key);
  $("figs").replaceChildren(fig3(G.named, null, "yardsticks the plan names", `one panel each, counted at each Day's close, ${N === 1 ? `Day ${days[0]}` : `Days ${days[0]} to ${lastDay}`}`),
    fig3(G.below.length, ` of ${G.judged} judged`, "below their average on the last Day counted",
      (below.length ? `${andList(below).replace(/^./, c => c.toUpperCase())}.` : "None.") + (unjudged.length ? ` Not judged: ${andList(unjudged)}, where no direction is better` : "")),
    ...G.kit.map(k => { const p = P.find(x => x.key === k.key); return fig3(k.above, ` of ${n(k.of, "Day", "Days")}`, `above the kit's figure for ${k.key}`,
      `the kit, with a person driving every step: ${fmt(p, k.kit)}${k.last ? `; the last Day: ${fmt(p, k.last.value)}` : ""}`); }));
  $("k-kit").textContent = G.kit.length ? `${G.kit.length} of the ${G.named} have one: ${andList(G.kit.map(k => k.key))}` : "none of the yardsticks has one";
  $("stamp").textContent = `Drawn from the page's data at ${G.head || "?"}${G.last_pr ? ` (#${G.last_pr})` : ""}, generated ${G.generated} · ${n(G.named, "yardstick", "yardsticks")} · Days ${days[0]} to ${lastDay}`;
  // the figure
  fig.replaceChildren();
  fig.setAttribute("viewBox", `0 0 ${f(P.length * PW)} 307`);
  fig.setAttribute("aria-label", `${P.length} gels side by side, one for each yardstick. In each, a ladder lane with the kit's figure and the average so far, then one lane for each Day from ${days[0]} to ${lastDay} with one band at the height of that Day's figure`);
  const lanes = [];
  P.forEach((p, i) => {
    const X = i * PW, g = el("g", { class: "pan", "data-y": p.key }), top = nice(Math.max(...p.lanes.map(x => x.value || 0), p.kit || 0, p.average || 0, 1e-9));
    const Y = v => 271 - v / top * 172, LX = X + 43, LW = (X + 160.1 - LX) / N;
    wrap(p.name, 28).slice(0, 2).forEach((line, j) => el("text", { class: "t-name", x: f(X), y: 11 + 14 * j }, line, g));
    const v = p.verdict === "better" || p.verdict === "worse" ? p.verdict : "flat";
    if (p.last) {
      el("path", { class: `tri ${v}`, d: v === "better" ? `M${f(X)} 43.5 h9 l-4.5 7z` : `M${f(X)} 50.5 h9 l-4.5 -7z` }, null, g);
      el("text", { class: `t-val ${v === "flat" ? "" : v}`, x: f(X + 14), y: 55 }, fmt(p, p.last.value), g);
      el("text", { class: "t-sub", x: f(X), y: 71 }, `Day ${p.last.day}${p.average != null ? ` · avg ${avgOf(p)}` : ""}`, g);
    }
    el("rect", { class: "box", x: f(X + 23), y: 82, width: 140.1, height: 198, rx: 7 }, null, g);
    el("rect", { class: "track ref", x: f(X + 26), y: 87, width: 15, height: 188, rx: 1.5 }, null, g);
    p.lanes.forEach((x, j) => { el("rect", { class: "track", x: f(LX + j * LW + 0.7), y: 87, width: f(LW - 1.4), height: 188, rx: 1.5 }, null, g);
      el("rect", { class: "well", x: f(LX + j * LW + 1.7), y: 87, width: f(LW - 3.4), height: 3, rx: 1 }, null, g); });
    el("text", { class: "t-ax", x: f(X + 19), y: 102.2, "text-anchor": "end" }, fmt(p, top, 0), g);
    el("text", { class: "t-ax", x: f(X + 19), y: 274.2, "text-anchor": "end" }, fmt(p, 0, 0), g);
    el("path", { class: "tick", d: `M${f(X + 21)} 99 h3 M${f(X + 21)} 271 h3` }, null, g);
    // the ladder: the average so far, and the kit's figure where it has one; labels kept apart when the two are close
    const refs = [["avg", p.average], ["kit", p.kit]].filter(r => r[1] != null).map(([k, val]) => ({ k, val, y: Y(val), ly: Y(val) + 3.2, lo: Y(val) - 6, hi: Y(val) + 6 }));
    if (refs.length === 2 && Math.abs(refs[0].ly - refs[1].ly) < 10) { const [a, b] = refs[0].y <= refs[1].y ? refs : [refs[1], refs[0]], mid = (a.ly + b.ly) / 2, cut = (a.y + b.y) / 2;
      a.ly = mid - 5; b.ly = mid + 5; a.hi = cut; b.lo = cut; }
    refs.forEach(r => { el("path", { class: `across ${r.k}`, d: `M${f(X + 42)} ${f(r.y)} H${f(X + 160.1)}` }, null, g);
      el("text", { class: "t-ref", x: f(X + 19), y: f(r.ly), "text-anchor": "end" }, r.k, g); });
    refs.forEach(r => { const b = el("g", { class: "b rb", tabindex: 0, "data-k": `${p.key}-${r.k}`, "aria-label": r.k === "avg" ? `The average so far for ${p.name}: ${avgOf(p)}` : `The kit's figure for ${p.name}: ${fmt(p, p.kit)}` }, null, g);
      el("rect", { class: "hit", x: f(X + 26), y: f(r.lo), width: 15, height: f(r.hi - r.lo) }, null, b);
      el("rect", { class: `band ${r.k}`, x: f(X + 27.6), y: f(r.y - 2.3), width: 11.8, height: 4.6, rx: 2.3 }, null, b); });
    D[`${p.key}-avg`] = { t: `Average so far · ${said(p, p.average, Math.max(1, p.decimals))}`, l: [p.name, `Taken over ${over(p)}, up to Day ${lastDay}.`] };
    if (p.kit != null) D[`${p.key}-kit`] = { t: `The kit's figure · ${said(p, p.kit)}`, l: [p.name, `What the kit reached with a person driving every step. ${p.above_kit} of the ${p.counted} Days counted are above it.`, p.source ? `Recorded in ${p.source}.` : null] };
    // a lane per Day
    p.lanes.forEach((x, j) => {
      const at = LX + j * LW, last = p.last && p.last.day === x.day, has = x.value != null;
      const b = el("g", { class: "b ln", tabindex: 0, "data-k": `${p.key}-${x.day}`, "aria-label": `Day ${x.day}: ${has ? fmt(p, x.value) : "no figure"}` }, null, g);
      el("rect", { class: "hit", x: f(at), y: 84, width: f(LW), height: 194 }, null, b);
      if (has) el("rect", { class: `band ${last ? "last" : "earlier"}`, x: f(at + 1.2), y: f(Y(x.value) - 2.3), width: f(LW - 2.4), height: 4.6, rx: 2.3 }, null, b);
      el("text", { class: `t-day ${last ? "last" : has ? "" : "none"}`, x: f(at + LW / 2), y: j % 2 ? 302 : 292, "text-anchor": "middle" }, String(x.day), g);
      lanes.push([b, x.day]);
      const cmp = p.average == null ? null : x.value < p.average ? "below" : x.value > p.average ? "above" : "level with";
      D[`${p.key}-${x.day}`] = has ? { t: `Day ${x.day} · ${said(p, x.value)}`, q: x.text, l: [p.name,
        p.kit != null ? `${x.value > p.kit ? "Above" : "Within"} the kit's figure of ${fmt(p, p.kit)}.` : null,
        last && cmp ? `The last Day counted: ${cmp} its average so far, ${avgOf(p)}.` : null] }
        : { t: `Day ${x.day} · no figure`, q: x.text, l: [p.name, "An empty lane: nothing was counted for this Day."] };
    });
    el("text", { class: "t-day ref", x: f(X + 32.5), y: 302, "text-anchor": "middle" }, "ref", g);
  });
  // what the picture shows, and where the model bends
  const li = (list, cls, b, t) => { const e = h("li", { class: cls || null }, h("b", null, b), t); list.appendChild(e); };
  const finds = $("finds"), bends = $("bends"); finds.replaceChildren(); bends.replaceChildren();
  P.filter(p => p.last).forEach(p => {
    const rel = p.average == null ? "" : p.last.value < p.average ? "Below" : p.last.value > p.average ? "Above" : "Level with";
    li(finds, p.lower_better ? p.verdict : "", `${p.name}: ${fmt(p, p.last.value)} on Day ${p.last.day}.`,
      ` ${rel ? `${rel} its average so far (${avgOf(p)})` : "No average yet"}${p.kit != null ? ` and ${p.last.value > p.kit ? "above" : "within"} the kit's figure (${fmt(p, p.kit)})` : ""}.`
      + (p.lower_better ? "" : " No direction is better here, so it is not judged.")
      + (p.drift ? ` Its ${p.counted} bands drift ${p.drift}${p.counted === 2 ? ", and two bands are a thin line to read" : ""}.` : "")
      + (p.empty ? ` ${p.empty} of its ${N} lanes are empty.` : ""));
  });
  const up = P.filter(p => p.drift === "up").length, down = P.filter(p => p.drift === "down").length;
  $("drift").textContent = `The drift is the sign of a straight line fitted to every band of a panel: up for ${n(up, "yardstick", "yardsticks")}, down for ${down}. It is only a slope. It says nothing of why, and one Day can turn it.`;
  const emptiest = P.reduce((a, p) => !a || p.empty > a.empty ? p : a, null), kits = P.filter(p => p.kit != null);
  [["A real gel has one scale.", ` There every lane shares it, and distance means size. Here each of the ${P.length} panels has its own scale and its own unit: compare bands inside a panel, never across panels.`],
    ["A band is one number, not a quantity of material.", " Its thickness and its darkness measure nothing. The darkest band only marks the last Day counted."],
    ["An empty lane is not a zero.", ` A band on the floor of the gel is a figure of zero. An empty lane is a Day with no figure${emptiest && emptiest.empty ? `: ${emptiest.empty} of the ${N} lanes for ${GEL_SHORT[emptiest.key] || emptiest.key}` : ""}.`],
    ["The ladder is short, and half of it moves.", ` It has at most two bands, because the kit recorded only ${n(kits.length, "figure", "figures")}${kits.length ? `: ${andList(kits.map(p => `${fmt(p, p.kit)} for ${p.key}`))}` : ""}. The other band, the average so far, shifts with every Day. A real ladder is a fixed standard.`],
    ["Dollars are API list prices, not a bill.", " They say what the tokens would cost at list price, not what was paid."]].forEach(([b, t]) => li(bends, "", b, t));
  pointerBox(fig, tip, k => k != null && D[k] ? tipFill(tip, D[k]) : false, b => b.getAttribute("data-k"));
  // the page's Day buttons dim every other Day's lane
  onDay.push(day => lanes.forEach(([b, d]) => b.classList.toggle("mk-dim", day != null && d !== day)));
  return fig;
}

/* Graphs 3 to 5 as proteins, as the mockup at #228 draws them: counted in scripts/spec_drift_views.py (protein); this
   folds each chain and words it. `get` finds an element by its id; `onDay` is the page's Day buttons. Colours are in
   dashboard.css, under #prt. */
const PRT_MARK = { proven: ["proved", 13], unproven: ["unproved", 11.4], skipped: ["norun", 12], repair: ["stale", 13], broken: ["broken", 13],
  replaced: ["replaced", 12.1], open: ["unbuilt", 11.9], building: ["unbuilt", 11.9], unchecked: ["unbuilt", 11.9] };
const PRT_SAYS = { proven: "holds, and a break on purpose proved its test", unproven: "holds, never seen to fail", skipped: "the replay cannot run its check",
  repair: "its recorded break no longer applies", broken: "does not hold", replaced: "replaced by a later promise", open: "written, not built",
  building: "not yet in force: its Day is still being built", unchecked: "in force, not re-checked yet" };
// a chain folded into rows `span` wide: each cell's row and its place along the row; a new Day leaves a wider gap
function prtFold(cells, span) {
  const out = []; let row = 0, u = 0;
  cells.forEach((c, i) => { if (i) { const step = c.day !== cells[i - 1].day ? 20 : 16; if (u + step > span - 15) { row++; u = 0; } else u += step; } out.push({ row, u }); });
  return out;
}
function protDraw(P, get, onDay) {
  const $ = id => get("prt-" + id), fig = $("fig"), tip = $("tip"), say = $("say");
  const el = (n, a, txt, parent) => { const e = document.createElementNS(SVG_NS, n); for (const k in a) if (a[k] != null) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; (parent || fig).appendChild(e); return e; };
  const f = v => (+v).toFixed(1).replace(/\.0$/, "");
  const n = (k, one, many) => `${k} ${k === 1 ? one : many}`;
  const nums = (a, max) => a.slice(0, max).map(x => "#" + x).join(", ") + (a.length > max ? ` and ${a.length - max} more` : "");
  const span = ds => ds.length === 1 ? `on Day ${ds[0]}` : `over Days ${ds[0]} to ${ds[ds.length - 1]}`;
  const wrap = (s, w) => String(s).split(" ").reduce((ls, word) => { const l = ls[ls.length - 1]; if (l && (l + " " + word).length <= w) ls[ls.length - 1] = l + " " + word; else ls.push(word); return ls; }, []);
  const C = P.chains, D = {}, cellOf = {}, byId = {}, SLOT = 241.6, MAXSPAN = 185, RING = 2 * Math.PI * 8.5;
  const group = c => c.role === "rung" ? 0 : c.role === "rail" ? 1 : c.key == null ? 2 : 0, TITLE = ["NEEDED TO CLIMB THE LEVELS", "RAILS: NEEDED AT EVERY LEVEL", "NO ABILITY NAMED"];
  const rungs = C.filter(c => c.role === "rung"), rails = C.filter(c => c.role === "rail"), none = C.find(c => c.key == null);
  // where each chain folds: the fewest rows MAXSPAN allows, then the narrowest span that keeps them
  const shape = c => { const rows = k => k.length ? k[k.length - 1].row + 1 : 0, at = rows(prtFold(c.cells, MAXSPAN)); let s = MAXSPAN;
    if (at > 1) while (s > 60 && rows(prtFold(c.cells, s - 0.5)) === at) s -= 0.5; return { span: s, rows: Math.max(1, at) }; };
  // the line of figures
  const cnt = s => P.counts[s] || 0, notYet = P.in_force - P.proven, pct = P.rechecked ? Math.round(100 * P.proven / P.rechecked) : 0;
  const fig5 = (num, small, what, sub) => h("div", null, h("div", { class: "num" }, String(num), small && h("small", null, small)), h("div", { class: "what" }, what), h("div", { class: "sub" }, sub));
  const parts = [[cnt("unproven"), "holds but was never seen to fail", "hold but were never seen to fail"], [cnt("skipped"), "the replay cannot run", "the replay cannot run"],
    [cnt("repair"), "has a recorded break that no longer applies", "have a recorded break that no longer applies"], [cnt("broken"), "does not hold", "do not hold"],
    [cnt("open"), "was written and not built", "were written and not built"], [cnt("building"), "is not in force yet", "are not in force yet"], [cnt("unchecked"), "is not re-checked yet", "are not re-checked yet"]]
    .filter(x => x[0]).map(([k, one, many]) => `${k} ${k === 1 ? one : many}`);
  const W = P.weakest, S = P.strongest, U = P.used;
  const never = [rungs.some(c => c.run && c.run.how === "stop" && !c.run.n) && "a stop has never been seen", rungs.some(c => c.run && c.run.how === "uncounted") && "a rehearsal is not counted"].filter(Boolean);
  $("figs").replaceChildren(...[fig5(rungs.length + rails.length, null, "abilities, one protein each", `${rungs.length} needed to climb the levels and ${n(rails.length, "rail", "rails")}.`
      + (none ? ` ${none.cells.length === 1 ? "1 promise names no ability, and sits alone" : `${none.cells.length} promises name no ability, and sit in a chain of their own`}.` : "")),
    fig5(P.proven, `of ${P.rechecked}`, "promises proven, of those re-checked", `${pct}%. Of the ${P.written} promises written, ${P.replaced} were replaced and ${P.outside.length} ${P.outside.length === 1 ? "is" : "are"} in force but outside the re-check${P.outside.length ? ` (${P.outside.join(", ")})` : ""}: none of these is re-checked`),
    fig5(notYet, null, "promises in force, not proven yet", parts.length ? andList(parts) : "none"),
    W ? fig5(`${Math.round(100 * W.proven / W.rechecked)}%`, null, `the weakest: ${W.name}`, `${W.proven} of its ${W.rechecked} re-checked promises are proven. The strongest is ${S.name}, ${S.proven} of ${S.rechecked}`) : null,
    fig5(U.n, `of ${U.of}`, "abilities used in a real run", `Of the ${U.of} needed to climb the levels, counted from the ${n(U.steps, "step", "steps")} the driver started on another project.`
      + (never.length ? ` ${andList(never).replace(/^./, c => c.toUpperCase())}.` : ""))].filter(Boolean));
  // the key's counts, and the one criterion outside the re-check
  [["proven", "proven"], ["unproven", "unproven"], ["skipped", "skipped"], ["open", "open"], ["repair", "repair"], ["broken", "broken"], ["replaced", "replaced"]].forEach(([k, s]) => { const e = $(`k-${k}`); if (e) e.textContent = String(cnt(s)); });
  $("k-back").textContent = String(P.back);
  $("k-all").textContent = `All ${P.written} promises are drawn; ${P.rechecked} of them are what the last re-check counted.` + (cnt("open") ? ` ${cnt("open")} ${cnt("open") === 1 ? "was" : "were"} written and not built (${C.flatMap(c => c.cells).filter(x => x.state === "open").map(x => x.id).join(", ")}): in force, and outside the re-check.` : "");
  $("stamp").textContent = `Drawn from the page's data at ${P.head || "?"}${P.last_pr ? ` (#${P.last_pr})` : ""}, generated ${P.generated} · ${n(P.written, "promise", "promises")} in ${n(C.length, "chain", "chains")}`;
  // the figure: one box per chain, five to a row, a row for the rungs and one for the rest
  fig.replaceChildren();
  const defs = el("defs", {}), pat = el("pattern", { id: "prt-pat-norun", width: 3, height: 3, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, null, defs);
  el("rect", { class: "pn-bg", width: 3, height: 3 }, null, pat); el("rect", { class: "pn-l", width: 1.4, height: 3 }, null, pat);
  const rows = [[], []]; C.forEach(c => rows[group(c) === 0 ? 0 : 1].push(c));
  const lines = []; rows.filter(r => r.length).forEach(r => { for (let i = 0; i < r.length; i += 5) lines.push(r.slice(i, i + 5)); });
  const chainAt = (c, x0, y0, sh, tab) => {
    // one chain: the dot, the bone through every cell row by row, a Day's number over its first cell
    const xL = x0 + 20, xR = xL + sh.span, places = prtFold(c.cells, sh.span), Y = r => y0 + 30 * r;
    const cx = p => p.row % 2 ? xR - 7.5 - p.u : xL + 7.5 + p.u, last = places[places.length - 1];
    let d = `M${f(x0 + 15)} ${f(y0)}`;
    for (let r = 0; r <= last.row; r++) { d += ` H${f(r === last.row ? cx(last) : r % 2 ? xL : xR)}`; if (r < last.row) d += ` a7.5 15 0 0 ${r % 2 ? 0 : 1} 0 30`; }
    el("path", { class: "bone", d }); el("circle", { class: "nterm", cx: f(x0 + 15), cy: f(y0), r: 2.6 });
    const gs = [];
    c.cells.forEach((x, i) => {
      const p = places[i], X = cx(p), Yc = Y(p.row);
      if (!i || x.day !== c.cells[i - 1].day) el("text", { class: "t-day", "data-d": x.day, x: f(X), y: f(Yc - 9.5), "text-anchor": "middle" }, String(x.day));
      const g = el("g", { class: "b rs", "data-c": x.id, "data-d": x.day, tabindex: tab ? (i ? -1 : 0) : null });
      if (tab) el("rect", { class: "hit", x: f(X - 8), y: f(Yc - 8.5), width: 16, height: 17 }, null, g);
      const [cls, s] = PRT_MARK[x.state] || PRT_MARK.unchecked, scar = x.state === "proven" && x.back;
      const sz = scar ? 11.7 : s;
      el("rect", { class: `m ${cls}${scar ? " scar" : ""}`, x: f(X - sz / 2), y: f(Yc - sz / 2), width: f(sz), height: f(sz), rx: 3.2 }, null, g);
      if (cls === "stale") el("path", { class: "sign", d: `M${f(X)} ${f(Yc - 3.6)}v4.2 M${f(X)} ${f(Yc + 3.4)}v.1` }, null, g);
      if (cls === "broken") el("path", { class: "sign", d: `M${f(X - 2.6)} ${f(Yc - 2.6)}l5.2 5.2 M${f(X + 2.6)} ${f(Yc - 2.6)}l-5.2 5.2` }, null, g);
      if (tab) { cellOf[x.id] = g; byId[x.id] = x; gs.push(g); }
      x.at = { X, Y: Yc };
    });
    return { gs, places, xL, xR, cx, Y };
  };
  // a row of cards, then 28.5 to the next group's heading and 8.5 from it to the cards, as in the mockup
  const ROWGAP = 37;
  let top = 20.5, lastTop = top;
  const walk = [];
  lines.forEach(line => {
    const extra = Math.max(...line.map(c => wrap(c.name, 30).length)) > 1 ? 15 : 0, shapes = line.map(shape);
    const more = 30 * Math.max(0, Math.max(...shapes.map(s => s.rows)) - 4), H = 285 + extra + more, rule = top + 168.5 + extra + more;
    let seen = null;
    lastTop = top;
    line.forEach((c, i) => {
      const x0 = 0.5 + i * SLOT, xt = x0 + 11.5, g = group(c);
      if (g !== seen) { el("text", { class: "t-grp", x: f(i ? x0 - 0.5 : 0), y: f(top - 8.5) }, TITLE[g]); seen = g; }
      const box = el("g", { class: "prot", "data-a": c.key == null ? "none" : c.key, role: "group", "aria-label": `${c.name}: ${n(c.cells.length, "promise", "promises")}, ${c.proven} of ${c.rechecked} proven` });
      el("rect", { class: "tl", x: f(x0), y: f(top), width: 228.6, height: H, rx: 8 }, null, box);
      const name = el("text", { class: "t-name", x: f(xt), y: f(top + 22.5) }, null, box);
      wrap(c.name, 30).forEach((l, j) => el("tspan", { x: f(xt), dy: j ? 15 : 0 }, l, name));
      // its figures right under its own name, one line lower only when that name wraps (the chain keeps the row's line)
      const sub = el("text", { class: "t-sub", x: f(xt), y: f(top + 36.5 + (wrap(c.name, 30).length > 1 ? 15 : 0)) }, null, box);
      if (c.score != null) el("tspan", { class: "b sc", "data-k": "sc", "data-v": c.key, tabindex: 0 }, `score ${c.score}`, sub);
      el("tspan", {}, `${c.score == null ? "no score" : ""} · ${n(c.cells.length, "promise", "promises")}`, sub);
      walk.push(c.cells.length ? chainAt(c, x0, top + 66 + extra, shapes[i], true).gs : []);
      el("path", { class: "rule", d: `M${f(xt)} ${f(rule)}H${f(x0 + 217.1)}` });
      const ring = el("g", { class: "b arc", "data-k": "ring", "data-v": c.key == null ? "none" : c.key, tabindex: 0 });
      el("rect", { class: "hit", x: f(xt), y: f(rule + 6), width: 205.6, height: 24 }, null, ring);
      el("circle", { class: "ring-bg", cx: f(x0 + 22.5), cy: f(rule + 18), r: 8.5 }, null, ring);
      if (c.proven) el("circle", { class: "ring-fg", cx: f(x0 + 22.5), cy: f(rule + 18), r: 8.5, "stroke-dasharray": `${(RING * c.proven / c.rechecked).toFixed(2)} ${RING.toFixed(2)}`, transform: `rotate(-90 ${f(x0 + 22.5)} ${f(rule + 18)})` }, null, ring);
      el("text", { class: "t-ring", x: f(x0 + 39.5), y: f(rule + 22) }, c.rechecked ? `${c.proven} of ${c.rechecked} proven` : "none re-checked", ring);
      const prs = c.key == null ? Object.entries(c.cells.reduce((a, x) => { (a[x.day] = a[x.day] || []).push(...x.prs); return a; }, {})).map(([d, l]) => [+d, [...new Set(l)]]) : c.prs;
      const k = prs.reduce((s, x) => s + x[1].length, 0);
      const pt = el("text", { class: "b t-pr", "data-k": "pr", "data-v": c.key == null ? "none" : c.key, tabindex: 0, x: f(xt), y: f(rule + 44) });
      [`${n(k, "pull request", "pull requests")}${prs.length ? " " + span(prs.map(x => x[0])) : ""}`, ...(c.between.length ? [`${c.between.length} more between Days,`, "which made no promise"] : [])]
        .forEach((l, j) => el("tspan", { x: f(xt), dy: j ? 12 : 0 }, l, pt));
      const key = c.key == null ? "none" : c.key;
      D[`pr:${key}`] = { t: `${c.name} · ${n(k + c.between.length, "pull request", "pull requests")}`, l: [...prs.map(x => `Day ${x[0]}: ${nums(x[1], 12)}`),
        c.between.length ? ["q", `Between Days: ${nums(c.between, 8)}. They grew the ability and built no promise drawn here.`] : null] };
      D[`ring:${key}`] = { t: `${c.name} · ${c.proven} of ${c.rechecked} proven`, l: [`${n(c.cells.length, "promise", "promises")} in the chain: ${Object.entries(c.counts).map(([s, v]) => `${v} ${lower(STATES[s] ? STATES[s].word : s)}`).join(", ")}.`,
        ["q", "The count is only of the promises the last re-check counted. A replaced promise, and one written and not built, stay in the chain and out of the count."]] };
      if (c.score != null) D[`sc:${key}`] = { t: `${c.name} · score ${c.score}`, l: [`The dashboard's score for the ability, out of 100${c.parts ? `: ${c.parts}` : ""}.`] };
      const R = c.run;
      if (R) {
        const by = R.parks.reduce((a, p) => { const w = p.by === "fault" ? "on a fault" : /every day is done/i.test(p.line) ? "with every day done" : `by the ${p.by}`; a[w] = (a[w] || 0) + 1; return a; }, {});
        const crash = R.crashes[0], faultAt = crash && R.parks.some(p => p.pr === crash.pr && p.by === "fault");
        const word = R.how === "rail" ? ["does not apply", "a rail, not a step of a run", "na"] : R.how === "uncounted" ? ["not counted", "the run log keeps no rehearsal", "na"]
          : R.how === "loop" ? [`${R.n} of ${n(R.of, "step", "steps")}`, "reached their merge with no park", R.n ? "seen" : "never"]
          : R.how === "park" ? [n(R.n, "park", "parks"), Object.entries(by).map(([w, v]) => `${v} ${w}`).join(", ") || "none in the run log", R.n ? "seen" : "never"]
          : R.how === "recover" ? [n(R.n, "crash", "crashes"), R.n === 1 ? `it ended ${crash.ended === "parked" ? `in a park${faultAt ? " on a fault" : ""}` : crash.ended}` : R.n ? `${R.n} steps with a crash` : `no crash recorded in ${R.of} steps`, R.n ? "seen" : "never"]
          : R.n ? [n(R.n, "stop", "stops"), `in ${n(R.of, "step", "steps")}`, "seen"] : ["never yet", `no stop recorded in ${n(R.of, "step", "steps")}`, "never"];
        const rg = el("g", { class: "b run", "data-k": "run", "data-v": key, tabindex: 0, role: "img", "aria-label": `In real runs: ${word[0]}. ${word[1]}` });
        const yb = top + H - 33;
        el("rect", { class: "rhit", x: f(xt), y: f(yb), width: 205.6, height: 31 }, null, rg);
        el("path", { class: "rdiv", d: `M${f(xt)} ${f(yb - 1)}H${f(x0 + 217.1)}` }, null, rg);
        el("rect", { class: `rm ${word[2]}`, x: f(xt), y: f(yb + 6.5), width: 9, height: 9, rx: 2 }, null, rg);
        const tr = el("text", { class: "t-run", x: f(xt + 14), y: f(yb + 14.5) }, "In real runs", rg);
        el("tspan", { class: "rv", dx: 6 }, word[0], tr);
        el("text", { class: "t-sub", x: f(xt), y: f(yb + 27) }, word[1], rg);
        const from = P.source ? ["q", `Counted from the driver's run log (${P.source}${P.counted ? `, counted ${String(P.counted).slice(0, 16).replace("T", " ")}` : ""}). Which step counts for which ability is the maintainer's reading, not the data's.`] : null;
        const others = R.of - (R.merged || []).length;
        D[`run:${key}`] = { t: `${c.name} · in real runs: ${word[0]}`, l: R.how === "rail" ? ["Does not apply. A rail is needed at every level and is not used by one step of a run, so the driver's count has no figure for it.", from]
          : R.how === "uncounted" ? ["Not counted. The run log records the steps the driver started, and a rehearsal starts none, so the count cannot show this ability in use.", from]
          : R.how === "loop" ? [`${R.n} of the ${n(R.of, "step", "steps")} the driver started reached their merge with no park${R.prs.length ? `: ${nums(R.prs.filter(x => x != null), 8)}` : ""}.`,
            ["q", `The other ${others}: ${andList([R.crashes.length && `${n(R.crashes.length, "crashed", "crashed")} (${nums(R.crashes.map(x => x.pr).filter(x => x != null), 4)})`, R.parks.filter(p => p.pr == null).length && `${R.parks.filter(p => p.pr == null).length} ${R.parks.filter(p => p.pr == null).length === 1 ? "was a park" : "were parks"} with no step of its own`, R.open.length && `${R.open.length} ${R.open.length === 1 ? "is" : "are"} still open (${nums(R.open, 4)})`].filter(Boolean))}. A step still open is counted in no ability yet.`], from]
          : R.how === "park" ? [`${n(R.n, "park", "parks")} in the ${n(R.of, "step", "steps")} the driver started.`, ...R.parks.map(p => ["q", `${p.pr != null ? `#${p.pr}` : "With no step of its own"}: ${p.line || p.by}.`]),
            R.crashes.length ? ["q", "A step that crashed and then parked is counted here and under the crash too: it is one step, not two."] : null, from]
          : R.how === "recover" ? [`${n(R.n, "crash", "crashes")} in ${n(R.of, "step", "steps")}${R.prs.length ? `, on ${nums(R.prs.filter(x => x != null), 4)}` : ""}.`,
            ...R.crashes.map(x => ["q", `#${x.pr}: the step ended ${x.ended}, over ${n(x.sessions, "session", "sessions")}. The count does not say who started the next. Its park is counted under "${(C.find(a => a.run && a.run.how === "park") || {}).name || "park"}" as well: the same step.`]), from]
          : [R.n ? `${n(R.n, "stop", "stops")} in ${n(R.of, "step", "steps")}.` : `Never yet. In the ${n(R.of, "step", "steps")} the driver started on another project, the count records no stop.`,
            ["q", `The chain above is ${c.proven} of ${c.rechecked} proven: by tests, not by a stop in a real run.`], from] };
      }
    });
    top += H + ROWGAP;
  });
  // how to read one: the shortest rung chain of six or more, folded narrower, with four numbered marks
  const free = 5 - lines[lines.length - 1].length, ex = rungs.filter(c => c.cells.length >= 6).sort((a, b) => a.cells.length - b.cells.length)[0];
  let VH = top - ROWGAP + 2.5;
  if (ex && free >= 2) {
    const x0 = 0.5 + (5 - free) * SLOT + 15, kp = el("g", { class: "keyp", "aria-label": "How to read a protein" });
    el("text", { class: "t-name", x: f(x0), y: f(lastTop + 22.5) }, "How to read one", kp);
    const t = el("text", { class: "t-sub", x: f(x0), y: f(lastTop + 37.5) }, null, kp);
    [`“${ex.name}” again,`, "folded narrower. The order along", "the chain is the same."].forEach((l, j) => el("tspan", { x: f(x0), dy: j ? 13 : 0 }, l, t));
    const copy = { cells: ex.cells.map(x => Object.assign({}, x)) };
    const m = chainAt(copy, x0 + 18.5, lastTop + 120, { span: 95, rows: 0 }, false);
    const first = copy.cells[0], lastC = copy.cells[copy.cells.length - 1], kn = (k, x, y) => { el("circle", { class: "kn", cx: f(x), cy: f(y), r: 7 }); el("text", { class: "t-kn", x: f(x), y: f(y + 3.3), "text-anchor": "middle" }, String(k)); };
    kn(1, x0 + 18.5, lastTop + 120); kn(2, first.at.X, first.at.Y - 25.5);
    if (m.places[m.places.length - 1].row > 0) kn(3, m.xR + 17.5, lastTop + 135);
    kn(4, lastC.at.X - 18.5, lastC.at.Y);
    const notes = [`Start at the dot. The first cell is the first promise built: ${first.id}, on Day ${first.day}.`, "A small number is a Day. The cell under it is that Day's first promise in this chain.",
      "At the end of a row the chain turns back. The turn says nothing.", `The last cell is the newest promise: ${lastC.id}, on Day ${lastC.day}.`, "The same cell size everywhere: a longer chain is a larger protein."];
    let y = lastTop + 27.5;
    notes.forEach((s, j) => { if (j < 4) kn(j + 1, x0 + 206, y - 3.5); const tx = el("text", { class: "t-key", x: f(x0 + 220), y: f(y) }, null, kp);
      const ls = wrap(s, 40); ls.forEach((l, i) => el("tspan", { x: f(x0 + 220), dy: i ? 13.5 : 0 }, l, tx)); y += 13.5 * ls.length + 7; });
  }
  fig.setAttribute("viewBox", `0 0 1196 ${f(VH)}`);
  // what the picture shows, and where the model bends
  const li = (list, b, t, ids) => { const e = h("li", ids && ids.length ? { "data-t": ids.join(" "), tabindex: 0 } : null, h("b", null, b), t); list.appendChild(e); return e; };
  const finds = $("finds"), bends = $("bends"); finds.replaceChildren(); bends.replaceChildren();
  const real = C.filter(c => c.key != null && c.cells.length), big = [...real].sort((a, b) => b.cells.length - a.cells.length), most = big.filter(c => c.cells.length === big[0].cells.length);
  if (big.length) li(finds, `The largest ${most.length > 1 ? "proteins are" : "protein is"} ${andList(most.map(c => `“${c.name}”`))}, ${big[0].cells.length} residues${most.length > 1 ? " each" : ""}.`,
    ` The smallest is “${big[big.length - 1].name}”, ${big[big.length - 1].cells.length}. Size is how many promises the specs made for an ability, not how well it works.`);
  const full = real.filter(c => c.rechecked && c.proven === c.rechecked);
  full.forEach(c => li(finds, `“${c.name}” has every re-checked residue proven: ${c.proven} of ${c.rechecked}.`,
    ` Its chain still holds ${c.cells.length - c.rechecked} more that the count leaves out${c.cells.length > c.rechecked ? ` (${c.cells.filter(x => !COUNTED.includes(x.state)).map(x => x.id).join(", ")})` : ""}.`));
  C.forEach(c => { const not = c.cells.filter(x => x.state !== "proven" && x.state !== "replaced"); if (!not.length) return;
    const by = s => not.filter(x => x.state === s).map(x => x.id);
    li(finds, `“${c.name}” holds ${n(not.length, "residue", "residues")} not proven.`, " " + Object.keys(PRT_SAYS).filter(s => by(s).length).map(s => `${PRT_SAYS[s]}: ${by(s).join(", ")}`).join("; ").replace(/^./, x => x.toUpperCase()) + ".", not.map(x => x.id)); });
  const perDay = {}; C.forEach(c => c.cells.forEach(x => { (perDay[x.day] = perDay[x.day] || []).push(x.id); }));
  const dayMost = Object.keys(perDay).sort((a, b) => perDay[b].length - perDay[a].length)[0];
  if (dayMost) li(finds, `Day ${dayMost} added the most residues: ${perDay[dayMost].length}.`, "", perDay[dayMost]);
  const back = C.flatMap(c => c.cells).filter(x => x.state === "proven" && x.back).map(x => x.id);
  if (back.length) li(finds, `${n(back.length, "residue is", "residues are")} proven now and edged.`, ` The replay once saw each stop holding, and it came back: ${back.join(", ")}.`, back);
  const between = C.reduce((s, c) => s + c.between.length, 0), shared = C.flatMap(c => c.cells).filter(x => x.also.length).length;
  [["The fold's shape means nothing.", " Only the order along the chain does. A chain turns where its tile runs out of room, and two cells that touch across a row have nothing to do with each other."],
    ["A real protein folds one way, and works or does not.", " These work residue by residue: a chain with one hollow cell still has every other promise proven."],
    ["Time is only the Day numbers.", " A chain says the order promises were built in, not how long it took. A small number marks where a new Day starts, and nothing here is drawn to a Day's length."],
    ["Pull requests between Days grew an ability and added no residue.", ` ${n(between, "pull request is", "pull requests are")} counted under a chain and drawn nowhere in it.`],
    ["A residue sits in one protein only.", ` ${n(shared, "promise touches", "promises touch")} more than one ability. Each is drawn once, under the first of its abilities in the dashboard's order. The pointer says which others it grew.`],
    ["A replaced residue stays in the chain.", ` In a cell it would be cut out. Here the ${cnt("replaced")} hollow cells keep their place, so a chain's length is every promise ever made for the ability.`]].forEach(([b, t]) => li(bends, b, t));
  // the pointer box, the kin of a replaced promise lit with it, the arrow keys along a chain
  const kin = id => { const x = byId[id]; if (!x) return []; const ids = [...x.replaced_by]; Object.values(byId).forEach(y => { if (y.replaced_by.includes(id)) ids.push(y.id); }); return ids.length ? [id, ...ids] : []; };
  const light = ids => { fig.classList.remove("foc"); Object.values(cellOf).forEach(g => g.classList.remove("lit")); const on = ids.filter(id => cellOf[id]); on.forEach(id => cellOf[id].classList.add("lit")); if (on.length) fig.classList.add("foc"); };
  const cellTip = x => ({ t: `${x.id} · Day ${x.day} · ${x.tag === "hold" ? "safety check" : "new work"}`, l: [x.text,
    ["st", `${PRT_SAYS[x.state].replace(/^./, c => c.toUpperCase())}${x.state === "proven" && x.back ? "; the replay once saw it stop, and it came back" : ""}${x.state === "replaced" ? `: ${x.replaced_by.join(", ")}` : ""}${x.last && COUNTED.includes(x.state) ? ` (last re-checked at #${x.last})` : ""}.`],
    ["q", x.prs.length ? `Cites ${n(x.prs.length, "pull request", "pull requests")}: ${nums(x.prs, 10)}.` : "Cites no pull request."],
    ...x.stops.filter(s => x.state !== "replaced" || s.held).map(s => ["q", `At #${s.pr} the replay first reported “${s.state}”${s.held ? `, and it held again by #${s.held}.` : ", and it has not been seen holding since."}`]),
    x.also.length ? ["q", `Drawn here, and it also grows: ${x.also.map(a => (C.find(c => c.key === a) || {}).name || a).join(", ")}.`] : null] });
  pointerBox(fig, tip, (k, b) => { if (k == null) { light([]); return false; } const x = byId[k]; if (x) { light(kin(k)); return tipFill(tip, cellTip(x)); } light([]); return D[k] ? tipFill(tip, D[k]) : false; },
    b => b.getAttribute("data-c") || `${b.getAttribute("data-k")}:${b.getAttribute("data-v")}`);
  fig.addEventListener("keydown", e => { const b = e.target && e.target.closest ? e.target.closest(".rs") : null; if (!b) return;
    const list = walk.find(l => l.includes(b)), i = list ? list.indexOf(b) : -1, step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (i < 0 || !step || !list[i + step]) return; e.preventDefault(); b.setAttribute("tabindex", "-1"); list[i + step].setAttribute("tabindex", "0"); list[i + step].focus(); });
  finds.addEventListener("pointerover", e => { const l = e.target && e.target.closest ? e.target.closest("li[data-t]") : null; light(l ? l.getAttribute("data-t").split(" ") : []); });
  finds.addEventListener("pointerleave", () => light([]));
  // the page's Day buttons light one Day's promises
  const days = fig.querySelectorAll ? () => [...fig.querySelectorAll(".t-day")] : () => [];
  // what the line above the chains says: every Day's promises, or the chosen Day's, chain by chain, as the view counts them
  const dayOf = list => new Map(list || []), wrote = P.per_day || [];
  const sayDay = day => { if (day == null) { say.textContent = wrote.length ? `Every Day: ${n(P.written, "promise", "promises")}, ${wrote.length > 1 ? `Days ${wrote[0][0]} to ${wrote[wrote.length - 1][0]}` : `Day ${wrote[0][0]}`}.` : ""; return; }
    const k = dayOf(wrote).get(day) || 0, parts = C.map(c => [c, dayOf(c.per_day).get(day) || 0]).filter(p => p[1]);
    say.textContent = `Day ${day}: ${k ? `${n(k, "promise", "promises")}, ${parts.map(([c, m]) => `${m} in “${c.name}”`).join(", ")}.` : "no promise."}`; };
  sayDay(null);
  onDay.push(day => { Object.values(cellOf).forEach(g => g.classList.toggle("off", day != null && +g.getAttribute("data-d") !== day));
    days().forEach(t => t.classList.toggle("off", day != null && +t.getAttribute("data-d") !== day));
    sayDay(day); });
  return fig;
}

/* Graph 7 as proofreading, as the mockup at #228 draws it: one stream of defects, thinning left to right at each layer
   of checking. Counted in scripts/spec_drift_views.py (proofreading), by graph 7's rules; this lays it out and words
   it, and counts nothing. `get` finds an element by its id; `onDay` is the page's Day buttons. Colours are in
   dashboard.css, under #prf. */
const PRF_MEM = [316, 704, 872, 1060];  // each layer's membrane, left to right
// The trays under the stream, [x, width]: one per layer for its gates, the leak's after the first layer, the marks'.
const PRF_TRAY = { layers: [[20.5, 299], [514.5, 193], [726.5, 149], [894.5, 169]], leak: [338.5, 165], out: [1084.5, 167] };
const PRF_WORD = ["no", "one", "two", "three", "four", "five", "six"];
function prfDraw(P, get, onDay) {
  if (!P || P.empty) return null;  // without the gates' runs and cost there is no stream: the section says why
  const $ = id => get("prf-" + id), fig = $("fig"), tip = $("tip");
  const el = (n, a, txt, parent) => { const e = document.createElementNS(SVG_NS, n); for (const k in a) if (a[k] != null) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; (parent || fig).appendChild(e); return e; };
  const f = v => (+v).toFixed(1).replace(/\.0$/, "");
  const n = (k, one, many) => `${k} ${k === 1 ? one : many}`;
  const G = P.gates, L = P.layers, T = P.total, k = Math.min(0.4, 143.6 / T), Y0 = 66, last = L.length - 1;
  const leak = G.find(g => g.key === P.leak), lower1 = s => s.charAt(0).toLowerCase() + s.slice(1);
  const layerWord = i => lower1(L[i].name), gateAt = key => (G.find(g => g.key === key) || {}).at;
  fig.replaceChildren();
  fig.setAttribute("aria-label", "All defects as one stream running left to right through four layers of checking; under each layer a tray of the defects caught there, one dot each, grouped by gate; at the right what the Days' own checks let through; below, the hooks' refusals");
  const defs = el("defs", {});
  const grad = el("linearGradient", { id: "prf-grad-in", x1: 0, x2: 1, y1: 0, y2: 0 }, null, defs);
  el("stop", { offset: 0, "stop-color": "var(--prf-flow)", "stop-opacity": 0 }, null, grad);
  el("stop", { offset: 1, "stop-color": "var(--prf-flow)", "stop-opacity": 1 }, null, grad);
  const pat = el("pattern", { id: "prf-pat-leak", width: 6, height: 6, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, null, defs);
  el("rect", { width: 6, height: 6, fill: "var(--prf-flow)" }, null, pat);
  el("rect", { width: 2.2, height: 6, fill: "var(--prf-flow-2)" }, null, pat);

  // the stream: each layer's catches drop out at its membrane, the leak's before the second layer's gates
  const drops = [];
  L.forEach((x, i) => {
    if (leak && leak.layer === i) drops.push({ n: leak.caught, R: PRF_TRAY.leak[0] + 131.5, leak: true, layer: i });
    drops.push({ n: x.caught - (leak && leak.layer === i ? leak.caught : 0), R: PRF_MEM[i] - 5, layer: i });
  });
  let left = T;
  drops.forEach(d => { d.before = left; left -= d.n; d.after = left; d.w = d.n * k; d.x0 = d.R - d.w - 9; });
  const shown = drops.filter(d => d.n > 0);
  el("rect", { class: "flow-in", x: 20, y: Y0, width: 34, height: f(T * k) });
  let from = 53.5;
  shown.forEach(d => { el("rect", { class: "flow", x: f(from), y: Y0, width: f(d.x0 + 0.5 - from), height: f(d.before * k) }); from = d.x0; });
  if (left > 0) el("rect", { class: "flow", x: f(from), y: Y0, width: f(1252 - from), height: f(left * k) });
  shown.forEach(d => { const top = Y0 + d.after * k, w = d.w, R = d.R;
    const p = `M${f(d.x0)} ${f(top)}A${f(w + 9)} ${f(w + 9)} 0 0 1 ${f(R)} ${f(top + w + 9)}V245H${f(R - w)}V${f(top + w + 9)}A9 9 0 0 0 ${f(d.x0)} ${f(top + w)}Z`;
    el("path", { class: "flow", d: p });
    if (d.leak) el("path", { class: "leakflow", d: p }); });
  el("path", { class: "tail", d: "M1070 67H1252" });

  // the trays, each gate's dots in it; a tray grows when its gates need more room than the mockup's
  const trays = L.map((x, i) => ({ xw: PRF_TRAY.layers[i], layer: i, gates: G.filter(g => g.layer === i && g !== leak) }));
  if (leak) trays.splice(leak.layer, 0, { xw: PRF_TRAY.leak, layer: leak.layer, gates: [leak], leak: true });
  const bins = trays.map(t => el("rect", { class: t.leak ? "bin leak" : "bin", x: t.xw[0], y: 240.5, width: t.xw[1], height: 275, rx: 6 }));
  shown.forEach(d => { el("rect", { class: "flow", x: f(d.R - d.w), y: 238, width: f(d.w), height: 6 });
    if (d.leak) el("rect", { class: "leakflow", x: f(d.R - d.w), y: 238, width: f(d.w), height: 6, style: "stroke:none" }); });
  const index = new Map(P.defects.map((o, i) => [o, i])), ix = new Map(P.defects.map((o, i) => [o.id, i]));
  const dotEls = [], dotsOf = {}, grpOf = {}, perOf = {};
  const cost = g => [g.runs != null ? `${n(g.runs, "run", "runs")} · ${money(g.cost)}` : "", g.per != null ? `about ${money(g.per)} a catch` : "",
    g.by ? `by: tracks ${g.by.track} · self ${g.by.self} · other ${g.by.other}` : "", g.caught ? "" : "none in the Notes yet"].filter(Boolean);
  let deepest = 0;
  trays.forEach(t => {
    const [x, w] = t.xw, per = Math.floor((w - 23) / 13), hx = x + 6.5, hw = w - 13, tx = hx + 5, rx = hx + hw - 5;
    let bottom = null;
    t.gates.forEach(g => {
      const gi = G.indexOf(g);
      let y = 253;
      if (bottom != null) { el("path", { class: "sep", d: `M${f(tx)} ${f(bottom + 6)}H${f(rx)}` }); y = bottom + 10; }
      const grp = el("g", { class: "b grp", "data-k": "g", "data-v": gi, "data-per": per, tabindex: 0, role: "group", "aria-label": `${g.label}: ${g.caught} caught` });
      const hit = el("rect", { class: "hit", x: f(hx), y: f(y), width: f(hw), height: 0, rx: 4 }, null, grp);
      el("text", { x: f(tx), y: f(y + 14), class: "t-g" }, g.label, grp);
      el("text", { x: f(rx), y: f(y + 14), class: "t-gn", "text-anchor": "end" }, String(g.caught), grp);
      if (g.sub) el("text", { x: f(tx), y: f(y + 26), class: "t-gs" }, g.sub, grp);
      const top = y + (g.sub ? 32 : 20), mine = P.causes.flatMap(c => P.defects.filter(o => o.gate === g.key && o.cause === c));
      grpOf[gi] = grp; perOf[gi] = per; dotsOf[gi] = [];
      mine.forEach((o, j) => {
        const cx = tx + (j % per) * 13, cy = top + Math.floor(j / per) * 13, c = `c-${o.cause}`, i = index.get(o);
        const b = el("g", { class: ["b", "d", o.escaped && "sq", o.back && "bk"].filter(Boolean).join(" "), "data-k": "d", "data-v": i, "data-g": gi, tabindex: -1, role: "img",
          "aria-label": `${o.id}, Day ${o.day}, ${o.cause}, ${g.at}${o.back ? ", came back" : ""}${o.escaped ? ", made on an earlier Day" : ""}` });
        el("rect", { class: "hit", x: f(cx), y: f(cy), width: 13, height: 13 }, null, b);
        if (o.escaped && o.back) { el("rect", { class: "rg", x: f(cx + 0.8), y: f(cy + 0.8), width: 11.4, height: 11.4, rx: 2.6 }, null, b);
          el("rect", { class: c, x: f(cx + 2.8), y: f(cy + 2.8), width: 7.4, height: 7.4, rx: 1.2 }, null, b); }
        else if (o.escaped) el("rect", { class: c, x: f(cx + 2.8), y: f(cy + 2.8), width: 7.4, height: 7.4, rx: 1.2 }, null, b);
        else if (o.back) { el("circle", { class: "rg", cx: f(cx + 6.5), cy: f(cy + 6.5), r: 5.6 }, null, b); el("circle", { class: c, cx: f(cx + 6.5), cy: f(cy + 6.5), r: 3.4 }, null, b); }
        else el("circle", { class: c, cx: f(cx + 6.5), cy: f(cy + 6.5), r: 4 }, null, b);
        dotEls[i] = { b, o }; dotsOf[gi].push(b);
      });
      let ly = top + Math.ceil(mine.length / per) * 13;
      cost(g).forEach(s => { ly += 12; el("text", { x: f(tx), y: f(ly), class: "t-cost" }, s, grp); });
      bottom = ly + 5;
      hit.setAttribute("height", f(bottom - y));
    });
    // the close's tray ends with the second reader, who reads every Day's tags at its close
    if (t.layer === 2 && !t.leak) {
      const sy = (bottom == null ? 247 : bottom + 6), R = P.reader;
      el("path", { class: "sep", d: `M${f(tx)} ${f(sy)}H${f(rx)}` });
      el("text", { x: f(tx), y: f(sy + 18), class: "t-g" }, "A second reader");
      el("text", { x: f(tx), y: f(sy + 30), class: "t-gs" }, "relabel.py, the defect-rater");
      const said = R ? [`${comma(R.differ)} of ${comma(R.tags)} tags read`, "differently"] : ["no Day's tags read", "yet"];
      said.forEach((s, j) => el("text", { x: f(tx), y: f(sy + 42 + 12 * j), class: "t-cost" }, s));
      bottom = sy + 42 + 12 * (said.length - 1) + 5;
    }
    deepest = Math.max(deepest, bottom || 0);
  });

  // the layers: a membrane each, and what it caught of what reached it
  L.forEach((x, i) => { const mx = PRF_MEM[i];
    el("rect", { class: "mem", x: f(mx - 3.5), y: 57, width: 7, height: 180, rx: 3.5 });
    el("path", { class: "mem-c", d: `M${mx} 62V232` });
    const say = `catches ${x.caught} of ${x.reached} · ${x.pct}%`;
    const b = el("g", { class: "b lay", "data-k": "L", "data-v": i, tabindex: 0, role: "group", "aria-label": `Layer ${i + 1}, ${x.name}: ${say}` });
    el("rect", { class: "hit", x: f(mx + 4 - 172), y: 6, width: 172, height: 48, rx: 4 }, null, b);
    const t = el("text", { x: f(mx + 4), y: 20, class: "t-name", "text-anchor": "end" }, null, b);
    el("tspan", { class: "k" }, String(i + 1), t); el("tspan", {}, ` ${x.name}`, t);
    el("text", { x: f(mx + 4), y: 33, class: "t-bio", "text-anchor": "end" }, x.bio.toUpperCase(), b);
    el("text", { x: f(mx + 4), y: 48, class: "t-sec", "text-anchor": "end" }, say, b); });
  el("text", { x: 20, y: 48, class: "t-note" }, "Every defect in the Days' Notes");
  // how many are still in the stream: before the first drop, and after each membrane
  const label = (x, count, first) => { const hh = count * k, cap = first ? "defects, none caught yet" : "still uncaught";
    if (hh >= 100) { el("text", { x: f(x), y: f(Y0 + hh / 2 + 5), class: "t-on", "text-anchor": "middle" }, comma(count)); el("text", { x: f(x), y: f(Y0 + hh / 2 + 22), class: "t-cap", "text-anchor": "middle" }, cap); }
    else if (hh >= 40) { el("text", { x: f(x), y: f(Y0 + hh / 2 + 2), class: "t-on m", "text-anchor": "middle" }, comma(count)); el("text", { x: f(x), y: f(Y0 + hh / 2 + 17), class: "t-cap", "text-anchor": "middle" }, cap); }
    else el("text", { x: f(x), y: f(Y0 + hh / 2 + (hh >= 16 ? 4.6 : 4)), class: hh >= 16 ? "t-on s" : "t-on xs", "text-anchor": "middle" }, `${comma(count)} ${cap}`); };
  if (shown.length) label((53.5 + shown[0].x0 + 0.5) / 2, T, true);
  L.slice(0, last).forEach((x, i) => { const next = shown.find(d => d.layer > i);
    if (x.went_on > 0) label((PRF_MEM[i] + (next ? next.x0 : 1252)) / 2, x.went_on, false); });
  shown.forEach(d => { const word = d.leak ? `${comma(d.n)}, no gate` : `${comma(d.n)} caught`;
    if (d.w >= 60) el("text", { x: f(d.R - d.w / 2), y: 232, class: "t-drop in", "text-anchor": "middle" }, word);
    else el("text", { x: f(d.x0 + 3), y: 228, class: "t-drop", "text-anchor": "end" }, word); });

  // past every layer: what the Days' own checks let through, the escapes and the problems that came back
  const out = el("rect", { class: "bin out", x: PRF_TRAY.out[0], y: 240.5, width: PRF_TRAY.out[1], height: 275, rx: 6 });
  el("text", { x: 1084, y: 20, class: "t-name" }, "Past every layer");
  el("text", { x: 1084, y: 33, class: "t-bio" }, "WHAT SURVIVES IS A MUTATION");
  el("text", { x: 1084, y: 48, class: "t-sec" }, `${L[last].went_on} left in the count`);
  ["The count ends at zero: a", "defect is counted only once", "somebody found it. What nobody", "found is not here."].forEach((s, j) => el("text", { x: 1084, y: 91 + 13 * j, class: "t-note" }, s));
  el("text", { x: 1096, y: 267, class: "t-g" }, "Let through by a Day's");
  el("text", { x: 1096, y: 280, class: "t-g" }, "own checks");
  const M = P.marks, perLayer = m => m.layers.map((c, i) => c ? `${layerWord(i)} ${c}` : "").filter(Boolean);
  let my = 288;
  [["esc", M.escaped, `${M.escaped.n} made on an earlier Day, caught on a later one`, ["made on an earlier Day,", "caught on a later one"]],
    ["back", M.back, `${M.back.n} the same problem as an earlier defect, back again`, ["the same problem as an", "earlier defect, back again"]]].forEach(([key, m, aria, sec]) => {
    const b = el("g", { class: "b mk", "data-k": "mk", "data-v": key, tabindex: 0, role: "group", "aria-label": aria });
    const hit = el("rect", { class: "hit", x: 1091, y: my, width: 154, height: 0, rx: 4 }, null, b);
    if (key === "esc") el("rect", { class: "c-other", x: 1097, y: my + 8, width: 9, height: 9, rx: 1.4 }, null, b);
    else { el("circle", { class: "rg", cx: 1102, cy: my + 14, r: 6.4 }, null, b); el("circle", { class: "c-other", cx: 1102, cy: my + 14, r: 3.8 }, null, b); }
    el("text", { x: 1116, y: my + 23, class: "t-big" }, comma(m.n), b);
    sec.forEach((s, j) => el("text", { x: 1096, y: my + 36 + 13 * j, class: "t-sec" }, s, b));
    const lines = perLayer(m);
    lines.forEach((s, j) => el("text", { x: 1096, y: my + 64 + 12 * j, class: "t-cost" }, s, b));
    const bottom = lines.length ? my + 64 + 12 * (lines.length - 1) + 6 : my + 55;
    hit.setAttribute("height", f(bottom - my)); my = bottom + 2;
  });
  el("text", { x: 1096, y: f(my + 9), class: "t-gs" }, `${n(M.both, "dot carries", "dots carry")} both marks`);
  deepest = Math.max(deepest, my + 9);
  const H = Math.max(275, deepest + 14 - 240.5);
  [...bins, out].forEach(r => r.setAttribute("height", f(H)));

  // the hooks, beside the stream: they refuse a call, they catch no defect
  const B = 240.5 + H + 22, HK = P.hooks || { guards: [], refused: 0 }, most = Math.max(1, ...HK.guards.map(g => g.refused)), sc = Math.min(2.2, 250 / most);
  const BH = Math.max(66, 16 * HK.guards.length + 18);
  el("rect", { class: "bin out", x: 20.5, y: f(B), width: 1231, height: BH, rx: 6 });
  el("text", { x: 32, y: f(B + 20.5), class: "t-name" }, "The hooks");
  el("text", { x: 98, y: f(B + 20.5), class: "t-bio" }, "REFLEXES");
  el("text", { x: 32, y: f(B + 37.5), class: "t-sec" }, "They refuse a call. They do not catch a defect,");
  el("text", { x: 32, y: f(B + 51.5), class: "t-sec" }, "so they are not in the stream.");
  let end = 434;
  HK.guards.forEach((g, i) => { const w = g.refused * sc, y = B + 16 * i;
    const b = el("g", { class: "b hk", "data-k": "h", "data-v": g.guard, tabindex: 0, role: "img", "aria-label": `${g.guard}: ${g.refused} refused` });
    el("rect", { class: "hit", x: 342, y: f(y + 9.5), width: f(w + 132), height: 15, rx: 3 }, null, b);
    el("text", { x: 426, y: f(y + 20.5), class: "t-sec", "text-anchor": "end" }, g.guard, b);
    el("rect", { class: "hbar", x: 434, y: f(y + 12.5), width: f(w), height: 9, rx: 1.5 }, null, b);
    el("text", { x: f(434 + w + 6), y: f(y + 21), class: "t-gn" }, comma(g.refused), b);
    end = Math.max(end, 434 + w); });
  el("text", { x: f(end + 70), y: f(B + 29.5), class: "t-big" }, comma(HK.refused));
  el("text", { x: f(end + 70 + 51), y: f(B + 29.5), class: "t-sec" }, "calls refused, all dates");
  if (HK.runs != null) el("text", { x: f(end + 70), y: f(B + 47.5), class: "t-cost" }, `${n(HK.runs, "run", "runs")} · ${money(HK.cost)}`);
  ["cap-output trims long output.", "It never refuses, so it has", "no count here."].forEach((s, j) => el("text", { x: 1014, y: f(B + 23.5 + 14 * j), class: "t-note" }, s));
  fig.setAttribute("viewBox", `0 0 1272 ${f(B + BH + 9.5)}`);

  // the line of figures, the key's counts, CI's counts and the stamp
  const fig4 = (num, small, what, sub) => h("div", null, h("div", { class: "num" }, num, small && h("small", null, small)), h("div", { class: "what" }, what), h("div", { class: "sub" }, sub));
  const priced = G.filter(g => g.per != null).sort((a, b) => a.per - b.per), cheap = priced[0], dear = priced[priced.length - 1];
  const late = P.late.length ? `; ${daySpan(P.late)} left out, merged after it` : "";
  const reachedLast = L[last].reached;
  $("figs").replaceChildren(
    fig4(comma(T), null, "defects", `in the Notes of ${n(P.days.length, "Day", "Days")}; ${P.cause_counts.spec} ${P.cause_counts.spec === 1 ? "was" : "were"} in a spec`),
    fig4(`${L[0].share}%`, null, "caught before any code", `${L[0].caught} of ${T}, by the auditors and the spec-change pull request`),
    fig4(`${Math.round(100 * reachedLast / T)}%`, null, `reached "${lower1(L[last].name)}"`, `${reachedLast} of ${T} got past the close`),
    priced.length ? fig4(money(cheap.per), priced.length > 1 ? `to ${money(dear.per)}` : null, priced.length > 1 ? "a catch, cheapest and dearest gate" : "a catch, at the one gate with a cost",
      `${priced.length > 1 ? `${cheap.at}; ${dear.at}` : cheap.at}. Of the ${n(priced.length, "gate", "gates")} with a cost on record, over the catches of the Days merged by the count${late}`)
      : fig4("–", null, "a catch", "no gate has a cost on record yet"));
  const icon = (shape, cls) => { const s = document.createElementNS(SVG_NS, "svg"); const a = { width: 9, height: 9, viewBox: "-4.5 -4.5 9 9", "aria-hidden": "true" };
    for (const x in a) s.setAttribute(x, a[x]); const c = document.createElementNS(SVG_NS, shape); c.setAttribute("class", cls); c.setAttribute("r", 4); s.appendChild(c); return s; };
  $("k-total").textContent = comma(T);
  $("k-causes").replaceChildren(...P.causes.filter(c => P.cause_counts[c]).map(c => h("span", null, icon("circle", `c-${c}`), `${c} ${comma(P.cause_counts[c])}`)));
  $("k-back").textContent = comma(M.back.n); $("k-esc").textContent = comma(M.escaped.n); $("k-leak").textContent = comma(leak ? leak.caught : 0);
  const CI = P.ci, ciName = w => w === "Evidence replay" ? "Evidence replay (the close's rehearsal)" : w, rehearsal = G.find(g => g.key === "rehearsal");
  $("ci").replaceChildren(h("span", { class: "h" }, "CI on every pull request"), ...CI.workflows.map(w => h("span", null, h("b", null, comma(w.failed)), ciName(w.name))),
    h("span", { class: "rest" }, CI.counted ? `Pull requests each workflow failed on, of ${comma(CI.merged)} merged; ${comma(CI.failed_any)} had at least one failed workflow. CI is not in the stream: the Notes credit it no defect, except through the close's rehearsal, which has ${rehearsal ? rehearsal.caught : 0} so far.`
      : "No workflow run is counted yet. CI is not in the stream: the Notes credit it no defect, except through the close's rehearsal."));
  const at = P.counted_at ? ` · the gates' runs and dollars are counted up to ${String(P.counted_at).slice(0, 16).replace("T", " ")}` : "";
  $("stamp").textContent = `Drawn from the page's data at ${P.head || "?"}${P.last_pr ? ` (#${P.last_pr})` : ""}, generated ${P.generated}${at}`;

  // what the picture shows, and where the model bends
  const li = (list, b, t) => list.appendChild(h("li", null, h("b", null, b), t));
  const finds = $("finds"), bends = $("bends"); finds.replaceChildren(); bends.replaceChildren();
  li(finds, "Each layer, of what reached it.", " " + L.map((x, i) => i === last && x.caught === x.reached
    ? `${x.name}: the last ${comma(x.caught)}, all of them, because nothing uncaught is counted.` : `${x.name}: ${comma(x.caught)} of ${comma(x.reached)} (${x.pct}%).`).join(" "));
  if (leak) { const Lk = L[leak.layer], gated = G.filter(g => g.layer === leak.layer && g !== leak), by = leak.by || { track: 0, self: 0, other: 0 };
    const above = G.filter(g => g !== leak && g.caught > leak.caught);
    const rank = !above.length ? "more than any gate caught" : above.length <= 2 ? `more than any gate caught except ${andList(above.map(g => g.at))}` : `fewer than ${above.length} of the gates caught`;
    li(finds, `The leak is ${comma(leak.caught)}.`, ` Of the ${comma(Lk.caught)} that left the stream ${lower1(Lk.name)}, the ${PRF_WORD[gated.length] || gated.length} gates caught ${comma(Lk.caught - leak.caught)} and ${comma(leak.caught)} ${leak.caught === 1 ? "was" : "were"} only noticed in the work (tracks ${by.track}, the session itself ${by.self}${by.other ? `, other ${by.other}` : ""}). That is ${T ? Math.round(100 * leak.caught / T) : 0}% of all defects, ${rank}.`); }
  const unpriced = G.filter(g => g.per == null && g !== leak).map(g => g.at);
  li(finds, "A catch costs", priced.length ? `, cheapest first, over the catches of the Days merged by the count: ${priced.map(g => `about ${money(g.per)} at ${g.at} (${money(g.cost)} over ${n(g.in_count, "catch", "catches")})`).join("; ")}.`
    + (P.late.length ? ` ${daySpan(P.late)} had a pull request merge after the count, so ${P.late.length === 1 ? "its" : "their"} catches share none of the dollars.` : "")
    + (unpriced.length ? ` The other gates have no cost on record (${andList(unpriced)}).` : "") : ": no gate has a cost on record yet.");
  const lastN = M.escaped.layers[last];
  li(finds, `${comma(M.escaped.n)} escaped a Day.`, M.escaped.n ? ` They were made on an earlier Day and found on a later one: ${perLayer(M.escaped).join(", ")}.`
    + (lastN < M.escaped.n ? ` Only ${lastN} of them sit${lastN === 1 ? "s" : ""} in the last layer, because a later Day found the rest while writing or closing its own work.` : " All of them sit in the last layer.") : " None was made on an earlier Day.");
  const backAt = G.filter(g => g.back).sort((a, b) => b.back - a.back).map(g => `${g.at} ${g.back}`);
  li(finds, `${comma(M.back.n)} came back.`, (M.back.n ? ` The same problem as an earlier defect, caught again: ${backAt.join(", ")}. ${M.both} of them ${M.both === 1 ? "is" : "are"} also escapes.` : " No defect names an earlier one as the same problem.")
    + ` They are not the ${comma(M.after_merge)} caught after the merge: the two sets share ${comma(M.shared)}.`);
  const R = P.reader;
  li(finds, "A second reader", R ? ` gave ${comma(R.differ)} of ${comma(R.tags)} tags differently.` + (R.stage ? ` For the tag that decides the tray, the gate that caught it, that is ${comma(R.stage[0])} of ${comma(R.stage[1])} defects (${R.stage[1] ? Math.round(100 * R.stage[0] / R.stage[1]) : 0}%).` : "")
    : " has read no Day's tags yet.");
  if (P.hooks) li(finds, "The hooks", ` refused ${n(P.hooks.refused, "call", "calls")}${P.hooks.guards.length ? ` (${P.hooks.guards.map(g => `${g.guard} ${g.refused}`).join(", ")})` : ""}${P.hooks.cost != null ? ` for ${money(P.hooks.cost)}` : ""}. No defect in the Notes is credited to them.`);
  [["Only what was found.", " A defect here is one somebody found and wrote in a Day's Notes. So the stream ends at zero, and it says nothing of what nobody found. In a cell, what survives is exactly what is not seen."],
    ["The checks are not fixed machinery.", " A cell's three checks do not change. Here a gate is added or changed between Days: the close's rehearsal is counted only from Day 12, and before that its catches sit with the evidence replay."],
    [`${n(P.days.length, "Day", "Days")} in one stream.`, " Each Day passes the layers once; the picture pools them. A square dot in \"while writing\" passed all four layers of the Day that made it and is drawn where a later Day noticed it."],
    ["Later is drawn further right,", " not lower as on the pipe below. Inside a layer the order means nothing: the leak is drawn before the gates only to keep it apart."],
    ["The leak is not a membrane.", " \"Noticed in the work\" is where a defect goes when its line names no gate. A catch by a gate the Notes do not name is counted there too."],
    ["The cost of a catch", " divides a gate's dollars by its catches on the Days whose pull requests all merged by the count, as graph 7 does: the dollars end at the count, and a Day still merging would share them with catches not yet paid for. It ignores what the gate prevented, and a gate that catches nothing has no price at all."]].forEach(([b, t]) => li(bends, b, t));

  // what the pointer says
  const where = o => typeof o.made === "number" && o.made !== o.day ? `Made on Day ${o.made} and caught on Day ${o.day}` + (o.made < o.day ? `: it escaped for ${n(o.day - o.made, "Day", "Days")}.` : ".")
    : typeof o.made === "number" ? `Made and caught on Day ${o.day}.` : o.made === "none" ? "Made outside any Day: in the plan, a tool or a machine." : `Caught on Day ${o.day}; its line does not say which Day made it.`;
  const causes = g => P.causes.map((c, i) => g.causes[i] ? `${c} ${g.causes[i]}` : "").filter(Boolean).join(", ");
  const extra = g => g.by ? `By: tracks ${g.by.track}, the session itself ${g.by.self}, other ${g.by.other}.` : g.key === "rehearsal" && CI.counted ? `CI's Evidence replay check failed on ${n(CI.rehearsal, "pull request", "pull requests")}.` : "";
  const hookDoes = g => (HOOKS.gates.find(x => x.guard === g) || {}).does;
  const say = (kind, v) => {
    if (kind === "d") { const o = P.defects[+v], g = G.find(x => x.key === o.gate);
      return { t: `${o.id} · Day ${o.day} · ${o.cause}`, l: [`Caught by: ${g.at} (${layerWord(o.layer)}).`, where(o), o.back ? `Came back: the same problem as ${o.same_as}, back again.` : "", o.noticed ? `Noticed by: ${o.noticed}.` : ""] }; }
    if (kind === "g") { const g = G[+v];
      return { t: g.label + (g.sub ? ` · ${g.sub}` : ""), l: [`${n(g.caught, "defect", "defects")} caught` + (g.caught ? `: ${causes(g)}.` : "."),
        g.runs != null ? `${n(g.runs, "run", "runs")} · ${money(g.cost)}` + (g.per != null ? ` · about ${money(g.per)} a catch, over its ${n(g.in_count, "catch", "catches")} on the Days merged by the count.` : ".") : "Its runs and cost are not counted.", extra(g), g.does] }; }
    if (kind === "L") { const x = L[+v]; return { t: `${x.name} · ${x.bio}`, l: [`${x.reached} reached it. ${x.caught} caught here (${x.pct}%). ${x.went_on} went on.`, x.what] }; }
    if (kind === "h") { const g = HK.guards.find(x => x.guard === v); return g ? { t: `${g.guard} · ${n(g.refused, "call", "calls")} refused`, l: [hookDoes(g.guard)] } : null; }
    if (kind === "mk" && v === "esc") return { t: `${n(M.escaped.n, "defect", "defects")} made on an earlier Day`, l: ["Counted as graph 7 counts it: the line's made: names a Day, and it is not the Day whose Notes record the defect. A line that says none (made in the plan, a tool or a machine) is not counted.",
      `Drawn square, in the tray of the gate that caught it on the later Day: ${perLayer(M.escaped).join(", ") || "none"}.`] };
    if (kind === "mk" && v === "back") return { t: `${n(M.back.n, "problem", "problems")} that came back`, l: ["Counted as graph 7 counts it: the defect's line names an earlier defect as the same problem.",
      `Drawn ringed, where it was caught again: ${perLayer(M.back).join(", ") || "none"}.`, `Came back is not after the merge: of the ${comma(M.after_merge)} caught after the merge, ${comma(M.shared)} came back.`] };
    return null;
  };
  // pointing at a ringed dot lights the defect it repeats; at a gate, its dots; at a mark, the dots that carry it
  let lit = [];
  const clear = () => { fig.classList.remove("foc"); lit.forEach(e => e.classList.remove("lit")); lit = []; };
  const light = list => { if (!list.length) return; list.forEach(e => { e.classList.add("lit"); lit.push(e); }); fig.classList.add("foc"); };
  const focusOn = b => { const kind = b.getAttribute("data-k"), v = b.getAttribute("data-v");
    if (kind === "d") { const o = P.defects[+v], j = o.same_as != null ? ix.get(o.same_as) : null; if (j != null && dotEls[j]) light([b, dotEls[j].b]); }
    else if (kind === "mk") light(dotEls.filter(x => x && (v === "esc" ? x.o.escaped : x.o.back)).map(x => x.b));
    else if (kind === "g") light(dotsOf[v] || []); };
  pointerBox(fig, tip, (key, b) => { clear(); const d = key && say(...key.split("|")); if (!d) return false; focusOn(b); return tipFill(tip, d); },
    b => `${b.getAttribute("data-k")}|${b.getAttribute("data-v")}`);
  // the arrow keys walk a gate's dots, a row at a time up and down; Escape goes back to the gate
  fig.addEventListener("keydown", e => { const b = e.target && e.target.closest ? e.target.closest(".b") : null; if (!b) return;
    const kind = b.getAttribute("data-k"), gi = kind === "g" ? b.getAttribute("data-v") : kind === "d" ? b.getAttribute("data-g") : null; if (gi == null) return;
    const dots = dotsOf[gi] || [], i = dots.indexOf(b), per = perOf[gi], grp = grpOf[gi];
    if (e.key === "Escape" && kind === "d") { grp.focus(); e.preventDefault(); return; }
    if (!dots.length) return;
    const to = { ArrowRight: i + 1, ArrowLeft: i < 0 ? null : i - 1, ArrowDown: i < 0 ? 0 : i + per, ArrowUp: i < 0 ? null : i - per, Home: 0, End: dots.length - 1 }[e.key];
    if (to == null) return;
    e.preventDefault();
    if (to < 0) grp.focus(); else dots[Math.min(to, dots.length - 1)].focus(); });
  // the page's Day buttons dim every other Day's dots
  onDay.push(day => dotEls.forEach(x => x && x.b.classList.toggle("mk-dim", day != null && x.o.day !== day)));
  return fig;
}

/* Graph 8 as an energy budget: one bead for each $2 of tokens at list prices, in a column for each Day beside the
   work between Days, or in a column for each date, coloured by where the dollars went. Counted in
   scripts/spec_drift_views.py (budget): every bead, dollar and share; this lays them out and words them, and counts
   nothing. `get` finds an element by its id; `onDay` is the page's Day buttons. Colours are in dashboard.css, under #atp. */
// The layout. A bead is 6.6 px on a pitch of 8.6. By date the columns share the width from x0 to x1, a step each and
// 3 px apart, `per` beads to a row. By Day a column is `step` wide at most, `per` beads to a row, and the Days end at
// x1 at the latest; the work between Days starts at bx0, each part's beads filled column by column as tall as the
// tallest Day, to bx1 at the widest. The tallest column's top row sits at y `top`, its dollars 6 px over.
const ATP_GEO = { pitch: 8.6, bead: 6.6, top: 30, date: { x0: 104, x1: 1192, per: 5 }, day: { x0: 8, x1: 590, step: 44, per: 3, bx0: 700, bx1: 1190 } };
const atpDates = (a, b) => a === b ? shortDate(a) : a.slice(0, 7) === b.slice(0, 7) ? `${+a.slice(8, 10)} to ${shortDate(b)}` : `${shortDate(a)} to ${shortDate(b)}`;
function atpDraw(B, get, onDay) {
  if (!B || B.empty) return null;  // without the dollars there are no beads: the section says why
  const $ = id => get("atp-" + id), root = get("atp"), fig = $("fig"), tip = $("tip"), G = ATP_GEO;
  const el = (n, a, txt, parent) => { const e = document.createElementNS(SVG_NS, n); for (const k in a) if (a[k] != null) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; (parent || fig).appendChild(e); return e; };
  const f = v => (+v).toFixed(1).replace(/\.0$/, "");
  const n = (k, one, many) => `${comma(k)} ${k === 1 ? one : many}`;
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
  const P = B.parts_named, PT = B.parts, days = B.cols.day, rest = B.cols.between;
  fig.replaceChildren();
  const sayDays = c => c.days.length ? daySpan(c.days) : "no Day worked";
  // `count` beads from the `from`th of a column, `per` to a row from the bottom up; `down`, `per` to a column instead
  const beads = (b, cls, from, count, per, x, bottom, down) => { for (let j = from; j < from + count; j++)
    el("rect", { class: `q ${cls}`, x: f(x + (down ? Math.floor(j / per) : j % per) * G.pitch), y: f(bottom - (down ? j % per : Math.floor(j / per)) * G.pitch), width: G.bead, height: G.bead, rx: 1.2 }, null, b); };
  const vb = {}, colEls = { date: [], day: [] };

  // by Day: a column for each Day with the average closed Day as a line, and apart from them the work between Days
  { const V = G.day, step = Math.min(V.step, (V.x1 - V.x0) / Math.max(1, days.length)), narrow = step < 40;
    const per = Math.max(1, Math.min(V.per, Math.floor((step - 4 - G.bead) / G.pitch) + 1));
    const wide = Math.floor((V.bx1 - V.bx0 - G.bead) / G.pitch) + 1, bn = rest.reduce((s, c) => s + c.b, 0);
    // as tall as the tallest Day, or taller when the blocks would not fit: each starts a new column, half a pitch apart
    const rows = Math.max(1, ...days.map(c => Math.ceil(c.b / per)), Math.ceil(bn / (wide - 2 * rest.length)));
    const bottom = G.top + (rows - 1) * G.pitch, base = bottom + G.bead + 3.5, end = V.x0 + days.length * step;
    const g = el("g", { class: "v v-day" });
    if (days.length) el("path", { class: "base", d: `M${V.x0} ${f(base)}H${f(end)}` }, null, g);
    days.forEach((c, i) => {
      const hx = V.x0 + i * step, cx = hx + step / 2, tall = Math.max(1, Math.ceil(c.b / per));
      const b = el("g", { class: "b col", tabindex: i ? -1 : 0, role: "img", "data-v": "day", "data-i": i, "aria-label": `Day ${c.day}, ${atpDates(c.dates[0], c.dates[1])}, ${money(c.u)}${c.closed ? "" : ", still open"}` }, null, g);
      el("rect", { class: "hit", x: f(hx + 1), y: 2, width: f(step - 2), height: f(base + 20), rx: 5 }, null, b);
      beads(b, "p0", 0, c.b, per, cx - ((per - 1) * G.pitch + G.bead) / 2, bottom);
      el("text", { class: "t-col", x: f(cx), y: f(base + 15.5), "text-anchor": "middle" }, narrow ? String(c.day) : `Day ${c.day}`, b);
      colEls.day.push({ b, c });
    });
    // the average closed Day on the Days' scale: a row of `per` beads is per times the unit
    if (B.mean != null) { const ay = bottom + G.bead - B.mean / B.unit / per * G.pitch;
      el("path", { class: "avgl", d: `M${V.x0} ${f(ay)}H${f(end + 6)}` }, null, g);
      el("text", { class: "t-avg", x: f(end + 10), y: f(ay + 3.5) }, `average ${money(B.mean)}`, g); }
    // each Day's dollars, drawn after the line so that it runs under them
    const tags = el("g", { class: "tags", "aria-hidden": "true" }, null, g);
    days.forEach((c, i) => { const cx = V.x0 + i * step + step / 2, tall = Math.max(1, Math.ceil(c.b / per));
      colEls.day[i].t = el("text", { class: "t-usd", x: f(cx), y: f(bottom - (tall - 1) * G.pitch - 6), "text-anchor": "middle" }, narrow ? `$${Math.round(c.u)}` : money(c.u), tags); });
    if (bn) { let col = 0, right = V.bx0;
      rest.forEach((c, i) => { if (!c.b) return;
        const x = V.bx0 + col * G.pitch, across = Math.ceil(c.b / rows);
        const b = el("g", { class: "b col", tabindex: colEls.day.length ? -1 : 0, role: "img", "data-v": "day", "data-i": days.length + i, "aria-label": `Between Days, ${c.label}, ${money(c.u)}` }, null, g);
        right = x + (across - 1) * G.pitch + G.bead;
        el("rect", { class: "hit", x: f(x - 2), y: 2, width: f(right - x + 4), height: f(base + 1), rx: 3 }, null, b);
        beads(b, "p" + c.part, 0, c.b, rows, x, bottom, true);
        col += across + 0.5; colEls.day.push({ b, c }); });
      el("path", { class: "base", d: `M${V.bx0} ${f(base)}H${f(right)}` }, null, g);
      el("text", { class: "t-usd", x: V.bx0, y: f(bottom - (Math.min(rows, rest.find(c => c.b).b) - 1) * G.pitch - 6) }, money(B.between), g);
      el("text", { class: "t-col", x: V.bx0, y: f(base + 15.5) }, "Between Days", g);
      el("text", { class: "t-ref", x: V.bx0, y: f(base + 29.5) }, andList(rest.map(c => c.label)), g); }
    vb.day = [1198, f(base + 38)]; }

  // by date: a column for each date with a session, its beads coloured by part from the bottom up
  { const V = G.date, cols = B.cols.date, step = (V.x1 - V.x0) / Math.max(1, cols.length), w = step - 3;
    const per = Math.max(1, Math.min(V.per, Math.floor((w - 6 - G.bead) / G.pitch) + 1));
    const rows = c => Math.ceil(c.b / per), bottom = G.top + (Math.max(1, ...cols.map(rows)) - 1) * G.pitch;
    const base = bottom + G.bead + 3.5, block = (per - 1) * G.pitch + G.bead;
    const g = el("g", { class: "v v-date" });
    el("path", { class: "base", d: `M${V.x0} ${f(base)}H${V.x1}` }, null, g);
    el("text", { class: "t-row", x: 92, y: f(base + 15.5), "text-anchor": "end" }, "date", g);
    el("text", { class: "t-row", x: 92, y: f(base + 31.5), "text-anchor": "end" }, "hooks refused", g);
    cols.forEach((c, i) => {
      const hx = V.x0 + 1.5 + i * step, bx = hx + (w - block) / 2, cx = hx + w / 2;
      const b = el("g", { class: "b col", tabindex: i ? -1 : 0, role: "img", "data-v": "date", "data-i": i, "aria-label": `${shortDate(c.date)}, ${sayDays(c)}, ${money(c.u)}` }, null, g);
      el("rect", { class: "hit", x: f(hx), y: 2, width: f(w), height: f(base + 36.5), rx: 5 }, null, b);
      let at = 0;
      c.pb.forEach((k, j) => { beads(b, "p" + j, at, k, per, bx, bottom); at += k; });
      el("text", { class: "t-usd", x: f(cx), y: f(bottom - (Math.max(1, rows(c)) - 1) * G.pitch - 6), "text-anchor": "middle" }, money(c.u), b);
      el("text", { class: "t-col", x: f(cx), y: f(base + 15.5), "text-anchor": "middle" }, shortDate(c.date), b);
      el("text", { class: "t-ref", x: f(cx), y: f(base + 31.5), "text-anchor": "middle" }, comma(c.refused), b);
      colEls.date.push({ b, c });
    });
    el("text", { class: "t-row", x: 92, y: f(base + 53.5), "text-anchor": "end" }, "Day worked on", g);
    const pg = el("g", { "aria-hidden": "true" }, null, g);
    B.pills.forEach(p => { const x = V.x0 + 1.5 + p.from * step + 3.5, y = base + 43.5 + 16 * p.lane, pw = (p.to - p.from + 1) * step - 10;
      el("rect", { class: "pill", x: f(x), y: f(y), width: f(pw), height: 13, rx: 6.5 }, null, pg);
      el("text", { class: "t-pill", x: f(x + pw / 2), y: f(y + 10), "text-anchor": "middle" }, `Day ${p.day}`, pg); });
    vb.date = [1198, f(base + 43.5 + 16 * Math.max(1, B.lanes) + 2.8)]; }
  const grp = () => root.getAttribute("data-grp") === "date" ? "date" : "day";
  const frame = v => { fig.setAttribute("viewBox", `0 0 ${vb[v][0]} ${vb[v][1]}`);
    fig.setAttribute("aria-label", (v === "day" ? "One column of beads for each Day with the average closed Day as a line, and beside them the work between Days, a block for each part"
      : "One column of beads for each date with a session, coloured by where the dollars went") + `; one bead for each $${B.unit} of tokens at list prices`); };
  frame(grp());

  // the figures: where the dollars went, then what they bought
  const fig4 = (num, small, what, sub) => h("div", null, h("div", { class: "num" }, num, small && h("small", null, small)), h("div", { class: "what" }, what), h("p", { class: "sub" }, sub));
  const K = B.kinds, W = B.who, low = days[B.cheap_day], high = days[B.dear_day];
  $("figs").replaceChildren(
    B.mean != null ? fig4(money(B.mean), null, "for a Day, on average", `Over ${n(B.mean_over, "closed Day", "closed Days")}`
      + (B.mean_over < B.closed ? `; ${n(B.closed - B.mean_over, "more has", "more have")} no token row` : "")
      + `. Half of them cost ${money(B.median)} or less. Day ${low.day} cost the least (${money(low.u)}), Day ${high.day} the most (${money(high.u)}).`)
      : fig4("–", null, "for a Day, on average", "No Day with a token row is closed yet."),
    fig4(money(B.on_days), `${B.on_days_pct}%`, "on the Days", `The spec, the tracks and the close of each Day: ${money(B.own)} on the Days’ own branches and ${money(B.home)} in their sessions’ replies on main.`
      + (B.built ? ` ${money(B.days_per_built)} for each of the ${n(B.built, "promise", "promises")} built.` : "")),
    fig4(money(B.between), `${B.between_pct}%`, "between the Days", rest.length ? `${cap(andList(rest.map(c => `${c.label} ${money(c.u)}`)))}.` : "Nothing was spent between Days."),
    fig4(money(B.total), null, "of tokens at list prices", `Not a bill: the maintainer pays a flat subscription. ${n(B.dates, "date", "dates")}, ${n(B.replies, "reply", "replies")}.`
      + (B.closed ? ` Shared over the ${n(B.closed, "closed Day", "closed Days")}, it is ${money(B.per_closed)} each.` : "")));
  const share = $("share");
  share.replaceChildren(...PT.map((v, i) => v ? h("i", { class: "p" + i, style: `flex:${(100 * v / B.total).toFixed(2)} 0 0` }) : null).filter(Boolean));
  share.setAttribute("aria-label", PT.map((v, i) => v ? `${B.part_pct[i]}% ${P[i]}` : null).filter(Boolean).join(", "));
  $("bought").replaceChildren(
    fig4(`${B.kind_pct[0]}%`, "upkeep", "re-reading the conversation", `${money(K[0])}. Writing context took ${B.kind_pct[1]}%, writing output ${B.kind_pct[2]}%.` + (K[3] ? ` ${money(K[3])} could not be split.` : "")),
    B.past != null ? fig4(`${B.past_pct}%`, "past 150k", "spent in replies that read over 150k tokens", `${money(B.past)}, of which ${money(B.past_main || 0)} in the main session. A fresh session would spare most of it.`
      + (B.past_unknown ? ` ${n(B.past_unknown, "row has", "rows have")} no such figure, and ${B.past_unknown === 1 ? "is" : "are"} left out.` : ""))
      : fig4("–", "past 150k", "spent in replies that read over 150k tokens", "No row has that figure yet."));
  // the short key: a bead, each part with its dollars, and the line at the average
  const sw = cls => { const s = document.createElementNS(SVG_NS, "svg"); [["width", 9], ["height", 9], ["viewBox", "0 0 9 9"], ["aria-hidden", "true"]].forEach(([k, v]) => s.setAttribute(k, v));
    const r = document.createElementNS(SVG_NS, "rect"); [["class", `q ${cls}`], ["x", 1], ["y", 1], ["width", 7], ["height", 7]].forEach(([k, v]) => r.setAttribute(k, v)); s.appendChild(r); return s; };
  const item = (cls, word, v) => h("span", null, sw(cls), `${word} `, h("b", null, money(v)));
  $("key").replaceChildren(...[h("span", null, sw("qn"), h("span", { class: "kt" }, "one bead is ", h("b", null, `$${B.unit}`), ", rounded")), h("i", { class: "sep" }),
    ...PT.map((v, i) => v ? item("p" + i, P[i], v) : null),
    B.mean != null ? h("span", { class: "avg" }, h("i", { class: "ln" }), "the average closed Day ", h("b", null, money(B.mean))) : null].filter(Boolean));

  // the folded text: how the beads are rounded and the dollars split, the two tables and the stamp
  $("k-beads").textContent = comma(B.beads);
  $("round").textContent = `${n(B.beads, "bead", "beads")} of ${money(B.unit)} make ${money(B.beads * B.unit)}; the data says ${money(B.total)}. The whole beads go to the columns by largest remainder, so the picture always holds ${comma(B.beads)} beads, by Day and by date; the furthest a date’s column is from its dollars is ${B.furthest} of a bead. The colours inside a date’s column are shared out over its beads the same way, so a part worth less than half a bead on a date may have none there. The figure over a column is its exact dollars.`;
  const U = B.unsplit, S = B.split;
  $("split").textContent = `What the dollars bought is worked out from the list prices in scripts/token-usage.py, checked ${B.prices_checked}. A row is split only when its cost, worked out again from its tokens, is within 1% of the cost in the data: ${S.rows} of ${S.rows + U.rows} rows are (${money(S.dollars)}${S.off != null ? `; the furthest is ${S.off}% off` : ""}), with the main session’s cache writes at the one-hour price and an agent’s at the five-minute price.`
    + (U.rows ? ` The other ${n(U.rows, "row", "rows")} (${money(U.dollars)}; ${U.models.join(", ")}) ${U.rows === 1 ? "is" : "are"} not: a price set reply by reply, as for a long prompt, or a model not in the list, cannot be worked out again from sums.` : "");
  const td = v => h("td", { class: "r" }, v), dollars = x => x == null ? "" : (+x).toFixed(2);
  const tableOf = (head, rows, all) => h("table", null, h("tr", null, head.map(x => h("th", null, x))), rows, all);
  const KH = ["Re-reading", "Writing context", "Writing output", "Not split"], WH = ["Main session", "Auditors", "Defect-rater", "Implementer", "Other agents"];
  const DC = B.cols.date, drawn = PT.map((v, i) => v ? i : null).filter(i => i != null);
  $("tbl-date").replaceChildren(tableOf(["Date", "Days", "Dollars", "Beads", ...drawn.map(i => cap(P[i])), ...KH, "Past 150k", "Past 150k, main", ...WH, "Replies", "Calls refused", "Outputs cut"],
    DC.map(c => h("tr", null, h("td", null, shortDate(c.date)), h("td", null, c.days.join(", ")), td(dollars(c.u)), td(c.b), drawn.map(i => td(dollars(c.pt[i]))), c.k.map(x => td(dollars(x))), td(dollars(c.p)), td(dollars(c.pm)),
      c.w.map(x => td(dollars(x))), td(comma(c.rp)), td(c.refused), td(c.cut))),
    h("tr", null, h("th", null, "All"), h("td", null, ""), td(dollars(B.total)), td(B.beads), drawn.map(i => td(dollars(PT[i]))), K.map(x => td(dollars(x))), td(dollars(B.past)), td(dollars(B.past_main)),
      W.map(x => td(dollars(x))), td(comma(B.replies)), td(B.refused), td(B.cut))));
  const row = (name, when, c, day) => h("tr", null, h("td", null, name), h("td", null, when), td(dollars(c.u)), td(day ? dollars(c.own) : ""), td(day ? dollars(c.home) : ""), td(c.b),
    c.k.map(x => td(dollars(x))), td(dollars(c.p)), c.w.map(x => td(dollars(x))), td(comma(c.rp)));
  $("tbl-day").replaceChildren(tableOf(["Day or part", "Dates with a session", "Dollars", "On its own branch", "On main", "Beads", ...KH, "Past 150k", ...WH, "Replies"],
    [...days.map(c => row(`Day ${c.day}${c.closed ? "" : " (open)"}`, atpDates(c.dates[0], c.dates[1]), c, true)), ...rest.map(c => row(`Between Days: ${c.label}`, n(c.n_dates, "date", "dates"), c, false))]));
  $("stamp").textContent = `Drawn from the page’s data at ${B.head || "?"}${B.last_pr ? ` (#${B.last_pr})` : ""}, generated ${B.generated}`;

  // what the picture shows, and where the model bends
  const li = (list, b, t) => list.appendChild(h("li", null, h("b", null, b), t));
  const finds = $("finds"), bends = $("bends"); finds.replaceChildren(); bends.replaceChildren();
  if (B.mean != null) li(finds, `A closed Day cost ${money(B.mean)} on average.`, ` Half of the ${n(B.mean_over, "closed Day", "closed Days")} cost ${money(B.median)} or less; Day ${low.day} cost the least (${money(low.u)}) and Day ${high.day} the most (${money(high.u)}).`);
  li(finds, `The Days took ${B.on_days_pct}%`, `: ${money(B.on_days)} of ${money(B.total)}, ${money(B.own)} of it on the Days’ own branches and ${money(B.home)} in their sessions’ replies on main.`);
  li(finds, `${B.between_pct}% went between the Days`, rest.length ? `: ${andList(rest.map(c => `${c.label} ${money(c.u)} (${B.part_pct[c.part]}%)`))}.` : ".");
  li(finds, `Upkeep is ${B.read_tokens_pct}% of the tokens and ${B.kind_pct[0]}% of the dollars.`, ` Re-reading cost ${money(K[0])} of ${money(B.total)}.`
    + (B.write_over_read ? ` At list prices a token written to the main session’s cache costs ${B.write_over_read} times a token read from it (${B.main_model}: $${B.write_price} against $${B.read_price.toFixed(2)} a million).` : ""));
  li(finds, `Growth is ${B.kind_pct[1] + B.kind_pct[2]}%.`, ` Writing new context cost ${money(K[1])} and writing output ${money(K[2])}.` + (U.rows ? ` ${n(U.rows, "row", "rows")} (${money(U.dollars)}) could not be split.` : ""));
  if (B.past != null) { const top = DC[B.past_most];
    li(finds, `${money(B.past)} was spent in replies past 150k tokens`, `, ${B.past_pct}% of everything: ${money(B.past_main || 0)} in the main session and ${money(B.past - (B.past_main || 0))} in agents.`
      + (top && top.p ? ` ${shortDate(top.date)} has the largest share, ${money(top.p)} of its ${money(top.u)}.` : "")); }
  const agents = ["the auditors", "the defect-rater", "the implementer", "other agents"].map((w, i) => [w, W[i + 1]]).filter(x => x[1]);
  li(finds, `The main session spent ${B.who_pct[0]}%`, ` (${money(W[0])}).` + (agents.length ? ` ${agents.map(([w, v], i) => `${i ? w : `${cap(w)} spent`} ${money(v)}`).join(", ")}.` : " No agent spent anything."));
  const dear = DC[B.dear], cheap = DC[B.cheap];
  li(finds, `${shortDate(dear.date)} was the dearest date`, ` (${money(dear.u)}${dear.days.length ? `, ${daySpan(dear.days)}` : ""}) and ${shortDate(cheap.date)} the cheapest (${money(cheap.u)}).`);
  const most = DC[B.most_refused];
  li(finds, `The hooks refused ${n(B.refused, "call", "calls")}`, (B.guards.length ? ` (${B.guards.map(([g, k]) => `${comma(k)} by the ${g}`).join(", ")})` : "") + ` and cut ${n(B.cut, "long output", "long outputs")}.`
    + (most && most.refused ? ` ${shortDate(most.date)} had the most refusals, ${comma(most.refused)}.` : ""));
  if (B.driver) li(finds, "The driver’s own runs are not in these beads.", ` Its run log counts ${n(B.driver.sessions, "session", "sessions")} over ${n(B.driver.steps, "step", "steps")}, ${money(B.driver.cost)}, on the project it drove.`);
  [["A session has one home.", " A reply on a branch counts to that branch. A reply on main counts to the branch its session spent the most on, so a session that audited a Day and then built the dashboard counts its audit as dashboard."],
    ["Stayed on main is not idle.", " A session that never left main read, audited, answered or ran the steps after a merge. Which Day it served is not known, so it stands between the Days."],
    ["An open Day is not in the average.", " Its dollars are still moving. It has a column, and the average waits for its close."],
    ["List prices are not the bill.", " The maintainer pays a flat subscription. The beads measure use on the pay-per-token price list, for this repository’s sessions only, counted on the maintainer’s computer."],
    ["Upkeep is not waste.", " A cell that stops its upkeep dies. A reply that does not read the conversation does not know the work. Only the part a shorter conversation would not have read is avoidable."],
    ["Growth is not all tissue.", " Writing context and output includes the attempts that failed and the checks that passed. The beads count dollars, not what was built."],
    ["A bead is not a molecule.", ` It is ${money(B.unit)}, rounded: a column or a part can be up to about one bead from its exact dollars, and a part worth less than half a bead on a date may have none there.`]].forEach(([b, t]) => li(bends, b, t));

  // what the pointer says
  const parts = (names, vals) => names.map((x, i) => vals[i] ? `${x} ${money(vals[i])}` : null).filter(Boolean).join(", ") || "nothing";
  const past = c => c.p == null ? "No row has a figure for the replies that read over 150k tokens." : c.p ? `${money(c.p)} of it in replies that read over 150k tokens` + (c.pm != null && c.pm >= c.p ? ", all in the main session." : c.pm ? `, ${money(c.pm)} of that in the main session.` : ", none of that in the main session.") : "Nothing in replies that read over 150k tokens.";
  const say = (v, i) => { const date = v === "date", c = date ? B.cols.date[+i] : days[+i] || rest[+i - days.length]; if (!c) return null;
    const l = [`What it bought: ${parts(B.kinds_named, c.k)}.`, `Who spent it: ${parts(B.who_named, c.w)}.`, past(c)];
    const q = `${n(c.b, "bead", "beads")} of ${money(B.unit)} make ${money(c.b * B.unit)}; the exact figure is ${money(c.u)}.`;
    if (date) return { t: `${shortDate(c.date)} · ${sayDays(c)} · ${money(c.u)}`, q, l: [`Where it went: ${parts(P, c.pt)}.`, ...l,
      `${n(c.rp, "reply", "replies")}. The hooks refused ${n(c.refused, "call", "calls")}${c.rf.length ? ` (${c.rf.map(([g, k]) => `${k} by the ${g}`).join(", ")})` : ""}.`] };
    if (c.day != null) return { t: `Day ${c.day} · ${atpDates(c.dates[0], c.dates[1])} · ${money(c.u)}`, q, l: [`${money(c.own)} on its own branch, ${money(c.home)} in its sessions’ replies on main.`,
      c.over == null ? "Still open: not in the average." : `${money(Math.abs(c.over))} ${c.over >= 0 ? "over" : "under"} the average closed Day.`, ...l, `${n(c.rp, "reply", "replies")}.`] };
    return { t: `Between Days · ${c.label} · ${money(c.u)}`, q, l: [`${B.part_pct[c.part]}% of everything, on ${n(c.n_dates, "date", "dates")}.`, ...l, `${n(c.rp, "reply", "replies")}.`] }; };
  pointerBox(fig, tip, key => { const d = key && say(...key.split("|")); return d ? tipFill(tip, d) : false; }, b => `${b.getAttribute("data-v")}|${b.getAttribute("data-i")}`);
  // one Tab stop for the columns; the arrow keys walk along them
  fig.addEventListener("keydown", e => { const cur = e.target && e.target.closest ? e.target.closest(".col") : null; if (!cur) return;
    const all = colEls[cur.getAttribute("data-v")].map(x => x.b), i = all.indexOf(cur);
    const j = { ArrowRight: i + 1, ArrowDown: i + 1, ArrowLeft: i - 1, ArrowUp: i - 1, Home: 0, End: all.length - 1 }[e.key];
    if (j == null) return;
    e.preventDefault(); const k = Math.max(0, Math.min(all.length - 1, j));
    if (k !== i) { cur.setAttribute("tabindex", "-1"); all[k].setAttribute("tabindex", "0"); all[k].focus(); } });
  // the control: what a column is
  $("ctl").addEventListener("click", e => { const b = e.target && e.target.closest ? e.target.closest("button[data-set]") : null; if (!b) return;
    b.parentNode.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", x === b ? "true" : "false"));
    root.setAttribute(`data-${b.getAttribute("data-set")}`, b.getAttribute("data-val"));
    frame(grp());
    tip.hidden = true; });
  // the page's Day buttons dim every column not on that Day, and the work between Days with them
  onDay.push(day => { colEls.date.forEach(x => x.b.classList.toggle("mk-dim", day != null && !x.c.days.includes(day)));
    colEls.day.forEach(x => [x.b, x.t].forEach(e => e && e.classList.toggle("mk-dim", day != null && x.c.day !== day))); });
  return fig;
}

/* Graph 9 as growth rings, as the mockup at #228 draws it: a ring for each Day, as wide as the lines its own pull
   requests changed, and below, a hatched ring for the work no Day owns, at the furthest Day begun when it merged. Counted in
   scripts/spec_drift_views.py (rings): every ring's lines, share and pull requests; this turns lines into px with one
   scale for both strips, and words them. Colours are in dashboard.css, under #rng. */
const RNG_NAME = { prod: "Production code", test: "Tests", spec: "Specs", context: "Agent context", tooling: "Tooling" };
// The layout, from the mockup's coordinates. A strip is 120 px tall (upper y 47, lower y 236); its rings start at x 7,
// 2 px apart. A ring's left edge is one quadratic, x = x0 + 20t(1 - t), its control 10 px right at mid-height; a band
// is the sub-curve of it from its start to its end share, and its right edge the same curve `w` px further. One px of
// width is the same number of lines in both strips: the larger of the upper strip's lines over 745 px and the lower
// strip's over 1182 px, less the gaps. A ring under 20 px is named under its strip, under a lead.
const RNG_GEO = { h: 120, gap: 2, x0: 7, up: 47, low: 236, upW: 745, lowW: 1182, label: 20 };
function rngDraw(R, get, onDay) {
  if (!R || R.empty) return null;
  const $ = id => get("rng-" + id), fig = $("fig"), tip = $("tip"), G = RNG_GEO;
  const el = (n, a, txt, parent) => { const e = document.createElementNS(SVG_NS, n); for (const k in a) if (a[k] != null) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; (parent || fig).appendChild(e); return e; };
  const f = v => String(Math.round(+v * 100) / 100);
  const n = (k, one, many) => `${comma(k)} ${k === 1 ? one : many}`;
  fig.replaceChildren();
  const pat = el("pattern", { id: "rng-hatch", width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, null, el("defs", {}));
  el("rect", { class: "hatch", width: 2.1, height: 5 }, null, pat);
  const D = R.days, O = R.outside, up = sum(D, x => x.lines), low = sum(O, x => x.lines);
  const L = Math.max(up / Math.max(1, G.upW - G.gap * Math.max(0, D.length - 1)), low / Math.max(1, G.lowW - G.gap * Math.max(0, O.length - 1)), 1e-9);
  // a point of a ring's left edge at t, and the control point of its sub-curve from t0 to t1 (de Casteljau)
  const bx = (x0, t) => x0 + 20 * t * (1 - t), cx = (x0, t0, t1) => x0 + 10 * (t0 + t1 - 2 * t0 * t1);
  const ringName = r => r.day != null ? `Day ${r.day}` : `at Day ${r.at}`;
  const aria = r => `${r.day != null ? `Day ${r.day}` : `Outside any Day, at Day ${r.at}`}: ${n(r.lines, "line", "lines")} changed in ${n(r.prs, "pull request", "pull requests")}. `
    + r.k.filter(k => r.day != null || k[1]).map(k => `${lower(RNG_NAME[k[0]])} ${k[2]}`).join(", ");
  const groups = [];
  // a word's box, about 5.6 px a character, from 9 px above its baseline to 2 below, and whether two boxes touch
  const box = (x, y, len, end) => { const w = 5.6 * len, x0 = end ? x - w : x; return [x0, x0 + w, y - 9, y + 2]; };
  const hits = (p, q) => p[0] < q[1] + 2 && q[0] < p[1] + 2 && p[2] < q[3] && q[2] < p[3];
  // `taken`: the boxes of the words already under the strip (its pith and bark); each run's words are added to it
  const strip = (rings, y0, hatched, taken) => {
    let x = G.x0; const mid = y0 + G.h / 2, y1 = y0 + G.h, thin = [];
    rings.forEach(r => {
      const w = r.lines / L;
      if (w >= G.label) { el("text", { class: "t-day", x: f(x + w / 2), y: f(y0 - 19), "text-anchor": "middle" }, ringName(r));
        el("text", { class: "t-lines", x: f(x + w / 2), y: f(y0 - 7), "text-anchor": "middle" }, comma(r.lines)); }
      else thin.push({ r, x, w });
      const b = el("g", { class: hatched ? "b out" : "b", tabindex: 0, role: "img", "data-k": r.key, "aria-label": aria(r) });
      let t0 = 0, seams = [], pills = [];
      r.k.forEach(([k, lines, share, frac]) => { if (!lines) return; const t1 = Math.min(1, t0 + frac), ya = y0 + G.h * t0, yb = y0 + G.h * t1, c = cx(x, t0, t1), cy = y0 + G.h * (t0 + t1) / 2;
        el("path", { class: `k-${k}`, d: `M${f(bx(x, t0))} ${f(ya)} Q${f(c)} ${f(cy)} ${f(bx(x, t1))} ${f(yb)}L${f(bx(x, t1) + w)} ${f(yb)} Q${f(c + w)} ${f(cy)} ${f(bx(x, t0) + w)} ${f(ya)}Z` }, null, b);
        if (t1 < 0.9999) seams.push([bx(x, t1), yb]);
        // a band tall enough, in a ring wide enough, carries its share on a pill
        const pw = 5.89 * share.length + 7;
        if (yb - ya >= 16 && w >= pw + 4) pills.push([bx(x, (t0 + t1) / 2) + w / 2, (ya + yb) / 2, pw, share]);
        t0 = t1; });
      if (hatched) el("path", { class: "over", fill: "url(#rng-hatch)", d: `M${f(x)} ${y0} Q${f(x + 10)} ${mid} ${f(x)} ${y1}L${f(x + w)} ${y1} Q${f(x + w + 10)} ${mid} ${f(x + w)} ${y0}Z` }, null, b);
      seams.forEach(([sx, sy]) => el("path", { class: "seam", d: `M${f(sx)} ${f(sy)} H${f(sx + w)}` }, null, b));
      pills.forEach(([px, py, pw, s]) => { el("rect", { class: "pill", x: f(px - pw / 2), y: f(py - 6.5), width: f(pw), height: 13, rx: 3 }, null, b);
        el("text", { class: "t-share", x: f(px), y: f(py + 3.3), "text-anchor": "middle" }, s, b); });
      el("path", { class: "late", d: `M${f(x + w)} ${y0} Q${f(x + w + 10)} ${mid} ${f(x + w)} ${y1}` }, null, b);
      const hw = Math.max(5, w), hx = x + w / 2 - hw / 2;
      el("path", { class: "hit", d: `M${f(hx)} ${y0} Q${f(hx + 10)} ${mid} ${f(hx)} ${y1}L${f(hx + hw)} ${y1} Q${f(hx + hw + 10)} ${mid} ${f(hx + hw)} ${y0}Z` }, null, b);
      groups.push({ b, r });
      x += w + G.gap;
    });
    // the rings too thin for a label: one lead under each run of them, and their names and lines after it. Words that
    // would touch words already there go to the run's other side, or a line lower on a longer lead, until they touch none.
    const runs = []; thin.forEach(t => { const last = runs[runs.length - 1]; if (last && Math.abs(last[last.length - 1].x + last[last.length - 1].w + G.gap - t.x) < 0.01) last.push(t); else runs.push([t]); });
    runs.forEach(run => { const a = run[0].x + 0.5, z = Math.max(a, run[run.length - 1].x + run[run.length - 1].w - 0.5);
      const words = run.map(t => `${ringName(t.r)}: ${comma(t.r.lines)}`).join(" · "), right = a + 5.6 * words.length > 1100;
      let at = null;
      for (let k = 0; !at; k++) for (const end of right ? [true, false] : [false, true]) {
        const x = end ? z : Math.max(1, a - 0.5), y = y1 + 17 + 12 * k, b = box(x, y, words.length, end);
        if (!at && (k > 8 || (b[0] >= 0 && b[1] <= 1198 && !taken.some(t => hits(t, b))))) at = { x, y, end, b };
      }
      // a longer lead runs down to its words, and is not drawn where it would cross words already there
      const lx = at.end ? z : a, stop = at.y - 10;
      let more = "", from = y1 + 6;
      if (at.y > y1 + 17) {
        taken.filter(t => t[0] <= lx && lx <= t[1]).map(t => [t[2] - 1, t[3] + 1]).sort((p, q) => p[0] - q[0]).forEach(([c0, c1]) => {
          if (Math.min(c0, stop) - from > 0.5) more += ` M${f(lx)} ${f(from)} V${f(Math.min(c0, stop))}`;
          from = Math.max(from, c1); });
        if (stop - from > 0.5) more += ` M${f(lx)} ${f(from)} V${f(stop)}`;
      }
      taken.push(at.b);
      el("path", { class: "lead", d: `M${f(a)} ${y1 + 6} V${y1 + 3} H${f(z)} V${y1 + 6}` + more });
      el("text", { class: "t-lines", x: f(at.x), y: at.y, "text-anchor": at.end ? "end" : null }, words); });
    return x - G.gap;
  };
  const head1 = el("text", { class: "t-head", x: 7, y: 10 }, "Inside the Days ");
  el("tspan", { class: "t-note" }, `· each ring is a Day’s own pull requests · ${n(R.inside.lines, "line", "lines")} in ${n(R.inside.prs, "pull request", "pull requests")}`, head1);
  // the pith's and the bark's words are placed first, so the thin rings' words keep clear of them
  const bark = G.x0 + sum(D, r => r.lines / L) + G.gap * Math.max(0, D.length - 1) + 2.5, endY = G.up + G.h + 12;
  const pith = D.length ? `pith · Day ${D[0].day}, ${D[0].first}` : "", barkW = D.length ? `bark · Day ${D[D.length - 1].day}, ${D[D.length - 1].last}` : "";
  const upTaken = D.length ? [box(1, endY, pith.length, false), box(bark + 3.5, endY, barkW.length, true)] : [];
  strip(D, G.up, false, upTaken);
  if (D.length) {
    el("circle", { class: "pith", cx: 3, cy: G.up + G.h / 2, r: 2.6 });
    el("path", { class: "bark", d: `M${f(bark)} ${G.up} Q${f(bark + 10)} ${G.up + G.h / 2} ${f(bark)} ${G.up + G.h}` });
    el("text", { class: "t-end", x: 1, y: endY }, pith);
    el("text", { class: "t-end", x: f(bark + 3.5), y: endY, "text-anchor": "end" }, barkW);
  }
  // the lower strip moves down as far as the upper strip's words reach, 4 px clear of its heading's top
  const LOW = G.low + Math.max(0, Math.max(0, ...upTaken.map(b => b[3])) + 4 - (G.low - 46));
  const head2 = el("text", { class: "t-head", x: 7, y: LOW - 37 }, "Outside any Day ");
  el("tspan", { class: "t-note" }, O.length ? `· each ring is the work merged at that Day, while it was open or after it closed · ${n(R.out.lines, "line", "lines")} in ${n(R.out.prs, "pull request", "pull requests")}` : "· no pull request on no Day’s branch has merged yet", head2);
  const lowTaken = O.length ? [box(1195, LOW + G.h + 17, "bark · today".length, true)] : [];
  const lowEnd = strip(O, LOW, true, lowTaken);
  if (O.length) { el("path", { class: "bark", d: `M${f(lowEnd + 2.5)} ${LOW} Q${f(lowEnd + 12.5)} ${LOW + G.h / 2} ${f(lowEnd + 2.5)} ${LOW + G.h}` });
    el("text", { class: "t-end", x: 1195, y: LOW + G.h + 17, "text-anchor": "end" }, "bark · today"); }

  // the two columns at the top right: the whole project by kind, inside the Days and outside; the narrower is 24 px
  const sides = [[R.inside, `The ${n(R.inside.n_days, "Day", "Days")}`, "all", false], ...(R.out.lines ? [[R.out, "Outside any Day", "out", true]] : [])];
  const x1 = Math.max(bark, 300) + 41.5, x2 = (x1 + 1196) / 2 - 4.4, narrow = Math.min(...sides.map(s => s[0].lines)) || 1;
  const ht = el("text", { class: "t-head", x: f(x1), y: 10 }, "The whole project ");
  el("tspan", { class: "t-note" }, `· ${n(R.drawn, "line", "lines")}, by what the file is`, ht);
  sides.forEach(([S, name, key, hatched], i) => {
    const x = i ? x2 : x1, w = 24 * S.lines / narrow, right = x + w;
    el("text", { class: "t-day", x: f(x), y: 28 }, name); el("text", { class: "t-lines", x: f(x), y: 40 }, `${comma(S.lines)} · ${S.share}`);
    const b = el("g", { class: hatched ? "b out" : "b", tabindex: 0, role: "img", "data-k": key, "aria-label": `${name}: ${n(S.lines, "line", "lines")} changed. ` + S.k.map(k => `${lower(RNG_NAME[k[0]])} ${k[2]}`).join(", ") });
    let y = G.up; const marks = [];
    S.k.forEach(([k, lines, share, frac]) => { if (!lines) return; const hgt = G.h * frac;
      el("rect", { class: `k-${k}`, x: f(x), y: f(y), width: f(w), height: f(Math.max(0.4, hgt)) }, null, b);
      marks.push({ k, lines, share, mid: y + hgt / 2 }); y += hgt; });
    if (hatched) el("rect", { class: "over", fill: "url(#rng-hatch)", x: f(x), y: G.up, width: f(w), height: G.h }, null, b);
    el("rect", { class: "hit", x: f(x), y: G.up, width: f((i || sides.length === 1 ? 1196 : x2 - 6) - x), height: G.h }, null, b);
    groups.push({ b, r: S });
    // the leads: each kind's label at its band's middle, pushed apart to 12.5 px, between y 52 and 163
    marks.forEach((m, j) => { m.y = Math.max(m.mid, j ? marks[j - 1].y + 12.5 : 52); });
    for (let j = marks.length - 1; j >= 0; j--) marks[j].y = Math.min(marks[j].y, j < marks.length - 1 ? marks[j + 1].y - 12.5 : 163);
    marks.forEach(m => { el("path", { class: "lead", d: `M${f(right + 1)} ${f(m.mid)} L${f(right + 6)} ${f(m.y)} H${f(right + 10)}` });
      const t = el("text", { class: "t-kind", x: f(right + 12), y: f(m.y + 3.5) }, `${RNG_NAME[m.k]} `);
      el("tspan", { class: "t-lines" }, `${comma(m.lines)} · ${m.share}`, t); });
  });
  fig.setAttribute("viewBox", `0 0 1198 ${Math.round(Math.max(379 + LOW - G.low, ...lowTaken.map(b => b[3] + 4)))}`);
  fig.setAttribute("aria-label", `Two strips of rings on one scale. Above, one ring for each Day${D.length ? ` from ${D[0].day} to ${D[D.length - 1].day}` : ""}, as wide as the lines its own pull requests changed, ${comma(R.inside.lines)} in all. Below, ${n(O.length, "ring", "rings")} of work outside any Day, ${n(R.out.lines, "line", "lines")}. Each ring is cut into bands by kind of file. Beside them, the whole project by kind`);

  // the line of figures, the scale, the stamp
  const fig4 = (num, what, sub) => h("div", null, h("div", { class: "num" }, num), h("div", { class: "what" }, what), h("div", { class: "sub" }, sub));
  const day = i => D[i], ow = i => O[i];
  $("figs").replaceChildren(
    fig4(comma(R.drawn), `lines changed in ${n(R.prs, "merged pull request", "merged pull requests")}`, `${comma(R.inside.lines)} inside the ${n(R.inside.n_days, "Day", "Days")}, ${comma(R.out.lines)} outside any Day`),
    fig4(R.prod_share, "of them are production code", `${n(R.prod_lines, "line", "lines")}. Inside the Days alone: ${R.inside.k[0][2]}`),
    R.ratio != null ? fig4(R.ratio.toFixed(1), "lines of tests for each line of production code", `inside the Days.${R.ratio_low && R.ratio_high ? ` From ${R.ratio_low[0].toFixed(1)} on Day ${R.ratio_low[1]} to ${R.ratio_high[0].toFixed(1)} on Day ${R.ratio_high[1]}` : ""}`)
      : fig4("–", "lines of tests for each line of production code", "no production code inside the Days yet"),
    R.heavy != null ? fig4(`Day ${day(R.heavy).day}`, `is the heaviest: ${n(day(R.heavy).lines, "line", "lines")}`, `the lightest is Day ${day(R.light).day}, ${comma(day(R.light).lines)}.`
      + (R.wide_out != null ? ` The widest ring outside a Day: at Day ${ow(R.wide_out).at}, ${comma(ow(R.wide_out).lines)}` : "")) : null);
  $("scale").textContent = comma(L);
  $("stamp").textContent = `Drawn from the page’s data at ${R.head || "?"}${R.last_pr ? ` (#${R.last_pr})` : ""}, generated ${R.generated} · ${n(R.merges, "merge", "merges")}${D.length ? ` · ${daySpan(D.map(x => x.day))}` : ""}`
    + (R.before.lines ? ` · ${n(R.before.lines, "line", "lines")} before Day 1, in no ring` : "") + (R.unplaced.lines ? ` · ${n(R.unplaced.lines, "line", "lines")} on neither strip` : "");

  // what the picture shows, and where the model bends
  const li = (list, b, t) => list.appendChild(h("li", null, h("b", null, b), t));
  const finds = $("finds"), bends = $("bends"); finds.replaceChildren(); bends.replaceChildren();
  const I = R.inside, X = R.out, pctOf = (a, b) => b ? Math.round(100 * a / b) : 0;
  li(finds, X.lines > I.lines ? "Most of the wood is outside the Days." : "Most of the wood is inside the Days.", ` ${comma(X.lines)} of the ${comma(R.drawn)} lines (${pctOf(X.lines, R.drawn)}%) merged in ${n(X.prs, "pull request", "pull requests")} outside any Day. The ${n(I.n_days, "Day", "Days")}’ own ${n(I.prs, "pull request", "pull requests")} changed ${comma(I.lines)}.`);
  const isAre = k => k === "test" || k === "spec" ? "are" : "is";
  if (X.lines) { const top = [...X.k].sort((a, b) => b[1] - a[1]).slice(0, 2).filter(k => k[1]), inK = k => I.k.find(x => x[0] === k);
    li(finds, "That work is another tissue.", ` Outside the Days, ${top.map((k, i) => `${k[2]}${i ? "" : " of the lines"} are ${lower(RNG_NAME[k[0]])}`).join(" and ")}. Inside them, ${top.map(k => `${lower(RNG_NAME[k[0]])} ${isAre(k[0])} ${inK(k[0])[2]}`).join(" and ")}.`);
    if (O.length > 2 && 2 * R.top_out.lines > X.lines) li(finds, "Two rings hold most of it.", ` The work at ${andList(R.top_out.at.map(a => `Day ${a}`))} is ${comma(R.top_out.lines)} of the ${comma(X.lines)} lines outside any Day (${R.top_out.share}).`); }
  li(finds, "Production code grows inside the Days.", ` ${comma(I.w.prod)} of its ${comma(R.prod_lines)} lines are in a Day’s own pull requests.${X.w.prod ? ` Only ${comma(X.w.prod)} ${X.w.prod === 1 ? "is" : "are"} outside.` : ""}`);
  const [tk, tc] = R.tallest.length ? R.tallest[0] : ["test", 0];
  if (D.length) li(finds, `${RNG_NAME[tk]} ${isAre(tk)} the tallest band in ${tc === D.length ? "all" : `${tc} of the`} ${n(D.length, "Day’s ring", "Days’ rings")}.`, `${R.spec_over_test.length ? ` Counted with specs and agent context as one kind, that kind is larger than tests on ${daySpan(R.spec_over_test)}.` : ""} Over the Days: tests ${comma(I.w.test)}, specs and agent context ${comma(I.w.spec + I.w.context)} (${comma(I.w.spec)} and ${comma(I.w.context)}), production code ${comma(I.w.prod)}, tooling ${comma(I.w.tooling)}.`);
  if (R.spread != null) li(finds, X.lines ? "The Days’ rings differ less than the others." : "How much the Days’ rings differ.", ` The widest Day is ${R.spread} times the narrowest (Day ${day(R.heavy).day} against Day ${day(R.light).day}).`
    + (O.length ? ` Outside the Days the widest ring is ${n(ow(R.wide_out).lines, "line", "lines")} and the narrowest ${comma(ow(R.thin_out).lines)}.` : ""));
  const seasons = R.seasons.map(([k, c]) => `${n(c, "Day", "Days")} took ${n(k, "calendar date", "calendar dates")}`);
  [["A tree grows one tissue.", " A ring of wood is the same material all through. A Day’s ring is five kinds of file, and the bands are the point of the picture."],
    ["A deleted line is growth here.", " A ring’s width is lines added plus lines deleted, so removing code widens a ring."],
    ["A Day is not a season.", ` A tree’s ring is one year. A Day is a step of the plan${seasons.length ? `: ${andList(seasons)}` : ""}. Ring width says how much changed, not how fast.`],
    ["Old rings do not stay whole.", " Wood laid down stays where it is. A merged Day cannot be changed, but a later Day rewrites the same files, so a ring is what changed then, not what stands today."],
    ["A tree has no work between its rings.", ` Here the lower strip is ${low > up ? "wider" : "narrower"} than the upper one. It is not a second tree: its rings sit between the Days’ rings in time, and are drawn apart so the Days stay readable.`],
    ["Some lines are not counted.", " Files a tool writes and binary files are left out. Breaks on purpose never merge, so checking did more than its lines show."]].forEach(([b, t]) => li(bends, b, t));

  // the exact numbers
  const td = v => h("td", { class: "r" }, v);
  const outAt = d => O.find(o => o.at === d);
  $("table").replaceChildren(h("tr", null, ["Day", ...Object.values(RNG_NAME), "All", "Pull requests merged", "Test lines for each production line", "Outside any Day: lines", "Outside any Day: pull requests"].map(x => h("th", null, x))),
    // spread: replaceChildren() does not flatten an array, it writes it as text
    ...D.map(r => h("tr", null, h("td", null, `Day ${r.day}`), r.k.map(k => td(comma(k[1]))), td(comma(r.lines)), td(r.prs), td(r.ratio == null ? "–" : r.ratio.toFixed(1)),
      td(comma(outAt(r.day) ? outAt(r.day).lines : 0)), td(outAt(r.day) ? outAt(r.day).prs : 0))),
    h("tr", null, h("td", null, h("b", null, "All")), I.k.map(k => td(h("b", null, comma(k[1])))), td(h("b", null, comma(I.lines))), td(h("b", null, String(I.prs))),
      td(h("b", null, I.ratio == null ? "–" : I.ratio.toFixed(1))), td(h("b", null, comma(X.lines))), td(h("b", null, String(X.prs)))),
    h("tr", null, h("td", null, "Outside any Day"), X.k.map(k => td(comma(k[1]))), td(comma(X.lines)), td(X.prs), td("·"), td(""), td("")));

  // what the pointer says: the ring's lines by kind, its pull requests and its test lines for each production line
  const byKey = new Map(groups.map(g => [g.b.getAttribute("data-k"), g.r]));
  const fill = key => { const r = byKey.get(key); if (!r) return false;
    const name = key === "all" ? `The ${n(I.n_days, "Day", "Days")}` : key === "out" ? "Outside any Day" : r.day != null ? `Day ${r.day}` : `Outside any Day, at Day ${r.at}`;
    tip.replaceChildren(h("div", { class: "t" }, `${name} · ${n(r.lines, "line", "lines")} changed`), r.title ? h("div", { class: "q" }, r.title) : null,
      h("div", { class: "kt" }, r.k.map(k => [h("i", { class: `rng-sw k-${k[0]}` }), h("span", null, RNG_NAME[k[0]]), h("span", { class: "n" }, comma(k[1])), h("span", { class: "p" }, k[2])])),
      h("div", { class: "l" }, `${n(r.prs, "pull request", "pull requests")}${r.pr_kinds.length ? ` (${r.pr_kinds.map(([k, c]) => `${c} ${k}`).join(", ")})` : ""}${r.pr_list.length && r.pr_list.length <= 30 ? `: ${r.pr_list.map(p => `#${p}`).join(", ")}` : ""}.`),
      r.ratio != null ? h("div", { class: "l" }, `${r.ratio.toFixed(1)} test lines for each line of production code.`) : null);
    tip.hidden = false; return true; };
  pointerBox(fig, tip, key => key ? fill(key) : false, b => b.getAttribute("data-k"));
  // the page's Day buttons dim every ring not of that Day, or not placed at it
  onDay.push(d => groups.forEach(g => g.b.classList.toggle("mk-dim", d != null && g.r.key !== "all" && g.r.key !== "out" && (g.r.day != null ? g.r.day : g.r.at) !== d)));
  return fig;
}

/* Graph 10 as an actogram: every date on one clock, 05:00 to 05:00, a row each. Every figure is counted in Python
   (spec_drift_views.actogram); this lays the rows out and words them. A row has five lanes, top to bottom: the main
   session, the sub-agents, the pull requests open, their checks, the merges. A lane is [its offset from the row's top,
   its height]; an hour is 35 px. A row opens graph 10, folded below, at its date. */
const ACT_GEO = { w: 1232, x0: 160, x1: 1000, top: 30, rh: 58, lanes: [[6, 10], [19, 7], [29, 7], [39, 7], [49, 6]] };
const ACT_LANES = [["main session", 14.3], ["sub-agents", 25.8], ["pull request", 35.8], ["checks", 45.8], ["merge", 55.3]];
function actDraw(A, get, onDay, onDate) {
  if (!A || A.empty) return null;
  const $ = id => get("act-" + id), fig = $("fig"), tip = $("tip"), G = ACT_GEO, D = A.dates, T = A.totals;
  const el = (n, a, txt, parent) => { const e = document.createElementNS(SVG_NS, n); for (const k in a) if (a[k] != null) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; (parent || fig).appendChild(e); return e; };
  const f = v => String(Math.round(+v * 100) / 100), X = m => G.x0 + m * (G.x1 - G.x0) / 1440;
  const n = (k, one, many) => `${comma(k)} ${k === 1 ? one : many}`;
  const hm = m => `${String(Math.floor(m / 60) % 24).padStart(2, "0")}:${String(Math.floor(m % 60)).padStart(2, "0")}`, wall = m => hm((m + 300) % 1440);
  const hrs = m => `${(m / 60).toFixed(1)} h`, dur = m => { const r = Math.round(m); return r >= 60 ? `${Math.floor(r / 60)} h ${r % 60} min` : `${Math.max(r, m > 0 ? 1 : 0)} min`; };
  const pct = (a, b) => b ? Math.round(100 * a / b) : 0, sumRan = x => sum(x.ran);
  const daysOf = x => x.days.length ? daySpan(x.days) : "outside any Day", dateOf = x => [x.weekday, x.label].filter(Boolean).join(" ");
  const RUN_WORD = ["tests", "GitHub's checks", "other commands"];
  fig.replaceChildren();
  const pat = el("pattern", { id: "act-hatch", width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, null, el("defs", {}));
  el("rect", { class: "act-hatch", width: 1.4, height: 5 }, null, pat);
  fig.setAttribute("viewBox", `0 0 ${G.w} ${G.top + G.rh * D.length + 6}`);
  // the head: the clock's hours over the lanes, the columns of figures at the right
  const W = G.x1 - G.x0, MID = X(1140), HOURLY = Array.from({ length: 25 }, (_, k) => X(k * 60));
  el("text", { class: "act-t-col", x: 8, y: 23 }, "date and Day worked on");
  el("text", { class: "act-t-hr", x: 147, y: 23 }, "05:00");
  [6, 9, 12, 15, 18, 21, 0, 3].forEach(hh => el("text", { class: "act-t-hr", x: f(X((hh * 60 - 300 + 1440) % 1440)), y: 23, "text-anchor": "middle" }, hm(hh * 60)));
  el("text", { class: "act-t-hr", x: G.x1, y: 23, "text-anchor": "middle" }, "05:00");
  el("text", { class: "act-t-col", x: 1012, y: 11 }, "a session busy");
  el("text", { class: "act-t-col", x: 1096, y: 11 }, "of it waiting");
  el("text", { class: "act-t-col", x: 1228, y: 11, "text-anchor": "end" }, "merged");
  // a stretch as a closed box of a path, at least `min` wide; the small bar at the right draws every row on one scale
  const box = (a, b, y, ht, min) => { const w = Math.max(min, X(b) - X(a)); return `M${f(X(a))} ${f(y)}h${f(w)}v${f(ht)}h-${f(w)}z`; };
  const SCALE = 150 / Math.max(1, ...D.map(d => d.busy));
  const rows = D.map((d, i) => {
    const y = G.top + i * G.rh, L = G.lanes.map(([at, ht]) => [y + at, ht]), w = sumRan(d);
    const longest = d.merges.length ? d.merges.reduce((a, b) => b.wait > a.wait ? b : a) : null;
    const g = el("g", { class: "act-row b", "data-k": i, tabindex: 0, role: "button",
      "aria-label": `${dateOf(d)}, ${daysOf(d)}. A session busy for ${hrs(d.busy)}, ${hrs(w)} of it waiting on commands. ${n(d.merged, "pull request", "pull requests")} merged. Opens graph 10 at this date.` });
    el("rect", { class: "act-bg", x: 1, y: f(y + 0.5), width: G.w - 2, height: G.rh - 1 }, null, g);
    el("path", { class: "act-trk", d: L.slice(0, 4).map(([at, ht]) => `M${G.x0} ${f(at)}h${W}v${ht}h-${W}z`).join("") }, null, g);
    el("path", { class: "act-base", d: `M${G.x0} ${f(y + 55.5)}H${G.x1}` }, null, g);
    el("path", { class: "act-grid", d: HOURLY.filter(x => x !== MID).map(x => `M${f(x)} ${y + 2}v54`).join("") }, null, g);
    el("path", { class: "act-mid", d: `M${f(MID)} ${y + 1}v56` }, null, g);
    el("text", { class: "act-t-date", x: 10, y: y + 20 }, dateOf(d), g);
    el("text", { class: "act-t-day", x: 10, y: y + 34 }, daysOf(d), g);
    ACT_LANES.forEach(([name, at]) => el("text", { class: "act-t-ln", x: 154, y: f(y + at), "text-anchor": "end" }, name, g));
    // lanes 0 and 1: a session busy, fainter while it waits on a command; over lane 0, a strip while two main sessions were busy
    const busy = (list, k) => list.forEach(([a, b]) => el("rect", { class: "act-s", x: f(X(a)), y: f(L[k][0]), width: f(Math.max(0.6, X(b) - X(a))), height: L[k][1] }, null, g));
    const path = (cls, list, at, ht, min) => { if (list.length) el("path", { class: cls, d: list.map(([a, b]) => box(a, b, at, ht, min)).join("") }, null, g); };
    const waits = k => (d.wait_segs || []).filter(s => (s[3] || 0) === k);
    busy(d.segs.filter(s => s[2] === "main"), 0);
    path("act-w", waits(0), L[0][0], L[0][1], 0.6);
    path("act-two", d.two || [], y + 3, 2.2, 0.8);
    busy(d.subs || [], 1);
    path("act-w", waits(1), L[1][0], L[1][1], 0.6);
    // lanes 2 to 4: each pull request open (one opened while another is open at half height), its checks, the merges
    (d.prs || []).forEach((p, j) => el("rect", { class: `act-b b act-p${p.half ? " act-p2" : ""} act-k-${p.kind}`, "data-k": `${i}:p:${j}`, x: f(X(p.from)),
      y: f(p.half ? y + 32.5 : L[2][0]), width: f(Math.max(1, X(p.to) - X(p.from))), height: p.half ? 3.5 : L[2][1] }, null, g));
    (d.checks || []).forEach(([a, b, failed], j) => el("rect", { class: `act-b b ${failed ? "act-failed" : "act-ok"}`, "data-k": `${i}:c:${j}`, x: f(X(a)),
      y: f(L[3][0]), width: f(Math.max(1, X(b) - X(a))), height: failed ? 7 : 4 }, null, g));
    d.merges.forEach((m, j) => el("rect", { class: "act-b b act-m", "data-k": `${i}:m:${j}`, x: f(X(m.at) - 0.8), y: f(L[4][0]), width: 1.6, height: L[4][1] }, null, g));
    // after the last count of the sessions: hatched over their two lanes, a dashed mark where the count ends
    if (d.up_to < 1440) { const x = X(d.up_to), rest = f(G.x1 - x);
      el("path", { class: "act-unc", d: [0, 1].map(k => `M${f(x)} ${f(L[k][0])}h${rest}v${L[k][1]}h-${rest}z`).join("") }, null, g);
      if (d.up_to > 0) { const say = `sessions counted to ${wall(d.up_to)}`, past = x + 6 + say.length * 4.8 > G.x1;
        el("path", { class: "act-cnt", d: `M${f(x)} ${y + 2}V${y + 27}` }, null, g);
        el("text", { class: "act-t-cnt", x: f(past ? x - 6 : x + 6), y: f(y + 14.5), "text-anchor": past ? "end" : null }, say, g); }
      else el("text", { class: "act-t-cnt", x: G.x0 + 6, y: f(y + 14.5) }, "sessions not counted yet", g); }
    // at the right: the hours busy, the hours of them waiting with their share, the merges, and both hours as one small bar
    el("text", { class: "act-t-num", x: 1012, y: y + 20 }, hrs(d.busy), g);
    el("tspan", { class: "act-pct" }, ` ${pct(w, d.busy)}%`, el("text", { class: "act-t-num", x: 1096, y: y + 20 }, hrs(w), g));
    el("text", { class: "act-t-num", x: 1228, y: y + 20, "text-anchor": "end" }, String(d.merged), g);
    const mini = SCALE * d.busy, miniW = SCALE * Math.min(w, d.busy);
    el("rect", { class: "act-mini", x: 1012, y: y + 28, width: f(mini), height: 5 }, null, g);
    el("rect", { class: "act-mini-w", x: f(1012 + mini - miniW), y: y + 28, width: f(miniW), height: 5 }, null, g);
    return { g, d, longest };
  });
  // a line between two rows, on the figure and not in a row
  D.forEach((d, i) => { if (i) el("path", { class: "act-sep", d: `M0 ${G.top + i * G.rh}H${G.w}` }); });
  fig.setAttribute("aria-label", `An actogram: one row for each of ${n(D.length, "date", "dates")}, on one clock from 05:00 to 05:00 (${A.zone}). In each row five lanes: the main session busy, sub-agents busy, pull requests open, their checks running, and the merges. At the right of each row, its hours with a session busy, the hours of that waiting on commands, and the pull requests merged.`);

  // the line of figures
  const fig4 = (num, small, what, sub) => h("div", null, h("div", { class: "act-num" }, num, small ? h("small", null, small) : null), h("div", { class: "act-what" }, what), h("div", { class: "act-sub" }, sub));
  const R = T.ran, ranAll = sum(R);
  // "on all 11 dates counted whole" when every date counted whole had one, "on 9 of the 11 dates counted whole" when not
  const wholeSay = T.after_midnight === T.whole ? `${T.whole === 1 ? "the one date" : `all ${T.whole} dates`} counted whole`
    : `${T.after_midnight} of the ${T.whole === 1 ? "one date" : `${T.whole} dates`} counted whole`;
  $("figs").replaceChildren(
    fig4(String(T.dates), null, `${T.dates === 1 ? "date" : "dates"} with a session`, T.first ? `${shortDate(T.first)} to ${shortDate(T.last)}; on ${wholeSay}, a session was still busy after midnight` : "none counted yet"),
    fig4((T.busy / 60).toFixed(1), "h", "with a session busy", `two sessions at once counted once; the main session alone ${hrs(T.main)}`),
    fig4(T.waiting_share == null ? "–" : String(Math.round(100 * T.waiting_share)), T.waiting_share == null ? null : "%", "of it waiting on commands",
      `${hrs(ranAll)}: tests ${dur(R[0])}, other commands ${dur(R[2])}, GitHub's checks ${dur(R[1])}`),
    fig4(T.median == null ? "–" : String(Math.round(T.median)), T.median == null ? null : "min", "median wait, opened to merged",
      T.merged ? `${n(T.merged, "pull request", "pull requests")}; ${T.over_hour} waited over an hour, the longest ${dur(T.longest.wait)} (#${T.longest.pr})` : "no pull request merged yet"));

  // what the picture shows (picked from the figures), and where the model bends
  const li = (list, b, t) => list.appendChild(h("li", null, h("b", null, b), t));
  const finds = $("finds"), bends = $("bends"); finds.replaceChildren(); bends.replaceChildren();
  const worked = D.filter(d => d.busy > 0), top = worked.length ? worked.reduce((a, b) => b.busy > a.busy ? b : a) : null;
  if (top) li(finds, `The busiest date was ${top.label}.`, ` ${hrs(top.busy)} with a session busy, ${pct(sumRan(top), top.busy)}% of it waiting on commands; ${n(top.merged, "pull request", "pull requests")} merged.`);
  if (ranAll >= 1) { const k = R.indexOf(Math.max(...R));
    li(finds, `${pct(ranAll, T.busy)}% of the busy time was a wait on a command.`, ` Most of it on ${RUN_WORD[k]}: ${hrs(R[k])} of ${hrs(ranAll)}.`); }
  if (T.merged) li(finds, `Half the pull requests merged within ${dur(T.median)} of opening.`, ` ${T.over_hour} of the ${T.merged} waited over an hour; the longest, #${T.longest.pr}, ${dur(T.longest.wait)}.`);
  if (T.whole && T.after_midnight) li(finds, "Work runs past midnight.", ` On ${wholeSay}, a session was still busy after 00:00.`);
  if (T.two >= 1) { const most = D.reduce((a, b) => (b.two_min || 0) > (a.two_min || 0) ? b : a);
    li(finds, `Two main sessions were busy at once for ${dur(T.two)}.`, ` The strip over the main session's lane marks it; the most on ${dateOf(most)}, ${dur(most.two_min)}.`); }
  [["A gap is not a rest.", " Only this repository's sessions are drawn; the maintainer's reading and typing leave no mark."],
    ["Two waits at once count twice.", " The waiting share is every session's waits, sub-agents' included, over the busy time counted once: two sessions waiting at the same time count twice, as graph 10 counts them."],
    R[1] >= 1 ? ["One wait is drawn twice.", ` A session waiting on GitHub's checks is fainter in its own lane (${dur(R[1])} in all), and the same minutes are a bar in the checks lane.`] : null,
    ["A date runs 05:00 to 05:00.", " Work after midnight stays on the evening it belongs to, so a row is a working day, not a calendar one."],
    ["Times are on the clock of the machine that recorded the sessions.", ` ${A.zone}; GitHub's times are moved to it.`]].filter(Boolean).forEach(([b, t]) => li(bends, b, t));

  // the exact numbers
  const td = v => h("td", { class: "r" }, v);
  $("table").replaceChildren(h("tr", null, ["Date", "Days", "A session busy", "Main session", "Sub-agents", "Two main at once", "Waiting on commands", "Share", "Pull requests open", "Checks running",
    "Merged", "Median wait"].map(x => h("th", null, x))),
    ...D.map(d => h("tr", null, h("td", null, dateOf(d)), h("td", null, daysOf(d)), td(hrs(d.busy)), td(hrs(d.main)), td(hrs(d.sub || 0)), td(dur(d.two_min || 0)), td(dur(sumRan(d))),
      td(`${pct(sumRan(d), d.busy)}%`), td(String(d.open || 0)), td(dur(d.checks_min || 0)), td(String(d.merged)), td(d.median == null ? "–" : dur(d.median)))));

  // what the pointer says: a pull request, a check or a merge says its own; anywhere else in a row, the date's figures
  const early = x => x.cut ? "; it opened on an earlier date" : "";
  const said = { p: (d, p) => [`Pull request #${p.pr} · ${KINDS[p.kind] || p.kind}`,
      p.state === "merged" ? `Open ${wall(p.from)} to ${wall(p.to)}, ${dur(p.wait)} before it merged${early(p)}.`
        : p.state === "closed" ? `Open ${wall(p.from)} to ${wall(p.to)}, ${dur(p.wait)} before it was closed without merging${early(p)}.`
          : `Open from ${wall(p.from)}: still open, not merged or closed yet${early(p)}.`,
      p.half ? "Drawn at half height: it opened while another pull request was open." : null],
    c: (d, c) => [`Checks on pull request #${c[3]}`, `${wall(c[0])} to ${wall(c[1])}: ${c[2] ? "a run failed" : "passed"}.`],
    m: (d, m) => [`Merged #${m.pr} at ${wall(m.at)}`, `${dur(m.wait)} after it opened${early(m)}.`] };
  const dateSaid = r => { const d = r.d, w = sumRan(d);
    return [`${dateOf(d)} · ${daysOf(d)}`,
      `Busy ${hrs(d.busy)}, two sessions at once counted once; the main session alone ${hrs(d.main)}.`,
      `Sub-agents busy ${dur(d.sub || 0)}; two main sessions at once ${dur(d.two_min || 0)}.`,
      `Waiting on commands ${dur(w)}, ${pct(w, d.busy)}%: tests ${dur(d.ran[0])}, GitHub's checks ${dur(d.ran[1])}, other commands ${dur(d.ran[2])}.`,
      `${n(d.open || 0, "pull request", "pull requests")} open; checks running ${dur(d.checks_min || 0)}.`,
      `${n(d.merged, "pull request", "pull requests")} merged${d.median != null ? `, median wait ${dur(d.median)}` : ""}.`,
      r.longest ? `The longest wait: #${r.longest.pr}, ${dur(r.longest.wait)}${r.longest.cut ? ", opened on an earlier date" : ""}.` : null,
      d.up_to < 1440 ? `Counted up to ${wall(d.up_to)}.` : null]; };
  const fill = key => { const [at, kind, j] = String(key).split(":"), r = rows[+at]; if (!r) return false;
    const mark = kind ? ({ p: r.d.prs, c: r.d.checks, m: r.d.merges }[kind] || [])[+j] : null;
    if (kind && !mark) return false;
    // a line left out is not handed over: a browser writes a null as the word
    tip.replaceChildren(...(mark ? said[kind](r.d, mark) : dateSaid(r)).filter(Boolean).map((t, k) => h("div", { class: k ? "l" : "t" }, t)));
    tip.hidden = false; return true; };
  pointerBox(fig, tip, key => key != null ? fill(key) : false, b => b.getAttribute("data-k"));
  // a row opens graph 10, folded below, at its date; a click on a mark opens its row's
  const open = g => { const r = rows[+g.getAttribute("data-k")]; if (!r) return; (onDate || []).forEach(fn => fn(r.d.date)); openFolds(get("g10")); };
  const rowOf = e => e.target && e.target.closest ? e.target.closest(".act-row") : null;
  fig.addEventListener("click", e => { const g = rowOf(e); if (g) open(g); });
  fig.addEventListener("keydown", e => { const g = rowOf(e); if (g && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); open(g); } });
  // the page's Day buttons dim every date not of that Day
  onDay.push(day => rows.forEach(r => r.g.classList.toggle("mk-dim", day != null && !r.d.days.includes(day))));
  return fig;
}

/* Graph 11 as reflex arcs: a row for each step the driver started, read left to right from the step through its
   sessions to its pull request; a step that parked climbs to the band of the person. Every figure and sentence is
   made in Python (spec_drift_views.reflex); this lays the rows out as the mockup at #228 does. The Days are the
   driven project's, so the page's Day buttons are not wired here. */
const RFX_GEO = { top: 64, pitch: 32, stim: 252, first: 330, last: 811, gap: 150, pill: 861, go: 922, fin: 946, band: 28, under: 41 };
function rfxDraw(R, get) {
  const $ = id => get("rfx-" + id), fig = $("fig"), tip = $("tip"), G = RFX_GEO, rows = R.rows || [];
  const el = (n, a, txt, parent) => svgEl(fig, n, a, txt, parent);
  const most = Math.max(1, ...rows.map(r => r.sessions.length));
  // distance along a row is order, not time: the first session at 330, the next ones 150 apart or closer
  const step = most > 1 ? Math.min(G.gap, (G.last - G.first) / (most - 1)) : 0, xOf = j => G.first + j * step;
  const yOf = i => G.top + i * G.pitch, bottom = yOf(Math.max(0, rows.length - 1));
  fig.replaceChildren();
  fig.setAttribute("viewBox", `0 0 1198 ${bottom + 19}`);
  fig.setAttribute("aria-label", R.aria);
  el("rect", { class: "x-band", x: 240, y: 16, width: 716, height: 24, rx: 5 });
  [["t-who", 0, 32, "The person", "THE BRAIN"], ["t-hd", 0, 9, "The step the driver started", "STIMULUS"], ["t-hd", 325, 9, "Its sessions, in order", "THE NERVE"],
    ["t-hd", 861, 9, "Its pull request, and how it ended", "THE RESPONSE"]].forEach(([c, x, y, t, bio]) => el("tspan", { class: "t-bio", dx: 5 }, bio, el("text", { class: c, x, y }, t)));
  el("path", { class: "x-guide", d: `M${G.go} 40V${bottom}` });
  // the climb: up from the session it parked at (or the step, with none yet) to the band, and down at the one it came back at
  const climb = (r, y, p) => {
    const x = p.up == null ? G.stim : xOf(p.up), e = p.up == null ? G.stim + 32 : x + 14;
    const up = `M${x} ${y}Q${e} ${y} ${e} ${y - 9}V`;
    if (p.back == null) return { e, d: up + G.band, halo: [up + G.under] };
    const x2 = xOf(p.back), down = `V${y - 9} Q${x2 - 14} ${y} ${x2} ${y}`;
    return { e, d: `${up}${G.band}H${x2 - 14}${down}`, halo: [up + G.under, `M${x2 - 14} ${G.under}${down}`] };
  };
  rows.forEach((r, i) => {
    const y = yOf(i), n = r.sessions.length, skip = j => r.parks.some(p => p.back != null && (p.up == null ? -1 : p.up) <= j && p.back > j);
    el("path", { class: "x-track", d: `M${G.stim} ${y}H${G.fin}` });
    if (n) {
      el("path", { class: "x-nerve" + (skip(-1) ? " skip" : ""), d: `M${G.stim} ${y}H${G.first}` });
      for (let j = 0; j + 1 < n; j++) el("path", { class: "x-nerve" + (skip(j) ? " skip" : ""), d: `M${xOf(j)} ${y}H${xOf(j + 1)}` });
      if (r.pr) el("path", { class: "x-nerve", d: `M${xOf(n - 1)} ${y}H${G.pill}` });
    }
    if (r.pr) el("path", { class: "x-nerve" + (r.pr.state === "open" ? " await" : ""), d: `M${G.pill + 38} ${y}H${G.fin - 6}` });
  });
  rows.forEach((r, i) => r.parks.forEach(p => climb(r, yOf(i), p).halo.forEach(d => el("path", { class: "x-halo", d }))));
  // the trial for level 2: a box for each pull request in a row with no change asked
  const L2 = R.level_2;
  if (L2 && L2.of) {
    const g = el("g", { class: "b", tabindex: 0, "data-k": "l2", "aria-label": R.tips.l2.a }), w = Math.min(14, 210 / L2.of);
    el("rect", { class: "hit", x: 964, y: 14, width: 234, height: 28, rx: 3 }, null, g);
    for (let k = 0; k < L2.of; k++) el("rect", { class: "x-l2" + (k < L2.run ? " run" : ""), x: 968.5 + k * w, y: 18, width: w - 3, height: 7, rx: 1.5 }, null, g);
    el("text", { class: "t-l2", x: 968, y: 37 }, R.tips.l2.t, g);
  }
  const mark = (k, parent) => el("g", { class: "b", tabindex: 0, "data-k": k, "aria-label": (R.tips[k] || {}).a || "" }, null, parent);
  rows.forEach((r, i) => {
    const y = yOf(i), s = mark(`s${i}`);
    el("rect", { class: "hit", x: -2, y: y - 15, width: 262, height: 30, rx: 3 }, null, s);
    el("text", { class: "t-lab", x: 0, y: y - 1.5 }, r.label, s);
    el("text", { class: "t-sub", x: 0, y: y + 10 }, r.sub, s);
    el("path", { class: "x-stim", d: `M248 ${y - 5}l9 5-9 5z` }, null, s);
    r.sessions.forEach((x, j) => {
      const g = mark(`s${i}x${j}`), cx = xOf(j);
      el("rect", { class: "hit", x: cx - 10, y: y - 10, width: 20, height: 20, rx: 3 }, null, g);
      if (x.crashed) { el("circle", { class: "x-crash", cx, cy: y, r: 5.2 }, null, g); el("path", { class: "x-crashx", d: `M${cx - 2.5} ${y - 2.5}l5 5m0 -5l-5 5` }, null, g); }
      else if (x.fixes) { el("circle", { class: "x-fix", cx, cy: y, r: 7 }, null, g); el("text", { class: "x-fixn", x: cx, y: y + 3.2 }, String(x.fixes), g); }
      else el("circle", { class: "x-ses", cx, cy: y, r: 4.5 }, null, g);
    });
    r.parks.forEach((p, j) => {
      const g = mark(`s${i}p${j}`), c = climb(r, y, p), by = p.by === "fault" ? "fault" : "maint";
      el("path", { class: "hitl", d: c.d }, null, g);
      el("path", { class: `x-br ${by}`, d: c.d }, null, g);
      if (by === "fault") el("rect", { class: "x-term fault", x: c.e - 3.5, y: G.band - 3.5, width: 7, height: 7, rx: 1 }, null, g);
      else el("circle", { class: "x-term maint", cx: c.e, cy: G.band, r: 3.6 }, null, g);
    });
    if (!r.pr) el("text", { class: "t-none", x: 880, y: y + 3.3 }, "no pull request");
    const g = mark(`s${i}r`);
    if (r.pr) {
      const wait = r.pr.state === "open" ? " await" : "";
      el("rect", { class: "hit", x: 858, y: y - 11, width: 96, height: 22, rx: 3 }, null, g);
      el("rect", { class: "x-pill" + wait, x: G.pill, y: y - 8, width: 38, height: 16, rx: 8 }, null, g);
      el("text", { class: "x-pilln", x: 880, y: y + 3.4 }, `#${r.pr.number}`, g);
      el("path", { class: "x-go" + wait, d: `M${G.go} ${y - 5}l5 5-5 5-5-5z` }, null, g);
    } else el("rect", { class: "hit", x: 936, y: y - 11, width: 20, height: 22, rx: 3 }, null, g);
    if (r.fin === "fault") el("rect", { class: "x-fin fault", x: G.fin - 4.5, y: y - 4.5, width: 9, height: 9, rx: 1.5 }, null, g);
    else el("circle", { class: `x-fin ${r.fin}`, cx: G.fin, cy: y, r: r.fin === "still" ? 4.2 : 5 }, null, g);
    el("text", { class: "t-end", x: 968, y: y - 1.5 }, r.end);
    el("text", { class: "t-sub", x: 968, y: y + 10 }, r.end_sub);
  });
  el("text", { class: "t-go", x: 912, y: 31 }, "the go-ahead to merge, at every pull request");
  // the figures, the folded lists and the pointer box: their words are Python's
  $("figs").replaceChildren(...R.figs.map(f => h("div", null, h("span", { class: "num" }, f.num, f.small ? h("small", null, f.small) : null),
    h("span", { class: "txt" }, h("b", { class: "what" }, f.what), h("span", { class: "sub" }, f.sub)))));
  $("hint").textContent = R.hint;
  $("stamp").textContent = R.stamp.charAt(0).toUpperCase() + R.stamp.slice(1);
  $("finds").replaceChildren(...R.finds.map(([c, b, t]) => h("li", { class: c || null }, h("b", null, b), " ", t)));
  $("bends").replaceChildren(...R.bends.map(([b, t]) => h("li", null, h("b", null, b), " ", t)));
  pointerBox(fig, tip, key => key != null && R.tips[key] ? tipFill(tip, R.tips[key]) : false, b => b.getAttribute("data-k"));
  return fig;
}

/* A link to a graph folded under its new drawing (#g1, #g2, #g6, #g7, #g10) opens every fold around it, and
   scrolls to it. A link to a graph that has left the page (#g3, #g4, #g5, #g8, #g9) lands on the empty anchor in the
   section drawn in its place, which is in no fold. */
function openFolds(target) {
  for (let e = target; e; e = e.parentElement || e.parentNode) if (e.tagName && String(e.tagName).toUpperCase() === "DETAILS") e.open = true;
  if (target && target.scrollIntoView) target.scrollIntoView({ block: "start" });
}
function foldLinks() {
  const go = () => { const id = decodeURIComponent((location.hash || "").slice(1)); if (id) openFolds(document.getElementById(id)); };
  if (typeof addEventListener === "function") addEventListener("hashchange", go);
  go();
}

function draw(M, DATA) {
  const $ = id => document.getElementById(id);
  const put = (id, ...kids) => { const box = $(id); box.replaceChildren(...kids.flat(Infinity).filter(c => c != null && c !== false)); return box; };
  const marks = [], resets = [];
  const forDays = (node, ds) => { node.dataset.days = ds.join(" "); marks.push(node); return node; };

  // The readout under a graph: what the graph says as a whole, until a mark is pointed at, tapped or tabbed to.
  function reader(g, first) {
    let on = null, base = first;
    const say = r => put(`${g}-read`, h("strong", null, r.t), r.b.map(line => h("span", null, rich(line))));
    const clear = () => { if (on) on.classList.remove("on"); on = null; };
    resets.push(() => { clear(); say(base); });
    say(first);
    const mark = (node, r) => {
      node.setAttribute("aria-label", r.t);
      const pick = () => { if (on === node) return; clear(); on = node; node.classList.add("on"); say(r); };
      ["mouseenter", "focus", "click"].forEach(ev => node.addEventListener(ev, pick));
      return node;
    };
    mark.base = r => { base = r; clear(); say(r); };  // a graph that redraws (graph 10, per date) says its new whole
    return mark;
  }
  const key = (id, items) => put(id, items.map(([cls, text, glyph]) => h("span", null, cls && h("i", { class: cls }, glyph || ""), text)));
  function table(id, T) {
    const cell = v => h("td", { class: typeof v === "number" ? "r" : null }, typeof v === "number" ? comma(v) : String(v));
    put(id, h("thead", null, h("tr", null, T.head.map(x => h("th", null, x)))), h("tbody", null, T.rows.map(r => h("tr", null, r.map(cell)))));
  }
  function graph(g, fn) {
    const m = M[g], failed = e => { put(`${g}-plot`, h("p", { class: "load-error" }, `This graph could not be drawn: ${e}`)); console.error(`${g}: ${e}`); };
    if (m.error) return failed(m.error);
    try { fn(m, reader(g, m.read)); table(`${g}-table`, m.table); } catch (e) { failed(String((e && e.message) || e)); }
  }
  const px = n => `${n.toFixed(1)}px`;

  /* the header */
  const H = M.head;
  $("eyebrow").textContent = [H.project, H.when && `read from git and GitHub on ${H.when}`, H.commit && `commit ${H.commit}`].filter(Boolean).join(" · ");
  const banner = $("demo-banner");
  banner.textContent = "Example data: this project has no day specs yet. The page will show real data after the first day spec merges.";
  banner.hidden = !H.demo;
  const missing = $("data-banner");
  missing.textContent = H.missing || "";
  missing.hidden = !H.missing;
  put("now", h("strong", null, "Now: "), H.now, " ", h("strong", null, "Next step: "), rich(H.next));
  if (H.took) $("words-took").textContent = H.took;
  const A = M.attention;
  const items = groups => groups.map(g => h("li", null, h("b", null, `${g.label} (${g.ids.length})`), " ", g.detail ? [rich(g.detail), ": "] : null, g.ids.join(", ")));
  $("attention").hidden = !A.total && !A.expected;
  put("attention-n", `Needs attention: ${plural(A.total, "item", "items")}` + (A.expected ? ` · ${A.expected} expected` : ""));
  put("attention-list", items(A.groups));
  $("attention-known").hidden = !A.expected;
  put("attention-known-n", `Expected, not counted: ${plural(A.expected, "item", "items")}`);
  put("attention-known-list", items(A.known));

  /* the quality score: the finished Days', or the chosen Day's */
  const Q = M.quality && !M.quality.error ? M.quality : null;
  const bar = n => h("span", { class: "q-bar" }, h("i", { style: `width:${n}%` }));
  const showScore = day => {
    $("quality").hidden = !Q;
    if (!Q) return;
    const v = day == null ? Q.all : Q.days[day];
    put("q-n", v ? String(v.n) : "–");
    put("q-of", v ? `quality of ${v.label}, out of 100` : `Day ${day} has no score: it is not finished`);
    put("q-rows", v ? v.parts.map(p => h("a", { class: "q-row", href: `#${p.graph}` }, h("span", { class: "q-name" }, p.name, p.low && h("span", { class: "q-low" }, "lowest")),
      bar(p.n), h("b", null, String(p.n)), h("span", { class: "q-where" }, `graph ${p.graph.slice(1)}`))) : []);
    table("q-table", { head: ["Part", "What is counted", "Count", "Share"], rows: v ? v.rows : [] });
  };
  showScore(null);
  const dq = v => v && h("b", { class: "dq" }, String(v.n));

  /* the day buttons: one day lit in every graph */
  let lit = null;
  const onDay = [showScore];  // what else happens when a day is picked: the score turns to it, graph 10 to its last date
  const relight = () => marks.forEach(node => node.classList.toggle("dim", lit !== null && !node.dataset.days.split(" ").includes(String(lit))));
  const chips = [null, ...M.days.map(d => d.day)].map(day => h("button", { type: "button", "aria-pressed": day === null ? "true" : "false" }, day === null ? ["All Days", Q && dq(Q.all)] : [`Day ${day}`, Q && dq(Q.days[day])]));
  chips.forEach((chip, i) => chip.addEventListener("click", () => {
    lit = i ? M.days[i - 1].day : null;
    chips.forEach((c, j) => c.setAttribute("aria-pressed", j === i ? "true" : "false"));
    relight();
    onDay.forEach(f => f(lit));
  }));
  put("days", h("span", null, "Highlight one Day in every graph:"), chips);

  /* Where we are, as a ring: a Day on it presses its button, a second press lets it go. The ring's middle says the next
     step, so the plain Now line hides while the ring is drawn, and is all the page says of where the work is without it. */
  {
    const w = M.whr, failed = e => { put("whr-scroll", h("p", { class: "load-error" }, `This graph could not be drawn: ${e}`)); console.error(`whr: ${e}`); };
    const press = day => { const i = M.days.findIndex(d => d.day === day); chips[i >= 0 && lit !== day ? i + 1 : 0].click(); };
    $("whr").hidden = !!w.empty;
    $("now").hidden = false;
    if (w.error) failed(w.error);
    else if (!w.empty) try { ringDraw(w, $, onDay, press); $("now").hidden = true; } catch (e) { failed(String((e && e.message) || e)); }
  }

  /* Graph 1 read as a gene, in graph 1's place; graph 1 is folded under it, its level cards drawn in it */
  {
    const r = M.rdg, failed = e => { put("rdg-scroll", h("p", { class: "load-error" }, `This graph could not be drawn: ${e}`)); console.error(`rdg: ${e}`); };
    if (r.error) failed(r.error);
    else if (r.empty) put("rdg-scroll", h("p", { class: "load-error" }, "Not measured yet: ", rich(r.empty)));
    else try { readingDraw(r, $, onDay); } catch (e) { failed(String((e && e.message) || e)); }
  }

  /* Graph 2 as a gel, graphs 3 to 5 as proteins, graph 7 as proofreading, graph 8 as an energy budget, graph 9 as
     growth rings and graph 10 as an actogram, in their places; graphs 2, 7 and 10 are folded under theirs */
  // graph 10 turns to a date the actogram's row names, once both are drawn
  const onDate = [];
  [["gel", gelDraw], ["prt", protDraw], ["prf", prfDraw], ["atp", atpDraw], ["rng", rngDraw], ["act", actDraw]].forEach(([k, fn]) => {
    const g = M[k], failed = e => { put(`${k}-scroll`, h("p", { class: "load-error" }, `This graph could not be drawn: ${e}`)); console.error(`${k}: ${e}`); };
    if (g.error) failed(g.error);
    else if (g.empty) put(`${k}-scroll`, h("p", { class: "load-error" }, "Not measured yet: ", rich(g.empty)));
    else try { fn(g, $, onDay, onDate); } catch (e) { failed(String((e && e.message) || e)); }
  });
  // graph 11 as reflex arcs: its Days are the driven project's, so it takes no Day button
  [["rfx", rfxDraw]].forEach(([k, fn]) => {
    const g = M[k], failed = e => { put(`${k}-scroll`, h("p", { class: "load-error" }, `This graph could not be drawn: ${e}`)); console.error(`${k}: ${e}`); };
    if (g.error) failed(g.error);
    else if (g.empty) put(`${k}-scroll`, h("p", { class: "load-error" }, "Not measured yet: ", rich(g.empty)));
    else try { fn(g, $); } catch (e) { failed(String((e && e.message) || e)); }
  });

  /* Graph 1 */
  graph("g1", (m, mark) => {
    const TOP = 200, ALL = 280, NS = "http://www.w3.org/2000/svg", n = m.merges.length, cols = Math.max(1, n + m.ahead.length);
    const Y = v => (v * TOP).toFixed(1);
    // A stepped line: each column's value runs across the column's own width, and a short step joins it to the next.
    const steps = ys => ys.map((y, i) => `${i ? "L" : "M"}${i},${Y(y)} L${i + 1},${Y(y)}`).join(" ");
    const yw = m.merges.map(x => x.yw), yb = m.merges.map(x => x.yb);
    let gapD = "", writtenD = "", builtD = "", projD = "";
    if (n) {
      // The gap is the band between the written steps and the built steps, so the built steps run back under them.
      gapD = steps(yw);
      for (let i = n - 1; i >= 0; i--) gapD += ` L${i + 1},${Y(yb[i])} L${i},${Y(yb[i])}`;
      gapD += " Z";
      // Written stays flat over the columns still to come, since no promise is added to it until a spec merges.
      writtenD = steps([...yw, ...m.ahead.map(() => yw[n - 1])]);
      builtD = steps(yb);
      projD = [`M${n - 0.5},${Y(yb[n - 1])}`, ...m.ahead.map((a, j) => `L${n + j + 0.5},${Y(a.yb)}`)].join(" ");
    }
    const path = (cls, d) => { const p = document.createElementNS(NS, "path"); p.setAttribute("class", cls); p.setAttribute("d", d); return p; };
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${cols} ${TOP}`); svg.setAttribute("preserveAspectRatio", "none"); svg.setAttribute("aria-hidden", "true");
    svg.append(path("gap", gapD), path("written", writtenD), path("built", builtD), path("proj", projD));
    const axis = h("div", { class: "g1-axis" }, h("span", { style: "top:0" }, "Day"), m.ticks.map(t => h("span", { style: `top:${px(22 + t.y * TOP - 7)}` }, t.label)),
      m.barTicks.map(t => h("span", { style: `top:${px(22 + ALL - t.h * 60 - 7)}` }, t.label)));
    const bands = h("div", { class: "g1-bands" }, m.bands.map((b, i) => forDays(h("div", { class: i % 2 ? "odd" : "", style: `flex-grow:${b.n}` }, b.day ? String(b.day) : "–"), b.day ? [b.day] : [])));
    const colsEl = h("div", { class: "g1-cols" },
      m.merges.map(x => forDays(mark(h("button", { type: "button", class: "g1-col" },
        h("span", { class: `pt ${x.kind}`, style: `top:${px(x.yb * TOP)}` }), x.open > 0 && h("span", { class: "open-bar", style: `height:${px(x.h * 60)}` })), x), x.day ? [x.day] : [])),
      m.ahead.map(a => forDays(mark(h("button", { type: "button", class: "g1-col ahead" }, h("span", { class: "pt todo", style: `top:${px(a.yb * TOP)}` }),
        h("span", { class: "g1-under" }, a.close ? "✓" : a.label)), a), [a.day])));
    const lines = [...m.ticks.map(t => t.y * TOP), TOP, ...m.barTicks.map(t => ALL - t.h * 60), ALL].map((y, i, a) => h("div", { class: `g1-line${y === TOP || i === a.length - 1 ? " strong" : ""}`, style: `top:${px(y)}` }));
    // Near the right edge the label goes left of the dashed line, where it has room (#213, B13).
    const today = h("div", { class: `g1-today${n / cols > 0.85 ? " end" : ""}`, style: `left:${(100 * n / cols).toFixed(2)}%` }, h("span", null, "today"));
    const area = h("div", { class: "g1-area" }, lines, svg, colsEl, today);
    const after = h("div", { class: "g1-after" },
      m.unknown.map(u => forDays(mark(h("button", { type: "button", class: "g1-unknown" }, h("strong", null, `Day ${u.day}`), h("span", null, "no spec yet"),
        h("span", null, "size unknown"), u.waits > 0 && h("span", { class: "g1-waits" }, `${u.waits} wait here`)), u), [u.day])),
      m.stop != null && h("div", { class: "g1-stop" }, h("span", null, "stop")),
      m.stop != null && h("div", { class: "g1-later" }, "After the stop: not specified until the maintainer lifts it"));
    put("g1-plot", h("div", { class: "g1", style: `min-width:${Math.max(820, (n + m.ahead.length) * 9 + m.unknown.length * 110 + 120)}px` }, axis,
      h("div", { class: "g1-main" }, h("div", { class: "g1-lane" }, bands, area), after)));
    $("g1-say").textContent = m.say;
    key("g1-key", m.key);
    // One card per level: who starts and who merges at it. The levels below the one marked "now" are passed;
    // a level with a count (Level 2) draws how far its run has got, as a bar.
    const at = m.ladder.findIndex(r => r.cls === "now");
    put("g1-ladder", m.ladder.map((r, i) => h("div", { class: `level ${r.cls}${i < at ? " done" : ""}` },
      h("span", { class: "lv" }, r.lv + (r.cls === "now" ? " · now" : "")), h("b", null, r.name),
      h("span", { class: "who" }, (r.who || []).map(([by, does]) => [h("i", { class: by }, by), ` ${does} `])),
      r.need && h("p", null, r.need),
      typeof r.of === "number" && h("span", { class: "track", role: "img", "aria-label": `${r.run} of ${r.of}` }, h("i", { style: `width:${Math.max(2, 100 * r.run / Math.max(1, r.of)).toFixed(1)}%` })),
      h("small", null, r.state))));
  });

  /* Graph 6 */
  graph("g6", (m, mark) => {
    const TOP = 200, ALL = 280, n = Math.max(1, m.merges.length);
    $("g6-say").textContent = m.say;
    key("g6-key", m.key.map(([k, text]) => [`pt ${k}`, text]));
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path"), svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    path.setAttribute("d", m.merges.filter(x => x.y != null).map((x, i) => `${i ? "L" : "M"}${(m.merges.indexOf(x) + 0.5).toFixed(1)},${(x.y * TOP).toFixed(1)}`).join(" "));
    svg.setAttribute("viewBox", `0 0 ${n} ${TOP}`); svg.setAttribute("preserveAspectRatio", "none"); svg.setAttribute("aria-hidden", "true"); svg.append(path);
    const axis = h("div", { class: "g6-axis" }, h("span", { style: "top:0" }, "Day"), m.ticks.map(t => h("span", { style: `top:${px(22 + t.y * TOP - 7)}` }, t.label)),
      m.barTicks.map(t => h("span", { style: `top:${px(22 + ALL - t.h * 60 - 7)}` }, t.label)));
    const bands = h("div", { class: "g6-bands" }, m.bands.map((b, i) => forDays(h("div", { class: i % 2 ? "odd" : "", style: `flex-grow:${b.n}` }, b.day ? String(b.day) : "–"), b.day ? [b.day] : [])));
    const cols = h("div", { class: "g6-cols" }, m.merges.map(x => forDays(mark(h("button", { type: "button", class: "g6-col" },
      x.y != null && h("span", { class: `pt ${x.kind}`, style: `top:${px(x.y * TOP)}` }), x.failed && h("span", { class: "pt failed" }),
      h("span", { class: "open-bar", style: `height:${px(x.h * 60)}` })), x), x.day ? [x.day] : [])));
    const lines = [...m.ticks.map(t => t.y * TOP), TOP, ...m.barTicks.slice(1).map(t => ALL - t.h * 60), ALL].map((y, i, a) => h("div", { class: `g6-line${y === TOP || i === a.length - 1 ? " strong" : ""}`, style: `top:${px(y)}` }));
    put("g6-plot", h("div", { class: "g6", style: `min-width:${Math.max(820, n * 9)}px` }, axis, h("div", { class: "g6-main" }, bands, h("div", { class: "g6-area" }, lines, svg, cols))));
  });

  /* Graph 7 */
  graph("g7", (m, mark) => {
    $("g7-say").textContent = m.say;
    key("g7-key", [["", "Cause:"], ...m.key.map(k => [k.cls, k.text]), ["", "Grey: how often a gate stopped something, all dates"]]);
    const P = m.pipe, dot = o => forDays(mark(h("button", { type: "button", class: `dot ${o.cause}${o.escaped ? " square" : ""}${o.back ? " ring" : ""}` }), o), [o.day]);
    // The valves: a full one for a gate that stops work, a small one for a check counted under PR checks, a pale one for the kit's.
    const valve = kind => {
      const s = document.createElementNS(SVG_NS, "svg"), big = kind === "valve", r = big ? 15 : 10;
      s.setAttribute("width", 2 * r); s.setAttribute("height", 2 * r); s.setAttribute("viewBox", `0 0 ${2 * r} ${2 * r}`); s.setAttribute("aria-hidden", "true");
      s.setAttribute("class", `valve ${kind}`);
      if (kind === "leak") { svgEl(s, "path", { class: "zig", d: "M26 6 l-6 4 l6 4 l-6 4 l6 4 l-6 4" }); s.setAttribute("width", 30); s.setAttribute("height", 30); s.setAttribute("viewBox", "0 0 30 30"); return s; }
      svgEl(s, "circle", { class: "body", cx: r, cy: r, r: r - 1 });
      svgEl(s, "circle", { class: "wheel", cx: r, cy: r, r: big ? 9 : 5.5 });
      if (big) { svgEl(s, "path", { class: "wheel", d: "M15 15 L24 15 M15 15 L10.5 22.8 M15 15 L10.5 7.2" }); svgEl(s, "circle", { class: "hub", cx: 15, cy: 15, r: 2.6 }); }
      return s;
    };
    const gate = g => h("div", { class: `pipe-row gate ${g.kind}` },
      h("div", { class: "pipe-name" }, g.names.map((nm, i) => h("div", { class: "one" }, mark(h("button", { type: "button" }, nm), g), g.subs[i] && h("span", { class: "sub" }, g.subs[i])))),
      h("div", { class: `pipe${g.names.length > 1 ? " two" : ""}` }, g.names.map(() => valve(g.kind))),
      h("div", { class: "pipe-side" }, g.stop && h("span", { class: "stop" }, g.stop), g.plain && h("span", { class: "nc" }, g.plain),
        g.dots && h("span", { class: "caught" }, g.caught), g.by && h("span", { class: "wsplit" }, g.by),
        g.dots && g.dots.length > 0 && h("div", { class: "tray" }, g.dots.map(dot))));
    const stage = (st, cls) => h("div", { class: `pipe-stage${cls ? ` ${cls}` : ""}` },
      h("div", { class: "pipe-row stage-head" }, h("div", { class: "t" }, st.n ? `${st.n} · ${st.name}` : st.name), h("div", { class: "pipe" }), h("div", { class: "n" }, st.note)),
      st.gates.map(gate));
    // The stages in their order by name: a looped one inside the track loop; before CI, the note that every pull request comes to it.
    const staged = P.stages.map(st => st.loop ? h("div", { class: "pipe-loop" }, h("span", { class: "loop-label" }, "once per track PR"), stage(st))
      : st.name === "CI on every pull request" ? [h("p", { class: "pipe-feed" }, "Every pull request comes through here: the spec change, each track and the close."), stage(st)] : stage(st));
    const end = (cls, text) => h("div", { class: `pipe-row ends ${cls}` }, h("div", { class: "end" }, text), h("div", { class: "pipe" }, h("div", { class: "end-cap" })), h("div"));
    // The split, the key and the readout sit in a panel beside the pipe that stays in view while the pipe scrolls past.
    put("g7-split",
      h("div", { class: "split", role: "img", "aria-label": P.phases.map(p => `${p.name} ${p.n}`).join(", ") },
        P.phases.map(p => h("div", { style: `flex:${Math.max(p.n, 0.0001)} 1 0` }, p.pct >= 6 ? `${p.pct}%` : ""))),
      h("div", { class: "split-key" }, P.phases.map(p => h("div", null, h("b", null, `${p.pct}%`), `${p.name} · ${p.n}`))));
    const pipeline = h("div", { class: "pipeline" },
      h("p", { class: "pipe-feed" }, "Beside every stage of the pipe, in the session:"), stage(P.hooks, "hooks-band"),
      h("div", { class: "pipe-body" },
        h("div", { class: "rail" }, h("span", null, `${P.escaped} got through a whole Day, caught on a later one`)),
        end("in", "A Day's work"), staged, end("out", "Next Day")),
      h("div", { class: "pipe-after" }, h("p", { class: "pipe-feed" }, "After a phase's last Day, outside the Day's pipe:"), stage(P.phase_end, "phase-end")));
    const sieve = h("div", { class: "sieve" },
      h("div", { class: "sieve-row head" }, h("div", { class: "sieve-day" }), h("div", { class: "sieve-gates" }, m.gates.map(g => h("div", { class: "sieve-gate" }, h("strong", null, g.name), h("span", null, g.sub)))),
        h("div", { class: "sieve-note" }, "Tags a second reader gave differently")),
      m.rows.map(r => forDays(h("div", { class: "sieve-row" }, h("div", { class: "sieve-day" }, `Day ${r.day}`),
        h("div", { class: "sieve-gates" }, r.cells.map(list => h("div", { class: "sieve-cell" }, list.slice(0, SIEVE_CAP).map(o => mark(h("button", { type: "button", class: `dot ${o.cause}${o.escaped ? " square" : ""}${o.back ? " ring" : ""}` }), o)),
          list.length > SIEVE_CAP ? h("span", { class: "sieve-more" }, `+${list.length - SIEVE_CAP}`) : null))),
        h("div", { class: "sieve-note mono" }, r.note)), [r.day])));
    // The same dots one row per Day: the only view that sets the Days side by side, to see whether catches move earlier.
    // Its own key, since it is read opened alone; a cell shows SIEVE_CAP dots and counts the rest, so one busy Day keeps its row's height.
    const sieveKey = h("div", { class: "legend sieve-key" }, m.key.map(k => h("span", null, h("i", { class: k.cls }), k.text)),
      h("span", null, `A cell shows at most ${SIEVE_CAP} dots; "+N" counts the rest. The share on the right: tags a blind reader gave differently, and ↑ or ↓ against the Day read before.`));
    put("g7-plot", pipeline);
    put("g7-days", h("details", { class: "by-day" }, h("summary", null, "By Day: each Day's catches side by side"), sieveKey, h("div", { class: "scroll-x" }, sieve)));
  });

  /* Graph 2 */
  graph("g2", (m, mark) => {
    key("g2-key", [["b-sw range", "Range of all Days"], ["b-sw last", "Last Day"], ["b-sw diamond", "Average so far"], ["b-sw kit", "The kit, with a person driving"]]);
    const pct = v => `${(100 * v).toFixed(1)}%`;
    // The trend, Day by Day, on the row's own scale; each Day's point lights with the Day buttons.
    const spark = (r, B) => {
      const s = document.createElementNS(SVG_NS, "svg"), X = p => (4 + p.x * 112).toFixed(1), Y = p => (30 - p.y * 26).toFixed(1);
      s.setAttribute("viewBox", "0 0 120 34"); s.setAttribute("class", "b-spark"); s.setAttribute("aria-hidden", "true");
      if (B.base != null) svgEl(s, "line", { class: "base", x1: 4, x2: 116, y1: Y({ y: B.base }), y2: Y({ y: B.base }) });
      svgEl(s, "path", { class: "trend", d: B.spark.map((p, i) => `${i ? "L" : "M"}${X(p)} ${Y(p)}`).join(" ") });
      B.spark.forEach((p, i) => forDays(svgEl(s, "circle", { class: i === B.spark.length - 1 ? "pt last" : "pt", cx: X(p), cy: Y(p), r: i === B.spark.length - 1 ? 2.8 : 1.8 }), [p.day]));
      return s;
    };
    put("g2-plot", h("div", { class: "bullets" },
      m.rows.flatMap(r => { const B = r.bullet; return [mark(h("div", { class: "b-row", tabindex: "0" },
        h("div", { class: "b-name" }, r.name, h("small", null, r.note)),
        h("div", { class: "b-bar" }, h("span", { class: "well" }), h("span", { class: "range", style: `left:${pct(B.lo)};width:${pct(Math.max(B.hi - B.lo, 0.005))}` }),
          h("span", { class: "last", style: `width:${pct(Math.max(B.last, 0.004))}` }), B.avg != null && h("span", { class: "diamond", style: `left:${pct(B.avg)}` }),
          B.base != null && h("span", { class: "kit", style: `left:${pct(B.base)}` })),
        spark(r, B),
        h("div", { class: "b-now" }, h("span", { class: B.cmp }, B.now), h("small", null, `Day ${B.day} · avg ${B.avgText}`))), B),
        r.foot && h("p", { class: "yard-foot" }, r.foot)]; }),
      m.waiting.map(w => h("div", { class: "b-row" }, h("div", { class: "b-name" }, w.name, h("small", null, "draws here once it is counted")), h("div", { class: "yard-wait" }, h("span", null, "Not measured yet: ", rich(w.why)))))));
  });

  /* Graph 10 */
  graph("g10", (m, mark) => {
    if (m.empty) { put("g10-plot", h("p", { class: "load-error" }, "Not measured yet: ", rich(m.empty))); return; }
    key("g10-key", [["sw busy", "Session busy"], ...m.runs.map(([k, text]) => [`sw run-${k}`, text]), ["", "Pull requests:"], ["sw spec", "Spec"], ["sw prod", "Code"], ["sw close", "The Day's close"], ["sw tooling", "Other (tooling, dashboard)"], ["sw failed", "Checks with a failure"], ["sw merge", "Merge"],
      ...(m.driver ? [["sw act", "The driver starts a session or sees a merge"], ["sw crash", "A session crashed"], ["sw park", "Parked, waiting for the maintainer"]] : [])]);
    const dates = m.dates.map(d => forDays(h("button", { type: "button", "aria-pressed": "false" }, d.label), d.days));
    put("g10-dates", h("span", null, "One date on the clock:"), dates);
    const show = i => {
      const d = m.dates[i];
      dates.forEach((c, j) => c.setAttribute("aria-pressed", j === i ? "true" : "false"));
      put("g10-plot", h("div", { class: "clock" },
        h("div", { class: "lane head" }, h("div", { class: "lane-name" }, m.zone), h("div", { class: "lane-bars" }, m.hours.map(x => h("span", { class: "hour", style: `left:${x.x.toFixed(2)}%` }, x.t)))),
        d.lanes.map(l => { const rows = Math.max(1, ...l.bars.map(b => (b.row || 0) + 1));
          return h("div", { class: "lane" }, h("div", { class: "lane-name" }, h("strong", null, l.name), h("span", null, l.sub)),
            h("div", { class: "lane-bars", style: rows > 1 ? `height:${26 + 20 * (rows - 1)}px` : null }, l.bars.map(b => forDays(mark(h("button", { type: "button", class: `lane-bar ${b.cls}`, style: `left:${b.x.toFixed(2)}%;width:${b.w.toFixed(2)}%${b.row ? `;top:${4 + 20 * b.row}px` : ""}` }), b), b.days)))); })));
      table("g10-table", d.table);
      mark.base(d.read);
      relight();
    };
    dates.forEach((c, i) => c.addEventListener("click", () => show(i)));
    onDay.push(day => { const i = m.dates.reduce((k, d, j) => d.days.includes(day) ? j : k, -1); if (i >= 0) show(i); });
    onDate.push(date => { const i = m.dates.findIndex(d => d.date === date); if (i >= 0) show(i); });
    show(m.at);
  });

  /* Graph 12, drawn beside graph 6: the plan against the specs, as the by-script mockup draws it (SVG) */
  /* The gene, first in its chapter: the plan read down to proved code */
  graph("gene", m => {
    if (m.empty) { put("gene-plot", h("p", { class: "load-error" }, "Not measured yet: ", rich(m.empty))); return; }
    // each class's sign beside its figure, as the picture draws it
    const sign = (w, hgt, ...marks) => { const s = document.createElementNS(SVG_NS, "svg"); s.setAttribute("width", w); s.setAttribute("height", hgt);
      s.setAttribute("viewBox", `0 0 ${w} ${hgt}`); s.setAttribute("aria-hidden", "true"); marks.forEach(([tag, attrs]) => svgEl(s, tag, attrs)); return s; };
    const dot = (cls, r) => sign(14, 14, ["circle", { class: cls, cx: 7, cy: 7, r }]);
    const SIGN = { proved: () => dot("proved", 6), unproved: () => dot("unproved", 5.2), unreplayable: () => dot("norun", 5.5), repair: () => dot("stale", 6), fails: () => dot("broken", 6),
      unbuilt: () => dot("unbuilt", 5.5), spliced: () => sign(22, 14, ["path", { class: "arc", d: "M1 12 Q11 -6 21 12" }], ["rect", { class: "ex skip", x: 7, y: 7, width: 8, height: 6, rx: 1.5 }]),
      regulatory: () => sign(12, 16, ["rect", { class: "rule", x: 1, y: 1, width: 10, height: 14 }]), switched: () => sign(12, 16, ["rect", { class: "notdue", x: 1, y: 1, width: 10, height: 14 }]),
      overdue: () => sign(12, 16, ["rect", { class: "overdue", x: 1, y: 1, width: 10, height: 14 }]) };
    put("gene-figs", m.figs.map(f => h("div", null, h("div", { class: "num" }, SIGN[f.cls](), String(f.n)), h("div", { class: "what" }, f.what), h("div", { class: "sub" }, f.sub))));
    $("gene-total").textContent = String(m.total);
    const fig = geneDraw(m, $("gene-plot"), $("gene-tip"), forDays);
    put("gene-finds", m.finds.map(f => {
      const li = h("li", { tabindex: f.ids.length ? 0 : null }, h("b", null, f.b), " ", rich(f.text));
      if (f.ids.length) { [["pointerenter", "focus"], ["pointerleave", "blur"]].forEach(([a, b], off) => [a, b].forEach(ev => li.addEventListener(ev, () => off ? fig.clear() : fig.light(f.ids)))); }
      return li; }));
    const plain = list => list.map(([b, text]) => h("li", null, h("b", null, rich(b)), rich(text)));
    put("gene-expected", plain(m.expected)); put("gene-bends", plain(m.bends));
  });

  /* The merge graph, in graph 6's place: the merges against the criteria they give evidence to */
  {
    const m = M.mrg, failed = e => { put("mrg-scroll", h("p", { class: "load-error" }, `This graph could not be drawn: ${e}`)); console.error(`mrg: ${e}`); };
    if (m.error) failed(m.error);
    else if (m.empty) put("mrg-scroll", h("p", { class: "load-error" }, "Not measured yet: ", rich(m.empty)));
    else try { mergeDraw(m, $, onDay); } catch (e) { failed(String((e && e.message) || e)); }
  }

  graph("g12", m => {
    if (m.empty) { put("g12-plot", h("p", { class: "load-error" }, "Not measured yet: ", rich(m.empty))); return; }
    put("g12-say", rich(m.say));
    planBar(m, $("g12-plot"), $("g12-tip"), $("g12-panel"), forDays, resets);
    planLadder(m.chart, $("g12-ladder"), $("g12-ltip"));
  });

  /* the foot of the page */
  put("caveats", M.caveats.map(c => h("li", null, rich(c))));
  put("not-measured", M.notMeasured.map(([name, why]) => h("li", null, h("b", null, name), ": ", rich(why))));
  // the file map: placed and laid out in Python (spec_drift_files), so it takes no Day button
  try { filDraw(DATA.file_map, $); } catch (e) {
    put("fil-scroll", h("p", { class: "load-error" }, `This graph could not be drawn: ${(e && e.message) || e}`)); console.error(`fil: ${(e && e.message) || e}`);
  }
  document.addEventListener("keydown", e => { if (e.key === "Escape") resets.forEach(r => r()); });
  foldLinks();
  // the old page, by its tag, on the repository the build read: the page names no repository of its own
  const blob = howBlob(DATA), old = document.getElementById("old-page");
  if (blob && old) old.setAttribute("href", blob.replace(/blob\/main\/$/, "tree/dashboard-v1/docs/dashboard"));
}

/* ---------- light or dark: the system's choice until the reader picks one ---------- */
// The theme a press of the switch sets: the opposite of what shows now, which is the reader's
// saved choice, or the system's when there is none.
function flipTheme(saved, systemDark) {
  const shown = saved === "dark" || saved === "light" ? saved : systemDark ? "dark" : "light";
  return shown === "dark" ? "light" : "dark";
}

function themeToggle() {
  const root = document.documentElement, button = document.getElementById("theme");
  if (!button) return;
  const system = matchMedia("(prefers-color-scheme: dark)");
  let saved = null;
  try { saved = localStorage.getItem("theme"); } catch (e) { /* storage blocked: follow the system */ }
  const show = () => {
    if (saved === "dark" || saved === "light") root.dataset.theme = saved; else delete root.dataset.theme;
    button.setAttribute("aria-pressed", String(flipTheme(saved, system.matches) === "light"));
  };
  button.addEventListener("click", () => {
    saved = flipTheme(saved, system.matches);
    try { localStorage.setItem("theme", saved); } catch (e) { /* kept for this visit only */ }
    show();
  });
  system.addEventListener("change", show);
  show();
}

/* The file map, "Where does each file belong?": every tracked file as one dot under the station of the workflow it
   serves. Placed and laid out in Python (spec_drift_files.file_map) from git's file list and
   docs/dashboard/file-stations.json on every build; this draws the cell, its seven stations and the checks between
   them, then the dots where the model put them. `get` finds an element by its id. Colours are in dashboard.css, under #fil. */
const FIL_STATIONS = [ // the pill's x, its zone, its name in one or two lines, and what it is in the cell
  [30, "doc", ["The goal"], "the gene"], [196, "doc", ["A Day's spec"], "transcription"], [368, "doc", ["A promise"], "the transcript"],
  [506, "try", ["A test that", "fails first"], "folding check"], [682, "try", ["The code, then", "a planted bug"], "the protein"],
  [970, "after", ["The Day", "closes"], "delivered, labelled"], [1136, "after", ["The re-check"], "still working?"]];
const FIL_REGION = { doc: "the nucleus", try: "the cytoplasm", after: "out of the cell, on main" };
function filDraw(F, get) {
  const $ = id => get("fil-" + id), fig = $("fig"), tip = $("tip");
  if (!F || F.empty) {
    $("scroll").replaceChildren(h("p", { class: "load-error" }, "Not measured yet: ", rich((F && F.empty) || "this build has no file list, so there is no file to draw.")));
    return;
  }
  const el = (n, a, txt, parent) => svgEl(fig, n, a, txt, parent), G = F.geo, kinds = F.kinds.map(k => k.key);
  const cnt = (n, one, many) => `${comma(n)} ${n === 1 ? one : many}`, cap = s => s.charAt(0).toUpperCase() + s.slice(1);
  fig.replaceChildren();
  fig.setAttribute("viewBox", `0 ${G.top} 1236 ${G.height}`);
  fig.setAttribute("aria-label", `A cell with seven numbered stations, and every file of the repository hung under the station it serves: ${F.zones.map(z => `${cnt(z.files, "file", "files")} ${z.where}`).join(", ")}; one dot is one file and its area is its line count`);
  // the cell: its wall and membrane, the nucleus with two pores, and the gap the way leaves it by; each as deep as its tallest column
  el("rect", { class: "cellb", x: 6, y: 112, width: 918, height: G.cell_h, rx: 44 });
  el("rect", { class: "mem-c", x: 10.5, y: 116.5, width: 909, height: G.cell_h - 9, rx: 40 });
  el("rect", { class: "nuc", x: 22, y: 130, width: 456, height: G.nuc_h, rx: 40 });
  el("rect", { class: "wipe", x: 912, y: 141, width: 24, height: 82 });
  [157, 179].forEach(cy => el("circle", { class: "pore", cx: 478, cy, r: 3.6 }));
  [["doc", 46, G.nuc_label], ["try", 506, G.cyto_label], ["after", 946, G.after_label]].forEach(([k, x, y]) => {
    const g = el("g", { class: `k-${k}` }), zone = F.zones.find(z => z.key === k);
    el("circle", { class: "sw", cx: x, cy: y, r: 4 }, null, g);
    el("tspan", { class: "t-bio", dx: 8 }, FIL_REGION[k], el("text", { class: "t-reg", x: x + 10, y: y + 4 }, (zone ? zone.name : k).toUpperCase(), g));
  });
  // the way, left to right, and on it the checks by someone else: a diamond an AI reviewer, a square a script, the gate a person
  el("line", { class: "way", x1: 76, y1: 168, x2: 1182, y2: 168 });
  [188, 360, 498, 674, 962, 1128].forEach(x => el("polygon", { class: "head", points: `${x},164 ${x + 7},168 ${x},172` }));
  const name = (x, t, bio) => { el("text", { class: "t-g", x, y: 204, "text-anchor": "middle" }, t); if (bio) el("text", { class: "t-bio", x, y: 216, "text-anchor": "middle" }, bio); };
  const diamond = x => el("path", { class: "chk", d: `M${x},158 l10,10 l-10,10 l-10,-10 z` });
  diamond(159); name(159, "plan-auditor");
  diamond(328); name(328, "spec-auditor", "proofreading");
  el("ellipse", { class: "ribo", cx: 640, cy: 157, rx: 27, ry: 14 }); el("ellipse", { class: "ribo", cx: 640, cy: 179, rx: 20, ry: 8.5 });
  el("line", { class: "way", x1: 610, y1: 168, x2: 670, y2: 168 }); name(640, "implementer", "the ribosome");
  el("rect", { class: "chk", x: 834, y: 160, width: 16, height: 16, rx: 2 }); name(842, "CI's checks", "quality control");
  [144, 175].forEach(y => el("rect", { class: "chk", x: 917, y, width: 14, height: 17, rx: 4 })); name(924, "the maintainer", "membrane gate");
  diamond(1100); name(1100, "defect-rater");
  FIL_STATIONS.forEach(([x, zone, words, bio], i) => {
    const g = el("g", { class: `k-${zone}` });
    el("rect", { class: "pill", x, y: 149, width: 92, height: 38, rx: 19 }, null, g);
    words.forEach((t, j) => el("text", { class: "t-nm", x: x + 49, y: words.length > 1 ? 166 + 12 * j : 172, "text-anchor": "middle" }, t, g));
    el("circle", { class: "no", cx: x + 5, cy: 150, r: 9.5 }, null, g);
    el("text", { class: "t-no", x: x + 5, y: 153.6, "text-anchor": "middle" }, i + 1, g);
    if (i === 6) el("rect", { class: "chk", x: x + 78, y: 143, width: 11, height: 11, rx: 1.5 }, null, g); // the re-check is itself a script's check
    el("text", { class: "t-bio", x: x + 46, y: 204, "text-anchor": "middle" }, bio, g);
  });
  // the files: a label and a count over each group, then its dots; the ring holds what hangs on no station
  if (G.plasmid) {
    el("circle", { class: "plasmid", cx: G.plasmid.x, cy: G.plasmid.cy, r: G.plasmid.r });
    el("text", { class: "t-bio", x: G.plasmid.x, y: G.plasmid.cy + G.plasmid.r + 14, "text-anchor": "middle" }, "on no station");
  }
  F.groups.forEach(g => {
    el("tspan", { class: "n" }, g.files, el("text", { class: "t-sub", x: g.x, y: g.y, "text-anchor": "middle" }, `${g.label} `));
    const box = el("g", { class: "grp", role: "img", "aria-label": `${g.label}: ${cnt(g.files, "file", "files")}, ${cnt(g.lines, "line", "lines")}, ${g.ring ? "" : "at "}${g.at}` });
    g.dots.forEach(([i, cx, cy, r]) => el("circle", { class: `b f ${kinds[F.files[i][2]]}`, "data-i": i, cx, cy, r }, null, box));
  });
  let on = null;
  pointerBox(fig, tip, (key, b) => {
    if (on) on.classList.remove("on");
    on = null;
    const d = key != null && F.files[+key];
    if (!d) return false;
    const g = F.groups[d[3]];
    on = b; b.classList.add("on");
    return tipFill(tip, { t: d[0], l: [`${cnt(d[1], "line", "lines")} · ${F.kinds[d[2]].name}`, d[4] ? F.unplaced_what : g.what, `Hung ${g.ring ? "" : "at "}${g.at}.`] });
  }, b => b.getAttribute("data-i"));

  // the figures, the key (the graph's own: no other graph explains its marks), the hint, the table and how it is drawn
  const fg = (num, what, sub, cls) => h("div", cls ? { class: cls } : null, h("div", { class: "num" }, comma(num)), h("div", { class: "what" }, what), h("p", { class: "sub" }, sub));
  $("figs").replaceChildren(fg(F.files.length, "files in the repository, each drawn once", `${comma(F.lines)} lines in all · one dot is one file, and its area is its line count`, "wide"),
    ...F.zones.map(z => fg(z.files, z.name, `${cnt(z.lines, "line", "lines")}, ${z.where}`)));
  const ico = (w, ht, parts) => { const s = document.createElementNS(SVG_NS, "svg"); for (const [k, v] of [["width", w], ["height", ht], ["viewBox", `0 0 ${w} ${ht}`], ["aria-hidden", "true"]]) s.setAttribute(k, v); parts.forEach(([n, a]) => svgEl(s, n, a)); return s; };
  const entry = (mark, text) => h("span", null, mark, text);
  $("key").replaceChildren(
    ...F.kinds.map(k => entry(ico(12, 12, [["circle", { class: `f ${k.key}`, cx: 6, cy: 6, r: 5 }]]), `${k.name} (${comma(k.n)})`)),
    entry(ico(34, 16, [[3, 1.8], [12, 3.6], [26, 7.2]].map(([cx, r]) => ["circle", { class: "f tool", cx, cy: 8, r }])), "25, 100 and 400 lines"),
    entry(ico(14, 14, [["path", { class: "chk", d: "M7,0.5 l6.5,6.5 l-6.5,6.5 l-6.5,-6.5 z" }]]), "check by an AI reviewer"),
    entry(ico(12, 12, [["rect", { class: "chk", width: 12, height: 12, rx: 2 }]]), "check by a script"),
    entry(ico(10, 20, [["rect", { class: "chk", width: 10, height: 8.5, rx: 3 }], ["rect", { class: "chk", y: 11.5, width: 10, height: 8.5, rx: 3 }]]), "check by a person"),
    entry(ico(26, 18, [["ellipse", { class: "ribo", cx: 13, cy: 6, rx: 12, ry: 5.4 }], ["ellipse", { class: "ribo", cx: 13, cy: 14, rx: 9, ry: 3.4 }]]), "the writer"));
  const U = F.unplaced || [], them = U.length === 1 ? "it" : "them";
  $("hint").replaceChildren("Point at a dot for the file's name, its length and what it is for.",
    ...(U.length ? [` ${cnt(U.length, "file is", "files are")} in the ring because the table does not place ${them}: ${U.slice(0, 6).join(", ")}${U.length > 6 ? ` and ${U.length - 6} more` : ""}. Add ${them} to `, h("code", null, F.table), "."] : []));
  $("table").replaceChildren(h("thead", null, h("tr", null, ...["Zone", "Hung at", "What it is", "Files", "Lines", "Names, longest first"].map(t => h("th", null, t)))),
    h("tbody", null, ...F.groups.map(g => h("tr", null, h("td", null, cap((F.zones.find(z => z.key === g.zone) || {}).name || "")), h("td", null, g.ring ? "No station" : cap(g.at)),
      h("td", null, g.what + (g.ring && U.length ? ` Also ${cnt(U.length, "file", "files")} the table does not place.` : "")), h("td", { class: "r" }, comma(g.files)), h("td", { class: "r" }, comma(g.lines)),
      h("td", { class: "nm" }, g.dots.map(d => F.files[d[0]][0]).join(", "))))));
  $("stamp").replaceChildren(`Drawn from the file list at ${String(F.head || "this build").slice(0, 7)}: ${comma(F.files.length)} tracked files, ${comma(F.lines)} lines. `, "The table that places them is ", h("code", null, F.table), ".");
  const li = (b, ...rest) => h("li", null, h("b", null, b), " ", ...rest);
  const folders = F.groups.filter(g => g.folder && g.zone === "try" && /^station/.test(g.at)).slice(0, 2);
  $("how").replaceChildren(
    li("The path is one promise's way.", "Seven numbered stations, left to right, from the written goal to the re-check on later merged code. Between them a diamond is a check by an AI reviewer and a square is a check by a script; the doubled gate in the cell's wall is the maintainer's merge, and the two ovals are the implementer, who writes the code. The small square on station 7 says that station is itself a script's check."),
    li("A folder places itself.", "A file hangs where its folder belongs", ...folders.flatMap((g, i) => [i ? ", " : ": ", h("code", null, g.label), ` at ${g.at.split(",")[0]}`]), ". A new file there appears by itself."),
    li("A script is placed by a short table.", `The ${cnt(F.scripts, "script sits", "scripts sit")} in one folder, so a table says which station each one checks. A script's own test hangs beside it, hollow. A script the table does not name is drawn in the ring, on no station.`),
    li("A dot's area is the file's line count.", "Within a group the longest file comes first."),
    li("Colour is the kind of file.", "They are the page's colours: blue for written text, orange for the app's code, magenta for its tests, grey for tooling and docs."));
}

function boot(DATA) {
  draw(model(DATA), DATA);
}

function start() {
  themeToggle();
  if (window.SPEC_DRIFT) return boot(window.SPEC_DRIFT);
  document.getElementById("now").textContent = "The data did not load. Build the page with python scripts/spec-drift.py --build dashboard.html; if this is the built page, it was published without its data line.";
}
