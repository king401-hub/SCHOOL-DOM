import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import 'admin_announcements_screen.dart';
import 'admin_attendance_screen.dart';
import 'admin_staff_screen.dart';
import 'help_screen.dart';
import 'settings_screen.dart';

/// Admin app's More tab - secondary features per the spec ("Put secondary
/// features under More: Staff, Attendance, Exams/CBT, Announcements,
/// Reports, Settings, School Profile"). Exams/CBT already has its own
/// primary "Academics" nav tab; Reports/School Profile fold into Settings
/// and Attendance's own "Reports" link rather than duplicating entries.
class AdminMoreScreen extends StatelessWidget {
  const AdminMoreScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
          children: [
            Text('More', style: TextStyle(color: AppColors.text, fontSize: 22, fontWeight: FontWeight.w900)),
            const SizedBox(height: 16),
            Container(
              width: double.infinity,
              decoration: BoxDecoration(
                color: AppColors.card,
                borderRadius: BorderRadius.circular(16),
                boxShadow: const [
                  BoxShadow(color: Color(0x0C000000), blurRadius: 12, offset: Offset(0, 2)),
                ],
              ),
              child: Column(
                children: [
                  _MoreTile(
                    icon: Icons.badge_outlined,
                    title: 'Staff',
                    onTap: () =>
                        Navigator.of(context).push(MaterialPageRoute(builder: (_) => const AdminStaffScreen())),
                  ),
                  Divider(height: 1, color: AppColors.border),
                  _MoreTile(
                    icon: Icons.qr_code_scanner_outlined,
                    title: 'Attendance',
                    onTap: () => Navigator.of(context)
                        .push(MaterialPageRoute(builder: (_) => const AdminAttendanceScreen())),
                  ),
                  Divider(height: 1, color: AppColors.border),
                  _MoreTile(
                    icon: Icons.campaign_outlined,
                    title: 'Announcements',
                    onTap: () => Navigator.of(context)
                        .push(MaterialPageRoute(builder: (_) => const AdminAnnouncementsScreen())),
                  ),
                  Divider(height: 1, color: AppColors.border),
                  _MoreTile(
                    icon: Icons.settings_outlined,
                    title: 'Settings',
                    onTap: () =>
                        Navigator.of(context).push(MaterialPageRoute(builder: (_) => const SettingsScreen())),
                  ),
                  Divider(height: 1, color: AppColors.border),
                  _MoreTile(
                    icon: Icons.help_outline,
                    title: 'Help & Support',
                    onTap: () =>
                        Navigator.of(context).push(MaterialPageRoute(builder: (_) => const HelpScreen())),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MoreTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final VoidCallback onTap;
  const _MoreTile({required this.icon, required this.title, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        child: Row(
          children: [
            Icon(icon, color: AppColors.primary, size: 20),
            const SizedBox(width: 14),
            Expanded(
              child: Text(title, style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w800)),
            ),
            Icon(Icons.chevron_right, color: AppColors.muted),
          ],
        ),
      ),
    );
  }
}
