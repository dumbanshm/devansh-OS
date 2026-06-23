"""/api/cards — modular KPI cards, recency-first (systems, not scores)."""
from __future__ import annotations

from fastapi import APIRouter

from .. import aggregates as agg
from ..db import all_sync_state
from ..providers.base import registry

router = APIRouter()

# Maps a CardSpec "show" key to (label, compute) — extend freely.
_STATS = {
    "week_sum": ("This week", lambda p, m: agg.week_sum(p, m)),
    "month_sum": ("This month", lambda p, m: agg.month_sum(p, m)),
    "week_avg": ("7-day avg", lambda p, m: agg.week_avg(p, m)),
    "day_avg": ("Daily avg", lambda p, m: agg.day_avg(p, m)),
}


def _recency(provider_key: str, metric: str) -> dict:
    n = agg.days_since(provider_key, metric)
    if n is None:
        text = "no activity yet"
    elif n == 0:
        text = "today"
    elif n == 1:
        text = "yesterday"
    else:
        text = f"{n} days ago"
    return {"days_since": n, "text": text}


@router.get("/cards")
def cards():
    sync = all_sync_state()
    out = []
    # Only surface providers that actually have a data source wired up — keeps
    # the board to real signal (no "not configured" placeholder clutter).
    for provider in registry.enabled():
        state = sync.get(provider.key)
        for card in provider.cards:
            metric = card.metric
            spec = next((m for m in provider.metrics if m.key == metric), None)
            unit = spec.unit if spec else ""
            stats = []
            for key in card.show:
                if key == "last_active":
                    continue
                if key in _STATS:
                    label, fn = _STATS[key]
                    val = fn(provider.key, metric)
                    stats.append({"label": label,
                                  "value": _fmt(val),
                                  "unit": unit})
            out.append({
                "provider": provider.key,
                "title": card.title,
                "color": spec.color if spec else "slate",
                "enabled": provider.enabled(),
                "recency": _recency(provider.key, metric),
                "stats": stats,
                "current_streak": agg.current_streak(provider.key, metric),
                "sync_status": state["status"] if state else "never",
                "sync_message": state["message"] if state else "",
            })
    return {"cards": out}


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(round(v, 2))
