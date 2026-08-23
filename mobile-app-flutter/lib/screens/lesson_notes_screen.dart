import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/teacher_endpoints.dart';
import '../auth/auth_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/primary_button.dart';

/// Mobile take on the web's "Lesson Plans & Notepad" (Course Outline &
/// Notepad at Non-K12 schools) - two simple lists (structured lesson plans,
/// and freeform quick notes) each with a "+" to add one via a bottom sheet
/// form, instead of the web's two-column form-plus-list layout which
/// wouldn't fit a phone screen.
class LessonNotesScreen extends StatefulWidget {
  const LessonNotesScreen({super.key});

  @override
  State<LessonNotesScreen> createState() => _LessonNotesScreenState();
}

class _LessonNotesScreenState extends State<LessonNotesScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController = TabController(length: 2, vsync: this);

  Map<String, dynamic>? _planning;
  List<dynamic> _notes = [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([loadLessonPlanning(), loadTeacherNotes()]);
      setState(() {
        _planning = results[0];
        _notes = (results[1]['notes'] ?? []) as List<dynamic>;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openAddPlan() async {
    final options = (_planning?['options'] ?? {}) as Map<String, dynamic>;
    final classes = (options['classes'] ?? []) as List<dynamic>;
    final subjects = (options['subjects'] ?? []) as List<dynamic>;
    if (classes.isEmpty || subjects.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No assigned classes or subjects to plan for yet.')),
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
      ),
    );
    if (saved == true) _load();
  }

  Future<void> _openAddNote() async {
    final saved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const _NoteForm(),
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
        title: Text(nonK12 ? 'Course Outline & Notepad' : 'Lesson Plans & Notepad',
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppColors.primary,
          unselectedLabelColor: AppColors.muted,
          indicatorColor: AppColors.primary,
          tabs: [Tab(text: nonK12 ? 'Course Outline' : 'Lesson Plans'), const Tab(text: 'Notes')],
        ),
      ),
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator(color: AppColors.primary))
            : _error != null
                ? Center(child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(_error!, style: const TextStyle(color: AppColors.danger)),
                  ))
                : TabBarView(
                    controller: _tabController,
                    children: [
                      RefreshIndicator(
                        onRefresh: _load,
                        color: AppColors.primary,
                        child: ListView(
                          padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
                          children: [
                            if (plans.isEmpty)
                              Padding(
                                padding: const EdgeInsets.only(top: 40),
                                child: Center(
                                  child: Text('No ${planLabel.toLowerCase()}s yet.',
                                      style: TextStyle(color: AppColors.muted)),
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
                      RefreshIndicator(
                        onRefresh: _load,
                        color: AppColors.primary,
                        child: ListView(
                          padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
                          children: [
                            if (_notes.isEmpty)
                              Padding(
                                padding: const EdgeInsets.only(top: 40),
                                child: Center(
                                  child: Text('No notes yet.', style: TextStyle(color: AppColors.muted)),
                                ),
                              )
                            else
                              for (final raw in _notes) ...[
                                _NoteCard(item: raw as Map<String, dynamic>),
                                const SizedBox(height: 10),
                              ],
                          ],
                        ),
                      ),
                    ],
                  ),
      ),
      floatingActionButton: AnimatedBuilder(
        animation: _tabController,
        builder: (context, _) => FloatingActionButton.extended(
          backgroundColor: AppColors.primary,
          onPressed: _tabController.index == 0 ? _openAddPlan : _openAddNote,
          icon: const Icon(Icons.add, color: Colors.white),
          label: Text(_tabController.index == 0 ? 'Add $planLabel' : 'Add note',
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
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
              child: Text(status.toUpperCase(),
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

class _NoteCard extends StatelessWidget {
  final Map<String, dynamic> item;
  const _NoteCard({required this.item});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      children: [
        Row(
          children: [
            if (item['pinned'] == true) ...[
              const Icon(Icons.push_pin, size: 14, color: AppColors.warning),
              const SizedBox(width: 6),
            ],
            Expanded(
              child: Text((item['title'] ?? 'Note').toString(),
                  style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
            ),
          ],
        ),
        if ((item['body'] ?? '').toString().isNotEmpty)
          Text(item['body'].toString(),
              maxLines: 4, overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: AppColors.mutedDark, fontSize: 13)),
      ],
    );
  }
}

class _LessonPlanForm extends StatefulWidget {
  final List<Map<String, dynamic>> classes;
  final List<Map<String, dynamic>> subjects;
  const _LessonPlanForm({required this.classes, required this.subjects});

  @override
  State<_LessonPlanForm> createState() => _LessonPlanFormState();
}

class _LessonPlanFormState extends State<_LessonPlanForm> {
  late int _classId = widget.classes.first['id'] as int;
  late int _subjectId = widget.subjects.first['id'] as int;
  int _week = 1;
  String _status = 'planned';
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

  Future<void> _save() async {
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
        status: _status,
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
              const Text('New lesson plan',
                  style: TextStyle(color: AppColors.textDark, fontSize: 18, fontWeight: FontWeight.w900)),
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
              Row(
                children: [
                  Expanded(
                    child: TextFormField(
                      initialValue: '1',
                      style: const TextStyle(color: AppColors.textDark),
                      decoration: const InputDecoration(labelText: 'Week'),
                      keyboardType: TextInputType.number,
                      onChanged: (v) => _week = int.tryParse(v) ?? 1,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: DropdownButtonFormField<String>(
                      initialValue: _status,
                      style: const TextStyle(color: AppColors.textDark),
                      decoration: const InputDecoration(labelText: 'Status'),
                      items: const [
                        DropdownMenuItem(
                            value: 'planned',
                            child: Text('Planned', style: TextStyle(color: AppColors.textDark))),
                        DropdownMenuItem(
                            value: 'completed',
                            child: Text('Completed', style: TextStyle(color: AppColors.textDark))),
                        DropdownMenuItem(
                            value: 'draft',
                            child: Text('Draft', style: TextStyle(color: AppColors.textDark))),
                      ],
                      onChanged: (v) => setState(() => _status = v!),
                    ),
                  ),
                ],
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
              PrimaryButton(title: 'Save', loading: _saving, onPressed: _save),
            ],
          ),
        ),
      ),
    );
  }
}

class _NoteForm extends StatefulWidget {
  const _NoteForm();

  @override
  State<_NoteForm> createState() => _NoteFormState();
}

class _NoteFormState extends State<_NoteForm> {
  final _title = TextEditingController(text: 'Quick note');
  final _body = TextEditingController();
  bool _pinned = false;
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _title.dispose();
    _body.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await saveTeacherNote(title: _title.text.trim(), body: _body.text.trim(), pinned: _pinned);
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
              const Text('New note',
                  style: TextStyle(color: AppColors.textDark, fontSize: 18, fontWeight: FontWeight.w900)),
              const SizedBox(height: 16),
              TextField(
                controller: _title,
                style: const TextStyle(color: AppColors.textDark),
                decoration: const InputDecoration(labelText: 'Title'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _body,
                style: const TextStyle(color: AppColors.textDark),
                decoration: const InputDecoration(
                  labelText: 'Note',
                  alignLabelWithHint: true,
                ),
                maxLines: 5,
              ),
              Row(
                children: [
                  Checkbox(
                    value: _pinned,
                    activeColor: AppColors.primary,
                    onChanged: (v) => setState(() => _pinned = v ?? false),
                  ),
                  const Text('Pin this note', style: TextStyle(color: AppColors.mutedDark)),
                ],
              ),
              if (_error != null) ...[
                Text(_error!, style: const TextStyle(color: AppColors.danger)),
                const SizedBox(height: 8),
              ],
              const SizedBox(height: 8),
              PrimaryButton(title: 'Save', loading: _saving, onPressed: _save),
            ],
          ),
        ),
      ),
    );
  }
}
