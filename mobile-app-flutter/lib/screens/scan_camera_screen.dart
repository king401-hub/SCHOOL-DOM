import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:image_picker/image_picker.dart';
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

    await _controller.stop();
    await _processScan(value);
    if (mounted) await _controller.start();
  }

  /// Lets someone scan a QR they already have as a photo (screenshot, saved
  /// image, etc.) instead of only ever pointing the live camera at it.
  Future<void> _pickFromGallery() async {
    if (_busy) return;
    await _controller.stop();
    try {
      final file = await ImagePicker()
          .pickImage(source: ImageSource.gallery, imageQuality: 90);
      if (file == null) return;

      final capture = await _controller.analyzeImage(file.path);
      final value = (capture != null && capture.barcodes.isNotEmpty)
          ? capture.barcodes.first.rawValue
          : null;
      if (value == null || value.isEmpty) {
        if (mounted) {
          setState(() {
            _bannerIsError = true;
            _banner = 'No QR code was found in that photo.';
          });
        }
        return;
      }
      await _processScan(value);
    } finally {
      if (mounted) await _controller.start();
    }
  }

  Future<void> _processScan(String value) async {
    setState(() {
      _busy = true;
      _banner = null;
    });
    final auth = context.read<AuthProvider>();

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
      if (mounted) setState(() => _busy = false);
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
            icon: const Icon(Icons.image_outlined),
            tooltip: 'Upload a photo of the QR code',
            onPressed: _pickFromGallery,
          ),
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
          const _ScanFrameOverlay(),
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

const _kFrameSize = 260.0;

/// Dims everything outside the scan area, draws corner brackets instead of a
/// plain full rectangle border, and sweeps a glowing line up and down inside
/// - the standard "camera scanner" look instead of a flat white box.
class _ScanFrameOverlay extends StatefulWidget {
  const _ScanFrameOverlay();

  @override
  State<_ScanFrameOverlay> createState() => _ScanFrameOverlayState();
}

class _ScanFrameOverlayState extends State<_ScanFrameOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1800),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        LayoutBuilder(
          builder: (context, constraints) {
            final left = (constraints.maxWidth - _kFrameSize) / 2;
            final top = (constraints.maxHeight - _kFrameSize) / 2;
            final dim = Container(color: Colors.black.withValues(alpha: 0.55));
            return Stack(
              children: [
                Positioned(top: 0, left: 0, right: 0, height: top, child: dim),
                Positioned(
                    top: top + _kFrameSize,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    child: dim),
                Positioned(top: top, left: 0, width: left, height: _kFrameSize, child: dim),
                Positioned(
                    top: top,
                    right: 0,
                    width: left,
                    height: _kFrameSize,
                    child: dim),
              ],
            );
          },
        ),
        Center(
          child: SizedBox(
            width: _kFrameSize,
            height: _kFrameSize,
            child: Stack(
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(24),
                  child: AnimatedBuilder(
                    animation: _controller,
                    builder: (context, _) => Align(
                      // Sweeps the line from the top of the frame to the
                      // bottom and back (repeat(reverse:true) ping-pongs
                      // _controller.value 0->1->0).
                      alignment: Alignment(0, -1 + _controller.value * 2),
                      child: Container(
                        height: 3,
                        margin: const EdgeInsets.symmetric(horizontal: 18),
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(2),
                          gradient: LinearGradient(
                            colors: [
                              AppColors.primary.withValues(alpha: 0),
                              AppColors.primary,
                              AppColors.primary.withValues(alpha: 0),
                            ],
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: AppColors.primary.withValues(alpha: 0.85),
                              blurRadius: 10,
                              spreadRadius: 1,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
                _CornerBracket(top: true, left: true),
                _CornerBracket(top: true, left: false),
                _CornerBracket(top: false, left: true),
                _CornerBracket(top: false, left: false),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _CornerBracket extends StatelessWidget {
  final bool top;
  final bool left;
  const _CornerBracket({required this.top, required this.left});

  static const _length = 34.0;
  static const _thickness = 5.0;

  @override
  Widget build(BuildContext context) {
    return Positioned(
      top: top ? 0 : null,
      bottom: top ? null : 0,
      left: left ? 0 : null,
      right: left ? null : 0,
      child: SizedBox(
        width: _length,
        height: _length,
        child: Stack(
          children: [
            Positioned(
              top: top ? 0 : null,
              bottom: top ? null : 0,
              left: 0,
              right: 0,
              child: Container(
                height: _thickness,
                decoration: BoxDecoration(
                  color: AppColors.primary,
                  borderRadius: BorderRadius.circular(_thickness),
                ),
              ),
            ),
            Positioned(
              left: left ? 0 : null,
              right: left ? null : 0,
              top: 0,
              bottom: 0,
              child: Container(
                width: _thickness,
                decoration: BoxDecoration(
                  color: AppColors.primary,
                  borderRadius: BorderRadius.circular(_thickness),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
