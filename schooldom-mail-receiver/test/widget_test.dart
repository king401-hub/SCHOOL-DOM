import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:schooldom_mail_receiver/screens/login_screen.dart';

void main() {
  testWidgets('login screen shows the sign-in form', (WidgetTester tester) async {
    // Pumps LoginScreen directly rather than the full app: build() never
    // touches AuthProvider (only the submit handlers do), so this avoids
    // depending on the real async boot()/secure-storage read settling.
    await tester.pumpWidget(const MaterialApp(home: LoginScreen()));

    expect(find.text('SchoolDom Mail Receiver'), findsOneWidget);
    expect(find.widgetWithText(ElevatedButton, 'Sign in'), findsOneWidget);
  });
}
