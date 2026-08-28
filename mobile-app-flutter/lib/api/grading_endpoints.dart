import 'client.dart';

/// Theory-answer grading (essay/short-answer questions that can't be
/// auto-graded by the CBT engine) - see backend/exams/exam_views.py
/// `theory_grading_queue` / `attempt_theory_answers` / `grade_theory_answer` /
/// `publish_theory_grades_view`. Scoped server-side by role: a teacher only
/// sees attempts for exams they authored; an admin sees their whole school.

/// Submitted attempts that still have at least one ungraded theory answer.
Future<Map<String, dynamic>> loadGradingQueue() => getJson('/api/exams/theory/queue/');

/// Every theory-type answer for one attempt, for the grading detail screen.
Future<Map<String, dynamic>> loadAttemptTheoryAnswers(int attemptId) =>
    getJson('/api/exams/attempt/$attemptId/theory-answers/');

Future<Map<String, dynamic>> gradeTheoryAnswer(
  int attemptId,
  int answerId, {
  required double score,
  String feedback = '',
}) =>
    postJson('/api/exams/attempt/$attemptId/theory-answers/$answerId/grade/', {
      'score': score,
      'feedback': feedback,
    });

/// Only succeeds once every theory answer on the attempt has a score.
Future<Map<String, dynamic>> publishTheoryGrades(int attemptId) =>
    postJson('/api/exams/attempt/$attemptId/publish-theory-grades/', const {});
