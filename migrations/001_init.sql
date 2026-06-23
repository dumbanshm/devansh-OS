-- Devansh OS — initial schema.
-- Generic + provider-agnostic: adding a new provider requires NO schema change.

-- One row per provider/metric/day. Powers heatmaps, cards, streaks, neglect.
CREATE TABLE IF NOT EXISTS metric_daily (
  provider   TEXT NOT NULL,        -- 'github'
  metric     TEXT NOT NULL,        -- 'commits'
  day        TEXT NOT NULL,        -- 'YYYY-MM-DD' (local tz)
  value      REAL NOT NULL,        -- 4, 7.5, 1 (bool-ish)
  source     TEXT NOT NULL,        -- 'api' | 'manual'
  updated_at TEXT NOT NULL,
  PRIMARY KEY (provider, metric, day)
);

-- Discrete timeline events (a commit batch, a solve, a deploy, a workout).
CREATE TABLE IF NOT EXISTS events (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  provider   TEXT NOT NULL,
  type       TEXT NOT NULL,        -- 'commit' | 'solve' | 'workout' | 'deploy'
  ts         TEXT NOT NULL,        -- ISO8601
  day        TEXT NOT NULL,        -- 'YYYY-MM-DD' (local tz) for fast day filters
  title      TEXT NOT NULL,
  detail     TEXT,
  payload    TEXT                  -- JSON blob (url, count, difficulty, repos...)
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_provider_day ON events(provider, day);

-- A stable identity for dedupe of API-sourced events across syncs.
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_dedupe
  ON events(provider, type, ts, title);

-- Sync bookkeeping for the dashboard's data-freshness + error display.
CREATE TABLE IF NOT EXISTS sync_state (
  provider     TEXT PRIMARY KEY,
  last_run     TEXT,
  last_success TEXT,
  status       TEXT,               -- 'ok' | 'error' | 'never' | 'disabled'
  message      TEXT
);
