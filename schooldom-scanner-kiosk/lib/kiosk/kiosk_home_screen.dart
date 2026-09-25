import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:battery_plus/battery_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:nfc_manager/nfc_manager.dart';
import 'package:open_filex/open_filex.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:path_provider/path_provider.dart';
import 'package:wakelock_plus/wakelock_plus.dart';
import '../api/client.dart';
import '../api/config.dart';
import '../api/gate_endpoints.dart';
import '../services/app_updater.dart';
import '../services/local_sms.dart';
import '../services/receipt_printer.dart';
import '../storage/gate_settings_cache.dart';
import '../storage/guardian_contacts_cache.dart';
import '../storage/offline_queue.dart';
import '../storage/session_store.dart';
import '../theme/app_theme.dart';
import 'gate_settings_screen.dart';
import 'kiosk_store.dart';
import 'update_progress_dialog.dart';

enum _ScanOutcome { welcome, goodbye, invalid, duplicate, error }

/// Spec sections 3-8, 30 - the entire on-site experience: Ready to Scan,
/// tap a card, see who it is (never the raw card UID - section 2/10), hear a
/// voice line, auto-return. No menus, no logout (section 9/10).
class KioskHomeScreen extends StatefulWidget {
  const KioskHomeScreen({super.key});

  @override
  State<KioskHomeScreen> createState() => _KioskHomeScreenState();
}

class _KioskHomeScreenState extends State<KioskHomeScreen> with SingleTickerProviderStateMixin {
  // A card held near the reader too long can be discovered repeatedly in a
  // single tap - same reasoning as the RFID Win7 desktop app's cooldown.
  // Default of 8s until gate settings load; then server-configurable
  // (spec section 7 - "duplicate-protection interval should ideally be
  // configurable at the backend/device level").
  int _cooldownSeconds = 8;
  static const _resultDisplaySeconds = 4;
  // How long a tapped card may sit on "Reading card..." waiting for the
  // backend to identify it. After this the scan is treated as offline and
  // handled from the locally cached data (see _handleScan).
  static const _scanReadTimeout = Duration(seconds: 3);
  // How often the terminal reports in (battery, location, app version, unsynced
  // scans) and picks up remote changes (log-out, school switch, updates). It was
  // every 2 minutes. The server now calls a device offline after 12 minutes of
  // silence (Device.OFFLINE_AFTER_SECONDS), so a couple of missed beats still
  // don't flip it.
  static const _heartbeatInterval = Duration(minutes: 5);
  // The offline card list (name + guardian phone per card, used to text a parent
  // from the terminal's own SIM when the network is down) used to be downloaded
  // in full on every heartbeat - for a big school that is a large download and a
  // lot of JSON work on the UI thread every couple of minutes. It only changes
  // when cards are assigned, so pulling it this often is plenty.
  static const _contactsRefreshInterval = Duration(minutes: 30);

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
  Map<String, dynamic>? _updateInfo;
  bool _downloadingUpdate = false;
  // The build number we last popped the update dialog up for (once per launch,
  // and again only if an even newer build appears) - see _maybePromptForUpdate.
  int? _promptedUpdateCode;
  bool _updateDialogOpen = false;
  String? _pairedSchoolId;
  String? _pairedSchoolName;
  bool _switchingSchool = false;

  final Map<String, DateTime> _recentScans = {};
  Timer? _resultTimer;
  Timer? _heartbeatTimer;

  // Slow breathing glow behind the scan circle on the idle screen - purely
  // decorative, gives the "Ready to Scan" state some life instead of a
  // static ring sitting on a flat background.
  late final AnimationController _pulseController;

  // ------------------------------------------------------ External USB HID reader
  // A plugged-in USB HID keyboard-emulation card reader (the common/cheap type -
  // same category the Windows app's HidRfidReader.cs handles) shows up to Android
  // exactly like a physical keyboard: no USB permission dialog, no native plugin,
  // just ordinary key events delivered to whichever widget holds focus. This
  // FocusNode/KeyboardListener pair is that "whichever widget" - it must hold
  // focus at all times since kiosk mode has nothing else to give it to, and it
  // feeds the same _handleScan used by the built-in-NFC path above.
  final FocusNode _hidFocusNode = FocusNode();
  final StringBuffer _hidBuffer = StringBuffer();
  DateTime? _lastHidKeyAt;
  bool _hidBufferLooksLikeScan = true;
  static const _hidFastKeystrokeThresholdMs = 50;
  static const _hidIdleResetMs = 400;

  // Settings/PIN screens are pushed ON TOP of this one - KioskHomeScreen
  // stays mounted underneath (Navigator.push never disposes the route it
  // covers), so without this flag the reclaim-focus listener below would
  // keep stealing focus back from those screens' own text fields every
  // 50ms, making their on-screen keyboard flash open/closed in a fight
  // for focus. _pauseHidCapture()/_resumeHidCapture() bracket every such
  // navigation.
  bool _hidCaptureEnabled = true;

  void _pauseHidCapture() {
    _hidCaptureEnabled = false;
    _hidFocusNode.unfocus();
  }

  void _resumeHidCapture() {
    _hidCaptureEnabled = true;
    if (mounted) _hidFocusNode.requestFocus();
  }

  @override
  void initState() {
    super.initState();
    WakelockPlus.enable();
    _pulseController = AnimationController(vsync: this, duration: const Duration(seconds: 2))..repeat(reverse: true);
    _tts.setLanguage('en-US');
    _tts.setSpeechRate(0.46);
    _tts.setVolume(1.0);
    _loadSchoolName();
    _loadGateSettings();
    _startNfcSession();
    _ensureLocationPermission();
    _sendHeartbeat();
    _heartbeatTimer = Timer.periodic(_heartbeatInterval, (_) => _sendHeartbeat());
    _hidFocusNode.addListener(() {
      if (_hidCaptureEnabled && !_hidFocusNode.hasFocus) {
        Future.delayed(const Duration(milliseconds: 50), () {
          if (mounted && _hidCaptureEnabled) _hidFocusNode.requestFocus();
        });
      }
    });
  }

