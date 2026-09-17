"""Thin wrappers over the Postgres compute layer (supabase/migrations/*_compute_layer.sql).

The streak/recency/rollup math itself now lives in SQL (fn_days_since,
fn_rolling_avg, fn_current_streak, ...) so any client — FastAPI or the Flutter
app — reads identical, live-computed values without this process running.
These wrappers exist so callers (api/cards.py, api/heatmaps.py, neglect.py,
providers) don't need to change.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .config import get_settings
from .db import metric_series, query_one


def today() -> date:
    row = query_one("SELECT fn_today() AS d")
    return row["d"] if row else datetime.now(get_settings().tz).date()


def _iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def protein_day(now: datetime | None = None) -> str:
    """Logical protein-day (see fn_protein_day() in the compute-layer migration
    for the wrap-around eating-window logic). ``now`` is accepted for call-site
    compatibility but every caller passes the current moment, so this always
    delegates to the DB's live "now" rather than reimplementing the anchoring
    logic twice."""
    row = query_one("SELECT fn_protein_day() AS d")
    return _iso(row["d"]) if row else _iso(today())


def series_for_year(provider: str, metric: str) -> dict[str, float]:
    end = today()
    start = end - timedelta(days=370)
    return metric_series(provider, metric, _iso(start), _iso(end))


def window_series(provider: str, metric: str, days: int) -> dict[str, float]:
    end = today()
    start = end - timedelta(days=days - 1)
    return metric_series(provider, metric, _iso(start), _iso(end))


def week_sum(provider: str, metric: str) -> float:
    row = query_one("SELECT fn_week_sum(%s, %s) AS v", (provider, metric))
    return float(row["v"] or 0) if row else 0.0


def month_sum(provider: str, metric: str) -> float:
    row = query_one("SELECT fn_month_sum(%s, %s) AS v", (provider, metric))
    return float(row["v"] or 0) if row else 0.0


def week_avg(provider: str, metric: str) -> float:
    vals = [v for v in window_series(provider, metric, 7).values() if v > 0]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def day_avg(provider: str, metric: str, days: int = 30) -> float:
    """Average over active days (days with any value) in the window."""
    vals = [v for v in window_series(provider, metric, days).values() if v > 0]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def rolling_avg(provider: str, metric: str, window: int) -> float:
    row = query_one("SELECT fn_rolling_avg(%s, %s, %s) AS v", (provider, metric, window))
    return float(row["v"] or 0) if row else 0.0


def last_active_day(provider: str, metric: str) -> str | None:
    row = query_one("SELECT fn_last_active_day(%s, %s) AS d", (provider, metric))
    return _iso(row["d"]) if row and row["d"] else None


def days_since(provider: str, metric: str) -> int | None:
    row = query_one("SELECT fn_days_since(%s, %s) AS n", (provider, metric))
    return row["n"] if row else None


def current_streak(provider: str, metric: str) -> int:
    row = query_one("SELECT fn_current_streak(%s, %s) AS n", (provider, metric))
    return int(row["n"] or 0) if row else 0


def longest_streak(provider: str, metric: str) -> int:
    row = query_one("SELECT fn_longest_streak(%s, %s) AS n", (provider, metric))
    return int(row["n"] or 0) if row else 0
