import 'package:flutter/material.dart';
import 'package:rita_mobile/core/constants/routes.dart';
import 'package:rita_mobile/features/auth/presentation/screens/autologin_screen.dart';
import 'package:rita_mobile/features/alerts/presentation/screens/alert_detail_screen.dart';
import 'package:rita_mobile/features/caregiver/presentation/screens/caregiver_history_screen.dart';
import 'package:rita_mobile/features/caregiver/presentation/screens/caregiver_home_screen.dart';
import 'package:rita_mobile/features/caregiver/presentation/screens/caregiver_profile_screen.dart';
import 'package:rita_mobile/features/auth/presentation/screens/register_screen.dart';
import 'package:rita_mobile/features/alerts/presentation/screens/alerts_screen.dart';
import 'package:rita_mobile/features/auth/presentation/screens/login_screen.dart';
import 'package:rita_mobile/features/users/presentation/screens/baseline_profile_screen.dart';
import 'package:rita_mobile/features/users/presentation/screens/user_detail_screen.dart';
import 'package:rita_mobile/features/users/presentation/screens/persona_profile_edit_screen.dart';
import 'package:rita_mobile/features/users/data/models/user_read.dart';


class AppRouter {
  static Route<dynamic> generateRoute(RouteSettings settings) {
    switch (settings.name) {
      // Auth routes
      case '/autologin':
        return MaterialPageRoute<void>(
          settings: settings,
          builder: (_) => const AutoLoginScreen(),
        );
      case AppRoutes.login:
        return MaterialPageRoute<void>(
          settings: settings,
          builder: (_) => const LoginScreen(),
        );
      case AppRoutes.register:
        return MaterialPageRoute<void>(
          settings: settings,
          builder: (_) => const RegisterScreen(),
        );
      
      // Primary caregiver experience (4 main tabs)
      case AppRoutes.home:
        return MaterialPageRoute<void>(
          settings: settings,
          builder: (_) => const CaregiverHomeScreen(),
        );
      case AppRoutes.alerts:
        return MaterialPageRoute<void>(
          settings: settings,
          builder: (_) => const AlertsScreen(),
        );
      case AppRoutes.history:
        return MaterialPageRoute<void>(
          settings: settings,
          builder: (_) => const CaregiverHistoryScreen(),
        );
      case AppRoutes.profile:
        return MaterialPageRoute<void>(
          settings: settings,
          builder: (_) => const CaregiverProfileScreen(),
        );
      
      // Detail routes within primary tabs
      case AppRoutes.alertDetail:
        final alertId = settings.arguments as int?;
        if (alertId == null) {
          return MaterialPageRoute<void>(
            settings: settings,
            builder: (_) => const AlertsScreen(),
          );
        }
        return MaterialPageRoute<void>(
          settings: settings,
          builder: (_) => AlertDetailScreen(alertId: alertId),
        );
      case AppRoutes.userDetail:
        final userId = settings.arguments as int?;
        if (userId == null) {
          return MaterialPageRoute<void>(
            settings: settings,
            builder: (_) => const CaregiverProfileScreen(),
          );
        }
        return MaterialPageRoute<void>(
          settings: settings,
          builder: (_) => UserDetailScreen(userId: userId),
        );
      case AppRoutes.userBaseline:
        final userId = settings.arguments as int?;
        if (userId == null) {
          return MaterialPageRoute<void>(
            settings: settings,
            builder: (_) => const CaregiverHomeScreen(),
          );
        }
        return MaterialPageRoute<void>(
          settings: settings,
          builder: (_) => BaselineProfileScreen(userId: userId),
        );
      case AppRoutes.editPersona:
        final user = settings.arguments as UserRead?;
        if (user == null) {
          return MaterialPageRoute<void>(
            settings: settings,
            builder: (_) => const CaregiverHomeScreen(),
          );
        }
        return MaterialPageRoute<void>(
          settings: settings,
          builder: (_) => PersonaProfileEditScreen(user: user),
        );

      // Default fallback
      default:
        return MaterialPageRoute<void>(builder: (_) => const LoginScreen());
    }
  }
}
