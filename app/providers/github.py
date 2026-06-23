"""GitHubProvider — coding activity.

Daily values + the contribution heatmap come from the GraphQL
``contributionsCollection.contributionCalendar`` (this includes *private*
contributions when the token has the right scope, matching what you see on your
GitHub profile). The timeline + drill-down (repos worked, branches, commit
counts) come from recent push events.
"""
from __future__ import annotations

from datetime import datetime

import httpx

from ..config import get_settings
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

# Drill-down query — scoped with optional from/to (a single day, or last year).
_DETAIL_QUERY = """
query($login: String!, $from: DateTime, $to: DateTime) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      restrictedContributionsCount
      commitContributionsByRepository(maxRepositories: 25) {
        repository { nameWithOwner url }
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

    # ── Drill-down: live from GraphQL contributions (includes PRIVATE) ─────
    async def fetch_detail(self, day: str | None = None) -> ProviderDetail:
        """Repos worked + commit/PR/review counts straight from the GraphQL
        contributions API, so private work shows up (the public events feed
        doesn't). For a single day we scope the query with from/to."""
        s = get_settings()
        if day:
            variables = {"login": s.github_username,
                         "from": f"{day}T00:00:00Z", "to": f"{day}T23:59:59Z"}
            title = f"GitHub — {day}"
        else:
            variables = {"login": s.github_username, "from": None, "to": None}
            title = "GitHub — last year"

        try:
            cc = await self._contrib(variables)
        except Exception as exc:  # graceful: panel shows the error, board is fine
            return ProviderDetail(
                title="GitHub",
                sections=[PanelSection("Couldn't load", [PanelRow("error", str(exc)[:140])])],
            )

        repos = cc.get("commitContributionsByRepository") or []
        public_commits = cc.get("totalCommitContributions", 0)
        private = cc.get("restrictedContributionsCount", 0)

        repo_rows = [
            PanelRow(r["repository"]["nameWithOwner"],
                     f"{r['contributions']['totalCount']} commits",
                     href=r["repository"].get("url"))
            for r in sorted(repos, key=lambda x: -x["contributions"]["totalCount"])
        ]
        if private:
            repo_rows.append(
                PanelRow("private repos", f"{private} contributions · names hidden by GitHub")
            )

        sections = [
            PanelSection("Summary", [
                PanelRow("Commits (public repos)", public_commits),
                PanelRow("Private contributions", private),
                PanelRow("Repos worked", len(repos)),
                PanelRow("Pull requests", cc.get("totalPullRequestContributions", 0)),
                PanelRow("Reviews", cc.get("totalPullRequestReviewContributions", 0)),
                PanelRow("Issues", cc.get("totalIssueContributions", 0)),
            ]),
            PanelSection("Repos worked", repo_rows or [PanelRow("—", "no commits in range")]),
        ]
        return ProviderDetail(title=title, sections=sections)

    async def _contrib(self, variables: dict) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                GQL_URL, headers=self._headers(),
                json={"query": _DETAIL_QUERY, "variables": variables},
            )
            resp.raise_for_status()
            data = resp.json()
        if data.get("errors"):
            raise RuntimeError(data["errors"][0].get("message", "GraphQL error"))
        return data["data"]["user"]["contributionsCollection"]

    # ── helpers ────────────────────────────────────────────────────────────
    def _to_local_day(self, iso_utc: str) -> str:
        dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
        return dt.astimezone(get_settings().tz).strftime("%Y-%m-%d")
