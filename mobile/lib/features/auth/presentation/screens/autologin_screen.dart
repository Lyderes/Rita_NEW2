import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rita_mobile/core/constants/routes.dart';
import 'package:rita_mobile/shared/providers/app_providers.dart';

/// Dev-only screen: auto-logs in with demo credentials.
/// Accessible at /#/autologin — only active in debug/profile builds.
class AutoLoginScreen extends ConsumerStatefulWidget {
  const AutoLoginScreen({super.key});

  @override
  ConsumerState<AutoLoginScreen> createState() => _AutoLoginScreenState();
}

class _AutoLoginScreenState extends ConsumerState<AutoLoginScreen> {
  @override
  void initState() {
    super.initState();
    if (!kReleaseMode) {
      _login();
    } else {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        Navigator.of(context).pushReplacementNamed(AppRoutes.login);
      });
    }
  }

  Future<void> _login() async {
    final ok = await ref.read(authControllerProvider.notifier).login(
          username: 'admin',
          password: 'admin123',
        );
    if (mounted) {
      Navigator.of(context).pushReplacementNamed(
        ok ? AppRoutes.home : AppRoutes.login,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: CircularProgressIndicator()),
    );
  }
}
