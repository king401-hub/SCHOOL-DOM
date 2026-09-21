// AppUpdater streams the new APK to disk with progress. These run the real
// http client against a throwaway local server, so a stalled, truncated or
// cancelled download behaves as it would on the terminal.
import 'dart:async';
import 'dart:io';
import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:schooldom_scanner_kiosk/services/app_updater.dart';

void main() {
  late HttpServer server;
  late Directory tmp;
  late http.Client client;
  late void Function(HttpRequest) handler;

  setUp(() async {
    tmp = Directory.systemTemp.createTempSync('updater_test');
    server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    server.listen((req) => handler(req));
    client = http.Client();
  });

  tearDown(() async {
    client.close();
    await server.close(force: true);
    tmp.deleteSync(recursive: true);
  });

  Uri url() => Uri.parse('http://127.0.0.1:${server.port}/app.apk');
  File dest() => File('${tmp.path}${Platform.pathSeparator}app.apk');

  Future<void> sendInChunks(HttpResponse res, List<int> body, {int chunk = 100 * 1024}) async {
    for (var i = 0; i < body.length; i += chunk) {
      res.add(body.sublist(i, min(i + chunk, body.length)));
      await res.flush();
      await Future<void>.delayed(const Duration(milliseconds: 40));
    }
  }

  test('saves the file and reports growing progress against the announced total', () async {
    final body = List<int>.generate(300 * 1024, (i) => i % 251);
    handler = (req) async {
      req.response.contentLength = body.length;
      await sendInChunks(req.response, body);
      await req.response.close();
    };

    final seen = <int>[];
    int? total;
    await AppUpdater.download(
      client: client,
      url: url(),
      destination: dest(),
      onProgress: (received, t) {
        seen.add(received);
        total = t;
      },
    );

    expect(await dest().readAsBytes(), body);
    expect(total, body.length);
    expect(seen.first, 0);
    expect(seen.last, body.length);
    expect(seen, orderedEquals([...seen]..sort()), reason: 'progress never goes backwards');
    expect(seen.length, greaterThan(2), reason: 'progress is reported along the way, not just at the end');
  });

  test('a download with no announced size still saves, with an unknown total', () async {
    final body = List<int>.filled(50 * 1024, 7);
    handler = (req) async {
      await sendInChunks(req.response, body, chunk: 20 * 1024); // chunked: no Content-Length
      await req.response.close();
    };

    int? total = -1;
    await AppUpdater.download(
      client: client,
      url: url(),
      destination: dest(),
      onProgress: (_, t) => total = t,
    );

    expect(total, isNull);
    expect(await dest().readAsBytes(), body);
  });

  test('a bad status is an error and leaves no file behind', () async {
    handler = (req) async {
      req.response.statusCode = 404;
      await req.response.close();
    };

    await expectLater(
      AppUpdater.download(client: client, url: url(), destination: dest(), onProgress: (_, _) {}),
      throwsA(isA<HttpException>().having((e) => e.message, 'message', contains('404'))),
    );
    expect(dest().existsSync(), isFalse);
  });

  test('a body shorter than announced is an error and the partial file is deleted', () async {
    handler = (req) async {
      req.response.contentLength = 1000;
      req.response.add(List<int>.filled(400, 1));
      await req.response.flush();
      try {
        await req.response.close(); // fewer bytes than promised: the server drops the connection
      } catch (_) {}
    };

    await expectLater(
      AppUpdater.download(client: client, url: url(), destination: dest(), onProgress: (_, _) {}),
      throwsA(anything),
    );
    expect(dest().existsSync(), isFalse, reason: 'a truncated APK must never reach the installer');
  });

  test('a download that stalls gives up after the idle timeout and cleans up', () async {
    handler = (req) async {
      req.response.contentLength = 1000;
      req.response.add(List<int>.filled(100, 1));
      await req.response.flush(); // ...and then never sends another byte
    };

    await expectLater(
      AppUpdater.download(
        client: client,
        url: url(),
        destination: dest(),
        onProgress: (_, _) {},
        idleTimeout: const Duration(milliseconds: 400),
      ),
      throwsA(isA<TimeoutException>()),
    );
    expect(dest().existsSync(), isFalse);
  });

  test('closing the client cancels a download in flight', () async {
    final started = Completer<void>();
    handler = (req) async {
      req.response.contentLength = 10 * 1024 * 1024;
      req.response.add(List<int>.filled(64 * 1024, 1));
      await req.response.flush(); // then wait for the client to give up
    };

    final result = AppUpdater.download(
      client: client,
      url: url(),
      destination: dest(),
      onProgress: (received, _) {
        if (received > 0 && !started.isCompleted) started.complete();
      },
    );
    await started.future.timeout(const Duration(seconds: 5));
    client.close(); // what the Cancel button does

    await expectLater(result, throwsA(anything));
    expect(dest().existsSync(), isFalse);
  });

  group('describeUpdateError', () {
    test('a network failure reads as a connection problem, not a stack trace', () {
      const wording = 'Could not reach the server. Check the connection and try again.';
      expect(describeUpdateError(const SocketException('Failed host lookup')), wording);
      expect(describeUpdateError(TimeoutException('idle')), wording);
      expect(describeUpdateError(http.ClientException('Connection closed')), wording);
    });

    test('an HTTP error keeps its own message, and anything else loses the Exception prefix', () {
      expect(describeUpdateError(const HttpException('Download failed (HTTP 404).')), 'Download failed (HTTP 404).');
      expect(describeUpdateError(Exception('Could not open the installer')), 'Could not open the installer');
    });
  });
}
