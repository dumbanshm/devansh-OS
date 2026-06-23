"""ChemVectoProvider — Phase 2 stub.

Registry-conformant placeholder for the ChemVecto product metrics
(deployments, active users, revenue, API requests). It declares its cards,
metrics and detail panel now, so the moment the real data source is wired into
``fetch_metrics``/``fetch_events`` the heatmap, cards, neglect and drill-down all
light up with no core changes. Disabled until implemented.
"""
from __future__ import annotations

from ..models import (
    CardSpec,
    MetricSpec,
    PanelRow,
    PanelSection,
    ProviderDetail,
    Rule,
)
from .base import DataProvider, register


@register
class ChemVectoProvider(DataProvider):
    key = "chemvecto"
    display_name = "ChemVecto"
    metrics = [
        MetricSpec(key="deployments", label="Deployments", color="rose", unit=""),
    ]
    cards = [CardSpec(metric="deployments", title="ChemVecto Deploys")]
    neglect_rules = [
        Rule(metric="deployments", kind="days_since", label="ChemVecto deploy",
             warn=7, crit=10)
    ]

    def enabled(self) -> bool:
        return False  # Phase 2: connect the ChemVecto DB/API to enable.

    async def fetch_detail(self, day: str | None = None) -> ProviderDetail:
        return ProviderDetail(
            title="ChemVecto",
            sections=[
                PanelSection(
                    "Not yet connected",
                    [
                        PanelRow("Status", "Phase 2 stub"),
                        PanelRow("Will track", "deployments, active users, revenue, API requests"),
                    ],
                )
            ],
        )
