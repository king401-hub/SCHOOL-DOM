import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const _kSession = 'schooldom_session';
const _kBiometric = 'schooldom_biometric';

const _storage = FlutterSecureStorage(
  aOptions: AndroidOptions(encryptedSharedPreferences: true),
);

Future<Map<String, dynamic>?> getSession() async {
  final raw = await _storage.read(key: _kSession);
  if (raw == null) return null;
  try {
    return jsonDecode(raw) as Map<String, dynamic>;
  } catch (_) {
    return null;
  }
}

Future<void> saveSession(Map<String, dynamic> session) async {
  await _storage.write(key: _kSession, value: jsonEncode(session));
}

Future<void> clearSession() async {
  await _storage.delete(key: _kSession);
}

Future<bool> isBiometricEnabled() async {
  return (await _storage.read(key: _kBiometric)) == 'true';
}

Future<void> setBiometricEnabled(bool enabled) async {
  await _storage.write(key: _kBiometric, value: enabled ? 'true' : 'false');
}
