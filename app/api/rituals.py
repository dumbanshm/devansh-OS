"""/api/rituals/* — the rituals bank (CRUD) + per-day binary toggling.

Toggling a ritual recomputes that day's metric_daily cells (each ritual's binary
series + the composite adherence count) so heatmaps, the card and neglect stay in
sync with the log. The log is the source of truth. Bank mutations rebuild the
provider's dynamic metrics + neglect rules via ``refresh_metrics()``.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import aggregates as agg
from ..db import (
    rituals_bank_add,
    rituals_bank_all,
    rituals_bank_delete,
    rituals_bank_get,
    rituals_bank_update,
    rituals_done,
    rituals_log_add,
    rituals_log_remove,
)
from ..providers.base import registry

router = APIRouter()

PROVIDER = "rituals"


def _today() -> str:
    return agg.today().strftime("%Y-%m-%d")


def _refresh_provider() -> None:
    provider = registry.get(PROVIDER)
    if provider and hasattr(provider, "refresh_metrics"):
        provider.refresh_metrics()


def _recompute(day: str) -> None:
    provider = registry.get(PROVIDER)
    if provider and hasattr(provider, "recompute_day"):
        provider.recompute_day(day)


# ── Bank ──────────────────────────────────────────────────────────────────

class RitualItem(BaseModel):
    name: str
    interval_days: int = 1
    dose_label: Optional[str] = None
    active: bool = True


def _bank_row(r) -> dict:
    return {
        "id": r["id"], "name": r["name"], "active": bool(r["active"]),
        "interval_days": r["interval_days"], "dose_label": r["dose_label"],
    }


@router.get("/rituals/bank")
def list_bank():
    return {"items": [_bank_row(r) for r in rituals_bank_all()]}


@router.post("/rituals/bank")
def add_bank(body: RitualItem):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    if body.interval_days < 1:
        raise HTTPException(400, "interval_days must be at least 1")
    try:
        ritual_id = rituals_bank_add(
            name, body.interval_days, _clean(body.dose_label), body.active
        )
    except Exception:
        raise HTTPException(409, f"'{name}' already in the bank")
    _refresh_provider()
    _recompute(_today())
    return _bank_row(rituals_bank_get(ritual_id))


@router.put("/rituals/bank/{ritual_id}")
def update_bank(ritual_id: int, body: RitualItem):
    if not rituals_bank_get(ritual_id):
        raise HTTPException(404, "unknown ritual")
    if body.interval_days < 1:
        raise HTTPException(400, "interval_days must be at least 1")
    rituals_bank_update(
        ritual_id, body.name.strip(), body.interval_days,
        _clean(body.dose_label), body.active,
    )
    _refresh_provider()
    _recompute(_today())
    return _bank_row(rituals_bank_get(ritual_id))


@router.delete("/rituals/bank/{ritual_id}")
def delete_bank(ritual_id: int):
    rituals_bank_delete(ritual_id)
    _refresh_provider()
    _recompute(_today())
    return {"ok": True}


# ── Daily toggle ────────────────────────────────────────────────────────────

class Toggle(BaseModel):
    ritual_id: int
    done: bool
    day: Optional[str] = None


def _day_payload(day: str) -> dict:
    active = rituals_bank_all(active_only=True)
    done = rituals_done(day)
    return {
        "day": day,
        "items": [
            {
                "id": r["id"], "name": r["name"], "dose_label": r["dose_label"],
                "done": r["id"] in done,
            }
            for r in active
        ],
    }


@router.get("/rituals/day")
def get_day(day: Optional[str] = None):
    return _day_payload(day or _today())


@router.post("/rituals/toggle")
def toggle(body: Toggle):
    ritual = rituals_bank_get(body.ritual_id)
    if not ritual:
        raise HTTPException(404, "unknown ritual")
    day = body.day or _today()
    if body.done:
        rituals_log_add(body.ritual_id, ritual["name"], day)
    else:
        rituals_log_remove(body.ritual_id, day)
    _recompute(day)
    return _day_payload(day)


def _clean(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None
