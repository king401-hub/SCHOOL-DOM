import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
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

/// Sender-only - see users/app_views.py `edit_message`.
Future<Map<String, dynamic>> editMessage(String id, String body) =>
    patchJson('/api/app/messages/$id/edit/', {'body': body});

/// "Delete for me" - either side can do this for their own view without
/// removing it for the other party. See users/app_views.py `delete_message`.
Future<Map<String, dynamic>> deleteMessage(String id) =>
    deleteJson('/api/app/messages/$id/');

/// One row per conversation partner, aggregated server-side across every
/// message the caller has ever sent/received - unlike loadMessages()'s
/// `inbox` (capped at the 20 most recent messages tenant-wide), a
/// conversation here can never silently disappear just because other people
/// sent messages more recently. See users/app_views.py `message_conversations`.
Future<Map<String, dynamic>> loadConversations() => getJson('/api/app/messages/conversations/');

/// Full history with one partner (most recent 200, chronological) -
/// independent of the same tenant-wide cap. See users/app_views.py
/// `message_thread`.
Future<Map<String, dynamic>> loadMessageThread(String partnerEmail) =>
    getJson('/api/app/messages/thread/?email=${Uri.encodeComponent(partnerEmail)}');

/// Photo/video/voice-note attachments (see users/app_views.py
/// `_collect_message_attachments` - up to 5 files, 10MB each, any content
/// type accepted). `filePath` is a local file path from image_picker or the
/// `record` package; `filename` controls the name shown to the recipient.
/// `contentType` (e.g. "image/jpeg") is required - without it, MultipartFile
/// silently defaults to "application/octet-stream", which is stored as-is
/// server-side and breaks the chat's image/video/audio previews once the
/// thread is reloaded from the server instead of shown from local state.
Future<Map<String, dynamic>> sendMessageWithAttachment({
  required String recipientEmail,
  String body = '',
  required String filePath,
  String? filename,
  required String contentType,
}) =>
    postMultipart(
      '/api/app/messages/send/',
      {'recipient_email': recipientEmail, 'body': body},
      () async => [
        await http.MultipartFile.fromPath(
          'attachments',
          filePath,
          filename: filename,
          contentType: MediaType.parse(contentType),
        ),
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
