"""ClaudeProvider — real Claude Code usage from local session logs.

Parses the JSONL transcripts under ``~/.claude/projects/**/*.jsonl`` (override
with ``CLAUDE_DIR``). Each line carries a ``timestamp``, ``sessionId``, ``cwd``
(→ project) and, for assistant turns, ``message.usage`` token counts.

Derived per local day:
  • hours   — active working time (sum of gaps between consecutive messages,
              capped at 5 min so breaks don't inflate it)
  • tokens  — input + output + cache tokens processed
plus sessions and per-project breakdown for the drill-down. This replaces the
old manual "deep work" metric: real signal, zero logging.
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from ..config import get_settings
from ..models import (
    CardSpec,
    HeatmapCell,
    Metric,
    MetricSpec,
    PanelRow,
    PanelSection,
    ProviderDetail,
    Rule,
)
from .base import DataProvider, register

GAP_CAP = 300.0   # seconds; gaps longer than this are "breaks", not work
CACHE_TTL = 45.0  # re-scan logs at most this often


@register
class ClaudeProvider(DataProvider):
    key = "claude"
    display_name = "Claude"
    metrics = [
        MetricSpec(key="hours", label="Claude Hours", color="indigo", unit="h",
                   scale_max=8.0),
        MetricSpec(key="tokens", label="Tokens", color="indigo", unit="",
                   heatmap=False),
    ]
    cards = [CardSpec(metric="hours", title="Claude",
                      show=["last_active", "week_sum", "day_avg"])]
    neglect_rules = [
        Rule(metric="hours", kind="days_since", label="Claude", warn=4, crit=7)
    ]

    def __init__(self) -> None:
        self._cache: tuple | None = None  # (signature, scanned_at, data)

    def _dir(self) -> Path:
        return Path(get_settings().claude_dir)

    def enabled(self) -> bool:
        return self._dir().is_dir()

    # ── Log scanning (cached) ──────────────────────────────────────────────
    def _signature(self, files: list[Path]) -> tuple:
        mtime = max((f.stat().st_mtime for f in files), default=0)
        return (len(files), round(mtime, 2))

    def _scan(self) -> dict[str, dict]:
        root = self._dir()
        files = list(root.rglob("*.jsonl"))
        sig = self._signature(files)
        if self._cache and self._cache[0] == sig and \
                (time.time() - self._cache[1]) < CACHE_TTL:
            return self._cache[2]

        tz = get_settings().tz
        raw: dict[str, dict] = defaultdict(
            lambda: {"epochs": [], "proj": defaultdict(list),
                     "tokens": 0, "tin": 0, "tout": 0, "sessions": set()}
        )
        for f in files:
            self._consume_file(f, root, raw, tz)

        days: dict[str, dict] = {}
        for day, d in raw.items():
            days[day] = {
                "hours": round(self._active_secs(d["epochs"]) / 3600, 2),
                "tokens": d["tokens"],
                "tin": d["tin"],
                "tout": d["tout"],
                "sessions": len(d["sessions"]),
                "projects": {
                    p: round(self._active_secs(eps) / 3600, 2)
                    for p, eps in d["proj"].items()
                },
            }
        self._cache = (sig, time.time(), days)
        return days

    def _consume_file(self, f: Path, root: Path, raw: dict, tz) -> None:
        """Parse one session file. A file belongs to a single project, so we
        attribute records that lack a ``cwd`` to the file's project rather than
        bucketing them as 'unknown'."""
        records: list[dict] = []
        file_proj: str | None = None
        try:
            with f.open("r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    rec = self._parse_line(line, tz)
                    if rec is None:
                        continue
                    if rec["proj"] and file_proj is None:
                        file_proj = rec["proj"]
                    records.append(rec)
        except OSError:
            return
        if file_proj is None:
            file_proj = self._project_from_path(f, root)
        for rec in records:
            proj = rec["proj"] or file_proj
            d = raw[rec["day"]]
            d["epochs"].append(rec["ep"])
            d["proj"][proj].append(rec["ep"])
            if rec["sid"]:
                d["sessions"].add(rec["sid"])
            d["tin"] += rec["tin"]
            d["tout"] += rec["tout"]
            d["tokens"] += rec["tin"] + rec["tout"]

    @staticmethod
    def _parse_line(line: str, tz) -> dict | None:
        line = line.strip()
        if not line:
            return None
        try:
            o = json.loads(line)
        except ValueError:
            return None
        ts = o.get("timestamp")
        if not ts:
            return None
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(tz)
        except ValueError:
            return None
        usage = (o.get("message") or {}).get("usage") or {}
        tin = (usage.get("input_tokens", 0) or 0) \
            + (usage.get("cache_read_input_tokens", 0) or 0) \
            + (usage.get("cache_creation_input_tokens", 0) or 0)
        return {
            "day": dt.strftime("%Y-%m-%d"),
            "ep": dt.timestamp(),
            "proj": os.path.basename((o.get("cwd") or "").rstrip("/")),
            "sid": o.get("sessionId"),
            "tin": tin,
            "tout": usage.get("output_tokens", 0) or 0,
        }

    @staticmethod
    def _project_from_path(f: Path, root: Path) -> str:
        """Fallback project name from the encoded ~/.claude/projects/<dir> name
        (used only when no record in the file carries a cwd)."""
        try:
            enc = f.relative_to(root).parts[0]
        except (ValueError, IndexError):
            return "unknown"
        return enc.rstrip("-").split("-")[-1] or "unknown"

    @staticmethod
    def _active_secs(epochs: list[float]) -> float:
        if len(epochs) < 2:
            return 0.0
        epochs.sort()
        total = 0.0
        for a, b in zip(epochs, epochs[1:]):
            gap = b - a
            if gap < GAP_CAP:
                total += gap
        return total

    # ── Provider contract ──────────────────────────────────────────────────
    async def fetch_metrics(self) -> list[Metric]:
        days = self._scan()
        out: list[Metric] = []
        for day, d in days.items():
            if d["hours"] > 0:
                out.append(Metric(self.key, "hours", day, d["hours"]))
            if d["tokens"] > 0:
                out.append(Metric(self.key, "tokens", day, float(d["tokens"])))
        return out

    async def fetch_heatmap_data(self) -> list[HeatmapCell]:
        return [HeatmapCell(day, d["hours"]) for day, d in self._scan().items()]

    async def fetch_detail(self, day: str | None = None) -> ProviderDetail:
        days = self._scan()
        if day:
            d = days.get(day)
            if not d:
                return ProviderDetail(
                    title=f"Claude — {day}",
                    sections=[PanelSection("No Claude activity", [PanelRow("—", "—")])],
                )
            projects = sorted(d["projects"].items(), key=lambda x: -x[1])
            return ProviderDetail(
                title=f"Claude — {day}",
                sections=[
                    PanelSection("Summary", [
                        PanelRow("Active time", f"{d['hours']}h"),
                        PanelRow("Tokens", self._human(d["tokens"])),
                        PanelRow("· input/cache", self._human(d["tin"])),
                        PanelRow("· output", self._human(d["tout"])),
                        PanelRow("Sessions", d["sessions"]),
                    ]),
                    PanelSection("Projects", [
                        PanelRow(p, f"{h}h") for p, h in projects
                    ] or [PanelRow("—", "—")]),
                ],
            )

        # Overview: last 30 days.
        recent = sorted(days.keys(), reverse=True)[:30]
        tot_h = round(sum(days[x]["hours"] for x in recent), 1)
        tot_tok = sum(days[x]["tokens"] for x in recent)
        sessions = sum(days[x]["sessions"] for x in recent)
        proj_h: dict[str, float] = defaultdict(float)
        for x in recent:
            for p, h in days[x]["projects"].items():
                proj_h[p] += h
        top = sorted(proj_h.items(), key=lambda x: -x[1])[:8]
        return ProviderDetail(
            title="Claude — last 30 days",
            sections=[
                PanelSection("Summary", [
                    PanelRow("Active time", f"{tot_h}h"),
                    PanelRow("Tokens", self._human(tot_tok)),
                    PanelRow("Sessions", sessions),
                    PanelRow("Active days", len(recent)),
                ]),
                PanelSection("Top projects", [
                    PanelRow(p, f"{round(h, 1)}h") for p, h in top
                ] or [PanelRow("—", "—")]),
                PanelSection("Recent days", [
                    PanelRow(x, f"{days[x]['hours']}h · {self._human(days[x]['tokens'])}")
                    for x in recent[:10]
                ]),
            ],
        )

    @staticmethod
    def _human(n: float) -> str:
        n = float(n)
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}k"
        return str(int(n))
