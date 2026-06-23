"""/api/timeline — chronological activity feed grouped by day."""
from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter

from .. import aggregates as agg
from ..db import query
from ..providers.base import registry

router = APIRouter()


def _relative_day(day: str) -> str:
    delta = (agg.today() - date.fromisoformat(day)).days
    if delta == 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    return date.fromisoformat(day).strftime("%A, %b %d")


@router.get("/timeline")
def timeline(days: int = 7):
    start = (agg.today().toordinal() - (days - 1))
    start_day = date.fromordinal(start).strftime("%Y-%m-%d")
    rows = query(
        "SELECT provider, type, ts, day, title, detail, payload FROM events "
        "WHERE day >= ? ORDER BY ts DESC LIMIT 500",
        (start_day,),
    )
    names = {p.key: p.display_name for p in registry.all()}
    colors = {p.key: (p.metrics[0].color if p.metrics else "slate")
              for p in registry.all()}

    groups: dict[str, list] = {}
    for r in rows:
        groups.setdefault(r["day"], []).append({
            "provider": r["provider"],
            "provider_name": names.get(r["provider"], r["provider"]),
            "color": colors.get(r["provider"], "slate"),
            "type": r["type"],
            "ts": r["ts"],
            "title": r["title"],
            "detail": r["detail"],
            "payload": json.loads(r["payload"]) if r["payload"] else None,
        })

    out = [
        {"day": day, "label": _relative_day(day), "items": groups[day]}
        for day in sorted(groups.keys(), reverse=True)
    ]
    return {"groups": out}
