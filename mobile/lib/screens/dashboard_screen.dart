import 'package:flutter/material.dart';

import '../services/dashboard_service.dart';

/// Screen 2: the dashboard mirror — neglect banner, KPI cards, heatmaps,
/// timeline. No detail-sidebar / Settings / Life-calendar (desktop-only).
/// Everything here reads Supabase directly, so it works even if FastAPI /
/// the laptop is off.
class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final _service = DashboardService();

  List<NeglectItem> _neglect = [];
  List<KpiCard> _cards = [];
  List<Map<String, dynamic>> _timeline = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final results = await Future.wait([
      _service.neglect(),
      _service.cards(),
      _service.timeline(),
    ]);
    if (!mounted) return;
    setState(() {
      _neglect = results[0] as List<NeglectItem>;
      _cards = results[1] as List<KpiCard>;
      _timeline = results[2] as List<Map<String, dynamic>>;
      _loading = false;
    });
  }

  Color _severityColor(String severity) {
    switch (severity) {
      case 'critical':
        return Colors.redAccent;
      case 'warning':
        return Colors.orangeAccent;
      default:
        return Colors.blueGrey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Devansh OS')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  if (_neglect.isNotEmpty) ...[
                    Text('Neglect', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 8),
                    ..._neglect.map((n) => Card(
                          color: _severityColor(n.severity).withOpacity(0.15),
                          child: ListTile(
                            leading: Icon(Icons.warning_amber, color: _severityColor(n.severity)),
                            title: Text(n.label),
                            subtitle: Text(n.message),
                          ),
                        )),
                    const SizedBox(height: 24),
                  ],
                  Text('Systems', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  GridView.count(
                    crossAxisCount: 2,
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    childAspectRatio: 1.4,
                    crossAxisSpacing: 8,
                    mainAxisSpacing: 8,
                    children: _cards
                        .map((c) => Card(
                              child: Padding(
                                padding: const EdgeInsets.all(12),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(c.title, style: const TextStyle(fontWeight: FontWeight.bold)),
                                    const Spacer(),
                                    Text(c.daysSince == null
                                        ? 'no activity yet'
                                        : c.daysSince == 0
                                            ? 'today'
                                            : '${c.daysSince}d ago'),
                                    Text('streak ${c.currentStreak}', style: Theme.of(context).textTheme.bodySmall),
                                  ],
                                ),
                              ),
                            ))
                        .toList(),
                  ),
                  const SizedBox(height: 24),
                  Text('Timeline', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  ..._timeline.take(30).map((e) => ListTile(
                        dense: true,
                        title: Text(e['title'] as String? ?? ''),
                        subtitle: Text('${e['provider']} · ${e['day']}'),
                      )),
                ],
              ),
            ),
    );
  }
}
