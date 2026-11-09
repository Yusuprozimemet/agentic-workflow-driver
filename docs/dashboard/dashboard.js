// The spec-drift dashboard. scripts/spec-drift.py writes the data line that calls start().
function boot(DATA) {
const R = DATA.rows;
const N = R.length;
const KIND = { spec: "Spec change", code: "Code track", close: "Close the day", other: "Other", origin: "Plan as written" };
const KVAR = { spec: "var(--spec)", code: "var(--code)", close: "var(--close)", other: "var(--other)", origin: "var(--muted)" };
const fmt = (x, d = 1) => x == null ? "–" : Number(x).toFixed(d);
const band = b => b == null ? "–" : `${fmt(b[0])}–${fmt(b[1])}°`;
// Where a merge's gap sits against its shuffled counts' 95% band, endpoints inside. It says how the
// gap compares, not that the code is right or that the difference is significant.
const bandPlace = r => r.gap_full == null || r.gap_chance_band == null ? "comparison unavailable" :
  `${r.gap_full < r.gap_chance_band[0] ? "below" : r.gap_full > r.gap_chance_band[1] ? "above" : "inside"} the shuffled-count reference band`;
// The ordinal of a percentile rounded to a whole number: 61st, 62nd, 63rd, and 11th to 13th take "th".
const ordinal = p => { const n = Math.round(p), t = n % 100; return n + (t >= 11 && t <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] || "th"); };
// PR titles come from anyone who opens a pull request, so everything from the data is escaped.
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const md = s => esc(s)
  .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
  .replace(/`([^`]+)`/g, "<code>$1</code>")
  .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
  .replace(/\*([^*\s][^*]*)\*/g, "<em>$1</em>");
const dd = n => String(n).padStart(2, "0");
const prLabel = r => r.pr ? "#" + r.pr : "start";
const dayOfFile = f => { const m = f.match(/day-(\d+)/); return m ? +m[1] : 0; };
// A day's place in the run order (plan.md): a day may run before a lower-numbered one. Mirrors ranker() in the script.
const ORDER = DATA.order || [];
const rank = d => !d ? -1 : ORDER.includes(d) ? ORDER.indexOf(d) : ORDER.length + d;
// The days that break the rising run of the order: run ahead of a lower day, or behind a higher one.
const OOO = new Set(DATA.out_of_order || []);
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const shortDate = s => `${MONTHS[+s.slice(5, 7) - 1]} ${+s.slice(8)}`;
const ranBetween = d => { const i = ORDER.indexOf(d); return [ORDER[i - 1], ORDER[i + 1]].map(x => x ? `Day ${dd(x)}` : "–"); };
const NS = "http://www.w3.org/2000/svg";
let sel = N - 1;
function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}

/* ---------- tooltip ---------- */
const tip = document.getElementById("tip");
function showTip(ev, html) {
  tip.innerHTML = html; tip.hidden = false;
  const w = tip.offsetWidth, h = tip.offsetHeight;
  let x = ev.clientX + 14, y = ev.clientY + 14;
  if (x + w > innerWidth - 8) x = ev.clientX - w - 14;
  if (y + h > innerHeight - 8) y = ev.clientY - h - 14;
  tip.style.left = Math.max(8, x) + "px"; tip.style.top = Math.max(8, y) + "px";
}
const hideTip = () => { tip.hidden = true; };
function rowTip(r) {
  return `<b>${prLabel(r)} · ${KIND[r.kind]}</b><div style="margin:3px 0 6px">${esc(r.title)}</div>
  <div class="row"><span>date</span><span>${r.date}</span></div>
  <div class="row"><span>day reached</span><span>${r.day || "–"}</span></div>
  <div class="row"><span>spec names in code</span><span>${r.name_coverage == null ? "–" : fmt(r.name_coverage * 100, 1) + "%"}</span></div>
  <div class="row"><span>spec names in production</span><span>${r.prod_name_coverage == null ? "–" : fmt(r.prod_name_coverage * 100, 1) + "%"}</span></div>
  <div class="row"><span>Jaccard, spec ∩ code</span><span>${r.jaccard == null ? "–" : fmt(r.jaccard, 2)}</span></div>
  <div class="row"><span>names kept, dropped by specs</span><span>${r.names_kept ?? "–"}</span></div>
  <div class="row"><span>Spec names retired from the code</span><span>${r.names_retired ?? "–"}</span></div>
  <div class="row"><span>name-gap angle (secondary)</span><span>${fmt(r.gap_full)}°</span></div>
  <div class="row"><span>name gap by chance</span><span>${r.gap_chance == null ? "–" : fmt(r.gap_chance) + "°"} <small>(${band(r.gap_chance_band)})</small></span></div>
  <div class="row"><span>reached names in code</span><span>${r.coverage == null ? "–" : fmt(r.coverage * 100, 1) + "%"}</span></div>
  <div class="row"><span>service code out</span><span>${movedShare(r) == null ? "–" : fmt(movedShare(r)) + "%"}</span></div>`;
}

/* ---------- derived numbers ---------- */
const first = R[0], last = R[N - 1];
// A merge with no gap angle (no spec name in the code yet) takes no step, to it or from it.
const step = (a, b) => a == null || b == null ? 0 : +(b - a).toFixed(2);
const byKind = { spec: 0, code: 0, close: 0, other: 0 };
// A commit with no PR is the plan as written, as in the kind charts: it moves no kind's share.
for (let i = 1; i < N; i++) if (R[i].kind in byKind) byKind[R[i].kind] += step(R[i - 1].gap_full, R[i].gap_full);
const gapClosed = -Object.values(byKind).reduce((a, b) => a + b, 0);
// With no gap closed there is no share: "–", not NaN.
const ofGap = x => gapClosed ? `${Math.round(-x / gapClosed * 100)}%` : "–";
const firstGap = R.find(r => r.gap_full != null) || first;
const specShare = -byKind.spec / gapClosed;
// Degrees with their sign, − closer and + away, and what a kind's sum did to the gap.
const gapDeg = x => (x > 0 ? "+" : x < 0 ? "−" : "±") + fmt(Math.abs(x), 1) + "°";
const gapMove = x => x > 0 ? `widened it by ${fmt(x, 1)}°` : x < 0 ? `closed it by ${fmt(-x, 1)}°` : "did not move it";
const thousands = n => n == null ? "–" : Number(n).toLocaleString("en-US");
const nKind = k => R.filter(r => r.kind === k).length;
// A count and its noun, singular for one: "1 day", "2 days".
const many = (n, one, more = one + "s") => `${n} ${n === 1 ? one : more}`;
let forward = 0, specEdits = 0;
R.forEach(r => {
  for (const [f, n] of Object.entries(r.spec_files || {})) {
    const d = dayOfFile(f);
    if (!d) continue;
    specEdits += n;
    if (rank(d) > rank(r.day)) forward += n;
  }
});

/* ---------- stats ---------- */
document.getElementById("stats").innerHTML = `
  <div class="stat"><span class="k">Spec names in the code · Jaccard</span>
    <span class="v num">${last.name_coverage == null ? "–" : fmt(last.name_coverage * 100, 1) + "%"} <small>· ${last.jaccard == null ? "–" : fmt(last.jaccard, 2)}</small></span>
    <span class="n">Of the backticked names the specs use today, the share the code has${last.spec_names == null ? "" : ` (${last.names_in_code} of ${last.spec_names}; in production, ${last.names_in_prod})`}; Jaccard is the names in both over the names in either.</span>
    <span class="n" style="color:var(--muted)">Name-gap angle (secondary): ${fmt(firstGap.gap_full)}° → ${fmt(last.gap_full)}°, ${fmt(gapClosed)}° closed across ${N - 1} merges; ${fmt(last.gap_chance)}° by chance (95%: ${band(last.gap_chance_band)}). ${last.names_kept == null ? "" : `${last.names_kept} names the specs dropped are still in the code. `}${last.names_retired == null ? "" : `${last.names_retired} of the names not in the code were there at an earlier merge: retired, still counted as missing. `}${last.coverage == null ? "" : `${fmt(last.coverage * 100, 1)}% of the names the reached days use are in the code.`}</span></div>
  <div class="stat" title="Share of the gap closed: spec ${ofGap(byKind.spec)}, code ${ofGap(byKind.code)}"><span class="k">Name gap moved, by kind of PR</span>
    <span class="v num">net ${gapDeg(-gapClosed)}</span>
    <span class="n"><span class="sw" style="background:var(--spec)"></span>${many(nKind("spec"), "spec-change PR")} ${gapMove(byKind.spec)}${byKind.spec > 0 ? ", naming what was not built yet" : ""}; <span class="sw" style="background:var(--code)"></span>${many(nKind("code"), "code PR")} ${gapMove(byKind.code)}. Signed as in “Total pull in each direction”: − is closer.</span></div>
  <div class="stat"><span class="k">Spec text since ${shortDate(R[0].date)}</span>
    <span class="v num">${thousands(last.deleted)} <small>of ${thousands(DATA.origin_lines)} original spec lines rewritten · ${thousands(last.added)} added</small></span>
    <span class="n">${Math.round(last.deleted / DATA.origin_lines * 100)}% of the spec as written rewritten, the rest kept</span></div>`;
document.getElementById("headline").textContent = specShare >= -byKind.code / gapClosed
  ? "The plan moved to meet the code" : "The spec leads, the code follows";
document.querySelectorAll(".vocab-n").forEach(e => { e.textContent = DATA.vocab_size; });
const merged = R.filter(r => r.pr).map(r => r.pr);
document.getElementById("pr-range").textContent = many(N - 1, "merge") + (merged.length ? `, #${Math.min(...merged)}–#${Math.max(...merged)}` : "");
document.getElementById("gap-chance").textContent = `${fmt(last.gap_chance)}° (95%: ${band(last.gap_chance_band)})`;
document.getElementById("caveats").innerHTML = ((DATA.meta || {}).caveats || []).map(c => `<li>${esc(c)}</li>`).join("");
// spec-drift.py's example-data fallback (demo: true): say so under the header until the first day spec merges.
const banner = document.getElementById("demo-banner");
banner.textContent = "Example data: this project has no day specs yet. The page will show real data after the first day spec merges.";
banner.hidden = DATA.demo !== true;

/* ---------- scrubber ---------- */
const scrub = document.getElementById("pr-scrub");
scrub.max = N - 1; scrub.value = sel;
scrub.addEventListener("input", () => setSel(+scrub.value));
let timer = null;
const playBtn = document.getElementById("play");
function stop() { clearInterval(timer); timer = null; playBtn.textContent = "▶ Replay"; }
playBtn.addEventListener("click", () => {
  if (timer) return stop();
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) { setSel(N - 1); return; }
  playBtn.textContent = "❚❚ Pause";
  let i = sel >= N - 1 ? 0 : sel;
  setSel(i);
  timer = setInterval(() => { i++; if (i >= N) return stop(); setSel(i); }, 260);
});

/* ---------- sparklines beside the selected merge ---------- */
const SPARK_W = 96, SPARK_H = 20;
const spX = i => +(i / Math.max(1, N - 1) * SPARK_W).toFixed(1);
const spY = (v, hi) => +(SPARK_H - 2 - Math.min(1, v / hi) * (SPARK_H - 4)).toFixed(1);
// The top of a scale: the largest value, or a high percentile when one huge merge should not flatten the rest.
const scaleTop = (get, p = 1) => { const s = R.map(get).filter(v => v > 0).sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(p * s.length))] || 1; };
// A line over every merge, broken where a merge has no value, so a gap shows as a gap.
const linePath = (get, hi) => R.map((r, i) => get(r) == null ? "" : `${i && get(R[i - 1]) != null ? "L" : "M"}${spX(i)},${spY(get(r), hi)}`).join("");
// One bar per merge, up from the baseline; a value past the top is clipped.
const barPath = (get, hi) => R.map((r, i) => get(r) ? `M${spX(i)},${SPARK_H - 1}V${spY(get(r), hi)}` : "").join("");
const specTotal = r => Object.values(r.spec_files || {}).reduce((a, b) => a + b, 0);
const SPARK_SERIES = {
  names: [{ get: r => r.name_coverage, hi: 1, color: "var(--code)" }, { get: r => r.jaccard, hi: 1, color: "var(--muted)", dash: true }],
  prod: [{ get: r => r.prod_name_coverage, hi: 1, color: "var(--code)" }],
  kept: [{ get: r => r.names_kept, hi: scaleTop(r => r.names_kept), color: "var(--code)" }],
  retired: [{ get: r => r.names_retired, hi: scaleTop(r => r.names_retired), color: "var(--code)" }],
  gap: [{ get: r => r.gap_full, hi: scaleTop(r => r.gap_full), color: "var(--gap)" }],
  coverage: [{ get: r => r.coverage, hi: 1, color: "var(--code)" }],
  code: [{ get: r => r.code_churn, hi: scaleTop(r => r.code_churn, 0.95), color: "var(--code)", bars: true }],
  spec: [{ get: specTotal, hi: scaleTop(specTotal, 0.95), color: "var(--spec)", bars: true }],
};
// The paths are made once; a redraw only adds the dot at the selected merge.
const SPARK = Object.fromEntries(Object.entries(SPARK_SERIES).map(([k, ss]) =>
  [k, ss.map(s => ({ ...s, d: s.bars ? barPath(s.get, s.hi) : linePath(s.get, s.hi) }))]));
const sparkHtml = k => `<svg viewBox="0 0 ${SPARK_W} ${SPARK_H}" preserveAspectRatio="none" role="img" aria-label="Trend across merges, dot at the selected merge">`
  + SPARK[k].map(s => {
    const v = s.get(R[sel]);
    // The dot is a zero-length round stroke, not a circle: it stays round however the svg is stretched.
    return `<path d="${s.d}" fill="none" stroke="${s.color}" stroke-width="1.25" vector-effect="non-scaling-stroke"${s.dash ? ' stroke-dasharray="3 2"' : ""}/>`
      + (v == null ? "" : `<path d="M${spX(sel)},${spY(v, s.hi)}h0" stroke="var(--ink)" stroke-width="5" stroke-linecap="round" vector-effect="non-scaling-stroke"/>`);
  }).join("") + "</svg>";

// A name share with its counts; with no spec name there is nothing to divide, which is not 0% or 100%.
// Data from before the counts were kept has no spec_names: the share alone, or – without one.
const nameShare = (x, n, d) => x == null ? (d === 0 ? "not measured: no extracted spec names" : "–")
  : `${fmt(x * 100, 1)}%` + (d == null ? "" : ` <small>${n}/${d}</small>`);
// The names behind the two shares: each found only outside production with its places and paths, then the missing.
function nameLists(s) {
  if (s.names_outside_prod == null) return "";  // data from before the lists were kept
  const out = Object.entries(s.names_outside_prod), absent = s.names_absent || [];
  return `<details class="names"><summary>Present only outside production <span class="num">(${out.length})</span></summary>
      ${out.length ? `<ul>${out.map(([n, at]) => `<li><code>${esc(n)}</code> ${Object.entries(at).map(([p, fs]) =>
        `<span class="chip">${esc(p)}</span> ${fs.map(f => `<code class="path">${esc(f)}</code>`).join(" ")}`).join(" ")}</li>`).join("")}</ul>` : "<p>None.</p>"}
    </details>
    <details class="names"><summary>Absent from all scanned code <span class="num">(${absent.length})</span></summary>
      ${absent.length ? `<ul>${absent.map(n => `<li><code>${esc(n)}</code></li>`).join("")}</ul>` : "<p>None.</p>"}
    </details>`;
}

function drawReadout() {
  const s = R[sel], prev = R[Math.max(0, sel - 1)];
  const dGap = s.gap_full - prev.gap_full, specLines = Object.values(s.spec_files || {}).reduce((a, b) => a + b, 0);
  const sign = x => (x > 0 ? "+" : x < 0 ? "−" : "±") + Math.abs(x).toFixed(2);
  const edits = Object.entries(s.spec_files || {}).sort((a, b) => b[1] - a[1]);
  const against = s.gap_excess == null ? "comparison unavailable" :
    `${sign(s.gap_excess)}° ${s.gap_excess < 0 ? "below" : "above"} chance, ${ordinal(s.gap_percentile)} percentile of the shuffles`;
  const moved = sel === 0 ? "Starting point: the code and the plan written for it." :
    !specLines && Math.abs(dGap) < 0.05 ? "Neither the spec nor the gap moved noticeably." :
    !specLines ? `Only the code moved. The gap ${dGap < 0 ? "narrowed" : "widened"} by ${Math.abs(dGap).toFixed(2)}°.` :
    `${specLines} spec lines changed and the gap ${dGap < 0 ? "narrowed" : "widened"} by ${Math.abs(dGap).toFixed(2)}°.`;
  document.getElementById("readout").innerHTML = `
    <div class="eyebrow">Selected merge</div>
    <div class="title">${prLabel(s)} · ${esc(s.title)}</div>
    <div><span class="chip" style="color:${KVAR[s.kind]}">${KIND[s.kind]}</span> <span class="num" style="color:var(--muted);font-size:12.5px;margin-left:6px">${s.sha} · ${s.date}</span></div>
    <p style="font-size:14px;color:var(--ink-2)">${moved}</p>
    <div class="hr"></div>
    <dl>
      <dt>Spec names in code, all places</dt><dd>${nameShare(s.name_coverage, s.names_in_code, s.spec_names)}</dd><dd class="spark">${sparkHtml("names")}</dd>
      <dt>Spec names in production</dt><dd>${nameShare(s.prod_name_coverage, s.names_in_prod, s.spec_names)}</dd><dd class="spark">${sparkHtml("prod")}</dd>
      <dt>Jaccard, spec ∩ code</dt><dd>${s.jaccard == null ? "–" : fmt(s.jaccard, 2)}</dd><dd></dd>
      <dt>Names the specs dropped, still in code</dt><dd>${s.names_kept ?? "–"}</dd><dd class="spark">${sparkHtml("kept")}</dd>
      <dt>Spec names retired from the code</dt><dd>${s.names_retired ?? "–"}</dd><dd class="spark">${sparkHtml("retired")}</dd>
      <dt>Spec–code name-gap angle (secondary)</dt><dd>${fmt(s.gap_full, 2)}° <span style="color:var(--muted)">(${sign(dGap)})</span></dd><dd class="spark">${sparkHtml("gap")}</dd>
      <dt>Against shuffled counts (95%: ${band(s.gap_chance_band)})</dt><dd>${bandPlace(s)}</dd><dd></dd>
      <dt>Name gap less its chance value</dt><dd>${against}</dd><dd></dd>
      <dt>Reached-day names in code</dt><dd>${s.coverage == null ? "–" : fmt(s.coverage * 100, 1) + "%"}</dd><dd class="spark">${sparkHtml("coverage")}</dd>
      <dt>Code lines changed</dt><dd>${s.code_churn.toLocaleString()}</dd><dd class="spark">${sparkHtml("code")}</dd>
      <dt>Spec lines changed</dt><dd>${edits.reduce((a, b) => a + b[1], 0)}</dd><dd class="spark">${sparkHtml("spec")}</dd>
    </dl>
    <p class="limit">Vocabulary: matches extracted names, not behavior. Test and tool names may legitimately be absent from production.
      Gap: compared with seeded shuffles of name counts; this is not a correctness test.</p>
    ${nameLists(s)}
    ${edits.length ? `<div style="font-size:12.5px;color:var(--ink-2)">${edits.slice(0, 5).map(([f, n]) => `<div style="display:flex;justify-content:space-between;gap:10px"><code>${esc(f.replace("specs/", ""))}</code><span class="num">${n}</span></div>`).join("")}${edits.length > 5 ? `<div style="color:var(--muted)">+${edits.length - 5} more files</div>` : ""}</div>` : ""}`;
}

