import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../auth/auth_provider.dart';
import '../theme/app_theme.dart';
import 'help_screen.dart';
import 'lesson_plans_screen.dart';
import 'notes_screen.dart';
import 'settings_screen.dart';
import 'timetable_screen.dart';

/// Fourth bottom-nav tab (spec section 4) - houses the tools that don't need
/// their own place in the primary Home|Attendance|Messages row: Timetable,
/// Lesson Plans, Notes, Settings, Help. Profile lives inside Settings rather
/// than duplicating a second profile screen here.
class MoreScreen extends StatelessWidget {
  const MoreScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final planLabel = auth.isNonK12School ? 'Course Outline' : 'Lesson Plans';

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
                    icon: Icons.calendar_month_outlined,
                    title: 'Timetable',
                    onTap: () => Navigator.of(context)
                        .push(MaterialPageRoute(builder: (_) => const TimetableScreen())),
                  ),
                  Divider(height: 1, color: AppColors.border),
                  _MoreTile(
                    icon: Icons.menu_book_outlined,
                    title: planLabel,
                    onTap: () => Navigator.of(context)
                        .push(MaterialPageRoute(builder: (_) => const LessonPlansScreen())),
                  ),
                  Divider(height: 1, color: AppColors.border),
                  _MoreTile(
                    icon: Icons.sticky_note_2_outlined,
                    title: 'Notes',
                    onTap: () =>
                        Navigator.of(context).push(MaterialPageRoute(builder: (_) => const NotesScreen())),
                  ),
                  Divider(height: 1, color: AppColors.border),
                  _MoreTile(
                    icon: Icons.settings_outlined,
                    title: 'Settings',
                    onTap: () => Navigator.of(context)
                        .push(MaterialPageRoute(builder: (_) => const SettingsScreen())),
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
