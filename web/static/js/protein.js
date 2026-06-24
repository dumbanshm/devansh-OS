// Protein log widget — the one manual input on the board. Lists today's meals,
// quick-add from the bank (or free-form), and keeps a running total / target.
// Optimistically re-renders and calls onChange() so the card + heatmap refresh.

import { api } from "./api.js";
import { openSettings } from "./settings.js";

const esc = (s) => String(s).replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// ── Slide-in Protein panel (reuses the .detail-panel chrome) ───────────────
let overlayEl, panelEl, hostEl;

function ensurePanel() {
  if (panelEl) return;
  overlayEl = document.createElement("div");
  overlayEl.className = "detail-overlay";
  overlayEl.addEventListener("click", closeProtein);

  panelEl = document.createElement("aside");
  panelEl.className = "detail-panel protein-panel";
  panelEl.innerHTML = `
    <div class="detail-head">
      <span class="detail-title">Protein</span>
      <button class="detail-close" aria-label="Close">esc</button>
    </div>
    <div class="detail-body protein-host"></div>
    <div class="protein-panel-foot">
      <button class="btn-link" data-manage>Manage bank &amp; target →</button>
    </div>`;
  panelEl.querySelector(".detail-close").addEventListener("click", closeProtein);

  document.body.appendChild(overlayEl);
  document.body.appendChild(panelEl);
  hostEl = panelEl.querySelector(".protein-host");
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && panelEl.classList.contains("open")) closeProtein();
  });
}

export async function openProtein({ onChange } = {}) {
  ensurePanel();
  overlayEl.classList.add("open");
  panelEl.classList.add("open");
  panelEl.querySelector("[data-manage]").onclick = () => {
    closeProtein();
    openSettings({ onChange });
  };
  await mountProtein(hostEl, { onChange });
}

export function closeProtein() {
  if (!panelEl) return;
  overlayEl.classList.remove("open");
  panelEl.classList.remove("open");
}

export async function mountProtein(el, { onChange } = {}) {
  let custom = false; // free-form input mode

  async function render() {
    let bank = [], log = { entries: [], total_g: 0, target_g: 130 };
    try {
      [{ items: bank }, log] = await Promise.all([api.proteinBank(), api.proteinLog()]);
    } catch (err) {
      el.innerHTML = `<div class="hm-error">protein: ${esc(err.message)}</div>`;
      return;
    }

    const pct = Math.min(100, Math.round((log.total_g / log.target_g) * 100));
    const entries = log.entries.map((e) => {
      const serv = e.servings && e.servings !== 1 ? ` ·×${e.servings}` : "";
      return `<li class="pl-item">
          <span class="pl-name">${esc(e.food_name)}${serv}</span>
          <span class="pl-g">${e.grams}g</span>
          <button class="pl-del" data-del="${e.id}" title="remove">×</button>
        </li>`;
    }).join("");

    const opts = bank.map((b) =>
      `<option value="${b.id}">${esc(b.name)} · ${b.protein_g}g${b.serving_label ? ` (${esc(b.serving_label)})` : ""}</option>`
    ).join("");

    const adder = custom
      ? `<input class="pl-in pl-name-in" placeholder="food name" />
         <input class="pl-in pl-num" type="number" min="0" step="1" placeholder="g" />
         <label class="pl-save" title="add to bank"><input type="checkbox" class="pl-save-cb" /> bank</label>
         <button class="pl-add" data-mode="custom">add</button>
         <button class="pl-toggle btn-link" data-toggle>pick</button>`
      : `<select class="pl-in pl-select">${opts || '<option disabled>empty bank</option>'}</select>
         <input class="pl-in pl-num" type="number" min="0" step="0.5" value="1" title="servings" />
         <button class="pl-add" data-mode="bank">add</button>
         <button class="pl-toggle btn-link" data-toggle>custom</button>`;

    el.innerHTML = `
      <div class="pl-head">
        <span class="pl-total">${log.total_g}<span class="pl-target">/${log.target_g}g</span></span>
        <div class="pl-bar"><span style="width:${pct}%"></span></div>
      </div>
      <ul class="pl-list">${entries || '<li class="pl-empty">nothing logged today</li>'}</ul>
      <div class="pl-add-row">${adder}</div>`;

    el.querySelectorAll("[data-del]").forEach((b) =>
      b.addEventListener("click", () => act(api.proteinDelete(Number(b.dataset.del)))));
    el.querySelector("[data-toggle]")?.addEventListener("click", () => { custom = !custom; render(); });
    el.querySelector(".pl-add")?.addEventListener("click", add);
    el.querySelector(".pl-name-in")?.addEventListener("keydown", (e) => { if (e.key === "Enter") add(); });
  }

  async function add() {
    const mode = el.querySelector(".pl-add").dataset.mode;
    if (mode === "bank") {
      const sel = el.querySelector(".pl-select");
      if (!sel || !sel.value) return;
      const servings = parseFloat(el.querySelector(".pl-num").value) || 1;
      await act(api.proteinAdd({ food_id: Number(sel.value), servings }));
    } else {
      const name = el.querySelector(".pl-name-in").value.trim();
      const grams = parseFloat(el.querySelector(".pl-num").value);
      if (!name || !grams || grams <= 0) return;
      const save = el.querySelector(".pl-save-cb").checked;
      await act(api.proteinAdd({ food_name: name, grams, save_to_bank: save }));
    }
  }

  async function act(promise) {
    try { await promise; } catch (err) { console.error(err); }
    await render();
    onChange?.();
  }

  await render();
  return render;
}
