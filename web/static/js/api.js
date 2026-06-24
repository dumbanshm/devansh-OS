// Thin fetch wrapper around the /api surface.

async function http(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail || msg; } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}

export const api = {
  summary: () => http("GET", "/api/summary"),
  cards: () => http("GET", "/api/cards"),
  neglect: () => http("GET", "/api/neglect"),
  timeline: (days = 7) => http("GET", `/api/timeline?days=${days}`),
  heatmaps: () => http("GET", "/api/heatmaps"),
  heatmap: (provider, metric, range = "year") =>
    http("GET", `/api/heatmap/${provider}/${metric}?range=${range}`),
  detail: (provider, day) =>
    http("GET", `/api/detail/${provider}${day ? `?day=${day}` : ""}`),
  commands: () => http("GET", "/api/commands"),
  entry: (cmd) => http("POST", "/api/entry", { cmd }),
  syncOne: (provider) => http("POST", `/api/sync/${provider}`),
  syncAll: () => http("POST", "/api/sync"),

  // Protein
  proteinLog: (day) =>
    http("GET", `/api/protein/log${day ? `?day=${day}` : ""}`),
  proteinAdd: (entry) => http("POST", "/api/protein/log", entry),
  proteinDelete: (id) => http("DELETE", `/api/protein/log/${id}`),
  proteinBank: () => http("GET", "/api/protein/bank"),
  proteinBankAdd: (item) => http("POST", "/api/protein/bank", item),
  proteinBankUpdate: (id, item) => http("PUT", `/api/protein/bank/${id}`, item),
  proteinBankDelete: (id) => http("DELETE", `/api/protein/bank/${id}`),
  proteinSettings: () => http("GET", "/api/settings/protein"),
  proteinSettingsSave: (s) => http("PUT", "/api/settings/protein", s),
};
