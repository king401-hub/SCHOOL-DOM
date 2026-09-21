import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';

import '../theme/app_theme.dart';

enum UpdatePhase { downloading, installing, failed }

/// What the update screen is showing right now.
@immutable
class UpdateProgress {
  final UpdatePhase phase;
  final int received;
  final int? total;
  final String? error;

  const UpdateProgress.downloading(this.received, this.total)
      : phase = UpdatePhase.downloading,
        error = null;
  const UpdateProgress.installing()
      : phase = UpdatePhase.installing,
        received = 0,
        total = null,
        error = null;
  const UpdateProgress.failed(this.error)
      : phase = UpdatePhase.failed,
        received = 0,
        total = null;

  /// 0..1, or null when the total size isn't known.
  double? get fraction {
    final t = total;
    if (t == null || t <= 0) return null;
    return (received / t).clamp(0.0, 1.0);
  }
}

String _megabytes(int bytes) => (bytes / (1024 * 1024)).toStringAsFixed(1);

/// Full-screen update progress: download percentage, then the hand-off to
/// Android's installer. Shown non-dismissibly (back does nothing) while the
/// download runs; the only ways out are Cancel, Close, or the install
/// completing. While installing, "Open installer again" reopens the already
/// downloaded file - the first install on a terminal sends the user off to
/// Android's "allow installs from this app" switch, and coming back from there
/// shouldn't mean downloading 50 MB a second time.
class UpdateProgressDialog extends StatelessWidget {
  final String versionName;
  final ValueListenable<UpdateProgress> progress;
  final VoidCallback onCancel;
  final VoidCallback onRetry;
  final VoidCallback onOpenInstaller;
  final VoidCallback onClose;

  const UpdateProgressDialog({
    super.key,
    required this.versionName,
    required this.progress,
    required this.onCancel,
    required this.onRetry,
    required this.onOpenInstaller,
    required this.onClose,
  });

  static const _panel = Color(0xFF15213A);

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      child: Dialog.fullscreen(
        backgroundColor: _panel,
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: ValueListenableBuilder<UpdateProgress>(
                  valueListenable: progress,
                  builder: (context, state, _) => _content(state),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _content(UpdateProgress state) {
    final failed = state.phase == UpdatePhase.failed;
    final installing = state.phase == UpdatePhase.installing;

    final title = failed
        ? 'Update failed'
        : installing
            ? 'Ready to install'
            : 'Downloading update';
    final icon = failed
        ? Icons.error_outline
        : installing
            ? Icons.system_update_alt
            : Icons.downloading_rounded;
    final color = failed ? AppColors.danger : AppColors.primary;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 56, color: color),
        const SizedBox(height: 16),
        Text(
          title,
          textAlign: TextAlign.center,
          style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.w700),
        ),
        if (versionName.isNotEmpty) ...[
          const SizedBox(height: 4),
          Text('SchoolGate Kiosk $versionName', style: const TextStyle(color: Colors.white54, fontSize: 13)),
        ],
        const SizedBox(height: 24),
        if (state.phase == UpdatePhase.downloading) ..._downloading(state),
        if (installing) ..._installing(),
        if (failed) ..._failed(state),
      ],
    );
  }

  List<Widget> _downloading(UpdateProgress state) {
    final fraction = state.fraction;
    final total = state.total;
    return [
      ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: LinearProgressIndicator(
          value: fraction,
          minHeight: 12,
          backgroundColor: Colors.white12,
          color: AppColors.primary,
        ),
      ),
      const SizedBox(height: 12),
      Text(
        fraction == null ? '${_megabytes(state.received)} MB downloaded' : '${(fraction * 100).floor()}%',
        style: const TextStyle(color: Colors.white, fontSize: 26, fontWeight: FontWeight.w800),
      ),
      if (total != null && total > 0)
        Text(
          '${_megabytes(state.received)} of ${_megabytes(total)} MB',
          style: const TextStyle(color: Colors.white54, fontSize: 13),
        ),
      const SizedBox(height: 8),
      const Text(
        'Keep the terminal switched on and connected.',
        textAlign: TextAlign.center,
        style: TextStyle(color: Colors.white54, fontSize: 13),
      ),
      const SizedBox(height: 24),
      TextButton(
        onPressed: onCancel,
        child: const Text('Cancel', style: TextStyle(color: Colors.white54)),
      ),
    ];
  }

  List<Widget> _installing() {
    return [
      const Text(
        'Download complete. Android will now ask to install the update: tap Install, then wait. '
        'The app restarts by itself when it is done.',
        textAlign: TextAlign.center,
        style: TextStyle(color: Colors.white70, fontSize: 15, height: 1.4),
      ),
      const SizedBox(height: 20),
      const ClipRRect(
        borderRadius: BorderRadius.all(Radius.circular(8)),
        child: LinearProgressIndicator(minHeight: 8, backgroundColor: Colors.white12, color: AppColors.primary),
      ),
      const SizedBox(height: 24),
      Wrap(
        alignment: WrapAlignment.center,
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: 12,
        runSpacing: 8,
        children: [
          TextButton(
            onPressed: onClose,
            child: const Text('Close', style: TextStyle(color: Colors.white54)),
          ),
          FilledButton(
            onPressed: onOpenInstaller,
            style: FilledButton.styleFrom(backgroundColor: AppColors.primary),
            child: const Text('Open installer again'),
          ),
        ],
      ),
    ];
  }

  List<Widget> _failed(UpdateProgress state) {
    return [
      Text(
        state.error ?? 'Something went wrong.',
        textAlign: TextAlign.center,
        style: const TextStyle(color: Colors.white70, fontSize: 15, height: 1.4),
      ),
      const SizedBox(height: 24),
      Wrap(
        alignment: WrapAlignment.center,
        crossAxisAlignment: WrapCrossAlignment.center,
        spacing: 12,
        runSpacing: 8,
        children: [
          TextButton(
            onPressed: onClose,
            child: const Text('Close', style: TextStyle(color: Colors.white54)),
          ),
          FilledButton(
            onPressed: onRetry,
            style: FilledButton.styleFrom(backgroundColor: AppColors.primary),
            child: const Text('Try again'),
          ),
        ],
      ),
    ];
  }
}
