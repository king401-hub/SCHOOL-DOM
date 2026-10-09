import 'package:flutter/foundation.dart';

// Override at build time:
//   flutter build windows --dart-define=API_BASE_URL=https://yourserver.com
const String _envUrl =
    String.fromEnvironment('API_BASE_URL', defaultValue: '');

String get apiBaseUrl {
  if (_envUrl.isNotEmpty) return _envUrl.replaceAll(RegExp(r'/+$'), '');
  // Default: production server, or localhost when running debug on-device.
  // Windows/desktop debug runs reach the backend over plain localhost (no
  // emulator loopback translation needed, unlike the Android emulator).
  return kDebugMode
      ? 'http://localhost:8000'
      : 'https://schooldom.academy';
}
