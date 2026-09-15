import 'package:flutter/services.dart';

/// Fee Reminder receipt printing (spec section 2B). Talks to the Topwise
/// CloudPOS thermal printer via a native MethodChannel bridge
/// (TopwisePrinterBridge.kt) that binds directly to the vendor's system
/// service - there is no public SDK for this hardware. This used to go
/// through the sunmi_printer_plus plugin, but that targets Sunmi hardware
/// specifically and throws on this Topwise device
/// (`lateinit property configPrinter has not been initialized`), so it can
/// never work here. This is the one place in the app that talks to the
/// printer directly; nothing else needs to change if the bridge changes.
class ReceiptPrinter {
  static const MethodChannel _channel = MethodChannel('schooldom/topwise_printer');

  static Future<bool> isAvailable() async {
    try {
      final result = await _channel.invokeMethod<bool>('isAvailable');
      return result ?? false;
    } catch (_) {
      return false;
    }
  }

  static Future<void> printFeeReminder({
    required String schoolName,
    required String studentName,
    required String studentClass,
    required String studentId,
    required String paid,
    required String outstanding,
    String? accountNumber,
    String? bankName,
  }) async {
    await _channel.invokeMethod('printFeeReminder', {
      'schoolName': schoolName,
      'studentName': studentName,
      'studentClass': studentClass,
      'studentId': studentId,
      'paid': paid,
      'outstanding': outstanding,
      'accountNumber': accountNumber ?? '',
      'bankName': bankName ?? '',
      'dateText': DateTime.now().toString().substring(0, 16),
    });
  }
}
