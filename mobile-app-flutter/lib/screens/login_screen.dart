import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';
import 'package:provider/provider.dart';
import '../api/auth.dart';
import '../auth/auth_provider.dart';
import '../scanner_kiosk/kiosk_provisioning_screen.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/primary_button.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen>
    with SingleTickerProviderStateMixin {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _schoolCode = TextEditingController();
  final _otpCode = TextEditingController();

  bool _loading = false;
  bool _obscurePassword = true;
  Map<String, dynamic>? _otpChallenge;

  bool _biometricAvailable = false;
  BiometricType? _biometricKind;

  late final AnimationController _entrance;
  late final Animation<double> _logoFade;
  late final Animation<Offset> _logoSlide;
  late final Animation<double> _formFade;
  late final Animation<Offset> _formSlide;

  @override
  void initState() {
    super.initState();
    _entrance = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
    _logoFade = CurvedAnimation(
      parent: _entrance,
      curve: const Interval(0.0, 0.6, curve: Curves.easeOut),
    );
    _logoSlide = Tween<Offset>(
      begin: const Offset(0, -0.15),
      end: Offset.zero,
    ).animate(_logoFade);
    _formFade = CurvedAnimation(
      parent: _entrance,
      curve: const Interval(0.3, 1.0, curve: Curves.easeOut),
    );
    _formSlide = Tween<Offset>(
      begin: const Offset(0, 0.12),
      end: Offset.zero,
    ).animate(_formFade);
    _entrance.forward();
    _checkBiometricAndMaybeUnlock();
  }

  /// Detects what the device actually supports (fingerprint, face, or
  /// neither) so the "returning user" screen can offer whichever applies -
  /// falling back silently to the password field when there's no biometric
  /// hardware/enrollment at all, rather than showing a dead button.
  Future<void> _checkBiometricAndMaybeUnlock() async {
    final auth = context.read<AuthProvider>();
    if (auth.status != AuthStatus.locked) return;
    try {
      final localAuth = LocalAuthentication();
      final supported = await localAuth.isDeviceSupported();
      final available = await localAuth.getAvailableBiometrics();
      if (!mounted) return;
      setState(() {
        _biometricAvailable = supported && available.isNotEmpty;
        _biometricKind = available.contains(BiometricType.face)
            ? BiometricType.face
            : available.isNotEmpty
                ? available.first
                : null;
      });
      if (_biometricAvailable) _attemptBiometricUnlock();
    } catch (_) {
      // Can't query biometric capability - just leave the password field
      // below as the only option, no error needed for this.
    }
  }

  Future<void> _attemptBiometricUnlock() async {
    await context.read<AuthProvider>().unlock();
    // A failed/cancelled prompt just leaves the password field below as the
    // fallback - no error banner needed, the user can simply type it.
  }

  String get _biometricLabel => switch (_biometricKind) {
        BiometricType.face => 'Unlock with Face ID',
        BiometricType.fingerprint => 'Unlock with Fingerprint',
        _ => 'Unlock with Biometrics',
      };

  IconData get _biometricIcon => switch (_biometricKind) {
        BiometricType.face => Icons.face,
        BiometricType.fingerprint => Icons.fingerprint,
        _ => Icons.security,
      };

  /// Re-authenticates a returning user with just their password - the email
  /// and school code are already known from the stored session, so this is
  /// the "type your password instead of biometrics" fallback, not a full
  /// from-scratch sign-in. Still a real call to the normal login endpoint,
  /// so it actually verifies the password rather than just trusting the UI.
  Future<void> _submitUnlockPassword() async {
    setState(() => _loading = true);
    try {
      final auth = context.read<AuthProvider>();
      final storedEmail = (auth.session?['user']?['email'] ?? '') as String;
      final storedSchoolCode = (auth.session?['school_code'] ??
          auth.session?['school']?['school_code'] ??
          '') as String;
      final result = await auth.signIn({
        'email': storedEmail,
        'password': _password.text,
        'school_code': storedSchoolCode,
      });
      if (result['requires_otp'] == true) {
        setState(() => _otpChallenge = result);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.toString()), backgroundColor: AppColors.danger),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _submit() async {
    setState(() => _loading = true);
    try {
      final auth = context.read<AuthProvider>();
      if (_otpChallenge != null) {
        await auth.completeOtp(_otpChallenge!, _otpCode.text.trim());
      } else {
        final result = await auth.signIn({
          'email': _email.text.trim(),
          'password': _password.text,
          'school_code': _schoolCode.text.trim(),
        });
        if (result['requires_otp'] == true) {
          setState(() => _otpChallenge = result);
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(e.toString()), backgroundColor: AppColors.danger),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _showSchoolCodeHelp() {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.card,
        title: const Text('What is a school code?',
            style: TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
        content: const Text(
          "Your school code identifies your school on SchoolDom. It's provided by "
          'your school administrator - check your welcome email, or ask your admin '
          "if you're not sure.",
          style: TextStyle(color: AppColors.mutedDark),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Got it'),
          ),
        ],
      ),
    );
  }

  void _showContactAdminHelp() {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        backgroundColor: AppColors.card,
        title: const Text('Need help signing in?',
            style: TextStyle(color: AppColors.textDark, fontWeight: FontWeight.w900)),
        content: const Text(
          'Contact your school administrator to confirm your email, school code, '
          'or account status. They can also reset your access if it was disabled.',
          style: TextStyle(color: AppColors.mutedDark),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Future<void> _openForgotPassword() async {
    final resetEmail = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => _ForgotPasswordSheet(initialEmail: _email.text.trim()),
    );
    if (resetEmail != null && mounted) {
      setState(() => _email.text = resetEmail);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Password reset. Sign in with your new password.'),
          backgroundColor: AppColors.success,
        ),
      );
    }
  }

  @override
  void dispose() {
    _entrance.dispose();
    _email.dispose();
    _password.dispose();
    _schoolCode.dispose();
    _otpCode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final returning = auth.status == AuthStatus.locked;

    return Scaffold(
      backgroundColor: AppColors.background,
      body: DecoratedBox(
        decoration: BoxDecoration(
          gradient: RadialGradient(
            center: const Alignment(0, -0.55),
            radius: 1.1,
            colors: [const Color(0xFF16234A), AppColors.background],
            stops: const [0.0, 1.0],
          ),
        ),
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 40),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                FadeTransition(
                  opacity: _logoFade,
                  child: SlideTransition(
                    position: _logoSlide,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const _BrandMark(),
                        const SizedBox(height: 16),
                        const Text(
                          'SchoolDom App',
                          style: TextStyle(
                            color: AppColors.primary,
                            fontWeight: FontWeight.w900,
                            fontSize: 14,
                            letterSpacing: 1.5,
                          ),
                        ),
                        const SizedBox(height: 4),
                        ShaderMask(
                          shaderCallback: (bounds) => const LinearGradient(
                            colors: [Color(0xFFEAF2FF), AppColors.primary],
                          ).createShader(bounds),
                          child: const Text(
                            'Welcome back',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 32,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          returning
                              ? 'Sign back in to continue on this device.'
                              : 'Use your existing SchoolDom account and school code.',
                          style: TextStyle(color: AppColors.muted, fontSize: 16),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 32),
                FadeTransition(
                  opacity: _formFade,
                  child: SlideTransition(
                    position: _formSlide,
                    child: AppCard(
                      elevated: true,
                      borderRadius: 24,
                      children: _otpChallenge != null
                          ? _buildOtpFields()
                          : returning
                              ? _buildUnlockFields(auth)
                              : _buildSignInFields(),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  List<Widget> _buildUnlockFields(AuthProvider auth) {
    final initial = (auth.displayName?.trim().isNotEmpty == true)
        ? auth.displayName!.trim()[0].toUpperCase()
        : 'U';
    return [
      Row(
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: AppColors.primarySoft,
              borderRadius: BorderRadius.circular(12),
            ),
            alignment: Alignment.center,
            child: Text(
              initial,
              style: const TextStyle(
                  color: AppColors.primary, fontWeight: FontWeight.w900, fontSize: 18),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  auth.displayName ?? 'Welcome back',
                  style: const TextStyle(
                      color: AppColors.textDark, fontWeight: FontWeight.w900, fontSize: 16),
                ),
                const Text('Not you? Sign out below.',
                    style: TextStyle(color: AppColors.mutedDark, fontSize: 12)),
              ],
            ),
          ),
        ],
      ),
      const SizedBox(height: 20),
      if (_biometricAvailable) ...[
        SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: _attemptBiometricUnlock,
            style: ElevatedButton.styleFrom(
              backgroundColor: AppColors.primary,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 16),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            icon: Icon(_biometricIcon),
            label: Text(_biometricLabel, style: const TextStyle(fontWeight: FontWeight.w800)),
          ),
        ),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(child: Divider(color: AppColors.border)),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              child: Text('or', style: TextStyle(color: AppColors.muted, fontSize: 12)),
            ),
            Expanded(child: Divider(color: AppColors.border)),
          ],
        ),
        const SizedBox(height: 16),
      ],
      _LoginField(
        controller: _password,
        hintText: 'Password',
        icon: Icons.lock_outline,
        obscureText: _obscurePassword,
        suffixIcon: IconButton(
          icon: Icon(
            _obscurePassword ? Icons.visibility_outlined : Icons.visibility_off_outlined,
            color: AppColors.mutedDark,
          ),
          onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
        ),
      ),
      const SizedBox(height: 6),
      PrimaryButton(
        title: _loading ? 'Please wait...' : 'Unlock',
        onPressed: _submitUnlockPassword,
        loading: _loading,
      ),
      const SizedBox(height: 12),
      Center(
        child: TextButton(
          onPressed: () => context.read<AuthProvider>().signOut(),
          child: Text('Not you? Sign out',
              style: TextStyle(color: AppColors.muted, fontWeight: FontWeight.w700)),
        ),
      ),
    ];
  }

  List<Widget> _buildSignInFields() => [
        const Text(
          'Sign in',
          style: TextStyle(
              color: AppColors.textDark,
              fontSize: 22,
              fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 4),
        _LoginField(
          controller: _email,
          hintText: 'Email address',
          icon: Icons.mail_outline,
          keyboardType: TextInputType.emailAddress,
        ),
        _LoginField(
          controller: _password,
          hintText: 'Password',
          icon: Icons.lock_outline,
          obscureText: _obscurePassword,
          suffixIcon: IconButton(
            icon: Icon(
              _obscurePassword ? Icons.visibility_outlined : Icons.visibility_off_outlined,
              color: AppColors.mutedDark,
            ),
            onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
          ),
        ),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton(
            onPressed: _openForgotPassword,
            style: TextButton.styleFrom(
              padding: EdgeInsets.zero,
              minimumSize: const Size(0, 32),
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            ),
            child: const Text('Forgot password?',
                style: TextStyle(color: AppColors.primary, fontWeight: FontWeight.w700)),
          ),
        ),
        _LoginField(
          controller: _schoolCode,
          hintText: 'School code',
          icon: Icons.apartment_outlined,
          suffixIcon: IconButton(
            icon: const Icon(Icons.info_outline, color: AppColors.mutedDark, size: 20),
            onPressed: _showSchoolCodeHelp,
          ),
        ),
        const SizedBox(height: 6),
        PrimaryButton(
          title: _loading ? 'Please wait...' : 'Sign in',
          onPressed: _submit,
          loading: _loading,
        ),
        const SizedBox(height: 4),
        Center(
          child: TextButton(
            onPressed: _showContactAdminHelp,
            child: const Text(
              'Need help signing in? Contact your school admin',
              style: TextStyle(color: AppColors.mutedDark, fontWeight: FontWeight.w600),
              textAlign: TextAlign.center,
            ),
          ),
        ),
        Center(
          child: TextButton(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const KioskProvisioningScreen()),
            ),
            child: Text(
              'Set up as Scanner Terminal',
              style: TextStyle(color: AppColors.mutedDark.withValues(alpha: 0.55), fontSize: 12),
              textAlign: TextAlign.center,
            ),
          ),
        ),
      ];

  List<Widget> _buildOtpFields() => [
        const Text(
          'Admin verification',
          style: TextStyle(
              color: AppColors.textDark,
              fontSize: 22,
              fontWeight: FontWeight.w900),
        ),
        Text(
          'Enter the 6-digit code sent to ${_otpChallenge!['user']?['email'] ?? 'your email'}.',
          style: const TextStyle(color: AppColors.mutedDark),
        ),
        TextField(
          controller: _otpCode,
          keyboardType: TextInputType.number,
          maxLength: 6,
          style: const TextStyle(
              color: AppColors.textDark,
              fontSize: 24,
              letterSpacing: 8,
              fontWeight: FontWeight.bold),
          decoration:
              const InputDecoration(hintText: '000000', counterText: ''),
        ),
        PrimaryButton(
          title: _loading ? 'Verifying...' : 'Verify and continue',
          onPressed: _submit,
          loading: _loading,
        ),
        TextButton(
          onPressed: () => setState(() => _otpChallenge = null),
          child: const Text('Back to sign in'),
        ),
      ];
}

