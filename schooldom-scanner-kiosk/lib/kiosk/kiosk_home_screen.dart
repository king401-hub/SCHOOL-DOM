import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:battery_plus/battery_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:http/http.dart' as http;
import 'package:nfc_manager/nfc_manager.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:wakelock_plus/wakelock_plus.dart';
import '../api/client.dart';
import '../api/config.dart';
import '../storage/session_store.dart';
import '../theme/app_theme.dart';
import 'kiosk_store.dart';

enum _ScanOutcome { welcome, goodbye, invalid, duplicate, error }

/// Spec sections 3-8, 30 - the entire on-site experience: Ready to Scan,
/// tap a card, see who it is (never the raw card UID - section 2/10), hear a
/// voice line, auto-return. No menus, no logout (section 9/10).
class KioskHomeScreen extends StatefulWidget {
  const KioskHomeScreen({super.key});

  @override
  State<KioskHomeScreen> createState() => _KioskHomeScreenState();
}

class _KioskHomeScreenState extends State<KioskHomeScreen> {
  // A card held near the reader too long can be discovered repeatedly in a
  // single tap - same reasoning as the RFID Win7 desktop app's cooldown.
  static const _cooldownSeconds = 8;
  static const _resultDisplaySeconds = 4;

  final FlutterTts _tts = FlutterTts();
  final Battery _battery = Battery();

  bool _nfcAvailable = true;
  bool _busy = false;
  _ScanOutcome? _outcome;
  Map<String, dynamic>? _resultData;
  String? _resultMessage;
  String? _schoolName;
  bool _online = true;
  int _pendingCount = 0;

  final Map<String, DateTime> _recentScans = {};
  Timer? _resultTimer;
  Timer? _heartbeatTimer;

  @override
  void initState() {
    super.initState();
    WakelockPlus.enable();
    _tts.setSpeechRate(0.46);
    _loadSchoolName();
    _startNfcSession();
    _sendHeartbeat();
    _heartbeatTimer = Timer.periodic(const Duration(minutes: 2), (_) => _sendHeartbeat());
  }

  @override
  void dispose() {
    _resultTimer?.cancel();
    _heartbeatTimer?.cancel();
    NfcManager.instance.stopSession();
    WakelockPlus.disable();
    _tts.stop();
    super.dispose();
  }

  Future<void> _loadSchoolName() async {
    final name = await KioskStore.schoolName;
    if (mounted) setState(() => _schoolName = name);
  }

  // ---------------------------------------------------------------- NFC

  Future<void> _startNfcSession() async {
    final available = await NfcManager.instance.isAvailable();
    if (!mounted) return;
    setState(() => _nfcAvailable = available);
    if (!available) return;

    NfcManager.instance.startSession(
      onDiscovered: (NfcTag tag) async {
        final uid = _extractUid(tag);
        // Always restart listening right away - a card resting on the
        // reader shouldn't stall the whole terminal, and a genuinely new
        // tap needs a fresh session regardless of whether this one matched.
        _restartNfcSession();
        if (uid != null) await _handleScan(uid);
      },
    );
  }

  void _restartNfcSession() {
    NfcManager.instance.stopSession();
    Future.delayed(const Duration(milliseconds: 300), () {
      if (mounted) _startNfcSession();
    });
  }

  /// Card UID as a hex string, from whichever NFC technology this tag
  /// exposes - never invented, and never shown to the user (spec sections
  /// 2/10: only the desktop Superadmin/RFID apps ever see the raw UID).
  String? _extractUid(NfcTag tag) {
    final data = tag.data as Map;
    for (final techKey in ['nfca', 'nfcb', 'nfcf', 'nfcv', 'isodep', 'mifareclassic', 'mifareultralight']) {
      final tech = data[techKey];
      if (tech is Map && tech['identifier'] != null) {
        final bytes = (tech['identifier'] as List).cast<int>();
        return bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join().toUpperCase();
      }
    }
    return null;
  }

  // ---------------------------------------------------------------- Scan handling

