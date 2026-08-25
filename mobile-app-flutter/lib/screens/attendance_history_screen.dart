import 'package:flutter/material.dart';
import '../api/scanner_endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/branded_refresh.dart';

class AttendanceHistoryScreen extends StatefulWidget {
  const AttendanceHistoryScreen({super.key});

  @override
  State<AttendanceHistoryScreen> createState() => _AttendanceHistoryScreenState();
}

class _AttendanceHistoryScreenState extends State<AttendanceHistoryScreen> {
  DateTime _date = DateTime.now();
  int? _classId;
  List<dynamic> _classOptions = [];
  List<dynamic> _records = [];
  int _present = 0;
  int _onSite = 0;
  int _clockedOut = 0;
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
      final data = await loadScannerAttendanceHistory(date: _date, classId: _classId);
      setState(() {
        _records = (data['records'] ?? []) as List<dynamic>;
        _classOptions = (data['class_options'] ?? []) as List<dynamic>;
        _present = (data['total_present'] ?? 0) as int;
        _onSite = (data['total_on_site'] ?? 0) as int;
        _clockedOut = (data['total_clocked_out'] ?? 0) as int;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now(),
      builder: (context, child) => Theme(
        data: Theme.of(context).copyWith(
          colorScheme: ColorScheme.dark(
            primary: AppColors.primary,
            surface: AppColors.surface,
          ),
        ),
        child: child!,
      ),
    );
    if (picked != null) {
      setState(() => _date = picked);
      _load();
    }
  }

  String _formatDate(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  String _formatTime(String? iso) {
    if (iso == null || iso.isEmpty) return '';
    final parsed = DateTime.tryParse(iso);
    if (parsed == null) return '';
    final local = parsed.toLocal();
    final hour = local.hour % 12 == 0 ? 12 : local.hour % 12;
    final minute = local.minute.toString().padLeft(2, '0');
    final period = local.hour >= 12 ? 'PM' : 'AM';
    return '$hour:$minute $period';
  }

  static const _kUnassignedLabel = 'No class assigned';

  /// Groups records by class, preserving first-seen order, so the list can
  /// render as collapsible per-class sections instead of one long flat list.
  List<MapEntry<String, List<dynamic>>> get _groupedRecords {
    final groups = <String, List<dynamic>>{};
    for (final raw in _records) {
      final record = raw as Map<String, dynamic>;
      final className = (record['class_name'] ?? _kUnassignedLabel).toString();
      groups.putIfAbsent(className, () => []).add(record);
    }
    return groups.entries.toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        foregroundColor: AppColors.text,
        title: const Text('Attendance History',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
              child: Column(
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: _FilterChip(
                          icon: Icons.calendar_today_outlined,
                          label: _formatDate(_date),
                          onTap: _pickDate,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _ClassFilterChip(
                          options: _classOptions,
                          selectedId: _classId,
                          onChanged: (id) {
                            setState(() => _classId = id);
                            _load();
                          },
                        ),
                      ),
                    ],
                  ),
                  if (!_loading && _error == null) ...[
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        _SummaryPill(label: 'Present', value: _present, color: AppColors.success),
                        const SizedBox(width: 10),
                        _SummaryPill(label: 'On site', value: _onSite, color: AppColors.warning),
                        const SizedBox(width: 10),
                        _SummaryPill(label: 'Clocked out', value: _clockedOut, color: AppColors.muted),
                      ],
                    ),
                  ],
                ],
              ),
            ),
            Expanded(
              child: BrandedRefresh(
                onRefresh: _load,
                showSpinner: _loading && _records.isNotEmpty,
                child: _loading && _records.isEmpty
                    ? const _HistorySkeletonList()
                    : _error != null
                        ? _centeredScrollable(
                            _StateMessage(
                              icon: Icons.error_outline,
                              iconColor: AppColors.danger,
                              title: 'Something went wrong',
                              message: _error!,
                            ),
                          )
                        : _records.isEmpty
                            ? _centeredScrollable(const _StateMessage(
                                icon: Icons.event_busy_outlined,
                                iconColor: AppColors.primary,
                                title: 'No attendance recorded',
                                message:
                                    'Nothing was scanned for this day yet. Pull down to refresh or try another date.',
                              ))
                            : ListView(
                                padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
                                children: [
                                  for (final group in _groupedRecords) ...[
                                    _ClassGroupSection(
                                      className: group.key,
                                      records: group.value,
                                      formatTime: _formatTime,
                                      // Only expanded by default when a single class is
                                      // already selected via the filter - otherwise "All
                                      // classes" starts fully collapsed so the list isn't
                                      // one long wall of cards.
                                      initiallyExpanded: _classId != null,
                                    ),
                                    const SizedBox(height: 16),
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

Widget _centeredScrollable(Widget child) {
  return LayoutBuilder(
    builder: (context, constraints) => ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
      children: [
        ConstrainedBox(
          constraints: BoxConstraints(minHeight: constraints.maxHeight - 40),
          child: Center(child: child),
        ),
      ],
    ),
  );
}

class _StateMessage extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final String message;
  const _StateMessage({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.message,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 88,
          height: 88,
          decoration: BoxDecoration(
            color: iconColor.withValues(alpha: 0.12),
            shape: BoxShape.circle,
          ),
          alignment: Alignment.center,
          child: Icon(icon, size: 40, color: iconColor),
        ),
        const SizedBox(height: 20),
        Text(title,
            style: TextStyle(color: AppColors.text, fontSize: 17, fontWeight: FontWeight.w900)),
        const SizedBox(height: 6),
        Text(message,
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.muted, fontSize: 13)),
      ],
    );
  }
}

