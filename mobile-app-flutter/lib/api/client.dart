import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../storage/offline_queue.dart';
import '../storage/session_store.dart';
import 'config.dart';

class ApiException implements Exception {
  final String message;
  final int? statusCode;
  ApiException(this.message, {this.statusCode});
  @override
  String toString() => message;
}

class SessionExpiredException implements Exception {}

String _parseError(dynamic data, String fallback) {
  if (data == null) return fallback;
  if (data is String) return data;
  if (data is Map) {
    for (final k in ['message', 'detail', 'error']) {
      if (data[k] != null) return data[k].toString();
    }
    final first = data.entries.firstOrNull;
    if (first != null) {
      final v = first.value;
      return '${first.key}: ${v is List ? v.first : v}';
    }
  }
  return fallback;
}

Future<Map<String, dynamic>?> _tryRefresh(
    Map<String, dynamic> session) async {
  final refresh = session['refresh'] as String?;
  if (refresh == null) {
    await clearSession();
    throw SessionExpiredException();
  }
  final res = await http.post(
    Uri.parse('$apiBaseUrl/api/auth/refresh/'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({'refresh': refresh}),
  );
  final data =
      res.body.isNotEmpty ? jsonDecode(res.body) as Map<String, dynamic> : null;
  if (res.statusCode != 200 || data?['access'] == null) {
    await clearSession();
    throw SessionExpiredException();
  }
  final next = {
    ...session,
    'access': data!['access'],
    if (data['refresh'] != null) 'refresh': data['refresh'],
    'signedInAt': DateTime.now().toIso8601String(),
  };
  await saveSession(next);
  return next;
}

Future<Map<String, dynamic>> apiRequest(
  String method,
  String endpoint, {
  dynamic payload,
  bool retry = true,
  bool queueWhenOffline = false,
}) async {
  var session = await getSession();
  if (session?['access'] == null) {
    await clearSession();
    throw SessionExpiredException();
  }

  final uri = Uri.parse('$apiBaseUrl$endpoint');
  final isForm = payload is Map && payload.containsKey('_form');

  Map<String, String> headers = {
    'Authorization': 'Bearer ${session!['access']}',
  };
  Object? body;
  if (payload != null && !isForm) {
    headers['Content-Type'] = 'application/json';
    body = jsonEncode(payload);
  }

  http.Response res;
  try {
    res = await _send(method, uri, headers, body);
  } on SocketException catch (_) {
    if (queueWhenOffline && method != 'GET') {
      await enqueue({'method': method, 'endpoint': endpoint, 'payload': payload});
      return {'success': true, 'offline': true, 'message': 'Saved offline.'};
    }
    throw ApiException('Network error. Check your connection.');
  }

  if (res.statusCode == 401 && retry) {
    session = await _tryRefresh(session);
    headers['Authorization'] = 'Bearer ${session!['access']}';
    try {
      res = await _send(method, uri, headers, body);
    } on SocketException catch (_) {
      throw ApiException('Network error. Check your connection.');
    }
  }

  final data = res.body.isNotEmpty
      ? jsonDecode(res.body) as Map<String, dynamic>
      : <String, dynamic>{};

  if (res.statusCode >= 200 && res.statusCode < 300) return data;

  if (res.statusCode == 401) {
    await clearSession();
    throw SessionExpiredException();
  }

  throw ApiException(
    _parseError(data, 'Request failed (${res.statusCode}).'),
    statusCode: res.statusCode,
  );
}

Future<http.Response> _send(
    String method, Uri uri, Map<String, String> headers, Object? body) {
  switch (method) {
    case 'GET':
      return http.get(uri, headers: headers);
    case 'POST':
      return http.post(uri, headers: headers, body: body);
    case 'PATCH':
      return http.patch(uri, headers: headers, body: body);
    case 'DELETE':
      return http.delete(uri, headers: headers, body: body);
    default:
      return http.get(uri, headers: headers);
  }
}

Future<Map<String, dynamic>> getJson(String endpoint) =>
    apiRequest('GET', endpoint);

Future<Map<String, dynamic>> postJson(String endpoint, Map<String, dynamic> payload,
        {bool queueWhenOffline = false}) =>
    apiRequest('POST', endpoint,
        payload: payload, queueWhenOffline: queueWhenOffline);

Future<Map<String, dynamic>> patchJson(
        String endpoint, Map<String, dynamic> payload,
        {bool queueWhenOffline = false}) =>
    apiRequest('PATCH', endpoint,
        payload: payload, queueWhenOffline: queueWhenOffline);

Future<Map<String, dynamic>> deleteJson(String endpoint,
        {bool queueWhenOffline = false}) =>
    apiRequest('DELETE', endpoint, queueWhenOffline: queueWhenOffline);

Future<({int synced, int remaining})> replayOfflineQueue() async {
  final queue = await readQueue();
  if (queue.isEmpty) return (synced: 0, remaining: 0);

  final failed = <QueueItem>[];
  var synced = 0;
  for (final item in queue) {
    try {
      await apiRequest(
        item['method'] as String,
        item['endpoint'] as String,
        payload: item['payload'],
        queueWhenOffline: false,
      );
      synced++;
    } catch (_) {
      failed.add(item);
    }
  }
  await writeQueue(failed);
  return (synced: synced, remaining: failed.length);
}
