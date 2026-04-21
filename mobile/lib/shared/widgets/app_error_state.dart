import 'package:flutter/material.dart';
import 'package:rita_mobile/shared/widgets/empty_state.dart';

class AppErrorState extends StatelessWidget {
  const AppErrorState({
    required this.message,
    this.onRetry,
    super.key,
  });

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: EmptyState(
        title: 'Se produjo un error',
        message: message,
        icon: Icons.error_outline_rounded,
        actionLabel: onRetry != null ? 'Reintentar' : null,
        onActionTap: onRetry,
      ),
    );
  }
}