class _SkeletonBlock extends StatefulWidget {
  final double height;
  final double? width;
  final BorderRadius? radius;
  const _SkeletonBlock({this.height = 14, this.width, this.radius});

  @override
  State<_SkeletonBlock> createState() => _SkeletonBlockState();
}

class _SkeletonBlockState extends State<_SkeletonBlock> with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) => Container(
        width: widget.width,
        height: widget.height,
        decoration: BoxDecoration(
          color: AppColors.card.withValues(alpha: 0.28 + _controller.value * 0.22),
          borderRadius: widget.radius ?? BorderRadius.circular(8),
        ),
      ),
    );
  }
}

class _HistorySkeletonList extends StatelessWidget {
  const _HistorySkeletonList();

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
      children: [
        for (int i = 0; i < 4; i++) ...[
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppColors.card.withValues(alpha: 0.5),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SkeletonBlock(height: 16, width: 140),
                const SizedBox(height: 10),
                const _SkeletonBlock(height: 12, width: 90),
                const SizedBox(height: 16),
                _SkeletonBlock(height: 44, width: double.infinity, radius: BorderRadius.circular(12)),
              ],
            ),
          ),
          const SizedBox(height: 16),
        ],
      ],
    );
  }
}

class _FilterChip extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _FilterChip({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: AppColors.surfaceSoft,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.border),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 16, color: AppColors.muted),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                label,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: AppColors.text, fontWeight: FontWeight.w700),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ClassFilterChip extends StatelessWidget {
  final List<dynamic> options;
  final int? selectedId;
  final ValueChanged<int?> onChanged;
  const _ClassFilterChip({required this.options, required this.selectedId, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final selectedLabel = selectedId == null
        ? 'All classes'
        : (options.firstWhere(
                (c) => c['id'] == selectedId,
                orElse: () => {'label': 'All classes'})['label'] ??
            'All classes');

    return PopupMenuButton<int?>(
      onSelected: onChanged,
      color: AppColors.surfaceSoft,
      itemBuilder: (context) => [
        const PopupMenuItem<int?>(value: null, child: Text('All classes')),
        for (final c in options)
          PopupMenuItem<int?>(
            value: c['id'] as int?,
            child: Text((c['label'] ?? c['name'] ?? '').toString()),
          ),
      ],
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        decoration: BoxDecoration(
          color: AppColors.surfaceSoft,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.border),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.class_outlined, size: 16, color: AppColors.muted),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                selectedLabel.toString(),
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: AppColors.text, fontWeight: FontWeight.w700),
              ),
            ),
            Icon(Icons.arrow_drop_down, color: AppColors.muted),
          ],
        ),
      ),
    );
  }
}

class _SummaryPill extends StatelessWidget {
  final String label;
  final int value;
  final Color color;
  const _SummaryPill({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.16),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: color.withValues(alpha: 0.35)),
        ),
        child: Column(
          children: [
            Text(value.toString(),
                style: TextStyle(color: color, fontSize: 22, fontWeight: FontWeight.w900)),
            const SizedBox(height: 2),
            Text(label,
                style: TextStyle(
                    color: AppColors.text,
                    fontSize: 11.5,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.2)),
          ],
        ),
      ),
    );
  }
}

