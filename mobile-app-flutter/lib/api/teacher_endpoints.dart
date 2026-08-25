import 'client.dart';

/// Read-only for teachers - the backend scopes /api/app/timetables/ to the
/// caller's own entries automatically (see users/app_views.py
/// timetables_snapshot); only admins can create entries.
Future<Map<String, dynamic>> loadTimetable() => getJson('/api/app/timetables/');

/// See users/app_views.py `lesson_planning` (GET returns the roster of
/// lesson plans + class/subject options, POST upserts one plan keyed on
/// teacher+year+term+class+subject+week).
Future<Map<String, dynamic>> loadLessonPlanning() => getJson('/api/app/academic/planning/');

Future<Map<String, dynamic>> saveLessonPlan({
  required int classId,
  required int subjectId,
  required int weekNumber,
  required String title,
  String objectives = '',
  String activities = '',
  String resources = '',
  String assessment = '',
  String notes = '',
  String status = 'planned',
}) =>
    postJson('/api/app/academic/planning/', {
      'class_id': classId,
      'subject_id': subjectId,
      'week_number': weekNumber,
      'title': title,
      'objectives': objectives,
      'activities': activities,
      'resources': resources,
      'assessment': assessment,
      'notes': notes,
      'status': status,
    });

/// See users/app_views.py `teacher_notes`.
Future<Map<String, dynamic>> loadTeacherNotes() => getJson('/api/app/academic/notes/');

Future<Map<String, dynamic>> saveTeacherNote({
  required String title,
  required String body,
  bool pinned = false,
}) =>
    postJson('/api/app/academic/notes/', {
      'title': title,
      'body': body,
      'pinned': pinned,
    });

/// See users/app_views.py `teacher_note_detail`.
Future<Map<String, dynamic>> editTeacherNote(
  int id, {
  String? title,
  String? body,
  bool? pinned,
}) =>
    patchJson('/api/app/academic/notes/$id/', {
      if (title != null) 'title': title,
      if (body != null) 'body': body,
      if (pinned != null) 'pinned': pinned,
    });

Future<Map<String, dynamic>> deleteTeacherNote(int id) =>
    deleteJson('/api/app/academic/notes/$id/');
