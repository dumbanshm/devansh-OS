"""GitHubProvider — coding activity.

Daily values + the contribution heatmap come from the GraphQL
``contributionsCollection.contributionCalendar`` (this includes *private*
contributions when the token has the right scope, matching what you see on your
GitHub profile). The timeline + drill-down (repos worked, branches, commit
counts) come from recent push events.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime

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

GQL_URL = "https://api.github.com/graphql"
REST_BASE = "https://api.github.com"

_CONTRIB_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks {
          contributionDays { date contributionCount }
        }
      }
      commitContributionsByRepository(maxRepositories: 25) {
        repository { nameWithOwner }
        contributions { totalCount }
      }
    }
  }
}
"""


@register
class GitHubProvider(DataProvider):
    key = "github"
    display_name = "GitHub"
    metrics = [MetricSpec(key="commits", label="Commits", color="green", unit="")]
    cards = [CardSpec(metric="commits", title="Commits")]
    neglect_rules = [
        Rule(metric="commits", kind="days_since", label="GitHub", warn=3, crit=5)
    ]

    def enabled(self) -> bool:
        s = get_settings()
        return bool(s.github_token and s.github_username)

    def _headers(self) -> dict[str, str]:
        s = get_settings()
        return {
            "Authorization": f"Bearer {s.github_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "devansh-os",
        }

    # ── Metrics + heatmap (GraphQL contribution calendar) ──────────────────
    async def fetch_metrics(self) -> list[Metric]:
        s = get_settings()
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                GQL_URL,
                headers=self._headers(),
                json={"query": _CONTRIB_QUERY, "variables": {"login": s.github_username}},
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("errors"):
            raise RuntimeError(data["errors"][0].get("message", "GraphQL error"))
        cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        out: list[Metric] = []
        for week in cal["weeks"]:
            for d in week["contributionDays"]:
                out.append(
                    Metric(self.key, "commits", d["date"], float(d["contributionCount"]))
                )
        return out

    async def fetch_heatmap_data(self) -> list[HeatmapCell]:
        return [HeatmapCell(m.day, m.value) for m in await self.fetch_metrics()]

    # ── Timeline events (REST push events) ─────────────────────────────────
    async def fetch_events(self) -> list[Event]:
        s = get_settings()
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{REST_BASE}/users/{s.github_username}/events?per_page=100",
                headers=self._headers(),
            )
            resp.raise_for_status()
            raw = resp.json()
        events: list[Event] = []
        for ev in raw:
            if ev.get("type") != "PushEvent":
                continue
            created = ev["created_at"]  # ISO8601 UTC
            day = self._to_local_day(created)
            repo = ev["repo"]["name"]
            ref = ev["payload"].get("ref", "")
            branch = ref.split("/")[-1] if ref else ""
            n = ev["payload"].get("size", 0)
            events.append(
                Event(
                    provider=self.key,
                    type="commit",
                    ts=created,
                    day=day,
                    title=f"Pushed {n} commit{'s' if n != 1 else ''} to {repo}",
                    detail=f"branch {branch}" if branch else None,
                    payload={"repo": repo, "branch": branch, "commits": n,
                             "url": f"https://github.com/{repo}"},
                )
            )
        return events

    # ── Drill-down: repos worked, branches, commit counts ──────────────────
    async def fetch_detail(self, day: str | None = None) -> ProviderDetail:
        # Aggregate from the push events we've already persisted (fast, offline).
        if day:
            rows = query(
                "SELECT title, detail, ts, payload FROM events "
                "WHERE provider=? AND day=? ORDER BY ts DESC",
                (self.key, day),
            )
            title = f"GitHub — {day}"
        else:
            rows = query(
                "SELECT title, detail, ts, payload FROM events "
                "WHERE provider=? ORDER BY ts DESC LIMIT 100",
                (self.key,),
            )
            title = "GitHub — recent activity"

        repos: dict[str, int] = defaultdict(int)
        branches: set[str] = set()
        recent: list[PanelRow] = []
        total_commits = 0
        for r in rows:
            p = json.loads(r["payload"]) if r["payload"] else {}
            repos[p.get("repo", "?")] += p.get("commits", 0)
            if p.get("branch"):
                branches.add(p["branch"])
            total_commits += p.get("commits", 0)
            if len(recent) < 15:
                recent.append(
                    PanelRow(label=self._short_time(r["ts"]), value=r["title"],
                             href=p.get("url"))
                )

        sections = [
            PanelSection(
                heading="Summary",
                rows=[
                    PanelRow("Commits pushed", total_commits),
                    PanelRow("Repos worked", len(repos)),
                    PanelRow("Branches", len(branches)),
                ],
            ),
            PanelSection(
                heading="Repos worked",
                rows=[PanelRow(repo, f"{c} commits",
                               href=f"https://github.com/{repo}")
                      for repo, c in sorted(repos.items(), key=lambda x: -x[1])],
            ),
            PanelSection(
                heading="Branches",
                rows=[PanelRow("branch", b) for b in sorted(branches)] or
                     [PanelRow("branch", "—")],
            ),
            PanelSection(heading="Recent pushes", rows=recent),
        ]
        return ProviderDetail(title=title, sections=sections)

    # ── helpers ────────────────────────────────────────────────────────────
    def _to_local_day(self, iso_utc: str) -> str:
        dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
        return dt.astimezone(get_settings().tz).strftime("%Y-%m-%d")

    def _short_time(self, iso_utc: str) -> str:
        dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
        return dt.astimezone(get_settings().tz).strftime("%b %d %H:%M")
