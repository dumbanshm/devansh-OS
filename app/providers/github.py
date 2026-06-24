"""GitHubProvider — coding activity.

The contribution heatmap comes from the GraphQL
``contributionsCollection.contributionCalendar`` (this includes *private*
contributions when the token has the right scope, matching what you see on your
GitHub profile), which only ever counts the **default branch**.

Recent daily commit *counts* (the card/counter) are overlaid from all-branch
sources so feature-branch and private work shows up immediately, without waiting
for a push or a merge to the default branch:
  1. local clones (every branch, public + private) — primary, see ``gitscan``
  2. the Search Commits API (public repos only) — fallback for uncloned repos
Each is max-merged onto the calendar, so the count never drops below GitHub's
own. The timeline + drill-down come from push events.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import httpx

from ..config import get_settings
from ..db import delete_events
from ..gitscan import local_commit_counts, local_commits
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

log = logging.getLogger("devansh.providers.github")

GQL_URL = "https://api.github.com/graphql"
REST_BASE = "https://api.github.com"

# How many recent days to overlay with all-branch commit counts. The contribution
# calendar still drives older history + the heatmap; only this trailing window is
# replaced with the (more complete) cross-branch number.
_ALL_BRANCH_WINDOW_DAYS = 30
_SEARCH_MAX_PAGES = 10  # 100/page → up to 1000 commits in the window; plenty.

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
        by_day: dict[str, float] = {}
        for week in cal["weeks"]:
            for d in week["contributionDays"]:
                by_day[d["date"]] = float(d["contributionCount"])

        # Overlay the trailing window with all-branch commit counts so feature-branch
        # work shows up before it's merged. Sources, in order of completeness:
        #   1. local clones (every branch, public + private)   ← primary
        #   2. Search Commits API (public repos only)          ← fallback
        # We max-merge each onto the calendar so the number never drops below
        # GitHub's own (and a repo not cloned locally still falls back to search).
        # Both are best-effort: a failure in either degrades to the next source.
        for day, n in (await self._local_counts()).items():
            by_day[day] = max(by_day.get(day, 0.0), float(n))
        try:
            for day, n in (await self._all_branch_counts()).items():
                by_day[day] = max(by_day.get(day, 0.0), float(n))
        except Exception:  # noqa: BLE001 — degrade to local/calendar, never break sync
            log.warning("search-commit overlay failed; using local + calendar", exc_info=True)

        return [Metric(self.key, "commits", day, val) for day, val in by_day.items()]

    async def _local_counts(self) -> dict[str, int]:
        """All-branch commit counts from local clones (primary source).

        Runs the blocking git walk off the event loop. Best-effort: any failure
        logs and yields nothing, so the GitHub-API sources still apply.
        """
        s = get_settings()
        if not s.git_repo_paths:
            return {}
        try:
            return await asyncio.to_thread(
                local_commit_counts,
                s.git_repo_paths, s.git_author_matchers, s.tz, _ALL_BRANCH_WINDOW_DAYS,
            )
        except Exception:  # noqa: BLE001
            log.warning("local git commit scan failed; falling back to GitHub API", exc_info=True)
            return {}

    async def _all_branch_counts(self) -> dict[str, int]:
        """Commits authored by the user on *any* branch over the recent window,
        bucketed by local day, via the Search Commits API.

        Keyed off GitHub's author→account association (same as the contribution
        graph), so commits authored under an email not linked to the account
        still won't appear.
        """
        s = get_settings()
        since = (datetime.now(s.tz) - timedelta(days=_ALL_BRANCH_WINDOW_DAYS)).strftime("%Y-%m-%d")
        query = f"author:{s.github_username} author-date:>={since}"
        counts: dict[str, int] = {}
        async with httpx.AsyncClient(timeout=20) as client:
            for page in range(1, _SEARCH_MAX_PAGES + 1):
                resp = await client.get(
                    f"{REST_BASE}/search/commits",
                    headers=self._headers(),
                    params={"q": query, "per_page": 100, "page": page,
                            "sort": "author-date", "order": "desc"},
                )
                resp.raise_for_status()
                items = resp.json().get("items", [])
                if not items:
                    break
                for it in items:
                    iso = it["commit"]["author"]["date"]  # ISO8601 UTC
                    day = self._to_local_day(iso)
                    counts[day] = counts.get(day, 0) + 1
                if len(items) < 100:
                    break
        return counts

    async def fetch_heatmap_data(self) -> list[HeatmapCell]:
        return [HeatmapCell(m.day, m.value) for m in await self.fetch_metrics()]

    # ── Timeline events (local commits + REST push events) ─────────────────
    async def fetch_events(self) -> list[Event]:
        # Per-commit events from local clones first (covers private + feature
        # branches). Track which repos we covered so we can suppress the
        # redundant "Pushed to …" aggregate for those same repos below.
        events = await self._local_events()
        covered = {e.payload["repo"].lower() for e in events if e.payload.get("repo")}

        # For repos we cover with per-commit rows, clear the existing events so
        # they're rewritten fresh: retire push-event aggregates (now redundant)
        # and any prior "Committed to …" rows (so format changes take effect —
        # the dedupe key is title, which doesn't change). SQLite LIKE is
        # case-insensitive for ASCII, so lowercase slugs match.
        for slug in covered:
            if "/" in slug:
                delete_events(self.key, f"Pushed%to {slug}")
                delete_events(self.key, f"Committed to {slug}")

        s = get_settings()
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{REST_BASE}/users/{s.github_username}/events?per_page=100",
                headers=self._headers(),
            )
            resp.raise_for_status()
            raw = resp.json()
        for ev in raw:
            if ev.get("type") != "PushEvent":
                continue
            repo = ev["repo"]["name"]
            if repo.lower() in covered:
                continue  # already shown as individual local commits
            created = ev["created_at"]  # ISO8601 UTC
            day = self._to_local_day(created)
            ref = ev["payload"].get("ref", "")
            branch = ref.split("/")[-1] if ref else ""
            size = ev["payload"].get("size")
            # GitHub's events feed sometimes returns no commit count (size=null).
            # Only show a count when it's actually a positive number.
            n = size if isinstance(size, int) else None
            if n and n > 0:
                title = f"Pushed {n} commit{'s' if n != 1 else ''} to {repo}"
            else:
                title = f"Pushed to {repo}"
            events.append(
                Event(
                    provider=self.key,
                    type="commit",
                    ts=created,
                    day=day,
                    title=title,
                    detail=f"branch {branch}" if branch else None,
                    payload={"repo": repo, "branch": branch, "commits": n or 0,
                             "url": f"https://github.com/{repo}"},
                )
            )
        return events

    async def _local_events(self) -> list[Event]:
        """One timeline event per local commit (all branches, public + private).
        Best-effort: failures log and yield nothing, leaving push events intact.
        """
        s = get_settings()
        if not s.git_repo_paths:
            return []
        try:
            commits = await asyncio.to_thread(
                local_commits,
                s.git_repo_paths, s.git_author_matchers, s.tz, _ALL_BRANCH_WINDOW_DAYS,
            )
        except Exception:  # noqa: BLE001
            log.warning("local git event scan failed; using push events only", exc_info=True)
            return []
        out: list[Event] = []
        for c in commits:
            slug, sha = c["slug"], c["sha"]
            # Link to GitHub only when slug looks like owner/name (has a remote).
            url = f"https://github.com/{slug}/commit/{sha}" if "/" in slug else None
            # Keep the timeline compact: action + repo + branch only. The full
            # message stays in the payload for the drill-down.
            out.append(
                Event(
                    provider=self.key,
                    type="commit",
                    ts=c["ts"],
                    day=c["day"],
                    title=f"Committed to {slug}",
                    detail=f"branch {c['branch']}",
                    payload={"repo": slug, "branch": c["branch"], "sha": sha,
                             "message": c["message"], "url": url},
                )
            )
        return out

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
