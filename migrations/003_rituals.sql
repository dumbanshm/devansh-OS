-- Rituals: daily supplements / meds / routines as a recency system. Like
-- protein, this is a legitimately-manual source (no API observes whether you
-- took your magnesium), but reshaped to stay observatory-native: per-ritual
-- heatmaps are binary (did it / didn't) and lapses surface through neglect
-- detection — never a "4/5 done today" completion score.

-- Reusable bank of rituals. ``active`` gates everything (inputs, neglect,
-- heatmap dropdown, adherence); deactivating keeps history but drops a ritual
-- out of accounting. ``interval_days`` is the cadence used to scale neglect
-- thresholds (daily = 1; a weekly med = 7). ``dose_label`` is display-only.
CREATE TABLE IF NOT EXISTS rituals_bank (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT NOT NULL UNIQUE,           -- "Creatine", "Magnesium", "Fish oil"
  active        INTEGER NOT NULL DEFAULT 1,      -- 1 = counted, 0 = retired (history kept)
  interval_days INTEGER NOT NULL DEFAULT 1,      -- cadence; scales neglect warn/crit
  dose_label    TEXT,                            -- "5g", "2 caps" (display only)
  sort_order    INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- One row per ritual per day it was done (presence = done; binary, no quantity).
-- ritual_name is denormalized (frozen at log time) so history survives a rename
-- or delete. UNIQUE(day, ritual_id) makes logging a toggle, not a counter.
CREATE TABLE IF NOT EXISTS rituals_log (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  day         TEXT NOT NULL,                     -- 'YYYY-MM-DD' (local tz)
  ritual_id   INTEGER REFERENCES rituals_bank(id) ON DELETE SET NULL,
  ritual_name TEXT NOT NULL,
  logged_at   TEXT NOT NULL,                     -- ISO8601
  UNIQUE(day, ritual_id)
);
CREATE INDEX IF NOT EXISTS idx_rituals_log_day ON rituals_log(day);
