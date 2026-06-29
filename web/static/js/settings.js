// Settings modal — protein target / eating window + protein bank CRUD.
// Built lazily into the DOM (same pattern as detail.js). Calls onChange() after
// any save so the dashboard (card pace, heatmap scale) refreshes.

import { api } from "./api.js";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

let overlayEl, panelEl, bodyEl, changed = false, onChangeCb = null;

function ensure() {
  if (panelEl) return;
  overlayEl = document.createElement("div");
  overlayEl.className = "detail-overlay settings-overlay";
  overlayEl.addEventListener("click", close);

  panelEl = document.createElement("aside");
  panelEl.className = "detail-panel settings-panel";
  panelEl.innerHTML = `
    <div class="detail-head">
      <span class="detail-title">Settings</span>
      <button class="detail-close" aria-label="Close">esc</button>
    </div>
    <div class="detail-body settings-body"></div>`;
  panelEl.querySelector(".detail-close").addEventListener("click", close);

  document.body.appendChild(overlayEl);
  document.body.appendChild(panelEl);
  bodyEl = panelEl.querySelector(".settings-body");
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && panelEl.classList.contains("open")) close();
  });
}

export async function openSettings({ onChange } = {}) {
  ensure();
  onChangeCb = onChange;
  changed = false;
  overlayEl.classList.add("open");
  panelEl.classList.add("open");
  await render();
}

function close() {
  if (!panelEl) return;
  overlayEl.classList.remove("open");
  panelEl.classList.remove("open");
  if (changed) onChangeCb?.();
}

