// Rituals log widget — daily supplements / meds / routines. Lists today's active
// rituals as binary toggles (tap = done / not-done); presence is the only data,
// no quantities. Optimistically re-renders and calls onChange() so the card,
// heatmap block and neglect refresh. Reuses the .detail-panel chrome.

import { api } from "./api.js";
import { openSettings } from "./settings.js";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

let overlayEl, panelEl, hostEl;

function ensurePanel() {
  if (panelEl) return;
  overlayEl = document.createElement("div");
  overlayEl.className = "detail-overlay";
  overlayEl.addEventListener("click", closeRituals);

  panelEl = document.createElement("aside");
  panelEl.className = "detail-panel rituals-panel";
  panelEl.innerHTML = `
    <div class="detail-head">
      <span class="detail-title">Rituals</span>
      <button class="detail-close" aria-label="Close">esc</button>
    </div>
    <div class="detail-body rituals-host"></div>
    <div class="rituals-panel-foot">
      <button class="btn-link" data-manage>Manage rituals →</button>
    </div>`;
  panelEl.querySelector(".detail-close").addEventListener("click", closeRituals);

  document.body.appendChild(overlayEl);
  document.body.appendChild(panelEl);
  hostEl = panelEl.querySelector(".rituals-host");
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && panelEl.classList.contains("open")) closeRituals();
  });
}

export async function openRituals({ onChange } = {}) {
  ensurePanel();
  overlayEl.classList.add("open");
  panelEl.classList.add("open");
  panelEl.querySelector("[data-manage]").onclick = () => {
    closeRituals();
    openSettings({ onChange });
  };
  await mountRituals(hostEl, { onChange });
}

export function closeRituals() {
  if (!panelEl) return;
  overlayEl.classList.remove("open");
  panelEl.classList.remove("open");
}

export async function mountRituals(el, { onChange } = {}) {
  async function render() {
    let day = { items: [] };
    try {
      day = await api.ritualsDay();
    } catch (err) {
      el.innerHTML = `<div class="hm-error">rituals: ${esc(err.message)}</div>`;
      return;
    }

    const doneCount = day.items.filter((i) => i.done).length;
    const items = day.items.map((it) => `
      <li class="rl-item${it.done ? " rl-on" : ""}">
        <button class="rl-check" data-toggle="${it.id}" data-done="${it.done ? 1 : 0}"
                aria-pressed="${it.done}" title="${it.done ? "mark not done" : "mark done"}">${it.done ? "✓" : ""}</button>
        <span class="rl-name">${esc(it.name)}${it.dose_label ? ` <span class="rl-dose">${esc(it.dose_label)}</span>` : ""}</span>
      </li>`).join("");

    el.innerHTML = `
      <div class="rl-head">
        <span class="rl-count">${doneCount}<span class="rl-of">/${day.items.length}</span></span>
        <span class="rl-lbl">done today</span>
      </div>
      <ul class="rl-list">${items || '<li class="rl-empty">no active rituals — add some in settings</li>'}</ul>`;

    el.querySelectorAll("[data-toggle]").forEach((b) =>
      b.addEventListener("click", () => {
        const id = Number(b.dataset.toggle);
        const done = b.dataset.done === "1";
        act(api.ritualsToggle({ ritual_id: id, done: !done }));
      }));
  }

  async function act(promise) {
    try { await promise; } catch (err) { console.error(err); }
    await render();
    onChange?.();
  }

  await render();
  return render;
}
