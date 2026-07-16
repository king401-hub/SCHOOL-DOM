import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

String _key(String bucket, String? scope) =>
    'cache_${scope ?? "global"}_$bucket';

Future<Map<String, dynamic>?> readCache(String bucket, String? scope) async {
  final prefs = await SharedPreferences.getInstance();
  final raw = prefs.getString(_key(bucket, scope));
  if (raw == null) return null;
  try {
    return jsonDecode(raw) as Map<String, dynamic>;
  } catch (_) {
    return null;
  }
}

Future<void> writeCache(
    String bucket, dynamic data, String? scope) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setString(
    _key(bucket, scope),
    jsonEncode({'data': data, 'cachedAt': DateTime.now().toIso8601String()}),
  );
}
