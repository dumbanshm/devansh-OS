"""GymProvider — workouts from Hevy, automatically or from a CSV export.

Two free ways in (no Hevy Pro needed):

1. **Auto (preferred)** — set ``HEVY_AUTH_TOKEN``. Grabbed once from the Hevy
   web app, it lets us pull workouts from the unofficial ``workouts_batch``
   endpoint on every poll. Works with Google sign-in (token, not password).
   Note: this is an unofficial endpoint and can change.

2. **CSV fallback** — drop a Hevy "Export Workouts" CSV at ``data/hevy.csv``.

Both map to the same internal workout shape, so the heatmap / card / neglect /
drill-down don't care where the data came from.
"""
from __future__ import annotations

import csv
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import httpx

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
HEVY_API = "https://api.hevyapp.com"
HEVY_WEB_KEY = "shelobs_hevy_web"   # web app's public api key
API_CACHE_TTL = 120.0
API_PAGE = 20
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
        self._cache: tuple | None = None       # CSV cache (keyed by mtime)
        self._api_cache: tuple | None = None   # API cache (time-based)

    # ── data source dispatch ───────────────────────────────────────────────
    def _token(self) -> str:
        t = get_settings().hevy_auth_token.strip()
        if t.lower().startswith("bearer "):  # tolerate a pasted "Bearer " prefix
            t = t[7:].strip()
        return t

    def _username(self) -> str:
        return get_settings().hevy_username.strip()

    def _api_ready(self) -> bool:
        return bool(self._token() and self._username())

    def enabled(self) -> bool:
        return self._api_ready() or self._path().is_file()

    async def _workouts(self) -> dict[str, dict]:
        """Workouts keyed by id, from the API if token+username are set, else CSV."""
        if self._api_ready():
            try:
                return await self._load_api()
            except Exception:
                # API hiccup (expired token, endpoint change) — fall back to CSV
                # if we have one, so the board degrades gracefully.
                if self._path().is_file():
                    return self._load_csv()
                raise
        return self._load_csv()

    # ── Hevy API (unofficial web endpoint) ─────────────────────────────────
    async def _load_api(self) -> dict[str, dict]:
        if self._api_cache and (time.time() - self._api_cache[0]) < API_CACHE_TTL:
            return self._api_cache[1]
        headers = {
            "accept": "application/json, text/plain, */*",
            "authorization": f"Bearer {self._token()}",
            "x-api-key": HEVY_WEB_KEY,
            "hevy-platform": "web",
            "origin": "https://hevy.com",
            "referer": "https://hevy.com/",
        }
        username = self._username()
        tz = get_settings().tz
        workouts: dict[str, dict] = {}
        offset = 0
        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            for _ in range(100):  # safety cap: up to 2000 workouts
                resp = await client.get(
                    f"{HEVY_API}/user_workouts_paged",
                    params={"username": username, "limit": API_PAGE, "offset": offset},
                    headers={"x-client-time": f"{time.time():.3f}"},
                )
                resp.raise_for_status()
                batch = (resp.json() or {}).get("workouts") or []
                if not batch:
                    break
                for w in batch:
                    self._add_api_workout(w, workouts, tz)
                offset += len(batch)
                if len(batch) < API_PAGE:
                    break
        self._api_cache = (time.time(), workouts)
        return workouts

    @staticmethod
    def _add_api_workout(w: dict, workouts: dict, tz) -> None:
        start = w.get("start_time")
        if start is None:
            return
        start = float(start)
        if start > 1e12:  # milliseconds → seconds
            start /= 1000.0
        dt = datetime.fromtimestamp(start, tz)
        end = w.get("end_time")
        dur = None
        if end:
            end = float(end)
            if end > 1e12:
                end /= 1000.0
            dur = max(0, int((end - start) // 60))
        exercises: dict[str, int] = defaultdict(int)
        sets = 0
        volume = 0.0
        for ex in w.get("exercises") or []:
            name = (ex.get("title") or "Exercise").strip()
            ex_sets = ex.get("sets") or []
            exercises[name] += len(ex_sets)
            sets += len(ex_sets)
            for st in ex_sets:
                try:
                    volume += float(st.get("weight_kg") or 0) * float(st.get("reps") or 0)
                except (TypeError, ValueError):
                    pass
        if not volume and w.get("estimated_volume_kg"):
            volume = float(w["estimated_volume_kg"])
        workouts[str(w.get("id") or start)] = {
            "day": dt.strftime("%Y-%m-%d"),
            "dt": dt,
            "title": (w.get("name") or "Workout").strip(),
            "end": "",
            "exercises": exercises,
            "sets": sets,
            "volume": volume,
            "duration_min": dur,
        }

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

    # ── CSV parsing (cached by mtime) ──────────────────────────────────────
    def _load_csv(self) -> dict[str, dict]:
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
        for w in (await self._workouts()).values():
            per_day[w["day"]] += 1
        return [Metric(self.key, "workout", day, float(n)) for day, n in per_day.items()]

    async def fetch_heatmap_data(self) -> list[HeatmapCell]:
        return [HeatmapCell(m.day, m.value) for m in await self.fetch_metrics()]

    async def fetch_events(self) -> list[Event]:
        events: list[Event] = []
        for w in (await self._workouts()).values():
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
        workouts = sorted((await self._workouts()).values(),
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
