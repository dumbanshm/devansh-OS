"""/api/summary — header payload, plus manual sync triggers."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from .. import aggregates as agg
from ..config import get_settings
from ..db import all_sync_state, metric_series
from ..providers.base import registry

router = APIRouter()


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(round(v, 2))


@router.get("/summary")
def summary():
    today = agg.today().strftime("%Y-%m-%d")
    now = datetime.now(get_settings().tz)
    items = []
    for p in registry.enabled():
        spec = p.metrics[0] if p.metrics else None
        if not spec:
            continue
        series = metric_series(p.key, spec.key, today, today)
        val = series.get(today, 0.0)
        if val > 0:
            unit = spec.unit
            label = spec.label.lower()
            items.append({
                "provider": p.key,
                "color": spec.color,
                "text": f"{_fmt(val)}{unit} {label}" if unit else f"{_fmt(val)} {label}",
            })
    return {
        "date": now.strftime("%A, %B %d, %Y"),
        "iso_date": today,
        "time": now.strftime("%H:%M:%S"),
        "timezone": get_settings().timezone,
        "summary": items,
        "sync": {k: dict(v) for k, v in all_sync_state().items()},
    }


@router.post("/sync/{provider_key}")
async def sync_one(provider_key: str):
    provider = registry.get(provider_key)
    if not provider:
        raise HTTPException(404, "unknown provider")
    await provider.sync()
    return {"ok": True, "provider": provider_key}


@router.post("/sync")
async def sync_all():
    synced = []
    for p in registry.enabled():
        if not p.manual:
            await p.sync()
            synced.append(p.key)
    return {"ok": True, "synced": synced}
