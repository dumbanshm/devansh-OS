import '../supabase_client.dart';

class Ritual {
  final int id;
  final String name;
  final String? doseLabel;

  Ritual({required this.id, required this.name, this.doseLabel});

  factory Ritual.fromJson(Map<String, dynamic> json) => Ritual(
        id: json['id'] as int,
        name: json['name'] as String,
        doseLabel: json['dose_label'] as String?,
      );
}

class RitualsService {
  Future<List<Ritual>> activeBank() async {
    final rows = await supabase
        .from('rituals_bank')
        .select()
        .eq('active', 1)
        .order('sort_order');
    return rows.map((r) => Ritual.fromJson(r)).toList();
  }

  /// ritual_ids already logged today. `today` is the device's local date —
  /// fine for just rendering current state; the authoritative day still comes
  /// from the DB default (fn_today()) on write.
  Future<Set<int>> doneToday(String today) async {
    final rows = await supabase.from('rituals_log').select('ritual_id').eq('day', today);
    return rows.map((r) => r['ritual_id'] as int).toSet();
  }

  Future<void> markDone(Ritual ritual, String today) async {
    await supabase.from('rituals_log').insert({
      'day': today,
      'ritual_id': ritual.id,
      'ritual_name': ritual.name,
      'logged_at': DateTime.now().toIso8601String(),
    });
  }

  Future<void> markUndone(Ritual ritual, String today) async {
    await supabase
        .from('rituals_log')
        .delete()
        .eq('day', today)
        .eq('ritual_id', ritual.id);
  }

  /// The DB's authoritative "today" (fn_today()), used to key writes so the
  /// server-side day-anchoring logic is the single source of truth.
  Future<String> today() async {
    final result = await supabase.rpc('fn_today');
    return result as String;
  }
}
