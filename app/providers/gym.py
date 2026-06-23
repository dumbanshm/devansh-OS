"""GymProvider — manual workout tracking. Command: ``g``."""
from __future__ import annotations

from ..models import CardSpec, MetricSpec, Rule
from .base import register
from .manual import ManualProvider


@register
class GymProvider(ManualProvider):
    key = "gym"
    display_name = "Gym"
    trigger = "g"
    takes_value = False
    default_value = 1.0
    event_type = "workout"
    metrics = [MetricSpec(key="workout", label="Workout", color="violet", unit="")]
    cards = [CardSpec(metric="workout", title="Gym",
                      show=["last_active", "week_sum", "month_sum"])]
    neglect_rules = [
        Rule(metric="workout", kind="days_since", label="Gym", warn=3, crit=6)
    ]

    def enabled(self) -> bool:
        # No data source yet — manual entry is disabled by design. Re-enable
        # once a fitness tracker / Apple Health integration is wired in (Phase 2).
        return False

    def event_title(self, value: float) -> str:
        return "Completed a workout"
