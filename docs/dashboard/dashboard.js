// The dashboard in ten graphs. Each answers one question, folds what used to be several panels into
// its marks, and says the detail in the readout under it. model() reads the data and touches no
// document, so a test can run it; draw() puts what it returns on the page.

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
// A Defect line's found: or cause: value as scripts/spec-drift.py's gate_report reads it: older Notes write
// "The auditor (spec-auditor)". scripts/test_dashboard_page.py holds the two to the same values.
const tagOf = v => String(v == null ? "" : v).trim().toLowerCase().replace(/^the /, "").replace(/ \(.*\)$/, "");
// Minutes covered by a list of [from, to] intervals, a minute two of them share counted once.
const covered = list => [...list].sort((a, b) => a[0] - b[0]).reduce((acc, [a, b]) => ({ n: acc.n + Math.max(0, b - Math.max(a, acc.end)), end: Math.max(acc.end, b) }), { n: 0, end: -Infinity }).n;
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
  building: { word: "Not yet in force", means: "its Day is still being built" },
  open: { word: "Left unticked", means: "its Day closed without ticking it" },
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
const KINDS = { origin: "the first commit", spec: "spec", code: "code", close: "a Day's close", other: "other" };
const WORK = [["spec", "Spec and agent context"], ["prod", "Production code"], ["test", "Tests"], ["tooling", "Tooling"]];
const REASONS = { replay_failed: "Replay failed", replay_error: "Replay error", replay_stale: "Replay stale",
  evidence_missing: "Evidence missing", not_seen_red: "Not seen red", test_not_found: "Test not found", handoff_unclaimed: "Hand-off unclaimed",
  not_breakable: "No break possible from the repository", test_skippable: "Can be skipped in CI (expected)",
  handoff_next: "Hand-off for the next Day", handoff_unpicked: "Hand-off no later Day picks up" };
const YARD_HINT = { escapes: "fewer is better", refusals: "many of one kind mean a rule is in the way", reread: "re-reading is most of the cost",
  gates: "a gate run in the main session is also inside the pull requests' cost above" };