  Future<void> _handleScan(String uid) async {
    if (_busy) return;

    final lastAt = _recentScans[uid];
    if (lastAt != null && DateTime.now().difference(lastAt).inSeconds < _cooldownSeconds) {
      return; // Same card tapped again almost immediately - ignore silently, no re-announcement.
    }
    _recentScans[uid] = DateTime.now();
    _recentScans.removeWhere((_, t) => DateTime.now().difference(t).inMinutes > 10);

    setState(() => _busy = true);

    try {
      final result = await postJson(
        '/api/rfid/attendance/scan/',
        {
          'card_uid': uid,
          'idempotency_key': _uuid(),
          'device_id': await KioskStore.deviceId,
        },
        queueWhenOffline: true,
      );

      if (result['offline'] == true) {
        await _showResult(_ScanOutcome.welcome, message: 'Saved - will sync when back online.');
        await _refreshPendingCount();
        return;
      }

      final action = result['action'] as String?;
      final person = result['person'] as Map<String, dynamic>?;
      await _showResult(
        action == 'clock_out' ? _ScanOutcome.goodbye : _ScanOutcome.welcome,
        data: person,
        message: result['message'] as String?,
      );
    } on ApiException catch (e) {
      if (e.statusCode == 404) {
        await _showResult(_ScanOutcome.invalid);
      } else if (e.statusCode == 400 && _looksLikeAlreadyHandled(e.message)) {
        // Covers both attendance_scan_create's "X already has clocked out
        // today" AND the 3-hour clock-in/out gate's "clocked in recently -
        // wait N minutes" - neither can succeed right now, but neither is a
        // real error either; both read to the person at the terminal as
        // "you're already accounted for."
        await _showResult(_ScanOutcome.duplicate, message: e.message);
      } else {
        await _showResult(_ScanOutcome.error, message: e.message);
      }
    } on SessionExpiredException {
      // The device's own session expired/was revoked server-side (a
      // superadmin hitting "Log Out Device" invalidates it immediately -
      // see device_fleet.views.revoke_device). Never silently keep scanning
      // as if nothing happened.
      await _showResult(_ScanOutcome.error, message: 'This terminal has been logged out remotely.');
    } catch (_) {
      await _showResult(_ScanOutcome.error, message: 'Unable to record attendance. Please try again.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  bool _looksLikeAlreadyHandled(String message) {
    final m = message.toLowerCase();
    return m.contains('already') || m.contains('wait') || m.contains('recently');
  }

  Future<void> _showResult(_ScanOutcome outcome, {Map<String, dynamic>? data, String? message}) async {
    if (!mounted) return;
    setState(() {
      _outcome = outcome;
      _resultData = data;
      _resultMessage = message;
    });

    final name = data?['name'] as String?;
    final line = switch (outcome) {
      _ScanOutcome.welcome => name != null ? 'Welcome, $name.' : 'Welcome.',
      _ScanOutcome.goodbye => name != null ? 'Goodbye, $name.' : 'Goodbye.',
      _ScanOutcome.invalid => 'This card is not registered.',
      _ScanOutcome.duplicate => 'Attendance has already been recorded.',
      _ScanOutcome.error => 'Unable to record attendance. Please try again.',
    };
    unawaited(_tts.speak(line));

    _resultTimer?.cancel();
    _resultTimer = Timer(const Duration(seconds: _resultDisplaySeconds), () {
      if (mounted) setState(() => _outcome = null);
    });
  }

  Future<void> _refreshPendingCount() async {
    // replayOfflineQueue() also opportunistically flushes - harmless to call
    // here since a fresh scan just landed in the same queue, and this is
    // the only place in kiosk mode that needs the count at all.
    final result = await replayOfflineQueue();
    if (mounted) setState(() => _pendingCount = result.remaining);
  }

  // ---------------------------------------------------------------- Heartbeat

  Future<void> _sendHeartbeat() async {
    try {
      final battery = await _battery.batteryLevel.catchError((_) => -1);
      final state = await _battery.batteryState.catchError((_) => BatteryState.unknown);
      final packageInfo = await PackageInfo.fromPlatform();
      final deviceAuthToken = await KioskStore.deviceAuthToken;
      if (deviceAuthToken == null) return;

      final response = await http.post(
        Uri.parse('$apiBaseUrl/api/device-fleet/device/heartbeat/'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'auth_token': deviceAuthToken,
          'app_version': packageInfo.version,
          if (battery >= 0) 'battery_percentage': battery,
          'battery_charging': state == BatteryState.charging || state == BatteryState.full,
          'synced': _pendingCount == 0,
        }),
      );
      if (!mounted) return;
      setState(() => _online = response.statusCode == 200);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        if (data['authorized'] == false) {
          await _handleRemoteRevocation();
          return;
        }
        final schoolName = data['school_name'] as String?;
        if (schoolName != null && schoolName != _schoolName) {
          setState(() => _schoolName = schoolName);
        }
      }
    } catch (_) {
      if (mounted) setState(() => _online = false);
    }
    _refreshPendingCount();
  }

