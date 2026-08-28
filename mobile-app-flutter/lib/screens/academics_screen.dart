import 'package:flutter/material.dart';
import '../api/endpoints.dart';
import '../api/grading_endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/branded_refresh.dart';
import '../widgets/primary_button.dart';
import '../widgets/skeleton.dart';
import 'create_exam_screen.dart';
import 'grading_detail_screen.dart';

/// Admin app's "Academics" nav tab - All Exams / CBT / Results / Grading,
/// all pulled from the single existing users/app_views.py `exams_snapshot`
/// payload (exam_format was added to each exam row for the CBT filter;
/// everything else - exams, submitted_results, class/subject options -
/// already existed). Grading itself is its own screen (GradingQueueScreen),
/// reached via a tab here since it's still an exams-related workflow.
class AcademicsScreen extends StatefulWidget {
  const AcademicsScreen({super.key});

  @override
  State<AcademicsScreen> createState() => _AcademicsScreenState();
}

class _AcademicsScreenState extends State<AcademicsScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabController = TabController(length: 4, vsync: this);
  Map<String, dynamic>? _data;
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
      final data = await loadExams();
      setState(() => _data = data);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openCreate() async {
    final options = (_data?['options'] ?? {}) as Map<String, dynamic>;
    final created = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => CreateExamScreen(
          classes: ((options['classes'] ?? []) as List<dynamic>).cast<Map<String, dynamic>>(),
          subjects: ((options['subjects'] ?? []) as List<dynamic>).cast<Map<String, dynamic>>(),
        ),
      ),
    );
    if (created == true) _load();
  }

  @override
  Widget build(BuildContext context) {
    final allExams = (_data?['exams'] ?? []) as List<dynamic>;
    final cbtExams = allExams.where((e) => (e as Map)['exam_format'] != 'theory').toList();
    final results = (_data?['submitted_results'] ?? []) as List<dynamic>;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        foregroundColor: AppColors.text,
        title: const Text('Exams', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900)),
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppColors.primary,
          unselectedLabelColor: AppColors.muted,
          indicatorColor: AppColors.primary,
          tabs: const [Tab(text: 'All Exams'), Tab(text: 'CBT'), Tab(text: 'Results'), Tab(text: 'Grading')],
        ),
      ),
      floatingActionButton: Container(
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(28), gradient: AppGradients.brand),
        child: FloatingActionButton.extended(
          backgroundColor: Colors.transparent,
          elevation: 0,
          onPressed: _openCreate,
          icon: const Icon(Icons.add, color: Colors.white),
          label: const Text('Create New Exam', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
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
                          const Text("Couldn't load exams.",
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
                    child: TabBarView(
                      controller: _tabController,
                      children: [
                        _ExamList(items: allExams.cast<Map<String, dynamic>>()),
                        _ExamList(items: cbtExams.cast<Map<String, dynamic>>()),
                        _ResultsList(items: results.cast<Map<String, dynamic>>()),
                        const _GradingTab(),
                      ],
                    ),
                  ),
      ),
    );
  }
}

class _ExamList extends StatelessWidget {
  final List<Map<String, dynamic>> items;
  const _ExamList({required this.items});

  String _formatDate(dynamic raw) {
    final dt = DateTime.tryParse((raw ?? '').toString());
    if (dt == null) return '';
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${months[dt.month - 1]} ${dt.day}, ${dt.year}';
  }

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return Center(child: Text('No exams found.', style: TextStyle(color: AppColors.muted)));
    }
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 90),
      children: [
        for (final item in items) ...[
          AppCard(
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text((item['title'] ?? 'Exam').toString(),
                        style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: (item['is_published'] == true ? AppColors.success : AppColors.warning).withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Text(item['is_published'] == true ? 'PUBLISHED' : 'DRAFT',
                        style: TextStyle(
                            color: item['is_published'] == true ? AppColors.success : AppColors.warning,
                            fontWeight: FontWeight.w800,
                            fontSize: 10)),
                  ),
                ],
              ),
              Text('${item['subject'] ?? 'General'} · ${item['class_name'] ?? 'All classes'}',
                  style: const TextStyle(color: AppColors.mutedDark, fontSize: 13)),
              Text(_formatDate(item['start_date']), style: TextStyle(color: AppColors.muted, fontSize: 12)),
            ],
          ),
          const SizedBox(height: 10),
        ],
      ],
    );
  }
}

class _ResultsList extends StatelessWidget {
  final List<Map<String, dynamic>> items;
  const _ResultsList({required this.items});

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return Center(child: Text('No submitted results yet.', style: TextStyle(color: AppColors.muted)));
    }
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 90),
      children: [
        for (final item in items) ...[
          AppCard(
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text((item['exam_title'] ?? 'Exam').toString(),
                        style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
                  ),
                  Text('${item['percentage'] ?? 0}%',
                      style: const TextStyle(color: AppColors.primary, fontWeight: FontWeight.w900)),
                ],
              ),
              Text('${item['student_name'] ?? ''} · ${item['class_name'] ?? ''}',
                  style: const TextStyle(color: AppColors.mutedDark, fontSize: 13)),
            ],
          ),
          const SizedBox(height: 10),
        ],
      ],
    );
  }
}

/// Submitted attempts with at least one ungraded theory answer - embedded
/// directly (rather than pushing GradingQueueScreen) so it sits inline as
/// this tab's content instead of nesting a second Scaffold/AppBar.
class _GradingTab extends StatefulWidget {
  const _GradingTab();

  @override
  State<_GradingTab> createState() => _GradingTabState();
}

class _GradingTabState extends State<_GradingTab> {
  List<dynamic> _attempts = [];
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
      final data = await loadGradingQueue();
      setState(() => _attempts = (data['attempts'] ?? []) as List<dynamic>);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _open(Map<String, dynamic> attempt) async {
    final graded = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => GradingDetailScreen(attemptId: attempt['attempt_id'] as int)),
    );
    if (graded == true) _load();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading && _attempts.isEmpty) {
      return const Center(child: CircularProgressIndicator(color: AppColors.primary));
    }
    if (_error != null && _attempts.isEmpty) {
      return Center(child: Text(_error!, style: const TextStyle(color: AppColors.danger)));
    }
    if (_attempts.isEmpty) {
      return Center(child: Text('No submissions need grading right now.', style: TextStyle(color: AppColors.muted)));
    }
    return RefreshIndicator(
      onRefresh: _load,
      color: AppColors.primary,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 90),
        children: [
          for (final raw in _attempts) ...[
            _GradingAttemptRow(item: raw as Map<String, dynamic>, onTap: () => _open(raw)),
            const SizedBox(height: 10),
          ],
        ],
      ),
    );
  }
}

class _GradingAttemptRow extends StatelessWidget {
  final Map<String, dynamic> item;
  final VoidCallback onTap;
  const _GradingAttemptRow({required this.item, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AppCard(
        children: [
          Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text((item['student_name'] ?? 'Student').toString(),
                        style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
                    Text((item['exam_title'] ?? 'Exam').toString(),
                        style: const TextStyle(color: AppColors.mutedDark, fontSize: 13)),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(color: AppColors.warning.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(20)),
                child: const Text('PENDING',
                    style: TextStyle(color: AppColors.warning, fontWeight: FontWeight.w800, fontSize: 10)),
              ),
              const SizedBox(width: 6),
              Icon(Icons.chevron_right, color: AppColors.muted),
            ],
          ),
        ],
      ),
    );
  }
}
