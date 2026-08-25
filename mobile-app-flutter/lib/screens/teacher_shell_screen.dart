import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/offline_banner.dart';
import 'messages_screen.dart';
import 'more_screen.dart';
import 'scanner_dashboard_screen.dart';
import 'teacher_home_screen.dart';

/// Teacher's main workspace - a mobile take on the web teacher dashboard.
/// Home | Attendance | Messages | More, with Settings/Timetable/Lesson
/// Plans/Notes/Help folded into More rather than crowding the primary row
/// (spec section 4). Exam authoring and theory grading aren't included yet -
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
    MoreScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          const OfflineBanner(),
          Expanded(child: IndexedStack(index: _index, children: _pages)),
        ],
      ),
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
            icon: Icon(Icons.grid_view_outlined, color: AppColors.muted),
            selectedIcon: const Icon(Icons.grid_view, color: AppColors.primary),
            label: 'More',
          ),
        ],
      ),
    );
  }
}
