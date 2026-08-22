import 'dart:convert';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const _kSession = 'schooldom_session';
const _kBiometric = 'schooldom_biometric';
// Deliberately a separate key from _kSession: this must survive sign-out
// (clearSession only removes _kSession) so an admin's device stays
// "remembered" - and OTP-exempt - across future sign-ins, not just within
// one session.
const _kDeviceTrust = 'schooldom_device_trust';

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

Future<String?> getDeviceTrustToken() => _storage.read(key: _kDeviceTrust);

Future<void> saveDeviceTrustToken(String token) async {
  await _storage.write(key: _kDeviceTrust, value: token);
}
