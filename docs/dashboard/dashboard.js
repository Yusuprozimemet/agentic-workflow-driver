// The dashboard in eight graphs. Each answers one question, folds what used to be several panels into
// its marks, and says the detail in the readout under it. model() reads the data and touches no
// document, so a test can run it; draw() puts what it returns on the page. A ninth graph, one day on
// the clock, waits for times nothing collects yet.

const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const shortDate = s => `${+s.slice(8, 10)} ${MONTHS[+s.slice(5, 7) - 1]}`;
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const money = n => "$" + Number(n).toFixed(2);
const comma = n => String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
const sum = (list, f) => list.reduce((a, x) => a + (Number(f ? f(x) : x) || 0), 0);
const andList = a => a.length < 3 ? a.join(" and ") : `${a.slice(0, -1).join(", ")} and ${a[a.length - 1]}`;
const finished = d => d.status === "done" || d.status === "closed" || d.status === "cut";
const openFor = m => m >= 60 ? `${(m / 60).toFixed(1)} h` : plural(Math.max(1, Math.round(m)), "minute", "minutes");
const plain = s => String(s == null ? "" : s).replace(/`/g, "");
const lower = s => s.charAt(0).toLowerCase() + s.slice(1);
// "Days 1 to 6" for a run of days, "Days 1, 2 and 4" for one with a hole in it.
const daySpan = ds => !ds.length ? "" : ds.length === 1 ? `Day ${ds[0]}`
  : ds[ds.length - 1] - ds[0] === ds.length - 1 ? `Days ${ds[0]} to ${ds[ds.length - 1]}` : `Days ${andList(ds.map(String))}`;

// What each replay state means to a reader: the group it counts in, and why it was not checked.
// tests/test_dashboard_gap.py holds these keys to the states scripts/replay-history.py writes.
const REPLAY_LOOK = {
  "code broken": { group: "broken" },
  "test weakened": { group: "repair", why: "its test no longer catches the bug it used to" },
  "break no longer applies": { group: "repair", why: "the code moved, so the planted bug could not be put back" },
  "not runnable": { group: "skipped", why: "the check could not run" },
  "not applicable on this platform": { group: "skipped", why: "it needs a different computer" },
  "live only": { group: "skipped", why: "it needs a real live run" },
  "holds, never broken": { group: "unproven" },
  "holds": { group: "proven" },
  "not yet in force": { group: null },
};
// Every state a promise's tile can be in. The first five are what a re-check can find, and the only ones counted
// as "re-checked"; each has its own colour and mark (dashboard.css), used for promise states and nothing else.
const STATES = {
  proven: { word: "Proven", glyph: "✓", means: "its test still passes, and still fails when the bug is put back" },
  unproven: { word: "Passes, not yet proven", means: "its test passes, and has not been seen to fail in the re-check" },
  repair: { word: "Needs repair", glyph: "!", means: "its test cannot be trusted to catch a failure" },
  broken: { word: "Broken", glyph: "✕", means: "the promise no longer holds" },
  skipped: { word: "Not checked here", means: "it needs a real live run or a different computer" },
  replaced: { word: "Replaced", glyph: "→", means: "a later promise took its place" },
  building: { word: "Not yet in force", means: "its day is still being built" },
  open: { word: "Left unticked", means: "its day closed without ticking it" },
  unchecked: { word: "Not re-checked yet", means: "no re-check has run on it" },
};
const COUNTED = ["proven", "unproven", "repair", "broken", "skipped"];
const ALWAYS_KEYED = ["proven", "unproven", "repair", "broken", "skipped"];

// The gates a defect can be caught at, in the order work passes them. A found: value that names none of
// them (a track, a review, the session itself) was noticed during the work.
const GATES = [
  { key: "auditor", name: "Auditors, before any code", at: "the auditors" },
  { key: "seen red", name: "A test seen failing", at: "a test seen failing" },
  { key: "break on purpose", name: "A break on purpose", at: "a break on purpose" },
  { key: "work", name: "Noticed during the work", at: "the work" },
  { key: "close", name: "The close", at: "the close" },
  { key: "evidence replay", name: "The evidence replay", at: "the evidence replay" },
];
const CAUSES = ["spec", "process", "implementation", "environment", "other"];
const KINDS = { origin: "the first commit", spec: "spec", code: "code", close: "a day's close", other: "other" };
const WORK = [["spec", "Spec and agent context"], ["prod", "Production code"], ["test", "Tests"], ["tooling", "Tooling"]];
const REASONS = { replay_failed: "Replay failed", replay_error: "Replay error", replay_stale: "Replay stale",
  evidence_missing: "Evidence missing", not_seen_red: "Not seen red", test_not_found: "Test not found", handoff_unclaimed: "Hand-off unclaimed",
  not_breakable: "No break possible from the repository", test_skippable: "Can be skipped in CI (expected)",
  handoff_next: "Hand-off for the next day", handoff_unpicked: "Hand-off no later day picks up" };
const YARD_HINT = { escapes: "fewer is better", refusals: "many of one kind mean a rule is in the way", reread: "re-reading is most of the cost" };

/* ---------- the model: what each graph draws and says, from the data alone ---------- */
function model(DATA) {
  const now = DATA.now || {}, days = [...(DATA.days || [])].sort((a, b) => a.day - b.day), current = now.current_day;
  const stories = (DATA.user_stories || {}).stories || [], named = (DATA.user_stories || {}).abilities || [];
  const abilityName = key => (named.find(a => a.key === key) || {}).name;
  const safe = fn => { try { return fn(); } catch (e) { return { error: String((e && e.message) || e) }; } };
  const done = days.filter(finished).map(d => d.day);
  const daysSay = (done.length ? `${daySpan(done)} ${done.length === 1 ? "is" : "are"} closed` : "No day is closed yet")
    + (current != null ? ` and Day ${current} is in progress.` : ".");

  function head() {
    const g = now.generated || "", when = g.length >= 16 ? `${shortDate(g)} ${g.slice(0, 4)} at ${g.slice(11, 16)}` : g;
    return { project: (DATA.meta || {}).project || "", when, commit: String(now.head || "").slice(0, 7), demo: DATA.demo === true,
      now: daysSay, next: String(now.next_step || ""), open: (now.open_prs || []).length };
  }

  /* Graph 1: ability by day */
  function abilityGraph() {
    const keyOf = s => named.some(a => a.key === s.ability) ? s.ability : null;
    const rowsOf = [...named, ...(stories.some(s => keyOf(s) === null) ? [{ key: null, name: "No ability named" }] : [])];
    const cols = [...days.map(d => ({ day: d.day, label: String(d.day), mark: finished(d) ? "✓" : d.day === current ? "now" : "" })),
      { day: null, label: "No day", mark: "" }];
    const colOf = s => days.some(d => d.day === s.day) ? s.day : null;
    const rows = rowsOf.map(a => ({ name: a.name, cells: cols.map(c => {
      const prs = stories.filter(s => keyOf(s) === a.key && colOf(s) === c.day).map(s => s.number).sort((x, y) => x - y), n = prs.length;
      const b = n ? `${plural(n, "merged pull request", "merged pull requests")} grew this ability ${c.day == null
          ? "between the days, as tooling and dashboard work, not as a day's track" : `on Day ${c.day}`}: ${prs.map(p => "#" + p).join(", ")}.`
        : c.day == null ? "Every pull request for this ability belongs to a day." : `No pull request grew this ability on Day ${c.day}.`;
      return { day: c.day, n, level: n >= 10 ? 4 : n >= 6 ? 3 : n >= 3 ? 2 : n >= 1 ? 1 : 0, t: `${a.name} · ${c.day == null ? "outside any day" : `Day ${c.day}`}`, b: [b] };
    }) }));
    const H = DATA.hand_offs || [], mine = H.filter(h => h.to === current), later = H.filter(h => current != null && h.to > current);
    const notes = [mine.length && `${mine.filter(h => h.picked).length} of the ${plural(mine.length, "note", "notes")} earlier days left for Day ${current} ${mine.length === 1 ? "was" : "were"} picked up`,
      later.length && `${later.length} more wait for ${daySpan([...new Set(later.map(h => h.to))].sort((a, b) => a - b))}`].filter(Boolean);
    return { cols, rows,
      read: { t: stories.length ? `${plural(stories.length, "merged pull request", "merged pull requests")}, each tagged with the ability it grew` : "No merged pull request yet",
        b: [daysSay + (notes.length ? ` ${notes.join("; ")}.` : "") + (now.stop_after != null ? ` The plan stops for the maintainer after Day ${now.stop_after}.` : "")] },
      table: { head: ["Ability", ...cols.map(c => c.day == null ? c.label : `Day ${c.label}`), "All"],
        rows: rows.map(r => [r.name, ...r.cells.map(c => c.n), sum(r.cells, c => c.n)]) } };
  }

  /* The promises: one reading for graphs 2 and 3, so they cannot disagree. Each promise takes the state of
     its newest re-check; one whose day is unfinished, or that a later promise replaced, is drawn and not counted. */
  function promises() {
    const rp = DATA.replay || {}, index = DATA.criteria_index || [], byDay = new Map(days.map(d => [d.day, d]));
    const merges = [...(rp.merges || [])].sort((a, b) => a.n - b.n), byN = new Map(merges.map(m => [m.n, m]));
    const cells = [...(rp.cells || [])].sort((a, b) => a.n - b.n), latest = new Map(cells.map(c => [c.criterion, c]));
    const age = pr => pr == null || now.last_pr == null ? "" : pr >= now.last_pr ? ", the latest change" : `, ${plural(now.last_pr - pr, "change", "changes")} ago`;
    const atClose = new Set(days.flatMap(d => d.broken_at_close || []));
    const tiles = index.map(c => {
      const day = byDay.get(c.day), cell = latest.get(c.id), look = (cell && REPLAY_LOOK[cell.state]) || {};
      const status = !day || !finished(day) ? "building" : (c.replaced_by || []).length ? "replaced" : c.ticked === false ? "open" : look.group || "unchecked";
      const why = status === "replaced" ? `by ${c.replaced_by.join(", ")}` : status === "building" ? `Day ${c.day} is still being built`
        : (COUNTED.includes(status) && look.why) || STATES[status].means;
      const seen = c.seen_red || {}, mark = (ok, yes, no) => ok ? `✓ ${yes}` : `✕ ${no}`;
      const lines = [c.plain || c.claim || ""];
      if (status === "building" && !c.ticked) lines.push("No evidence yet: the day is not closed.");
      else lines.push([mark(c.ticked, "ticked at the close", "not ticked"), mark(c.cited, "cites its pull request", "cites no pull request"),
        mark(c.test_found, "names a test that exists", "names no test that exists"),
        seen.state ? "✓ a failure was recorded when it was built" : seen.state === false && (seen.none || []).length ? `– no failure could be planted: ${seen.none.join("; ")}`
          : seen.state === false ? "✕ no failure recorded when built" : "– a failure when built was not measured"].join(" · ")
        + (atClose.has(c.id) ? " · its check was first seen failing at the close, not in the pull request that wrote it" : ""));
      const m = cell && byN.get(cell.n), grows = (c.abilities || []).map(abilityName).filter(Boolean);
      const last = [COUNTED.includes(status) && m ? `Last re-checked after pull request #${m.pr}${age(m.pr)}${cell.mixed ? "; its checks disagree" : ""}.` : "",
        grows.length ? `It grew “${grows[0]}”${grows.length > 1 ? `, and also ${andList(grows.slice(1).map(g => `“${g}”`))}` : ""}.` : ""].filter(Boolean).join(" ");
      if (last) lines.push(last);
      return { id: c.id, day: c.day, status, abilities: c.abilities || [], glyph: STATES[status].glyph || "",
        t: `${c.id} · ${c.tag === "hold" ? "must keep holding" : "new behaviour"} · ${STATES[status].word}: ${why}`, b: lines };
    });
    const n = (list, s) => list.filter(t => t.status === s).length, counted = list => list.filter(t => COUNTED.includes(t.status)).length;
    const replaced = new Set(index.filter(c => (c.replaced_by || []).length).map(c => c.id)), state = new Map();
    let k = 0;
    const hist = merges.map(m => {
      for (; k < cells.length && cells[k].n <= m.n; k++) if (!replaced.has(cells[k].criterion)) state.set(cells[k].criterion, (REPLAY_LOOK[cells[k].state] || {}).group);
      const counts = Object.fromEntries(COUNTED.map(g => [g, 0]));
      state.forEach(g => { if (g) counts[g]++; });
      const total = sum(Object.values(counts));
      return { pr: m.pr, counts, total, t: `Re-check after pull request #${m.pr}: ${counts.proven} of ${total} proven`,
        b: [`${counts.unproven} ${counts.unproven === 1 ? "passes but is" : "pass but are"} not yet proven, ${plural(counts.repair, "needs", "need")} repair, ${counts.broken} broken, ${counts.skipped} not checked here.`] };
    });
    const rows = [...new Set(tiles.map(t => t.day))].sort((a, b) => a - b).map(day => {
      const list = tiles.filter(t => t.day === day), c = counted(list);
      return { day, tiles: list, count: n(list, "building") === list.length ? "not yet in force" : !c ? "no re-check on record" : `${n(list, "proven")} of ${c} proven` };
    });
    const all = counted(tiles), newest = merges[merges.length - 1], first = hist[0], last = hist[hist.length - 1];
    const loaded = rp.state === "loaded" && all > 0;
    const building = [...new Set(tiles.filter(t => t.status === "building").map(t => t.day))].sort((a, b) => a - b);
    const rest = [n(tiles, "replaced") && `${plural(n(tiles, "replaced"), "was", "were")} replaced by later promises`,
      building.length && `${daySpan(building)}'s ${n(tiles, "building")} are not yet in force`,
      n(tiles, "open") && `${plural(n(tiles, "open"), "was", "were")} left unticked`, n(tiles, "unchecked") && `${plural(n(tiles, "unchecked"), "has", "have")} no re-check yet`].filter(Boolean);
    const board = { rows, hist, histMax: Math.max(1, ...hist.map(h => h.total)),
      key: Object.keys(STATES).filter(s => ALWAYS_KEYED.includes(s) || n(tiles, s)).map(s => ({ status: s, glyph: STATES[s].glyph || "", text: `${STATES[s].word} ${n(tiles, s)}` })),
      say: `One tile per promise the specs made, ${tiles.length} in all, in the state the last re-check found it.`,
      histSay: hist.length ? `Is trust growing? The same count at each of the ${plural(hist.length, "change", "changes")} the re-check ran on: ${first.counts.proven} proven of ${first.total} at first, ${last.counts.proven} of ${last.total} now.` : "",
      read: !loaded ? { t: tiles.length ? "No re-check of the promises is on record" : "No promise yet", b: rest.length ? [`${rest.join("; ")}.`] : [] }
        : { t: `${n(tiles, "proven")} of the ${all} promises re-checked are proven; ${n(tiles, "broken") ? plural(n(tiles, "broken"), "is broken", "are broken") : "none is broken"}`,
          b: [`${n(tiles, "unproven")} ${n(tiles, "unproven") === 1 ? "passes but is" : "pass but are"} not yet proven, ${plural(n(tiles, "repair"), "needs", "need")} repair and ${n(tiles, "skipped")} cannot be checked on this computer.`
            + (rest.length ? ` ${rest.join("; ").replace(/^./, c => c.toUpperCase())}.` : "")
            + (newest ? ` Last re-check: pull request #${newest.pr}${age(newest.pr)}. It is run by hand, so it can lag behind the newest change.` : "")] },
      table: { head: ["Day", ...Object.values(STATES).map(s => s.word), "All"],
        rows: rows.map(r => [`Day ${r.day}`, ...Object.keys(STATES).map(s => n(r.tiles, s)), r.tiles.length]) } };
    return { tiles, n, counted, board };
  }

  /* Graph 3: each ability with the promises its pull requests built */
  function reliedGraph(P) {
    const groupsOf = list => [...new Set(list.map(t => t.day))].sort((a, b) => a - b).map(day => ({ day, tiles: list.filter(t => t.day === day) }));
    const rows = named.map(a => {
      const mine = P.tiles.filter(t => t.abilities[0] === a.key), own = stories.filter(s => s.ability === a.key), c = P.counted(mine);
      return { name: a.name, tiles: mine, groups: groupsOf(mine), prs: own.length, proven: P.n(mine, "proven"), counted: c,
        note: mine.length ? "" : own.length && own.every(s => s.day == null) ? "No promise covers this ability. Its pull requests are work outside the day specs." : "No promise covers this ability yet.",
        count: (mine.length ? (c ? `${P.n(mine, "proven")} of ${c} proven` : plural(mine.length, "promise", "promises")) + " · " : "") + plural(own.length, "pull request", "pull requests") };
    });
    const loose = P.tiles.filter(t => !named.some(a => a.key === t.abilities[0]));
    if (loose.length) {
      const ds = [...new Set(loose.map(t => t.day))], building = loose.every(t => t.status === "building");
      rows.push({ name: building && ds.length === 1 ? `Day ${ds[0]}, still being built` : "Not tied to an ability yet", tiles: loose, groups: groupsOf(loose), prs: 0, proven: 0, counted: 0, loose: true,
        note: "", count: `${plural(loose.length, "promise", "promises")}, not yet tied to a pull request` });
    }
    const real = rows.filter(r => !r.loose), ranked = real.filter(r => r.counted).sort((a, b) => b.proven / b.counted - a.proven / a.counted || b.counted - a.counted);
    const none = ranked.filter(r => !r.proven), bare = real.filter(r => !r.tiles.length), shared = P.tiles.filter(t => t.abilities.length > 1).length;
    const b = [none.length && `${andList(none.map(r => `“${r.name}”`))} ${none.length === 1 ? "has" : "have"} none proven yet.`,
      bare.length && `${plural(bare.length, "ability", "abilities")}, with ${plural(sum(bare, r => r.prs), "pull request", "pull requests")} between them, ${bare.length === 1 ? "has" : "have"} no promise at all.`,
      shared && `${plural(shared, "promise touches", "promises touch")} more than one ability and ${shared === 1 ? "is" : "are"} drawn under the one most of ${shared === 1 ? "its" : "their"} pull requests grew.`].filter(Boolean);
    const cols = ["proven", "unproven", "repair", "broken", "skipped", "replaced", "building"];
    return { rows,
      read: { t: ranked.length && ranked[0].proven ? `“${ranked[0].name}” is the best proven: ${ranked[0].proven} of its ${plural(ranked[0].counted, "re-checked promise", "re-checked promises")}` : "No ability has a proven promise yet", b: [b.join(" ")].filter(Boolean) },
      table: { head: ["Ability", "Promises", ...cols.map(s => STATES[s].word), "Pull requests"],
        rows: rows.map(r => [r.name, r.tiles.length, ...cols.map(s => P.n(r.tiles, s)), r.prs]) } };
  }

  /* Graph 4: every merge, with the gap it left, how long it was open, and whether a check failed on it */
  function mergeGraph() {
    const R = DATA.rows || [], V = new Map((DATA.verification || []).map(v => [v.number, v]));
    const gaps = R.map(r => r.gap_full).filter(g => g != null);
    const lo = gaps.length ? Math.floor((Math.min(...gaps) - 1) / 5) * 5 : 0, hi = gaps.length ? Math.ceil((Math.max(...gaps) + 1) / 5) * 5 : 90;
    const mins = R.map(r => { const v = V.get(r.pr); return v && v.hours != null ? v.hours * 60 : null; });
    const top = Math.max(120, ...mins.filter(m => m != null)), barAt = m => (6 + Math.log2(Math.max(m, 1)) / Math.log2(top) * 54) / 60;
    let before = null;
    const merges = R.map((r, i) => {
      const kind = r.kind in KINDS ? r.kind : "other", v = V.get(r.pr) || {}, m = mins[i], failed = (v.failed || 0) > 0, g = r.gap_full;
      const moved = g == null || before == null ? null : g - before;
      if (g != null) before = g;
      const says = [g == null ? "The gap was not measured at this merge." : `Spec and code ${g.toFixed(1)}° apart${moved == null ? "" : Math.abs(moved) < 0.05 ? ", unchanged" : `, ${moved > 0 ? "up" : "down"} ${Math.abs(moved).toFixed(1)}° from the merge before`}.`,
        m == null ? "" : `Open for ${openFor(m)} before it merged.`,
        !r.pr ? "" : failed ? `A check failed on it first${(v.failed_in || []).length ? ` (${v.failed_in.join(", ")})` : ""}.` : "No check failed on it."].filter(Boolean).join(" ");
      return { pr: r.pr, kind, day: r.day || 0, date: r.date, gap: g, moved, mins: m, failed, y: g == null ? null : (hi - g) / (hi - lo), h: m == null ? 0 : barAt(m),
        t: `${r.pr ? `Pull request #${r.pr}` : "The first commit"} · ${KINDS[kind]} · ${r.day ? `Day ${r.day}` : "before Day 1"}`, b: [r.title, says].filter(Boolean) };
    });
    const bands = [];
    merges.forEach(m => { const b = bands[bands.length - 1]; if (b && b.day === m.day) b.n++; else bands.push({ day: m.day, n: 1 }); });
    const nKind = k => merges.filter(m => m.kind === k).length, withPr = merges.filter(m => m.pr), nFailed = merges.filter(m => m.failed).length;
    const mean = k => { const ms = merges.filter(m => m.kind === k && m.moved != null); return ms.length ? sum(ms, m => m.moved) / ms.length : null; };
    const last = R[R.length - 1] || {}, band = last.gap_chance_band, spec = mean("spec"), code = mean("code");
    const signed = x => `${x > 0 ? "up" : "down"} by ${Math.abs(x).toFixed(1)}°`;
    const b = [last.gap_full != null && band ? (last.gap_full < band[0] ? "The specs and the code share more names than chance would" : last.gap_full > band[1] ? "The specs and the code share fewer names than chance would" : "That is within what chance gives")
        + `: nineteen times in twenty, chance gives ${band[0].toFixed(1)}° to ${band[1].toFixed(1)}°.` : "",
      spec != null && code != null ? `On average a spec merge moved the dot ${signed(spec)} and a code merge ${signed(code)}.` : "",
      withPr.length ? `${nFailed} of ${plural(withPr.length, "pull request", "pull requests")} had a check fail before ${withPr.length === 1 ? "it" : "they"} merged.` : ""].filter(Boolean);
    const step = hi - lo > 30 ? 10 : 5, ticks = [];
    for (let t = lo + step; t < hi; t += step) ticks.push({ label: `${t}°`, y: (hi - t) / (hi - lo) });
    return { merges, bands, ticks, barTicks: [[1, "1 min"], [10, "10 min"], [top, top >= 90 ? `${Math.round(top / 60)} h` : `${Math.round(top)} min`]].map(([m, label]) => ({ label, h: barAt(m) })),
      key: [["spec", `Spec merge ${nKind("spec")}`], ["code", `Code merge ${nKind("code")}`], ["close", `A day's close ${nKind("close")}`],
        ["other", `Other (tooling, dashboard) ${nKind("other") + nKind("origin")}`], ["failed", `A check failed before the merge ${nFailed}`]],
      say: `One column per merge, ${merges.length} in all, oldest on the left. The dot is the angle between the specs and the code over the names the specs use, in degrees: lower means closer. The bar under it is how long the pull request stayed open.`,
      read: { t: last.gap_full == null ? "No gap is measured yet" : `Now ${last.gap_full.toFixed(1)}° apart` + (last.gap_chance != null ? `, where chance alone would give ${last.gap_chance.toFixed(1)}°` : ""), b: [b.join(" ")].filter(Boolean) },
      table: { head: ["Merge", "Kind", "Day", "Date", "Gap, degrees", "Minutes open", "Checks failed"],
        rows: merges.map(m => [m.pr ? `#${m.pr}` : "start", KINDS[m.kind], m.day || "", m.date || "", m.gap == null ? "" : m.gap.toFixed(1), m.mins == null ? "" : Math.round(m.mins), m.failed ? "yes" : ""]) } };
  }

  /* Graph 5: the sieve. Each defect at the gate that caught it */
  function sieveGraph() {
    const spent = new Map(((DATA.gate_report || {}).gates || []).filter(g => g.found).map(g => [g.found, g]));
    const back = new Map((((DATA.defect_recurrence || {}).recurrences) || []).map(r => [r.id, r.same_as]));
    const rows = days.map(d => {
      const dots = (d.defects || []).map((x, i) => {
        const gate = GATES.find(g => g.key === x.found) || GATES[3], cause = CAUSES.includes(x.cause) ? x.cause : "other";
        const m = /^Day 0*(\d+)$/i.exec(x.made || ""), made = m ? +m[1] : null, escaped = made != null && made !== d.day;
        const where = escaped ? `Made on Day ${made} and caught on Day ${d.day}` + (made < d.day ? `: it escaped for ${plural(d.day - made, "day", "days")}.` : ".")
          : made != null ? `Made and caught on Day ${d.day}.` : /^none$/i.test(x.made || "") ? "Made outside any day: in the plan, a tool or a machine."
          : `Caught on Day ${d.day}; its line does not say which day made it.`;
        return { id: x.id || `Day ${d.day}, defect ${i + 1}`, gate: gate.key, cause, escaped, back: back.has(x.id),
          t: `${x.id || `Day ${d.day}, defect ${i + 1}`} · ${cause} · caught by: ${lower(gate.name)}`,
          b: [where + (back.has(x.id) ? ` The same problem as ${back.get(x.id)}, back again.` : "") + (gate.key === "work" && x.found ? ` Noticed by: ${x.found}.` : "")] };
      });
      const R = d.relabel ? Object.values(d.relabel) : null;
      return { day: d.day, dots, cells: GATES.map(g => dots.filter(o => o.gate === g.key)), differ: R ? sum(R, r => r[1] - r[0]) : null, tags: R ? sum(R, r => r[1]) : null,
        note: R ? `${sum(R, r => r[1] - r[0])} of ${sum(R, r => r[1])}` : finished(d) ? "not read yet" : "read at its close" };
    });
    const all = rows.flatMap(r => r.dots), at = k => all.filter(o => o.gate === k).length, by = c => all.filter(o => o.cause === c).length;
    const gates = GATES.map(g => { const s = spent.get(g.key);
      return { name: g.name, sub: `${at(g.key)} caught` + (s ? ` · ${plural(s.runs, "run", "runs")} · ${money(s.cost)}` : g.key === "work" ? " · tracks, reviews, the session" : "") }; });
    const each = GATES.map(g => [g, spent.get(g.key)]).filter(([g, s]) => s && s.cost > 0 && at(g.key)).map(([g, s]) => [s.cost / at(g.key), g.at]).sort((a, b) => a[0] - b[0]);
    const read = rows.filter(r => r.tags), nEsc = all.filter(o => o.escaped).length, nBack = all.filter(o => o.back).length;
    const b = [by("spec") ? `${by("spec")} ${by("spec") === 1 ? "was" : "were"} in a spec.` : "",
      `${nEsc} escaped from an earlier day and ${nBack} came back.`,
      read.length ? `A second reader gave ${sum(read, r => r.differ)} of ${sum(read, r => r.tags)} tags differently.` : "",
      each.length ? `Each catch cost about ${andList(each.map(([c, name]) => `${money(c)} at ${name}`))}.` : ""].filter(Boolean);
    return { gates, rows,
      key: [...CAUSES.filter(c => c !== "other" || by(c)).map(c => ({ cls: `dot ${c}`, text: `${c.charAt(0).toUpperCase() + c.slice(1)} ${by(c)}` })),
        { cls: "dot ring", text: `Ringed: the same problem came back ${nBack}` }, { cls: "dot square", text: `Square: made on an earlier day ${nEsc}` }],
      say: `Each dot is one defect from a day's Notes, ${all.length} in all, placed at the gate that caught it. Work passes the gates from left to right, so a dot further right was caught later.`,
      read: { t: !all.length ? "No defect is recorded yet" : at("auditor") ? `${plural(all.length, "defect", "defects")}; the auditors caught ${at("auditor")} of them before any code was written` : `${plural(all.length, "defect", "defects")} in the days' Notes`,
        b: all.length ? [b.join(" ")] : [] },
      table: { head: ["Day", ...GATES.map(g => g.name), ...CAUSES.map(c => `Cause: ${c}`), "Escaped", "Came back", "Tags read differently", "Tags"],
        rows: rows.map(r => [`Day ${r.day}`, ...r.cells.map(c => c.length), ...CAUSES.map(c => r.dots.filter(o => o.cause === c).length),
          r.dots.filter(o => o.escaped).length, r.dots.filter(o => o.back).length, r.differ == null ? "" : r.differ, r.tags == null ? "" : r.tags]) } };
  }

  /* Graph 6: what each date cost, and what the hooks stopped on it */
  function costGraph() {
    const T = DATA.tokens || [], F = DATA.refusals || [], dates = [...new Set(T.map(t => t.date))].sort();
    const start = days.map(d => (d.worked || [])[0]).filter(Boolean).sort()[0];
    const bars = dates.map(date => {
      const rows = T.filter(t => t.date === date), cost = pick => sum(rows.filter(pick), t => t.cost);
      const main = cost(t => t.agent === "main"), aud = cost(t => /auditor|rater/.test(t.agent || "")), other = cost(() => true) - main - aud, total = main + aud + other;
      const on = days.filter(d => d.worked && d.worked[0] <= date && date <= d.worked[1]).map(d => d.day);
      const refused = F.filter(r => r.date === date && r.refused), nRefused = sum(refused, r => r.refused), cut = sum(rows, t => t.cut), replies = sum(rows, t => t.replies);
      const merged = (DATA.rows || []).filter(r => r.pr && r.date === date).length;
      return { date, label: shortDate(date), days: on, main, aud, other, total, replies, refused: nRefused, cut, merged, setup: !start || date < start,
        t: `${shortDate(date)} · ${on.length ? daySpan(on) : !start || date < start ? "before Day 1" : "between days"} · ${money(total)}`,
        b: [`Main session ${money(main)}, auditors ${money(aud)}, implementer and others ${money(other)}. ${comma(replies)} replies.`
          + ` The hooks refused ${plural(nRefused, "call", "calls")}${refused.length ? ` (${refused.map(r => `${r.refused} by the ${r.guard}`).join(", ")})` : ""} and cut ${plural(cut, "long output", "long outputs")}.`
          + (merged ? ` ${plural(merged, "pull request", "pull requests")} merged that date: ${money(total / merged)} each, all sessions.` : "")] };
    });
    const all = sum(bars, b => b.total), main = sum(bars, b => b.main), setup = bars.filter(b => b.setup), work = bars.filter(b => !b.setup);
    const newest = ((DATA.rows || [])[(DATA.rows || []).length - 1] || {}).date, lastDate = dates[dates.length - 1];
    const b = [setup.length && work.length ? `${plural(setup.length, "date", "dates")} of set-up cost ${money(sum(setup, x => x.total))} before Day 1.` : "",
      work.length ? `The days cost ${money(sum(work, x => x.total))} over ${plural(work.length, "date", "dates")} and ${plural(sum(work, x => x.merged), "merged pull request", "merged pull requests")}.` : "",
      `The hooks refused ${plural(sum(bars, x => x.refused), "call", "calls")} and cut ${plural(sum(bars, x => x.cut), "long output", "long outputs")}.`,
      newest && lastDate && newest > lastDate ? `Counted at each close on the maintainer's computer, so nothing after ${shortDate(lastDate)} is in yet.` : ""].filter(Boolean);
    return { bars, max: Math.max(0.01, ...bars.map(x => x.total)),
      key: [["main", `Main session ${money(main)}`], ["rest", `Auditors and the implementer ${money(all - main)}`]],
      say: "Dollars of tokens on each date with a session, at list prices, counted on the maintainer's computer.",
      read: { t: bars.length ? `${money(all)} of tokens; ${Math.round(100 * main / (all || 1))}% of it in the main session` : "No token counts yet", b: bars.length ? [b.join(" ")] : ["They are counted at a day's close, on the maintainer's computer."] },
      table: { head: ["Date", "Days", "Main session, $", "Auditors, $", "Implementer and others, $", "Replies", "Calls refused", "Outputs cut", "Pull requests merged"],
        rows: bars.map(x => [x.label, x.days.join(", "), x.main.toFixed(2), x.aud.toFixed(2), x.other.toFixed(2), x.replies, x.refused, x.cut, x.merged]) } };
  }

  /* Graph 7: the lines each day changed, by what the file is */
  function workGraph() {
    const R = DATA.rows || [], part = (r, k) => { const w = r.work || {}; return k === "spec" ? (w.spec || 0) + (w.context || 0) : w[k] || 0; };
    const of = list => Object.fromEntries(WORK.map(([k]) => [k, sum(list, r => part(r, k))]));
    const bars = days.map(d => {
      const mine = R.filter(r => r.day === d.day), w = of(mine), total = sum(Object.values(w)), prs = mine.filter(r => r.pr).length;
      const ratio = w.prod ? (w.test / w.prod).toFixed(1) : "–";
      return { day: d.day, w, total, prs, ratio, label: total >= 1000 ? `${(total / 1000).toFixed(1)}k` : String(total),
        t: `Day ${d.day}${d.day === current ? " (in progress)" : ""} · ${comma(total)} lines changed`,
        b: [`${WORK.map(([k, name], i) => `${i ? lower(name) : name} ${comma(w[k])}`).join(", ")}. ${plural(prs, "pull request", "pull requests")} merged.`
          + (w.prod ? ` ${ratio} test lines for each production line.` : "")] };
    });
    const all = of(R.filter(r => days.some(d => d.day === r.day))), total = sum(Object.values(all)), before = sum(Object.values(of(R.filter(r => !days.some(d => d.day === r.day)))));
    const ranked = WORK.map(([k, name]) => [name, all[k]]).sort((a, b) => b[1] - a[1]);
    return { bars, max: Math.max(1, ...bars.map(x => x.total)), key: WORK.map(([k, name]) => [k, name]),
      read: { t: total ? `${comma(total)} lines changed in ${daySpan(days.map(d => d.day))}; the largest share is ${lower(ranked[0][0])}` : "No day has merged work yet",
        b: total ? [`${ranked.map(([name, v], i) => `${i ? lower(name) : name} ${comma(v)}`).join(", ")}.` + (before ? ` Another ${comma(before)} lines came before Day 1.` : "")
          + " Breaks on purpose never merge, so checking did more than its lines show."] : [] },
      table: { head: ["Day", ...WORK.map(w => w[1]), "All", "Pull requests merged", "Test lines for each production line"],
        rows: bars.map(x => [`Day ${x.day}`, ...WORK.map(([k]) => x.w[k]), x.total, x.prs, x.ratio]) } };
  }

  /* Graph 8: the plan's yardsticks, each on its own scale, against the kit's baseline where it has one */
  function yardGraph() {
    const Y = DATA.yardsticks || {}, all = Y.rows || [], cols = [...new Set([...days.map(d => d.day), ...(Y.days || [])])].sort((a, b) => a - b);
    const show = (r, v) => r.unit === "$" ? `$${v.toFixed(r.decimals)}` : `${v.toFixed(r.decimals)}${r.unit || ""}`;
    const has = r => (r.values || []).some(v => v.value != null);
    const rows = all.filter(has).map(r => {
      const vals = r.values.filter(v => v.value != null), max = Math.max(...vals.map(v => v.value), r.baseline || 0) || 1;
      const cells = cols.map(day => {
        const v = r.values.find(x => x.day === day);
        if (!v || v.value == null) return { day, text: "·", h: 0, over: false, t: `${r.name} · Day ${day}`,
          b: [v && v.text ? v.text : day === current ? `Day ${day} is in progress: it is counted at its close.` : `Not counted for Day ${day}.`] };
        const over = r.baseline != null && v.value > r.baseline;
        return { day, value: v.value, text: show(r, v.value), h: v.value ? Math.max(0.06, v.value / max) : 0.03, over,
          t: `${r.name} · Day ${day}: ${show(r, v.value)}` + (r.baseline != null ? `${over ? ", above" : ", within"} the baseline of ${show(r, r.baseline)}` : ""), b: [v.text || ""] };
      });
      return { key: r.key, name: r.name, cells, line: r.baseline != null ? r.baseline / max : null, base: r.baseline != null ? show(r, r.baseline) : "",
        over: cells.filter(c => c.over).length, n: vals.length, last: vals[vals.length - 1],
        note: r.baseline != null ? `kit's baseline: ${show(r, r.baseline)}` : `no baseline${YARD_HINT[r.key] ? `; ${YARD_HINT[r.key]}` : ""}`, show: v => show(r, v) };
    });
    const waiting = all.filter(r => !has(r)).map(r => ({ name: r.name, why: ((r.values || []).filter(v => v.text).pop() || {}).text || "nothing is counted yet" }));
    const based = rows.filter(r => r.line != null);
    return { cols, rows: rows.map(({ show: _, last: __, ...r }) => r), waiting,
      read: { t: !rows.length ? "No yardstick is counted yet" : based.length ? "Above the kit's baseline " + based.map((r, i) => `${i ? "and " : ""}on ${r.over} of ${plural(r.n, "day", "days")} for ${r.key}`).join(", ")
          : `${plural(rows.length, "yardstick", "yardsticks")}, counted at each day's close`,
        b: [based.map(r => `${r.name}: ${r.show(r.last.value)} on Day ${r.last.day}, against ${r.base} with a person driving every step.`).join(" ")
          + ((Y.problems || []).length ? ` ${plural(Y.problems.length, "cell", "cells")} could not be read.` : "")].filter(s => s.trim()) },
      table: { head: ["Yardstick", "Kit's baseline", ...cols.map(d => `Day ${d}`)], rows: rows.map(r => [r.name, r.base, ...r.cells.map(c => c.value == null ? "" : c.text)]) } };
  }

  function attention() {
    const groups = [];
    (DATA.attention || []).forEach(a => {
      const label = REASONS[a.reason] || a.reason, detail = a.detail || "";
      const g = groups.find(x => x.label === label && x.detail === detail) || groups[groups.push({ label, detail, ids: [] }) - 1];
      g.ids.push(a.id);
    });
    return { total: (DATA.attention || []).length, groups };
  }

  function notMeasured(yard) {
    const I = DATA.infra || {};
    return [!I.latest && !(I.runs || []).length && ["Infrastructure checks", "no run is recorded, so nothing is drawn."],
      !DATA.deployment && ["The live deployment", "no run is recorded, so nothing is drawn."],
      ...((yard.waiting || []).map(w => [w.name, `${w.why}.`])),
      ["Where a day's time goes, and who waits for whom", "the times of sessions, pull requests and checks are not collected yet. It will be the ninth graph."]].filter(Boolean);
  }

  const P = safe(promises), g8 = safe(yardGraph);
  return { head: head(), days: days.map(d => ({ day: d.day, title: plain(d.title), closed: finished(d), active: d.day === current })),
    attention: attention(), g1: safe(abilityGraph), g2: P.error ? P : P.board, g3: P.error ? P : safe(() => reliedGraph(P)), g4: safe(mergeGraph), g5: safe(sieveGraph),
    g6: safe(costGraph), g7: safe(workGraph), g8, promises: P.error ? { counts: [] } : { counts: COUNTED.map(s => [s, P.n(P.tiles, s)]).filter(c => c[1]), total: P.counted(P.tiles) },
    caveats: (DATA.meta || {}).caveats || [], notMeasured: notMeasured(g8) };
}

