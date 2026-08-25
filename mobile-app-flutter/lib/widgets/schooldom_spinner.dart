import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// A branded loading mark - "S" and "D" (SchoolDom's initials) orbiting and
/// weaving around each other on a flattened ellipse, rather than a generic
/// Material circular spinner. Used for the boot-time loading screen and the
/// Home tab's pull-to-refresh indicator.
class SchoolDomSpinner extends StatefulWidget {
  final double size;
  const SchoolDomSpinner({super.key, this.size = 44});

  @override
  State<SchoolDomSpinner> createState() => _SchoolDomSpinnerState();
}

class _SchoolDomSpinnerState extends State<SchoolDomSpinner> with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1600),
  )..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: widget.size,
      height: widget.size,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          final angle = _controller.value * 2 * math.pi;
          return Stack(
            clipBehavior: Clip.none,
            children: [
              _orbitLetter('S', angle, AppColors.primary),
              _orbitLetter('D', angle + math.pi, AppColors.secondary),
            ],
          );
        },
      ),
    );
  }

  Widget _orbitLetter(String letter, double angle, Color color) {
    final radiusX = widget.size * 0.26;
    final radiusY = widget.size * 0.16;
    final dx = radiusX * math.cos(angle);
    final dy = radiusY * math.sin(angle);
    // depth in [-1, 1]: which letter is currently "in front" of the weave,
    // used to fade/scale the far one so the motion reads as interlocking
    // rather than two letters flatly circling each other.
    final depth = math.sin(angle);
    final depthT = (depth + 1) / 2;
    final letterSize = widget.size * 0.4;
    return Positioned(
      left: widget.size / 2 + dx - letterSize / 2,
      top: widget.size / 2 + dy - letterSize / 2,
      child: Transform.scale(
        scale: 0.7 + 0.35 * depthT,
        child: Opacity(
          opacity: 0.5 + 0.5 * depthT,
          child: SizedBox(
            width: letterSize,
            height: letterSize,
            child: Center(
              child: Text(
                letter,
                style: TextStyle(fontSize: letterSize, fontWeight: FontWeight.w900, color: color, height: 1),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
