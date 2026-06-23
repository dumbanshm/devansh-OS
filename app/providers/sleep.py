"""SleepProvider — manual sleep tracking. Command: ``s 7.5``.

Heatmap intensity encodes sleep *duration* (0..10h), not a count.
"""
from __future__ import annotations

from ..models import CardSpec, MetricSpec, Rule
from .base import register
from .manual import ManualProvider


@register
class SleepProvider(ManualProvider):
    key = "sleep"
    display_name = "Sleep"
    trigger = "s"
    takes_value = True
    default_value = 0.0
    event_type = "sleep"
    metrics = [
        MetricSpec(key="hours", label="Sleep", color="blue", unit="h",
                   aggregation="avg", scale_max=10.0)
    ]
    cards = [CardSpec(metric="hours", title="Sleep",
                      show=["last_active", "week_avg"])]
    neglect_rules = [
        Rule(metric="hours", kind="rolling_avg_below", label="Sleep",
             window=7, threshold=6.0, severity="warning", unit="h")
    ]

    def enabled(self) -> bool:
        # No data source yet — manual entry is disabled by design. Re-enable
        # once Apple Health / a sleep tracker is wired in (Phase 2).
        return False

    def event_title(self, value: float) -> str:
        return f"Slept {self._fmt(value)}h"