  @override
  void dispose() {
    _resultTimer?.cancel();
    _heartbeatTimer?.cancel();
    _pulseController.dispose();
    NfcManager.instance.stopSession();
    _hidFocusNode.dispose();
    WakelockPlus.disable();
    _tts.stop();
    super.dispose();
  }

  /// Distinguishing a card scan from stray/human key input is done purely by
  /// inter-keystroke timing, mirroring HidRfidReader.cs exactly: keys arriving
  /// less than [_hidFastKeystrokeThresholdMs] apart are a candidate scan;
  /// Enter/Tab commits the buffer; a gap larger than [_hidIdleResetMs] at any
  /// point invalidates the buffer as "not a scan" (dropped, never forwarded).
  void _handleHidKeyEvent(KeyEvent event) {
    if (event is! KeyDownEvent) return;
    final now = DateTime.now();
    final gapMs = _lastHidKeyAt == null ? null : now.difference(_lastHidKeyAt!).inMilliseconds;
    _lastHidKeyAt = now;

    if (gapMs == null || gapMs > _hidIdleResetMs) {
      _hidBuffer.clear();
      _hidBufferLooksLikeScan = true;
    } else if (_hidBuffer.isNotEmpty && gapMs > _hidFastKeystrokeThresholdMs) {
      _hidBufferLooksLikeScan = false;
    }

    // physicalKey, not logicalKey: logicalKey is translated through whatever
    // keyboard layout/locale Android has assigned to this external HID
    // device, and a generic/unbranded USB HID reader can get assigned a
    // non-US layout - digit keys then arrive as letters or symbols. The
    // physical key position is layout-independent, exactly like the Windows
    // app's raw virtual-key-code hook (VK_0-VK_9 are the same regardless of
    // layout there too).
    final key = event.physicalKey;
    if (key == PhysicalKeyboardKey.enter || key == PhysicalKeyboardKey.numpadEnter || key == PhysicalKeyboardKey.tab) {
      _commitHidBuffer();
      return;
    }

    final ch = _hidCharFor(key);
    if (ch != null) {
      _hidBuffer.write(ch);
    } else {
      // Any key that isn't a plausible UID character (arrows, function keys,
      // modifiers, etc.) can't be part of a reader payload.
      _hidBufferLooksLikeScan = false;
    }
  }

  // Deliberately simple, matching HidRfidReader.VirtualKeyToChar: readers only
  // ever "type" digits and occasionally uppercase letters (hex UIDs), always
  // via the shift-independent physical key regardless of actual shift state.
  // Not `const` - PhysicalKeyboardKey overrides == / hashCode, which the
  // language disallows as a const-map key even though these values never
  // change at runtime.
  static final _hidDigitKeys = {
    PhysicalKeyboardKey.digit0: '0', PhysicalKeyboardKey.digit1: '1',
    PhysicalKeyboardKey.digit2: '2', PhysicalKeyboardKey.digit3: '3',
    PhysicalKeyboardKey.digit4: '4', PhysicalKeyboardKey.digit5: '5',
    PhysicalKeyboardKey.digit6: '6', PhysicalKeyboardKey.digit7: '7',
    PhysicalKeyboardKey.digit8: '8', PhysicalKeyboardKey.digit9: '9',
    PhysicalKeyboardKey.numpad0: '0', PhysicalKeyboardKey.numpad1: '1',
    PhysicalKeyboardKey.numpad2: '2', PhysicalKeyboardKey.numpad3: '3',
    PhysicalKeyboardKey.numpad4: '4', PhysicalKeyboardKey.numpad5: '5',
    PhysicalKeyboardKey.numpad6: '6', PhysicalKeyboardKey.numpad7: '7',
    PhysicalKeyboardKey.numpad8: '8', PhysicalKeyboardKey.numpad9: '9',
  };
  static final _hidLetterKeys = {
    PhysicalKeyboardKey.keyA: 'A', PhysicalKeyboardKey.keyB: 'B', PhysicalKeyboardKey.keyC: 'C',
    PhysicalKeyboardKey.keyD: 'D', PhysicalKeyboardKey.keyE: 'E', PhysicalKeyboardKey.keyF: 'F',
    PhysicalKeyboardKey.keyG: 'G', PhysicalKeyboardKey.keyH: 'H', PhysicalKeyboardKey.keyI: 'I',
    PhysicalKeyboardKey.keyJ: 'J', PhysicalKeyboardKey.keyK: 'K', PhysicalKeyboardKey.keyL: 'L',
    PhysicalKeyboardKey.keyM: 'M', PhysicalKeyboardKey.keyN: 'N', PhysicalKeyboardKey.keyO: 'O',
    PhysicalKeyboardKey.keyP: 'P', PhysicalKeyboardKey.keyQ: 'Q', PhysicalKeyboardKey.keyR: 'R',
    PhysicalKeyboardKey.keyS: 'S', PhysicalKeyboardKey.keyT: 'T', PhysicalKeyboardKey.keyU: 'U',
    PhysicalKeyboardKey.keyV: 'V', PhysicalKeyboardKey.keyW: 'W', PhysicalKeyboardKey.keyX: 'X',
    PhysicalKeyboardKey.keyY: 'Y', PhysicalKeyboardKey.keyZ: 'Z',
  };

  String? _hidCharFor(PhysicalKeyboardKey key) => _hidDigitKeys[key] ?? _hidLetterKeys[key];

