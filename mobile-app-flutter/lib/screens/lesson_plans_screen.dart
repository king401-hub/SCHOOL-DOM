import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/teacher_endpoints.dart';
import '../auth/auth_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/branded_refresh.dart';
import '../widgets/primary_button.dart';
import '../widgets/skeleton.dart';

/// Mobile take on the web's "Lesson Plans" (Course Outline at Non-K12
/// schools) - split out from the old combined Lesson Plans & Notepad screen
/// so this can carry its own "Save Draft" / "Publish Lesson" flow instead of
/// a manual status dropdown (see spec section 5).
class LessonPlansScreen extends StatefulWidget {
  const LessonPlansScreen({super.key});

  @override
  State<LessonPlansScreen> createState() => _LessonPlansScreenState();
}

class _LessonPlansScreenState extends State<LessonPlansScreen> {
  Map<String, dynamic>? _planning;
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
      final data = await loadLessonPlanning();
      setState(() => _planning = data);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openAddPlan(String planLabel) async {
    final options = (_planning?['options'] ?? {}) as Map<String, dynamic>;
    final classes = (options['classes'] ?? []) as List<dynamic>;
    final subjects = (options['subjects'] ?? []) as List<dynamic>;
    if (classes.isEmpty || subjects.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('No assigned classes or subjects to plan for yet.')),
      );
      return;
    }
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _LessonPlanForm(
        classes: classes.cast<Map<String, dynamic>>(),
        subjects: subjects.cast<Map<String, dynamic>>(),
        planLabel: planLabel,
      ),
    );
    if (saved == true) _load();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final nonK12 = auth.isNonK12School;
    final plans = (_planning?['lesson_plans'] ?? []) as List<dynamic>;
    final planLabel = nonK12 ? 'Course outline' : 'Lesson plan';

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        foregroundColor: AppColors.text,
        title: Text(nonK12 ? 'Course Outline' : 'Lesson Plans',
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900)),
      ),
      floatingActionButton: FloatingActionButton.extended(
        backgroundColor: AppColors.primary,
        onPressed: () => _openAddPlan(planLabel),
        icon: const Icon(Icons.add, color: Colors.white),
        label: Text('Add $planLabel', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
      ),
      body: SafeArea(
        child: _planning == null && _loading
            ? const SkeletonList()
            : _error != null
                ? _ErrorState(planLabel: planLabel, onRetry: _load)
                : BrandedRefresh(
                    onRefresh: _load,
                    showSpinner: _loading,
                    child: ListView(
                      padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
                      children: [
                        if (plans.isEmpty)
                          Padding(
                            padding: const EdgeInsets.only(top: 40),
                            child: Center(
                              child: Text('No ${planLabel.toLowerCase()}s yet. Tap + to add one.',
                                  textAlign: TextAlign.center, style: TextStyle(color: AppColors.muted)),
                            ),
                          )
                        else
                          for (final raw in plans) ...[
                            _LessonPlanCard(item: raw as Map<String, dynamic>),
                            const SizedBox(height: 10),
                          ],
                      ],
                    ),
                  ),
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  final String planLabel;
  final VoidCallback onRetry;
  const _ErrorState({required this.planLabel, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, color: AppColors.danger, size: 40),
            const SizedBox(height: 12),
            Text("Couldn't load your ${planLabel.toLowerCase()}s.",
                style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
            const SizedBox(height: 4),
            Text('Check your connection and try again.',
                textAlign: TextAlign.center, style: TextStyle(color: AppColors.muted, fontSize: 13)),
            const SizedBox(height: 16),
            SizedBox(width: 160, child: PrimaryButton(title: 'Retry', onPressed: onRetry)),
          ],
        ),
      ),
    );
  }
}

