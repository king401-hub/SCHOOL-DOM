import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';
import 'package:provider/provider.dart';
import '../api/endpoints.dart';
import '../auth/auth_provider.dart';
import '../storage/offline_cache.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/primary_button.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  Map<String, dynamic>? _school;
  bool _confirmingBiometrics = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadSchool());
  }

  Future<void> _loadSchool() async {
    final auth = context.read<AuthProvider>();
    try {
      final data = await loadDashboard(auth.role);
      final school = data['school'] as Map<String, dynamic>?;
      if (school != null && mounted) setState(() => _school = school);
    } catch (_) {
      final cached = await readCache('dashboard', auth.scopeKey);
      final school =
          (cached?['data'] as Map<String, dynamic>?)?['school'] as Map<String, dynamic>?;
      if (school != null && mounted) setState(() => _school = school);
    }
  }

  /// Enabling biometric unlock actually runs a real fingerprint/Face ID
  /// prompt first - it only turns the setting on once that succeeds, so a
  /// device with no biometric enrolled (or a failed scan) can't silently
  /// "enable" a lock it then can never pass.
  Future<void> _enableBiometrics(BuildContext context) async {
    setState(() => _confirmingBiometrics = true);
    try {
      final localAuth = LocalAuthentication();
      final supported = await localAuth.isDeviceSupported();
      final available = await localAuth.getAvailableBiometrics();
      if (!supported || available.isEmpty) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('No fingerprint or face unlock is set up on this device.'),
              backgroundColor: AppColors.danger,
            ),
          );
        }
        return;
      }
      final confirmed = await localAuth.authenticate(
        localizedReason: 'Confirm your fingerprint or face to enable biometric unlock',
        options: const AuthenticationOptions(biometricOnly: false),
      );
      if (!confirmed) {
        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Biometric confirmation cancelled.')),
          );
        }
        return;
      }
      if (context.mounted) {
        await context.read<AuthProvider>().enableBiometrics(true);
      }
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Biometric unlock enabled.'),
            backgroundColor: AppColors.success,
          ),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.toString()), backgroundColor: AppColors.danger),
        );
      }
    } finally {
      if (mounted) setState(() => _confirmingBiometrics = false);
    }
  }

  Future<void> _toggleTheme(bool dark) async {
    await ThemeController.instance.setDark(dark);
    if (mounted) setState(() {});
  }

  Future<void> _signOut(BuildContext context) async {
    final auth = context.read<AuthProvider>();
    await auth.signOut();
    // SettingsScreen is a pushed route (reached via Navigator.push from the
    // dashboard), so just changing auth state doesn't bring the sign-in
    // screen into view underneath - without popping back to the root, the
    // app looks "stuck" here even though signOut() already ran.
    if (context.mounted) {
      Navigator.of(context).popUntil((route) => route.isFirst);
    }
  }

  /// Sign out sits right below other tappable content with the same bright
  /// danger color as a normal action, so a confirmation guards against an
  /// accidental tap immediately signing the device out.
  Future<void> _confirmSignOut(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: AppColors.surface,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text('Sign out?',
            style: TextStyle(color: AppColors.text, fontWeight: FontWeight.w900)),
        content: Text('You will need to sign in again to use the scanner.',
            style: TextStyle(color: AppColors.muted)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: Text('Cancel', style: TextStyle(color: AppColors.muted)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Sign out',
                style: TextStyle(color: AppColors.danger, fontWeight: FontWeight.w800)),
          ),
        ],
      ),
    );
    if (confirmed == true && context.mounted) {
      await _signOut(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final isDark = ThemeController.instance.isDark;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 24, 20, 16),
                children: [
                  Text(
                    'Settings',
                    style: TextStyle(
                        color: AppColors.text,
                        fontSize: 22,
                        fontWeight: FontWeight.w900),
                  ),
                  const SizedBox(height: 16),
                  AppCard(
                    children: [
                      Row(
                        children: [
                          ClipRRect(
                            borderRadius: BorderRadius.circular(12),
                            child: (_school?['logo'] as String?)?.isNotEmpty == true
                                ? Image.network(
                                    _school!['logo'] as String,
                                    width: 52,
                                    height: 52,
                                    fit: BoxFit.cover,
                                    errorBuilder: (_, _, _) => _SchoolLogoFallback(
                                      name: _school?['name'] as String?,
                                    ),
                                  )
                                : _SchoolLogoFallback(name: _school?['name'] as String?),
                          ),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  (_school?['name'] as String?) ?? auth.schoolName ?? 'SchoolDom',
                                  style: const TextStyle(
                                      color: AppColors.textDark,
                                      fontSize: 16,
                                      fontWeight: FontWeight.w900),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  auth.displayName ?? 'User',
                                  style: const TextStyle(
                                      color: AppColors.mutedDark,
                                      fontSize: 13,
                                      fontWeight: FontWeight.w700),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      if (auth.role != null) ...[
                        Divider(height: 24, color: AppColors.border),
                        Row(
                          children: [
                            Icon(Icons.badge_outlined, size: 16, color: AppColors.muted),
                            const SizedBox(width: 8),
                            Text(
                              auth.role!.toUpperCase(),
                              style: const TextStyle(
                                  color: AppColors.primary,
                                  fontWeight: FontWeight.w800,
                                  fontSize: 12,
                                  letterSpacing: 0.4),
                            ),
                          ],
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 16),
                  AppCard(
                    children: [
                      Row(
                        children: [
                          Icon(Icons.palette_outlined, size: 18, color: AppColors.primary),
                          const SizedBox(width: 8),
                          const Text(
                            'Appearance',
                            style: TextStyle(
                                color: AppColors.textDark,
                                fontSize: 16,
                                fontWeight: FontWeight.w900),
                          ),
                        ],
                      ),
                      Row(
                        children: [
                          Icon(
                            isDark ? Icons.dark_mode_outlined : Icons.light_mode_outlined,
                            color: AppColors.primary,
                          ),
                          const SizedBox(width: 12),
                          const Expanded(
                            child: Text('Dark mode',
                                style: TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w700)),
                          ),
                          Switch(
                            value: isDark,
                            activeThumbColor: AppColors.primary,
                            onChanged: _toggleTheme,
                          ),
                        ],
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  AppCard(
                    children: [
                      Row(
                        children: [
                          Icon(Icons.security_outlined, size: 18, color: AppColors.primary),
                          const SizedBox(width: 8),
                          const Text(
                            'Device services',
                            style: TextStyle(
                                color: AppColors.textDark,
                                fontSize: 16,
                                fontWeight: FontWeight.w900),
                          ),
                        ],
                      ),
                      PrimaryButton(
                        title: _confirmingBiometrics ? 'Confirming...' : 'Enable biometric unlock',
                        icon: Icons.fingerprint,
                        loading: _confirmingBiometrics,
                        onPressed: () => _enableBiometrics(context),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  PrimaryButton(
                    title: 'Sign out',
                    tone: ButtonTone.danger,
                    icon: Icons.logout,
                    onPressed: () => _confirmSignOut(context),
                  ),
                ],
              ),
            ),
            const _SettingsFooter(),
          ],
        ),
      ),
    );
  }
}

class _SettingsFooter extends StatelessWidget {
  const _SettingsFooter();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      decoration: BoxDecoration(
        color: AppColors.surfaceSoft,
        border: Border(top: BorderSide(color: AppColors.border)),
      ),
      child: Center(
        child: Text(
          'Powered by Xcel Technologies',
          style: TextStyle(
              color: AppColors.muted,
              fontSize: 12,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.2),
        ),
      ),
    );
  }
}

class _SchoolLogoFallback extends StatelessWidget {
  final String? name;
  const _SchoolLogoFallback({this.name});

  @override
  Widget build(BuildContext context) {
    final initial = (name?.trim().isNotEmpty == true) ? name!.trim()[0].toUpperCase() : 'S';
    return Container(
      width: 52,
      height: 52,
      decoration: BoxDecoration(
        color: AppColors.primarySoft,
        borderRadius: BorderRadius.circular(12),
      ),
      alignment: Alignment.center,
      child: Text(
        initial,
        style: const TextStyle(
          color: AppColors.primary,
          fontSize: 22,
          fontWeight: FontWeight.w900,
        ),
      ),
    );
  }
}
