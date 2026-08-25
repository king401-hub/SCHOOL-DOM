import 'package:flutter/material.dart';
import '../api/admin_endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/avatar.dart';
import '../widgets/branded_refresh.dart';
import '../widgets/primary_button.dart';
import '../widgets/skeleton.dart';

enum _StaffTab { all, teaching, nonTeaching }

/// Admin app's Staff screen - backed entirely by the existing hr/views.py
/// `hr_snapshot` (already covers teaching + non-teaching staff in one call,
/// with a real summary), so this is a new screen only, no backend change.
class AdminStaffScreen extends StatefulWidget {
  const AdminStaffScreen({super.key});

  @override
  State<AdminStaffScreen> createState() => _AdminStaffScreenState();
}

class _AdminStaffScreenState extends State<AdminStaffScreen> {
  Map<String, dynamic>? _data;
  bool _loading = true;
  String? _error;
  _StaffTab _tab = _StaffTab.all;
  final _searchController = TextEditingController();
  String _query = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await loadHrOverview();
      setState(() => _data = data);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  List<Map<String, dynamic>> get _filtered {
    final all = ((_data?['staff'] ?? []) as List<dynamic>).cast<Map<String, dynamic>>();
    final byTab = switch (_tab) {
      _StaffTab.all => all,
      _StaffTab.teaching => all.where((s) => s['staff_type'] == 'teaching').toList(),
      _StaffTab.nonTeaching => all.where((s) => s['staff_type'] == 'non_teaching').toList(),
    };
    if (_query.trim().isEmpty) return byTab;
    final q = _query.trim().toLowerCase();
    return byTab
        .where((s) =>
            (s['name'] ?? '').toString().toLowerCase().contains(q) ||
            (s['role'] ?? '').toString().toLowerCase().contains(q))
        .toList();
  }

  @override
  Widget build(BuildContext context) {
    final summary = (_data?['summary'] ?? {}) as Map<String, dynamic>;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        foregroundColor: AppColors.text,
        title: const Text('Staff', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900)),
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
                          const Text("Couldn't load staff.",
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
                      padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                      children: [
                        TextField(
                          controller: _searchController,
                          style: const TextStyle(color: AppColors.textDark),
                          onChanged: (v) => setState(() => _query = v),
                          decoration: InputDecoration(
                            hintText: 'Search staff by name or role',
                            prefixIcon: Icon(Icons.search, color: AppColors.muted),
                          ),
                        ),
                        const SizedBox(height: 14),
                        SizedBox(
                          height: 36,
                          child: ListView(
                            scrollDirection: Axis.horizontal,
                            children: [
                              _FilterChip(
                                label: 'All Staff',
                                selected: _tab == _StaffTab.all,
                                onTap: () => setState(() => _tab = _StaffTab.all),
                              ),
                              const SizedBox(width: 8),
                              _FilterChip(
                                label: 'Teaching',
                                selected: _tab == _StaffTab.teaching,
                                onTap: () => setState(() => _tab = _StaffTab.teaching),
                              ),
                              const SizedBox(width: 8),
                              _FilterChip(
                                label: 'Non-Teaching',
                                selected: _tab == _StaffTab.nonTeaching,
                                onTap: () => setState(() => _tab = _StaffTab.nonTeaching),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 14),
                        Row(
                          children: [
                            Expanded(
                                child: _CountCard(label: 'Total Staff', value: '${summary['total_staff'] ?? 0}')),
                            const SizedBox(width: 10),
                            Expanded(
                                child: _CountCard(
                                    label: 'Teaching', value: '${summary['teaching_staff'] ?? 0}', color: AppColors.primary)),
                            const SizedBox(width: 10),
                            Expanded(
                                child: _CountCard(
                                    label: 'Non-Teaching',
                                    value: '${summary['non_teaching_staff'] ?? 0}',
                                    color: AppColors.secondary)),
                          ],
                        ),
                        const SizedBox(height: 16),
                        if (_filtered.isEmpty)
                          Padding(
                            padding: const EdgeInsets.only(top: 40),
                            child: Center(
                              child: Text('No staff match this filter.', style: TextStyle(color: AppColors.muted)),
                            ),
                          )
                        else
                          for (final s in _filtered) ...[
                            _StaffRow(item: s),
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

class _StaffRow extends StatelessWidget {
  final Map<String, dynamic> item;
  const _StaffRow({required this.item});

  @override
  Widget build(BuildContext context) {
    final active = item['employment_status'] == 'active';
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
                  Text((item['name'] ?? 'Staff').toString(),
                      style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
                  Text(
                      [item['role'], item['department']].where((v) => (v ?? '').toString().isNotEmpty).join(' · '),
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
              child: Text(active ? 'ACTIVE' : (item['employment_status'] ?? '').toString().toUpperCase(),
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
