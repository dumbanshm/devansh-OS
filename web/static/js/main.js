// Dashboard bootstrap: loads every section, wires drill-downs, manual entry,
// the live clock and periodic refresh.

import { api } from "./api.js";
import { renderHeatmap } from "./heatmap.js";
import { renderCards } from "./cards.js";
import { renderNeglect } from "./neglect.js";
import { renderTimeline } from "./timeline.js";
import { openDetail } from "./detail.js";
import { openProtein } from "./protein.js";
import { openSettings } from "./settings.js";
import { accent } from "./palette.js";

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

async function loadHeatmaps() {
  const { heatmaps } = await api.heatmaps();
  const wrap = $("#heatmaps");
  wrap.innerHTML = "";
  // Short ranges are narrow, so pack two per row instead of letting cells balloon.
  wrap.classList.toggle("heatmaps-grid--cols", heatmapRange !== "year");
  await Promise.all(
    heatmaps.map(async (h) => {
      const cell = document.createElement("div");
      cell.className = "heatmap-card";
      wrap.appendChild(cell);
      try {
        const data = await api.heatmap(h.provider, h.metric, heatmapRange);
        renderHeatmap(cell, data, {
          onCellClick: (day) => openDetail(h.provider, day),
        });
      } catch (err) {
        cell.innerHTML = `<div class="hm-error">${h.label}: ${err.message}</div>`;
      }
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
  $("#protein-btn").addEventListener("click", () =>
    openProtein({ onChange: onProteinChange }));

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
  startClock();
  wireControls();
  await refreshAll();
  // Periodic refresh so the always-on board stays current.
  setInterval(refreshAll, 60_000);
}

main();
