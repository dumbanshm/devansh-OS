import 'package:supabase_flutter/supabase_flutter.dart';

/// Fill these in from your Supabase project (Settings → API). The anon key is
/// safe to ship in the APK — it can only do what RLS allows, and every table
/// is locked to the `authenticated` role (see supabase/migrations/*_rls.sql).
const supabaseUrl = String.fromEnvironment('SUPABASE_URL', defaultValue: '');
const supabaseAnonKey = String.fromEnvironment('SUPABASE_ANON_KEY', defaultValue: '');

SupabaseClient get supabase => Supabase.instance.client;

Future<void> initSupabase() async {
  await Supabase.initialize(url: supabaseUrl, anonKey: supabaseAnonKey);
}
