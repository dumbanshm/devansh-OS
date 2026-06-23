"""LeetCodeProvider — DSA activity.

LeetCode has no official API. This uses the community ``leetcode.com/graphql``
endpoint: ``submissionCalendar`` for the daily heatmap and
``recentAcSubmissionList`` for the timeline + drill-down. If the unofficial
endpoint changes, only this provider's card shows an error — the rest of the
board is unaffected.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx

from ..config import get_settings
from ..db import query
from ..models import (
    CardSpec,
    Event,
    HeatmapCell,
    Metric,
    MetricSpec,
    PanelRow,
    PanelSection,
    ProviderDetail,
    Rule,
)
from .base import DataProvider, register

LC_URL = "https://leetcode.com/graphql"

_CALENDAR_QUERY = """
query($username: String!) {
  matchedUser(username: $username) {
    submissionCalendar
  }
}
"""

_RECENT_QUERY = """
query($username: String!) {
  recentAcSubmissionList(username: $username, limit: 30) {
    title titleSlug timestamp
  }
}
"""


@register
class LeetCodeProvider(DataProvider):
    key = "leetcode"
    display_name = "LeetCode"
    metrics = [MetricSpec(key="solved", label="Solved", color="amber", unit="")]
    cards = [CardSpec(metric="solved", title="LeetCode")]
    neglect_rules = [
        Rule(metric="solved", kind="days_since", label="LeetCode", warn=2, crit=4)
    ]

    def enabled(self) -> bool:
        return bool(get_settings().leetcode_username)

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com",
            "User-Agent": "devansh-os",
        }

    async def _gql(self, client: httpx.AsyncClient, query_str: str) -> dict:
        s = get_settings()
        resp = await client.post(
            LC_URL,
            headers=self._headers(),
            json={"query": query_str, "variables": {"username": s.leetcode_username}},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errors"):
            raise RuntimeError(data["errors"][0].get("message", "LeetCode error"))
        return data["data"]

    async def fetch_metrics(self) -> list[Metric]:
        async with httpx.AsyncClient(timeout=20) as client:
            data = await self._gql(client, _CALENDAR_QUERY)
        raw = data["matchedUser"]["submissionCalendar"]
        calendar: dict[str, int] = json.loads(raw) if raw else {}
        tz = get_settings().tz
        out: list[Metric] = []
        for ts_str, count in calendar.items():
            day = datetime.fromtimestamp(int(ts_str), tz).strftime("%Y-%m-%d")
            out.append(Metric(self.key, "solved", day, float(count)))
        return out

    async def fetch_heatmap_data(self) -> list[HeatmapCell]:
        return [HeatmapCell(m.day, m.value) for m in await self.fetch_metrics()]

    async def fetch_events(self) -> list[Event]:
        async with httpx.AsyncClient(timeout=20) as client:
            data = await self._gql(client, _RECENT_QUERY)
        tz = get_settings().tz
        events: list[Event] = []
        for sub in data.get("recentAcSubmissionList") or []:
            dt = datetime.fromtimestamp(int(sub["timestamp"]), tz)
            events.append(
                Event(
                    provider=self.key,
                    type="solve",
                    ts=dt.astimezone(timezone.utc).isoformat(timespec="seconds"),
                    day=dt.strftime("%Y-%m-%d"),
                    title=f"Solved “{sub['title']}”",
                    payload={"slug": sub["titleSlug"],
                             "url": f"https://leetcode.com/problems/{sub['titleSlug']}/"},
                )
            )
        return events

    async def fetch_detail(self, day: str | None = None) -> ProviderDetail:
        if day:
            rows = query(
                "SELECT title, ts, payload FROM events WHERE provider=? AND day=? "
                "ORDER BY ts DESC",
                (self.key, day),
            )
            title = f"LeetCode — {day}"
        else:
            rows = query(
                "SELECT title, ts, payload FROM events WHERE provider=? "
                "ORDER BY ts DESC LIMIT 30",
                (self.key,),
            )
            title = "LeetCode — recent solves"
        solves = [
            PanelRow(
                label=self._short_time(r["ts"]),
                value=r["title"].replace("Solved ", ""),
                href=(json.loads(r["payload"]) if r["payload"] else {}).get("url"),
            )
            for r in rows
        ]
        sections = [
            PanelSection("Summary", [PanelRow("Problems solved", len(solves))]),
            PanelSection("Recent solves", solves or [PanelRow("—", "no solves")]),
        ]
        return ProviderDetail(title=title, sections=sections)

    def _short_time(self, iso_utc: str) -> str:
        dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
        return dt.astimezone(get_settings().tz).strftime("%b %d %H:%M")