/* ---------- the model: what each graph draws and says, from the data alone ---------- */
function model(DATA) {
  const now = DATA.now || {}, days = [...(DATA.days || [])].sort((a, b) => a.day - b.day), current = now.current_day;
  const stories = (DATA.user_stories || {}).stories || [], named = (DATA.user_stories || {}).abilities || [];
  const abilityName = key => (named.find(a => a.key === key) || {}).name;
  const safe = fn => { try { return fn(); } catch (e) { return { error: String((e && e.message) || e) }; } };
  const done = days.filter(finished).map(d => d.day);
  const daysSay = (done.length ? `${daySpan(done)} ${done.length === 1 ? "is" : "are"} closed` : "No Day is closed yet")
    + (current != null ? ` and Day ${current} is in progress.` : ".");
  // The dollars, refusals, gate runs and sessions are counted on the maintainer's computer and end at that count
  // (docs/dashboard/counted.json); the pull requests come from GitHub and go on. What sets one against the other
  // takes only the pull requests merged by then. With no count on record, nothing is left out and nothing is claimed.
  const countedAt = (DATA.counted || {}).at || null, countedMs = countedAt ? Date.parse(countedAt) : null;
  const countedSay = countedAt ? `${countedAt.slice(11, 16)} on ${shortDate(countedAt)}` : "";
  const TIMES = ((DATA.clock || {}).prs || []).filter(p => p.opened && p.merged);
  const mergedAt = new Map(TIMES.map(p => [p.number, Date.parse(p.merged)]));
  const inCount = pr => countedMs == null || !mergedAt.has(pr) || mergedAt.get(pr) <= countedMs;
  const dayInCount = day => countedMs == null || !TIMES.some(p => p.day === day && Date.parse(p.merged) > countedMs);
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

  function head() {
    const g = now.generated || "", when = g.length >= 16 ? `${shortDate(g)} ${g.slice(0, 4)} at ${g.slice(11, 16)}` : g;
    // A Day is a step of the plan and not a calendar day: how many dates the closed Days' own pull requests ran over says so.
    // `worked` is a Day's first and last merge date; a pull request outside any Day that merged between two Days is not its work.
    const closed = days.filter(d => finished(d) && (d.worked || []).length === 2), dates = new Set();
    closed.forEach(d => { for (let t = Date.parse(d.worked[0]); t <= Date.parse(d.worked[1]); t += 86400000) dates.add(t); });
    const took = closed.length ? `${daySpan(closed.map(d => d.day))} took ${plural(dates.size, "date", "dates")}` : "";
    return { project: (DATA.meta || {}).project || "", when, commit: String(now.head || "").slice(0, 7), demo: DATA.demo === true,
      now: daysSay, next: String(now.next_step || ""), open: (now.open_prs || []).length, took };
  }

  /* Graph 3: ability by day */
  function abilityGraph() {
    const keyOf = s => named.some(a => a.key === s.ability) ? s.ability : null;
    const rowsOf = [...named, ...(stories.some(s => keyOf(s) === null) ? [{ key: null, name: "No ability named" }] : [])];
    const cols = [...days.map(d => ({ day: d.day, label: String(d.day), mark: finished(d) ? "✓" : d.day === current ? "now" : "" })),
      { day: null, label: "No Day", mark: "" }];
    const colOf = s => days.some(d => d.day === s.day) ? s.day : null;
    const rows = rowsOf.map(a => ({ name: a.name, cells: cols.map(c => {
      const prs = stories.filter(s => keyOf(s) === a.key && colOf(s) === c.day).map(s => s.number).sort((x, y) => x - y), n = prs.length;
      const b = n ? `${plural(n, "merged pull request", "merged pull requests")} grew this ability ${c.day == null
          ? "between the Days, as tooling and dashboard work, not as a Day's track" : `on Day ${c.day}`}: ${prs.map(p => "#" + p).join(", ")}.`
        : c.day == null ? "Every pull request for this ability belongs to a Day." : `No pull request grew this ability on Day ${c.day}.`;
      return { day: c.day, n, level: n >= 10 ? 4 : n >= 6 ? 3 : n >= 3 ? 2 : n >= 1 ? 1 : 0, t: `${a.name} · ${c.day == null ? "outside any Day" : `Day ${c.day}`}`, b: [b] };
    }) }));
    const H = DATA.hand_offs || [], mine = H.filter(h => h.to === current), later = H.filter(h => current != null && h.to > current);
    const notes = [mine.length && `${mine.filter(h => h.picked).length} of the ${plural(mine.length, "note", "notes")} earlier Days left for Day ${current} ${mine.length === 1 ? "was" : "were"} picked up`,
      later.length && `${later.length} more wait for ${daySpan([...new Set(later.map(h => h.to))].sort((a, b) => a - b))}, ${later.filter(h => h.id).length || "none"} of them numbered`].filter(Boolean);
    return { cols, rows,
      read: { t: stories.length ? `${plural(stories.length, "merged pull request", "merged pull requests")}, each tagged with the ability it grew` : "No merged pull request yet",
        b: [daysSay + (notes.length ? ` ${notes.join("; ")}.` : "") + (now.stop_after != null ? ` The plan stops for the maintainer after Day ${now.stop_after}.` : "")] },
      table: { head: ["Ability", ...cols.map(c => c.day == null ? c.label : `Day ${c.label}`), "All"],
        rows: rows.map(r => [r.name, ...r.cells.map(c => c.n), sum(r.cells, c => c.n)]) } };
  }

  /* The promises: one reading for graphs 4 and 5, so they cannot disagree. Each promise takes the state of
     its newest re-check; one whose day is unfinished, or that a later promise replaced, is drawn and not counted. */
  function promises() {
    const rp = DATA.replay || {}, index = DATA.criteria_index || [], byDay = new Map(days.map(d => [d.day, d]));
    const merges = [...(rp.merges || [])].sort((a, b) => a.n - b.n), byN = new Map(merges.map(m => [m.n, m]));
    const cells = [...(rp.cells || [])].sort((a, b) => a.n - b.n), latest = new Map(cells.map(c => [c.criterion, c]));
    const age = pr => pr == null || now.last_pr == null ? "" : pr >= now.last_pr ? ", the latest change" : `, ${plural(now.last_pr - pr, "change", "changes")} ago`;
    const atClose = new Set(days.flatMap(d => d.broken_at_close || []));
    // An open Day's promises get their abilities only at its close: until then graph 1 says which pull request built each one.
    const builtBy = new Map(((DATA.look_ahead || {}).columns || []).filter(c => c.pr != null).flatMap(c => (c.got || []).map(id => [id, c.pr])));
    const abilityOf = pr => { const s = stories.find(x => x.number === pr), a = s ? s.ability : null; return named.some(k => k.key === a) ? [a] : []; };
    const tiles = index.map(c => {
      const day = byDay.get(c.day), cell = latest.get(c.id), look = (cell && REPLAY_LOOK[cell.state]) || {};
      const pr = builtBy.get(c.id) || null, abilities = (c.abilities || []).length ? c.abilities : abilityOf(pr);
      const status = !day || !finished(day) ? "building" : (c.replaced_by || []).length ? "replaced" : c.ticked === false ? "open" : look.group || "unchecked";
      const why = status === "replaced" ? `by ${c.replaced_by.join(", ")}` : status === "building" ? `Day ${c.day} is still being built`
        : (COUNTED.includes(status) && look.why) || STATES[status].means;
      const seen = c.seen_red || {}, mark = (ok, yes, no) => ok ? `✓ ${yes}` : `✕ ${no}`;
      const lines = [c.plain || c.claim || ""];
      if (status === "building" && !c.ticked) lines.push(pr ? `Built by pull request #${pr}. No evidence yet: the Day is not closed.` : "No evidence yet: the Day is not closed.");
      else lines.push([mark(c.ticked, "ticked at the close", "not ticked"), mark(c.cited, "cites its pull request", "cites no pull request"),
        mark(c.test_found, "names a test that exists", "names no test that exists"),
        seen.state ? "✓ a failure was recorded when it was built" : seen.state === false && (seen.none || []).length ? `– no failure could be planted: ${seen.none.join("; ")}`
          : seen.state === false ? "✕ no failure recorded when built" : "– a failure when built was not measured"].join(" · ")
        + (atClose.has(c.id) ? " · its check was first seen failing at the close, not in the pull request that wrote it" : ""));
      const m = cell && byN.get(cell.n), grows = abilities.map(abilityName).filter(Boolean);
      const last = [COUNTED.includes(status) && m ? `Last re-checked after pull request #${m.pr}${age(m.pr)}${cell.mixed ? "; its checks disagree" : ""}.` : "",
        grows.length ? `It grew “${grows[0]}”${grows.length > 1 ? `, and also ${andList(grows.slice(1).map(g => `“${g}”`))}` : ""}.` : ""].filter(Boolean).join(" ");
      if (last) lines.push(last);
      return { id: c.id, day: c.day, status, abilities, built_by: pr, glyph: STATES[status].glyph || "",
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

  /* Graph 5: each ability with the promises its pull requests built */
  function reliedGraph(P) {
    const groupsOf = list => [...new Set(list.map(t => t.day))].sort((a, b) => a - b).map(day => ({ day, tiles: list.filter(t => t.day === day) }));
    const rows = named.map(a => {
      const mine = P.tiles.filter(t => t.abilities[0] === a.key), own = stories.filter(s => s.ability === a.key), c = P.counted(mine);
      return { name: a.name, tiles: mine, groups: groupsOf(mine), prs: own.length, proven: P.n(mine, "proven"), counted: c,
        note: mine.length ? "" : own.length && own.every(s => s.day == null) ? "No promise covers this ability. Its pull requests are work outside the Day specs." : "No promise covers this ability yet.",
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
      shared && `${plural(shared, "promise touches", "promises touch")} more than one ability and ${shared === 1 ? "is" : "are"} drawn under the one most of ${shared === 1 ? "its" : "their"} pull requests grew, the first named when they tie.`].filter(Boolean);
    const cols = ["proven", "unproven", "repair", "broken", "skipped", "replaced", "building"];
    return { rows,
      read: { t: ranked.length && ranked[0].proven ? `“${ranked[0].name}” is the best proven: ${ranked[0].proven} of its ${plural(ranked[0].counted, "re-checked promise", "re-checked promises")}` : "No ability has a proven promise yet", b: [b.join(" ")].filter(Boolean) },
      table: { head: ["Ability", "Promises", ...cols.map(s => STATES[s].word), "Pull requests"],
        rows: rows.map(r => [r.name, r.tiles.length, ...cols.map(s => P.n(r.tiles, s)), r.prs]) } };
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
      withPr.length ? `${nFailed} of ${plural(withPr.length, "pull request", "pull requests")} had a check fail before ${withPr.length === 1 ? "it" : "they"} merged.` : ""].filter(Boolean);
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

  /* Graph 7: the sieve. Each defect at the gate that caught it */
  function sieveGraph() {
    const spent = new Map(((DATA.gate_report || {}).gates || []).filter(g => g.found).map(g => [g.found, g]));
    const back = new Map((((DATA.defect_recurrence || {}).recurrences) || []).map(r => [r.id, r.same_as]));
    const rows = days.map(d => {
      const dots = (d.defects || []).map((x, i) => {
        const gate = GATES.find(g => g.key === tagOf(x.found)) || GATES[3], cause = CAUSES.includes(tagOf(x.cause)) ? tagOf(x.cause) : "other";
        const m = /^Day 0*(\d+)$/i.exec(x.made || ""), made = m ? +m[1] : null, escaped = made != null && made !== d.day;
        const where = escaped ? `Made on Day ${made} and caught on Day ${d.day}` + (made < d.day ? `: it escaped for ${plural(d.day - made, "Day", "Days")}.` : ".")
          : made != null ? `Made and caught on Day ${d.day}.` : /^none$/i.test(x.made || "") ? "Made outside any Day: in the plan, a tool or a machine."
          : `Caught on Day ${d.day}; its line does not say which Day made it.`;
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
    // A gate's dollars end at the count, so they are shared over the catches of the Days whose pull requests were all merged by then.
    const late = rows.filter(r => r.dots.length && !dayInCount(r.day)).map(r => r.day), inAt = k => rows.filter(r => !late.includes(r.day)).flatMap(r => r.dots).filter(o => o.gate === k).length;
    const each = GATES.map(g => [g, spent.get(g.key)]).filter(([g, s]) => s && s.cost > 0 && inAt(g.key)).map(([g, s]) => [s.cost / inAt(g.key), g.at]).sort((a, b) => a[0] - b[0]);
    const read = rows.filter(r => r.tags), nEsc = all.filter(o => o.escaped).length, nBack = all.filter(o => o.back).length;
    const b = [by("spec") ? `${by("spec")} ${by("spec") === 1 ? "was" : "were"} in a spec.` : "",
      `${nEsc} escaped from an earlier Day and ${nBack} came back.`,
      read.length ? `A second reader gave ${sum(read, r => r.differ)} of ${sum(read, r => r.tags)} tags differently.` : "",
      each.length ? `Each catch cost about ${andList(each.map(([c, name]) => `${money(c)} at ${name}`))}${late.length ? `, over the catches of the Days in the count: ${daySpan(late)} had a pull request merge after it` : ""}.` : "",
      countedAt && spent.size ? `The gates' runs and dollars are counted up to ${countedSay}.` : ""].filter(Boolean);
    return { gates, rows,
      key: [...CAUSES.filter(c => c !== "other" || by(c)).map(c => ({ cls: `dot ${c}`, text: `${c.charAt(0).toUpperCase() + c.slice(1)} ${by(c)}` })),
        { cls: "dot ring", text: `Ringed: the same problem came back ${nBack}` }, { cls: "dot square", text: `Square: made on an earlier Day ${nEsc}` }],
      say: `Each dot is one defect from a Day's Notes, ${all.length} in all, placed at the gate that caught it. Work passes the gates from left to right, so a dot further right was caught later.`,
      read: { t: !all.length ? "No defect is recorded yet" : at("auditor") ? `${plural(all.length, "defect", "defects")}; the auditors caught ${at("auditor")} of them before any code was written` : `${plural(all.length, "defect", "defects")} in the Days' Notes`,
        b: all.length ? [b.join(" ")] : [] },
      table: { head: ["Day", ...GATES.map(g => g.name), ...CAUSES.map(c => `Cause: ${c}`), "Escaped", "Came back", "Tags read differently", "Tags"],
        rows: rows.map(r => [`Day ${r.day}`, ...r.cells.map(c => c.length), ...CAUSES.map(c => r.dots.filter(o => o.cause === c).length),
          r.dots.filter(o => o.escaped).length, r.dots.filter(o => o.back).length, r.differ == null ? "" : r.differ, r.tags == null ? "" : r.tags]) } };
  }

  /* Graph 8: what each date cost, and what the hooks stopped on it */
  function costGraph() {
    const T = DATA.tokens || [], F = DATA.refusals || [], dates = [...new Set(T.map(t => t.date))].sort();
    const start = days.map(d => (d.worked || [])[0]).filter(Boolean).sort()[0];
    const bars = dates.map(date => {
      const rows = T.filter(t => t.date === date), cost = pick => sum(rows.filter(pick), t => t.cost);
      const main = cost(t => t.agent === "main"), aud = cost(t => /auditor|rater/.test(t.agent || "")), other = cost(() => true) - main - aud, total = main + aud + other;
      const on = days.filter(d => d.worked && d.worked[0] <= date && date <= d.worked[1]).map(d => d.day);
      const refused = F.filter(r => r.date === date && r.refused), nRefused = sum(refused, r => r.refused), cut = sum(rows, t => t.cut), replies = sum(rows, t => t.replies);
      // The date's dollars end at the count: only the pull requests merged by then share them.
      const prs = (DATA.rows || []).filter(r => r.pr && r.date === date), merged = prs.length, shared = prs.filter(r => inCount(r.pr)).length;
      // The main session's dollars after a session passed 150k tokens (cost_past_150k): a row without the key is not known, so no row that has it is not zero.
      const known = rows.filter(t => t.agent === "main" && t.cost_past_150k != null), past = known.length ? sum(known, t => t.cost_past_150k) : null;
      return { date, label: shortDate(date), days: on, main, aud, other, total, replies, refused: nRefused, cut, merged, shared, past, setup: !start || date < start,
        t: `${shortDate(date)} · ${on.length ? daySpan(on) : !start || date < start ? "before Day 1" : "between Days"} · ${money(total)}`,
        b: [`Main session ${money(main)}, auditors ${money(aud)}, implementer and others ${money(other)}. ${comma(replies)} replies.`
          + (past == null ? "" : ` ${money(past)} of the main session's ${money(main)} came after a session passed 150k tokens.`)
          + ` The hooks refused ${plural(nRefused, "call", "calls")}${refused.length ? ` (${refused.map(r => `${r.refused} by the ${r.guard}`).join(", ")})` : ""} and cut ${plural(cut, "long output", "long outputs")}.`
          + (!merged ? "" : ` ${plural(merged, "pull request", "pull requests")} merged that date`
            + (shared === merged ? `: ${money(total / merged)} each, all sessions.` : shared ? `, ${shared} of them before the count at ${countedSay}: ${money(total / shared)} each, all sessions.`
              : `, none of them before the count at ${countedSay}.`))] };
    });
    const all = sum(bars, b => b.total), main = sum(bars, b => b.main), setup = bars.filter(b => b.setup), work = bars.filter(b => !b.setup);
    const pastBars = bars.filter(b => b.past != null), pastKey = pastBars.length ? [["past", `Of the main session, after a session passed 150k tokens ${money(sum(pastBars, b => b.past))}`]] : [];
    const later = (DATA.rows || []).filter(r => r.pr && !inCount(r.pr)).length, shared = sum(work, x => x.shared);
    const newest = ((DATA.rows || [])[(DATA.rows || []).length - 1] || {}).date, lastDate = dates[dates.length - 1];
    const b = [setup.length && work.length ? `${plural(setup.length, "date", "dates")} of set-up cost ${money(sum(setup, x => x.total))} before Day 1.` : "",
      work.length ? `The Days cost ${money(sum(work, x => x.total))} over ${plural(work.length, "date", "dates")}, on which ${plural(shared, "pull request", "pull requests")} merged${shared < sum(work, x => x.merged) ? " before the count" : ""}.` : "",
      `The hooks refused ${plural(sum(bars, x => x.refused), "call", "calls")} and cut ${plural(sum(bars, x => x.cut), "long output", "long outputs")}.`,
      pastBars.length ? `Over ${plural(pastBars.length, "date", "dates")} where it is known, ${money(sum(pastBars, x => x.past))} of the main session's ${money(sum(pastBars, x => x.main))} came after a session passed 150k tokens.` : "",
      countedAt ? `Counted on the maintainer's computer up to ${countedSay}${later ? `: ${plural(later, "pull request has", "pull requests have")} merged since, and what ${later === 1 ? "it" : "they"} cost is not in yet` : ""}.`
      // With no count on record, the last date is counted up to the close run on it: what merged later that date is in the pull requests and not in the dollars.
      : newest && lastDate && newest >= lastDate ? `Counted at each Day's close on the maintainer's computer, so ${shortDate(lastDate)} is counted only up to the close run on it${newest > lastDate ? ", and nothing after it is in yet" : ""}.` : ""].filter(Boolean);
    return { bars, max: Math.max(0.01, ...bars.map(x => x.total)),
      key: [["main", `Main session ${money(main)}`], ["rest", `Auditors and the implementer ${money(all - main)}`], ...pastKey],
      say: "What each date's tokens would cost on the pay-per-token API, at list prices. This repository's sessions only, counted on the maintainer's computer. The maintainer pays a flat subscription, so this measures usage and is not a bill.",
      read: { t: bars.length ? `${money(all)} of tokens at list prices; ${Math.round(100 * main / (all || 1))}% of it in the main session` : "No token counts yet", b: bars.length ? [b.join(" ")] : ["They are counted at a Day's close, on the maintainer's computer."] },
      table: { head: ["Date", "Days", "Main session, $", "Main session after 150k, $", "Auditors, $", "Implementer and others, $", "Replies", "Calls refused", "Outputs cut", "Pull requests merged", "Merged before the count"],
        rows: bars.map(x => [x.label, x.days.join(", "), x.main.toFixed(2), x.past == null ? "" : x.past.toFixed(2), x.aud.toFixed(2), x.other.toFixed(2), x.replies, x.refused, x.cut, x.merged, x.shared]) } };
  }

  /* Graph 9: the lines each day changed, by what the file is */
  function workGraph() {
    const R = DATA.rows || [], part = (r, k) => { const w = r.work || {}; return k === "spec" ? (w.spec || 0) + (w.context || 0) : w[k] || 0; };
    const of = list => Object.fromEntries(WORK.map(([k]) => [k, sum(list, r => part(r, k))]));
    // A Day's bar is its own pull requests (by `own_day`); the area work placed beside it is drawn paler and counts in no Day.
    const breakdown = w => WORK.map(([k, name], i) => `${i ? lower(name) : name} ${comma(w[k])}`).join(", ");
    const bars = days.map(d => {
      const mine = R.filter((r, i) => PLACED[i].own === d.day), w = of(mine), total = sum(Object.values(w)), prs = mine.filter(r => r.pr).length;
      const ratio = w.prod ? (w.test / w.prod).toFixed(1) : "–";
      const beside = R.filter((r, i) => PLACED[i].area && PLACED[i].at === d.day), aw = of(beside), atotal = sum(Object.values(aw)), aprs = beside.filter(r => r.pr).length;
      return { day: d.day, w, total, prs, ratio, label: total >= 1000 ? `${(total / 1000).toFixed(1)}k` : String(total),
        t: `Day ${d.day}${d.day === current ? " (in progress)" : ""} · ${comma(total)} lines changed`,
        b: [`${breakdown(w)}. ${plural(prs, "pull request", "pull requests")} merged.` + (w.prod ? ` ${ratio} test lines for each production line.` : "")],
        aside: atotal > 0 || aprs > 0 ? { w: aw, total: atotal, prs: aprs, label: atotal >= 1000 ? `${(atotal / 1000).toFixed(1)}k` : String(atotal),
          t: `Outside any Day · merged while Day ${d.day} was open or after it closed · ${comma(atotal)} lines changed`,
          b: [`${breakdown(aw)}. ${plural(aprs, "pull request", "pull requests")} merged. No Day's size or test ratio counts them.`] } : null };
    });
    const all = of(R.filter((r, i) => days.some(d => d.day === PLACED[i].own))), total = sum(Object.values(all));
    const before = sum(Object.values(of(R.filter((r, i) => PLACED[i].own == null && PLACED[i].at === 0))));
    const asideTotal = sum(bars, x => x.aside ? x.aside.total : 0), asidePrs = sum(bars, x => x.aside ? x.aside.prs : 0);
    const asideSay = bars.some(x => x.aside) ? `Another ${comma(asideTotal)} lines, in ${plural(asidePrs, "pull request", "pull requests")}, are outside any Day (dashboard and tooling work): drawn paler beside the Day that was open when they merged, and in no Day's size or test ratio.` : "";
    const ranked = WORK.map(([k, name]) => [name, all[k]]).sort((a, b) => b[1] - a[1]);
    return { bars, max: Math.max(1, ...bars.map(x => x.total), ...bars.map(x => x.aside ? x.aside.total : 0)),
      key: [...WORK.map(([k, name]) => [k, name]), ["aside", "Paler: outside any Day"]],
      read: { t: total ? `${comma(total)} lines changed in ${daySpan(days.map(d => d.day))}; the largest share is ${lower(ranked[0][0])}` : "No Day has merged work yet",
        b: total ? [`${ranked.map(([name, v], i) => `${i ? lower(name) : name} ${comma(v)}`).join(", ")}.` + (before ? ` Another ${comma(before)} lines came before Day 1.` : "")
          + (asideSay ? ` ${asideSay}` : "") + " Breaks on purpose never merge, so checking did more than its lines show."] : [] },
      table: { head: ["Day", ...WORK.map(w => w[1]), "All", "Pull requests merged", "Test lines for each production line", "Outside any Day: lines", "Outside any Day: pull requests"],
        rows: bars.map(x => [`Day ${x.day}`, ...WORK.map(([k]) => x.w[k]), x.total, x.prs, x.ratio, x.aside ? x.aside.total : 0, x.aside ? x.aside.prs : 0]) } };
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
  function yardGraph() {
    const Y = DATA.yardsticks || {}, all = (Y.rows || []).map(parksFromRuns), cols = [...new Set([...days.map(d => d.day), ...(Y.days || [])])].sort((a, b) => a - b);
    const show = (r, v) => r.unit === "$" ? `$${v.toFixed(r.decimals)}` : `${v.toFixed(r.decimals)}${r.unit || ""}`;
    const has = r => (r.values || []).some(v => v.value != null);
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
      return { key: r.key, name: r.name, cells, line: r.baseline != null ? r.baseline / max : null, base: r.baseline != null ? show(r, r.baseline) : "",
        over: cells.filter(c => c.over).length, n: vals.length, last: vals[vals.length - 1],
        note: r.baseline != null ? `kit's baseline: ${show(r, r.baseline)}` : `no baseline${YARD_HINT[r.key] ? `; ${YARD_HINT[r.key]}` : ""}`, show: v => show(r, v),
        avg, avgNote: lastAvg ? `average so far: ${lastAvg.text}${noun ? ` over every ${noun}` : ""}` : "" };
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
    const tracks = P ? (P.tracks || []) : [];
    const b = [P ? (tracks.length ? `Day ${P.day} has ${plural(tracks.length, "track left", "tracks left")} (${tracks.map(t => `${t.track}: ${(t.ids || []).length}`).join(", ")}) and its close.`
        : `Day ${P.day} has only its close left.`) : "",
      ...unknown.map(u => `Day ${u.day} has no spec, so its size cannot be drawn.` + (u.waits ? ` ${plural(u.waits, "numbered hand-off waits", "numbered hand-offs wait")} for it (${u.ids.join(", ")}).` : "")),
      stop != null ? `After Day ${stop} the plan stops for the maintainer. What comes after is not specified, so the graph ends there and gives no percentage of the whole plan.` : ""].filter(Boolean);
    const ticks = [], every = pMax > 120 ? 40 : 20;
    for (let t = 0; t <= pMax; t += every) ticks.push({ label: String(t), y: 1 - t / pMax });
    return { merges, ahead: aheadOut, unknown, stop, pMax, hMax, ticks, bands, barTicks: [{ label: String(hMax / 2), h: 0.5 }, { label: String(hMax), h: 1 }],
      key: [["pt spec", `Spec merge ${nKind("spec")}`], ["pt code", `Code merge ${nKind("code")}`], ["pt close", `A Day's close ${nKind("close")}`],
        ["pt other", `Other (tooling, dashboard) ${nKind("other")}`], ["sw built", "Promises built"], ["sw written", "Promises written"],
        ["sw handoff", "Hand-offs open"], ["pt todo", "Specified, not merged"], ["sw unknown", "Not specified yet"]],
      say: `One column per merge, ${merges.length} in all, oldest on the left. The dot is the number of promises built once that merge landed; the dashed line above it is the number written. The bar under it is the numbered hand-offs still open. Right of today, the outlined dots are tracks that are specified and not merged. The first column is the first commit, before any pull request.`,
      ladder: [{ cls: "now", name: "Level 0 · today", need: "The maintainer starts each step and merges.", state: "Where the project is" },
        { cls: "", name: "Level 1 · the maintainer merges", need: "The driver starts each step.", state: "Enters at the Day 8 trial" },
        { cls: "wait", name: "Level 2 · the driver merges", need: "15 pull requests in a row with no change asked.", state: "Not counted yet" },
        { cls: "wait", name: "Level 3 · phases chain", need: "One whole phase at level 2 with no escape.", state: "Not counted yet" }],
      read: !C.length ? { t: "Nothing is merged yet", b: [] }
        : { t: `${built} of ${written} promises built` + (parts.length ? ` · ${andList(parts)}${stop != null ? " before the stop" : " still to come"}` : ""), b },
      table: { head: ["Merge", "Kind", "Day", "Built", "Written", "Hand-offs open"],
        rows: [...merges.map(m => [m.pr ? `#${m.pr}` : "start", KINDS[m.kind], m.day || "", m.built, m.written, m.open]),
          ...aheadOut.map(a => [a.close ? "close" : `track ${a.label}`, "not merged", a.day, a.built, written, ""])] } };
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

  // Graph 10: one date on the clock. The sessions (docs/dashboard/sessions.json) are stamped with the offset of the
  // machine that recorded them, so the clock is the maintainer's and not the reader's; GitHub's times are UTC and
  // are moved to that offset. A stretch that crosses midnight is clipped to each date it touches.
  const LANES = [["main", "Main session"], ["implementer", "Implementer"], ["auditors", "Auditors"], ["other", "Other subagents"]];
  const laneOf = a => a === "main" || a === "implementer" ? a : /-auditor$|^defect-rater$/.test(a) ? "auditors" : "other";
  const offsetOf = s => { const m = /(Z|[+-]\d\d:\d\d)$/.exec(s || ""); return !m || m[1] === "Z" ? 0 : (m[1][0] === "-" ? -1 : 1) * (+m[1].slice(1, 3) * 60 + +m[1].slice(4, 6)); };
  const hm = m => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(Math.floor(m % 60)).padStart(2, "0")}`;
  const span = m => { const r = Math.round(m); return r >= 60 ? `${Math.floor(r / 60)} h ${r % 60} min` : plural(Math.max(1, r), "minute", "minutes"); };
  // What a session waited on inside a busy stretch (scripts/token-usage.py's RUN_KINDS): its key, its legend and its words in a sentence.
  const RUNS = [["tests", "waiting on tests", "tests"], ["checks", "waiting on GitHub's checks", "GitHub's checks"], ["other", "waiting on another command", "other commands"]];
  function clockGraph() {
    const C = DATA.clock || {}, S = (C.sessions || []).filter(s => s.from && s.to), PRS = (C.prs || []).filter(p => p.opened && p.merged);
    const none = { head: ["Lane", "What", "From", "To", "Minutes"], rows: [] };
    // The driver's runs: the sessions it started, the merges it saw and its parks. Its times are UTC and are moved to the
    // sessions' clock like the pull requests' are; a park's step is the one whose park names its issue, for its Day.
    const DR = DATA.driver_runs || {}, DSTEPS = DR.steps || null, DPARKS = DR.parks || null, DCOUNT = DR.counted || null;
    const DSESS = (DSTEPS || []).flatMap(s => (s.sessions || []).filter(x => x.start).map(x => ({ x, s })));
    const DMERGES = (DSTEPS || []).filter(s => s.merged), stepOfPark = i => (DSTEPS || []).find(s => (s.parks || []).some(p => p.issue === i.number));
    if (!S.length && !PRS.length && !DSESS.length && !DMERGES.length && !(DPARKS || []).length) return { empty: "no session, pull request or check times are recorded yet. `python scripts/token-usage.py` writes the sessions to `docs/dashboard/sessions.json` from this machine's transcripts; the pull requests' and checks' times come from GitHub.",
      dates: [], at: -1, hours: [], read: { t: "No times are recorded yet.", b: [] }, table: none };
    const counts = new Map();
    S.forEach(s => counts.set(offsetOf(s.from), (counts.get(offsetOf(s.from)) || 0) + 1));
    const zone = S.length ? [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0] : 0;
    const zoneText = zone ? `UTC${zone > 0 ? "+" : "−"}${hm(Math.abs(zone))}` : "UTC";
    const dateOf = s => new Date(Date.parse(s) + zone * 60000).toISOString().slice(0, 10);
    const midnight = date => Date.parse(`${date}T00:00:00Z`) - zone * 60000;
    // An interval on one date, in minutes from its midnight, or null when it misses the date.
    const clip = (date, a, b) => { const t0 = midnight(date), x = (Date.parse(a) - t0) / 60000, y = (Date.parse(b) - t0) / 60000; return y < 0 || x > 1440 || isNaN(x) || isNaN(y) ? null : [Math.max(0, x), Math.min(1440, Math.max(y, x))]; };
    const dates = [...new Set([...S.map(s => dateOf(s.from)), ...PRS.flatMap(p => [dateOf(p.opened), dateOf(p.merged)]),
      ...DSESS.map(({ x }) => dateOf(x.start)), ...DMERGES.map(s => dateOf(s.merged)), ...(DPARKS || []).flatMap(i => [i.opened, i.closed || DCOUNT]).filter(Boolean).map(dateOf)])].sort();
    const laneKeys = LANES.filter(([k]) => k !== "other" || S.some(s => laneOf(s.agent) === "other"));
    const bar = (cls, [a, b], t, b2, day) => ({ x: a / 14.4, w: (b - a) / 14.4, cls, t, b: b2, days: day ? [day] : [], mins: b - a, from: hm(a), to: hm(Math.min(b, 1439.99)) });
    const prKind = p => p.kind in KINDS && p.kind !== "origin" ? p.kind : "other";
    // A pull request's checks: the stretches its workflow runs were running in, so the time between two pushes is in none
    // of them. Data written before the stretches were kept has only the first start and the last end.
    const spansOf = ch => ch.spans && ch.spans.length ? ch.spans : [[ch.start, ch.end, ch.failed]];
    const whole = ([a, b]) => (Date.parse(b) - Date.parse(a)) / 60000, kindOf = r => (RUNS.find(k => k[0] === r[2]) || RUNS[2])[0];
    const runsSay = ch => `${plural(ch.runs, "workflow run", "workflow runs")}${ch.pushes ? ` over ${plural(ch.pushes, "push", "pushes")}` : ""}${ch.failed ? `, ${ch.failed} of them failed.` : ", all passed."}`;
    const out = dates.map(date => {
      const days = new Set(), lanes = [], busy = [], rows = [];
      // The minute of this date the sessions are counted up to: all of it, none of it, or part of it.
      const upTo = countedMs == null ? 1440 : Math.max(0, Math.min(1440, (countedMs - midnight(date)) / 60000));
      const unseen = upTo <= 0 ? "not counted yet" : upTo < 1440 ? `nothing recorded up to ${hm(upTo)}` : "nothing recorded";
      const add = (name, bars, sub, busyFor) => { lanes.push({ name, sub, bars, busyFor }); bars.forEach(b => { b.days.forEach(d => days.add(d)); rows.push([name, b.what || b.t.split(" · ")[0], b.from, b.to, Math.round(b.mins)]); }); return bars; };
      const ran = RUNS.map(() => 0), who = s => s.agent === "main" ? "Main session" : s.agent;
      let counted = false;  // a stretch written before the waits were counted has no `ran`: the date then says nothing about them
      laneKeys.forEach(([k, name]) => {
        const mine = S.filter(s => laneOf(s.agent) === k).map(s => ({ s, c: clip(date, s.from, s.to) })).filter(x => x.c);
        // What a stretch waited on, for the part of it on this date.
        const part = (s, c) => { const all = (Date.parse(s.to) - Date.parse(s.from)) / 60000; return all > 0 ? (c[1] - c[0]) / all : 1; };
        // A wait of a minute or more has its own times and is cut to the date; only the rest of `ran`, the shorter waits, is shared by the part of the stretch on it.
        const bars = mine.map(({ s, c }) => { const mins = RUNS.map(([kind]) => { const long = (s.runs || []).filter(r => kindOf(r) === kind);
            return sum(long, r => { const x = clip(date, r[0], r[1]); return x ? x[1] - x[0] : 0; }) + Math.max(0, ((s.ran || {})[kind] || 0) / 60 - sum(long, whole)) * part(s, c); }), all = sum(mins);
          return { ...bar("busy", c, `${who(s)} · busy ${hm(c[0])} to ${hm(c[1])}`, [`${plural(s.replies, "reply", "replies")}, with no gap longer than 5 minutes.`
            + (all >= 1 ? ` ${span(all)} of it waiting on commands it ran: ${andList(RUNS.map(([, , word], i) => mins[i] >= 1 ? `${span(mins[i])} on ${word}` : "").filter(Boolean))}.` : "")], s.day), ran: mins, counted: Boolean(s.ran || s.runs) }; });
        const waits = mine.flatMap(({ s }) => (s.runs || []).map(([a, b, kind]) => { const c = clip(date, a, b), run = RUNS.find(r => r[0] === kind) || RUNS[2];
          return c && { ...bar(`run ${run[0]}`, c, `${who(s)} · ${run[1]} ${hm(c[0])} to ${hm(c[1])}`, [`${span(c[1] - c[0])} inside a busy stretch: the session had run a command and was waiting for it to finish.`], s.day), what: `${who(s)}, ${run[1]}` }; }).filter(Boolean));
        busy.push(...bars);
        RUNS.forEach((_, i) => { ran[i] += sum(bars, b => b.ran[i]); });
        counted = counted || bars.some(b => b.counted);
        // Two sessions of a lane busy at once are one stretch of the clock, not two.
        const mins = covered(mine.map(x => x.c)), wait = Math.min(mins, sum(bars, b => sum(b.ran)));
        add(name, [...bars, ...waits], bars.length ? `busy ${span(mins)}${wait >= 1 ? `, ${span(wait)} of it waiting on commands` : ""}` : unseen, bars.length ? span(mins) : "");
      });
      const open = PRS.map(p => { const c = clip(date, p.opened, p.merged); if (!c) return null; const ch = p.checks;
        return bar(prKind(p), c, `Pull request #${p.number} · ${p.branch} · open ${hm(c[0])} to ${hm(c[1])}`,
          [`Open for ${span(whole([p.opened, p.merged]))} before it merged${c[0] === 0 && Date.parse(p.opened) < midnight(date) ? ", opened on an earlier date" : ""}.`,
            ch ? `Its checks were running for ${span(sum(spansOf(ch), whole))}: ${runsSay(ch)}` : "No check is recorded for it."], p.day); }).filter(Boolean);
      add("Pull request open", open, open.length ? `${plural(open.length, "pull request", "pull requests")}, ${span(sum(open, b => b.mins))} in all` : "none open");
      const checks = PRS.flatMap(p => !p.checks ? [] : spansOf(p.checks).map(([a, b, failed]) => { const c = clip(date, a, b);
        return c && { ...bar(failed ? "failed" : "ok", c, `Checks on pull request #${p.number} · ${hm(c[0])} to ${hm(c[1])}`, [`On this pull request in all: ${runsSay(p.checks)}`], p.day), pr: p.number }; }).filter(Boolean));
      busy.push(...checks);
      const checked = new Set(checks.map(b => b.pr)), red = new Set(checks.filter(b => b.cls === "failed").map(b => b.pr));
      add("Checks running", checks, checks.length ? `on ${plural(checked.size, "pull request", "pull requests")}, running for ${span(covered(checks.map(b => [b.x * 14.4, b.x * 14.4 + b.mins])))}, ${red.size} with a failure` : "none");
      const merged = PRS.filter(p => dateOf(p.merged) === date).map(p => ({ p, wait: (Date.parse(p.merged) - Date.parse(p.opened)) / 60000 }));
      const merges = merged.map(({ p, wait }) => { const at = (Date.parse(p.merged) - midnight(date)) / 60000; return bar("merge", [at, at], `Merged pull request #${p.number} · at ${hm(at)}`, [`The maintainer merged it ${span(wait)} after it opened.`], p.day); });
      add("Maintainer merges", merges, plural(merges.length, "merge", "merges"));
      // The driver's lanes come first and are not busy time: a mark for each session it started, each merge it saw and each
      // crashed session (the run log does not say when it was on or off, so no lane shows that), and its parks as bars.
      const minuteOf = t => (Date.parse(t) - midnight(date)) / 60000, sessionsOn = DSESS.filter(({ x }) => dateOf(x.start) === date);
      const acts = [...sessionsOn.map(({ x, s }) => bar("act", [minuteOf(x.start), minuteOf(x.start)], `The driver started a session · ${hm(minuteOf(x.start))}`, [s.step], s.day)),
        ...DMERGES.filter(s => dateOf(s.merged) === date).map(s => bar("act", [minuteOf(s.merged), minuteOf(s.merged)], `The driver saw pull request ${s.pr != null ? `#${s.pr}` : "a pull request"} merged · ${hm(minuteOf(s.merged))}`, [s.step], s.day))];
      const crashes = sessionsOn.filter(({ x }) => x.crashed).map(({ x, s }) => bar("crash", [minuteOf(x.start), minuteOf(x.start)], `A session crashed · started ${hm(minuteOf(x.start))}`, ["The run log has no end for it."], s.day));
      const parks = (DPARKS || []).map(i => { const end = i.closed || DCOUNT, c = end ? clip(date, i.opened, end) : null;
        return c && bar("park", c, `Parked · ${hm(c[0])} to ${hm(c[1])}`, [i.closed ? `Waited ${span((Date.parse(i.closed) - Date.parse(i.opened)) / 60000)}: ${i.title}` : `Still waiting at the count: ${i.title}`], (stepOfPark(i) || {}).day); }).filter(Boolean);
      const drv = DSTEPS ? [{ name: "Driver", sub: acts.length || crashes.length ? `${plural(acts.length, "act", "acts")}, ${plural(crashes.length, "crashed session", "crashed sessions")}` : unseen, bars: [...acts, ...crashes] },
        { name: "Parked for the maintainer", sub: !DPARKS ? "the parked issues could not be read" : parks.length ? `${plural(parks.length, "park", "parks")}, ${span(sum(parks, b => b.mins))} in all` : "none", bars: parks }] : [];
      drv.forEach(l => l.bars.forEach(b => { b.days.forEach(d => days.add(d)); rows.push([l.name, b.what || b.t.split(" · ")[0], b.from, b.to, Math.round(b.mins)]); }));
      lanes.unshift(...drv);
      const driverSay = DSTEPS && (sessionsOn.length || parks.length) ? `The driver started ${plural(sessionsOn.length, "session", "sessions")} and waited ${parks.length ? `${span(sum(parks, b => b.mins))} on ${plural(parks.length, "park", "parks")}` : "on no park"}.` : "";
      // What the date says as a whole: the merges and the typical wait, who was busy how long, the longest stretch with nothing running, the longest waits.
      const waits = merged.map(m => m.wait).sort((a, b) => a - b), median = waits.length ? waits[Math.floor((waits.length - 1) / 2)] : null;
      const was = lanes.filter(l => l.busyFor).map((l, i) => `${i ? "the " : "The "}${lower(l.name)} ${i ? "" : "was busy "}for ${l.busyFor}`);
      const waited = !counted ? "" : sum(ran) < 1 ? "None of that was a wait on a command of a minute or more."
        : `Of that, the sessions waited ${span(sum(ran))} on commands they had run: ${andList(RUNS.map(([, , word], i) => ran[i] >= 1 ? `${span(ran[i])} on ${word}` : "").filter(Boolean))}.${ran[1] >= 1 ? " The wait on GitHub's checks is drawn again under Checks running." : ""}`;
      const idle = busy.map(b => [b.x * 14.4, b.x * 14.4 + b.mins]).sort((a, b) => a[0] - b[0]).reduce((acc, [a, b]) => { if (acc.end != null && a - acc.end > acc.gap && a <= upTo) { acc.gap = a - acc.end; acc.from = acc.end; acc.to = a; } acc.end = acc.end == null ? b : Math.max(acc.end, b); return acc; }, { end: null, gap: 0 });
      const longest = merged.sort((a, b) => b.wait - a.wait).slice(0, 3);
      const read = { t: `${shortDate(date)}: ${plural(merged.length, "pull request", "pull requests")} merged${median != null ? `, half of them open for ${span(median)} or less` : ""}`,
        b: [days.size ? `Work of ${daySpan([...days].sort((a, b) => a - b))}.` : "", was.length ? `${andList(was)}.` : upTo <= 0 ? `The sessions of this date are not counted yet: the count ends at ${countedSay}.` : "No session was recorded on this date.", was.length ? waited : "", driverSay,
          upTo > 0 && upTo < 1440 ? `The sessions are counted up to ${hm(upTo)}: after that, only GitHub's pull requests and checks are in.` : "",
          idle.gap >= 60 ? `Nothing ran from ${hm(idle.from)} to ${hm(idle.to)}.` : "", longest.length ? `The longest ${longest.length === 1 ? "wait" : "waits"} for a merge: ${andList(longest.map(m => `#${m.p.number} (${span(m.wait)})`))}.` : "",
          `Times are on the clock of the machine that recorded the sessions (${zoneText}).`].filter(Boolean) };
      return { date, label: shortDate(date), days: [...days].sort((a, b) => a - b), lanes, read, table: { head: none.head, rows } };
    });
    const at = out.length - 1;
    return { dates: out, at, zone: zoneText, runs: RUNS.map(([k, text]) => [k, text]), hours: [0, 3, 6, 9, 12, 15, 18, 21].map(hh => ({ t: hm(hh * 60), x: hh * 60 / 14.4 })), read: out[at].read, table: out[at].table, driver: DSTEPS !== null };
  }

  // Graph 11: each step the driver started, one dot, placed by how it ended. A park's wait is its issue's opened to closed;
  // an issue still open, or one the count did not find, has no wait and is left out of the sums.
  function runGraph() {
    const DR = DATA.driver_runs || {}, steps = DR.steps || null, parks = DR.parks || null, counted = DR.counted || null;
    const issues = new Map((parks || []).map(i => [i.number, i]));
    const waitOf = p => { const i = issues.get(p.issue); return i && i.closed ? (Date.parse(i.closed) - Date.parse(i.opened)) / 60000 : null; };
    const COLS = [["merged", "Merged, nobody touched it"], ["fixed", "Merged after fixing itself"], ["maintainer", "Parked: a decision that is the maintainer's"],
      ["fault", "Parked: the driver or the kit was at fault"]];
    const colOf = s => s.ended === "merged" ? "merged" : s.ended === "fixed" ? "fixed" : s.ended === "parked" ? ((s.parks || []).some(p => p.by === "fault") ? "fault" : "maintainer") : null;
    const dayOf = s => s.day == null ? null : s.day;
    const sentence = t => !t || /[.!?]$/.test(t) ? t : `${t}.`;
    const dot = (s, col, day) => {
      const fixes = s.fixes || 0, pk = s.parks || [], parked = col === "maintainer" || col === "fault", waits = pk.map(waitOf);
      const wait = parked && pk.length && waits.every(w => w != null) ? sum(waits) : null;
      const how = { merged: "merged, nobody touched it", fixed: `merged after ${plural(fixes, "fix round", "fix rounds")}`, maintainer: "parked for the maintainer", fault: "parked by a fault" }[col];
      const crashed = (s.crashes || 0) > 0;
      return { col, fixes, crashed, wait, t: `${day == null ? "No Day" : `Day ${day}`} · ${s.step} · ${how}`,
        b: [parked && pk.length ? `${pk.map(p => sentence(p.line)).join(" ")} ${wait == null ? "The wait is not known." : `It waited ${span(wait)}.`}` : null,
          crashed ? "A session of this step crashed: the run log has no end for it." : null].filter(Boolean) };
    };
    // A column's sub: its steps, the fix rounds of the merged-after-fixing column, and the waits of its parks.
    const subOf = (key, list) => {
      const n = plural(list.length, "step", "steps");
      if (key === "fixed") return `${n} · ${plural(sum(list, s => s.fixes), "fix round", "fix rounds")}`;
      if (key !== "maintainer" && key !== "fault") return n;
      if (!parks) return `${n} · the waits could not be read`;
      const known = list.flatMap(s => s.parks || []).map(waitOf).filter(w => w != null);
      return !list.length ? n : known.length ? `${n} · waited ${span(sum(known))}` : `${n} · the waits are not known`;
    };
    const cols = COLS.map(([key, name]) => ({ key, name, sub: steps ? subOf(key, steps.filter(s => colOf(s) === key)) : "" }));
    // One row per Day that has a step, then the steps with no Day.
    const rowDays = steps ? [...new Set(steps.map(dayOf))].sort((a, b) => (a == null) - (b == null) || a - b) : [];
    const rows = rowDays.map(day => {
      const mine = steps.filter(s => dayOf(s) === day), cells = COLS.map(([col]) => mine.filter(s => colOf(s) === col).map(s => dot(s, col, day)));
      const n = sum(cells, c => c.length), alone = cells[0].length + cells[1].length, open = mine.filter(s => s.ended === "open").length;
      const ps = mine.flatMap(s => s.parks || []), known = ps.map(waitOf).filter(w => w != null);
      return { day, label: day == null ? "No Day" : `Day ${day}`, cells, n, alone, open, share: n ? alone / n : null,
        fixes: sum(mine, s => s.fixes), crashes: sum(mine, s => s.crashes), parks: ps.length, minutes: Math.round(sum(known)) };
    });
    const all = steps || [], ended = sum(rows, r => r.n), alone = sum(rows, r => r.alone), open = sum(rows, r => r.open);
    const ps = all.flatMap(s => s.parks || []), maint = ps.filter(p => p.by !== "fault").length, fault = ps.length - maint;
    const crashes = sum(all, s => s.crashes), crashed = all.filter(s => s.crashes > 0).length;
    const read = { t: !steps ? "No step of the driver is counted yet" : !steps.length ? "The driver has started no step yet" : !ended ? "No step has ended yet"
        : `${plural(ended, "step", "steps")}, ${alone} of them with no person`,
      b: !steps || !steps.length ? [] : [[ps.length ? `${plural(maint, "park", "parks")} for the maintainer and ${plural(fault, "park", "parks")} by a fault.` : "No park yet.",
        crashes ? `${plural(crashes, "crashed session", "crashed sessions")} in ${plural(crashed, "step", "steps")}.` : "No session crashed.",
        open ? `${plural(open, "step", "steps")} still open.` : "",
        counted ? `Counted on the maintainer's computer up to ${counted.slice(11, 16)} on ${shortDate(counted)}.` : "",
        "A park is an issue the driver opens with the label \"parked\", so its reason and its wait come from GitHub; the fix rounds, the crashes and how a step ended come from the driver's run log."].filter(Boolean).join(" ")] };
    return { empty: steps ? null : "the driver's run log is not counted for this project yet. `python scripts/driver-runs.py --project <its path>` writes `docs/dashboard/driver-runs.json` from the run log on the maintainer's computer.",
      say: `Each dot is one step the driver started${steps ? `, ${steps.length} in all,` : ""} placed by how the step ended. A step further right needed more of a person.`,
      cols, rows, read, table: { head: ["Day", ...COLS.map(c => c[1]), "Still open", "Fix rounds", "Crashed sessions", "Parks", "Minutes parked", "Needed no person"],
        rows: rows.map(r => [r.label, ...r.cells.map(c => c.length), r.open, r.fixes, r.crashes, r.parks, r.minutes, `${r.alone} of ${r.n}`]) } };
  }

  function notMeasured(yard, clock, run) {
    const I = DATA.infra || {};
    return [!I.latest && !(I.runs || []).length && ["Infrastructure checks", "no run is recorded, so nothing is drawn."],
      !DATA.deployment && ["The live deployment", "no run is recorded, so nothing is drawn."],
      ...((yard.waiting || []).map(w => [w.name, `${w.why}.`])),
      run.empty && ["Whether it runs without a person", run.empty],
      clock.empty && ["Where a date's time goes, and who waits for whom", clock.empty]].filter(Boolean);
  }

  const P = safe(promises), g2 = safe(yardGraph), g10 = safe(clockGraph), g11 = safe(runGraph);
  return { head: head(), days: days.map(d => ({ day: d.day, title: plain(d.title), closed: finished(d), active: d.day === current })),
    attention: attention(), g3: safe(abilityGraph), g4: P.error ? P : P.board, g5: P.error ? P : safe(() => reliedGraph(P)), g6: safe(mergeGraph), g7: safe(sieveGraph),
    g8: safe(costGraph), g9: safe(workGraph), g1: safe(lookGraph), g2, g10, g11, promises: P.error ? { counts: [] } : { counts: COUNTED.map(s => [s, P.n(P.tiles, s)]).filter(c => c[1]), total: P.counted(P.tiles) },
    caveats: (DATA.meta || {}).caveats || [], notMeasured: notMeasured(g2, g10, g11) };
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
  Phases: "Groups of Days, each with one goal.",
  "Stopping points": "Where work halts until the maintainer lifts the stop.",
};
const HOW_SPEC_GLOSS = {
  Goal: "What is true at the end of the Day that was not at the start.",
  "In scope": "What this Day builds.",
  "Out of scope": "What it leaves, and which Day owns it.",
  Tracks: "The work, split into pull requests that can each be reviewed alone.",
  "Acceptance criteria": "The Day's promises: step 3.",
  Verify: "Commands anyone can run from the repository alone.",
  Notes: "What went wrong and what was handed on, written at the close.",
};
const HOW_CAST = [
  ["The maintainer", "A person. Owns the plan and, today, merges every pull request.", "bug"],
  ["Main AI session", "Usually writes the specs and briefs, reviews the code, plants the bugs and writes the pull requests.", "bug"],
  ["Implementer", "A smaller AI model. Usually writes code and tests from a brief, and never commits.", "red"],
  ["Plan-auditor", "At the start and end of a phase: is the plan still right for the code?", "goal"],
  ["Spec-auditor", "Before every Day: is each claim true, and can each check fail?", "spec"],
  ["Defect-rater", "At every close: labels the Day's mistakes without seeing the original labels.", "close"],
  ["Three end-of-phase auditors", "Security, agentic engineering and architecture. Run once, after the last phase in the plan.", "goal"],
];
// The excerpts are the build's own reading of the plan, the newest finished day's spec and its record; they go in
// as HTML through esc(). `tally` is graph 4's count of the re-checked promises, so the two cannot disagree.
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
    { id: "goal", kind: "doc", name: "The goal", line: "What we want built, in phases", gate: "<b>plan-auditor</b>, at a phase's start and end, asks: do the Days still add up to the goal?",
      body: `<p>One document says what the whole project is for, what stays with a person, and the order of the work. It rarely changes. There is only one plan, so it has no template. These are some of the sections it contains.</p>${planParts}`
        + howExcerpt(X.plan_phase, "Where it was scheduled: plan.md") + src("plan.md") },
    { id: "spec", kind: "doc", name: "A Day's spec", line: "One Day's work, written down first", gate: "<b>spec-auditor</b> runs every check on the code as it is and tries to prove each claim wrong",
      body: `<p>Each Day gets one file, filled in from the same template. The template forces the awkward questions early: what is left out, and who picks it up.</p>${specParts}` + src("specs/_template.md", "the template") + (chosen ? src(chosen.spec, `Day ${chosen.day}'s spec`) : "") },
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
    { id: "close", kind: "after", name: "The Day closes", line: "Each tick cites its evidence", gate: "<b>defect-rater</b> labels the Day's mistakes blind, to see if a second reader agrees",
      body: `<p>A last pull request ticks each promise and names what proves it. A box with no evidence stays unticked, with the reason written under it.</p>${howExcerpt(tick, `The tick on ${id}`)}`
        + `<ul><li>Mistakes go in the Notes, including the AI's own.</li><li>Automation replays the recorded evidence against the closing commit. If that fails, the next Day does not start.</li></ul>` + src("docs/lab-notebook.md", "the lab notebook") },
    { id: "recheck", kind: "after", name: "The re-check", line: "Are the promises still true later?", gate: null,
      body: `<p>Code keeps changing after a Day closes. So finished promises are tested again on later merged code, and the planted bugs are put back to see if the tests still notice.</p>${recheck}${counted}` + src("docs/dashboard/replay-history.json", "the re-check results") },
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
  // A step link anywhere on the page (graph 4 has four) opens the walk-through at that step.
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
  const tile = (t, mark) => mark(h("button", { type: "button", class: `tile ${t.status}` }, t.glyph), t);
  const px = n => `${n.toFixed(1)}px`;

  /* the header */
  const H = M.head;
  $("eyebrow").textContent = [H.project, H.when && `read from git and GitHub on ${H.when}`, H.commit && `commit ${H.commit}`].filter(Boolean).join(" · ");
  const banner = $("demo-banner");
  banner.textContent = "Example data: this project has no day specs yet. The page will show real data after the first day spec merges.";
  banner.hidden = !H.demo;
  put("now", h("strong", null, "Now: "), H.now, " ", h("strong", null, "Next step: "), rich(H.next));
  if (H.took) $("words-took").textContent = H.took;
  const A = M.attention;
  $("attention").hidden = !A.total;
  put("attention-n", `Needs attention: ${plural(A.total, "item", "items")}`);
  put("attention-list", A.groups.map(g => h("li", null, h("b", null, `${g.label} (${g.ids.length})`), " ", g.detail ? [rich(g.detail), ": "] : null, g.ids.join(", "))));

  /* the day buttons: one day lit in every graph */
  let lit = null;
  const onDay = [];  // what else happens when a day is picked: graph 10 turns to that day's last date
  const relight = () => marks.forEach(node => node.classList.toggle("dim", lit !== null && !node.dataset.days.split(" ").includes(String(lit))));
  const chips = [null, ...M.days.map(d => d.day)].map(day => h("button", { type: "button", "aria-pressed": day === null ? "true" : "false" }, day === null ? "All Days" : `Day ${day}`));
  chips.forEach((chip, i) => chip.addEventListener("click", () => {
    lit = i ? M.days[i - 1].day : null;
    chips.forEach((c, j) => c.setAttribute("aria-pressed", j === i ? "true" : "false"));
    relight();
    onDay.forEach(f => f(lit));
  }));
  put("days", h("span", null, "Highlight one Day in every graph:"), chips);

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
    const today = h("div", { class: "g1-today", style: `left:${(100 * n / cols).toFixed(2)}%` }, h("span", null, "today"));
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
    put("g1-ladder", m.ladder.map(r => h("div", { class: `rung ${r.cls}` }, h("b", null, r.name), r.need, h("small", null, r.state))));
  });

  /* Graph 3 */
  graph("g3", (m, mark) => {
    const line = (name, cells, cls) => h("div", { class: `g3-row ${cls || ""}` }, h("div", { class: "g3-name" }, name), h("div", { class: "g3-cells" }, cells));
    const col = c => c.day == null ? [] : [c.day];
    put("g3-plot", line("Day", m.cols.map(c => forDays(h("div", { class: "g3-h" }, c.label), col(c))), "head"),
      line("Closed", m.cols.map(c => forDays(h("div", { class: "g3-h mark" }, c.mark), col(c))), "head"),
      m.rows.map(r => line(r.name, r.cells.map(c => forDays(mark(h("button", { type: "button", class: `g3-cell s${c.level}` }, c.n ? String(c.n) : "·"), c), col(c))))));
    key("g3-key", [["", "Pull requests:"], ["sw s1", "1–2"], ["sw s2", "3–5"], ["sw s3", "6–9"], ["sw s4", "10 or more"]]);
  });

  /* Graph 4 */
  graph("g4", (m, mark) => {
    $("g4-say").textContent = m.say;
    key("g4-key", m.key.map(k => [`tile ${k.status}`, k.text, k.glyph]));
    put("g4-plot", m.rows.map(r => forDays(h("div", { class: "board-row" }, h("div", { class: "board-day" }, `Day ${r.day}`),
      h("div", { class: "tiles" }, r.tiles.map(t => tile(t, mark))), h("div", { class: "board-count" }, r.count)), [r.day])));
    $("g4-hist-say").textContent = m.histSay;
    put("g4-hist", m.hist.map(x => mark(h("button", { type: "button", class: "strip-col" },
      ["skipped", "broken", "repair", "unproven", "proven"].map(s => h("span", { class: s, style: `height:${px(x.counts[s] * 48 / m.histMax)}` }))), x)));
    $("g4-hist").hidden = !m.hist.length;
  });

  /* Graph 5 */
  graph("g5", (m, mark) => {
    put("g5-plot", m.rows.map(r => h("div", { class: "ab-row" }, h("div", { class: "ab-name" }, r.name),
      h("div", { class: "ab-groups" }, r.groups.map(g => forDays(h("div", { class: "ab-group" }, h("span", { class: "mono" }, `D${g.day}`),
        h("div", { class: "tiles" }, g.tiles.map(t => tile(t, mark)))), [g.day])), r.note && h("span", { class: "ab-note" }, r.note)),
      h("div", { class: "ab-count" }, r.count))));
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
    key("g7-key", [["", "Cause:"], ...m.key.map(k => [k.cls, k.text])]);
    put("g7-plot", h("div", { class: "sieve" },
      h("div", { class: "sieve-row head" }, h("div", { class: "sieve-day" }), h("div", { class: "sieve-gates" }, m.gates.map(g => h("div", { class: "sieve-gate" }, h("strong", null, g.name), h("span", null, g.sub)))),
        h("div", { class: "sieve-note" }, "Tags a second reader gave differently")),
      m.rows.map(r => forDays(h("div", { class: "sieve-row" }, h("div", { class: "sieve-day" }, `Day ${r.day}`),
        h("div", { class: "sieve-gates" }, r.cells.map(list => h("div", { class: "sieve-cell" }, list.map(o => mark(h("button", { type: "button", class: `dot ${o.cause}${o.escaped ? " square" : ""}${o.back ? " ring" : ""}` }), o))))),
        h("div", { class: "sieve-note mono" }, r.note)), [r.day]))));
  });

  /* Graphs 8 and 9: stacked bars over a shared baseline, with rows of counts under them */
  function bars(g, m, mark, items, parts, under) {
    const H = 150;
    const stack = x => parts.map(([cls, value]) => [cls, value(x) / m.max * H]).filter(p => p[1] >= 1).map(([cls, hgt], i) => h("span", { class: `seg ${cls}${i ? "" : " cap"}`, style: `height:${Math.max(2, Math.round(hgt))}px` }));
    put(`${g}-plot`, h("div", { class: "bars" }, items.map(x => forDays(mark(h("button", { type: "button", class: x.pale ? "bar aside" : "bar" }, h("b", null, x.top), stack(x)), x), x.lit))),
      h("div", { class: "bar-labels" }, items.map(x => forDays(h("div", null, x.under), x.lit))),
      under.map(([name, value]) => h("div", { class: "bar-extra" }, h("p", null, name), h("div", { class: "mono" }, items.map(x => forDays(h("div", null, value(x)), x.lit))))));
  }
  graph("g8", (m, mark) => {
    $("g8-say").textContent = m.say;
    key("g8-key", m.key.map(([k, text]) => [`sw ${k}`, text]));
    bars("g8", m, mark, m.bars.map(x => ({ ...x, top: `$${Math.round(x.total)}`, under: x.label, lit: x.days })), [["rest", x => x.aud + x.other], ["past", x => x.past || 0], ["main", x => x.main - (x.past || 0)]],
      [["Calls the hooks refused", x => x.refused ? String(x.refused) : "·"], ["Long outputs the hooks cut short", x => x.cut ? String(x.cut) : "·"]]);
  });
  graph("g9", (m, mark) => {
    key("g9-key", m.key.map(([k, text]) => [`sw ${k}`, text]));
    // A Day's paler bar of outside-any-Day work follows its own bar, and counts in no Day's size.
    const items = m.bars.flatMap(x => [{ ...x, top: x.label, under: String(x.day), lit: [x.day] },
      ...(x.aside ? [{ ...x.aside, top: x.aside.label, under: "+", lit: [x.day], pale: true, prs: x.aside.prs, ratio: "·" }] : [])]);
    bars("g9", m, mark, items, m.key.filter(([k]) => k !== "aside").reverse().map(([k]) => [k, x => x.w[k]]),
      [["Pull requests merged", x => String(x.prs)], ["Test lines for each production line", x => x.ratio]]);
  });

  /* Graph 2 */
  graph("g2", (m, mark) => {
    key("g2-key", [["sw main", "At or under the kit's baseline, or no baseline"], ["sw over", "Above the kit's baseline"], ["dash", "Baseline"], ["sw avg", "Average so far"]]);
    // The average so far, over the row's columns on the bars' own 34px scale; the columns are centred at i + 0.5.
    const NS = "http://www.w3.org/2000/svg";
    const avgSvg = r => {
      const pts = r.avg.map(a => [m.cols.indexOf(a.day) + 0.5, 34 * (1 - a.y)]);
      const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x},${y.toFixed(1)}`).join(" "), dots = pts.map(([x, y]) => `M${x},${y.toFixed(1)} h0`).join(" ");
      const path = (cls, d) => { const p = document.createElementNS(NS, "path"); p.setAttribute("class", cls); p.setAttribute("d", d); return p; };
      const svg = document.createElementNS(NS, "svg");
      svg.setAttribute("class", "yard-avg"); svg.setAttribute("viewBox", `0 0 ${m.cols.length} 34`); svg.setAttribute("preserveAspectRatio", "none"); svg.setAttribute("aria-hidden", "true");
      svg.append(path("halo", line), path("line", line), path("dots", dots));
      return svg;
    };
    put("g2-plot", h("div", { class: "yard" },
      h("div", { class: "yard-row head" }, h("div", { class: "yard-name" }), h("div", { class: "yard-cells" }, m.cols.map(d => forDays(h("div", null, `Day ${d}`), [d]))), h("div", { class: "yard-note" })),
      m.rows.map(r => h("div", { class: "yard-row" }, h("div", { class: "yard-name" }, r.name),
        h("div", { class: "yard-cells" }, r.cells.map(c => forDays(mark(h("button", { type: "button", class: "yard-cell" }, h("b", null, c.text), h("span", { class: c.over ? "over" : "", style: `height:${px(c.h * 34)}` })), c), [c.day])),
          r.line != null && h("div", { class: "yard-line", style: `bottom:${px(r.line * 34)}` }), r.avg.length > 0 && avgSvg(r)),
        h("div", { class: "yard-note" }, r.note, r.avgNote ? h("span", { class: "yard-avg-note" }, r.avgNote) : null))),
      m.waiting.map(w => h("div", { class: "yard-row" }, h("div", { class: "yard-name" }, w.name), h("div", { class: "yard-wait" }, h("span", null, "Not measured yet: ", rich(w.why))), h("div", { class: "yard-note" }, "draws here once it is counted")))));
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
        d.lanes.map(l => h("div", { class: "lane" }, h("div", { class: "lane-name" }, h("strong", null, l.name), h("span", null, l.sub)),
          h("div", { class: "lane-bars" }, l.bars.map(b => forDays(mark(h("button", { type: "button", class: `lane-bar ${b.cls}`, style: `left:${b.x.toFixed(2)}%;width:${b.w.toFixed(2)}%` }), b), b.days)))))));
      table("g10-table", d.table);
      mark.base(d.read);
      relight();
    };
    dates.forEach((c, i) => c.addEventListener("click", () => show(i)));
    onDay.push(day => { const i = m.dates.reduce((k, d, j) => d.days.includes(day) ? j : k, -1); if (i >= 0) show(i); });
    show(m.at);
  });

  /* Graph 11 */
  graph("g11", (m, mark) => {
    $("g11-say").textContent = m.say;
    key("g11-key", [["dot run-merged", "Ended with no person"], ["dot run-fixed", "Fixed its own pull request, in that many rounds"], ["dot run-maintainer", "Parked for the maintainer"],
      ["dot run-fault square", "Parked by a fault"], ["sw wait", "The tail is how long the park waited, 10 pixels for 10 minutes"], ["dot ring", "Ringed: a session of the step crashed"]]);
    if (m.empty) { put("g11-plot", h("p", { class: "load-error" }, "Not measured yet: ", rich(m.empty))); return; }
    put("g11-plot", h("div", { class: "run-plot" },
      h("div", { class: "run-row head" }, h("div", { class: "run-day" }), h("div", { class: "run-cols" }, m.cols.map(c => h("div", { class: "run-col" }, h("strong", null, c.name), h("span", null, c.sub)))),
        h("div", { class: "run-share" }, "Steps that needed no person")),
      m.rows.map(r => forDays(h("div", { class: "run-row" }, h("div", { class: "run-day" }, r.label),
        h("div", { class: "run-cols" }, r.cells.map(list => h("div", { class: "run-cell" }, list.map(o => mark(h("button", { type: "button", class: `dot run-${o.col}${o.col === "fault" ? " square" : ""}${o.crashed ? " ring" : ""}`, style: o.wait != null ? `margin-left:${Math.min(160, o.wait).toFixed(1)}px` : "" },
          o.col === "fixed" ? String(o.fixes) : null, o.wait != null ? h("i", { class: "run-tail", style: `width:${Math.min(160, o.wait).toFixed(1)}px` }) : null), o))))),
        h("div", { class: "run-share" }, h("span", { class: "run-bar" }, h("i", { style: `width:${r.share == null ? 0 : (100 * r.share).toFixed(1)}%` })),
          h("span", { class: "mono" }, `${r.alone} of ${r.n}`), r.open ? h("span", { class: "run-open" }, `${r.open} still open`) : null)), [r.day]))));
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
