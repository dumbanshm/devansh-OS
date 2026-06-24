// KPI cards — recency-first (the "system" number leads, totals are secondary).

import { accent } from "./palette.js";

function statusDot(status) {
  const map = {
    ok: "var(--ok)", error: "var(--crit)",
    disabled: "var(--dim)", never: "var(--dim)",
  };
  return `<span class="dot" style="background:${map[status] || "var(--dim)"}"
              title="${status}"></span>`;
}

export function renderCards(container, data, { onCardClick } = {}) {
  container.innerHTML = "";
  data.cards.forEach((card) => {
    const el = document.createElement("button");
    el.className = "card";
    el.style.setProperty("--accent", accent(card.color));

    const r = card.recency;
    const stale = r.days_since !== null && r.days_since >= 3;
    const recencyClass = r.days_since === 0 ? "recency-fresh"
      : stale ? "recency-stale" : "recency-warm";

    // Protein leads with pace (goal vs eating-window), not a recency line.
    const lead = card.pace
      ? `<div class="card-pace pace-${card.pace.state}">
           <span class="card-pace-main">${card.pace.today_g}<span class="card-pace-target">/${card.pace.target_g}g</span></span>
           <span class="card-pace-sub">${card.pace.text}</span>
         </div>`
      : `<div class="card-recency ${recencyClass}">
           <span class="card-recency-lbl">last</span>
           <span class="card-recency-val">${r.text}</span>
         </div>`;

    const stats = card.stats.map((s) =>
      `<div class="card-stat">
         <span class="card-stat-val">${s.value}${s.unit || ""}</span>
         <span class="card-stat-lbl">${s.label}</span>
       </div>`).join("");

    el.innerHTML = `
      <div class="card-head">
        <span class="card-title">${card.title}</span>
        <span class="card-meta">${statusDot(card.sync_status)}</span>
      </div>
      ${lead}
      <div class="card-stats">${stats || ""}</div>
      <div class="card-foot">
        <span class="card-streak">▲ ${card.current_streak}d streak</span>
        ${card.enabled ? "" : '<span class="card-disabled">not configured</span>'}
      </div>`;

    if (onCardClick) el.addEventListener("click", () => onCardClick(card.provider));
    container.appendChild(el);
  });
}
