import 'package:flutter/material.dart';
import '../api/admin_endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/branded_refresh.dart';
import '../widgets/primary_button.dart';
import '../widgets/skeleton.dart';
import 'attendance_history_screen.dart';
import 'scan_camera_screen.dart';

/// Admin app's Attendance tab - Scan Student/Scan Staff as the primary
/// actions (reusing the existing ScanCameraScreen), plus a school-wide
/// Present/Absent/Late/Not-Marked summary for today from the new
/// users/app_views.py `admin_attendance_summary` endpoint.
class AdminAttendanceScreen extends StatefulWidget {
  const AdminAttendanceScreen({super.key});

  @override
  State<AdminAttendanceScreen> createState() => _AdminAttendanceScreenState();
}

class _AdminAttendanceScreenState extends State<AdminAttendanceScreen> {
  Map<String, dynamic>? _data;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await loadAdminAttendanceSummary();
      setState(() => _data = data);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        foregroundColor: AppColors.text,
        title: const Text('Attendance', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900)),
      ),
      body: SafeArea(
        child: _loading && _data == null
            ? const SkeletonList()
            : BrandedRefresh(
                onRefresh: _load,
                showSpinner: _loading && _data != null,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                  children: [
                    Text('Scan QR Code',
                        style: TextStyle(color: AppColors.text, fontSize: 16, fontWeight: FontWeight.w900)),
                    const SizedBox(height: 4),
                    Text('Mark attendance by scanning a student or staff ID.',
                        style: TextStyle(color: AppColors.muted, fontSize: 13)),
                    const SizedBox(height: 14),
                    Row(
                      children: [
                        Expanded(
                          child: _ScanButton(
                            label: 'Scan Student',
                            icon: Icons.badge_outlined,
                            colors: const [AppColors.brandGreen, Color(0xFF16A34A)],
                            onTap: () => Navigator.of(context)
                                .push(MaterialPageRoute(builder: (_) => const ScanCameraScreen(mode: ScanMode.student))),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          // There's no existing flow for an admin to scan
                          // ANOTHER staff member's ID (only the shared gate
                          // QR for one's own attendance exists server-side),
                          // so this stays honestly labeled rather than
                          // implying a "scan any staff ID" feature that
                          // doesn't exist yet.
                          child: _ScanButton(
                            label: 'My Attendance',
                            icon: Icons.badge,
                            colors: const [AppColors.brandBlue, Color(0xFF1D4ED8)],
                            onTap: () => Navigator.of(context)
                                .push(MaterialPageRoute(builder: (_) => const ScanCameraScreen(mode: ScanMode.selfStaff))),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 24),
                    Row(
                      children: [
                        Text("Today's Summary",
                            style: TextStyle(color: AppColors.text, fontSize: 16, fontWeight: FontWeight.w900)),
                        const Spacer(),
                        Material(
                          color: Colors.transparent,
                          child: InkWell(
                            borderRadius: BorderRadius.circular(10),
                            onTap: () => Navigator.of(context)
                                .push(MaterialPageRoute(builder: (_) => const AttendanceHistoryScreen())),
                            child: Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text('Reports',
                                      style: TextStyle(
                                          color: AppColors.primary, fontSize: 12, fontWeight: FontWeight.w800)),
                                  const SizedBox(width: 2),
                                  Icon(Icons.chevron_right, size: 16, color: AppColors.primary),
                                ],
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    if (_error != null && _data == null)
                      Column(
                        children: [
                          Text(_error!, style: const TextStyle(color: AppColors.danger)),
                          const SizedBox(height: 8),
                          SizedBox(width: 160, child: PrimaryButton(title: 'Retry', onPressed: _load)),
                        ],
                      )
                    else ...[
                      Row(
                        children: [
                          Expanded(
                            child: _SummaryTile(
                                label: 'Present', value: '${_data?['present'] ?? 0}', color: AppColors.success),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: _SummaryTile(
                                label: 'Absent', value: '${_data?['absent'] ?? 0}', color: AppColors.danger),
                          ),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Expanded(
                            child: _SummaryTile(
                                label: 'Late', value: '${_data?['late'] ?? 0}', color: AppColors.warning),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: _SummaryTile(
                                label: 'Not Marked', value: '${_data?['not_marked'] ?? 0}', color: AppColors.muted),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
      ),
    );
  }
}

class _ScanButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final List<Color> colors;
  final VoidCallback onTap;
  const _ScanButton({required this.label, required this.icon, required this.colors, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 18),
          decoration: BoxDecoration(
            gradient: LinearGradient(colors: colors),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            children: [
              Icon(icon, color: Colors.white, size: 26),
              const SizedBox(height: 8),
              Text(label, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
            ],
          ),
        ),
      ),
    );
  }
}

class _SummaryTile extends StatelessWidget {
  final String label;
  final String value;
  final Color color;
  const _SummaryTile({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return AppCard(
      elevated: true,
      children: [
        Text(label, style: const TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w800, fontSize: 12)),
        Text(value, style: TextStyle(color: color, fontSize: 26, fontWeight: FontWeight.w900)),
      ],
    );
  }
}
