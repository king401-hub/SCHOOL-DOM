import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';
import '../api/auth.dart';
import '../storage/session_store.dart';

enum AuthStatus { booting, unauthenticated, locked, authenticated }

class AuthProvider extends ChangeNotifier {
  Map<String, dynamic>? _session;
  AuthStatus _status = AuthStatus.booting;

  Map<String, dynamic>? get session => _session;
  AuthStatus get status => _status;

  String? get role => _session?['user']?['role'] as String?;
  String? get displayName =>
      (_session?['user']?['full_name'] ??
          _session?['user']?['email']) as String?;
  String? get schoolName =>
      (_session?['school']?['name'] ?? _session?['school_name']) as String?;
  String? get scopeKey =>
      (_session?['school_code'] ??
          _session?['school']?['school_code'] ??
          _session?['user']?['tenant_id'] ??
          _session?['user']?['email']) as String?;

  Future<void> boot() async {
    final stored = await getSession();
    final bio = await isBiometricEnabled();
    _session = stored;
    _status = stored == null
        ? AuthStatus.unauthenticated
        : bio
            ? AuthStatus.locked
            : AuthStatus.authenticated;
    notifyListeners();
  }

  Future<Map<String, dynamic>> signIn(Map<String, String> credentials) async {
    final result = await login(credentials);
    if (result['requiresOtp'] == true) return result;
    await saveSession(result);
    _session = result;
    _status = AuthStatus.authenticated;
    notifyListeners();
    return result;
  }

  Future<void> completeOtp(Map<String, String> payload) async {
    final result = await verifyOtp(payload);
    await saveSession(result);
    _session = result;
    _status = AuthStatus.authenticated;
    notifyListeners();
  }

  Future<bool> unlock() async {
    final auth = LocalAuthentication();
    final ok = await auth.authenticate(
      localizedReason: 'Unlock SchoolDom',
      options: const AuthenticationOptions(biometricOnly: false),
    );
    if (ok) {
      _status = AuthStatus.authenticated;
      notifyListeners();
    }
    return ok;
  }

  Future<void> enableBiometrics(bool enabled) async {
    await setBiometricEnabled(enabled);
  }

  Future<void> signOut() async {
    await clearSession();
    _session = null;
    _status = AuthStatus.unauthenticated;
    notifyListeners();
  }

  void onSessionExpired() {
    _session = null;
    _status = AuthStatus.unauthenticated;
    notifyListeners();
  }
}
