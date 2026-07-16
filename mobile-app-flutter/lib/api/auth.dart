import 'dart:convert';
import 'package:http/http.dart' as http;
import 'client.dart';
import 'config.dart';

Future<Map<String, dynamic>> login(Map<String, String> credentials) async {
  final res = await http.post(
    Uri.parse('$apiBaseUrl/api/auth/login/'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode(credentials),
  );
  final data = jsonDecode(res.body) as Map<String, dynamic>;
  if (res.statusCode == 200) return data;
  throw ApiException(
    _pick(data, ['message', 'detail', 'error']) ??
        'Sign in failed (${res.statusCode}).',
    statusCode: res.statusCode,
  );
}

Future<Map<String, dynamic>> verifyOtp(Map<String, String> payload) async {
  final res = await http.post(
    Uri.parse('$apiBaseUrl/api/auth/otp/verify/'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode(payload),
  );
  final data = jsonDecode(res.body) as Map<String, dynamic>;
  if (res.statusCode == 200) return data;
  throw ApiException(
    _pick(data, ['message', 'detail', 'error']) ??
        'OTP verification failed (${res.statusCode}).',
    statusCode: res.statusCode,
  );
}

String? _pick(Map<String, dynamic> m, List<String> keys) {
  for (final k in keys) {
    if (m[k] != null) return m[k].toString();
  }
  return null;
}
