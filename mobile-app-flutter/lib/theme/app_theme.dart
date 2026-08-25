import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _kThemeDarkPref = 'schooldom_theme_dark';

/// Drives the app's light/dark mode. A plain ChangeNotifier singleton rather
/// than routing every color through Theme.of(context) - AppColors is used
/// as bare static fields throughout the app (many inside `const` widgets),
/// so this keeps that call-site pattern working while still making colors
/// respond live to the Settings toggle: anything that rebuilds after
/// notifyListeners() picks up the new values on its next build.
class ThemeController extends ChangeNotifier {
  ThemeController._();
  static final ThemeController instance = ThemeController._();

  Brightness _brightness = Brightness.dark;
  Brightness get brightness => _brightness;
  bool get isDark => _brightness == Brightness.dark;

  Future<void> loadPersisted() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final storedDark = prefs.getBool(_kThemeDarkPref);
      if (storedDark != null) {
        _brightness = storedDark ? Brightness.dark : Brightness.light;
      }
    } catch (_) {
      // Fall back to the default (dark) - not worth surfacing an error for.
    }
  }

  Future<void> setDark(bool dark) async {
    final next = dark ? Brightness.dark : Brightness.light;
    if (_brightness == next) return;
    _brightness = next;
    notifyListeners();
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_kThemeDarkPref, dark);
    } catch (_) {
      // Non-fatal - the toggle still works for the rest of this session.
    }
  }
}

class AppColors {
  static bool get _isDark => ThemeController.instance.isDark;

  // Outer page chrome - these actually differ between light and dark.
  static Color get background =>
      _isDark ? const Color(0xFF0F172A) : const Color(0xFFF3F6FB);
  static Color get surface =>
      _isDark ? const Color(0xFF111C31) : const Color(0xFFFFFFFF);
  static Color get surfaceSoft =>
      _isDark ? const Color(0xFF17233A) : const Color(0xFFEEF2FF);
  static Color get text =>
      _isDark ? const Color(0xFFF8FAFC) : const Color(0xFF0F172A);
  static Color get muted =>
      _isDark ? const Color(0xFF94A3B8) : const Color(0xFF64748B);
  static Color get border =>
      _isDark ? const Color(0xFF263449) : const Color(0xFFE2E8F0);

  // Cards are white with dark text in both modes already (the app's existing
  // "white card floating on the page background" look), so these stay put -
  // and stay genuinely `const`, which is why most `const` widgets elsewhere
  // that only reference these never needed to change.
  static const card = Color(0xFFFFFFFF);
  static const cardSoft = Color(0xFFF8FAFC);
  static const primary = Color(0xFF2563EB);
  static const primarySoft = Color(0xFFDBEAFE);
  // Second accent tone - used to keep a group of chips/tags (e.g. "Classes")
  // visually distinct from ones already using primary (e.g. "Subjects").
  static const secondary = Color(0xFF0D9488);
  static const secondarySoft = Color(0xFFCCFBF1);
  static const success = Color(0xFF16A34A);
  static const warning = Color(0xFFF59E0B);
  static const danger = Color(0xFFDC2626);
  static const textDark = Color(0xFF0F172A);
  static const mutedDark = Color(0xFF475569);
}

class AppTheme {
  static ThemeData get theme {
    final base = ThemeController.instance.isDark
        ? const ColorScheme.dark()
        : const ColorScheme.light();
    return ThemeData(
      colorScheme: base.copyWith(
        surface: AppColors.background,
        primary: AppColors.primary,
        onSurface: AppColors.text,
      ),
      scaffoldBackgroundColor: AppColors.background,
      fontFamily: 'Roboto',
      useMaterial3: true,
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.cardSoft,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFDBE3EF)),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Color(0xFFDBE3EF)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:
              const BorderSide(color: AppColors.primary, width: 1.5),
        ),
        hintStyle: const TextStyle(color: AppColors.mutedDark),
      ),
    );
  }
}
