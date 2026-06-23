// Generic drill-down side panel. Renders ANY provider's declared detail payload
// (sections -> rows -> {label,value,href}). One component for every provider.

import { api } from "./api.js";
import { accent } from "./palette.js";

let panelEl, overlayEl, bodyEl, titleEl;

function ensure() {
  if (panelEl) return;
  overlayEl = document.createElement("div");
  overlayEl.className = "detail-overlay";
  overlayEl.addEventListener("click", close);

  panelEl = document.createElement("aside");
  panelEl.className = "detail-panel";
  panelEl.innerHTML = `
    <div class="detail-head">
      <span class="detail-title"></span>
      <button class="detail-close" aria-label="Close">esc</button>
    </div>
    <div class="detail-body"></div>`;
  panelEl.querySelector(".detail-close").addEventListener("click", close);

  document.body.appendChild(overlayEl);
  document.body.appendChild(panelEl);
  titleEl = panelEl.querySelector(".detail-title");
  bodyEl = panelEl.querySelector(".detail-body");
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });
}

function rowHtml(row) {
  const val = row.href
    ? `<a href="${row.href}" target="_blank" rel="noopener">${row.value}</a>`
    : row.value;
  return `<div class="d-row"><span class="d-row-lbl">${row.label}</span>
            <span class="d-row-val">${val}</span></div>`;
}

export async function openDetail(provider, day) {
  ensure();
  titleEl.textContent = "Loading…";
  bodyEl.innerHTML = "";
  overlayEl.classList.add("open");
  panelEl.classList.add("open");
  try {
    const data = await api.detail(provider, day);
    panelEl.style.setProperty("--accent", accent(data.color));
    titleEl.textContent = data.title;
    bodyEl.innerHTML = (data.sections || []).map((s) => `
      <section class="d-section">
        <h4 class="d-heading">${s.heading}</h4>
        ${(s.rows || []).map(rowHtml).join("") || '<div class="d-row d-empty">—</div>'}
      </section>`).join("");
  } catch (err) {
    titleEl.textContent = provider;
    bodyEl.innerHTML = `<div class="d-error">Failed to load: ${err.message}</div>`;
  }
}

export function close() {
  if (!panelEl) return;
  overlayEl.classList.remove("open");
  panelEl.classList.remove("open");
}
