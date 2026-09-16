import 'package:flutter/services.dart';

/// Sends an SMS directly over the kiosk terminal's own SIM (LocalSmsBridge.kt)
/// - used only as an offline fallback when a scan can't reach the backend at
/// all, so a parent still gets the gate-attendance text even without
/// internet. See kiosk_home_screen.dart's _handleScan offline branch.
class LocalSms {
  static const MethodChannel _channel = MethodChannel('schooldom/local_sms');

  static Future<bool> send(String phone, String message) async {
    try {
      final result = await _channel.invokeMethod<bool>('sendSms', {
        'phone': phone,
        'message': message,
      });
      return result ?? false;
    } catch (_) {
      return false;
    }
  }
}
