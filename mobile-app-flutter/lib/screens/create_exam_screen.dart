import 'package:flutter/material.dart';
import '../api/admin_endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/primary_button.dart';

/// Simplified exam-shell creation - title/class/subject/format/dates/
/// duration only. Full CBT question authoring (the web dashboard's
/// multi-step wizard) isn't replicated here; this creates a draft exam
/// (unpublished, zero questions) an admin can then finish building on the
/// web, matching the "Save Draft" scope already used elsewhere in this app.
class CreateExamScreen extends StatefulWidget {
  final List<Map<String, dynamic>> classes;
  final List<Map<String, dynamic>> subjects;
  const CreateExamScreen({super.key, required this.classes, required this.subjects});

  @override
  State<CreateExamScreen> createState() => _CreateExamScreenState();
}

class _CreateExamScreenState extends State<CreateExamScreen> {
  final _title = TextEditingController();
  final _duration = TextEditingController(text: '60');
  int? _classId;
  int? _subjectId;
  String _examFormat = 'objective';
  DateTime _startDate = DateTime.now().add(const Duration(days: 1));
  DateTime _endDate = DateTime.now().add(const Duration(days: 1, hours: 1));
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _title.dispose();
    _duration.dispose();
    super.dispose();
  }

  Future<void> _pickDate({required bool isStart}) async {
    final initial = isStart ? _startDate : _endDate;
    final date = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime.now().subtract(const Duration(days: 1)),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (date == null || !mounted) return;
    final time = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(initial));
    if (time == null) return;
    final combined = DateTime(date.year, date.month, date.day, time.hour, time.minute);
    setState(() {
      if (isStart) {
        _startDate = combined;
      } else {
        _endDate = combined;
      }
    });
  }

  Future<void> _save({required bool publish}) async {
    if (_title.text.trim().length < 3) {
      setState(() => _error = 'Exam title must be at least 3 characters.');
      return;
    }
    if (!_endDate.isAfter(_startDate)) {
      setState(() => _error = 'End date must be after the start date.');
      return;
    }
    final duration = int.tryParse(_duration.text.trim()) ?? 0;
    if (duration <= 0) {
      setState(() => _error = 'Enter a valid duration in minutes.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await createExamDraft(
        title: _title.text.trim(),
        classId: _classId,
        subjectId: _subjectId,
        startDate: _startDate,
        endDate: _endDate,
        durationMinutes: duration,
        examFormat: _examFormat,
        isPublished: publish,
      );
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  String _formatDateTime(DateTime dt) =>
      '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
      '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        foregroundColor: AppColors.text,
        title: const Text('Create Exam', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
          children: [
            Text('Exam Information',
                style: TextStyle(color: AppColors.text, fontWeight: FontWeight.w900, fontSize: 14)),
            const SizedBox(height: 12),
            TextField(
              controller: _title,
              style: const TextStyle(color: AppColors.textDark),
              decoration: const InputDecoration(labelText: 'Exam title', hintText: 'e.g SS2 First Term Examination'),
            ),
            const SizedBox(height: 12),
            const Text('Exam format', style: TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w700, fontSize: 12)),
            const SizedBox(height: 8),
            Row(
              children: [
                for (final f in const [
                  ['objective', 'CBT'],
                  ['theory', 'Theory'],
                  ['mixed', 'Mixed'],
                ]) ...[
                  Expanded(
                    child: GestureDetector(
                      onTap: () => setState(() => _examFormat = f[0]),
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                          gradient: _examFormat == f[0] ? AppGradients.brand : null,
                          color: _examFormat == f[0] ? null : AppColors.surfaceSoft,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(f[1],
                            style: TextStyle(
                                color: _examFormat == f[0] ? Colors.white : AppColors.mutedDark,
                                fontWeight: FontWeight.w800,
                                fontSize: 12)),
                      ),
                    ),
                  ),
                  if (f[0] != 'mixed') const SizedBox(width: 8),
                ],
              ],
            ),
            const SizedBox(height: 14),
            DropdownButtonFormField<int>(
              initialValue: _classId,
              style: const TextStyle(color: AppColors.textDark),
              decoration: const InputDecoration(labelText: 'Class'),
              items: [
                for (final c in widget.classes)
                  DropdownMenuItem(
                      value: c['id'] as int,
                      child: Text(c['label'].toString(), style: const TextStyle(color: AppColors.textDark))),
              ],
              onChanged: (v) => setState(() => _classId = v),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<int>(
              initialValue: _subjectId,
              style: const TextStyle(color: AppColors.textDark),
              decoration: const InputDecoration(labelText: 'Subject'),
              items: [
                for (final s in widget.subjects)
                  DropdownMenuItem(
                      value: s['id'] as int,
                      child: Text(s['name'].toString(), style: const TextStyle(color: AppColors.textDark))),
              ],
              onChanged: (v) => setState(() => _subjectId = v),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _DateField(label: 'Start date', value: _formatDateTime(_startDate), onTap: () => _pickDate(isStart: true)),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _DateField(label: 'End date', value: _formatDateTime(_endDate), onTap: () => _pickDate(isStart: false)),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _duration,
              style: const TextStyle(color: AppColors.textDark),
              decoration: const InputDecoration(labelText: 'Duration (mins)', hintText: 'e.g 60'),
              keyboardType: TextInputType.number,
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: AppColors.danger)),
            ],
            const SizedBox(height: 20),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: _saving ? null : () => _save(publish: false),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      side: BorderSide(color: AppColors.border),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: Text('Save Draft', style: TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w800)),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: PrimaryButton(title: 'Publish', loading: _saving, onPressed: () => _save(publish: true)),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _DateField extends StatelessWidget {
  final String label;
  final String value;
  final VoidCallback onTap;
  const _DateField({required this.label, required this.value, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: InputDecorator(
        decoration: InputDecoration(labelText: label),
        child: Text(value, style: const TextStyle(color: AppColors.textDark, fontSize: 13)),
      ),
    );
  }
}
