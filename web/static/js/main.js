// Dashboard bootstrap: loads every section, wires drill-downs, manual entry,
// the live clock and periodic refresh.

import { api } from "./api.js";
import { renderHeatmap } from "./heatmap.js";
import { renderCards } from "./cards.js";
import { renderNeglect } from "./neglect.js";
import { renderTimeline } from "./timeline.js";
import { openDetail } from "./detail.js";
import { openProtein } from "./protein.js";
import { openRituals } from "./rituals.js";
import { openSettings } from "./settings.js";
import { accent } from "./palette.js";
import { initSpatialNav } from "./spatial_nav.js";
import { initPaletteUI } from "./palette_ui.js";
import { registerProvider } from "./registry.js";

const $ = (sel) => document.querySelector(sel);
let heatmapRange = "year";

async function loadHeader() {
  const s = await api.summary();
  $("#hdr-date").textContent = s.date;
  const sum = $("#hdr-summary");
  if (s.summary.length) {
    sum.innerHTML = s.summary
      .map((i) =>
        `<span class="hdr-chip">
           <span class="hdr-dot" style="background:${accent(i.color)}"></span>
           ${i.text}
         </span>`)
      .join("");
  } else {
    sum.innerHTML = `<span class="hdr-chip hdr-chip-empty">nothing logged today</span>`;
  }
}

async function loadNeglect() {
  const data = await api.neglect();
  renderNeglect($("#neglect"), data, { onClick: (p) => openDetail(p) });
}

async function loadCards() {
  const data = await api.cards();
  renderCards($("#cards"), data, {
    onCardClick: (p) =>
      p === "protein" ? openProtein({ onChange: onProteinChange }) : openDetail(p),
  });
}

// Fetch + render one heatmap into its card. For blocks with variants (Rituals),
// switching the dropdown re-draws the same card with the chosen series.
async function drawHeatmapCard(cell, provider, metric, label) {
  try {
    const data = await api.heatmap(provider, metric, heatmapRange);
    renderHeatmap(cell, data, {
      onCellClick: (day) => openDetail(provider, day),
      onVariantChange: (newMetric) => drawHeatmapCard(cell, provider, newMetric, label),
    });
  } catch (err) {
    cell.innerHTML = `<div class="hm-error">${label}: ${err.message}</div>`;
  }
}

async function loadHeatmaps() {
  const { heatmaps } = await api.heatmaps();
  const wrap = $("#heatmaps");
  wrap.innerHTML = "";
  // Short ranges are narrow, so pack two per row instead of letting cells balloon.
  wrap.classList.toggle("heatmaps-grid--cols", heatmapRange !== "year");
  await Promise.all(
    heatmaps.map((h) => {
      const cell = document.createElement("div");
      cell.className = "heatmap-card";
      wrap.appendChild(cell);
      return drawHeatmapCard(cell, h.provider, h.metric, h.label);
    })
  );
}

async function loadTimeline() {
  const data = await api.timeline(10);
  renderTimeline($("#timeline"), data, { onClick: (p, day) => openDetail(p, day) });
}

// Logging protein changes the day total → refresh the card (pace), the heatmap
// and the header chips, but not the whole board.
async function onProteinChange() {
  await Promise.allSettled([loadHeader(), loadCards(), loadHeatmaps()]);
}

// Toggling a ritual changes a binary cell + adherence → refresh the card, the
// heatmap block, header chips and neglect (a lapse can clear/appear).
async function onRitualsChange() {
  await Promise.allSettled([loadHeader(), loadCards(), loadHeatmaps(), loadNeglect()]);
}

async function refreshAll() {
  await Promise.allSettled([
    loadHeader(), loadNeglect(), loadCards(), loadHeatmaps(), loadTimeline(),
  ]);
}

function startClock() {
  const el = $("#hdr-clock");
  const tick = () => {
    el.textContent = new Date().toLocaleTimeString([], {
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  };
  tick();
  setInterval(tick, 1000);
}

function wireControls() {
  registerProvider("System", () => [
    {
      id: "sys.protein",
      title: "Add Protein",
      category: "Actions",
      keywords: ["food", "diet", "nutrition", "eat"],
      action: () => openProtein({ onChange: onProteinChange })
    },
    {
      id: "sys.rituals",
      title: "Log Rituals",
      category: "Actions",
      keywords: ["supplement", "creatine", "magnesium", "medicine", "meds", "vitamin", "daily"],
      action: () => openRituals({ onChange: onRitualsChange })
    },
    {
      id: "sys.settings",
      title: "Open Settings",
      category: "Navigation",
      keywords: ["config", "preferences", "edit"],
      action: () => openSettings({ onChange: refreshAll })
    },
    {
      id: "sys.sync",
      title: "Force Sync All",
      category: "Actions",
      keywords: ["refresh", "reload", "update"],
      action: async () => {
        const btn = $("#sync-btn");
        btn.disabled = true;
        btn.textContent = "syncing…";
        try { await api.syncAll(); await refreshAll(); }
        finally { btn.disabled = false; btn.textContent = "sync"; }
      }
    }
  ]);

  $("#protein-btn").addEventListener("click", () =>
    openProtein({ onChange: onProteinChange }));

  $("#rituals-btn").addEventListener("click", () =>
    openRituals({ onChange: onRitualsChange }));

  $("#settings-btn").addEventListener("click", () =>
    openSettings({ onChange: refreshAll }));

  $("#sync-btn").addEventListener("click", async (e) => {
    e.target.disabled = true;
    e.target.textContent = "syncing…";
    try { await api.syncAll(); await refreshAll(); }
    finally { e.target.disabled = false; e.target.textContent = "sync"; }
  });

  document.querySelectorAll("[data-range]").forEach((btn) => {
    btn.addEventListener("click", () => {
      heatmapRange = btn.dataset.range;
      document.querySelectorAll("[data-range]").forEach((b) =>
        b.classList.toggle("active", b === btn));
      loadHeatmaps();
    });
  });
}

async function main() {
  initSpatialNav();
  initPaletteUI();
  startClock();
  wireControls();
  await refreshAll();
  // Periodic refresh so the always-on board stays current.
  setInterval(refreshAll, 60_000);
}

main();
