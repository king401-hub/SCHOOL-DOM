import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/endpoints.dart';
import '../auth/auth_provider.dart';
import '../storage/offline_cache.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/app_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  Map<String, dynamic>? _snapshot;
  bool _refreshing = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
  }

  Future<void> _refresh() async {
    setState(() => _refreshing = true);
    final auth = context.read<AuthProvider>();
    try {
      final data = await loadDashboard(auth.role);
      setState(() => _snapshot = data);
      await writeCache('dashboard', data, auth.scopeKey);
    } catch (_) {
      final cached = await readCache('dashboard', auth.scopeKey);
      if (cached?['data'] != null && mounted) {
        setState(() => _snapshot = cached!['data'] as Map<String, dynamic>?);
      }
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final metrics = (_snapshot?['metrics'] ?? {}) as Map<String, dynamic>;
    final school = (_snapshot?['school']?['name'] ??
            auth.schoolName ??
            'SchoolDom')
        .toString();

    return RefreshableScreen(
      onRefresh: _refresh,
      children: [
        if (_refreshing && _snapshot == null)
          const Center(child: CircularProgressIndicator(color: AppColors.primary)),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              school.toUpperCase(),
              style: const TextStyle(
                color: AppColors.primary,
                fontWeight: FontWeight.w900,
                fontSize: 12,
                letterSpacing: 1.2,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              'Welcome, ${auth.displayName ?? 'User'}',
              style: const TextStyle(
                color: AppColors.text,
                fontSize: 26,
                fontWeight: FontWeight.w900,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              '${auth.role ?? 'User'} workspace synced with SchoolDom.',
              style: const TextStyle(color: AppColors.muted),
            ),
          ],
        ),
        GridView.count(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisCount: 2,
          crossAxisSpacing: 14,
          mainAxisSpacing: 14,
          childAspectRatio: 1.4,
          children: [
            _MetricCard(
              label: 'Unread',
              value: (metrics['unread_messages'] ??
                      metrics['unread_inbox'] ??
                      0)
                  .toString(),
            ),
            _MetricCard(
              label: 'Notifications',
              value:
                  (metrics['unread_notifications'] ?? 0).toString(),
            ),
            _MetricCard(
              label: 'Students',
              value: (metrics['students'] ??
                      metrics['total_students'] ??
                      '-')
                  .toString(),
            ),
            _MetricCard(
              label: 'Exams',
              value: (metrics['exams'] ??
                      metrics['upcoming_exams'] ??
                      '-')
                  .toString(),
            ),
          ],
        ),
      ],
    );
  }
}

class _MetricCard extends StatelessWidget {
  final String label;
  final String value;
  const _MetricCard({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      children: [
        Text(label,
            style: const TextStyle(
                color: AppColors.mutedDark, fontWeight: FontWeight.w800)),
        Text(value,
            style: const TextStyle(
                color: AppColors.textDark,
                fontSize: 28,
                fontWeight: FontWeight.w900)),
      ],
    );
  }
}
