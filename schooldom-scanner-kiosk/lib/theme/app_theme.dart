import 'package:flutter/material.dart';

/// Fixed palette - the kiosk terminal has no light/dark toggle (it is
/// always the same on-site attendance screen), unlike the main SchoolDom
/// app's theme-aware AppColors.
class AppColors {
  static const background = Color(0xFFF3F6FB);
  static const surface = Color(0xFFFFFFFF);
  static const text = Color(0xFF0F172A);
  static const muted = Color(0xFF64748B);
  static const border = Color(0xFFE2E8F0);

  static const primary = Color(0xFF2563EB);
  static const primarySoft = Color(0xFFDBEAFE);
  static const success = Color(0xFF16A34A);
  static const warning = Color(0xFFF59E0B);
  static const danger = Color(0xFFDC2626);
}
