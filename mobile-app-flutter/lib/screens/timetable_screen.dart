import 'package:flutter/material.dart';
import '../api/teacher_endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/branded_refresh.dart';
import '../widgets/primary_button.dart';
import '../widgets/skeleton.dart';

/// A teacher's weekly timetable is read-only on mobile (only admins edit
/// it) - so instead of replicating the web's cramped day-by-day grid table,
/// this shows a single day's periods as a scrollable agenda with a day
/// switcher up top, which reads far better on a phone screen.
class TimetableScreen extends StatefulWidget {
  const TimetableScreen({super.key});

  @override
  State<TimetableScreen> createState() => _TimetableScreenState();
}

class _TimetableScreenState extends State<TimetableScreen> {
  List<dynamic> _entries = [];
  List<dynamic> _days = [];
  List<dynamic> _activities = [];
  int _selectedDay = 0;
  bool _loading = true;
  bool _initialLoadDone = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    // DateTime.weekday is 1=Mon..7=Sun; the backend's day_of_week is 0=Mon..5=Sat.
    // Sunday has no school day option, so it falls back to Monday.
    final weekday = DateTime.now().weekday;
    _selectedDay = weekday <= 6 ? weekday - 1 : 0;
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await loadTimetable();
      setState(() {
        _entries = (data['entries'] ?? []) as List<dynamic>;
        _days = (data['days'] ?? []) as List<dynamic>;
        _activities = (data['school_activities'] ?? []) as List<dynamic>;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
          _initialLoadDone = true;
        });
      }
    }
  }

  List<Map<String, dynamic>> get _dayEntries {
    final list = _entries
        .cast<Map<String, dynamic>>()
        .where((e) => e['day_of_week'] == _selectedDay)
        .toList();
    list.sort((a, b) => (a['start_time'] ?? '').toString().compareTo((b['start_time'] ?? '').toString()));
    return list;
  }

  String _formatActivityDate(Map<String, dynamic> item) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    if (item['activity_date'] != null) {
      final d = DateTime.tryParse(item['activity_date'].toString());
      if (d != null) return '${months[d.month - 1]} ${d.day}';
    }
    if (item['month'] != null) {
      final m = int.tryParse(item['month'].toString());
      if (m != null && m >= 1 && m <= 12) return '${months[m - 1]}${item['year'] != null ? ' ${item['year']}' : ''}';
    }
    return '';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        foregroundColor: AppColors.text,
        title: const Text('My Timetable', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
      ),
      body: SafeArea(
        child: !_initialLoadDone && _loading
            ? const SkeletonList()
            : _error != null
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.error_outline, color: AppColors.danger, size: 40),
                          const SizedBox(height: 12),
                          const Text("Couldn't load your timetable.",
                              style: TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
                          const SizedBox(height: 4),
                          Text('Check your connection and try again.',
                              textAlign: TextAlign.center, style: TextStyle(color: AppColors.muted, fontSize: 13)),
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
                      padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
                      children: [
                        if (_activities.isNotEmpty) ...[
                          Text('Upcoming school activities',
                              style: TextStyle(color: AppColors.text, fontWeight: FontWeight.w900, fontSize: 14)),
                          const SizedBox(height: 10),
                          for (final raw in _activities.take(3)) ...[
                            _ActivityCard(item: raw as Map<String, dynamic>, formatDate: _formatActivityDate),
                            const SizedBox(height: 8),
                          ],
                          const SizedBox(height: 14),
                        ],
                        if (_days.isNotEmpty)
                          SizedBox(
                            height: 40,
                            child: ListView.separated(
                              scrollDirection: Axis.horizontal,
                              itemCount: _days.length,
                              separatorBuilder: (_, _) => const SizedBox(width: 8),
                              itemBuilder: (context, index) {
                                final day = _days[index] as Map<String, dynamic>;
                                final value = day['value'] as int;
                                return _DayChip(
                                  label: (day['label'] ?? '').toString(),
                                  selected: value == _selectedDay,
                                  onTap: () => setState(() => _selectedDay = value),
                                );
                              },
                            ),
                          ),
                        const SizedBox(height: 16),
                        if (_dayEntries.isEmpty)
                          Padding(
                            padding: const EdgeInsets.only(top: 40),
                            child: Center(
                              child: Text('No classes scheduled for this day.',
                                  style: TextStyle(color: AppColors.muted)),
                            ),
                          )
                        else
                          for (final entry in _dayEntries) ...[
                            _PeriodCard(entry: entry),
                            const SizedBox(height: 10),
                          ],
                      ],
                    ),
                  ),
      ),
    );
  }
}

class _DayChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _DayChip({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: selected ? AppColors.primary : AppColors.surfaceSoft,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: selected ? AppColors.primary : AppColors.border),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: selected ? Colors.white : AppColors.text,
            fontWeight: FontWeight.w800,
            fontSize: 13,
          ),
        ),
      ),
    );
  }
}

class _PeriodCard extends StatelessWidget {
  final Map<String, dynamic> entry;
  const _PeriodCard({required this.entry});

  @override
  Widget build(BuildContext context) {
    final start = (entry['start_time'] ?? '').toString();
    final end = (entry['end_time'] ?? '').toString();
    return AppCard(
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 64,
              padding: const EdgeInsets.symmetric(vertical: 6),
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppColors.primarySoft,
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                '$start\n$end',
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.w800, fontSize: 11),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    (entry['display_label'] ?? entry['subject_name'] ?? 'Period').toString(),
                    style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900),
                  ),
                  if ((entry['class_name'] ?? '').toString().isNotEmpty)
                    Text(entry['class_name'].toString(),
                        style: const TextStyle(color: AppColors.mutedDark, fontSize: 13)),
                  if ((entry['room'] ?? '').toString().isNotEmpty)
                    Text('Room ${entry['room']}',
                        style: TextStyle(color: AppColors.muted, fontSize: 12)),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }
}

class _ActivityCard extends StatelessWidget {
  final Map<String, dynamic> item;
  final String Function(Map<String, dynamic>) formatDate;
  const _ActivityCard({required this.item, required this.formatDate});

  @override
  Widget build(BuildContext context) {
    Color color = AppColors.primary;
    final raw = (item['color'] ?? '').toString();
    if (raw.startsWith('#')) {
      final hex = raw.substring(1);
      final parsed = int.tryParse(hex.length == 6 ? 'FF$hex' : hex, radix: 16);
      if (parsed != null) color = Color(parsed);
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(12),
        border: Border(left: BorderSide(color: color, width: 4)),
        boxShadow: const [BoxShadow(color: Color(0x0C000000), blurRadius: 12, offset: Offset(0, 2))],
      ),
      child: Row(
        children: [
          Expanded(
            child: Text((item['title'] ?? 'Activity').toString(),
                style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w800, fontSize: 13)),
          ),
          Text(formatDate(item),
              style: const TextStyle(color: AppColors.mutedDark, fontSize: 12, fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }
}
