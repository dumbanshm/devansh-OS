// Life-in-Weeks calendar — a full-viewport overlay (memento mori). One cell per
// week of life: 52 columns × N years (default 90). Past weeks are filled, the
// current week pulses, future weeks are empty. Milestones pin a marker to a week.
//
// Read-only, like the rest of the dashboard: this page only displays. Milestones
// are authored in Settings → Life, not here.
//
// Perf: up to ~4,680 cells are rendered once into a DocumentFragment with NO
// per-cell listeners — the hover tooltip is handled by delegation on the grid
// container, reading each cell's data-i (week index).
//
// Week scoring is delegated to the backend, which is dormant: every lived week
// renders neutral until the multi-signal engine ships. The band legend is shown
// greyed until `scoring_active` flips true.

import { api } from "./api.js";
import { openSettings } from "./settings.js";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const DAY_MS = 86400000;

// Lucide "flag" icon, inlined (the app is offline-first — no icon-library CDN).
const FLAG_SVG = `<svg class="life-flag" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><path d="M4 22v-7"/></svg>`;

let overlayEl, panelEl, bodyEl;
let state = null;          // last /api/life payload
let milestonesByWeek = new Map();
let tooltipEl = null;

// ── Lifecycle ────────────────────────────────────────────────────────────────

function ensure() {
  if (panelEl) return;
  overlayEl = document.createElement("div");
  overlayEl.className = "life-overlay";
  overlayEl.addEventListener("click", (e) => { if (e.target === overlayEl) close(); });

  panelEl = document.createElement("div");
  panelEl.className = "life-panel";
  panelEl.innerHTML = `
    <header class="life-head">
      <div class="life-title">Life in Weeks <span class="life-sub">— every box is one week</span></div>
      <div class="life-head-right">
        <div id="life-legend" class="life-legend"></div>
        <button class="life-close" aria-label="Close">esc</button>
      </div>
    </header>
    <div class="life-body"></div>`;
  panelEl.querySelector(".life-close").addEventListener("click", close);

  document.body.appendChild(overlayEl);
  document.body.appendChild(panelEl);
  bodyEl = panelEl.querySelector(".life-body");

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && panelEl.classList.contains("open")) close();
  });

  // Re-fit the grid to the window (debounced) whenever it's open.
  let rz;
  window.addEventListener("resize", () => {
    if (!panelEl.classList.contains("open") || !state?.birth_date) return;
    clearTimeout(rz);
    rz = setTimeout(renderGrid, 120);
  });
}

export async function openLife() {
  ensure();
  overlayEl.classList.add("open");
  panelEl.classList.add("open");
  await load();
}

function close() {
  hideTooltip();
  overlayEl?.classList.remove("open");
  panelEl?.classList.remove("open");
}

async function load() {
  bodyEl.innerHTML = `<div class="life-msg">Loading…</div>`;
  try {
    state = await api.life();
  } catch (err) {
    bodyEl.innerHTML = `<div class="life-msg life-err">Failed to load: ${esc(err.message)}</div>`;
    return;
  }
  milestonesByWeek = new Map();
  for (const m of state.milestones || []) {
    if (m.week_index == null) continue;
    if (!milestonesByWeek.has(m.week_index)) milestonesByWeek.set(m.week_index, []);
    milestonesByWeek.get(m.week_index).push(m);
  }
  renderLegend();
  if (!state.birth_date) { renderEmpty(); return; }
  renderGrid();
}

// ── Empty state (no birth date yet) ──────────────────────────────────────────

function renderEmpty() {
  bodyEl.innerHTML = `
    <div class="life-msg">
      <p>Set your birth date to draw your life.</p>
      <button id="life-setup" class="btn">Open Settings → Life</button>
    </div>`;
  bodyEl.querySelector("#life-setup").addEventListener("click", () => {
    close();
    openSettings({ onChange: () => {} });
  });
}

// ── Legend ────────────────────────────────────────────────────────────────────

function renderLegend() {
  const el = panelEl.querySelector("#life-legend");
  if (!state.birth_date) { el.innerHTML = ""; return; }
  const lived = state.current_week_index != null ? state.current_week_index + 1 : 0;
  const left = Math.max(0, state.total_weeks - lived);
  const dormant = !state.scoring_active
    ? `<span class="life-legend-note" title="Per-week value scoring is not active yet">value engine: inactive</span>`
    : "";
  el.innerHTML = `
    <span class="life-stat"><strong>${lived.toLocaleString()}</strong> lived</span>
    <span class="life-stat"><strong>${left.toLocaleString()}</strong> left</span>
    ${dormant}`;
}

// ── Grid ──────────────────────────────────────────────────────────────────────

const GAP = 3, CELL_MIN = 6, CELL_MAX = 16, AGES_W = 26;

