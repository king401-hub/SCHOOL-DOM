import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import '../storage/offline_queue.dart';
import '../theme/app_theme.dart';

/// Shows a persistent "Offline" strip whenever the device has no network,
/// including how many locally-queued actions (from offline_queue.dart) are
/// waiting to sync - replaces silently failing requests with an honest,
/// visible status instead.
class OfflineBanner extends StatefulWidget {
  const OfflineBanner({super.key});

  @override
  State<OfflineBanner> createState() => _OfflineBannerState();
}

class _OfflineBannerState extends State<OfflineBanner> {
  bool _offline = false;
  int _pendingCount = 0;
  StreamSubscription<List<ConnectivityResult>>? _subscription;

  @override
  void initState() {
    super.initState();
    _check();
    _subscription = Connectivity().onConnectivityChanged.listen((_) => _check());
  }

  @override
  void dispose() {
    _subscription?.cancel();
    super.dispose();
  }

  Future<void> _check() async {
    final results = await Connectivity().checkConnectivity();
    final offline = results.every((r) => r == ConnectivityResult.none);
    final queue = await readQueue();
    if (mounted) {
      setState(() {
        _offline = offline;
        _pendingCount = queue.length;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!_offline) return const SizedBox.shrink();
    final message = _pendingCount > 0
        ? "Offline — $_pendingCount change${_pendingCount == 1 ? '' : 's'} will sync when you're connected."
        : "Offline — changes will sync when you're connected.";
    return Container(
      width: double.infinity,
      color: AppColors.warning,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          const Icon(Icons.cloud_off_outlined, color: Colors.white, size: 16),
          const SizedBox(width: 8),
          Expanded(
            child: Text(message,
                style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700)),
          ),
        ],
      ),
    );
  }
}
