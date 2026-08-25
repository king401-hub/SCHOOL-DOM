import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/endpoints.dart';
import '../api/scanner_endpoints.dart';
import '../auth/auth_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/branded_refresh.dart';
import 'attendance_history_screen.dart';
import 'scan_camera_screen.dart';
import 'settings_screen.dart';
import 'tap_attendance_screen.dart';

class ScannerDashboardScreen extends StatefulWidget {
  const ScannerDashboardScreen({super.key});

  @override
  State<ScannerDashboardScreen> createState() => _ScannerDashboardScreenState();
}

class _ScannerDashboardScreenState extends State<ScannerDashboardScreen> {
  bool _loading = true;
  String? _error;
  bool _checkedIn = false;
  bool _checkedOut = false;
  String? _checkInTime;
  String? _checkOutTime;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refreshStatus());
  }

  Future<void> _refreshStatus() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final auth = context.read<AuthProvider>();
    try {
      if (auth.canScanOthers) {
        final data = await myAttendanceStatusStaff(actorEmail: auth.email ?? '');
        final att = data['data'] as Map<String, dynamic>?;
        setState(() {
          _checkedIn = data['checked_in'] == true;
          _checkedOut = data['checked_out'] == true;
          _checkInTime = att?['check_in_time_formatted'] as String?;
          _checkOutTime = att?['check_out_time_formatted'] as String?;
        });
      } else if (auth.role == 'student' && auth.isNonK12School) {
        final data = await loadDashboard(auth.role);
        final metrics = (data['metrics'] ?? {}) as Map<String, dynamic>;
        setState(() {
          _checkedIn = metrics['attendance_marked_today'] == true;
          _checkedOut = false;
          _checkInTime = null;
          _checkOutTime = null;
        });
      }
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openScanner(ScanMode mode) async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => ScanCameraScreen(mode: mode)),
    );
    if (mounted) _refreshStatus();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();

    final content = <Widget>[
      AppCard(
        children: [
          Text(
            auth.displayName ?? 'User',
            style: const TextStyle(
              color: AppColors.textDark,
              fontSize: 20,
              fontWeight: FontWeight.w900,
            ),
          ),
          Text(
            (auth.role ?? '').toUpperCase(),
            style: const TextStyle(
              color: AppColors.primary,
              fontWeight: FontWeight.w800,
              fontSize: 12,
              letterSpacing: 0.6,
            ),
          ),
          if (auth.schoolName != null)
            Text(auth.schoolName!,
                style: const TextStyle(color: AppColors.mutedDark)),
        ],
      ),
      if (auth.canScanOthers ||
          (auth.role == 'student' && auth.isNonK12School)) ...[
        const SizedBox(height: 16),
        _StatusCard(
          loading: _loading,
          error: _error,
          checkedIn: _checkedIn,
          checkedOut: _checkedOut,
          checkInTime: _checkInTime,
          checkOutTime: _checkOutTime,
        ),
      ],
      const SizedBox(height: 20),
      if (auth.canScanOthers) ...[
        _ScanButton(
          icon: Icons.badge_outlined,
          label: 'Scan Student',
          onTap: () => _openScanner(ScanMode.student),
        ),
        if (auth.canTapMarkAttendance) ...[
          const SizedBox(height: 16),
          _ScanButton(
            icon: Icons.touch_app_outlined,
            label: 'Tap Attendance',
            tone: false,
            onTap: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const TapAttendanceScreen()),
            ),
          ),
        ],
        const SizedBox(height: 16),
        _ScanButton(
          icon: Icons.qr_code_scanner,
          label: 'Scan My Attendance',
          tone: false,
          onTap: () => _openScanner(ScanMode.selfStaff),
        ),
        const SizedBox(height: 16),
        Center(
          child: TextButton.icon(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const AttendanceHistoryScreen()),
            ),
            icon: Icon(Icons.history, color: AppColors.muted),
            label: Text('View Attendance History',
                style: TextStyle(color: AppColors.muted, fontWeight: FontWeight.w700)),
          ),
        ),
      ] else if (auth.role == 'student' && auth.isNonK12School) ...[
        _ScanButton(
          icon: Icons.qr_code_scanner,
          label: 'Scan My Attendance',
          onTap: () => _openScanner(ScanMode.selfStudent),
        ),
      ] else ...[
        const AppCard(children: [
          Text(
            'Attendance scanning is not available for this account.',
            style: TextStyle(color: AppColors.mutedDark),
          ),
        ]),
      ],
    ];

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
              child: _BrandHeader(
                onLogout: () => auth.signOut(),
                onSettings: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const SettingsScreen()),
                ),
              ),
            ),
            Expanded(
              child: BrandedRefresh(
                onRefresh: _refreshStatus,
                showSpinner: _loading,
                child: LayoutBuilder(
                  builder: (context, constraints) => SingleChildScrollView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    child: ConstrainedBox(
                      constraints: BoxConstraints(minHeight: constraints.maxHeight),
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: content,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _BrandHeader extends StatelessWidget {
  final VoidCallback onLogout;
  final VoidCallback onSettings;
  const _BrandHeader({required this.onLogout, required this.onSettings});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: AppColors.background,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.border),
          ),
          alignment: Alignment.center,
          child: RichText(
            text: const TextSpan(
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
              children: [
                TextSpan(text: 'S', style: TextStyle(color: Color(0xFF7DD3FC))),
                TextSpan(text: 'D', style: TextStyle(color: Color(0xFF4ADE80))),
              ],
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            'SchoolDom App',
            style: TextStyle(
              color: AppColors.text,
              fontSize: 22,
              fontWeight: FontWeight.w900,
            ),
          ),
        ),
        IconButton(
          onPressed: onSettings,
          icon: Icon(Icons.settings_outlined, color: AppColors.muted),
          tooltip: 'Settings',
        ),
        IconButton(
          onPressed: onLogout,
          icon: Icon(Icons.logout, color: AppColors.muted),
          tooltip: 'Log out',
        ),
      ],
    );
  }
}

