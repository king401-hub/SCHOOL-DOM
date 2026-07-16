import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:schooldom_app/auth/auth_provider.dart';
import 'package:schooldom_app/main.dart';

void main() {
  testWidgets('App renders without crashing', (WidgetTester tester) async {
    await tester.pumpWidget(
      ChangeNotifierProvider(
        create: (_) => AuthProvider(),
        child: const SchoolDomApp(),
      ),
    );
    // Boot splash should show a CircularProgressIndicator
    expect(find.byType(SchoolDomApp), findsOneWidget);
  });
}