/// Small "SD" monogram matching the app icon and Scanner Dashboard header,
/// used here so the sign-in screen carries the same brand mark.
class _BrandMark extends StatelessWidget {
  const _BrandMark();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 52,
      height: 52,
      decoration: BoxDecoration(
        color: AppColors.surfaceSoft,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.border),
      ),
      alignment: Alignment.center,
      child: RichText(
        text: const TextSpan(
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
          children: [
            TextSpan(text: 'S', style: TextStyle(color: Color(0xFF7DD3FC))),
            TextSpan(text: 'D', style: TextStyle(color: Color(0xFF4ADE80))),
          ],
        ),
      ),
    );
  }
}

/// A labeled input used by the sign-in card - gives every field (email,
/// password, school code) the same leading icon + focus treatment instead of
/// only some fields looking "filled in".
class _LoginField extends StatelessWidget {
  final TextEditingController controller;
  final String hintText;
  final IconData icon;
  final bool obscureText;
  final Widget? suffixIcon;
  final TextInputType? keyboardType;

  const _LoginField({
    required this.controller,
    required this.hintText,
    required this.icon,
    this.obscureText = false,
    this.suffixIcon,
    this.keyboardType,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: TextField(
        controller: controller,
        obscureText: obscureText,
        keyboardType: keyboardType,
        autocorrect: false,
        textCapitalization: TextCapitalization.none,
        style: const TextStyle(color: AppColors.textDark),
        decoration: InputDecoration(
          hintText: hintText,
          prefixIcon: Icon(icon, color: AppColors.mutedDark, size: 20),
          suffixIcon: suffixIcon,
        ),
      ),
    );
  }
}

