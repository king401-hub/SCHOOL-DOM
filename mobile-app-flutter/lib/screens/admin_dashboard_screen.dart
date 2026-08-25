import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/admin_endpoints.dart';
import '../api/endpoints.dart';
import '../auth/auth_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/avatar.dart';
import '../widgets/branded_refresh.dart';
import '../widgets/primary_button.dart';
import '../widgets/skeleton.dart';
import 'admin_announcements_screen.dart';
import 'admin_attendance_screen.dart';
import 'admin_staff_screen.dart';
import 'admin_students_screen.dart';
import 'create_exam_screen.dart';
import 'notifications_screen.dart';

/// Admin app's Home/Dashboard tab - composes 4 existing/lightly-extended
/// endpoints in parallel (dashboard_snapshot for school/announcements/
/// recent students, finance admin_overview for real ₦ amounts, hr_snapshot
/// for staff counts, and the new admin_attendance_summary for today's
/// present/absent/late/not-marked) rather than one large new backend view.
class AdminDashboardScreen extends StatefulWidget {
  const AdminDashboardScreen({super.key});

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen> {
  Map<String, dynamic>? _dashboard;
  Map<String, dynamic>? _finance;
  Map<String, dynamic>? _hr;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        loadDashboard('admin'),
        loadFinanceOverview(),
        loadHrOverview(),
      ]);
      setState(() {
        _dashboard = results[0];
        _finance = results[1];
        _hr = results[2];
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _naira(dynamic value) {
    final amount = double.tryParse(value?.toString() ?? '') ?? 0;
    final whole = amount.truncate().toString();
    final withCommas = whole.replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',');
    return '₦$withCommas';
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final school = (_dashboard?['school'] ?? {}) as Map<String, dynamic>;
    final metrics = (_dashboard?['metrics'] ?? {}) as Map<String, dynamic>;
    final announcements = (_dashboard?['announcements'] ?? []) as List<dynamic>;
    final recentStudents = (_dashboard?['recent_students'] ?? []) as List<dynamic>;
    final hrSummary = (_hr?['summary'] ?? {}) as Map<String, dynamic>;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
              child: Row(
                children: [
                  Avatar(
                    name: (auth.displayName ?? 'Admin').toString(),
                    pictureUrl: school['logo'] as String?,
                    size: 46,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text((school['name'] ?? auth.schoolName ?? 'SchoolDom').toString(),
                            style: TextStyle(color: AppColors.text, fontSize: 16, fontWeight: FontWeight.w900)),
                        Text('Good morning, Admin 👋', style: TextStyle(color: AppColors.muted, fontSize: 12)),
                      ],
                    ),
                  ),
                  GestureDetector(
                    onTap: () async {
                      await Navigator.of(context).push(MaterialPageRoute(builder: (_) => const NotificationsScreen()));
                      _load();
                    },
                    child: Container(
                      width: 42,
                      height: 42,
                      decoration: BoxDecoration(
                        color: AppColors.surfaceSoft,
                        shape: BoxShape.circle,
                        border: Border.all(color: AppColors.border),
                      ),
                      child: Icon(Icons.notifications_outlined, color: AppColors.muted),
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: _loading && _dashboard == null
                  ? const SkeletonList()
                  : _error != null && _dashboard == null
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(24),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(Icons.error_outline, color: AppColors.danger, size: 40),
                                const SizedBox(height: 12),
                                const Text("Couldn't load your dashboard.",
                                    style: TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
                                const SizedBox(height: 16),
                                SizedBox(width: 160, child: PrimaryButton(title: 'Retry', onPressed: _load)),
                              ],
                            ),
                          ),
                        )
                      : BrandedRefresh(
                          onRefresh: _load,
                          showSpinner: _loading,
                          child: ListView(
                            padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
                            children: [
                              Text('Overview', style: TextStyle(color: AppColors.text, fontSize: 16, fontWeight: FontWeight.w900)),
                              const SizedBox(height: 12),
                              Row(
                                children: [
                                  Expanded(
                                    child: _OverviewCard(
                                      label: 'Fees Collected',
                                      value: _naira(_finance?['amount_received']),
                                      icon: Icons.account_balance_wallet_outlined,
                                      accent: AppColors.brandGreen,
                                    ),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: _OverviewCard(
                                      label: 'Outstanding Fees',
                                      value: _naira(_finance?['outstanding_balance']),
                                      icon: Icons.receipt_long_outlined,
                                      accent: AppColors.warning,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              Row(
                                children: [
                                  Expanded(
                                    child: _OverviewCard(
                                      label: 'Total Students',
                                      value: '${metrics['active_students'] ?? 0}',
                                      icon: Icons.groups_outlined,
                                      accent: AppColors.primary,
                                    ),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: _OverviewCard(
                                      label: 'Total Staff',
                                      value: '${hrSummary['total_staff'] ?? 0}',
                                      icon: Icons.badge_outlined,
                                      accent: AppColors.secondary,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 24),
                              Text('Quick Actions',
                                  style: TextStyle(color: AppColors.text, fontSize: 16, fontWeight: FontWeight.w900)),
                              const SizedBox(height: 12),
                              GridView.count(
                                shrinkWrap: true,
                                physics: const NeverScrollableScrollPhysics(),
                                crossAxisCount: 4,
                                crossAxisSpacing: 10,
                                mainAxisSpacing: 10,
                                childAspectRatio: 0.85,
                                children: [
                                  _QuickAction(
                                    label: 'Add Student',
                                    icon: Icons.person_add_alt_1,
                                    onTap: () => Navigator.of(context)
                                        .push(MaterialPageRoute(builder: (_) => const AdminStudentsScreen())),
                                  ),
                                  _QuickAction(
                                    label: 'Add Staff',
                                    icon: Icons.badge_outlined,
                                    onTap: () => Navigator.of(context)
                                        .push(MaterialPageRoute(builder: (_) => const AdminStaffScreen())),
                                  ),
                                  _QuickAction(
                                    label: 'Create Exam',
                                    icon: Icons.quiz_outlined,
                                    onTap: () async {
                                      final options = (await loadExams())['options'] as Map<String, dynamic>? ?? {};
                                      if (!context.mounted) return;
                                      Navigator.of(context).push(MaterialPageRoute(
                                        builder: (_) => CreateExamScreen(
                                          classes: ((options['classes'] ?? []) as List<dynamic>).cast<Map<String, dynamic>>(),
                                          subjects: ((options['subjects'] ?? []) as List<dynamic>).cast<Map<String, dynamic>>(),
                                        ),
                                      ));
                                    },
                                  ),
                                  _QuickAction(
                                    label: 'Send Notice',
                                    icon: Icons.campaign_outlined,
                                    onTap: () => Navigator.of(context)
                                        .push(MaterialPageRoute(builder: (_) => const AdminAnnouncementsScreen())),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 24),
                              Row(
                                children: [
                                  Text("Today's Summary",
                                      style: TextStyle(color: AppColors.text, fontSize: 16, fontWeight: FontWeight.w900)),
                                  const Spacer(),
                                  GestureDetector(
                                    onTap: () => Navigator.of(context)
                                        .push(MaterialPageRoute(builder: (_) => const AdminAttendanceScreen())),
                                    child: Padding(
                                      padding: const EdgeInsets.symmetric(vertical: 8),
                                      child: Text('View all',
                                          style: TextStyle(color: AppColors.primary, fontSize: 12, fontWeight: FontWeight.w800)),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 8),
                              AppCard(
                                children: [
                                  _SummaryRow(label: 'Pending fees', value: '${_finance?['pending_fees'] ?? 0}'),
                                  _SummaryRow(label: 'Overdue fees', value: '${_finance?['overdue_fees'] ?? 0}'),
                                  _SummaryRow(label: "Today's staff present", value: '${hrSummary['today_present'] ?? 0}'),
                                ],
                              ),
                              const SizedBox(height: 24),
                              Text('Announcements',
                                  style: TextStyle(color: AppColors.text, fontSize: 16, fontWeight: FontWeight.w900)),
                              const SizedBox(height: 12),
                              if (announcements.isEmpty)
                                Text('No announcements.', style: TextStyle(color: AppColors.muted))
                              else
                                for (final raw in announcements) ...[
                                  _AnnouncementRow(item: raw as Map<String, dynamic>),
                                  const SizedBox(height: 10),
                                ],
                              const SizedBox(height: 24),
                              Text('Recent Students',
                                  style: TextStyle(color: AppColors.text, fontSize: 16, fontWeight: FontWeight.w900)),
                              const SizedBox(height: 12),
                              if (recentStudents.isEmpty)
                                Text('No recent students.', style: TextStyle(color: AppColors.muted))
                              else
                                for (final raw in recentStudents.take(5)) ...[
                                  _RecentStudentRow(item: raw as Map<String, dynamic>),
                                  const SizedBox(height: 10),
                                ],
                            ],
                          ),
                        ),
            ),
          ],
        ),
      ),
    );
  }
}

class _OverviewCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color accent;
  const _OverviewCard({required this.label, required this.value, required this.icon, required this.accent});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      elevated: true,
      padding: const EdgeInsets.all(14),
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [AppColors.card, accent.withValues(alpha: 0.07)],
      ),
      children: [
        Container(
          width: 30,
          height: 30,
          decoration: BoxDecoration(color: accent.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(10)),
          alignment: Alignment.center,
          child: Icon(icon, size: 15, color: accent),
        ),
        const SizedBox(height: 6),
        Text(label, style: const TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w800, fontSize: 11)),
        Text(value,
            style: const TextStyle(color: AppColors.textDark, fontSize: 17, fontWeight: FontWeight.w900),
            maxLines: 1,
            overflow: TextOverflow.ellipsis),
      ],
    );
  }
}

class _QuickAction extends StatelessWidget {
  final String label;
  final IconData icon;
  final VoidCallback onTap;
  const _QuickAction({required this.label, required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Container(
          decoration: BoxDecoration(color: AppColors.card, borderRadius: BorderRadius.circular(16)),
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: const BoxDecoration(gradient: AppGradients.brand, shape: BoxShape.circle),
                alignment: Alignment.center,
                child: Icon(icon, color: Colors.white, size: 18),
              ),
              const SizedBox(height: 6),
              Text(label,
                  textAlign: TextAlign.center,
                  maxLines: 2,
                  style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w700, fontSize: 10)),
            ],
          ),
        ),
      ),
    );
  }
}

class _SummaryRow extends StatelessWidget {
  final String label;
  final String value;
  const _SummaryRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(Icons.circle, size: 5, color: AppColors.muted),
        const SizedBox(width: 8),
        Expanded(child: Text(label, style: const TextStyle(color: AppColors.mutedDark, fontSize: 13))),
        Text(value, style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w800, fontSize: 13)),
      ],
    );
  }
}

class _AnnouncementRow extends StatelessWidget {
  final Map<String, dynamic> item;
  const _AnnouncementRow({required this.item});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      children: [
        Text((item['title'] ?? 'Announcement').toString(),
            style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
      ],
    );
  }
}

class _RecentStudentRow extends StatelessWidget {
  final Map<String, dynamic> item;
  const _RecentStudentRow({required this.item});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      children: [
        Row(
          children: [
            Avatar(name: (item['name'] ?? '').toString()),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text((item['name'] ?? 'Student').toString(),
                      style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
                  Text('${item['student_id'] ?? ''} · ${item['class_name'] ?? ''}',
                      style: const TextStyle(color: AppColors.mutedDark, fontSize: 12)),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }
}
