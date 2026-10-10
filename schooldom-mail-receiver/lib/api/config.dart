import 'dart:io';
import 'package:flutter/foundation.dart';

// Override at build time:
//   flutter run --dart-define=API_BASE_URL=https://yourserver.com
const String _envUrl =
    String.fromEnvironment('API_BASE_URL', defaultValue: '');

String get apiBaseUrl {
  if (_envUrl.isNotEmpty) return _envUrl.replaceAll(RegExp(r'/+$'), '');
  if (!kDebugMode) return 'https://schooldom.academy';
  // Debug default only - every platform here reaches a locally-run backend
  // differently: the Android emulator's "localhost" is the emulator itself,
  // not the host machine, so it needs the special 10.0.2.2 loopback alias;
  // desktop/web debug runs share the host's real localhost.
  return Platform.isAndroid ? 'http://10.0.2.2:8000' : 'http://localhost:8000';
}
