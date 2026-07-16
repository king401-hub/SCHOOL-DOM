import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import '../api/endpoints.dart';
import '../theme/app_theme.dart';
import '../widgets/app_card.dart';
import '../widgets/app_screen.dart';
import '../widgets/primary_button.dart';

class AttendanceScreen extends StatefulWidget {
  const AttendanceScreen({super.key});

  @override
  State<AttendanceScreen> createState() => _AttendanceScreenState();
}

class _AttendanceScreenState extends State<AttendanceScreen> {
  bool _loading = false;
  String? _lastMessage;
  bool _lastSuccess = false;

  Future<void> _submit() async {
    setState(() {
      _loading = true;
      _lastMessage = null;
    });
    try {
      final permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        final req = await Geolocator.requestPermission();
        if (req == LocationPermission.denied ||
            req == LocationPermission.deniedForever) {
          throw Exception(
              'Location permission is required to mark attendance.');
        }
      }
      final pos = await Geolocator.getCurrentPosition(
        locationSettings:
            const LocationSettings(accuracy: LocationAccuracy.high),
      );
      await markAttendance({
        'status': 'present',
        'latitude': pos.latitude,
        'longitude': pos.longitude,
      });
      setState(() {
        _lastSuccess = true;
        _lastMessage = 'Attendance marked successfully.';
      });
    } catch (e) {
      setState(() {
        _lastSuccess = false;
        _lastMessage = e.toString();
      });
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppScreen(
      children: [
        const Text(
          'Attendance',
          style: TextStyle(
              color: AppColors.text,
              fontSize: 28,
              fontWeight: FontWeight.w900),
        ),
        AppCard(
          children: [
            const Text(
              'GPS attendance',
              style: TextStyle(
                  color: AppColors.textDark,
                  fontSize: 18,
                  fontWeight: FontWeight.w900),
            ),
            const Text(
              'Submit your current location to mark yourself present.',
              style: TextStyle(color: AppColors.mutedDark),
            ),
            if (_lastMessage != null)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: _lastSuccess
                      ? AppColors.success.withValues(alpha: 0.1)
                      : AppColors.danger.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  _lastMessage!,
                  style: TextStyle(
                    color: _lastSuccess ? AppColors.success : AppColors.danger,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            PrimaryButton(
              title: _loading ? 'Locating...' : 'Mark attendance',
              onPressed: _submit,
              loading: _loading,
            ),
          ],
        ),
      ],
    );
  }
}
