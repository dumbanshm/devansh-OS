-- Devansh OS — initial schema (ported from migrations/001_init.sql).
-- Generic + provider-agnostic: adding a new provider requires NO schema change.

-- One row per provider/metric/day. Powers heatmaps, cards, streaks, neglect.
CREATE TABLE IF NOT EXISTS metric_daily (
  provider   TEXT NOT NULL,
  metric     TEXT NOT NULL,
  day        TEXT NOT NULL,              -- 'YYYY-MM-DD' (local tz)
  value      DOUBLE PRECISION NOT NULL,
  source     TEXT NOT NULL,              -- 'api' | 'manual'
  updated_at TEXT NOT NULL,
  PRIMARY KEY (provider, metric, day)
);

-- Discrete timeline events (a commit batch, a solve, a deploy, a workout).
CREATE TABLE IF NOT EXISTS events (
  id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  provider   TEXT NOT NULL,
  type       TEXT NOT NULL,
  ts         TEXT NOT NULL,              -- ISO8601
  day        TEXT NOT NULL,              -- 'YYYY-MM-DD' (local tz)
  title      TEXT NOT NULL,
  detail     TEXT,
  payload    TEXT                        -- JSON blob (url, count, difficulty, repos...)
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_provider_day ON events(provider, day);
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_dedupe
  ON events(provider, type, ts, title);

-- Sync bookkeeping for the dashboard's data-freshness + error display.
CREATE TABLE IF NOT EXISTS sync_state (
  provider     TEXT PRIMARY KEY,
  last_run     TEXT,
  last_success TEXT,
  status       TEXT,
  message      TEXT
);
