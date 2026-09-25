import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';
import '../api/client.dart';

/// Local snapshot of {card_uid -> {name, phone, role}}, pulled from
/// /api/rfid/card-assignments/ (the same active-assignment list the Win7
/// desktop app already relies on for offline card matching). Lets the kiosk
/// text a parent directly via the terminal's own SIM when a scan can't
/// reach the backend at all - see _handleScan's offline branch in
/// kiosk_home_screen.dart.
const _kCacheKey = 'guardian_contacts_cache';

class GuardianContactsCache {
  /// True when the list was pulled and saved, false when it could not be (the
  /// previous copy is kept) - so a caller can retry sooner after a failure than
  /// after a success.
  static Future<bool> refresh() async {
    try {
      final result = await getJson('/api/rfid/card-assignments/');
      final data = (result['data'] as List?) ?? const [];
      final map = <String, Map<String, String>>{};
      for (final row in data) {
        if (row is! Map) continue;
        final uid = (row['card_uid'] ?? '').toString();
        if (uid.isEmpty) continue;
        map[uid] = {
          'name': (row['person_name'] ?? '').toString(),
          'phone': (row['guardian_phone'] ?? '').toString(),
          'role': (row['role'] ?? '').toString(),
        };
      }
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_kCacheKey, jsonEncode(map));
      return true;
    } catch (_) {
      // Offline, or the pull failed - keep whatever was cached last time.
      return false;
    }
  }

  static Future<Map<String, String>?> lookup(String cardUid) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_kCacheKey);
    if (raw == null) return null;
    try {
      final map = jsonDecode(raw) as Map<String, dynamic>;
      final entry = map[cardUid];
      if (entry == null) return null;
      return (entry as Map).map((k, v) => MapEntry(k.toString(), v.toString()));
    } catch (_) {
      return null;
    }
  }
}
