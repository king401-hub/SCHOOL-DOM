import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
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

Future<Map<String, dynamic>?> _tryRefresh(Map<String, dynamic> session) async {
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
  };
  await saveSession(next);
  return next;
}

Future<http.Response> _send(
    String method, Uri uri, Map<String, String> headers, Object? body) {
  switch (method) {
    case 'GET':
      return http.get(uri, headers: headers);
    case 'POST':
      return http.post(uri, headers: headers, body: body);
    default:
      return http.get(uri, headers: headers);
  }
}

Future<Map<String, dynamic>> apiRequest(
  String method,
  String endpoint, {
  dynamic payload,
  bool retry = true,
}) async {
  var session = await getSession();
  if (session?['access'] == null) {
    await clearSession();
    throw SessionExpiredException();
  }

  final uri = Uri.parse('$apiBaseUrl$endpoint');
  final headers = {
    'Authorization': 'Bearer ${session!['access']}',
    if (payload != null) 'Content-Type': 'application/json',
  };
  final body = payload != null ? jsonEncode(payload) : null;

  http.Response res;
  try {
    res = await _send(method, uri, headers, body);
  } on SocketException catch (_) {
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

Future<Map<String, dynamic>> getJson(String endpoint) => apiRequest('GET', endpoint);

Future<Map<String, dynamic>> postJson(String endpoint, Map<String, dynamic> payload) =>
    apiRequest('POST', endpoint, payload: payload);
