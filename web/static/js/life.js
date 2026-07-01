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

function renderGrid() {
  const { total_weeks, current_week_index, weeks_per_year } = state;
  const cols = weeks_per_year;
  const rows = Math.ceil(total_weeks / cols);

  const wrap = document.createElement("div");
  wrap.className = "life-grid-wrap";

  const grid = document.createElement("div");
  grid.className = "life-grid";
  grid.style.setProperty("--life-cols", cols);

  const frag = document.createDocumentFragment();
  for (let i = 0; i < total_weeks; i++) {
    const cell = document.createElement("div");
    cell.className = "life-cell";
    cell.dataset.i = i;

    if (current_week_index == null || i > current_week_index) {
      cell.classList.add("future");
    } else if (i === current_week_index) {
      cell.classList.add("current");
    } else {
      cell.classList.add("lived");
      const sc = state.scores?.[i];
      if (sc && sc.band) cell.classList.add(`band-${sc.band}`);
    }

    if (milestonesByWeek.has(i)) {
      cell.classList.add("has-milestone");
      cell.innerHTML = FLAG_SVG;
    }
    frag.appendChild(cell);
  }
  grid.appendChild(frag);

  // Age labels down the left, one per decade row.
  const ages = document.createElement("div");
  ages.className = "life-ages";
  for (let r = 0; r < rows; r++) {
    const span = document.createElement("span");
    if (r % 10 === 0) span.textContent = r;
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
  t.style.left = e.pageX + 14 + "px";
  t.style.top = e.pageY + 14 + "px";
}
