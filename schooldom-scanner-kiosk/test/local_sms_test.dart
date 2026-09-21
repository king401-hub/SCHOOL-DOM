// LocalSms.send must say true only when the native side confirms the text was
// sent: the kiosk uses "true" to stop the server texting the parent again when
// the scan syncs, so every failure mode has to come back false.
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:schooldom_scanner_kiosk/services/local_sms.dart';

const _channel = MethodChannel('schooldom/local_sms');

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  void nativeAnswers(Future<Object?> Function(MethodCall call) handler) {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(_channel, handler);
  }

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(_channel, null);
  });

  test('true when the native side reports the SMS sent, passing phone and text through', () async {
    MethodCall? seen;
    nativeAnswers((call) async {
      seen = call;
      return true;
    });

    expect(await LocalSms.send('08012345678', 'Ada arrived at 7:42 AM. -SchoolDom'), isTrue);
    expect(seen?.method, 'sendSms');
    expect(seen?.arguments, {'phone': '08012345678', 'message': 'Ada arrived at 7:42 AM. -SchoolDom'});
  });

  test('false when the native side reports the SMS failed (no airtime, no signal...)', () async {
    nativeAnswers((call) async => false);

    expect(await LocalSms.send('08012345678', 'hi'), isFalse);
  });

  test('false when the native side throws', () async {
    nativeAnswers((call) async => throw PlatformException(code: 'boom'));

    expect(await LocalSms.send('08012345678', 'hi'), isFalse);
  });

  test('false when the native side has no such method', () async {
    // No handler registered -> MissingPluginException.
    expect(await LocalSms.send('08012345678', 'hi'), isFalse);
  });

  test('false when the native side never answers', () async {
    nativeAnswers((call) => Future<Object?>.delayed(const Duration(seconds: 30)));

    final started = DateTime.now();
    final sent = await LocalSms.send('08012345678', 'hi', timeout: const Duration(milliseconds: 300));

    expect(sent, isFalse);
    expect(DateTime.now().difference(started), lessThan(const Duration(seconds: 3)));
  });
}
