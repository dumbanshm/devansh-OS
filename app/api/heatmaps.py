"""/api/heatmap — contribution-graph data + streak stats for one metric."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException

from .. import aggregates as agg
from ..models import MetricSpec
from ..providers.base import registry

router = APIRouter()


def _spec(provider, metric: str) -> MetricSpec | None:
    return next((m for m in provider.metrics if m.key == metric), None)


@router.get("/heatmap/{provider_key}/{metric}")
def heatmap(provider_key: str, metric: str, range: str = "year"):
    provider = registry.get(provider_key)
    if not provider:
        raise HTTPException(404, "unknown provider")
    spec = _spec(provider, metric)
    if not spec:
        raise HTTPException(404, "unknown metric")

    days = 365 if range == "year" else 31
    end = agg.today()
    start = end - timedelta(days=days - 1)
    series = agg.window_series(provider_key, metric, days)

    cells = []
    cursor = start
    while cursor <= end:
        key = cursor.strftime("%Y-%m-%d")
        cells.append({"day": key, "value": series.get(key, 0.0)})
        cursor += timedelta(days=1)

    return {
        "provider": provider_key,
        "metric": metric,
        "label": spec.label,
        "color": spec.color,
        "unit": spec.unit,
        "scale_max": spec.scale_max,
        "range": range,
        "cells": cells,
        "current_streak": agg.current_streak(provider_key, metric),
        "longest_streak": agg.longest_streak(provider_key, metric),
        "last_active": agg.last_active_day(provider_key, metric),
    }


@router.get("/heatmaps")
def heatmap_index():
    """List every heatmap-eligible metric across enabled providers."""
    out = []
    for p in registry.enabled():
        for m in p.metrics:
            if m.heatmap:
                out.append({"provider": p.key, "metric": m.key,
                            "label": f"{p.display_name} · {m.label}",
                            "color": m.color})
    return {"heatmaps": out}
