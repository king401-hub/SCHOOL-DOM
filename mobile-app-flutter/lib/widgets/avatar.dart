import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

/// Shows a person's profile picture when one is set, falling back to their
/// initials on a tinted circle otherwise (also the fallback if the image
/// URL 404s or fails to load) - used anywhere a contact is shown by name
/// (conversation list, new-message picker, chat thread header).
class Avatar extends StatelessWidget {
  final String name;
  final String? pictureUrl;
  final double size;
  const Avatar({super.key, required this.name, this.pictureUrl, this.size = 44});

  String get _initials {
    final trimmed = name.trim();
    if (trimmed.isEmpty) return '?';
    return trimmed.split(RegExp(r'\s+')).take(2).map((s) => s[0]).join().toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    final hasPicture = (pictureUrl ?? '').isNotEmpty;
    return ClipOval(
      child: Container(
        width: size,
        height: size,
        color: AppColors.primarySoft,
        alignment: Alignment.center,
        child: hasPicture
            ? Image.network(
                pictureUrl!,
                width: size,
                height: size,
                fit: BoxFit.cover,
                errorBuilder: (_, _, _) => Text(
                  _initials,
                  style: TextStyle(
                      color: AppColors.primary, fontWeight: FontWeight.w900, fontSize: size * 0.36),
                ),
              )
            : Text(
                _initials,
                style: TextStyle(color: AppColors.primary, fontWeight: FontWeight.w900, fontSize: size * 0.36),
              ),
      ),
    );
  }
}
