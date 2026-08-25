import 'package:flutter/material.dart';
import 'package:local_auth/local_auth.dart';
import '../api/auth.dart';
import '../services/push_notifications.dart';
import '../storage/session_store.dart';

enum AuthStatus { booting, unauthenticated, locked, authenticated }

class AuthProvider extends ChangeNotifier {
  Map<String, dynamic>? _session;
  AuthStatus _status = AuthStatus.booting;
  bool _biometricEnabled = false;

  Map<String, dynamic>? get session => _session;
  AuthStatus get status => _status;

  String? get role => _session?['user']?['role'] as String?;
  String? get email => _session?['user']?['email'] as String?;
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

  // Mirrors backend ADMIN_ROLES (users/app_views.py + attendance/views.py).
  static const _adminRoles = {
    'school_admin',
    'principal',
    'super_admin',
    'school_superadmin',
  };
  bool get biometricEnabled => _biometricEnabled;
  bool get isAdmin => _adminRoles.contains(role);
  bool get isTeacher => role == 'teacher';
  // SchoolDom Scanner: admins and teachers can scan students; everyone else
  // (e.g. a Non-K12 student) may only scan their own attendance.
  bool get canScanOthers => isAdmin || isTeacher;
  bool get isNonK12School =>
      (_session?['school']?['school_type'] as String?) == 'non_k12';

  // Tap Attendance (teacher_class_students/teacher_mark_student_attendance)
  // deliberately excludes school_superadmin server-side - those views assume
  // a single request.user.tenant, which a proprietor (owns a SchoolGroup of
  // many schools, not one school) never has. K12 only - Non-K12 is QR-only.
  bool get canTapMarkAttendance =>
      !isNonK12School &&
      (isTeacher || {'school_admin', 'principal', 'super_admin'}.contains(role));

  Future<void> boot() async {
    final stored = await getSession();
    final bio = await isBiometricEnabled();
    _session = stored;
    _biometricEnabled = bio;
    _status = stored == null
        ? AuthStatus.unauthenticated
        : bio
            ? AuthStatus.locked
            : AuthStatus.authenticated;
    notifyListeners();
    if (_status == AuthStatus.authenticated) PushNotifications.registerToken();
  }

  /// Called whenever the app is backgrounded (see WidgetsBindingObserver in
  /// main.dart). Without this, biometric lock only ever applied once, at
  /// cold boot - leaving the app fully unlocked forever if it was just
  /// backgrounded and resumed rather than fully closed and reopened.
  void lockIfEnabled() {
    if (_biometricEnabled && _status == AuthStatus.authenticated) {
      _status = AuthStatus.locked;
      notifyListeners();
    }
  }

  Future<Map<String, dynamic>> signIn(Map<String, String> credentials) async {
    final result = await login(credentials);
    if (result['requires_otp'] == true) return result;
    await saveSession(result);
    _session = result;
    _status = AuthStatus.authenticated;
    notifyListeners();
    PushNotifications.registerToken();
    return result;
  }

  /// `otpChallenge` is the login() response that carried requires_otp - it
  /// already has the email/challenge verifyOtp needs, so only the code the
  /// admin typed has to be passed in separately.
  Future<void> completeOtp(Map<String, dynamic> otpChallenge, String code) async {
    final result = await verifyOtp(otpChallenge, code: code);
    await saveSession(result);
    _session = result;
    _status = AuthStatus.authenticated;
    notifyListeners();
    PushNotifications.registerToken();
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
      PushNotifications.registerToken();
    }
    return ok;
  }

  Future<void> enableBiometrics(bool enabled) async {
    await setBiometricEnabled(enabled);
    _biometricEnabled = enabled;
    notifyListeners();
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
