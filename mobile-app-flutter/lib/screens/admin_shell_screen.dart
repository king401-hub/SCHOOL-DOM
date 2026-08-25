import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/offline_banner.dart';
import 'academics_screen.dart';
import 'admin_dashboard_screen.dart';
import 'admin_more_screen.dart';
import 'admin_students_screen.dart';
import 'finance_screen.dart';

/// Admin's main workspace - Dashboard | Students | Finance | Academics |
/// More, per the admin app spec's Main Navigation section. Replaces the
/// previous no-tabs routing straight to ScannerDashboardScreen; the scanner
/// itself is still reachable (Attendance lives under More, with Scan
/// Student/My Attendance as its primary actions).
class AdminShellScreen extends StatefulWidget {
  const AdminShellScreen({super.key});

  @override
  State<AdminShellScreen> createState() => _AdminShellScreenState();
}

class _AdminShellScreenState extends State<AdminShellScreen> {
  int _index = 0;

  static const _pages = [
    AdminDashboardScreen(),
    AdminStudentsScreen(),
    FinanceScreen(),
    AcademicsScreen(),
    AdminMoreScreen(),
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
            icon: Icon(Icons.dashboard_outlined, color: AppColors.muted),
            selectedIcon: const Icon(Icons.dashboard, color: AppColors.primary),
            label: 'Dashboard',
          ),
          NavigationDestination(
            icon: Icon(Icons.groups_outlined, color: AppColors.muted),
            selectedIcon: const Icon(Icons.groups, color: AppColors.primary),
            label: 'Students',
          ),
          NavigationDestination(
            icon: Icon(Icons.account_balance_wallet_outlined, color: AppColors.muted),
            selectedIcon: const Icon(Icons.account_balance_wallet, color: AppColors.primary),
            label: 'Finance',
          ),
          NavigationDestination(
            icon: Icon(Icons.quiz_outlined, color: AppColors.muted),
            selectedIcon: const Icon(Icons.quiz, color: AppColors.primary),
            label: 'Academics',
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
