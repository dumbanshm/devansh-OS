"""/api/cards — modular KPI cards, recency-first (systems, not scores)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from .. import aggregates as agg
from ..config import get_settings
from ..db import all_sync_state, get_setting, protein_day_total
from ..providers.base import registry

router = APIRouter()


def _protein_pace() -> dict:
    """Goal-vs-eating-window pace for the protein card. Expected grams ramp
    across the configured eating window (default 08:00–22:00), so we aren't
    flagged 'behind' before we've had a chance to eat."""
    target = float(get_setting("protein_target_g", 130) or 130)
    ws = float(get_setting("protein_window_start", 8) or 8)
    we = float(get_setting("protein_window_end", 22) or 22)
    now = datetime.now(get_settings().tz)
    today = now.strftime("%Y-%m-%d")
    today_g = protein_day_total(today)

    span = max(we - ws, 0.1)
    frac = (now.hour + now.minute / 60 - ws) / span
    frac = min(1.0, max(0.0, frac))
    expected = target * frac
    delta = today_g - expected

    if delta >= 10:
        state, text = "ahead", f"{round(delta)}g ahead"
    elif delta <= -10:
        state, text = "behind", f"{round(-delta)}g behind pace"
    else:
        state, text = "ontrack", "on track"
    if today_g >= target:
        state, text = "ahead", "target hit"

    return {
        "today_g": round(today_g, 1),
        "target_g": round(target, 1),
        "expected_g": round(expected),
        "delta": round(delta),
        "state": state,
        "text": text,
    }

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
            entry = {
                "provider": provider.key,
                "title": card.title,
                "color": spec.color if spec else "slate",
                "enabled": provider.enabled(),
                "recency": _recency(provider.key, metric),
                "stats": stats,
                "current_streak": agg.current_streak(provider.key, metric),
                "sync_status": state["status"] if state else "never",
                "sync_message": state["message"] if state else "",
            }
            # Protein leads with pace (goal vs eating-window), not recency.
            if provider.key == "protein":
                entry["pace"] = _protein_pace()
            out.append(entry)
    return {"cards": out}


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(round(v, 2))
