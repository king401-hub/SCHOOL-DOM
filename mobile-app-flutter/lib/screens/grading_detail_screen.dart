import 'package:flutter/material.dart';
import '../api/grading_endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/primary_button.dart';
import '../widgets/skeleton.dart';

/// Grade every theory (essay/short-answer) question on one exam attempt,
/// then publish once all of them have a score. See
/// backend/exams/exam_views.py `attempt_theory_answers` / `grade_theory_answer`
/// / `publish_theory_grades_view`.
class GradingDetailScreen extends StatefulWidget {
  final int attemptId;
  const GradingDetailScreen({super.key, required this.attemptId});

  @override
  State<GradingDetailScreen> createState() => _GradingDetailScreenState();
}

class _GradingDetailScreenState extends State<GradingDetailScreen> {
  Map<String, dynamic>? _data;
  List<Map<String, dynamic>> _answers = [];
  bool _loading = true;
  bool _publishing = false;
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
      final data = await loadAttemptTheoryAnswers(widget.attemptId);
      setState(() {
        _data = data;
        _answers = ((data['answers'] ?? []) as List<dynamic>).cast<Map<String, dynamic>>();
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  bool get _allGraded => _answers.every((a) => a['score'] != null);

  Future<void> _saveScore(Map<String, dynamic> answer, double score, String feedback) async {
    try {
      final result = await gradeTheoryAnswer(
        widget.attemptId,
        answer['answer_id'] as int,
        score: score,
        feedback: feedback,
      );
      setState(() {
        answer['score'] = result['score'];
        answer['teacher_feedback'] = result['teacher_feedback'];
      });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Score saved.'), backgroundColor: AppColors.success),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.toString()), backgroundColor: AppColors.danger),
        );
      }
    }
  }

  Future<void> _publish() async {
    setState(() => _publishing = true);
    try {
      final result = await publishTheoryGrades(widget.attemptId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Published - ${result['percentage']}% (${result['score']}/${result['total_points']}).'),
            backgroundColor: AppColors.success,
          ),
        );
        Navigator.of(context).pop(true);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.toString()), backgroundColor: AppColors.danger),
        );
      }
    } finally {
      if (mounted) setState(() => _publishing = false);
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
          title: Text((_data?['student_name'] ?? 'Grade submission').toString(),
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
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
                            const Text("Couldn't load this submission.",
                                style: TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
                            const SizedBox(height: 16),
                            SizedBox(width: 160, child: PrimaryButton(title: 'Retry', onPressed: _load)),
                          ],
                        ),
                      ),
                    )
                  : Column(
                      children: [
                        Padding(
                          padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
                          child: Text((_data?['exam_title'] ?? '').toString(),
                              style: TextStyle(color: AppColors.muted, fontSize: 13, fontWeight: FontWeight.w700)),
                        ),
                        Expanded(
                          child: ListView(
                            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
                            children: [
                              for (int i = 0; i < _answers.length; i++) ...[
                                _AnswerCard(
                                  index: i + 1,
                                  answer: _answers[i],
                                  onSave: (score, feedback) => _saveScore(_answers[i], score, feedback),
                                ),
                                const SizedBox(height: 12),
                              ],
                            ],
                          ),
                        ),
                        Padding(
                          padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                          child: Column(
                            children: [
                              if (!_allGraded)
                                Padding(
                                  padding: const EdgeInsets.only(bottom: 8),
                                  child: Text('Score every answer below before publishing.',
                                      style: TextStyle(color: AppColors.muted, fontSize: 12)),
                                ),
                              PrimaryButton(
                                title: 'Publish Results',
                                loading: _publishing,
                                onPressed: _publish,
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
        ),
      );
  }
}

class _AnswerCard extends StatefulWidget {
  final int index;
  final Map<String, dynamic> answer;
  final void Function(double score, String feedback) onSave;
  const _AnswerCard({required this.index, required this.answer, required this.onSave});

  @override
  State<_AnswerCard> createState() => _AnswerCardState();
}

class _AnswerCardState extends State<_AnswerCard> {
  late final _scoreController =
      TextEditingController(text: widget.answer['score'] == null ? '' : '${widget.answer['score']}');
  late final _feedbackController = TextEditingController(text: (widget.answer['teacher_feedback'] ?? '').toString());
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _scoreController.dispose();
    _feedbackController.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    final points = (widget.answer['points'] as num?)?.toDouble() ?? 0;
    final score = double.tryParse(_scoreController.text.trim());
    if (score == null || score < 0 || score > points) {
      setState(() => _error = 'Enter a score between 0 and ${points.toStringAsFixed(points % 1 == 0 ? 0 : 1)}.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      widget.onSave(score, _feedbackController.text.trim());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final answer = widget.answer;
    final points = (answer['points'] as num?)?.toDouble() ?? 0;
    final graded = answer['score'] != null;
    final imageUrl = (answer['image'] ?? '').toString();

    return AppCard(
      elevated: true,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Text('Q${widget.index}. ${answer['question_text'] ?? ''}',
                  style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
              decoration: BoxDecoration(
                color: (graded ? AppColors.success : AppColors.warning).withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(graded ? 'GRADED' : 'PENDING',
                  style: TextStyle(
                      color: graded ? AppColors.success : AppColors.warning,
                      fontWeight: FontWeight.w800,
                      fontSize: 10)),
            ),
          ],
        ),
        if (imageUrl.isNotEmpty)
          ClipRRect(
            borderRadius: BorderRadius.circular(10),
            child: Image.network(imageUrl, fit: BoxFit.cover),
          ),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: AppColors.cardSoft, borderRadius: BorderRadius.circular(10)),
          child: Text(
            (answer['answer_text'] ?? '').toString().isEmpty
                ? 'No answer submitted.'
                : answer['answer_text'].toString(),
            style: TextStyle(
              color: (answer['answer_text'] ?? '').toString().isEmpty ? AppColors.muted : AppColors.mutedDark,
              fontSize: 13,
              fontStyle:
                  (answer['answer_text'] ?? '').toString().isEmpty ? FontStyle.italic : FontStyle.normal,
            ),
          ),
        ),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 90,
              child: TextField(
                controller: _scoreController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                style: const TextStyle(color: AppColors.textDark),
                decoration: InputDecoration(labelText: 'Score / ${points.toStringAsFixed(points % 1 == 0 ? 0 : 1)}'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: TextField(
                controller: _feedbackController,
                style: const TextStyle(color: AppColors.textDark),
                decoration: const InputDecoration(labelText: 'Feedback (optional)'),
              ),
            ),
          ],
        ),
        if (_error != null) Text(_error!, style: const TextStyle(color: AppColors.danger, fontSize: 12)),
        SizedBox(
          height: 40,
          child: PrimaryButton(title: 'Save', loading: _saving, onPressed: _save),
        ),
      ],
    );
  }
}
