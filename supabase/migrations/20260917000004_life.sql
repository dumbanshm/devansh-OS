-- Life calendar (ported from migrations/004_life.sql): "Life in Weeks" grid.

CREATE TABLE IF NOT EXISTS milestones (
  id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  day        TEXT NOT NULL,
  title      TEXT NOT NULL,
  detail     TEXT,
  emoji      TEXT,
  created_at TEXT NOT NULL DEFAULT (now()::text)
);
CREATE INDEX IF NOT EXISTS idx_milestones_day ON milestones(day);

INSERT INTO app_settings (key, value) VALUES
  ('life_expectancy_years', '90'),
  ('week_good_threshold', '0.35')
ON CONFLICT (key) DO NOTHING;
