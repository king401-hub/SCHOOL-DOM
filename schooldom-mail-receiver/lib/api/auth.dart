import 'dart:convert';
import 'package:http/http.dart' as http;
import 'client.dart';
import 'config.dart';

Future<Map<String, dynamic>> login(String email, String password) async {
  final res = await http.post(
    Uri.parse('$apiBaseUrl/api/auth/login/'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({'email': email, 'password': password}),
  );
  final data = jsonDecode(res.body) as Map<String, dynamic>;
  if (res.statusCode == 200) return data;
  throw ApiException(
    _pickError(data) ?? 'Sign in failed (${res.statusCode}).',
    statusCode: res.statusCode,
  );
}

/// `otpChallenge` is the raw login() response that carried requires_otp - the
/// admin's email and challenge live inside it already.
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
  if (res.statusCode == 200) return data;
  throw ApiException(
    _pickError(data) ?? 'OTP verification failed (${res.statusCode}).',
    statusCode: res.statusCode,
  );
}

String? _pick(Map<String, dynamic> m, List<String> keys) {
  for (final k in keys) {
    if (m[k] != null) return m[k].toString();
  }
  return null;
}

/// Backend error responses come in two shapes: a flat {message|detail|error}
/// string, or DRF's serializer validation shape {"errors": {...}}.
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