/* ---------- line charts ---------- */
const LW = 1000, LP = { l: 44, r: 104, t: 14, b: 60 };
// A lone row (no merge yet) sits mid-plot, and its strip cell, i ± 0.5, spans the plot.
const lx = i => LP.l + (N > 1 ? i / (N - 1) : i + 0.5) * (LW - LP.l - LP.r);
function dayStarts() {
  const out = []; let d = -1;
  R.forEach((r, i) => { if (r.day !== d) { out.push([i, r.day]); d = r.day; } });
  return out;
}
// The first merge of each calendar day: the x axis is merges, so a busy date takes more width.
function dateStarts() {
  return R.map((r, i) => [i, r.date]).filter(([i, s]) => !i || R[i - 1].date !== s);
}
const steps = (lo, hi, n) => Array.from({ length: n + 1 }, (_, i) => +(lo + (hi - lo) * i / n).toFixed(1));
// The out-of-order days that have a merge: one not run yet has no day label for a * to mark.
const oooRun = () => [...OOO].filter(d => R.some(r => r.day === d)).sort((a, b) => rank(a) - rank(b));
// The key to the * on a day label, under any axis that draws day labels; there is none when no day ran out of order.
function oooNote(box) {
  const days = oooRun();
  if (!days.length) return;
  box.insertAdjacentHTML("beforeend", `<p class="axis-note">* Day run out of number order: ${days.map(d => "D" + dd(d)).join(", ")}.</p>`);
}
// bands: [{ color, get: r => [lo, hi] }], shaded under the lines.
// empty: what the chart says instead, when no solid line has a point yet.
function lineChart(box, { H, yMin, yMax, ticks, unit, series, bands, label, strip, digits = 1, empty }) {
  box.innerHTML = "";
  if (empty && !series.some(s => !s.dash && R.some(r => s.get(r) != null))) { box.innerHTML = `<p class="load-error">${empty}</p>`; return; }
  const svg = el("svg", { viewBox: `0 0 ${LW} ${H}`, role: "img", "aria-label": label }, box);
  const ly = v => LP.t + (1 - (v - yMin) / (yMax - yMin)) * (H - LP.t - LP.b);
  ticks.forEach(t => {
    el("line", { x1: LP.l, x2: LW - LP.r, y1: ly(t), y2: ly(t), stroke: "var(--grid)" }, svg);
    el("text", { x: LP.l - 8, y: ly(t) + 4, "text-anchor": "end", class: "num" }, svg).textContent = t + unit;
  });
  el("line", { x1: LP.l, x2: LW - LP.r, y1: H - LP.b, y2: H - LP.b, stroke: "var(--axis)" }, svg);
  let lastX = -99;
  dayStarts().forEach(([i, d]) => {
    if (!d || lx(i) - lastX < 34) return;
    lastX = lx(i);
    el("line", { x1: lx(i), x2: lx(i), y1: LP.t, y2: H - LP.b, stroke: "var(--grid)", "stroke-dasharray": "2 3" }, svg);
    const t = el("text", { x: lx(i) + 3, y: H - LP.b + (strip ? 30 : 16), class: "num" + (OOO.has(d) ? " ooo" : "") }, svg);
    t.textContent = "D" + dd(d) + (OOO.has(d) ? "*" : "");
  });
  let lastDate = -99;
  dateStarts().forEach(([i, s]) => {
    el("line", { x1: lx(i), x2: lx(i), y1: H - LP.b, y2: H - LP.b + (strip ? 36 : 22), stroke: "var(--axis)" }, svg);
    if (lx(i) - lastDate < 44) return;
    lastDate = lx(i);
    el("text", { x: lx(i) + 3, y: H - LP.b + (strip ? 46 : 32), class: "date" }, svg).textContent = shortDate(s);
  });
  if (strip) {
    // A merge's cell runs halfway to each neighbour, clipped to the plot: with few merges a cell is wide, and the end ones ran off the card.
    const edge = x => Math.min(LW - LP.r, Math.max(LP.l, x));
    R.forEach((r, i) => {
      const a = edge(lx(i - 0.5)), b = edge(lx(i + 0.5));
      el("rect", { x: a + 1, y: H - LP.b + 5, width: Math.max(2, b - a - 2), height: 8, rx: 2, fill: KVAR[r.kind] }, svg);
    });
  }
  el("line", { x1: lx(sel), x2: lx(sel), y1: LP.t, y2: H - LP.b, stroke: "var(--ink-2)", "stroke-width": 1 }, svg);
  const cross = el("line", { x1: 0, x2: 0, y1: LP.t, y2: H - LP.b, stroke: "var(--muted)", "stroke-dasharray": "3 3", visibility: "hidden" }, svg);
  (bands || []).forEach(b => {
    const pts = R.map((r, i) => [i, b.get(r)]).filter(p => p[1] != null);
    if (!pts.length) return;
    const edge = k => pts.map(([i, v]) => `${lx(i)},${ly(v[k])}`);
    el("polygon", { points: [...edge(0), ...edge(1).reverse()].join(" "), fill: b.color, "fill-opacity": 0.12, stroke: "none" }, svg);
  });
  const labels = [];
  series.forEach(s => {
    const pts = R.map((r, i) => [i, s.get(r)]).filter(p => p[1] != null);
    if (!pts.length) return;
    el("polyline", { points: pts.map(([i, v]) => `${lx(i)},${ly(v)}`).join(" "), fill: "none", stroke: s.color, "stroke-width": s.dash ? 1.5 : 2, "stroke-linejoin": "round", "stroke-linecap": "round", ...(s.dash ? { "stroke-dasharray": "5 4" } : {}) }, svg);
    const v = s.get(R[sel]);
    if (v != null && !s.dash) el("circle", { cx: lx(sel), cy: ly(v), r: 5, fill: s.color, stroke: "var(--surface)", "stroke-width": 2 }, svg);
    const end = pts[pts.length - 1];
    labels.push({ x: lx(end[0]) + 10, y: ly(end[1]) + 4 + (s.dy || 0), text: s.end || `${s.name} ${fmt(end[1], digits)}${unit}` });
  });
  // End labels top to bottom, each at least a line below the one above, so close lines keep readable labels.
  labels.sort((a, b) => a.y - b.y).reduce((above, l) => {
    l.y = Math.max(l.y, above + 11);
    el("text", { x: l.x, y: l.y, class: "lbl" }, svg).textContent = l.text;
    return l.y;
  }, -Infinity);
  const hit = el("rect", { x: LP.l - 6, y: 0, width: LW - LP.l - LP.r + 12, height: H, class: "hit" }, svg);
  const idxAt = ev => {
    const p = svg.createSVGPoint(); p.x = ev.clientX; p.y = ev.clientY;
    const q = p.matrixTransform(svg.getScreenCTM().inverse());
    return Math.max(0, Math.min(N - 1, Math.round((q.x - LP.l) / (LW - LP.l - LP.r) * (N - 1))));
  };
  hit.addEventListener("mousemove", ev => { const i = idxAt(ev); cross.setAttribute("x1", lx(i)); cross.setAttribute("x2", lx(i)); cross.setAttribute("visibility", "visible"); showTip(ev, rowTip(R[i])); });
  hit.addEventListener("mouseleave", () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
  hit.addEventListener("click", ev => setSel(idxAt(ev)));
  oooNote(box);
}
// The axes follow the data, so a later phase that pushes the gap or coverage past today's range stays on the chart.
// At least one 15° step: with no gap yet the axis was 0 to 0, its ticks 0/0, and drew "NaN°".
// The gap less its chance runs both ways about zero, out to its largest value or band end, in 5° steps and at least 5° each way.
const exValues = R.flatMap(r => [r.gap_excess, ...(r.gap_excess_band || [])]).filter(v => v != null).map(Math.abs);
const exMax = Math.max(5, Math.ceil(Math.max(0, ...exValues) / 5) * 5);
const coverPct = v => v == null ? null : +(v * 100).toFixed(2);
// The cover chart's shares of a merge: in code, then production, tests and flags.
const coverShares = [r => r.coverage, r => r.class_coverage?.prod, r => r.class_coverage?.test, r => r.class_coverage?.flags];
const covMin = Math.max(0, Math.min(92, Math.floor(Math.min(...R.flatMap(r => coverShares.map(f => f(r))).filter(v => v != null).map(v => v * 100)) / 10) * 10));
function drawLines() {
  // The legend's sample is this repository's first out-of-order day, and there is no key when none ran out of order.
  const key = document.getElementById("ooo-key"), first = oooRun()[0];
  if (key) { if (first == null) key.style.display = "none"; else key.querySelector("b").textContent = "D" + dd(first) + "*"; }
  lineChart(document.getElementById("lines"), {
    H: 330, yMin: -exMax, yMax: exMax, ticks: steps(-exMax, exMax, 2 * exMax / 5), unit: "°", strip: true,
    label: "Spec–code name gap minus its chance value, in degrees, across merges",
    series: [
      { name: "gap", color: "var(--gap)", get: r => r.gap_excess ?? null },
      { name: "chance", color: "var(--gap)", dash: true, get: () => 0 },
    ],
    bands: [{ color: "var(--gap)", get: r => r.gap_excess_band ?? null }],
  });
  lineChart(document.getElementById("cover"), {
    H: 190, yMin: covMin, yMax: 100, ticks: steps(covMin, 100, 4), unit: "%", strip: false,
    label: "Share of reached-day spec names present in code, all and by class",
    series: [
      { name: "in code", color: "var(--code)", get: r => coverPct(r.coverage) },
      { name: "prod", color: "var(--close)", end: "production", get: r => coverPct(r.class_coverage?.prod) },
      { name: "test", color: "var(--muted)", end: "tests", get: r => coverPct(r.class_coverage?.test) },
      { name: "flags", color: "var(--spec)", end: "flags", get: r => coverPct(r.class_coverage?.flags) },
    ],
  });
  // The names behind the cover chart: the latest merge's, split by class, with the flags apart.
  const names = last.class_names, named = names ? names.prod + names.test : 0;
  document.getElementById("class-share").textContent = named ? `Of the ${named} code names the specs use at the latest merge, ${names.test} (${Math.round(100 * names.test / named)}%) are test names, ${names.prod} production identifiers; the specs also name ${names.flags} flags, counted apart because they do not enter the gap.` : "";
  lineChart(document.getElementById("evidence-history"), {
    H: 190, yMin: 0, yMax: evMax, ticks: steps(0, evMax, 4), unit: "", strip: false, digits: 0,
    label: "Tests named by finished days: present on each merge, not running (orange), retired (grey)",
    series: [
      { name: "present", color: "var(--close)", get: r => r.evidence && r.evidence.present },
      { name: "not running", color: "var(--code)", dy: 8, get: r => r.evidence && r.evidence.skippable + r.evidence.missing },
      { name: "retired", color: "var(--muted)", dy: -7, get: r => r.evidence && (r.evidence.retired || 0) },
    ],
  });
  lineChart(document.getElementById("moved"), {
    H: 190, yMin: 0, yMax: 100, ticks: steps(0, 100, 4), unit: "%", strip: false,
    label: "Share of the services' main source lines in their own directories",
    empty: "No service code yet: the share counts the packages under <code>services</code> in <code>spec-drift.config.json</code>, and the code has none.",
    series: [{ name: "out", color: "var(--close)", get: r => movedShare(r) }],
  });
  lineChart(document.getElementById("churn"), {
    H: 220, yMin: 0, yMax: 100, ticks: steps(0, 100, 4), unit: "%", strip: true,
    label: "Spec and code lines changed so far, each as a share of its own total",
    series: [
      { name: "code", color: "var(--code)", end: "code", dy: -7, get: r => cumShare(r, "code") },
      { name: "spec", color: "var(--spec)", end: "spec", dy: 8, get: r => cumShare(r, "spec") },
    ],
  });
  lineChart(document.getElementById("test-ratio"), {
    H: 200, yMin: 0, yMax: ratioMax, ticks: steps(0, ratioMax, ratioMax <= 6 ? ratioMax : 4),
    unit: "×", strip: false, digits: 2,
    empty: `No ratio yet: it starts once ${RATIO_FROM.toLocaleString("en")} production lines have changed; ${(WORK.get(last).prod || 0).toLocaleString("en")} so far.`,
    label: "Test lines changed so far per production line changed so far",
    series: [
      { name: "one to one", color: "var(--muted)", dash: true, end: "1 : 1", get: () => 1 },
      { name: "tests", color: "var(--close)", get: r => testRatio(r) },
    ],
  });
  const p = R[sel].placed || {};
  document.getElementById("placed").innerHTML = `<p>At ${prLabel(R[sel])}: ` + (Object.keys(p).sort().map(s =>
    `<b>${s}</b> ${p[s][1] ? (p[s][0] ? `${p[s][1]} lines out, ${p[s][0]} still in place` : `out (${p[s][1]} lines)`) : `in place (${p[s][0]} lines)`}`).join(" · ")
    || "no service code.") + "</p>";
}
const movedShare = r => {
  const v = Object.values(r.placed || {}), all = v.reduce((a, [i, o]) => a + i + o, 0);
  return all ? +(v.reduce((a, [, o]) => a + o, 0) / all * 100).toFixed(1) : null;
};
const evMax = Math.max(4, Math.ceil(Math.max(0, ...R.map(r => r.evidence ? r.evidence.present : 0)) / 20) * 20);
// Code lines outnumber spec lines several times over, so each runs to 100% of its own total rather than sharing a scale.
const CUM = new Map();
R.reduce(([s, c], r) => {
  const next = [s + Object.values(r.spec_files || {}).reduce((a, b) => a + b, 0), c + (r.code_churn || 0)];
  CUM.set(r, next); return next;
}, [0, 0]);
const cumShare = (r, k) => { const [s, c] = CUM.get(r), [S, C] = CUM.get(last); return k === "spec" ? (S ? s / S * 100 : 0) : (C ? c / C * 100 : 0); };
// Lines per box, summed merge by merge; the ratio waits for 1,000 production lines, so tests written before any code do not read as a spike.
const WORK = new Map();
R.reduce((acc, r) => {
  const next = { ...acc };
  Object.entries(r.work || {}).forEach(([k, v]) => { next[k] = (next[k] || 0) + v; });
  next.fixtures = (acc.fixtures || 0) + (r.test_fixtures || 0);
  WORK.set(r, next); return next;
}, {});
const RATIO_FROM = 1000;
// Fixture lines (golden files, sample data) stay in the Tests box but are not tests the ratio counts.
const testRatio = r => { const w = WORK.get(r); return w.prod >= RATIO_FROM ? +(((w.test || 0) - w.fixtures) / w.prod).toFixed(2) : null; };
const ratioMax = Math.max(2, Math.ceil(Math.max(0, ...R.map(testRatio).filter(v => v != null))));
// One bar, split into boxes in order; a box's share is printed inside it when there is room.
function shareBar(box, parts, label) {
  box.innerHTML = "";
  const H = 40, total = parts.reduce((a, p) => a + p.value, 0) || 1, P = { l: 0, r: 0 };
  const svg = el("svg", { viewBox: `0 0 ${LW} ${H}`, role: "img", "aria-label": label }, box);
  let x = P.l;
  parts.forEach(p => {
    const w = p.value / total * (LW - P.l - P.r);
    if (!w) return;
    const rect = el("rect", { x: x + 1, y: 4, width: Math.max(1, w - 2), height: H - 8, rx: 3, fill: p.color, ...(p.opacity == null ? {} : { opacity: p.opacity }) }, svg);
    if (w > 54) el("text", { x: x + 10, y: H / 2 + 5, class: "num", style: "fill:var(--surface);font-weight:600" }, svg).textContent = fmt(p.value / total * 100, 0) + "%";
    rect.addEventListener("mousemove", ev => showTip(ev, `<b>${esc(p.name)}</b>${p.tip || ""}<div class="row"><span>share</span><span>${fmt(p.value / total * 100, 1)}%</span></div>`));
    rect.addEventListener("mouseleave", hideTip);
    x += w;
  });
}
function drawWork() {
  const w = WORK.get(last), n = k => w[k] || 0;
  const row = (k, v) => `<div class="row"><span>${k}</span><span>${v.toLocaleString()}</span></div>`;
  const parts = [
    { name: "Specs", value: n("spec"), color: "var(--spec)", tip: row("plan.md and specs/", n("spec")) },
    { name: "Context", value: n("context"), color: "var(--w-context)", tip: row("CLAUDE.md, agents, README, docs", n("context")) },
    { name: "Production code", value: n("prod"), color: "var(--code)", tip: row("code and config", n("prod")) },
    { name: "Tests and verification", value: n("test") + n("tooling"), color: "var(--close)",
      tip: row("tests", n("test")) + row("scripts, CI, dashboard", n("tooling")) },
  ];
  shareBar(document.getElementById("work-bar"), parts, "Lines changed in merged pull requests, by what the file is");
  document.getElementById("work-legend").innerHTML = parts.map(p =>
    `<span><i class="dot" style="background:${p.color}"></i>${p.name} · ${kilo(p.value)}</span>`).join("")
    + `<span>${fmt(n("test") / Math.max(1, n("prod")), 1)} test lines per production line</span>`;
}
const gapDelta = i => step(R[i - 1].gap_full, R[i].gap_full);
const signed = (x, d = 2) => (x > 0 ? "+" : x < 0 ? "−" : "") + fmt(Math.abs(x), d);

/* ---------- per-merge change in gap ---------- */
// A panel on the merge axis of the line chart above: the step each merge took on the gap.
function drawDeltas() {
  const box = document.getElementById("deltas");
  box.innerHTML = "";
  const panels = [
    { name: "gap", label: "Δ gap", get: r => r.gap_full },
  ];
  const PH = 200, GAP = 18, H = LP.t + panels.length * PH + (panels.length - 1) * GAP + 40;
  const svg = el("svg", { viewBox: `0 0 ${LW} ${H}`, role: "img", "aria-label": "Change in gap at each merge, in merge order" }, box);
  panels.forEach((pn, k) => {
    const top = LP.t + k * (PH + GAP), bot = top + PH;
    const pts = R.slice(1).map((r, j) => ({ i: j + 1, r, d: step(pn.get(R[j]), pn.get(r)) }));
    const lo = Math.min(0, ...pts.map(p => p.d)), hi = Math.max(0, ...pts.map(p => p.d));
    const unit = hi - lo > 4 ? 1 : 0.5, yMin = Math.floor(lo / unit) * unit, yMax = Math.max(Math.ceil(hi / unit) * unit, yMin + unit);
    const ly = v => top + (1 - (v - yMin) / (yMax - yMin)) * PH;
    for (let t = yMin; t <= yMax + 1e-9; t += unit) {
      el("line", { x1: LP.l, x2: LW - LP.r, y1: ly(t), y2: ly(t), stroke: Math.abs(t) < 1e-9 ? "var(--axis)" : "var(--grid)" }, svg);
      el("text", { x: LP.l - 8, y: ly(t) + 4, "text-anchor": "end", class: "num" }, svg).textContent = signed(t, t % 1 ? 1 : 0) + "°";
    }
    el("rect", { x: LP.l, y: top, width: LW - LP.l - LP.r, height: PH, fill: "none", stroke: "var(--axis)" }, svg);
    el("text", { x: LW - LP.r + 10, y: top + 16, class: "lbl" }, svg).textContent = pn.label;
    const net = pts.reduce((a, p) => a + p.d, 0);
    el("text", { x: LW - LP.r + 10, y: top + 34, class: "num" }, svg).textContent = `net ${signed(net, 1)}°`;
    let lastX = -99;
    dayStarts().forEach(([i, d]) => {
      if (!d || lx(i) - lastX < 34) return;
      lastX = lx(i);
      el("line", { x1: lx(i), x2: lx(i), y1: top, y2: bot, stroke: "var(--grid)", "stroke-dasharray": "2 3" }, svg);
      if (k === panels.length - 1) {
        const t = el("text", { x: lx(i) + 3, y: bot + 16, class: "num" + (OOO.has(d) ? " ooo" : "") }, svg);
        t.textContent = "D" + dd(d) + (OOO.has(d) ? "*" : "");
      }
    });
    el("line", { x1: lx(sel), x2: lx(sel), y1: top, y2: bot, stroke: "var(--ink-2)", "stroke-width": 1 }, svg);
    pts.forEach(p => {
      el("circle", { cx: lx(p.i), cy: ly(p.d), r: 3.5, fill: KVAR[p.r.kind], stroke: "var(--surface)", "stroke-width": 1 }, svg);
      if (p.i === sel) el("circle", { cx: lx(p.i), cy: ly(p.d), r: 7, fill: "none", stroke: "var(--ink)", "stroke-width": 1.5 }, svg);
      const hit = el("circle", { cx: lx(p.i), cy: ly(p.d), r: 7, class: "hit" }, svg);
      hit.addEventListener("mousemove", ev => showTip(ev, rowTip(p.r) + `<div class="row"><span>change in ${pn.name}</span><span>${signed(p.d)}°</span></div>`));
      hit.addEventListener("mouseleave", hideTip);
      hit.addEventListener("click", () => setSel(p.i));
    });
  });
  let lastDate = -99;
  const bot = H - 40 + 4;
  dateStarts().forEach(([i, s]) => {
    if (lx(i) - lastDate < 44) return;
    lastDate = lx(i);
    el("text", { x: lx(i) + 3, y: bot + 28, class: "date" }, svg).textContent = shortDate(s);
  });
  oooNote(box);
}

/* ---------- what each spec change did to the gap ---------- */
// One point per spec-change PR: the names it added to the specs (production and test; flags do not
// enter the gap) against its step on the gap less chance. A PR that added none but dropped some is a
// hollow diamond, so a pure removal does not read as a dot at "nothing happened".
const sumPT = c => c ? c.prod + c.test : 0;
const SPEC_STEPS = R.map((r, i) => ({ r, i })).filter(p => p.i && p.r.kind === "spec" && p.r.names_added
  && p.r.gap_excess != null && R[p.i - 1].gap_excess != null)
  .map(p => ({ ...p, x: sumPT(p.r.names_added), out: sumPT(p.r.names_dropped), d: step(R[p.i - 1].gap_excess, p.r.gap_excess) }));
function drawSpecSteps() {
  const box = document.getElementById("spec-steps");
  box.innerHTML = "";
  if (!SPEC_STEPS.length) { box.innerHTML = '<p class="load-error">No spec-change PR has merged yet.</p>'; return; }
  const H = 300, top = LP.t, bot = H - 44, left = LP.l, right = LW - LP.r;
  const xMax = Math.max(10, Math.ceil(Math.max(...SPEC_STEPS.map(p => p.x)) / 10) * 10);
  const lo = Math.min(0, ...SPEC_STEPS.map(p => p.d)), hi = Math.max(0, ...SPEC_STEPS.map(p => p.d));
  const unit = hi - lo > 8 ? 2 : 1, yMin = Math.floor(lo / unit) * unit, yMax = Math.max(Math.ceil(hi / unit) * unit, yMin + unit);
  const sx = v => left + v / xMax * (right - left), sy = v => top + (1 - (v - yMin) / (yMax - yMin)) * (bot - top);
  const svg = el("svg", { viewBox: `0 0 ${LW} ${H}`, role: "img", "aria-label": "Names each spec-change PR added, against its step on the gap less chance" }, box);
  for (let t = yMin; t <= yMax + 1e-9; t += unit) {
    el("line", { x1: left, x2: right, y1: sy(t), y2: sy(t), stroke: Math.abs(t) < 1e-9 ? "var(--axis)" : "var(--grid)" }, svg);
    el("text", { x: left - 8, y: sy(t) + 4, "text-anchor": "end", class: "num" }, svg).textContent = signed(t, 0) + "°";
  }
  for (let t = 0; t <= xMax; t += xMax / 5) {
    el("text", { x: sx(t), y: bot + 18, "text-anchor": "middle", class: "num" }, svg).textContent = fmt(t, 0);
  }
  el("rect", { x: left, y: top, width: right - left, height: bot - top, fill: "none", stroke: "var(--axis)" }, svg);
  el("text", { x: (left + right) / 2, y: bot + 38, "text-anchor": "middle", class: "lbl" }, svg).textContent = "names added to the specs (production and test)";
  el("text", { x: right + 10, y: top + 16, class: "lbl" }, svg).textContent = "Δ gap less chance";
  const placed = [];
  SPEC_STEPS.forEach(p => {
    const cx = sx(p.x), cy = sy(p.d), removal = p.x === 0 && p.out > 0;
    if (removal) el("path", { d: `M${cx},${cy - 5}L${cx + 5},${cy}L${cx},${cy + 5}L${cx - 5},${cy}Z`, fill: "var(--surface)", stroke: "var(--spec)", "stroke-width": 1.5, class: "removal" }, svg);
    else el("circle", { cx, cy, r: 4, fill: "var(--spec)", stroke: "var(--surface)", "stroke-width": 1 }, svg);
    if (p.i === sel) el("circle", { cx, cy, r: 8, fill: "none", stroke: "var(--ink)", "stroke-width": 1.5 }, svg);
    // Labels that would land on one already drawn are left to the tooltip: several PRs sit at zero.
    if (!placed.some(([x, y]) => Math.abs(x - cx) < 40 && Math.abs(y - cy) < 14)) {
      placed.push([cx, cy]);
      el("text", { x: cx + 8, y: cy - 6, class: "num" }, svg).textContent = prLabel(p.r);
    }
    const a = p.r.names_added, o = p.r.names_dropped;
    const hit = el("circle", { cx, cy, r: 8, class: "hit" }, svg);
    hit.addEventListener("mousemove", ev => showTip(ev, rowTip(p.r)
      + `<div class="row"><span>names added (prod / test)</span><span>${a.prod} / ${a.test}</span></div>`
      + `<div class="row"><span>names dropped (prod / test)</span><span>${o.prod} / ${o.test}</span></div>`
      + `<div class="row"><span>flags added / dropped</span><span>${a.flags} / ${o.flags}</span></div>`
      + `<div class="row"><span>change in gap less chance</span><span>${signed(p.d)}°</span></div>`));
    hit.addEventListener("mouseleave", hideTip);
    hit.addEventListener("click", () => setSel(p.i));
  });
}

/* ---------- how the pulls on the gap add up ---------- */
// The steps above, summed: steps away from the code against steps toward it. The sum is a change
// since the plan, not the gap. Day 0 is "Setup", the merges before Day 01's first pull request.
const PULLS = R.slice(1).map((r, j) => ({ r, i: j + 1, d: step(R[j].gap_full, r.gap_full) }));
PULLS.reduce((run, p) => (p.cum = +(run + p.d).toFixed(2)), 0);
const PULL_DAYS = [...new Set(PULLS.map(p => p.r.day || 0))];
const pullDay = d => d === "all" ? "All merges" : d ? "D" + dd(d) : "Setup";
const pullsOf = d => d === "all" ? PULLS : PULLS.filter(p => (p.r.day || 0) === d);
function pullSum(ps) {
  const add = a => +a.reduce((x, p) => x + p.d, 0).toFixed(2), up = ps.filter(p => p.d > 0), dn = ps.filter(p => p.d < 0);
  return { up: add(up), dn: add(dn), net: add(ps), nu: up.length, nd: dn.length, nz: ps.length - up.length - dn.length };
}
const pullTip = p => rowTip(p.r) + `<div class="row"><span>step on the gap</span><span>${signed(p.d)}°</span></div>` +
  `<div class="row"><span>sum since the plan</span><span>${signed(p.cum)}°</span></div>`;
function noPulls(box) {
  if (PULLS.length) return false;
  box.innerHTML = '<p class="load-error">No merge yet: the pulls start at the first merge after the plan.</p>';
  return true;
}
// Day buttons above a view: it opens on `start` and redraws on a click.
function pullPicker(id, draw, start) {
  const box = document.getElementById(id + "-pick");
  box.innerHTML = PULLS.length ? ["all", ...PULL_DAYS].map(d =>
    `<button type="button" data-d="${d}" aria-pressed="${d === start}">${pullDay(d)}</button>`).join("") : "";
  box.querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
    box.querySelectorAll("button").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
    panel(id, () => draw(b.dataset.d === "all" ? "all" : +b.dataset.d));
  }));
  panel(id, () => draw(start));
}
function gridY(svg, ly, yMin, yMax, unit, x1, x2) {
  for (let v = yMin; v <= yMax + 1e-9; v += unit) {
    el("line", { x1, x2, y1: ly(v), y2: ly(v), stroke: Math.abs(v) < 1e-9 ? "var(--axis)" : "var(--grid)" }, svg);
    el("text", { x: x1 - 8, y: ly(v) + 4, "text-anchor": "end", class: "num" }, svg).textContent = signed(v, unit < 1 ? 1 : 0) + "°";
  }
}

