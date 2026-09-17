-- Compute layer: ports app/aggregates.py + app/neglect.py into Postgres so any
-- client (FastAPI or the Flutter app) can read live cards/heatmaps/neglect
-- without the FastAPI process running. Python provider declarations
-- (MetricSpec/CardSpec/Rule in app/models.py) stay the source of truth for
-- labels/colors/thresholds; FastAPI mirrors them into these tables on startup
-- via db.sync_metric_catalog(). Only FastAPI (connected as the `postgres`
-- role) writes these tables — see the RLS migration.

-- ── Metadata mirror (upserted by FastAPI on startup from provider declarations) ──

CREATE TABLE IF NOT EXISTS metric_specs (
  provider    TEXT NOT NULL,
  metric      TEXT NOT NULL,
  label       TEXT NOT NULL,
  color       TEXT NOT NULL,
  unit        TEXT NOT NULL DEFAULT '',
  aggregation TEXT NOT NULL DEFAULT 'sum',
  heatmap     BOOLEAN NOT NULL DEFAULT TRUE,
  scale_max   DOUBLE PRECISION,
  binary_metric BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (provider, metric)
);

CREATE TABLE IF NOT EXISTS provider_cards (
  provider TEXT NOT NULL,
  metric   TEXT NOT NULL,
  title    TEXT NOT NULL,
  show     TEXT[] NOT NULL,
  PRIMARY KEY (provider, metric)
);

