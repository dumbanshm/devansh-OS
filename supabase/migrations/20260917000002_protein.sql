-- Protein tracking (ported from migrations/002_protein.sql): a reusable food
-- bank, a per-meal log, and a generic key/value settings table.

CREATE TABLE IF NOT EXISTS protein_bank (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE,
  protein_g     DOUBLE PRECISION NOT NULL,
  serving_label TEXT
);

CREATE TABLE IF NOT EXISTS protein_log (
  id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  day       TEXT NOT NULL,
  food_id   BIGINT REFERENCES protein_bank(id) ON DELETE SET NULL,
  food_name TEXT NOT NULL,
  servings  DOUBLE PRECISION NOT NULL DEFAULT 1,
  grams     DOUBLE PRECISION NOT NULL,
  logged_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_protein_log_day ON protein_log(day);

CREATE TABLE IF NOT EXISTS app_settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
INSERT INTO app_settings (key, value) VALUES
  ('protein_target_g', '130'),
  ('protein_window_start', '8'),
  ('protein_window_end', '22'),
  ('timezone', 'Asia/Kolkata')
ON CONFLICT (key) DO NOTHING;

INSERT INTO protein_bank (name, protein_g, serving_label) VALUES
  ('Whey',         25, '1 scoop'),
  ('Eggs',         12, '2 eggs'),
  ('Paneer',       18, '100g'),
  ('Cheese',        7, '1 slice'),
  ('Chicken',      31, '100g'),
  ('Greek Yogurt', 17, '170g'),
  ('Lunch',        30, 'meal est.'),
  ('Dinner',       35, 'meal est.')
ON CONFLICT (name) DO NOTHING;
