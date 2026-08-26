// Override at build time (e.g. to point a debug build at a local backend):
//   flutter build apk --dart-define=API_BASE_URL=https://yourserver.com
const String _envUrl =
    String.fromEnvironment('API_BASE_URL', defaultValue: '');

// This app only ever runs on real dedicated terminal hardware, never an
// Android emulator - unlike the main SchoolDom app, there is no debug/
// emulator default to fall back to (10.0.2.2 is unreachable from a real
// device and just produces a confusing "can't reach the server" on-screen).
// Always the production server unless a build explicitly overrides it.
String get apiBaseUrl {
  if (_envUrl.isNotEmpty) return _envUrl.replaceAll(RegExp(r'/+$'), '');
  return 'https://schooldom.academy';
}