CREATE TABLE IF NOT EXISTS neglect_rule_specs (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  provider    TEXT NOT NULL,
  metric      TEXT NOT NULL,
  kind        TEXT NOT NULL,             -- 'days_since' | 'rolling_avg_below'
  label       TEXT NOT NULL,
  warn        DOUBLE PRECISION,
  crit        DOUBLE PRECISION,
  window_days INTEGER,
  threshold   DOUBLE PRECISION,
  severity    TEXT NOT NULL DEFAULT 'warning',
  unit        TEXT NOT NULL DEFAULT '',
  grace_hour  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_neglect_rule_specs_provider ON neglect_rule_specs(provider);

-- ── Time helpers ────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION fn_tz() RETURNS text AS $$
  SELECT COALESCE((SELECT value FROM app_settings WHERE key = 'timezone'), 'UTC')
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_today() RETURNS date AS $$
  SELECT (now() AT TIME ZONE fn_tz())::date
$$ LANGUAGE sql STABLE;

-- Ports app/aggregates.py::protein_day() — anchors a wrap-around eating window's
-- post-midnight tail to the day the window opened.
CREATE OR REPLACE FUNCTION fn_protein_day() RETURNS date AS $$
DECLARE
  ws int := COALESCE((SELECT value::int FROM app_settings WHERE key = 'protein_window_start'), 8);
  we int := COALESCE((SELECT value::int FROM app_settings WHERE key = 'protein_window_end'), 22);
  local_ts timestamp := now() AT TIME ZONE fn_tz();
  d date := local_ts::date;
  h int := EXTRACT(hour FROM local_ts)::int;
BEGIN
  IF we <= ws AND h < we THEN
    d := d - 1;
  END IF;
  RETURN d;
END;
$$ LANGUAGE plpgsql STABLE;

-- ── Aggregation, ports app/aggregates.py ────────────────────────────────────

CREATE OR REPLACE FUNCTION fn_window_series(p text, m text, days int)
RETURNS TABLE(day text, value double precision) AS $$
  SELECT day, value FROM metric_daily
  WHERE provider = p AND metric = m
    AND day BETWEEN (fn_today() - (days - 1))::text AND fn_today()::text
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_week_sum(p text, m text) RETURNS double precision AS $$
  SELECT ROUND(COALESCE(SUM(value), 0)::numeric, 2)::double precision FROM fn_window_series(p, m, 7)
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_month_sum(p text, m text) RETURNS double precision AS $$
  SELECT ROUND(COALESCE(SUM(value), 0)::numeric, 2)::double precision FROM fn_window_series(p, m, 30)
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_rolling_avg(p text, m text, win int) RETURNS double precision AS $$
  SELECT CASE WHEN win = 0 THEN 0 ELSE
    ROUND((COALESCE(SUM(value), 0) / win)::numeric, 2)::double precision
  END
  FROM fn_window_series(p, m, win)
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_last_active_day(p text, m text) RETURNS date AS $$
  SELECT day::date FROM metric_daily
  WHERE provider = p AND metric = m AND value > 0
    AND day >= (fn_today() - 370)::text
  ORDER BY day DESC LIMIT 1
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_days_since(p text, m text) RETURNS int AS $$
  SELECT CASE WHEN fn_last_active_day(p, m) IS NULL THEN NULL
    ELSE (fn_today() - fn_last_active_day(p, m))::int END
$$ LANGUAGE sql STABLE;

CREATE OR REPLACE FUNCTION fn_current_streak(p text, m text) RETURNS int AS $$
DECLARE
  cur date := fn_today();
  streak int := 0;
  has_today boolean;
BEGIN
  SELECT EXISTS(
    SELECT 1 FROM metric_daily
    WHERE provider = p AND metric = m AND day = fn_today()::text AND value > 0
  ) INTO has_today;
  IF NOT has_today THEN
    cur := cur - 1;
  END IF;
  LOOP
    EXIT WHEN NOT EXISTS(
      SELECT 1 FROM metric_daily
      WHERE provider = p AND metric = m AND day = cur::text AND value > 0
    );
    streak := streak + 1;
    cur := cur - 1;
  END LOOP;
  RETURN streak;
END;
$$ LANGUAGE plpgsql STABLE;

CREATE OR REPLACE FUNCTION fn_longest_streak(p text, m text) RETURNS int AS $$
DECLARE
  rec record;
  prev date;
  run int := 0;
  best int := 0;
BEGIN
  FOR rec IN
    SELECT day::date AS d FROM metric_daily
    WHERE provider = p AND metric = m AND value > 0
      AND day >= (fn_today() - 370)::text
    ORDER BY day::date
  LOOP
    IF prev IS NULL OR rec.d - prev > 1 THEN
      run := 1;
    ELSE
      run := run + 1;
    END IF;
    best := GREATEST(best, run);
    prev := rec.d;
  END LOOP;
  RETURN best;
END;
$$ LANGUAGE plpgsql STABLE;

-- ── Neglect evaluation, ports app/neglect.py::evaluate() ────────────────────

CREATE OR REPLACE FUNCTION fn_neglect_evaluate()
RETURNS TABLE(provider text, label text, severity text, message text, value double precision) AS $$
DECLARE
  r neglect_rule_specs%ROWTYPE;
  n int;
  avgv double precision;
  local_hour int := EXTRACT(hour FROM now() AT TIME ZONE fn_tz())::int;
  sev text;
  ago text;
BEGIN
  FOR r IN SELECT * FROM neglect_rule_specs LOOP
    IF r.kind = 'days_since' THEN
      n := fn_days_since(r.provider, r.metric);
      IF n IS NULL THEN
        provider := r.provider; label := r.label; severity := 'info';
        message := r.label || ': no activity recorded yet'; value := NULL;
        RETURN NEXT;
        CONTINUE;
      END IF;
      IF n = 0 THEN CONTINUE; END IF;
      sev := NULL;
      IF r.crit IS NOT NULL AND n >= r.crit THEN sev := 'critical';
      ELSIF r.warn IS NOT NULL AND n >= r.warn THEN sev := 'warning';
      END IF;
      IF sev IS NULL THEN CONTINUE; END IF;
      IF r.grace_hour IS NOT NULL AND sev = 'warning' AND r.warn IS NOT NULL
         AND n = r.warn::int AND local_hour < r.grace_hour THEN
        CONTINUE;
      END IF;
      ago := CASE WHEN n = 1 THEN 'yesterday' ELSE n::text || ' days ago' END;
      provider := r.provider; label := r.label; severity := sev;
      message := r.label || ': last activity ' || ago; value := n;
      RETURN NEXT;
    ELSIF r.kind = 'rolling_avg_below' THEN
      avgv := fn_rolling_avg(r.provider, r.metric, COALESCE(r.window_days, 7));
      IF r.threshold IS NULL OR avgv >= r.threshold THEN CONTINUE; END IF;
      provider := r.provider; label := r.label; severity := r.severity;
      message := r.label || ': ' || COALESCE(r.window_days, 7)::text || '-day average '
        || avgv::text || r.unit || ' (below ' || r.threshold::text || r.unit || ')';
      value := avgv;
      RETURN NEXT;
    END IF;
  END LOOP;
END;
$$ LANGUAGE plpgsql STABLE;

-- ── Views composing metadata + computed values ──────────────────────────────

CREATE OR REPLACE VIEW v_heatmap_index AS
  SELECT provider, metric, label, color, unit, scale_max, binary_metric
  FROM metric_specs WHERE heatmap;

CREATE OR REPLACE VIEW v_cards AS
  SELECT pc.provider, pc.metric, pc.title, ms.color, ms.unit, pc.show,
         fn_days_since(pc.provider, pc.metric) AS days_since,
         fn_current_streak(pc.provider, pc.metric) AS current_streak,
         fn_longest_streak(pc.provider, pc.metric) AS longest_streak,
         fn_week_sum(pc.provider, pc.metric) AS week_sum,
         fn_month_sum(pc.provider, pc.metric) AS month_sum
  FROM provider_cards pc
  JOIN metric_specs ms USING (provider, metric);