  Future<void> _handleRemoteRevocation() async {
    await clearSession();
    await KioskStore.deactivate();
    if (!mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil('/', (route) => false);
  }

  String _uuid() {
    final rnd = Random.secure();
    final bytes = List<int>.generate(16, (_) => rnd.nextInt(256));
    bytes[6] = (bytes[6] & 0x0F) | 0x40;
    bytes[8] = (bytes[8] & 0x3F) | 0x80;
    final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
  }

  // ---------------------------------------------------------------- UI

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0B1220),
      body: SafeArea(
        child: Stack(
          children: [
            Center(child: _outcome == null ? _buildReadyState() : _buildResultState()),
            Positioned(top: 12, left: 0, right: 0, child: _buildStatusBar()),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(_schoolName ?? 'SchoolDom', style: const TextStyle(color: Colors.white54, fontSize: 12, fontWeight: FontWeight.w600)),
          Row(children: [
            if (_pendingCount > 0) ...[
              Icon(Icons.cloud_upload_outlined, size: 14, color: Colors.amber.shade300),
              const SizedBox(width: 4),
              Text('$_pendingCount pending', style: TextStyle(color: Colors.amber.shade300, fontSize: 11, fontWeight: FontWeight.w700)),
              const SizedBox(width: 12),
            ],
            Icon(_online ? Icons.wifi : Icons.wifi_off, size: 14, color: _online ? Colors.white38 : Colors.redAccent),
          ]),
        ],
      ),
    );
  }

  Widget _buildReadyState() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text('School', style: TextStyle(color: Colors.white, fontSize: 34, fontWeight: FontWeight.w900, height: 1)),
        const Text('Dom', style: TextStyle(color: AppColors.primary, fontSize: 34, fontWeight: FontWeight.w900, height: 1)),
        const SizedBox(height: 56),
        Container(
          width: 190,
          height: 190,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: AppColors.primary.withValues(alpha: 0.5), width: 2),
          ),
          child: Center(
            child: Container(
              width: 130,
              height: 130,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.primary.withValues(alpha: 0.12),
              ),
              child: Icon(
                _busy ? Icons.hourglass_top_rounded : Icons.contactless_rounded,
                size: 60,
                color: AppColors.primary,
              ),
            ),
          ),
        ),
        const SizedBox(height: 40),
        const Text('Ready to Scan', style: TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w800)),
        const SizedBox(height: 8),
        Text(
          _nfcAvailable ? 'Tap or scan your student card' : 'NFC is not available on this device',
          style: TextStyle(color: _nfcAvailable ? Colors.white54 : Colors.redAccent, fontSize: 14),
        ),
      ],
    );
  }

  Widget _buildResultState() {
    final outcome = _outcome!;
    final isGood = outcome == _ScanOutcome.welcome || outcome == _ScanOutcome.goodbye;
    final color = switch (outcome) {
      _ScanOutcome.welcome => AppColors.success,
      _ScanOutcome.goodbye => AppColors.primary,
      _ScanOutcome.invalid => AppColors.danger,
      _ScanOutcome.duplicate => AppColors.warning,
      _ScanOutcome.error => AppColors.danger,
    };
    final title = switch (outcome) {
      _ScanOutcome.welcome => 'Welcome!',
      _ScanOutcome.goodbye => 'Goodbye!',
      _ScanOutcome.invalid => 'Card Not Recognized',
      _ScanOutcome.duplicate => 'Already Recorded',
      _ScanOutcome.error => 'Something Went Wrong',
    };
    final name = _resultData?['name'] as String?;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 120,
          height: 120,
          decoration: BoxDecoration(shape: BoxShape.circle, color: color.withValues(alpha: 0.15)),
          child: Icon(
            isGood ? Icons.check_rounded : (outcome == _ScanOutcome.error ? Icons.error_outline_rounded : Icons.info_outline_rounded),
            color: color,
            size: 64,
          ),
        ),
        const SizedBox(height: 24),
        Text(title, style: TextStyle(color: color, fontSize: 26, fontWeight: FontWeight.w900)),
        if (name != null) ...[
          const SizedBox(height: 14),
          Text(name, style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700)),
        ] else if (_resultMessage != null) ...[
          const SizedBox(height: 12),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 40),
            child: Text(_resultMessage!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white70, fontSize: 14)),
          ),
        ],
      ],
    );
  }
}
