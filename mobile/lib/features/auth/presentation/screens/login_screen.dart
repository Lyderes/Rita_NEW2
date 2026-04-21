import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:rita_mobile/core/constants/routes.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';
import 'package:rita_mobile/features/auth/data/state/auth_state.dart';
import 'package:rita_mobile/features/auth/presentation/widgets/login_form.dart';
import 'package:rita_mobile/shared/providers/app_providers.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _rememberMe = false;

  @override
  void initState() {
    super.initState();
    _loadSavedUsername();
  }

  Future<void> _loadSavedUsername() async {
    final prefs = await SharedPreferences.getInstance();
    final savedUsername = prefs.getString('saved_username');
    if (savedUsername != null && savedUsername.isNotEmpty) {
      if (mounted) {
        setState(() {
          _usernameController.text = savedUsername;
          _rememberMe = true;
        });
      }
    }
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final username = _usernameController.text.trim();
    final password = _passwordController.text;
    if (username.isEmpty || password.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Usuario y contraseña requeridos')),
      );
      return;
    }

    final ok = await ref.read(authControllerProvider.notifier).login(
          username: username,
          password: password,
        );

    if (ok && mounted) {
      final prefs = await SharedPreferences.getInstance();
      if (_rememberMe) {
        await prefs.setString('saved_username', username);
      } else {
        await prefs.remove('saved_username');
      }
      if (mounted) {
        Navigator.of(context).pushReplacementNamed(AppRoutes.home);
      }
    }
  }

  void _showRecoveryBottomSheet() {
    showModalBottomSheet(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (context) => Container(
        decoration: const BoxDecoration(
          color: AppColors.white,
          borderRadius: BorderRadius.vertical(top: Radius.circular(32)),
        ),
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: AppColors.border,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 24),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppColors.secondary.withValues(alpha: 0.1),
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.support_agent_rounded,
                color: AppColors.secondary,
                size: 32,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Recuperar Acceso',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                    color: AppColors.onSurface,
                  ),
            ),
            const SizedBox(height: 12),
            Text(
              'Si has olvidado tus datos o no puedes entrar, no te preocupes. Contacta con tu administrador del centro o con el equipo de soporte de RITA.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: AppColors.onSurfaceMuted,
                    height: 1.5,
                  ),
            ),
            const SizedBox(height: 32),
            SizedBox(
              width: double.infinity,
              height: 54,
              child: FilledButton(
                onPressed: () => Navigator.pop(context),
                style: FilledButton.styleFrom(
                  backgroundColor: AppColors.primary,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(28),
                  ),
                ),
                child: const Text('Entendido'),
              ),
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authControllerProvider);
    final textTheme = Theme.of(context).textTheme;

    ref.listen<AuthState>(authControllerProvider, (_, next) {
      final errorMessage = next.errorMessage;
      if (errorMessage != null && errorMessage.isNotEmpty) {
        ScaffoldMessenger.of(context)
          ..hideCurrentSnackBar()
          ..showSnackBar(SnackBar(content: Text(errorMessage)));
      }
    });

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AppColors.appBackgroundGradient),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(AppSpacing.xl),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 500),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    const SizedBox(height: 60),
                    // Logo/Brand Section
                    Column(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(20),
                          decoration: BoxDecoration(
                            color: AppColors.white,
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(
                                color: AppColors.secondary.withValues(alpha: 0.1),
                                blurRadius: 40,
                                spreadRadius: 5,
                              ),
                            ],
                          ),
                          child: const Icon(
                            Icons.bubble_chart_rounded,
                            color: AppColors.secondary,
                            size: 48,
                          ),
                        ),
                        const SizedBox(height: 24),
                        Text(
                          'RITA',
                          textAlign: TextAlign.center,
                          style: textTheme.displaySmall?.copyWith(
                            color: AppColors.onSurface,
                            fontWeight: FontWeight.w900,
                            letterSpacing: -1,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Cuidado humano e inteligente',
                          textAlign: TextAlign.center,
                          style: textTheme.bodyLarge?.copyWith(
                            color: AppColors.onSurfaceMuted,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 48),
                    // Login Panel
                    Container(
                      decoration: BoxDecoration(
                        color: AppColors.white,
                        borderRadius: BorderRadius.circular(32),
                        boxShadow: const <BoxShadow>[
                          BoxShadow(
                            color: Color(0x0A000000),
                            blurRadius: 30,
                            offset: Offset(0, 10),
                          ),
                        ],
                      ),
                      padding: const EdgeInsets.all(AppSpacing.xl),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: <Widget>[
                          Text(
                            'Bienvenido de nuevo',
                            style: textTheme.titleLarge?.copyWith(
                              fontWeight: FontWeight.w800,
                              color: AppColors.onSurface,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Ingresa tus credenciales para continuar',
                            style: textTheme.bodyMedium?.copyWith(
                              color: AppColors.onSurfaceMuted,
                            ),
                          ),
                          const SizedBox(height: AppSpacing.xl),
                          LoginForm(
                            usernameController: _usernameController,
                            passwordController: _passwordController,
                            isLoading: authState.isLoading,
                            onSubmit: _submit,
                            rememberMe: _rememberMe,
                            onRememberMeChanged: (val) => setState(() => _rememberMe = val ?? false),
                            onForgotPassword: _showRecoveryBottomSheet,
                          ),
                          const SizedBox(height: AppSpacing.lg),
                          TextButton(
                            onPressed: authState.isLoading
                                ? null
                                : () => Navigator.of(context)
                                    .pushReplacementNamed(AppRoutes.register),
                            child: RichText(
                              text: TextSpan(
                                style: textTheme.bodyMedium?.copyWith(color: AppColors.onSurfaceMuted),
                                children: [
                                  const TextSpan(text: '¿No tienes cuenta? '),
                                  TextSpan(
                                    text: 'Registrate',
                                    style: TextStyle(
                                      color: AppColors.primary,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 40),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
