"""SQLite access layer.

A thin, dependency-free wrapper around the stdlib ``sqlite3`` module. The DB is
tiny and single-user, so a fresh short-lived connection per operation keeps
things simple and avoids cross-thread issues with the scheduler.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterable, Iterator

from .config import DATA_DIR, MIGRATIONS_DIR, get_settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    settings = get_settings()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Apply every ``*.sql`` migration in order (idempotent)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            conn.executescript(path.read_text())


# ── Writes ────────────────────────────────────────────────────────────────

def upsert_metric(
    provider: str, metric: str, day: str, value: float, source: str = "api"
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO metric_daily (provider, metric, day, value, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
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
        conn.executemany(
            """
            INSERT INTO metric_daily (provider, metric, day, value, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
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
        conn.executemany(
            """
            INSERT OR IGNORE INTO events
                (provider, type, ts, day, title, detail, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )


def set_sync_state(provider: str, status: str, message: str = "", success: bool = False) -> None:
    now = _now_iso()
    with connect() as conn:
        existing = conn.execute(
            "SELECT last_success FROM sync_state WHERE provider=?", (provider,)
        ).fetchone()
        last_success = now if success else (existing["last_success"] if existing else None)
        conn.execute(
            """
            INSERT INTO sync_state (provider, last_run, last_success, status, message)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(provider) DO UPDATE SET
                last_run=excluded.last_run,
                last_success=excluded.last_success,
                status=excluded.status,
                message=excluded.message
            """,
            (provider, now, last_success, status, message),
        )


# ── Reads ─────────────────────────────────────────────────────────────────

def query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(sql, params).fetchall()


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(sql, params).fetchone()


def metric_series(provider: str, metric: str, start_day: str, end_day: str) -> dict[str, float]:
    """Return {day: value} for a provider/metric within an inclusive range."""
    rows = query(
        """
        SELECT day, value FROM metric_daily
        WHERE provider=? AND metric=? AND day BETWEEN ? AND ?
        """,
        (provider, metric, start_day, end_day),
    )
    return {r["day"]: r["value"] for r in rows}


def all_sync_state() -> dict[str, sqlite3.Row]:
    return {r["provider"]: r for r in query("SELECT * FROM sync_state")}