  void _commitHidBuffer() {
    final candidate = _hidBuffer.toString();
    _hidBuffer.clear();
    final wasQualified = _hidBufferLooksLikeScan;
    _hidBufferLooksLikeScan = true;
    if (!wasQualified || candidate.isEmpty) return;
    _handleScan(candidate);
  }

  Future<void> _loadSchoolName() async {
    final name = await KioskStore.schoolName;
    final pairedId = await KioskStore.pairedSchoolId;
    final pairedName = await KioskStore.pairedSchoolName;
    if (mounted) {
      setState(() {
        _schoolName = name;
        _pairedSchoolId = pairedId;
        _pairedSchoolName = pairedName;
      });
    }
  }

  Future<void> _loadGateSettings() async {
    try {
      final res = await loadGateSettings();
      final data = res['data'] as Map<String, dynamic>;
      final seconds = (data['duplicate_protection_seconds'] as num?)?.toInt();
      if (mounted && seconds != null) setState(() => _cooldownSeconds = seconds);
      await GateSettingsCache.save(data);
    } catch (_) {
      // Keep the 8s default (and whatever was cached last time) - a
      // settings-fetch failure shouldn't block scanning.
    }
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
      // Spec section 7: an explicit message instead of a silent ignore -
      // "Attendance already recorded at 7:42 AM."
      await _showResult(_ScanOutcome.duplicate, message: 'Attendance already recorded at ${_formatTime(lastAt)}.');
      return;
    }
    _recentScans[uid] = DateTime.now();
    _recentScans.removeWhere((_, t) => DateTime.now().difference(t).inMinutes > 10);

    setState(() => _busy = true);
    final idempotencyKey = _uuid();

