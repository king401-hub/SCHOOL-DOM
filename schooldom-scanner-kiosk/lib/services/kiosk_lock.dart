import 'package:flutter/services.dart';

/// Screen Pinning wrapper - see MainActivity.kt. Never throws: a kiosk that
/// can't pin itself should still function as a scanner, just without the
/// extra lock-down.
class KioskLock {
  static const _channel = MethodChannel('com.schooldom.scanner_kiosk/lock_task');

  static Future<void> start() async {
    try {
      await _channel.invokeMethod('startLockTask');
    } catch (_) {}
  }

  static Future<void> stop() async {
    try {
      await _channel.invokeMethod('stopLockTask');
    } catch (_) {}
  }
}
