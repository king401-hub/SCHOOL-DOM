import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../api/auth.dart';
import '../api/client.dart';
import '../auth/auth_provider.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _otpController = TextEditingController();

  bool _loading = false;
  String? _error;
  Map<String, dynamic>? _otpChallenge;

  Future<void> _submitLogin() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await login(_emailController.text.trim(), _passwordController.text);
      if (data['requires_otp'] == true) {
        setState(() => _otpChallenge = data);
        return;
      }
      if (!mounted) return;
      await context.read<AuthProvider>().setSession(data);
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _submitOtp() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await verifyOtp(_otpChallenge!, code: _otpController.text.trim());
      if (!mounted) return;
      await context.read<AuthProvider>().setSession(data);
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final showOtp = _otpChallenge != null;
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 360),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  'SchoolDom Mail Receiver',
                  style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                if (_error != null) ...[
                  Text(_error!, style: const TextStyle(color: Colors.red)),
                  const SizedBox(height: 12),
                ],
                if (!showOtp) ...[
                  TextField(
                    controller: _emailController,
                    decoration: const InputDecoration(labelText: 'Email'),
                    keyboardType: TextInputType.emailAddress,
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _passwordController,
                    decoration: const InputDecoration(labelText: 'Password'),
                    obscureText: true,
                    onSubmitted: (_) => _loading ? null : _submitLogin(),
                  ),
                  const SizedBox(height: 20),
                  ElevatedButton(
                    onPressed: _loading ? null : _submitLogin,
                    child: _loading
                        ? const SizedBox(
                            width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Text('Sign in'),
                  ),
                ] else ...[
                  Text(_otpChallenge!['message'] as String? ??
                      'Enter the verification code sent to your email.'),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _otpController,
                    decoration: const InputDecoration(labelText: '6-digit code'),
                    keyboardType: TextInputType.number,
                  ),
                  const SizedBox(height: 20),
                  ElevatedButton(
                    onPressed: _loading ? null : _submitOtp,
                    child: _loading
                        ? const SizedBox(
                            width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Text('Verify'),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