/// Two-step "forgot password" flow (request code -> confirm new password),
/// backed by the existing /api/auth/password-reset/ endpoints.
class _ForgotPasswordSheet extends StatefulWidget {
  final String initialEmail;
  const _ForgotPasswordSheet({required this.initialEmail});

  @override
  State<_ForgotPasswordSheet> createState() => _ForgotPasswordSheetState();
}

class _ForgotPasswordSheetState extends State<_ForgotPasswordSheet> {
  late final TextEditingController _email =
      TextEditingController(text: widget.initialEmail);
  final _code = TextEditingController();
  final _newPassword = TextEditingController();
  final _confirmPassword = TextEditingController();

  bool _loading = false;
  bool _obscure = true;
  String? _challenge;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _code.dispose();
    _newPassword.dispose();
    _confirmPassword.dispose();
    super.dispose();
  }

  Future<void> _requestCode() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await requestPasswordReset(_email.text.trim());
      setState(() => _challenge = result['otp_challenge'] as String?);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _confirm() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await confirmPasswordReset(
        email: _email.text.trim(),
        code: _code.text.trim(),
        challenge: _challenge ?? '',
        password: _newPassword.text,
        confirmPassword: _confirmPassword.text,
      );
      if (mounted) Navigator.of(context).pop(_email.text.trim());
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final inCodeStep = _challenge != null;
    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
      ),
      child: Container(
        padding: const EdgeInsets.fromLTRB(24, 24, 24, 32),
        decoration: const BoxDecoration(
          color: AppColors.card,
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 40,
                height: 4,
                margin: const EdgeInsets.only(bottom: 20),
                decoration: BoxDecoration(
                  color: AppColors.border,
                  borderRadius: BorderRadius.circular(2),
                ),
              ),
            ),
            Text(
              inCodeStep ? 'Enter reset code' : 'Reset your password',
              style: const TextStyle(
                  color: AppColors.textDark, fontSize: 20, fontWeight: FontWeight.w900),
            ),
            const SizedBox(height: 6),
            Text(
              inCodeStep
                  ? 'Enter the 6-digit code sent to ${_email.text.trim()} and choose a new password.'
                  : "Enter your account email and we'll send a 6-digit reset code.",
              style: const TextStyle(color: AppColors.mutedDark),
            ),
            const SizedBox(height: 20),
            if (_error != null) ...[
              Text(_error!, style: const TextStyle(color: AppColors.danger)),
              const SizedBox(height: 12),
            ],
            if (!inCodeStep) ...[
              _LoginField(
                controller: _email,
                hintText: 'Email address',
                icon: Icons.mail_outline,
                keyboardType: TextInputType.emailAddress,
              ),
              const SizedBox(height: 16),
              PrimaryButton(
                title: _loading ? 'Sending...' : 'Send reset code',
                onPressed: _requestCode,
                loading: _loading,
              ),
            ] else ...[
              _LoginField(
                controller: _code,
                hintText: '6-digit code',
                icon: Icons.password_outlined,
                keyboardType: TextInputType.number,
              ),
              _LoginField(
                controller: _newPassword,
                hintText: 'New password',
                icon: Icons.lock_outline,
                obscureText: _obscure,
                suffixIcon: IconButton(
                  icon: Icon(
                    _obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                    color: AppColors.mutedDark,
                  ),
                  onPressed: () => setState(() => _obscure = !_obscure),
                ),
              ),
              _LoginField(
                controller: _confirmPassword,
                hintText: 'Confirm new password',
                icon: Icons.lock_outline,
                obscureText: _obscure,
              ),
              const SizedBox(height: 16),
              PrimaryButton(
                title: _loading ? 'Resetting...' : 'Reset password',
                onPressed: _confirm,
                loading: _loading,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
