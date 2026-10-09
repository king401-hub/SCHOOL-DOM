import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'auth/auth_provider.dart';
import 'screens/inbox_screen.dart';
import 'screens/login_screen.dart';

void main() {
  runApp(const MailReceiverApp());
}

class MailReceiverApp extends StatelessWidget {
  const MailReceiverApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => AuthProvider()..boot(),
      child: MaterialApp(
        title: 'SchoolDom Mail Receiver',
        theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
        home: const _RootScreen(),
      ),
    );
  }
}

class _RootScreen extends StatelessWidget {
  const _RootScreen();

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    switch (auth.status) {
      case AuthStatus.booting:
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      case AuthStatus.unauthenticated:
        return const LoginScreen();
      case AuthStatus.authenticated:
        return const InboxScreen();
    }
  }
}
