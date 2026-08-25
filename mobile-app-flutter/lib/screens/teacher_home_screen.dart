import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/endpoints.dart';
import '../auth/auth_provider.dart';
import '../theme/app_theme.dart';
import '../api/teacher_endpoints.dart';
import '../widgets/app_card.dart';
import '../widgets/avatar.dart';
import '../widgets/branded_refresh.dart';
import '../widgets/primary_button.dart';
import '../widgets/skeleton.dart';
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

class _TeacherHomeScreenState extends State<TeacherHomeScreen> with TickerProviderStateMixin {
  Map<String, dynamic>? _data;
  List<Map<String, dynamic>> _todayEntries = [];
  bool _loading = true;
  String? _error;
  bool _hasPlayedEntrance = false;

  late final AnimationController _enterController = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 650),
  );
  late final Animation<double> _enterFade = CurvedAnimation(parent: _enterController, curve: Curves.easeOut);
  late final Animation<Offset> _enterSlide = Tween<Offset>(
    begin: const Offset(0, 0.06),
    end: Offset.zero,
  ).animate(CurvedAnimation(parent: _enterController, curve: Curves.easeOutCubic));

  // Slow "breathing" loop behind the header - purely decorative, gives the
  // otherwise-static accent glow a bit of life without being distracting.
  late final AnimationController _glowController = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 4),
  )..repeat(reverse: true);

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _enterController.dispose();
    _glowController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([loadDashboard('teacher'), loadTimetable()]);
      final data = results[0];
      final timetable = results[1];
      final weekday = DateTime.now().weekday;
      final todayValue = weekday <= 6 ? weekday - 1 : 0;
      final entries = ((timetable['entries'] ?? []) as List<dynamic>)
          .cast<Map<String, dynamic>>()
          .where((e) => e['day_of_week'] == todayValue)
          .toList()
        ..sort((a, b) => (a['start_time'] ?? '').toString().compareTo((b['start_time'] ?? '').toString()));
      setState(() {
        _data = data;
        _todayEntries = entries;
      });
      if (!_hasPlayedEntrance) {
        _hasPlayedEntrance = true;
        _enterController.forward();
      }
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
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
              child: Stack(
                clipBehavior: Clip.none,
                children: [
                  Positioned(
                    top: -50,
                    right: -50,
                    child: IgnorePointer(
                      child: AnimatedBuilder(
                        animation: _glowController,
                        builder: (context, child) {
                          final t = _glowController.value;
                          return Opacity(
                            opacity: 0.12 + t * 0.10,
                            child: Transform.scale(
                              scale: 0.92 + t * 0.16,
                              child: child,
                            ),
                          );
                        },
                        child: Container(
                          width: 140,
                          height: 140,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            gradient: RadialGradient(
                              colors: [AppColors.primary.withValues(alpha: 0.9), Colors.transparent],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  Positioned(
                    top: 10,
                    left: 40,
                    child: IgnorePointer(
                      child: AnimatedBuilder(
                        animation: _glowController,
                        builder: (context, child) {
                          final t = 1 - _glowController.value;
                          return Opacity(
                            opacity: 0.08 + t * 0.08,
                            child: Transform.scale(
                              scale: 0.9 + t * 0.14,
                              child: child,
                            ),
                          );
                        },
                        child: Container(
                          width: 90,
                          height: 90,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            gradient: RadialGradient(
                              colors: [AppColors.secondary.withValues(alpha: 0.9), Colors.transparent],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      Avatar(
                        name: (profile['name'] ?? auth.displayName ?? 'Teacher').toString(),
                        pictureUrl: profile['profile_picture'] as String?,
                        size: 48,
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
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
                              style: TextStyle(color: AppColors.text, fontSize: 24, fontWeight: FontWeight.w900),
                            ),
                          ],
                        ),
                      ),
                      _NotificationBell(
                        unreadCount: (metrics['unread_notifications'] as num?)?.toInt() ?? 0,
                        onTap: () async {
                          await Navigator.of(context).push(
                            MaterialPageRoute(builder: (_) => const NotificationsScreen()),
                          );
                          _load();
                        },
                      ),
                    ],
                  ),
                ],
              ),
            ),
            Expanded(
              child: _loading && _data == null
                  ? const SkeletonList()
                  : _error != null && _data == null
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
                                const SizedBox(height: 4),
                                Text('Check your connection and try again.',
                                    textAlign: TextAlign.center,
                                    style: TextStyle(color: AppColors.muted, fontSize: 13)),
                                const SizedBox(height: 16),
                                SizedBox(width: 160, child: PrimaryButton(title: 'Retry', onPressed: _load)),
                              ],
                            ),
                          ),
                        )
                      : BrandedRefresh(
                          onRefresh: _load,
                          showSpinner: _loading && _data != null,
                          child: FadeTransition(
                            opacity: _enterFade,
                            child: SlideTransition(
                              position: _enterSlide,
                              child: ListView(
                            padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
                            children: [
              if (_error != null)
                Text(_error!, style: const TextStyle(color: AppColors.danger)),
              if (_data != null) ...[
                _TeachingCard(
                  monthlySalary: monthlySalary,
                  subjects: subjectsTaught,
                  classes: classesTaught,
                ),
                const SizedBox(height: 20),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Expanded(
                      child: _StatCard(
                        label: 'Upcoming assessments',
                        value: (metrics['upcoming_assessments'] ?? 0).toString(),
                        icon: Icons.calendar_month_outlined,
                        accent: AppColors.primary,
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: _StatCard(
                        label: 'Needs grading',
                        value: (metrics['pending_submissions'] ?? 0).toString(),
                        icon: Icons.edit_note_outlined,
                        accent: AppColors.warning,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 14),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Expanded(
                      child: _StatCard(
                        label: 'Unread messages',
                        value: (metrics['unread_inbox'] ?? 0).toString(),
                        icon: Icons.mail_outline,
                        accent: AppColors.secondary,
                      ),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: _StatCard(
                        label: 'Average score',
                        value: '${metrics['average_cbt_score'] ?? 0}%',
                        icon: Icons.bar_chart_outlined,
                        accent: AppColors.success,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                Row(
                  children: [
                    Text("Today's Schedule",
                        style: TextStyle(color: AppColors.text, fontSize: 16, fontWeight: FontWeight.w900)),
                    const Spacer(),
                    Material(
                      color: Colors.transparent,
                      child: InkWell(
                        borderRadius: BorderRadius.circular(10),
                        onTap: () => Navigator.of(context)
                            .push(MaterialPageRoute(builder: (_) => const TimetableScreen())),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text('View timetable',
                                  style: TextStyle(
                                      color: AppColors.primary, fontSize: 12, fontWeight: FontWeight.w800)),
                              const SizedBox(width: 2),
                              Icon(Icons.chevron_right, size: 16, color: AppColors.primary),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                if (_todayEntries.isEmpty)
                  AppCard(
                    children: [
                      Center(
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              width: 36,
                              height: 36,
                              decoration: BoxDecoration(
                                  color: AppColors.primarySoft, borderRadius: BorderRadius.circular(18)),
                              alignment: Alignment.center,
                              child: const Icon(Icons.event_available_outlined,
                                  size: 18, color: AppColors.primary),
                            ),
                            const SizedBox(width: 10),
                            Text('No classes scheduled for today.',
                                style: TextStyle(color: AppColors.muted, fontSize: 13)),
                          ],
                        ),
                      ),
                    ],
                  )
                else
                  for (final entry in _todayEntries) ...[
                    _TodayPeriodCard(entry: entry),
                    const SizedBox(height: 10),
                  ],
                const SizedBox(height: 24),
                Text('Needs Your Attention',
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
                        ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NotificationBell extends StatelessWidget {
  final int unreadCount;
  final VoidCallback onTap;
  const _NotificationBell({required this.unreadCount, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: AppColors.surfaceSoft,
          shape: BoxShape.circle,
          border: Border.all(color: AppColors.border),
          boxShadow: const [BoxShadow(color: Color(0x1A000000), blurRadius: 10, offset: Offset(0, 3))],
        ),
        child: Stack(
          clipBehavior: Clip.none,
          alignment: Alignment.center,
          children: [
            Icon(
              unreadCount > 0 ? Icons.notifications : Icons.notifications_outlined,
              color: unreadCount > 0 ? AppColors.primary : AppColors.muted,
            ),
            // The badge is the part that "disappears" once notifications are
            // opened and marked read - the bell icon itself always stays.
            if (unreadCount > 0)
              Positioned(
                top: -2,
                right: -2,
                child: Container(
                  padding: const EdgeInsets.all(3),
                  constraints: const BoxConstraints(minWidth: 16, minHeight: 16),
                  decoration: const BoxDecoration(color: AppColors.danger, shape: BoxShape.circle),
                  alignment: Alignment.center,
                  child: Text(
                    unreadCount > 9 ? '9+' : unreadCount.toString(),
                    textAlign: TextAlign.center,
                    style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w800),
                  ),
                ),
              ),
          ],
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
      elevated: true,
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [AppColors.card, AppColors.primarySoft.withValues(alpha: 0.4)],
      ),
      children: [
        if (monthlySalary != null) ...[
          Row(
            children: [
              Container(
                width: 30,
                height: 30,
                decoration: BoxDecoration(
                  color: AppColors.primarySoft,
                  borderRadius: BorderRadius.circular(9),
                  boxShadow: [BoxShadow(color: AppColors.primary.withValues(alpha: 0.18), blurRadius: 8, offset: const Offset(0, 3))],
                ),
                alignment: Alignment.center,
                child: const Icon(Icons.account_balance_wallet_outlined, size: 16, color: AppColors.primary),
              ),
              const SizedBox(width: 8),
              const Text('Monthly salary',
                  style: TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w800, fontSize: 12)),
            ],
          ),
          Text(_formatNaira(monthlySalary),
              style: const TextStyle(color: AppColors.textDark, fontSize: 22, fontWeight: FontWeight.w900)),
          Divider(height: 22, color: AppColors.border),
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
                  for (final s in subjects)
                    _Pill(label: s.toString(), color: AppColors.primary, soft: AppColors.primarySoft),
                ],
              ),
        const SizedBox(height: 12),
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
                    _Pill(
                      label: ((c as Map<String, dynamic>)['label'] ?? c['name'] ?? '').toString(),
                      color: AppColors.secondary,
                      soft: AppColors.secondarySoft,
                    ),
                ],
              ),
      ],
    );
  }
}

class _Pill extends StatelessWidget {
  final String label;
  final Color color;
  final Color soft;
  const _Pill({required this.label, this.color = AppColors.primary, this.soft = AppColors.primarySoft});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: soft,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w800, fontSize: 12)),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color accent;
  const _StatCard({required this.label, required this.value, required this.icon, required this.accent});

  bool get _isZero => (double.tryParse(value.replaceAll('%', '')) ?? -1) == 0;

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
          decoration: BoxDecoration(
            color: accent.withValues(alpha: 0.14),
            borderRadius: BorderRadius.circular(10),
            boxShadow: [BoxShadow(color: accent.withValues(alpha: 0.22), blurRadius: 8, offset: const Offset(0, 3))],
          ),
          alignment: Alignment.center,
          child: Icon(icon, size: 15, color: accent),
        ),
        const SizedBox(height: 6),
        Text(label, style: const TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w800, fontSize: 12)),
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 350),
          transitionBuilder: (child, animation) => FadeTransition(
            opacity: animation,
            child: SlideTransition(
              position: Tween<Offset>(begin: const Offset(0, 0.3), end: Offset.zero).animate(animation),
              child: child,
            ),
          ),
          child: Text(value,
              key: ValueKey(value),
              style: TextStyle(
                color: _isZero ? AppColors.muted : AppColors.textDark,
                fontSize: 26,
                fontWeight: _isZero ? FontWeight.w700 : FontWeight.w900,
              )),
        ),
      ],
    );
  }
}

class _TodayPeriodCard extends StatelessWidget {
  final Map<String, dynamic> entry;
  const _TodayPeriodCard({required this.entry});

  @override
  Widget build(BuildContext context) {
    final start = (entry['start_time'] ?? '').toString();
    final end = (entry['end_time'] ?? '').toString();
    return AppCard(
      children: [
        Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(color: AppColors.primarySoft, borderRadius: BorderRadius.circular(10)),
              child: Text('$start-$end',
                  style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.w800, fontSize: 11)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text((entry['display_label'] ?? entry['subject_name'] ?? 'Period').toString(),
                      style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900, fontSize: 13)),
                  if ((entry['class_name'] ?? '').toString().isNotEmpty)
                    Text(entry['class_name'].toString(),
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
