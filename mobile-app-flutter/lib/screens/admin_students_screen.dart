import 'dart:async';

import 'package:flutter/material.dart';
import '../api/admin_endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/avatar.dart';
import '../widgets/branded_refresh.dart';
import '../widgets/primary_button.dart';
import '../widgets/skeleton.dart';

/// Admin app's Students screen - list/search/filter/add, backed by
/// users/app_views.py `students_snapshot` (now with optional class_id/status
/// filters and male/female counts added for this screen) and
/// `student_search` (existing, unchanged) for the search box.
class AdminStudentsScreen extends StatefulWidget {
  const AdminStudentsScreen({super.key});

  @override
  State<AdminStudentsScreen> createState() => _AdminStudentsScreenState();
}

enum _StudentTab { all, byClass, byStatus }

class _AdminStudentsScreenState extends State<AdminStudentsScreen> {
  Map<String, dynamic>? _data;
  List<dynamic> _students = [];
  bool _loading = true;
  String? _error;
  _StudentTab _tab = _StudentTab.all;
  int? _selectedClassId;
  String? _selectedStatus;
  final _searchController = TextEditingController();
  List<dynamic>? _searchResults;
  Timer? _searchDebounce;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _searchController.dispose();
    _searchDebounce?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await loadAdminStudents(classId: _selectedClassId, status: _selectedStatus);
      setState(() {
        _data = data;
        _students = (data['students'] ?? []) as List<dynamic>;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _onSearchChanged(String value) {
    _searchDebounce?.cancel();
    if (value.trim().length < 2) {
      setState(() => _searchResults = null);
      return;
    }
    _searchDebounce = Timer(const Duration(milliseconds: 350), () async {
      try {
        final data = await searchStudents(value.trim());
        if (mounted) setState(() => _searchResults = (data['results'] ?? []) as List<dynamic>);
      } catch (_) {
        // Leave previous results in place - search is a convenience, not a
        // primary data path.
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final summary = (_data?['summary'] ?? {}) as Map<String, dynamic>;
    final classes = ((_data?['options'] as Map<String, dynamic>?)?['classes'] ?? []) as List<dynamic>;
    final showingSearch = _searchResults != null;
    final listItems = showingSearch ? _searchResults! : _students;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        foregroundColor: AppColors.text,
        title: const Text('Students', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900)),
      ),
      floatingActionButton: Container(
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(28), gradient: AppGradients.brand),
        child: FloatingActionButton.extended(
          backgroundColor: Colors.transparent,
          elevation: 0,
          onPressed: () async {
            final added = await Navigator.of(context)
                .push<bool>(MaterialPageRoute(builder: (_) => _AddStudentScreen(classes: classes.cast<Map<String, dynamic>>())));
            if (added == true) _load();
          },
          icon: const Icon(Icons.person_add_alt_1, color: Colors.white),
          label: const Text('Add Student', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
        ),
      ),
      body: SafeArea(
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
                          const Text("Couldn't load students.",
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
                      padding: const EdgeInsets.fromLTRB(20, 8, 20, 90),
                      children: [
                        TextField(
                          controller: _searchController,
                          style: const TextStyle(color: AppColors.textDark),
                          onChanged: _onSearchChanged,
                          decoration: InputDecoration(
                            hintText: 'Search students by name or ID',
                            prefixIcon: Icon(Icons.search, color: AppColors.muted),
                            suffixIcon: showingSearch
                                ? IconButton(
                                    icon: Icon(Icons.close, color: AppColors.muted),
                                    onPressed: () {
                                      _searchController.clear();
                                      setState(() => _searchResults = null);
                                    },
                                  )
                                : null,
                          ),
                        ),
                        const SizedBox(height: 14),
                        if (!showingSearch) ...[
                          SizedBox(
                            height: 36,
                            child: ListView(
                              scrollDirection: Axis.horizontal,
                              children: [
                                _FilterChip(
                                  label: 'All Students',
                                  selected: _tab == _StudentTab.all,
                                  onTap: () => setState(() {
                                    _tab = _StudentTab.all;
                                    _selectedClassId = null;
                                    _selectedStatus = null;
                                    _load();
                                  }),
                                ),
                                const SizedBox(width: 8),
                                _FilterChip(
                                  label: 'By Class',
                                  selected: _tab == _StudentTab.byClass,
                                  onTap: () => setState(() => _tab = _StudentTab.byClass),
                                ),
                                const SizedBox(width: 8),
                                _FilterChip(
                                  label: 'By Status',
                                  selected: _tab == _StudentTab.byStatus,
                                  onTap: () => setState(() => _tab = _StudentTab.byStatus),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 12),
                          if (_tab == _StudentTab.byClass)
                            SizedBox(
                              height: 36,
                              child: ListView(
                                scrollDirection: Axis.horizontal,
                                children: [
                                  for (final c in classes) ...[
                                    _FilterChip(
                                      label: (c as Map<String, dynamic>)['label'].toString(),
                                      selected: _selectedClassId == c['id'],
                                      onTap: () => setState(() {
                                        _selectedClassId = c['id'] as int;
                                        _load();
                                      }),
                                    ),
                                    const SizedBox(width: 8),
                                  ],
                                ],
                              ),
                            ),
                          if (_tab == _StudentTab.byStatus)
                            SizedBox(
                              height: 36,
                              child: ListView(
                                scrollDirection: Axis.horizontal,
                                children: [
                                  for (final s in const [
                                    ['active', 'Active'],
                                    ['inactive', 'Inactive'],
                                    ['unassigned', 'No class'],
                                  ]) ...[
                                    _FilterChip(
                                      label: s[1],
                                      selected: _selectedStatus == s[0],
                                      onTap: () => setState(() {
                                        _selectedStatus = s[0];
                                        _load();
                                      }),
                                    ),
                                    const SizedBox(width: 8),
                                  ],
                                ],
                              ),
                            ),
                          const SizedBox(height: 14),
                          Row(
                            children: [
                              Expanded(
                                child: _CountCard(label: 'Total Students', value: '${summary['total_students'] ?? 0}'),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: _CountCard(
                                    label: 'Male', value: '${summary['male_count'] ?? 0}', color: AppColors.primary),
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: _CountCard(
                                    label: 'Female', value: '${summary['female_count'] ?? 0}', color: AppColors.secondary),
                              ),
                            ],
                          ),
                          const SizedBox(height: 16),
                        ],
                        if (listItems.isEmpty)
                          Padding(
                            padding: const EdgeInsets.only(top: 40),
                            child: Center(
                              child: Text(showingSearch ? 'No students match your search.' : 'No students yet.',
                                  style: TextStyle(color: AppColors.muted)),
                            ),
                          )
                        else
                          for (final raw in listItems) ...[
                            _StudentRow(item: raw as Map<String, dynamic>),
                            const SizedBox(height: 10),
                          ],
                      ],
                    ),
                  ),
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _FilterChip({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          gradient: selected ? AppGradients.brand : null,
          color: selected ? null : AppColors.surfaceSoft,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: selected ? Colors.transparent : AppColors.border),
        ),
        child: Text(label,
            style: TextStyle(
                color: selected ? Colors.white : AppColors.text, fontWeight: FontWeight.w800, fontSize: 13)),
      ),
    );
  }
}

class _CountCard extends StatelessWidget {
  final String label;
  final String value;
  final Color? color;
  const _CountCard({required this.label, required this.value, this.color});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.all(14),
      children: [
        Text(label, style: const TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w800, fontSize: 11)),
        Text(value,
            style: TextStyle(color: color ?? AppColors.textDark, fontSize: 20, fontWeight: FontWeight.w900)),
      ],
    );
  }
}

class _StudentRow extends StatelessWidget {
  final Map<String, dynamic> item;
  const _StudentRow({required this.item});

