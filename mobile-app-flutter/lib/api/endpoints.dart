import 'package:http/http.dart' as http;
import 'client.dart';

Future<Map<String, dynamic>> loadDashboard(String? role) {
  if (role == 'student') return getJson('/api/app/student/dashboard/');
  if (role == 'teacher') return getJson('/api/app/teacher/dashboard/');
  if (role == 'staff') return getJson('/api/hr/me/');
  return getJson('/api/app/dashboard/');
}

Future<Map<String, dynamic>> loadMessages() => getJson('/api/app/messages/');

Future<Map<String, dynamic>> sendMessage(Map<String, dynamic> payload) =>
    postJson('/api/app/messages/send/', payload, queueWhenOffline: true);

Future<Map<String, dynamic>> markMessageRead(String id) =>
    postJson('/api/app/messages/$id/read/', const {});

/// Photo/video/voice-note attachments (see users/app_views.py
/// `_collect_message_attachments` - up to 5 files, 10MB each, any content
/// type accepted). `filePath` is a local file path from image_picker or the
/// `record` package; `filename` controls the name shown to the recipient.
Future<Map<String, dynamic>> sendMessageWithAttachment({
  required String recipientEmail,
  String body = '',
  required String filePath,
  String? filename,
}) =>
    postMultipart(
      '/api/app/messages/send/',
      {'recipient_email': recipientEmail, 'body': body},
      () async => [
        await http.MultipartFile.fromPath('attachments', filePath, filename: filename),
      ],
    );

// Notifications are served from the same snapshot as Messages
// (data['notifications']); kept as its own named call for readability.
Future<Map<String, dynamic>> loadNotifications() =>
    getJson('/api/app/messages/');

Future<Map<String, dynamic>> markNotificationRead(String id) =>
    postJson('/api/app/notifications/$id/read/', const {});

Future<Map<String, dynamic>> loadExams() => getJson('/api/app/exams/');

Future<Map<String, dynamic>> loadResults() => getJson('/api/app/results/my/');

Future<Map<String, dynamic>> markAttendance(Map<String, dynamic> payload) =>
    postJson('/api/app/attendance/mark/', payload, queueWhenOffline: true);

Future<Map<String, dynamic>> registerDevice(Map<String, dynamic> payload) =>
    postJson('/api/app/mobile/device/', payload);

Future<Map<String, dynamic>> loadExpenses() =>
    getJson('/api/finance/admin/expenses/');

Future<Map<String, dynamic>> createExpense(Map<String, dynamic> payload) =>
    postJson('/api/finance/admin/expenses/', payload, queueWhenOffline: true);

Future<Map<String, dynamic>> deleteExpense(dynamic id) =>
    deleteJson('/api/finance/admin/expenses/$id/', queueWhenOffline: true);

Future<Map<String, dynamic>> loadFinanceTransactions({int limit = 50}) =>
    getJson('/api/finance/admin/transactions/?limit=$limit');
