import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Brand intro shown once at cold start, before the login/sign-up screen -
/// the "S" drops in from above and the "D" rises in from below, meeting in
/// the center to form the mark, then "SchoolDom Scanner" slides up
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

  // "S" falls from above the mark, "D" rises from below it, both settling
  // into place side by side - the easeOutBack curve gives them a small
  // overshoot/bounce right as they meet in the center.
  late final Animation<double> _sDrop = Tween<double>(begin: -220, end: 0).animate(
    CurvedAnimation(parent: _controller, curve: const Interval(0.0, 0.6, curve: Curves.easeOutBack)),
  );
  late final Animation<double> _dRise = Tween<double>(begin: 220, end: 0).animate(
    CurvedAnimation(parent: _controller, curve: const Interval(0.0, 0.6, curve: Curves.easeOutBack)),
  );
  late final Animation<double> _lettersFade = CurvedAnimation(
    parent: _controller,
    curve: const Interval(0.0, 0.25, curve: Curves.easeOut),
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
            Container(
              width: 96,
              height: 96,
              decoration: BoxDecoration(
                color: AppColors.background,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(color: AppColors.border, width: 2),
              ),
              clipBehavior: Clip.antiAlias,
              alignment: Alignment.center,
              child: FadeTransition(
                opacity: _lettersFade,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    AnimatedBuilder(
                      animation: _sDrop,
                      builder: (context, child) => Transform.translate(
                        offset: Offset(0, _sDrop.value),
                        child: child,
                      ),
                      child: const Text(
                        'S',
                        style: TextStyle(
                          fontSize: 40,
                          fontWeight: FontWeight.w900,
                          color: Color(0xFF7DD3FC),
                        ),
                      ),
                    ),
                    AnimatedBuilder(
                      animation: _dRise,
                      builder: (context, child) => Transform.translate(
                        offset: Offset(0, _dRise.value),
                        child: child,
                      ),
                      child: const Text(
                        'D',
                        style: TextStyle(
                          fontSize: 40,
                          fontWeight: FontWeight.w900,
                          color: Color(0xFF4ADE80),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
            SlideTransition(
              position: _textSlide,
              child: FadeTransition(
                opacity: _textFade,
                child: Text(
                  'SchoolDom App',
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
