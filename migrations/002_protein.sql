-- Protein tracking: a reusable food bank, a per-meal log, and a generic
-- key/value settings table. Protein is the one legitimately-manual system
-- (no API can observe what you ate), so it re-introduces structured input
-- without violating the read-only philosophy of the rest of the board.

-- Reusable dictionary of foods + grams-per-serving. Editable from Settings.
CREATE TABLE IF NOT EXISTS protein_bank (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL UNIQUE,   -- "Whey", "Eggs", "Paneer"
  protein_g     REAL NOT NULL,          -- grams per serving
  serving_label TEXT                    -- "1 scoop", "2 eggs", "100g" (display only)
);

-- Individual logged meals. food_name/grams are denormalized (frozen at log
-- time) so the history survives bank edits or deletions.
CREATE TABLE IF NOT EXISTS protein_log (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  day       TEXT NOT NULL,              -- 'YYYY-MM-DD' (local tz)
  food_id   INTEGER REFERENCES protein_bank(id) ON DELETE SET NULL,
  food_name TEXT NOT NULL,
  servings  REAL NOT NULL DEFAULT 1,
  grams     REAL NOT NULL,              -- protein_g * servings, frozen at log time
  logged_at TEXT NOT NULL               -- ISO8601
);
CREATE INDEX IF NOT EXISTS idx_protein_log_day ON protein_log(day);

-- Generic settings (target, eating window, future knobs) — one table, no
-- future migration needed to add a setting.
CREATE TABLE IF NOT EXISTS app_settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT OR IGNORE INTO app_settings (key, value) VALUES
  ('protein_target_g', '130'),
  ('protein_window_start', '8'),   -- eating-window start hour (local)
  ('protein_window_end', '22');    -- eating-window end hour

-- Seed the bank once. IGNORE keeps the user's edits on subsequent boots.
INSERT OR IGNORE INTO protein_bank (name, protein_g, serving_label) VALUES
  ('Whey',         25, '1 scoop'),
  ('Eggs',         12, '2 eggs'),
  ('Paneer',       18, '100g'),
  ('Cheese',        7, '1 slice'),
  ('Chicken',      31, '100g'),
  ('Greek Yogurt', 17, '170g'),
  ('Lunch',        30, 'meal est.'),
  ('Dinner',       35, 'meal est.');
