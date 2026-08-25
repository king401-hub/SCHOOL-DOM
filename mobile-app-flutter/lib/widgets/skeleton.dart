import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// A single pulsing placeholder block - the pattern originally built for
/// Attendance History's loading state, pulled out here so every other
/// screen's skeleton loader (Timetable, Lesson Plans, Notes, Messages,
/// Home) can reuse the same look instead of duplicating it.
class SkeletonBlock extends StatefulWidget {
  final double height;
  final double? width;
  final BorderRadius? radius;
  const SkeletonBlock({super.key, this.height = 14, this.width, this.radius});

  @override
  State<SkeletonBlock> createState() => _SkeletonBlockState();
}

class _SkeletonBlockState extends State<SkeletonBlock> with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) => Container(
        width: widget.width,
        height: widget.height,
        decoration: BoxDecoration(
          color: AppColors.card.withValues(alpha: 0.28 + _controller.value * 0.22),
          borderRadius: widget.radius ?? BorderRadius.circular(8),
        ),
      ),
    );
  }
}

/// A single skeleton "card" - a title-width block, a subtitle-width block,
/// and a full-width row block, matching the general shape of most list
/// cards in this app (AppCard-style).
class SkeletonCard extends StatelessWidget {
  const SkeletonCard({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.card.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(16),
      ),
      child: const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SkeletonBlock(height: 16, width: 140),
          SizedBox(height: 10),
          SkeletonBlock(height: 12, width: 90),
          SizedBox(height: 16),
          SkeletonBlock(height: 44, width: double.infinity, radius: BorderRadius.all(Radius.circular(12))),
        ],
      ),
    );
  }
}

/// A repeated list of [SkeletonCard]s, filling the loading state of a
/// scrollable list-style screen.
class SkeletonList extends StatelessWidget {
  final int count;
  final EdgeInsets padding;
  const SkeletonList({
    super.key,
    this.count = 4,
    this.padding = const EdgeInsets.fromLTRB(20, 16, 20, 24),
  });

  @override
  Widget build(BuildContext context) {
    return ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: padding,
      children: [
        for (int i = 0; i < count; i++) ...[
          const SkeletonCard(),
          const SizedBox(height: 16),
        ],
      ],
    );
  }
}
