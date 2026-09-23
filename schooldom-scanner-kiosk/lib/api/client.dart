import 'dart:async';
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
  // One overall budget for the whole call (first attempt, any token refresh
  // and the retry). Running out of it is treated like having no network:
  // with queueWhenOffline the request is queued and `timed_out` is returned.
  Duration? timeout,
}) async {
  var session = await getSession();
  if (session?['access'] == null) {
    await clearSession();
    throw SessionExpiredException();
  }

  final uri = Uri.parse('$apiBaseUrl$endpoint');

  Map<String, String> headers = {
    'Authorization': 'Bearer ${session!['access']}',
  };
  Object? body;
  if (payload != null) {
    headers['Content-Type'] = 'application/json';
    body = jsonEncode(payload);
  }

  final deadline = timeout == null ? null : DateTime.now().add(timeout);
  Future<T> withinBudget<T>(Future<T> call) {
    if (deadline == null) return call;
    final left = deadline.difference(DateTime.now());
    return call.timeout(left.isNegative ? Duration.zero : left);
  }

  Future<Map<String, dynamic>> saveForLater({required bool timedOut}) async {
    await enqueue({'method': method, 'endpoint': endpoint, 'payload': payload});
    return {
      'success': true,
      'offline': true,
      if (timedOut) 'timed_out': true,
      'message': 'Saved offline.',
    };
  }

  http.Response res;
  try {
    res = await withinBudget(_send(method, uri, headers, body));
  } on SocketException catch (_) {
    if (queueWhenOffline && method != 'GET') return saveForLater(timedOut: false);
    throw ApiException('Network error. Check your connection.');
  } on TimeoutException catch (_) {
    if (queueWhenOffline && method != 'GET') return saveForLater(timedOut: true);
    throw ApiException('The server took too long to respond.');
  }

  if (res.statusCode == 401 && retry) {
    try {
      session = await withinBudget<Map<String, dynamic>?>(_tryRefresh(session));
      headers['Authorization'] = 'Bearer ${session!['access']}';
      res = await withinBudget(_send(method, uri, headers, body));
    } on SocketException catch (_) {
      if (queueWhenOffline && method != 'GET') return saveForLater(timedOut: false);
      throw ApiException('Network error. Check your connection.');
    } on TimeoutException catch (_) {
      if (queueWhenOffline && method != 'GET') return saveForLater(timedOut: true);
      throw ApiException('The server took too long to respond.');
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
    default:
      return http.get(uri, headers: headers);
  }
}

Future<Map<String, dynamic>> postJson(String endpoint, Map<String, dynamic> payload,
        {bool queueWhenOffline = false, Duration? timeout}) =>
    apiRequest('POST', endpoint,
        payload: payload, queueWhenOffline: queueWhenOffline, timeout: timeout);

Future<Map<String, dynamic>> getJson(String endpoint) => apiRequest('GET', endpoint);

// Bounds each queued item's sync attempt - same reasoning as _scanReadTimeout
// in kiosk_home_screen.dart, just more generous since this runs in the
// background rather than holding up "Reading card...". Without this, a
// flaky-but-not-fully-down connection (weak Wi-Fi at the gate, not a clean
// disconnect) left every apiRequest call here unbounded, and since this
// function used to be awaited from _handleScan's offline branch, that hang
// held _busy true - so the terminal ended up back on "Reading card..." after
// the brief result flash ended, for good, on the very connection quality this
// offline queue exists to handle.
const _replayItemTimeout = Duration(seconds: 10);

// True while a pass through the queue is in flight. Guards against a slow
// pass (still possible even with the per-item timeout above, e.g. many
// queued items each taking the full 10s) still being underway when the next
// caller - the 2-minute heartbeat timer, or another scan - asks to replay
// again; without this a slow connection accumulates more and more concurrent
// replay passes over the same queue instead of just one at a time.
bool _replayInProgress = false;

Future<({int synced, int remaining})> replayOfflineQueue() async {
  if (_replayInProgress) {
    return (synced: 0, remaining: (await readQueue()).length);
  }
  _replayInProgress = true;
  try {
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
          timeout: _replayItemTimeout,
        );
        synced++;
      } catch (_) {
        failed.add(item);
      }
    }
    await writeQueue(failed);
    return (synced: synced, remaining: failed.length);
  } finally {
    _replayInProgress = false;
  }
}
