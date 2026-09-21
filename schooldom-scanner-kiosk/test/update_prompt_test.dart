// When the kiosk pops the "update available" dialog up by itself.
import 'package:flutter_test/flutter_test.dart';
import 'package:schooldom_scanner_kiosk/services/app_updater.dart';

bool prompt({
  int? latestCode = 9,
  int? promptedCode,
  bool busy = false,
  bool showingResult = false,
  bool screenIsCurrent = true,
  bool dialogOpen = false,
}) =>
    shouldPromptForUpdate(
      latestCode: latestCode,
      promptedCode: promptedCode,
      busy: busy,
      showingResult: showingResult,
      screenIsCurrent: screenIsCurrent,
      dialogOpen: dialogOpen,
    );

void main() {
  test('asks about a new build the first time it is seen after launch', () {
    expect(prompt(), isTrue);
  });

  test('asks only once per build, but again when an even newer one appears', () {
    expect(prompt(promptedCode: 9), isFalse, reason: 'already asked - "Later" leaves just the icon');
    expect(prompt(latestCode: 10, promptedCode: 9), isTrue);
  });

  test('never interrupts a card being read, a scan result on screen, or another dialog', () {
    expect(prompt(busy: true), isFalse);
    expect(prompt(showingResult: true), isFalse);
    expect(prompt(dialogOpen: true), isFalse);
  });

  test('never pops up over another screen such as settings', () {
    expect(prompt(screenIsCurrent: false), isFalse);
  });

  test('does nothing when the server did not name a build', () {
    expect(prompt(latestCode: null), isFalse);
  });
}
