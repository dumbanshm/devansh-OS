"""Neglect-detection engine — the most prominent feature.

Evaluates every provider's declared rules against the data and returns warnings
sorted worst-first. Rules are owned by providers (in their files), so this engine
stays generic: it just iterates the registry.
"""
from __future__ import annotations

from datetime import datetime

from . import aggregates as agg
from .config import get_settings
from .models import Rule, Severity
from .providers.base import registry

_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(round(v, 1))


def _local_hour() -> int:
    """Current local hour (0–23). Factored out so tests can monkeypatch it."""
    return datetime.now(get_settings().tz).hour


def _eval_days_since(provider_key: str, label: str, rule: Rule) -> dict | None:
    n = agg.days_since(provider_key, rule.metric)
    if n is None:
        # Never recorded — flag once at info level so it surfaces.
        return {
            "provider": provider_key,
            "label": label,
            "severity": "info",
            "message": f"{label}: no activity recorded yet",
            "value": None,
        }
    if n == 0:
        return None
    severity: Severity | None = None
    if rule.crit is not None and n >= rule.crit:
        severity = "critical"
    elif rule.warn is not None and n >= rule.warn:
        severity = "warning"
    if severity is None:
        return None
    # Due-day grace: on the exact day a ritual comes due (n == warn), hold the
    # warning until the grace hour — the whole day is still available to do it.
    # Overdue (n > warn) and critical bands are unaffected and fire at any hour.
    if (
        rule.grace_hour is not None
        and severity == "warning"
        and rule.warn is not None
        and n == int(rule.warn)
        and _local_hour() < rule.grace_hour
    ):
        return None
    ago = "yesterday" if n == 1 else f"{n} days ago"
    return {
        "provider": provider_key,
        "label": label,
        "severity": severity,
        "message": f"{label}: last activity {ago}",
        "value": n,
    }


def _eval_rolling_avg(provider_key: str, label: str, rule: Rule) -> dict | None:
    avg = agg.rolling_avg(provider_key, rule.metric, rule.window or 7)
    if rule.threshold is None or avg >= rule.threshold:
        return None
    return {
        "provider": provider_key,
        "label": label,
        "severity": rule.severity,
        "message": (
            f"{label}: {rule.window}-day average {_fmt(avg)}{rule.unit} "
            f"(below {_fmt(rule.threshold)}{rule.unit})"
        ),
        "value": avg,
    }


def evaluate() -> list[dict]:
    warnings: list[dict] = []
    for provider in registry.enabled():
        for rule in provider.neglect_rules:
            if rule.kind == "days_since":
                w = _eval_days_since(provider.key, rule.label, rule)
            elif rule.kind == "rolling_avg_below":
                w = _eval_rolling_avg(provider.key, rule.label, rule)
            else:
                w = None
            if w:
                warnings.append(w)
    warnings.sort(key=lambda w: (_SEVERITY_ORDER.get(w["severity"], 9),
                                 -(w["value"] or 0) if isinstance(w["value"], (int, float)) else 0))
    return warnings
