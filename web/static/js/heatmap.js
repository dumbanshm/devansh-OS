// Reusable GitHub-style contribution heatmap (custom, no chart lib).
// Responsive: cells scale to fill the container width so the whole range is
// always fully visible (no horizontal scroll). Hover tooltips, month labels
// and a current/longest streak footer.

import { cellColor } from "./palette.js";

const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

let tooltipEl = null;
function tooltip() {
  if (!tooltipEl) {
    tooltipEl = document.createElement("div");
    tooltipEl.className = "hm-tooltip";
    document.body.appendChild(tooltipEl);
  }
  return tooltipEl;
}

function fmt(v) {
  return Number.isInteger(v) ? String(v) : String(Math.round(v * 100) / 100);
}

// data: { label, color, unit, scale_max, range, cells:[{day,value}],
//         current_streak, longest_streak, last_active }
export function renderHeatmap(container, data, { onCellClick } = {}) {
  container.innerHTML = "";
  container.classList.add("heatmap");

  const head = document.createElement("div");
  head.className = "hm-head";
  head.innerHTML = `
    <div class="hm-title">${data.label}</div>
    <div class="hm-streaks">
      <span title="Current streak">▲ ${data.current_streak}d</span>
      <span class="hm-dim" title="Longest streak">max ${data.longest_streak}d</span>
    </div>`;
  container.appendChild(head);

  const cells = data.cells;
  if (!cells.length) {
    const empty = document.createElement("div");
    empty.className = "hm-empty";
    empty.textContent = "no data";
    container.appendChild(empty);
    return;
  }

  // Group into weeks (columns). Pad the first week so weekday aligns (Sun top).
  const first = new Date(cells[0].day + "T00:00:00");
  const lead = first.getDay();
  const padded = Array(lead).fill(null).concat(cells);
  const weeks = [];
  for (let i = 0; i < padded.length; i += 7) weeks.push(padded.slice(i, i + 7));

  // Cells per column scale via CSS grid `repeat(N, 1fr)` keyed off this var.
  container.style.setProperty("--hm-weeks", weeks.length);

  const grid = document.createElement("div");
  grid.className = "hm-grid";

  // Month-label row (aligned to the body columns, offset past the dow gutter).
  const monthRow = document.createElement("div");
  monthRow.className = "hm-months";
  let lastMonth = -1;
  weeks.forEach((week) => {
    const span = document.createElement("span");
    const firstReal = week.find((c) => c);
    if (firstReal) {
      const m = new Date(firstReal.day + "T00:00:00").getMonth();
      if (m !== lastMonth) { span.textContent = MONTHS[m]; lastMonth = m; }
    }
    monthRow.appendChild(span);
  });
  grid.appendChild(monthRow);

  // Lane: weekday gutter + the responsive body.
  const lane = document.createElement("div");
  lane.className = "hm-lane";

  const dows = document.createElement("div");
  dows.className = "hm-dows";
  for (let i = 0; i < 7; i++) {
    const s = document.createElement("span");
    if (i === 1 || i === 3 || i === 5) s.textContent = DOW[i];
    dows.appendChild(s);
  }
  lane.appendChild(dows);

  const body = document.createElement("div");
  body.className = "hm-body";
  weeks.forEach((week) => {
    const col = document.createElement("div");
    col.className = "hm-col";
    for (let d = 0; d < 7; d++) {
      const c = week[d];
      const cell = document.createElement("div");
      cell.className = "hm-cell";
      if (!c) { cell.classList.add("hm-pad"); col.appendChild(cell); continue; }
      cell.style.backgroundColor = cellColor(data.color, c.value, data.scale_max, data.binary);
      cell.addEventListener("mousemove", (e) => {
        const t = tooltip();
        t.innerHTML = `<strong>${fmt(c.value)}${data.unit || ""}</strong> · ${c.day}`;
        t.style.opacity = "1";
        t.style.left = e.pageX + 12 + "px";
        t.style.top = e.pageY + 12 + "px";
      });
      cell.addEventListener("mouseleave", () => { tooltip().style.opacity = "0"; });
      if (onCellClick) {
        cell.setAttribute("tabindex", "0");
        cell.addEventListener("click", () => onCellClick(c.day, c.value));
        cell.addEventListener("keydown", (e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onCellClick(c.day, c.value);
          }
        });
        cell.style.cursor = "pointer";
      }
      col.appendChild(cell);
    }
    body.appendChild(col);
  });
  lane.appendChild(body);
  grid.appendChild(lane);
  container.appendChild(grid);
}
