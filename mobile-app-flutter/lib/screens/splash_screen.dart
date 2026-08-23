import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Brand intro shown once at cold start, before the login/sign-up screen -
/// the "SD" mark scales/fades in first, then "SchoolDom Scanner" slides up
/// underneath it. Runs for a fixed duration regardless of how quickly
/// AuthProvider.boot() resolves (see main.dart's _Root), so the app always
/// shows the intro rather than only when boot happens to still be running.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  )..forward();

  late final Animation<double> _logoScale = CurvedAnimation(
    parent: _controller,
    curve: const Interval(0.0, 0.55, curve: Curves.elasticOut),
  );
  late final Animation<double> _logoFade = CurvedAnimation(
    parent: _controller,
    curve: const Interval(0.0, 0.3, curve: Curves.easeOut),
  );
  late final Animation<Offset> _textSlide = Tween<Offset>(
    begin: const Offset(0, 0.4),
    end: Offset.zero,
  ).animate(CurvedAnimation(
    parent: _controller,
    curve: const Interval(0.4, 0.9, curve: Curves.easeOutCubic),
  ));
  late final Animation<double> _textFade = CurvedAnimation(
    parent: _controller,
    curve: const Interval(0.4, 0.9, curve: Curves.easeOut),
  );

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ScaleTransition(
              scale: _logoScale,
              child: FadeTransition(
                opacity: _logoFade,
                child: Container(
                  width: 96,
                  height: 96,
                  decoration: BoxDecoration(
                    color: AppColors.background,
                    borderRadius: BorderRadius.circular(24),
                    border: Border.all(color: AppColors.border, width: 2),
                  ),
                  alignment: Alignment.center,
                  child: RichText(
                    text: const TextSpan(
                      style: TextStyle(fontSize: 40, fontWeight: FontWeight.w900),
                      children: [
                        TextSpan(text: 'S', style: TextStyle(color: Color(0xFF7DD3FC))),
                        TextSpan(text: 'D', style: TextStyle(color: Color(0xFF4ADE80))),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 24),
            SlideTransition(
              position: _textSlide,
              child: FadeTransition(
                opacity: _textFade,
                child: Text(
                  'SchoolDom Scanner',
                  style: TextStyle(
                    color: AppColors.text,
                    fontSize: 24,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 0.3,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
