import 'package:flutter/material.dart';

class AppColors {
  AppColors._();
  static const primary = Color(0xFF0F172A); // deep navy
  static const accent = Color(0xFF22D3EE); // cyan
  static const background = Color(0xFFFFFFFF);
  static const surfaceAlt = Color(0xFFF8FAFC);
  static const border = Color(0xFFE2E8F0);
  static const textMuted = Color(0xFF475569); // 7.5:1 on white
  static const danger = Color(0xFFB91C1C);
  static const success = Color(0xFF047857);
}

class AppSpacing {
  AppSpacing._();
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 16.0;
  static const lg = 24.0;
  static const xl = 32.0;
}

ThemeData buildTheme() {
  const scheme = ColorScheme(
    brightness: Brightness.light,
    primary: AppColors.primary,
    onPrimary: Colors.white,
    secondary: AppColors.accent,
    onSecondary: AppColors.primary,
    error: AppColors.danger,
    onError: Colors.white,
    surface: AppColors.background,
    onSurface: AppColors.primary,
    outline: AppColors.border,
    surfaceContainerHighest: AppColors.surfaceAlt,
  );
  final radius = BorderRadius.circular(12);
  OutlineInputBorder border(Color c, [double w = 1]) => OutlineInputBorder(borderRadius: radius, borderSide: BorderSide(color: c, width: w));
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: AppColors.background,
    appBarTheme: const AppBarTheme(backgroundColor: AppColors.background, foregroundColor: AppColors.primary, elevation: 0, scrolledUnderElevation: 0, centerTitle: false),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: AppColors.surfaceAlt,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: border(AppColors.border),
      enabledBorder: border(AppColors.border),
      focusedBorder: border(AppColors.primary, 1.6),
      errorBorder: border(AppColors.danger),
      focusedErrorBorder: border(AppColors.danger, 1.6),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size.fromHeight(52),
        shape: RoundedRectangleBorder(borderRadius: radius),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size.fromHeight(52),
        side: const BorderSide(color: AppColors.border),
        shape: RoundedRectangleBorder(borderRadius: radius),
        textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
      ),
    ),
    textButtonTheme: TextButtonThemeData(style: TextButton.styleFrom(foregroundColor: AppColors.primary, textStyle: const TextStyle(fontWeight: FontWeight.w600))),
    cardTheme: CardThemeData(
      color: AppColors.background,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: const BorderSide(color: AppColors.border)),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: AppColors.background,
      indicatorColor: AppColors.accent.withValues(alpha: 0.25),
      labelTextStyle: WidgetStateProperty.all(const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
    ),
    snackBarTheme: SnackBarThemeData(behavior: SnackBarBehavior.floating, shape: RoundedRectangleBorder(borderRadius: radius)),
    textTheme: Typography.blackMountainView.apply(bodyColor: AppColors.primary, displayColor: AppColors.primary),
  );
}
