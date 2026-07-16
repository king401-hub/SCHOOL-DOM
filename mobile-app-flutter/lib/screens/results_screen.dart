import 'package:flutter/material.dart';
import '../api/endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/app_screen.dart';

class ResultsScreen extends StatefulWidget {
  const ResultsScreen({super.key});

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> {
  List<dynamic> _results = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await loadResults();
      setState(() => _results =
          (data['results'] ?? data['report_card']?['subjects'] ?? [])
              as List<dynamic>);
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    return RefreshableScreen(
      onRefresh: _load,
      children: [
        const Text(
          'Results',
          style: TextStyle(
              color: AppColors.text,
              fontSize: 28,
              fontWeight: FontWeight.w900),
        ),
        if (_error != null)
          Text(_error!, style: const TextStyle(color: AppColors.danger)),
        if (_results.isEmpty && _error == null)
          const Text('No results found.',
              style: TextStyle(color: AppColors.muted)),
        for (final item in _results)
          AppCard(
            children: [
              Text(
                ((item as Map)['subject'] ?? item['name'] ?? 'Subject').toString(),
                style: const TextStyle(
                    color: AppColors.textDark,
                    fontWeight: FontWeight.w900),
              ),
              Text(
                (item['score'] ?? item['total'] ?? item['grade'] ?? 'Pending')
                    .toString(),
                style: const TextStyle(
                    color: AppColors.primary,
                    fontSize: 20,
                    fontWeight: FontWeight.w900),
              ),
            ],
          ),
      ],
    );
  }
}
