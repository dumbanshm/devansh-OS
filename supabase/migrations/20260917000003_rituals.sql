-- Rituals (ported from migrations/003_rituals.sql): daily supplements / meds /
-- routines as a recency system.

CREATE TABLE IF NOT EXISTS rituals_bank (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  active        INTEGER NOT NULL DEFAULT 1,   -- kept as 1/0 (not BOOLEAN) to match db.py's int writes
  interval_days INTEGER NOT NULL DEFAULT 1,
  dose_label    TEXT,
  sort_order    INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL DEFAULT (now()::text)
);

CREATE TABLE IF NOT EXISTS rituals_log (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  day         TEXT NOT NULL,
  ritual_id   BIGINT REFERENCES rituals_bank(id) ON DELETE SET NULL,
  ritual_name TEXT NOT NULL,
  logged_at   TEXT NOT NULL,
  UNIQUE(day, ritual_id)
);
CREATE INDEX IF NOT EXISTS idx_rituals_log_day ON rituals_log(day);
