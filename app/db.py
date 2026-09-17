"""Postgres (Supabase) access layer.

A thin, dependency-light wrapper around ``psycopg`` v3, kept synchronous to
match every existing caller (routes, providers) — see supabase/migrations for
the schema this targets. Public function signatures are unchanged from the
old sqlite3-backed version; only the connection/placeholder internals moved.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import get_settings

_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            get_settings().database_url, min_size=1, max_size=5, kwargs={"row_factory": dict_row}
        )
    return _pool


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    with _get_pool().connection() as conn:
        yield conn


# ── Writes ────────────────────────────────────────────────────────────────

def upsert_metric(
    provider: str, metric: str, day: str, value: float, source: str = "api"
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO metric_daily (provider, metric, day, value, source, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT(provider, metric, day)
            DO UPDATE SET value=excluded.value,
                          source=excluded.source,
                          updated_at=excluded.updated_at
            """,
            (provider, metric, day, float(value), source, _now_iso()),
        )


def upsert_metrics(rows: Iterable[tuple]) -> None:
    """Bulk upsert. Each row: (provider, metric, day, value, source)."""
    now = _now_iso()
    payload = [(p, m, d, float(v), s, now) for (p, m, d, v, s) in rows]
    if not payload:
        return
    with connect() as conn:
        conn.cursor().executemany(
            """
            INSERT INTO metric_daily (provider, metric, day, value, source, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT(provider, metric, day)
            DO UPDATE SET value=excluded.value,
                          source=excluded.source,
                          updated_at=excluded.updated_at
            """,
            payload,
        )


def insert_events(rows: Iterable[dict[str, Any]]) -> None:
    """Insert timeline events, ignoring duplicates (provider+type+ts+title)."""
    payload = [
        (
            r["provider"],
            r["type"],
            r["ts"],
            r["day"],
            r["title"],
            r.get("detail"),
            json.dumps(r.get("payload")) if r.get("payload") is not None else None,
        )
        for r in rows
    ]
    if not payload:
        return
    with connect() as conn:
        conn.cursor().executemany(
            """
            INSERT INTO events
                (provider, type, ts, day, title, detail, payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            payload,
        )


def delete_events(provider: str, title_like: str) -> int:
    """Delete a provider's events whose title matches a SQL LIKE pattern. Used to
    retire superseded events (e.g. push aggregates now shown as per-commit rows).
    Returns the number of rows removed."""
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM events WHERE provider = %s AND title LIKE %s",
            (provider, title_like),
        )
        return cur.rowcount


def set_sync_state(provider: str, status: str, message: str = "", success: bool = False) -> None:
    now = _now_iso()
    with connect() as conn:
        existing = conn.execute(
            "SELECT last_success FROM sync_state WHERE provider=%s", (provider,)
        ).fetchone()
        last_success = now if success else (existing["last_success"] if existing else None)
        conn.execute(
            """
            INSERT INTO sync_state (provider, last_run, last_success, status, message)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT(provider) DO UPDATE SET
                last_run=excluded.last_run,
                last_success=excluded.last_success,
                status=excluded.status,
                message=excluded.message
            """,
            (provider, now, last_success, status, message),
        )


# ── Reads ─────────────────────────────────────────────────────────────────

def query(sql: str, params: tuple = ()) -> list[dict]:
    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def query_one(sql: str, params: tuple = ()) -> dict | None:
    with connect() as conn:
        return conn.execute(sql, params).fetchone()


def metric_series(provider: str, metric: str, start_day: str, end_day: str) -> dict[str, float]:
    """Return {day: value} for a provider/metric within an inclusive range."""
    rows = query(
        """
        SELECT day, value FROM metric_daily
        WHERE provider=%s AND metric=%s AND day BETWEEN %s AND %s
        """,
        (provider, metric, start_day, end_day),
    )
    return {r["day"]: r["value"] for r in rows}


def all_sync_state() -> dict[str, dict]:
    return {r["provider"]: r for r in query("SELECT * FROM sync_state")}


# ── App settings (generic key/value) ───────────────────────────────────────

def get_setting(key: str, default: Any = None) -> Any:
    """Read a value from app_settings; tolerant of a missing table (pre-migration)."""
    try:
        row = query_one("SELECT value FROM app_settings WHERE key=%s", (key,))
    except psycopg.errors.UndefinedTable:
        return default
    return row["value"] if row else default


def set_setting(key: str, value: Any) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value) VALUES (%s, %s)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, str(value)),
        )


# ── Metric/card/neglect catalog mirror (read by Flutter, written by FastAPI) ─

def sync_metric_catalog(
    provider: str, metrics: list, cards: list, rules: list
) -> None:
    """Upsert one provider's MetricSpec/CardSpec/Rule declarations into the
    Postgres metadata-mirror tables, so any client can read a live, fully-formed
    catalog without FastAPI running. Called on every FastAPI startup."""
    with connect() as conn:
        conn.execute("DELETE FROM metric_specs WHERE provider=%s", (provider,))
        for m in metrics:
            conn.execute(
                """
                INSERT INTO metric_specs
                    (provider, metric, label, color, unit, aggregation, heatmap, scale_max, binary_metric)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (provider, m.key, m.label, m.color, m.unit, m.aggregation, m.heatmap, m.scale_max, m.binary),
            )
        conn.execute("DELETE FROM provider_cards WHERE provider=%s", (provider,))
        for c in cards:
            conn.execute(
                """
                INSERT INTO provider_cards (provider, metric, title, show)
                VALUES (%s, %s, %s, %s)
                """,
                (provider, c.metric, c.title, c.show),
            )
        conn.execute("DELETE FROM neglect_rule_specs WHERE provider=%s", (provider,))
        for r in rules:
            conn.execute(
                """
                INSERT INTO neglect_rule_specs
                    (provider, metric, kind, label, warn, crit, window_days, threshold, severity, unit, grace_hour)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (provider, r.metric, r.kind, r.label, r.warn, r.crit, r.window, r.threshold,
                 r.severity, r.unit, r.grace_hour),
            )


# ── Protein bank + log ──────────────────────────────────────────────────────

def protein_bank_all() -> list[dict]:
    return query("SELECT * FROM protein_bank ORDER BY LOWER(name)")


def protein_bank_get(food_id: int) -> dict | None:
    return query_one("SELECT * FROM protein_bank WHERE id=%s", (food_id,))


def protein_bank_add(name: str, protein_g: float, serving_label: str | None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO protein_bank (name, protein_g, serving_label) VALUES (%s, %s, %s) RETURNING id",
            (name, float(protein_g), serving_label),
        )
        return int(cur.fetchone()["id"])


def protein_bank_update(food_id: int, name: str, protein_g: float, serving_label: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE protein_bank SET name=%s, protein_g=%s, serving_label=%s WHERE id=%s",
            (name, float(protein_g), serving_label, food_id),
        )


def protein_bank_delete(food_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM protein_bank WHERE id=%s", (food_id,))


def protein_entries(day: str) -> list[dict]:
    return query(
        "SELECT * FROM protein_log WHERE day=%s ORDER BY logged_at", (day,)
    )


def protein_day_total(day: str) -> float:
    row = query_one("SELECT COALESCE(SUM(grams), 0) AS t FROM protein_log WHERE day=%s", (day,))
    return float(row["t"]) if row else 0.0


def protein_log_add(
    day: str, food_id: int | None, food_name: str, servings: float, grams: float
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO protein_log (day, food_id, food_name, servings, grams, logged_at)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (day, food_id, food_name, float(servings), float(grams), _now_iso()),
        )
        return int(cur.fetchone()["id"])


def protein_log_delete(entry_id: int) -> str | None:
    """Delete a log entry; return its day (so the caller can recompute the total)."""
    with connect() as conn:
        row = conn.execute(
            "SELECT day FROM protein_log WHERE id=%s", (entry_id,)
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM protein_log WHERE id=%s", (entry_id,))
        return row["day"]


# ── Rituals bank + log ──────────────────────────────────────────────────────

def rituals_bank_all(active_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM rituals_bank"
    if active_only:
        sql += " WHERE active=1"
    sql += " ORDER BY sort_order, LOWER(name)"
    return query(sql)


def rituals_bank_get(ritual_id: int) -> dict | None:
    return query_one("SELECT * FROM rituals_bank WHERE id=%s", (ritual_id,))


def rituals_bank_add(
    name: str, interval_days: int = 1, dose_label: str | None = None, active: bool = True
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO rituals_bank (name, active, interval_days, dose_label)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            (name, 1 if active else 0, int(interval_days), dose_label),
        )
        return int(cur.fetchone()["id"])


def rituals_bank_update(
    ritual_id: int, name: str, interval_days: int, dose_label: str | None, active: bool
) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE rituals_bank
            SET name=%s, interval_days=%s, dose_label=%s, active=%s
            WHERE id=%s
            """,
            (name, int(interval_days), dose_label, 1 if active else 0, ritual_id),
        )


