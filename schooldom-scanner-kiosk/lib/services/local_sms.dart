import 'package:flutter/services.dart';

/// Sends an SMS directly over the kiosk terminal's own SIM (LocalSmsBridge.kt)
/// - used only as an offline fallback when a scan can't reach the backend at
/// all, so a parent still gets the gate-attendance text even without
/// internet. See kiosk_home_screen.dart's _handleScan offline branch.
class LocalSms {
  static const MethodChannel _channel = MethodChannel('schooldom/local_sms');

  /// True only when the phone itself reported the whole message as sent - not
  /// merely that the request was accepted. Anything else (no permission, no
  /// SIM, no airtime, no signal, no report in time) is false, so the caller
  /// can leave the parent's text for the server to send once the scan syncs.
  ///
  /// [timeout] is a backstop; the native side already gives up on its own.
  static Future<bool> send(
    String phone,
    String message, {
    Duration timeout = const Duration(seconds: 15),
  }) async {
    try {
      final result = await _channel.invokeMethod<bool>('sendSms', {
        'phone': phone,
        'message': message,
      }).timeout(timeout);
      return result ?? false;
    } catch (_) {
      return false;
    }
  }
}
