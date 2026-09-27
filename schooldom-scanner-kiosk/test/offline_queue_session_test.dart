// A queued scan whose sync attempt fails because the terminal's own session
// has died (SIMPLE_JWT's 7-day refresh token, never renewed while the
// terminal sat idle) must never look like an ordinary offline spell:
// replayOfflineQueue() has to say so distinctly, and must not lose or reorder
// what is still queued while it does.
//
//   flutter test test/offline_queue_session_test.dart \
//     --dart-define=API_BASE_URL=http://127.0.0.1:18788
import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:schooldom_scanner_kiosk/api/client.dart';
import 'package:schooldom_scanner_kiosk/api/config.dart';
import 'package:schooldom_scanner_kiosk/storage/offline_queue.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _port = 18788;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  HttpOverrides.global = null;

  final skipReason = apiBaseUrl == 'http://127.0.0.1:$_port'
      ? null
      : 'run with --dart-define=API_BASE_URL=http://127.0.0.1:$_port';

  late HttpServer server;
  late Map<String, void Function(HttpRequest)> routes;

  setUp(() async {
    if (skipReason != null) return;
    SharedPreferences.setMockInitialValues({});
    FlutterSecureStorage.setMockInitialValues({
      'schooldom_scanner_session': jsonEncode({'access': 'a', 'refresh': 'r'}),
    });
    routes = {};
    server = await HttpServer.bind(InternetAddress.loopbackIPv4, _port);
    server.listen((req) {
      final handler = routes[req.uri.path];
      if (handler == null) {
        req.response
          ..statusCode = 404
          ..close();
      } else {
        handler(req);
      }
    });
  });

  tearDown(() async {
    if (skipReason != null) return;
    await server.close(force: true);
  });

  void answer(HttpRequest req, int status, Object body) {
    req.response
      ..statusCode = status
      ..headers.contentType = ContentType.json
      ..write(jsonEncode(body))
      ..close();
  }

  Future<void> queueTwoScans() async {
    await enqueue({'method': 'POST', 'endpoint': '/scan', 'payload': {'card_uid': 'A', 'idempotency_key': 'key-a'}});
    await enqueue({'method': 'POST', 'endpoint': '/scan', 'payload': {'card_uid': 'B', 'idempotency_key': 'key-b'}});
  }

  test('a dead refresh token is reported as sessionExpired, and nothing queued is lost', () async {
    await queueTwoScans();
    // Every attempt gets an expired access token; the refresh itself is also refused.
    routes['/scan'] = (req) => answer(req, 401, {'detail': 'expired'});
    routes['/api/auth/refresh/'] = (req) => answer(req, 401, {'detail': 'refresh expired'});

    final result = await replayOfflineQueue();

    expect(result.sessionExpired, isTrue);
    expect(result.synced, 0);
    expect(result.remaining, 2);
    final queue = await readQueue();
    expect(queue, hasLength(2));
    expect(queue[0]['payload']['idempotency_key'], 'key-a');
    expect(queue[1]['payload']['idempotency_key'], 'key-b');
  }, skip: skipReason);

  test('an ordinary network failure is not reported as sessionExpired', () async {
    await queueTwoScans();
    routes['/scan'] = (req) => answer(req, 201, {'success': true, 'action': 'clock_in'});

    final result = await replayOfflineQueue();

    expect(result.sessionExpired, isFalse);
    expect(result.synced, 2);
    expect(result.remaining, 0);
    expect(await readQueue(), isEmpty);
  }, skip: skipReason);

  test('the item ahead of the dead session still syncs before the stop', () async {
    await queueTwoScans();
    var calls = 0;
    routes['/scan'] = (req) {
      calls++;
      if (calls == 1) {
        answer(req, 201, {'success': true, 'action': 'clock_in'});
      } else {
        answer(req, 401, {'detail': 'expired'});
      }
    };
    routes['/api/auth/refresh/'] = (req) => answer(req, 401, {'detail': 'refresh expired'});

    final result = await replayOfflineQueue();

    expect(result.synced, 1);
    expect(result.sessionExpired, isTrue);
    expect(result.remaining, 1);
    final queue = await readQueue();
    expect(queue, hasLength(1));
    expect(queue.single['payload']['idempotency_key'], 'key-b');
  }, skip: skipReason);
}
