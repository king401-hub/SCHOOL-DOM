import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'auth/auth_provider.dart';
import 'screens/login_screen.dart';
import 'screens/lock_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/attendance_screen.dart';
import 'screens/messages_screen.dart';
import 'screens/exams_screen.dart';
import 'screens/results_screen.dart';
import 'screens/expenses_screen.dart';
import 'screens/settings_screen.dart';
import 'theme/app_theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    ChangeNotifierProvider(
      create: (_) => AuthProvider()..boot(),
      child: const SchoolDomApp(),
    ),
  );
}

class SchoolDomApp extends StatelessWidget {
  const SchoolDomApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SchoolDom',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.theme,
      home: const _Root(),
    );
  }
}

class _Root extends StatelessWidget {
  const _Root();

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    return switch (auth.status) {
      AuthStatus.booting => const Scaffold(
          backgroundColor: AppColors.background,
          body: Center(
            child: CircularProgressIndicator(color: AppColors.primary),
          ),
        ),
      AuthStatus.unauthenticated => const LoginScreen(),
      AuthStatus.locked => const LockScreen(),
      AuthStatus.authenticated => const MainShell(),
    };
  }
}

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _index = 0;

  static const _tabs = [
    _Tab(icon: Icons.home_outlined, label: 'Home', screen: DashboardScreen()),
    _Tab(icon: Icons.check_circle_outline, label: 'Attendance', screen: AttendanceScreen()),
    _Tab(icon: Icons.mail_outline, label: 'Messages', screen: MessagesScreen()),
    _Tab(icon: Icons.quiz_outlined, label: 'Exams', screen: ExamsScreen()),
    _Tab(icon: Icons.bar_chart, label: 'Results', screen: ResultsScreen()),
    _Tab(icon: Icons.receipt_long_outlined, label: 'Expenses', screen: ExpensesScreen()),
    _Tab(icon: Icons.settings_outlined, label: 'Settings', screen: SettingsScreen()),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: IndexedStack(
        index: _index,
        children: [for (final t in _tabs) t.screen],
      ),
      bottomNavigationBar: NavigationBar(
        backgroundColor: AppColors.surface,
        indicatorColor: AppColors.primary.withValues(alpha: 0.15),
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        labelBehavior: NavigationDestinationLabelBehavior.onlyShowSelected,
        destinations: [
          for (final t in _tabs)
            NavigationDestination(
              icon: Icon(t.icon, color: AppColors.muted),
              selectedIcon: Icon(t.icon, color: AppColors.primary),
              label: t.label,
            ),
        ],
      ),
    );
  }
}

class _Tab {
  final IconData icon;
  final String label;
  final Widget screen;
  const _Tab({required this.icon, required this.label, required this.screen});
}