/* ---------- how this works: one promise, followed through its steps ---------- */
const howHas = x => Boolean(x && x.text && !x.missing);
function howMissing(x) {
  return `<span class="how-missing">Missing from this build: ${esc((x && x.source) || "this excerpt")} (${esc((x && x.missing) || "not in this data")})</span>`;
}
function howExcerpt(x, caption) {
  const body = howHas(x) ? `<pre>${esc(x.text)}</pre>` : howMissing(x);
  return `<figure class="how-ex"><figcaption>${esc(caption)}</figcaption>${body}</figure>`;
}
function howRecheck(x, id) {
  if (!howHas(x)) return howExcerpt(x, "The latest re-check");
  if (!x.text.checks.length) return `<figure class="how-ex"><figcaption>${esc(id)}</figcaption><pre>not re-checked yet</pre></figure>`;
  return `<figure class="how-ex"><figcaption>${esc(id)} at its latest re-check${x.text.pr ? `, the merge of PR #${x.text.pr}` : ""}</figcaption><pre>${x.text.checks.map(c => `${esc(c.check)} → <span class="put">${esc(c.state)}</span>`).join("\n")}</pre></figure>`;
}
const HOW_BLOB = "https://github.com/Yusuprozimemet/agentic-workflow-driver/blob/main/";
const HOW_PLAN_GLOSS = {
  "Short answer": "Can the human leave the loop, and what must stay with them.",
  "Who does what": "The maintainer, the driver and the sessions.",
  "When the driver parks": "The reasons the driver stops and waits for a person.",
  Phases: "Groups of days, each with one goal.",
  "Stopping points": "Where work halts until the maintainer lifts the stop.",
};
const HOW_SPEC_GLOSS = {
  Goal: "What is true at the end of the day that was not at the start.",
  "In scope": "What this day builds.",
  "Out of scope": "What it leaves, and which day owns it.",
  Tracks: "The work, split into pull requests that can each be reviewed alone.",
  "Acceptance criteria": "The day's promises: step 3.",
  Verify: "Commands anyone can run from the repository alone.",
  Notes: "What went wrong and what was handed on, written at the close.",
};
const HOW_CAST = [
  ["The maintainer", "A person. Owns the plan and, today, merges every pull request.", "bug"],
  ["Main AI session", "Usually writes the specs and briefs, reviews the code, plants the bugs and writes the pull requests.", "bug"],
  ["Implementer", "A smaller AI model. Usually writes code and tests from a brief, and never commits.", "red"],
  ["Plan-auditor", "At the start and end of a phase: is the plan still right for the code?", "goal"],
  ["Spec-auditor", "Before every day: is each claim true, and can each check fail?", "spec"],
  ["Defect-rater", "At every close: labels the day's mistakes without seeing the original labels.", "close"],
  ["Three end-of-phase auditors", "Security, agentic engineering and architecture. Run once, after the last phase in the plan.", "goal"],
];
// The excerpts are the build's own reading of the plan, the newest finished day's spec and its record; they go in
// as HTML through esc(). `tally` is graph 2's count of the re-checked promises, so the two cannot disagree.
function drawHow(DATA, tally) {
  const X = DATA.how_this_works || {}, criteria = DATA.criteria_index || [];
  const chosen = howHas(X.promise) ? X.promise.text : null, id = chosen ? chosen.id : "this promise";
  const value = x => howHas(x) ? esc(x.text) : howMissing(x);
  const src = (path, label) => `<a class="how-src" href="${HOW_BLOB}${path}" target="_blank" rel="noopener">Read ${esc(label || path)}</a>`;
  const anat = rows => `<dl class="how-anat">${rows.map(([k, g, v]) => `<div><dt>${esc(k)}</dt><dd><span>${esc(g)}</span>${v ? `<span class="mono">${v}</span>` : ""}</dd></div>`).join("")}</dl>`;
  const promise = criteria.find(c => c.id === id);
  document.getElementById("how-route").innerHTML = `Below is the route one real promise took: <strong>${promise ? esc(promise.plain || promise.claim) : howMissing(X.promise)}</strong> Select a step to see what happened there.`;
  document.getElementById("how-path").innerHTML = howHas(X.crumbs) ? X.crumbs.text.map(c => `<b>${esc(c)}</b>`).join("›") : howMissing(X.crumbs);

  const planParts = howHas(X.plan_parts) ? anat(X.plan_parts.text.map(p => [p, HOW_PLAN_GLOSS[p] || ""])) : howMissing(X.plan_parts);
  const dayValues = { Goal: X.day_goal, "Out of scope": X.day_out_of_scope, Tracks: X.day_tracks, "Acceptance criteria": X.day_criteria };
  const specParts = howHas(X.template_parts)
    ? anat(X.template_parts.text.map(p => [p, HOW_SPEC_GLOSS[p] || "", dayValues[p] ? value(dayValues[p]) : ""])) : howMissing(X.template_parts);
  const bugs = howHas(X.bugs) ? X.bugs.text.map((b, i) => `<figure class="how-ex"><figcaption>Planted bug ${i + 1}, in ${esc(b.file)}: ${esc(b.what)}</figcaption><pre><span class="gone">${esc(b.find)}</span>\n<span class="put">${esc(b.replace)}</span>\n<span class="out">The test reported → ${esc(b.reported)}</span></pre></figure>`).join("")
    : howExcerpt(X.bugs, "The planted bugs");
  const tick = howHas(X.tick) && howHas(X.evidence) ? { source: X.tick.source, text: `${X.tick.text}\n      Evidence: ${X.evidence.text}` } : howHas(X.tick) ? X.evidence : X.tick;
  const recheck = howRecheck(X.recheck, id);
  const bad = sum(tally.counts.filter(c => c[0] === "broken" || c[0] === "repair"), c => c[1]);
  const counted = !tally.counts.length ? "<p>No re-check of the promises is on record.</p>"
    : `<p>All ${plural(tally.total, "promise", "promises")} at their latest re-check:</p>`
      + `<div class="how-bar" role="img" aria-label="${tally.counts.map(([s, n]) => `${n} ${lower(STATES[s].word)}`).join(", ")}">${tally.counts.map(([s, n]) => `<i class="tile ${s}" style="--n:${n}"></i>`).join("")}</div>`
      + `<div class="how-barkey">${tally.counts.map(([s, n]) => `<span><i class="tile ${s}">${STATES[s].glyph || ""}</i><div><b>${n}</b> ${esc(STATES[s].word)}: ${esc(STATES[s].means)}</div></span>`).join("")}</div>`
      + `<p>${bad ? `${plural(bad, "promise needs", "promises need")} attention.` : "None is broken."} This check is run by hand, so it can lag behind the newest change.</p>`;

  const STEPS = [
    { id: "goal", kind: "doc", name: "The goal", line: "What we want built, in phases", gate: "<b>plan-auditor</b>, at a phase's start and end, asks: do the days still add up to the goal?",
      body: `<p>One document says what the whole project is for, what stays with a person, and the order of the work. It rarely changes. There is only one plan, so it has no template. These are some of the sections it contains.</p>${planParts}`
        + howExcerpt(X.plan_phase, "Where it was scheduled: plan.md") + src("plan.md") },
    { id: "spec", kind: "doc", name: "A day's spec", line: "One day's work, written down first", gate: "<b>spec-auditor</b> runs every check on the code as it is and tries to prove each claim wrong",
      body: `<p>Each day gets one file, filled in from the same template. The template forces the awkward questions early: what is left out, and who picks it up.</p>${specParts}` + src("specs/_template.md", "the template") + (chosen ? src(chosen.spec, `Day ${chosen.day}'s spec`) : "") },
    { id: "promise", kind: "doc", name: "A promise", line: "One sentence someone else can check", gate: "",
      body: `<p>A promise is what the specs call an <em>acceptance criterion</em>. It must be checkable by someone who did not write the code. It is tagged <strong>new</strong> if the behaviour does not exist yet, or <strong>hold</strong> if it is true today and must stay true.</p>`
        + howExcerpt(X.form, "The blank form, from the template") + `<p>Filled in, for this promise:</p>`
        + anat([[id, "The promise, as the spec words it.", value(X.claim)], ["Red today", "How it must fail before the work.", value(X.red_today)], ["Test", "The named tests that decide it.", value(X.test)]])
        + `<p>The spec stays the source of truth. The bold sentence above is only a rewording.</p>` },
    { id: "red", kind: "try", name: "A test that fails first", line: "Proof the behaviour isn't there yet", gate: "<b>implementer</b>, a smaller AI model, usually writes the code and tests from a brief. It never commits",
      body: `<p>The tests are written to the promise and run against the code as it stands. They have to fail, and fail the way the spec predicted. A test that passes on code that lacks the feature is testing nothing.</p>`
        + howExcerpt(X.seen_red, `What was recorded for ${id}`) + `<p>Compare it with the “Red today” line in step 3.</p>` },
    { id: "bug", kind: "try", name: "The code, then a planted bug", line: "Does the test actually notice?", gate: "<b>The maintainer</b> reviews and merges. Today nothing merges without a person",
      body: `<p>Once the tests pass, the finished code is sabotaged on purpose and they are run again. If they still pass, they would not have caught a real failure. The sabotage is undone and never merges.</p>${bugs}`
        + `<p>Each last line is what the test reported with the bug in place: the test failing is the good result. Automated checks also run on the pull request: style, every test, and a limit of 400 changed lines so it stays reviewable.</p>` + (chosen ? src(chosen.breaks, `Day ${chosen.day}'s planted bugs`) : "") },
    { id: "close", kind: "after", name: "The day closes", line: "Each tick cites its evidence", gate: "<b>defect-rater</b> labels the day's mistakes blind, to see if a second reader agrees",
      body: `<p>A last pull request ticks each promise and names what proves it. A box with no evidence stays unticked, with the reason written under it.</p>${howExcerpt(tick, `The tick on ${id}`)}`
        + `<ul><li>Mistakes go in the Notes, including the AI's own.</li><li>Automation replays the recorded evidence against the closing commit. If that fails, the next day does not start.</li></ul>` + src("docs/lab-notebook.md", "the lab notebook") },
    { id: "recheck", kind: "after", name: "The re-check", line: "Are the promises still true later?", gate: null,
      body: `<p>Code keeps changing after a day closes. So finished promises are tested again on later merged code, and the planted bugs are put back to see if the tests still notice.</p>${recheck}${counted}` + src("docs/dashboard/replay-history.json", "the re-check results") },
  ];
  const spine = document.getElementById("how-spine"), detail = document.getElementById("how-detail"), flow = document.getElementById("how-flow");
  const narrow = matchMedia("(max-width: 760px)"), stepOf = s => STEPS.find(x => x.id === s);
  spine.innerHTML = STEPS.map((s, i) => `<button type="button" class="how-step how-${s.kind}" id="how-step-${s.id}" data-how="${s.id}" aria-expanded="false" aria-controls="how-detail"><span class="how-dot">${i + 1}</span><span><strong>${s.name}</strong><small>${s.line}</small></span></button>`
    + (s.gate === null ? "" : `<div class="how-gate">${s.gate}</div>`)).join("");
  document.getElementById("how-cast").innerHTML = HOW_CAST.map(([who, what, s]) => `<button type="button" class="how-row" data-how="${s}"><strong>${who}</strong><span>${what}</span><em>Step ${STEPS.indexOf(stepOf(s)) + 1}: ${stepOf(s).name}</em></button>`).join("");
  let current = "promise";
  const place = () => {
    if (narrow.matches) document.getElementById("how-step-" + current).after(detail);
    else if (detail.parentElement !== flow) flow.append(detail);
  };
  const show = (s, scroll) => {
    current = s;
    spine.querySelectorAll(".how-step").forEach(b => b.setAttribute("aria-expanded", b.dataset.how === s));
    detail.innerHTML = `<div class="how-kicker">Step ${STEPS.indexOf(stepOf(s)) + 1} of ${STEPS.length}</div><h3>${stepOf(s).name}</h3>${stepOf(s).body}`;
    place();
    if (!scroll) return;
    document.getElementById("how-fold").open = true;
    document.getElementById("how-step-" + s).scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  };
  // A step link anywhere on the page (graph 2 has four) opens the walk-through at that step.
  document.addEventListener("click", e => {
    const b = e.target.closest && e.target.closest("[data-how]");
    if (b) { e.preventDefault(); show(b.dataset.how, !spine.contains(b)); }
  });
  narrow.addEventListener("change", place);
  const wanted = location.hash.startsWith("#how-step-") && location.hash.slice(10);
  show(stepOf(wanted) ? wanted : current, Boolean(stepOf(wanted)));
}

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

