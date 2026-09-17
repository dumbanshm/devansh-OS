"""One-time cutover: copy the existing local SQLite database into Supabase
Postgres. Run manually from the dev machine once the schema has been applied
via `supabase db push` (or pasted into the SQL editor), with both the old
SQLite file and the new Supabase project reachable.

Usage:
    DATABASE_URL=postgres://... python scripts/migrate_to_supabase.py path/to/devansh.db

Not part of the shipped app — throwaway, run once, then retire the SQLite file.
"""
from __future__ import annotations

import os
import sqlite3
import sys

import psycopg

# Copy order matters: parents before children (FK-safe).
TABLES = [
    "app_settings",
    "protein_bank",
    "rituals_bank",
    "milestones",
    "protein_log",
    "rituals_log",
    "metric_daily",
    "events",
    "sync_state",
]

# Tables with an identity `id` column whose value must be preserved and whose
# sequence must be re-synced afterward.
ID_TABLES = {"protein_bank", "rituals_bank", "milestones", "protein_log", "rituals_log", "events"}


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python scripts/migrate_to_supabase.py path/to/devansh.db")
        sys.exit(1)
    sqlite_path = sys.argv[1]
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("set DATABASE_URL to the Supabase Postgres connection string")
        sys.exit(1)

    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row
    dst = psycopg.connect(database_url)

    # protein_bank/rituals_bank are pre-seeded by the schema migration with
    # placeholder rows/ids that would collide with the real historical ids
    # below (protein_log.food_id references these by id). The SQLite copy is
    # authoritative for both tables, so clear the seed rows first.
    with dst.cursor() as cur:
        cur.execute("DELETE FROM protein_bank")
        cur.execute("DELETE FROM rituals_bank")
    dst.commit()
    print("cleared seeded protein_bank/rituals_bank rows before cutover")

    for table in TABLES:
        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"{table}: 0 rows, skipping")
            continue
        cols = rows[0].keys()
        col_list = ", ".join(cols)
        placeholders = ", ".join(["%s"] * len(cols))
        overriding = " OVERRIDING SYSTEM VALUE" if table in ID_TABLES else ""
        # app_settings holds real, possibly-edited config (target grams, eating
        # window, birth date) — overwrite the placeholder seed values rather
        # than skipping, since the SQLite copy is the authoritative source here.
        conflict = "ON CONFLICT (key) DO UPDATE SET value = excluded.value" if table == "app_settings" \
            else "ON CONFLICT DO NOTHING"
        sql = (
            f"INSERT INTO {table} ({col_list}){overriding} VALUES ({placeholders}) "
            f"{conflict}"
        )
        with dst.cursor() as cur:
            for row in rows:
                cur.execute(sql, tuple(row[c] for c in cols))
        dst.commit()
        print(f"{table}: copied {len(rows)} rows")

    # Re-sync identity sequences so future inserts don't collide with copied ids.
    for table in ID_TABLES:
        with dst.cursor() as cur:
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
            )
        dst.commit()
        print(f"{table}: sequence re-synced")

    # Verify row counts match on both sides.
    print("\nVerification:")
    for table in TABLES:
        src_count = src.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        with dst.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            dst_count = cur.fetchone()[0]
        flag = "OK" if src_count == dst_count else "MISMATCH"
        print(f"  {table}: sqlite={src_count} postgres={dst_count} [{flag}]")

    src.close()
    dst.close()


if __name__ == "__main__":
    main()
