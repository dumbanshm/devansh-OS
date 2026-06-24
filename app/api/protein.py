"""/api/protein/* + /api/settings/protein — the one manual data source.

Bank CRUD, per-meal logging, and the daily-target / eating-window settings.
Logging recomputes the day's total in ``metric_daily`` so heatmaps, cards and
streaks stay in sync with the log (the log is the source of truth).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import aggregates as agg
from ..db import (
    get_setting,
    protein_bank_add,
    protein_bank_all,
    protein_bank_delete,
    protein_bank_get,
    protein_bank_update,
    protein_day_total,
    protein_entries,
    protein_log_add,
    protein_log_delete,
    set_setting,
    upsert_metric,
)
from ..providers.base import registry

router = APIRouter()

PROVIDER = "protein"
METRIC = "protein_g"


def _today() -> str:
    # Logical protein-day, anchored to the eating window — so meals logged after
    # midnight (within a wrap-around window) stay on the day the session started.
    return agg.protein_day()


def _recompute(day: str) -> float:
    """Sync metric_daily with the log for one day. Returns the new total."""
    total = protein_day_total(day)
    upsert_metric(PROVIDER, METRIC, day, total, source="manual")
    return total


# ── Settings ────────────────────────────────────────────────────────────────

class ProteinSettings(BaseModel):
    target_g: Optional[float] = None
    window_start: Optional[int] = None
    window_end: Optional[int] = None


def _read_settings() -> dict:
    return {
        "target_g": float(get_setting("protein_target_g", 130) or 130),
        "window_start": int(get_setting("protein_window_start", 8) or 8),
        "window_end": int(get_setting("protein_window_end", 22) or 22),
    }


@router.get("/settings/protein")
def get_protein_settings():
    return _read_settings()


@router.put("/settings/protein")
def put_protein_settings(body: ProteinSettings):
    if body.target_g is not None:
        if body.target_g <= 0:
            raise HTTPException(400, "target must be positive")
        set_setting("protein_target_g", body.target_g)
    if body.window_start is not None:
        set_setting("protein_window_start", int(body.window_start))
    if body.window_end is not None:
        set_setting("protein_window_end", int(body.window_end))
    # Keep the heatmap gradient ceiling in sync with the new target.
    provider = registry.get(PROVIDER)
    if provider and hasattr(provider, "refresh_target"):
        provider.refresh_target()
    return _read_settings()


# ── Bank ──────────────────────────────────────────────────────────────────

class BankItem(BaseModel):
    name: str
    protein_g: float
    serving_label: Optional[str] = None


def _bank_row(r) -> dict:
    return {"id": r["id"], "name": r["name"], "protein_g": r["protein_g"],
            "serving_label": r["serving_label"]}


@router.get("/protein/bank")
def list_bank():
    return {"items": [_bank_row(r) for r in protein_bank_all()]}


@router.post("/protein/bank")
def add_bank(body: BankItem):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    if body.protein_g <= 0:
        raise HTTPException(400, "protein_g must be positive")
    try:
        food_id = protein_bank_add(name, body.protein_g, body.serving_label)
    except Exception:
        raise HTTPException(409, f"'{name}' already in the bank")
    return _bank_row(protein_bank_get(food_id))


@router.put("/protein/bank/{food_id}")
def update_bank(food_id: int, body: BankItem):
    if not protein_bank_get(food_id):
        raise HTTPException(404, "unknown food")
    protein_bank_update(food_id, body.name.strip(), body.protein_g, body.serving_label)
    return _bank_row(protein_bank_get(food_id))


@router.delete("/protein/bank/{food_id}")
def delete_bank(food_id: int):
    protein_bank_delete(food_id)
    return {"ok": True}


# ── Log ───────────────────────────────────────────────────────────────────

class LogEntry(BaseModel):
    food_id: Optional[int] = None
    food_name: Optional[str] = None
    grams: Optional[float] = None   # required for free-form (no food_id)
    servings: float = 1
    day: Optional[str] = None
    save_to_bank: bool = False      # free-form: also create a bank entry


def _entry_row(r) -> dict:
    return {"id": r["id"], "food_name": r["food_name"], "servings": r["servings"],
            "grams": r["grams"], "logged_at": r["logged_at"]}


def _day_payload(day: str) -> dict:
    rows = protein_entries(day)
    return {
        "day": day,
        "total_g": round(sum(r["grams"] for r in rows), 1),
        "target_g": _read_settings()["target_g"],
        "entries": [_entry_row(r) for r in rows],
    }


@router.get("/protein/log")
def get_log(day: Optional[str] = None):
    return _day_payload(day or _today())


@router.post("/protein/log")
def add_log(body: LogEntry):
    day = body.day or _today()
    servings = body.servings or 1

    if body.food_id is not None:
        food = protein_bank_get(body.food_id)
        if not food:
            raise HTTPException(404, "unknown food")
        name = food["name"]
        grams = float(food["protein_g"]) * servings
        food_id = body.food_id
    else:
        # Free-form: needs an explicit grams (per serving) value.
        name = (body.food_name or "").strip()
        if not name:
            raise HTTPException(400, "food_name or food_id required")
        if body.grams is None or body.grams <= 0:
            raise HTTPException(400, "grams required for a free-form entry")
        per_serving = float(body.grams)
        grams = per_serving * servings
        food_id = None
        if body.save_to_bank:
            try:
                food_id = protein_bank_add(name, per_serving, None)
            except Exception:
                food_id = None  # already exists — log it anyway

    protein_log_add(day, food_id, name, servings, grams)
    _recompute(day)
    return _day_payload(day)


@router.delete("/protein/log/{entry_id}")
def delete_log(entry_id: int):
    day = protein_log_delete(entry_id)
    if day is None:
        raise HTTPException(404, "unknown entry")
    _recompute(day)
    return _day_payload(day)
