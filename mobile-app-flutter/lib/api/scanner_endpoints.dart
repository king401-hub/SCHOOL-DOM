import 'client.dart';

/// Tag written into AttendanceRecord.device_info / TeacherAttendance's
/// client_device_info via the existing `location.device_info` field every
/// attendance endpoint already accepts - there is no dedicated "source"
/// column, so this is how scans from this app stay distinguishable in
/// reports from web/GPS-recorded attendance without a schema change.
const _scannerSource = 'SchoolDom Scanner';

/// Extracts the bare token from a scanned QR value that may be a full URL
/// (`.../attendance/scan/<token>` or `...?token=<token>`) or already a bare
/// token. Mirrors the tolerant parsing the backend already applies to the
/// student/ID-card scan endpoints (see users/app_views.py
/// `_qr_token_from_request` / `_id_card_token_from_value`) - needed here only
/// because the shared "gate" QR endpoint takes its token from the URL path,
/// so the app must build that path itself before the request goes out.
String extractGateToken(String raw) {
  final value = raw.trim();
  if (value.isEmpty) return value;
  final tokenMatch = RegExp(r'token=([^&]+)').firstMatch(value);
  if (tokenMatch != null) {
    return Uri.decodeComponent(tokenMatch.group(1)!);
  }
  if (value.contains('/')) {
    final trimmed = value.replaceAll(RegExp(r'/+$'), '');
    return trimmed.split('/').last;
  }
  return value;
}

/// Admin/teacher scanning a STUDENT's personal ID-card QR to mark that
/// student's attendance. Backend already tolerates any raw scanned format
/// (full verify URL, query param, or bare token) - see
/// users/app_views.py `id_card_scan_attendance`.
Future<Map<String, dynamic>> scanStudentAttendance(String rawScan) => postJson(
    '/api/app/id-cards/scan-attendance/',
    {'token': rawScan, 'location': {'device_info': _scannerSource}});

/// Non-K12 student scanning the shared per-school gate QR to mark their own
/// attendance. See users/app_views.py `student_qr_mark_attendance`.
Future<Map<String, dynamic>> scanMyAttendanceStudent(String rawScan) => postJson(
    '/api/app/attendance/student-qr-mark/',
    {'token': rawScan, 'location': {'device_info': _scannerSource}});

/// Admin/teacher scanning the same shared per-school gate QR to self check-in.
/// This endpoint (attendance/views.py `scan_qr_code`) deliberately runs with
/// authentication disabled server-side (kiosk support) and instead resolves
/// the acting user from an `email`/`user_id` field in the body, so the
/// caller's own verified session email is passed explicitly rather than
/// relying on the Authorization header.
Future<Map<String, dynamic>> scanMyAttendanceStaff(
  String rawScan, {
  required String actorEmail,
  double? latitude,
  double? longitude,
  double? accuracy,
}) {
  final token = extractGateToken(rawScan);
  return postJson('/api/attendance/scan/$token/', {
    'email': actorEmail,
    'location': {
      'latitude': ?latitude,
      'longitude': ?longitude,
      'accuracy': ?accuracy,
      'device_info': _scannerSource,
    },
  });
}

/// Today's self check-in status for the logged-in admin/teacher.
Future<Map<String, dynamic>> myAttendanceStatusStaff(
        {required String actorEmail}) =>
    getJson('/api/attendance/check-status/?email=${Uri.encodeComponent(actorEmail)}');

String _isoDate(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// Tap Attendance: a teacher/admin steps through their class roster one
/// student at a time instead of scanning an ID card - K12 schools only (see
/// users/app_views.py `teacher_class_students`). Omitting classId returns
/// just the `classes` picker list; passing it also returns that class's
/// `students` and today's `attendance_records` for the given date.
Future<Map<String, dynamic>> loadClassStudents({
  int? classId,
  required DateTime date,
}) {
  final params = <String, String>{'date': _isoDate(date)};
  if (classId != null) params['class_id'] = classId.toString();
  final query = params.entries.map((e) => '${e.key}=${Uri.encodeComponent(e.value)}').join('&');
  return getJson('/api/app/attendance/class-students/?$query');
}

/// See users/app_views.py `teacher_mark_student_attendance`.
Future<Map<String, dynamic>> markStudentAttendance({
  required String studentId,
  required int classId,
  required String status,
  required DateTime date,
}) =>
    postJson('/api/app/attendance/teacher-mark/', {
      'student_id': studentId,
      'class_id': classId,
      'status': status,
      'date': _isoDate(date),
    });

/// SchoolDom Scanner's History page: student attendance for one day,
/// optionally filtered by class. See users/app_views.py
/// `scanner_attendance_history` - works at every school type (unlike
/// student_attendance_list, a separate Non-K12-only feature), and is scoped
/// to the whole school for admins or just the teacher's own classes.
Future<Map<String, dynamic>> loadScannerAttendanceHistory({
  DateTime? date,
  int? classId,
}) {
  final params = <String, String>{};
  if (date != null) {
    params['date'] =
        '${date.year.toString().padLeft(4, '0')}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  }
  if (classId != null) params['class_id'] = classId.toString();
  final query = params.entries.map((e) => '${e.key}=${Uri.encodeComponent(e.value)}').join('&');
  final suffix = query.isEmpty ? '' : '?$query';
  return getJson('/api/app/attendance/scanner-history/$suffix');
}
