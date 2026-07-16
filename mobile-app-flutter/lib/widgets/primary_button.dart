import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

enum ButtonTone { primary, ghost, danger }

class PrimaryButton extends StatelessWidget {
  final String title;
  final VoidCallback? onPressed;
  final bool loading;
  final ButtonTone tone;

  const PrimaryButton({
    super.key,
    required this.title,
    this.onPressed,
    this.loading = false,
    this.tone = ButtonTone.primary,
  });

  @override
  Widget build(BuildContext context) {
    final isPrimary = tone == ButtonTone.primary;
    final isDanger = tone == ButtonTone.danger;

    return SizedBox(
      width: double.infinity,
      height: 50,
      child: ElevatedButton(
        onPressed: loading ? null : onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: isPrimary
              ? AppColors.primary
              : isDanger
                  ? AppColors.danger
                  : Colors.transparent,
          foregroundColor:
              isPrimary || isDanger ? Colors.white : AppColors.primary,
          elevation: isPrimary ? 2 : 0,
          side: tone == ButtonTone.ghost
              ? const BorderSide(color: AppColors.primary)
              : null,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        child: loading
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              )
            : Text(
                title,
                style: const TextStyle(
                    fontWeight: FontWeight.w800, fontSize: 15),
              ),
      ),
    );
  }
}