  @override
  Widget build(BuildContext context) {
    final active = item['is_active'] != false;
    return AppCard(
      children: [
        Row(
          children: [
            Avatar(name: (item['name'] ?? '').toString(), pictureUrl: item['profile_picture'] as String?),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text((item['name'] ?? 'Student').toString(),
                      style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
                  Text('${item['student_id'] ?? ''} · ${item['class_name'] ?? 'Unassigned'}',
                      style: const TextStyle(color: AppColors.mutedDark, fontSize: 12)),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: (active ? AppColors.success : AppColors.muted).withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(active ? 'ACTIVE' : 'INACTIVE',
                  style: TextStyle(
                      color: active ? AppColors.success : AppColors.muted,
                      fontWeight: FontWeight.w800,
                      fontSize: 10)),
            ),
          ],
        ),
      ],
    );
  }
}

class _AddStudentScreen extends StatefulWidget {
  final List<Map<String, dynamic>> classes;
  const _AddStudentScreen({required this.classes});

  @override
  State<_AddStudentScreen> createState() => _AddStudentScreenState();
}

class _AddStudentScreenState extends State<_AddStudentScreen> {
  final _email = TextEditingController();
  final _firstName = TextEditingController();
  final _lastName = TextEditingController();
  final _guardianName = TextEditingController();
  final _guardianPhone = TextEditingController();
  int? _classId;
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _firstName.dispose();
    _lastName.dispose();
    _guardianName.dispose();
    _guardianPhone.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_email.text.trim().isEmpty) {
      setState(() => _error = 'Email is required.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await createStudent(
        email: _email.text.trim(),
        firstName: _firstName.text.trim(),
        lastName: _lastName.text.trim(),
        classId: _classId,
        guardianName: _guardianName.text.trim(),
        guardianPhone: _guardianPhone.text.trim(),
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
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        foregroundColor: AppColors.text,
        title: const Text('Add Student', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
          children: [
            TextField(
              controller: _email,
              style: const TextStyle(color: AppColors.textDark),
              decoration: const InputDecoration(labelText: 'Student email *'),
              keyboardType: TextInputType.emailAddress,
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _firstName,
                    style: const TextStyle(color: AppColors.textDark),
                    decoration: const InputDecoration(labelText: 'First name'),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: _lastName,
                    style: const TextStyle(color: AppColors.textDark),
                    decoration: const InputDecoration(labelText: 'Last name'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
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
            TextField(
              controller: _guardianName,
              style: const TextStyle(color: AppColors.textDark),
              decoration: const InputDecoration(labelText: 'Guardian name'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _guardianPhone,
              style: const TextStyle(color: AppColors.textDark),
              decoration: const InputDecoration(labelText: 'Guardian phone'),
              keyboardType: TextInputType.phone,
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: AppColors.danger)),
            ],
            const SizedBox(height: 20),
            PrimaryButton(title: 'Add Student', loading: _saving, onPressed: _save),
          ],
        ),
      ),
    );
  }
}
