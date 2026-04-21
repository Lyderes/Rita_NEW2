import 'package:flutter/material.dart';
import 'package:rita_mobile/core/theme/app_colors.dart';

class OperationalBadges {
  static Widget severityChip(BuildContext context, String severity) {
    final normalized = severity.toLowerCase();
    final color = switch (normalized) {
      'critical' => AppColors.critical,
      'high' => AppColors.criticalDeep,
      'medium' => AppColors.warning,
      'low' => AppColors.success,
      _ => AppColors.onSurfaceMuted,
    };

    final bgColor = switch (normalized) {
      'critical' => AppColors.criticalSoft,
      'high' => AppColors.criticalSoft,
      'medium' => AppColors.warningSoft,
      'low' => AppColors.successSoft,
      _ => AppColors.neutralSoft,
    };

    return _chip(
      context,
      label: _humanize(severity),
      color: color,
      bgColor: bgColor,
      icon: Icons.flag_circle_rounded,
    );
  }

  static Widget statusChip(BuildContext context, String status) {
    final normalized = status.toLowerCase();
    final color = switch (normalized) {
      'new' || 'pending' || 'open' => AppColors.warning,
      'acknowledged' => AppColors.secondary,
      'resolved' || 'closed' => AppColors.success,
      _ => AppColors.onSurfaceMuted,
    };

    final bgColor = switch (normalized) {
      'new' || 'pending' || 'open' => AppColors.warningSoft,
      'acknowledged' => AppColors.secondaryContainer,
      'resolved' || 'closed' => AppColors.successSoft,
      _ => AppColors.neutralSoft,
    };

    return _chip(
      context,
      label: _humanize(status),
      color: color,
      bgColor: bgColor,
      icon: Icons.radio_button_checked_rounded,
    );
  }

  static Color severityStripeColor(String severity) {
    final normalized = severity.toLowerCase();
    return switch (normalized) {
      'critical' => AppColors.critical,
      'high' => AppColors.criticalDeep,
      'medium' => AppColors.warning,
      'low' => AppColors.success,
      _ => AppColors.onSurfaceMuted,
    };
  }

  static Widget _chip(
    BuildContext context, {
    required String label,
    required Color color,
    required Color bgColor,
    required IconData icon,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.1)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Text(
            label.toUpperCase(),
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: color,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.5,
                  fontSize: 10,
                ),
          ),
        ],
      ),
    );
  }

  static String _humanize(String raw) {
    final value = raw.replaceAll('_', ' ').trim();
    if (value.isEmpty) {
      return '-';
    }
    return value[0].toUpperCase() + value.substring(1).toLowerCase();
  }
}
