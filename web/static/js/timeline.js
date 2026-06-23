// Chronological activity feed — reconstruct recent life, grouped by day.

import { accent } from "./palette.js";

function timeOf(ts) {
  try {
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch (_) { return ""; }
}

export function renderTimeline(container, data, { onClick } = {}) {
  container.innerHTML = "";
  if (!data.groups.length) {
    container.innerHTML = `<div class="tl-empty">No recent activity recorded.</div>`;
    return;
  }
  data.groups.forEach((group) => {
    const g = document.createElement("div");
    g.className = "tl-group";
    g.innerHTML = `<div class="tl-day">${group.label}</div>`;
    const list = document.createElement("div");
    list.className = "tl-items";
    group.items.forEach((it) => {
      const row = document.createElement("button");
      row.className = "tl-item";
      const href = it.payload && it.payload.url;
      row.innerHTML = `
        <span class="tl-dot" style="background:${accent(it.color)}"></span>
        <span class="tl-time">${timeOf(it.ts)}</span>
        <span class="tl-prov" style="color:${accent(it.color)}">${it.provider_name}</span>
        <span class="tl-title">${it.title}${it.detail ? ` · ${it.detail}` : ""}</span>`;
      row.addEventListener("click", () => {
        if (href) window.open(href, "_blank");
        else if (onClick) onClick(it.provider, group.day);
      });
      list.appendChild(row);
    });
    g.appendChild(list);
    container.appendChild(g);
  });
}
