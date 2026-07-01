// Settings modal — tabbed sections (Protein / Rituals / …). A row of tabs sits
// under the header; only the active tab's content is fetched + rendered, so a
// large bank never buries the other tabs. Built lazily into the DOM (same pattern
// as detail.js). Calls onChange() after any save so the dashboard refreshes.

import { api } from "./api.js";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// Lucide "flag" icon, inlined (offline-first — no icon-library dependency).
const FLAG_SVG = `<svg class="life-flag" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><path d="M4 22v-7"/></svg>`;

// Tab registry — single source of truth. Add a tab = append one entry here.
const TABS = [
  { id: "protein", label: "Protein", render: renderProteinTab },
  { id: "rituals", label: "Rituals", render: renderRitualsTab },
  { id: "life", label: "Life", render: renderLifeTab },
];
let activeTab = "protein"; // remembered across opens

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
    <div class="settings-tabs">
      ${TABS.map((t) =>
        `<button class="settings-tab" data-tab="${t.id}">${esc(t.label)}</button>`
      ).join("")}
    </div>
    <div class="detail-body settings-body"></div>`;
  panelEl.querySelector(".detail-close").addEventListener("click", close);

  panelEl.querySelectorAll(".settings-tab").forEach((btn) =>
    btn.addEventListener("click", () => switchTab(btn.dataset.tab)));

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
  await renderActive();
}

function close() {
  if (!panelEl) return;
  overlayEl.classList.remove("open");
  panelEl.classList.remove("open");
  if (changed) onChangeCb?.();
}

function switchTab(id) {
  activeTab = id;
  renderActive();
}

async function renderActive() {
  // Reflect the active tab in the tab bar.
  panelEl.querySelectorAll(".settings-tab").forEach((b) =>
    b.classList.toggle("active", b.dataset.tab === activeTab));

  bodyEl.innerHTML = `<div class="d-empty">Loading…</div>`;
  const tab = TABS.find((t) => t.id === activeTab) || TABS[0];
  await tab.render();
}

// ── Protein tab ─────────────────────────────────────────────────────────────

async function renderProteinTab() {
  let settings, bank;
  try {
    [settings, { items: bank }] = await Promise.all([
      api.proteinSettings(), api.proteinBank(),
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
      renderActive();
    });
  });

  // ── wire add ──
  bodyEl.querySelector("#st-add").addEventListener("click", async (e) => {
    const name = bodyEl.querySelector("#st-new-name").value.trim();
    const g = parseFloat(bodyEl.querySelector("#st-new-g").value);
    if (!name || !g || g <= 0) return;
    const serving_label = bodyEl.querySelector("#st-new-serv").value.trim() || null;
    await guard(e.target, api.proteinBankAdd({ name, protein_g: g, serving_label }));
    renderActive();
  });
}

// ── Rituals tab ─────────────────────────────────────────────────────────────

async function renderRitualsTab() {
  let rituals;
  try {
    ({ items: rituals } = await api.ritualsBank());
  } catch (err) {
    bodyEl.innerHTML = `<div class="d-error">Failed to load: ${esc(err.message)}</div>`;
    return;
  }

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

  // ── wire rituals bank row save/delete (skip the empty-state placeholder row) ──
  bodyEl.querySelectorAll("#rk-bank tr[data-id]").forEach((tr) => {
    const id = Number(tr.dataset.id);
    tr.querySelector(".rk-save").addEventListener("click", (e) =>
      guard(e.target, api.ritualsBankUpdate(id, readRitualRow(tr))));
    tr.querySelector(".rk-del").addEventListener("click", async (e) => {
      await guard(e.target, api.ritualsBankDelete(id));
      renderActive();
    });
  });

  // ── wire rituals add ──
  bodyEl.querySelector("#rk-add").addEventListener("click", async (e) => {
    const name = bodyEl.querySelector("#rk-new-name").value.trim();
    if (!name) return;
    const interval_days = parseInt(bodyEl.querySelector("#rk-new-int").value, 10) || 1;
    const dose_label = bodyEl.querySelector("#rk-new-dose").value.trim() || null;
    await guard(e.target, api.ritualsBankAdd({ name, interval_days, dose_label, active: true }));
    renderActive();
  });
}

// ── Life tab ──────────────────────────────────────────────────────────────────

async function renderLifeTab() {
  let s, milestones;
  try {
    [s, { items: milestones }] = await Promise.all([
      api.lifeSettings(), api.milestones(),
    ]);
  } catch (err) {
    bodyEl.innerHTML = `<div class="d-error">Failed to load: ${esc(err.message)}</div>`;
    return;
  }

  // Split any stored YYYY-MM-DD so the three pickers preselect it.
  const [by, bm, bd] = (s.birth_date || "").split("-");
  const now = new Date();
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  const dayOpts = (sel) => Array.from({ length: 31 }, (_, i) => i + 1)
    .map((d) => `<option value="${d}"${String(d) === String(+sel) ? " selected" : ""}>${d}</option>`).join("");
  const monthOpts = (sel) => MONTHS
    .map((m, i) => `<option value="${i + 1}"${String(i + 1) === String(+sel) ? " selected" : ""}>${m}</option>`).join("");
  const yearOpts = (sel) => {
    const end = now.getFullYear();
    const years = [];
    for (let y = end; y >= 1920; y--) years.push(y);
    return years.map((y) => `<option value="${y}"${String(y) === String(+sel) ? " selected" : ""}>${y}</option>`).join("");
  };

  const milestoneRows = milestones.map((m) => `
    <tr data-id="${m.id}">
      <td class="ms-icon">${FLAG_SVG}</td>
      <td><input class="st-in ms-in-title" value="${esc(m.title)}" /></td>
      <td class="ms-day"><input class="st-in ms-in-day" type="date" value="${esc(m.day)}" /></td>
      <td class="st-actions">
        <button class="btn-link ms-save" title="save">save</button>
        <button class="btn-link ms-del" title="delete">del</button>
      </td>
    </tr>`).join("");
  const milestoneEmpty = `<tr class="rk-empty-row"><td colspan="4">No milestones yet — add your first below.</td></tr>`;

  bodyEl.innerHTML = `
    <section class="d-section">
      <h4 class="d-heading">Life calendar</h4>
      <label class="st-field"><span>Birth date</span></label>
      <div class="st-dob">
        <select id="st-birth-d" class="st-in" aria-label="Day"><option value="">DD</option>${dayOpts(bd)}</select>
        <select id="st-birth-m" class="st-in" aria-label="Month"><option value="">MM</option>${monthOpts(bm)}</select>
        <select id="st-birth-y" class="st-in" aria-label="Year"><option value="">YYYY</option>${yearOpts(by)}</select>
      </div>
      <div class="st-grid" style="margin-top:12px">
        <label class="st-field"><span>Life expectancy (years)</span>
          <input id="st-life-years" class="st-in" type="number" min="1" max="130" step="1" value="${s.life_expectancy_years}" /></label>
      </div>
      <button id="st-save-life" class="btn" style="margin-top:12px">save</button>
      <p class="st-note">The grid is ${s.life_expectancy_years} rows × 52 weeks. Every box is one week of life — past filled, this week highlighted, the rest ahead of you.</p>
    </section>

    <section class="d-section">
      <h4 class="d-heading">Milestones</h4>
      <table class="st-table ms-table">
        <thead><tr><th></th><th>Milestone</th><th>Date</th><th></th></tr></thead>
        <tbody id="ms-list">${milestoneRows || milestoneEmpty}</tbody>
        <tfoot>
          <tr class="rk-add">
            <td class="ms-icon">${FLAG_SVG}</td>
            <td><input id="ms-new-title" class="st-in" placeholder="e.g. Started college" /></td>
            <td class="ms-day"><input id="ms-new-day" class="st-in" type="date" /></td>
            <td class="st-actions"><button id="ms-add" class="btn">add</button></td>
          </tr>
        </tfoot>
      </table>
      <p class="st-note">Milestones pin a marker to the week they fall in — past or future. They show on the Life calendar on hover.</p>
    </section>`;

  bodyEl.querySelector("#st-save-life").addEventListener("click", async (e) => {
    const d = bodyEl.querySelector("#st-birth-d").value;
    const m = bodyEl.querySelector("#st-birth-m").value;
    const y = bodyEl.querySelector("#st-birth-y").value;
    let birth_date = "";
    if (d && m && y) {
      birth_date = `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    } else if (d || m || y) {
      e.target.textContent = "pick D/M/Y";
      setTimeout(() => { e.target.textContent = "save"; }, 1200);
      return;
    }
    const body = {
      birth_date,
      life_expectancy_years: parseInt(bodyEl.querySelector("#st-life-years").value, 10),
    };
    await guard(e.target, api.lifeSettingsSave(body));
  });

  // ── wire milestone row save/delete (skip the empty-state placeholder) ──
  bodyEl.querySelectorAll("#ms-list tr[data-id]").forEach((tr) => {
    const id = Number(tr.dataset.id);
    tr.querySelector(".ms-save").addEventListener("click", (e) =>
      guard(e.target, api.milestoneUpdate(id, readMilestoneRow(tr))));
    tr.querySelector(".ms-del").addEventListener("click", async (e) => {
      await guard(e.target, api.milestoneDelete(id));
      renderActive();
    });
  });

  // ── wire milestone add ──
  bodyEl.querySelector("#ms-add").addEventListener("click", async (e) => {
    const title = bodyEl.querySelector("#ms-new-title").value.trim();
    const day = bodyEl.querySelector("#ms-new-day").value;
    if (!title || !day) return;
    await guard(e.target, api.milestoneAdd({ day, title }));
    renderActive();
  });
}

// ── Shared helpers ──────────────────────────────────────────────────────────

function readMilestoneRow(tr) {
  return {
    day: tr.querySelector(".ms-in-day").value,
    title: tr.querySelector(".ms-in-title").value.trim(),
  };
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
