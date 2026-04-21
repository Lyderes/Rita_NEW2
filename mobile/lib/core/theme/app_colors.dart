import 'package:flutter/material.dart';

class AppColors {
  const AppColors._();

  static const Color primary = Color(0xFF4A9B8A);
  static const Color primaryDeep = Color(0xFF387D6F);
  static const Color onPrimary = Color(0xFFFFFFFF);
  static const Color primaryContainer = Color(0xFFD6EFEC);
  static const Color onPrimaryContainer = Color(0xFF1B4D44);
 
  static const Color secondary = Color(0xFF81B29A);
  static const Color onSecondary = Color(0xFFFFFFFF);
  static const Color secondaryContainer = Color(0xFFDCEBE3);
 
  static const Color background = Color(0xFFF0F9F8);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surfaceVariant = Color(0xFFE6F4F2);
  static const Color onSurface = Color(0xFF2C3E50);
  static const Color onSurfaceMuted = Color(0xFF7F8C8D);
  static const Color border = Color(0xFFE1EDEB);
  static const Color white = Color(0xFFFFFFFF);

  static const Color success = Color(0xFF27AE60);
  static const Color warning = Color(0xFFF39C12);
  static const Color critical = Color(0xFFE74C3C);
  static const Color criticalDeep = Color(0xFFB93D2F);
  static const Color neutral = Color(0xFF8D8F9C);
  static const Color info = Color(0xFF6C7A92);

  static const Color successSoft = Color(0xFFE8F7EF);
  static const Color warningSoft = Color(0xFFFFF1DA);
  static const Color criticalSoft = Color(0xFFFDE8E5);
  static const Color neutralSoft = Color(0xFFF1F2F5);

  static const LinearGradient appBackgroundGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: <Color>[Color(0xFFF0F9F8), Color(0xFFE6F4F2), Color(0xFFF0F9F8)],
  );

  static const Color heroGradientStart = Color(0xFF4A9B8A);
  static const Color heroGradientEnd = Color(0xFF328574);
  static const Color mintSoft = Color(0xFFEAF4EE);
  static const Color mintMedium = Color(0xFFCAE0D3);
  static const Color cyanSoft = Color(0xFFE0F7F9);

  static const LinearGradient heroGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: <Color>[Color(0xFF5AB4A2), Color(0xFF388E7E)],
  );

  static const LinearGradient criticalGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: <Color>[critical, criticalDeep],
  );

  static const LinearGradient accentGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: <Color>[Color(0xFF4A9B8A), Color(0xFF81B29A)],
  );

  static const LinearGradient wellnessGoodGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: <Color>[Color(0xFF7FD6A8), Color(0xFF4FBF8A)],
  );

  static const LinearGradient wellnessWarningGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: <Color>[Color(0xFFF8CA7D), Color(0xFFF0A546)],
  );

  static const LinearGradient wellnessCriticalGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: <Color>[Color(0xFFF29A90), Color(0xFFE17266)],
  );

  static const Color shadowSoft = Color(0x122C3E50);
  static const Color shadowWarm = Color(0x104A9B8A);
  static const Color heroShadowStrong = Color(0x34296B5E);
  static const Color heroShadowSoft = Color(0x144A9B8A);
}
