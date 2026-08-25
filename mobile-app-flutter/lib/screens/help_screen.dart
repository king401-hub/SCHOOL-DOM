import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';

/// Support screen (spec section 8) - a real mailto contact channel plus a
/// few static tips. Deliberately has no "Help Center" web link since no such
/// page exists yet - inventing one would just be a dead end for the teacher.
class HelpScreen extends StatelessWidget {
  const HelpScreen({super.key});

  Future<void> _openMail(BuildContext context, {required String subject}) async {
    final uri = Uri(
      scheme: 'mailto',
      path: 'support@schooldom.academy',
      query: 'subject=${Uri.encodeComponent(subject)}',
    );
    final launched = await launchUrl(uri);
    if (!launched && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No email app found on this device.')),
      );
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
        title: const Text('Help & Support', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900)),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
          children: [
            AppCard(
              children: [
                _HelpTile(
                  icon: Icons.mail_outline,
                  title: 'Contact SchoolDom',
                  subtitle: 'support@schooldom.academy',
                  onTap: () => _openMail(context, subject: 'SchoolDom App - Support request'),
                ),
                Divider(height: 24, color: AppColors.border),
                _HelpTile(
                  icon: Icons.bug_report_outlined,
                  title: 'Report a problem',
                  subtitle: 'Tell us what went wrong',
                  onTap: () => _openMail(context, subject: 'SchoolDom App - Problem report'),
                ),
              ],
            ),
            const SizedBox(height: 16),
            AppCard(
              children: [
                Row(
                  children: [
                    Icon(Icons.lightbulb_outline, size: 18, color: AppColors.primary),
                    const SizedBox(width: 8),
                    const Text('Tips',
                        style: TextStyle(color: AppColors.textDark, fontSize: 16, fontWeight: FontWeight.w900)),
                  ],
                ),
                const SizedBox(height: 4),
                _TipRow(text: 'Long-press a message to edit or delete it.'),
                _TipRow(text: 'Pin important notes so they stay at the top.'),
                _TipRow(text: 'Turn on biometric unlock in Settings for faster, more secure sign-in.'),
                _TipRow(text: 'You can still mark attendance while offline - it syncs automatically once you\'re back online.'),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _HelpTile extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  const _HelpTile({required this.icon, required this.title, required this.subtitle, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(color: AppColors.primarySoft, borderRadius: BorderRadius.circular(12)),
            alignment: Alignment.center,
            child: Icon(icon, color: AppColors.primary, size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w800)),
                Text(subtitle, style: const TextStyle(color: AppColors.mutedDark, fontSize: 12)),
              ],
            ),
          ),
          Icon(Icons.chevron_right, color: AppColors.muted),
        ],
      ),
    );
  }
}

class _TipRow extends StatelessWidget {
  final String text;
  const _TipRow({required this.text});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 5),
            child: Icon(Icons.circle, size: 5, color: AppColors.muted),
          ),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: const TextStyle(color: AppColors.mutedDark, fontSize: 13))),
        ],
      ),
    );
  }
}
