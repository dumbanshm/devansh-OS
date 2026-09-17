import '../supabase_client.dart';

class NeglectItem {
  final String provider;
  final String label;
  final String severity;
  final String message;

  NeglectItem({required this.provider, required this.label, required this.severity, required this.message});

  factory NeglectItem.fromJson(Map<String, dynamic> json) => NeglectItem(
        provider: json['provider'] as String,
        label: json['label'] as String,
        severity: json['severity'] as String,
        message: json['message'] as String,
      );
}

class KpiCard {
  final String provider;
  final String metric;
  final String title;
  final String color;
  final int? daysSince;
  final int currentStreak;
  final double weekSum;
  final double monthSum;

  KpiCard({
    required this.provider,
    required this.metric,
    required this.title,
    required this.color,
    required this.daysSince,
    required this.currentStreak,
    required this.weekSum,
    required this.monthSum,
  });

  factory KpiCard.fromJson(Map<String, dynamic> json) => KpiCard(
        provider: json['provider'] as String,
        metric: json['metric'] as String,
        title: json['title'] as String,
        color: json['color'] as String,
        daysSince: json['days_since'] as int?,
        currentStreak: (json['current_streak'] as num?)?.toInt() ?? 0,
        weekSum: (json['week_sum'] as num?)?.toDouble() ?? 0,
        monthSum: (json['month_sum'] as num?)?.toDouble() ?? 0,
      );
}

class HeatmapMetric {
  final String provider;
  final String metric;
  final String label;
  final String color;

  HeatmapMetric({required this.provider, required this.metric, required this.label, required this.color});

  factory HeatmapMetric.fromJson(Map<String, dynamic> json) => HeatmapMetric(
        provider: json['provider'] as String,
        metric: json['metric'] as String,
        label: json['label'] as String,
        color: json['color'] as String,
      );
}

/// Reads the dashboard directly from Supabase — no dependency on FastAPI being
/// up (that's the whole point of the standalone-mobile-dashboard decision).
class DashboardService {
  Future<List<NeglectItem>> neglect() async {
    final rows = await supabase.rpc('fn_neglect_evaluate');
    return (rows as List).map((r) => NeglectItem.fromJson(r as Map<String, dynamic>)).toList();
  }

  Future<List<KpiCard>> cards() async {
    final rows = await supabase.from('v_cards').select();
    return rows.map((r) => KpiCard.fromJson(r)).toList();
  }

  Future<List<HeatmapMetric>> heatmapIndex() async {
    final rows = await supabase.from('v_heatmap_index').select();
    return rows.map((r) => HeatmapMetric.fromJson(r)).toList();
  }

  /// Raw {day: value} for one metric in a date range; caller zero-fills.
  Future<Map<String, double>> series(String provider, String metric, String startDay, String endDay) async {
    final rows = await supabase
        .from('metric_daily')
        .select('day, value')
        .eq('provider', provider)
        .eq('metric', metric)
        .gte('day', startDay)
        .lte('day', endDay);
    return {for (final r in rows) r['day'] as String: (r['value'] as num).toDouble()};
  }

  Future<List<Map<String, dynamic>>> timeline({int days = 7}) async {
    final start = DateTime.now().subtract(Duration(days: days - 1));
    final startDay = start.toIso8601String().split('T').first;
    final rows = await supabase
        .from('events')
        .select()
        .gte('day', startDay)
        .order('ts', ascending: false)
        .limit(500);
    return List<Map<String, dynamic>>.from(rows);
  }
}
