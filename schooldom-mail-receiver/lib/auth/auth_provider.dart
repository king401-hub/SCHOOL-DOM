import 'package:flutter/material.dart';
import '../storage/session_store.dart';

enum AuthStatus { booting, unauthenticated, authenticated }

class AuthProvider extends ChangeNotifier {
  Map<String, dynamic>? _session;
  AuthStatus _status = AuthStatus.booting;

  Map<String, dynamic>? get session => _session;
  AuthStatus get status => _status;
  String? get displayName =>
      (_session?['user']?['full_name'] ?? _session?['user']?['email']) as String?;

  Future<void> boot() async {
    _session = await getSession();
    _status = _session == null ? AuthStatus.unauthenticated : AuthStatus.authenticated;
    notifyListeners();
  }

  Future<void> setSession(Map<String, dynamic> session) async {
    await saveSession(session);
    _session = session;
    _status = AuthStatus.authenticated;
    notifyListeners();
  }

  Future<void> signOut() async {
    await clearSession();
    _session = null;
    _status = AuthStatus.unauthenticated;
    notifyListeners();
  }
}