function drawPullSum() {
  const box = document.getElementById("pull-sum");
  box.innerHTML = "";
  if (noPulls(box)) return;
  const H = 250, top = LP.t, bot = H - 40, pts = [{ i: 0, cum: 0 }, ...PULLS];
  const lo = Math.min(0, ...pts.map(p => p.cum)), hi = Math.max(0, ...pts.map(p => p.cum));
  const unit = hi - lo > 20 ? 5 : hi - lo > 8 ? 2 : 1;
  const yMin = Math.floor(lo / unit) * unit, yMax = Math.max(Math.ceil(hi / unit) * unit, yMin + unit);
  const ly = v => top + (yMax - v) / (yMax - yMin) * (bot - top);
  const svg = el("svg", { viewBox: `0 0 ${LW} ${H}`, role: "img", "aria-label": "Sum of the gap's steps since the plan, in merge order" }, box);
  gridY(svg, ly, yMin, yMax, unit, LP.l, LW - LP.r);
  let lastX = -99;
  dayStarts().forEach(([i, d]) => {
    if (!d || lx(i) - lastX < 34) return;
    lastX = lx(i);
    el("line", { x1: lx(i), x2: lx(i), y1: top, y2: bot, stroke: "var(--grid)", "stroke-dasharray": "2 3" }, svg);
    el("text", { x: lx(i) + 3, y: bot + 16, class: "num" }, svg).textContent = "D" + dd(d);
  });
  const line = pts.map((p, k) => (k ? "L" : "M") + lx(p.i).toFixed(1) + " " + ly(p.cum).toFixed(1)).join("");
  const area = line + `L${lx(N - 1)} ${ly(0)}L${lx(0)} ${ly(0)}Z`, defs = el("defs", {}, svg);
  el("rect", { x: 0, y: 0, width: LW, height: ly(0) }, el("clipPath", { id: "pull-up" }, defs));
  el("rect", { x: 0, y: ly(0), width: LW, height: H }, el("clipPath", { id: "pull-dn" }, defs));
  el("path", { d: area, fill: "var(--away)", "fill-opacity": 0.22, "clip-path": "url(#pull-up)" }, svg);
  el("path", { d: area, fill: "var(--closer)", "fill-opacity": 0.18, "clip-path": "url(#pull-dn)" }, svg);
  el("path", { d: line, fill: "none", stroke: "var(--ink)", "stroke-width": 2, "stroke-linejoin": "round" }, svg);
  el("line", { x1: lx(sel), x2: lx(sel), y1: top, y2: bot, stroke: "var(--ink-2)" }, svg);
  el("circle", { cx: lx(sel), cy: ly(sel ? PULLS[sel - 1].cum : 0), r: 4.5, fill: "var(--ink)", stroke: "var(--surface)", "stroke-width": 2 }, svg);
  const end = PULLS[PULLS.length - 1], now = [...R].reverse().find(r => r.gap_full != null);
  el("text", { x: LW - LP.r + 10, y: ly(end.cum) + 4, class: "lbl-strong num" }, svg).textContent = signed(end.cum, 1) + "°";
  el("text", { x: LW - LP.r + 10, y: ly(end.cum) + 20, class: "num" }, svg).textContent = `gap ${fmt(now && now.gap_full)}°`;
  if (Math.abs(ly(end.cum) - ly(0)) > 34)
    el("text", { x: LW - LP.r + 10, y: ly(0) + 4, class: "num" }, svg).textContent = `0 = gap ${fmt(R[0].gap_full)}°`;
  const w = (LW - LP.l - LP.r) / Math.max(1, N - 1);
  PULLS.forEach(p => {
    const hit = el("rect", { x: lx(p.i) - w / 2, y: top, width: w, height: bot - top, class: "hit" }, svg);
    hit.addEventListener("mousemove", ev => showTip(ev, pullTip(p)));
    hit.addEventListener("mouseleave", hideTip);
    hit.addEventListener("click", () => setSel(p.i));
  });
}

function drawPullSteps(d) {
  const box = document.getElementById("pull-steps");
  if (noPulls(box)) return;
  const ps = pullsOf(d), t = pullSum(ps), few = ps.length <= 16, H = 280, P = { l: LP.l, r: 20, t: 22, b: 44 };
  box.innerHTML = `<p class="pull-cap num">${pullDay(d)}: ${ps.length} merges · away ${signed(t.up)}° · closer ${signed(t.dn)}° · net ${signed(t.net)}°</p>`;
  let run = 0;
  const bars = ps.map(p => { const a = run; run = +(run + p.d).toFixed(2); return { p, a, b: run }; });
  const vals = [0, ...bars.map(b => b.b)], lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo || 1;
  const unit = span > 40 ? 10 : span > 16 ? 5 : span > 6 ? 2 : span > 2.5 ? 1 : 0.5;
  const yMin = Math.floor((lo - span * 0.08) / unit) * unit, yMax = Math.ceil((hi + span * 0.08) / unit) * unit;
  const ly = v => P.t + (yMax - v) / (yMax - yMin) * (H - P.t - P.b);
  const slot = (LW - P.l - P.r) / (ps.length + 1.4), bw = Math.min(30, Math.max(3, slot * 0.68)), x = k => P.l + slot * (k + 0.7);
  const svg = el("svg", { viewBox: `0 0 ${LW} ${H}`, role: "img", "aria-label": `Each merge's step on the gap: ${pullDay(d)}` }, box);
  gridY(svg, ly, yMin, yMax, unit, P.l, LW - P.r);
  let lastX = -99;
  bars.forEach(({ p, a, b }, k) => {
    el("line", { x1: x(k) + bw / 2, x2: x(k + 1) - bw / 2, y1: ly(b), y2: ly(b), stroke: "var(--axis)" }, svg);
    const y0 = Math.min(ly(a), ly(b)), h = Math.max(2, Math.abs(ly(a) - ly(b)));
    el("rect", { x: x(k) - bw / 2, y: y0, width: bw, height: h, rx: Math.min(2, bw / 4),
      fill: p.d > 0 ? "var(--away)" : p.d < 0 ? "var(--closer)" : "var(--muted)" }, svg);
    if (few) {
      if (p.d) el("text", { x: x(k), y: p.d > 0 ? y0 - 5 : y0 + h + 13, "text-anchor": "middle", class: "num" }, svg).textContent = signed(p.d);
      el("text", { x: x(k), y: H - P.b + 16, "text-anchor": "middle", class: "num" }, svg).textContent = prLabel(p.r);
    } else if ((!k || (p.r.day || 0) !== (ps[k - 1].r.day || 0)) && x(k) - lastX >= 34) {
      lastX = x(k);
      el("line", { x1: x(k) - slot / 2, x2: x(k) - slot / 2, y1: P.t, y2: H - P.b, stroke: "var(--grid)", "stroke-dasharray": "2 3" }, svg);
      el("text", { x: x(k) - slot / 2 + 3, y: H - P.b + 16, class: "num" }, svg).textContent = p.r.day ? "D" + dd(p.r.day) : "S";
    }
    const hit = el("rect", { x: x(k) - slot / 2, y: P.t, width: slot, height: H - P.t - P.b, class: "hit" }, svg);
    hit.addEventListener("mousemove", ev => showTip(ev, pullTip(p)));
    hit.addEventListener("mouseleave", hideTip);
    hit.addEventListener("click", () => setSel(p.i));
  });
  const nx = x(bars.length), y0 = Math.min(ly(0), ly(run)), h = Math.max(2, Math.abs(ly(0) - ly(run)));
  el("rect", { x: nx - bw / 2, y: y0, width: bw, height: h, rx: Math.min(2, bw / 4), fill: "var(--ink)" }, svg);
  el("text", { x: nx, y: run > 0 ? y0 - 5 : y0 + h + 13, "text-anchor": "middle", class: "lbl-strong num" }, svg).textContent = signed(run, few ? 2 : 1);
  el("text", { x: nx, y: H - P.b + 16, "text-anchor": "middle", class: "lbl" }, svg).textContent = "net";
}

function drawPullTotals() {
  const box = document.getElementById("pull-totals");
  if (noPulls(box)) return;
  const all = pullSum(PULLS), days = PULL_DAYS.map(d => [pullDay(d), pullSum(pullsOf(d))]);
  const dayMax = Math.max(1e-9, ...days.map(([, t]) => Math.max(t.up, -t.dn)));
  const row = (name, t, max, cls = "") => `<div class="name">${name}</div>` +
    `<div class="side l ${cls}"><span class="v num">${t.nd ? signed(t.dn, 1) + "°" : ""}</span><i style="width:${(-t.dn / max * 80).toFixed(1)}%" title="${t.nd} merges"></i></div>` +
    `<div class="side r ${cls}"><i style="width:${(t.up / max * 80).toFixed(1)}%" title="${t.nu} merges"></i><span class="v num">${t.nu ? signed(t.up, 1) + "°" : ""}</span></div>` +
    `<div class="net num">net ${signed(t.net, 1)}°</div>`;
  box.innerHTML = `<div></div><div class="hd l">← pulled closer</div><div class="hd r">pulled away →</div><div></div>` +
    row("All", all, Math.max(1e-9, all.up, -all.dn), "big") + `<div class="sep"></div>` +
    days.map(([n, t]) => row(n, t, dayMax)).join("") +
    `<p class="note">All has its own scale; the days share one, so they compare with each other.</p>`;
}

function drawPullScale(d) {
  const box = document.getElementById("pull-scale");
  box.innerHTML = "";
  if (noPulls(box)) return;
  const t = pullSum(pullsOf(d)), all = pullSum(PULLS), W = 640, H = 330, cx = W / 2, py = 112, half = 210;
  const up = t.up, dn = -t.dn, ang = (up - dn) / (up + dn || 1) * 30, rad = ang * Math.PI / 180;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `Balance of the pulls closer and away: ${pullDay(d)}` }, box);
  const L = { x: cx - half * Math.cos(rad), y: py - half * Math.sin(rad) }, Rt = { x: cx + half * Math.cos(rad), y: py + half * Math.sin(rad) };
  el("path", { d: `M${cx} ${py}L${cx - 34} ${H - 60}L${cx + 34} ${H - 60}Z`, fill: "var(--surface-2)", stroke: "var(--axis)" }, svg);
  el("line", { x1: L.x, y1: L.y, x2: Rt.x, y2: Rt.y, stroke: "var(--ink)", "stroke-width": 4, "stroke-linecap": "round" }, svg);
  el("circle", { cx, cy: py, r: 6, fill: "var(--surface)", stroke: "var(--ink)", "stroke-width": 2 }, svg);
  const heaviest = Math.max(1e-9, all.up, -all.dn);
  [[L, dn, -dn, t.nd, "var(--closer)", "pulled closer"], [Rt, up, up, t.nu, "var(--away)", "pulled away"]].forEach(([e, w, v, n, fill, name]) => {
    const y = e.y + 78, bh = w > 0 ? Math.max(3, Math.sqrt(w / heaviest) * 52) : 0;
    el("path", { d: `M${e.x} ${e.y}L${e.x - 46} ${y}M${e.x} ${e.y}L${e.x + 46} ${y}`, fill: "none", stroke: "var(--axis)" }, svg);
    el("path", { d: `M${e.x - 58} ${y}L${e.x + 58} ${y}Q${e.x} ${y + 26} ${e.x - 58} ${y}Z`, fill: "var(--surface-2)", stroke: "var(--axis)" }, svg);
    if (bh) el("rect", { x: e.x - 32, y: y - bh, width: 64, height: bh, rx: 3, fill }, svg);
    el("text", { x: e.x, y: y + 42, "text-anchor": "middle", class: "lbl" }, svg).textContent = name;
    el("text", { x: e.x, y: y + 60, "text-anchor": "middle", class: "num" }, svg).textContent = `${signed(v, 1)}° in ${n} merges`;
  });
  el("text", { x: cx, y: H - 28, "text-anchor": "middle", class: "lbl-strong num" }, svg).textContent = `net ${signed(t.net)}°`;
  el("text", { x: cx, y: H - 8, "text-anchor": "middle", class: "num" }, svg).textContent =
    `${pullDay(d)} · tilt ${fmt(Math.abs(ang), 1)}° toward ${up > dn ? "away" : up < dn ? "closer" : "neither"} · ${t.nz} merges did not move it`;
}

/* ---------- pull requests per day ---------- */
function drawPerDay() {
  const [S, C] = CUM.get(last);
  document.getElementById("churn-legend").innerHTML = `<span><i style="background:var(--spec)"></i>Spec lines changed · ${kilo(S)}</span>
    <span><i style="background:var(--code)"></i>Code lines changed · ${kilo(C)}</span>`;
  const merges = R.filter(r => r.pr);
  const totals = ["spec", "code", "close"].map(k => ({ name: KIND[k], value: merges.filter(r => r.kind === k).length, color: KVAR[k] }));
  // Shades of one grey could not be told apart: the bar draws every other PR as one segment, and
  // the legend and its tooltip give the split by branch area.
  const groups = DATA.other_groups, split = groups ? groups.map(g => `${esc(g.name)} · ${g.count}`).join(", ") : "";
  totals.push({ name: KIND.other, value: merges.filter(r => r.kind === "other").length, color: KVAR.other,
    tip: split && `<div class="row"><span>by area</span><span>${split}</span></div>` });
  shareBar(document.getElementById("pr-total"), totals, "Every merged pull request by kind");
  document.getElementById("pr-total-legend").innerHTML = totals.map(t =>
    `<span><i class="dot" style="background:${t.color}"></i>${esc(t.name)} · ${t.value}${t.tip ? ` (${split})` : ""}</span>`).join("") + `<span>${merges.length} in all</span>`;
  const box = document.getElementById("perday");
  box.innerHTML = "";
  const kinds = ["spec", "code", "close", "other"], H = 240, P = { l: 44, r: 16, t: 22, b: 30 };
  const days = DATA.days.filter(d => d.prs.length).sort((a, b) => rank(a.day) - rank(b.day));
  if (!days.length) { box.innerHTML = '<p class="load-error">No day has a merged pull request yet: a PR counts for a day when its branch is <code>day-NN/…</code>.</p>'; return; }
  const count = (d, k) => d.prs.filter(p => p.kind === k).length;
  const yMax = Math.max(4, Math.ceil(Math.max(...days.map(d => d.prs.length)) / 4) * 4);
  const ly = v => P.t + (1 - v / yMax) * (H - P.t - P.b);
  const bw = (LW - P.l - P.r) / days.length, w = Math.min(28, bw - 6);
  const svg = el("svg", { viewBox: `0 0 ${LW} ${H}`, role: "img", "aria-label": "Pull requests per day by kind, in run order" }, box);
  steps(0, yMax, 4).forEach(t => {
    el("line", { x1: P.l, x2: LW - P.r, y1: ly(t), y2: ly(t), stroke: t ? "var(--grid)" : "var(--axis)" }, svg);
    el("text", { x: P.l - 8, y: ly(t) + 4, "text-anchor": "end", class: "num" }, svg).textContent = t;
  });
  days.forEach((d, j) => {
    const x = P.l + j * bw + (bw - w) / 2;
    let base = 0;
    kinds.forEach(k => {
      const n = count(d, k);
      if (!n) return;
      // A 2px gap of surface between segments, taken from the top of each.
      el("rect", { x, y: ly(base + n), width: w, height: Math.max(1, ly(base) - ly(base + n) - 2), rx: 2, fill: KVAR[k] }, svg);
      base += n;
    });
    el("text", { x: x + w / 2, y: ly(base) - 6, "text-anchor": "middle", class: "num" }, svg).textContent = base;
    el("text", { x: x + w / 2, y: H - P.b + 16, "text-anchor": "middle", class: "num" + (OOO.has(d.day) ? " ooo" : "") }, svg)
      .textContent = "D" + dd(d.day) + (OOO.has(d.day) ? "*" : "");
    const hit = el("rect", { x: P.l + j * bw, y: P.t, width: bw, height: H - P.t - P.b, class: "hit" }, svg);
    hit.addEventListener("mousemove", ev => showTip(ev, `<b>Day ${dd(d.day)}</b><div style="margin:3px 0 6px">${esc(d.title)}</div>`
      + kinds.map(k => `<div class="row"><span>${KIND[k]}</span><span>${count(d, k)}</span></div>`).join("")
      + `<div class="row"><span>expected PRs, first written</span><span>${d.expected_first ?? "–"}</span></div>`
      + `<div class="row"><span>expected PRs, last written</span><span>${d.expected ?? "–"}</span></div>`));
    hit.addEventListener("mouseleave", hideTip);
    hit.addEventListener("click", () => {
      const nums = new Set(d.prs.map(p => p.number)), i = R.map(r => nums.has(r.pr)).lastIndexOf(true);
      if (i > 0) setSel(i);
    });
  });
  oooNote(box);
}

/* ---------- verification that leaves no lines ---------- */
function drawVerification() {
  const V = DATA.verification || [], code = V.filter(v => v.kind === "code");
  if (!V.length) return;
  const n = (vs, s) => vs.filter(v => v.breaks === s).length;
  // From this PR the rules ask for the break line, so only those PRs can be silent; 0 is every PR.
  const from = (DATA.meta || {}).break_line_from_pr || 0;
  const since = code.filter(v => v.breaks !== "not measured"), silent = since.filter(v => v.breaks === "silent");
  const recorded = n(since, "recorded"), none = n(since, "none");
  document.getElementById("breaks").innerHTML = `<p>${from ? `Since #${from}, ` : ""}${recorded} of ${since.length} code PRs record a break on purpose${none ? `, ${none} say why there is none` : ""}; ${silent.length} silent.</p>`
    + (from ? `<p style="font-size:13px;color:var(--muted)">${n(code, "not measured")} code PRs before #${from} are not measured.</p>` : "")
    + (silent.length ? `<ul>${silent.map(v => `<li>${v.url ? `<a href="${esc(v.url)}">#${v.number}</a>` : `#${v.number}`}${v.day ? ` · Day ${dd(v.day)}` : ""}</li>`).join("")}</ul>` : "");
  const sum = (vs, k) => vs.reduce((a, v) => a + v[k], 0);
  const pushes = sum(V, "pushes"), failed = sum(V, "failed"), bad = V.filter(v => v.failed);
  document.getElementById("ci-legend").textContent = `${bad.length} of ${V.length} merged PRs failed CI at least once (${failed} of ${pushes} pushes, ${fmt(failed / Math.max(1, pushes) * 100, 1)}%).`;
  document.getElementById("ci-fails").innerHTML = `<thead><tr><th>PR</th><th>Day</th><th class="r">Failed pushes</th><th>Workflows that failed</th></tr></thead><tbody>` +
    bad.map(v => `<tr><td class="num">#${v.number}</td><td class="num">${v.day ? dd(v.day) : "–"}</td><td class="r num">${v.failed} of ${v.pushes}</td><td>${esc(v.failed_in.join(", "))}</td></tr>`).join("") + "</tbody>";
}