class _ClassGroupSection extends StatelessWidget {
  final String className;
  final List<dynamic> records;
  final String Function(String?) formatTime;
  final bool initiallyExpanded;

  const _ClassGroupSection({
    required this.className,
    required this.records,
    required this.formatTime,
    required this.initiallyExpanded,
  });

  @override
  Widget build(BuildContext context) {
    final onSiteCount = records
        .cast<Map<String, dynamic>>()
        .where((r) => r['clock_in_at'] != null && r['clock_out_at'] == null)
        .length;
    final isUnassigned = className == _AttendanceHistoryScreenState._kUnassignedLabel;

    return Theme(
      // Removes the default divider ExpansionTile draws above/below itself,
      // which otherwise looks like a stray line against this dark background.
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.circular(16),
          boxShadow: const [
            BoxShadow(color: Color(0x0C000000), blurRadius: 12, offset: Offset(0, 2)),
          ],
        ),
        clipBehavior: Clip.antiAlias,
        child: ExpansionTile(
          initiallyExpanded: initiallyExpanded,
          iconColor: AppColors.primary,
          collapsedIconColor: AppColors.mutedDark,
          title: Row(
            children: [
              if (isUnassigned) ...[
                const Icon(Icons.error_outline, size: 16, color: AppColors.warning),
                const SizedBox(width: 6),
              ],
              Expanded(
                child: Text(
                  className,
                  style: TextStyle(
                      color: isUnassigned ? AppColors.warning : AppColors.textDark,
                      fontWeight: FontWeight.w900),
                ),
              ),
            ],
          ),
          subtitle: Text(
            isUnassigned
                ? '${records.length} scanned · ask an admin to assign a class'
                : '${records.length} scanned${onSiteCount > 0 ? ' · $onSiteCount on site' : ''}',
            style: const TextStyle(color: AppColors.mutedDark, fontSize: 12),
          ),
          childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 14),
          children: [
            for (final raw in records) ...[
              _HistoryCard(
                record: raw as Map<String, dynamic>,
                formatTime: formatTime,
                flat: true,
              ),
              const SizedBox(height: 10),
            ],
          ],
        ),
      ),
    );
  }
}

class _HistoryCard extends StatelessWidget {
  final Map<String, dynamic> record;
  final String Function(String?) formatTime;
  // True when nested inside a _ClassGroupSection: skips the redundant class
  // name line (already the section header) and uses a tinted background
  // instead of AppCard's white, so it reads against that white container.
  final bool flat;

  const _HistoryCard({
    required this.record,
    required this.formatTime,
    this.flat = false,
  });

  @override
  Widget build(BuildContext context) {
    final clockIn = formatTime(record['clock_in_at'] as String?);
    final clockOut = formatTime(record['clock_out_at'] as String?);
    final onSite = record['clock_in_at'] != null && record['clock_out_at'] == null;

    final content = [
      Row(
        children: [
          Expanded(
            child: Text(
              (record['student_name'] ?? 'Student').toString(),
              style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900),
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: (onSite ? AppColors.warning : AppColors.success).withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              onSite ? 'On site' : 'Clocked out',
              style: TextStyle(
                color: onSite ? AppColors.warning : AppColors.success,
                fontWeight: FontWeight.w800,
                fontSize: 11,
              ),
            ),
          ),
        ],
      ),
      if (!flat)
        Text(
          (record['class_name'] ?? _AttendanceHistoryScreenState._kUnassignedLabel).toString(),
          style: const TextStyle(color: AppColors.mutedDark),
        ),
      if (clockIn.isNotEmpty)
        Text('Clocked in $clockIn', style: const TextStyle(color: AppColors.mutedDark, fontSize: 13)),
      if (clockOut.isNotEmpty)
        Text('Clocked out $clockOut', style: const TextStyle(color: AppColors.mutedDark, fontSize: 13)),
      if ((record['marked_by'] ?? '').toString().isNotEmpty)
        Text('Marked by ${record['marked_by']}',
            style: TextStyle(color: AppColors.muted, fontSize: 11)),
    ];

    if (!flat) {
      return AppCard(children: content);
    }
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.cardSoft,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (int i = 0; i < content.length; i++) ...[
            content[i],
            if (i < content.length - 1) const SizedBox(height: 6),
          ],
        ],
      ),
    );
  }
}
