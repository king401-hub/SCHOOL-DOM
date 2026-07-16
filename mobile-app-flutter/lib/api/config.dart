import 'package:flutter/foundation.dart';

// Override at build time:
//   flutter build apk --dart-define=API_BASE_URL=https://yourserver.com
const String _envUrl =
    String.fromEnvironment('API_BASE_URL', defaultValue: '');

String get apiBaseUrl {
  if (_envUrl.isNotEmpty) return _envUrl.replaceAll(RegExp(r'/+$'), '');
  // Default: production server, or localhost when running debug on-device
  return kDebugMode
      ? 'http://10.0.2.2:8000' // Android emulator loopback
      : 'https://schooldom.academy';
}
