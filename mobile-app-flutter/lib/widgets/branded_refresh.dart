import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'schooldom_spinner.dart';

/// Pull-to-refresh with SchoolDom's own branded mark (two orbiting "S"/"D"
/// letters behind frosted glass, centered on screen) instead of the generic
/// Material spinner. Keeps [RefreshIndicator] underneath purely for its
/// battle-tested drag-gesture detection - its own indicator is fully
/// transparent, and [showSpinner] (driven by the screen's own loading state)
/// controls the actual visible mark.
class BrandedRefresh extends StatelessWidget {
  final Future<void> Function() onRefresh;
  final bool showSpinner;
  final Widget child;
  const BrandedRefresh({super.key, required this.onRefresh, required this.showSpinner, required this.child});

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        RefreshIndicator(
          onRefresh: onRefresh,
          color: Colors.transparent,
          backgroundColor: Colors.transparent,
          elevation: 0,
          displacement: 120,
          child: child,
        ),
        if (showSpinner)
          Positioned.fill(
            child: Center(
              child: ClipRRect(
                borderRadius: BorderRadius.circular(999),
                child: BackdropFilter(
                  filter: ui.ImageFilter.blur(sigmaX: 14, sigmaY: 14),
                  child: Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.14),
                      shape: BoxShape.circle,
                      border: Border.all(color: Colors.white.withValues(alpha: 0.35), width: 1.2),
                      boxShadow: [
                        BoxShadow(color: Colors.black.withValues(alpha: 0.12), blurRadius: 20, offset: const Offset(0, 8)),
                      ],
                    ),
                    child: const SchoolDomSpinner(size: 40),
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}
