// Neglect banner — the dashboard's headline. Worst severity first, prominent.

const ICON = { critical: "✕", warning: "!", info: "i" };

export function renderNeglect(container, data, { onClick } = {}) {
  container.innerHTML = "";
  container.dataset.worst = data.worst;

  const header = document.createElement("div");
  header.className = "neglect-head";
  const c = data.counts;
  header.innerHTML = `
    <span class="neglect-label">Neglect Detection</span>
    <span class="neglect-counts">
      ${c.critical ? `<span class="nc nc-critical">${c.critical} critical</span>` : ""}
      ${c.warning ? `<span class="nc nc-warning">${c.warning} warning</span>` : ""}
      ${c.info ? `<span class="nc nc-info">${c.info} info</span>` : ""}
      ${data.worst === "ok" ? `<span class="nc nc-ok">all systems active</span>` : ""}
    </span>`;
  container.appendChild(header);

  if (!data.warnings.length) {
    const ok = document.createElement("div");
    ok.className = "neglect-ok";
    ok.textContent = "Nothing neglected — every tracked system has recent activity.";
    container.appendChild(ok);
    return;
  }

  const list = document.createElement("div");
  list.className = "neglect-list";
  data.warnings.forEach((w) => {
    const item = document.createElement("button");
    item.className = `neglect-item sev-${w.severity}`;
    item.innerHTML = `
      <span class="sev-icon">${ICON[w.severity] || "i"}</span>
      <span class="neglect-msg">${w.message}</span>`;
    if (onClick) item.addEventListener("click", () => onClick(w.provider));
    list.appendChild(item);
  });
  container.appendChild(list);
}
