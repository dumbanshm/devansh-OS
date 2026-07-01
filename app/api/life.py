"""/api/life/* + /api/settings/life — the Life-in-Weeks calendar.

The grid is 52 weeks × N years (default 90). A "week" is defined off the birth
date, not the ISO calendar: ``week_index(day) = (day - birth_date).days // 7``.
That keeps milestone→cell mapping and the current-week highlight in exact
agreement and sidesteps year-boundary edge cases.

Milestones are a legitimately-manual source (a person authors them), so — like
protein and rituals — their CRUD router is mounted. Week scoring is delegated to
``app.scoring``, which is dormant: every lived week is neutral until the
multi-signal engine is built, at which point only ``scoring.py`` changes.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import aggregates as agg
from .. import scoring
from ..db import (
    get_setting,
    milestones_add,
    milestones_all,
    milestones_delete,
    milestones_get,
    milestones_update,
    set_setting,
)

router = APIRouter()

WEEKS_PER_YEAR = 52


def _birth_date() -> date | None:
    raw = get_setting("birth_date", None)
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _life_years() -> int:
    return int(get_setting("life_expectancy_years", 90) or 90)


def _week_index(day: date, birth: date) -> int:
    return (day - birth).days // 7


def _week_bounds(index: int, birth: date) -> tuple[str, str]:
    start = birth + timedelta(days=7 * index)
    end = start + timedelta(days=6)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


# ── Settings ──────────────────────────────────────────────────────────────────

class LifeSettings(BaseModel):
    birth_date: Optional[str] = None
    life_expectancy_years: Optional[int] = None


def _read_settings() -> dict:
    b = _birth_date()
    return {
        "birth_date": b.strftime("%Y-%m-%d") if b else None,
        "life_expectancy_years": _life_years(),
    }


@router.get("/settings/life")
def get_life_settings():
    return _read_settings()


@router.put("/settings/life")
def put_life_settings(body: LifeSettings):
    if body.birth_date is not None:
        raw = body.birth_date.strip()
        if raw:
            try:
                datetime.strptime(raw, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(400, "birth_date must be YYYY-MM-DD")
            set_setting("birth_date", raw)
        else:
            set_setting("birth_date", "")
    if body.life_expectancy_years is not None:
        if not (1 <= body.life_expectancy_years <= 130):
            raise HTTPException(400, "life_expectancy_years must be 1–130")
        set_setting("life_expectancy_years", int(body.life_expectancy_years))
    return _read_settings()


# ── Grid ──────────────────────────────────────────────────────────────────────

def _milestone_row(r) -> dict:
    return {
        "id": r["id"], "day": r["day"], "title": r["title"],
        "detail": r["detail"], "emoji": r["emoji"],
    }


@router.get("/life")
def get_life():
    birth = _birth_date()
    years = _life_years()
    total_weeks = years * WEEKS_PER_YEAR

    milestones = [_milestone_row(r) for r in milestones_all()]

    if birth is None:
        return {
            "birth_date": None,
            "life_expectancy_years": years,
            "weeks_per_year": WEEKS_PER_YEAR,
            "total_weeks": total_weeks,
            "current_week_index": None,
            "milestones": milestones,
            "scores": {},
            "scoring_active": scoring.is_active(),
        }

    current = _week_index(agg.today(), birth)

    # Attach a week_index to every milestone so the frontend maps to a cell
    # without re-deriving birth-date math.
    for m in milestones:
        try:
            m_day = datetime.strptime(m["day"], "%Y-%m-%d").date()
            m["week_index"] = _week_index(m_day, birth)
        except ValueError:
            m["week_index"] = None

    # Scores stay empty while the engine is dormant (frontend renders neutral).
    # When active, roll up each lived week from metric_daily.
    scores: dict[int, dict] = {}
    if scoring.is_active():
        for i in range(min(current, total_weeks - 1) + 1):
            start, end = _week_bounds(i, birth)
            ws = scoring.score_week(start, end)
            scores[i] = {"score": ws.score, "band": ws.band}

    return {
        "birth_date": birth.strftime("%Y-%m-%d"),
        "life_expectancy_years": years,
        "weeks_per_year": WEEKS_PER_YEAR,
        "total_weeks": total_weeks,
        "current_week_index": current,
        "milestones": milestones,
        "scores": scores,
        "scoring_active": scoring.is_active(),
    }


# ── Milestones CRUD ─────────────────────────────────────────────────────────

class MilestoneItem(BaseModel):
    day: str
    title: str
    detail: Optional[str] = None
    emoji: Optional[str] = None


def _validate(body: MilestoneItem) -> tuple[str, str, Optional[str], Optional[str]]:
    day = body.day.strip()
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(400, "day must be YYYY-MM-DD")
    title = body.title.strip()
    if not title:
        raise HTTPException(400, "title required")
    return day, title, _clean(body.detail), _clean(body.emoji)


@router.get("/life/milestones")
def list_milestones():
    return {"items": [_milestone_row(r) for r in milestones_all()]}


@router.post("/life/milestones")
def add_milestone(body: MilestoneItem):
    day, title, detail, emoji = _validate(body)
    mid = milestones_add(day, title, detail, emoji)
    return _milestone_row(milestones_get(mid))


@router.put("/life/milestones/{milestone_id}")
def update_milestone(milestone_id: int, body: MilestoneItem):
    if not milestones_get(milestone_id):
        raise HTTPException(404, "unknown milestone")
    day, title, detail, emoji = _validate(body)
    milestones_update(milestone_id, day, title, detail, emoji)
    return _milestone_row(milestones_get(milestone_id))


@router.delete("/life/milestones/{milestone_id}")
def delete_milestone(milestone_id: int):
    milestones_delete(milestone_id)
    return {"ok": True}


def _clean(s: Optional[str]) -> Optional[str]:
    s = (s or "").strip()
    return s or None
