import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/endpoints.dart';
import '../auth/auth_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import 'lesson_notes_screen.dart';
import 'notifications_screen.dart';
import 'timetable_screen.dart';

/// Teacher's "Home" tab - a mobile take on the web teacher dashboard's
/// overview: key metrics, upcoming assessments, and announcements. Pulled
/// from the same /api/app/teacher/dashboard/ endpoint the web app uses.
class TeacherHomeScreen extends StatefulWidget {
  const TeacherHomeScreen({super.key});

  @override
  State<TeacherHomeScreen> createState() => _TeacherHomeScreenState();
}

class _TeacherHomeScreenState extends State<TeacherHomeScreen> {
  Map<String, dynamic>? _data;
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
      final data = await loadDashboard('teacher');
      setState(() => _data = data);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String _formatDate(dynamic raw) {
    if (raw == null) return '';
    final parsed = DateTime.tryParse(raw.toString());
    if (parsed == null) return raw.toString();
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
    ];
    return '${months[parsed.month - 1]} ${parsed.day}';
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final profile = (_data?['profile'] ?? {}) as Map<String, dynamic>;
    final metrics = (_data?['metrics'] ?? {}) as Map<String, dynamic>;
    final upcoming = (_data?['upcoming_assessments'] ?? []) as List<dynamic>;
    final announcements = (_data?['announcements'] ?? []) as List<dynamic>;
    final subjectsTaught = (profile['subjects_taught'] ?? []) as List<dynamic>;
    final classesTaught =
        ((_data?['options'] as Map<String, dynamic>?)?['classes'] ?? []) as List<dynamic>;
    final monthlySalary = profile['monthly_salary'];
    final schoolName =
        ((_data?['school'] as Map<String, dynamic>?)?['name'] ?? auth.schoolName ?? 'SchoolDom')
            .toString();

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          color: AppColors.primary,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
            children: [
              Text(
                schoolName.toUpperCase(),
                style: const TextStyle(
                  color: AppColors.primary,
                  fontWeight: FontWeight.w900,
                  fontSize: 12,
                  letterSpacing: 1.2,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'Welcome, ${profile['name'] ?? auth.displayName ?? 'Teacher'}',
                style: TextStyle(color: AppColors.text, fontSize: 26, fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 20),
              if (_loading && _data == null)
                const Padding(
                  padding: EdgeInsets.only(top: 40),
                  child: Center(child: CircularProgressIndicator(color: AppColors.primary)),
                ),
              if (_error != null)
                Text(_error!, style: const TextStyle(color: AppColors.danger)),
              if (_data != null) ...[
                _TeachingCard(
                  monthlySalary: monthlySalary,
                  subjects: subjectsTaught,
                  classes: classesTaught,
                ),
                const SizedBox(height: 20),
                GridView.count(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  crossAxisCount: 2,
                  crossAxisSpacing: 14,
                  mainAxisSpacing: 14,
                  childAspectRatio: 1.5,
                  children: [
                    _StatCard(
                      label: 'Upcoming assessments',
                      value: (metrics['upcoming_assessments'] ?? 0).toString(),
                    ),
                    _StatCard(
                      label: 'Needs grading',
                      value: (metrics['pending_submissions'] ?? 0).toString(),
                    ),
                    _StatCard(
                      label: 'Unread messages',
                      value: (metrics['unread_inbox'] ?? 0).toString(),
                    ),
                    _StatCard(
                      label: 'Notifications',
                      value: (metrics['unread_notifications'] ?? 0).toString(),
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute(builder: (_) => const NotificationsScreen()),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                Row(
                  children: [
                    Expanded(
                      child: _QuickActionCard(
                        icon: Icons.calendar_month_outlined,
                        label: 'Timetable',
                        onTap: () => Navigator.of(context).push(
                          MaterialPageRoute(builder: (_) => const TimetableScreen()),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: _QuickActionCard(
                        icon: Icons.edit_note_outlined,
                        label: 'Lesson Notes',
                        onTap: () => Navigator.of(context).push(
                          MaterialPageRoute(builder: (_) => const LessonNotesScreen()),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                Text('Upcoming assessments',
                    style: TextStyle(color: AppColors.text, fontSize: 16, fontWeight: FontWeight.w900)),
                const SizedBox(height: 12),
                if (upcoming.isEmpty)
                  Text('No upcoming assessments.', style: TextStyle(color: AppColors.muted))
                else
                  for (final raw in upcoming) ...[
                    _AssessmentCard(item: raw as Map<String, dynamic>, formatDate: _formatDate),
                    const SizedBox(height: 10),
                  ],
                const SizedBox(height: 12),
                Text('Announcements',
                    style: TextStyle(color: AppColors.text, fontSize: 16, fontWeight: FontWeight.w900)),
                const SizedBox(height: 12),
                if (announcements.isEmpty)
                  Text('No announcements.', style: TextStyle(color: AppColors.muted))
                else
                  for (final raw in announcements) ...[
                    _AnnouncementCard(item: raw as Map<String, dynamic>),
                    const SizedBox(height: 10),
                  ],
              ],
            ],
          ),
        ),
      ),
    );
  }
}

String _formatNaira(dynamic value) {
  final amount = double.tryParse(value?.toString() ?? '') ?? 0;
  final whole = amount.truncate().abs().toString();
  final withCommas = whole.replaceAllMapped(RegExp(r'\B(?=(\d{3})+(?!\d))'), (m) => ',');
  final cents = ((amount.abs() - amount.truncate().abs()) * 100).round().toString().padLeft(2, '0');
  return '${amount < 0 ? '-' : ''}₦$withCommas.$cents';
}

class _TeachingCard extends StatelessWidget {
  final dynamic monthlySalary;
  final List<dynamic> subjects;
  final List<dynamic> classes;
  const _TeachingCard({required this.monthlySalary, required this.subjects, required this.classes});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      children: [
        if (monthlySalary != null) ...[
          const Text('Monthly salary',
              style: TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w800, fontSize: 12)),
          Text(_formatNaira(monthlySalary),
              style: const TextStyle(color: AppColors.textDark, fontSize: 22, fontWeight: FontWeight.w900)),
          Divider(height: 24, color: AppColors.border),
        ],
        const Text('Subjects',
            style: TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w800, fontSize: 12)),
        const SizedBox(height: 6),
        subjects.isEmpty
            ? const Text('No subjects assigned yet.', style: TextStyle(color: AppColors.mutedDark, fontSize: 13))
            : Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final s in subjects) _Pill(label: s.toString()),
                ],
              ),
        const SizedBox(height: 14),
        const Text('Classes',
            style: TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w800, fontSize: 12)),
        const SizedBox(height: 6),
        classes.isEmpty
            ? const Text('No classes assigned yet.', style: TextStyle(color: AppColors.mutedDark, fontSize: 13))
            : Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final c in classes)
                    _Pill(label: ((c as Map<String, dynamic>)['label'] ?? c['name'] ?? '').toString()),
                ],
              ),
      ],
    );
  }
}

