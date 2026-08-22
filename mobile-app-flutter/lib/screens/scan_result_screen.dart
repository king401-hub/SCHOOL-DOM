import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../auth/auth_provider.dart';
import '../theme/app_theme.dart';
import 'attendance_history_screen.dart';

class ScanResultScreen extends StatefulWidget {
  final bool success;
  final String message;

  /// Either the `attendance` map (id-card / student-qr flows) or the `data`
  /// map (shared gate-QR staff flow) from the scan response - shapes differ
  /// between endpoints, so fields are looked up defensively below.
  final Map<String, dynamic>? attendance;

  /// True only after a "Scan Student" scan (admin/teacher) - offers a way to
  /// jump straight back into scanning (the next scan of the same card clocks
  /// the student out, per the backend's own clock-in/out inference) and a
  /// link to the attendance History page, instead of just a generic "Done".
  final bool showStudentActions;

  const ScanResultScreen({
    super.key,
    required this.success,
    required this.message,
    this.attendance,
    this.showStudentActions = false,
  });

  @override
  State<ScanResultScreen> createState() => _ScanResultScreenState();
}

class _ScanResultScreenState extends State<ScanResultScreen> {
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer(const Duration(seconds: 4), () {
      if (mounted) Navigator.of(context).pop();
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  String? _pick(List<String> keys) {
    final a = widget.attendance;
    if (a == null) return null;
    for (final k in keys) {
      final v = a[k];
      if (v != null && v.toString().isNotEmpty) return v.toString();
    }
    final details = a['teacher_details'] as Map<String, dynamic>?;
    if (details != null) {
      for (final k in keys) {
        final v = details[k];
        if (v != null && v.toString().isNotEmpty) return v.toString();
      }
    }
    return null;
  }

  String _formatTime(String? iso) {
    if (iso == null || iso.isEmpty) return '';
    final parsed = DateTime.tryParse(iso);
    if (parsed == null) return iso;
    final local = parsed.toLocal();
    final hour = local.hour % 12 == 0 ? 12 : local.hour % 12;
    final minute = local.minute.toString().padLeft(2, '0');
    final period = local.hour >= 12 ? 'PM' : 'AM';
    return '$hour:$minute $period';
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.read<AuthProvider>();
    final name = _pick(['student_name', 'full_name', 'name']) ?? auth.displayName ?? 'You';
    final roleLabel = (_pick(['class_name']) != null)
        ? 'Student · ${_pick(['class_name'])}'
        : (_pick(['status']) ?? auth.role ?? '').toString().toUpperCase();
    final time = _formatTime(
      _pick(['check_out_time', 'clock_out_at']) ??
          _pick(['check_in_time', 'clock_in_at']),
    );

    final color = widget.success ? AppColors.success : AppColors.danger;
    final icon = widget.success ? Icons.check_circle : Icons.error;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, color: color, size: 96),
                const SizedBox(height: 24),
                if (widget.success) ...[
                  Text(
                    name,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: AppColors.text,
                      fontSize: 26,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                  if (roleLabel.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(
                      roleLabel,
                      style: const TextStyle(
                        color: AppColors.primary,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ],
                  if (time.isNotEmpty) ...[
                    const SizedBox(height: 14),
                    Text(
                      time,
                      style: TextStyle(
                        color: AppColors.muted,
                        fontSize: 32,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                  ],
                ],
                const SizedBox(height: 20),
                Text(
                  widget.message,
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.muted, fontSize: 15),
                ),
                const SizedBox(height: 40),
                if (widget.showStudentActions) ...[
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: () {
                        _timer?.cancel();
                        Navigator.of(context).pop();
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
                      icon: const Icon(Icons.qr_code_scanner),
                      label: const Text('Scan to Clock Out',
                          style: TextStyle(fontWeight: FontWeight.w800)),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextButton.icon(
                    onPressed: () {
                      _timer?.cancel();
                      Navigator.of(context).push(
                        MaterialPageRoute(
                            builder: (_) => const AttendanceHistoryScreen()),
                      );
                    },
                    icon: Icon(Icons.history, color: AppColors.muted),
                    label: Text('View History',
                        style: TextStyle(
                            color: AppColors.muted, fontWeight: FontWeight.w700)),
                  ),
                ] else
                  TextButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Done',
                        style: TextStyle(
                            color: AppColors.primary, fontWeight: FontWeight.w800)),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