async function render() {
  bodyEl.innerHTML = `<div class="d-empty">Loading…</div>`;
  let settings, bank, rituals;
  try {
    [settings, { items: bank }, { items: rituals }] = await Promise.all([
      api.proteinSettings(), api.proteinBank(), api.ritualsBank(),
    ]);
  } catch (err) {
    bodyEl.innerHTML = `<div class="d-error">Failed to load: ${esc(err.message)}</div>`;
    return;
  }

  const rows = bank.map((b) => `
    <tr data-id="${b.id}">
      <td><input class="st-in st-name" value="${esc(b.name)}" /></td>
      <td><input class="st-in st-g" type="number" min="0" step="1" value="${b.protein_g}" /></td>
      <td><input class="st-in st-serv" value="${esc(b.serving_label)}" placeholder="—" /></td>
      <td class="st-actions">
        <button class="btn-link st-save" title="save">save</button>
        <button class="btn-link st-del" title="delete">del</button>
      </td>
    </tr>`).join("");

  // "Every" cadence as a clear 1–7 day dropdown (keeps any out-of-range legacy value).
  const everyOptions = (val) => {
    const days = [1, 2, 3, 4, 5, 6, 7];
    if (val > 7) days.push(val);
    return days.map((d) =>
      `<option value="${d}"${d === val ? " selected" : ""}>${d} ${d === 1 ? "day" : "days"}</option>`
    ).join("");
  };

  const ritualRows = rituals.map((r) => `
    <tr data-id="${r.id}">
      <td><input class="st-in rk-name" value="${esc(r.name)}" /></td>
      <td class="rk-on-cell">
        <label class="rk-switch" title="active — only active rituals are tracked">
          <input type="checkbox" class="rk-active" ${r.active ? "checked" : ""} />
          <span class="rk-slider"></span>
        </label>
      </td>
      <td><select class="st-in rk-int" title="cadence">${everyOptions(r.interval_days)}</select></td>
      <td><input class="st-in rk-dose" value="${esc(r.dose_label)}" placeholder="—" /></td>
      <td class="st-actions">
        <button class="btn-link rk-save" title="save">save</button>
        <button class="btn-link rk-del" title="delete">del</button>
      </td>
    </tr>`).join("");

  const ritualEmpty = `<tr class="rk-empty-row"><td colspan="5">No rituals yet — add your first below.</td></tr>`;

  bodyEl.innerHTML = `
    <section class="d-section">
      <h4 class="d-heading">Protein target & eating window</h4>
      <div class="st-grid">
        <label class="st-field"><span>Daily target (g)</span>
          <input id="st-target" class="st-in" type="number" min="1" step="5" value="${settings.target_g}" /></label>
        <label class="st-field"><span>Window start (h)</span>
          <input id="st-ws" class="st-in" type="number" min="0" max="23" value="${settings.window_start}" /></label>
        <label class="st-field"><span>Window end (h)</span>
          <input id="st-we" class="st-in" type="number" min="1" max="24" value="${settings.window_end}" /></label>
      </div>
      <button id="st-save-settings" class="btn">save target & window</button>
      <p class="st-note">Pace ramps across the window — before ${settings.window_start}:00 expected = 0, after ${settings.window_end}:00 expected = target.</p>
    </section>

    <section class="d-section">
      <h4 class="d-heading">Protein bank</h4>
      <table class="st-table">
        <thead><tr><th>Food</th><th>g</th><th>Serving</th><th></th></tr></thead>
        <tbody id="st-bank">${rows}</tbody>
      </table>
      <div class="st-add-row">
        <input id="st-new-name" class="st-in" placeholder="name" />
        <input id="st-new-g" class="st-in" type="number" min="0" step="1" placeholder="g" />
        <input id="st-new-serv" class="st-in" placeholder="serving (opt.)" />
        <button id="st-add" class="btn">add</button>
      </div>
    </section>

    <section class="d-section">
      <h4 class="d-heading">Rituals</h4>
      <table class="st-table rk-table">
        <thead><tr><th>Ritual</th><th class="rk-col-on">On</th><th class="rk-col-every">Every</th><th>Dose</th><th></th></tr></thead>
        <tbody id="rk-bank">${ritualRows || ritualEmpty}</tbody>
        <tfoot>
          <tr class="rk-add">
            <td><input id="rk-new-name" class="st-in" placeholder="e.g. Creatine" /></td>
            <td></td>
            <td><select id="rk-new-int" class="st-in rk-int" title="cadence">${everyOptions(1)}</select></td>
            <td><input id="rk-new-dose" class="st-in rk-dose" placeholder="5g (opt.)" /></td>
            <td class="st-actions"><button id="rk-add" class="btn">add</button></td>
          </tr>
        </tfoot>
      </table>
      <p class="st-note">"Every" is the cadence in days (1 = daily). Only active rituals count toward neglect, the heatmap and inputs — deactivating keeps history.</p>
    </section>`;

  // ── wire settings save ──
  bodyEl.querySelector("#st-save-settings").addEventListener("click", async (e) => {
    const body = {
      target_g: parseFloat(bodyEl.querySelector("#st-target").value),
      window_start: parseInt(bodyEl.querySelector("#st-ws").value, 10),
      window_end: parseInt(bodyEl.querySelector("#st-we").value, 10),
    };
    await guard(e.target, api.proteinSettingsSave(body));
  });

  // ── wire bank row save/delete ──
  bodyEl.querySelectorAll("#st-bank tr").forEach((tr) => {
    const id = Number(tr.dataset.id);
    tr.querySelector(".st-save").addEventListener("click", (e) =>
      guard(e.target, api.proteinBankUpdate(id, readRow(tr))));
    tr.querySelector(".st-del").addEventListener("click", async (e) => {
      await guard(e.target, api.proteinBankDelete(id));
      render();
    });
  });

  // ── wire add ──
  bodyEl.querySelector("#st-add").addEventListener("click", async (e) => {
    const name = bodyEl.querySelector("#st-new-name").value.trim();
    const g = parseFloat(bodyEl.querySelector("#st-new-g").value);
    if (!name || !g || g <= 0) return;
    const serving_label = bodyEl.querySelector("#st-new-serv").value.trim() || null;
    await guard(e.target, api.proteinBankAdd({ name, protein_g: g, serving_label }));
    render();
  });

  // ── wire rituals bank row save/delete (skip the empty-state placeholder row) ──
  bodyEl.querySelectorAll("#rk-bank tr[data-id]").forEach((tr) => {
    const id = Number(tr.dataset.id);
    tr.querySelector(".rk-save").addEventListener("click", (e) =>
      guard(e.target, api.ritualsBankUpdate(id, readRitualRow(tr))));
    tr.querySelector(".rk-del").addEventListener("click", async (e) => {
      await guard(e.target, api.ritualsBankDelete(id));
      render();
    });
  });

  // ── wire rituals add ──
  bodyEl.querySelector("#rk-add").addEventListener("click", async (e) => {
    const name = bodyEl.querySelector("#rk-new-name").value.trim();
    if (!name) return;
    const interval_days = parseInt(bodyEl.querySelector("#rk-new-int").value, 10) || 1;
    const dose_label = bodyEl.querySelector("#rk-new-dose").value.trim() || null;
    await guard(e.target, api.ritualsBankAdd({ name, interval_days, dose_label, active: true }));
    render();
  });
}

function readRitualRow(tr) {
  return {
    name: tr.querySelector(".rk-name").value.trim(),
    interval_days: parseInt(tr.querySelector(".rk-int").value, 10) || 1,
    dose_label: tr.querySelector(".rk-dose").value.trim() || null,
    active: tr.querySelector(".rk-active").checked,
  };
}

function readRow(tr) {
  return {
    name: tr.querySelector(".st-name").value.trim(),
    protein_g: parseFloat(tr.querySelector(".st-g").value),
    serving_label: tr.querySelector(".st-serv").value.trim() || null,
  };
}

async function guard(btn, promise) {
  const old = btn.textContent;
  btn.disabled = true;
  try {
    await promise;
    changed = true;
    btn.textContent = "✓";
    setTimeout(() => { btn.textContent = old; btn.disabled = false; }, 700);
  } catch (err) {
    btn.textContent = "!";
    btn.title = err.message;
    setTimeout(() => { btn.textContent = old; btn.disabled = false; }, 1200);
  }
}
