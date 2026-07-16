import 'package:flutter/material.dart';
import '../api/endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/app_screen.dart';

class ExamsScreen extends StatefulWidget {
  const ExamsScreen({super.key});

  @override
  State<ExamsScreen> createState() => _ExamsScreenState();
}

class _ExamsScreenState extends State<ExamsScreen> {
  List<dynamic> _items = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await loadExams();
      setState(() =>
          _items = (data['exams'] ?? data['upcoming_exams'] ?? []) as List<dynamic>);
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
          'Exams',
          style: TextStyle(
              color: AppColors.text,
              fontSize: 28,
              fontWeight: FontWeight.w900),
        ),
        if (_error != null)
          Text(_error!, style: const TextStyle(color: AppColors.danger)),
        if (_items.isEmpty && _error == null)
          const Text('No exams found.',
              style: TextStyle(color: AppColors.muted)),
        for (final item in _items)
          AppCard(
            children: [
              Text(
                ((item as Map)['title'] ?? item['subject'] ?? 'Exam').toString(),
                style: const TextStyle(
                    color: AppColors.textDark,
                    fontWeight: FontWeight.w900),
              ),
              Text(
                (item['start_date'] ?? item['due_date'] ?? item['status'] ?? 'Ready')
                    .toString(),
                style: const TextStyle(color: AppColors.mutedDark),
              ),
            ],
          ),
      ],
    );
  }
}
