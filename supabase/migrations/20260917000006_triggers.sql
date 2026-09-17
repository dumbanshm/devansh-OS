-- Recompute triggers: makes metric_daily correct regardless of which client
-- (FastAPI or Flutter) wrote the log row. Ports app/api/protein.py::_recompute()
-- and app/providers/rituals.py's recompute_day()/refresh_metrics().

-- ── Protein ──────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION fn_protein_recompute_day(p_day text) RETURNS void AS $$
DECLARE
  total double precision;
BEGIN
  SELECT COALESCE(SUM(grams), 0) INTO total FROM protein_log WHERE day = p_day;
  INSERT INTO metric_daily (provider, metric, day, value, source, updated_at)
  VALUES ('protein', 'protein_g', p_day, total, 'manual', now()::text)
  ON CONFLICT (provider, metric, day) DO UPDATE
    SET value = excluded.value, source = excluded.source, updated_at = excluded.updated_at;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trg_protein_recompute() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    PERFORM fn_protein_recompute_day(OLD.day);
    RETURN OLD;
  END IF;
  PERFORM fn_protein_recompute_day(NEW.day);
  IF TG_OP = 'UPDATE' AND OLD.day IS DISTINCT FROM NEW.day THEN
    PERFORM fn_protein_recompute_day(OLD.day);
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS protein_log_recompute ON protein_log;
CREATE TRIGGER protein_log_recompute
  AFTER INSERT OR UPDATE OR DELETE ON protein_log
  FOR EACH ROW EXECUTE FUNCTION trg_protein_recompute();

-- ── Rituals ──────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION fn_rituals_recompute_day(p_day text) RETURNS void AS $$
DECLARE
  r record;
  done_count int := 0;
  is_done boolean;
BEGIN
  FOR r IN SELECT id FROM rituals_bank WHERE active = 1 LOOP
    SELECT EXISTS(
      SELECT 1 FROM rituals_log WHERE day = p_day AND ritual_id = r.id
    ) INTO is_done;
    INSERT INTO metric_daily (provider, metric, day, value, source, updated_at)
    VALUES ('rituals', 'r_' || r.id, p_day, CASE WHEN is_done THEN 1.0 ELSE 0.0 END, 'manual', now()::text)
    ON CONFLICT (provider, metric, day) DO UPDATE
      SET value = excluded.value, source = excluded.source, updated_at = excluded.updated_at;
    IF is_done THEN done_count := done_count + 1; END IF;
  END LOOP;
  INSERT INTO metric_daily (provider, metric, day, value, source, updated_at)
  VALUES ('rituals', 'adherence', p_day, done_count, 'manual', now()::text)
  ON CONFLICT (provider, metric, day) DO UPDATE
    SET value = excluded.value, source = excluded.source, updated_at = excluded.updated_at;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trg_rituals_recompute() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    PERFORM fn_rituals_recompute_day(OLD.day);
    RETURN OLD;
  END IF;
  PERFORM fn_rituals_recompute_day(NEW.day);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS rituals_log_recompute ON rituals_log;
CREATE TRIGGER rituals_log_recompute
  AFTER INSERT OR DELETE ON rituals_log
  FOR EACH ROW EXECUTE FUNCTION trg_rituals_recompute();

-- Rebuilds metric_specs/provider_cards/neglect_rule_specs for provider='rituals'
-- from the active bank — ports RitualsProvider.refresh_metrics(). Runs whenever
-- the bank changes, from either client.
CREATE OR REPLACE FUNCTION fn_rituals_refresh_metrics() RETURNS void AS $$
DECLARE
  active_count int;
  r record;
BEGIN
  SELECT COUNT(*) INTO active_count FROM rituals_bank WHERE active = 1;

  DELETE FROM metric_specs WHERE provider = 'rituals';
  INSERT INTO metric_specs (provider, metric, label, color, unit, heatmap, scale_max, binary_metric)
  VALUES ('rituals', 'adherence', 'Rituals', 'cyan', '', true, GREATEST(active_count, 1), false);

  FOR r IN SELECT * FROM rituals_bank WHERE active = 1 LOOP
    INSERT INTO metric_specs (provider, metric, label, color, unit, heatmap, scale_max, binary_metric)
    VALUES ('rituals', 'r_' || r.id, r.name, 'cyan', '', false, NULL, true);
  END LOOP;

  DELETE FROM neglect_rule_specs WHERE provider = 'rituals';
  FOR r IN SELECT * FROM rituals_bank WHERE active = 1 LOOP
    INSERT INTO neglect_rule_specs (provider, metric, kind, label, warn, crit, grace_hour)
    VALUES ('rituals', 'r_' || r.id, 'days_since', r.name, r.interval_days, r.interval_days * 2, 18);
  END LOOP;

  PERFORM fn_rituals_recompute_day(fn_today()::text);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trg_rituals_bank_refresh() RETURNS trigger AS $$
BEGIN
  PERFORM fn_rituals_refresh_metrics();
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS rituals_bank_refresh ON rituals_bank;
CREATE TRIGGER rituals_bank_refresh
  AFTER INSERT OR UPDATE OR DELETE ON rituals_bank
  FOR EACH ROW EXECUTE FUNCTION trg_rituals_bank_refresh();

-- Seed rituals' metric_specs/neglect_rule_specs once at migration time, since
-- there's no bank row change to fire the trigger on a fresh project.
SELECT fn_rituals_refresh_metrics();
