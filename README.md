# Devansh OS

A self-hosted **personal observability platform** — a single, dense, always-on
dark dashboard for your own life. Inspired by Grafana, GitHub contribution
graphs, Datadog and fitness trackers. It answers two questions:

> **What have I actually been doing recently?**
> **What important things have I NOT been doing recently?**

Not a productivity app. No streaks-as-rewards, no badges, no quotes, no social.
Metrics are framed as **systems** (recency / trend), not **scores** (ego totals):
the dashboard leads with *"last solved: 2 days ago"*, not *"427 solved"*.

```
┌ Devansh OS · Tue Jun 24 · 14:22:07 ─────────────── today: 1 workout · 4 commits ┐
│ NEGLECT DETECTION          ✕ 1 critical   ! 2 warning                            │
│  ✕ Gym: last activity 6 days ago                                                 │
│  ! LeetCode: last activity 3 days ago                                            │
│  ! Sleep: 7-day average 5.4h (below 6h)                                          │
├ SYSTEMS ─────────────────────────────────────────────────────────────────────── │
│  [GitHub] last: today   [LeetCode] last: 3d ago   [Gym] last: 6d ago   …         │
├ ACTIVITY (heatmaps) ───────────────────────────────────────────────────────────  │
│  Commits ▓▓░▒▓ …   Solved ░▒░░ …   Workout ▒░░ …   Sleep ▓▓▒ …   Deep Work ▒▓ …  │
├ TIMELINE ──────────────────────────────────────────────────────────────────────  │
│  Today    19:02 GitHub  Pushed 3 commits to chemvecto · branch main              │
└──────────────────────────────────────────────────────────────────────────────── ┘
```

## Architecture

A FastAPI backend with a **plug-and-play provider architecture**. Every data
source is a self-contained provider that declares its metrics, KPI cards, neglect
rules and drill-down panel, and implements the async fetch contract. The generic
core (routes, scheduler, heatmaps, cards, neglect, detail) renders everything from
those declarations.

> **Adding a new data source = drop one file in `app/providers/` + import it.**
> Zero changes to the schema, routes or frontend.

The browser never calls external APIs. A background scheduler polls providers and
caches normalized data in SQLite; the dashboard reads only from SQLite, so it's
instant and resilient to rate limits or being offline. Manual entries write
straight to SQLite.

```
Browser ──fetch──▶ FastAPI (/api) ──reads──▶ SQLite ◀──writes── Providers (poll/manual)
```

| Provider   | Source                         | Metric            | Phase |
|------------|--------------------------------|-------------------|-------|
| GitHub     | GraphQL contributions (private)| commits/day       | 1     |
| LeetCode   | unofficial GraphQL calendar    | problems solved   | 1     |
| Gym        | manual (`g`)                   | workout           | 1     |
| Sleep      | manual (`s 7.5`)               | hours slept       | 1     |
| Deep Work  | manual (`d 3`)                 | focused hours     | 1     |
| ChemVecto  | stub                           | deployments …     | 2     |
| Claude     | stub                           | hours / tokens …  | 2     |

## Quick start (local)

```bash
# 1. Configure (all fields optional — providers without creds stay idle)
cp .env.example .env
#    set GITHUB_TOKEN + GITHUB_USERNAME, LEETCODE_USERNAME, TIMEZONE

# 2. Python deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Build the stylesheet (offline, no runtime JS deps)
bash scripts/build_css.sh        # uses Tailwind standalone or npx

# 4. Run
python -m app.main               # → http://127.0.0.1:8000
```

Open `http://127.0.0.1:8000` and leave it on your second monitor.

## Docker

```bash
cp .env.example .env             # fill in values
docker compose up --build        # → http://127.0.0.1:8000
```

SQLite is stored in `./data` (mounted volume), so your data survives rebuilds.

## Native macOS app (no terminal)

Package the whole thing as a double-click `.app` — a menu-bar agent that runs
the server in the background and opens a native window. Pure Python (pywebview +
rumps + PyInstaller); ~25 MB, no Electron.

```bash
source .venv/bin/activate
bash scripts/build_app.sh        # → dist/Devansh OS.app
```

Drag `dist/Devansh OS.app` to `/Applications` and launch from Spotlight. It lives
in the menu bar (◐) with **Open Dashboard**, **Open in Browser**, **Launch at
Login**, and **Quit**. A native window opens on launch.

- Config + database live in `~/Library/Application Support/DevanshOS/` (the bundle
  is read-only). The build script seeds these from your project `.env` + `data/`.
- The app serves on `127.0.0.1:8770` (separate from the Docker instance's 8000).
- The Claude provider reads `~/.claude/projects` directly — works since it's the
  same machine.

## Manual entry (keyboard-driven)

Press **`i`** (or `⌘/Ctrl-K`) anywhere to focus the command bar. Sub-3-second loop:

| Type           | Effect                          |
|----------------|---------------------------------|
| `g`            | gym workout completed today     |
| `s 7.5`        | 7.5h sleep today                |
| `d 3`          | 3h deep work today              |
| `s 7 -1`       | 7h sleep, **yesterday**         |
| `g yesterday`  | back-date a workout one day     |

## GitHub token

For **private** contributions to count, use a token with read access to your
repos (classic `repo` scope, or a fine-grained token with the relevant repos).
The GraphQL `contributionsCollection` returns the daily contribution calendar
directly — the same graph you see on your profile.

> **LeetCode** has no official API; this uses the community `leetcode.com/graphql`
> endpoint and may break if it changes. Failures are isolated to the LeetCode
> card — the rest of the board is unaffected.

## Adding a provider

Create `app/providers/<name>.py`:

```python
from ..models import CardSpec, MetricSpec, Rule
from .base import DataProvider, register

@register
class MyProvider(DataProvider):
    key = "myservice"
    display_name = "My Service"
    metrics = [MetricSpec(key="thing", label="Things", color="teal")]
    cards = [CardSpec(metric="thing", title="My Service")]
    neglect_rules = [Rule(metric="thing", kind="days_since",
                          label="My Service", warn=3, crit=7)]

    def enabled(self): return True
    async def fetch_metrics(self): ...   # return [Metric(...)]
    async def fetch_events(self): ...    # return [Event(...)]
    async def fetch_detail(self, day=None): ...  # rich drill-down
```

Add `myservice` to the import line in `app/providers/__init__.py`. It now appears
as a heatmap, a card, a neglect rule and a clickable drill-down — automatically.

## Project layout

```
app/            FastAPI backend
  providers/    one file per data source (plug-and-play)
  api/          generic routes (summary, heatmap, cards, neglect, timeline, detail, entry)
  aggregates.py streaks / rollups / recency
  neglect.py    rule-based neglect engine
web/            dashboard: index.html, src/input.css (Tailwind), static/js/*
migrations/     SQLite schema
```
