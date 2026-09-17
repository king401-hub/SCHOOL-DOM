import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

/// Local mirror of GateSettings' configured early/late/clock-out time
/// windows (rfid_attendance.models.GateSettings.classify_event), so the
/// kiosk can label an attendance event by time-of-day even with no network
/// to ask the server - see kiosk_home_screen.dart's offline scan branch.
/// Direction (clock-in vs clock-out) still can't be determined offline -
/// that depends on whether the student already clocked in today, which
/// requires server-side attendance history this client doesn't keep - so
/// this only classifies the time window itself, same as the server does
/// before it separately decides direction.
class GateSettingsCache {
  static const _kKey = 'gate_settings_cache';

  /// Call with whatever loadGateSettings() already returned at some other
  /// call site - deliberately not fetching its own copy here, since the
  /// kiosk already polls /api/rfid/gate-settings/ regularly for its own
  /// purposes (see kiosk_home_screen.dart's _loadGateSettings).
  static Future<void> save(Map<String, dynamic> data) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kKey, jsonEncode(data));
  }

  /// Mirrors GateSettings.classify_event: 'early' | 'late' | 'clockout' | 'other'.
  static Future<String> classifyEvent(DateTime now) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_kKey);
    if (raw == null) return 'other';
    try {
      final data = jsonDecode(raw) as Map<String, dynamic>;
      final minutes = now.hour * 60 + now.minute;

      bool between(String startKey, String endKey) {
        final start = _parseMinutes(data[startKey] as String?);
        final end = _parseMinutes(data[endKey] as String?);
        if (start == null || end == null) return false;
        return minutes >= start && minutes <= end;
      }

      if (between('early_start', 'early_end')) return 'early';
      if (between('late_start', 'late_end')) return 'late';
      if (between('clockout_start', 'clockout_end')) return 'clockout';
      return 'other';
    } catch (_) {
      return 'other';
    }
  }

  static int? _parseMinutes(String? hhmmss) {
    if (hhmmss == null) return null;
    final parts = hhmmss.split(':');
    if (parts.length < 2) return null;
    final h = int.tryParse(parts[0]);
    final m = int.tryParse(parts[1]);
    if (h == null || m == null) return null;
    return h * 60 + m;
  }
}
