import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:provider/provider.dart';
import '../api/client.dart';
import '../api/scanner_endpoints.dart';
import '../auth/auth_provider.dart';
import '../theme/app_theme.dart';
import 'scan_result_screen.dart';

enum ScanMode {
  /// Admin/teacher scanning a student's ID card.
  student,

  /// Admin/teacher scanning the shared gate QR for their own attendance.
  selfStaff,

  /// Non-K12 student scanning the shared gate QR for their own attendance.
  selfStudent,
}

class ScanCameraScreen extends StatefulWidget {
  final ScanMode mode;
  const ScanCameraScreen({super.key, required this.mode});

  @override
  State<ScanCameraScreen> createState() => _ScanCameraScreenState();
}

class _ScanCameraScreenState extends State<ScanCameraScreen> {
  final MobileScannerController _controller = MobileScannerController(
    detectionSpeed: DetectionSpeed.noDuplicates,
  );
  bool _busy = false;
  String? _banner;
  bool _bannerIsError = false;

  String get _title => switch (widget.mode) {
        ScanMode.student => 'Scan Student',
        ScanMode.selfStaff || ScanMode.selfStudent => 'Scan My Attendance',
      };

  String get _hint => switch (widget.mode) {
        ScanMode.student => "Align the student's ID card inside the frame.",
        ScanMode.selfStaff ||
        ScanMode.selfStudent =>
          'Align the school attendance QR code inside the frame.',
      };

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _onDetect(BarcodeCapture capture) async {
    if (_busy) return;
    final value = capture.barcodes.isNotEmpty
        ? capture.barcodes.first.rawValue
        : null;
    if (value == null || value.isEmpty) return;

    setState(() {
      _busy = true;
      _banner = null;
    });
    final auth = context.read<AuthProvider>();
    await _controller.stop();

    try {
      final result = await _handle(value, auth);
      if (!mounted) return;
      final attendance = (result['attendance'] ?? result['data']) as Map<String, dynamic>?;
      await Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => ScanResultScreen(
            success: true,
            message: (result['message'] ?? 'Attendance recorded.').toString(),
            attendance: attendance,
            showStudentActions: widget.mode == ScanMode.student,
          ),
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _bannerIsError = true;
        _banner = e.toString();
      });
    } finally {
      if (mounted) {
        setState(() => _busy = false);
        await _controller.start();
      }
    }
  }

  Future<Map<String, dynamic>> _handle(String value, AuthProvider auth) async {
    switch (widget.mode) {
      case ScanMode.student:
        return scanStudentAttendance(value);
      case ScanMode.selfStudent:
        return scanMyAttendanceStudent(value);
      case ScanMode.selfStaff:
        Position? position;
        try {
          var permission = await Geolocator.checkPermission();
          if (permission == LocationPermission.denied) {
            permission = await Geolocator.requestPermission();
          }
          if (permission != LocationPermission.denied &&
              permission != LocationPermission.deniedForever) {
            position = await Geolocator.getCurrentPosition(
              locationSettings:
                  const LocationSettings(accuracy: LocationAccuracy.high),
            );
          }
        } catch (_) {
          // Location is best-effort here; the backend only rejects the scan
          // if it's missing entirely, which surfaces as an ApiException below.
        }
        if (position == null) {
          throw ApiException(
              'Enable location services to record your attendance.');
        }
        return scanMyAttendanceStaff(
          value,
          actorEmail: auth.email ?? '',
          latitude: position.latitude,
          longitude: position.longitude,
          accuracy: position.accuracy,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: Text(_title, style: const TextStyle(fontWeight: FontWeight.w900)),
        actions: [
          IconButton(
            icon: const Icon(Icons.flash_on),
            onPressed: () => _controller.toggleTorch(),
          ),
        ],
      ),
      body: Stack(
        fit: StackFit.expand,
        children: [
          MobileScanner(controller: _controller, onDetect: _onDetect),
          _ScanFrameOverlay(),
          Positioned(
            left: 0,
            right: 0,
            bottom: 32,
            child: Column(
              children: [
                Text(
                  _hint,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (_banner != null) ...[
                  const SizedBox(height: 16),
                  Container(
                    margin: const EdgeInsets.symmetric(horizontal: 32),
                    padding: const EdgeInsets.symmetric(
                        horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: (_bannerIsError
                              ? AppColors.danger
                              : AppColors.success)
                          .withValues(alpha: 0.92),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      _banner!,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                          color: Colors.white, fontWeight: FontWeight.w700),
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (_busy)
            Container(
              color: Colors.black54,
              child: const Center(
                child: CircularProgressIndicator(color: AppColors.primary),
              ),
            ),
        ],
      ),
    );
  }
}

class _ScanFrameOverlay extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        width: 260,
        height: 260,
        decoration: BoxDecoration(
          border: Border.all(color: Colors.white, width: 3),
          borderRadius: BorderRadius.circular(20),
        ),
      ),
    );
  }
}
