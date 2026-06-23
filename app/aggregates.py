"""Pure aggregation helpers over ``metric_daily``.

Shared by cards, heatmaps and the neglect engine so streak/recency/rollup logic
lives in exactly one place.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .config import get_settings
from .db import metric_series


def today() -> date:
    return datetime.now(get_settings().tz).date()


def _iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def series_for_year(provider: str, metric: str) -> dict[str, float]:
    end = today()
    start = end - timedelta(days=370)
    return metric_series(provider, metric, _iso(start), _iso(end))


def window_series(provider: str, metric: str, days: int) -> dict[str, float]:
    end = today()
    start = end - timedelta(days=days - 1)
    return metric_series(provider, metric, _iso(start), _iso(end))


def week_sum(provider: str, metric: str) -> float:
    return round(sum(window_series(provider, metric, 7).values()), 2)


def month_sum(provider: str, metric: str) -> float:
    return round(sum(window_series(provider, metric, 30).values()), 2)


def week_avg(provider: str, metric: str) -> float:
    vals = [v for v in window_series(provider, metric, 7).values() if v > 0]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def day_avg(provider: str, metric: str, days: int = 30) -> float:
    """Average over active days (days with any value) in the window."""
    vals = [v for v in window_series(provider, metric, days).values() if v > 0]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def rolling_avg(provider: str, metric: str, window: int) -> float:
    """Average across *every* day in the window, including zero/missing days."""
    s = window_series(provider, metric, window)
    total = sum(s.values())
    return round(total / window, 2) if window else 0.0


def last_active_day(provider: str, metric: str) -> str | None:
    """The most recent day with a positive value, or None."""
    s = series_for_year(provider, metric)
    active = sorted(d for d, v in s.items() if v > 0)
    return active[-1] if active else None


def days_since(provider: str, metric: str) -> int | None:
    last = last_active_day(provider, metric)
    if last is None:
        return None
    return (today() - date.fromisoformat(last)).days


def _active_days(provider: str, metric: str) -> set[str]:
    return {d for d, v in series_for_year(provider, metric).items() if v > 0}


def current_streak(provider: str, metric: str) -> int:
    """Consecutive active days ending today (or yesterday — today still counts as
    a live streak even before today's entry exists)."""
    active = _active_days(provider, metric)
    if not active:
        return 0
    streak = 0
    cursor = today()
    # Allow the streak to "hold" if today isn't logged yet.
    if _iso(cursor) not in active:
        cursor -= timedelta(days=1)
    while _iso(cursor) in active:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def longest_streak(provider: str, metric: str) -> int:
    active = sorted(_active_days(provider, metric))
    if not active:
        return 0
    best = run = 1
    prev = date.fromisoformat(active[0])
    for d_str in active[1:]:
        d = date.fromisoformat(d_str)
        run = run + 1 if (d - prev).days == 1 else 1
        best = max(best, run)
        prev = d
    return best
