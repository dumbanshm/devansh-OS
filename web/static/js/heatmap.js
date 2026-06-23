// Reusable GitHub-style contribution heatmap (custom, no chart lib).
// Renders a 7-row week grid, hover tooltips, month labels and a streak footer.

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

  // Header: title + streaks.
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

  // Group cells into weeks (columns). Pad the first week so weekday aligns.
  const first = new Date(cells[0].day + "T00:00:00");
  const lead = first.getDay(); // 0=Sun
  const padded = Array(lead).fill(null).concat(cells);

  const weeks = [];
  for (let i = 0; i < padded.length; i += 7) weeks.push(padded.slice(i, i + 7));

  const grid = document.createElement("div");
  grid.className = "hm-grid";

  // Month label row.
  const monthRow = document.createElement("div");
  monthRow.className = "hm-months";
  let lastMonth = -1;
  weeks.forEach((week) => {
    const label = document.createElement("span");
    const firstReal = week.find((c) => c);
    if (firstReal) {
      const m = new Date(firstReal.day + "T00:00:00").getMonth();
      if (m !== lastMonth) { label.textContent = MONTHS[m]; lastMonth = m; }
    }
    monthRow.appendChild(label);
  });

  // Columns of day cells.
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
      cell.style.backgroundColor = cellColor(data.color, c.value, data.scale_max);
      cell.dataset.day = c.day;
      cell.addEventListener("mousemove", (e) => {
        const t = tooltip();
        const unit = data.unit || "";
        t.innerHTML = `<strong>${fmt(c.value)}${unit}</strong> · ${c.day}`;
        t.style.opacity = "1";
        t.style.left = e.pageX + 12 + "px";
        t.style.top = e.pageY + 12 + "px";
      });
      cell.addEventListener("mouseleave", () => { tooltip().style.opacity = "0"; });
      if (onCellClick) {
        cell.addEventListener("click", () => onCellClick(c.day, c.value));
        cell.style.cursor = "pointer";
      }
      col.appendChild(cell);
    }
    body.appendChild(col);
  });

  grid.appendChild(monthRow);

  // Weekday gutter + body side by side.
  const lane = document.createElement("div");
  lane.className = "hm-lane";
  const dows = document.createElement("div");
  dows.className = "hm-dows";
  [1, 3, 5].forEach((i) => {
    const s = document.createElement("span");
    s.textContent = DOW[i];
    s.style.gridRow = i + 1;
    dows.appendChild(s);
  });
  lane.appendChild(dows);
  lane.appendChild(body);
  grid.appendChild(lane);

  container.appendChild(grid);
}
