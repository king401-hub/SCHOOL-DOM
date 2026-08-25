import 'client.dart';

/// Students screen (list/search/filter). Backend: users/app_views.py
/// `students_snapshot` - class_id/status are optional server-side filters
/// added for this screen; omitting them keeps existing callers unaffected.
Future<Map<String, dynamic>> loadAdminStudents({int? classId, String? status}) {
  final params = <String>[];
  if (classId != null) params.add('class_id=$classId');
  if (status != null && status.isNotEmpty) params.add('status=$status');
  final query = params.isEmpty ? '' : '?${params.join('&')}';
  return getJson('/api/app/students/$query');
}

Future<Map<String, dynamic>> searchStudents(String query) =>
    getJson('/api/app/students/search/?q=${Uri.encodeComponent(query)}');

/// See users/app_views.py `create_student` - only `student_email` is
/// actually required server-side; everything else here is optional.
Future<Map<String, dynamic>> createStudent({
  required String email,
  String firstName = '',
  String lastName = '',
  int? classId,
  String guardianName = '',
  String guardianPhone = '',
}) =>
    postJson('/api/app/students/create/', {
      'student_email': email,
      'first_name': firstName,
      'last_name': lastName,
      if (classId != null) 'class_id': classId,
      'guardian_name': guardianName,
      'guardian_phone': guardianPhone,
    });

/// Finance overview (collected/outstanding/expected/rate) - see
/// finance/views.py `admin_overview`. Heavier than the mobile app strictly
/// needs (it also carries ledger/activation-credit detail meant for the web
/// dashboard) but it's the one endpoint with the real ₦ amounts, so this
/// reuses it rather than standing up a duplicate lightweight one.
Future<Map<String, dynamic>> loadFinanceOverview() => getJson('/api/finance/admin/overview/');

/// Staff directory + summary (teaching + non-teaching in one call) - see
/// hr/views.py `hr_snapshot`.
Future<Map<String, dynamic>> loadHrOverview() => getJson('/api/hr/overview/');

/// Present/Absent/Late/Not-Marked counts for one day, school-wide. See
/// users/app_views.py `admin_attendance_summary`.
Future<Map<String, dynamic>> loadAdminAttendanceSummary() =>
    getJson('/api/app/attendance/admin-summary/');

/// Announcements (Notice/Circular/Event). See users/app_views.py
/// `announcements_list` / `announcement_create` / `announcement_detail`.
Future<Map<String, dynamic>> loadAnnouncements({String? category}) {
  final query = (category != null && category.isNotEmpty) ? '?category=$category' : '';
  return getJson('/api/app/announcements/$query');
}

Future<Map<String, dynamic>> createAnnouncement({
  required String title,
  required String content,
  required String category,
}) =>
    postJson('/api/app/announcements/create/', {
      'title': title,
      'content': content,
      'category': category,
    });

Future<Map<String, dynamic>> editAnnouncement(
  String id, {
  String? title,
  String? content,
  String? category,
  bool? isPublished,
}) =>
    patchJson('/api/app/announcements/$id/', {
      if (title != null) 'title': title,
      if (content != null) 'content': content,
      if (category != null) 'category': category,
      if (isPublished != null) 'is_published': isPublished,
    });

Future<Map<String, dynamic>> deleteAnnouncement(String id) =>
    deleteJson('/api/app/announcements/$id/');

/// Creates a draft exam (title/class/subject/format/dates/duration, no
/// questions yet) - see users/app_views.py `create_exam`. Full CBT question
/// authoring stays a web-dashboard task; this gives an admin a quick way to
/// stand up the exam shell from their phone.
Future<Map<String, dynamic>> createExamDraft({
  required String title,
  int? classId,
  int? subjectId,
  required DateTime startDate,
  required DateTime endDate,
  required int durationMinutes,
  required String examFormat,
  bool isPublished = false,
}) =>
    postJson('/api/app/exams/create/', {
      'title': title,
      if (classId != null) 'class_id': classId,
      if (subjectId != null) 'subject_id': subjectId,
      'start_date': startDate.toIso8601String(),
      'end_date': endDate.toIso8601String(),
      'duration_minutes': durationMinutes,
      'exam_format': examFormat,
      'is_published': isPublished,
      'questions': [],
    });
