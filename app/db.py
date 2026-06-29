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


def delete_events(provider: str, title_like: str) -> int:
    """Delete a provider's events whose title matches a SQL LIKE pattern. Used to
    retire superseded events (e.g. push aggregates now shown as per-commit rows).
    Returns the number of rows removed."""
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM events WHERE provider = ? AND title LIKE ?",
            (provider, title_like),
        )
        return cur.rowcount


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


# ── App settings (generic key/value) ───────────────────────────────────────

def get_setting(key: str, default: Any = None) -> Any:
    """Read a value from app_settings; tolerant of a missing table (pre-migration)."""
    try:
        row = query_one("SELECT value FROM app_settings WHERE key=?", (key,))
    except sqlite3.OperationalError:
        return default
    return row["value"] if row else default


def set_setting(key: str, value: Any) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, str(value)),
        )


# ── Protein bank + log ──────────────────────────────────────────────────────

def protein_bank_all() -> list[sqlite3.Row]:
    return query("SELECT * FROM protein_bank ORDER BY name COLLATE NOCASE")


def protein_bank_get(food_id: int) -> sqlite3.Row | None:
    return query_one("SELECT * FROM protein_bank WHERE id=?", (food_id,))


def protein_bank_add(name: str, protein_g: float, serving_label: str | None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO protein_bank (name, protein_g, serving_label) VALUES (?, ?, ?)",
            (name, float(protein_g), serving_label),
        )
        return int(cur.lastrowid)


def protein_bank_update(food_id: int, name: str, protein_g: float, serving_label: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE protein_bank SET name=?, protein_g=?, serving_label=? WHERE id=?",
            (name, float(protein_g), serving_label, food_id),
        )


def protein_bank_delete(food_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM protein_bank WHERE id=?", (food_id,))


def protein_entries(day: str) -> list[sqlite3.Row]:
    return query(
        "SELECT * FROM protein_log WHERE day=? ORDER BY logged_at", (day,)
    )


def protein_day_total(day: str) -> float:
    row = query_one("SELECT COALESCE(SUM(grams), 0) AS t FROM protein_log WHERE day=?", (day,))
    return float(row["t"]) if row else 0.0


def protein_log_add(
    day: str, food_id: int | None, food_name: str, servings: float, grams: float
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO protein_log (day, food_id, food_name, servings, grams, logged_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (day, food_id, food_name, float(servings), float(grams), _now_iso()),
        )
        return int(cur.lastrowid)


def protein_log_delete(entry_id: int) -> str | None:
    """Delete a log entry; return its day (so the caller can recompute the total)."""
    with connect() as conn:
        row = conn.execute(
            "SELECT day FROM protein_log WHERE id=?", (entry_id,)
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM protein_log WHERE id=?", (entry_id,))
        return row["day"]


# ── Rituals bank + log ──────────────────────────────────────────────────────

def rituals_bank_all(active_only: bool = False) -> list[sqlite3.Row]:
    sql = "SELECT * FROM rituals_bank"
    if active_only:
        sql += " WHERE active=1"
    sql += " ORDER BY sort_order, name COLLATE NOCASE"
    return query(sql)


def rituals_bank_get(ritual_id: int) -> sqlite3.Row | None:
    return query_one("SELECT * FROM rituals_bank WHERE id=?", (ritual_id,))


def rituals_bank_add(
    name: str, interval_days: int = 1, dose_label: str | None = None, active: bool = True
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO rituals_bank (name, active, interval_days, dose_label)
            VALUES (?, ?, ?, ?)
            """,
            (name, 1 if active else 0, int(interval_days), dose_label),
        )
        return int(cur.lastrowid)


def rituals_bank_update(
    ritual_id: int, name: str, interval_days: int, dose_label: str | None, active: bool
) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE rituals_bank
            SET name=?, interval_days=?, dose_label=?, active=?
            WHERE id=?
            """,
            (name, int(interval_days), dose_label, 1 if active else 0, ritual_id),
        )


def rituals_bank_delete(ritual_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM rituals_bank WHERE id=?", (ritual_id,))


def rituals_done(day: str) -> set[int]:
    """ritual_ids logged (done) on a given day."""
    rows = query(
        "SELECT ritual_id FROM rituals_log WHERE day=? AND ritual_id IS NOT NULL", (day,)
    )
    return {r["ritual_id"] for r in rows}


def rituals_entries(day: str) -> list[sqlite3.Row]:
    return query("SELECT * FROM rituals_log WHERE day=? ORDER BY logged_at", (day,))


def rituals_log_add(ritual_id: int, ritual_name: str, day: str) -> None:
    """Mark a ritual done for a day (idempotent — UNIQUE(day, ritual_id))."""
    with connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO rituals_log (day, ritual_id, ritual_name, logged_at)
            VALUES (?, ?, ?, ?)
            """,
            (day, ritual_id, ritual_name, _now_iso()),
        )


def rituals_log_remove(ritual_id: int, day: str) -> None:
    with connect() as conn:
        conn.execute(
            "DELETE FROM rituals_log WHERE day=? AND ritual_id=?", (day, ritual_id)
        )
