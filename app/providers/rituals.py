"""RitualsProvider — daily supplements / meds / routines as a recency system.

Like protein, this is a legitimately-manual source (no API can observe whether
you took your magnesium), but reshaped to stay observatory-native:

- Each **active** ritual is its own **binary** metric (``r_<id>``, did-it/didn't),
  surfaced through neglect detection rather than a completion checklist.
- A single composite ``adherence`` metric (value = how many active rituals were
  logged that day) is the one heatmap that appears in the grid; the per-ritual
  series stay off the grid (``heatmap=False``) and are reached via the block's
  dropdown (see ``heatmap_variants`` + the frontend).

The metrics + neglect rules are **dynamic** — rebuilt from the active bank by
``refresh_metrics()`` on startup and after every bank mutation (mirroring
protein's ``refresh_target()``). Only active rituals are ever accounted for.
Data arrives via the ``/api/rituals/*`` routes, not polling.
"""
from __future__ import annotations

from .. import aggregates as agg
from ..db import (
    rituals_bank_all,
    rituals_done,
    upsert_metric,
)
from ..models import (
    CardSpec,
    MetricSpec,
    PanelRow,
    PanelSection,
    ProviderDetail,
    Rule,
)
from .base import DataProvider, register

# One shared ramp for every ritual view + the composite — the dropdown swaps the
# data, never the hue, so the block stays consistent with the others.
COLOR = "cyan"
ADHERENCE = "adherence"


@register
class RitualsProvider(DataProvider):
    key = "rituals"
    display_name = "Rituals"
    manual = True  # data comes from /api/rituals/*, never the scheduler

    # Declarations are rebuilt from the active bank in refresh_metrics().
    metrics = [MetricSpec(key=ADHERENCE, label="All", color=COLOR, scale_max=1)]
    cards = [CardSpec(metric=ADHERENCE, title="Rituals", show=["last_active"])]
    neglect_rules: list[Rule] = []

    def enabled(self) -> bool:
        return True  # always on; no external creds needed

    def on_startup(self) -> None:
        self.refresh_metrics()

    # ── Dynamic declarations ─────────────────────────────────────────────────
    def refresh_metrics(self) -> None:
        """Rebuild metrics + neglect rules from the active bank. Call after any
        bank mutation so the grid block, dropdown and neglect stay in sync."""
        active = rituals_bank_all(active_only=True)

        # Composite "All" view: intensity = active rituals logged that day.
        adherence = MetricSpec(
            key=ADHERENCE, label="All", color=COLOR,
            scale_max=max(len(active), 1), heatmap=True,
        )
        # Per-ritual binary series — off the grid, fetchable behind the dropdown.
        per_ritual = [
            MetricSpec(
                key=f"r_{r['id']}", label=r["name"], color=COLOR,
                binary=True, heatmap=False,
            )
            for r in active
        ]
        self.metrics = [adherence, *per_ritual]

        # Cadence-scaled neglect: a daily ritual warns at 1 day, a weekly at 7.
        self.neglect_rules = [
            Rule(
                metric=f"r_{r['id']}", kind="days_since", label=r["name"],
                warn=float(r["interval_days"]), crit=float(r["interval_days"]) * 2,
            )
            for r in active
        ]

    # ── Dropdown options for the block ───────────────────────────────────────
    def heatmap_variants(self, metric: str | None = None) -> list[dict] | None:
        """Drives the in-block dropdown: All + each active ritual. Returns the
        same option list regardless of which metric is currently shown."""
        active = rituals_bank_all(active_only=True)
        return [{"metric": ADHERENCE, "label": "All"}] + [
            {"metric": f"r_{r['id']}", "label": r["name"]} for r in active
        ]

    # ── Recompute metric_daily from the log for one day ──────────────────────
    def recompute_day(self, day: str) -> None:
        """Sync metric_daily with the log for one day: each active ritual's
        binary cell + the composite adherence count. The log is the source of
        truth."""
        active = rituals_bank_all(active_only=True)
        done = rituals_done(day)
        for r in active:
            upsert_metric(
                self.key, f"r_{r['id']}", day,
                1.0 if r["id"] in done else 0.0, source="manual",
            )
        upsert_metric(self.key, ADHERENCE, day, float(len(done)), source="manual")

    # ── Drill-down ───────────────────────────────────────────────────────────
    async def fetch_detail(self, day: str | None = None) -> ProviderDetail:
        if day:
            return self._day_detail(day)
        return self._overview()

    def _day_detail(self, day: str) -> ProviderDetail:
        active = rituals_bank_all(active_only=True)
        done = rituals_done(day)
        rows = [
            PanelRow(
                _ritual_label(r),
                "✓ done" if r["id"] in done else "— missed",
            )
            for r in active
        ]
        sections = [
            PanelSection(
                "Summary",
                [
                    PanelRow("Done", f"{len(done & {r['id'] for r in active})}"),
                    PanelRow("Active rituals", len(active)),
                ],
            ),
            PanelSection("Rituals", rows or [PanelRow("—", "no active rituals")]),
        ]
        return ProviderDetail(title=f"Rituals — {day}", sections=sections)

    def _overview(self) -> ProviderDetail:
        active = rituals_bank_all(active_only=True)
        rows = []
        for r in active:
            n = agg.days_since(self.key, f"r_{r['id']}")
            if n is None:
                last = "no activity yet"
            elif n == 0:
                last = "today"
            elif n == 1:
                last = "yesterday"
            else:
                last = f"{n} days ago"
            cadence = "daily" if r["interval_days"] == 1 else f"every {r['interval_days']}d"
            rows.append(PanelRow(_ritual_label(r), f"{last} · {cadence}"))
        sections = [
            PanelSection("Last done", rows or [PanelRow("—", "no active rituals")]),
        ]
        return ProviderDetail(title="Rituals — recency", sections=sections)


def _ritual_label(row) -> str:
    return f"{row['name']} ({row['dose_label']})" if row["dose_label"] else row["name"]
