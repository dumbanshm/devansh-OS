"""GymProvider — workouts from a Hevy CSV export.

Hevy's REST API is Pro-only, but its CSV data export is free for everyone:
Hevy → Settings → Export & Import Data → Export Workouts. Drop the file at
``data/hevy.csv`` (or point HEVY_CSV at it) and this provider parses it — no
API key, no Pro, no manual logging. Each Hevy "set" is one CSV row; rows sharing
a start time are one workout.
"""
from __future__ import annotations

import csv
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from ..config import DATA_DIR, get_settings
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

CACHE_TTL = 30.0
_DT_FORMATS = (
    "%b %d, %Y, %I:%M %p",      # Hevy: "Jun 23, 2026, 3:03 PM"
    "%b %d, %Y, %I:%M:%S %p",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%d %b %Y, %H:%M",
    "%d %b %Y, %H:%M:%S",
    "%d %B %Y, %H:%M",
    "%Y-%m-%d %H:%M",
    "%m/%d/%Y %H:%M:%S",
)


@register
class GymProvider(DataProvider):
    key = "gym"
    display_name = "Gym"
    metrics = [MetricSpec(key="workout", label="Workout", color="violet", unit="")]
    cards = [CardSpec(metric="workout", title="Gym",
                      show=["last_active", "week_sum", "month_sum"])]
    neglect_rules = [
        Rule(metric="workout", kind="days_since", label="Gym", warn=3, crit=6)
    ]

    def __init__(self) -> None:
        self._cache: tuple | None = None

    # ── source location ────────────────────────────────────────────────────
    def _path(self) -> Path:
        s = get_settings()
        if s.hevy_csv:
            p = Path(s.hevy_csv)
        else:
            # Be forgiving about where the export landed under data/:
            #   data/hevy.csv  •  data/hevy/<any>.csv  •  data/*.csv
            if (DATA_DIR / "hevy.csv").is_file():
                return DATA_DIR / "hevy.csv"
            if (DATA_DIR / "hevy").is_dir():
                p = DATA_DIR / "hevy"
            else:
                loose = sorted(DATA_DIR.glob("*.csv"), key=lambda f: f.stat().st_mtime)
                return loose[-1] if loose else (DATA_DIR / "hevy.csv")
        if p.is_dir():
            csvs = sorted(p.glob("*.csv"), key=lambda f: f.stat().st_mtime)
            return csvs[-1] if csvs else p
        return p

    def enabled(self) -> bool:
        return self._path().is_file()

    # ── CSV parsing (cached by mtime) ──────────────────────────────────────
    def _load(self) -> dict[str, dict]:
        path = self._path()
        if not path.is_file():
            return {}
        sig = (str(path), round(path.stat().st_mtime, 2))
        if self._cache and self._cache[0] == sig and \
                (time.time() - self._cache[1]) < CACHE_TTL:
            return self._cache[2]

        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        workouts = self._group(rows)
        self._cache = (sig, time.time(), workouts)
        return workouts

    @staticmethod
    def _col(headers: list[str], *needles: str) -> str | None:
        low = {h.lower().strip(): h for h in headers}
        for needle in needles:
            for lc, orig in low.items():
                if needle in lc:
                    return orig
        return None

    def _group(self, rows: list[dict]) -> dict[str, dict]:
        """Return {start_time_str: workout} where workout has date, title,
        exercises{name:sets}, sets, volume, duration_min."""
        if not rows:
            return {}
        headers = list(rows[0].keys())
        c_start = self._col(headers, "start_time", "start", "date")
        c_end = self._col(headers, "end_time", "end")
        c_title = self._col(headers, "title", "workout_name", "name")
        c_ex = self._col(headers, "exercise_title", "exercise_name", "exercise")
        c_w = self._col(headers, "weight_kg", "weight")
        c_reps = self._col(headers, "reps")
        if not c_start:
            return {}

        tz = get_settings().tz
        workouts: dict[str, dict] = {}
        for r in rows:
            start = (r.get(c_start) or "").strip()
            if not start:
                continue
            w = workouts.get(start)
            if w is None:
                dt = self._parse_dt(start, tz)
                w = workouts[start] = {
                    "day": dt.strftime("%Y-%m-%d") if dt else None,
                    "dt": dt,
                    "title": (r.get(c_title) or "Workout").strip() if c_title else "Workout",
                    "end": (r.get(c_end) or "").strip() if c_end else "",
                    "exercises": defaultdict(int),
                    "sets": 0,
                    "volume": 0.0,
                }
            ex = (r.get(c_ex) or "Exercise").strip() if c_ex else "Exercise"
            w["exercises"][ex] += 1
            w["sets"] += 1
            try:
                w["volume"] += float(r.get(c_w) or 0) * float(r.get(c_reps) or 0)
            except (TypeError, ValueError):
                pass

        # duration from start/end
        for w in workouts.values():
            w["duration_min"] = self._duration_min(w["dt"], w["end"], get_settings().tz)
        return {k: v for k, v in workouts.items() if v["day"]}

    @staticmethod
    def _parse_dt(s: str, tz) -> datetime | None:
        s = s.strip()
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(tz)
        except ValueError:
            pass
        for fmt in _DT_FORMATS:
            try:
                return datetime.strptime(s, fmt).replace(tzinfo=tz)
            except ValueError:
                continue
        return None

    def _duration_min(self, start: datetime | None, end: str, tz) -> int | None:
        if not start or not end:
            return None
        e = self._parse_dt(end, tz)
        if not e:
            return None
        return max(0, int((e - start).total_seconds() // 60))

    # ── provider contract ──────────────────────────────────────────────────
    async def fetch_metrics(self) -> list[Metric]:
        per_day: dict[str, int] = defaultdict(int)
        for w in self._load().values():
            per_day[w["day"]] += 1
        return [Metric(self.key, "workout", day, float(n)) for day, n in per_day.items()]

    async def fetch_heatmap_data(self) -> list[HeatmapCell]:
        return [HeatmapCell(m.day, m.value) for m in await self.fetch_metrics()]

    async def fetch_events(self) -> list[Event]:
        events: list[Event] = []
        for w in self._load().values():
            n_ex = len(w["exercises"])
            events.append(Event(
                provider=self.key, type="workout",
                ts=w["dt"].isoformat(timespec="seconds") if w["dt"] else w["day"],
                day=w["day"],
                title=f"Workout: {w['title']}",
                detail=f"{n_ex} exercises · {w['sets']} sets",
                payload={"title": w["title"], "exercises": n_ex, "sets": w["sets"],
                         "volume": round(w["volume"]), "duration": w["duration_min"]},
            ))
        return events

    async def fetch_detail(self, day: str | None = None) -> ProviderDetail:
        workouts = sorted(self._load().values(),
                          key=lambda w: w["dt"] or datetime.min.replace(tzinfo=get_settings().tz),
                          reverse=True)
        if day:
            todays = [w for w in workouts if w["day"] == day]
            if not todays:
                return ProviderDetail(title=f"Gym — {day}",
                                      sections=[PanelSection("No workout", [PanelRow("—", "—")])])
            sections = []
            for w in todays:
                rows = [PanelRow("Duration", f"{w['duration_min']} min" if w["duration_min"] else "—"),
                        PanelRow("Sets", w["sets"]),
                        PanelRow("Volume", f"{round(w['volume'])} kg")]
                rows += [PanelRow(ex, f"{n} sets") for ex, n in w["exercises"].items()]
                sections.append(PanelSection(w["title"], rows))
            return ProviderDetail(title=f"Gym — {day}", sections=sections)

        # Overview
        ex_count: dict[str, int] = defaultdict(int)
        for w in workouts:
            for ex, n in w["exercises"].items():
                ex_count[ex] += n
        top_ex = sorted(ex_count.items(), key=lambda x: -x[1])[:8]
        recent = [
            PanelRow(w["day"],
                     f"{w['title']} · {len(w['exercises'])} ex"
                     + (f" · {w['duration_min']}min" if w["duration_min"] else ""))
            for w in workouts[:12]
        ]
        return ProviderDetail(
            title="Gym — Hevy",
            sections=[
                PanelSection("Summary", [
                    PanelRow("Total workouts", len(workouts)),
                    PanelRow("Exercises logged", sum(ex_count.values())),
                ]),
                PanelSection("Most trained", [PanelRow(ex, f"{n} sets") for ex, n in top_ex]
                             or [PanelRow("—", "—")]),
                PanelSection("Recent workouts", recent or [PanelRow("—", "—")]),
            ],
        )
