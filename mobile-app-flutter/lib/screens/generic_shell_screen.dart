import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/offline_banner.dart';
import 'dashboard_screen.dart';
import 'messages_screen.dart';
import 'settings_screen.dart';

/// Fallback workspace for roles that don't have a purpose-built dashboard
/// yet (parent, K12 student, staff/accountant) - a real Home + Messages +
/// Settings instead of a dead-end "not available" message, while the
/// teacher-specific experience (TeacherShellScreen) gets built out first.
class GenericShellScreen extends StatefulWidget {
  const GenericShellScreen({super.key});

  @override
  State<GenericShellScreen> createState() => _GenericShellScreenState();
}

class _GenericShellScreenState extends State<GenericShellScreen> {
  int _index = 0;

  static const _pages = [
    DashboardScreen(),
    MessagesScreen(),
    SettingsScreen(),
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
