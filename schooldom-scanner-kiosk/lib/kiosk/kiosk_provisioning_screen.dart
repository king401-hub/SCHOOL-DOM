import 'dart:convert';
import 'dart:io';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:package_info_plus/package_info_plus.dart';
import '../api/config.dart';
import '../storage/session_store.dart';
import '../theme/app_theme.dart';
import 'kiosk_home_screen.dart';
import 'kiosk_store.dart';

/// Spec section 11 - "New device -> displays provisioning screen -> enters
/// the Device License Key -> registers -> Ready to Scan". This is the very
/// first screen a freshly-installed terminal shows (see main.dart), and it
/// never appears again once a device is provisioned - main.dart routes
/// straight to KioskHomeScreen on every future launch.
class KioskProvisioningScreen extends StatefulWidget {
  const KioskProvisioningScreen({super.key});

  @override
  State<KioskProvisioningScreen> createState() =>
      _KioskProvisioningScreenState();
}

class _KioskProvisioningScreenState extends State<KioskProvisioningScreen> {
  final _keyController = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _keyController.dispose();
    super.dispose();
  }

  /// Real device_model/os_version/app_version - spec section 28: "Do not
  /// hardcode... device model... If a metric is unavailable, display 'Not
  /// Supported' rather than inventing a value." Falls back to empty strings
  /// (the backend already treats a blank device_model/os_version as
  /// "unknown", not a fabricated placeholder) if a plugin call fails.
  Future<Map<String, String>> _deviceTelemetry() async {
    var deviceModel = '';
    var osVersion = '';
    try {
      final deviceInfo = DeviceInfoPlugin();
      if (Platform.isAndroid) {
        final info = await deviceInfo.androidInfo;
        deviceModel = '${info.manufacturer} ${info.model}'.trim();
        osVersion = 'Android ${info.version.release}';
      } else if (Platform.isIOS) {
        final info = await deviceInfo.iosInfo;
        deviceModel = info.utsname.machine;
        osVersion = 'iOS ${info.systemVersion}';
      }
    } catch (_) {
      // Left blank rather than guessed - see the "Not Supported" rule above.
    }

    var appVersion = '';
    try {
      final packageInfo = await PackageInfo.fromPlatform();
      appVersion = packageInfo.version;
    } catch (_) {}

    return {
      'device_model': deviceModel,
      'os_version': osVersion,
      'app_version': appVersion,
    };
  }

  Future<void> _activate() async {
    final key = _keyController.text.trim();
    if (key.isEmpty) {
      setState(() => _error = 'Enter the device license key.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      final telemetry = await _deviceTelemetry();
      final response = await http.post(
        Uri.parse('$apiBaseUrl/api/device-fleet/device/provision/'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'provisioning_key': key,
          'device_name': 'SchoolDom Scanner',
          ...telemetry,
        }),
      );
      final body = response.body.isNotEmpty
          ? jsonDecode(response.body) as Map<String, dynamic>
          : <String, dynamic>{};

      if (response.statusCode != 201 || body['data'] == null) {
        setState(() {
          _error = (body['message'] as String?) ??
              'Could not activate this device. Check the key and try again.';
          _busy = false;
        });
        return;
      }

      final data = body['data'] as Map<String, dynamic>;
      await saveSession({
        'access': data['access_token'],
        'refresh': data['refresh_token'],
        'signedInAt': DateTime.now().toIso8601String(),
      });
      await KioskStore.activate(
        deviceId: data['device_id'] as String,
        deviceAuthToken: data['auth_token'] as String,
        schoolName: 'Waiting for school assignment',
      );

      if (!mounted) return;
      Navigator.of(context).pushAndRemoveUntil(
        MaterialPageRoute(builder: (_) => const KioskHomeScreen()),
        (route) => false,
      );
    } catch (_) {
      setState(() {
        _error = 'Network error - could not reach the SchoolDom server.';
        _busy = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 84,
                  height: 84,
                  decoration: BoxDecoration(
                    color: AppColors.primarySoft,
                    borderRadius: BorderRadius.circular(24),
                  ),
                  child: const Icon(Icons.qr_code_scanner_rounded,
                      size: 40, color: AppColors.primary),
                ),
                const SizedBox(height: 20),
                Text(
                  'SchoolDom Attendance Scanner',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w900,
                        color: AppColors.text,
                      ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Enter the device license key from the Superadmin Control Panel to activate this device as a dedicated attendance terminal.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.muted, fontSize: 13),
                ),
                const SizedBox(height: 28),
                TextField(
                  controller: _keyController,
                  textAlign: TextAlign.center,
                  textCapitalization: TextCapitalization.characters,
                  style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 1.5),
                  decoration: InputDecoration(
                    hintText: 'XXXX-XXXX-XXXX-XXXX',
                    filled: true,
                    fillColor: AppColors.surface,
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(12),
                      borderSide: BorderSide(color: AppColors.border),
                    ),
                  ),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 14),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.danger.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(_error!,
                        style: const TextStyle(
                            color: AppColors.danger,
                            fontWeight: FontWeight.w600,
                            fontSize: 13)),
                  ),
                ],
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  height: 50,
                  child: ElevatedButton(
                    onPressed: _busy ? null : _activate,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppColors.primary,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12)),
                    ),
                    child: _busy
                        ? const SizedBox(
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(
                                color: Colors.white, strokeWidth: 2.5),
                          )
                        : const Text('Activate Terminal',
                            style: TextStyle(
                                fontWeight: FontWeight.bold, fontSize: 15)),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
