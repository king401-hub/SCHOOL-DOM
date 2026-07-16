import 'package:flutter/material.dart';

class AppColors {
  static const background = Color(0xFF0F172A);
  static const surface = Color(0xFF111C31);
  static const surfaceSoft = Color(0xFF17233A);
  static const card = Color(0xFFFFFFFF);
  static const cardSoft = Color(0xFFF8FAFC);
  static const primary = Color(0xFF2563EB);
  static const primarySoft = Color(0xFFDBEAFE);
  static const success = Color(0xFF16A34A);
  static const warning = Color(0xFFF59E0B);
  static const danger = Color(0xFFDC2626);
  static const text = Color(0xFFF8FAFC);
  static const textDark = Color(0xFF0F172A);
  static const muted = Color(0xFF94A3B8);
  static const mutedDark = Color(0xFF475569);
  static const border = Color(0xFF263449);
}

class AppTheme {
  static ThemeData get theme => ThemeData(
        colorScheme: const ColorScheme.dark(
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
