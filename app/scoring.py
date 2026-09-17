"""Week-value scoring — a dormant seam for the life calendar.

Judging a "wasted week" honestly needs more than one signal: workouts, activity,
commits, rituals, and whatever future productivity markers exist years from now.
That engine is a moving goalpost, so it is deliberately NOT built yet. This
module defines the contract and returns a neutral "lived" score for every week
until contributors are registered.

The design keeps the API shape + frontend grid fixed so lighting up the engine
later touches only this file (plus a weights blob in ``app_settings``):

    1. Register ``SignalContributor``s (name, weight, fn over a week's metrics).
    2. ``score_week`` normalises each to 0..1, takes the weighted mean, and maps
       the composite to a colour band.

Contributors read the week's rows from ``metric_daily`` (commits, workouts,
protein, rituals already flow in there via the providers), so no new ingestion
is needed — a new provider's metrics become scoreable automatically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .db import get_setting, query

# A contributor turns one week's metric rows into a normalised 0..1 signal.
# rows are dicts with (provider, metric, day, value).
SignalFn = Callable[[list], float]


@dataclass
class SignalContributor:
    name: str
    weight: float
    fn: SignalFn


@dataclass
class WeekScore:
    """score is None while the engine is dormant → frontend renders neutral.
    band is a coarse colour bucket; breakdown holds per-signal detail (later)."""
    score: float | None = None
    band: str = "lived"
    breakdown: dict = field(default_factory=dict)


# Registry starts empty. Appending contributors here (and their weights) is the
# only change needed to activate scoring later.
_CONTRIBUTORS: list[SignalContributor] = []


def register(contributor: SignalContributor) -> None:
    _CONTRIBUTORS.append(contributor)


def is_active() -> bool:
    return bool(_CONTRIBUTORS)


def _week_rows(week_start_iso: str, week_end_iso: str) -> list:
    """All metric_daily rows in the inclusive week range [start, end]."""
    return query(
        "SELECT provider, metric, day, value FROM metric_daily WHERE day BETWEEN %s AND %s",
        (week_start_iso, week_end_iso),
    )


def _band_for(score: float) -> str:
    """Additive, green-only mapping (no red). A week earns a mark only when it
    clears the configurable quality bar; anything below reads as a plain lived
    week — identical to an untracked one, so a miss carries no visual penalty.

        below threshold        → "lived" (neutral)
        >= threshold           → "good"  (green)
        >= threshold + halfway  → "great" (brighter green)
    """
    threshold = float(get_setting("week_good_threshold", 0.35) or 0.35)
    if score >= threshold + (1.0 - threshold) / 2.0:
        return "great"
    if score >= threshold:
        return "good"
    return "lived"


def score_week(week_start_iso: str, week_end_iso: str) -> WeekScore:
    """Composite value of a lived week. Neutral ("lived") until the engine ships."""
    if not _CONTRIBUTORS:
        return WeekScore(score=None, band="lived", breakdown={})

    rows = _week_rows(week_start_iso, week_end_iso)
    total_weight = sum(c.weight for c in _CONTRIBUTORS) or 1.0
    breakdown: dict = {}
    acc = 0.0
    for c in _CONTRIBUTORS:
        v = max(0.0, min(1.0, c.fn(rows)))
        breakdown[c.name] = v
        acc += v * c.weight
    composite = acc / total_weight
    return WeekScore(score=composite, band=_band_for(composite), breakdown=breakdown)