    try {
      final result = await postJson(
        '/api/rfid/attendance/scan/',
        {
          'card_uid': uid,
          'idempotency_key': idempotencyKey,
          'device_id': await KioskStore.deviceId,
        },
        queueWhenOffline: true,
        timeout: _scanReadTimeout,
      );

      if (result['offline'] == true) {
        // Either no network at all, or the backend didn't answer within
        // _scanReadTimeout (timed_out) - either way we go on what is cached.
        // The queue mechanism above blindly stores ANY scan, so check the last-synced
        // assignment snapshot ourselves before claiming success for a card
        // that was never actually registered. An unknown card can never
        // succeed once replayed either, so drop it from the queue instead
        // of leaving it stuck retrying forever.
        final contact = await GuardianContactsCache.lookup(uid);
        if (contact == null && result['timed_out'] == true) {
          // The backend is only slow, not unreachable, so it may well know
          // this card - our cache just doesn't. Keep the scan queued for the
          // replay to settle instead of telling a real student their card is
          // unregistered.
          await _showResult(_ScanOutcome.welcome, message: 'Saved - will sync when back online.');
          unawaited(_refreshPendingCount());
          return;
        }
        if (contact == null) {
          await _removeQueuedScan(idempotencyKey);
          await _showResult(_ScanOutcome.invalid, message: 'Card not recognized (offline).');
          unawaited(_refreshPendingCount());
          return;
        }

        // Best-effort label from the admin-configured early/late/clock-out
        // time windows (GateSettingsCache mirrors GateSettings.classify_event)
        // - the actual clock-in/clock-out DIRECTION still can't be known
        // offline (that depends on whether this student already clocked in
        // today, which needs server-side attendance history this client
        // doesn't keep), but at least the wording matches what admin
        // settings say about the current time of day, rather than a
        // schedule-blind generic message.
        var message = 'Saved - will sync when back online.';
        final phone = contact['phone'] ?? '';
        final event = await GateSettingsCache.classifyEvent(DateTime.now());
        if (phone.isNotEmpty) {
          final name = contact['name'] ?? 'Student';
          final timeText = _formatTime(DateTime.now());
          final text = switch (event) {
            'clockout' => '$name left school at $timeText. -SchoolDom',
            'early' => '$name arrived (early) at $timeText. -SchoolDom',
            'late' => '$name arrived (late) at $timeText. -SchoolDom',
            _ => '$name was scanned at the school gate at $timeText. -SchoolDom',
          };
          final sent = await LocalSms.send(phone, text);
          if (sent) {
            await _markQueuedScanSmsSent(idempotencyKey);
            message = 'Saved - parent texted directly (offline).';
          } else {
            // The SIM couldn't send it (no airtime, no signal...). The scan is
            // deliberately NOT flagged sms_sent_locally, so the server texts
            // the parent itself when the scan syncs - say so the operator can
            // also fix the SIM.
            message = 'Saved - SMS failed (check SIM airtime). Parent will be texted once back online.';
          }
        }
        await _showResult(event == 'clockout' ? _ScanOutcome.goodbye : _ScanOutcome.welcome, message: message);
        // Not awaited: replayOfflineQueue() syncs in the background from
        // here on. Awaiting it used to mean a slow/flaky connection (not a
        // clean disconnect, which fails fast) held _busy true well past the
        // ~4s the result flash stays up for - so once _outcome reset to null,
        // the ready screen came back showing "Reading card..." (busy still
        // true) instead of "Ready to Scan", stuck until the sync eventually
        // gave up. See replayOfflineQueue's own _replayItemTimeout for the
        // network-side half of this fix.
        unawaited(_refreshPendingCount());
        return;
      }

      final action = result['action'] as String?;
      final person = result['person'] as Map<String, dynamic>?;
      // fees/student_dva are only ever non-null when the backend's own
      // Fee Tracker + clock-in gating (spec sections 2, 3) allows it - the
      // client trusts that gate rather than re-deciding it here.
      final combined = {
        ...?person,
        'fees': result['fees'],
        'student_dva': result['student_dva'],
        'attendance_event': result['attendance_event'],
      };
      await _showResult(
        action == 'clock_out' ? _ScanOutcome.goodbye : _ScanOutcome.welcome,
        data: combined,
        message: result['message'] as String?,
      );
    } on ApiException catch (e) {
      if (e.statusCode == 404) {
        // attendance_scan_create's "unregistered" response names the exact
        // card_uid it looked up and didn't find (e.g. "Card 0012345678 is
        // not linked to anyone.") - surfacing it is the only way to tell a
        // genuinely-unregistered card apart from a UID-format mismatch
        // against whatever string card_assignment_create actually stored.
        await _showResult(_ScanOutcome.invalid, message: e.message);
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

    // Deliberately generic, never the student's name - a shared kiosk
    // announcing names aloud is a privacy concern the school flagged.
    final line = switch (outcome) {
      _ScanOutcome.welcome => 'Welcome.',
      _ScanOutcome.goodbye => 'Goodbye.',
      _ScanOutcome.invalid => 'This card is not registered.',
      _ScanOutcome.duplicate => 'Attendance has already been recorded.',
      _ScanOutcome.error => 'Unable to record attendance. Please try again.',
    };
    unawaited(_tts.speak(line).catchError((Object error) {
      // flutter_tts fails silently on a device with no TTS engine installed
      // (common on locked-down Android POS terminal firmware) - logging it
      // at least makes that diagnosable instead of a mysterious "no sound".
      debugPrint('TTS speak failed: $error');
    }));

    // Fee Tracker's result (with Print/Send SMS buttons to act on) needs
    // real time to read and tap, unlike the plain welcome/goodbye flash -
    // spec sections 2B/8 assume a brief pause here, not an instant return.
    final hasFees = data?['fees'] != null;
    _resultTimer?.cancel();
    _resultTimer = Timer(Duration(seconds: hasFees ? 15 : _resultDisplaySeconds), () {
      if (mounted) setState(() => _outcome = null);
    });
  }

  /// Flags the just-enqueued offline scan so its eventual replay tells the
  /// server not to send its own gate SMS (we already texted the parent
  /// directly, see _handleScan's offline branch).
  Future<void> _markQueuedScanSmsSent(String idempotencyKey) async {
    final queue = await readQueue();
    for (final item in queue) {
      final payload = item['payload'];
      if (payload is Map && payload['idempotency_key'] == idempotencyKey) {
        payload['sms_sent_locally'] = true;
      }
    }
    await writeQueue(queue);
  }

  /// Drops the just-enqueued scan for a card GuardianContactsCache doesn't
  /// recognize - it would just fail the same way (404) on every replay
  /// attempt forever, keeping _pendingCount permanently stuck above zero.
  Future<void> _removeQueuedScan(String idempotencyKey) async {
    final queue = await readQueue();
    queue.removeWhere((item) {
      final payload = item['payload'];
      return payload is Map && payload['idempotency_key'] == idempotencyKey;
    });
    await writeQueue(queue);
  }

  Future<void> _refreshPendingCount() async {
    // replayOfflineQueue() also opportunistically flushes - harmless to call
    // here since a fresh scan just landed in the same queue, and this is
    // the only place in kiosk mode that needs the count at all.
    final result = await replayOfflineQueue();
    if (mounted) setState(() => _pendingCount = result.remaining);
  }

  // ---------------------------------------------------------------- Location

  /// Requested once at startup rather than lazily on first heartbeat -
  /// whoever is physically setting up the kiosk is present to tap "Allow"
  /// on the system dialog; nobody will be there to grant it later once the
  /// terminal is unattended at reception.
  Future<void> _ensureLocationPermission() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) return;
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
    } catch (_) {
      // Never blocks kiosk operation - location is a nice-to-have, not a
      // required capability like NFC/attendance recording.
    }
  }

  /// Null on any failure (denied, disabled, no fix within the timeout) -
  /// never guessed - a fixed indoor kiosk can genuinely fail to get a fix,
  /// and a stale/wrong coordinate would be worse than reporting none.
  Future<Position?> _getCurrentLocation() async {
    try {
      if (!await Geolocator.isLocationServiceEnabled()) return null;
      final permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
        return null;
      }
      return await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(accuracy: LocationAccuracy.medium, timeLimit: Duration(seconds: 12)),
      );
    } catch (_) {
      return null;
    }
  }

  // ---------------------------------------------------------------- Heartbeat

  // Guards against a slow heartbeat (see the timeout on the POST below - this
  // is a second line of defense for whatever that timeout doesn't cover,
  // e.g. time spent waiting on battery/location) still being in flight when
  // the next one fires a few minutes later; without it a run of degraded network
  // conditions could pile up more and more overlapping heartbeats instead of
  // just one at a time.
  bool _heartbeatInFlight = false;

  Future<void> _sendHeartbeat() async {
    if (_heartbeatInFlight) return;
    _heartbeatInFlight = true;
    try {
      final battery = await _battery.batteryLevel.catchError((_) => -1);
      final state = await _battery.batteryState.catchError((_) => BatteryState.unknown);
      final packageInfo = await PackageInfo.fromPlatform();
      final deviceAuthToken = await KioskStore.deviceAuthToken;
      if (deviceAuthToken == null) return;
      final position = await _getCurrentLocation();

      // Bounded like every other network call this app makes (see
      // _scanReadTimeout/_replayItemTimeout) - this used to have no timeout
      // at all, so a flaky-but-not-fully-down connection could leave a
      // heartbeat hanging indefinitely, and with a new one due every few
      // minutes regardless (_heartbeatInFlight guards that pile-up), a
      // terminal on a bad connection could accumulate more and more stuck
      // requests over hours of uptime.
      final response = await http.post(
        Uri.parse('$apiBaseUrl/api/device-fleet/device/heartbeat/'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'auth_token': deviceAuthToken,
          'app_version': packageInfo.version,
          'app_version_code': int.tryParse(packageInfo.buildNumber),
          if (battery >= 0) 'battery_percentage': battery,
          'battery_charging': state == BatteryState.charging || state == BatteryState.full,
          'synced': _pendingCount == 0,
          if (position != null) 'latitude': position.latitude,
          if (position != null) 'longitude': position.longitude,
        }),
      ).timeout(const Duration(seconds: 10));
      if (!mounted) return;
      setState(() => _online = response.statusCode == 200);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        if (data['authorized'] == false) {
          await _handleRemoteRevocation();
          return;
        }
        final schoolId = data['school_id'] as String?;
        final schoolName = data['school_name'] as String?;
        if (schoolId != null && schoolName != null && schoolName != _schoolName) {
          setState(() => _schoolName = schoolName);
          await KioskStore.setActiveSchool(id: schoolId, name: schoolName);
          // The card list on hand belongs to the previous school.
          _contactsRefreshedAt = null;
        }
        final pairedId = data['paired_school_id'] as String?;
        final pairedName = data['paired_school_name'] as String?;
        if (pairedId != _pairedSchoolId || pairedName != _pairedSchoolName) {
          setState(() {
            _pairedSchoolId = pairedId;
            _pairedSchoolName = pairedName;
          });
          await KioskStore.setPairedSchool(id: pairedId, name: pairedName);
        }
        if (data['update_available'] == true) {
          setState(() => _updateInfo = data);
          _maybePromptForUpdate(data);
        }
        // Piggyback on a confirmed-online heartbeat to keep the offline
        // guardian-phone cache fresh (see _handleScan's offline branch) - but
        // only when it has gone stale, not on every beat.
        _refreshContactsIfStale();
      }
    } catch (_) {
      if (mounted) setState(() => _online = false);
    } finally {
      _heartbeatInFlight = false;
    }
    _refreshPendingCount();
  }

  DateTime? _contactsRefreshedAt;
  bool _contactsRefreshing = false;

  /// Pulls the offline card list if it has never been pulled or is older than
  /// [_contactsRefreshInterval]. A failed pull does not count, so it is retried
  /// on the next heartbeat rather than after another 30 minutes.
  void _refreshContactsIfStale() {
    final last = _contactsRefreshedAt;
    if (_contactsRefreshing) return;
    if (last != null && DateTime.now().difference(last) < _contactsRefreshInterval) return;
    _contactsRefreshing = true;
    unawaited(
      GuardianContactsCache.refresh()
          .then((ok) {
            if (ok) _contactsRefreshedAt = DateTime.now();
          })
          .whenComplete(() => _contactsRefreshing = false),
    );
  }

  Future<void> _handleRemoteRevocation() async {
    await clearSession();
    await KioskStore.deactivate();
    if (!mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil('/', (route) => false);
  }

  String _formatTime(DateTime dt) {
    final hour = dt.hour % 12 == 0 ? 12 : dt.hour % 12;
    final minute = dt.minute.toString().padLeft(2, '0');
    final period = dt.hour >= 12 ? 'PM' : 'AM';
    return '$hour:$minute $period';
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
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment(0, -0.35),
            radius: 1.1,
            colors: [Color(0xFF152238), Color(0xFF0B1220)],
          ),
        ),
        child: KeyboardListener(
          focusNode: _hidFocusNode,
          autofocus: true,
          onKeyEvent: _handleHidKeyEvent,
          child: SafeArea(
            child: Stack(
              children: [
                Center(child: _outcome == null ? _buildReadyState() : _buildResultState()),
                Positioned(top: 12, left: 0, right: 0, child: _buildStatusBar()),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildStatusBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.04),
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
        ),
        // The school name used to sit at the left of this pill; it now leaves
        // the top bar to the icons (the big school name above the scan circle
        // is what identifies the school), so they can be centred and given
        // proper tap targets instead of 14px icons squeezed to one side.
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (_pendingCount > 0)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Icon(Icons.cloud_upload_outlined, size: 18, color: Colors.amber.shade300),
                  const SizedBox(width: 4),
                  Text('$_pendingCount pending', style: TextStyle(color: Colors.amber.shade300, fontSize: 12, fontWeight: FontWeight.w700)),
                ]),
              ),
            if (_updateInfo != null)
              _statusButton(
                onTap: _showUpdateDialog,
                child: Icon(Icons.system_update_outlined, size: _statusIconSize, color: Colors.amber.shade300),
              ),
            if (_pairedSchoolName != null)
              _statusButton(
                onTap: _switchingSchool ? null : _confirmSwitchSchool,
                child: _switchingSchool
                    ? const SizedBox(
                        width: _statusIconSize,
                        height: _statusIconSize,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white38),
                      )
                    : const Icon(Icons.sync_alt, size: _statusIconSize, color: Colors.white38),
              ),
            // Connection indicator - not a button.
            _statusButton(
              child: Icon(_online ? Icons.wifi : Icons.wifi_off, size: _statusIconSize, color: _online ? Colors.white38 : Colors.redAccent),
            ),
            _statusButton(
              onTap: () async {
                _pauseHidCapture();
                await Navigator.of(context).push(MaterialPageRoute(builder: (_) => const GatePinScreen()));
                _resumeHidCapture();
              },
              child: const Icon(Icons.settings_outlined, size: _statusIconSize, color: Colors.white38),
            ),
            // Re-opens the license-key entry screen - for recovering from a
            // wrong/expired code or a terminal stuck on "Waiting for school
            // assignment". Gated behind a confirmation dialog rather than
            // acting on a bare tap, since a single accidental tap
            // de-registering a live terminal would be worse than the
            // friction of one extra step.
            _statusButton(
              onTap: _confirmReProvision,
              child: const Icon(Icons.key_outlined, size: _statusIconSize, color: Colors.white38),
            ),
          ],
        ),
      ),
    );
  }

  static const double _statusIconSize = 20;

  /// One icon in the top pill, padded out to a comfortable tap target. The
  /// whole padded square answers taps (opaque), not just the icon's own pixels.
  Widget _statusButton({required Widget child, VoidCallback? onTap}) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: onTap,
      child: Padding(padding: const EdgeInsets.all(10), child: child),
    );
  }

  Future<void> _confirmReProvision() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: const Color(0xFF15213A),
        title: const Text('Re-enter license key?', style: TextStyle(color: Colors.white)),
        content: const Text(
          'This deactivates this terminal\'s current registration and returns to the activation screen. '
          'Use this if the wrong key was entered, or the device is stuck waiting for a school assignment.',
          style: TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Cancel', style: TextStyle(color: Colors.white54)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Continue', style: TextStyle(color: AppColors.primary, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await clearSession();
    await KioskStore.deactivate();
    if (!mounted) return;
    Navigator.of(context).pushNamedAndRemoveUntil('/', (route) => false);
  }

  Future<void> _showUpdateDialog() async {
    final info = _updateInfo;
    if (info == null || _downloadingUpdate || _updateDialogOpen) return;
    final versionName = info['latest_version_name'] as String? ?? '';
    final notes = (info['release_notes'] as String? ?? '').trim();

    _updateDialogOpen = true;
    final bool? confirmed;
    try {
      confirmed = await _askToUpdate(versionName, notes);
    } finally {
      _updateDialogOpen = false;
    }
    if (confirmed != true || !mounted) return;
    await _installUpdate(info);
  }

  /// Pops the "update available" question up on its own the first time a
  /// heartbeat reports a newer build after launch, instead of leaving it to a
  /// tiny icon nobody notices. Held back while a card is being read or a scan
  /// result is showing; the next heartbeat (5 min) tries again.
  void _maybePromptForUpdate(Map<String, dynamic> info) {
    final code = (info['latest_version_code'] as num?)?.toInt();
    final show = shouldPromptForUpdate(
      latestCode: code,
      promptedCode: _promptedUpdateCode,
      busy: _busy || _downloadingUpdate,
      showingResult: _outcome != null,
      screenIsCurrent: mounted && (ModalRoute.of(context)?.isCurrent ?? false),
      dialogOpen: _updateDialogOpen,
    );
    if (!show) return;
    _promptedUpdateCode = code;
    unawaited(_showUpdateDialog());
  }

  Future<bool?> _askToUpdate(String versionName, String notes) {
    return showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          backgroundColor: const Color(0xFF15213A),
          title: Text('Update available - $versionName', style: const TextStyle(color: Colors.white)),
          content: Text(
            notes.isNotEmpty ? notes : 'A newer version of this app is available.',
            style: const TextStyle(color: Colors.white70),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Later', style: TextStyle(color: Colors.white54)),
            ),
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Install Now', style: TextStyle(color: AppColors.primary, fontWeight: FontWeight.bold)),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _installUpdate(Map<String, dynamic> info) async {
    final apkUrl = info['apk_url'] as String?;
    if (apkUrl == null || apkUrl.isEmpty) return;
    final versionName = info['latest_version_name'] as String? ?? '';

    final progress = ValueNotifier<UpdateProgress>(const UpdateProgress.downloading(0, null));
    http.Client? client;
    File? downloaded; // kept so "Open installer again" doesn't download twice
    var cancelled = false;
    var closed = false; // once true, nothing may touch `progress` any more

    Future<void> openInstaller(File file) async {
      progress.value = const UpdateProgress.installing();
      // Hands the APK to Android's own package installer - the OS shows its
      // standard "install this app?" prompt (and, the very first time, an
      // "allow installs from this app" permission screen). This app never
      // installs anything silently.
      final result = await OpenFilex.open(file.path);
      if (result.type != ResultType.done && !closed) {
        progress.value = UpdateProgress.failed('Could not open the installer: ${result.message}');
      }
    }

    Future<void> download() async {
      cancelled = false;
      final myClient = client = http.Client();
      progress.value = const UpdateProgress.downloading(0, null);
      try {
        final dir = await getTemporaryDirectory();
        final versionCode = info['latest_version_code'] ?? DateTime.now().millisecondsSinceEpoch;
        final file = await AppUpdater.download(
          client: myClient,
          url: Uri.parse(apkUrl),
          destination: File('${dir.path}/schoolgate-kiosk-$versionCode.apk'),
          onProgress: (received, total) {
            if (!closed) progress.value = UpdateProgress.downloading(received, total);
          },
        );
        if (closed) return;
        downloaded = file;
        await openInstaller(file);
      } catch (e) {
        if (cancelled || closed) return;
        progress.value = UpdateProgress.failed(describeUpdateError(e));
      } finally {
        myClient.close();
      }
    }

    setState(() => _downloadingUpdate = true);
    final screen = showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => UpdateProgressDialog(
        versionName: versionName,
        progress: progress,
        onCancel: () {
          cancelled = true;
          closed = true;
          client?.close();
          Navigator.of(dialogContext).pop();
        },
        onRetry: () {
          final file = downloaded;
          unawaited(file != null ? openInstaller(file) : download());
        },
        onOpenInstaller: () {
          final file = downloaded;
          if (file != null) unawaited(openInstaller(file));
        },
        onClose: () {
          closed = true;
          Navigator.of(dialogContext).pop();
        },
      ),
    );
    unawaited(download());
    await screen;
    closed = true;
    progress.dispose();
    if (mounted) setState(() => _downloadingUpdate = false);
  }

  // ---------------------------------------------------------------- Dual-school switching

  Future<Map<String, dynamic>?> _switchActiveSchool(String schoolId) async {
    final deviceAuthToken = await KioskStore.deviceAuthToken;
    if (deviceAuthToken == null) return null;
    final response = await http.post(
      Uri.parse('$apiBaseUrl/api/device-fleet/device/switch-active-school/'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'auth_token': deviceAuthToken, 'school_id': schoolId}),
    );
    final data = jsonDecode(response.body) as Map<String, dynamic>;
    if (response.statusCode != 200 || data['success'] != true) {
      throw Exception(data['message'] ?? 'Switch failed (HTTP ${response.statusCode}).');
    }
    return data;
  }

  Future<void> _confirmSwitchSchool() async {
    final pairedId = _pairedSchoolId;
    final pairedName = _pairedSchoolName;
    if (pairedId == null || pairedName == null || _switchingSchool) return;

    _pauseHidCapture();
    NfcManager.instance.stopSession();
    setState(() => _switchingSchool = true);
    try {
      // Force a real flush and check what actually remains - a queued scan
      // that syncs after the switch would otherwise be attributed to the
      // newly active school instead of the one it was captured for.
      final flush = await replayOfflineQueue();
      if (flush.remaining > 0) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Could not sync ${flush.remaining} pending scan(s) - check connection and try again.'),
              backgroundColor: AppColors.danger,
            ),
          );
        }
        return;
      }
      setState(() => _pendingCount = 0);

      if (!mounted) return;
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          backgroundColor: const Color(0xFF15213A),
          title: const Text('Switch active school?', style: TextStyle(color: Colors.white)),
          content: Text(
            'This terminal will now record attendance for $pairedName instead of $_schoolName, until switched back.',
            style: const TextStyle(color: Colors.white70),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, false),
              child: const Text('Cancel', style: TextStyle(color: Colors.white54)),
            ),
            TextButton(
              onPressed: () => Navigator.pop(dialogContext, true),
              child: const Text('Switch', style: TextStyle(color: AppColors.primary, fontWeight: FontWeight.bold)),
            ),
          ],
        ),
      );
      if (confirmed != true) return;

      final result = await _switchActiveSchool(pairedId);
      if (result == null) return;

      final newSchoolId = result['school_id'] as String?;
      final newSchoolName = result['school_name'] as String?;
      final newPairedId = result['paired_school_id'] as String?;
      final newPairedName = result['paired_school_name'] as String?;
      if (newSchoolId != null && newSchoolName != null) {
        await KioskStore.setActiveSchool(id: newSchoolId, name: newSchoolName);
      }
      await KioskStore.setPairedSchool(id: newPairedId, name: newPairedName);

      // The duplicate-tap cache is keyed on card UID alone, which is only
      // unique per school - it must not carry across a school boundary. Same
      // for the offline card list: fetch the new school's right away.
      _recentScans.clear();
      _contactsRefreshedAt = null;
      _refreshContactsIfStale();

      if (mounted) {
        setState(() {
          _schoolName = newSchoolName;
          _pairedSchoolId = newPairedId;
          _pairedSchoolName = newPairedName;
        });
      }
      await _loadGateSettings();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not switch school: $e'), backgroundColor: AppColors.danger),
        );
      }
    } finally {
      if (mounted) setState(() => _switchingSchool = false);
      _startNfcSession();
      _resumeHidCapture();
    }
  }

  Widget _buildReadyState() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // The school's own identity leads - this is their kiosk, standing
        // in their reception/gate, not a "SchoolDom" branded device from a
        // visitor's point of view. Product branding is now the small
        // "Powered by" line underneath instead of the headline.
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Text(
            _schoolName ?? 'Welcome',
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: Colors.white, fontSize: 30, fontWeight: FontWeight.w900, height: 1.15),
          ),
        ),
        const SizedBox(height: 8),
        RichText(
          text: const TextSpan(
            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: 0.3),
            children: [
              TextSpan(text: 'Powered by ', style: TextStyle(color: Colors.white38)),
              TextSpan(text: 'School', style: TextStyle(color: Colors.white54)),
              TextSpan(text: 'Dom', style: TextStyle(color: AppColors.primary)),
            ],
          ),
        ),
        const SizedBox(height: 48),
        AnimatedBuilder(
          animation: _pulseController,
          builder: (context, child) {
            final t = _pulseController.value; // 0 -> 1 -> 0
            return Container(
              width: 190,
              height: 190,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: AppColors.primary.withValues(alpha: 0.18 + (0.12 * t)),
                    blurRadius: 30 + (20 * t),
                    spreadRadius: 2 + (4 * t),
                  ),
                ],
                border: Border.all(color: AppColors.primary.withValues(alpha: 0.4 + (0.2 * t)), width: 2),
              ),
              child: child,
            );
          },
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
        const SizedBox(height: 36),
        Text(
          _busy ? 'Reading card...' : 'Ready to Scan',
          style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 10),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.05),
            borderRadius: BorderRadius.circular(999),
          ),
          child: Text(
            // The connected USB reader path works regardless of _nfcAvailable
            // (it doesn't touch the device's own NFC antenna at all), so this
            // no longer claims scanning is unavailable just because the
            // device's built-in NFC is missing/off.
            _nfcAvailable ? 'Tap your card, or scan it on the connected reader' : 'Scan your card on the connected reader',
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.white54, fontSize: 13, fontWeight: FontWeight.w600),
          ),
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
    final photoUrl = _resultData?['photo_url'] as String?;
    final role = _resultData?['role'] as String?;
    final roleLabel = _resultData?['role_label'] as String?;
    final className = _resultData?['class_name'] as String?;
    final studentId = _resultData?['student_id'] as String?;
    // Spec sections 2B/3: fees/DVA are only ever non-null when the backend's
    // own mode+direction gating allows it (Fee Tracker mode, clock-in only) -
    // never shown on clock-out or in Attendance Only mode, and never
    // re-decided client-side.
    final fees = _resultData?['fees'] as Map<String, dynamic>?;
    final studentDva = _resultData?['student_dva'] as Map<String, dynamic>?;
    final isTeacher = isGood && role != null && role != 'student';

    Widget iconCircle() => Container(
          width: 120,
          height: 120,
          decoration: BoxDecoration(shape: BoxShape.circle, color: color.withValues(alpha: 0.15)),
          child: Icon(
            isGood ? Icons.check_rounded : (outcome == _ScanOutcome.error ? Icons.error_outline_rounded : Icons.info_outline_rounded),
            color: color,
            size: 64,
          ),
        );

    return SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // A recognized person's own photo reads far better at a glance than a
          // generic checkmark - falls back to the checkmark/icon circle above
          // whenever there's no photo on file, or the scan wasn't a real match
          // (invalid/duplicate/error never have a person to show a photo of).
          if (isGood && name != null && (photoUrl ?? '').isNotEmpty)
            ClipOval(
              child: Image.network(
                photoUrl!,
                width: 120,
                height: 120,
                fit: BoxFit.cover,
                errorBuilder: (_, _, _) => iconCircle(),
              ),
            )
          else
            iconCircle(),
          const SizedBox(height: 24),
          Text(title, style: TextStyle(color: color, fontSize: 26, fontWeight: FontWeight.w900)),
          if (name != null) ...[
            const SizedBox(height: 14),
            Text(name, style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700)),
            // Spec section 4: "Teacher cards must be distinguishable from
            // student cards" - staff/admin get a role badge; students get
            // their class + Student ID instead (sections 2A/2B).
            if (isTeacher) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(color: AppColors.primary.withValues(alpha: 0.18), borderRadius: BorderRadius.circular(20)),
                child: Text((roleLabel ?? role).toUpperCase(),
                    style: const TextStyle(color: AppColors.primary, fontSize: 11, fontWeight: FontWeight.w800)),
              ),
            ] else if (className != null || studentId != null) ...[
              const SizedBox(height: 6),
              Text(
                [if (className != null) className, if (studentId != null) studentId].join(' · '),
                style: const TextStyle(color: Colors.white54, fontSize: 13),
              ),
            ],
          ] else if (_resultMessage != null) ...[
            const SizedBox(height: 12),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 40),
              child: Text(_resultMessage!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white70, fontSize: 14)),
            ),
          ],
          if (fees != null) ...[
            const SizedBox(height: 20),
            _buildFeeCard(fees, studentDva, name ?? '', className ?? '', studentId ?? ''),
          ],
        ],
      ),
    );
  }

  Widget _buildFeeCard(
    Map<String, dynamic> fees,
    Map<String, dynamic>? studentDva,
    String name,
    String className,
    String studentId,
  ) {
    final paid = (fees['paid'] ?? '0').toString();
    final outstanding = (fees['outstanding'] ?? '0').toString();
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 32),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: const Color(0xFF15213A), borderRadius: BorderRadius.circular(16)),
      child: Column(
        children: [
          _feeRow('Fees Paid', '₦$paid', AppColors.success),
          const SizedBox(height: 6),
          _feeRow('Outstanding', '₦$outstanding', AppColors.danger),
          if (studentDva != null) ...[
            const SizedBox(height: 10),
            const Divider(color: Colors.white12, height: 1),
            const SizedBox(height: 10),
            Text('Student DVA', style: TextStyle(color: Colors.white54, fontSize: 11, fontWeight: FontWeight.w700)),
            Text('${studentDva['bank_name']} · ${studentDva['account_number']}',
                style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600)),
            if ((studentDva['account_name'] ?? '').toString().isNotEmpty)
              Text(studentDva['account_name'].toString(),
                  style: const TextStyle(color: Colors.white70, fontSize: 12, fontWeight: FontWeight.w500)),
          ],
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () => _printFeeReminder(name, className, studentId, paid, outstanding, studentDva),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: Colors.white,
                    side: const BorderSide(color: Colors.white24),
                    padding: const EdgeInsets.symmetric(vertical: 10),
                  ),
                  icon: const Icon(Icons.print_outlined, size: 16),
                  label: const Text('Print', style: TextStyle(fontSize: 12)),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: ElevatedButton.icon(
                  onPressed: () => _sendFeeReminderSms(),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.primary,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(vertical: 10),
                  ),
                  icon: const Icon(Icons.sms_outlined, size: 16),
                  label: const Text('Send SMS', style: TextStyle(fontSize: 12)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _feeRow(String label, String value, Color valueColor) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(color: Colors.white70, fontSize: 13)),
        Text(value, style: TextStyle(color: valueColor, fontSize: 15, fontWeight: FontWeight.w800)),
      ],
    );
  }

  Future<void> _printFeeReminder(String name, String className, String studentId, String paid, String outstanding, Map<String, dynamic>? studentDva) async {
    try {
      await ReceiptPrinter.printFeeReminder(
        schoolName: _schoolName ?? 'SchoolDom',
        studentName: name,
        studentClass: className,
        studentId: studentId,
        paid: '₦$paid',
        outstanding: '₦$outstanding',
        accountNumber: studentDva?['account_number']?.toString(),
        bankName: studentDva?['bank_name']?.toString(),
        accountName: studentDva?['account_name']?.toString(),
      );
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not print: $e'), backgroundColor: AppColors.danger),
        );
      }
    }
  }

  Future<void> _sendFeeReminderSms() async {
    final studentId = _resultData?['id'] as String?;
    if (studentId == null) return;
    try {
      await sendFeeReminder(studentId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Fee reminder sent.'), backgroundColor: AppColors.success),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not send: $e'), backgroundColor: AppColors.danger),
        );
      }
    }
  }
}
