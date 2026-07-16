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