function draw(M, DATA) {
  const $ = id => document.getElementById(id);
  const put = (id, ...kids) => { const box = $(id); box.replaceChildren(...kids.flat(Infinity).filter(c => c != null && c !== false)); return box; };
  const marks = [], resets = [];
  const forDays = (node, ds) => { node.dataset.days = ds.join(" "); marks.push(node); return node; };

  // The readout under a graph: what the graph says as a whole, until a mark is pointed at, tapped or tabbed to.
  function reader(g, first) {
    let on = null;
    const say = r => put(`${g}-read`, h("strong", null, r.t), r.b.map(line => h("span", null, rich(line))));
    resets.push(() => { if (on) on.classList.remove("on"); on = null; say(first); });
    say(first);
    return (node, r) => {
      node.setAttribute("aria-label", r.t);
      const pick = () => { if (on === node) return; if (on) on.classList.remove("on"); on = node; node.classList.add("on"); say(r); };
      ["mouseenter", "focus", "click"].forEach(ev => node.addEventListener(ev, pick));
      return node;
    };
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
  const tile = (t, mark) => mark(h("button", { type: "button", class: `tile ${t.status}` }, t.glyph), t);
  const px = n => `${n.toFixed(1)}px`;

  /* the header */
  const H = M.head;
  $("eyebrow").textContent = [H.project, H.when && `read from git and GitHub on ${H.when}`, H.commit && `commit ${H.commit}`].filter(Boolean).join(" · ");
  const banner = $("demo-banner");
  banner.textContent = "Example data: this project has no day specs yet. The page will show real data after the first day spec merges.";
  banner.hidden = !H.demo;
  put("now", h("strong", null, "Now: "), H.now, " ", h("strong", null, "Next step: "), rich(H.next));
  const A = M.attention;
  $("attention").hidden = !A.total;
  put("attention-n", `Needs attention: ${plural(A.total, "item", "items")}`);
  put("attention-list", A.groups.map(g => h("li", null, h("b", null, `${g.label} (${g.ids.length})`), " ", g.detail ? [rich(g.detail), ": "] : null, g.ids.join(", "))));

  /* the day buttons: one day lit in every graph */
  let lit = null;
  const chips = [null, ...M.days.map(d => d.day)].map(day => h("button", { type: "button", "aria-pressed": day === null ? "true" : "false" }, day === null ? "All days" : `Day ${day}`));
  chips.forEach((chip, i) => chip.addEventListener("click", () => {
    lit = i ? M.days[i - 1].day : null;
    chips.forEach((c, j) => c.setAttribute("aria-pressed", j === i ? "true" : "false"));
    marks.forEach(node => node.classList.toggle("dim", lit !== null && !node.dataset.days.split(" ").includes(String(lit))));
  }));
  put("days", h("span", null, "Highlight one day in every graph:"), chips);

  /* Graph 1 */
  graph("g1", (m, mark) => {
    const line = (name, cells, cls) => h("div", { class: `g1-row ${cls || ""}` }, h("div", { class: "g1-name" }, name), h("div", { class: "g1-cells" }, cells));
    const col = c => c.day == null ? [] : [c.day];
    put("g1-plot", line("Day", m.cols.map(c => forDays(h("div", { class: "g1-h" }, c.label), col(c))), "head"),
      line("Closed", m.cols.map(c => forDays(h("div", { class: "g1-h mark" }, c.mark), col(c))), "head"),
      m.rows.map(r => line(r.name, r.cells.map(c => forDays(mark(h("button", { type: "button", class: `g1-cell s${c.level}` }, c.n ? String(c.n) : "·"), c), col(c))))));
    key("g1-key", [["", "Pull requests:"], ["sw s1", "1–2"], ["sw s2", "3–5"], ["sw s3", "6–9"], ["sw s4", "10 or more"]]);
  });

  /* Graph 2 */
  graph("g2", (m, mark) => {
    $("g2-say").textContent = m.say;
    key("g2-key", m.key.map(k => [`tile ${k.status}`, k.text, k.glyph]));
    put("g2-plot", m.rows.map(r => forDays(h("div", { class: "board-row" }, h("div", { class: "board-day" }, `Day ${r.day}`),
      h("div", { class: "tiles" }, r.tiles.map(t => tile(t, mark))), h("div", { class: "board-count" }, r.count)), [r.day])));
    $("g2-hist-say").textContent = m.histSay;
    put("g2-hist", m.hist.map(x => mark(h("button", { type: "button", class: "strip-col" },
      ["skipped", "broken", "repair", "unproven", "proven"].map(s => h("span", { class: s, style: `height:${px(x.counts[s] * 48 / m.histMax)}` }))), x)));
    $("g2-hist").hidden = !m.hist.length;
  });

  /* Graph 3 */
  graph("g3", (m, mark) => {
    put("g3-plot", m.rows.map(r => h("div", { class: "ab-row" }, h("div", { class: "ab-name" }, r.name),
      h("div", { class: "ab-groups" }, r.groups.map(g => forDays(h("div", { class: "ab-group" }, h("span", { class: "mono" }, `D${g.day}`),
        h("div", { class: "tiles" }, g.tiles.map(t => tile(t, mark)))), [g.day])), r.note && h("span", { class: "ab-note" }, r.note)),
      h("div", { class: "ab-count" }, r.count))));
  });

  /* Graph 4 */
  graph("g4", (m, mark) => {
    const TOP = 200, ALL = 280, n = Math.max(1, m.merges.length);
    $("g4-say").textContent = m.say;
    key("g4-key", m.key.map(([k, text]) => [`pt ${k}`, text]));
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path"), svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    path.setAttribute("d", m.merges.filter(x => x.y != null).map((x, i) => `${i ? "L" : "M"}${(m.merges.indexOf(x) + 0.5).toFixed(1)},${(x.y * TOP).toFixed(1)}`).join(" "));
    svg.setAttribute("viewBox", `0 0 ${n} ${TOP}`); svg.setAttribute("preserveAspectRatio", "none"); svg.setAttribute("aria-hidden", "true"); svg.append(path);
    const axis = h("div", { class: "g4-axis" }, h("span", { style: "top:0" }, "Day"), m.ticks.map(t => h("span", { style: `top:${px(22 + t.y * TOP - 7)}` }, t.label)),
      m.barTicks.map(t => h("span", { style: `top:${px(22 + ALL - t.h * 60 - 7)}` }, t.label)));
    const bands = h("div", { class: "g4-bands" }, m.bands.map((b, i) => forDays(h("div", { class: i % 2 ? "odd" : "", style: `flex-grow:${b.n}` }, b.day ? String(b.day) : "–"), b.day ? [b.day] : [])));
    const cols = h("div", { class: "g4-cols" }, m.merges.map(x => forDays(mark(h("button", { type: "button", class: "g4-col" },
      x.y != null && h("span", { class: `pt ${x.kind}`, style: `top:${px(x.y * TOP)}` }), x.failed && h("span", { class: "pt failed" }),
      h("span", { class: "open-bar", style: `height:${px(x.h * 60)}` })), x), x.day ? [x.day] : [])));
    const lines = [...m.ticks.map(t => t.y * TOP), TOP, ...m.barTicks.slice(1).map(t => ALL - t.h * 60), ALL].map((y, i, a) => h("div", { class: `g4-line${y === TOP || i === a.length - 1 ? " strong" : ""}`, style: `top:${px(y)}` }));
    put("g4-plot", h("div", { class: "g4", style: `min-width:${Math.max(820, n * 9)}px` }, axis, h("div", { class: "g4-main" }, bands, h("div", { class: "g4-area" }, lines, svg, cols))));
  });

  /* Graph 5 */
  graph("g5", (m, mark) => {
    $("g5-say").textContent = m.say;
    key("g5-key", [["", "Cause:"], ...m.key.map(k => [k.cls, k.text])]);
    put("g5-plot", h("div", { class: "sieve" },
      h("div", { class: "sieve-row head" }, h("div", { class: "sieve-day" }), h("div", { class: "sieve-gates" }, m.gates.map(g => h("div", { class: "sieve-gate" }, h("strong", null, g.name), h("span", null, g.sub)))),
        h("div", { class: "sieve-note" }, "Tags a second reader gave differently")),
      m.rows.map(r => forDays(h("div", { class: "sieve-row" }, h("div", { class: "sieve-day" }, `Day ${r.day}`),
        h("div", { class: "sieve-gates" }, r.cells.map(list => h("div", { class: "sieve-cell" }, list.map(o => mark(h("button", { type: "button", class: `dot ${o.cause}${o.escaped ? " square" : ""}${o.back ? " ring" : ""}` }), o))))),
        h("div", { class: "sieve-note mono" }, r.note)), [r.day]))));
  });

  /* Graphs 6 and 7: stacked bars over a shared baseline, with rows of counts under them */
  function bars(g, m, mark, items, parts, under) {
    const H = 150;
    const stack = x => parts.map(([cls, value]) => [cls, value(x) / m.max * H]).filter(p => p[1] >= 1).map(([cls, hgt], i) => h("span", { class: `seg ${cls}${i ? "" : " cap"}`, style: `height:${Math.max(2, Math.round(hgt))}px` }));
    put(`${g}-plot`, h("div", { class: "bars" }, items.map(x => forDays(mark(h("button", { type: "button", class: "bar" }, h("b", null, x.top), stack(x)), x), x.lit))),
      h("div", { class: "bar-labels" }, items.map(x => forDays(h("div", null, x.under), x.lit))),
      under.map(([name, value]) => h("div", { class: "bar-extra" }, h("p", null, name), h("div", { class: "mono" }, items.map(x => forDays(h("div", null, value(x)), x.lit))))));
  }
  graph("g6", (m, mark) => {
    $("g6-say").textContent = m.say;
    key("g6-key", m.key.map(([k, text]) => [`sw ${k}`, text]));
    bars("g6", m, mark, m.bars.map(x => ({ ...x, top: `$${Math.round(x.total)}`, under: x.label, lit: x.days })), [["rest", x => x.aud + x.other], ["main", x => x.main]],
      [["Calls the hooks refused", x => x.refused ? String(x.refused) : "·"], ["Long outputs the hooks cut short", x => x.cut ? String(x.cut) : "·"]]);
  });
  graph("g7", (m, mark) => {
    key("g7-key", m.key.map(([k, text]) => [`sw ${k}`, text]));
    bars("g7", m, mark, m.bars.map(x => ({ ...x, top: x.label, under: String(x.day), lit: [x.day] })), [...m.key].reverse().map(([k]) => [k, x => x.w[k]]),
      [["Pull requests merged", x => String(x.prs)], ["Test lines for each production line", x => x.ratio]]);
  });

  /* Graph 8 */
  graph("g8", (m, mark) => {
    key("g8-key", [["sw main", "At or under the kit's baseline, or no baseline"], ["sw over", "Above the kit's baseline"], ["dash", "Baseline"]]);
    put("g8-plot", h("div", { class: "yard" },
      h("div", { class: "yard-row head" }, h("div", { class: "yard-name" }), h("div", { class: "yard-cells" }, m.cols.map(d => forDays(h("div", null, `Day ${d}`), [d]))), h("div", { class: "yard-note" })),
      m.rows.map(r => h("div", { class: "yard-row" }, h("div", { class: "yard-name" }, r.name),
        h("div", { class: "yard-cells" }, r.cells.map(c => forDays(mark(h("button", { type: "button", class: "yard-cell" }, h("b", null, c.text), h("span", { class: c.over ? "over" : "", style: `height:${px(c.h * 34)}` })), c), [c.day])),
          r.line != null && h("div", { class: "yard-line", style: `bottom:${px(r.line * 34)}` })),
        h("div", { class: "yard-note" }, r.note))),
      m.waiting.map(w => h("div", { class: "yard-row" }, h("div", { class: "yard-name" }, w.name), h("div", { class: "yard-wait" }, h("span", null, "Not measured yet: ", rich(w.why))), h("div", { class: "yard-note" }, "draws here once it is counted")))));
  });

  /* the foot of the page */
  put("caveats", M.caveats.map(c => h("li", null, rich(c))));
  put("not-measured", M.notMeasured.map(([name, why]) => h("li", null, h("b", null, name), ": ", rich(why))));
  try { drawHow(DATA, M.promises); } catch (e) { console.error(`how this works: ${(e && e.message) || e}`); }
  document.addEventListener("keydown", e => { if (e.key === "Escape") resets.forEach(r => r()); });
}

function boot(DATA) {
  draw(model(DATA), DATA);
}

function start() {
  if (window.SPEC_DRIFT) return boot(window.SPEC_DRIFT);
  document.getElementById("now").textContent = "The data did not load. Build the page with python scripts/spec-drift.py --build dashboard.html; if this is the built page, it was published without its data line.";
}