def rituals_bank_delete(ritual_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM rituals_bank WHERE id=%s", (ritual_id,))


def rituals_done(day: str) -> set[int]:
    """ritual_ids logged (done) on a given day."""
    rows = query(
        "SELECT ritual_id FROM rituals_log WHERE day=%s AND ritual_id IS NOT NULL", (day,)
    )
    return {r["ritual_id"] for r in rows}


def rituals_entries(day: str) -> list[dict]:
    return query("SELECT * FROM rituals_log WHERE day=%s ORDER BY logged_at", (day,))


def rituals_log_add(ritual_id: int, ritual_name: str, day: str) -> None:
    """Mark a ritual done for a day (idempotent — UNIQUE(day, ritual_id))."""
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO rituals_log (day, ritual_id, ritual_name, logged_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (day, ritual_id, ritual_name, _now_iso()),
        )


def rituals_log_remove(ritual_id: int, day: str) -> None:
    with connect() as conn:
        conn.execute(
            "DELETE FROM rituals_log WHERE day=%s AND ritual_id=%s", (day, ritual_id)
        )


# ── Life calendar: milestones ────────────────────────────────────────────────

def milestones_all() -> list[dict]:
    return query("SELECT * FROM milestones ORDER BY day")


def milestones_get(milestone_id: int) -> dict | None:
    return query_one("SELECT * FROM milestones WHERE id=%s", (milestone_id,))


def milestones_add(day: str, title: str, detail: str | None, emoji: str | None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO milestones (day, title, detail, emoji) VALUES (%s, %s, %s, %s) RETURNING id",
            (day, title, detail, emoji),
        )
        return int(cur.fetchone()["id"])


def milestones_update(
    milestone_id: int, day: str, title: str, detail: str | None, emoji: str | None
) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE milestones SET day=%s, title=%s, detail=%s, emoji=%s WHERE id=%s",
            (day, title, detail, emoji, milestone_id),
        )


def milestones_delete(milestone_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM milestones WHERE id=%s", (milestone_id,))
