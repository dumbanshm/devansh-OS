"""Shared dataclasses + provider declaration specs.

These types are the contract between providers and the generic core. A provider
declares *what* it tracks (metrics, cards, neglect rules, a detail panel) and
returns *data* (Metric / Event / HeatmapCell / ProviderDetail); the core renders
everything without knowing anything provider-specific.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["info", "warning", "critical"]
HeatmapRange = Literal["year", "month"]


# ── Declarations (static, live inside each provider) ────────────────────────

@dataclass
class MetricSpec:
    """A trackable daily metric and how to draw it as a heatmap."""
    key: str                       # 'commits'
    label: str                     # 'Commits'
    color: str                     # palette key, e.g. 'green'
    unit: str = ""                 # 'h', 'commits', ''
    aggregation: str = "sum"       # 'sum' | 'avg' | 'max' — how to roll up a day
    heatmap: bool = True           # show as a heatmap section
    # For sleep-style ramps the intensity maps a value range, not a count.
    scale_max: float | None = None # if set, heatmap colors scale 0..scale_max
    # Binary metrics (e.g. "did I work out?") render dark=0 / full-color=1+,
    # with no intensity spectrum.
    binary: bool = False


@dataclass
class CardSpec:
    """A KPI / recency card. Recency-first by design (systems, not scores)."""
    metric: str                    # which metric this card summarizes
    title: str                     # 'Commits'
    # Which stats to surface; the recency line always leads.
    show: list[str] = field(
        default_factory=lambda: ["last_active", "week_sum", "month_sum"]
    )


@dataclass
class Rule:
    """A neglect-detection rule, owned by the provider that declares it."""
    metric: str
    kind: Literal["days_since", "rolling_avg_below"]
    label: str                     # 'Gym', 'Sleep'
    warn: float | None = None      # days_since: warn threshold (days)
    crit: float | None = None      # days_since: critical threshold (days)
    window: int | None = None      # rolling_avg_below: window in days
    threshold: float | None = None # rolling_avg_below: avg below this triggers
    severity: Severity = "warning" # severity for rolling_avg_below
    unit: str = ""


@dataclass
class PanelRow:
    label: str
    value: Any
    href: str | None = None


@dataclass
class PanelSection:
    heading: str
    rows: list[PanelRow] = field(default_factory=list)


@dataclass
class PanelSpec:
    """Static description of a provider's drill-down panel layout."""
    title: str


# ── Data (returned by fetch_* at runtime) ──────────────────────────────────

@dataclass
class Metric:
    provider: str
    metric: str
    day: str                       # 'YYYY-MM-DD'
    value: float
    source: str = "api"


@dataclass
class Event:
    provider: str
    type: str
    ts: str                        # ISO8601
    day: str                       # 'YYYY-MM-DD'
    title: str
    detail: str | None = None
    payload: dict | None = None


@dataclass
class HeatmapCell:
    day: str
    value: float


@dataclass
class ProviderDetail:
    """Generic drill-down payload; the frontend renders this verbatim."""
    title: str
    sections: list[PanelSection] = field(default_factory=list)
    charts: list[dict] = field(default_factory=list)
