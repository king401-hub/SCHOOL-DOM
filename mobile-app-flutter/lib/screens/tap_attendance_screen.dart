import 'package:flutter/material.dart';
import '../api/scanner_endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';

/// "Tap Attendance": lets a teacher/admin step through their class roster
/// one student at a time and tap Present/Late/Excused/Absent, instead of
/// scanning each student's ID card - the same feature and backend endpoints
/// (teacher_class_students / teacher_mark_student_attendance) the web
/// dashboard's Tap Attendance panel already uses.
class TapAttendanceScreen extends StatefulWidget {
  const TapAttendanceScreen({super.key});

  @override
  State<TapAttendanceScreen> createState() => _TapAttendanceScreenState();
}

class _TapAttendanceScreenState extends State<TapAttendanceScreen> {
  DateTime _date = DateTime.now();
  List<dynamic> _classes = [];
  int? _classId;
  List<dynamic> _students = [];
  List<dynamic> _records = [];
  bool _loading = true;
  String? _error;
  String? _savingStatus;
  bool _showTick = false;
  String _tickLabel = '';

  @override
  void initState() {
    super.initState();
    _loadClasses();
  }

  Future<void> _loadClasses() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await loadClassStudents(date: _date);
      final classes = (data['classes'] ?? []) as List<dynamic>;
      setState(() {
        _classes = classes;
        if ((_classId == null || !classes.any((c) => c['id'] == _classId)) &&
            classes.isNotEmpty) {
          _classId = classes.first['id'] as int?;
        }
      });
      if (_classId != null) {
        await _loadRoster();
      } else {
        setState(() => _loading = false);
      }
    } catch (e) {
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  Future<void> _loadRoster() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await loadClassStudents(classId: _classId, date: _date);
      setState(() {
        _students = (data['students'] ?? []) as List<dynamic>;
        _records = (data['attendance_records'] ?? []) as List<dynamic>;
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
      await _loadRoster();
    }
  }

  String _formatDate(DateTime d) =>
      '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  Set<String> get _markedIds =>
      _records.map((r) => (r['student_id'] ?? '').toString()).toSet();

  List<dynamic> get _pending => _students
      .where((s) => !_markedIds.contains((s['student_id'] ?? '').toString()))
      .toList();

  Future<void> _mark(String status) async {
    final active = _pending.isNotEmpty ? _pending.first : null;
    if (active == null || _savingStatus != null) return;
    setState(() => _savingStatus = status);
    try {
      final result = await markStudentAttendance(
        studentId: (active['student_id'] ?? '').toString(),
        classId: _classId!,
        status: status,
        date: _date,
      );
      final attendance = result['attendance'] as Map<String, dynamic>?;
      if (attendance != null) {
        setState(() {
          _records = [
            attendance,
            ..._records.where((r) => r['student_id'] != attendance['student_id']),
          ];
        });
        _flashTick(status);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.toString()), backgroundColor: AppColors.danger),
        );
      }
    } finally {
      if (mounted) setState(() => _savingStatus = null);
    }
  }

  void _flashTick(String status) {
    setState(() {
      _showTick = true;
      _tickLabel = status;
    });
    Future.delayed(const Duration(milliseconds: 850), () {
      if (mounted) setState(() => _showTick = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final active = _pending.isNotEmpty ? _pending.first : null;
    final markedCount = _students.length - _pending.length;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        foregroundColor: AppColors.text,
        title: const Text('Tap Attendance',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900)),
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _loadClasses,
          color: AppColors.primary,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
            children: [
              if (_classes.isNotEmpty)
                SizedBox(
                  height: 40,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: _classes.length,
                    separatorBuilder: (_, _) => const SizedBox(width: 8),
                    itemBuilder: (context, index) {
                      final item = _classes[index] as Map<String, dynamic>;
                      final selected = item['id'] == _classId;
                      return _ClassChip(
                        label: (item['label'] ?? item['name'] ?? '').toString(),
                        selected: selected,
                        onTap: () {
                          setState(() => _classId = item['id'] as int?);
                          _loadRoster();
                        },
                      );
                    },
                  ),
                ),
              const SizedBox(height: 12),
              _DateChip(label: _formatDate(_date), onTap: _pickDate),
              const SizedBox(height: 16),
              if (_error != null)
                Text(_error!, style: const TextStyle(color: AppColors.danger)),
              if (_loading)
                const Padding(
                  padding: EdgeInsets.only(top: 40),
                  child: Center(child: CircularProgressIndicator(color: AppColors.primary)),
                )
              else if (_error == null) ...[
                Center(
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                    decoration: BoxDecoration(
                      color: AppColors.surfaceSoft,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Text(
                      '$markedCount / ${_students.length} marked',
                      style: TextStyle(color: AppColors.muted, fontWeight: FontWeight.w700, fontSize: 12),
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Stack(
                  alignment: Alignment.center,
                  children: [
                    active != null
                        ? _ActiveStudentCard(
                            student: active,
                            savingStatus: _savingStatus,
                            onMark: _mark,
                          )
                        : AppCard(children: [
                            Center(
                              child: Text(
                                _classId == null
                                    ? 'Select a class to begin.'
                                    : _students.isEmpty
                                        ? 'No students are in this class yet.'
                                        : 'All students marked for this date.',
                                style: const TextStyle(color: AppColors.mutedDark),
                              ),
                            ),
                          ]),
                    if (_showTick) _AnimatedTick(key: UniqueKey(), label: _tickLabel),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _ClassChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _ClassChip({required this.label, required this.selected, required this.onTap});

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

class _DateChip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;
  const _DateChip({required this.label, required this.onTap});

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
            Icon(Icons.calendar_today_outlined, size: 16, color: AppColors.muted),
            const SizedBox(width: 8),
            Text(label, style: TextStyle(color: AppColors.text, fontWeight: FontWeight.w700)),
          ],
        ),
      ),
    );
  }
}

class _ActiveStudentCard extends StatelessWidget {
  final Map<String, dynamic> student;
  final String? savingStatus;
  final ValueChanged<String> onMark;
  const _ActiveStudentCard({required this.student, required this.savingStatus, required this.onMark});

  @override
  Widget build(BuildContext context) {
    final name = (student['name'] ?? 'Student').toString();
    final initials = name.trim().isEmpty
        ? '?'
        : name.trim().split(RegExp(r'\s+')).take(2).map((s) => s[0]).join().toUpperCase();

    return AppCard(
      children: [
        Center(
          child: Container(
            width: 64,
            height: 64,
            decoration: const BoxDecoration(color: AppColors.primarySoft, shape: BoxShape.circle),
            alignment: Alignment.center,
            child: Text(initials,
                style: const TextStyle(color: AppColors.primary, fontSize: 22, fontWeight: FontWeight.w900)),
          ),
        ),
        Center(
          child: Text(name,
              style: const TextStyle(color: AppColors.textDark, fontSize: 18, fontWeight: FontWeight.w900)),
        ),
        Center(
          child: Text(
            '${student['student_id'] ?? ''} · ${student['class_name'] ?? ''}',
            style: const TextStyle(color: AppColors.mutedDark),
          ),
        ),
        const SizedBox(height: 4),
        Row(
          children: [
            Expanded(
              child: _StatusButton(
                label: 'Present',
                color: AppColors.success,
                loading: savingStatus == 'present',
                disabled: savingStatus != null,
                onTap: () => onMark('present'),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: _StatusButton(
                label: 'Late',
                color: AppColors.warning,
                loading: savingStatus == 'late',
                disabled: savingStatus != null,
                onTap: () => onMark('late'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: _StatusButton(
                label: 'Excused',
                color: AppColors.muted,
                loading: savingStatus == 'excused',
                disabled: savingStatus != null,
                onTap: () => onMark('excused'),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: _StatusButton(
                label: 'Absent',
                color: AppColors.danger,
                loading: savingStatus == 'absent',
                disabled: savingStatus != null,
                onTap: () => onMark('absent'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        const Center(
          child: Text(
            'Tap a status to save and move to the next student.',
            textAlign: TextAlign.center,
            style: TextStyle(color: AppColors.mutedDark, fontSize: 12),
          ),
        ),
      ],
    );
  }
}

class _StatusButton extends StatelessWidget {
  final String label;
  final Color color;
  final bool loading;
  final bool disabled;
  final VoidCallback onTap;
  const _StatusButton({
    required this.label,
    required this.color,
    required this.loading,
    required this.disabled,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: disabled ? null : onTap,
      child: Container(
        height: 46,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: color.withValues(alpha: disabled && !loading ? 0.08 : 0.14),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withValues(alpha: 0.5)),
        ),
        child: loading
            ? SizedBox(
                width: 18,
                height: 18,
                child: CircularProgressIndicator(strokeWidth: 2, color: color),
              )
            : Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w800)),
      ),
    );
  }
}

class _AnimatedTick extends StatefulWidget {
  final String label;
  const _AnimatedTick({super.key, required this.label});

  @override
  State<_AnimatedTick> createState() => _AnimatedTickState();
}

class _AnimatedTickState extends State<_AnimatedTick> with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 500),
  )..forward();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Color get _color => switch (widget.label) {
        'present' => AppColors.success,
        'late' => AppColors.warning,
        'excused' => AppColors.muted,
        _ => AppColors.danger,
      };

  IconData get _icon => widget.label == 'absent' ? Icons.close : Icons.check;

  @override
  Widget build(BuildContext context) {
    final scale = CurvedAnimation(parent: _controller, curve: Curves.elasticOut);
    final fade = CurvedAnimation(
      parent: _controller,
      curve: const Interval(0, 0.4, curve: Curves.easeOut),
      reverseCurve: Curves.easeIn,
    );
    return IgnorePointer(
      child: ScaleTransition(
        scale: scale,
        child: FadeTransition(
          opacity: fade,
          child: Container(
            width: 84,
            height: 84,
            decoration: BoxDecoration(
              color: _color,
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(color: _color.withValues(alpha: 0.5), blurRadius: 24, spreadRadius: 2),
              ],
            ),
            child: Icon(_icon, color: Colors.white, size: 44),
          ),
        ),
      ),
    );
  }
}
