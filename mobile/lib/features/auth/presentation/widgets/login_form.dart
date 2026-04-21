import 'package:flutter/material.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';
import 'package:rita_mobile/core/theme/app_spacing.dart';

class LoginForm extends StatelessWidget {
  const LoginForm({
    required this.usernameController,
    required this.passwordController,
    required this.isLoading,
    required this.onSubmit,
    required this.rememberMe,
    required this.onRememberMeChanged,
    required this.onForgotPassword,
    super.key,
  });

  final TextEditingController usernameController;
  final TextEditingController passwordController;
  final bool isLoading;
  final VoidCallback onSubmit;
  final bool rememberMe;
  final ValueChanged<bool?> onRememberMeChanged;
  final VoidCallback onForgotPassword;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Username pill input
        Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(28),
            border: Border.all(color: AppColors.border, width: 1.5),
          ),
          child: TextField(
            controller: usernameController,
            decoration: const InputDecoration(
              contentPadding: EdgeInsets.symmetric(
                horizontal: AppSpacing.lg,
                vertical: AppSpacing.md,
              ),
              labelText: 'Usuario',
              hintText: 'Introduce tu usuario',
              prefixIcon: Icon(Icons.person_outline_rounded),
              border: InputBorder.none,
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        // Password pill input
        Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(28),
            border: Border.all(color: AppColors.border, width: 1.5),
          ),
          child: TextField(
            controller: passwordController,
            obscureText: true,
            decoration: const InputDecoration(
              contentPadding: EdgeInsets.symmetric(
                horizontal: AppSpacing.lg,
                vertical: AppSpacing.md,
              ),
              labelText: 'Contraseña',
              hintText: 'Introduce tu contraseña',
              prefixIcon: Icon(Icons.lock_outline_rounded),
              border: InputBorder.none,
            ),
            onSubmitted: (_) => onSubmit(),
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Checkbox(
                  value: rememberMe,
                  onChanged: onRememberMeChanged,
                  activeColor: AppColors.primary,
                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
                ),
                const Text(
                  'Recordar',
                  style: TextStyle(
                    color: AppColors.onSurfaceMuted,
                    fontWeight: FontWeight.w500,
                    fontSize: 14,
                  ),
                ),
              ],
            ),
            TextButton(
              onPressed: isLoading ? null : onForgotPassword,
              style: TextButton.styleFrom(
                visualDensity: VisualDensity.compact,
                padding: EdgeInsets.zero,
              ),
              child: const Text(
                '¿Olvidaste el acceso?',
                style: TextStyle(
                  color: AppColors.primary,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        // Primary button
        SizedBox(
          height: 54,
          child: FilledButton(
            onPressed: isLoading ? null : onSubmit,
            style: FilledButton.styleFrom(
              backgroundColor: AppColors.primary,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(28),
              ),
            ),
            child: Text(
              isLoading ? 'Entrando...' : 'Entrar a RITA',
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ),
        ),
      ],
    );
  }
}
