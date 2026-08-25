import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';
import 'package:provider/provider.dart';
import '../api/endpoints.dart';
import '../auth/auth_provider.dart';
import '../storage/offline_cache.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/primary_button.dart';
import 'help_screen.dart';

/// Account / Appearance / Security / Notifications / Support / Sign out
/// (spec section 8). Profile info lives in the Account card at the top
/// rather than a separate screen.
class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  Map<String, dynamic>? _school;
  bool _confirmingBiometrics = false;

  bool _prefsLoading = true;
  bool _allowPush = true;
  Map<String, bool> _eventPrefs = {
    'messages': true,
    'attendance': true,
    'assessments': true,
    'announcements': true,
  };

  static const _eventLabels = {
    'messages': 'Messages',
    'attendance': 'Attendance',
    'assessments': 'Assessments & grading',
    'announcements': 'Announcements',
  };

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadSchool());
    _loadNotificationPreferences();
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

  Future<void> _loadNotificationPreferences() async {
    try {
      final data = await loadNotificationPreferences();
      if (!mounted) return;
      final events = (data['event_preferences'] ?? {}) as Map<String, dynamic>;
      setState(() {
        _allowPush = data['allow_push'] != false;
        _eventPrefs = {for (final key in _eventLabels.keys) key: events[key] != false};
      });
    } catch (_) {
      // Keep the defaults - a screen that quietly falls back to "everything
      // on" is better than blocking Settings from opening at all.
    } finally {
      if (mounted) setState(() => _prefsLoading = false);
    }
  }

  Future<void> _setAllowPush(bool value) async {
    setState(() => _allowPush = value);
    try {
      await updateNotificationPreferences(allowPush: value);
    } catch (e) {
      if (mounted) {
        setState(() => _allowPush = !value);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not update: $e'), backgroundColor: AppColors.danger),
        );
      }
    }
  }

  Future<void> _setEventPref(String key, bool value) async {
    final previous = Map<String, bool>.from(_eventPrefs);
    setState(() => _eventPrefs[key] = value);
    try {
      await updateNotificationPreferences(eventPreferences: {key: value});
    } catch (e) {
      if (mounted) {
        setState(() => _eventPrefs = previous);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Could not update: $e'), backgroundColor: AppColors.danger),
        );
      }
    }
  }

  /// Enabling biometric unlock actually runs a real fingerprint/Face ID
  /// prompt first - it only turns the setting on once that succeeds, so a
  /// device with no biometric enrolled (or a failed scan) can't silently
  /// "enable" a lock it then can never pass.
  Future<void> _toggleBiometrics(bool enable) async {
    if (!enable) {
      await context.read<AuthProvider>().enableBiometrics(false);
      return;
    }
    setState(() => _confirmingBiometrics = true);
    try {
      final localAuth = LocalAuthentication();
      final supported = await localAuth.isDeviceSupported();
      final available = await localAuth.getAvailableBiometrics();
      if (!supported || available.isEmpty) {
        if (mounted) {
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
      if (!confirmed) return;
      if (mounted) await context.read<AuthProvider>().enableBiometrics(true);
    } catch (e) {
      if (mounted) {
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

  Future<void> _openChangePassword() async {
    await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => const _ChangePasswordSheet(),
    );
  }

  Future<void> _signOut(BuildContext context) async {
    final auth = context.read<AuthProvider>();
    await auth.signOut();
    // SettingsScreen is a pushed route (reached via Navigator.push from
    // More), so just changing auth state doesn't bring the sign-in screen
    // into view underneath - without popping back to the root, the app
    // looks "stuck" here even though signOut() already ran.
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
        title: Text('Sign out?', style: TextStyle(color: AppColors.text, fontWeight: FontWeight.w900)),
        content: Text('You will need to sign in again to use the app.', style: TextStyle(color: AppColors.muted)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: Text('Cancel', style: TextStyle(color: AppColors.muted)),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text('Sign out', style: TextStyle(color: AppColors.danger, fontWeight: FontWeight.w800)),
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
      appBar: AppBar(
        backgroundColor: AppColors.background,
        elevation: 0,
        foregroundColor: AppColors.text,
        title: const Text('Settings', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900)),
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
                children: [
                  _SectionLabel('Account'),
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
                                    errorBuilder: (_, _, _) =>
                                        _SchoolLogoFallback(name: _school?['name'] as String?),
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
                                      color: AppColors.textDark, fontSize: 16, fontWeight: FontWeight.w900),
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  auth.displayName ?? 'User',
                                  style: const TextStyle(
                                      color: AppColors.mutedDark, fontSize: 13, fontWeight: FontWeight.w700),
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
                                  color: AppColors.primary, fontWeight: FontWeight.w800, fontSize: 12, letterSpacing: 0.4),
                            ),
                          ],
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 20),
                  _SectionLabel('Appearance'),
                  AppCard(
                    children: [
                      _ToggleRow(
                        icon: isDark ? Icons.dark_mode_outlined : Icons.light_mode_outlined,
                        label: 'Dark mode',
                        value: isDark,
                        onChanged: _toggleTheme,
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  _SectionLabel('Security'),
                  AppCard(
                    children: [
                      _ToggleRow(
                        icon: Icons.fingerprint,
                        label: _confirmingBiometrics ? 'Confirming...' : 'Biometric unlock',
                        value: auth.biometricEnabled,
                        onChanged: _confirmingBiometrics ? null : _toggleBiometrics,
                      ),
                      Divider(height: 24, color: AppColors.border),
                      InkWell(
                        onTap: _openChangePassword,
                        child: Row(
                          children: [
                            Icon(Icons.lock_outline, color: AppColors.primary),
                            const SizedBox(width: 12),
                            const Expanded(
                              child: Text('Change password',
                                  style: TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w700)),
                            ),
                            Icon(Icons.chevron_right, color: AppColors.muted),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  _SectionLabel('Notifications'),
                  AppCard(
                    children: _prefsLoading
                        ? [
                            const Center(
                              child: Padding(
                                padding: EdgeInsets.symmetric(vertical: 8),
                                child: CircularProgressIndicator(color: AppColors.primary),
                              ),
                            ),
                          ]
                        : [
                            _ToggleRow(
                              icon: Icons.notifications_outlined,
                              label: 'Push notifications',
                              value: _allowPush,
                              onChanged: _setAllowPush,
                            ),
                            Divider(height: 24, color: AppColors.border),
                            for (final key in _eventLabels.keys) ...[
                              _ToggleRow(
                                icon: Icons.circle_outlined,
                                iconSize: 14,
                                label: _eventLabels[key]!,
                                value: _eventPrefs[key] ?? true,
                                onChanged: _allowPush ? (v) => _setEventPref(key, v) : null,
                                dense: true,
                              ),
                            ],
                          ],
                  ),
                  const SizedBox(height: 20),
                  _SectionLabel('Support'),
                  AppCard(
                    children: [
                      InkWell(
                        onTap: () => Navigator.of(context)
                            .push(MaterialPageRoute(builder: (_) => const HelpScreen())),
                        child: Row(
                          children: [
                            Icon(Icons.help_outline, color: AppColors.primary),
                            const SizedBox(width: 12),
                            const Expanded(
                              child: Text('Help & Support',
                                  style: TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w700)),
                            ),
                            Icon(Icons.chevron_right, color: AppColors.muted),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),
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

class _SectionLabel extends StatelessWidget {
  final String text;
  const _SectionLabel(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8, left: 4),
      child: Text(
        text.toUpperCase(),
        style: TextStyle(color: AppColors.muted, fontSize: 12, fontWeight: FontWeight.w800, letterSpacing: 0.6),
      ),
    );
  }
}

class _ToggleRow extends StatelessWidget {
  final IconData icon;
  final double iconSize;
  final String label;
  final bool value;
  final ValueChanged<bool>? onChanged;
  final bool dense;
  const _ToggleRow({
    required this.icon,
    this.iconSize = 20,
    required this.label,
    required this.value,
    required this.onChanged,
    this.dense = false,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.symmetric(vertical: dense ? 2 : 0),
      child: Row(
        children: [
          Icon(icon, size: iconSize, color: AppColors.primary),
          const SizedBox(width: 12),
          Expanded(
            child: Text(label,
                style: TextStyle(
                    color: AppColors.mutedDark, fontWeight: FontWeight.w700, fontSize: dense ? 13 : 14)),
          ),
          Switch(value: value, activeThumbColor: AppColors.primary, onChanged: onChanged),
        ],
      ),
    );
  }
}

class _ChangePasswordSheet extends StatefulWidget {
  const _ChangePasswordSheet();

  @override
  State<_ChangePasswordSheet> createState() => _ChangePasswordSheetState();
}

class _ChangePasswordSheetState extends State<_ChangePasswordSheet> {
  final _old = TextEditingController();
  final _next = TextEditingController();
  final _confirm = TextEditingController();
  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _old.dispose();
    _next.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_old.text.isEmpty || _next.text.isEmpty || _confirm.text.isEmpty) {
      setState(() => _error = 'Fill in every field.');
      return;
    }
    if (_next.text != _confirm.text) {
      setState(() => _error = 'New password and confirmation do not match.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await changePassword(
        oldPassword: _old.text,
        newPassword: _next.text,
        confirmPassword: _confirm.text,
      );
      if (mounted) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Password changed.'), backgroundColor: AppColors.success),
        );
      }
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 20),
        decoration: const BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('Change password',
                  style: TextStyle(color: AppColors.textDark, fontSize: 18, fontWeight: FontWeight.w900)),
              const SizedBox(height: 16),
              TextField(
                controller: _old,
                obscureText: true,
                style: const TextStyle(color: AppColors.textDark),
                decoration: const InputDecoration(labelText: 'Current password'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _next,
                obscureText: true,
                style: const TextStyle(color: AppColors.textDark),
                decoration: const InputDecoration(labelText: 'New password'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _confirm,
                obscureText: true,
                style: const TextStyle(color: AppColors.textDark),
                decoration: const InputDecoration(labelText: 'Confirm new password'),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: AppColors.danger)),
              ],
              const SizedBox(height: 16),
              PrimaryButton(title: 'Update password', loading: _saving, onPressed: _submit),
            ],
          ),
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
          style: TextStyle(color: AppColors.muted, fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: 0.2),
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
      decoration: BoxDecoration(color: AppColors.primarySoft, borderRadius: BorderRadius.circular(12)),
      alignment: Alignment.center,
      child: Text(initial, style: const TextStyle(color: AppColors.primary, fontSize: 22, fontWeight: FontWeight.w900)),
    );
  }
}