class _StatusCard extends StatelessWidget {
  final bool loading;
  final String? error;
  final bool checkedIn;
  final bool checkedOut;
  final String? checkInTime;
  final String? checkOutTime;

  const _StatusCard({
    required this.loading,
    required this.error,
    required this.checkedIn,
    required this.checkedOut,
    required this.checkInTime,
    required this.checkOutTime,
  });

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const AppCard(children: [
        Center(
            child: Padding(
          padding: EdgeInsets.symmetric(vertical: 8),
          child: CircularProgressIndicator(color: AppColors.primary),
        )),
      ]);
    }
    if (error != null) {
      return AppCard(children: [
        Text(error!, style: const TextStyle(color: AppColors.danger)),
      ]);
    }

    final statusText = checkedOut
        ? 'Checked out'
        : checkedIn
            ? 'Checked in'
            : 'Not scanned yet today';
    final statusColor =
        checkedIn ? AppColors.success : AppColors.warning;

    return AppCard(
      children: [
        Row(
          children: [
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                  color: statusColor, shape: BoxShape.circle),
            ),
            const SizedBox(width: 8),
            Text(
              "Today's attendance",
              style: const TextStyle(
                  color: AppColors.mutedDark, fontWeight: FontWeight.w800),
            ),
          ],
        ),
        Text(
          statusText,
          style: const TextStyle(
              color: AppColors.textDark,
              fontSize: 20,
              fontWeight: FontWeight.w900),
        ),
        if (checkInTime != null)
          Text('Clocked in $checkInTime',
              style: const TextStyle(color: AppColors.mutedDark)),
        if (checkOutTime != null)
          Text('Clocked out $checkOutTime',
              style: const TextStyle(color: AppColors.mutedDark)),
      ],
    );
  }
}

class _ScanButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final bool tone;
  const _ScanButton({
    required this.icon,
    required this.label,
    required this.onTap,
    this.tone = true,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 26),
        decoration: BoxDecoration(
          color: tone ? AppColors.primary : AppColors.primary.withValues(alpha: 0.14),
          borderRadius: BorderRadius.circular(20),
          border: tone
              ? null
              : Border.all(color: AppColors.primary.withValues(alpha: 0.55), width: 1.6),
          boxShadow: [
            BoxShadow(
              color: AppColors.primary.withValues(alpha: tone ? 0.35 : 0.16),
              blurRadius: tone ? 24 : 18,
              offset: const Offset(0, 10),
            ),
          ],
        ),
        child: Column(
          children: [
            Icon(icon,
                size: 40,
                color: tone ? Colors.white : AppColors.primary),
            const SizedBox(height: 10),
            Text(
              label,
              style: TextStyle(
                color: tone ? Colors.white : AppColors.primary,
                fontSize: 16,
                fontWeight: FontWeight.w900,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
