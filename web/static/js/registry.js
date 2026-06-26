// Command Palette Registry
// Decouples search logic and data from the UI.

// A Provider registers itself by providing a name and a function that returns its current SearchItems.
// SearchItem schema:
// {
//   id: string,
//   title: string,
//   category: "Navigation" | "Records" | "Actions",
//   keywords: string[], // optional extra search terms
//   action: function, // what to do when selected
//   provider: string // injected automatically by registry
// }

const providers = new Map();

// Load recents from localStorage
let recents = [];
try {
  recents = JSON.parse(localStorage.getItem("cmd_recents") || "[]");
} catch (e) {
  recents = [];
}

function saveRecents() {
  localStorage.setItem("cmd_recents", JSON.stringify(recents.slice(0, 10)));
}

export function registerProvider(name, getItemsFn) {
  providers.set(name, getItemsFn);
}

export function recordAction(item) {
  // Add to recents (by id to avoid serializing functions)
  // We only store the ID and title, since functions can't be serialized.
  const storedItem = { id: item.id, title: item.title, category: item.category, provider: item.provider };
  recents = recents.filter((r) => r.id !== item.id);
  recents.unshift(storedItem);
  saveRecents();
}

function scoreItem(item, query) {
  const q = query.toLowerCase();
  const title = item.title.toLowerCase();
  
  // Exact match
  if (title === q) return 100;
  // Prefix match
  if (title.startsWith(q)) return 80;
  // Substring match
  if (title.includes(q)) return 50;
  
  // Keyword match
  if (item.keywords) {
    for (const kw of item.keywords) {
      if (kw.toLowerCase().includes(q)) return 30;
    }
  }
  
  return 0;
}

export function search(query) {
  const q = (query || "").trim();
  let allItems = [];
  
  // Gather items from all providers
  for (const [providerName, getItemsFn] of providers.entries()) {
    try {
      const items = getItemsFn().map(it => ({ ...it, provider: providerName }));
      allItems.push(...items);
    } catch (e) {
      console.error(`Error getting items from provider ${providerName}:`, e);
    }
  }

  // If query is empty, return recents by hydrating them from allItems
  if (!q) {
    const hydratedRecents = recents.map(r => {
      return allItems.find(it => it.id === r.id) || null;
    }).filter(Boolean);
    
    return [
      {
        category: "Recent",
        items: hydratedRecents
      }
    ].filter(g => g.items.length > 0);
  }

  // Score and filter
  const results = allItems
    .map(item => ({ item, score: scoreItem(item, q) }))
    .filter(res => res.score > 0)
    .sort((a, b) => b.score - a.score)
    .map(res => res.item);

  // Group by category
  const groups = {
    Navigation: [],
    Records: [],
    Actions: []
  };

  results.forEach(item => {
    if (groups[item.category]) {
      groups[item.category].push(item);
    } else {
      // Fallback if provider gave weird category
      groups["Actions"].push(item);
    }
  });

  return Object.entries(groups)
    .filter(([_, items]) => items.length > 0)
    .map(([category, items]) => ({ category, items }));
}
