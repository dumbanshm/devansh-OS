"""DataProvider contract + the registry that makes the app plug-and-play.

A provider self-describes its metrics, cards, neglect rules and detail panel, and
implements the async fetch_* contract. The default ``sync()`` persists whatever
the fetches return. The generic core (API routes, scheduler, heatmaps, cards,
neglect, detail) iterates ``registry`` and renders from these declarations, so a
new data source is a single file + one import.
"""
from __future__ import annotations

import logging
from abc import ABC
from datetime import datetime
from typing import ClassVar

from ..config import get_settings
from ..db import insert_events, set_sync_state, upsert_metrics
from ..models import (
    CardSpec,
    Event,
    HeatmapCell,
    Metric,
    MetricSpec,
    PanelSection,
    ProviderDetail,
    Rule,
)

log = logging.getLogger("devansh.providers")


class DataProvider(ABC):
    # ── Identity / declarations (override in subclasses) ───────────────────
    key: ClassVar[str] = ""
    display_name: ClassVar[str] = ""
    metrics: ClassVar[list[MetricSpec]] = []
    cards: ClassVar[list[CardSpec]] = []
    neglect_rules: ClassVar[list[Rule]] = []
    # Manual providers receive data via /api/entry rather than polling.
    manual: ClassVar[bool] = False

    # ── Capability / config ────────────────────────────────────────────────
    def enabled(self) -> bool:
        """Whether the provider has what it needs to run (creds, etc.)."""
        return True

    @property
    def primary_metric(self) -> str:
        return self.metrics[0].key if self.metrics else ""

    # ── Core fetch contract (override the ones you need) ───────────────────
    async def fetch_metrics(self) -> list[Metric]:
        return []

    async def fetch_events(self) -> list[Event]:
        return []

    async def fetch_heatmap_data(self) -> list[HeatmapCell]:
        """Optional: most providers derive heatmaps from metric_daily instead."""
        return []

    # ── Drill-down contract ────────────────────────────────────────────────
    async def fetch_detail(self, day: str | None = None) -> ProviderDetail:
        """Rich, provider-specific drill-down. Override for real detail.

        Default implementation returns an empty panel; providers fill in
        sections/charts (commits & repos, tokens & hours, bedtime, ...).
        """
        return ProviderDetail(title=self.display_name, sections=[])

    # ── Persistence ────────────────────────────────────────────────────────
    async def sync(self) -> None:
        """Fetch everything and persist it; record sync status either way."""
        if not self.enabled():
            set_sync_state(self.key, "disabled", "Not configured", success=False)
            return
        try:
            metrics = await self.fetch_metrics()
            events = await self.fetch_events()
            upsert_metrics(
                (m.provider, m.metric, m.day, m.value, m.source) for m in metrics
            )
            insert_events(
                {
                    "provider": e.provider,
                    "type": e.type,
                    "ts": e.ts,
                    "day": e.day,
                    "title": e.title,
                    "detail": e.detail,
                    "payload": e.payload,
                }
                for e in events
            )
            set_sync_state(
                self.key,
                "ok",
                f"{len(metrics)} metrics, {len(events)} events",
                success=True,
            )
            log.info("synced %s: %d metrics, %d events", self.key, len(metrics), len(events))
        except Exception as exc:  # isolate failures to this one provider
            log.exception("sync failed for %s", self.key)
            set_sync_state(self.key, "error", str(exc)[:300], success=False)

    # ── Helpers ────────────────────────────────────────────────────────────
    def _today(self) -> str:
        return datetime.now(get_settings().tz).strftime("%Y-%m-%d")


class ProviderRegistry:
    """Holds one instance per provider class and exposes lookup helpers."""

    def __init__(self) -> None:
        self._providers: dict[str, DataProvider] = {}

    def register(self, provider: DataProvider) -> None:
        self._providers[provider.key] = provider

    def all(self) -> list[DataProvider]:
        return list(self._providers.values())

    def enabled(self) -> list[DataProvider]:
        return [p for p in self._providers.values() if p.enabled()]

    def get(self, key: str) -> DataProvider | None:
        return self._providers.get(key)


registry = ProviderRegistry()


def register(cls: type[DataProvider]) -> type[DataProvider]:
    """Class decorator: instantiate and add to the global registry."""
    registry.register(cls())
    return cls
