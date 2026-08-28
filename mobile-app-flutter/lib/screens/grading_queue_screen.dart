import 'package:flutter/material.dart';
import '../api/grading_endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/branded_refresh.dart';
import '../widgets/primary_button.dart';
import '../widgets/skeleton.dart';
import 'grading_detail_screen.dart';

/// Submitted exam attempts that still have at least one ungraded theory
/// (essay/short-answer) question - the "Needs grading" list linked from the
/// teacher Home stat card and the admin Academics tab. Scoped server-side:
/// a teacher sees only their own exams; an admin sees their whole school.
class GradingQueueScreen extends StatefulWidget {
  const GradingQueueScreen({super.key});

  @override
  State<GradingQueueScreen> createState() => _GradingQueueScreenState();
}

class _GradingQueueScreenState extends State<GradingQueueScreen> {
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

  String _formatDate(dynamic raw) {
    final dt = DateTime.tryParse((raw ?? '').toString());
    if (dt == null) return '';
    final local = dt.toLocal();
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    final hour = local.hour % 12 == 0 ? 12 : local.hour % 12;
    final minute = local.minute.toString().padLeft(2, '0');
    final period = local.hour >= 12 ? 'PM' : 'AM';
    return '${months[local.month - 1]} ${local.day} · $hour:$minute $period';
  }

  Future<void> _openAttempt(Map<String, dynamic> attempt) async {
    final graded = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => GradingDetailScreen(attemptId: attempt['attempt_id'] as int)),
    );
    if (graded == true) _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        foregroundColor: AppColors.text,
        title: const Text('Needs Grading', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900)),
      ),
      body: SafeArea(
        child: _loading && _attempts.isEmpty
            ? const SkeletonList()
            : _error != null && _attempts.isEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.error_outline, color: AppColors.danger, size: 40),
                          const SizedBox(height: 12),
                          const Text("Couldn't load the grading queue.",
                              style: TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
                          const SizedBox(height: 16),
                          SizedBox(width: 160, child: PrimaryButton(title: 'Retry', onPressed: _load)),
                        ],
                      ),
                    ),
                  )
                : BrandedRefresh(
                    onRefresh: _load,
                    showSpinner: _loading && _attempts.isNotEmpty,
                    child: _attempts.isEmpty
                        ? ListView(
                            physics: const AlwaysScrollableScrollPhysics(),
                            children: [
                              Padding(
                                padding: const EdgeInsets.only(top: 80),
                                child: Center(
                                  child: Column(
                                    children: [
                                      Container(
                                        width: 64,
                                        height: 64,
                                        decoration: BoxDecoration(
                                            color: AppColors.success.withValues(alpha: 0.12), shape: BoxShape.circle),
                                        alignment: Alignment.center,
                                        child: const Icon(Icons.task_alt, size: 30, color: AppColors.success),
                                      ),
                                      const SizedBox(height: 14),
                                      Text('All caught up',
                                          style: TextStyle(color: AppColors.text, fontWeight: FontWeight.w900, fontSize: 16)),
                                      const SizedBox(height: 4),
                                      Text('No submissions are waiting to be graded.',
                                          style: TextStyle(color: AppColors.muted, fontSize: 13)),
                                    ],
                                  ),
                                ),
                              ),
                            ],
                          )
                        : ListView(
                            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
                            children: [
                              for (final raw in _attempts) ...[
                                _AttemptCard(
                                  item: raw as Map<String, dynamic>,
                                  formatDate: _formatDate,
                                  onTap: () => _openAttempt(raw),
                                ),
                                const SizedBox(height: 10),
                              ],
                            ],
                          ),
                  ),
      ),
    );
  }
}

class _AttemptCard extends StatelessWidget {
  final Map<String, dynamic> item;
  final String Function(dynamic) formatDate;
  final VoidCallback onTap;
  const _AttemptCard({required this.item, required this.formatDate, required this.onTap});

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
                    if (item['submitted_at'] != null)
                      Text('Submitted ${formatDate(item['submitted_at'])}',
                          style: TextStyle(color: AppColors.muted, fontSize: 11)),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: AppColors.muted),
            ],
          ),
        ],
      ),
    );
  }
}
