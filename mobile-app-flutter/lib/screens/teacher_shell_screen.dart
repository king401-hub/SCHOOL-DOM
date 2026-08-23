import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import 'messages_screen.dart';
import 'scanner_dashboard_screen.dart';
import 'settings_screen.dart';
import 'teacher_home_screen.dart';

/// Teacher's main workspace - a mobile take on the web teacher dashboard,
/// starting with the tabs that translate well to a phone: Home (overview),
/// Attendance (the existing scan/tap/history suite), Messages, and Settings.
/// Exam authoring, lesson planning, and theory grading aren't included yet -
/// those are heavier authoring tools that need a proper mobile-specific
/// design rather than a rough port of the web forms.
class TeacherShellScreen extends StatefulWidget {
  const TeacherShellScreen({super.key});

  @override
  State<TeacherShellScreen> createState() => _TeacherShellScreenState();
}

class _TeacherShellScreenState extends State<TeacherShellScreen> {
  int _index = 0;

  static const _pages = [
    TeacherHomeScreen(),
    ScannerDashboardScreen(),
    MessagesScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _index, children: _pages),
      bottomNavigationBar: NavigationBar(
        backgroundColor: AppColors.surface,
        indicatorColor: AppColors.primary.withValues(alpha: 0.15),
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        destinations: [
          NavigationDestination(
            icon: Icon(Icons.home_outlined, color: AppColors.muted),
            selectedIcon: const Icon(Icons.home, color: AppColors.primary),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.qr_code_scanner_outlined, color: AppColors.muted),
            selectedIcon: const Icon(Icons.qr_code_scanner, color: AppColors.primary),
            label: 'Attendance',
          ),
          NavigationDestination(
            icon: Icon(Icons.mail_outline, color: AppColors.muted),
            selectedIcon: const Icon(Icons.mail, color: AppColors.primary),
            label: 'Messages',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined, color: AppColors.muted),
            selectedIcon: const Icon(Icons.settings, color: AppColors.primary),
            label: 'Settings',
          ),
        ],
      ),
    );
  }
}