/* ---------- time from opened to merged, per step ---------- */
const STEP = { spec: "Spec change", code: "Code track", close: "Close the day", tooling: "Tooling", other: "Other" };
// Hours as minutes, hours or days, whichever reads at a glance.
const span = h => h < 1 ? `${Math.round(h * 60)} min` : h < 48 ? `${fmt(h)} h` : `${fmt(h / 24)} d`;
const median = xs => { const s = [...xs].sort((a, b) => a - b), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
function drawMergeTime() {
  const timed = (DATA.verification || []).filter(v => typeof v.hours === "number"), box = document.getElementById("merge-time");
  if (!timed.length) { box.innerHTML = '<caption class="load-error">No merged pull request with its times yet.</caption>'; return; }
  box.innerHTML = `<thead><tr><th>Step</th><th class="r">Merged PRs</th><th class="r">Median</th><th class="r">Longest</th></tr></thead><tbody>` +
    Object.keys(STEP).map(k => [k, timed.filter(v => (v.step || v.kind) === k)]).filter(([, vs]) => vs.length).map(([k, vs]) => {
      const hs = vs.map(v => v.hours), worst = vs.reduce((a, v) => v.hours > a.hours ? v : a);
      return `<tr><td>${STEP[k]}</td><td class="r num">${vs.length}</td><td class="r num">${span(median(hs))}</td><td class="r num">${span(worst.hours)} (#${worst.number})</td></tr>`;
    }).join("") + "</tbody>";
}

/* ---------- heatmap ---------- */
function drawHeat() {
  const box = document.getElementById("heat");
  box.innerHTML = "";
  const files = DATA.files, cols = R.slice(1);
  const CW = 15, CH = 13, L = 96, T = 30;
  const W = L + cols.length * CW + 8, H = T + files.length * CH + 34;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-label": "Lines edited per spec file per merge", style: `min-width:${W}px;max-width:${W}px` }, box);
  const max = Math.max(...cols.flatMap(r => Object.values(r.spec_files || {})), 1);
  files.forEach((f, j) => {
    const d = dayOfFile(f), twin = files.filter(g => dayOfFile(g) === d).length > 1;
    el("text", { x: L - 8, y: T + j * CH + CH - 3, "text-anchor": "end", class: "num", style: "font-size:10.5px" }, svg)
      .textContent = f === "plan.md" ? "plan.md" : "day " + dd(d) + (twin ? " " + f.split("-")[2] : "");
  });
  cols.forEach((r, c) => {
    const x = L + c * CW;
    el("rect", { x: x + 1, y: 8, width: CW - 2, height: 8, rx: 2, fill: KVAR[r.kind] }, svg);
    files.forEach((f, j) => {
      const n = (r.spec_files || {})[f] || 0;
      const pct = n ? Math.round(22 + 78 * Math.sqrt(n / max)) : 0;
      el("rect", { x: x + 1, y: T + j * CH + 1, width: CW - 2, height: CH - 2, rx: 2,
        fill: n ? `color-mix(in oklab, var(--spec) ${pct}%, var(--surface))` : "var(--surface-2)" }, svg);
    });
    if (c % 5 === 0 || c === cols.length - 1)
      el("text", { x: x + CW / 2, y: H - 12, "text-anchor": "middle", class: "num", style: "font-size:10px" }, svg).textContent = "#" + r.pr;
  });
  // frontier: bottom edge of the day being worked on
  const rowOfDay = d => files.findIndex(f => dayOfFile(f) === d);
  let path = "";
  cols.forEach((r, c) => {
    const y = T + (rowOfDay(Math.max(r.day, 1)) + 1) * CH;
    path += (c === 0 ? `M${L + c * CW},${y}` : `V${y}`) + `H${L + (c + 1) * CW}`;
  });
  el("path", { d: path, fill: "none", stroke: "var(--code)", "stroke-width": 2, "stroke-linejoin": "round" }, svg);
  if (sel > 0) el("rect", { x: L + (sel - 1) * CW + 0.5, y: 4, width: CW - 1, height: T + files.length * CH - 2, rx: 3, fill: "none", stroke: "var(--ink)", "stroke-width": 1.5 }, svg);
  const hit = el("rect", { x: L, y: 0, width: cols.length * CW, height: T + files.length * CH, class: "hit" }, svg);
  const at = ev => {
    const p = svg.createSVGPoint(); p.x = ev.clientX; p.y = ev.clientY;
    const q = p.matrixTransform(svg.getScreenCTM().inverse());
    return [Math.floor((q.x - L) / CW), Math.floor((q.y - T) / CH)];
  };
  hit.addEventListener("mousemove", ev => {
    const [c, j] = at(ev);
    if (c < 0 || c >= cols.length) return hideTip();
    const r = cols[c];
    if (j < 0 || j >= files.length) return showTip(ev, rowTip(r));
    const f = files[j], n = (r.spec_files || {})[f] || 0, d = dayOfFile(f);
    const where = !d ? "the plan" : rank(d) > rank(r.day) ? `a future day (working on day ${r.day})` : d === r.day ? "the current day" : "a finished day";
    showTip(ev, `<b>${prLabel(r)} → ${esc(f.replace("specs/", ""))}</b><div style="margin:3px 0 6px">${esc(r.title)}</div>
      <div class="row"><span>lines edited</span><span>${n}</span></div><div class="row"><span>target</span><span>${where}</span></div>`);
  });
  hit.addEventListener("mouseleave", hideTip);
  hit.addEventListener("click", ev => { const [c] = at(ev); if (c >= 0 && c < cols.length) setSel(c + 1); });
  el("text", { x: L, y: H - 1, class: "lbl", style: "font-size:11px" }, svg).textContent = "▬ orange step: the day being worked on · darker blue = more lines edited";
}

/* ---------- findings + table ---------- */
// Each heading is a claim, so each is chosen by the numbers it rests on rather than fixed.
function drawFindings() {
  const covFloor = Math.min(...R.filter(r => r.coverage != null).map(r => r.coverage)) * 100;
  const codeShare = -byKind.code / gapClosed;
  const days = DATA.days.filter(finished).length;
  const f = [
    [last.deleted < DATA.origin_lines / 2 ? "Most of the plan as written still stands" : "Most of the plan as written has been rewritten",
     `${many(days, "day")} in, ${Math.round(last.deleted / DATA.origin_lines * 100)}% of the ${shortDate(R[0].date)} spec's lines have been rewritten, and ${last.added} lines added.`],
    [!gapClosed ? "No gap has closed yet" : specShare >= codeShare ? "The spec moved toward the code, not the reverse" : "The code now closes more of the gap than the spec",
     `Of the ${fmt(gapClosed)}° of gap that closed, ${ofGap(byKind.spec)} came from ${many(nKind("spec"), "spec-change PR")} and ${ofGap(byKind.code)} from ${many(nKind("code"), "code PR")}.`],
    // With no day reached there is no coverage to fall: Math.min() of nothing is Infinity.
    isFinite(covFloor) ? [covFloor >= 90 ? "Spec first keeps the gap from ever opening" : "The gap opened at least once",
     `Reached-day coverage never fell below ${fmt(covFloor, 1)}%: the share of names in the specs of days already reached that exist in the code.`]
      : ["No day reached yet", "Reached-day coverage, the share of names in the specs of days already reached that exist in the code, starts at the first merge that reaches a day."],
    [forward * 2 >= specEdits ? "Corrections reach forward" : "Corrections land on the day at hand",
     `${specEdits ? Math.round(forward / specEdits * 100) + "%" : "–"} of all edited day-spec lines (${forward} of ${specEdits}) went to days not reached yet.`],
  ];
  document.getElementById("findings").innerHTML = f.map(([h, p]) => `<div class="finding"><h3>${h}</h3><p>${p}</p></div>`).join("");
}
function drawTable() {
  document.getElementById("tbl").innerHTML = `<thead><tr><th>PR</th><th>Type</th><th>Day</th><th class="r">Name gap °</th><th class="r">Names in code</th><th class="r">Spec lines</th><th class="r">Code lines</th><th>Title</th></tr></thead><tbody>` +
    R.map((r, i) => `<tr data-i="${i}" class="${i === sel ? "sel" : ""}"><td class="num">${prLabel(r)}</td><td><span class="sw" style="background:${KVAR[r.kind]}"></span>${KIND[r.kind]}</td><td class="num">${r.day || "–"}</td><td class="r">${fmt(r.gap_full, 2)}</td><td class="r">${r.coverage == null ? "–" : fmt(r.coverage * 100, 1) + "%"}</td><td class="r">${Object.values(r.spec_files || {}).reduce((a, b) => a + b, 0)}</td><td class="r">${r.code_churn}</td><td class="t">${esc(r.title)}</td></tr>`).join("") + "</tbody>";
}
function drawScrubNow() {
  const s = R[sel];
  document.getElementById("scrub-now").innerHTML = `<span class="chip" style="color:${KVAR[s.kind]}">${KIND[s.kind]}</span>
    <span class="t">${prLabel(s)} · ${esc(s.title)}</span>
    <span class="num" style="color:var(--ink-2)">gap ${fmt(s.gap_full)}°</span>`;
}
// Each panel draws on its own: one that throws says so in its first box and the console, and the
// panels after it still draw.
function panel(id, draw) {
  try { draw(); } catch (e) {
    console.error(e);
    const box = document.getElementById(id), tag = box.tagName === "TABLE" ? "caption" : "p";
    box.innerHTML = `<${tag} class="load-error">This panel failed: ${esc(e && e.message || e)}</${tag}>`;
  }
}
function setSel(i) {
  sel = i; scrub.value = i;
  panel("scrub-now", drawScrubNow); panel("readout", drawReadout); panel("lines", drawLines); panel("deltas", drawDeltas); panel("spec-steps", drawSpecSteps); panel("heat", drawHeat);
  panel("pull-sum", drawPullSum);
  document.querySelectorAll("#tbl tr[data-i]").forEach(tr => tr.classList.toggle("sel", +tr.dataset.i === sel));
}

/* ---------- where we are ---------- */
// From spec-drift.py: the repository's name, plan.md's phase headings, and the days its list marks **Stop and evaluate.**
const PROJECT = (DATA.meta || {}).project || "";
document.title = `${PROJECT} Spec Drift`;
const PHASES = ((DATA.meta || {}).phases || []).map(esc);  // plan.md's text, which the template fills from <name>
const STOPS = (DATA.meta || {}).stops || [];
const STATUS = { done: "Done", closed: "Closed, boxes open", active: "In progress", ready: "Ready", provisional: "Provisional", cut: "Cut" };
const finished = d => d.status === "done" || d.status === "closed" || d.status === "cut";
function drawNow() {
  const now = DATA.now, days = DATA.days;
  const cur = days.find(d => d.day === now.current_day);
  const done = days.filter(finished).length;
  const open = now.open_prs.map(p => `<a href="${esc(p.url)}" target="_blank" rel="noopener">#${p.number}</a> ${esc(p.title)}`).join("<br>");
  const nextBox = `<div class="next"><span class="eyebrow">Next step</span><b>${md(now.next_step)}</b>${open ? `<div>${open}</div>` : ""}</div>
    <div class="refreshed">refreshed ${esc(now.generated.replace("T", " "))} · main at ${esc(now.head)}${now.last_pr ? ` (#${now.last_pr})` : ""}</div>`;
  // The days plan.md runs, and those with a spec it does not (cut): a new project writes specs one day at a time.
  const planned = new Set([...ORDER, ...days.map(d => d.day)]).size;
  // Merged PRs are the merges to main that name a PR; a direct commit is not one.
  document.getElementById("eyebrow").textContent = cur
    ? `${PROJECT} · Day ${dd(now.current_day)} of ${planned} · ${many(merged.length, "merged PR")}`
    : `${PROJECT} · between days · ${many(merged.length, "merged PR")}`;
  // Between days: the next piece of work has no day spec yet (the platform step, the cleanup day), or work has stopped.
  if (!cur) document.getElementById("today").innerHTML = `
    <div class="eyebrow">Between days</div>
    <div class="phase">${done} of ${days.length} days finished</div>${nextBox}`;
  else {
  const c = cur.criteria;
  const prs = cur.prs.length
    ? cur.prs.map(p => `<span class="chip" style="color:${KVAR[p.kind]}" title="${esc(p.title)}">#${p.number}</span>`).join(" ")
    : "none yet";
  document.getElementById("today").innerHTML = `
    <div class="eyebrow">Day ${dd(cur.day)} · ${STATUS[cur.status]}</div>
    <div class="day-title">${md(cur.title)}</div>
    <div class="phase">Phase ${cur.phase}: ${PHASES[cur.phase] || ""} · ${done} of ${days.length} days finished</div>
    <dl class="kv">
      <dt>Tracks</dt><dd><div class="trks">${cur.tracks.map(t => `<span class="trk ${cur.tracks_merged.includes(t) ? "done" : ""}" title="${esc(cur.track_work[t] || "")}">${t}</span>`).join("")}</div></dd>
      <dt>Criteria</dt><dd><span class="num">${c.ticked}/${c.total}</span> ticked · <span class="num">${c.new}</span> new · <span class="num">${c.hold}</span> hold</dd>
      <dt>Estimate</dt><dd><span class="num">${cur.expected_first ?? "–"} → ${cur.expected ?? "–"}</span> PRs, as first written → now</dd>
      <dt>Merged</dt><dd>${prs}</dd>
    </dl>
    ${nextBox}`;
  }
  // The next day plan.md names before its spec is written (the cleanup day), after the day it follows.
  const u = now.unwritten;
  const rows = PHASES.map((name, p) => {
    const ds = days.filter(d => d.phase === p);
    if (!ds.length) return "";
    const later = u && u.phase === p ? `<div class="tile unwritten" tabindex="0" aria-label="Day ${u.day}, spec not written">${dd(u.day)}</div>` : "";
    return `<div class="phase-row"><div class="phase-name"><b>${p}. ${name}</b>Days ${ds[0].day}–${later ? u.day : ds[ds.length - 1].day}</div><div class="tiles">${ds.map(d => {
      const share = d.tracks.length ? Math.min(1, d.tracks_merged.length / d.tracks.length) : 0;
      const bar = d.status === "active" ? `<span class="bar"><i style="width:${Math.round(share * 100)}%"></i></span>` : "";
      return `<div class="tile ${d.status}${STOPS.includes(d.day) ? " stop" : ""}${OOO.has(d.day) ? " ooo" : ""}" data-day="${d.day}" tabindex="0" aria-label="Day ${d.day}, ${STATUS[d.status]}">${dd(d.day)}${bar}</div>`;
    }).join("")}${later}</div></div>`;
  }).join("");
  document.getElementById("roadmap").innerHTML = rows + `<div class="tile-legend">
    <span><i class="tile done"></i>Done</span><span><i class="tile closed"></i>Closed, boxes open</span><span><i class="tile active"></i>In progress (bar: tracks merged)</span>
    <span><i class="tile"></i>Ready</span><span><i class="tile provisional"></i>Provisional</span><span><i class="tile cut"></i>Cut</span>${u ? `<span><i class="tile unwritten"></i>Spec not written</span>` : ""}
    <span><i class="tile stop"></i>Stop and evaluate</span><span><i class="tile ooo"></i>Run out of numeric order</span></div>`;
  document.querySelectorAll("#roadmap .tile.unwritten[tabindex]").forEach(tile => {
    const show = ev => showTip(ev, `<b>Day ${dd(u.day)} · Spec not written</b><div style="margin:3px 0 6px">${md(u.title)}</div>
      <div>${md(now.next_step)}</div>`);
    tile.addEventListener("mousemove", show);
    tile.addEventListener("focus", () => { const r = tile.getBoundingClientRect(); show({ clientX: r.right, clientY: r.bottom }); });
    tile.addEventListener("mouseleave", hideTip);
    tile.addEventListener("blur", hideTip);
  });
  document.querySelectorAll("#roadmap .tile[data-day]").forEach(tile => {
    const d = days.find(x => x.day === +tile.dataset.day);
    const show = ev => showTip(ev, `<b>Day ${dd(d.day)} · ${STATUS[d.status]}</b><div style="margin:3px 0 6px">${md(d.title)}</div>
      <div class="row"><span>estimate</span><span>${d.expected_first ?? "–"} → ${d.expected ?? "–"} PRs</span></div>
      <div class="row"><span>track PRs merged</span><span>${d.track_prs}</span></div>
      <div class="row"><span>criteria ticked</span><span>${d.criteria.ticked}/${d.criteria.total}</span></div>
      <div class="row"><span>tagged new / hold</span><span>${d.criteria.new} / ${d.criteria.hold}</span></div>
      <div class="row"><span>merged on</span><span>${d.worked ? shortDate(d.worked[0]) + (d.worked[1] !== d.worked[0] ? " – " + shortDate(d.worked[1]) : "") : "–"}</span></div>
      ${OOO.has(d.day) ? `<div class="row"><span>runs between</span><span>${ranBetween(d.day).join(" and ")}</span></div>` : ""}`);
    tile.addEventListener("mousemove", show);
    tile.addEventListener("focus", () => { const r = tile.getBoundingClientRect(); show({ clientX: r.right, clientY: r.bottom }); });
    tile.addEventListener("mouseleave", hideTip);
    tile.addEventListener("blur", hideTip);
  });
}

/* ---------- what it can do: the ladder ---------- */
// One dot per merged pull request, on the step its user story's Ability: line names; "rail" abilities are the railing. A count opens that ability's stories.
// The night's times and sentences are an illustration: only each marker's state comes from the data.
const NIGHT = [
  ["21:00", "rehearse", "You ask what it would do. It names the next step and starts nothing."],
  ["21:05", "loop", "You switch it on. It starts that step in a fresh session and watches the checks on what comes back."],
  ["21:50", "loop", "The checks pass. It waits for you to merge, from your phone, then starts the next step."],
  ["23:30", "park", "A step needs a decision only a person can make. It opens an issue and waits for your answer."],
  ["any time", "stop", "Something looks wrong. An issue titled STOP, opened from your phone, halts everything at once."],
  ["07:00", "recover", "The PC restarted in the night. The next start reads what was left behind and carries on, or asks you."],
];
const NIGHT_NOTE = { built: "", open: "Still being built.", none: "Not built yet." };
function drawLadder() {
  const box = document.getElementById("plot-ladder"), night = document.getElementById("plot-night");
  const us = DATA.user_stories || {}, stories = us.stories || [], abilities = us.abilities || [];
  const placed = stories.filter(s => abilities.some(a => a.key === s.ability));
  if (!placed.length) {
    box.innerHTML = notMeasured("Not counted yet: no merged pull request names an ability.");
    night.innerHTML = notMeasured("Not drawn until the steps are counted.");
    return;
  }
  const openDays = new Set(DATA.days.filter(d => !finished(d)).map(d => d.day));
  const count = list => many(list.length, "story", "stories");
  const dots = list => tileRow(list.map(s => `<i class="mini-tile story" title="${esc(`#${s.number} ${s.title}`)}"></i>`), count(list));
  const opener = (a, list) => `<button type="button" class="story-open" data-stories="${esc(a.key)}" aria-expanded="false" aria-controls="stories-${esc(a.key)}">${count(list)}</button>`;
  const lists = abilities.map(a => { const list = placed.filter(s => s.ability === a.key); return !list.length ? "" : `<div class="inline-detail story-list" id="stories-${esc(a.key)}" hidden><h3>${esc(a.name)} · ${count(list)}</h3><ol>`
    + list.map(s => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener">#${s.number}</a> ${esc(s.story || s.title)}<small>${s.day != null ? `Day ${s.day}` : "Between days"}${s.date ? ` · ${shortDate(s.date)}` : ""}</small></li>`).join("") + `</ol></div>`; }).join("");
  const rungs = abilities.filter(a => a.role === "rung").map(a => {
    const list = placed.filter(s => s.ability === a.key);
    const days = [...new Set(list.map(s => s.day).filter(d => d != null))].sort((x, y) => x - y);
    const open = days.filter(d => openDays.has(d));
    return { ...a, list, days, open, state: !list.length ? "none" : open.length ? "open" : "built" };
  });
  const here = rungs.reduce((top, r, i) => r.list.length ? i : top, -1);
  const reached = rungs.filter(r => r.list.length).length, building = rungs.filter(r => r.state === "open").length;
  const lost = stories.length - placed.length;
  const dayList = days => days.length ? `${days.length === 1 ? "Day" : "Days"} ${days.join(", ")}` : "between days";
  box.innerHTML = `<p class="plot-headline"><b>${reached} of ${rungs.length}</b> steps reached${building ? `, <b>${building}</b> still being built` : ""}</p>
    <div class="legend"><span><i class="mini-tile story"></i><b>One merged pull request</b></span><span><i class="rung-key open"></i><b>Still being built: its day is not closed</b></span>${reached < rungs.length ? `<span><i class="rung-key none"></i><b>Not started</b></span>` : ""}</div>
    <div class="ladder" style="--n:${rungs.length}"><div class="railing"><b>The railing</b><span>what shows and proves that the steps hold</span>`
    + abilities.filter(a => a.role === "rail").map(a => { const list = placed.filter(s => s.ability === a.key); return `<div class="rail-row">${dots(list)}<span>${list.length ? opener(a, list) : count(list)} · ${esc(a.name)}</span></div>`; }).join("") + `</div>`
    + rungs.map((r, i) => `<div class="rung ${r.state}" style="--i:${i + 1}"><div class="rung-label"><b>${esc(r.name)}</b>`
      + (r.list.length ? `${opener(r, r.list)}<span>${dayList(r.days)}</span>` : `<span>Not started</span>`) + `</div><div class="rung-step">${r.list.length ? dots(r.list) : ""}`
      + (r.open.length ? `<span>${dayList(r.open)} still open</span>` : "") + (i === here ? `<span class="rung-here">You are here</span>` : "") + `</div></div>`).join("") + `</div>`
    + lists
    + (lost ? `<p class="plot-quiet">${many(lost, "pull request")} named no ability and ${lost === 1 ? "is" : "are"} not drawn.</p>` : "");
  box.addEventListener("click", e => {
    const button = e.target.closest("button[data-stories]");
    if (!button) return;
    const opening = button.getAttribute("aria-expanded") !== "true";
    box.querySelectorAll("button[data-stories]").forEach(b => b.setAttribute("aria-expanded", String(opening && b === button)));
    box.querySelectorAll(".story-list").forEach(l => { l.hidden = !(opening && l.id === "stories-" + button.dataset.stories); if (!l.hidden) l.scrollIntoView({ block: "nearest" }); });
  });
  const stateOf = key => (rungs.find(r => r.key === key) || { state: "none" }).state;
  night.innerHTML = `<ol class="night">` + NIGHT.map(([time, key, text]) => {
    const state = stateOf(key);
    return `<li class="${state}"><span class="night-time">${time}</span><span>${text}${NIGHT_NOTE[state] ? `<small>${NIGHT_NOTE[state]}</small>` : ""}</span></li>`;
  }).join("") + `</ol>`;
}

/* ---------- when each ability grew ---------- */
// One row per ability, one column per day from the first to the last a story's branch names, then the stories merged between days.
function drawGrew() {
  const box = document.getElementById("plot-grew");
  const us = DATA.user_stories || {}, abilities = us.abilities || [];
  const placed = (us.stories || []).filter(s => abilities.some(a => a.key === s.ability));
  if (!placed.length) { box.innerHTML = notMeasured("Not counted yet: no merged pull request names an ability."); return; }
  const dayed = placed.filter(s => s.day != null), between = placed.length - dayed.length;
  const openDays = new Set(DATA.days.filter(d => !finished(d)).map(d => d.day));
  const first = Math.min(...dayed.map(s => s.day)), last = Math.max(...dayed.map(s => s.day));
  const cols = [];
  for (let d = first; d <= last; d++) cols.push({ day: d, name: `Day ${d}`, open: openDays.has(d) });
  if (between) cols.push({ day: null, name: "Between days", open: false });
  const at = (a, c) => placed.filter(s => s.ability === a.key && (s.day ?? null) === c.day).length;
  const most = Math.max(...abilities.flatMap(a => cols.map(c => at(a, c))));
  const open = c => c.open ? ' class="open"' : "";
  const cell = (a, c) => { const n = at(a, c); return `<td${open(c)}>` + (n ? `<i class="grew-dot" style="--d:${(8 + 18 * Math.sqrt(n / most)).toFixed(1)}px" title="${esc(`${c.name} · ${a.name}: ${many(n, "story", "stories")}`)}"></i><small>${n}</small>` : "") + `</td>`; };
  const busy = new Set(dayed.map(s => s.day));
  box.innerHTML = `<p class="plot-headline"><b>${dayed.length}</b> ${dayed.length === 1 ? "story" : "stories"} on <b>${busy.size}</b> ${busy.size === 1 ? "day" : "days"}${between ? `, <b>${between}</b> between days` : ""}</p>
    <div class="legend"><span><i class="grew-dot key"></i><b>Stories merged for that day: a larger dot is more</b></span>${[...busy].some(d => openDays.has(d)) ? `<span><i class="grew-dot key open"></i><b>Its day is not closed</b></span>` : ""}</div>
    <div class="scroll-x"><table class="grew" style="--n:${cols.length}"><thead><tr><td></td>${cols.map(c => `<th scope="col"${open(c)}>${c.name}</th>`).join("")}</tr></thead><tbody>`
    + abilities.map(a => `<tr${a.role === "rail" ? ' class="rail"' : ""}><th scope="row">${esc(a.name)}${a.role === "rail" ? "<small>the railing</small>" : ""}</th>${cols.map(c => cell(a, c)).join("")}</tr>`).join("") + `</tbody></table></div>`;
}

/* ---------- evidence ---------- */
// Counted from each finished day's ticked criteria; the test states are main's, from the script.
function drawEvidence() {
  const days = DATA.days.filter(d => finished(d) && d.evidence.some(c => c.ticked));
  // A day written before the evidence format was never asked to record these: its zero is "not measured".
  const cell = (n, of, pre) => pre ? `<td class="r pre">${n ? `${n}/${of}` : "not measured"}</td>`
    : `<td class="r${n ? "" : " none"}">${n}/${of}</td>`;
  document.getElementById("evidence").innerHTML = `<thead><tr><th>Day</th><th class="r">Cite a PR</th><th class="r">Name a test</th><th class="r">Failure recorded when built</th><th class="r">Tests on main</th><th>Title</th></tr></thead><tbody>` +
    days.map(d => {
      const ev = d.evidence.filter(c => c.ticked), states = ev.flatMap(c => Object.values(c.tests));
      // A retired test is a loss a later day chose, so only skippable and missing tests turn the cell orange.
      const off = states.filter(s => s === "skippable" || s === "missing").length;
      const kept = states.filter(s => s === "present").length, retired = states.filter(s => s === "retired").length;
      const pre = !d.evidence_format;
      return `<tr${pre ? ` title="Spec written before the evidence format"` : ""}><td class="num">${dd(d.day)}${pre ? ` <span class="pre-tag">pre-format</span>` : ""}</td>${cell(ev.filter(c => c.prs.length).length, ev.length, pre)}${cell(ev.filter(c => Object.keys(c.tests).length).length, ev.length, pre)}${cell(ev.filter(c => c.red).length, ev.length, !d.break_format)}<td class="r${off ? " none" : ""}">${states.length ? `${kept}/${states.length} present${retired ? `, ${retired} retired` : ""}` : "–"}</td><td class="t">${md(d.title)}</td></tr>`;
    }).join("") + "</tbody>";
  const gaps = days.flatMap(d => d.evidence.flatMap(c => Object.entries(c.tests).filter(([, s]) => s !== "present")
    .map(([t, s]) => `<li>Day ${dd(d.day)}: <code>${esc(t)}</code> ${s === "retired" ? "is retired: a later day's spec names it and its PR removed it" : `is ${s}`} · ${md(c.claim)}</li>`)));
  document.getElementById("evidence-gaps").innerHTML = `<h3>Named tests not running on main</h3>` +
    (gaps.length ? `<ul>${gaps.join("")}</ul>` : `<p>None: every test a finished day names is on <code>main</code>, and none can be skipped.</p>`);
  // A check first seen red in the closing PR waited a whole day to be shown it can fail.
  const late = days.flatMap(d => (d.broken_at_close || []).map(id => `<li>Day ${dd(d.day)}: ${md(id)}</li>`));
  document.getElementById("evidence-gaps").innerHTML += `<h3>Criteria first broken at the close</h3>` +
    (late.length ? `<ul>${late.join("")}</ul>` : `<p>None: every ticked criterion whose break cites a PR was broken before its day's closing PR.</p>`);
  // A check's state at one merge: found lines, read no files (so its nothing proves nothing), or clean.
  // Since is the merge where the state on main began; problems sort first.
  const REMOVAL = { found: [0, "var(--code)"], empty: [1, "var(--muted)"], clean: [2, "var(--close)"] };
  const removals = (DATA.removals || []).map(c => {
    const state = k => c.hits[k] ? "found" : c.files[k] ? "clean" : "empty", last = c.hits.length - 1, now = state(last);
    let k = last;
    while (k > 0 && state(k - 1) === now) k--;
    return { ...c, now, from: c.since + k, n: c.hits[last], reads: c.files[last] };
  }).sort((a, b) => REMOVAL[a.now][0] - REMOVAL[b.now][0] || a.day - b.day);
  const chip = c => `<span class="chip" style="color:${REMOVAL[c.now][1]}">${c.now === "found" ? `${c.n} line${c.n === 1 ? "" : "s"}` : c.now === "empty" ? "reads no files" : "clean"}</span>`;
  const found = c => c.found.length ? `<tr class="found"><td></td><td colspan="5"><ul>${c.found.map(f =>
    `<li><code>${esc(f.path)}:${f.line}</code> ${esc(f.text)}</li>`).join("")}${c.n > c.found.length ? `<li>and ${c.n - c.found.length} more</li>` : ""}</ul></td></tr>` : "";
  document.getElementById("removals").innerHTML = !removals.length
    ? `<tbody><tr><td>None: no finished day's criteria or Verify name a grep that must print nothing.</td></tr></tbody>` : `<thead><tr><th>Day</th><th>Check</th><th>From</th><th>On main</th><th class="r">Files read</th><th>Since</th></tr></thead><tbody>` +
    removals.map(c => `<tr><td class="num">${dd(c.day)}</td><td class="t"><code>${esc(c.cmd)}</code></td><td class="num">${esc(c.base)}</td><td>${chip(c)}</td><td class="r num">${c.reads}</td>` +
      `<td class="num" title="${esc(R[c.from].title || "")}">${prLabel(R[c.from])}${c.from === c.since ? " · day end" : ""}</td></tr>${found(c)}`).join("") + "</tbody>";
}

// The report scripts/evidence.py wrote, as spec-drift.py read it. No report is "not checked", and a
// day the report leaves out is too: neither is ever drawn as a pass.
const CHECK_KINDS = [["named_test", "Named tests"], ["verify", "Verify"], ["break", "Breaks replayed"], ["proof", "Evidence on record"]];
function drawEvidenceChecks() {
  const ec = DATA.evidence_checks || { state: "absent" }, box = document.getElementById("evidence-checks");
  if (ec.state === "absent") {
    box.innerHTML = `<p class="off">Not checked: no report. <code>python scripts/close-evidence.py --all docs/dashboard/evidence-checks.json</code> writes one; the dashboard workflow runs it before each build.</p>`;
    return;
  }
  if (ec.state !== "loaded") {
    box.innerHTML = `<p class="load-error">Report unavailable: ${esc(ec.diagnostic || ec.state)}</p>`;
    return;
  }
  // passed / (passed + failed + error): with none run, no share.
  const cell = (n, word) => {
    if (!n) return `<td class="r pre">none</td>`;
    const ran = n.passed + n.failed + n.error, na = n.not_applicable ? ` · ${n.not_applicable} n/a` : "";
    return ran ? `<td class="r${n.passed < ran ? " none" : ""}">${n.passed}/${ran} ${word}${n.error ? `, ${n.error} error` : ""}${na}</td>`
      : `<td class="r pre">–${na}</td>`;
  };
  const r = ec.runner || {};
  box.innerHTML = `<p class="limit">Report of ${esc(String(ec.generated).replace("T", " "))} · ${esc(ec.ref)} at ${esc(String(ec.ref_sha || "none").slice(0, 7))} · runner ${esc(String(r.revision || "unknown").slice(0, 7))}${r.dirty ? " (edited)" : ""}</p>` +
    `<div class="scroll-x"><table><thead><tr><th>Day</th><th>Report</th>${CHECK_KINDS.map(([, h]) => `<th class="r">${h}</th>`).join("")}</tr></thead><tbody>` +
    ec.days.map(d => d.state === "not checked"
      ? `<tr><td class="num">${dd(d.day)}</td><td class="pre" colspan="${CHECK_KINDS.length + 1}">not checked: the report leaves this day out</td></tr>`
      : `<tr${d.state === "stale" ? ` class="off" title="${esc(d.why.join("; "))}"` : ""}><td class="num">${dd(d.day)}</td><td>${d.state === "stale" ? `<span class="pre-tag">stale</span> ${esc(d.why.join("; "))}` : "current"}</td>${CHECK_KINDS.map(([k]) => cell(d.counts[k], k === "named_test" ? "found" : "passed")).join("")}</tr>`).join("") +
    `</tbody></table></div>`;
  const problems = ec.days.flatMap(d => (d.problems || []).map(p =>
    `<li>Day ${dd(d.day)}: ${esc(p.status)} · ${esc(p.label)}${p.diagnostic ? ` → ${esc(p.diagnostic)}` : ""}</li>`));
  if (problems.length) box.innerHTML += `<h3>Failed or could not run</h3><ul>${problems.join("")}</ul>`;
}

// spec-drift.py's proof_kinds, strongest first; not recorded is drawn apart, as an outline.
const PROOF = [["test", "Named test", "var(--p-test)"], ["command", "Command", "var(--p-command)"],
  ["break", "Break", "var(--p-break)"], ["reader", "Reader", "var(--p-reader)"], ["unproved", "Nothing on record", "var(--other)"]];
function drawProofKinds() {
  const ec = DATA.evidence_checks || { state: "absent" }, box = document.getElementById("proof-kinds");
  const legend = document.getElementById("proof-kinds-legend");
  box.innerHTML = legend.innerHTML = "";
  const days = ec.state === "loaded" ? ec.days.filter(d => d.proof).sort((a, b) => rank(a.day) - rank(b.day)) : [];
  // One message whatever the report's state: the panel above names it.
  if (!days.length) { box.innerHTML = `<p class="off">No replayed day to count: see the report above.</p>`; return; }
  const sum = k => days.reduce((s, d) => s + d.proof[k], 0);
  legend.innerHTML = PROOF.map(([k, name, c]) => `<span><i class="dot" style="background:${c}"></i>${name} · ${sum(k)}</span>`).join("")
    + `<span><i class="dot" style="border:1.5px dashed var(--muted)"></i>Not recorded · ${sum("not_recorded")}</span>`;
  const H = 220, P = { l: 44, r: 16, t: 22, b: 30 };
  const total = d => PROOF.reduce((s, [k]) => s + d.proof[k], 0) + d.proof.not_recorded;
  const yMax = Math.max(4, Math.ceil(Math.max(...days.map(total)) / 4) * 4);
  const ly = v => P.t + (1 - v / yMax) * (H - P.t - P.b);
  const bw = (LW - P.l - P.r) / days.length, w = Math.min(28, bw - 6);
  const svg = el("svg", { viewBox: `0 0 ${LW} ${H}`, role: "img", "aria-label": "Criteria per finished day by the evidence on record" }, box);
  steps(0, yMax, 4).forEach(t => {
    el("line", { x1: P.l, x2: LW - P.r, y1: ly(t), y2: ly(t), stroke: t ? "var(--grid)" : "var(--axis)" }, svg);
    el("text", { x: P.l - 8, y: ly(t) + 4, "text-anchor": "end", class: "num" }, svg).textContent = t;
  });
  days.forEach((d, j) => {
    const x = P.l + j * bw + (bw - w) / 2, stale = d.state === "stale";
    let base = 0;
    const seg = (n, attrs) => {
      if (!n) return;
      // A 2px gap of surface between segments, taken from the top of each.
      el("rect", { x, y: ly(base + n), width: w, height: Math.max(1, ly(base) - ly(base + n) - 2), rx: 2, ...attrs }, svg);
      base += n;
    };
    PROOF.forEach(([k, , c]) => seg(d.proof[k], { fill: c, opacity: stale ? 0.5 : 1 }));
    seg(d.proof.not_recorded, { fill: "none", stroke: "var(--muted)", "stroke-dasharray": "3 3" });
    el("text", { x: x + w / 2, y: ly(base) - 6, "text-anchor": "middle", class: "num" }, svg).textContent = base;
    el("text", { x: x + w / 2, y: H - P.b + 16, "text-anchor": "middle", class: "num" + (OOO.has(d.day) ? " ooo" : "") }, svg)
      .textContent = "D" + dd(d.day) + (OOO.has(d.day) ? "*" : "");
    const title = (DATA.days.find(x => x.day === d.day) || {}).title || "";
    const hit = el("rect", { x: P.l + j * bw, y: P.t, width: bw, height: H - P.t - P.b, class: "hit" }, svg);
    hit.addEventListener("mousemove", ev => showTip(ev, `<b>Day ${dd(d.day)}</b><div style="margin:3px 0 6px">${esc(title)}${stale ? " · stale report" : ""}</div>`
      + PROOF.map(([k, name]) => `<div class="row"><span>${name}</span><span>${d.proof[k]}</span></div>`).join("")
      + `<div class="row"><span>Not recorded</span><span>${d.proof.not_recorded}</span></div>`));
    hit.addEventListener("mouseleave", hideTip);
  });
  oooNote(box);
}

/* ---------- promises kept ---------- */
// What each replay state means to a reader: the group it counts in, and why it was not checked.
const REPLAY_LOOK = {
  "code broken": { group: "broken" },
  "test weakened": { group: "repair", why: "its test no longer catches the bug it used to" },
  "break no longer applies": { group: "repair", why: "the code moved, so the planted bug could not be put back" },
  "not runnable": { group: "skipped", why: "the check could not run" },
  "not applicable on this platform": { group: "skipped", why: "needs a different computer" },
  "live only": { group: "skipped", why: "needs a real live run" },
  "holds, never broken": { group: "unproven" },
  "holds": { group: "proven" },
  "not yet in force": { group: null },
};
// The five states a re-checked promise can be in, in the one order every bar, row of tiles and table draws them.
// Each has its own colour and its own mark (dashboard.css, --s-*), used for promise states and nothing else.
const PROMISE_GROUPS = {
  proven: { word: "Proven", count: ["proven", "proven"], means: "a bug was planted on purpose and its test caught it", glyph: "✓" },
  unproven: { word: "Passes, not yet proven", count: ["passes, not yet proven", "pass, not yet proven"], means: "the test passes, but no bug has been planted to see if it would notice" },
  skipped: { word: "Not checked here", count: ["not checked here", "not checked here"], means: "needs a real live run or a different computer" },
  repair: { word: "Test needs repair", count: ["test needs repair", "tests need repair"], means: "its test cannot be trusted to catch a failure", glyph: "!" },
  broken: { word: "Broken", count: ["broken", "broken"], means: "the promise no longer holds", glyph: "✕" },
};
const PROMISE_ORDER = Object.keys(PROMISE_GROUPS);
const promiseSays = (g, n) => `${n} ${PROMISE_GROUPS[g].count[n === 1 ? 0 : 1]}`;
// A reader's name for what each finished day built. A day not named here shows its spec's title up to the colon.
const PROMISE_FEATURES = {
  1: "Working out the next step",
  2: "Checking the setup before starting",
  3: "Stopping the driver safely",
  4: "Running one step",
  5: "Pausing for a person",
};
const promiseFeature = day => PROMISE_FEATURES[day]
  || ((DATA.days.find(d => d.day === day) || {}).title || `Day ${day}`).replace(/`/g, "").split(":")[0];
const promiseTile = group => `<i class="promise ${group}">${PROMISE_GROUPS[group].glyph || ""}</i>`;
const promiseText = c => (c.plain || c.claim || "").replace(/`/g, "");
const plural = (n, one, more) => `${n} ${n === 1 ? one : more}`;
// One reading of the re-check history for every panel that speaks about promises, so they cannot disagree:
// each promise's newest check, less those not in force and those a later promise replaced.
function promiseReading() {
  const rp = DATA.replay || { state: "absent" }, index = DATA.criteria_index || [];
  const replaced = new Set(index.filter(c => (c.replaced_by || []).length).map(c => c.id));
  const latest = new Map();
  (rp.cells || []).forEach(c => { if (!latest.has(c.criterion) || latest.get(c.criterion).n < c.n) latest.set(c.criterion, c); });
  const promises = [...latest.values()].filter(c => REPLAY_LOOK[c.state].group && !replaced.has(c.criterion))
    .map(c => ({ ...c, group: REPLAY_LOOK[c.state].group, day: Number(c.day) }));
  const merges = rp.merges || [], byN = new Map(merges.map(m => [m.n, m])), lastPr = (DATA.now || {}).last_pr;
  const age = pr => pr == null || lastPr == null ? "" : pr >= lastPr ? "at the latest change" : plural(lastPr - pr, "change ago", "changes ago");
  const inGroup = (list, g) => list.filter(p => p.group === g);
  return { rp, latest, promises, replaced, byN, age, inGroup, newest: merges.length ? age(merges[merges.length - 1].pr) : "" };
}
// Is trust growing? The same reading at every merge the re-check ran on: each promise in the state of its newest
// check at or before that merge, so one not re-checked there keeps its last state. The last entry is promiseReading()'s count.
function promiseHistory() {
  const { rp, replaced } = promiseReading(), state = new Map();
  const merges = [...(rp.merges || [])].sort((a, b) => a.n - b.n), cells = [...(rp.cells || [])].sort((a, b) => a.n - b.n);
  let k = 0;
  return merges.map(m => {
    for (; k < cells.length && cells[k].n <= m.n; k++) if (!replaced.has(cells[k].criterion)) state.set(cells[k].criterion, REPLAY_LOOK[cells[k].state].group);
    const counts = Object.fromEntries(PROMISE_ORDER.map(g => [g, 0]));
    state.forEach(g => { if (g) counts[g]++; });
    return { m, counts, total: PROMISE_ORDER.reduce((a, g) => a + counts[g], 0) };
  });
}
// The top of the promise board: the worst thing the last re-check found, what it covered, and the promises that need a person.
function drawReplay() {
  const reading = promiseReading(), { rp, promises, byN, inGroup, newest } = reading, box = document.getElementById("replay");
  const table = document.getElementById("replay-table");
  box.innerHTML = table.innerHTML = "";
  table.hidden = true;
  if (rp.state === "absent") { box.innerHTML = `<p class="off">No history: <code>python scripts/replay-history.py</code> writes <code>docs/dashboard/replay-history.json</code>.</p>`; return; }
  if (rp.state === "invalid") { box.innerHTML = `<p class="load-error">replay-history.json could not be read: ${esc(rp.why)}. Nothing is counted as holding.</p>`; return; }
  const claims = new Map((DATA.criteria_index || []).map(c => [c.id, c]));
  if (!promises.length) { box.innerHTML = `<p class="off">No merge sampled yet.</p>`; return; }

  const sentence = p => {
    const text = promiseText(claims.get(p.criterion) || { claim: "No description found" });
    return text.length > 170 ? text.slice(0, 170).replace(/\s+\S*$/, "") + "…" : text;
  };
  const item = p => {
    const note = [REPLAY_LOOK[p.state].why, p.mixed && "its checks disagree"].filter(Boolean).join("; ");
    return `<li title="${esc(p.criterion + ": " + ((claims.get(p.criterion) || {}).claim || ""))}">${promiseTile(p.group)}<span><b>${PROMISE_GROUPS[p.group].word}</b> in ${esc(promiseFeature(p.day))}${note ? ` (${esc(note)})` : ""}: ${esc(sentence(p))}</span></li>`;
  };

  // The verdict: the worst thing found, then what the re-check covered. The board under it draws every promise once.
  const broken = inGroup(promises, "broken"), repair = inGroup(promises, "repair");
  const verdict = broken.length ? plural(broken.length, "promise is broken", "promises are broken")
    : repair.length ? promiseSays("repair", repair.length)
    : "Nothing was broken at the last re-check";
  const covered = `We re-checked ${plural(promises.length, "promise", "promises")} by hand${newest ? `, most recently ${newest}` : ""}, so this can be behind the latest change. ${broken.length} failed.`
    + (repair.length && broken.length ? ` ${promiseSays("repair", repair.length)}.` : "");
  const problems = [...broken, ...repair];
  box.innerHTML = `<div class="promise-alert${problems.length ? " bad" : ""}"><p class="promise-verdict">${esc(verdict)}</p><p class="promise-covered">${esc(covered)}</p>`
    + (problems.length ? `<ul class="promise-list">${problems.map(item).join("")}</ul>` : "") + `</div>`;

  // The table view: every check that does not hold, newest merge first.
  const off = rp.cells.flatMap(c => c.checks.filter(k => k.state !== "holds").map(k => ({ c, k }))).sort((a, b) => b.c.n - a.c.n);
  table.hidden = false;
  table.innerHTML = `<summary>Technical detail: every check that did not pass cleanly · ${off.length}</summary>` + (off.length ? `<table class="replay-off"><thead><tr><th>Merge</th><th>Criterion</th><th>Check</th><th>State</th><th>Detail</th></tr></thead><tbody>`
    + off.map(({ c, k }) => { const m = byN.get(c.n); return `<tr><td>${m.pr ? "#" + m.pr : esc(m.merge)}</td><td>${esc(c.criterion)}</td><td>${esc(k.check)}</td><td>${esc(k.state)}</td><td>${esc(k.detail || "")}</td></tr>`; }).join("")
    + `</tbody></table>` : `<p class="off">None: every check replayed holds.</p>`);
}

/* ---------- hand-offs ---------- */
// The script sorts them by the receiving day's place in the run order, open ones first; those no
// later day picks up (`to` null) come last, then tracks a PR announced that no branch names.
function drawHandOffs() {
  const groups = [];
  for (const h of DATA.hand_offs || []) {
    if (!groups.length || groups[groups.length - 1].to !== h.to) groups.push({ to: h.to, items: [] });
    groups[groups.length - 1].items.push(h);
  }
  const unopened = DATA.days.flatMap(d => (d.tracks_unopened || []).map(t =>
    ({ source: `Day ${dd(d.day)}`, text: `Track ${t.track}: announced in #${t.pr}, no branch names it`, picked: false })));
  if (unopened.length) groups.push({ to: "tracks", items: unopened });
  const label = g => g.to === null ? "<b>No later day picks these up</b>"
    : g.to === "tracks" ? "<b>Tracks announced, never opened</b>"
    : `<b>Day ${dd(g.to)}</b> ${(d => d ? md(d.title) : "")(DATA.days.find(x => x.day === g.to))}`;
  const source = s => s.startsWith("Day ") ? esc(s) : `<code title="${esc(s)}">${esc(s.split("/").pop())}</code>`;
  document.getElementById("hand-offs").innerHTML = groups.length ? groups.map((g, k) => {
    const open = g.items.filter(h => !h.picked);
    return `<details${k === 0 || g.to === null || g.to === "tracks" ? " open" : ""}><summary>${label(g)} · <span class="${open.length ? "none" : ""}">${open.length} open</span> of ${g.items.length}</summary>
      <ul>${g.items.map(h => `<li class="${h.picked ? "picked" : ""}">${source(h.source)}${h.id ? ` <code>${esc(h.id)}</code>` : ""}: ${md(h.text)}${h.picked ? " <em>(picked up)</em>" : ""}</li>`).join("")}</ul></details>`;
  }).join("") : "<p>No finished day names a day not yet run.</p>";
}

/* ---------- conclusion ---------- */
// Everything here comes from the lab notebook at the head of main or from git, so it cannot go
// stale between refreshes. When the notebook falls behind the phases, the panel says so.
function drawConclusion() {
  const days = DATA.days, now = DATA.now, { reads, measured } = DATA.conclusion;
  const phases = [...new Set(days.map(d => d.phase))].filter(p => p != null);
  const closed = Math.max(-1, ...phases.filter(p => days.filter(d => d.phase === p).every(finished)));
  const read = reads[reads.length - 1];
  document.getElementById("conclusion-eyebrow").textContent = closed < 0
    ? "Conclusion · no phase closed yet"
    : `Conclusion · after Phase ${closed} · ${N - 1} merges`;
  const behind = !read ? `<p class="stale">The lab notebook has no phase read yet.</p>`
    : read.phase < closed ? `<p class="stale">The lab notebook's latest read is from the end of Phase ${read.phase}; Phase ${closed} has closed since and has none yet.</p>` : "";
  document.getElementById("read").innerHTML = behind + (read
    ? read.text.split(/\n\s*\n/).map(p => `<p>${md(p.replace(/\s*\n\s*/g, " "))}</p>`).join("")
    : "");

  const done = days.filter(finished).length;
  const cur = days.find(d => d.day === now.current_day);
  let next = `<p><b>${md(now.next_step)}</b></p>`;
  if (cur) {
    const ds = days.filter(d => d.phase === cur.phase);
    const left = ds.filter(d => !finished(d)).length;
    const prov = days.filter(d => d.status === "provisional");
    next = `<p><b>${md(now.next_step)}</b></p>
      <p>Phase ${cur.phase}, ${PHASES[cur.phase] || ""}, ends at Day ${dd(ds[ds.length - 1].day)}: ${left} day${left === 1 ? "" : "s"} left, counting this one.</p>
      ${prov.length ? `<p>${prov.length} day specs are still provisional, from Day ${dd(prov[0].day)} on.</p>` : ""}`;
  }
  document.getElementById("facts").innerHTML = `
    <div class="finding"><h3>By the count</h3>
      <p>${done} of ${days.length} days finished (${days.filter(d => d.status === "closed").length} with boxes open, ${days.filter(d => d.status === "cut").length} cut), ${closed + 1} of ${phases.length} phases closed. ${N - 1} merges to <code>main</code>:
      ${nKind("code")} code tracks, ${nKind("spec")} spec changes, ${nKind("close")} closing PRs and ${nKind("other")} others.</p></div>
    <div class="finding"><h3>What is next</h3>${next}</div>`;

  const head = DATA.conclusion.measured_head || ["Question", "Evidence so far"];
  document.getElementById("measured").innerHTML = measured.length
    ? `<thead><tr>${head.map(h => `<th>${md(h)}</th>`).join("")}</tr></thead><tbody>` +
      measured.map(r => `<tr>${r.map(c => `<td class="t">${md(c)}</td>`).join("")}</tr>`).join("") + "</tbody>"
    : `<tbody><tr><td class="t">The lab notebook has no measurement table.</td></tr></tbody>`;
}

/* ---------- tokens ---------- */
const MODEL_VAR = { "claude-opus-5-5": "var(--m-opus)", "claude-opus-5": "var(--m-opus-prev)", "claude-sonnet-5": "var(--m-sonnet)", "claude-haiku-4-5": "var(--m-haiku-prev)", "claude-haiku-5-5": "var(--m-haiku)" };
const modelName = m => m.replace(/^claude-/, "").replace(/^(\w)(\w*)-/, (_, a, b) => a.toUpperCase() + b + " ").replace(/-/g, ".");
const kilo = n => n >= 1e6 ? fmt(n / 1e6, 2) + "M" : n >= 1e3 ? fmt(n / 1e3, 0) + "k" : String(n);
const pct = (a, b) => fmt(b ? a / b * 100 : 0, 1) + "%";
function drawTokens() {
  const T = DATA.tokens || [];
  drawHooks(T);
  drawGates();
  const box = document.getElementById("token-bars");
  if (!T.length) {
    box.innerHTML = '<p class="load-error">No token counts yet: run <code>python scripts/token-usage.py</code>.</p>';
    document.getElementById("token-agents").innerHTML = '<p class="load-error">No agents to show: there are no token counts to split by agent.</p>';
    return;
  }
  const sum = (rows, k) => rows.reduce((a, r) => a + r[k], 0);
  // Every reply re-reads the whole conversation, so context per reply is what a long session costs.
  const ctx = rows => sum(rows, "input") + sum(rows, "cache_write") + sum(rows, "cache_read");
  const perReply = rows => kilo(Math.round(ctx(rows) / Math.max(1, sum(rows, "replies"))));
  const models = [...new Set(T.map(r => r.model))].sort((a, b) => sum(T.filter(r => r.model === b), "output") - sum(T.filter(r => r.model === a), "output"));
  const color = m => MODEL_VAR[m] || "var(--other)";
  document.getElementById("token-legend").innerHTML = models.map(m =>
    `<span><i class="dot" style="background:${color(m)}"></i>${esc(modelName(m))} · ${kilo(sum(T.filter(r => r.model === m), "output"))}</span>`).join("")
    // A row counted before costs were has none: the total is then a floor, and with none at all it is not shown.
    + (T.some(r => r.cost) ? `<span>$${fmt(T.reduce((a, r) => a + (r.cost || 0), 0), 2)} at list prices, the main sessions $${fmt(T.filter(r => r.agent === "main").reduce((a, r) => a + (r.cost || 0), 0), 2)}</span>` : "");
  const who = r => r.agent || "unknown";
  const impl = T.filter(r => who(r) === "implementer"), main = T.filter(r => who(r) === "main");
  // A row counted before agents were, or a subagent with no type beside it, belongs to no agent: not the checkers'.
  const unknown = T.filter(r => who(r) === "unknown");
  document.getElementById("token-implementer").innerHTML = impl.length
    ? `<b>The implementer</b> (which writes the track code from a brief) used <b>${pct(ctx(impl), ctx(T))}</b> of the context read (${kilo(ctx(impl))} of ${kilo(ctx(T))}) and <b>${pct(sum(impl, "output"), sum(T, "output"))}</b> of the output (${kilo(sum(impl, "output"))} of ${kilo(sum(T, "output"))}); the main sessions (specs, review, the breaks on purpose, the pull requests) <b>${pct(sum(main, "output"), sum(T, "output"))}</b> of the output; ${unknown.length ? `tokens with no agent recorded <b>${pct(sum(unknown, "output"), sum(T, "output"))}</b>; ` : ""}the checking agents the rest.`
    : "";
  drawAgents(T, sum, ctx, perReply, color);
  const dates = [...new Set(T.map(r => r.date))].sort();
  const H = 260, P = { l: 56, r: 12, t: 12, b: 46 }, bw = (LW - P.l - P.r) / dates.length;
  const perDate = dates.map(d => T.filter(r => r.date === d));
  const labelEvery = Math.ceil(dates.length / 6);
  const top = Math.max(...perDate.map(rs => sum(rs, "output")));
  const yMax = Math.ceil(top / 10 ** Math.floor(Math.log10(top)) * 2) / 2 * 10 ** Math.floor(Math.log10(top));
  const ly = v => P.t + (1 - v / yMax) * (H - P.t - P.b);
  box.innerHTML = "";
  const svg = el("svg", { viewBox: `0 0 ${LW} ${H}`, role: "img", "aria-label": "Output tokens per date by model" }, box);
  steps(0, yMax, 4).forEach(t => {
    el("line", { x1: P.l, x2: LW - P.r, y1: ly(t), y2: ly(t), stroke: "var(--grid)" }, svg);
    el("text", { x: P.l - 8, y: ly(t) + 4, "text-anchor": "end", class: "num" }, svg).textContent = kilo(t);
  });
  perDate.forEach((rs, i) => {
    const x = P.l + i * bw;
    let y = 0;
    models.forEach(m => {
      const v = sum(rs.filter(r => r.model === m), "output");
      if (!v) return;
      const rect = el("rect", { x: x + bw * 0.15, y: ly(y + v), width: bw * 0.7, height: ly(y) - ly(y + v), fill: color(m) }, svg);
      rect.addEventListener("mousemove", ev => showTip(ev, `<b>${dates[i]} · ${esc(modelName(m))}</b>
        <div class="row"><span>output</span><span>${kilo(v)}</span></div>
        <div class="row"><span>input + cache</span><span>${kilo(ctx(rs.filter(r => r.model === m)))}</span></div>
        <div class="row"><span>context per reply</span><span>${perReply(rs.filter(r => r.model === m))}</span></div>
        <div class="row"><span>replies</span><span>${sum(rs.filter(r => r.model === m), "replies")}</span></div>`));
      rect.addEventListener("mouseleave", hideTip);
      y += v;
    });
    el("text", { x: x + bw / 2, y: H - P.b + 18, "text-anchor": "middle", class: `num tk-date${(dates.length - 1 - i) % labelEvery ? " tk-skip" : ""}` }, svg).textContent = dates[i].slice(5);
    el("text", { x: x + bw / 2, y: H - P.b + 34, "text-anchor": "middle", class: "num tk-ctx" }, svg).textContent = perReply(rs) + " ctx";
  });
  const days = [...new Set(T.map(r => r.day))].sort((a, b) => rank(a) - rank(b));
  const cell = (rs, m) => { const v = sum(rs.filter(r => r.model === m), "output"); return `<td class="num">${v ? kilo(v) : "–"}</td>`; };
  document.getElementById("token-days").innerHTML =
    `<thead><tr><th>Day</th><th>Replies</th><th>Output</th><th>Input + cache</th><th>Context per reply</th>${models.map(m => `<th>${esc(modelName(m))}</th>`).join("")}</tr></thead><tbody>` +
    days.map(d => {
      const rs = T.filter(r => r.day === d);
      return `<tr><td>${d == null ? "Between days (main, tooling, docs)" : "Day " + dd(d)}</td><td class="num">${sum(rs, "replies")}</td>
        <td class="num">${kilo(sum(rs, "output"))}</td><td class="num">${kilo(ctx(rs))}</td><td class="num">${perReply(rs)}</td>${models.map(m => cell(rs, m)).join("")}</tr>`;
    }).join("") + "</tbody>";
}

// Per date, how the hooks fared: cut Bash results, whole Reads of a file over 8,000 bytes, and each
// guard's refusals (scripts/refusal_log.py). Token rows counted before the hooks were have no bash
// field, so they are left out; a date with refusals and no such row shows "–" for the counts it lacks.
function drawHooks(T) {
  const box = document.getElementById("token-hooks");
  const H = T.filter(r => "bash" in r), R = DATA.refusals || [];
  if (!H.length && !R.length) {
    box.innerHTML = '<caption><p class="load-error">No hook counts yet: run <code>python scripts/token-usage.py</code>.</p></caption>';
    return;
  }
  const guards = ["step-guard", "read-guard", "auditor-guard"];
  const sum = (rows, k) => rows.reduce((a, r) => a + r[k], 0);
  const share = (a, b) => `${a} (${b ? pct(a, b) : "–"})`;
  const dates = [...new Set(H.map(r => r.date).concat(R.map(r => r.date)))].sort();
  const refused = (d, g) => sum(R.filter(r => r.date === d && r.guard === g), "refused");
  const logged = R.length ? R.map(r => r.date).sort()[0] : null;  // before the log began, no count is not zero
  box.innerHTML = `<thead><tr><th>Date</th><th>Bash results</th><th>Cut</th><th>Large Reads</th><th>Whole</th>` +
    guards.map(g => `<th>Refused: ${g.replace("-guard", "")}</th>`).join("") + `</tr></thead><tbody>` +
    dates.map(d => {
      const rs = H.filter(r => r.date === d);
      const tok = rs.length ? `<td class="num">${sum(rs, "bash")}</td><td class="num">${share(sum(rs, "cut"), sum(rs, "bash"))}</td>` +
        `<td class="num">${sum(rs, "reads")}</td><td class="num">${share(sum(rs, "whole"), sum(rs, "reads"))}</td>` : `<td class="num">–</td>`.repeat(4);
      return `<tr><td>${esc(d)}</td>${tok}` +
        guards.map(g => `<td class="num">${logged && d >= logged ? refused(d, g) : "–"}</td>`).join("") + `</tr>`;
    }).join("") + "</tbody>";
}

// Per gate (scripts/spec-drift.py, gate_report()): the Defect lines it found, by cause, or the hooks'
// refusals, beside its runs, replies, context and cost; and the Defect lines no gate found.
function drawGates() {
  const G = DATA.gate_report, box = document.getElementById("gate-report");
  if (!G) {
    box.innerHTML = '<caption><p class="load-error">No gate report yet: rebuild with <code>python scripts/spec-drift.py --build</code>.</p></caption>';
    return;
  }
  const causes = ["spec", "implementation", "process", "environment", "other"];
  box.innerHTML = `<thead><tr><th>Gate</th><th>Found</th>${causes.map(c => `<th>${c[0].toUpperCase() + c.slice(1)}</th>`).join("")}` +
    `<th>Runs</th><th>Replies</th><th>Context</th><th>Output</th><th>Cost</th><th>Per catch</th></tr></thead><tbody>` +
    G.gates.map(g => {
      const hooks = g.found === null, caught = hooks ? g.refused : g.defects;
      return `<tr><td>${esc(g.gate)}</td><td class="num">${caught == null ? "–" : caught}${hooks && caught != null ? " refused" : ""}</td>` +
        causes.map(c => `<td class="num">${hooks ? "–" : g.causes[c]}</td>`).join("") +
        `<td class="num">${g.runs}</td><td class="num">${g.replies}</td><td class="num">${kilo(g.context)}</td>` +
        `<td class="num">${kilo(g.output)}</td><td class="num">$${fmt(g.cost, 2)}</td><td class="num">${caught ? "$" + fmt(g.cost / caught, 2) : "–"}</td></tr>`;
    }).join("") + "</tbody>";
  document.getElementById("gate-note").innerHTML = `${G.defects} Defect line${G.defects === 1 ? "" : "s"} in all; ${G.elsewhere} ` +
    `found elsewhere: in the spec-change PR, in review, by the session itself or a track, at the close, on the dashboard, in a later day, or with no <code>found:</code>.`;
}

// One bar per agent, longest first, coloured by the model it ran on (the legend above names them).
// HTML, not an SVG: an SVG scales its text with the screen, and at phone width the labels were unreadable.
function drawAgents(T, sum, ctx, perReply, color) {
  const box = document.getElementById("token-agents");
  const label = a => a === "main" ? "main sessions" : a === "unknown" ? "agent not recorded" : a;
  const agents = [...new Set(T.map(r => r.agent || "unknown"))]
    .map(a => ({ a, rs: T.filter(r => (r.agent || "unknown") === a) }))
    .map(o => ({ ...o, out: sum(o.rs, "output"), model: [...new Set(o.rs.map(r => r.model))] }))
    .sort((x, y) => y.out - x.out);
  if (!agents.length) { box.innerHTML = ""; return; }
  const top = agents[0].out, w = v => fmt(Math.max(0.1, v / top * 100), 2) + "%";
  box.innerHTML = `<div class="hbars" role="img" aria-label="Output tokens by agent">` + agents.map((o, i) =>
    `<div class="hbar-row" data-i="${i}"><span class="hbar-label">${esc(label(o.a))}</span><span class="hbar-track">` +
    o.model.map(m => `<i style="width:${w(sum(o.rs.filter(r => r.model === m), "output"))};background:${color(m)}"></i>`).join("") +
    `</span><span class="hbar-value num">${kilo(o.out)}</span></div>`).join("") + "</div>";
  box.querySelectorAll(".hbar-row").forEach(row => {
    const o = agents[+row.dataset.i];
    row.addEventListener("mousemove", ev => showTip(ev, `<b>${esc(label(o.a))}</b>
      <div class="row"><span>model</span><span>${o.model.map(m => esc(modelName(m))).join(", ")}</span></div>
      <div class="row"><span>output</span><span>${kilo(o.out)}</span></div>
      <div class="row"><span>input + cache</span><span>${kilo(ctx(o.rs))}</span></div>
      <div class="row"><span>context per reply</span><span>${perReply(o.rs)}</span></div>
      <div class="row"><span>replies</span><span>${sum(o.rs, "replies")}</span></div>`));
    row.addEventListener("mouseleave", hideTip);
  });
}

// Shared by the plots. HTML and CSS, so each reflows at phone width. A bar's length is its total
// out of `max`, so a small sample looks small; parts are { n, cls } or { n, color }, in the order they are drawn.
function stackedBar(parts, max, label) {
  const total = parts.reduce((a, p) => a + p.n, 0);
  return `<div class="stack" role="img" aria-label="${esc(label)}" title="${esc(label)}" style="width:${total / max * 100}%">`
    + parts.filter(p => p.n).map(p => `<i class="${p.cls || ""}" style="flex:${p.n} 1 0${p.color ? `;background:${p.color}` : ""}"></i>`).join("") + `</div>`;
}
const tileRow = (tiles, label) => `<span class="mini-tiles" role="img" aria-label="${esc(label)}" title="${esc(label)}">${tiles.join("")}</span>`;
const notMeasured = text => `<span class="not-measured">${esc(text)}</span>`;

const READER_AXES = [["stage", "When it was found"], ["cause", "Why it happened"], ["made", "Which day made it"]];
const READER_NONE = "Not counted yet: a day is counted once its closing PR pastes the comparison’s lines.";

// Plot 7: one tile per label the second reader gave, per day and per question. Differing is not a failure, so no alarm colour.
function drawReaderPlot(days) {
  const box = document.getElementById("relabel-plot");
  if (!days.some(d => d.relabel)) { box.innerHTML = notMeasured(READER_NONE); return; }
  const tile = cls => `<i class="mini-tile ${cls}"></i>`;
  const count = (a, n) => `${a} of ${n}`;
  box.innerHTML = `<div class="legend">${[["agree", "Same label as the day gave"], ["differ", "A different label"]].map(([c, w]) => `<span>${tile(c)}<b>${w}</b></span>`).join("")}</div>`
    + `<div class="reader-axes">` + READER_AXES.map(([f, head]) => {
      const [a, n] = days.reduce((t, d) => d.relabel && d.relabel[f] ? [t[0] + d.relabel[f][0], t[1] + d.relabel[f][1]] : t, [0, 0]);
      return `<div><h3>${head}</h3>` + (n ? `<div class="reader-total">${stackedBar([{ n: a, cls: "agree" }, { n: n - a, cls: "differ" }], n, `${head}: ${count(a, n)} agree, all counted days`)}<b class="num">${count(a, n)}</b></div>` : "")
        + days.map(d => {
          const p = d.relabel && d.relabel[f];
          return `<div class="reader-row"><span class="num">Day ${dd(d.day)}</span>` + (p
            ? `${tileRow([...Array(p[0]).fill(tile("agree")), ...Array(p[1] - p[0]).fill(tile("differ"))], `Day ${dd(d.day)}: ${count(p[0], p[1])} agree`)}<span class="num">${count(p[0], p[1])}</span>`
            : notMeasured("not counted")) + `</div>`;
        }).join("") + `</div>`;
    }).join("") + `</div>`;
}

// Per finished day, how many tags the blind defect-rater gave the same way; null where nothing gives counts.
function drawRelabel() {
  const days = DATA.days.filter(finished).sort((a, b) => rank(a.day) - rank(b.day));
  drawReaderPlot(days);
  if (!days.length) {
    document.getElementById("relabel").innerHTML = `<tbody><tr><td class="t">No finished day yet: a day is counted once its closing PR pastes <code>relabel.py compare</code>’s lines.</td></tr></tbody>`;
    return;
  }
  const F = ["stage", "cause", "made"];
  const cell = p => !p ? `<td class="r pre">–</td>`
    : `<td class="r"><span class="meter"><i style="width:${p[0] / p[1] * 100}%"></i></span>${p[0]} of ${p[1]}</td>`;
  const tot = F.map(f => days.reduce((a, d) => d.relabel && d.relabel[f] ? [a[0] + d.relabel[f][0], a[1] + d.relabel[f][1]] : a, [0, 0]));
  // Defect lines whose same-as: names an earlier defect (scripts/spec-drift.py, recurrence()); older data has
  // none, and draws as it did.
  const R = DATA.defect_recurrence, rep = ns => !R ? ""
    : `<td class="r">${R.recurrences.filter(r => ns.includes(+r.id.slice(1).split(".")[0])).length}</td>`;
  document.getElementById("relabel").innerHTML = `<thead><tr><th>Day</th>${F.map(f => `<th class="r">${f[0].toUpperCase() + f.slice(1)}</th>`).join("")}${R ? '<th class="r">Repeats</th>' : ""}<th>Title</th></tr></thead><tbody>` +
    days.map(d => `<tr><td class="num">${dd(d.day)}</td>${d.relabel ? F.map(f => cell(d.relabel[f])).join("")
      : `<td class="r pre" colspan="3">not counted: no closing PR gives a whole run</td>`}${rep([d.day])}<td class="t">${md(d.title)}</td></tr>`).join("") +
    `<tr><td><b>All counted</b></td>${tot.map(p => cell(p[1] ? p : null)).join("")}${rep(days.map(d => d.day))}<td></td></tr></tbody>`;
  if (R) document.getElementById("recurrence").innerHTML =
    `${R.recurrences.length} of ${R.with_id} Defect lines with an ID ${R.recurrences.length === 1 ? "repeats" : "repeat"} an earlier defect` +
    (R.recurrences.length ? ": " + R.recurrences.map(r => `<code>${esc(r.id)}</code> (same as <code>${esc(r.same_as)}</code>)`).join(", ") : "") + "." +
    (R.problems.length ? ` Not counted: ${R.problems.map(esc).join("; ")}.` : "");
}

/* ---------- the plots: HTML and CSS, so each reflows at phone width ---------- */
const plotRow = (name, bar, value) => `<div class="plot-row"><span class="plot-name">${name}</span><span class="plot-bar">${bar}</span><span class="plot-value num">${value}</span></div>`;
const plotKey = items => `<div class="legend">${items.map(([look, word]) => `<span>${look}<b>${word}</b></span>`).join("")}</div>`;
const keyTile = (cls, style) => `<i class="mini-tile ${cls}"${style ? ` style="${style}"` : ""}></i>`;
const addUp = (rows, k) => rows.reduce((a, r) => a + (r[k] || 0), 0);
const contextOf = rows => addUp(rows, "input") + addUp(rows, "cache_write") + addUp(rows, "cache_read");
const mergedPrs = () => Array.isArray(DATA.verification) ? DATA.verification : [];

// Plot 1: every re-checked promise in one bar, a segment per state. A segment over a fifth of the bar says what it
// is; the key under it counts all five states, a zero too, and says what each means. The table is the same by feature.
function drawPromisePlots() {
  const { rp, promises, inGroup, newest } = promiseReading();
  const all = document.getElementById("plot-all"), table = document.getElementById("trust-table"), trust = document.getElementById("trust-note");
  if (rp.state !== "loaded" || !promises.length) {
    all.innerHTML = notMeasured("No re-check on record yet.");
    table.innerHTML = `<caption>No re-check on record, so no confidence can be shown.</caption>`;
    trust.textContent = "";
    return;
  }
  const count = (list, g) => inGroup(list, g).length, says = PROMISE_ORDER.map(g => promiseSays(g, count(promises, g)));
  const segment = g => {
    const n = count(promises, g), [, words] = promiseSays(g, n).match(/^\d+( .*)$/);
    return n ? `<span class="promise ${g}" style="flex:${n} 0 0" title="${promiseSays(g, n)}">${n / promises.length > 0.2 ? `<b>${n}</b><em>${words}</em>` : ""}</span>` : "";
  };
  all.innerHTML = `<p class="plot-headline promise-headline"><b class="num">${count(promises, "proven")} of ${promises.length}</b> promises are proven: their test caught a planted bug</p>`
    + `<div class="promise-bar" role="img" aria-label="${says.join(", ")}">${PROMISE_ORDER.map(segment).join("")}</div>`
    + `<ul class="promise-states">${PROMISE_ORDER.map(g => `<li${count(promises, g) ? "" : ' class="zero"'}>${promiseTile(g)}<span><b>${count(promises, g)}</b>${promiseSays(g, count(promises, g)).replace(/^\d+/, "")}<small>${PROMISE_GROUPS[g].means}</small></span></li>`).join("")}</ul>`;

  const row = (name, list, tag = "td") => `<tr><${tag}>${name}</${tag}>`
    + PROMISE_ORDER.map(g => `<td class="r">${count(list, g)}${g === "proven" ? ` of ${list.length}` : ""}</td>`).join("") + `</tr>`;
  const days = [...new Set(promises.map(p => p.day))].sort((a, b) => a - b);
  table.innerHTML = `<thead><tr><th>Feature</th>${PROMISE_ORDER.map(g => `<th class="r">${PROMISE_GROUPS[g].word}</th>`).join("")}</tr></thead><tbody>`
    + days.map(d => row(esc(promiseFeature(d)), promises.filter(p => p.day === d))).join("") + row("<b>All</b>", promises) + `</tbody>`;
  trust.textContent = `The re-check is run by hand, so it can be behind the latest change${newest ? `: the last one was ${newest}` : ""}. Proven is counted per feature because planted bugs are recorded against promises, not against single tests; a score per test would be invented precision.`;
}

// Plot 2: is trust growing? A stepped area per state over the merges the re-check ran on (promiseHistory()).
function drawTrustHistory() {
  const box = document.getElementById("plot-history"), table = document.getElementById("history-table"), say = document.getElementById("history-say");
  const rp = DATA.replay || { state: "absent" }, hist = rp.state === "loaded" ? promiseHistory().filter(h => h.total) : [];
  box.innerHTML = table.innerHTML = say.innerHTML = "";
  if (!hist.length) { box.innerHTML = notMeasured("No re-check on record yet."); table.innerHTML = `<caption>No re-check on record.</caption>`; return; }
  const n = hist.length, first = hist[0], last = hist[n - 1], name = m => m.pr ? "#" + m.pr : m.merge;
  const seen = PROMISE_ORDER.filter(g => hist.some(h => h.counts[g]));
  say.textContent = `The same states, counted at each of the ${plural(n, "re-checked change", "re-checked changes")}${n > 1 ? `, ${name(first.m)} to ${name(last.m)}` : ""}. `
    + `Proven went from ${first.counts.proven} of ${plural(first.total, "promise", "promises")} to ${last.counts.proven} of ${last.total}.`;
  table.innerHTML = `<thead><tr><th>Change</th>${PROMISE_ORDER.map(g => `<th class="r">${PROMISE_GROUPS[g].word}</th>`).join("")}<th class="r">Promises</th></tr></thead><tbody>`
    + hist.map(h => `<tr><td>${esc(name(h.m))}</td>${PROMISE_ORDER.map(g => `<td class="r">${h.counts[g]}</td>`).join("")}<td class="r">${h.total}</td></tr>`).join("") + `</tbody>`;

  const H = 260, P = { l: 34, r: 210, t: 12, b: 32 }, most = Math.max(...hist.map(h => h.total));
  const tick = most <= 12 ? 4 : most <= 40 ? 10 : 20, yMax = Math.ceil(most / tick) * tick;
  const x = i => +(P.l + i / n * (LW - P.l - P.r)).toFixed(1), y = v => +(P.t + (1 - v / yMax) * (H - P.t - P.b)).toFixed(1);
  const svg = el("svg", { viewBox: `0 0 ${LW} ${H}`, role: "img", "aria-label": `Promise states at each of ${plural(n, "re-checked change", "re-checked changes")}; at the latest: ${seen.map(g => promiseSays(g, last.counts[g])).join(", ")}` }, box);
  const hatch = el("pattern", { id: "promise-hatch", width: 5, height: 5, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, el("defs", {}, svg));
  el("rect", { width: 5, height: 5, class: "hatch-ground" }, hatch); el("rect", { width: 1.6, height: 5, class: "hatch-line" }, hatch);
  for (let t = 0; t <= yMax; t += tick) {
    el("line", { x1: P.l, x2: LW - P.r, y1: y(t), y2: y(t), stroke: t ? "var(--grid)" : "var(--axis)" }, svg);
    el("text", { x: P.l - 8, y: y(t) + 4, "text-anchor": "end", class: "num" }, svg).textContent = t;
  }
  let base = Array(n).fill(0), labelY = Infinity;
  seen.forEach(g => {
    const top = base.map((b, i) => b + hist[i].counts[g]);
    // Steps, not slopes: a count holds from its re-check to the next one.
    let d = `M${x(0)} ${y(top[0])}`;
    for (let i = 0; i < n; i++) d += `H${x(i + 1)}` + (i + 1 < n ? `V${y(top[i + 1])}` : "");
    for (let i = n - 1; i >= 0; i--) d += `V${y(base[i])}H${x(i)}`;
    el("path", { d: d + "Z", class: `area s-${g}` }, svg);
    const v = last.counts[g], at = Math.min(y(base[n - 1] + v / 2) + 4, labelY - 17);
    labelY = at;
    el("rect", { x: LW - P.r + 12, y: at - 10, width: 11, height: 11, rx: 2, class: `s-${g}` }, svg);
    el("text", { x: LW - P.r + 30, y: at, class: "strong" }, svg).textContent = promiseSays(g, v);
    base = top;
  });
  const every = Math.ceil(n / 8);
  hist.forEach((h, i) => {
    if (i % every === 0) el("text", { x: x(i + 0.5), y: H - P.b + 18, "text-anchor": "middle", class: "num" }, svg).textContent = name(h.m);
    const hit = el("rect", { x: x(i), y: P.t, width: +(x(i + 1) - x(i)).toFixed(1), height: H - P.t - P.b, class: "hit" }, svg);
    hit.addEventListener("mousemove", ev => showTip(ev, `<b>${esc(name(h.m))}</b>`
      + PROMISE_ORDER.filter(g => seen.includes(g)).map(g => `<div class="row"><span>${PROMISE_GROUPS[g].word}</span><span>${h.counts[g]}</span></div>`).join("")
      + `<div class="row"><span>Promises</span><span>${h.total}</span></div>`));
    hit.addEventListener("mouseleave", hideTip);
  });
}

// Plot 3: one bar per group. Each group has one "when", so nothing is stacked.
function drawTestBars() {
  const I = DATA.test_inventory, box = document.getElementById("plot-groups");
  if (!I) { box.innerHTML = notMeasured("Not in this data"); return; }
  const look = w => /^every/i.test(w) ? "n-strong" : /^by hand/i.test(w) ? "n-hollow" : "n-mid";
  const when = w => w.split(/[:(]/)[0].trim(), most = Math.max(1, ...I.groups.map(g => g.tests));
  box.innerHTML = I.groups.map(g => plotRow(esc(g.label), stackedBar([{ n: g.tests, cls: look(g.when) }], most, `${g.label}: ${g.tests} tests, ${when(g.when)}`), g.tests)).join("")
    + plotKey([...new Set(I.groups.map(g => g.when))].map(w => [keyTile(look(w)), esc(when(w))]));
}

// Plot 4: a tile per ticked promise for what was written down when it was built, then what the replay says today.
// Quiet unless something failed or is stale; no report, or a day it leaves out, is never drawn as a pass.
function replayWord(d, ec) {
  if (ec.state !== "loaded") return notMeasured("no report");
  const day = ec.days.find(x => x.day === d.day);
  if (!day || day.state === "not checked") return notMeasured("not checked");
  if (day.state === "stale") return `<span class="plot-bad" title="${esc(day.why.join("; "))}">stale</span>`;
  const counts = CHECK_KINDS.map(([k]) => day.counts[k]).filter(Boolean);
  const failed = addUp(counts, "failed") + addUp(counts, "error");
  const passed = k => (day.counts[k] || {}).passed || 0;
  return failed ? `<span class="plot-bad">${failed} failed</span>` : `<span class="plot-quiet">${plural(passed("named_test"), "named test", "named tests")} found; ${plural(passed("verify"), "Verify command", "Verify commands")} and ${plural(passed("break"), "break", "breaks")} re-run; none failed</span>`;
}
function drawEvidencePlot() {
  const box = document.getElementById("plot-evidence"), head = document.getElementById("evidence-headline"), skip = document.getElementById("evidence-skip");
  const ec = DATA.evidence_checks || { state: "absent" };
  const days = DATA.days.filter(d => finished(d) && d.evidence.some(c => c.ticked)).sort((a, b) => rank(a.day) - rank(b.day));
  if (!days.length) { box.innerHTML = notMeasured("No finished day yet."); head.innerHTML = skip.innerHTML = ""; return; }
  const ticked = d => d.evidence.filter(c => c.ticked), asked = days.filter(d => d.evidence_format).flatMap(ticked);
  const states = days.flatMap(d => ticked(d).flatMap(c => Object.values(c.tests))), n = s => states.filter(x => x === s).length;
  const stat = (big, small) => `<div><b class="num">${big}</b><span>${small}</span></div>`;
  head.innerHTML = stat(`${asked.filter(c => c.prs.length).length} of ${asked.length}`, "promises cite the pull request they landed in")
    + stat(`${asked.filter(c => Object.keys(c.tests).length).length} of ${asked.length}`, "promises name a test")
    + stat(`${n("present")} of ${states.length}`, `named tests are still on <code>main</code>${n("retired") ? `, ${n("retired")} retired` : ""}`);
  const live = n("skippable");
  skip.innerHTML = (live ? `${plural(live, "live test needs", "live tests need")} real Claude; CI skips them, run by hand.` : "")
    + (n("missing") ? ` <span class="plot-bad">${plural(n("missing"), "named test has", "named tests have")} left <code>main</code>.</span>` : "");
  const tile = (d, c) => {
    const look = c.red ? "rec-yes" : d.break_format ? "rec-no" : "rec-none";
    const said = `${c.id || c.claim}: ${c.red ? "failure recorded when built" : d.break_format ? "no failure recorded" : "not measured"}`;
    return c.id ? `<button type="button" class="ev-tile ${look}" data-id="${esc(c.id)}" aria-expanded="false" aria-label="${esc(said)}" title="${esc(said)}"></button>` : `<i class="ev-tile ${look}" title="${esc(said)}"></i>`;
  };
  box.innerHTML = plotKey([[`<i class="ev-tile rec-yes"></i>`, "Failure recorded when built"], [`<i class="ev-tile rec-no"></i>`, "None recorded"], [`<i class="ev-tile rec-none"></i>`, "Not measured: written before this was asked for"]])
    + `<div class="ev-row ev-head"><span>Day</span><span>Written down when built</span><span>Replayed today</span></div>`
    + days.map(d => `<div class="ev-row"><span class="plot-name">Day ${dd(d.day)} · ${esc(promiseFeature(d.day))}</span><span class="ev-tiles">${ticked(d).map(c => tile(d, c)).join("")}</span><span class="ev-status">${replayWord(d, ec)}</span></div>`).join("");
  box.addEventListener("click", e => {
    const button = e.target.closest("button[data-id]");
    if (!button) return;
    const row = button.closest(".ev-row"), open = row.nextElementSibling, shown = open && open.hasAttribute("data-detail");
    const same = shown && open.dataset.id === button.dataset.id;
    if (shown) { open.remove(); row.querySelectorAll('[aria-expanded="true"]').forEach(b => b.setAttribute("aria-expanded", "false")); }
    if (same) return;
    row.insertAdjacentHTML("afterend", `<div class="inline-detail" data-detail data-id="${esc(button.dataset.id)}">${detailFor(button.dataset.id)}</div>`);
    button.setAttribute("aria-expanded", "true");
  });
}

// Plot 5: how many merged PRs each workflow failed on. A PR can fail on several, so the note says the bars overlap.
function drawCiPlot() {
  const V = mergedPrs(), box = document.getElementById("plot-ci"), bad = V.filter(v => v.failed);
  if (!V.length) { box.innerHTML = notMeasured("No merged pull request yet."); return; }
  if (!bad.length) { box.innerHTML = `<p class="plot-quiet">CI failed on no merged pull request.</p>`; return; }
  const seen = new Map();
  bad.forEach(v => new Set(v.failed_in).forEach(w => seen.set(w, (seen.get(w) || 0) + 1)));
  const rows = [...seen].sort((a, b) => b[1] - a[1]), most = rows[0][1], total = rows.reduce((a, r) => a + r[1], 0);
  box.innerHTML = rows.map(([w, n]) => plotRow(esc(w), stackedBar([{ n, cls: "ci-failed" }], most, `${w}: ${n} pull requests`), n)).join("")
    + (total > bad.length ? `<p class="plot-note">The bars add up to ${total}, more than the ${bad.length} pull requests, because one can fail in several workflows.</p>` : "");
}

// Plot 6: a dot per merged PR on a log scale. Never green: quick is not the same as good.
function drawOpenTimes() {
  const box = document.getElementById("plot-open"), timed = mergedPrs().filter(v => typeof v.hours === "number");
  if (!timed.length) { box.innerHTML = notMeasured("No merged pull request with its times yet."); return; }
  const mins = v => Math.max(v.hours * 60, 0.5), all = timed.map(mins);
  const lo = Math.floor(Math.log10(Math.min(...all))), hi = Math.max(lo + 1, Math.ceil(Math.log10(Math.max(...all))));
  const at = m => (Math.log10(m) - lo) / (hi - lo) * 100;
  const dot = v => {
    const said = `#${v.number} · ${span(v.hours)}${v.failed ? " · CI failed on it" : ""}`, style = `left:${at(mins(v))}%;top:${6 + v.number * 7 % 28}px`;
    const cls = `pr-dot${v.failed ? " failed" : ""}`;
    return v.url ? `<a class="${cls}" style="${style}" href="${esc(v.url)}" title="${esc(said)}" aria-label="${esc(said)}"></a>` : `<i class="${cls}" style="${style}" title="${esc(said)}"></i>`;
  };
  const ticks = Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);
  box.innerHTML = plotKey([[`<i class="pr-dot key"></i>`, "A merged pull request"], [`<i class="pr-dot failed key"></i>`, "CI failed on it first"], [`<i class="pr-median key"></i>`, "Median"]])
    + Object.keys(STEP).map(k => [k, timed.filter(v => (v.step || v.kind) === k)]).filter(([, vs]) => vs.length).map(([k, vs]) => {
      const middle = median(vs.map(v => v.hours));
      return plotRow(STEP[k], `<span class="dot-track"><i class="pr-median" style="left:${at(Math.max(middle * 60, 0.5))}%"></i>${vs.map(dot).join("")}</span>`, span(middle));
    }).join("")
    + plotRow("", `<span class="dot-axis">${ticks.map(p => `<span style="left:${(p - lo) / (hi - lo) * 100}%">${(10 ** p).toLocaleString("en")}</span>`).join("")}</span>`, "minutes");
}

// Plot 8: every same-as: link followed back to the first defect of its family, one group per day.
function drawRepeats() {
  const box = document.getElementById("plot-repeats"), Rec = DATA.defect_recurrence;
  if (!Rec) { box.innerHTML = notMeasured("Not in this data"); return; }
  if (!Rec.recurrences.length) { box.innerHTML = `<p class="plot-quiet">No problem has been recorded as a repeat of an earlier one.</p>`; return; }
  const dayOf = id => +id.slice(1).split(".")[0], same = new Map(Rec.recurrences.map(r => [r.id, r.same_as]));
  const rootOf = id => { const seen = new Set(); while (same.has(id) && !seen.has(id)) { seen.add(id); id = same.get(id); } return id; };
  const families = new Map();
  Rec.recurrences.forEach(r => { const root = rootOf(r.id); families.set(root, [...(families.get(root) || [root]), r.id]); });
  const within = Rec.recurrences.filter(r => dayOf(r.id) === dayOf(r.same_as)).length, across = Rec.recurrences.length - within;
  const chip = id => {
    const was = same.get(id), inDay = was && dayOf(was) === dayOf(id);
    return `<code class="chain-id${inDay ? " same-day" : ""}" title="${esc(was ? `${id} is the same problem as ${was}` : `${id} is the first time this was recorded`)}">${esc(id)}</code>`;
  };
  box.innerHTML = `<p class="plot-headline"><b>${Rec.recurrences.length}</b> ${Rec.recurrences.length === 1 ? "problem repeated" : "problems repeated"} an earlier one: <b>${across}</b> on a later day, <b>${within}</b> the same day</p>`
    + plotKey([[`<code class="chain-id">D1.2</code>`, "First seen, or came back on a later day"], [`<code class="chain-id same-day">D1.3</code>`, "Came back the same day"]])
    + [...families.values()].sort((a, b) => b.length - a.length || dayOf(a[0]) - dayOf(b[0])).map(ids => {
      const days = [...new Set(ids.map(dayOf))].sort((a, b) => a - b);
      return `<div class="chain">${days.map(d => `<span class="chain-day"><small>Day ${dd(d)}</small>${ids.filter(i => dayOf(i) === d).map(chip).join("")}</span>`).join(`<span class="chain-arrow" aria-hidden="true">→</span>`)}</div>`;
    }).join("");
}

// Plots 9 and 10: where the context went, then what each day wrote and on which model.
function drawTokenPlots() {
  const T = DATA.tokens || [], split = document.getElementById("plot-context"), byDay = document.getElementById("plot-days");
  if (!T.length) { split.innerHTML = byDay.innerHTML = notMeasured("No token counts yet."); return; }
  const outside = contextOf(T.filter(r => r.day == null)), inside = contextOf(T.filter(r => r.day != null)), all = outside + inside;
  split.innerHTML = `<p class="plot-headline"><b>${pct(outside, all)}</b> of the context read was between days</p>`
    + stackedBar([{ n: outside, cls: "n-strong" }, { n: inside, cls: "n-mid" }], all, `Between days ${kilo(outside)}, during days ${kilo(inside)}`)
    + plotKey([[keyTile("n-strong"), `Between days (${kilo(outside)})`], [keyTile("n-mid"), `During days (${kilo(inside)})`]])
    + `<p class="plot-note">Each reply re-read about <b class="num">${kilo(Math.round(all / Math.max(1, addUp(T, "replies"))))}</b> tokens of context.</p>`;
  const days = [...new Set(T.map(r => r.day).filter(d => d != null))].sort((a, b) => rank(a) - rank(b));
  if (!days.length) { byDay.innerHTML = notMeasured("No tokens counted against a day yet."); return; }
  const models = [...new Set(T.map(r => r.model))].sort((a, b) => addUp(T.filter(r => r.model === b), "output") - addUp(T.filter(r => r.model === a), "output"));
  const most = Math.max(...days.map(d => addUp(T.filter(r => r.day === d), "output")));
  byDay.innerHTML = days.map(d => {
    const rs = T.filter(r => r.day === d);
    const parts = models.map(m => ({ n: addUp(rs.filter(r => r.model === m), "output"), color: MODEL_VAR[m] || "var(--other)" }));
    return plotRow(`Day ${dd(d)}`, stackedBar(parts, most, models.filter(m => rs.some(r => r.model === m)).map(m => `${modelName(m)} ${kilo(addUp(rs.filter(r => r.model === m), "output"))}`).join(", ")), kilo(addUp(rs, "output")));
  }).join("");
}

// Plot 11: a gate's catches by cause. Hooks sit apart, because a refusal is not a defect; cost stays a quiet number.
const CAUSES = ["spec", "implementation", "process", "environment", "other"];
function drawGatePlot() {
  const G = DATA.gate_report, box = document.getElementById("plot-gates");
  if (!G) { box.innerHTML = notMeasured("No gate report yet."); return; }
  const gates = G.gates.filter(g => g.found !== null), hooks = G.gates.filter(g => g.found === null);
  const name = c => c[0].toUpperCase() + c.slice(1), most = Math.max(1, ...gates.map(g => g.defects)), top = Math.max(1, ...hooks.map(g => g.refused || 0));
  box.innerHTML = plotKey(CAUSES.filter(c => gates.some(g => g.causes[c])).map(c => [keyTile("", `background:var(--c-${c})`), name(c)]))
    + gates.map(g => plotRow(esc(g.gate), stackedBar(CAUSES.map(c => ({ n: g.causes[c], color: `var(--c-${c})` })), most, CAUSES.filter(c => g.causes[c]).map(c => `${g.causes[c]} ${c}`).join(", ") || "nothing found"),
      `${g.defects}${g.defects ? ` <small>$${fmt(g.cost / g.defects, 2)} each</small>` : ""}`)).join("")
    + (hooks.length ? `<h4>Hooks refuse an action; a refusal is not a defect</h4>` + hooks.map(g => plotRow(esc(g.gate), g.refused == null ? notMeasured("not counted") : stackedBar([{ n: g.refused, cls: "n-mid" }], top, `${g.refused} refused`), g.refused == null ? "–" : `${g.refused} refused`)).join("") : "");
}

// Plots 12 and 13: per date. A refused Read is left out of "allowed", and a date before the refusal log is not a zero.
function drawHookPlots() {
  const H = (DATA.tokens || []).filter(r => "bash" in r), Refused = DATA.refusals || [];
  const cut = document.getElementById("plot-cut"), reads = document.getElementById("plot-reads");
  const shares = [...new Set(H.map(r => r.date))].sort().map(d => { const rs = H.filter(r => r.date === d); return { d, cut: addUp(rs, "cut"), bash: addUp(rs, "bash") }; }).filter(p => p.bash);
  if (!shares.length) cut.innerHTML = notMeasured("No hook counts yet.");
  else {
    const share = p => p.cut / p.bash * 100, top = Math.max(1, ...shares.map(share)), peak = shares.reduce((a, p) => share(p) > share(a) ? p : a);
    const time = p => Date.parse(p.d), t0 = time(shares[0]), t1 = time(shares[shares.length - 1]);
    const x = p => t1 > t0 ? (time(p) - t0) / (t1 - t0) * 100 : 50, y = p => 100 - share(p) / top * 100;
    const named = [...new Set([shares[0], peak, shares[shares.length - 1]])];
    cut.innerHTML = `<div class="mini-line" role="img" aria-label="${esc(shares.map(p => `${p.d}: ${fmt(share(p), 1)}%`).join(", "))}"><svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><polyline points="${shares.map(p => `${x(p)},${y(p)}`).join(" ")}"/></svg>`
      + shares.map(p => `<i style="left:${x(p)}%;top:${y(p)}%" title="${esc(`${p.d}: ${p.cut} of ${p.bash} cut`)}"></i>`).join("")
      + named.map(p => `<span class="num" style="left:${x(p)}%;top:${y(p)}%">${fmt(share(p), 1)}%</span>`).join("") + `</div>`
      + `<div class="mini-axis num">${named.map(p => `<span style="left:${x(p)}%">${esc(p.d.slice(5))}</span>`).join("")}</div>`;
  }
  const refusedOn = d => addUp(Refused.filter(r => r.date === d && r.guard === "read-guard"), "refused");
  const logged = Refused.length ? Refused.map(r => r.date).sort()[0] : null;
  const rows = [...new Set(H.map(r => r.date).concat(Refused.map(r => r.date)))].sort().map(d => ({ d, read: addUp(H.filter(r => r.date === d), "reads"), no: refusedOn(d) })).filter(r => r.read || r.no);
  if (!rows.length) { reads.innerHTML = notMeasured("No hook counts yet."); return; }
  const parts = r => [{ n: Math.max(0, r.read - r.no), cls: "n-strong" }, { n: r.no, cls: "n-hollow" }];
  const most = Math.max(1, ...rows.map(r => Math.max(r.read, r.no)));
  reads.innerHTML = plotKey([[keyTile("n-strong"), "Allowed"], [keyTile("n-hollow"), "Refused"]])
    + rows.map(r => {
      if (!logged || r.d < logged) return plotRow(esc(r.d.slice(5)), notMeasured("before the refusal log"), "–");
      return plotRow(esc(r.d.slice(5)), stackedBar(parts(r), most, `${r.d}: ${r.no} refused, ${Math.max(0, r.read - r.no)} allowed`), `${r.no} of ${Math.max(r.read, r.no)}`);
    }).join("");
}

// The infra workflow's last summary on main (scripts/infra-summary.py), and each of its runs on main.
function drawInfra() {
  const I = DATA.infra || { runs: [], latest: null }, L = I.latest, S = L ? L.summary : {};
  const tone = s => ({ pass: "var(--close)", success: "var(--close)", fail: "var(--fail)", failure: "var(--fail)" })[s] || "var(--muted)";
  const chip = (name, state) => `<span class="chip" style="color:${tone(state)}">${esc(name)} · ${esc(state)}</span>`;
  document.getElementById("infra-head").innerHTML = L
    ? `<p>The latest run on main is <a href="${esc(L.url)}"><code>${esc(L.sha)}</code></a> from ${esc(L.date)}: <span class="chip" style="color:${tone(L.conclusion)}">${esc(L.conclusion || "running")}</span></p>`
    : '<p class="load-error">No infra summary on main yet: it appears after the infra workflow next runs on main.</p>';
  document.getElementById("infra-criteria").innerHTML = Object.entries(S.criteria || {}).map(([c, s]) => chip(c, s)).join("");
  document.getElementById("infra-steps").innerHTML = Object.entries(S.steps || {}).map(([n, s]) => chip(n, s)).join("");
  const resources = Object.entries(S.resources || {}).sort((a, b) => b[1] - a[1]);
  document.getElementById("infra-resources").innerHTML = resources.length
    ? `<table><thead><tr><th>Service</th><th>Created</th></tr></thead><tbody>${resources.map(([s, n]) => `<tr><td>${esc(s)}</td><td class="num">${n}</td></tr>`).join("")}</tbody></table>`
    : "";
  const cost = S.cost;
  document.getElementById("infra-cost").innerHTML = cost
    ? `<table><thead><tr><th>Item</th><th>Count</th><th>$ per hour</th></tr></thead><tbody>${cost.items.map(i => `<tr><td>${esc(i.name)}</td><td class="num">${i.count}</td><td class="num">${i.per_hour == null ? "–" : fmt(i.per_hour, 4)}</td></tr>`).join("")}<tr><th>Total</th><td></td><td class="num">$${fmt(cost.per_hour, 3)}</td></tr></tbody></table><p style="font-size:13px;color:var(--muted)">${esc(cost.note)}, ${esc(cost.region)}. A class with no price is listed with no rate and left out of the total.</p>`
    : "";
  document.getElementById("infra-runs").innerHTML = I.runs.slice().reverse().map(r =>
    `<a class="run-sq" href="${esc(r.url)}" style="background:${tone(r.conclusion)}" title="${esc(`${r.sha} ${r.date} ${r.conclusion || "running"}`)}"></a>`).join("");
}

// The live checks of the one deployment (the project's own), each with the time it ran.
function drawDeployment() {
  const D = DATA.deployment, C = D ? D.checks : [];
  const tone = ok => ok ? "var(--close)" : "var(--fail)";
  if (!D) {
    document.getElementById("deployment-head").innerHTML = '<p class="load-error">Nothing deployed yet: the panel fills when a live check has written docs/dashboard/deployment.json.</p>';
    document.getElementById("deployment-checks").innerHTML = "";
    return;
  }
  document.getElementById("deployment-head").innerHTML = `<p>Checked ${esc(D.domain)} at ${esc(D.checkedAt)}: ${C.filter(c => c.ok).length} of ${C.length} checks passed.</p>`;
  document.getElementById("deployment-checks").innerHTML = `<table><thead><tr><th>Criterion</th><th>Check</th><th>Result</th><th>Detail</th><th>Checked at</th></tr></thead><tbody>${C.map(c => `<tr><td>${esc(c.criterion)}</td><td>${esc(c.name)}</td><td><span class="chip" style="color:${tone(c.ok)}">${c.ok ? "pass" : "fail"}</span></td><td>${esc(c.detail)}</td><td>${esc(c.at)}</td></tr>`).join("")}</tbody></table>`;
}

// Display the evidence as supplied by the data build.
const reasonLabels = { replay_failed: "Replay failed", replay_error: "Replay error", replay_stale: "Replay stale",
  evidence_missing: "Evidence missing", not_seen_red: "Not seen red", test_not_found: "Test not found", handoff_unclaimed: "Hand-off unclaimed",
  not_breakable: "No break possible", test_skippable: "Can be skipped",
  handoff_next: "Hand-off for the next day", handoff_unpicked: "Hand-off no later day picks up" };
// Listed apart, after the rest, each under its heading: a check whose `broken: none → <why>` says no
// break can run from the repository, and a named test CI can skip (orange in "Tests on main").
const NOTED = {
  not_breakable: ["Can’t be broken here", "Checked by hand: the reason no break can run from the repository."],
  test_skippable: ["Can be skipped in CI (expected)", "A live test runs only when its variable is set, so CI skips it: run it by hand. “Tests on main” draws these orange."] };
const seenRed = s => s.state === false && s.none && s.none.length ? `<span title="${esc(s.none.join("; "))}">can’t</span>` : measured(s.state);
const attention = DATA.attention || [], criteria = DATA.criteria_index || [];
const unknown = '<span title="not measured">–</span>';
const measured = value => value == null ? unknown : value ? "yes" : "no";
const values = items => items && items.length ? items.map(esc).join(", ") : unknown;
// A criterion's replay checks counted by status, failed and errored first and marked: "11/11 passed".
const replayCount = status => {
  if (!status || !status.length) return unknown;
  const n = status.reduce((t, s) => (t[s] = (t[s] || 0) + 1, t), {}), bad = ["failed", "error"];
  if (Object.keys(n).length === 1 && n.passed) return `${n.passed}/${n.passed} passed`;
  return [...bad.filter(s => n[s]), ...Object.keys(n).filter(s => !bad.includes(s))].map(s => bad.includes(s)
    ? `<b class="replay-bad">✗ ${n[s]} ${esc(s)}</b>` : `${n[s]} ${esc(s)}`).join(" · ");
};
const itemText = item => `<b>${esc(item.id)}</b> · ${esc(reasonLabels[item.reason] || item.reason)}: ${esc(item.detail)}`;
// What the Inspector used to show for a criterion or day: now opened directly under what was clicked.
function detailFor(id) {
  const row = criteria.find(c => c.id === id), items = attention.filter(a => a.id === id);
  // A check with no diagnostic says only its status: those are counted, not listed one by one.
  const tally = row ? Object.entries(row.replay.checks.reduce((n, c) => (n[c.status] = (n[c.status] || 0) + 1, n), {}))
    .map(([s, n]) => `${n} ${esc(s)}`).join(", ") : "";
  const details = row ? `<h3>${esc(row.id)}</h3><p>${md(row.claim)}</p>
    <p>Spec: ${row.spec ? esc(row.spec) : unknown} · Track: ${row.track == null ? unknown : esc(row.track)}</p>
    <p>PRs: ${values(row.prs)} · Tests: ${values(row.tests)}</p>
    <p>Failure recorded when built: ${row.seen_red.lines && row.seen_red.lines.length ? row.seen_red.lines.map(md).join(", ") : unknown}</p>
    <p>Replay: ${esc(row.replay.state)}${tally ? ` · checks: ${tally}` : ""} · ${values(row.replay.why)}</p>
    <ul>${row.replay.checks.filter(c => c.diagnostic != null).map(c => `<li>${esc(c.status)}: ${esc(c.diagnostic)}</li>`).join("")}</ul>
    <p>Replaces: ${values(row.replaces)} · Replaced by: ${values(row.replaced_by)}</p>` : `<h3>${esc(id)}</h3>`;
  return details + (items.length ? `<p>Attention:</p><ul>${items.map(a => `<li>${itemText(a)}</li>`).join("")}</ul>` : "");
}
// Opens html directly under the clicked element, or closes it if it is already open.
function detailUnder(anchor, wrap) {
  const next = anchor.nextElementSibling;
  if (next && next.hasAttribute("data-detail")) { next.remove(); anchor.setAttribute("aria-expanded", "false"); return; }
  anchor.insertAdjacentHTML("afterend", wrap);
  anchor.setAttribute("aria-expanded", "true");
}
function drawCriteria() {
  const list = document.getElementById("attention-list"), matrix = document.getElementById("criteria-matrix");
  const button = (a, i) => `<button type="button" data-attention="${i}" aria-expanded="false">${itemText(a)}</button>`;
  const flagged = attention.map(button).filter((_, i) => !(attention[i].reason in NOTED));
  const noted = Object.entries(NOTED).map(([reason, [head, why]]) => {
    const items = attention.map(button).filter((_, i) => attention[i].reason === reason);
    return items.length ? `<h3>${head}</h3><p>${why}</p>${items.join("")}` : "";
  }).join("");
  list.innerHTML = DATA.attention == null ? "Not in this data" : (flagged.length ? flagged.join("") : "Nothing needs attention") + noted;
  if (flagged.length) document.getElementById("attention-fold").open = true;
  matrix.innerHTML = DATA.criteria_index == null ? "<caption>Not in this data</caption>" : !criteria.length ? "<caption>No criteria yet</caption>" :
    `<thead><tr><th>Criterion</th><th>Day</th><th>Tag</th><th>Cites a PR</th><th>Test found</th><th>Failure recorded when built</th><th>Replay</th></tr></thead><tbody>${criteria.map((c, i) =>
      `<tr tabindex="0" role="button" aria-expanded="false" data-criterion="${i}"><td>${esc(c.id)}</td><td>${esc(c.day)}</td><td>${esc(c.tag)}</td><td>${measured(c.cited)}</td><td>${measured(c.test_found)}</td><td>${seenRed(c.seen_red)}</td><td>${replayCount(c.replay.status)}</td></tr>`).join("")}</tbody>`;
  list.addEventListener("click", e => {
    const b = e.target.closest("button[data-attention]");
    if (b) detailUnder(b, `<div class="inline-detail" data-detail>${detailFor(attention[+b.dataset.attention].id)}</div>`);
  });
  const toggleRow = e => {
    const r = e.target.closest("tr[data-criterion]");
    if (r) detailUnder(r, `<tr class="detail-row" data-detail><td colspan="7"><div class="inline-detail">${detailFor(criteria[+r.dataset.criterion].id)}</div></td></tr>`);
  };
  matrix.addEventListener("click", toggleRow);
  matrix.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleRow(e); } });
}

/* ---------- the promises, in plain words ---------- */
// Where a promise stands, from the same re-check data as the count over the board: its group there,
// or why it is not in that count.
function promiseStatus(c, reading) {
  const day = DATA.days.find(d => d.day === c.day);
  if (!day || !finished(day)) return "building";
  if ((c.replaced_by || []).length) return "replaced";
  if (c.ticked === false) return "open";
  const cell = reading.latest.get(c.id), look = cell && REPLAY_LOOK[cell.state];
  return look && look.group ? look.group : "unchecked";
}
// The three measurements that once shared the word "proven", as separate facts. Each says how it knows.
function promiseFacts(c, status, reading) {
  const cell = reading.latest.get(c.id), look = cell ? REPLAY_LOOK[cell.state] : {};
  const when = cell ? reading.age((reading.byN.get(cell.n) || {}).pr) : "";
  const mixed = cell && cell.mixed ? " (its checks disagree)" : "";
  const not = { building: "Not yet: this day is not finished", replaced: "No longer checked: replaced by a later promise",
    open: "Not run: this promise was left unticked", unchecked: "Not run: no re-check on record" }[status];
  const passed = not ? [null, not] : status === "skipped" ? [null, `Not run: ${look.why}`]
    : status === "broken" ? [false, `No${when ? ", " + when : ""}: the promise no longer holds${mixed}`]
    : status === "repair" ? [null, `Cannot be trusted: ${look.why}${mixed}`]
    : [true, `Yes${when ? ", " + when : ""}${mixed}`];
  const s = c.seen_red || {};
  const recorded = status === "building" && s.state == null ? [null, "Not yet: this day is not finished"]
    : s.state ? [true, "Yes, noted in the spec"]
    : s.state === false ? (s.none && s.none.length ? [null, `Cannot be planted here: ${s.none.join("; ")}`] : [false, "No"])
    : [null, "Not measured"];
  const planted = not ? [null, not] : status === "skipped" ? [null, `Not run: ${look.why}`]
    : status === "proven" ? [true, `Yes, ${when || "at the last re-check"}${mixed}`]
    : status === "unproven" ? [null, "Not tried: no planted bug is on record for it"]
    : status === "broken" ? [false, "Not reached: the test itself failed"]
    : [false, `No: ${look.why}`];
  return [["Test passed at the last re-check", ...passed], ["Failure was recorded when built", ...recorded], ["Planted bug caught on re-check", ...planted]];
}
// A promise the re-check does not count draws as a hollow circle, and says why.
const STATUS_TILE = { building: "pending", replaced: "pending", open: "pending", unchecked: "pending" };
const STATUS_WORD = { building: "Still being built", open: "Left unticked", unchecked: "Not re-checked", replaced: "Replaced by a later promise" };
const BOARD_ORDER = [...PROMISE_ORDER, "open", "unchecked", "building"];
const statusTile = (s, attrs = "") => `<i class="promise ${STATUS_TILE[s] || s}"${attrs}>${(PROMISE_GROUPS[s] || {}).glyph || ""}</i>`;
const plainOf = c => c.plain ? esc(c.plain) : md(c.claim);
// The one promise board: a row per day, its tiles sorted by state so the row reads like a bar and still counts like
// squares, one count beside them. A replaced promise is no longer on the board; it stays in its row's opened list.
function drawPromises() {
  const box = document.getElementById("promise-days"), key = document.getElementById("promise-key");
  key.innerHTML = "";
  if (DATA.criteria_index == null) { box.innerHTML = `<p class="off">Not in this data</p>`; return; }
  if (!criteria.length) { box.innerHTML = `<p class="off">No promises yet.</p>`; return; }
  const reading = promiseReading(), all = criteria.map(c => ({ c, status: promiseStatus(c, reading) }));
  const days = [...new Set(criteria.map(c => c.day))].sort((a, b) => rank(a) - rank(b));
  box.innerHTML = days.map(day => {
    const rows = all.filter(r => r.c.day === day), on = rows.filter(r => r.status !== "replaced");
    const board = [...on].sort((a, b) => BOARD_ORDER.indexOf(a.status) - BOARD_ORDER.indexOf(b.status));
    const n = s => on.filter(r => r.status === s).length, counted = on.filter(r => r.status in PROMISE_GROUPS).length;
    let note;
    if (on.length && n("building") === on.length) {
      const done = on.filter(r => r.c.ticked).length, some = plural(on.length, "promise", "promises");
      note = `<b>being built</b><em>${done ? `${done} of ${some} finished so far` : `${some}, none finished yet`}</em>`;
    } else if (reading.rp.state !== "loaded" || !counted) {
      note = `${plural(on.length, "promise", "promises")}: no re-check on record`;
    } else {
      const more = [n("broken") && promiseSays("broken", n("broken")), n("repair") && promiseSays("repair", n("repair")), n("skipped") && promiseSays("skipped", n("skipped")),
        n("open") && `${n("open")} left unticked`, n("unchecked") && `${n("unchecked")} with no re-check`].filter(Boolean);
      note = `<b class="num">${n("proven")} of ${counted}</b> proven${more.length ? `<em>${more.join(" · ")}</em>` : ""}`;
    }
    const label = BOARD_ORDER.filter(n).map(s => s in PROMISE_GROUPS ? promiseSays(s, n(s)) : `${n(s)} ${STATUS_WORD[s].toLowerCase()}`).join(", ");
    const tiles = board.map(({ c, status }) => statusTile(status, ` data-promise="${esc(c.id)}" title="${esc(`${(PROMISE_GROUPS[status] || {}).word || STATUS_WORD[status]}: ${promiseText(c)}`)}"`)).join("");
    const items = rows.map(({ c, status }) => `<li><details class="promise-item" data-promise="${esc(c.id)}"><summary>${statusTile(status)}<span>${plainOf(c)}${status === "replaced" ? ` <em class="promise-replaced">${STATUS_WORD.replaced}</em>` : ""}</span></summary>
      <ul class="facts">${promiseFacts(c, status, reading).map(([name, ok, text]) => `<li class="fact ${ok === true ? "yes" : ok === false ? "no" : "unknown"}"><span class="fact-name">${name}</span><span class="fact-value">${esc(text)}</span></li>`).join("")}</ul>
      <details class="tech"><summary>Technical detail</summary><div class="inline-detail">${detailFor(c.id)}</div></details></details></li>`).join("");
    return `<details class="promise-row promise-day"><summary><span class="promise-name"><small class="num">Day ${dd(day)}</small>${esc(promiseFeature(day))}</span><span class="promise-tiles" role="group" aria-label="${esc(label)}">${tiles}</span><span class="promise-age">${note}</span></summary><ul class="promise-items">${items}</ul></details>`;
  }).join("");
  const pending = all.filter(r => r.status !== "replaced" && !(r.status in PROMISE_GROUPS)).length, gone = all.filter(r => r.status === "replaced").length;
  key.innerHTML = (pending ? `<span><i class="promise pending"></i><span><b>Not counted yet</b> still being built, left unticked, or never re-checked</span></span>` : "")
    + (gone ? `<span>${plural(gone, "promise was", "promises were")} replaced by a later one: no longer on the board, still listed when its row is opened</span>` : "");
  // A square is a shortcut to its promise: open the row at that promise instead of toggling the row.
  box.addEventListener("click", e => {
    const tile = e.target.closest(".promise-tiles [data-promise]");
    if (!tile) return;
    e.preventDefault();
    const row = tile.closest("details"), item = [...row.querySelectorAll(".promise-item")].find(d => d.dataset.promise === tile.dataset.promise);
    row.open = item.open = true;
    item.scrollIntoView({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  });
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
const howLink = (text, step) => `<a href="#how-step-${step}" data-how="${step}">${text}</a>`;
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
function drawHow() {
  const X = DATA.how_this_works || {}, { promises, inGroup } = promiseReading();
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
  const groups = PROMISE_ORDER.map(g => [g, inGroup(promises, g).length]).filter(([, n]) => n);
  const bad = inGroup(promises, "broken").length + inGroup(promises, "repair").length;
  const tally = !groups.length ? "<p>No re-check of the promises is on record.</p>"
    : `<p>All ${plural(promises.length, "promise", "promises")} at their latest re-check:</p>`
      + `<div class="how-bar" role="img" aria-label="${groups.map(([g, n]) => promiseSays(g, n)).join(", ")}">${groups.map(([g, n]) => `<i class="promise ${g}" style="--n:${n}"></i>`).join("")}</div>`
      + `<div class="how-barkey">${groups.map(([g, n]) => `<span>${promiseTile(g)}<div><b>${n}</b> ${esc(PROMISE_GROUPS[g].means)}</div></span>`).join("")}</div>`
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
      body: `<p>Code keeps changing after a day closes. So finished promises are tested again on later merged code, and the planted bugs are put back to see if the tests still notice.</p>${recheck}${tally}` + src("docs/dashboard/replay-history.json", "the re-check results") },
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
    if (scroll) document.getElementById("how-step-" + s).closest("details.measure").open = true;
    if (scroll) document.getElementById("how-step-" + s).scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  };
  [[spine, false], [document.getElementById("how-cast"), true], [document.getElementById("summary-known"), true]].forEach(([box, scroll]) => box.addEventListener("click", e => {
    const b = e.target.closest("[data-how]");
    if (b) { e.preventDefault(); show(b.dataset.how, scroll); }
  }));
  narrow.addEventListener("change", place);
  const wanted = location.hash.startsWith("#how-step-") && location.hash.slice(10);
  show(stepOf(wanted) ? wanted : current, Boolean(stepOf(wanted)));
}

/* ---------- the summary ---------- */
// "Day 07 Track 0: The tests: C07.1, C07.2" is the step and the criteria it names.
const nextParts = step => { const m = step.match(/^(.*?):\s*(C\d+\.\d+(?:\s*[,\u2013]\s*C\d+\.\d+)*)\s*$/s); return m ? [m[1], m[2]] : [step, ""]; };
function drawSummary() {
  const reading = promiseReading(), { rp, promises, inGroup, newest } = reading, now = DATA.now, days = DATA.days;
  const planned = new Set([...ORDER, ...days.map(d => d.day)]).size, done = days.filter(finished).length;
  const cur = days.find(d => d.day === now.current_day);
  const count = g => inGroup(promises, g).length;
  const building = criteria.filter(c => promiseStatus(c, reading) === "building").length;
  const ec = DATA.evidence_checks || { state: "absent" };
  const checked = ec.state === "loaded" ? ec.days.filter(d => d.counts) : [];
  const stale = ec.state === "loaded" ? ec.days.filter(d => d.state !== "current").length : 0;
  const tally = s => checked.reduce((t, d) => t + Object.values(d.counts).reduce((a, k) => a + k[s], 0), 0);
  const failed = tally("failed") + tally("error");

  const known = rp.state === "loaded" && promises.length > 0;
  const health = !known ? ["Not known", "no re-check of the promises is on record", "unknown"]
    : count("broken") ? [plural(count("broken"), "promise is broken", "promises are broken"), "see the promises below", "bad"]
    : count("repair") ? [plural(count("repair"), "test needs repair", "tests need repair"), "see the promises below", "bad"]
    : failed ? [plural(failed, "evidence check failed", "evidence checks failed"), "see Evidence behind the ticks", "bad"]
    : ["Nothing was broken at the last re-check", `${plural(promises.length, "promise", "promises")} re-checked${newest ? `, most recently ${newest}` : ""}`, "good"];

  const nextId = (now.next_step.match(/\bC\d+\.\d+/) || [])[0], nextRow = criteria.find(c => c.id === nextId);
  const [nextHead, nextIds] = nextParts(now.next_step);
  const T = DATA.tokens || [], costed = T.filter(r => r.cost);
  const total = costed.reduce((a, r) => a + r.cost, 0);
  const card = (k, v, n, tone = "") => `<div class="stat-card ${tone}"><div class="stat-k">${k}</div><div class="stat-v">${v}</div><div class="stat-n">${n}</div></div>`;
  document.getElementById("summary-cards").innerHTML =
    card("Progress", `${done} of ${planned} days finished`, cur ? `Day ${dd(cur.day)} in progress: ${md(cur.title)}` : "between days")
    + card("Health", esc(health[0]), esc(health[1]), health[2])
    + card("What is next", `<span title="${esc(nextHead)}">${md(nextHead)}</span>`, nextRow && nextRow.plain ? esc(nextRow.plain) : esc(nextIds), "clamp")
    + card("Cost so far", costed.length ? `${costed.length < T.length ? "at least " : ""}$${fmt(total, 2)}` : "Not known",
      costed.length ? "AI usage at list prices, counted on the maintainer's computer; sessions run elsewhere are not in it" : "no token counts yet");

  const list = items => `<ul>${items.filter(Boolean).map(t => `<li>${t}</li>`).join("")}</ul>`;
  const kept = count("proven") + count("unproven");
  const yes = known ? [
    howLink(`${kept} of ${plural(promises.length, "finished promise", "finished promises")} kept at the last re-check`, "recheck"),
    howLink(`${plural(count("proven"), "promise", "promises")} caught a planted bug`, "bug"),
  ] : [];
  if (checked.length) yes.push(howLink(`${plural(tally("passed"), "check", "checks")} of the recorded evidence replayed, each at its day's close, ${failed} failed`, "close"));
  const I = DATA.test_inventory;
  if (I && I.total) yes.push(howLink(`${plural(I.total, "test", "tests")} in the project`, "red"));
  const live = I && (I.groups.find(g => g.key === "live") || {}).tests;
  const no = [
    !known && "Whether the promises still hold: no re-check is on record",
    count("unproven") && (count("unproven") === 1 ? "1 promise passes, but no planted bug has tried it" : `${count("unproven")} promises pass, but no planted bug has tried them`),
    count("skipped") && (count("skipped") === 1 ? "1 promise cannot be checked here" : `${count("skipped")} promises cannot be checked here`),
    building && (building === 1 ? "1 promise is not finished yet" : `${building} promises are not finished yet`),
    known && newest && `The last re-check was ${newest}, and it is run by hand`,
    stale && plural(stale, "finished day's evidence report is out of date", "finished days' evidence reports are out of date"),
    live && `${plural(live, "test runs", "tests run")} against real Claude only by hand, never in CI`,
  ];
  document.getElementById("summary-known").innerHTML =
    `<div class="known yes"><h3>What we know</h3>${list(yes.length ? yes : ["Nothing yet"])}</div>`
    + `<div class="known no"><h3>What we do not know yet</h3>${list(no.some(Boolean) ? no : ["Nothing listed"])}</div>`;
}

/* ---------- where the tests are ---------- */
function drawTested() {
  const I = DATA.test_inventory, groups = document.getElementById("test-groups"), note = document.getElementById("test-note");
  const present = ((R[N - 1] || {}).evidence || {}).present;
  groups.innerHTML = !I ? "<caption>Not in this data</caption>"
    : `<thead><tr><th>Group</th><th class="r">Tests</th><th>When they run</th></tr></thead><tbody>`
      + I.groups.map(g => `<tr><td>${esc(g.label)}</td><td class="r">${g.tests}</td><td class="t">${esc(g.when)}</td></tr>`).join("")
      + `<tr><td><b>Total</b></td><td class="r"><b>${I.total}</b></td><td></td></tr></tbody>`;
  note.innerHTML = (present != null
    ? `The “Tests on main” chart shows “present ${present}”: that counts the test names finished promises cite that still exist, not all tests.`
    : `The “Tests on main” chart counts the test names finished promises cite that still exist, not all tests.`)
    + (I && I.unreadable.length ? ` Not counted, because they could not be read: ${I.unreadable.map(esc).join(", ")}.` : "");
}
panel("attention-list", drawCriteria); panel("promise-days", drawPromises); panel("test-groups", drawTested);

panel("summary-cards", drawSummary); panel("how-flow", drawHow); panel("today", drawNow); panel("plot-ladder", drawLadder); panel("plot-grew", drawGrew); panel("work-bar", drawWork); panel("perday", drawPerDay); panel("breaks", drawVerification); panel("merge-time", drawMergeTime);
pullPicker("pull-steps", drawPullSteps, PULL_DAYS[PULL_DAYS.length - 1]); panel("pull-totals", drawPullTotals); pullPicker("pull-scale", drawPullScale, "all");
panel("infra-head", drawInfra); panel("deployment-head", drawDeployment); panel("token-bars", drawTokens); panel("relabel", drawRelabel);
panel("evidence-gaps", drawEvidence); panel("evidence-checks", drawEvidenceChecks); panel("proof-kinds", drawProofKinds); panel("hand-offs", drawHandOffs); panel("read", drawConclusion);
panel("plot-all", drawPromisePlots); panel("replay", drawReplay); panel("plot-history", drawTrustHistory); panel("plot-groups", drawTestBars); panel("plot-evidence", drawEvidencePlot); panel("plot-ci", drawCiPlot); panel("plot-open", drawOpenTimes);
panel("plot-repeats", drawRepeats); panel("plot-context", drawTokenPlots); panel("plot-gates", drawGatePlot); panel("plot-cut", drawHookPlots);
panel("findings", drawFindings); panel("tbl", drawTable); setSel(sel); panel("not-measured-list", drawNotMeasured);

// A panel with nothing to draw yet stays in its place and is also one line under "Not measured yet",
// in the words its box already drew; once it has data it drops off the list.
function drawNotMeasured() {
  const said = id => (document.getElementById(id).innerHTML.match(/<(p|td)\b[^>]*>(.*?)<\/\1>/) || [])[2] || "";
  const rec = DATA.defect_recurrence, I = DATA.infra || { runs: [] };
  const empty = [
    ["services", "Service boundaries", !R.some(r => movedShare(r) != null), said("moved")],
    ["second-reader", "Does a second reader agree with the defect tags?", !DATA.days.some(d => finished(d) && d.relabel) && !(rec && rec.recurrences.length),
      DATA.days.some(finished) ? READER_NONE : said("relabel")],
    ["infra", "Infrastructure", !I.latest && !I.runs.length, said("infra-head")],
    ["deployment", "Deployment", !DATA.deployment, said("deployment-head")],
    ["removal-checks", "Removal checks", !(DATA.removals || []).length, said("removals")],
  ].filter(p => p[2]);
  const show = (id, on) => {
    document.getElementById(id).hidden = !on;
    document.querySelectorAll(`#toc a[href="#${id}"]`).forEach(a => { a.parentElement.hidden = !on; });
  };
  show("not-measured", empty.length);
  document.getElementById("not-measured-list").innerHTML = empty.map(([, name, , why]) => `<li><b>${name}</b>: ${why}</li>`).join("");
}
}

// The contents is open as a rail beside the cards from 1100px, and a menu on a narrower screen that a picked link closes.
// A link to something inside a closed measurement opens that measurement first.
function openTarget() {
  const target = location.hash && document.getElementById(location.hash.slice(1));
  if (!target) return;
  for (let d = target; d; d = d.parentElement) if (d.tagName === "DETAILS") d.open = true;
  target.scrollIntoView();
}
// The contents marks the section being read: the last one whose top has passed the top of the screen.
function markContents() {
  const links = [...document.querySelectorAll("#toc a")].map(a => [a, document.getElementById(a.hash.slice(1))]).filter(([, t]) => t);
  const rail = matchMedia("(min-width: 1100px)");
  const mark = () => {
    let here = null;
    for (const [a, t] of links) if (!t.closest("[hidden]") && (t.closest("details.measure") || t).getBoundingClientRect().top <= (rail.matches ? 120 : 174)) here = a;
    links.forEach(([a]) => a === here ? a.setAttribute("aria-current", "true") : a.removeAttribute("aria-current"));
  };
  mark();
  addEventListener("scroll", mark, { passive: true });
}
function contents() {
  const toc = document.getElementById("toc"), rail = matchMedia("(min-width: 1100px)"), fit = () => { toc.open = rail.matches; };
  fit(); rail.addEventListener("change", fit);
  toc.addEventListener("click", e => { if (!rail.matches && e.target.closest("a")) toc.open = false; });
  addEventListener("hashchange", openTarget);
  openTarget();
  markContents();
}

function start() {
  contents();
  if (window.SPEC_DRIFT) return boot(window.SPEC_DRIFT);
  document.getElementById("today").innerHTML = '<p class="load-error">The data did not load. Build the page with <code>python scripts/spec-drift.py --build dashboard.html</code>; if this is the built page, it was published without its data line.</p>';
}