class _LessonPlanCard extends StatelessWidget {
  final Map<String, dynamic> item;
  const _LessonPlanCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final status = (item['status'] ?? '').toString();
    final statusColor = status == 'completed'
        ? AppColors.success
        : status == 'draft'
            ? AppColors.muted
            : AppColors.warning;
    final statusLabel = status == 'planned' ? 'PUBLISHED' : status.toUpperCase();
    return AppCard(
      children: [
        Row(
          children: [
            Expanded(
              child: Text((item['title'] ?? 'Untitled').toString(),
                  style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: statusColor.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(statusLabel,
                  style: TextStyle(color: statusColor, fontWeight: FontWeight.w800, fontSize: 10)),
            ),
          ],
        ),
        Text('Week ${item['week_number'] ?? '-'} · ${item['subject'] ?? ''} · ${item['class_name'] ?? ''}',
            style: const TextStyle(color: AppColors.mutedDark, fontSize: 13)),
        if ((item['objectives'] ?? '').toString().isNotEmpty)
          Text(item['objectives'].toString(),
              maxLines: 2, overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: AppColors.mutedDark, fontSize: 13)),
      ],
    );
  }
}

class _LessonPlanForm extends StatefulWidget {
  final List<Map<String, dynamic>> classes;
  final List<Map<String, dynamic>> subjects;
  final String planLabel;
  const _LessonPlanForm({required this.classes, required this.subjects, required this.planLabel});

  @override
  State<_LessonPlanForm> createState() => _LessonPlanFormState();
}

class _LessonPlanFormState extends State<_LessonPlanForm> {
  late int _classId = widget.classes.first['id'] as int;
  late int _subjectId = widget.subjects.first['id'] as int;
  int _week = 1;
  final _title = TextEditingController();
  final _objectives = TextEditingController();
  final _activities = TextEditingController();
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _title.dispose();
    _objectives.dispose();
    _activities.dispose();
    super.dispose();
  }

  Future<void> _save(String status) async {
    if (_title.text.trim().isEmpty) {
      setState(() => _error = 'Enter a title.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await saveLessonPlan(
        classId: _classId,
        subjectId: _subjectId,
        weekNumber: _week,
        title: _title.text.trim(),
        objectives: _objectives.text.trim(),
        activities: _activities.text.trim(),
        status: status,
      );
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 20),
        decoration: const BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('New ${widget.planLabel.toLowerCase()}',
                  style: const TextStyle(color: AppColors.textDark, fontSize: 18, fontWeight: FontWeight.w900)),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: DropdownButtonFormField<int>(
                      initialValue: _classId,
                      style: const TextStyle(color: AppColors.textDark),
                      decoration: const InputDecoration(labelText: 'Class'),
                      items: [
                        for (final c in widget.classes)
                          DropdownMenuItem(
                            value: c['id'] as int,
                            child: Text((c['label'] ?? '').toString(),
                                style: const TextStyle(color: AppColors.textDark)),
                          ),
                      ],
                      onChanged: (v) => setState(() => _classId = v!),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: DropdownButtonFormField<int>(
                      initialValue: _subjectId,
                      style: const TextStyle(color: AppColors.textDark),
                      decoration: const InputDecoration(labelText: 'Subject'),
                      items: [
                        for (final s in widget.subjects)
                          DropdownMenuItem(
                            value: s['id'] as int,
                            child: Text((s['name'] ?? '').toString(),
                                style: const TextStyle(color: AppColors.textDark)),
                          ),
                      ],
                      onChanged: (v) => setState(() => _subjectId = v!),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              TextFormField(
                initialValue: '1',
                style: const TextStyle(color: AppColors.textDark),
                decoration: const InputDecoration(labelText: 'Week'),
                keyboardType: TextInputType.number,
                onChanged: (v) => _week = int.tryParse(v) ?? 1,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _title,
                style: const TextStyle(color: AppColors.textDark),
                decoration: const InputDecoration(labelText: 'Topic / scheme of work'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _objectives,
                style: const TextStyle(color: AppColors.textDark),
                decoration: const InputDecoration(labelText: 'Objectives'),
                maxLines: 2,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _activities,
                style: const TextStyle(color: AppColors.textDark),
                decoration: const InputDecoration(labelText: 'Activities'),
                maxLines: 2,
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: AppColors.danger)),
              ],
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _saving ? null : () => _save('draft'),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        side: BorderSide(color: AppColors.border),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      child: Text('Save Draft',
                          style: TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w800)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: PrimaryButton(
                      title: 'Publish',
                      loading: _saving,
                      onPressed: () => _save('planned'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
