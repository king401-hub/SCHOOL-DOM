import 'dart:async';
import 'dart:io';

import 'package:http/http.dart' as http;

/// Downloads a new kiosk APK, reporting progress as it goes.
///
/// The old update code did `http.get(...)`: nothing visible for the whole
/// download (minutes on a slow SIM/Wi-Fi) and the entire ~50 MB body buffered
/// in memory. This streams straight to disk instead.
class AppUpdater {
  /// Streams [url] to [destination], calling [onProgress] with the bytes
  /// received so far and the total size ([total] is null when the server
  /// doesn't say).
  ///
  /// The caller owns [client]: closing it aborts the download (that is how the
  /// Cancel button works). Any failure - a bad status, a dropped connection, no
  /// data for [idleTimeout], a body shorter than announced - throws, and the
  /// partial file is deleted so a truncated APK can never be handed to the
  /// installer.
  static Future<File> download({
    required http.Client client,
    required Uri url,
    required File destination,
    required void Function(int received, int? total) onProgress,
    Duration idleTimeout = const Duration(seconds: 30),
  }) async {
    IOSink? sink;
    try {
      final response = await client.send(http.Request('GET', url)).timeout(idleTimeout);
      if (response.statusCode != 200) {
        throw HttpException('Download failed (HTTP ${response.statusCode}).');
      }
      final total = response.contentLength;
      var received = 0;
      onProgress(0, total);

      sink = destination.openWrite();
      // The timeout applies between chunks, so a slow but moving download is
      // fine and only a stalled one gives up.
      await for (final chunk in response.stream.timeout(idleTimeout)) {
        sink.add(chunk);
        received += chunk.length;
        onProgress(received, total);
      }
      await sink.flush();
      await sink.close();
      sink = null;

      if (total != null && received != total) {
        throw HttpException('Download incomplete ($received of $total bytes).');
      }
      return destination;
    } catch (_) {
      try {
        await sink?.close();
      } catch (_) {
        // The sink is already broken; the file is removed below anyway.
      }
      if (await destination.exists()) {
        await destination.delete();
      }
      rethrow;
    }
  }
}

/// Whether to pop the "update available" dialog up now, unprompted.
///
/// The kiosk asks once per launch (and again if an even newer build appears),
/// never while a card is being read or a scan result is on screen, and never
/// over another screen such as the settings page. Declining ("Later") leaves
/// the update icon in the top bar to reopen it.
bool shouldPromptForUpdate({
  required int? latestCode,
  required int? promptedCode,
  required bool busy,
  required bool showingResult,
  required bool screenIsCurrent,
  required bool dialogOpen,
}) {
  if (latestCode == null) return false;
  if (promptedCode == latestCode) return false;
  if (busy || showingResult || dialogOpen) return false;
  return screenIsCurrent;
}

/// Human wording for a failed update, without the raw exception text.
String describeUpdateError(Object error) {
  if (error is SocketException || error is http.ClientException || error is TimeoutException) {
    return 'Could not reach the server. Check the connection and try again.';
  }
  if (error is HttpException) return error.message;
  return error.toString().replaceFirst('Exception: ', '');
}