class _Pill extends StatelessWidget {
  final String label;
  const _Pill({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(label, style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.w800, fontSize: 12)),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final VoidCallback? onTap;
  const _StatCard({required this.label, required this.value, this.onTap});

  @override
  Widget build(BuildContext context) {
    final card = AppCard(
      children: [
        Text(label, style: const TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w800, fontSize: 12)),
        Text(value,
            style: const TextStyle(color: AppColors.textDark, fontSize: 26, fontWeight: FontWeight.w900)),
      ],
    );
    if (onTap == null) return card;
    return GestureDetector(onTap: onTap, child: card);
  }
}

class _QuickActionCard extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _QuickActionCard({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AppCard(
        children: [
          Row(
            children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                  color: AppColors.primarySoft,
                  borderRadius: BorderRadius.circular(10),
                ),
                alignment: Alignment.center,
                child: Icon(icon, size: 18, color: AppColors.primary),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(label,
                    style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w800, fontSize: 13)),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _AssessmentCard extends StatelessWidget {
  final Map<String, dynamic> item;
  final String Function(dynamic) formatDate;
  const _AssessmentCard({required this.item, required this.formatDate});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                (item['title'] ?? 'Assessment').toString(),
                style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900),
              ),
            ),
            if (item['start_date'] != null)
              Text(formatDate(item['start_date']),
                  style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.w800, fontSize: 12)),
          ],
        ),
        Text(
          '${item['subject'] ?? 'General'} · ${item['class_name'] ?? 'All classes'}',
          style: const TextStyle(color: AppColors.mutedDark, fontSize: 13),
        ),
      ],
    );
  }
}

class _AnnouncementCard extends StatelessWidget {
  final Map<String, dynamic> item;
  const _AnnouncementCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final priority = (item['priority'] ?? '').toString().toLowerCase();
    final tagColor = priority == 'high' ? AppColors.danger : priority == 'medium' ? AppColors.warning : AppColors.muted;
    return AppCard(
      children: [
        Row(
          children: [
            Expanded(
              child: Text(
                (item['title'] ?? 'Announcement').toString(),
                style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900),
              ),
            ),
            if (priority.isNotEmpty)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: tagColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(
                  priority.toUpperCase(),
                  style: TextStyle(color: tagColor, fontWeight: FontWeight.w800, fontSize: 10),
                ),
              ),
          ],
        ),
      ],
    );
  }
}
