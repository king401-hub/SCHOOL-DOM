import 'package:flutter/material.dart';
import 'kiosk/kiosk_home_screen.dart';
import 'kiosk/kiosk_provisioning_screen.dart';
import 'kiosk/kiosk_store.dart';
import 'theme/app_theme.dart';

void main() {
  runApp(const ScannerKioskApp());
}

/// This app has exactly two states, ever: unprovisioned (show the license
/// key entry screen) or provisioned (show the scanner terminal). There is
/// no navigation menu, no settings, no sign-out - see kiosk_store.dart and
/// kiosk_home_screen.dart for why.
class ScannerKioskApp extends StatelessWidget {
  const ScannerKioskApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SchoolDom Attendance Scanner',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorSchemeSeed: AppColors.primary,
        scaffoldBackgroundColor: AppColors.background,
      ),
      onGenerateRoute: (_) =>
          MaterialPageRoute(builder: (_) => const _KioskRoot()),
    );
  }
}

class _KioskRoot extends StatefulWidget {
  const _KioskRoot();

  @override
  State<_KioskRoot> createState() => _KioskRootState();
}

class _KioskRootState extends State<_KioskRoot> {
  bool? _provisioned;

  @override
  void initState() {
    super.initState();
    KioskStore.isEnabled().then((enabled) {
      if (mounted) setState(() => _provisioned = enabled);
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_provisioned == null) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }
    return _provisioned!
        ? const KioskHomeScreen()
        : const KioskProvisioningScreen();
  }
}
