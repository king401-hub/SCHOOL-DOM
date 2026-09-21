// The full-screen update progress: download percentage, hand-off to Android's
// installer, and a failure with a way to retry.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:schooldom_scanner_kiosk/kiosk/update_progress_dialog.dart';

const _mb = 1024 * 1024;

void main() {
  late ValueNotifier<UpdateProgress> progress;
  late List<String> taps;

  Widget screen() => MaterialApp(
        home: UpdateProgressDialog(
          versionName: '1.4.4',
          progress: progress,
          onCancel: () => taps.add('cancel'),
          onRetry: () => taps.add('retry'),
          onOpenInstaller: () => taps.add('open-installer'),
          onClose: () => taps.add('close'),
        ),
      );

  setUp(() {
    progress = ValueNotifier(const UpdateProgress.downloading(0, 50 * _mb));
    taps = [];
  });

  tearDown(() => progress.dispose());

  testWidgets('shows the percentage, the megabytes and the version while downloading', (tester) async {
    progress.value = const UpdateProgress.downloading(25 * _mb, 50 * _mb);
    await tester.pumpWidget(screen());

    expect(find.text('Downloading update'), findsOneWidget);
    expect(find.text('SchoolGate Kiosk 1.4.4'), findsOneWidget);
    expect(find.text('50%'), findsOneWidget);
    expect(find.text('25.0 of 50.0 MB'), findsOneWidget);
    expect(tester.widget<LinearProgressIndicator>(find.byType(LinearProgressIndicator)).value, 0.5);
  });

  testWidgets('follows the download as it progresses', (tester) async {
    await tester.pumpWidget(screen());
    expect(find.text('0%'), findsOneWidget);

    progress.value = const UpdateProgress.downloading(50 * _mb, 50 * _mb);
    await tester.pump();

    expect(find.text('100%'), findsOneWidget);
    expect(find.text('50.0 of 50.0 MB'), findsOneWidget);
  });

  testWidgets('with no known total it shows megabytes so far and an indeterminate bar', (tester) async {
    progress.value = const UpdateProgress.downloading(3 * _mb, null);
    await tester.pumpWidget(screen());

    expect(find.text('3.0 MB downloaded'), findsOneWidget);
    expect(tester.widget<LinearProgressIndicator>(find.byType(LinearProgressIndicator)).value, isNull);
  });

  testWidgets('Cancel is offered while downloading', (tester) async {
    await tester.pumpWidget(screen());

    await tester.tap(find.text('Cancel'));
    expect(taps, ['cancel']);
  });

  testWidgets('after the download it tells the operator what Android will ask, and can reopen the installer',
      (tester) async {
    progress.value = const UpdateProgress.installing();
    await tester.pumpWidget(screen());

    expect(find.text('Ready to install'), findsOneWidget);
    expect(find.textContaining('tap Install'), findsOneWidget);
    expect(find.text('Cancel'), findsNothing);

    await tester.tap(find.text('Open installer again'));
    await tester.tap(find.text('Close'));
    expect(taps, ['open-installer', 'close']);
  });

  testWidgets('a failure says why and offers Try again and Close', (tester) async {
    progress.value = const UpdateProgress.failed('Could not reach the server. Check the connection and try again.');
    await tester.pumpWidget(screen());

    expect(find.text('Update failed'), findsOneWidget);
    expect(find.textContaining('Could not reach the server'), findsOneWidget);

    await tester.tap(find.text('Try again'));
    await tester.tap(find.text('Close'));
    expect(taps, ['retry', 'close']);
  });

  testWidgets('fits a small terminal screen in every state without overflowing', (tester) async {
    tester.view.physicalSize = const Size(360, 480); // devicePixelRatio 1 -> 360x480
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(screen());
    for (final state in const [
      UpdateProgress.downloading(12 * _mb, 50 * _mb),
      UpdateProgress.downloading(3 * _mb, null),
      UpdateProgress.installing(),
      UpdateProgress.failed('Could not reach the server. Check the connection and try again.'),
    ]) {
      progress.value = state;
      await tester.pump();
      expect(tester.takeException(), isNull, reason: 'overflow in ${state.phase}');
    }
  });
}
