-- Row Level Security: this is a single-tenant app (there will only ever be one
-- legitimate signed-in user, you). FastAPI connects as the `postgres` role and
-- bypasses RLS entirely (trusted server component holding a secret
-- DATABASE_URL). Flutter connects as `authenticated` after signing in with the
-- one Supabase Auth account, and gets a blanket allow policy per table — no
-- per-row user_id ownership needed. metric_specs/provider_cards/
-- neglect_rule_specs are read-only to `authenticated` since only FastAPI ever
-- writes them.

ALTER TABLE metric_daily        ENABLE ROW LEVEL SECURITY;
ALTER TABLE events              ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_state          ENABLE ROW LEVEL SECURITY;
ALTER TABLE protein_bank        ENABLE ROW LEVEL SECURITY;
ALTER TABLE protein_log         ENABLE ROW LEVEL SECURITY;
ALTER TABLE app_settings        ENABLE ROW LEVEL SECURITY;
ALTER TABLE rituals_bank        ENABLE ROW LEVEL SECURITY;
ALTER TABLE rituals_log         ENABLE ROW LEVEL SECURITY;
ALTER TABLE milestones          ENABLE ROW LEVEL SECURITY;
ALTER TABLE metric_specs        ENABLE ROW LEVEL SECURITY;
ALTER TABLE provider_cards      ENABLE ROW LEVEL SECURITY;
ALTER TABLE neglect_rule_specs  ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated full access" ON metric_daily
  FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "authenticated full access" ON events
  FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "authenticated full access" ON sync_state
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "authenticated full access" ON protein_bank
  FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "authenticated full access" ON protein_log
  FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "authenticated read settings" ON app_settings
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "authenticated full access" ON rituals_bank
  FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "authenticated full access" ON rituals_log
  FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "authenticated full access" ON milestones
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

CREATE POLICY "authenticated read catalog" ON metric_specs
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "authenticated read catalog" ON provider_cards
  FOR SELECT TO authenticated USING (true);
CREATE POLICY "authenticated read catalog" ON neglect_rule_specs
  FOR SELECT TO authenticated USING (true);

-- fn_neglect_evaluate() and fn_today()/fn_protein_day() are called via RPC by
-- Flutter — grant execute to authenticated (they're STABLE/read-only).
GRANT EXECUTE ON FUNCTION fn_neglect_evaluate() TO authenticated;
GRANT EXECUTE ON FUNCTION fn_today() TO authenticated;
GRANT EXECUTE ON FUNCTION fn_protein_day() TO authenticated;
