import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../auth/auth_provider.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/primary_button.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _schoolCode = TextEditingController();
  final _otpCode = TextEditingController();

  bool _loading = false;
  Map<String, dynamic>? _otpChallenge;

  Future<void> _submit() async {
    setState(() => _loading = true);
    try {
      final auth = context.read<AuthProvider>();
      if (_otpChallenge != null) {
        await auth.completeOtp({
          'email': _otpChallenge!['email'] as String,
          'code': _otpCode.text.trim(),
          'challenge': _otpChallenge!['challenge'] as String? ?? '',
        });
      } else {
        final result = await auth.signIn({
          'email': _email.text.trim(),
          'password': _password.text,
          'school_code': _schoolCode.text.trim(),
        });
        if (result['requiresOtp'] == true) {
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

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _schoolCode.dispose();
    _otpCode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 48),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'SchoolDom App',
                style: TextStyle(
                  color: AppColors.primary,
                  fontWeight: FontWeight.w900,
                  fontSize: 14,
                  letterSpacing: 1.5,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Native school workspace',
                style: TextStyle(
                  color: AppColors.text,
                  fontSize: 32,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Use your existing SchoolDom account and school code.',
                style: TextStyle(color: AppColors.muted, fontSize: 16),
              ),
              const SizedBox(height: 40),
              AppCard(
                children: _otpChallenge != null
                    ? _buildOtpFields()
                    : _buildSignInFields(),
              ),
            ],
          ),
        ),
      ),
    );
  }

  List<Widget> _buildSignInFields() => [
        const Text(
          'Sign in',
          style: TextStyle(
              color: AppColors.textDark,
              fontSize: 22,
              fontWeight: FontWeight.w900),
        ),
        TextField(
          controller: _email,
          keyboardType: TextInputType.emailAddress,
          autocorrect: false,
          textCapitalization: TextCapitalization.none,
          style: const TextStyle(color: AppColors.textDark),
          decoration:
              const InputDecoration(hintText: 'Email address'),
        ),
        TextField(
          controller: _password,
          obscureText: true,
          style: const TextStyle(color: AppColors.textDark),
          decoration: const InputDecoration(hintText: 'Password'),
        ),
        TextField(
          controller: _schoolCode,
          autocorrect: false,
          textCapitalization: TextCapitalization.none,
          style: const TextStyle(color: AppColors.textDark),
          decoration: const InputDecoration(hintText: 'School code'),
        ),
        PrimaryButton(
          title: _loading ? 'Please wait...' : 'Sign in',
          onPressed: _submit,
          loading: _loading,
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
          'Enter the 6-digit code sent to ${_otpChallenge!['email']}.',
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
