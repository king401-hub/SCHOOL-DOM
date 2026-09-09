import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Branded intro shown while _KioskRoot decides whether to route to
/// provisioning or the scanner home screen - replaces a bare spinner on a
/// plain background, so the very first thing anyone sees is recognizably
/// SchoolDom, not an unbranded loading flash. The native Android launch
/// screen (drawable/launch_background.xml) covers the instant before
/// Flutter can even draw; this picks up right after that.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _fade;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 700));
    _fade = CurvedAnimation(parent: _controller, curve: Curves.easeOut);
    _scale = Tween<double>(begin: 0.85, end: 1.0).animate(CurvedAnimation(parent: _controller, curve: Curves.easeOutBack));
    _controller.forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0B1220),
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment(0, -0.1),
            radius: 1.1,
            colors: [Color(0xFF152238), Color(0xFF0B1220)],
          ),
        ),
        child: Center(
          child: FadeTransition(
            opacity: _fade,
            child: ScaleTransition(
              scale: _scale,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  RichText(
                    text: const TextSpan(
                      style: TextStyle(fontSize: 44, fontWeight: FontWeight.w900, height: 1),
                      children: [
                        TextSpan(text: 'School', style: TextStyle(color: Colors.white)),
                        TextSpan(text: 'Dom', style: TextStyle(color: AppColors.primary)),
                      ],
                    ),
                  ),
                  const SizedBox(height: 10),
                  const Text(
                    'ATTENDANCE SCANNER',
                    style: TextStyle(color: Colors.white38, fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: 2),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
