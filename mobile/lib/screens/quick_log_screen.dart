import 'package:flutter/material.dart';

import '../services/protein_service.dart';
import '../services/rituals_service.dart';
import 'dashboard_screen.dart';

/// Screen 1 (default landing): fast logging. Protein bank as tappable chips,
/// rituals as a checklist, and a small button into the full dashboard mirror.
class QuickLogScreen extends StatefulWidget {
  const QuickLogScreen({super.key});

  @override
  State<QuickLogScreen> createState() => _QuickLogScreenState();
}

class _QuickLogScreenState extends State<QuickLogScreen> {
  final _protein = ProteinService();
  final _rituals = RitualsService();

  List<ProteinBankItem> _bank = [];
  List<Ritual> _ritualBank = [];
  Set<int> _doneToday = {};
  String? _today;
  double _proteinToday = 0;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    final today = await _rituals.today();
    final results = await Future.wait([
      _protein.bank(),
      _rituals.activeBank(),
      _rituals.doneToday(today),
      _protein.todayTotal(today),
    ]);
    if (!mounted) return;
    setState(() {
      _today = today;
      _bank = results[0] as List<ProteinBankItem>;
      _ritualBank = results[1] as List<Ritual>;
      _doneToday = results[2] as Set<int>;
      _proteinToday = results[3] as double;
      _loading = false;
    });
  }

  Future<void> _logProtein(ProteinBankItem item) async {
    await _protein.logBankItem(item);
    final total = await _protein.todayTotal(_today!);
    if (!mounted) return;
    setState(() => _proteinToday = total);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Logged ${item.name}'), duration: const Duration(seconds: 1)),
    );
  }

  Future<void> _toggleRitual(Ritual ritual) async {
    final done = _doneToday.contains(ritual.id);
    if (done) {
      await _rituals.markUndone(ritual, _today!);
      setState(() => _doneToday.remove(ritual.id));
    } else {
      await _rituals.markDone(ritual, _today!);
      setState(() => _doneToday.add(ritual.id));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Quick Log')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text('Protein — ${_proteinToday.round()}g today', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: _bank
                        .map((item) => ActionChip(
                              label: Text('${item.name} (+${item.proteinG.round()}g)'),
                              onPressed: () => _logProtein(item),
                            ))
                        .toList(),
                  ),
                  const SizedBox(height: 28),
                  Text('Rituals', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  ..._ritualBank.map((r) => CheckboxListTile(
                        value: _doneToday.contains(r.id),
                        onChanged: (_) => _toggleRitual(r),
                        title: Text(r.name),
                        subtitle: r.doseLabel != null ? Text(r.doseLabel!) : null,
                        controlAffinity: ListTileControlAffinity.leading,
                      )),
                  const SizedBox(height: 32),
                  Center(
                    child: FilledButton.icon(
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute(builder: (_) => const DashboardScreen()),
                      ),
                      icon: const Icon(Icons.dashboard),
                      label: const Text('Enter the app'),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}
