import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class AppCard extends StatelessWidget {
  final List<Widget> children;
  final EdgeInsets padding;
  final double borderRadius;
  final bool elevated;

  const AppCard({
    super.key,
    required this.children,
    this.padding = const EdgeInsets.all(20),
    this.borderRadius = 16,
    this.elevated = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: AppColors.card,
        borderRadius: BorderRadius.circular(borderRadius),
        boxShadow: elevated
            ? const [
                BoxShadow(
                  color: Color(0x33000B26),
                  blurRadius: 32,
                  offset: Offset(0, 16),
                ),
                BoxShadow(
                  color: Color(0x1A2563EB),
                  blurRadius: 48,
                  offset: Offset(0, 0),
                ),
              ]
            : const [
                BoxShadow(
                  color: Color(0x0C000000),
                  blurRadius: 12,
                  offset: Offset(0, 2),
                ),
              ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (int i = 0; i < children.length; i++) ...[
            children[i],
            if (i < children.length - 1) const SizedBox(height: 10),
          ]
        ],
      ),
    );
  }
}
