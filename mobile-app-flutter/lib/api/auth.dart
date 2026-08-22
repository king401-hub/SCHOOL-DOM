import 'dart:convert';
import 'package:http/http.dart' as http;
import 'client.dart';
import 'config.dart';
import '../storage/session_store.dart';

Future<Map<String, dynamic>> login(Map<String, String> credentials) async {
  final deviceTrustToken = await getDeviceTrustToken();
  final res = await http.post(
    Uri.parse('$apiBaseUrl/api/auth/login/'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      ...credentials,
      'device_trust_token': ?deviceTrustToken,
    }),
  );
  final data = jsonDecode(res.body) as Map<String, dynamic>;
  if (res.statusCode == 200) {
    await _saveDeviceTrustTokenIfPresent(data);
    return data;
  }
  throw ApiException(
    _pickError(data) ?? 'Sign in failed (${res.statusCode}).',
    statusCode: res.statusCode,
  );
}

/// `otpChallenge` is the raw login() response that carried requires_otp -
/// the caller's email and challenge live inside it (user.email /
/// otp_challenge), not as separate values it already has, since the admin
/// never types either of those in themselves.
Future<Map<String, dynamic>> verifyOtp(
  Map<String, dynamic> otpChallenge, {
  required String code,
}) async {
  final res = await http.post(
    Uri.parse('$apiBaseUrl/api/auth/admin/verify-otp/'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'email': otpChallenge['user']?['email'],
      'code': code,
      'challenge': otpChallenge['otp_challenge'],
    }),
  );
  final data = jsonDecode(res.body) as Map<String, dynamic>;
  if (res.statusCode == 200) {
    await _saveDeviceTrustTokenIfPresent(data);
    return data;
  }
  throw ApiException(
    _pickError(data) ?? 'OTP verification failed (${res.statusCode}).',
    statusCode: res.statusCode,
  );
}

Future<void> _saveDeviceTrustTokenIfPresent(Map<String, dynamic> data) async {
  final token = data['device_trust_token'];
  if (token is String && token.isNotEmpty) {
    await saveDeviceTrustToken(token);
  }
}

Future<Map<String, dynamic>> requestPasswordReset(String email) async {
  final res = await http.post(
    Uri.parse('$apiBaseUrl/api/auth/password-reset/'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({'email': email}),
  );
  final data = jsonDecode(res.body) as Map<String, dynamic>;
  if (res.statusCode == 200) return data;
  throw ApiException(
    _pickError(data) ?? 'Could not request a reset code (${res.statusCode}).',
    statusCode: res.statusCode,
  );
}

Future<Map<String, dynamic>> confirmPasswordReset({
  required String email,
  required String code,
  required String challenge,
  required String password,
  required String confirmPassword,
}) async {
  final res = await http.post(
    Uri.parse('$apiBaseUrl/api/auth/password-reset/confirm/'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({
      'email': email,
      'code': code,
      'challenge': challenge,
      'password': password,
      'confirm_password': confirmPassword,
    }),
  );
  final data = jsonDecode(res.body) as Map<String, dynamic>;
  if (res.statusCode == 200) return data;
  throw ApiException(
    _pickError(data) ?? 'Could not reset your password (${res.statusCode}).',
    statusCode: res.statusCode,
  );
}

String? _pick(Map<String, dynamic> m, List<String> keys) {
  for (final k in keys) {
    if (m[k] != null) return m[k].toString();
  }
  return null;
}

/// Backend error responses come in two shapes depending on which check
/// failed: a flat {message|detail|error} string (most hand-written checks,
/// e.g. suspended school, OTP failure), or DRF's serializer validation shape
/// {"errors": {"field": ["msg", ...], ...}} (e.g. LoginSerializer's "Invalid
/// credentials." on bad email/password/school_code). Without unpacking the
/// second shape, every validation failure silently fell back to a generic
/// "Sign in failed (400)." with no indication of what was actually wrong.
String? _pickError(Map<String, dynamic> m) {
  final flat = _pick(m, ['message', 'detail', 'error']);
  if (flat != null) return flat;

  final errors = m['errors'];
  if (errors is Map) {
    for (final value in errors.values) {
      if (value is List && value.isNotEmpty) return value.first.toString();
      if (value != null && value.toString().isNotEmpty) return value.toString();
    }
  } else if (errors is List && errors.isNotEmpty) {
    return errors.first.toString();
  }
  return null;
}
