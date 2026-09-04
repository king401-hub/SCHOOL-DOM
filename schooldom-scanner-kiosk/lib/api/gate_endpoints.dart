import 'client.dart';

/// SchoolGate settings (mode, attendance windows, duplicate-protection
/// interval, PIN state) - see backend/rfid_attendance/views.py
/// gate_settings_get/gate_settings_update.
Future<Map<String, dynamic>> loadGateSettings() => getJson('/api/rfid/gate-settings/');

Future<Map<String, dynamic>> updateGateSettings(Map<String, dynamic> fields) =>
    postJson('/api/rfid/gate-settings/update/', fields);

/// Empty pin ('') is valid here - gate_pin_verify treats "no PIN configured
/// yet" as always-valid, so a fresh terminal's Settings screen never
/// locks an admin out before they've set one up.
Future<bool> verifyGatePin(String pin) async {
  final data = await postJson('/api/rfid/gate-settings/verify-pin/', {'pin': pin});
  return data['valid'] == true;
}

Future<Map<String, dynamic>> setGatePin({required String currentPin, required String newPin}) =>
    postJson('/api/rfid/gate-settings/set-pin/', {'current_pin': currentPin, 'new_pin': newPin});

/// The spec's on-demand "Send Fee Reminder" button - distinct from the
/// automatic per-scan attendance SMS, which the backend sends on its own
/// without the app asking.
Future<Map<String, dynamic>> sendFeeReminder(String studentId) =>
    postJson('/api/rfid/fee-reminder/send/', {'student_id': studentId});
