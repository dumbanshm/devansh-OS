"""ProteinProvider — the one legitimately-manual system.

No API can observe what you ate, so protein is logged by hand: pick a food from
the bank (or free-form), and the day's grams accumulate in ``metric_daily`` like
any other metric. The heatmap is a gradient on grams (0g darkest → target
brightest); the card shows *pace* (goal vs eating-window progress) instead of the
usual recency line. Data arrives via the ``/api/protein/*`` routes, not polling.
"""
from __future__ import annotations

from ..db import get_setting, protein_day_total, protein_entries
from ..models import (
    CardSpec,
    MetricSpec,
    PanelRow,
    PanelSection,
    ProviderDetail,
)
from .base import DataProvider, register

DEFAULT_TARGET = 130.0


@register
class ProteinProvider(DataProvider):
    key = "protein"
    display_name = "Protein"
    manual = True  # data comes from /api/protein/*, never the scheduler
    metrics = [
        MetricSpec(
            key="protein_g",
            label="Protein",
            color="orange",
            unit="g",
            scale_max=DEFAULT_TARGET,  # kept in sync with the configured target
        )
    ]
    # Average over logged days, not a recency line — the card surfaces pace.
    cards = [CardSpec(metric="protein_g", title="Protein", show=["week_avg"])]
    neglect_rules = []  # eating protein isn't a streak to defend

    def enabled(self) -> bool:
        return True  # always on; no external creds needed

    # Keep the heatmap gradient ceiling synced with the configured daily target.
    def on_startup(self) -> None:
        self.refresh_target()

    def refresh_target(self) -> float:
        target = float(get_setting("protein_target_g", DEFAULT_TARGET) or DEFAULT_TARGET)
        self.metrics[0].scale_max = target
        return target

    # ── Drill-down ──────────────────────────────────────────────────────────
    async def fetch_detail(self, day: str | None = None) -> ProviderDetail:
        target = self.refresh_target()
        if day:
            return self._day_detail(day, target)
        return self._overview(target)

    def _day_detail(self, day: str, target: float) -> ProviderDetail:
        rows = protein_entries(day)
        total = sum(r["grams"] for r in rows)
        meal_rows = [
            PanelRow(
                _meal_label(r),
                f"{_fmt(r['grams'])}g",
            )
            for r in rows
        ]
        sections = [
            PanelSection(
                "Summary",
                [
                    PanelRow("Total", f"{_fmt(total)}g"),
                    PanelRow("Target", f"{_fmt(target)}g"),
                    PanelRow("Remaining", f"{_fmt(max(target - total, 0))}g"),
                    PanelRow("Meals logged", len(rows)),
                ],
            ),
            PanelSection("Meals", meal_rows or [PanelRow("—", "nothing logged")]),
        ]
        return ProviderDetail(title=f"Protein — {day}", sections=sections)

    def _overview(self, target: float) -> ProviderDetail:
        from .. import aggregates as agg

        series = agg.window_series(self.key, "protein_g", 30)
        active = {d: v for d, v in series.items() if v > 0}
        days = len(active)
        avg = round(sum(active.values()) / days, 1) if days else 0.0
        best_day = max(active, key=active.get) if active else None
        best_val = active[best_day] if best_day else 0.0
        at_target = sum(1 for v in active.values() if v >= target)
        sections = [
            PanelSection(
                "Last 30 days",
                [
                    PanelRow("Daily avg (logged days)", f"{_fmt(avg)}g"),
                    PanelRow("Days logged", days),
                    PanelRow("Days at/over target", at_target),
                    PanelRow(
                        "Best day",
                        f"{_fmt(best_val)}g · {best_day}" if best_day else "—",
                    ),
                    PanelRow("Target", f"{_fmt(target)}g"),
                ],
            )
        ]
        return ProviderDetail(title="Protein — last 30 days", sections=sections)


def _meal_label(row) -> str:
    name = row["food_name"]
    servings = row["servings"]
    if servings and servings != 1:
        return f"{name} ×{_fmt(servings)}"
    return name


def _fmt(v: float) -> str:
    v = float(v)
    return str(int(v)) if v.is_integer() else str(round(v, 1))
