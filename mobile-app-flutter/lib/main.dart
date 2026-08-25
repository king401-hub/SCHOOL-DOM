import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'auth/auth_provider.dart';
import 'scanner_kiosk/kiosk_home_screen.dart';
import 'scanner_kiosk/kiosk_store.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/attendance_screen.dart';
import 'screens/messages_screen.dart';
import 'screens/exams_screen.dart';
import 'screens/results_screen.dart';
import 'screens/expenses_screen.dart';
import 'screens/finance_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/scanner_dashboard_screen.dart';
import 'screens/admin_shell_screen.dart';
import 'screens/generic_shell_screen.dart';
import 'screens/splash_screen.dart';
import 'screens/teacher_shell_screen.dart';
import 'services/push_notifications.dart';
import 'theme/app_theme.dart';
import 'widgets/schooldom_spinner.dart';

// Roles allowed to manage school finances - mirrors backend FINANCE_ROLES
// (users/... ADMIN_ROLES | {"accountant"}) used to gate finance.admin_overview
// and finance.admin_finance_transactions.
const _financeRoles = {
  'school_admin',
  'principal',
  'super_admin',
  'school_superadmin',
  'accountant',
};

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ThemeController.instance.loadPersisted();
  await PushNotifications.initialize();
  runApp(
    ChangeNotifierProvider(
      create: (_) => AuthProvider()..boot(),
      child: const SchoolDomApp(),
    ),
  );
}

class SchoolDomApp extends StatefulWidget {
  const SchoolDomApp({super.key});

  @override
  State<SchoolDomApp> createState() => _SchoolDomAppState();
}

class _SchoolDomAppState extends State<SchoolDomApp> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // AppColors reads ThemeController.instance directly rather than through
    // Theme.of(context) (see theme/app_theme.dart), so this is what actually
    // makes the Settings light/dark toggle repaint the app live.
    ThemeController.instance.addListener(_onThemeChanged);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    ThemeController.instance.removeListener(_onThemeChanged);
    super.dispose();
  }

  void _onThemeChanged() => setState(() {});

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Re-lock the moment the app leaves the foreground (switched away from,
    // phone locked, etc.) rather than only ever checking once at cold boot -
    // otherwise biometric lock never actually re-engages for an app that's
    // merely backgrounded, only one that's fully closed and relaunched.
    if (state == AppLifecycleState.paused) {
      context.read<AuthProvider>().lockIfEnabled();
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SchoolDom App',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.theme,
      home: const _Root(),
    );
  }
}

class _Root extends StatefulWidget {
  const _Root();

  @override
  State<_Root> createState() => _RootState();
}

class _RootState extends State<_Root> {
  // Plays the brand intro for a fixed duration regardless of how quickly
  // AuthProvider.boot() itself resolves (reading local storage is normally
  // near-instant), so the splash always gets to run rather than only
  // flashing on a slow cold start.
  bool _showSplash = true;

  // Checked before anything else - a provisioned scanner terminal (spec
  // section 9: "permanently logged in... closing/reopening the app should
  // not require login") boots straight to Ready to Scan on every launch,
  // bypassing the normal splash/login/dashboard flow entirely rather than
  // ever showing them and then redirecting away.
  bool? _kioskProvisioned;

  @override
  void initState() {
    super.initState();
    KioskStore.isEnabled().then((enabled) {
      if (mounted) setState(() => _kioskProvisioned = enabled);
    });
    Future.delayed(const Duration(milliseconds: 1900), () {
      if (mounted) setState(() => _showSplash = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_kioskProvisioned == null) {
      return const Scaffold(backgroundColor: Color(0xFF0B1220), body: SizedBox.shrink());
    }
    if (_kioskProvisioned == true) {
      return const KioskHomeScreen();
    }
    if (_showSplash) return const SplashScreen();
    final auth = context.watch<AuthProvider>();
    return switch (auth.status) {
      AuthStatus.booting => Scaffold(
          backgroundColor: AppColors.background,
          body: const Center(
            child: SchoolDomSpinner(size: 64),
          ),
        ),
      // Both a fresh sign-in and returning to an already-signed-in device
      // land on the same screen now - LoginScreen itself checks
      // auth.status to decide whether to offer biometric/face unlock (with
      // password as the fallback) or the full email/password/school-code
      // form. LockScreen is kept below, unused, rather than deleted.
      AuthStatus.unauthenticated => const LoginScreen(),
      AuthStatus.locked => const LoginScreen(),
      AuthStatus.authenticated => _homeForRole(auth),
    };
  }
}

/// Teachers get the full purpose-built workspace (Home/Attendance/Messages/
/// Settings); single-school admins (school_admin/principal/super_admin) get
/// the full Dashboard/Students/Finance/Academics/More workspace; a
/// school_superadmin (proprietor, manages a SchoolGroup of many schools) and
/// self-scanning Non-K12 students keep the scanner-first experience (the new
/// admin dashboard's endpoints deliberately 403 a proprietor - see
/// AuthProvider.isSingleSchoolAdmin); every other role (parent, K12 student,
/// staff) gets a generic-but-real workspace instead of a dead end, until
/// their own dashboards are built out. MainShell (the original multi-tab
/// workspace, pre-dating both of these) is kept below, unused, in case its
/// navigation is wanted back later.
Widget _homeForRole(AuthProvider auth) {
  if (auth.isTeacher) return const TeacherShellScreen();
  if (auth.isSingleSchoolAdmin) return const AdminShellScreen();
  if (auth.isAdmin) return const ScannerDashboardScreen();
  if (auth.role == 'student' && auth.isNonK12School) return const ScannerDashboardScreen();
  return const GenericShellScreen();
}

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _index = 0;

  static const _baseTabs = [
    _Tab(icon: Icons.home_outlined, label: 'Home', screen: DashboardScreen()),
    _Tab(icon: Icons.check_circle_outline, label: 'Attendance', screen: AttendanceScreen()),
    _Tab(icon: Icons.mail_outline, label: 'Messages', screen: MessagesScreen()),
    _Tab(icon: Icons.quiz_outlined, label: 'Exams', screen: ExamsScreen()),
    _Tab(icon: Icons.bar_chart, label: 'Results', screen: ResultsScreen()),
  ];

  static const _financeTabs = [
    _Tab(icon: Icons.receipt_long_outlined, label: 'Expenses', screen: ExpensesScreen()),
    _Tab(icon: Icons.account_balance_wallet_outlined, label: 'Finance', screen: FinanceScreen()),
  ];

  static const _settingsTab =
      _Tab(icon: Icons.settings_outlined, label: 'Settings', screen: SettingsScreen());

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final canSeeFinance = _financeRoles.contains(auth.role);
    final tabs = [
      ..._baseTabs,
      if (canSeeFinance) ..._financeTabs,
      _settingsTab,
    ];
    if (_index >= tabs.length) _index = 0;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: IndexedStack(
        index: _index,
        children: [for (final t in tabs) t.screen],
      ),
      bottomNavigationBar: NavigationBar(
        backgroundColor: AppColors.surface,
        indicatorColor: AppColors.primary.withValues(alpha: 0.15),
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        labelBehavior: NavigationDestinationLabelBehavior.onlyShowSelected,
        destinations: [
          for (final t in tabs)
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
