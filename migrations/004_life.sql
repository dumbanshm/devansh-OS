-- Life calendar: a "Life in Weeks" grid (memento mori). Each cell is one week
-- of life; milestones pin a human-authored marker to a week (past or future).
-- Like protein/rituals, milestones are a legitimately-manual source — a person
-- authors them, not an API — so a mounted CRUD router stays observatory-native.

CREATE TABLE IF NOT EXISTS milestones (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  day        TEXT NOT NULL,                       -- 'YYYY-MM-DD' (may be future)
  title      TEXT NOT NULL,
  detail     TEXT,                                -- optional longer note
  emoji      TEXT,                                -- optional marker glyph
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_milestones_day ON milestones(day);

-- Lifespan baseline for the grid (90 rows × 52 weeks). Editable in Settings.
-- birth_date has no default — the page prompts until it's set.
INSERT OR IGNORE INTO app_settings (key, value) VALUES
  ('life_expectancy_years', '90');
