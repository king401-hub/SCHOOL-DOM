import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import 'branded_refresh.dart';

class AppScreen extends StatelessWidget {
  final List<Widget> children;
  final Widget? refreshIndicator;
  final EdgeInsets padding;
  final bool refreshing;

  const AppScreen({
    super.key,
    required this.children,
    this.refreshIndicator,
    this.padding =
        const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
    this.refreshing = false,
  });

  @override
  Widget build(BuildContext context) {
    Widget body = ListView(
      padding: padding,
      children: [
        for (final child in children) ...[
          child,
          const SizedBox(height: 16),
        ]
      ],
    );

    if (refreshIndicator != null) {
      body = BrandedRefresh(
        onRefresh: () async {},
        showSpinner: refreshing,
        child: body,
      );
    }

    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(child: body),
    );
  }
}

/// Convenience wrapper that handles pull-to-refresh via a callback.
class RefreshableScreen extends StatelessWidget {
  final List<Widget> children;
  final Future<void> Function() onRefresh;
  final EdgeInsets padding;
  final bool refreshing;

  const RefreshableScreen({
    super.key,
    required this.children,
    required this.onRefresh,
    this.padding =
        const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
    this.refreshing = false,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: SafeArea(
        child: BrandedRefresh(
          onRefresh: onRefresh,
          showSpinner: refreshing,
          child: ListView(
            padding: padding,
            children: [
              for (final child in children) ...[
                child,
                const SizedBox(height: 16),
              ]
            ],
          ),
        ),
      ),
    );
  }
}