// Choose a column count + cell size so all `total` cells fill the available box
// (both dimensions) with square cells — instead of a fixed 52-wide strip. The
// column count is derived from the box's aspect ratio; the cell size is then the
// largest that fits both width and height (clamped so cells stay small).
function computeLayout(total) {
  // bodyEl.client* includes its 20px padding; subtract it, the ages gutter and
  // the wrap gap so the grid fits without triggering a scrollbar.
  const W = Math.max(120, bodyEl.clientWidth - 40 - AGES_W - 8);
  const H = Math.max(120, bodyEl.clientHeight - 40);
  const aspect = W / H;
  let cols = Math.round(Math.sqrt(total * aspect));
  cols = Math.max(26, Math.min(cols, total));
  const rows = Math.ceil(total / cols);
  const cell = Math.max(CELL_MIN, Math.min(
    CELL_MAX,
    Math.floor(Math.min((W - cols * GAP) / cols, (H - rows * GAP) / rows)),
  ));
  return { cols, rows, cell };
}

function renderGrid() {
  const { total_weeks, current_week_index } = state;
  const { cols, rows, cell } = computeLayout(total_weeks);

  const wrap = document.createElement("div");
  wrap.className = "life-grid-wrap";

  const grid = document.createElement("div");
  grid.className = "life-grid";
  grid.style.gridTemplateColumns = `repeat(${cols}, ${cell}px)`;
  grid.style.setProperty("--life-cell", `${cell}px`);
  grid.style.setProperty("--life-gap", `${GAP}px`);

  const frag = document.createDocumentFragment();
  for (let i = 0; i < total_weeks; i++) {
    const c = document.createElement("div");
    c.className = "life-cell";
    c.dataset.i = i;

    if (current_week_index == null || i > current_week_index) {
      c.classList.add("future");
    } else if (i === current_week_index) {
      c.classList.add("current");
    } else {
      c.classList.add("lived");
      const sc = state.scores?.[i];
      if (sc && sc.band) c.classList.add(`band-${sc.band}`);
    }

    if (milestonesByWeek.has(i)) {
      c.classList.add("has-milestone");
      c.innerHTML = FLAG_SVG;
    }
    frag.appendChild(c);
  }
  grid.appendChild(frag);

  // Age gutter: label the first row of each decade of age. With a variable
  // column count a row no longer equals a year, so derive age from the week
  // index at the row's start (week = row * cols).
  const ages = document.createElement("div");
  ages.className = "life-ages";
  ages.style.setProperty("--life-cell", `${cell}px`);
  ages.style.setProperty("--life-gap", `${GAP}px`);
  let lastDecade = -1;
  for (let r = 0; r < rows; r++) {
    const span = document.createElement("span");
    const age = Math.floor((r * cols) / state.weeks_per_year);
    const decade = Math.floor(age / 10) * 10;
    if (decade !== lastDecade) { span.textContent = decade; lastDecade = decade; }
    ages.appendChild(span);
  }

  wrap.appendChild(ages);
  wrap.appendChild(grid);
  bodyEl.innerHTML = "";
  bodyEl.appendChild(wrap);

  // Delegated hover only — the page is read-only.
  grid.addEventListener("mousemove", onHover);
  grid.addEventListener("mouseleave", hideTooltip);
}

// ── Week helpers (mirror the backend definition) ─────────────────────────────

function weekStart(i) {
  const b = new Date(state.birth_date + "T00:00:00");
  return new Date(b.getTime() + i * 7 * DAY_MS);
}

function fmtDate(d) {
  return d.toISOString().slice(0, 10);
}

// ── Tooltip ───────────────────────────────────────────────────────────────────

function tooltip() {
  if (!tooltipEl) {
    tooltipEl = document.createElement("div");
    tooltipEl.className = "life-tooltip";
    document.body.appendChild(tooltipEl);
  }
  return tooltipEl;
}
function hideTooltip() { if (tooltipEl) tooltipEl.style.opacity = "0"; }

function onHover(e) {
  const cell = e.target.closest(".life-cell");
  if (!cell) { hideTooltip(); return; }
  const i = Number(cell.dataset.i);
  const start = weekStart(i);
  const end = new Date(start.getTime() + 6 * DAY_MS);
  const age = Math.floor(i / state.weeks_per_year);
  const wk = i % state.weeks_per_year;
  const ms = milestonesByWeek.get(i) || [];
  const msLine = ms.length
    ? `<div class="life-tt-ms">${ms.map((m) => `${FLAG_SVG} ${esc(m.title)}`).join("<br>")}</div>`
    : "";
  const t = tooltip();
  t.innerHTML = `<strong>age ${age} · wk ${wk}</strong>
    <div class="life-tt-dim">${fmtDate(start)} → ${fmtDate(end)}</div>${msLine}`;
  t.style.opacity = "1";
  // Viewport coords + position:fixed so the tooltip never extends the document
  // (which would spawn a scrollbar). Flip near the right/bottom edges.
  const pad = 14;
  const r = t.getBoundingClientRect();
  let x = e.clientX + pad;
  let y = e.clientY + pad;
  if (x + r.width > window.innerWidth) x = e.clientX - r.width - pad;
  if (y + r.height > window.innerHeight) y = e.clientY - r.height - pad;
  t.style.left = Math.max(4, x) + "px";
  t.style.top = Math.max(4, y) + "px";
}
