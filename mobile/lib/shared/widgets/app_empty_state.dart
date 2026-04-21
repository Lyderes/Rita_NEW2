import 'package:flutter/material.dart';
import 'package:rita_mobile/shared/widgets/empty_state.dart';

class AppEmptyState extends StatelessWidget {
  const AppEmptyState({
    required this.message,
    super.key,
  });

  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: EmptyState(
        title: 'Sin resultados',
        message: message,
        icon: Icons.inbox_outlined,
      ),
    );
  }
}
