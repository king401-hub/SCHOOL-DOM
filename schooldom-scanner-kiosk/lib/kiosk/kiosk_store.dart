import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Device identity/metadata for the kiosk terminal - kept separate from
/// session_store.dart (which only holds `access`/`refresh` in the generic
/// shape apiRequest expects). Provisioning writes to BOTH: the device's
/// synthetic-user JWT goes into the normal session store (so every
/// apiRequest()/postJson() call in this app just works, offline queue
/// included, as if a human staff member were logged in), while this store
/// holds terminal-only bookkeeping: whether this device has been
/// provisioned yet, and its own identity for the heartbeat endpoint (a
/// different credential - see device_fleet.views._device_from_token on the
/// backend).
class KioskStore {
  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  static const _kEnabled = 'kiosk_mode_enabled';
  static const _kDeviceId = 'kiosk_device_id';
  static const _kDeviceAuthToken = 'kiosk_device_auth_token';
  static const _kSchoolName = 'kiosk_school_name';
  static const _kSchoolId = 'kiosk_school_id';
  static const _kPairedSchoolId = 'kiosk_paired_school_id';
  static const _kPairedSchoolName = 'kiosk_paired_school_name';

  static Future<bool> isEnabled() async {
    return (await _storage.read(key: _kEnabled)) == 'true';
  }

  static Future<void> activate({
    required String deviceId,
    required String deviceAuthToken,
    required String schoolName,
  }) async {
    await _storage.write(key: _kEnabled, value: 'true');
    await _storage.write(key: _kDeviceId, value: deviceId);
    await _storage.write(key: _kDeviceAuthToken, value: deviceAuthToken);
    await _storage.write(key: _kSchoolName, value: schoolName);
  }

  static Future<String?> get deviceId => _storage.read(key: _kDeviceId);
  static Future<String?> get deviceAuthToken =>
      _storage.read(key: _kDeviceAuthToken);
  static Future<String?> get schoolName => _storage.read(key: _kSchoolName);
  static Future<String?> get schoolId => _storage.read(key: _kSchoolId);
  static Future<String?> get pairedSchoolId =>
      _storage.read(key: _kPairedSchoolId);
  static Future<String?> get pairedSchoolName =>
      _storage.read(key: _kPairedSchoolName);

  /// Persists the active school's identity - called from the heartbeat
  /// response and after a successful switch, so a restarted app shows the
  /// real current school immediately rather than a stale/placeholder name
  /// until the next heartbeat lands.
  static Future<void> setActiveSchool({
    required String id,
    required String name,
  }) async {
    await _storage.write(key: _kSchoolId, value: id);
    await _storage.write(key: _kSchoolName, value: name);
  }

  /// `null` for both clears the pairing (e.g. no paired school reported).
  static Future<void> setPairedSchool({String? id, String? name}) async {
    if (id == null || name == null) {
      await _storage.delete(key: _kPairedSchoolId);
      await _storage.delete(key: _kPairedSchoolName);
      return;
    }
    await _storage.write(key: _kPairedSchoolId, value: id);
    await _storage.write(key: _kPairedSchoolName, value: name);
  }

  /// Called either after a superadmin remote-revokes (detected via
  /// heartbeat/scan responses reporting authorized:false), or from the
  /// confirmation-gated "Re-enter license key?" action on KioskHomeScreen's
  /// status bar (recovering from a wrong code or a terminal stuck waiting
  /// for school assignment) - not a bare, one-tap "sign out".
  static Future<void> deactivate() async {
    await _storage.delete(key: _kEnabled);
    await _storage.delete(key: _kDeviceId);
    await _storage.delete(key: _kDeviceAuthToken);
    await _storage.delete(key: _kSchoolName);
    await _storage.delete(key: _kSchoolId);
    await _storage.delete(key: _kPairedSchoolId);
    await _storage.delete(key: _kPairedSchoolName);
  }
}
