import 'package:sunmi_printer_plus/sunmi_printer_plus.dart';

/// Fee Reminder receipt printing (spec section 2B). Targets the built-in
/// printer on Sunmi-family Android POS terminals - the most common
/// "normal POS terminal with a printer" hardware for this kind of gate
/// device. If the actual terminal turns out to be a different vendor,
/// this is the one place to swap the implementation; nothing else in the
/// app talks to the printer directly.
///
/// No explicit "bind"/"init"/transaction step is needed with this package
/// version - SunmiPrinter.printText etc. talk to the native printer
/// service directly, and SunmiTextStyle carries alignment per call rather
/// than a separate global setAlignment().
class ReceiptPrinter {
  static Future<bool> isAvailable() async {
    try {
      final status = await SunmiConfig.getStatus();
      return status != null;
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
  }) async {
    await SunmiPrinter.printText(
      schoolName,
      style: SunmiTextStyle(bold: true, fontSize: 32, align: SunmiPrintAlign.CENTER),
    );
    await SunmiPrinter.printText(
      'Fee Reminder',
      style: SunmiTextStyle(bold: true, align: SunmiPrintAlign.CENTER),
    );
    await SunmiPrinter.lineWrap(1);
    await SunmiPrinter.printText('Name: $studentName', style: SunmiTextStyle(align: SunmiPrintAlign.LEFT));
    await SunmiPrinter.printText('Class: $studentClass', style: SunmiTextStyle(align: SunmiPrintAlign.LEFT));
    await SunmiPrinter.printText('Student ID: $studentId', style: SunmiTextStyle(align: SunmiPrintAlign.LEFT));
    await SunmiPrinter.lineWrap(1);
    await SunmiPrinter.printText('Fees Paid: $paid', style: SunmiTextStyle(align: SunmiPrintAlign.LEFT));
    await SunmiPrinter.printText('Outstanding: $outstanding', style: SunmiTextStyle(align: SunmiPrintAlign.LEFT));
    await SunmiPrinter.lineWrap(1);
    await SunmiPrinter.printText(
      DateTime.now().toString().substring(0, 16),
      style: SunmiTextStyle(fontSize: 20, align: SunmiPrintAlign.CENTER),
    );
    await SunmiPrinter.lineWrap(3);
    await SunmiPrinter.cutPaper();
  }
}
