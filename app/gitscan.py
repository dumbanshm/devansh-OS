"""Local git commit counting across all branches.

DevanshOS runs on the same machine where your repos are cloned, so the most
complete commit source isn't an API at all — it's the local clones. This walks
configured repo paths and counts commits on **every** branch (``git log --all``),
which means feature-branch and private-repo work is counted immediately, without
pushing or merging. No GitHub token, no API rate limits, no contribution-graph
default-branch rule.

The result is a ``{local_day: count}`` map that the GitHub provider overlays onto
its ``commits`` metric, so the existing counter / heatmap / streaks just work.
"""
from __future__ import annotations

import logging
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

log = logging.getLogger("devansh.gitscan")

# git log field separator unlikely to appear in emails/names.
_SEP = "\x1f"
_FMT = f"%H{_SEP}%aI{_SEP}%ae{_SEP}%an"
_FMT_EV = f"%H{_SEP}%aI{_SEP}%ae{_SEP}%an{_SEP}%s"  # + subject, for timeline events


def discover_repos(paths: list[str]) -> list[Path]:
    """Expand configured paths into git repos. A path may be a repo itself or a
    folder containing repos (scanned one level deep)."""
    repos: list[Path] = []
    seen: set[Path] = set()
    for raw in paths:
        root = Path(raw).expanduser()
        if not root.is_dir():
            continue
        candidates = [root] + [c for c in sorted(root.iterdir()) if c.is_dir()]
        for c in candidates:
            if (c / ".git").exists() and c not in seen:
                seen.add(c)
                repos.append(c)
    return repos


def remote_slug(repo: Path) -> str | None:
    """``owner/name`` from the repo's origin remote, or None. Used to link
    timeline events to GitHub and to dedup against the push-events feed."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    # git@github.com:owner/name.git  |  https://github.com/owner/name(.git)
    m = re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?/?$", out.stdout.strip())
    return m.group(1) if m else None


def _local_branches(repo: Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "for-each-ref", "--format=%(refname:short)",
             "refs/heads"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [b for b in out.stdout.splitlines() if b] if out.returncode == 0 else []


def _matches(email: str, name: str, matchers: list[str]) -> bool:
    if not matchers:
        return True  # no filter → count every commit (solo / AI-pair repos)
    hay = f"{email}\n{name}".lower()
    return any(m in hay for m in matchers)


def _repo_counts(
    repo: Path, since: str, matchers: list[str], tz: ZoneInfo
) -> dict[str, int]:
    """Per-day commit counts on all branches of one repo."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "log", "--all", "--no-merges",
             f"--since={since}", f"--pretty=format:{_FMT}"],
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("git log failed for %s: %s", repo, exc)
        return {}
    if out.returncode != 0:
        log.warning("git log non-zero for %s: %s", repo, out.stderr.strip()[:200])
        return {}

    counts: dict[str, int] = {}
    seen: set[str] = set()  # dedup commits reachable from multiple refs
    for line in out.stdout.splitlines():
        parts = line.split(_SEP)
        if len(parts) != 4:
            continue
        sha, iso, email, name = parts
        if sha in seen or not _matches(email, name, matchers):
            continue
        seen.add(sha)
        try:
            day = datetime.fromisoformat(iso).astimezone(tz).strftime("%Y-%m-%d")
        except ValueError:
            continue
        counts[day] = counts.get(day, 0) + 1
    return counts


def local_commit_counts(
    paths: list[str], matchers: list[str], tz: ZoneInfo, window_days: int
) -> dict[str, int]:
    """Merge per-day all-branch commit counts across every configured repo.

    Window is generous on the lower bound (``git --since`` filters on *commit*
    date) and then re-bucketed by *author* date in local tz.
    """
    since = (datetime.now(tz) - timedelta(days=window_days + 2)).strftime("%Y-%m-%d")
    floor = (datetime.now(tz) - timedelta(days=window_days)).strftime("%Y-%m-%d")
    totals: dict[str, int] = {}
    repos = discover_repos(paths)
    log.info("scanning %d local repo(s) for commits since %s", len(repos), since)
    for repo in repos:
        for day, n in _repo_counts(repo, since, matchers, tz).items():
            if day >= floor:
                totals[day] = totals.get(day, 0) + n
    return totals


def local_commits(
    paths: list[str], matchers: list[str], tz: ZoneInfo, window_days: int
) -> list[dict]:
    """Individual recent commits across every local branch, for the timeline.

    Each record: ``{slug, repo, branch, sha, ts, day, message, ...}``. Commits
    reachable from several branches are emitted once (first branch wins). ``slug``
    is the GitHub ``owner/name`` when an origin remote exists, else the dir name.
    """
    since = (datetime.now(tz) - timedelta(days=window_days + 2)).strftime("%Y-%m-%d")
    floor = (datetime.now(tz) - timedelta(days=window_days)).strftime("%Y-%m-%d")
    commits: list[dict] = []
    for repo in discover_repos(paths):
        slug = remote_slug(repo) or repo.name
        seen: set[str] = set()
        for branch in _local_branches(repo):
            try:
                out = subprocess.run(
                    ["git", "-C", str(repo), "log", branch, "--no-merges",
                     f"--since={since}", f"--pretty=format:{_FMT_EV}"],
                    capture_output=True, text=True, timeout=30,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                log.warning("git log failed for %s@%s: %s", repo, branch, exc)
                continue
            if out.returncode != 0:
                continue
            for line in out.stdout.splitlines():
                parts = line.split(_SEP, 4)
                if len(parts) != 5:
                    continue
                sha, iso, email, name, subject = parts
                if sha in seen or not _matches(email, name, matchers):
                    continue
                seen.add(sha)
                try:
                    day = datetime.fromisoformat(iso).astimezone(tz).strftime("%Y-%m-%d")
                except ValueError:
                    continue
                if day < floor:
                    continue
                commits.append({
                    "slug": slug, "repo": repo.name, "branch": branch,
                    "sha": sha, "ts": iso, "day": day,
                    "message": subject, "email": email, "name": name,
                })
    return commits
