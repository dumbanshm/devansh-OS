"""Shared base for keyboard-entry providers (gym, sleep, deep work).

These never poll an API; data arrives through the command palette
(``POST /api/entry``). A manual provider declares a single-letter ``trigger``
and whether it takes a numeric value, so the parser can route ``g`` / ``s 7.5``
/ ``d 3`` to the right provider with no per-command wiring.
"""
from __future__ import annotations

import json
from datetime import datetime

from ..config import get_settings
from ..db import insert_events, query, upsert_metric
from ..models import PanelRow, PanelSection, ProviderDetail
from .base import DataProvider


class ManualProvider(DataProvider):
    manual = True

    # Command-palette routing
    trigger: str = ""           # 'g' | 's' | 'd'
    takes_value: bool = False   # True for sleep/deep-work hours
    default_value: float = 1.0  # value when no number is supplied (e.g. gym)
    event_type: str = "manual"

    def event_title(self, value: float) -> str:
        return f"{self.display_name}: {value}"

    def apply_entry(self, value: float | None, day: str) -> dict:
        """Record a manual metric + a timeline event for the given day."""
        metric = self.primary_metric
        val = float(value) if value is not None else self.default_value
        upsert_metric(self.key, metric, day, val, source="manual")
        ts = datetime.now(get_settings().tz).isoformat(timespec="seconds")
        insert_events([
            {
                "provider": self.key,
                "type": self.event_type,
                "ts": ts,
                "day": day,
                "title": self.event_title(val),
                "detail": None,
                "payload": {"value": val, "manual": True},
            }
        ])
        return {"provider": self.key, "metric": metric, "day": day, "value": val}

    async def fetch_detail(self, day: str | None = None) -> ProviderDetail:
        spec = self.metrics[0]
        if day:
            rows = query(
                "SELECT day, value FROM metric_daily WHERE provider=? AND metric=? "
                "AND day=?",
                (self.key, spec.key, day),
            )
            title = f"{self.display_name} — {day}"
        else:
            rows = query(
                "SELECT day, value FROM metric_daily WHERE provider=? AND metric=? "
                "ORDER BY day DESC LIMIT 30",
                (self.key, spec.key),
            )
            title = f"{self.display_name} — last 30 entries"
        entries = [
            PanelRow(r["day"], f"{self._fmt(r['value'])}{(' ' + spec.unit) if spec.unit else ''}")
            for r in rows
        ]
        return ProviderDetail(
            title=title,
            sections=[PanelSection("Entries", entries or [PanelRow("—", "no data")])],
        )

    @staticmethod
    def _fmt(v: float) -> str:
        return str(int(v)) if float(v).is_integer() else str(v)
