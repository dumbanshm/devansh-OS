import '../supabase_client.dart';

class ProteinBankItem {
  final int id;
  final String name;
  final double proteinG;
  final String? servingLabel;

  ProteinBankItem({required this.id, required this.name, required this.proteinG, this.servingLabel});

  factory ProteinBankItem.fromJson(Map<String, dynamic> json) => ProteinBankItem(
        id: json['id'] as int,
        name: json['name'] as String,
        proteinG: (json['protein_g'] as num).toDouble(),
        servingLabel: json['serving_label'] as String?,
      );
}

class ProteinService {
  /// Reusable food bank — same table the desktop Settings panel edits.
  Future<List<ProteinBankItem>> bank() async {
    final rows = await supabase.from('protein_bank').select().order('name');
    return rows.map((r) => ProteinBankItem.fromJson(r)).toList();
  }

  /// Log one serving of a bank item. `day` is omitted — the DB defaults it via
  /// fn_protein_day(), so this stays correct without duplicating the
  /// eating-window anchoring logic on the client.
  Future<void> logBankItem(ProteinBankItem item, {double servings = 1}) async {
    await supabase.from('protein_log').insert({
      'food_id': item.id,
      'food_name': item.name,
      'servings': servings,
      'grams': item.proteinG * servings,
      'logged_at': DateTime.now().toIso8601String(),
    });
  }

  /// Free-form entry (mirrors app/api/protein.py's non-bank branch).
  Future<void> logFreeForm(String name, double gramsPerServing, {double servings = 1}) async {
    await supabase.from('protein_log').insert({
      'food_id': null,
      'food_name': name,
      'servings': servings,
      'grams': gramsPerServing * servings,
      'logged_at': DateTime.now().toIso8601String(),
    });
  }

  Future<double> todayTotal(String today) async {
    final rows = await supabase.from('protein_log').select('grams').eq('day', today);
    double total = 0;
    for (final r in rows) {
      total += (r['grams'] as num).toDouble();
    }
    return total;
  }
}
