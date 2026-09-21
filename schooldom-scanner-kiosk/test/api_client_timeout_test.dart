// The kiosk gives a card tap only a few seconds to be identified by the
// backend (see _scanReadTimeout in kiosk_home_screen.dart); apiRequest's
// `timeout` is what enforces it. These tests run the real client against a
// throwaway local server, so the API base URL has to point at it:
//
//   flutter test test/api_client_timeout_test.dart \
//     --dart-define=API_BASE_URL=http://127.0.0.1:18787
import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:schooldom_scanner_kiosk/api/client.dart';
import 'package:schooldom_scanner_kiosk/api/config.dart';
import 'package:schooldom_scanner_kiosk/storage/offline_queue.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _port = 18787;
const _scan = {'card_uid': 'ABC123', 'idempotency_key': 'key-1'};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  // The test binding replaces HTTP with a stub that answers 400 to everything.
  HttpOverrides.global = null;

  final skipReason = apiBaseUrl == 'http://127.0.0.1:$_port'
      ? null
      : 'run with --dart-define=API_BASE_URL=http://127.0.0.1:$_port';

  late HttpServer server;
  // path -> handler; a handler that never responds simulates a stalled backend.
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

  test('a backend that never answers is cut off at the budget and the scan is queued', () async {
    routes['/scan'] = (_) {}; // accept the request, never respond
    final started = DateTime.now();

    final result = await postJson('/scan', _scan,
        queueWhenOffline: true, timeout: const Duration(seconds: 1));
    final took = DateTime.now().difference(started);

    expect(result['offline'], isTrue);
    expect(result['timed_out'], isTrue);
    expect(took, greaterThanOrEqualTo(const Duration(milliseconds: 900)));
    expect(took, lessThan(const Duration(milliseconds: 2500)));
    final queue = await readQueue();
    expect(queue, hasLength(1));
    expect(queue.single['payload']['idempotency_key'], 'key-1');
  }, skip: skipReason);

  test('a backend that answers within the budget is used as normal', () async {
    routes['/scan'] = (req) => answer(req, 201, {'success': true, 'action': 'clock_in'});

    final result = await postJson('/scan', _scan,
        queueWhenOffline: true, timeout: const Duration(seconds: 3));

    expect(result['action'], 'clock_in');
    expect(result['offline'], isNull);
    expect(await readQueue(), isEmpty);
  }, skip: skipReason);

  test('the budget covers a token refresh too, not just the first attempt', () async {
    routes['/scan'] = (req) => answer(req, 401, {'detail': 'expired'});
    routes['/api/auth/refresh/'] = (_) {}; // refresh stalls as well

    final started = DateTime.now();
    final result = await postJson('/scan', _scan,
        queueWhenOffline: true, timeout: const Duration(seconds: 1));

    expect(result['timed_out'], isTrue);
    expect(DateTime.now().difference(started), lessThan(const Duration(milliseconds: 2500)));
    expect(await readQueue(), hasLength(1));
  }, skip: skipReason);

  test('without queueWhenOffline a timeout is reported as an error and nothing is queued', () async {
    routes['/scan'] = (_) {};

    await expectLater(
      postJson('/scan', _scan, timeout: const Duration(seconds: 1)),
      throwsA(isA<ApiException>()),
    );
    expect(await readQueue(), isEmpty);
  }, skip: skipReason);

  test('a real server error inside the budget is still an error, not a timeout', () async {
    routes['/scan'] = (req) => answer(req, 404, {'message': 'Card ABC123 is not linked to anyone.'});

    await expectLater(
      postJson('/scan', _scan, queueWhenOffline: true, timeout: const Duration(seconds: 3)),
      throwsA(isA<ApiException>().having((e) => e.statusCode, 'statusCode', 404)),
    );
    expect(await readQueue(), isEmpty);
  }, skip: skipReason);
}
