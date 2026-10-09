import 'client.dart';

/// mail_inbox/urls.py (backend/api/mail-inbox/) - gated by the Ops Console's
/// support_mail permission module, not school-tenant auth.
Future<Map<String, dynamic>> loadMessages({String? account, bool unreadOnly = false}) {
  final params = <String>[];
  if (account != null && account.isNotEmpty) params.add('account=$account');
  if (unreadOnly) params.add('unread_only=true');
  final query = params.isEmpty ? '' : '?${params.join('&')}';
  return getJson('/api/mail-inbox/messages/$query');
}

Future<Map<String, dynamic>> loadMessage(int id) =>
    getJson('/api/mail-inbox/messages/$id/');

Future<Map<String, dynamic>> markRead(int id, {bool isRead = true}) =>
    postJson('/api/mail-inbox/messages/$id/read/', {'is_read': isRead});

Future<Map<String, dynamic>> replyToMessage(int id, String body) =>
    postJson('/api/mail-inbox/messages/$id/reply/', {'body': body});
